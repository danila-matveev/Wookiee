# Reporter V4 — Design Spec

**Дата:** 2026-03-28
**Статус:** Approved
**Аудит-основа:** [reporting-system-audit.md](2026-03-27-reporting-system-audit.md)

---

## 1. Проблема

V3 система отчётов сломана с ~20 марта 2026:
- **4 LLM вызова** на отчёт = 4 точки отказа (3 аналитика + 1 compiler)
- **12 мёртвых агентов** из 25 — шум в кодовой базе
- **LLM ходит за данными** через tool calls — детерминированные SQL запросы через недетерминированный LLM
- **SQLite state** теряется при пересборке контейнера
- **Telegram спам**: ошибки prompt-tuner каждые 5 минут, повторные уведомления, дубли data-ready
- **Дублирование**: один отчёт = несколько Notion страниц + несколько Telegram сообщений

V2 была последней рабочей системой. V4 берёт лучшее из V2 (качество аналитики) и строит надёжную архитектуру.

---

## 2. Архитектура: Collect → Analyze → Format

```
Scheduler (3 cron jobs)
  │
  ▼
Conductor: Gate Check → Determine Schedule → Pipeline → Deliver → Log
  │
  ▼
Pipeline:
  ┌─────────────────┐     ┌──────────────┐     ┌─────────────┐     ┌───────────┐     ┌──────────┐
  │ DataCollector    │ ──► │ LLM Analyst  │ ──► │ Formatter   │ ──► │ Validator │ ──► │ Delivery │
  │ (Python/SQL)    │     │ (1 вызов)    │     │ (Jinja2)    │     │           │     │          │
  │ deterministic   │     │ structured   │     │ deterministic│     │           │     │ upsert   │
  └─────────────────┘     └──────────────┘     └─────────────┘     └───────────┘     └──────────┘
```

**Принципы:**
- **1 LLM вызов** на отчёт вместо 4
- **Данные собираются Python/SQL** — детерминированно, без tool calls
- **Шаблоны Jinja2** — гарантированная структура, LLM только даёт инсайты
- **Upsert everywhere** — один отчёт = один row в Supabase = одна Notion страница = одно Telegram сообщение
- **Supabase state** вместо SQLite — не теряется при rebuild

---

## 3. ReportScope — фильтрация через весь пайплайн

```python
@dataclass
class ReportScope:
    report_type: ReportType          # FINANCIAL_DAILY, MARKETING_WEEKLY, etc.
    period_from: date                # начало периода
    period_to: date                  # конец периода
    comparison_from: date            # начало периода сравнения
    comparison_to: date              # конец периода сравнения
    marketplace: str = "all"         # "wb", "ozon", "all"
    legal_entity: str = "all"       # "IP", "OOO", "all"
    model: str | None = None         # фильтр по модели (e.g. "wendy")
    article: str | None = None       # фильтр по артикулу

    @property
    def scope_hash(self) -> str:
        """Deterministic hash for dedup: date + type + filters."""
        parts = [
            self.period_from.isoformat(),
            self.period_to.isoformat(),
            self.report_type.value,
            self.marketplace,
            self.legal_entity,
            self.model or "",
            self.article or "",
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]
```

Scope передаётся через весь пайплайн: Collector → Analyst → Formatter → Delivery. Это позволяет генерировать отчёт за любой период, по любому маркетплейсу, модели или артикулу.

---

## 4. Типы отчётов

| ReportType | Расписание | Collector | Описание |
|---|---|---|---|
| `FINANCIAL_DAILY` | Ежедневно | FinancialCollector | Финансовый дневной отчёт |
| `FINANCIAL_WEEKLY` | Понедельник | FinancialCollector | Финансовый недельный отчёт |
| `FINANCIAL_MONTHLY` | 1-й понедельник месяца | FinancialCollector | Финансовый месячный отчёт |
| `MARKETING_WEEKLY` | Понедельник | MarketingCollector | Маркетинговый недельный |
| `MARKETING_MONTHLY` | 1-й понедельник месяца | MarketingCollector | Маркетинговый месячный |
| `FUNNEL_WEEKLY` | Понедельник | FunnelCollector | Воронка недельная |
| `FUNNEL_MONTHLY` | 1-й понедельник месяца | FunnelCollector | Воронка месячная |

