---
name: marketing-report
description: Deep marketing analytics for Wookiee brand (WB+OZON) — funnel analysis, DRR decomposition, model efficiency matrix, organic vs paid, external ads (bloggers/VK/SMM)
triggers:
  - /marketing-report
  - маркетинговый отчёт
  - маркетинг анализ
---

# Marketing Report Skill

Deep marketing analytics for the Wookiee brand (WB+OZON). Uses a 3-wave analytics engine (detect → diagnose → strategize) before generating an 11-section report with funnel analysis, DRR decomposition, model efficiency matrix, and external ad breakdown.

## Quick Start

```
/marketing-report 2026-04-05                     → дневной (vs вчера)
/marketing-report 2026-03-30 2026-04-05           → недельный
/marketing-report 2026-03-01 2026-03-31           → месячный
```

**Время выполнения:** ~20-30 минут (коллектор ~30с, 3 волны аналитики ~8м, 2 аналитика ~10м, верификация ~3м, синтез+публикация ~6м)

**Результаты:**
- MD: `docs/reports/{START}_{END}_marketing.md`
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

### 1.1 Marketing Data

Run the Python collector:

```bash
python3 scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/marketing-report-{START}_{END}.json
```

Read the output JSON. Save the full JSON as `data_bundle`.

**Error handling:**
- Check `data_bundle["meta"]["errors"]`
- If 0-3 errors → proceed, note missing blocks as `quality_flags`
- If >3 errors → report to user and STOP
- If collector fails entirely → report error and STOP

**Data blocks used in this skill:**
- `finance` — P&L totals and by-model (WB + OZON)
- `advertising` — ad spend, ROAS, DRR by channel (WB + OZON), organic vs paid split
- `external_marketing` — bloggers, VK, Yandex, SMM spend and attribution
- `traffic` — visits, conversion, by source (WB)
- `sku_statuses` — model lifecycle statuses (Growth / Harvest / Optimize / Cut)

---

## Stage 2: Analytics Engine (3 sequential waves)

Three waves run SEQUENTIALLY. Each wave builds on the previous one's output.

### Wave A: Detector

Read prompt: `.claude/skills/marketing-report/prompts/detector.md`
Read knowledge base: `.claude/skills/analytics-report/references/analytics-kb.md`

Launch Detector as a subagent (Agent tool):
- **Input data:** `advertising` + `traffic` + `finance` + `external_marketing` + `sku_statuses` blocks from `data_bundle`
- **Replace placeholders:**
  - `{{DATA}}` — the 5 data blocks above (JSON)
  - `{{DEPTH}}` — "day" | "week" | "month"
  - `{{PERIOD_LABEL}}` — human-readable current period
  - `{{PREV_PERIOD_LABEL}}` — human-readable previous period
- **Inject:** full analytics-kb.md content as reference context

Save output as `findings_raw`.

### Wave B: Diagnostician

Read prompt: `.claude/skills/marketing-report/prompts/diagnostician.md`

