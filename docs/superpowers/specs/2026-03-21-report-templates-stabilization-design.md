# Report Templates Stabilization — Design Spec

## Problem

Report formatting is inconsistent across 9+ report types:
- LLM drifts from template (e.g., March 20 daily report generated in old format)
- Single `report-compiler.md` tries to cover all report types → format confusion
- Marketing report has no toggles, funnel report has no trust envelope, finolog has flat structure
- Recent improvements (trust envelope, plan-fact, Russian dates, hypothesis quality) don't consistently appear

## Solution: Unified Style Guide + Per-Type Compilers

### Architecture

```
report-style-guide.md          ← unified formatting rules (HOW to format)
    ↑ imported by
report-compiler-financial.md   ← daily/weekly/monthly fin analysis (WHAT sections)
report-compiler-marketing.md   ← marketing + funnel weekly/monthly
report-compiler-funnel.md      ← funnel weekly/monthly (per-model)
report-compiler-pricing.md     ← pricing weekly/monthly (per-model nested)
report-compiler-finolog.md     ← DDS/finolog weekly
```

Orchestrator routes to the correct compiler via `COMPILER_MAP` based on `report_type`.

---

## 1. `report-style-guide.md` — Unified Formatting Rules

Imported by every compiler prompt. Defines HOW to format, not WHAT content.

### 1.1 Toggle Headings
- All top-level sections: `## Section Name {toggle="true"}`
- Nested subsections: `### Subsection {toggle="true"}` indented with `\t`
- Never flat sections with `---` dividers

### 1.2 Tables
- Notion format: `<table header-row="true" header-column="false">`
- After every data table: `**Интерпретация:**` block (2-4 sentences)
- Never empty tables — skip section with note in `sections_skipped`

### 1.3 Dates
- Russian format: «19 марта 2026», «9–15 марта 2026»
- Never ISO format (2026-03-19) in report body
- ISO only in JSON metadata fields

### 1.4 Numbers
- Thousands separator: space (1 234 567)
- Currency: ₽ suffix
- Percentages: % or п.п. (percentage points)
- Deltas: always with + or − prefix
- Large numbers: abbreviated with М (millions), К (thousands) where appropriate

### 1.5 Status Markers
- ✅ norm / on track
- ⚠️ attention / warning
- 🔴 critical
- ❌ failure / missed

### 1.6 Trust Envelope (when `_meta` is present)
- **Passport section:** Достоверность table (🟢 ≥0.75, 🟡 0.45-0.75, 🔴 <0.45)
- **Section headings:** confidence marker emoji: `## ▶ Section Name 🟢`
- **Conclusions:** toggle block with confidence/sources for driver/anti_driver/recommendation/anomaly types
- **Limitations:** bullet list after Достоверность table

### 1.7 Key Findings First
- Top conclusions (3-5 items with ₽ effect) always in first two sections
- Format: ₽ effect → What happened → Hypothesis → Action
- Sorted by absolute ₽ effect descending

### 1.8 Hypotheses Format
- Full format: Факт → Гипотеза → Действие → Метрика контроля → База → Цель → Ожидаемый эффект → Окно проверки → Риски
- Sorted by ₽ effect descending
- Priority markers: P0 (urgent), P1 (high), P2 (medium), P3 (low)

### 1.9 Telegram Summary
- BBCode format, 5-8 lines
- KPIs only, no tables
- Must include 1 plan-fact line (if plan data available)
- Deltas with emoji: 📈 for growth, 📉 for decline
- Key drivers and anti-drivers (1-2 lines)
- Top 3-5 actions

### 1.10 Prohibited
- Empty sections (skip with `sections_skipped` note)
- Simple average percentages (only weighted averages: sum(x)/sum(y)×100)
- GROUP BY model without LOWER()
- ISO dates in report body
- Omitting models with negative margin

---

## 2. Per-Type Compiler Prompts

### 2.1 `report-compiler-financial.md`

**Used for:** daily, weekly, monthly financial analysis

**Input artifacts:** margin-analyst, revenue-decomposer, ad-efficiency

**10-section structure:**

