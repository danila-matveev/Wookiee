# Аудит системы отчётов Wookiee — 27 марта 2026

## Статус: отчёты НЕ генерируются с ~20 марта

---

## 1. Общая архитектура

```
┌──────────────────────────────────────────────────────────┐
│  Docker container: wookiee_oleg                          │
│  Entry: python -m agents.v3                              │
│                                                          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ APScheduler  │  │ Telegram Bot   │  │ Watchdog     │ │
│  │ (cron jobs)  │  │ (aiogram poll) │  │ (heartbeat)  │ │
│  └──────┬───────┘  └────────────────┘  └──────────────┘ │
│         │                                                │
│         ▼                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Conductor (data_ready_check, deadline, catchup)  │   │
│  │ → Gate Checker → Orchestrator → Delivery         │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

**Сервер:** timeweb (77.233.212.61), Docker Compose: `/home/danila/projects/wookiee/deploy/`

---

## 2. V2 vs V3 — что есть что

### V2 (agents/oleg/)
- **Статус:** код СУЩЕСТВУЕТ, но НЕ ИСПОЛЬЗУЕТСЯ как оркестратор
- **Что осталось и реально используется V3:**
  - `agents/oleg/services/agent_tools.py` — 12 финансовых tool-обёрток над data_layer
  - `agents/oleg/services/price_tools.py` — 18 ценовых tools
  - `agents/oleg/services/marketing_tools.py` — маркетинговые tools
  - `agents/oleg/services/funnel_tools.py` — воронка
  - `agents/oleg/playbook.md` — финансовые правила
- **Что мёртвое (можно удалить):**
  - `agents/oleg/orchestrator/orchestrator.py` — 830 строк, никем не импортируется
  - `agents/oleg/agents/reporter/` — ReporterAgent, не инстанциируется
  - `agents/oleg/agents/advisor/` — экспериментальный, не используется
  - `agents/oleg/agents/validator/` — экспериментальный, не используется
  - `agents/oleg/agents/marketer/` — экспериментальный, не используется
  - `agents/oleg/executor/` — ReAct loop, заменён LangGraph в V3
  - `agents/oleg/watchdog/` — заменён agents/v3/monitor.py

### V3 (agents/v3/)
- **Статус:** активная система, но отчёты не генерируются из-за багов
- **Архитектура:** LangGraph micro-agents + APScheduler + Conductor pattern
- **Модели LLM:** GLM-4.7 (main) + Gemini 2.5 Flash (compiler) через OpenRouter

---

## 3. Как генерируется daily отчёт (текущий flow)

```
Cron: data_ready_check (каждый час 06:00-12:00 MSK)
  │
  ▼
Gate Checker: check_all("wb") + check_all("ozon")
  │  Hard gates: ETL ran today, data loaded (>30% avg), logistics > 0
  │  Soft gates: orders volume, revenue vs avg, margin fill
  │
  ▼ (оба passed)

Conductor: data_ready_check()
  │  Определяет расписание: какие отчёты нужны сегодня
  │  Фильтрует уже сгенерированные (SQLite state)
  │  Отправляет Telegram уведомление "данные готовы"
  │
  ▼

Orchestrator: run_daily_report(date_from, date_to, comparison_from, comparison_to)
  │
  ▼

Phase 1: ПАРАЛЛЕЛЬНЫЙ запуск 3 LLM-агентов
  ├── margin-analyst      → LLM (GLM-4.7) + tools → JSON artifact
  ├── revenue-decomposer  → LLM (GLM-4.7) + tools → JSON artifact
  └── ad-efficiency       → LLM (GLM-4.7) + tools → JSON artifact
  │
  │   Каждый агент:
  │   1. Читает .md файл (промпт + конфиг)
  │   2. Создаёт LangGraph ReAct agent
  │   3. Вызывает LLM с tools (SQL обёртки)
  │   4. LLM делает tool calls → получает данные → анализирует
  │   5. Возвращает JSON artifact
  │   Timeout: 180 сек на агента
  │
  ▼

Phase 2: Report Compiler (Gemini 2.5 Flash)
  │  Получает все artifacts + шаблон 12 секций
  │  Генерирует: detailed_report (markdown) + telegram_summary (BBCode)
  │
  ▼

Validator: quick_validate()
  │  Проверки: status, длина, русский текст, toggle-заголовки,
  │  кол-во секций (>=6), нет raw JSON, нет failure phrases
  │  Verdict: PASS / RETRY / FAIL
  │
  ▼

