# Financial Overview Skill — Design Spec

## Purpose

Reusable skill `/financial-overview` that generates a comprehensive financial + marketing comparison report between two arbitrary periods. Replaces the manual multi-agent workflow used for the Q4 2025 vs Q1 2026 report.

## Trigger

```
/financial-overview
финансовый обзор
financial overview
сравнение периодов
```

## Interactive Flow (Stage 0)

The skill asks 3-4 questions via AskUserQuestion before collecting data:

**Q1 — Current Period (Period A):**
Options: "Q1 2026", "Мар 2026", "Custom dates" + free text.
Parsed into `period_a_start` and `period_a_end` dates.
Supports formats: "Q1 2026", "мар 2026", "2026-01-01 — 2026-03-31", "январь-март 2026".

**Q2 — Comparison Period (Period B):**
Options: "Предыдущий аналогичный (auto)", "Q4 2025", "Custom dates".
Auto mode: Q1 → Q4 prev year, month → prev month, custom range → same-length preceding range.

**Q3 — Sections to include (multiSelect):**
- Финансы (ОПИУ) — always on by default
- Органика WB (воронка)
- Внутренний маркетинг WB/OZON
- Внешний performance (Яндекс + ВК)
- SMM
- Блогеры

All selected by default. User can deselect what's not needed.

**Q4 — Additional context (optional, free text):**
For notes like "март неполный, косвенные ≈ фев + 150K" or "OZON не включать".
Stored as `user_context` string, passed to synthesizer.

---

## Data Collection (Stage 1)

### Orchestrator: `scripts/financial_overview/collect_all.py`

```
python scripts/financial_overview/collect_all.py \
  --period-a "2026-01-01:2026-03-31" \
  --period-b "2025-10-01:2025-12-31" \
  --sections "finance,organic,ads,performance,smm,bloggers" \
  --output /tmp/financial_overview_data.json
```

Uses `ThreadPoolExecutor(max_workers=5)` to run collectors in parallel. Each collector returns a dict. Results merged into single JSON with `meta` block.

### Collectors

All collectors import from `shared/data_layer/` — no duplicated DB logic.

#### 1. `collectors/wb_funnel.py` — Organic WB Funnel
- Calls: `get_wb_traffic(period_a_start, period_b_start, period_a_end)` for both periods
- Calls: `get_wb_article_funnel(start, end, top_n=10)` for both periods
- Calls: `get_wb_organic_vs_paid_funnel()` for organic/paid split
- Returns:
  ```json
  {
    "funnel": {"period_a": {...}, "period_b": {...}},
    "conversions": {"period_a": {...}, "period_b": {...}},
    "organic_vs_paid": {"period_a": {...}, "period_b": {...}},
    "top_models": {"period_a": [...], "period_b": [...]}
  }
  ```

#### 2. `collectors/wb_ozon_finance.py` — Finance + Internal Ads
- Calls: `get_wb_finance()`, `get_ozon_finance()` for both periods
- Calls: `get_wb_external_ad_breakdown()` for ad spend split
- Calls: `get_wb_model_ad_roi()` for DRR/ROMI by model
- Returns: `{"wb_finance": {...}, "ozon_finance": {...}, "wb_ads": {...}, "ad_roi": {...}}`

#### 3. `collectors/sheets_performance.py` — External Performance Marketing
- Reads Google Sheet (ID from env: `PERFORMANCE_SHEET_ID`)
- Aggregates by month: расход, переходы, CPC, UTM-переходы, CPC UTM
- Returns: `{"monthly": {"2026-01": {...}, "2026-02": {...}, ...}}`

#### 4. `collectors/sheets_smm.py` — SMM
- Reads Google Sheet (ID from env: `SMM_SHEET_ID`)
- Monthly data: затраты, показы, переходы, CPC, CR
- Returns: `{"monthly": {"2025-10": {...}, ...}}`

#### 5. `collectors/sheets_bloggers.py` — Bloggers
- Reads Google Sheet (ID from env: `BLOGGERS_SHEET_ID`)
- Aggregates by month: budget, placements count, CPM, CPC, clicks, carts, orders, CR
- Returns: `{"monthly": {"2025-10": {...}, ...}, "quarterly": {"q4_2025": {...}, "q1_2026": {...}}}`

### Environment Variables (in `.env`)

```
PERFORMANCE_SHEET_ID=1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg
SMM_SHEET_ID=19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU
BLOGGERS_SHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
```

### Error Handling

- If a collector fails: log error, set `meta.errors[collector_name]`, continue with others
- If a Google Sheet is inaccessible: skip that section, note in `meta.quality_flags`
- If DB connection fails: fatal error, abort with message to user

### Output: `/tmp/financial_overview_data.json`

```json
{
  "wb_funnel": {...},
  "wb_ozon_finance": {...},
  "sheets_performance": {...},
  "sheets_smm": {...},
  "sheets_bloggers": {...},
  "meta": {
    "period_a": {"start": "2026-01-01", "end": "2026-03-31", "label": "Q1 2026"},
    "period_b": {"start": "2025-10-01", "end": "2025-12-31", "label": "Q4 2025"},
    "sections": ["finance", "organic", "ads", "performance", "smm", "bloggers"],
    "user_context": "март неполный, косвенные ≈ фев + 150K",
    "quality_flags": {},
    "errors": {},
    "collection_duration_sec": 45
  }
}
```