**Out of scope:** ДДС (Finolog) отчёт остаётся отдельной системой (`agents/finolog_categorizer/`). Price analysis — будущее расширение.

---

## 5. DataCollector — детерминированный сбор данных

### 5.1 Принцип "жадного" сбора

Collector собирает ВСЕ слои данных заранее, чтобы LLM не нужны были tool calls:

```
Layer 1: Top-level metrics (revenue, orders, margin, DRR, buyout %)
Layer 2: By marketplace (WB vs OZON breakdown)
Layer 3: By model (TOP-10 моделей по выручке + worst performers)
Layer 4: By article (TOP articles внутри моделей)
Layer 5: Trends (7-day rolling, week-over-week, month-over-month)
Layer 6: Context (stock levels, ad campaigns active, price changes)
```

### 5.2 Три коллектора

**FinancialCollector** — переиспользует SQL из `shared/data_layer/`:
- `finance.py`: get_wb_finance, get_ozon_finance, get_wb_by_model
- `advertising.py`: get_wb_external_ad_breakdown, get_wb_campaign_stats
- `inventory.py`: get_wb_avg_stock, get_wb_turnover_by_model
- `time_series.py`: get_wb_daily_series, get_ozon_daily_series
- `pricing.py`: get_wb_price_dynamics

**MarketingCollector**:
- `advertising.py`: campaign stats, DRR breakdown, CTR/CPC
- `traffic.py`: get_wb_traffic, get_ozon_traffic
- `funnel_seo.py`: organic vs paid split
- `time_series.py`: ad spend trends

**FunnelCollector**:
- `funnel_seo.py`: get_wb_organic_funnel, get_wb_seo_metrics
- `traffic.py`: conversion rates by stage
- `article.py`: article-level funnel performance

### 5.3 Выходной формат

Collector возвращает `CollectedData` — типизированный Pydantic model:

```python
class CollectedData(BaseModel):
    scope: dict                    # serialized ReportScope
    collected_at: datetime
    metrics: TopLevelMetrics       # revenue, orders, margin, etc.
    marketplace_breakdown: list[MarketplaceMetrics]
    model_breakdown: list[ModelMetrics]  # TOP-10 + worst
    trends: TrendData              # rolling averages, deltas
    context: ContextData           # stock, campaigns, price changes
    warnings: list[str]            # data quality issues
```

### 5.4 Правила из AGENTS.md

- GROUP BY по модели — **ВСЕГДА с LOWER()**: `LOWER(SPLIT_PART(article, '/', 1))`
- Процентные метрики — **ТОЛЬКО средневзвешенные**: `sum(spp_amount) / sum(revenue) * 100`
- Выкуп % — **лаговый** (3-21 день), только информационный
- ДРР — **с разбивкой** внутренняя/внешняя

---

## 6. LLM Analyst — единственная точка вызова LLM

### 6.1 Один вызов, structured output

```python
async def analyze(
    collected_data: CollectedData,
    scope: ReportScope,
    playbook_rules: list[PlaybookRule],
) -> ReportInsights:
    prompt = build_prompt(collected_data, scope, playbook_rules)
    response = await openrouter_call(
        model=MODEL_PRIMARY,
        messages=[{"role": "user", "content": prompt}],
        response_format=ReportInsights,  # Pydantic structured output
    )
    return response
```

### 6.2 Модели (через OpenRouter)

| Роль | Модель | Цена (input/output per 1M) | Использование |
|---|---|---|---|
| PRIMARY | `google/gemini-2.5-flash` | $0.15 / $0.60 | Основной анализ |
| FALLBACK_1 | `google/gemini-2.5-pro` | TBD | При ошибке PRIMARY |
| FALLBACK_2 | `openrouter/free` | $0 | Last resort |

**Стратегия ошибок:** PRIMARY → retry 1x (delay 5s) → FALLBACK_1 → FALLBACK_2

### 6.3 Pydantic Schema — ReportInsights