Launch Diagnostician as a subagent (Agent tool):
- **Input data:** `findings_raw` + relevant raw data slices (advertising totals, traffic, finance, external_marketing)
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{RAW_DATA}}` — advertising + traffic + finance totals + external_marketing from `data_bundle`
  - `{{DEPTH}}` — "day" | "week" | "month"

**Key rule:** If external ads cut AND organic traffic dropped → LINK as cause-effect (less sales → WB demotes → less organic).

Save output as `diagnostics`.

### Wave C: Strategist

Read prompt: `.claude/skills/marketing-report/prompts/strategist.md`

Launch Strategist as a subagent (Agent tool):
- **Input data:** `findings_raw` + `diagnostics`
- **Replace placeholders:**
  - `{{FINDINGS}}` — full `findings_raw` output
  - `{{DIAGNOSTICS}}` — full `diagnostics` output
  - `{{DEPTH}}` — "day" | "week" | "month"

Save output as `hypotheses`.

---

## Stage 3: Deep Analysis (2 analysts in parallel)

Launch BOTH analysts in a SINGLE message (2 Agent calls in parallel). Wait for both to complete before proceeding.

### Performance Analyst

Read prompt: `.claude/skills/marketing-report/prompts/performance-analyst.md`

Launch Performance Analyst as a subagent (Agent tool):
- **Input data:** `finance` (totals + by-model) + `advertising` (all) + `external_marketing` + `sku_statuses` + `findings_raw` + `diagnostics` + `hypotheses` + analytics-kb.md
- **Produces:** sections II (Channel P&L), V (External Ads), VI (Model Matrix), VII (Daily Dynamics), VIII (Avg Check + DRR)

Save output as `performance_deep`.

### Funnel Analyst

Read prompt: `.claude/skills/marketing-report/prompts/funnel-analyst.md`

Launch Funnel Analyst as a subagent (Agent tool):
- **Input data:** `traffic` + `advertising` (organic_vs_paid, daily_series) + `finance` (totals) + `findings_raw` + `diagnostics` + analytics-kb.md
- **Produces:** sections III (Funnel Analysis), IV (Organic vs Paid)

Save output as `funnel_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/marketing-report/prompts/verifier.md`

Launch Verifier as a subagent (Agent tool) with: `performance_deep` + `funnel_deep` + `findings_raw` + `hypotheses` + raw data blocks.

**10 checks:**
1. DRR split present (внутренняя МП и внешняя отдельно — нельзя объединять)
2. Dual KPI for each ad channel (spend + orders or ROAS — not spend alone)
3. Funnel math: each stage ≤ previous stage (no funnel inversions)
4. ROMI formula correct: `(revenue - ad_spend) / ad_spend * 100`
5. Organic + paid = total traffic (shares sum to 100%, within ±1%)
6. Matrix coverage: all models from sku_statuses appear in matrix (Growth/Harvest/Optimize/Cut)
7. Real models only: no invented model names — all from sku_statuses
8. ASCII funnel numbers match source data (spot-check 2 funnels)
9. Google Sheets / external data sourced correctly and noted
10. Action direction: every recommendation has a direction (increase/decrease/pause/test)

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/marketing-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer as a subagent (Agent tool) with ALL outputs: `findings_raw` + `diagnostics` + `hypotheses` + `performance_deep` + `funnel_deep`.

**Output:** ONE `final_document_md` — clean Markdown that `md_to_notion_blocks()` converts to native Notion blocks.

### 11-Section Report Structure

| # | Section | Content |
|---|---------|---------|
| I | Исполнительная сводка | Таблица: метрика/значение/Δ/статус + резюме 3-5 строк |
| II | Анализ по каналам | WB P&L маркетинга + OZON P&L маркетинга + ключевые выводы |
| III | Анализ воронки | WB organic ASCII + WB ad ASCII + OZON ad ASCII + бенчмарки |
| IV | Органик vs Платное | 3 таблицы: доли, динамика, конверсии + инсайт-callout |
| V | Внешняя реклама | Сводная разбивка каналов + V.1 Блогеры + V.2 VK/Яндекс + V.3 SMM |
| VI | Матрица эффективности моделей | Growth/Harvest/Optimize/Cut + WB детали + OZON детали |
| VII | Дневная динамика | WB по дням + OZON по дням (таблицы) |
| VIII | Средний чек и ДРР | Таблица ср. чек по моделям + рекомендации по ассортименту |
| IX | Рекомендации | Срочные (P0) + Оптимизация (P1) + Стратегические (P2) |
| X | Прогноз | Таблица прогноза + Риски + Возможности |
| XI | Advisor | 🔴🟡🟢 по каждому каналу с confidence% |

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported by md_to_notion_blocks)
- **Tables:** pipe format `| Col | Col |`. Bold in cells supported: `**+187К**`
- **Toggle headings:** `## ▶` for sections, `### ▶` for subsections
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text` → native Notion callout blocks
- **ASCII funnels:** in triple-backtick code blocks (``` ``` ```) — not plain text
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`, `42,8 млн`
- **Terminology:** Russian only (ДРР, Выручка, Органик, Воронка, Маржинальность)
- **Models:** Title Case (Wendy, not wendy). Only REAL models from sku_statuses
- **Anomalies:** Δ ДРР > 2 п.п. → ⚠️ mark; organic share drop > 5 п.п. → ⚠️ mark
- **Risks:** always with ₽ estimate + time horizon
- **ДРР:** ALWAYS split — внутренняя (МП) и внешняя (блогеры, VK) — never combined

### 5.2 Save MD file

Save to `docs/reports/{START}_{END}_marketing.md`.

### 5.3 Publish to Notion

Use `shared.notion_client.NotionClient.sync_report()`:

```python
PYTHONPATH=. python3 -c "
import asyncio, os
from dotenv import load_dotenv; load_dotenv()
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{START}_{END}_marketing.md').read_text()
    client = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
    url = await client.sync_report(start_date='{START}', end_date='{END}', report_md=md, report_type='marketing_weekly', source='Claude Code')
    print(f'Published: {url}')

asyncio.run(main())
"
```

**report_type mapping:** `day` → "marketing_daily", `week` → "marketing_weekly", `month` → "marketing_monthly"

### 5.4 Verify Notion Rendering

After publishing — fetch page via `mcp__claude_ai_Notion__notion-fetch` and verify:
- Tables render as native `<table>` blocks (not raw text)
- Toggle headings work (`{toggle="true"}`)
- Callouts render with icons and colors
- ASCII funnels preserved inside code blocks
- Bold text preserved in table cells

---

## Completion

Report to user (5-7 lines):
- Period analyzed and depth
- Verifier verdict
- Key DRR finding (внутренняя vs внешняя, Δ п.п.)
- Key funnel finding (organic share shift or conversion anomaly)
- Model recommendation (top Growth model to scale or Cut model to pause)
- External ad verdict (bloggers/VK: effective / ineffective with ₽ estimate)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Wave |
|------|------|------|
| `prompts/detector.md` | Marketing anomaly detection — DRR spikes, traffic drops, ad efficiency shifts | 2A |
| `prompts/diagnostician.md` | Root causes — ads↔organic linkage, external cut → organic drop | 2B |
| `prompts/strategist.md` | Budget reallocation, model actions, channel prioritization | 2C |
| `prompts/performance-analyst.md` | Channels P&L + model matrix + daily dynamics + external ads + avg check | 3 |
| `prompts/funnel-analyst.md` | ASCII funnels (WB organic, WB ad, OZON ad) + organic vs paid analysis | 3 |
| `prompts/verifier.md` | 10 marketing-specific checks — DRR split, funnel math, ROMI formula | 4 |
| `prompts/synthesizer.md` | 11-section report assembly with callouts and ASCII funnels | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec
