# Phase 5: Верификация - Research

**Researched:** 2026-04-01
**Domain:** Report quality verification, LLM output testing, Notion integration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Claude автономно находит лучшие отчёты за последний месяц в Notion для каждого из 8 типов
- **D-02:** Критерии отбора эталонов: длина, полнота секций, наличие реальных данных (не заглушек), глубина анализа
- **D-03:** Формат хранения эталонов — Claude решает (Notion-ссылки или локальные markdown-копии)
- **D-04:** 4 равнозначных критерия качества отчёта:
  1. Полнота данных — все секции заполнены реальными цифрами, нет заглушек
  2. Глубина анализа — monthly содержит P&L + юнит-экономику + стратегию; weekly — тренды и гипотезы; daily — компактную сводку
  3. Точность цифр — ключевые метрики (выручка, заказы, ДРР) совпадают с данными в БД
  4. Формат и читаемость — toggle-заголовки, единообразная структура, русский язык, профессиональный вид
- **D-05:** Проверка точности через SQL-запросы к БД для сверки ключевых метрик (выручка, количество заказов, ДРР). Плюс проверка адекватности (числа в разумных диапазонах, нет нолей/миллиардов)
- **D-06:** Специфика по типам:
  - Финансовые (daily/weekly/monthly): выручка WB+Ozon, заказы, маржа, ДРР с разбивкой
  - Маркетинговые (weekly/monthly): кампании, CTR, ДРР, бюджет
  - Воронка: конверсии по этапам
  - ДДС: поступления/списания по категориям
  - Локализация: логистические расходы WB