```python
class MetricChange(BaseModel):
    metric: str                    # "revenue", "margin_pct", "drr"
    current: float
    previous: float
    delta_pct: float
    direction: Literal["up", "down", "flat"]

class RootCause(BaseModel):
    description: str               # "Модель Wendy: падение маржи на 8% из-за роста ДРР"
    confidence: float              # 0.0 - 1.0
    evidence: list[str]            # ["ДРР Wendy: 18% → 26%", "CTR упал с 3.2% до 2.1%"]
    recommendation: str            # "Проверить эффективность кампании K-123"

class SectionInsight(BaseModel):
    section_id: int                # 0-12
    title: str                     # "Маржинальный анализ"
    summary: str                   # 2-3 предложения
    key_changes: list[MetricChange]
    root_causes: list[RootCause]
    anomalies: list[str]           # необычные наблюдения

class DiscoveredPattern(BaseModel):
    """Новый паттерн, обнаруженный LLM, для review."""
    pattern: str                   # "Когда ДРР > 20% и CTR < 2%, маржа падает > 5%"
    evidence: str                  # конкретные данные
    suggested_action: str          # рекомендация
    confidence: float

class ReportInsights(BaseModel):
    executive_summary: str         # 3-5 предложений для Telegram
    sections: list[SectionInsight]
    discovered_patterns: list[DiscoveredPattern]
    overall_confidence: float      # 0.0-1.0, используется в footer
    analysis_notes: list[str]      # внутренние заметки LLM
```

### 6.4 Промпт-структура

Промпт для LLM строится из 4 блоков:
1. **System context**: роль аналитика, бренд Wookiee, каналы WB+OZON
2. **Data payload**: JSON из CollectedData — все метрики, тренды, контекст
3. **Playbook rules**: активные правила из Supabase — направляют анализ
4. **Output instructions**: "верни ReportInsights JSON, заполни все секции"

Отдельный .md файл промпта для каждого типа отчёта:
- `prompts/financial_daily.md`
- `prompts/financial_weekly.md`
- `prompts/financial_monthly.md`
- `prompts/marketing_weekly.md`
- `prompts/marketing_monthly.md`
- `prompts/funnel_weekly.md`
- `prompts/funnel_monthly.md`

---

## 7. Hybrid Playbook — ручные правила + LLM-паттерны

### 7.1 Supabase таблица `analytics_rules`

```sql
CREATE TABLE analytics_rules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    rule_text TEXT NOT NULL,           -- "Если ДРР > 20%, проверить CTR и CPC"
    category TEXT NOT NULL,            -- "margin", "advertising", "funnel"
    source TEXT NOT NULL,              -- "manual" | "llm_discovered"
    status TEXT DEFAULT 'active',      -- "active" | "pending_review" | "rejected" | "archived"
    confidence FLOAT,                  -- для LLM-discovered
    evidence TEXT,                     -- доказательства
    report_types TEXT[],               -- ["FINANCIAL_DAILY", "MARKETING_WEEKLY"]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT                   -- "admin" | "auto_approved"
);

-- RLS: service_role full access, authenticated read only
ALTER TABLE analytics_rules ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON analytics_rules FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON analytics_rules FOR SELECT TO authenticated USING (true);
```

### 7.2 Workflow

1. **При старте**: загрузить все `status = 'active'` правила из Supabase
2. **В промпте**: передать правила как "hypothesis tree" — LLM проверяет каждое правило по данным
3. **После анализа**: LLM возвращает `discovered_patterns` — новые наблюдения
4. **Review**: новые паттерны сохраняются в Supabase как `status = 'pending_review'`
5. **Telegram inline keyboard**: админ approve/reject через бота

### 7.3 Миграция

При первом запуске V4: парсим `agents/oleg/playbook.md` → записываем правила в Supabase как `source = 'manual'`, `status = 'active'`.

---

## 8. Formatter — Jinja2 шаблоны

### 8.1 Два формата выхода

- **Notion markdown** (полный отчёт, 12+ секций с toggle headings)
- **Telegram HTML** (executive summary + ключевые метрики, ссылка на Notion)

### 8.2 Шаблон на основе "золотого стандарта" (отчёт 20 марта)

