---
name: analytics-report
description: Full analytics report for Wookiee brand (WB+OZON) — 12 subagents analyze finance, marketing, traffic, inventory, prices, plan-fact for any period
triggers:
  - /analytics-report
  - analytics report
  - аналитический отчёт
  - финансовый анализ
---

# Analytics Report Skill

Generates a verified analytics report for the Wookiee brand using a multi-wave agent architecture: 8 analysts, 3 verifiers, synthesizer.

## Quick Start

**Daily report** (1 date = today vs yesterday):
```
/analytics-report 2026-04-06
```

**Weekly report** (2 dates = week vs previous week):
```
/analytics-report 2026-03-31 2026-04-06
```

**Monthly report** (2 dates spanning a full month):
```
/analytics-report 2026-03-01 2026-03-31
```

Skill parses dates automatically — no questions asked, pipeline starts immediately.

**Estimated time:** ~15-25 minutes (collector ~30s, 8 analysts ~8m, 3 verifiers ~5m, synthesizer ~8m, publication ~2m)

**Results:**
- MD: `docs/reports/{START}_{END}_analytics.md`
- Notion: page in "Аналитические отчеты" (database `30158a2b-d587-8091-bfc3-000b83c6b747`)

---

## Stage 0: Parse Arguments

Parse the user's input — do NOT ask any questions.

**1 date** → daily report:
```
START = given date
END = given date
DEPTH = "day"
PREV_START = START - 1 day
PREV_END = END - 1 day
MONTH_START = first day of START's month
```

**2 dates** → determine depth by span:
```
START = first date
END = second date
span = (END - START).days + 1
DEPTH = "week" if span <= 14 else "month"
PREV_START = START - span days
PREV_END = START - 1 day
MONTH_START = first day of START's month
```

Compute labels:
```
PERIOD_LABEL = "{START} — {END}" (or just "{START}" for daily)
PREV_PERIOD_LABEL = "{PREV_START} — {PREV_END}" (or just "{PREV_START}" for daily)
```

Show to user:
```
Запуск аналитического отчёта ({DEPTH}) за {PERIOD_LABEL}
Сравнение: {PREV_PERIOD_LABEL}
```

---

## Stage 1: Data Collection

Run the Python collector:
```bash
python scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/analytics-report-{START}_{END}.json
```

Read the output JSON:
```bash
cat /tmp/analytics-report-{START}_{END}.json
```

Save the full JSON as `data_bundle`.

Check `data_bundle["meta"]["errors"]`:
- 0-3 errors → proceed, note failed collectors
- **>3 errors → STOP**, report failures to user

Extract `quality_flags` from `data_bundle["meta"]["quality_flags"]` (or empty list if absent).

---

## Stage 2: Multi-Wave Analysis

### Prepare Data Slices

For each analyst, extract their primary data block from `data_bundle` and prepare a 5-10 line summary of other blocks for cross-reference.

| Analyst | Primary slice | Cross-reference summary |
|---|---|---|
| Financial | `data_bundle["finance"]` | ad totals, inventory risk counts |
| Internal Ads | `data_bundle["advertising"]` | revenue by model from finance |
| External Marketing | `data_bundle["external_marketing"]` | total revenue from finance |
| Traffic Funnel | `data_bundle["traffic"]` | paid spend from advertising |
| Inventory | `data_bundle["inventory"]` | sales by model from finance |
| Pricing | `data_bundle["pricing"]` | turnover from inventory, margin from finance |
| Plan-Fact | `data_bundle["plan_fact"]` | MTD fact from finance |
| Anomaly Detector | Summary of ALL blocks | quality_flags |

### Wave 1: 8 Analysts (launch ALL 8 in parallel — 8 Agent calls in a SINGLE message)

For each analyst: read their prompt file, replace `{{placeholders}}`, launch as Agent subagent.

