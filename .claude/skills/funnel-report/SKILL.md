---
name: funnel-report
description: Deep funnel analytics for Wookiee brand WB — per-model funnel (переходы→корзина→заказы→выкупы), CRO as main metric, CR each step with Δ п.п., economics, significant articles, actionable recommendations with ₽ effect
triggers:
  - /funnel-report
  - воронка продаж
  - воронка WB
  - funnel анализ
---

# Funnel Report Skill

Deep WB funnel analytics for the Wookiee brand. Uses a 3-wave analytics engine (detect → diagnose → strategize) + per-model deep analysis before generating a 13-section report with brand overview, per-model toggle sections (funnel + economics + significant articles + analysis), and TOP-3 actions with ₽ effect.

## Quick Start

```
/funnel-report 2026-04-05                     → дневной (vs вчера)
/funnel-report 2026-03-30 2026-04-05           → недельный
/funnel-report 2026-03-01 2026-03-31           → месячный
```

**Время выполнения:** ~15-25 минут (коллектор ~30с, 3 волны ~6м, модельный аналитик ~8м, верификация ~3м, синтез+публикация ~5м)

**Результаты:**
- MD: `docs/reports/{START}_{END}_funnel.md`
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
  PERIOD_LABEL = "DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM.YYYY (вчера)"

If DEPTH == "week":
  PREV_START = START - (END - START + 1) days
  PREV_END = START - 1 day
  PERIOD_LABEL = "DD.MM — DD.MM.YYYY"
  PREV_PERIOD_LABEL = "DD.MM — DD.MM.YYYY (пред. неделя)"

If DEPTH == "month":
  PREV_START = same days in previous month
  PREV_END = last day of previous month
  PERIOD_LABEL = "Месяц YYYY"
  PREV_PERIOD_LABEL = "Месяц YYYY (пред. месяц)"
```

Save: `START`, `END`, `DEPTH`, `PREV_START`, `PREV_END`, `PERIOD_LABEL`, `PREV_PERIOD_LABEL`.

---

## Stage 1: Data Collection

Run the Python collector:

```bash
python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/funnel-report-{START}_{END}.json
```

Read the output JSON. Save the full JSON as `data_bundle`.

**Error handling:**
- Check `data_bundle["meta"]["errors"]`
- If 0-3 errors → proceed, note missing blocks as `quality_flags`
- If >3 errors → report to user and STOP
- If collector fails entirely → report error and STOP

**Data blocks used in this skill:**

WB data:
- `traffic.wb_total` — brand-level funnel from content_analysis (card_opens, cart, orders, buyouts)
- `traffic.wb_content_by_model` — **PER-MODEL funnel from content_analysis** (card_opens, cart, orders, buyouts). Columns: [period, model, card_opens, add_to_cart, orders, buyouts]. This is the CORRECT source for CRO calculation.
- `traffic.wb_by_model` — **ADS-ONLY data from wb_adv** (ad_views, ad_clicks, ad_spend, ad_to_cart, ad_orders). DO NOT use for CRO calculation — it contains only advertising traffic.
- `traffic.wb_organic_vs_paid` — organic vs paid split
- `traffic.wb_skleyka_halo` — halo-effect data (склейки): which models are in each cluster, ad spend, ad orders, total cluster orders
- `advertising` — ad spend, ROMI, DRR by model
- `finance` — revenue, margin, DRR by model (WB only)
- `sku_statuses` — model lifecycle statuses (Продается / Выводим / Архив / Запуск)

OZON data:
- `traffic.ozon_total` — OZON brand-level ad funnel from adv_stats_daily. Columns: [period, ad_views, ad_clicks, ad_orders, ad_spend, ctr, cpc]
- `traffic.ozon_ad_funnel_by_model` — OZON per-model ad funnel from ozon_adv_api. Columns: [period, model, views(0), clicks, to_cart, orders, spend, ctr(0), cpc, cpo]
- `traffic.ozon_organic_estimated` — OZON organic = total_orders(abc_date) - ad_orders(ozon_adv_api). Columns: [period, model, total_orders, ad_orders, organic_orders, total_revenue, ad_spend]

**CRITICAL: For per-model WB funnel (CRO), use `traffic.wb_content_by_model`, NOT `traffic.wb_by_model`.** The latter contains only advertising clicks and will produce absurdly high CRO (>30%) because ad clicks are a fraction of total traffic while orders come from all sources.

**CRITICAL: OZON has no organic funnel data** (no equivalent of WB content_analysis). OZON organic is estimated: organic_orders = total_orders - ad_orders. Always mark as "(расч.)". No CRO for OZON — only ad click→cart→order funnel from ozon_adv_api.

**Data NOT used (other skills handle these):**
- `external_marketing` → marketing-report
- `plan_fact` → finance-report
- `inventory` → finance-report
- `pricing` → finance-report

### 1.3 Start Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/funnel-report')
run_id = logger.start(trigger='manual', user='danila', version='v1',
    period_start='{START}', period_end='{END}', depth='{DEPTH}')
print(f'RUN_ID={run_id}')
"
```

