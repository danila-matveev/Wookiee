---
name: marketing-report
description: Deep marketing analytics for Wookiee brand (WB+OZON) — P&L funnel per channel, 3 traffic funnels, real Sheets data (bloggers/VK/SMM), all 37 models, actionable recommendations
triggers:
  - /marketing-report
  - маркетинговый отчёт
  - маркетинг анализ
---

# Marketing Report Skill

Deep marketing analytics for the Wookiee brand (WB+OZON). Uses a 3-wave analytics engine (detect -> diagnose -> strategize) before generating a 10-section report with P&L funnel per channel, 3 traffic funnels, real external ad data from Google Sheets, all 37 models with Russian lifecycle categories, and specific actionable recommendations.

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
- `sku_statuses` — model lifecycle statuses (Рост / Сбор / Оптимизация / Стоп)
- `skleyki` — WB card group performance: per-group revenue, margin, ads, ROMI, cross-model flags

**CRITICAL: wb_external_breakdown columns:**
`period`, `adv_internal` (МП), `adv_bloggers` (блогеры), `adv_vk` (ВК), `adv_creators` (=0, не используется), `adv_total`. The 183К value is `adv_vk` (ВК), NOT `adv_creators`!

### 1.2 External Ad Data from Google Sheets

Parse REAL data from 3 Google Sheets, filtered by period dates:

**Блогеры (Sheet ID: 1Y7ux...):**
```bash
gws sheets get --spreadsheet-id {BLOGGERS_SHEET_ID} --range "A1:Z200"
```
Filter rows where "Дата публикации" column falls within `[START, END]`.

**ВК/Яндекс (Sheet ID: 1h0Ne...):**
```bash
gws sheets get --spreadsheet-id {VK_SHEET_ID} --range "A1:Z200"
```
Filter rows by date columns within `[START, END]`.

**SMM (Sheet ID: 19NXH...):**
```bash
gws sheets get --spreadsheet-id {SMM_SHEET_ID} --range "A1:Z200"
```
Filter rows by date columns within `[START, END]`.

Save parsed data as `sheets_bloggers`, `sheets_vk`, `sheets_smm`. If a sheet fails — note in quality_flags, proceed with DB data only.

---

## Stage 1.5: Data Validation (MANDATORY)

After collecting data, run a quick validation script to catch data integrity issues BEFORE analytics waves begin. This prevents propagating bad data through the entire pipeline.