Структура financial daily/weekly/monthly (13 секций):

```
0. Паспорт отчёта (scope, период, дата генерации)
1. Executive Summary (3-5 ключевых выводов)
2. Доходы и выручка (revenue breakdown by marketplace, models)
3. Маржинальный каскад (waterfall: выручка → себестоимость → логистика → реклама → маржа)
4. Рекламная эффективность (DRR, ROMI, CTR, CPC by campaign type)
5. Декомпозиция по моделям (TOP-10 + worst performers)
6. Ценовая динамика (price changes, SPP, discounts)
7. Складские остатки и оборачиваемость (days of supply, turnover)
8. Воронка продаж (показы → карточка → корзина → заказ)
9. Аномалии и алерты (отклонения от нормы)
10. Тренды (7d rolling, WoW, MoM)
11. Рекомендации (action items with estimated impact)
12. Техническая информация (confidence, cost, duration, data quality)
```

Каждый тип отчёта имеет свой `.md.j2` шаблон:
- `templates/financial_daily.md.j2`
- `templates/financial_weekly.md.j2`
- `templates/financial_monthly.md.j2`
- `templates/marketing_weekly.md.j2`
- `templates/marketing_monthly.md.j2`
- `templates/funnel_weekly.md.j2`
- `templates/funnel_monthly.md.j2`

### 8.3 Telegram-специфичный формат

Краткая сводка (max 4000 chars):
- Executive summary
- Ключевые метрики (с ▲/▼ и %)
- TOP-3 action items
- Footer: confidence 🟢/🟡/🔴, cost, ссылка на Notion

---

## 9. Validator

Упрощённый валидатор (детерминированный, без LLM):

```python
class ValidationResult:
    verdict: Literal["PASS", "RETRY", "FAIL"]
    issues: list[str]

def validate(report_md: str, insights: ReportInsights) -> ValidationResult:
    issues = []

    # 1. Минимум секций
    toggle_count = report_md.count("## ▶")
    if toggle_count < 6:
        issues.append(f"Only {toggle_count} sections, need ≥6")

    # 2. Русский текст присутствует
    russian_ratio = count_russian(report_md) / max(len(report_md), 1)
    if russian_ratio < 0.3:
        issues.append("Low Russian text ratio")

    # 3. Нет raw JSON leak
    if report_md.strip().startswith("{") or "```json" in report_md[:100]:
        issues.append("Raw JSON detected in report")

    # 4. Confidence выше порога
    if insights.overall_confidence < 0.3:
        issues.append(f"Low confidence: {insights.overall_confidence}")

    # 5. Нет placeholder текста
    placeholders = ["Н/Д", "Данные отсутствуют", "TODO", "TBD"]
    placeholder_count = sum(report_md.count(p) for p in placeholders)
    if placeholder_count > 5:
        issues.append(f"Too many placeholders: {placeholder_count}")

    if any("Raw JSON" in i or "sections" in i for i in issues):
        return ValidationResult(verdict="RETRY", issues=issues)
    if len(issues) > 3:
        return ValidationResult(verdict="FAIL", issues=issues)
    return ValidationResult(verdict="PASS", issues=issues)