Save `RUN_ID`. If `None` — continue, logging is fire-and-forget.

---

## Stage 2: Analytics Engine (3 sequential waves)

Three waves run SEQUENTIALLY. Each wave builds on the previous one's output.

### Wave A: Detector

Read prompt: `.claude/skills/funnel-report/prompts/detector.md`
Read knowledge base: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch Detector as a subagent (Agent tool):
- **Input data:** `traffic` (all WB + OZON blocks) + `advertising` + `finance` + `sku_statuses` blocks from `data_bundle`
- **Replace placeholders:**
  - `{{DATA}}` — the 4 data blocks above (JSON)
  - `{{DEPTH}}` — "day" | "week" | "month"
  - `{{PERIOD_LABEL}}` — human-readable current period
  - `{{PREV_PERIOD_LABEL}}` — human-readable previous period
- **Inject:** full analytics-kb.md content as reference context

Save output as `findings_raw`.

### Wave B: Diagnostician

Read prompt: `.claude/skills/funnel-report/prompts/diagnostician.md`

Launch Diagnostician as a subagent (Agent tool):
- **Input data:** `findings_raw` + relevant raw data slices (traffic by model, advertising organic vs paid, finance by model)
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{RAW_DATA}}` — traffic + advertising + finance from `data_bundle`
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `diagnostics`.

### Wave C: Strategist

Read prompt: `.claude/skills/funnel-report/prompts/strategist.md`

Launch Strategist as a subagent (Agent tool):
- **Input data:** `findings_raw` + `diagnostics`
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{DIAGNOSTICS}}` — full `diagnostics` output
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `hypotheses`.

---

## Stage 3: Deep Analysis — Model Analyst

Read prompt: `.claude/skills/funnel-report/prompts/model-analyst.md`

Launch Model Analyst as a subagent (Agent tool):
- **Input data:** ALL data blocks (traffic by model, advertising organic vs paid, finance by model, sku_statuses) + `findings_raw` + `diagnostics` + `hypotheses` + analytics-kb.md
- **Task:** Generate per-model toggle sections for ALL models with status "Продается" or "Запуск" from sku_statuses.

For EACH model, produce:
1. **Воронка** — table: переходы, корзина, заказы, выкупы* + CR each step + Δ п.п. + CRO + CRP
2. **Экономика** — table: выручка, маржа, ДРР, ROMI, доля органики (переходы), доля органики (заказы)
3. **Значимые артикулы** — table: артикул, переходы, заказы, флаги (Δ >30%)
4. **Анализ** — КРИТИЧЕСКАЯ ПРОБЛЕМА or ПОЗИТИВ + ГИПОТЕЗА + расчёт эффекта ₽

Save output as `model_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/funnel-report/prompts/verifier.md`

Launch Verifier as a subagent (Agent tool) with: `model_deep` + `findings_raw` + `hypotheses` + raw data blocks.

**10 checks:**
1. Funnel math: each step <= previous step (no inversions)
2. CRO formula: CRO = orders / card_opens × 100 (must match table values)
3. CRP formula: CRP = buyouts / card_opens × 100 (check buyout lag caveat present)
4. Real models only: all from sku_statuses, no invented names
5. All "Продается" + "Запуск" models present in model sections
6. Effect calculations: correct formula (Δ CRO × переходы × avg_check × margin%)
7. Economics data matches finance block (revenue, margin, DRR)
8. Organic share formula: organic_orders / total_orders × 100
9. Buyout caveat: every buyout mention has "лаг 3-21 дн" note
10. Recommendations are specific: model + metric + base → target + ₽ effect

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/funnel-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer as a subagent (Agent tool) with ALL outputs: `findings_raw` + `diagnostics` + `hypotheses` + `model_deep` + OZON data blocks from `data_bundle` (`traffic.ozon_total` + `traffic.ozon_ad_funnel_by_model` + `traffic.ozon_organic_estimated`).

**Output:** ONE `final_document_md` — clean Markdown for Notion.

### Report Structure (Notion etalon: page 32758a2bd58781b394b4e4c4d16dfeba)