| # | Section | Content |
|---|---------|---------|
| 0 | Паспорт отчёта | Period, comparison, data completeness, lag note, trust envelope |
| 1 | Топ-выводы и действия | 3-5 items: ₽ effect → What → Hypothesis → Action |
| 2 | План-факт (MTD) | Brand/WB/OZON table with ✅⚠️❌, skip if no plan data |
| 3 | Ключевые изменения (Бренд) | 19 metrics (15 financial + 4 funnel) with Δ |
| 4 | Цены, ценовая стратегия, СПП | SPP dynamics table + average prices + forecast |
| 5 | Сведение ΔМаржи (Reconciliation) | Factor analysis waterfall: revenue → costs → margin, with невязка |
| 6 | WB / OZON breakdown | Per-channel toggle with subsections: volume, model decomposition, funnel, cost structure, ads |
| 7 | Модели — драйверы / антидрайверы | Extended table per channel |
| 8 | Гипотезы → действия → метрики | 10-column table sorted by ₽ effect |
| 9 | Итог | What changed → Why → Impact ranking → Action priorities |

**Period-specific behavior:**
- **Daily:** comparison with previous day
- **Weekly:** WoW comparison, 4-week trend column added
- **Monthly:** MoM + YoY comparison, extended plan-fact with full month targets

### 2.2 `report-compiler-marketing.md`

**Used for:** marketing_weekly, marketing_monthly

**Input artifacts:** ad-efficiency, campaign-optimizer, funnel-digitizer

**10-section structure:**

| # | Section | Content |
|---|---------|---------|
| 0 | Паспорт отчёта | Period, trust envelope |
| 1 | Исполнительная сводка | Key metrics table: revenue, margin, orders, DRR, avg check |
| 2 | Анализ по каналам | WB / OZON tables + conclusion per channel |
| 3 | Воронка продаж | ASCII funnel visualization + conversion analysis (organic + paid separately, per channel) |
| 4 | Органика vs Платное | Traffic share table, dynamics, conversion comparison |
| 5 | Внешняя реклама | Bloggers / VK / other — spend, share, effectiveness |
| 6 | Эффективность по моделям | Growth/Harvest/Optimize/Cut matrix + detailed top models |
| 7 | Дневная динамика рекламы | Daily table: impressions, clicks, CTR, spend, orders, CPO |
| 8 | Средний чек и связь с ДРР | Check dynamics + DRR correlation analysis |
| 9 | Рекомендации и план действий | Urgent (3 days) / Optimization (week) / Strategic (month) |

**Period-specific behavior:**
- **Monthly:** adds MoM trends and budget plan-fact

### 2.3 `report-compiler-funnel.md`

**Used for:** funnel_weekly, funnel_monthly

**Input artifacts:** funnel-digitizer

**Structure:**

| # | Section | Content |
|---|---------|---------|
| 0 | Паспорт + trust envelope | Period, channel, data quality |
| 1 | Общий обзор бренда | Table: transitions, orders, buyouts, revenue, margin, DRR |
| 2+ | Per-model sections (toggles) | Sorted by ΔOrders. Each model has: funnel table, economics table, significant SKUs table, hypotheses text |
| Last | Выводы и рекомендации | Top 3: Fact → Hypothesis → Action → Expected effect |

**Model section heading format:**
`## Модель: {name} — {trend description} {delta}% {toggle="true"}`

**Per-model subsections:**
- Воронка (conversion table WoW: transitions, cart, orders, buyouts, all CRs)
- Экономика (revenue, margin, DRR, ROMI, organic share)
- Значимые артикулы (table with flags: growth/decline percentages)
- Гипотезы (text: root cause analysis per significant SKU)

### 2.4 `report-compiler-pricing.md`

**Used for:** price_weekly, price_monthly

**Input artifacts:** price-strategist (+ pricing-impact-analyst if available)

**Structure:**

| # | Section | Content |
|---|---------|---------|
| 0 | Краткие итоги | Per WB/OZON: models count, raise/lower/hold counts, total ₽/month effect |
| 1+ | Per-model sections (toggles) | Sorted by ₽ effect. Each model has per-channel subsections |

**Model section heading format:**
`## {Model} {trend emoji} {recommendation} {toggle="true"}`

**Per-channel subsection (nested toggle):**
- Current metrics: price, margin%, sales/day, turnover, category
- Recommendation: price change % → new price
- Expected result (with confidence marker): margin%, volume Δ, daily margin profit, monthly effect
- How to verify: test period, expected volume, target margin
- Marketing adjustment (with confidence)
- Scenarios «что если»: -10%, -5%, -3%, +3%, +5%, +10%
- Rationale: elasticity, factors
- Elasticity + confidence

### 2.5 `report-compiler-finolog.md`

**Used for:** finolog_weekly