```

---

## 10. Conductor + Scheduler

### 10.1 Три cron job вместо 15

| Job | Расписание | Действие |
|---|---|---|
| `data_ready_check` | Каждый час 06:00-12:00 MSK | Gates → schedule → generate pending reports |
| `deadline_check` | 13:00 MSK | Если дневной отчёт не готов → алерт в Telegram |
| `heartbeat` | Каждые 6 часов | Health check + "alive" сообщение |

### 10.2 Conductor flow

```python
async def run_report(scope: ReportScope) -> None:
    run_id = await state.create_run(scope)  # Supabase INSERT

    try:
        # 1. Collect
        data = await collector_for(scope.report_type).collect(scope)

        # 2. Analyze
        playbook = await playbook_loader.load(scope.report_type)
        insights = await analyst.analyze(data, scope, playbook)

        # 3. Format
        notion_md = formatter.to_notion(insights, data, scope)
        telegram_html = formatter.to_telegram(insights, data, scope)

        # 4. Validate
        result = validator.validate(notion_md, insights)
        if result.verdict == "RETRY":
            await state.update_run(run_id, status="retry", issues=result.issues)
            # retry once with adjusted prompt
            insights = await analyst.analyze(data, scope, playbook, retry_hint=result.issues)
            notion_md = formatter.to_notion(insights, data, scope)
            telegram_html = formatter.to_telegram(insights, data, scope)
            result = validator.validate(notion_md, insights)

        if result.verdict == "FAIL":
            await state.update_run(run_id, status="failed", issues=result.issues)
            await notify_error(scope, result.issues)  # consolidated, not spam
            return

        # 5. Deliver (parallel)
        notion_url = await delivery.upsert_notion(notion_md, scope)
        tg_message_id = await delivery.send_or_edit_telegram(telegram_html, scope, notion_url)

        # 6. Log
        await state.update_run(run_id, status="success",
                              notion_url=notion_url,
                              telegram_message_id=tg_message_id,
                              confidence=insights.overall_confidence)

        # 7. Save discovered patterns
        for pattern in insights.discovered_patterns:
            await playbook_updater.save_pending(pattern, scope)

    except Exception as e:
        await state.update_run(run_id, status="error", error=str(e))
        await notify_error(scope, [str(e)])
```

### 10.3 Gate Checker

Переносится из V3 (`agents/v3/gates.py`) без изменений — 6 проверок:

| Gate | Тип | Что проверяет |
|---|---|---|
| ETL ran today | HARD | MAX(dateupdate).date() == today |
| Source data loaded | HARD | Заказы вчера vs avg 7d > 30% |
| Logistics > 0 | HARD | SUM(ABS(logistics)) > 0 |
| Orders volume | SOFT | Заказы вчера vs avg 7d > 70% |
| Revenue vs avg | SOFT | Выручка вчера vs avg 7d > 70% |
| Margin fill | SOFT | % строк с marga != 0 > 50% |

---

## 11. Supabase State Management

### 11.1 Таблица `report_runs`

```sql
CREATE TABLE report_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type TEXT NOT NULL,
    scope_hash TEXT NOT NULL,
    scope_json JSONB NOT NULL,         -- full ReportScope serialized
    status TEXT DEFAULT 'pending',     -- pending | collecting | analyzing | formatting | delivering | success | failed | error
    attempt INT DEFAULT 1,
    notion_url TEXT,
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    confidence FLOAT,
    cost_usd FLOAT,
    duration_sec FLOAT,
    issues JSONB,                      -- validation issues
    error TEXT,
    llm_model TEXT,
    llm_tokens_in INT,
    llm_tokens_out INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(report_date, report_type, scope_hash)
);

-- RLS
ALTER TABLE report_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON report_runs FOR ALL TO postgres USING (true);
CREATE POLICY "authenticated_read" ON report_runs FOR SELECT TO authenticated USING (true);
```

### 11.2 Dedup logic

```python
async def create_run(scope: ReportScope) -> str:
    """INSERT ... ON CONFLICT DO UPDATE SET attempt = attempt + 1, status = 'pending'"""
    # Если run уже существует для этого дня + типа + scope_hash:
    # - Увеличиваем attempt
    # - Сбрасываем status на 'pending'
    # - НЕ создаём новый row
```

Это гарантирует: **один отчёт = один row в Supabase**, сколько бы retry ни было.

---

## 12. Delivery — upsert everywhere

### 12.1 Notion

```python
async def upsert_notion(report_md: str, scope: ReportScope) -> str:
    """Find existing page by date+type → update, or create new."""
    existing = await find_page(scope.report_date, scope.report_type)
    if existing:
        await clear_blocks(existing.id)
        await append_blocks(existing.id, markdown_to_blocks(report_md))
        return existing.url
    else:
        page = await create_page(scope, report_md)
        return page.url