Delivery Router:
  ├── Notion: sync_report() — upsert (найти по дате+тип → обновить или создать)
  └── Telegram: send_report() — HTML chunks + ссылка на Notion
```

**Проблемы этого flow (см. раздел 5):**
- 4 вызова LLM = 4 точки отказа
- JSON extraction из LLM output хрупкий
- ~12 мин на один отчёт
- Если 1 агент упал → секции пропадают

---

## 4. Полная карта компонентов V3

### 4.1 Агенты (agents/v3/agents/*.md)

**12 АКТИВНЫХ (вызываются из orchestrator.py):**

| Агент | Используется в | Что делает |
|-------|---------------|------------|
| margin-analyst | daily, weekly, monthly, price | Маржинальный анализ: waterfall 10 строк, cost structure, SPP |
| revenue-decomposer | daily, weekly, monthly | Декомпозиция выручки: по каналам, моделям, план-факт |
| ad-efficiency | daily, weekly, monthly, marketing, price | Рекламная эффективность: DRR, ROMI, CTR, CPC |
| campaign-optimizer | marketing_weekly, marketing_monthly | Анализ кампаний: органика vs платный трафик |
| organic-vs-paid | marketing_weekly, marketing_monthly | Разделение organic/paid выручки |
| funnel-digitizer | funnel_weekly | Воронка: показы → карточка → корзина → заказ |
| keyword-analyst | funnel_weekly | SEO: ключевые слова, позиции, трафик |
| finolog-analyst | finolog_weekly | ДДС: доходы/расходы/остаток |
| price-strategist | price_analysis (Phase 1) | Ценовая эластичность, рекомендации |
| pricing-impact-analyst | price_analysis (Phase 2) | Оценка влияния цен на маржу |
| hypothesis-tester | price_analysis (Phase 2) | Тестирование ценовых гипотез |
| report-compiler | ВСЕ отчёты (финальная фаза) | Сборка markdown из artifacts |

**1 ОГРАНИЧЕННОГО ИСПОЛЬЗОВАНИЯ:**

| Агент | Использование |
|-------|-------------|
| prompt-tuner | Обработка feedback из Notion comments (cron каждые 60 мин) |

**12 МЁРТВЫХ (файлы есть, никогда не вызываются):**

| Агент | Статус |
|-------|--------|
| agent-monitor | Не используется |
| anomaly-detector | Не используется |
| content-optimizer | Не используется |
| content-searcher | Не используется |
| data-navigator | Только Telegram free-text (не отчёты) |
| data-validator | Не используется |
| kb-auditor | Не используется |
| kb-curator | Не используется |
| kb-searcher | Не используется |
| logistics-analyst | Не используется |
| quality-checker | Не используется |
| review-analyst | Не используется |

### 4.2 Типы отчётов (conductor/schedule.py — ReportType enum)

| Тип | Расписание | Агенты (Phase 1) | Метод оркестратора |
|-----|-----------|------------------|--------------------|
| DAILY | Каждый день | margin, revenue, ad | run_daily_report |
| WEEKLY | Понедельник | margin, revenue, ad | run_weekly_report |
| MONTHLY | 1й понедельник месяца | margin, revenue, ad | run_monthly_report |
| MARKETING_WEEKLY | Понедельник | campaign, organic-vs-paid, ad | run_marketing_report |
| MARKETING_MONTHLY | 1й понедельник | campaign, organic-vs-paid, ad | run_marketing_report |
| FUNNEL_WEEKLY | Понедельник | funnel-digitizer, keyword-analyst | run_funnel_report |
| PRICE_WEEKLY | Понедельник | 3-phase pipeline (5 агентов) | run_price_analysis |
| PRICE_MONTHLY | 1й понедельник | 3-phase pipeline (5 агентов) | run_price_analysis |
| FINOLOG_WEEKLY | Пятница | finolog-analyst | run_finolog_report |

### 4.3 Scheduler (два режима, активен Conductor)

**Conductor mode (USE_CONDUCTOR=true, по умолчанию):**

| Job | Время (MSK) | Что делает |
|-----|------------|------------|
| data_ready_check | Каждый час 06:00-12:00 | Gates → определить нужные отчёты → сгенерировать |
| deadline_check | 12:00 | Если отчёты не готовы → алерт в Telegram |
| catchup_check | 15:00 | Повторная попытка для daily отчёта |
| anomaly_monitor | Каждые N часов | Проверка аномалий метрик |
| watchdog_heartbeat | Каждые 6 часов | Health check + "alive" в Telegram |
| notion_feedback | Каждые 60 мин | Обработка комментариев из Notion |
| etl_daily_sync | 05:00 | Синхронизация данных маркетплейсов |
| etl_weekly_analysis | Воскресенье 03:00 | Анализ API/схем |
| localization_weekly | Понедельник 13:00 | Отчёт по локализации |

**Legacy mode (USE_CONDUCTOR=false):**
15 отдельных cron jobs с фиксированными временами. НЕ АКТИВЕН.

### 4.4 Data Layer (shared/data_layer/)

14 модулей, ~4660 строк SQL:

| Модуль | Строк | Функции |
|--------|-------|---------|
| finance.py | 232 | get_wb_finance, get_wb_by_model, get_ozon_finance |
| advertising.py | 802 | get_wb_external_ad_breakdown, get_wb_campaign_stats |
| inventory.py | 708 | get_wb_avg_stock, get_wb_turnover_by_model |
| pricing.py | 581 | get_wb_price_dynamics, get_wb_price_changes |
| funnel_seo.py | 535 | get_wb_organic_funnel, get_wb_seo_metrics |
| article.py | 404 | get_wb_article_summary, get_wb_article_status |
| time_series.py | 361 | get_wb_daily_series, get_ozon_daily_series |
| sku_mapping.py | 330 | get_wb_sku_mapping, map_to_osnova |
| pricing_article.py | 230 | get_wb_pricing_by_article, get_wb_elasticity |
| planning.py | 143 | get_wb_plan_vs_fact |
| traffic.py | 114 | get_wb_traffic, get_ozon_traffic |
| quality.py | 64 | get_wb_data_quality |

**Подключение к БД:**
- Legacy mode (default): PostgreSQL напрямую → pbi_wb_wookiee / pbi_ozon_wookiee
- Managed mode: через ETL DB с переключением schema

### 4.5 Gate Checker (agents/v3/gates.py)

6 проверок на маркетплейс (WB и OZON отдельно):

| Gate | Тип | Порог | Что проверяет |
|------|-----|-------|---------------|
| ETL ran today | HARD | — | MAX(dateupdate).date() == today |
| Source data loaded | HARD | 30% | Заказы вчера vs средние 7д |
| Logistics > 0 | HARD | 0 | SUM(ABS(logistics)) > 0 |
| Orders volume | SOFT | 70% | Заказы вчера vs средние 7д |
| Revenue vs avg | SOFT | 70% | Выручка вчера vs средние 7д |
| Margin fill | SOFT | 50% | % строк с marga != 0 |

Hard gate fail → отчёт ЗАБЛОКИРОВАН. Soft gate fail → отчёт с предупреждением.

### 4.6 Delivery

**Notion (shared/notion_client.py):**
- Upsert по дате + тип: `_find_existing_page()` → update или create
- Блоки: markdown → Notion blocks, toggle children отдельными PATCH
- Конкурентность: per-report-type lock

**Telegram (agents/v3/delivery/telegram.py):**
- HTML chunks (max 4000 chars), BBCode→HTML
- Ссылка на Notion страницу
- Footer: confidence 🟢/🟡/🔴, cost, agents, duration

### 4.7 LLM модели (через OpenRouter)

| Тир | Модель | Использование | Цена input/output ($/1K) |
|-----|--------|---------------|--------------------------|
| MAIN | z-ai/glm-4.7 | Все аналитические агенты | 0.00006 / 0.0004 |
| COMPILER | google/gemini-2.5-flash | report-compiler | 0.00015 / 0.0006 |
| LIGHT | z-ai/glm-4.7-flash | Не используется | 0.00007 / 0.0003 |
| HEAVY | google/gemini-3-flash-preview | Не используется | 0.0005 / 0.003 |
| FALLBACK | openrouter/free | На случай ошибок | бесплатно |

---

## 5. Известные баги и проблемы

### 5.1 КРИТИЧЕСКИЕ (отчёты не работают)

#### Bug #1: TelegramConflictError — бот не работает
- **Симптом:** 400+ ошибок `TelegramConflictError: terminated by other getUpdates request` за час
- **Причина:** Другой процесс (n8n? старый инстанс?) использует тот же бот-токен `8532836779` для polling
- **Влияние:** Бот не принимает команды. НО это НЕ блокирует генерацию отчётов — scheduler и conductor работают независимо от бота
- **Как исправить:** Найти и остановить дублирующий процесс, или использовать webhooks вместо polling

#### Bug #2: Отчёты не генерируются всю неделю
- **Симптом:** Нет логов `data_ready_check`, `Generating`, `success` за последние 7 дней
- **Возможные причины:**
  - Gates не проходят (ETL не загрузил данные) — наиболее вероятно
  - Контейнер пересоздавался, SQLite state потерян
  - Scheduler не стартовал корректно
- **Диагностика:** Нужно запустить gate check вручную и посмотреть результат
- **Как проверить:**
  ```bash
  docker exec wookiee_oleg python -c "
  from agents.v3.gates import GateChecker
  gc = GateChecker()
  wb = gc.check_all('wb')
  ozon = gc.check_all('ozon')
  print('WB:', wb.can_generate, [g.name + '=' + str(g.passed) for g in wb.gates])
  print('OZON:', ozon.can_generate, [g.name + '=' + str(g.passed) for g in ozon.gates])
  "
  ```

#### Bug #3: SQLite state в контейнере — теряется при rebuild
- **Симптом:** Volume монтирует только `agents/v3/data/`, а SQLite state (`v3_state.db`) там
- **Проверить:** `docker exec wookiee_oleg ls -la /app/agents/v3/data/v3_state.db`
- **Если потерян:** Conductor думает что всё уже сгенерировано (или наоборот, ничего нет — зависит от default)

### 5.2 РЕШЁННЫЕ (исправлены 26-27 марта)

#### Bug #4: Notion toggle children не отображались ✅
- **Симптом:** Отчёт в Notion показывал только "0. Паспорт отчёта", остальные 11 секций пусты
- **Причина:** Notion API не сохраняет children toggle headings если послать inline при создании страницы
- **Исправление:** Создаём страницу пустой → append parent blocks → append children отдельными PATCH
- **Файл:** shared/notion_client.py — `_append_blocks()` переписан

#### Bug #5: Пустой detailed_report (0 chars) ✅
- **Симптом:** Compiler agent возвращал JSON в ```json code fence, runner не мог извлечь
- **Причина:** Regex `\{[\s\S]*\}` жадно захватывал всё включая code fence markers
- **Исправление:** 3 стратегии JSON extraction: direct parse → fence strip → first-{/last-}
- **Файл:** agents/v3/runner.py

