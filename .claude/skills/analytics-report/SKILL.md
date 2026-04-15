---
name: analytics-report
description: Meta-orchestrator — runs or reuses finance/marketing/funnel reports, cross-validates, produces unified Executive Summary
triggers:
  - /analytics-report
  - analytics report
  - аналитический отчёт
  - сводный отчёт
---

# Analytics Report — Meta-Orchestrator v2

Orchestrates the full analytics pipeline for Wookiee brand. Either generates all 3 deep reports from scratch (finance, marketing, funnel) or reuses existing ones, then cross-validates and produces a unified Executive Summary.

## Quick Start

```
/analytics-report 2026-04-06 2026-04-12
```

**Estimated time:**
- With existing reports: ~5 min (read → validate → synthesize → publish)
- Full pipeline: ~45-60 min (3 skills ~15 min each → validate → synthesize → publish)

**Results:**
- MD: `docs/reports/{START}_{END}_analytics.md`
- Notion: page in "Аналитические отчеты" (database `30158a2b-d587-8091-bfc3-000b83c6b747`)
- Chat: Executive Summary

---

## Stage 0: Parse Arguments & Confirm

Parse dates from user input:

- **1 date** → `START = END = date`, `DEPTH = "day"`
- **2 dates** → `START = first`, `END = second`, `DEPTH = "week"` if span ≤ 14, else `"month"`

Compute:
```
PERIOD_LABEL = "DD.MM — DD.MM.YYYY" (or "DD.MM.YYYY" for daily)
```

### Check report availability

Check if reports exist for this period:
```
docs/reports/{START}_{END}_finance.md
docs/reports/{START}_{END}_marketing.md
docs/reports/{START}_{END}_funnel.md
```

### Confirm with user BEFORE starting

**ALWAYS ask** the user what to do. Show status and options:

```
📊 Сводный аналитический отчёт ({DEPTH}) за {PERIOD_LABEL}

Статус отчётов:
  - finance.md {✅ найден / ❌ отсутствует}
  - marketing.md {✅ найден / ❌ отсутствует}
  - funnel.md {✅ найден / ❌ отсутствует}

Варианты:
1. Использовать готовые отчёты → свести в единый (быстро, ~5 мин)
2. Сгенерировать недостающие → свести в единый (~15 мин за каждый)
3. Перегенерировать ВСЕ отчёты заново → свести (~45-60 мин)

Что делаем?
```

If all 3 exist, recommend option 1. If some missing, recommend option 2. Wait for user response before proceeding.

---

### Start Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/analytics-report')
run_id = logger.start(trigger='manual', user='danila', version='v2',
    period_start='{START}', period_end='{END}', depth='{DEPTH}')
print(f'RUN_ID={run_id}')
"
```

Save `RUN_ID`. If `None` — continue, logging is fire-and-forget.

## Stage 1: Obtain Reports

Based on user's choice in Stage 0:

### Option 1: Use existing reports

Read all 3 files. Save as `finance_report`, `marketing_report`, `funnel_report`.

### Option 2: Generate missing only

For each missing report, invoke the corresponding Skill tool:
- Missing finance → `Skill("finance-report", "{START} {END}")`
- Missing marketing → `Skill("marketing-report", "{START} {END}")`
- Missing funnel → `Skill("funnel-report", "{START} {END}")`

Run missing skills sequentially (each uses significant context). Report progress after each completes. Read existing reports from files.

### Option 3: Regenerate all

Run ALL 3 skills sequentially:
1. `Skill("finance-report", "{START} {END}")` → report progress
2. `Skill("marketing-report", "{START} {END}")` → report progress
3. `Skill("funnel-report", "{START} {END}")` → report progress

After all reports are available, save as `finance_report`, `marketing_report`, `funnel_report`.

---

## Stage 2: Cross-Validation (Agent)

Read prompt: `.claude/skills/analytics-report/prompts/cross-validator.md`

Launch **Cross-Validator** as a subagent (Agent tool):

- `{{FINANCE_REPORT}}` = full finance_report text
- `{{MARKETING_REPORT}}` = full marketing_report text
- `{{FUNNEL_REPORT}}` = full funnel_report text
- `{{PERIOD_LABEL}}` = period label
- `{{DEPTH}}` = depth

The validator checks:
1. **Number consistency** — same revenue/margin/orders across reports (tolerance ±2%)
2. **Directional consistency** — if finance says margin↓, marketing shouldn't say margin↑
3. **Completeness** — each report has its required sections
4. **Data quality flags** — unified list from all 3 reports

Save output as `validation_result`.

### Verdict Handling

**PASS** (or minor discrepancies only) → proceed to Stage 3, note discrepancies.

**FAIL** (critical inconsistencies):
- Report to user which numbers conflict and by how much
- Proceed to Stage 3 with discrepancy notes included (do not block)
- The synthesizer will flag inconsistencies in the final report

---

## Stage 3: Executive Synthesis (Agent)

Read prompt: `.claude/skills/analytics-report/prompts/executive-synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch **Executive Synthesizer** as a subagent (Agent tool):

- `{{FINANCE_REPORT}}` = full finance_report text
- `{{MARKETING_REPORT}}` = full marketing_report text
- `{{FUNNEL_REPORT}}` = full funnel_report text
- `{{VALIDATION_RESULT}}` = validation_result
- `{{PERIOD_LABEL}}` = period label
- `{{DEPTH}}` = depth
- `{{NOTION_GUIDE}}` = contents of notion-formatting-guide.md