```

Notion страница создаётся с properties:
- **Дата**: `scope.period_from` - `scope.period_to`
- **Тип**: `scope.report_type.value`
- **Система**: "V4 Reporter"
- **Статус**: "success" / "partial"
- **Confidence**: число 0-1

### 12.2 Telegram

```python
async def send_or_edit_telegram(html: str, scope: ReportScope, notion_url: str) -> int:
    """Send new message or edit existing one for this scope."""
    existing_msg_id = await state.get_telegram_message_id(scope)
    if existing_msg_id:
        await bot.edit_message_text(chat_id=ADMIN_CHAT_ID,
                                    message_id=existing_msg_id,
                                    text=html, parse_mode="HTML")
        return existing_msg_id
    else:
        msg = await bot.send_message(chat_id=ADMIN_CHAT_ID,
                                     text=html, parse_mode="HTML")
        return msg.message_id
```

При retry: **edit** существующее сообщение, не посылать новое.

---

## 13. Anti-Spam System

### 13.1 Проблемы V3 (из скриншотов)

1. **prompt-tuner 403 errors** каждые 5 минут — бесконечный retry
2. **Weekly ДДС failures** — 4 одинаковых сообщения об ошибке
3. **Duplicate data-ready** — "данные готовы" отправляется каждый час когда gates проходят
4. **Бесконечные ошибки** затапливают чат, невозможно увидеть реальные отчёты

### 13.2 Решения

**a) Circuit breaker на LLM вызовы:**
```python
class CircuitBreaker:
    failure_threshold: int = 3    # после 3 неудач — OPEN
    cooldown_sec: float = 3600    # ждать 1 час перед retry
    # Состояния: CLOSED (работает) → OPEN (стоп) → HALF_OPEN (пробный вызов)
```
Если LLM вызов падает 3 раза подряд → прекратить попытки на 1 час, отправить ОДНО сообщение "LLM circuit breaker open, retry через 1 час".

**b) One error per report type per day:**
```python
async def notify_error(scope: ReportScope, issues: list[str]) -> None:
    today = date.today()
    key = f"error:{scope.report_type.value}:{today.isoformat()}"
    if await state.was_error_notified(key):
        return  # уже уведомляли сегодня
    await bot.send_message(ADMIN_CHAT_ID, format_error(scope, issues))
    await state.mark_error_notified(key)
```

**c) Data-ready notification — once per day:**
```python
async def notify_data_ready(marketplace: str) -> None:
    today = date.today()
    key = f"data_ready:{marketplace}:{today.isoformat()}"
    if await state.was_notified(key):
        return  # уже отправляли
    await bot.send_message(ADMIN_CHAT_ID, f"✅ Данные {marketplace} готовы")
    await state.mark_notified(key)
```

**d) Нет prompt-tuner в V4:**
V4 не включает prompt-tuner. Feedback обрабатывается через playbook review (inline keyboards), а не через LLM-driven prompt optimization.

**e) Error consolidation в Telegram:**
- Ошибки группируются: один блок в конце дня "Статус: 5/7 отчётов готовы, 2 failed (причины: ...)"
- Heartbeat (каждые 6 часов) включает сводку: сколько отчётов готово, сколько pending, сколько failed

### 13.3 Supabase таблица notifications

```sql
CREATE TABLE notification_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    notification_key TEXT NOT NULL,    -- "error:FINANCIAL_DAILY:2026-03-28"
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    telegram_message_id BIGINT,
    UNIQUE(notification_key)
);

ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON notification_log FOR ALL TO postgres USING (true);
```

---

## 14. Telegram Bot

### 14.1 Новый бот

- **Токен**: отдельный от V3 (хранится в `.env` как `REPORTER_V4_BOT_TOKEN`)
- **Библиотека**: aiogram 3.x
- **Режим**: long polling (один инстанс, нет конфликтов)

### 14.2 Команды

| Команда | Действие |
|---|---|
| `/status` | Статус сегодняшних отчётов (таблица из Supabase) |
| `/run <type>` | Запустить отчёт вручную (e.g. `/run financial_daily`) |
| `/run <type> <date>` | Отчёт за конкретную дату |
| `/rules` | Список активных playbook правил |
| `/pending` | Паттерны, ожидающие review |
| `/logs <type>` | Последние 5 runs для типа отчёта |
| `/health` | Состояние системы: circuit breakers, last success, errors today |

### 14.3 Inline keyboards для playbook review

Когда LLM находит новый паттерн:
```
🔍 Новый паттерн обнаружен:
"Когда ДРР > 20% и CTR < 2%, маржа падает > 5%"
Confidence: 0.82
Доказательства: Wendy 25-31 марта, DRR 22%, CTR 1.8%, маржа -6.2%

