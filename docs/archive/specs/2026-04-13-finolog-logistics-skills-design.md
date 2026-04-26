# Design: Finolog DDS Report + Logistics Report Skills

**Date:** 2026-04-13
**Status:** Draft
**Approach:** C — Hybrid (Python collector + 2-wave LLM: Analyst → Verifier + Synthesizer)

---

## Scope

Two new Claude Code skills for Wookiee analytics:

1. **`finolog-dds-report`** — Анализ движения денежных средств из Финолога (еженедельный + ежемесячный)
2. **`logistics-report`** — Анализ логистических расходов, остатков, оборачиваемости (еженедельный + ежемесячный)

Plus cleanup:
- **DELETE** `agents/finolog_categorizer/` — ежедневная категоризация (больше не нужна)
- **DELETE** `docs/archive/retired_agents/vasily_agent_runtime/` — старая версия Vasily

---

## Architecture (shared pattern)

Both skills follow the same 4-stage pipeline:

```
Stage 0: Parameters (period type, date range)
Stage 1: Python collector → JSON with data blocks
Stage 2: Wave 1 — Analyst (LLM) — deep analysis + anomalies + forecasts
Stage 3: Wave 2 — Verifier (LLM) ‖ Synthesizer (LLM) — parallel
Stage 4: Save MD → Notion publish → Telegram notification
```

### Verifier rejection flow

If Verifier returns REJECT: re-run Analyst (Stage 2) with the Verifier's error details appended to the prompt. Max 1 retry. If second REJECT → publish with ⚠️ callout "Отчёт не прошёл верификацию" at the top.

### LLM tier

Per `economics.md`: all agents use MAIN tier (google/gemini-3-flash-preview). No escalation to HEAVY needed — data is structured, not complex reasoning.

### File structure

```
.claude/skills/finolog-dds-report/
├── SKILL.md                     # Orchestration, data collection, stages
└── prompts/
    ├── analyst.md               # Cash flow analyst
    ├── verifier.md              # Fact-checking + arithmetic
    └── synthesizer.md           # Final report assembly (Notion format)

.claude/skills/logistics-report/
├── SKILL.md                     # Orchestration, data collection, stages
└── prompts/
    ├── analyst.md               # Logistics analyst
    ├── verifier.md              # Fact-checking
    └── synthesizer.md           # Final report assembly (Notion format)
```

### Notion output format

All reports use the enhanced Notion format from the Q4-vs-Q1 example:
- Tables: `fit-page-width="true"`, `header-row="true"`, `header-column="true"`
- Header row color: `color="blue_bg"`
- Positive rows: `color="green_bg"`, negative: `color="red_bg"`, neutral: `color="gray_bg"`
- Callouts: `<callout icon="⚠️" color="yellow_bg">` (risk), `icon="💡" color="green_bg"` (positive), `icon="📊" color="blue_bg"` (summary), `icon="🔥" color="green_bg"` (achievement)
- Numbers: `1 234 567 ₽`, `24,1%`, `+3,2 пп`, `8,8М`, `42,8 млн`
- Bold on significant changes: `**+24%**`, `**-4,6 пп**`
- Russian terminology only

### Notion publishing

Both skills publish via existing `shared/notion_client.py`:
```python
PYTHONPATH=. python3 -c "
import asyncio, os
from shared.notion_client import NotionClient
from pathlib import Path

async def main():
    md = Path('docs/reports/{FILE}').read_text()
    client = NotionClient(
        token=os.getenv('NOTION_TOKEN'),
        database_id=os.getenv('NOTION_DATABASE_ID')
    )
    url = await client.sync_report(
        start_date='{START}', end_date='{END}',
        report_md=md, report_type='{TYPE}', source='Claude Code'
    )
    print(f'Published: {url}')

asyncio.run(main())
"
```

Report type mapping (already in `_REPORT_TYPE_MAP`):
- `"finolog_weekly"` → `"Еженедельная сводка ДДС"` / title `"Сводка ДДС"`
- `"localization_weekly"` → `"Анализ логистических расходов"` / title `"Анализ логистических расходов"`

New mappings to add:
- `"finolog_monthly"` → `"Ежемесячная сводка ДДС"` / title `"Сводка ДДС"`
- `"logistics_monthly"` → `"Ежемесячный анализ логистики"` / title `"Анализ логистики"`