---

## Verification (Stage 2a)

A dedicated verifier agent checks the collected data before synthesis.

### Verifier Checklist (`prompts/verifier.md`)

1. **Cross-source consistency**: WB finance from DB ≈ expected totals (if ОПИУ data provided in user_context)
2. **Arithmetic**: period sums, growth percentages, weighted averages
3. **Data completeness**: all requested sections have data for both periods
4. **Sensitive data**: no юрлица, ИНН, server IPs in output
5. **Quality flags**: note any data gaps, partial months, known discrepancies (content_analysis ~20% gap)

Output: JSON `{"status": "PASS|WARN|FAIL", "issues": [...], "warnings": [...]}`

On FAIL: abort and report to user.
On WARN: proceed but include warnings in report footer.
On PASS: proceed to synthesis.

---

## Synthesis (Stage 2b)

A synthesizer agent compiles the verified data into a formatted report.

### Input
- `/tmp/financial_overview_data.json` — collected data
- `prompts/synthesizer.md` — report template + formatting rules
- `user_context` — additional adjustments (e.g., March cost estimates)

### Report Template (`prompts/synthesizer.md`)

The template defines 6 sections, each conditionally included based on `meta.sections`:

**I. Финансы** — Q-to-Q table (выручка, маржа, EBITDA, ЧП), monthly trend, key insight
**II. Органика WB** — funnel (показы→корзина→заказы), CRs, organic vs paid, top models
**III. Внутренний маркетинг** — WB/OZON ad spend, DRR, ROMI
**IV. Внешний performance** — aggregate spend, clicks, CPC (no channel breakdown)
**V. SMM** — spend, views, clicks, CPC, CR
**VI. Блогеры** — placements, budget, CPM, CPC, CR

Plus:
- **Итоги** section — callout blocks summarizing each section
- **Footer** — data sources, caveats, quality warnings

### Formatting Rules
- All percentage metrics: weighted averages only
- Numbers: space-separated thousands (1 234 567)
- Deltas: absolute + percentage
- Estimates marked with asterisk (*)

### Output
1. **MD file**: `docs/reports/{period_a_label}-vs-{period_b_label}-overview.md`
2. **Notion page**: Published to "Аналитические отчеты" database with proper properties
   - Parent: `data_source_id: 30158a2b-d587-8091-bfc3-000b83c6b747`
   - Источник: "Claude Code"
   - Тип анализа: "Ежемесячный фин анализ"
   - Notion tables with colors, callouts for insights

---

## SKILL.md State Machine

```
Stage 0: Interactive Q&A
  → AskUserQuestion x3-4
  → Parse periods, sections, user_context

Stage 1: Data Collection
  → Run: python scripts/financial_overview/collect_all.py --period-a ... --period-b ... --sections ... --output /tmp/financial_overview_data.json
  → Check exit code and meta.errors

Stage 2: Parallel Verify + Synthesize
  → Launch Agent: Verifier (reads JSON, runs checklist)
  → If PASS/WARN: Launch Agent: Synthesizer (reads JSON + template → MD + Notion)
  → If FAIL: Report issues to user, suggest fixes

Stage 3: Delivery
  → Confirm MD file path
  → Confirm Notion URL
  → Show summary table to user
```

---

## File Structure

```
.claude/skills/financial-overview/
├── SKILL.md                         # Main skill definition
└── prompts/
    ├── synthesizer.md               # Report template + formatting rules
    └── verifier.md                  # Verification checklist

scripts/financial_overview/
├── collect_all.py                   # Orchestrator (ThreadPoolExecutor)
└── collectors/
    ├── __init__.py
    ├── wb_funnel.py                 # Organic WB traffic + funnel
    ├── wb_ozon_finance.py           # WB/OZON finance + ads
    ├── sheets_performance.py        # External performance (gws)
    ├── sheets_smm.py                # SMM (gws)
    └── sheets_bloggers.py           # Bloggers (gws)
```

Total: 10 files to create.

---

## Data Quality Rules (enforced in collectors + verifier)

1. GROUP BY LOWER() for all model aggregations
2. Weighted averages for all percentage metrics: `sum(numerator) / sum(denominator)`
3. content_analysis gap ~20% vs PowerBI — noted as caveat, used for trend only
4. Google Sheets amounts labeled "с НДС" or "без НДС" explicitly
5. No hardcoded "—" for missing comparison values — always compute both periods
6. Выкуп % is a lagging indicator (3-21 days) — noted but not used as causal

---

## Future Extensions

These are NOT in scope for v1 but noted for future iterations:
- OZON organic funnel (when data becomes available)
- Auto-detection of ОПИУ data from Google Sheets (currently manual/screenshots)
- Telegram bot delivery
- Scheduled weekly/monthly runs via /schedule