- **D-07:** Последовательно по одному типу с чекпоинтом — генерация → проверка → фикс → повторная генерация → следующий тип
- **D-08:** Порядок: daily → weekly → monthly → marketing_weekly → marketing_monthly → funnel_weekly → finolog_weekly → localization_weekly
- **D-09:** Даты для тестирования: свежие данные — вчера для daily, прошлая неделя для weekly, прошлый месяц для monthly. Claude определяет конкретные даты с полными данными в БД
- **D-10:** Запуск через существующий runner: `python scripts/run_report.py --type <type> --date <date>`
- **D-11:** Claude автономно диагностирует причину проблемы и фиксит там, где нужно:
  - Плейбуки/промпты (templates/*.md) — если LLM не следует инструкциям по структуре/глубине
  - Код pipeline/agents — если баги в передаче данных, ошибки в tools
  - Data layer — если данные не доставляются или неправильно агрегируются
- **D-12:** Количество итераций на тип — Claude решает исходя из прогресса. Нет жёсткого лимита

### Claude's Discretion

- Формат хранения эталонов (Notion-ссылки vs локальные markdown-копии)
- Конкретные SQL-запросы для сверки метрик
- Порог "приемлемого качества" для каждого типа отчёта
- Решение когда прекращать итерации (когда отчёт достаточно хорош)
- Стратегия исправления: менять плейбук, код или данные
- Использование LLM для проверки адекватности (опционально, если SQL недостаточно)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | Финансовый ежедневный отчёт генерируется корректно с полными данными | Verified pipeline path: run_report.py --type daily; template: agents/oleg/playbooks/templates/daily.md |
| RPT-02 | Финансовый еженедельный отчёт генерируется с глубоким анализом (тренды, модели, гипотезы) | template: weekly.md, depth: deep; requires multi-section validation |
| RPT-03 | Финансовый ежемесячный отчёт генерируется с максимальной глубиной (P&L, юнит-экономика, стратегия) | template: monthly.md, depth: max; highest validation bar |
| RPT-04 | Маркетинговый еженедельный отчёт генерируется корректно | Marketer agent path; template: marketing_weekly.md |
| RPT-05 | Маркетинговый ежемесячный отчёт генерируется корректно | Marketer agent path; template: marketing_monthly.md |
| RPT-06 | Воронка продаж еженедельный отчёт генерируется корректно | FunnelAgent path; build_funnel_report tool generates Python-side |
| RPT-07 | ДДС (finolog) еженедельный отчёт генерируется корректно | Data-driven template; Finolog data dependency |
| RPT-08 | Локализация еженедельный отчёт генерируется корректно | Data-driven template; wb_localization service dependency |
| VER-01 | Все 8 типов отчётов сгенерированы и проверены на реальных данных | Sequential verification cycle; DB freshness check first |
| VER-02 | Лучшие отчёты из Notion найдены и используются как эталон качества | Notion MCP search; database ID confirmed in memory |
</phase_requirements>

---

## Summary

Phase 5 is the end-to-end quality verification of all 8 report types against real production data. The infrastructure built in Phases 1-4 is fully operational: `scripts/run_report.py` is the single entry point, the pipeline handles gates/retry/validation/Notion publish, and all 8 playbook templates define expected sections. Phase 5 does not build new infrastructure — it runs the existing system, diagnoses failures, and iterates on playbooks/code/data until each report type meets the 4-criteria quality bar.

The core challenge is that report quality cannot be asserted by unit tests alone — LLM output is non-deterministic. The plan must account for a human-in-the-loop verification step per report type (inspect the Notion output), a SQL-based accuracy check of key metrics, and targeted fixes to the most likely failure points (playbook depth instructions, data tools returning empty results, or agent synthesis truncating content).

The 2-plan split suggested in STATE.md maps naturally to: Plan 1 — establish reference standards and verify financial reports (daily/weekly/monthly); Plan 2 — verify specialist reports (marketing x2, funnel, DDS, localization). Fixes discovered in either plan apply to playbooks or pipeline code and are committed atomically.

**Primary recommendation:** Run each report type against yesterday's/last week's date, inspect Notion output, SQL-verify 3-5 key metrics, fix root cause at the correct layer (playbook instructions, agent tool logic, or data layer), regenerate, then move on.

---

## Standard Stack

### Core
| Component | Version/Path | Purpose | Why Standard |
|-----------|-------------|---------|--------------|
| `scripts/run_report.py` | Phase 4 output | Entry point for all report runs | Single runner for all 8 types with --type and --date flags |
| `agents/oleg/pipeline/report_pipeline.py` | Phase 3 output | Full reliability flow (gates→LLM→validate→Notion→Telegram) | All retry, degradation, publish logic already built |
| `agents/oleg/pipeline/report_types.py` | Phase 3 output | ReportType enum + REPORT_CONFIGS | All 8 types with template_path, hard_gates, display names |
| `agents/oleg/pipeline/gate_checker.py` | Phase 3 output | Pre-flight data freshness check | 3 hard gates (WB/OZON/fin_data) block runs when data stale |
| `agents/oleg/playbooks/templates/*.md` | Phase 2 output | LLM instructions per report type | 8 templates with ## headings used for section validation |
| `shared/data_layer.py` | Project-wide | All DB queries | Mandatory per AGENTS.md — no direct psycopg2 imports elsewhere |
| `shared/notion_client.py` | Project-wide | Notion upsert via sync_report() | Single client with per-type concurrency locks |
| Notion MCP tools | MCP server | Search/read existing reports from Notion | Available via claude agent tools for finding reference reports |

### Supporting
| Component | Version/Path | Purpose | When to Use |
|-----------|-------------|---------|-------------|
| `agents/oleg/playbooks/data-map.md` | Phase 2 output | Maps tools to sections and report types | Reference when diagnosing which tool failed to populate a section |
| `tests/agents/oleg/runner/test_schedule_logic.py` | Phase 4 output | 24 unit tests for schedule logic | Run to verify no regressions after any runner changes |
| `tests/agents/oleg/playbooks/` | Phase 2 output | Playbook loader tests, depth markers | Run after any template changes to verify structure preserved |
| `python3 -m pytest tests/ -q --tb=short` | pytest 479 tests | Full test suite | Run after any code fixes to confirm no regressions |

**Installation:** No new packages needed. All dependencies installed.

---

## Architecture Patterns

### Recommended Project Structure (no changes needed)
```
scripts/
  run_report.py           # entry point — --type <type> --date <date>
agents/oleg/
  pipeline/
    report_pipeline.py   # gates → LLM → validate → Notion → Telegram
    report_types.py      # ReportType enum, REPORT_CONFIGS
    gate_checker.py      # 3 hard + 3 soft gates
  playbooks/
    templates/
      daily.md           # fix target if daily has wrong depth/sections
      weekly.md          # fix target if weekly missing trends/hypotheses
      monthly.md         # fix target if monthly missing P&L/unit-econ
      marketing_weekly.md
      marketing_monthly.md
      funnel_weekly.md
      dds.md
      localization.md
shared/
  data_layer.py          # SQL verification queries
```

### Pattern 1: Sequential Report Verification Cycle
**What:** Generate one report type, inspect Notion output, SQL-verify key metrics, fix at the correct layer, regenerate, move on.
**When to use:** For every one of the 8 report types in D-08 order.
**Steps:**
```bash
# 1. Determine date with fresh data
# 2. Generate
python3 scripts/run_report.py --type daily --date 2026-03-31

# 3. Inspect Notion (via MCP or URL from pipeline output)
# 4. SQL-verify metrics — see Pattern 3 below

# 5. If quality not met: diagnose layer, fix, regenerate
# 6. When quality met: move to next type
```

### Pattern 2: Finding Reference Reports via Notion MCP
**What:** Search Notion database for best existing reports per type using the MCP tools.
**When to use:** Plan 1, Task 1 — establish reference standards before verification starts.
**Database details:**
- Database ID: `30158a2bd58780728785cfd6db66eb82`
- Filter by: "Тип анализа" property matches report type label
- Quality criteria: longest content + all sections present + no placeholder text
**Notion type labels** (from `shared/notion_client.py`):
```python
"daily"              -> "Ежедневный фин анализ"
"weekly"             -> "Еженедельный фин анализ"
"monthly"            -> "Ежемесячный фин анализ"
"marketing_weekly"   -> "Маркетинговый анализ" (Еженедельный)
"marketing_monthly"  -> "Маркетинговый анализ" (Ежемесячный)
"funnel_weekly"      -> "Воронка продаж"
"finolog_weekly"     -> "Еженедельная сводка ДДС"
"localization_weekly"-> "Анализ логистических расходов"
```

### Pattern 3: SQL-Based Metric Accuracy Verification
**What:** Query DB for ground-truth values and compare against what the LLM report states.
**When to use:** D-05 — after each report generation as part of the 4-criteria check.
**Key queries (all via `shared/data_layer.py` as required by AGENTS.md):**

For DAILY (financial):
```python
# Total orders for the day — WB
SELECT SUM(orders_rub) FROM abc_date WHERE date = '<target_date>'

# ДРР check — must have WB internal + external split (AGENTS.md rule)
# Internal DRR:
SELECT SUM(advertising_cost) / NULLIF(SUM(orders_rub), 0) * 100
FROM advertising
WHERE date = '<target_date>'

# Margin check — from fin_data
SELECT SUM(margin) FROM fin_data WHERE date = '<target_date>'
```

For WEEKLY/MONTHLY (range):
```python
# Revenue — use LOWER() for GROUP BY per AGENTS.md mandatory rule
SELECT LOWER(SPLIT_PART(article, '/', 1)) as model, SUM(revenue)
FROM fin_data
WHERE date BETWEEN '<date_from>' AND '<date_to>'
GROUP BY LOWER(SPLIT_PART(article, '/', 1))
```

**Adequacy thresholds (D-05):**
- Revenue: must be > 0 and < 500M rubles for weekly period
- Orders (count): must be > 0 and < 100K per day
- ДРР: must be between 0% and 100%
- Margin: can be negative but not lower than -revenue

### Pattern 4: Root-Cause Diagnosis and Fix Layers
**What:** Three distinct fix targets — wrong layer = wrong fix.
**When to use:** After inspecting the generated report and identifying which criterion failed.

| Symptom | Root Cause | Fix Location |
|---------|-----------|--------------|
| Wrong sections / missing depth markers | LLM not following template | `agents/oleg/playbooks/templates/{type}.md` |
| Sections present but filled with placeholders | LLM depth instruction too vague | `agents/oleg/playbooks/templates/{type}.md` — add explicit constraint |
| Data correct but analysis too shallow | core.md or rules.md instructions not applied | `agents/oleg/playbooks/core.md` or `rules.md` |
| Placeholder text "Данные временно недоступны" | Tool returned empty/None or gate blocked | `agents/oleg/agents/{reporter,marketer,funnel}/tools/` or data_layer.py |
| Numbers in report don't match DB | Tool computing incorrectly or SQL wrong | `shared/data_layer.py` — check SQL aggregation, LOWER() rule |
| Report not published / Notion URL absent | Pipeline hard gate failed or Notion error | `scripts/run_report.py` logs, gate_checker output |
| ДДС report (RPT-07) has empty data | Finolog data not loaded | Check finolog data pipeline status, fallback to existing report structure |
| Localization report (RPT-08) has empty data | wb_localization service not run recently | Check `services/wb_localization/` recent run status |

### Anti-Patterns to Avoid
- **Running all 8 types at once as first step:** Each type has distinct failure modes; sequential order reveals dependency issues early.
- **Fixing template first without diagnosing:** If the data tool returns empty, no template fix will help — check tool logs first.
- **Comparing report to ideal, not to existing reference:** Use the actual best Notion report as the bar, not a hypothetical perfect report.
- **Regenerating without a code fix:** LLM is non-deterministic but won't suddenly produce correct data it doesn't have — fix the root cause.
- **SQL queries outside shared/data_layer.py:** AGENTS.md prohibits direct psycopg2 in verification scripts — must use data_layer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Report generation | Custom LLM call | `scripts/run_report.py --type X --date Y` | All pipeline logic (gates, retry, validate, Notion publish) already built |
| Notion search for references | Custom httpx calls | Notion MCP tools (available in agent context) | MCP tools handle auth, pagination, content extraction |
| DB metric lookup | Raw psycopg2 | `shared/data_layer.py` functions | AGENTS.md mandatory rule; GROUP BY with LOWER() already implemented |
| Section presence check | Custom regex | `_load_required_sections()` + `has_substantial_content()` in report_pipeline.py | Already parses ## headings from templates |
| Placeholder detection | Custom string search | `DEGRADATION_PLACEHOLDER` constant in report_pipeline.py | Standard placeholder string already defined |
| Test regression check | Manual inspection | `python3 -m pytest tests/ -q --tb=short` | 479 existing tests catch regressions in schedule logic, playbooks, agents |

---

## Common Pitfalls

### Pitfall 1: Gate Blocking Report Generation on Historical Dates
**What goes wrong:** Running `run_report.py --type daily --date 2026-03-25` fails because `GateChecker.check_all()` checks `MAX(dateupdate) >= target_date` — if target_date is far in the past, the gate may unexpectedly pass OR the comparison may behave oddly with timezone artifacts.
**Why it happens:** Gate is designed for "today" checks in cron context; historical verification is a different use case. `_normalize_date()` handles datetime→date conversion but dates far in past may still hit edge cases.
**How to avoid:** Use `--date` with a date that is recent enough to be within the ETL update window. D-09 specifies: yesterday for daily, last week for weekly. If gate fails, check `MAX(dateupdate)` manually via data_layer and pick a date within range.
**Warning signs:** Pipeline returns `skipped=True` with "Последнее обновление WB: X, ожидается: Y" message.

### Pitfall 2: DDS Report (RPT-07) Has No Finolog Data
**What goes wrong:** `finolog_weekly` report generates but sections are empty or contain only "Данные временно недоступны" placeholders.
**Why it happens:** DDS template (`agents/oleg/playbooks/templates/dds.md`) is data-driven — no deep LLM analysis. Data comes from Finolog API. The `finolog-cron` service was disabled in Phase 1 (Docker Compose profiles) and replaced by `run_report.py` cron, but finolog data may not have been populated since.
**How to avoid:** Before verifying RPT-07, check if finolog data exists in the DB for the target period. If not, determine if the finolog data source is available and populated, or document this as a known limitation.
**Warning signs:** DDS sections all contain placeholder text; DB query on finolog tables returns empty.

### Pitfall 3: ДРР Without Split in Financial Reports
**What goes wrong:** LLM generates a ДРР figure without separating internal (МП) and external (блогеры, ВК) advertising — violating the mandatory AGENTS.md rule.
**Why it happens:** LLM may aggregate both into a single ДРР number if the template instruction isn't explicit enough, or if `get_brand_finance` tool returns a single ДРР field.
**How to avoid:** During quality check, specifically verify that ДРР appears in the report as two separate lines: "ДРР внутренняя" and "ДРР внешняя". If not present, fix the template or the tool output format.
**Warning signs:** Report shows "ДРР: X%" as a single line without internal/external breakdown.

### Pitfall 4: GROUP BY Without LOWER() in SQL Verification Queries
**What goes wrong:** SQL verification queries show wrong totals because articles like "wendy" and "Wendy" aggregate into separate groups.
**Why it happens:** AGENTS.md mandatory rule requires `LOWER(SPLIT_PART(article, '/', 1))` for any GROUP BY on model — easy to forget when writing ad-hoc verification queries.
**How to avoid:** All SQL for metric verification MUST use `LOWER(SPLIT_PART(article, '/', 1))` for model grouping. Cross-check: if report shows model X revenue of 100K but SQL query shows 60K, LOWER() violation is the first suspect.
**Warning signs:** SQL totals don't match report numbers; totals seem lower than expected by ~20-40%.

### Pitfall 5: Template ## Heading Mismatch Breaking Section Validation
**What goes wrong:** After editing a template to improve depth instructions, the report passes generation but `has_substantial_content()` returns False and the report isn't published.
**Why it happens:** `_load_required_sections()` parses `## ` headings from the template file. If a fix changes a `## ▶ Header` to `## Header` (removing the arrow), or adds/removes headings, the validation no longer matches the LLM output.
**How to avoid:** When editing templates, preserve all `## ` headings exactly as they are. Only modify the `<!-- [depth: ...] -->` instructions inside sections. Run `python3 -m pytest tests/agents/oleg/playbooks/ -q` after any template edit.
**Warning signs:** Report generation succeeds (logs show "LLM returned substantial result") but Notion publish doesn't happen; pipeline returns `failed=True, reason="Report is all placeholders"`.

### Pitfall 6: Localization Report (RPT-08) Depends on External Service
**What goes wrong:** `localization_weekly` report generates but has no localization data.
**Why it happens:** Template is data-driven. Data comes from `services/wb_localization/` — an independent service that must be run separately. It isn't part of the Oleg pipeline.
**How to avoid:** Before verifying RPT-08, check if wb_localization data is available in the DB for a recent week. The gate checker has a soft gate for logistics data. If no data: document as known dependency and verify as much of the report structure as possible with available data.
**Warning signs:** Report has header sections but empty tables; gate soft warning shows "Логистических расходов за X: 0".

### Pitfall 7: Выкуп% Appearing as Analysis Driver in Daily Report
**What goes wrong:** The daily report (RPT-01) includes statements like "маржа упала из-за снижения выкупа" — violating the mandatory AGENTS.md analytic rule.
**Why it happens:** LLM may use Выкуп% from get_advertising_stats as a causal factor; template forbids this but LLM may not follow it consistently.
**How to avoid:** During quality check, scan the daily report for any sentence relating выкуп% to маржа changes. If found, strengthen the template instruction with a more explicit prohibition. Template already has "ЗАПРЕЩЕНО анализировать выкупы как причину изменений".
**Warning signs:** Report contains phrases like "снижение выкупа→падение маржи" or "выкуп упал до X%→влияет на доходность".

---

## Code Examples

Verified patterns from existing code:

### Running a Report Manually (entry point)
```bash
# Source: scripts/run_report.py (Phase 4)
python3 scripts/run_report.py --type daily --date 2026-03-31
python3 scripts/run_report.py --type weekly --date 2026-03-31
python3 scripts/run_report.py --type monthly --date 2026-04-01
python3 scripts/run_report.py --type marketing_weekly --date 2026-03-31
python3 scripts/run_report.py --type funnel_weekly --date 2026-03-31
python3 scripts/run_report.py --type finolog_weekly --date 2026-03-31
python3 scripts/run_report.py --type localization_weekly --date 2026-03-31
```

### Checking Section Completeness (existing validator in pipeline)
```python
# Source: agents/oleg/pipeline/report_pipeline.py
from agents.oleg.pipeline.report_pipeline import _load_required_sections, has_substantial_content
from agents.oleg.pipeline.report_types import ReportType

sections = _load_required_sections(ReportType.DAILY)
# Returns list of "## ▶ Header" strings from daily.md template
is_real = has_substantial_content(report_md, ReportType.DAILY, sections)
# Returns True if at least 1 section has non-placeholder content
```

### SQL Metric Verification Pattern (via data_layer)
```python
# Source: shared/data_layer.py (must use this, not direct psycopg2)
from shared.data_layer._connection import _db_cursor, _get_wb_connection

# Verify daily revenue total
with _db_cursor(_get_wb_connection) as (conn, cur):
    cur.execute(
        "SELECT COALESCE(SUM(revenue_rub), 0) FROM fin_data WHERE date = %s",
        (target_date,)
    )
    db_revenue = float(cur.fetchone()[0])

# Verify weekly model breakdown — MUST use LOWER() per AGENTS.md
with _db_cursor(_get_wb_connection) as (conn, cur):
    cur.execute(
        """
        SELECT LOWER(SPLIT_PART(article, '/', 1)) as model,
               SUM(revenue_rub), SUM(margin), SUM(orders_rub)
        FROM fin_data
        WHERE date BETWEEN %s AND %s
        GROUP BY LOWER(SPLIT_PART(article, '/', 1))
        ORDER BY SUM(revenue_rub) DESC
        """,
        (date_from, date_to)
    )
    rows = cur.fetchall()
```

### Notion Search for Reference Reports (MCP pattern)
```python
# Database ID from memory: 30158a2bd58780728785cfd6db66eb82
# Use Notion MCP tool: notion_query_database
# Filter: {"property": "Тип анализа", "select": {"equals": "Ежедневный фин анализ"}}
# Sort by "Период начала" descending
# Take top 5 candidates, select the one with most content and fewest placeholders
```

### Running Tests After a Fix
```bash
# Source: project test suite (479 tests, all passing as of 2026-04-01)

# After template change:
python3 -m pytest tests/agents/oleg/playbooks/ -q --tb=short

# After any pipeline/agent code change:
python3 -m pytest tests/ -q --tb=short

# Specific playbook loader test:
python3 -m pytest tests/agents/oleg/playbooks/test_loader.py -q
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| V3 LangGraph multi-agent | V2 single OlegOrchestrator with sub-agents | Phase 1 (2026-03-30) | Simpler, more reliable; no LangGraph state machine |
| Single monolithic playbook.md | Modular core.md + templates/{type}.md + rules.md | Phase 2 | Per-type depth control; DDS/localization are data-driven without depth markers |
| No pre-flight checks | GateChecker (3 hard + 3 soft gates) | Phase 3 | Reports blocked when data stale |
| No section validation | `has_substantial_content()` + graceful degradation | Phase 3 | All-placeholder reports never published |
| Manual/custom scripts | `scripts/run_report.py` unified runner | Phase 4 | Single entry point with lock-files, stubs, final notifications |

**Deprecated/outdated:**
- `agents/playbooks/playbook.md` (old monolithic): replaced by modular playbooks, archived as *_ARCHIVE.md
- `finolog-cron` Docker service: removed in Phase 4; FINOLOG_WEEKLY now runs inside wookiee-oleg via run_report.py --schedule
- `run_oleg_v2_reports.py`: superseded by scripts/run_report.py

---

## Open Questions

1. **Finolog data availability for RPT-07**
   - What we know: finolog-cron was disabled in Phase 1 and the service container removed in Phase 4. The DDS template is data-driven.
   - What's unclear: Whether the finolog data tables in the DB were populated before the service was disabled. If not, RPT-07 may generate structurally correct but empty reports.
   - Recommendation: During Plan 1/2 discovery, query the finolog tables to check data recency. If empty, document as known limitation and verify report structure only.

2. **Notion MCP tool availability during agent execution**
   - What we know: CONTEXT.md notes "Notion MCP tools доступны для поиска эталонных отчётов." The project `.mcp.json` has Notion configured.
   - What's unclear: Whether the Claude agent running the verification plan has Notion MCP available in its tool context vs. needing to use the `shared/notion_client.py` programmatically.
   - Recommendation: Plan the reference search step using the Notion MCP search tools (available in Claude Code context), not programmatic httpx calls.

3. **Date range determination for Phase 5 execution timing**
   - What we know: D-09 specifies "yesterday for daily, last week for weekly, last month for monthly." The plan runs on 2026-04-01.
   - What's unclear: Whether yesterday (2026-03-31) has complete ETL data in the DB. Gate hard-checks `MAX(dateupdate) >= target_date`.
   - Recommendation: First action of Plan 1 should be to query `MAX(dateupdate)` from abc_date (WB) and abc_date (OZON) to identify the most recent complete date, then use that for --date parameter.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.9 | All scripts | Yes | 3.9.x (system) | — |
| pytest | Test regression check | Yes | installed (479 tests collected) | — |
| DB Server (89.23.119.253:6433) | SQL metric verification, gate checks | READ-ONLY (confirmed in AGENTS.md) | PostgreSQL | Cannot write — read only per rules |
| Notion MCP | Reference report search | Yes (Claude Code context) | 2022-06-28 API | Use shared/notion_client.py programmatically |
| OpenRouter API | LLM report generation | Required (run_report.py → OpenRouterClient) | Live (env var OPENROUTER_API_KEY) | No fallback — must be available |
| Telegram Bot | Post-generation notifications | Available (env var TELEGRAM_BOT_TOKEN) | — | Telegram failure is warning not error (D-13) |
| Finolog data tables | RPT-07 DDS report | Unknown — needs verification | — | Generate structure-only report if empty |
| wb_localization data | RPT-08 localization report | Unknown — needs verification | — | Generate structure-only report if empty |

**Missing dependencies with no fallback:**
- OpenRouter API key must be set in `.env` or environment before running any report

**Missing dependencies with fallback:**
- Finolog data: if tables empty, RPT-07 will generate with placeholder content; document as known limitation
- wb_localization data: if no recent data, RPT-08 will trigger soft gate warning; generate and document

---

## Validation Architecture

**Note:** `workflow.nyquist_validation` is not set in `.planning/config.json` (key absent) — treat as enabled. However, Phase 5 is a live-system verification phase rather than a code implementation phase. Automated test assertions over LLM outputs are not viable (non-deterministic). The validation strategy here describes regression protection for any code fixes made during the phase.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none (uses pytest auto-discovery) |
| Quick run command | `python3 -m pytest tests/agents/oleg/playbooks/ -q --tb=short` |
| Full suite command | `python3 -m pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RPT-01..08 | Report generation quality | Manual inspection (LLM non-deterministic) | `python3 scripts/run_report.py --type X --date Y` + inspect Notion | N/A — manual |
| VER-01 | All 8 types generated | Smoke (run generates without exception) | `python3 scripts/run_report.py --type X --date Y` (check exit code 0) | N/A — run-time |
| VER-02 | Reference reports found | Manual Notion search | Notion MCP query | N/A — manual |
| (regression) | Template changes don't break section structure | unit | `python3 -m pytest tests/agents/oleg/playbooks/ -q --tb=short` | Yes |
| (regression) | Schedule logic unaffected by runner changes | unit | `python3 -m pytest tests/agents/oleg/runner/ -q --tb=short` | Yes |
| (regression) | Pipeline section validation unaffected | integration | `python3 -m pytest tests/ -q --tb=short` | Yes |

### Sampling Rate
- **Per fix commit:** `python3 -m pytest tests/agents/oleg/playbooks/ tests/agents/oleg/runner/ -q --tb=short`
- **Per plan completion:** `python3 -m pytest tests/ -q --tb=short` (full 479 test suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — no new test infrastructure needed. Existing 479 tests cover all regression surfaces. LLM output quality is verified manually via Notion inspection + SQL metric comparison per the verification cycle.

---

## Project Constraints (from CLAUDE.md)

These directives are mandatory and override any research findings:

| Directive | Source | Impact on This Phase |
|-----------|--------|---------------------|
| All DB queries via `shared/data_layer.py` only — no direct psycopg2 | AGENTS.md + data-quality.md | All SQL verification queries in this phase must use `_db_cursor` from data_layer |
| GROUP BY model ALWAYS with `LOWER(SPLIT_PART(article, '/', 1))` | AGENTS.md + data-quality.md | Mandatory for any model-level revenue/margin verification queries |
| ДРР ALWAYS with internal/external split | AGENTS.md + analytics.md | Quality check must verify split present in every financial report |
| Выкуп% is lagged (3-21 days) — NEVER use as daily causation driver | AGENTS.md + analytics.md | Daily report (RPT-01) quality check must verify this rule is followed |
| All LLM calls via OpenRouter only | economics.md | No direct Anthropic/z.ai calls in any verification scripts |
| App Server (77.233.212.61) = ONLY deploy target; DB Server (89.23.119.253) = READ ONLY | infrastructure.md | Verification runs locally or on app server; DB is read-only for SQL checks |
| Secrets ONLY in `.env`, never hardcoded | infrastructure.md | All verification scripts read DB/API creds from environment |
| Supabase: RLS on all tables, `anon` role blocked | infrastructure.md | If verification touches Supabase (product matrix), use authenticated client |

---

## Sources

### Primary (HIGH confidence)
- `agents/oleg/pipeline/report_pipeline.py` — Full pipeline code read directly; all 7 steps verified
- `agents/oleg/pipeline/report_types.py` — All 8 ReportType configs with template_path and hard_gates
- `agents/oleg/pipeline/gate_checker.py` — Gate logic with exact SQL queries for freshness checks
- `scripts/run_report.py` — Complete runner code with --type, --date, --schedule modes
- `agents/oleg/playbooks/templates/daily.md` — Full template with all 13 sections and depth markers
- `agents/oleg/playbooks/templates/weekly.md` — Template structure confirmed (depth: deep)
- `agents/oleg/playbooks/templates/dds.md` — Confirmed data-driven, no LLM depth markers
- `agents/oleg/playbooks/templates/localization.md` — Confirmed data-driven
- `shared/notion_client.py` — Full _REPORT_TYPE_MAP, sync_report(), database schema
- `agents/oleg/playbooks/data-map.md` — Complete tool→sections→report-types mapping
- `.planning/phases/05-verification/05-CONTEXT.md` — All D-01 through D-12 decisions
- `.planning/REQUIREMENTS.md` — RPT-01..08, VER-01, VER-02 definitions
- `AGENTS.md` / `.claude/rules/*.md` — Mandatory project rules (LOWER, ДРР split, Выкуп lag, OpenRouter)
- `python3 -m pytest tests/ --collect-only -q` — 483 tests collected, 479 pass (4 skipped)

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — Phase decisions history confirming finolog-cron disabled in Phase 1/4
- `.planning/phases/04-scheduling-delivery/04-01-SUMMARY.md` — Confirmed runner pattern and decisions
- Memory: `reference_notion_reports_db.md` — Notion database ID and schema confirmed

---

## Metadata

**Confidence breakdown:**
- Pipeline/runner understanding: HIGH — code read directly, all patterns verified
- Playbook structure: HIGH — templates read, section headings confirmed
- Notion reference search approach: HIGH — database ID confirmed, MCP tools available
- SQL verification approach: HIGH — gate_checker SQL patterns provide exact template
- Finolog/localization data availability: LOW — status unknown, needs runtime check
- LLM output quality prediction: LOW — non-deterministic; multiple iterations expected

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable domain — no external dependencies changing)