---

## Skill 1: `finolog-dds-report`

### Triggers

```
/finolog-dds-report                        # прошлая неделя
/finolog-dds-report week                   # прошлая неделя
/finolog-dds-report month                  # прошлый месяц (+ доли затрат)
/finolog-dds-report 2026-03-01 2026-03-31  # произвольный период
```

### Stage 0: Parameters

| Parameter | Default | Options |
|-----------|---------|---------|
| period | `week` | `week`, `month`, custom dates |
| START | last Monday | computed or explicit |
| END | last Sunday | computed or explicit |
| DEPTH | `weekly` | `weekly` or `monthly` (affects sections VI-VII) |

### Stage 1: Data Collection

Uses existing `agents/oleg/services/finolog_service.py` — `FinologService` class.

**Data blocks collected:**

| Block | Source | Content |
|-------|--------|---------|
| `balances` | Finolog API `/accounts` | Current balances: ИП Медведева + ООО ВУКИ, by purpose (operating, funds, personal, USD) |
| `cashflow_current` | Finolog API `/transactions` | Transactions for current period, grouped by category (Выручка, Закупки, Логистика, Маркетинг, Налоги, ФОТ, Склад, Услуги, Кредиты) |
| `cashflow_previous` | Finolog API `/transactions` | Same groups for previous period (for comparison) |
| `forecast` | FinologService `_build_forecast()` | 6-12 month projection: income, expense, net, balance per month |
| `forecast_by_group` | FinologService | Forecast broken down by expense group |

**Validation gate:** Abort if API returns errors or balances are stale (>24h).

### Stage 2: Analyst (LLM prompt: `prompts/analyst.md`)

Input: all 5 data blocks as JSON.

Analyst produces:
1. **Expense trends** — growth/decline per group vs previous period, top-3 changes with ₽ and %
2. **Cost structure shifts** (monthly only) — if group share changed >3 пп, flag it
3. **Cash gap scenarios** — 3 scenarios:
   - Optimistic: revenue +10%
   - Base: as-is (current trends)
   - Pessimistic: revenue -20%
   - For each: month when balance < 1M₽ threshold (or "no gap")
4. **Anomalies** — atypical transactions, sudden spikes in any group
5. **Recommendations** — "фонды недофинансированы на X₽", "свободные средства покрывают N месяцев операционки", "закупки выросли на X% — проверить сезонность"

Output format: structured JSON with fields for each section.

### Stage 3: Verifier + Synthesizer (parallel)

**Verifier** (`prompts/verifier.md`) checks:
- Arithmetic: group sums = total
- Balances match API data (not hallucinated)
- Forecast logic: scenarios are internally consistent
- Format: all amounts with ₽ separators, percentages with commas
- Verdict: APPROVE / CORRECT (with fixes) / REJECT (with reason)

**Synthesizer** (`prompts/synthesizer.md`) assembles Notion-format report:

### Report sections (weekly)

| # | Section | Content |
|---|---------|---------|
| I | Текущие остатки | Tables ИП + ООО (by purpose → account → balance). Summary: свободные / фонды / личные / всего |
| II | Cashflow за период | Table by group: приход, расход, сальдо. **Δ vs прошлый период** (₽ and %). Color: green_bg if improved, red_bg if worsened |
| III | Тренды расходов | Top-3 changes with analysis. Callout blocks for significant shifts |
| IV | Прогноз кассового разрыва | Table: month × 3 scenarios (optimistic/base/pessimistic) → balance. Callout ⚠️ if any scenario shows gap |
| V | Выводы и рекомендации | 3-5 callout blocks: key findings and actionable recommendations |

### Additional sections for monthly

| # | Section | Content |
|---|---------|---------|
| VI | Доли затрат | Table: group → absolute ₽ → % of total → Δ vs previous month. Color on significant shifts |
| VII | Структурные изменения | What grew/fell significantly, why, what to do |

### Output files
- `docs/reports/{START}_{END}_finolog_dds.md`
- Notion page in "Аналитические отчеты" DB
- Telegram summary (brief)

---

## Skill 2: `logistics-report`

### Triggers