```bash
PYTHONPATH=. python3 -c "
import json, sys
with open('/tmp/marketing-report-{START}_{END}.json') as f:
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
- **Input data:** `finance` (totals + by-model) + `advertising` (all) + `external_marketing` + `sku_statuses` + `skleyki` (card group performance) + `findings_raw` + `diagnostics` + `hypotheses` + analytics-kb.md
- **Produces:** sections II (P&L воронка по каналам), V (Внутренняя реклама МП), V.5 (Кросс-атрибуция склеек), VI (Эффективность по моделям), VII (Средний чек и ассортимент)

Save output as `performance_deep`.

### Funnel Analyst

Read prompt: `.claude/skills/marketing-report/prompts/funnel-analyst.md`

Launch Funnel Analyst as a subagent (Agent tool):
- **Input data:** `traffic` + `advertising` (organic_vs_paid, daily_series) + `finance` (totals) + `sheets_bloggers` + `sheets_vk` + `sheets_smm` + `findings_raw` + `diagnostics` + analytics-kb.md
- **Produces:** sections III (Воронки трафика), IV (Внешняя реклама)

Save output as `funnel_deep`.

---

## Stage 4: Verification

Read prompt: `.claude/skills/marketing-report/prompts/verifier.md`

Launch Verifier as a subagent (Agent tool) with: `performance_deep` + `funnel_deep` + `findings_raw` + `hypotheses` + raw data blocks.

**10 checks:**
1. ДРР split present (внутренняя МП и внешняя отдельно — нельзя объединять)
2. Dual KPI for each ad channel (spend + orders or ROAS — not spend alone)
3. Funnel math: each stage <= previous stage (no funnel inversions)
4. ROMI formula correct: `(revenue - ad_spend) / ad_spend * 100`
5. 3 traffic funnels present: внешний, внутренний МП, органика. Органика = total - внутренняя - внешняя
6. All 37 models from sku_statuses appear in model analysis (Рост/Сбор/Оптимизация/Стоп — Russian only)
7. Real models only: no invented model names — all from sku_statuses
8. Sheets data sourced correctly: bloggers filtered by "Дата публикации", VK/SMM by date columns
9. Recommendations are SPECIFIC: model name + channel + конкретное действие + сумма в ₽ (not "масштабировать")
10. Forecast in ₽ (Выручка, Маржа, ДРР) — NOT in штуки

**Verdict:** APPROVE / CORRECT / REJECT (max 1 retry).

---

## Stage 5: Synthesis + Publication

### 5.1 Synthesis

Read prompt: `.claude/skills/marketing-report/prompts/synthesizer.md`
Read formatting guide: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer as a subagent (Agent tool) with ALL outputs: `findings_raw` + `diagnostics` + `hypotheses` + `performance_deep` + `funnel_deep`.

**Output:** ONE `final_document_md` — clean Markdown that `md_to_notion_blocks()` converts to native Notion blocks.

### 10-Section Report Structure

| # | Секция | Содержание |
|---|--------|------------|
| 0 | Паспорт отчёта | Период, источники данных (БД WB, БД OZON, Google Sheets блогеры/ВК/SMM), с чем сравниваем, качество данных |
| I | Исполнительная сводка | Короткие буллеты (NOT стена текста). Каждый буллет = метрика + дельта + причина |
| II | P&L воронка по каналам | ПОЛНАЯ воронка на канал (WB, затем OZON): Показы → Переходы → Корзина → Заказы → Выкупы → Комиссия МП → Логистика → Хранение → Себестоимость → Маржа. С CR между каждым шагом. КЛЮЧЕВОЙ аналитический блок |
| III | Воронки трафика | 3 отдельных воронки: (a) внешний трафик (блогеры+ВК→переходы→заказы), (b) внутренняя реклама МП (показы→клики→корзина→заказы), (c) органика = total - внутренняя - внешняя. ASCII-диаграммы |
| IV | Внешняя реклама | РЕАЛЬНЫЕ данные из Google Sheets: блогеры (Sheet 1Y7ux, фильтр по "Дата публикации"), ВК/Яндекс (Sheet 1h0Ne), SMM (Sheet 19NXH). Парсинг и фильтрация по периоду. Dual KPI на каждый канал |
| V | Внутренняя реклама МП | Дневная динамика, кампании, эффективность рекламы по моделям. Объединяет старые секции VI+VII |
| V.5 | Кросс-атрибуция рекламы (склейки WB) | Групповой ROMI по склейкам, TOP-3 детализация, флаги кросс-атрибуции для рекомендаций. Данные из `skleyki.wb` |
| VI | Эффективность по моделям | ВСЕ 37 моделей из sku_statuses. Русские категории: Рост/Сбор/Оптимизация/Стоп. Конкретные рекомендации по каждой модели ("увеличить бюджет внутренней рекламы на 15К₽/нед" — НЕ "масштабировать") |
| VII | Средний чек и ассортимент | ВСЕ модели, анализ ассортимента, что продвигать для роста чека |
| VIII | Рекомендации и план действий | ОБЪЕДИНЕНО из старых IX+XI. Один блок: Срочные (сегодня) → Неделя → Месяц. Каждая рекомендация = конкретное действие + модель/канал + внутренняя/внешняя + ₽ эффект |
| IX | Прогноз | В ₽ (НЕ штуки!). Выручка, маржа, ДРР — прогноз с ₽ диапазонами |

### Formatting Rules

- **ONLY clean Markdown.** NO HTML (`<table>`, `<tr>`, `<callout>` — not supported by md_to_notion_blocks)
- **Tables:** pipe format `| Col | Col |`. Bold in cells supported: `**+187К**`
- **Toggle headings:** `## ▶` for sections, `### ▶` for subsections
- **Callouts:** `> ⚠️ text`, `> 💡 text`, `> 📊 text`, `> ✅ text` → native Notion callout blocks
- **ASCII funnels:** in triple-backtick code blocks — not plain text
- **Numbers:** `1 234 567 ₽`, `24,1%`, `+3,2 п.п.`, `8,8М`, `42,8 млн`
- **Terminology:** Russian ONLY (ДРР, Выручка, Органик, Воронка, Маржинальность)
- **Lifecycle categories:** Russian ONLY — Рост (not Growth), Сбор (not Harvest), Оптимизация (not Optimize), Стоп (not Cut)
- **Models:** Title Case (Wendy, not wendy). Only REAL models from sku_statuses. ALL 37 models must appear
- **Recommendations:** SPECIFIC — "увеличить бюджет внутренней рекламы Charlotte WB на 15К₽/нед" NOT "масштабировать"
- **Anomalies:** Δ ДРР > 2 п.п. → mark; organic share drop > 5 п.п. → mark
- **Risks:** always with ₽ estimate + time horizon
- **ДРР:** ALWAYS split — внутренняя (МП) и внешняя (блогеры, VK) — never combined
- **Forecast:** ALWAYS in ₽ (Выручка, Маржа) — never in штуки

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
- Model recommendation (top Рост model to scale or Стоп model to pause)
- External ad verdict (блогеры/ВК: effective / ineffective with ₽ estimate)
- Files: MD path + Notion link

