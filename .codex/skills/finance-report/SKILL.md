---
name: finance-report
description: Deep financial analytics for Wookiee brand (WB+OZON) — P&L funnel, model decomposition, cost structure, unit economics, ΔMargin reconciliation
triggers:
  - /finance-report
  - финансовый отчёт
  - фин анализ
---

# Finance Report Skill

Deep financial analytics for the Wookiee brand (WB+OZON). Uses a 3-wave analytics engine (detect - diagnose - strategize) before generating a 12-section report with callout blocks and bold highlighting.

## Quick Start

```
/finance-report 2026-04-05                     → дневной (vs вчера)
/finance-report 2026-03-30 2026-04-05           → недельный
/finance-report 2026-03-01 2026-03-31           → месячный
```

**Время выполнения:** ~20-30 минут (коллектор ~30с, 3 волны аналитики ~8м, 2 аналитика ~10м, верификация ~3м, синтез+публикация ~6м)

**Результаты:**
- MD: `docs/reports/{START}_{END}_finance.md`
- Notion: страница в "Аналитические отчеты" (database `30158a2b-d587-8091-bfc3-000b83c6b747`)

---

## Stage 0: Parse Arguments

Parse the user's input. No questions asked — infer everything from dates.

**Input patterns:**
- 1 date → daily report (vs previous day)
- 2 dates → auto-detect depth by span

**Depth detection (2 dates):**
- Span <= 14 days → `DEPTH = "week"`
- Span > 14 days → `DEPTH = "month"`

**Compute variables:**

```
START = first date (or the single date)
END = second date (or same as START for daily)

If DEPTH == "day":
  PREV_START = START - 1 day
  PREV_END = START - 1 day
  MONTH_START = first day of START's month
  PERIOD_LABEL = "DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM.YYYY (вчера)"

If DEPTH == "week":
  PREV_START = START - (END - START + 1) days
  PREV_END = START - 1 day
  MONTH_START = first day of START's month
  PERIOD_LABEL = "DD.MM — DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM — DD.MM.YYYY (пред. неделя)"

If DEPTH == "month":
  PREV_START = same days in previous month
  PREV_END = last day of previous month
  MONTH_START = START
  PERIOD_LABEL = "Месяц YYYY"
  PREV_PERIOD_LABEL = "Месяц YYYY (пред. месяц)"
```

Save: `START`, `END`, `DEPTH`, `PREV_START`, `PREV_END`, `MONTH_START`, `PERIOD_LABEL`, `PREV_PERIOD_LABEL`.

---

## Stage 1: Data Collection

### 1.1 Financial Data

Run the Python collector:

```bash
python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/finance-report-{START}_{END}.json
```

Read the output JSON. Save the full JSON as `data_bundle`.

**Error handling:**
- Check `data_bundle["meta"]["errors"]`
- If 0-3 errors → proceed, note missing blocks as `quality_flags`
- If >3 errors → report to user and STOP
- If collector fails entirely → report error and STOP

**Data blocks available in JSON:**
- `finance` — P&L totals and by-model (WB + OZON)
- `inventory` — stock levels, turnover, ABC
- `pricing` — current prices, price history, elasticity signals
- `advertising` — ad spend, ROAS, DRR by channel (WB + OZON)
- `traffic` — visits, conversion, by source (WB)
- `sku_statuses` — model lifecycle statuses
- `sheets` — Google Sheets supplementary data

### 1.2 Plan Data Collection

Collect plan data from DB (primary) or Google Sheets (fallback):

**Primary — from DB:**
```python
PYTHONPATH=. python3 -c "
from scripts.analytics_report.collectors.plan_fact import collect_plan_fact
import json
result = collect_plan_fact('{START}', '{END}', '{MONTH_START}')
with open('/tmp/fr_slice_plan_fact.json', 'w') as f:
    json.dump(result['plan_fact'], f, ensure_ascii=False, indent=1)
"
```

Plan data comes from `plan_article` table in WB database via `shared.data_layer.planning.get_plan_by_period()`.

**Fallback — from Google Sheets:**
```bash
gws sheets get --spreadsheet-id 1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk --range "WB!A1:Z50"
```

If both fail — proceed without plan, note: "План недоступен".

---

### 1.3 Start Tool Logging

Record the run start in Supabase tool_runs:

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/finance-report')
run_id = logger.start(trigger='manual', user='danila', version='v4',
    period_start='{START}', period_end='{END}', depth='{DEPTH}')
print(f'RUN_ID={run_id}')
"
```

Save the printed `RUN_ID` value — it is needed in Stage 5.5.
If run_id is `None` — continue normally, logging is fire-and-forget.

---

## Stage 1.5: Data Validation (MANDATORY)

After collecting data, run a quick validation script to catch data integrity issues BEFORE analytics waves begin. This prevents propagating bad data through the entire pipeline.

```bash
PYTHONPATH=. python3 -c "
import json, sys
with open('/tmp/finance-report-{START}_{END}.json') as f:
    d = json.load(f)
fin = d['finance']
errors = []

# 1. WB: margin = revenue - costs (sanity check)
wb = fin['wb_total']['current'][0]
wb_margin_check = wb['revenue_before_spp'] - wb.get('cost_of_goods',0) - wb.get('commission',0) - wb.get('logistics',0) - wb.get('storage',0) - wb.get('adv_internal',0) - wb.get('adv_external',0) - wb.get('nds',0)
if abs(wb_margin_check - wb['margin']) / max(abs(wb['margin']),1) > 0.15:
    errors.append(f'WB margin sanity: computed {wb_margin_check:.0f} vs reported {wb[\"margin\"]:.0f}')

# 2. OZON: margin = revenue - costs (sanity check)
oz = fin['ozon_total']['current'][0]
oz_margin_check = oz['revenue_before_spp'] - oz.get('cost_of_goods',0) - oz.get('commission',0) - oz.get('logistics',0) - oz.get('storage',0) - oz.get('adv_internal',0) - oz.get('adv_external',0) - oz.get('nds',0)
# OZON margin formula = marga - nds; commission includes SPP + services not in simple check; 25% tolerance
if abs(oz_margin_check - oz['margin']) / max(abs(oz['margin']),1) > 0.25:
    errors.append(f'OZON margin sanity: computed {oz_margin_check:.0f} vs reported {oz[\"margin\"]:.0f}')

# 3. Margin % in reasonable range (5-40%)
for name, ch in [('WB', wb), ('OZON', oz)]:
    marg_pct = ch['margin'] / ch['revenue_before_spp'] * 100 if ch['revenue_before_spp'] else 0
    if marg_pct < 5 or marg_pct > 40:
        errors.append(f'{name} маржинальность {marg_pct:.1f}% вне диапазона 5-40%')

# 4. Sales count positive and reasonable
for name, ch in [('WB', wb), ('OZON', oz)]:
    sc = ch.get('sales_count', 0)
    if sc < 0:
        errors.append(f'{name} sales_count отрицательный: {sc}')

# 5. Revenue > 0
for name, ch in [('WB', wb), ('OZON', oz)]:
    if ch['revenue_before_spp'] <= 0:
        errors.append(f'{name} revenue_before_spp <= 0: {ch[\"revenue_before_spp\"]}')

if errors:
    print('❌ DATA VALIDATION FAILED:')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    total_rev = wb['revenue_before_spp'] + oz['revenue_before_spp']
    total_margin = wb['margin'] + oz['margin']
    print(f'✅ Data validation passed')
    print(f'  WB:   выручка {wb[\"revenue_before_spp\"]:,.0f}, маржа {wb[\"margin\"]:,.0f} ({wb[\"margin\"]/wb[\"revenue_before_spp\"]*100:.1f}%)')
    print(f'  OZON: выручка {oz[\"revenue_before_spp\"]:,.0f}, маржа {oz[\"margin\"]:,.0f} ({oz[\"margin\"]/oz[\"revenue_before_spp\"]*100:.1f}%)')
    print(f'  Итого: выручка {total_rev:,.0f}, маржа {total_margin:,.0f} ({total_margin/total_rev*100:.1f}%)')