#### Bug #6: 197K chars raw JSON как detailed_report ✅
- **Симптом:** Orchestrator fallback записывал сырой JSON в detailed_report
- **Причина:** Fallback проверял `## ▶` ВНУТРИ JSON строки (не в начале)
- **Исправление:** Проверка `starts_with("## ▶")` + strip code fence перед JSON parse
- **Файл:** agents/v3/orchestrator.py

#### Bug #7: 6+ Telegram уведомлений за день ✅
- **Симптом:** Каждый retry отправлял новое сообщение в Telegram
- **Причина:** Conductor не отслеживал отправку Telegram отдельно от Notion
- **Исправление:**
  - `mark_telegram_sent()` / `is_telegram_sent()` в ConductorState (SQLite)
  - При retry attempt > 1: если Telegram уже отправлен → destinations=["notion"] only
- **Файлы:** conductor/state.py, conductor/conductor.py, scheduler.py

#### Bug #8: Валидатор пропускал неполные отчёты ✅
- **Симптом:** Отчёт с 1-2 секциями проходил валидацию
- **Исправление:**
  - `MIN_TOGGLE_SECTIONS = 6` — минимум секций
  - Детекция raw JSON leak (starts with `{` или ```` ```json ````)
- **Файл:** conductor/validator.py

#### Bug #9: Post-delivery проверка отсутствовала ✅
- **Симптом:** Отчёт помечался "success" даже если Notion delivery упал
- **Исправление:** После delivery проверяем notion_url; если None → retry
- **Файл:** conductor/conductor.py

### 5.3 АРХИТЕКТУРНЫЕ ПРОБЛЕМЫ

#### Problem #1: 4 LLM вызова = 4 точки отказа
- Daily отчёт: 3 аналитических агента + 1 compiler = 4 LLM запроса
- Каждый может: timeout (180с), вернуть мусор, обрезаться по токенам
- Если 1 агент упал → compiler получает неполные данные → секции пропадают
- **Рекомендация:** Один LLM вызов с полными данными (см. раздел 6)

#### Problem #2: LLM ходит за данными через tools
- Агент делает tool calls к SQL обёрткам → получает данные → анализирует
- Но данные ДЕТЕРМИНИРОВАННЫЕ — SQL запросы одинаковые каждый раз
- LLM тратит токены и время на формулировку tool calls
- **Рекомендация:** Собрать данные до LLM, передать готовый JSON

#### Problem #3: 25 agent-файлов, 12 мёртвых
- Половина агентов никогда не вызывается
- Создают путаницу при навигации
- **Рекомендация:** Удалить неиспользуемые или переместить в archive/

#### Problem #4: Два scheduler mode (legacy + conductor)
- Оба существуют в коде, но активен только conductor
- Legacy код (~200 строк) — мёртвый вес
- **Рекомендация:** Удалить legacy scheduler

#### Problem #5: V2 orchestrator — 830 строк мёртвого кода
- `agents/oleg/orchestrator/orchestrator.py` не импортируется
- Sub-agents (reporter, advisor, validator, marketer) не инстанциируются
- **Рекомендация:** Удалить всё кроме services/ и playbook.md

---

## 6. Предлагаемое упрощение архитектуры

### Текущая (Complex):
```
Scheduler → Gates → 3 LLM agents (parallel, tool calls) → Compiler LLM → Validator → Delivery
4 LLM вызова, ~12 мин, 4 точки отказа
```

### Предлагаемая (Simple):
```
Scheduler → Gates → Data Collector (Python, SQL) → 1 LLM (анализ + форматирование) → Validator → Delivery
1 LLM вызов, ~3 мин, 1 точка отказа
```

**Ключевые изменения:**
1. **Data Collector** — Python функция, вызывает все SQL запросы, собирает один JSON с данными
2. **Один LLM вызов** — получает полный JSON + шаблон 12 секций → генерирует markdown
3. **Удаление мёртвого кода** — 12 неиспользуемых агентов, legacy scheduler, V2 orchestrator
4. **Гарантия 12 секций** — шаблон детерминированный, LLM только заполняет аналитику

### Что сохраняется:
- Gate checker (проверки качества данных)
- Conductor pattern (smart scheduling)
- Delivery router (Notion upsert + Telegram dedup)
- Validator (проверка контента)
- Data layer (SQL запросы) — самая ценная часть системы
- Tool definitions из agents/oleg/services/ — логика переиспользуется

---

## 7. Немедленные действия для дебага

### Шаг 1: Диагностика Telegram conflict
```bash
# Найти все процессы с этим ботом
ssh danila@server "docker ps -a"
# Проверить n8n workflows на использование бот-токена
# Остановить дублирующий процесс
```

### Шаг 2: Проверить gates вручную
```bash
docker exec wookiee_oleg python -c "
from agents.v3.gates import GateChecker
gc = GateChecker()
for mp in ['wb', 'ozon']:
    r = gc.check_all(mp)
    print(f'{mp}: can_generate={r.can_generate}')
    for g in r.gates:
        print(f'  {g.name}: passed={g.passed} value={g.value} detail={g.detail}')
"
```

### Шаг 3: Запустить отчёт вручную
```bash
docker exec wookiee_oleg python -c "
import asyncio
from agents.v3.orchestrator import run_daily_report
from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days=1)
result = asyncio.run(run_daily_report(
    date_from=yesterday.isoformat(),
    date_to=yesterday.isoformat(),
    comparison_from=(yesterday - timedelta(days=1)).isoformat(),
    comparison_to=(yesterday - timedelta(days=1)).isoformat(),
    channel='both', trigger='manual'
))
print('status:', result.get('status'))
print('report length:', len(result.get('report', {}).get('detailed_report', '')))
"
```

### Шаг 4: Проверить SQLite state
```bash
docker exec wookiee_oleg python -c "
import sqlite3
conn = sqlite3.connect('/app/agents/v3/data/v3_state.db')
rows = conn.execute('SELECT date, report_type, status, attempts FROM conductor_log ORDER BY date DESC LIMIT 20').fetchall()
for r in rows:
    print(r)
