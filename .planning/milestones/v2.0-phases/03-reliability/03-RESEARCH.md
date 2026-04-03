# Phase 3: Надёжность - Research

**Researched:** 2026-03-30
**Domain:** Pipeline reliability — pre-flight data gates, LLM retry, report section validation, Notion upsert, Telegram sequencing
**Confidence:** HIGH (all findings based on direct codebase inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pre-flight проверки данных**
- D-01: Pre-flight проверяет свежесть данных в БД (Supabase PostgreSQL), НЕ в Google Sheets
- D-02: Ключевой индикатор готовности: поле `dateupdate` в каждой таблице БД. Если `dateupdate` = сегодня → данные свежие; если дата старая → ETL ещё не прошёл, отчёт не запускаем
- D-03: Проверяются все необходимые источники: финансовые данные, рекламные данные, заказы — по WB и Ozon
- D-04: Если данные за целевой день неполные — отчёт за этот день не запускается; можно анализировать другие дни, за которые данные уже загружены
- D-05: Результат pre-flight отправляется в Telegram ("✅ Данные за X готовы: WB заказов N, выручка X%..." + список запускаемых отчётов) + запись в лог
- D-06: Механизм описан в SYSTEM.md как `pipeline/gate_checker.py` (3 hard + 3 soft data quality gates), но не реализован — создаётся в этой фазе

**Retry стратегия**
- D-07: Claude определяет критерии "пустого/неполного" ответа LLM и стратегию retry (до 2 повторов, согласно REL-02)
- D-08: Claude выбирает оптимальный уровень retry (LLM-вызов или chain) на основе анализа кода orchestrator

**Валидация полноты отчёта**
- D-09: Обязательные секции для каждого типа отчёта берутся из шаблонов Phase 2 (playbook templates модули). Валидация проверяет наличие всех ожидаемых markdown-секций
- D-10: Если данных нет совсем — pre-flight предотвращает запуск. Если отчёт формируется, но часть данных недоступна — в секцию пишется объяснение человеческим языком + предложение решения (не технический error)
- D-11: Пустой отчёт не публикуется. Порядок: retry → graceful degradation (объяснение в секции) → публикация только если есть содержательные данные

**Порядок publish+notify**
- D-12: Claude проверит текущую логику sync_report (upsert по период+тип) и убедится что она корректна для всех 8 типов отчётов (REL-06)
- D-13: Claude определяет поведение при ошибке Telegram — Notion является основным артефактом

### Claude's Discretion
- Конкретные пороги для определения "пустого" LLM-ответа (длина, структура, наличие секций)
- Уровень retry: LLM-вызов vs chain перезапуск
- Поведение при Telegram failure после успешного Notion publish
- Конкретные hard/soft gates для gate_checker (какие таблицы и поля проверять)
- Формат Telegram-сообщения о готовности данных

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REL-01 | Pre-flight проверка данных перед запуском — если данных нет, отчёт не запускается | gate_checker.py создаётся в `agents/oleg/pipeline/`; interface уже определён в DiagnosticRunner |
| REL-02 | Retry при пустом/неполном ответе LLM (до 2 повторов) | Retry встраивается в `_synthesize()` или в pipeline wrapper; пороги: len < 200 или отсутствие обязательного заголовка |
| REL-03 | Валидация полноты секций перед публикацией — пустой отчёт не публикуется в Notion | Валидатор секций вызывается между ChainResult и sync_report; шаблоны из Phase 2 дают список ожидаемых секций |
| REL-04 | Graceful degradation — если секция не может быть заполнена, пишется причина | Реализуется в report_pipeline.py как post-processing шаг перед публикацией |
| REL-05 | Каждый опубликованный отчёт содержит все обязательные секции для своего типа | Следствие REL-03 + REL-04: либо секция заполнена, либо содержит объяснение |
| REL-06 | Один отчёт = одна страница в Notion (upsert по период+тип, без дублей) | `sync_report` уже реализует upsert через `_find_existing_page`; нужно верифицировать все 8 report_type ключей |
| REL-07 | Telegram-уведомление отправляется ТОЛЬКО после успешной валидации и публикации в Notion | Порядок в report_pipeline.py: validate → publish_notion → send_telegram |
</phase_requirements>

---

## Summary

Phase 3 создаёт надёжный конвейер вокруг существующего orchestrator. Три основных компонента: (1) `gate_checker.py` — pre-flight проверка свежести данных в БД до запуска цепочки; (2) retry логика внутри pipeline при пустом/коротком LLM-ответе; (3) `report_pipeline.py` — оркестратор порядка gate_check → run_chain → validate_sections → publish_notion → send_telegram.

Все компоненты создаются в новой директории `agents/oleg/pipeline/`, которая описана в SYSTEM.md как целевая архитектура, но на момент исследования не существует. Интеграционные точки чётко определены: DiagnosticRunner уже принимает `gate_checker` параметр, NotionClient.sync_report уже реализует upsert, Alerter.send_alert уже готов к повторному использованию для pre-flight уведомлений.

**Primary recommendation:** Создать `agents/oleg/pipeline/` с тремя файлами — gate_checker.py, report_pipeline.py, report_types.py — и интегрировать их в точки входа отчётов (cron-задачи Phase 4), не изменяя существующий orchestrator.py.

---

## Standard Stack

### Core (уже в проекте, переиспользуется)
| Компонент | Расположение | Назначение | Статус |
|-----------|-------------|-----------|--------|
| DiagnosticRunner | `agents/oleg/watchdog/diagnostic.py` | Interface gate_checker (check_all → gates[].passed) | Существует — нужно подключить gate_checker |
| Alerter | `agents/oleg/watchdog/alerter.py` | send_alert для Telegram (с дедупликацией) | Существует — переиспользуется для pre-flight notify |
| NotionClient.sync_report | `shared/notion_client.py` | Upsert по период+тип, per-lock concurrency | Существует — покрывает REL-06 |
| notion_blocks.remove_empty_sections | `shared/notion_blocks.py` | Фильтрация пустых MD-секций перед конвертацией | Существует — уже вызывается в sync_report |
| data_layer | `shared/data_layer.py` | Все DB-запросы — единственный разрешённый источник | Существует — обязателен по AGENTS.md |
| shared/config.py | `shared/config.py` | Конфигурация из .env | Существует — обязателен по AGENTS.md |

### Создаётся в Phase 3 (новые файлы)
| Файл | Назначение | Подключается к |
|------|-----------|----------------|
| `agents/oleg/pipeline/gate_checker.py` | 3 hard + 3 soft data quality gates | DiagnosticRunner (параметр gate_checker) |
| `agents/oleg/pipeline/report_pipeline.py` | gate → chain → validate → publish → notify | Вызывается из cron-точек (Phase 4) |
| `agents/oleg/pipeline/report_types.py` | ReportType enum + dataclasses с метаданными | gate_checker, report_pipeline, validator |

---

## Architecture Patterns

### Рекомендуемая структура pipeline/
```
agents/oleg/pipeline/
├── __init__.py
├── gate_checker.py       # Pre-flight data quality gates
├── report_pipeline.py    # Full pipeline: gate → chain → validate → publish → notify
└── report_types.py       # ReportType enum + required sections per type
```

### Pattern 1: Gate Checker — 3 hard + 3 soft gates

**Что такое hard gate:** блокирует запуск отчёта. Если хоть один не прошёл — отчёт не запускается, Telegram уведомление о причине.

**Что такое soft gate:** не блокирует, но фиксируется в логе и упоминается в pre-flight Telegram (предупреждение).

**Hard gates (блокирующие):**
1. WB orders freshness: `SELECT MAX(dateupdate) FROM abc_date` = today
2. OZON orders freshness: аналогичная таблица OZON с полем `date_update`
3. Financial data freshness: `SELECT MAX(dateupdate) FROM fin_data` (или эквивалентная таблица финансов) = today

**Soft gates (информационные):**
1. Advertising data: рекламные расходы за сегодня > 0
2. Margin fill rate: процент артикулов с рассчитанной маржой > 50%
3. Logistics data: логистические расходы за сегодня > 0

```python
# agents/oleg/pipeline/gate_checker.py — концептуальный интерфейс
from dataclasses import dataclass, field
from typing import List
from datetime import date

@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""
    is_hard: bool = True  # hard=блокирует, soft=предупреждение

@dataclass
class CheckAllResult:
    gates: List[GateResult] = field(default_factory=list)
    target_date: date = None

    @property
    def hard_failed(self) -> List[GateResult]:
        return [g for g in self.gates if g.is_hard and not g.passed]

    @property
    def soft_warnings(self) -> List[GateResult]:
        return [g for g in self.gates if not g.is_hard and not g.passed]

    @property
    def can_run(self) -> bool:
        return len(self.hard_failed) == 0


class GateChecker:
    def check_all(self, marketplace: str = "wb", target_date: date = None) -> CheckAllResult:
        ...
```

**Важно:** DiagnosticRunner принимает `gate_checker` и вызывает `gate_checker.check_all(marketplace)`. GateChecker должен реализовывать этот интерфейс совместимо.

### Pattern 2: Report Pipeline — последовательный конвейер

```python
# agents/oleg/pipeline/report_pipeline.py — концептуальный поток
async def run_report(
    report_type: str,
    target_date: date,
    orchestrator: OlegOrchestrator,
    notion_client: NotionClient,
    alerter: Alerter,
) -> ReportPipelineResult:

    # 1. Pre-flight gate check
    gate_result = gate_checker.check_all(marketplace, target_date)
    if not gate_result.can_run:
        reason = "; ".join(g.detail for g in gate_result.hard_failed)
        logger.info(f"Pre-flight FAIL: {reason}")
        await alerter.send_alert(f"Данные за {target_date} не готовы: {reason}")
        return ReportPipelineResult(skipped=True, reason=reason)

    # 2. Send pre-flight success notify (D-05)
    await _send_preflight_success(gate_result, report_type, alerter, target_date)

    # 3. Run chain (with retry on empty result)
    chain_result = await _run_chain_with_retry(orchestrator, report_type, target_date)
    if chain_result is None:
        logger.error("Chain returned empty after retries")
        return ReportPipelineResult(failed=True, reason="LLM empty after 2 retries")

    # 4. Validate sections
    validated_md = validate_and_degrade(chain_result.detailed, report_type)
    if not has_substantial_content(validated_md):
        logger.error("Report has no substantial content after validation")
        return ReportPipelineResult(failed=True, reason="Empty report after validation")

    # 5. Publish to Notion
    notion_url = await notion_client.sync_report(
        start_date=..., end_date=..., report_md=validated_md,
        report_type=report_type,
    )
    if not notion_url:
        return ReportPipelineResult(failed=True, reason="Notion publish failed")

    # 6. Send Telegram ONLY after successful Notion publish (REL-07)
    await alerter.send_alert(chain_result.telegram_summary + f"\n\n{notion_url}")

    return ReportPipelineResult(success=True, notion_url=notion_url)
```

### Pattern 3: LLM Retry — уровень и критерии

**Решение (D-08):** Retry на уровне `_synthesize()` внутри orchestrator ИЛИ в pipeline wrapper вокруг `run_chain()`. Анализ показывает, что `run_chain()` уже обрабатывает ошибки gracefully — при пустом ответе возвращает ChainResult с пустым summary. Retry проще реализовать в pipeline wrapper (не трогая orchestrator).

**Критерии "пустого/неполного" ответа (D-07):**
- `chain_result.detailed` is None или len < 200 символов → точно пустой
- `chain_result.detailed` не содержит ни одного заголовка `##` → нет структуры
- `chain_result.summary` пустой или len < 50 → LLM не дал краткой сводки

**Retry стратегия:**
```python
async def _run_chain_with_retry(
    orchestrator, report_type, target_date, max_retries=2
) -> Optional[ChainResult]:
    for attempt in range(max_retries + 1):
        result = await orchestrator.run_chain(task=..., task_type=report_type)
        if _is_substantial(result):
            return result
        if attempt < max_retries:
            logger.warning(f"Empty LLM result, retry {attempt+1}/{max_retries}")
    return None  # все попытки исчерпаны

def _is_substantial(result: ChainResult) -> bool:
    if not result.detailed or len(result.detailed) < 200:
        return False
    if "##" not in result.detailed:
        return False
    return True
```

### Pattern 4: Section Validation и Graceful Degradation

**Источник обязательных секций:** шаблоны Phase 2 в `agents/oleg/playbooks/templates/`. Каждый шаблон содержит заголовки вида `## ▶ Название секции` (D-07 Phase 2).

**Алгоритм валидации:**
```python
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "daily": ["## ▶ Сводка дня", "## ▶ Ключевые метрики", ...],
    "weekly": ["## ▶ Итоги недели", "## ▶ Тренды", ...],
    # ... для каждого из 8 типов
}

def validate_and_degrade(report_md: str, report_type: str) -> str:
    """
    Проверяет наличие обязательных секций.
    Если секция отсутствует — добавляет заглушку с объяснением человеческим языком.
    """
    required = REQUIRED_SECTIONS.get(report_type, [])
    for section_heading in required:
        if section_heading not in report_md:
            report_md += f"\n\n{section_heading}\n\nДанные для этой секции временно недоступны. Агент не смог получить информацию. Рекомендуется проверить подключение к источникам данных и повторить отчёт завтра.\n"
    return report_md
```

**Когда report не публикуется:** только если после graceful degradation в отчёте нет ни одной реально заполненной секции (все секции — заглушки). Функция `has_substantial_content()` проверяет наличие хотя бы N секций с реальным содержимым (> заглушки по длине).

### Pattern 5: Notion upsert — верификация для 8 типов отчётов

Существующий `_REPORT_TYPE_MAP` в `shared/notion_client.py` содержит 22 записи. Нужно убедиться, что все 8 типов отчётов v2.0 имеют корректные ключи:

| Тип отчёта v2.0 | Ключ для sync_report | Notion label (результат) |
|----------------|---------------------|--------------------------|
| Финансовый ежедневный | `"daily"` | "Ежедневный фин анализ" |
| Финансовый еженедельный | `"weekly"` | "Еженедельный фин анализ" |
| Финансовый ежемесячный | `"monthly"` | "Ежемесячный фин анализ" |
| Маркетинговый еженедельный | `"marketing_weekly"` | "Маркетинговый анализ" |
| Маркетинговый ежемесячный | `"marketing_monthly"` | "Маркетинговый анализ" |
| Воронка продаж еженедельный | `"funnel_weekly"` | "funnel_weekly" (ПРОБЛЕМА — см. Pitfall 2) |
| ДДС еженедельный | `"finolog_weekly"` | "Еженедельная сводка ДДС" |
| Локализация еженедельный | `"localization_weekly"` | "Анализ логистических расходов" |

**Вывод:** 7 из 8 ключей присутствуют. Для `funnel_weekly` Notion label = "funnel_weekly" (не русский) — нужно исправить на "Воронка продаж" или аналог.

### Pattern 6: Telegram — порядок и ошибки (D-13)

**Порядок (REL-07):** Telegram ТОЛЬКО после успешного sync_report.

**Поведение при Telegram failure:** Notion является основным артефактом. Если send_alert падает после успешного sync_report — логировать ошибку, но считать pipeline успешным (report_pipeline возвращает success с предупреждением). Не делать retry Telegram в pipeline — это ответственность watchdog/alerter.

### Anti-Patterns to Avoid
- **Retry внутри orchestrator.run_chain:** orchestrator уже сложный, добавление retry туда создаст вложенную логику. Retry должен быть в pipeline wrapper.
- **Публикация до валидации:** никогда не вызывать sync_report до `validate_and_degrade()`.
- **Telegram перед Notion:** нарушает REL-07. Всегда сначала await sync_report → получить notion_url → потом send_alert.
- **Изменение shared/notion_client.py:** уже работает корректно. Менять только _REPORT_TYPE_MAP для funnel_weekly label.
- **DB запросы вне shared/data_layer.py:** нарушает AGENTS.md. Все SQL в gate_checker должны идти через data_layer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Telegram sending | Свой httpx вызов к Telegram Bot API | `Alerter.send_alert()` | Уже есть дедупликация за 5 мин (sha256 hash), обработка ошибок per-recipient |
| Notion upsert | Свой POST/PATCH к Notion API | `NotionClient.sync_report()` | Уже обрабатывает: per-report-type locks, _find_existing_page, nested blocks, конвертацию MD → Notion blocks |
| Empty section cleanup | Кастомный regex | `remove_empty_sections()` из `shared/notion_blocks.py` | Уже вызывается в sync_report, проверено в production |
| DB connectivity check | Свой psycopg2 вызов | `shared/data_layer._get_wb_connection` + `_db_cursor` | DiagnosticRunner._check_postgres уже показывает этот паттерн (строки 127-145 в diagnostic.py) |
| Gate result dataclass | Новый DTO | Расширить DiagnosticRunner interface или создать GateResult совместимый с DiagCheck | DiagnosticRunner уже итерирует `gate_result.gates[].passed` — нужна совместимость |

**Key insight:** Все retry-паттерны в advisor chain (orchestrator.py строки 645-690) показывают established pattern: 2 попытки с logger.warning на каждой — это точный шаблон для LLM retry в report pipeline.

---

## Common Pitfalls

### Pitfall 1: dateupdate — datetime vs date comparison
**What goes wrong:** `gate.check()` сравнивает `dateupdate` (который может быть `datetime`) с `date.today()` (тип `date`) → всегда False → все gates fail.
**Why it happens:** В diagnostic.py строки 196-199 уже решено: нормализация через `.date()`. Тот же паттерн нужен в gate_checker.
**How to avoid:** Всегда `last_update.date() if hasattr(last_update, 'date') else last_update`.
**Warning signs:** Gate всегда fails даже когда ETL только что отработал.

### Pitfall 2: funnel_weekly Notion label не русский
**What goes wrong:** `_REPORT_TYPE_MAP["funnel_weekly"] = ("funnel_weekly", "Воронка WB (сводный)")` — Notion label "funnel_weekly" (не русский). REL-06 требует одна страница = один upsert, но label нерусский нарушает SCHED-04.
**Why it happens:** Запись добавлялась ad-hoc, без стандартизации.
**How to avoid:** При верификации (_REPORT_TYPE_MAP для REL-06) исправить на `("Воронка продаж", "Воронка WB (сводный)")`.
**Warning signs:** В Notion Тип анализа = "funnel_weekly" (латиница).

### Pitfall 3: Section headers из шаблонов — зависимость от Phase 2
**What goes wrong:** Если Phase 2 ещё не завершена, `REQUIRED_SECTIONS` словарь нельзя заполнить точными заголовками. Hardcode неправильных заголовков → валидация всегда видит "отсутствие" секций → graceful degradation заглушки везде.
**Why it happens:** Phase 3 зависит от Phase 2 (шаблоны в `agents/oleg/playbooks/templates/`).
**How to avoid:** Реализовать `REQUIRED_SECTIONS` как загрузку из файлов шаблонов Phase 2 (парсинг `## ▶` заголовков), а не hardcode. Тогда при изменении шаблона валидация автоматически обновляется.
**Warning signs:** `REQUIRED_SECTIONS["daily"]` содержит заголовки, которых нет в actual template.

### Pitfall 4: Retry перезапускает весь chain — дорого
**What goes wrong:** Retry `run_chain()` целиком → все LLM-вызовы повторяются → стоимость удваивается/утраивается.
**Why it happens:** chain может включать reporter → researcher → advisor → synthesize. Каждый шаг — LLM call.
**How to avoid:** Retry только при пустом `_synthesize()` output, не весь chain. Если агенты дали данные, но synthesize вернул пустое — переиспользовать chain_history, повторить только `_synthesize()`. Это оптимальный уровень (D-08).
**Warning signs:** Стоимость per-report растёт линейно с retry count.

### Pitfall 5: Graceful degradation заглушка — технический текст
**What goes wrong:** В секцию пишут `"Error: tool call failed with psycopg2.OperationalError..."` → пользователь видит технический error в Notion.
**Why it happens:** Соблазн прокинуть exception message напрямую.
**How to avoid:** Заглушка всегда на русском человеческом языке с предложением решения (D-10): "Данные для этой секции временно недоступны. Рекомендуется проверить ETL-контейнер и повторить отчёт завтра."
**Warning signs:** Слова "Error", "Exception", "traceback", "psycopg2" в Notion страницах.

### Pitfall 6: Pre-flight Telegram message — формат из D-05
**What goes wrong:** Кастомный формат не соответствует утверждённому пользователем формату.
**Why it happens:** Implementer придумывает свой формат.
**How to avoid:** Строго следовать формату из CONTEXT.md specifics:
```
✅ Данные за 29 марта готовы
WB: | заказов 1021 | выручка 102% | маржа 100%
OZON: | заказов 138 | выручка 114% | маржа 100%
📊 Запускаю: Daily фин, Weekly фин, Weekly маркетинг, Weekly воронка, Weekly ценовой
```
**Warning signs:** Telegram сообщение не содержит метрик WB/OZON или список отчётов.

---

## Code Examples

### Gate checker: dateupdate проверка (pattern из diagnostic.py)
```python
# Source: agents/oleg/watchdog/diagnostic.py, lines 173-218
from shared.data_layer import _get_wb_connection, _db_cursor
from datetime import date

def _check_freshness(conn_factory, table: str, date_col: str) -> GateResult:
    with _db_cursor(conn_factory) as (conn, cur):
        cur.execute(f"SELECT MAX({date_col}) FROM {table}")
        row = cur.fetchone()
        last_update = row[0] if row else None

    if last_update is None:
        return GateResult(name=f"{table} freshness", passed=False,
                         detail=f"Нет данных в {table}.{date_col}")

    # CRITICAL: normalize datetime → date
    try:
        update_date = last_update.date()
    except AttributeError:
        update_date = last_update

    today = date.today()
    if update_date < today:
        return GateResult(name=f"{table} freshness", passed=False,
                         detail=f"Последнее обновление: {update_date}, ожидалось {today}")

    return GateResult(name=f"{table} freshness", passed=True,
                     detail=f"Данные актуальны: {update_date}")
```

### Retry wrapper pattern (адаптация из advisor_chain retry, orchestrator.py строки 645-690)
```python
# Source: agents/oleg/orchestrator/orchestrator.py, lines 645-690 (retry pattern)
async def _run_chain_with_retry(
    orchestrator: OlegOrchestrator,
    task: str,
    task_type: str,
    context: dict,
    max_retries: int = 2,
) -> Optional[ChainResult]:
    for attempt in range(max_retries + 1):
        result = await orchestrator.run_chain(task=task, task_type=task_type, context=context)
        if _is_substantial(result):
            return result
        if attempt < max_retries:
            logger.warning(
                f"Empty chain result (attempt {attempt+1}/{max_retries}), retrying"
            )
    logger.error(f"Chain returned empty after {max_retries} retries")
    return None


def _is_substantial(result: ChainResult) -> bool:
    """Check if ChainResult has actual content."""
    detailed = result.detailed or ""
    if len(detailed) < 200:
        return False
    if "##" not in detailed:  # no markdown sections
        return False
    return True
```

### Notion upsert — уже работает (reference)
```python
# Source: shared/notion_client.py, line 110-198
# sync_report already handles:
# - _find_existing_page(start_date, end_date, report_type) — upsert lookup
# - per-report-type asyncio.Lock — no concurrent duplicates
# - remove_empty_sections(report_md) — clean before convert
# - md_to_notion_blocks(report_md) — MD → Notion blocks

page_url = await notion_client.sync_report(
    start_date="2026-03-29",
    end_date="2026-03-29",
    report_md=validated_md,
    report_type="daily",  # ключ из _REPORT_TYPE_MAP
    source="Oleg v2 (auto)",
)
# Returns URL string or None on failure
```

### Pre-flight Telegram (через Alerter)
```python
# Source: agents/oleg/watchdog/alerter.py — send_alert pattern
await alerter.send_alert(
    "✅ Данные за 29 марта готовы\n"
    "WB: | заказов 1021 | выручка 102% | маржа 100%\n"
    "OZON: | заказов 138 | выручка 114% | маржа 100%\n"
    "📊 Запускаю: Daily фин, Weekly фин"
)
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| 6 hard gates, all-or-nothing (SYSTEM.md описание) | 3 hard + 3 soft (Phase 3 решение) | Soft gates не блокируют, позволяют частичные отчёты |
| Нет pre-flight | gate_checker.py с dateupdate проверкой | Пустые отчёты не запускаются |
| Нет retry (orchestrator возвращает что есть) | 2 retry в pipeline wrapper | Временные LLM failures не ломают отчёт |
| Telegram и Notion вызываются ad-hoc | pipeline: validate → publish → notify строго | REL-07 всегда соблюдается |

**pipeline/ директория:** не существует. Создаётся в Phase 3 с нуля.

---

## Open Questions

1. **Какие именно таблицы и поля для OZON freshness check?**
   - Что знаем: для WB используется `abc_date.dateupdate` (из diagnostic.py строка 184)
   - Что неясно: точное имя OZON-таблицы и колонки. В diagnostic.py `dateupdate_col = "date_update"` для OZON, таблица `abc_date` — та же или другая?
   - Рекомендация: implementer должен прочитать `shared/data_layer.py` и найти OZON-таблицы с dateupdate-полями перед написанием gate_checker.

2. **Точные заголовки шаблонов для REQUIRED_SECTIONS**
   - Что знаем: шаблоны создаются в Phase 2 (зависимость), формат `## ▶ Название`
   - Что неясно: конкретные заголовки каждого из 8 шаблонов
   - Рекомендация: gate_checker парсит заголовки из файлов шаблонов динамически, не hardcode

3. **Метрики для pre-flight success message**
   - Что знаем: формат утверждён пользователем (заказов, выручка%, маржа%)
   - Что неясно: SQL-запросы для получения этих метрик быстро (без запуска всей chain)
   - Рекомендация: gate_checker, помимо freshness, также собирает summary-метрики для Telegram

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x + asyncio | pipeline/*.py | ✓ | Python 3.9 (system) | — |
| shared/data_layer.py | gate_checker SQL | ✓ | Существует | — |
| shared/notion_client.py | REL-06 upsert | ✓ | Существует | — |
| Alerter (aiogram bot) | pre-flight Telegram | ✓ (wired in app.py) | Существует | log-only режим |
| Supabase PostgreSQL | gate freshness checks | ✓ (production) | — | Gate returns WARN, не FAIL |

**Step 2.6: No missing dependencies — все компоненты существуют в проекте.**

---

## Validation Architecture

Config: `workflow.nyquist_validation` не установлен — раздел включён.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest с asyncio_mode=auto |
| Config file | `pyproject.toml` (testpaths = ["tests"]) |
| Quick run command | `python3 -m pytest tests/oleg/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REL-01 | gate_checker.check_all() блокирует при stale dateupdate | unit | `python3 -m pytest tests/oleg/pipeline/test_gate_checker.py -x` | ❌ Wave 0 |
| REL-01 | gate_checker.check_all() пропускает при свежем dateupdate | unit | `python3 -m pytest tests/oleg/pipeline/test_gate_checker.py -x` | ❌ Wave 0 |
| REL-02 | _run_chain_with_retry: retry при коротком ответе | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_retry -x` | ❌ Wave 0 |
| REL-02 | _run_chain_with_retry: max 2 попытки | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_retry_max -x` | ❌ Wave 0 |
| REL-03 | validate_and_degrade: пустой отчёт не публикуется | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_empty_report -x` | ❌ Wave 0 |
| REL-04 | validate_and_degrade: отсутствующая секция → заглушка по-русски | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_graceful -x` | ❌ Wave 0 |
| REL-05 | Опубликованный отчёт содержит все обязательные секции | unit | (следствие REL-03+REL-04, покрывается теми же тестами) | ❌ Wave 0 |
| REL-06 | sync_report upsert: повторный вызов обновляет, не дублирует | unit (mock) | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_upsert -x` | ❌ Wave 0 |
| REL-07 | send_telegram вызывается ПОСЛЕ sync_report | unit (call order) | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_order -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/oleg/pipeline/ -x -q`
- **Per wave merge:** `python3 -m pytest tests/oleg/ -x -q`
- **Phase gate:** `python3 -m pytest tests/ -x -q` green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/oleg/pipeline/__init__.py` — пустой init
- [ ] `tests/oleg/pipeline/test_gate_checker.py` — unit тесты gate logic (mock DB)
- [ ] `tests/oleg/pipeline/test_report_pipeline.py` — unit тесты pipeline flow (mock orchestrator, notion, alerter)
- [ ] `agents/oleg/pipeline/__init__.py` — пустой init для нового модуля

Существующие тесты в `tests/oleg/` (test_orchestrator.py, test_circuit_breaker.py, etc.) не ломаются — Phase 3 не изменяет orchestrator.py.

---

## Project Constraints (from CLAUDE.md + AGENTS.md)

| Directive | Source | Impact on Phase 3 |
|-----------|--------|-------------------|
| DB запросы ТОЛЬКО через `shared/data_layer.py` | AGENTS.md | gate_checker использует `_get_wb_connection`, `_db_cursor` из data_layer |
| Конфигурация ТОЛЬКО через `shared/config.py` | AGENTS.md | pipeline компоненты читают конфиги через config, не через os.environ напрямую |
| GROUP BY по модели — ВСЕГДА с LOWER() | AGENTS.md | Если gate_checker делает GROUP BY артикулам — применять LOWER() |
| Процентные метрики — только средневзвешенные | AGENTS.md | Выручка% и маржа% в pre-flight Telegram через абсолютные значения |
| Обновлять README.md при изменении структуры | AGENTS.md | При создании `agents/oleg/pipeline/` обновить SYSTEM.md и README |
| Новые компоненты → обновить overview docs | Memory/feedback | При создании pipeline/ обновить `agents/oleg/SYSTEM.md` (pipeline/ уже в нём описан) |

---

## Sources

### Primary (HIGH confidence)
- Прямое чтение `agents/oleg/orchestrator/orchestrator.py` — структура chain, retry pattern в advisor chain
- Прямое чтение `agents/oleg/watchdog/diagnostic.py` — DiagnosticRunner interface, dateupdate нормализация
- Прямое чтение `shared/notion_client.py` — sync_report upsert, _REPORT_TYPE_MAP полный список
- Прямое чтение `agents/oleg/watchdog/alerter.py` — send_alert interface
- Прямое чтение `agents/oleg/orchestrator/chain.py` — ChainResult dataclass fields
- Прямое чтение `agents/oleg/SYSTEM.md` — целевая архитектура pipeline/
- Прямое чтение `.planning/phases/03-reliability/03-CONTEXT.md` — user decisions
- Прямое чтение `.planning/phases/02-agent-setup/02-CONTEXT.md` — шаблоны Phase 2

### Secondary (MEDIUM confidence)
- `pyproject.toml` — pytest конфигурация (asyncio_mode=auto, testpaths)
- Глобальный поиск `tests/oleg/` — существующие тесты

---

## Metadata

**Confidence breakdown:**
- Существующий код (orchestrator, notion_client, alerter, diagnostic): HIGH — прочитан напрямую
- Новые компоненты (gate_checker, report_pipeline): HIGH — паттерны взяты из существующего кода
- Section headers для REQUIRED_SECTIONS: LOW — зависят от Phase 2 output (ещё не реализованы)
- OZON-таблицы для gate freshness: LOW — требует чтения data_layer.py implementer'ом

**Research date:** 2026-03-30
**Valid until:** Стабильно — зависит от Phase 2 выходов (шаблоны)