**Input artifacts:** finolog-analyst

**Structure:**

| # | Section | Content |
|---|---------|---------|
| 0 | Паспорт | Date, data source |
| 1 | Текущие остатки | Per legal entity: accounts table grouped by purpose (operational, tax fund, VAT fund, payroll fund, reserves, development, personal) |
| 2 | Сводка | Free cash (operational), reserved in funds, personal + currency, total |
| 3 | Прогноз по месяцам | 6-month table: income, expenses, balance, cumulative |
| 4 | Детализация по группам | Revenue, procurement, logistics, marketing, taxes, payroll, warehouse, services, loans, other |
| 5 | Кассовый разрыв | Forecast or "not expected" |

---

## 3. Orchestrator Changes

### 3.1 COMPILER_MAP

```python
COMPILER_MAP = {
    "daily": "report-compiler-financial",
    "weekly": "report-compiler-financial",
    "monthly": "report-compiler-financial",
    "marketing_weekly": "report-compiler-marketing",
    "marketing_monthly": "report-compiler-marketing",
    "funnel_weekly": "report-compiler-funnel",
    "funnel_monthly": "report-compiler-funnel",
    "price_weekly": "report-compiler-pricing",
    "price_monthly": "report-compiler-pricing",
    "finolog_weekly": "report-compiler-finolog",
}
```

### 3.2 Pipeline modification

In `_run_report_pipeline()`:
- Accept `report_type` parameter
- Look up compiler prompt name from `COMPILER_MAP`
- Load both `report-style-guide.md` and the specific compiler prompt
- Pass both as system context to compiler agent
- Pass `report_type` to compiler so it knows period-specific behavior (daily vs weekly vs monthly)

### 3.3 New orchestrator methods

Add entry points for new report types:
- `run_marketing_monthly_report(date_from, date_to)` — same agents as `run_marketing_report` but with monthly period
- `run_funnel_monthly_report(date_from, date_to)` — same agents as `run_funnel_report` but with monthly period
- `run_price_monthly_report(date_from, date_to)` — same agents as `run_price_analysis` but with monthly period

Or alternatively, parameterize existing methods with `period` parameter.

---

## 4. Schedule Changes

### 4.1 New ReportType enum values

Add to `schedule.py`:
- `marketing_monthly = "marketing_monthly"`
- `funnel_monthly = "funnel_monthly"`
- `price_monthly = "price_monthly"`

Each with `.orchestrator_method`, `.notion_label`, `.human_name` properties.

### 4.2 Updated `get_today_reports()` rules

- Daily: every day
- Weekly (weekly, marketing_weekly, funnel_weekly, price_weekly): Monday
- Monthly (monthly, marketing_monthly, funnel_monthly, price_monthly): 1st Monday of month
- Finolog: Friday

### 4.3 Conductor integration

No changes needed in `conductor.py` — it iterates `get_today_reports(today)` and handles each type through the same `generate_and_validate` flow. Cron triggers `data_ready_check` at approximate times; if gates fail, `DateTrigger` retry is scheduled. Report generates when data is ready.

---

## 5. Migration

### 5.1 New files created
- `agents/v3/agents/report-style-guide.md`
- `agents/v3/agents/report-compiler-financial.md`
- `agents/v3/agents/report-compiler-marketing.md`
- `agents/v3/agents/report-compiler-funnel.md`
- `agents/v3/agents/report-compiler-pricing.md`
- `agents/v3/agents/report-compiler-finolog.md`

### 5.2 Deleted files
- `agents/v3/agents/report-compiler.md` — content migrated to financial compiler + style guide

### 5.3 Modified files
- `agents/v3/orchestrator.py` — COMPILER_MAP, pipeline routing, new entry points
- `agents/v3/conductor/schedule.py` — new ReportType values + get_today_reports() rules
- `agents/v3/delivery/notion.py` — new entries in `_REPORT_TYPE_MAP` for marketing_monthly, funnel_monthly, price_monthly

### 5.4 Updated files
- `agents/v3/agents/report-conductor.md` — updated to reference new compiler structure for validation

---

## 6. Success Criteria

1. All 10 report types generate with correct formatting (toggles, tables, dates, trust envelope)
2. Format is consistent across runs — same report type always produces same structure
3. Style guide changes propagate to all report types
4. New monthly report types (marketing, funnel, pricing) generate and deliver to Notion
5. Existing tests pass, new tests cover COMPILER_MAP routing