The synthesizer produces `final_document` — a unified report in pure Markdown (Notion-compatible).

### Report Structure (8 sections)

| # | Section | Source |
|---|---------|--------|
| I | Паспорт отчёта | All 3 — period, channels, data quality flags |
| II | Резюме руководителя | Top 5 findings ranked by ₽ impact, cross-linked |
| III | P&L бренда | Finance — revenue funnel, margin decomposition, plan-fact |
| IV | Модельная декомпозиция | Finance — model P&L, top/bottom models, margin waterfall |
| V | Маркетинг и реклама | Marketing — DRR, ROAS, efficiency matrix, external channels |
| VI | Воронка и конверсия | Funnel — CRO/CRP, model funnels, halo-effect, conversion |
| VII | Остатки и риски | Finance (inventory/turnover) + risk signals from all 3 |
| VIII | Рекомендации и прогноз | Merged — prioritized actions, MTD forecast, control metrics |

### Formatting Rules

1. **Pure Markdown only** — pipe-tables, `## ▶` toggle headings, `> emoji text` callouts
2. **NO HTML** — no `<table>`, `<callout>`, `<tr>`, `<td>` tags
3. **Numbers from source reports** — never recalculate or invent
4. **Cross-reference** — link findings across reports (e.g., Vuki margin↓ in finance + CRO↓ in funnel)
5. **Conflict resolution** — if reports show different values, include both with note
6. **Russian language** — all headers, terminology per analytics-kb.md
7. **Number format** — `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`
8. **Model names** — Title Case (Wendy, Vuki, Ruby)
9. **Callout usage** — `> ⚠️` warnings, `> 🔥` wins, `> 📊` data, `> 🚀` actions

---

## Stage 4: Publication

### 4.1 Save MD file

```bash
mkdir -p docs/reports
```

Write `final_document` to `docs/reports/{START}_{END}_analytics.md`

### 4.2 Publish to Notion

Use `mcp__claude_ai_Notion__notion-create-pages` with `parent.type = "data_source_id"`.

- **Database ID (data_source_id):** `30158a2b-d587-8091-bfc3-000b83c6b747`
- **Title:** `Сводный анализ за {PERIOD_LABEL}`
- **Content:** Full `final_document` (all 8 sections, NEVER truncate)
- **Properties:**
  - Тип анализа = depth-dependent (see below)
  - Источник = "Claude Code"
  - Статус = "Актуальный"
  - date:Период начала:start = `{START}` (YYYY-MM-DD)
  - date:Период конца:start = `{END}` (YYYY-MM-DD)

**Тип анализа by depth:**
- `day` → "Ежедневный сводный анализ"
- `week` → "Еженедельный сводный анализ"
- `month` → "Ежемесячный сводный анализ"

### 4.3 Chat Summary

Show executive summary in chat (10-15 lines):

```
📊 Сводный аналитический отчёт ({DEPTH}) за {PERIOD_LABEL} — готов.

Ключевые цифры:
- Выручка: X ₽ (Δ Y%)
- Маржа: X ₽ / Z% (Δ Y п.п.)
- Заказы: X шт (Δ Y%)
- ДРР: X% (внутр. A% + внешн. B%)
- CRO: X% (Δ Y п.п.)

Топ-находки:
1. {Finding — biggest ₽ impact}
2. {Finding — most actionable}
3. {Finding — risk or opportunity}

Валидация: {PASS/FAIL} ({count} расхождений)

MD: docs/reports/{START}_{END}_analytics.md
Notion: {notion_url}
```

---

### Finish Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/analytics-report')
logger.finish('{RUN_ID}', status='success',
    result_url='{NOTION_URL}',
    output_sections=8)
"
```

If `RUN_ID` is empty — skip.

## Reference Files

| File | Purpose |
|---|---|
| `prompts/cross-validator.md` | Cross-validates 3 reports |
| `prompts/executive-synthesizer.md` | Merges 3 reports into 8-section summary |
| `templates/notion-formatting-guide.md` | Notion Markdown formatting rules |
| `references/analytics-kb.md` | Analytics business rules |
| `references/data-sources.md` | Data source documentation |

**Module skills (generate source reports):**

| Skill | Trigger | Output |
|---|---|---|
| `/finance-report` | `/finance-report START END` | `docs/reports/{S}_{E}_finance.md` + Notion |
| `/marketing-report` | `/marketing-report START END` | `docs/reports/{S}_{E}_marketing.md` + Notion |
| `/funnel-report` | `/funnel-report START END` | `docs/reports/{S}_{E}_funnel.md` + Notion |

---

## Changelog

### v2 (2026-04-13)
- Complete rewrite: meta-orchestrator with 3-module architecture
- Smart report reuse: uses existing reports or generates missing ones
- Cross-validation stage for inter-report consistency
- 8-section unified report (streamlined from v1's 13)
- Pure Markdown output (fixed v1 HTML rendering issues)
- ~5 min with existing reports, ~45 min full pipeline

### v1 (2026-04-07)
- Deprecated: 12 subagents (8 analysts + 3 verifiers + synthesizer), shallow analysis