---

## Prompt Files Reference

| File | Role | Wave |
|------|------|------|
| `prompts/detector.md` | Marketing anomaly detection — DRR spikes, traffic drops, ad efficiency shifts, correct column mapping (adv_vk != adv_creators) | 2A |
| `prompts/diagnostician.md` | Root causes — ads<->organic linkage, external cut → organic drop | 2B |
| `prompts/strategist.md` | Budget reallocation, model actions, channel prioritization | 2C |
| `prompts/performance-analyst.md` | P&L воронка по каналам + внутренняя реклама МП + все 37 моделей + средний чек | 3 |
| `prompts/funnel-analyst.md` | 3 воронки трафика (внешний, внутренний МП, органика) + внешняя реклама из Sheets | 3 |
| `prompts/verifier.md` | 10 marketing-specific checks — DRR split, funnel math, all models, specific recommendations, forecast in ₽ | 4 |
| `prompts/synthesizer.md` | 10-section report assembly: паспорт, буллеты-сводка, P&L воронка, 3 воронки, рекомендации, прогноз в ₽ | 5 |

**External references (read-only):**
- `.claude/skills/analytics-report/references/analytics-kb.md` — unified knowledge base
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md` — Notion formatting spec

---

## Changelog

### v4 (2026-04-13)
- NEW Section V.5: Кросс-атрибуция рекламы (склейки WB) — групповой ROMI по карточным группам
- NEW Collector: `collect_skleyki()` — агрегирует WB article data по склейкам из Supabase
- NEW data block: `skleyki.wb` — per-group revenue, margin, ads, ROMI, cross-model flags, article breakdown
- Performance Analyst now receives `{{SKLEYKI}}` input and produces Section V.5
- Key insight: 74% рекламного бюджета WB проходит через кросс-модельные склейки, искажая ROMI по моделям

### v3 (2026-04-13)
- NEW Stage 1.5: Data Validation — mandatory sanity checks before analytics waves (margin range, revenue > 0, costs reconciliation)
- NEW Verifier check #14: Data source integrity — detects missing return deductions in OZON revenue
- FIX: OZON revenue_before_spp now correctly deducts returns (shared fix with finance-report)
- Impact: all marketing reports before 2026-04-13 overstated OZON revenue by ~5%

### v2 (2026-04-11)
- 11 → 10 sections: removed Advisor (merged into Рекомендации), removed separate Органик vs Платное (merged into Воронки трафика)
- NEW Section 0: Паспорт отчёта (период, источники, качество данных)
- Section I: Исполнительная сводка rewritten as short bullet points (metric + delta + cause), not wall of text
- Section II: P&L воронка по каналам — FULL funnel per channel (Показы → Переходы → Корзина → Заказы → Выкупы → Комиссия → Логистика → Хранение → Себестоимость → Маржа) with CR between steps
- Section III: 3 separate traffic funnels (внешний, внутренний МП, органика = total - internal - external)
- Section IV: Real external ad data from Google Sheets (блогеры/ВК/SMM parsed by period dates)
- Section V: Merged internal ad sections (old VI+VII) into one block
- Section VI: ALL 37 models from sku_statuses, Russian categories (Рост/Сбор/Оптимизация/Стоп), specific recommendations
- Section VIII: Merged old Рекомендации + Advisor into one block (Срочные → Неделя → Месяц)
- Section IX: Forecast in ₽ (not штуки) — Выручка, Маржа, ДРР with ranges
- CRITICAL DATA FIX: wb_external_breakdown column mapping — adv_vk is ВК (183К), NOT adv_creators
- Sheets parsing: filter bloggers by "Дата публикации", VK/SMM by date columns
- Recommendations must be SPECIFIC: model + channel + action + ₽ amount
- Russian terminology enforced: Рост/Сбор/Оптимизация/Стоп (not Growth/Harvest/Optimize/Cut)

### v1 (2026-04-08)
- Initial release: 3-wave engine + 2 parallel analysts
- 11-section report, Notion publication