```
/logistics-report                          # прошлая неделя
/logistics-report week                     # прошлая неделя
/logistics-report month                    # прошлый месяц
/logistics-report 2026-03-01 2026-03-31    # произвольный период
```

### Stage 0: Parameters

| Parameter | Default | Options |
|-----------|---------|---------|
| period | `week` | `week`, `month`, custom dates |
| START | last Monday | computed or explicit |
| END | last Sunday | computed or explicit |
| CLOSED_PERIOD_END | END - 30 days | for buyout/return metrics (lag) |

### Stage 1: Data Collection

Multiple data sources, collected into 5 blocks:

**Block 1 — Logistics cost** (Python collector, new script):

| Data | Source | Details |
|------|--------|---------|
| WB logistics cost ИП | `services/logistics_audit/runner.py` | Overpayments, tariffs, ИЛ for ИП cabinet |
| WB logistics cost ООО | Same | Same for ООО cabinet |
| OZON logistics cost | `shared/data_layer` SQL | Logistics expenses from orders/finance tables. NOTE: may need new SQL query in data_layer if not yet available — verify during implementation |
| Revenue (for ratio) | `shared/data_layer` SQL | WB + OZON revenue for the period |
| Previous period costs | Same sources | For Δ comparison |

**Block 2 — Indices and delivery** (existing services):

| Data | Source | Details |
|------|--------|---------|
| WB Localization Index (ИЛ, ИРП) | `services/logistics_audit/` | Per-cabinet, dynamic for period |
| WB Zone breakdown | Same | ИРП-zone, ИЛ-zone, OK |
| WB Problem SKUs | Same | Top-15 by overpayment |
| OZON delivery time | DB if available | Average delivery time dynamics. NOTE: verify if OZON API provides this data — if not, skip this metric in v1 and note "данные недоступны" |

**Block 3 — Returns and buyouts** (closed period data):

| Data | Source | Details |
|------|--------|---------|
| WB buyout % by model | `shared/data_layer` SQL | For CLOSED_PERIOD_END (min 30 days ago) |
| OZON buyout % by model | Same | Same |
| Return dynamics | Same | % returns, Δ vs previous closed period |

**Block 4 — Inventory and turnover**:

| Data | Source | Details |
|------|--------|---------|
| WB FBO stock | `shared/data_layer/inventory.py` → `get_wb_avg_stock()` | By article |
| OZON FBO stock | `get_ozon_avg_stock()` | By article |
| MoySklad stock | `get_moysklad_stock_by_model()` | Office + in-transit |
| WB turnover | `get_wb_turnover_by_model()` | Days of stock |
| OZON turnover | `get_ozon_turnover_by_model()` | Days of stock |
| Risk assessment | Computed | DEFICIT / OK / WARNING / OVERSTOCK / DEAD_STOCK based on order velocity |

**Block 5 — Resupply recommendations**:

| Data | Source | Details |
|------|--------|---------|
| Available to ship | `shared/clients/moysklad_client.py` → `fetch_stock_by_store()` | Office warehouse stock |
| Current MP stock | Block 4 WB + OZON stock | What's already on marketplace |
| Order velocity | `shared/data_layer/inventory.py` | Orders/day per model (last 14 days) |
| Deficit calculation | Computed | model → target days of stock → gap → qty to ship |

**Validation gate:** Abort if WB API errors > 3, or stock data stale > 3 days.

### Stage 2: Analyst (LLM prompt: `prompts/analyst.md`)

Input: all 5 blocks as JSON.

Analyst produces:
1. **Logistics cost analysis** — trend, share of revenue (%), per-unit cost, ИП vs ООО comparison
2. **Localization index** — dynamics, problem regions, impact on overpayment in ₽
3. **Returns analysis** — growth/decline by model, correlation with logistics cost, seasonal patterns. IMPORTANT: only closed period data (lag 30+ days)
4. **Inventory assessment** — where deficit → lost sales in ₽ (order_velocity × days_of_deficit × avg_price), where overstock → frozen capital in ₽ (qty × cost_price)
5. **Resupply recommendations** — specific: model → MP warehouse → quantity. Not more than available on MoySklad
6. **Anomalies** — sudden logistics cost spike per unit, buyout drop on specific model, dead stock accumulation

Output format: structured JSON with fields for each section.

### Stage 3: Verifier + Synthesizer (parallel)