"
```

---

## 8. Файловая карта проекта (только отчётная система)

```
agents/
├── oleg/                              # V2 (ЧАСТИЧНО МЁРТВЫЙ)
│   ├── agents/                        # 4 sub-agents — НЕ ИСПОЛЬЗУЮТСЯ
│   ├── orchestrator/                  # OlegOrchestrator — НЕ ИСПОЛЬЗУЕТСЯ (830 строк)
│   ├── executor/                      # ReAct loop — ЗАМЕНЁН LangGraph
│   ├── services/                      # ✅ ИСПОЛЬЗУЕТСЯ V3 (tools для агентов)
│   │   ├── agent_tools.py             #   12 финансовых tools
│   │   ├── price_tools.py             #   18 ценовых tools
│   │   ├── marketing_tools.py         #   маркетинговые tools
│   │   ├── funnel_tools.py            #   воронка tools
│   │   └── price_analysis/            #   модули ценового анализа
│   ├── storage/                       # StateStore — используется V3
│   ├── watchdog/                      # ЗАМЕНЁН agents/v3/monitor.py
│   └── playbook.md                    # ✅ Финансовые правила — используется
│
├── v3/                                # V3 (АКТИВНАЯ СИСТЕМА)
│   ├── __main__.py                    # Entry: python -m agents.v3
│   ├── app.py                         # Startup: scheduler + bot + watchdog
│   ├── config.py                      # Конфигурация (модели, тайминги, flags)
│   ├── scheduler.py                   # APScheduler cron jobs (legacy + conductor)
│   ├── orchestrator.py                # 7 report entry points + pipeline
│   ├── runner.py                      # LangGraph agent execution
│   ├── gates.py                       # Data quality gate checker (6 gates)
│   ├── report_formatter.py            # Deterministic report formatting
│   ├── monitor.py                     # Watchdog heartbeat
│   │
│   ├── agents/                        # 25 .md agent definitions
│   │   ├── margin-analyst.md          # ✅ ACTIVE
│   │   ├── revenue-decomposer.md      # ✅ ACTIVE
│   │   ├── ad-efficiency.md           # ✅ ACTIVE
│   │   ├── report-compiler.md         # ✅ ACTIVE
│   │   ├── campaign-optimizer.md      # ✅ ACTIVE
│   │   ├── organic-vs-paid.md         # ✅ ACTIVE
│   │   ├── funnel-digitizer.md        # ✅ ACTIVE
│   │   ├── keyword-analyst.md         # ✅ ACTIVE
│   │   ├── finolog-analyst.md         # ✅ ACTIVE
│   │   ├── price-strategist.md        # ✅ ACTIVE
│   │   ├── pricing-impact-analyst.md  # ✅ ACTIVE
│   │   ├── hypothesis-tester.md       # ✅ ACTIVE
│   │   ├── prompt-tuner.md            # ✅ ACTIVE (feedback)
│   │   └── ... 12 UNUSED agents       # ❌ DEAD CODE
│   │
│   ├── conductor/                     # Smart scheduling
│   │   ├── conductor.py               # Gate → schedule → generate → validate → deliver
│   │   ├── schedule.py                # ReportType enum + расписание
│   │   ├── state.py                   # SQLite tracking (attempts, delivery, notifications)
│   │   └── validator.py               # Content quality validation
│   │
│   └── delivery/                      # Report delivery
│       ├── router.py                  # Orchestrates Notion + Telegram
│       ├── telegram.py                # Telegram HTML formatting + sending
│       └── messages.py                # Message templates
│
shared/
├── config.py                          # Env → config values (DB, tokens, models)
├── data_layer/                        # 14 SQL modules, ~4660 строк
├── notion_client.py                   # Notion API: sync_report (upsert), comments
├── notion_blocks.py                   # Markdown → Notion block format
└── clients/
    └── openrouter_client.py           # OpenRouter LLM client
```

---

## 9. Контейнеры на сервере

| Контейнер | Образ | Статус | Назначение |
|-----------|-------|--------|------------|
| wookiee_oleg | deploy-wookiee-oleg | Up | V3 bot + scheduler + reports |
| wookiee_sheets_sync | deploy-sheets-sync | Up | Google Sheets sync |
| eggent | deploy-eggent | Up | Node.js сервис (не связан с отчётами) |
| bitrix24_mcp | — | Up (healthy) | Bitrix24 MCP server |
| wb_mcp_ip | — | Up (healthy) | WB MCP (ИП) |
| wb_mcp_ooo | — | Up (healthy) | WB MCP (ООО) |
| vasily-api | — | Up (healthy) | API для локализации |
| n8n | — | Up | Автоматизации (ВОЗМОЖНЫЙ ИСТОЧНИК Telegram conflict) |
| caddy | — | Up | Reverse proxy |