**Financial Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/financial.md`
- `{{DATA_SLICE}}` = `data_bundle["finance"]`
- `{{SUMMARY}}` = ad totals + inventory risk counts (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `financial_findings`

**Internal Ads Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/internal-ads.md`
- `{{DATA_SLICE}}` = `data_bundle["advertising"]`
- `{{SUMMARY}}` = revenue by model from finance (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `ads_findings`

**External Marketing Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/external-marketing.md`
- `{{DATA_SLICE}}` = `data_bundle["external_marketing"]`
- `{{SUMMARY}}` = total revenue from finance (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `external_findings`

**Traffic Funnel Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/traffic-funnel.md`
- `{{DATA_SLICE}}` = `data_bundle["traffic"]`
- `{{SUMMARY}}` = paid spend from advertising (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `traffic_findings`

**Inventory Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/inventory.md`
- `{{DATA_SLICE}}` = `data_bundle["inventory"]`
- `{{SUMMARY}}` = sales by model from finance (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `inventory_findings`

**Pricing Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/pricing.md`
- `{{DATA_SLICE}}` = `data_bundle["pricing"]`
- `{{SUMMARY}}` = turnover from inventory + margin from finance (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `pricing_findings`

**Plan-Fact Analyst** — Read `.claude/skills/analytics-report/prompts/analysts/plan-fact.md`
- `{{DATA_SLICE}}` = `data_bundle["plan_fact"]`
- `{{SUMMARY}}` = MTD fact from finance (5-10 lines)
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `plan_fact_findings`

**Anomaly Detector** — Read `.claude/skills/analytics-report/prompts/analysts/anomaly-detector.md`
- `{{DATA_SLICE}}` = Summary of ALL blocks (key totals from each: revenue, orders, spend, stock, etc.)
- `{{SUMMARY}}` = quality_flags + meta.errors
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{QUALITY_FLAGS}}` = quality_flags
- Save output as `anomaly_findings`

Wait for all 8 analysts to complete.

### Concatenate Findings

```
all_findings = """
=== FINANCIAL ===
{financial_findings}

=== INTERNAL ADS ===
{ads_findings}

=== EXTERNAL MARKETING ===
{external_findings}

=== TRAFFIC FUNNEL ===
{traffic_findings}

=== INVENTORY ===
{inventory_findings}

=== PRICING ===
{pricing_findings}

=== PLAN-FACT ===
{plan_fact_findings}

=== ANOMALIES ===
{anomaly_findings}
"""
```

### Wave 2: 3 Verifiers (launch ALL 3 in parallel — 3 Agent calls in a SINGLE message)

**Marketplace Expert** — Read `.claude/skills/analytics-report/prompts/verifiers/marketplace-expert.md`
- `{{ALL_FINDINGS}}` = all_findings
- `{{QUALITY_FLAGS}}` = quality_flags
- `{{DEPTH}}` = DEPTH
- Save output as `marketplace_review`

**Data Quality Critic** — Read `.claude/skills/analytics-report/prompts/verifiers/data-quality-critic.md`
- `{{ALL_FINDINGS}}` = all_findings
- `{{QUALITY_FLAGS}}` = quality_flags
- `{{DEPTH}}` = DEPTH
- Save output as `dq_review`

**CFO** — Read `.claude/skills/analytics-report/prompts/verifiers/cfo.md`
- `{{ALL_FINDINGS}}` = all_findings
- `{{VERIFIER_FINDINGS}}` = "" (empty on first pass)
- `{{QUALITY_FLAGS}}` = quality_flags
- `{{DEPTH}}` = DEPTH
- Save output as `cfo_verdict`

Wait for all 3 verifiers to complete.

### CFO Verdict Handling

If `cfo_verdict` contains `"verdict": "APPROVE"` or `"verdict": "CORRECT"`:
- Note any corrections from CFO
- Proceed to Stage 3

If `cfo_verdict` contains `"verdict": "REJECT"`:
- Re-run ONLY the analysts listed in `rerun_analysts` from CFO output
- Re-run Data Quality Critic on the updated findings
- Re-run CFO with `{{VERIFIER_FINDINGS}}` = `dq_review`
- **CFO must APPROVE or CORRECT on Pass 2 — no further REJECT allowed**
- Proceed to Stage 3

---

## Stage 3: Synthesis

Read all three template files:
- `.claude/skills/analytics-report/prompts/synthesizer.md`
- `.claude/skills/analytics-report/templates/report-structure.md`
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer Agent with all data:
- `{{ALL_FINDINGS}}` = all_findings (final, after any re-runs)
- `{{CFO_OUTPUT}}` = cfo_verdict (including corrections)
- `{{QUALITY_FLAGS}}` = quality_flags
- `{{DEPTH}}` = DEPTH
- `{{PERIOD_LABEL}}` = PERIOD_LABEL
- `{{PREV_PERIOD_LABEL}}` = PREV_PERIOD_LABEL
- `{{REPORT_STRUCTURE}}` = contents of report-structure.md
- `{{NOTION_GUIDE}}` = contents of notion-formatting-guide.md

**The Synthesizer produces TWO outputs:**
1. `final_document_md` — standard markdown (for git/docs)
2. `final_document_notion` — Notion-enhanced format (native tables, colors, callouts, toggle headings)

### Document Structure (13 sections)

All 13 sections from report-structure.md are mandatory. Skipping a section = error.

0. Резюме (callout)
1. Топ-находки (3-5 findings ranked by ruble impact)
2. Финансы (P&L brand-level + by model)
3. Реклама внутренняя (spend, DRR, efficiency by campaign type)
4. Маркетинг внешний (bloggers, VK, external spend + ROI)
5. Воронка трафика (views → cart → orders, conversion rates)
6. Остатки и оборачиваемость (stock days, risk zones)
7. Ценообразование (price changes, elasticity, SPP)
8. План-факт (MTD progress vs monthly targets)
9. Аномалии и data quality (flags, gaps, warnings)
10. Рекомендации (action items with ruble estimates)
11. Риски и возможности (prioritized by impact)
12. Справочно (methodology, data sources — in toggles)

### Notion Formatting

The Notion version must follow notion-formatting-guide.md:
- `<table>` with `fit-page-width`, `header-row`, `header-column`
- Colored headers (`blue_bg`), totals (`gray_bg`), positive (`green_bg`), negative (`red_bg`), warning (`yellow_bg`)
- `<callout>` blocks after key sections
- **Toggle headings at ALL levels** (H1, H2, H3, H4 — everything collapsible)
- Human-readable table headers in Russian (no abbreviations)

---

## Stage 4: Publication

### 4.1 Save MD file
```bash
cat > docs/reports/{START}_{END}_analytics.md << 'EOF'
{final_document_md}
EOF
```

Create the directory if it doesn't exist:
```bash
mkdir -p docs/reports
```

### 4.2 Publish to Notion

Use the Notion MCP tool to create a new page in the analytics reports database:
- Database ID (data_source_id): `30158a2b-d587-8091-bfc3-000b83c6b747`
- **CRITICAL: Publish the FULL `final_document_notion` content** — all 13 sections with all tables and data. Do NOT publish a summary or abbreviated version.
- Properties:
  - Тип анализа = depth-based title (see below)
  - Источник = "Analytics Skill v1"
  - Статус = "Актуальный"
  - Период начала = START
  - Период конца = END
  - Корректность = "Да"

Title based on DEPTH:
- `day` → `Ежедневный фин анализ — {PERIOD_LABEL}`
- `week` → `Еженедельный фин анализ — {PERIOD_LABEL}`
- `month` → `Ежемесячный фин анализ — {PERIOD_LABEL}`

Use `mcp__claude_ai_Notion__notion-create-pages` tool with `parent.type = "data_source_id"`.

### 4.3 Report to User

Show a chat summary (5-7 lines):
```
Аналитический отчёт ({DEPTH}) за {PERIOD_LABEL} — готов.

Ключевые цифры:
- Выручка: X ₽ (Δ Y%)
- Маржа: X ₽ / Z% (Δ Y п.п.)
- ДРР: X%
- Заказы: X шт

CFO вердикт: {APPROVE/CORRECT} (Pass {1/2})
Data quality flags: {count} warnings

MD: docs/reports/{START}_{END}_analytics.md
Notion: {notion_url}
```

---

## Reference Files

| File | Purpose |
|---|---|
| `scripts/analytics_report/collect_all.py` | Data collector (8 parallel collectors) |
| `.claude/skills/analytics-report/prompts/analysts/*.md` | 8 analyst prompt templates |
| `.claude/skills/analytics-report/prompts/verifiers/*.md` | 3 verifier prompt templates |
| `.claude/skills/analytics-report/prompts/synthesizer.md` | Synthesizer prompt template |
| `.claude/skills/analytics-report/templates/report-structure.md` | 13-section report skeleton |
| `.claude/skills/analytics-report/templates/notion-formatting-guide.md` | Notion formatting rules |
| `.claude/skills/analytics-report/references/data-sources.md` | Data source documentation |
| `.claude/skills/analytics-report/references/analytics-rules.md` | Analytics business rules |

---

## Changelog

### v1 (2026-04-07)
- Initial release: 8 analysts, 3 verifiers, synthesizer
- Data collector: 8 parallel collectors (finance, ads, external marketing, traffic, inventory, pricing, plan-fact, SKU statuses)
- 13-section report structure
- Dual output: MD (git) + Notion-enhanced (native tables, colors, callouts)
- CFO verdict with 2-pass retry mechanism
- Auto depth detection: day/week/month from date arguments