"
```

**If validation fails** — STOP and report errors to user. Do NOT proceed to analytics waves.
**If validation passes** — print summary and proceed.

---

## Stage 2: Analytics Engine (3 sequential waves)

Three waves run SEQUENTIALLY. Each wave builds on the previous one's output.

### Wave A: Detector

Read prompt: `.claude/skills/finance-report/prompts/detector.md`
Read knowledge base: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch Detector as a subagent (Agent tool):
- **Input data:** `finance` + `inventory` + `pricing` + `sku_statuses` blocks from `data_bundle`
- **Replace placeholders:**
  - `{{DATA}}` — the 4 data blocks above (JSON)
  - `{{DEPTH}}` — "day" | "week" | "month"
  - `{{PERIOD_LABEL}}` — human-readable current period
  - `{{PREV_PERIOD_LABEL}}` — human-readable previous period
- **Inject:** full analytics-kb.md content as reference context

Save output as `findings_raw`.

### Wave B: Diagnostician

Read prompt: `.claude/skills/finance-report/prompts/diagnostician.md`

Launch Diagnostician as a subagent (Agent tool):
- **Input data:** `findings_raw` + relevant raw data slices (finance totals, model-level data, pricing, advertising)
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{RAW_DATA}}` — finance totals + model breakdown + pricing + advertising from `data_bundle`
  - `{{DEPTH}}` — "day" | "week" | "month"

**Key rule:** If external ads cut AND organic traffic dropped → LINK as cause-effect (less sales → WB demotes → less organic).

Save output as `diagnostics`.

### Wave C: Strategist

Read prompt: `.claude/skills/finance-report/prompts/strategist.md`

Launch Strategist as a subagent (Agent tool):
- **Input data:** `findings_raw` + `diagnostics`
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{DIAGNOSTICS}}` — full `diagnostics` output
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `hypotheses`.

---

## Stage 3: Deep Analysis (2 analysts in parallel)

Launch BOTH analysts in a SINGLE message (2 Agent calls in parallel). Wait for both.

### WB Analyst

Read prompt: `.claude/skills/finance-report/prompts/wb-analyst.md`

### OZON Analyst

Read prompt: `.claude/skills/finance-report/prompts/ozon-analyst.md`

Save outputs as `wb_deep` and `ozon_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/finance-report/prompts/verifier.md`

10 checks: arithmetic, margin formulas, DRR split, SPP weighted, no model dupes, no buyout-as-cause, shares sum, HIGH coverage, action direction, numbers match.

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/finance-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

**Output:** ONE `final_document_md` — clean Markdown that `md_to_notion_blocks()` converts to native Notion blocks.

### 12-Section Report Structure

| # | Section | Content |
|---|---------|---------|
| I | Паспорт отчёта | Период, каналы, качество данных (русским, не snake_case) |
| II | Топ-выводы и действия | Причинно-следственные цепочки, ⚠️ аномалии, риски с ₽-оценкой + callout |
| III | План-факт | Факт vs план из БД (plan_article), MTD + прогноз + callout |
| IV | Ключевые изменения бренда | 15+ строк с долями (% от выручки), **bold** на значимых Δ |
| V | Цены, СПП, стратегия | V.1 СПП по каналам, V.2 цены по top-10 моделям (мин/макс/волатильность), V.3 стратегия по статусам, V.4 "что если" сценарии + callout |
| VI | Сведение ΔМаржи | Waterfall: абсолют + доля тек% + доля пред% + Δ п.п. + callout |
| VII | Wildberries (deep) | VII.1-VII.6: P&L, модели, воронка, затраты, реклама, запасы |
| VIII | OZON (deep) | VIII.1-VIII.4: P&L, модели, затраты, запасы |
| IX | Драйверы и антидрайверы | WB+OZON объединены, колонка "Канал", ₽ риск/мес для антидрайверов + callout |
| X | Гипотезы → Действия | P0-P3: факт→следствие→действие→эффект→окно |
| XI | Рекомендации | Срочно / Важно / Рекомендация |
| XII | Итог | Что, почему, кто двигал, план-факт, 3 действия + callout |

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported by md_to_notion_blocks)
- **Tables:** pipe format `| Col | Col |`. Bold in cells supported: `**+187К**`
- **Toggle headings:** `## ▶` for sections, `### ▶` for subsections
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text` → native Notion callout blocks
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`, `42,8 млн`
- **Terminology:** Russian only (Себестоимость, Маржинальность, Выручка)
- **Models:** Title Case (Wendy, not wendy). Only REAL models from sku_statuses
- **Quality flags:** Russian, not snake_case ("Трафик: расхождение ~20% с PowerBI")
- **Anomalies:** Δ доли > 3 п.п. → ⚠️ mark
- **Risks:** always with ₽ estimate + time horizon