| # | Секция | Содержание |
|---|--------|------------|
| Title | Воронка WB за {PERIOD_LABEL} | Main heading |
| I | Общий обзор бренда | Table: переходы, заказы, выкупы*, выручка, маржа, ДРР — тек vs пред + Δ |
| I-b | Halo-эффект (склейки WB) | Таблица склеек: модели, артикулы, расход, рекл. заказы, все заказы, halo % |
| II-XII | Модель: {Name} — {headline} | Per-model WB toggle section (воронка + экономика + артикулы + анализ) |
| OZON-I | OZON обзор канала | Table: заказы, выручка, орг. доля (расч.), ДРР |
| OZON-II | OZON рекламная воронка | Table: клики, корзина, заказы, расходы, CTR, CPC (adv_stats_daily) |
| OZON per-model | OZON: {Name} — заказы {Δ}% | Toggle: заказы+органика + рекламная воронка (если есть клики) |
| XIII | Выводы и рекомендации | ТОП-3 действия + общий потенциал роста маржи |

**OZON toggle header format:** `## ▶ OZON: {Name} {emoji} — заказы {+/-n}%`
**OZON per-model subsections:**
- `### Заказы и органика` — total_orders, organic_orders (расч.), org_share, revenue, ad_spend, DRR
- `### Рекламная воронка` — clicks, to_cart, orders, CR click→cart, CR click→order, spend, CPC (only if clicks > 0)
**OZON rules:**
- NO CRO (no organic funnel data on OZON)
- NO выкупы / CRP in OZON sections
- Organic always marked "(расч.)"
- Skip models with 0 orders in both current and previous

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported)
- **Tables:** pipe format `| Col | Col |`. Bold in cells: `**+187К**`
- **Toggle headings:** `## Модель: Name — headline {toggle="true"}` for per-model sections
- **Subsections inside toggle:** tab-indented `### Воронка`, `### Экономика`, `### Значимые артикулы`, `### Анализ`
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text`
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`
- **Terminology:** Russian ONLY
- **Models:** Title Case (Wendy, not wendy). Only REAL models from sku_statuses
- **Buyout caveat:** `\*Данные по выкупам неполные (лаг 3-21 день)` after every buyout table row
- **CRO = MAIN metric.** Always highlight CRO changes in toggle headlines

### 5.2 Save MD file

Save to `docs/reports/{START}_{END}_funnel.md`.

### 5.3 Publish to Notion

Use `shared.notion_client.NotionClient.sync_report()`:

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_funnel.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type='funnel_weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
```

**report_type mapping:** `day` → "funnel_daily", `week` → "funnel_weekly", `month` → "funnel_monthly"

### 5.4 Verify Notion Rendering

After publishing — fetch page via `mcp__claude_ai_Notion__notion-fetch` and verify:
- Tables render as native table blocks
- Toggle headings work (`{toggle="true"}`)
- Callouts render with icons
- Bold text preserved in table cells
- Buyout caveats visible

### 5.5 Finish Tool Logging

```bash
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
logger = ToolLogger('/funnel-report')
logger.finish('{RUN_ID}', status='success',
    result_url='{NOTION_URL}',
    items_processed={MODEL_COUNT},
    output_sections=8)
"
```

If `RUN_ID` is empty — skip.

---

## Completion

Report to user (5-7 lines):
- Period analyzed and depth
- Verifier verdict
- Number of models analyzed (N "Продается" + M "Запуск")
- Top CRO finding (which model, Δ CRO, effect ₽)
- Top recommendation (model + action + ₽ effect)
- Total growth potential (sum of all TOP-3 effects)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Stage |
|------|------|-------|
| `prompts/detector.md` | Funnel anomaly detection — CR each step per model, significant articles | 2A |
| `prompts/diagnostician.md` | Root causes — CRO drop analysis, traffic quality, OOS | 2B |
| `prompts/strategist.md` | CRO restoration actions with ₽ effect | 2C |
| `prompts/model-analyst.md` | Per-model deep toggle sections (funnel + economics + articles + analysis) | 3 |
| `prompts/verifier.md` | 10 funnel-specific checks — math, formulas, models, effects | 4 |
| `prompts/synthesizer.md` | 13-section report assembly: brand overview + per-model toggles + TOP-3 conclusions | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec

---

## Changelog

### v2 (2026-04-15)
- OZON channel added: OZON-I (overview), OZON-II (ad funnel), per-model OZON toggles
- OZON data blocks: ozon_total, ozon_ad_funnel_by_model, ozon_organic_estimated
- Synthesizer receives OZON data and generates OZON sections after WB models
- Verifier check #11: validates OZON sections (no CRO/CRP, organic marked "(расч.)")
- Detector outputs OZON_OVERVIEW section with channel summary

### v1 (2026-04-12)
- Initial release: 3-wave engine + model analyst + verifier + synthesizer
- Per-model toggle sections with funnel, economics, significant articles, analysis
- CRO as main metric, effect calculations in ₽
- Notion publication with toggle support