[✅ Approve] [❌ Reject] [📝 Edit]
```

---

## 15. Файловая структура V4

```
agents/reporter/
├── __init__.py
├── __main__.py                  # Entry: python -m agents.reporter
├── config.py                    # Конфигурация V4
├── pipeline.py                  # Collect → Analyze → Format → Validate
├── conductor.py                 # Gate → Schedule → Pipeline → Deliver → Log
├── scheduler.py                 # APScheduler: 3 cron jobs
├── state.py                     # Supabase state management (report_runs, notification_log)
├── gates.py                     # Скопировано из v3/gates.py
│
├── collector/
│   ├── __init__.py
│   ├── base.py                  # ReportScope, BaseCollector, CollectedData
│   ├── financial.py             # FinancialCollector
│   ├── marketing.py             # MarketingCollector
│   └── funnel.py                # FunnelCollector
│
├── analyst/
│   ├── __init__.py
│   ├── analyst.py               # analyze() — single LLM call point
│   ├── schemas.py               # Pydantic: ReportInsights, SectionInsight, etc.
│   ├── circuit_breaker.py       # CircuitBreaker для LLM
│   └── prompts/
│       ├── financial_daily.md
│       ├── financial_weekly.md
│       ├── financial_monthly.md
│       ├── marketing_weekly.md
│       ├── marketing_monthly.md
│       ├── funnel_weekly.md
│       └── funnel_monthly.md
│
├── formatter/
│   ├── __init__.py
│   ├── notion.py                # Jinja2 → Notion markdown
│   ├── telegram.py              # → Telegram HTML
│   └── templates/
│       ├── financial_daily.md.j2
│       ├── financial_weekly.md.j2
│       ├── financial_monthly.md.j2
│       ├── marketing_weekly.md.j2
│       ├── marketing_monthly.md.j2
│       ├── funnel_weekly.md.j2
│       └── funnel_monthly.md.j2
│
├── playbook/
│   ├── __init__.py
│   ├── loader.py                # Load rules from Supabase
│   ├── updater.py               # Save discovered patterns
│   └── base_rules.md            # Fallback: initial rules from oleg/playbook.md
│
├── delivery/
│   ├── __init__.py
│   ├── notion.py                # Upsert logic
│   └── telegram.py              # Send/edit logic
│
├── bot/
│   ├── __init__.py
│   ├── bot.py                   # aiogram 3.x polling
│   ├── handlers.py              # /status, /run, /rules, /pending, /logs, /health
│   └── keyboards.py             # Inline keyboards for playbook review
│
└── MIGRATION.md                 # Kill switch checklist
```

---

## 16. Migration Plan

### Phase 1: BUILD (parallel с V3)

1. Создать `agents/reporter/` с полной структурой
2. Создать Supabase таблицы: `report_runs`, `analytics_rules`, `notification_log`
3. Мигрировать playbook.md → Supabase `analytics_rules`
4. Реализовать DataCollectors (переиспользуя shared/data_layer/)
5. Реализовать Analyst + Formatter + Validator
6. Реализовать Conductor + Scheduler
7. Реализовать Bot + Delivery
8. Новый Docker container: `wookiee_reporter` рядом с `wookiee_oleg`

### Phase 2: TEST (shadow mode)

1. V4 генерирует отчёты в shadow Notion database (не production)
2. V3 продолжает работать (или не работать) как есть
3. Сравнить качество V4 output vs V2 gold standard (отчёт 20 марта)
4. Telegram: V4 бот отправляет в тестовый чат

### Phase 3: SWITCH

1. V4 → production Notion database
2. V4 бот → production Telegram чат
3. V3 scheduler остановлен (env: `V3_REPORTS_ENABLED=false`)
4. V2 code оставлен как rollback

### Phase 4: CLEANUP

1. Удалить V3: `agents/v3/` (кроме gates.py, скопированного в V4)
2. Удалить мёртвый V2 код:
   - `agents/oleg/orchestrator/` (830 строк)
   - `agents/oleg/agents/reporter/`
   - `agents/oleg/agents/advisor/`
   - `agents/oleg/agents/validator/`
   - `agents/oleg/agents/marketer/`
   - `agents/oleg/executor/`
   - `agents/oleg/watchdog/`
3. Удалить 12 мёртвых .md агентов из `agents/v3/agents/`
4. Удалить legacy scheduler code
5. Удалить SQLite state management
6. Удалить docker container `wookiee_oleg` (если Oleg bot не нужен отдельно)

### Rollback plan

Если V4 не работает → **rollback на V2** (не V3, т.к. V3 уже сломан):
```bash
# В docker-compose:
# 1. Остановить wookiee_reporter
# 2. Включить V2 orchestrator в wookiee_oleg
# 3. Перенаправить cron на V2 entry points
```

### Kill switch checklist (`MIGRATION.md`)

```markdown
# V4 Reporter — Kill Switch