**Verifier** (`prompts/verifier.md`) checks:
- Closed period data used for buyout/returns (not current open period)
- Arithmetic: shares, sums, turnover calculations
- Resupply quantities ≤ available on MoySklad
- Deficit/overstock thresholds are reasonable
- Verdict: APPROVE / CORRECT / REJECT

**Synthesizer** (`prompts/synthesizer.md`) assembles Notion-format report:

### Report sections

| # | Section | Content |
|---|---------|---------|
| I | Сводка | Callout blocks: key metrics and changes for the period. Icon/color by severity |
| II | Стоимость логистики | Table: WB ИП / WB ООО / OZON — total cost, % of revenue, per unit, Δ. Color: green_bg if reduced, red_bg if increased |
| III | Индекс локализации WB | Table by cabinet: ИЛ, ИРП, dynamics. Problem SKUs (top-10). Zone breakdown table |
| IV | Возвраты и выкупы | Table: buyout % WB/OZON by model, Δ vs previous closed period. Callout on problem models. NOTE: data from closed period (lag 30+ days), clearly labeled |
| V | Остатки и оборачиваемость | Table by model: stock WB + OZON + MoySklad, turnover days, status (deficit/ok/overstock). Lost sales ₽ for deficit items. Frozen capital ₽ for overstock |
| VI | Рекомендации по допоставкам | Table: model → MP warehouse → qty to ship → available on MoySklad. Callout with priorities (urgent deficit first) |
| VII | Выводы и действия | 3-5 callout blocks: urgent / important / informational |

### Output files
- `docs/reports/{START}_{END}_logistics.md`
- Notion page in "Аналитические отчеты" DB
- Telegram summary (brief)

---

## Data collector (new script)

Both skills need a Python collector. Create:

### `scripts/finolog_dds_report/collect_data.py`

```
collect_finolog_dds(start_date, end_date) → dict:
    Uses: FinologService (agents/oleg/services/finolog_service.py)
    Returns: { balances, cashflow_current, cashflow_previous, forecast, forecast_by_group, meta }
```

### `scripts/logistics_report/collect_data.py`

```
collect_logistics(start_date, end_date, closed_period_end) → dict:
    Uses:
      - services/logistics_audit/runner.py (WB logistics costs, ИЛ)
      - shared/data_layer/inventory.py (stocks, turnover)
      - shared/data_layer SQL (OZON logistics, buyout/returns)
      - shared/clients/moysklad_client.py (office stock)
    Returns: { logistics_cost, indices, returns, inventory, resupply, meta }
```

Both collectors:
- Return JSON with `meta.errors` count and `meta.quality_flags`
- Gate: abort if `meta.errors > 3`
- Save to `/tmp/{skill}-{date}.json` for debugging

---

## Cleanup

### Delete entirely

| Path | Reason |
|------|--------|
| `agents/finolog_categorizer/` | Daily categorization no longer needed |
| `agents/finolog_categorizer/rules/` | Part of categorizer |
| `agents/finolog_categorizer/data/` | SQLite DB for categorizer |
| `docs/archive/retired_agents/vasily_agent_runtime/` | Old Vasily, active version in `services/wb_localization/` |

### Verify before deleting

| Path | Check |
|------|-------|
| `agents/oleg/services/finolog_categorizer.py` | Not imported elsewhere |
| `agents/oleg/services/finolog_categorizer_store.py` | Not imported elsewhere |
| `tests/test_returns_audit_collector.py` | Already deleted in git status |
| `tests/test_wb_client_returns.py` | Already deleted in git status |

### Modify

| Path | Change |
|------|--------|
| `shared/notion_client.py` | Add `finolog_monthly` and `logistics_monthly` to `_REPORT_TYPE_MAP` |

---

## Success criteria

1. `/finolog-dds-report` produces a Notion page with 5 sections (weekly) or 7 sections (monthly)
2. `/logistics-report` produces a Notion page with 7 sections
3. Both use the enhanced Notion format (colored tables, callouts, bold on significant Δ)
4. Analyst provides real analysis (not just data dump) — trends, anomalies, scenarios, recommendations
5. Verifier catches arithmetic errors before publication
6. `agents/finolog_categorizer/` fully removed
7. `docs/archive/retired_agents/vasily_agent_runtime/` fully removed