### 5.2 Save MD file

Save to `docs/reports/{START}_{END}_finance.md`.

### 5.3 Publish to Notion

Use `shared.notion_client.NotionClient.sync_report()`:

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_finance.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type='weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
```

**report_type mapping:** `day` → "daily", `week` → "weekly", `month` → "monthly"

### 5.4 Verify Notion Rendering

After publishing — fetch page via `mcp__claude_ai_Notion__notion-fetch` and verify:
- Tables render as native `<table>` blocks (not raw text)
- Toggle headings work (`{toggle="true"}`)
- Callouts render with icons and colors
- Bold text preserved in table cells

### 5.5 Finish Tool Logging

Record the run completion:

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/finance-report')
logger.finish('{RUN_ID}',
    status='success',
    result_url='{NOTION_URL}',
    items_processed={MODEL_COUNT},
    output_sections=12,
    details={
        'margin': {BRAND_MARGIN},
        'revenue': {BRAND_REVENUE},
        'depth': '{DEPTH}'
    })
print('Logged successfully')
"
```

Replace placeholders: `{RUN_ID}` from Stage 1.3, `{NOTION_URL}` from Stage 5.3, `{MODEL_COUNT}` = number of models analyzed, `{BRAND_MARGIN}` = total margin ₽, `{BRAND_REVENUE}` = total revenue ₽.
If run_id is empty/None — skip this step.

---

## Completion

Report to user (5-7 lines):
- Period analyzed and depth
- Verifier verdict
- Key finding #1 (biggest margin driver)
- Key finding #2 (most actionable recommendation)
- Key finding #3 (risk with ₽ estimate)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Wave |
|------|------|------|
| `prompts/detector.md` | Finds anomalies, significant deltas, cross-metric correlations | 2A |
| `prompts/diagnostician.md` | Determines root causes, causal chains, organic↔ads linkage | 2B |
| `prompts/strategist.md` | Generates actionable hypotheses with ₽ impact estimates | 2C |
| `prompts/wb-analyst.md` | Deep WB channel analysis (finance + inventory + pricing + traffic + ads) | 3 |
| `prompts/ozon-analyst.md` | Deep OZON channel analysis (finance + ads) | 3 |
| `prompts/verifier.md` | Cross-checks analyst outputs, 10 checks, catches contradictions | 4 |
| `prompts/synthesizer.md` | Merges all outputs into 12-section report with callouts | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec

---

## Changelog

### v4 (2026-04-13)
- NEW Stage 1.5: Data Validation — mandatory sanity checks before analytics waves (margin range, revenue > 0, costs reconciliation)
- NEW Verifier check #11: Data source integrity — detects missing return deductions in OZON revenue
- FIX: OZON revenue_before_spp now correctly deducts returns (return_end is negative)
- FIX: OZON sales_count now correctly deducts return count
- Root cause: `get_ozon_finance()` used `SUM(price_end)` without `+ COALESCE(SUM(return_end), 0)`
- Impact: all reports before 2026-04-13 overstated OZON revenue by ~5% and understated OZON marginality by ~1 п.п.

### v3 (2026-04-10)
- 14 → 12 sections (merged drivers/anti-drivers WB+OZON)
- Section V expanded: 4 subsections (SPP, prices by model with volatility, strategy by status, "what if" scenarios)
- Callout blocks: `> ⚠️`, `> 💡`, `> 📊`, `> ✅` → native Notion callouts
- Bold in table cells supported (notion_blocks.py fix)
- Plan-fact from DB (plan_article table) instead of Google Sheets
- COGS anomaly detection: if Δ share > 3 p.p. → flag ⚠️
- Organic↔external ads linkage in diagnostician
- Risks always with ₽ estimate + time horizon
- Quality flags in Russian (not snake_case)
- All cost items shown as % of revenue (shares) in ΔМаржи table
- Styling aligned with Q4 vs Q1 reference page

### v2 (2026-04-10)
- Plan-fact from DB added
- COGS analyzed in shares (% of revenue), anomalies flagged
- External ad cut → organic traffic linkage
- Risks with ₽ estimates
- 14 → 12 sections

### v1 (2026-04-08)
- Initial release: 3-wave engine + 2 parallel analysts
- 14-section report, Notion publication