## Before switching V4 to production:
- [ ] Supabase tables created with RLS
- [ ] V4 generates correct financial_daily in shadow mode
- [ ] V4 generates correct financial_weekly in shadow mode
- [ ] V4 generates correct marketing_weekly in shadow mode
- [ ] V4 generates correct funnel_weekly in shadow mode
- [ ] Notion upsert works (no duplicates)
- [ ] Telegram edit works (no duplicates)
- [ ] Anti-spam: no more than 1 error notification per type per day
- [ ] Circuit breaker tested (LLM failure → stops retrying)
- [ ] Playbook rules loaded from Supabase
- [ ] Bot commands work: /status, /run, /health

## Switching to production:
- [ ] V3 scheduler stopped
- [ ] V4 Notion database = production
- [ ] V4 Telegram chat = production (ADMIN_CHAT_ID)
- [ ] Monitor for 24 hours

## Rollback:
- [ ] Stop wookiee_reporter container
- [ ] Re-enable V2 in wookiee_oleg
```

---

## 17. Docker & Deploy

### Новый контейнер

```yaml
# deploy/docker-compose.yml
wookiee_reporter:
  build:
    context: ..
    dockerfile: deploy/Dockerfile.reporter
  container_name: wookiee_reporter
  env_file: ../.env
  environment:
    - REPORTER_V4_BOT_TOKEN=${REPORTER_V4_BOT_TOKEN}
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
  restart: unless-stopped
  depends_on:
    - caddy
```

### Entrypoint

```python
# agents/reporter/__main__.py
import asyncio
from agents.reporter.scheduler import start_scheduler
from agents.reporter.bot.bot import start_bot

async def main():
    scheduler = start_scheduler()
    await start_bot()  # blocking: aiogram polling

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 18. Стоимость

### V3 (текущая, когда работает)
- 4 LLM вызова × ~15K tokens = ~60K tokens/отчёт
- GLM-4.7 (main) + Gemini 2.5 Flash (compiler)
- ~$0.03-0.05 на отчёт

### V4 (прогноз)
- 1 LLM вызов × ~30K tokens input + ~5K output
- Gemini 2.5 Flash: $0.15/1M in + $0.60/1M out
- ~$0.008 на отчёт (в 4-5 раз дешевле)
- 7 отчётов/неделю × 4 недели = ~28 отчётов/месяц ≈ $0.22/месяц

---

## 19. Success Criteria

1. **Reliability**: 95%+ отчётов генерируются без ручного вмешательства (vs 0% сейчас)
2. **Quality**: Секции отчёта заполнены реальными данными (не "Н/Д"), качество на уровне отчёта 20 марта
3. **No spam**: Максимум 1 error notification per report type per day
4. **No duplicates**: Один отчёт = один Supabase row = одна Notion страница = одно Telegram сообщение
5. **Speed**: < 3 минут на отчёт (vs ~12 минут V3)
6. **Cost**: < $0.01 на отчёт
7. **Observability**: Полный лог каждого run в Supabase (status, confidence, cost, duration, errors)
