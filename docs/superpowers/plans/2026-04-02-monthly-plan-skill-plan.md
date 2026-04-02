# Monthly Plan Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill `/monthly-plan` that generates a verified monthly business plan for Wookiee brand using a multi-wave agent architecture (5 analysts, 2 critics, corrector, CFO, synthesizer).

**Architecture:** Python data collector gathers all data from DB/Sheets into JSON. Claude Code skill orchestrates 4 waves of subagents: analysts (parallel) -> critics (parallel) -> corrector -> CFO. Max 2 passes. Synthesizer produces 12-section document (A-L). Publishes to MD + Notion + Sheets.

**Tech Stack:** Python 3.11+, shared/data_layer (PostgreSQL), supabase-py, gspread/gws CLI, Claude Code Agent tool, Notion MCP, Google Sheets MCP.

**Design Spec:** `docs/superpowers/specs/2026-04-02-monthly-plan-skill-design.md`

**Reference Docs:**
- `docs/plans/MONTHLY-PLAN-TECHNICAL-SPEC.md` — data sources, functions, formulas, quality rules
- `docs/plans/MONTHLY-PLAN-PROCESS.md` — process, known issues, April pilot lessons
- `docs/plans/2026-04-business-plan-final.md` — example output (April 2026 plan)

---

## File Map

### Python Collector (`scripts/monthly_plan/`)

| File | Responsibility |
|------|---------------|
| `scripts/monthly_plan/__init__.py` | Package marker |
| `scripts/monthly_plan/utils.py` | Date computation, quality flags, tuple-to-dict helpers |
| `scripts/monthly_plan/collectors/__init__.py` | Package marker |
| `scripts/monthly_plan/collectors/pnl.py` | P&L data: total + by model, WB + OZON |
| `scripts/monthly_plan/collectors/pricing.py` | Price elasticity: daily article-level data (3 months) |
| `scripts/monthly_plan/collectors/advertising.py` | Ad spend: ROAS, DRR, external breakdown |
| `scripts/monthly_plan/collectors/inventory.py` | Stocks: FBO, MoySklad, turnover, risk assessment |
| `scripts/monthly_plan/collectors/abc.py` | ABC classification + financier plan from Sheets |
| `scripts/monthly_plan/collectors/traffic.py` | Traffic funnel + SEO positions |
| `scripts/monthly_plan/collectors/sheets.py` | Google Sheets access (financier plan, KPI, external ads) |
| `scripts/monthly_plan/collect_all.py` | CLI entry: runs all collectors, outputs JSON |

### Skill (`.claude/skills/monthly-plan/`)

| File | Responsibility |
|------|---------------|
| `.claude/skills/monthly-plan/SKILL.md` | Orchestration: questions -> collect -> triage -> waves -> synthesize -> publish |
| `.claude/skills/monthly-plan/prompts/triage.md` | Anomaly detection prompt template |
| `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md` | P&L analysis (sections A, B, C) |
| `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md` | Price elasticity + hypotheses (section I, part of D) |
| `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md` | Ad budget + efficiency (sections H, E, part of D) |
| `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md` | Inventory + ABC + financier (sections F, G) |
| `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md` | Traffic funnel + SEO (part of D) |
| `.claude/skills/monthly-plan/prompts/critics/data-quality-critic.md` | Data quality audit |
| `.claude/skills/monthly-plan/prompts/critics/strategy-critic.md` | Strategy contradiction audit |
| `.claude/skills/monthly-plan/prompts/corrector.md` | Error correction (fix, don't decide) |
| `.claude/skills/monthly-plan/prompts/cfo.md` | CFO: validate, arbitrate, prioritize |
| `.claude/skills/monthly-plan/prompts/synthesizer.md` | Document assembly (12 sections A-L) |
| `.claude/skills/monthly-plan/templates/plan-structure.md` | Output template skeleton |

### Tests

| File | Responsibility |
|------|---------------|
| `tests/monthly_plan/__init__.py` | Package marker |
| `tests/monthly_plan/test_utils.py` | Date computation, quality flags tests |
| `tests/monthly_plan/test_collect_all.py` | Orchestrator integration test (mocked collectors) |

---

## Task 1: Package Scaffold + Utils

**Files:**
- Create: `scripts/monthly_plan/__init__.py`
- Create: `scripts/monthly_plan/collectors/__init__.py`
- Create: `scripts/monthly_plan/utils.py`
- Create: `tests/monthly_plan/__init__.py`
- Create: `tests/monthly_plan/test_utils.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p scripts/monthly_plan/collectors
mkdir -p tests/monthly_plan
```

- [ ] **Step 2: Write test for date utils**

```python
# tests/monthly_plan/__init__.py
# (empty)
```

```python
# tests/monthly_plan/test_utils.py
"""Tests for monthly plan date utilities and quality flags."""
import pytest
from scripts.monthly_plan.utils import compute_date_params, build_quality_flags


class TestComputeDateParams:
    def test_may_plan(self):
        params = compute_date_params("2026-05")
        assert params["plan_month"] == "2026-05"
        assert params["current_month_start"] == "2026-04-01"
        assert params["current_month_end"] == "2026-05-01"
        assert params["prev_month_start"] == "2026-03-01"
        assert params["elasticity_start"] == "2026-01-01"
        assert params["stock_window_start"] == "2026-04-25"

    def test_january_plan(self):
        """January plan uses December as base, November as prev."""
        params = compute_date_params("2026-01")
        assert params["current_month_start"] == "2025-12-01"
        assert params["current_month_end"] == "2026-01-01"
        assert params["prev_month_start"] == "2025-11-01"
        assert params["elasticity_start"] == "2025-09-01"

    def test_stock_window_always_last_week(self):
        params = compute_date_params("2026-03")
        # February base month, stock window = last week of Feb
        assert params["stock_window_start"] == "2026-02-22"


class TestBuildQualityFlags:
    def test_static_flags_present(self):
        flags = build_quality_flags(models_data={})
        assert flags["fan_out_bug"] is True
        assert flags["ozon_no_external_ads"] is True
        assert flags["traffic_powerbi_gap_20pct"] is True

    def test_low_data_models_detected(self):
        models_data = {
            "charlotte": {"data_months": 2},
            "wendy": {"data_months": 12},
        }
        flags = build_quality_flags(models_data)
        assert "charlotte" in flags["models_with_low_data"]
        assert "wendy" not in flags["models_with_low_data"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -m pytest tests/monthly_plan/test_utils.py -v
```

Expected: ModuleNotFoundError (scripts.monthly_plan.utils not found)

- [ ] **Step 4: Implement utils.py**

```python
# scripts/monthly_plan/__init__.py
# (empty)
```

```python
# scripts/monthly_plan/collectors/__init__.py
# (empty)
```

```python
# scripts/monthly_plan/utils.py
"""Date computation, quality flags, and helpers for monthly plan collector."""
from datetime import date, timedelta
from calendar import monthrange


def compute_date_params(plan_month: str) -> dict:
    """Compute all date parameters from target plan month (YYYY-MM).

    plan_month is the month we're PLANNING FOR.
    Base month (current) = plan_month - 1 (data we analyze).
    Prev month = plan_month - 2 (for m/m comparison).
    """
    year, month = map(int, plan_month.split("-"))

    # Base month = plan_month - 1
    if month == 1:
        base_year, base_month = year - 1, 12
    else:
        base_year, base_month = year, month - 1

    # Prev month = plan_month - 2
    if base_month == 1:
        prev_year, prev_month = base_year - 1, 12
    else:
        prev_year, prev_month = base_year, base_month - 1

    # Elasticity start = 3 months before base month end
    elast_month = base_month
    elast_year = base_year
    for _ in range(3):
        if elast_month == 1:
            elast_month = 12
            elast_year -= 1
        else:
            elast_month -= 1

    # Stock window = last week of base month
    last_day = monthrange(base_year, base_month)[1]
    stock_start = date(base_year, base_month, last_day) - timedelta(days=5)

    return {
        "plan_month": plan_month,
        "current_month_start": f"{base_year}-{base_month:02d}-01",
        "current_month_end": f"{year}-{month:02d}-01",
        "prev_month_start": f"{prev_year}-{prev_month:02d}-01",
        "elasticity_start": f"{elast_year}-{elast_month:02d}-01",
        "stock_window_start": stock_start.isoformat(),
    }


def build_quality_flags(models_data: dict) -> dict:
    """Build quality flags dict for JSON output.

    Args:
        models_data: {model_name: {"data_months": int}} for elasticity data availability
    """
    low_data = [
        model for model, info in models_data.items()
        if info.get("data_months", 0) < 3
    ]
    return {
        "fan_out_bug": True,
        "db_vs_sheets_external_ads_gap": True,
        "ozon_no_external_ads": True,
        "traffic_powerbi_gap_20pct": True,
        "models_with_low_data": sorted(low_data),
    }


def tuples_to_dicts(rows: list, columns: list) -> list:
    """Convert list of tuples (from cursor.fetchall) to list of dicts."""
    return [dict(zip(columns, row)) for row in rows]


def safe_float(val) -> float | None:
    """Convert value to float, returning None for non-numeric."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def model_from_article(article: str) -> str:
    """Extract model name from article: 'wendy/black' -> 'wendy'."""
    return article.split("/")[0].lower() if article else ""
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/monthly_plan/test_utils.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/monthly_plan/ tests/monthly_plan/
git commit -m "feat(monthly-plan): add package scaffold and date utils"
```

---

## Task 2: P&L Collector

**Files:**
- Create: `scripts/monthly_plan/collectors/pnl.py`

**Reference:** `shared/data_layer/finance.py` — functions return tuples from cursor.fetchall().

- [ ] **Step 1: Implement P&L collector**

```python
# scripts/monthly_plan/collectors/pnl.py
"""P&L data collector: total brand + by model, WB + OZON."""
from shared.data_layer.finance import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_by_model,
    get_ozon_by_model,
    get_wb_orders_by_model,
    get_ozon_orders_by_model,
)
from shared.data_layer.sku_mapping import get_model_statuses_mapped
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

# Column names matching finance.py query output
WB_FINANCE_COLS = [
    "period", "orders_count", "sales_count", "revenue_before_spp",
    "revenue_after_spp", "adv_internal", "adv_external", "cost_of_goods",
    "logistics", "storage", "commission", "spp_amount", "nds",
    "penalty", "retention", "deduction", "margin",
    "returns_revenue", "revenue_before_spp_gross",
]
WB_ORDERS_COLS = ["period", "orders_count", "orders_rub"]

OZON_FINANCE_COLS = [
    "period", "sales_count", "revenue_before_spp", "revenue_after_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
    "logistics", "storage", "commission", "spp_amount", "nds",
]
OZON_ORDERS_COLS = ["period", "orders_count", "orders_rub"]

MODEL_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]
MODEL_ORDERS_COLS = ["period", "model", "orders_count", "orders_rub"]


def _finance_to_dict(rows, columns, period_label):
    """Convert finance rows to dict, filtering by period label."""
    dicts = tuples_to_dicts(rows, columns)
    return [
        {k: safe_float(v) if k != "period" else v for k, v in d.items()}
        for d in dicts if d["period"] == period_label
    ]


def _model_rows_to_list(fin_rows, orders_rows, period_label):
    """Merge finance + orders rows by model for a given period."""
    fin = tuples_to_dicts(fin_rows, MODEL_COLS)
    ords = tuples_to_dicts(orders_rows, MODEL_ORDERS_COLS)

    # Index orders by model
    orders_map = {}
    for o in ords:
        if o["period"] == period_label:
            orders_map[o["model"]] = {
                "orders_count": safe_float(o["orders_count"]),
                "orders_rub": safe_float(o["orders_rub"]),
            }

    result = []
    for f in fin:
        if f["period"] != period_label:
            continue
        model = f["model"]
        entry = {k: safe_float(v) if k not in ("period", "model") else v for k, v in f.items()}
        entry.update(orders_map.get(model, {"orders_count": 0, "orders_rub": 0}))
        result.append(entry)

    return result


def collect_pnl(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect P&L data for total brand and by model.

    Returns dict with keys: pnl_total, pnl_models.
    """
    # Total P&L
    wb_fin, wb_orders = get_wb_finance(current_start, prev_start, current_end)
    ozon_fin, ozon_orders = get_ozon_finance(current_start, prev_start, current_end)

    # By model
    wb_by_model = get_wb_by_model(current_start, prev_start, current_end)
    ozon_by_model = get_ozon_by_model(current_start, prev_start, current_end)
    wb_orders_model = get_wb_orders_by_model(current_start, prev_start, current_end)
    ozon_orders_model = get_ozon_orders_by_model(current_start, prev_start, current_end)

    # Statuses
    statuses = get_model_statuses_mapped()

    # Build total
    pnl_total = {
        "current": {
            "wb": _finance_to_dict(wb_fin, WB_FINANCE_COLS, "current"),
            "wb_orders": _finance_to_dict(wb_orders, WB_ORDERS_COLS, "current"),
            "ozon": _finance_to_dict(ozon_fin, OZON_FINANCE_COLS, "current"),
            "ozon_orders": _finance_to_dict(ozon_orders, OZON_ORDERS_COLS, "current"),
        },
        "previous": {
            "wb": _finance_to_dict(wb_fin, WB_FINANCE_COLS, "previous"),
            "wb_orders": _finance_to_dict(wb_orders, WB_ORDERS_COLS, "previous"),
            "ozon": _finance_to_dict(ozon_fin, OZON_FINANCE_COLS, "previous"),
            "ozon_orders": _finance_to_dict(ozon_orders, OZON_ORDERS_COLS, "previous"),
        },
    }

    # Build by model
    wb_models_current = _model_rows_to_list(wb_by_model, wb_orders_model, "current")
    wb_models_prev = _model_rows_to_list(wb_by_model, wb_orders_model, "previous")
    ozon_models_current = _model_rows_to_list(ozon_by_model, ozon_orders_model, "current")
    ozon_models_prev = _model_rows_to_list(ozon_by_model, ozon_orders_model, "previous")

    # Index by model for merging
    ozon_idx = {m["model"]: m for m in ozon_models_current}
    ozon_prev_idx = {m["model"]: m for m in ozon_models_prev}
    wb_prev_idx = {m["model"]: m for m in wb_models_prev}

    active, exiting = [], []
    for wb_m in wb_models_current:
        model_name = wb_m["model"]
        status = statuses.get(model_name, statuses.get(model_name.capitalize(), "Unknown"))
        entry = {
            "model": model_name,
            "status": status,
            "current": {
                "wb": wb_m,
                "ozon": ozon_idx.get(model_name, {}),
            },
            "previous": {
                "wb": wb_prev_idx.get(model_name, {}),
                "ozon": ozon_prev_idx.get(model_name, {}),
            },
        }
        if status in ("Выводим", "Архив"):
            exiting.append(entry)
        else:
            active.append(entry)

    # Add OZON-only models
    wb_model_names = {m["model"] for m in wb_models_current}
    for oz_m in ozon_models_current:
        if oz_m["model"] not in wb_model_names:
            model_name = oz_m["model"]
            status = statuses.get(model_name, "Unknown")
            entry = {
                "model": model_name,
                "status": status,
                "current": {"wb": {}, "ozon": oz_m},
                "previous": {"wb": {}, "ozon": ozon_prev_idx.get(model_name, {})},
            }
            if status in ("Выводим", "Архив"):
                exiting.append(entry)
            else:
                active.append(entry)

    pnl_models = {"active": active, "exiting": exiting}

    return {"pnl_total": pnl_total, "pnl_models": pnl_models}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/monthly_plan/collectors/pnl.py
git commit -m "feat(monthly-plan): add P&L collector"
```

---

## Task 3: Pricing Collector

**Files:**
- Create: `scripts/monthly_plan/collectors/pricing.py`

**Reference:** `shared/data_layer/pricing_article.py` — returns list of dicts.

- [ ] **Step 1: Implement pricing collector**

```python
# scripts/monthly_plan/collectors/pricing.py
"""Price elasticity data collector: daily article-level for 3 months."""
from shared.data_layer.pricing_article import (
    get_wb_price_margin_daily_by_article,
    get_ozon_price_margin_daily_by_article,
)
from scripts.monthly_plan.utils import model_from_article


def collect_pricing(elasticity_start: str, current_end: str) -> dict:
    """Collect pricing data for elasticity analysis.

    Returns dict with by_article list and summary by model.
    """
    wb_data = get_wb_price_margin_daily_by_article(elasticity_start, current_end)
    ozon_data = get_ozon_price_margin_daily_by_article(elasticity_start, current_end)

    # Group by article, compute data availability
    articles = {}
    for row in wb_data:
        art = row["article"]
        if art not in articles:
            articles[art] = {
                "article": art,
                "model": row["model"] or model_from_article(art),
                "channel": "wb",
                "days_with_data": 0,
                "days_with_sales": 0,
                "price_min": None,
                "price_max": None,
                "daily_data": [],
            }
        entry = articles[art]
        entry["days_with_data"] += 1
        if (row.get("sales_count") or 0) > 0:
            entry["days_with_sales"] += 1
        price = row.get("price_per_unit")
        if price and price > 0:
            if entry["price_min"] is None or price < entry["price_min"]:
                entry["price_min"] = price
            if entry["price_max"] is None or price > entry["price_max"]:
                entry["price_max"] = price
        entry["daily_data"].append(row)

    for row in ozon_data:
        art = f"ozon:{row['article']}"
        if art not in articles:
            articles[art] = {
                "article": row["article"],
                "model": row["model"] or model_from_article(row["article"]),
                "channel": "ozon",
                "days_with_data": 0,
                "days_with_sales": 0,
                "price_min": None,
                "price_max": None,
                "daily_data": [],
            }
        entry = articles[art]
        entry["days_with_data"] += 1
        if (row.get("sales_count") or 0) > 0:
            entry["days_with_sales"] += 1
        price = row.get("price_per_unit")
        if price and price > 0:
            if entry["price_min"] is None or price < entry["price_min"]:
                entry["price_min"] = price
            if entry["price_max"] is None or price > entry["price_max"]:
                entry["price_max"] = price
        entry["daily_data"].append(row)

    # Compute price variation flag per article
    by_article = []
    for art_data in articles.values():
        has_variation = (
            art_data["price_min"] is not None
            and art_data["price_max"] is not None
            and art_data["price_max"] > art_data["price_min"] * 1.05
        )
        by_article.append({
            "article": art_data["article"],
            "model": art_data["model"],
            "channel": art_data["channel"],
            "days_with_data": art_data["days_with_data"],
            "days_with_sales": art_data["days_with_sales"],
            "price_variation": has_variation,
            "price_min": art_data["price_min"],
            "price_max": art_data["price_max"],
            "daily_data": art_data["daily_data"],
        })

    return {"pricing": {"by_article": by_article}}
```

- [ ] **Step 2: Commit**

```bash
git add scripts/monthly_plan/collectors/pricing.py
git commit -m "feat(monthly-plan): add pricing/elasticity collector"
```

---

## Task 4: Advertising Collector

**Files:**
- Create: `scripts/monthly_plan/collectors/advertising.py`

**Reference:** `shared/data_layer/finance.py` (get_wb_by_model adv fields), `shared/data_layer/advertising.py` (external breakdown).

Note: We use `get_wb_by_model()` for ROAS (workaround for fan-out bug in `get_wb_model_ad_roi()`).

- [ ] **Step 1: Implement advertising collector**

```python
# scripts/monthly_plan/collectors/advertising.py
"""Advertising data collector: ROAS, DRR, external breakdown."""
from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.advertising import get_wb_external_ad_breakdown
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

MODEL_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]
EXTERNAL_COLS = [
    "period", "adv_internal", "adv_bloggers", "adv_vk",
    "adv_creators", "adv_total",
]


def collect_advertising(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect advertising data: per-model ROAS/DRR + external breakdown.

    Uses get_wb_by_model (not get_wb_model_ad_roi) to avoid fan-out bug.
    """
    wb_models = tuples_to_dicts(
        get_wb_by_model(current_start, prev_start, current_end),
        MODEL_COLS,
    )
    ozon_models = tuples_to_dicts(
        get_ozon_by_model(current_start, prev_start, current_end),
        MODEL_COLS,
    )

    # External ad breakdown (WB only)
    external_raw = get_wb_external_ad_breakdown(current_start, prev_start, current_end)
    external = tuples_to_dicts(external_raw, EXTERNAL_COLS)

    # Build per-model ad metrics
    by_model = []
    for row in wb_models:
        if row["period"] != "current":
            continue
        rev = safe_float(row["revenue_before_spp"]) or 0
        adv_int = safe_float(row["adv_internal"]) or 0
        adv_ext = safe_float(row["adv_external"]) or 0
        margin = safe_float(row["margin"]) or 0
        adv_total = adv_int + adv_ext

        # Break-even DRR = margin2 % (margin after external ads / revenue)
        margin2 = margin - adv_ext  # margin from get_wb_by_model is M-1
        margin2_pct = (margin2 / rev * 100) if rev > 0 else 0
        drr = (adv_total / rev * 100) if rev > 0 else 0
        drr_internal = (adv_int / rev * 100) if rev > 0 else 0
        drr_external = (adv_ext / rev * 100) if rev > 0 else 0
        roas = (rev / adv_total) if adv_total > 0 else None

        by_model.append({
            "model": row["model"],
            "channel": "wb",
            "revenue": rev,
            "adv_internal": adv_int,
            "adv_external": adv_ext,
            "adv_total": adv_total,
            "margin1": margin,
            "margin2": margin2,
            "margin2_pct": round(margin2_pct, 1),
            "drr_total": round(drr, 1),
            "drr_internal": round(drr_internal, 1),
            "drr_external": round(drr_external, 1),
            "break_even_drr": round(margin2_pct, 1),
            "roas": round(roas, 1) if roas else None,
            "is_ad_loss": drr > margin2_pct if rev > 0 else False,
        })

    for row in ozon_models:
        if row["period"] != "current":
            continue
        rev = safe_float(row["revenue_before_spp"]) or 0
        adv_int = safe_float(row["adv_internal"]) or 0
        margin = safe_float(row["margin"]) or 0
        drr = (adv_int / rev * 100) if rev > 0 else 0
        roas = (rev / adv_int) if adv_int > 0 else None

        by_model.append({
            "model": row["model"],
            "channel": "ozon",
            "revenue": rev,
            "adv_internal": adv_int,
            "adv_external": 0,  # OZON external not tracked
            "adv_total": adv_int,
            "margin1": margin,
            "margin2": margin,  # OZON M2 = M1
            "margin2_pct": round((margin / rev * 100) if rev > 0 else 0, 1),
            "drr_total": round(drr, 1),
            "drr_internal": round(drr, 1),
            "drr_external": 0,
            "break_even_drr": round((margin / rev * 100) if rev > 0 else 0, 1),
            "roas": round(roas, 1) if roas else None,
            "is_ad_loss": False,  # Can't determine without external ads
        })

    # External breakdown (current period)
    external_current = [e for e in external if e["period"] == "current"]

    return {
        "advertising": {
            "by_model": by_model,
            "external_breakdown": [
                {k: safe_float(v) if k != "period" else v for k, v in e.items()}
                for e in external_current
            ],
            "channels": ["МП_внутр", "блогеры", "ВК", "creators"],
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/monthly_plan/collectors/advertising.py
git commit -m "feat(monthly-plan): add advertising collector with fan-out workaround"
```

---

## Task 5: Inventory Collector

**Files:**
- Create: `scripts/monthly_plan/collectors/inventory.py`

**Reference:** `shared/data_layer/inventory.py` — returns dicts.

- [ ] **Step 1: Implement inventory collector**

```python
# scripts/monthly_plan/collectors/inventory.py
"""Inventory data collector: FBO stocks, MoySklad, turnover, risk assessment."""
from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_model,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
)
from scripts.monthly_plan.utils import model_from_article

# Risk thresholds (days of stock)
DEFICIT_DAYS = 14
OK_MAX_DAYS = 60
OVERSTOCK_DAYS = 90
DEAD_STOCK_DAYS = 250


def _assess_risk(turnover_days: float) -> str:
    """Assess inventory risk based on days of stock."""
    if turnover_days < DEFICIT_DAYS:
        return "DEFICIT"
    elif turnover_days <= OK_MAX_DAYS:
        return "OK"
    elif turnover_days <= OVERSTOCK_DAYS:
        return "WARNING"
    elif turnover_days <= DEAD_STOCK_DAYS:
        return "OVERSTOCK"
    else:
        return "DEAD_STOCK"


def collect_inventory(
    stock_start: str,
    stock_end: str,
    turnover_start: str,
    turnover_end: str,
) -> dict:
    """Collect inventory data: stocks, turnover, risk assessment.

    Args:
        stock_start: start of stock window (last week of month)
        stock_end: end of stock window (= current_month_end)
        turnover_start: start of turnover period (= current_month_start)
        turnover_end: end of turnover period (= current_month_end)
    """
    # Raw stock data (article-level)
    wb_stocks = get_wb_avg_stock(stock_start, stock_end)
    ozon_stocks = get_ozon_avg_stock(stock_start, stock_end)

    # MoySklad (model-level)
    ms_stocks = get_moysklad_stock_by_model()

    # Turnover (model-level, includes daily sales and days)
    wb_turnover = get_wb_turnover_by_model(turnover_start, turnover_end)
    ozon_turnover = get_ozon_turnover_by_model(turnover_start, turnover_end)

    # Aggregate WB stocks by model
    wb_by_model = {}
    for article, stock_val in wb_stocks.items():
        model = model_from_article(article)
        wb_by_model[model] = wb_by_model.get(model, 0) + (stock_val or 0)

    # Aggregate OZON stocks by model
    ozon_by_model = {}
    for article, stock_val in ozon_stocks.items():
        model = model_from_article(article)
        ozon_by_model[model] = ozon_by_model.get(model, 0) + (stock_val or 0)

    # Build unified model inventory with risks
    all_models = set(wb_by_model) | set(ozon_by_model) | set(wb_turnover) | set(ozon_turnover)

    inventory_models = []
    risks = []
    for model in sorted(all_models):
        wb_turn = wb_turnover.get(model, {})
        ozon_turn = ozon_turnover.get(model, {})
        ms = ms_stocks.get(model, {})

        wb_days = wb_turn.get("turnover_days", 0) or 0
        ozon_days = ozon_turn.get("turnover_days", 0) or 0

        entry = {
            "model": model,
            "wb_fbo_stock": wb_by_model.get(model, 0),
            "ozon_fbo_stock": ozon_by_model.get(model, 0),
            "moysklad_stock": ms.get("total", 0) if ms else 0,
            "moysklad_transit": ms.get("stock_transit", 0) if ms else 0,
            "wb_daily_sales": wb_turn.get("daily_sales", 0),
            "ozon_daily_sales": ozon_turn.get("daily_sales", 0),
            "wb_turnover_days": round(wb_days, 1),
            "ozon_turnover_days": round(ozon_days, 1),
            "wb_risk": _assess_risk(wb_days),
            "ozon_risk": _assess_risk(ozon_days),
        }
        inventory_models.append(entry)

        # Collect risks for triage
        if entry["wb_risk"] in ("DEFICIT", "OVERSTOCK", "DEAD_STOCK"):
            risks.append({
                "model": model, "channel": "wb",
                "risk": entry["wb_risk"], "days": wb_days,
            })
        if entry["ozon_risk"] in ("DEFICIT", "OVERSTOCK", "DEAD_STOCK"):
            risks.append({
                "model": model, "channel": "ozon",
                "risk": entry["ozon_risk"], "days": ozon_days,
            })

    return {
        "inventory": {
            "by_model": inventory_models,
            "risks": risks,
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/monthly_plan/collectors/inventory.py
git commit -m "feat(monthly-plan): add inventory collector with risk assessment"
```

---

## Task 6: ABC + Sheets Collectors

**Files:**
- Create: `scripts/monthly_plan/collectors/abc.py`
- Create: `scripts/monthly_plan/collectors/sheets.py`

**Reference:** `shared/data_layer/planning.py` for ABC, Google Sheets via gws CLI for financier plan.

- [ ] **Step 1: Implement Sheets collector**

```python
# scripts/monthly_plan/collectors/sheets.py
"""Google Sheets data collector: financier plan, KPI targets, external ads."""
import json
import subprocess

# Sheet IDs (stable)
FINANCIER_SHEET_ID = "1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk"
KPI_SHEET_ID = "1GRCGSAJESSDvAhoVMmXljXy-qErMKt-n45PV96YBiVY"
EXTERNAL_ADS_SHEET_ID = "1PvsgAkb2K84ss4iTD25yoD0pxSZYiVgcqetVUtCBvGg"

# Russian month names for sheet tab lookup
MONTH_NAMES_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def _read_sheet(sheet_id: str, range_str: str) -> list:
    """Read Google Sheet range via gws CLI. Returns list of rows."""
    try:
        result = subprocess.run(
            ["gws", "sheets", "get", sheet_id, "--range", range_str, "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return []


def collect_sheets(plan_month: str) -> dict:
    """Collect data from Google Sheets: financier plan, KPI, external ads.

    Args:
        plan_month: target month "YYYY-MM" (e.g., "2026-05")
    """
    year, month = map(int, plan_month.split("-"))

    # Base month = plan_month - 1 (for external ads of current period)
    if month == 1:
        base_month_num = 12
    else:
        base_month_num = month - 1
    base_month_name = MONTH_NAMES_RU.get(base_month_num, "")

    # Plan month name (for financier plan)
    plan_month_name = MONTH_NAMES_RU.get(month, "")

    # 1. Financier plan
    financier_wb = _read_sheet(FINANCIER_SHEET_ID, "WB!A1:Z50")
    financier_ozon = _read_sheet(FINANCIER_SHEET_ID, "OZON!A1:Z30")

    # 2. KPI targets
    kpi_data = _read_sheet(KPI_SHEET_ID, "Sheet1!A1:Z20")

    # 3. External ads (base month)
    external_ads_range = f"Итог {base_month_name}!A1:Q40"
    external_ads = _read_sheet(EXTERNAL_ADS_SHEET_ID, external_ads_range)

    return {
        "sheets": {
            "financier_plan": {
                "wb": financier_wb,
                "ozon": financier_ozon,
            },
            "kpi_targets": kpi_data,
            "external_ads_detailed": external_ads,
            "external_ads_month": base_month_name,
        }
    }
```

- [ ] **Step 2: Implement ABC collector**

```python
# scripts/monthly_plan/collectors/abc.py
"""ABC classification collector."""
from shared.data_layer.planning import get_active_models_with_abc


def collect_abc(current_start: str, current_end: str) -> dict:
    """Collect ABC classification data.

    Returns dict with abc classification list and summary.
    """
    abc_data = get_active_models_with_abc(current_start, current_end)

    # abc_data is list of dicts:
    # [{model, total_margin, articles: [{artikul, abc_class, margin, margin_share_pct, orders, opens}]}]

    classification = []
    for model_data in abc_data:
        a_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "A")
        b_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "B")
        c_count = sum(1 for a in model_data["articles"] if a["abc_class"] == "C")

        classification.append({
            "model": model_data["model"],
            "total_margin": model_data["total_margin"],
            "article_count": len(model_data["articles"]),
            "a_count": a_count,
            "b_count": b_count,
            "c_count": c_count,
            "articles": model_data["articles"],
        })

    return {"abc": {"classification": classification}}
```

- [ ] **Step 3: Commit**

```bash
git add scripts/monthly_plan/collectors/sheets.py scripts/monthly_plan/collectors/abc.py
git commit -m "feat(monthly-plan): add ABC and Google Sheets collectors"
```

---

## Task 7: Traffic Collector

**Files:**
- Create: `scripts/monthly_plan/collectors/traffic.py`

- [ ] **Step 1: Implement traffic collector**

```python
# scripts/monthly_plan/collectors/traffic.py
"""Traffic and funnel data collector: WB ad traffic + organic funnel + SEO."""
from shared.data_layer.traffic import get_wb_traffic_by_model
from shared.data_layer.funnel_seo import get_wb_article_funnel
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

TRAFFIC_COLS = [
    "period", "model", "ad_views", "ad_clicks", "ad_spend",
    "ad_to_cart", "ad_orders", "ctr", "cpc",
]
FUNNEL_COLS = [
    "model", "rank", "artikul", "opens", "cart", "orders",
    "buyouts", "cr_open_cart", "cr_cart_order", "cro", "crp",
    "revenue_spp", "margin", "orders_fin", "avg_check", "drr",
]


def collect_traffic(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect traffic, funnel and SEO data (WB only).

    Note: OZON traffic data not available. content_analysis has ~20% gap vs PowerBI.
    """
    # Ad traffic by model
    traffic_raw = get_wb_traffic_by_model(current_start, prev_start, current_end)
    traffic = tuples_to_dicts(traffic_raw, TRAFFIC_COLS)

    traffic_current = [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in t.items()}
        for t in traffic if t["period"] == "current"
    ]
    traffic_prev = [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in t.items()}
        for t in traffic if t["period"] == "previous"
    ]

    # Organic funnel (top articles per model)
    funnel_raw = get_wb_article_funnel(current_start, current_end, top_n=10)
    funnel = [
        {k: safe_float(v) if k not in ("model", "artikul") else v for k, v in row.items()}
        for row in tuples_to_dicts(funnel_raw, FUNNEL_COLS)
    ]

    return {
        "traffic": {
            "by_model_current": traffic_current,
            "by_model_previous": traffic_prev,
            "funnel": funnel,
            "limitations": [
                "WB only - OZON organic traffic not available",
                "~20% gap with PowerBI - use as trend indicator only",
            ],
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/monthly_plan/collectors/traffic.py
git commit -m "feat(monthly-plan): add traffic and funnel collector"
```

---

## Task 8: collect_all.py Orchestrator

**Files:**
- Create: `scripts/monthly_plan/collect_all.py`
- Create: `tests/monthly_plan/test_collect_all.py`

- [ ] **Step 1: Write test for collect_all**

```python
# tests/monthly_plan/test_collect_all.py
"""Tests for monthly plan data collection orchestrator."""
import json
import pytest
from unittest.mock import patch, MagicMock
from scripts.monthly_plan.collect_all import run_collection


@patch("scripts.monthly_plan.collect_all.collect_pnl")
@patch("scripts.monthly_plan.collect_all.collect_pricing")
@patch("scripts.monthly_plan.collect_all.collect_advertising")
@patch("scripts.monthly_plan.collect_all.collect_inventory")
@patch("scripts.monthly_plan.collect_all.collect_abc")
@patch("scripts.monthly_plan.collect_all.collect_traffic")
@patch("scripts.monthly_plan.collect_all.collect_sheets")
def test_run_collection_merges_all_blocks(
    mock_sheets, mock_traffic, mock_abc, mock_inv,
    mock_adv, mock_pricing, mock_pnl,
):
    mock_pnl.return_value = {"pnl_total": {}, "pnl_models": {"active": [], "exiting": []}}
    mock_pricing.return_value = {"pricing": {"by_article": []}}
    mock_adv.return_value = {"advertising": {"by_model": []}}
    mock_inv.return_value = {"inventory": {"by_model": [], "risks": []}}
    mock_abc.return_value = {"abc": {"classification": []}}
    mock_traffic.return_value = {"traffic": {"by_model_current": []}}
    mock_sheets.return_value = {"sheets": {"financier_plan": {}}}

    result = run_collection("2026-05")

    assert "meta" in result
    assert result["meta"]["plan_month"] == "2026-05"
    assert "pnl_total" in result
    assert "pricing" in result
    assert "advertising" in result
    assert "inventory" in result
    assert "abc" in result
    assert "traffic" in result
    assert "sheets" in result
    assert "quality_flags" in result["meta"]

    # Verify JSON serializable
    json.dumps(result)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/monthly_plan/test_collect_all.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement collect_all.py**

```python
# scripts/monthly_plan/collect_all.py
"""Monthly plan data collection orchestrator.

Usage:
    python scripts/monthly_plan/collect_all.py --month 2026-05
    python scripts/monthly_plan/collect_all.py --month 2026-05 --output /tmp/data.json
    python scripts/monthly_plan/collect_all.py --month 2026-05 --cached /tmp/data.json
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from scripts.monthly_plan.utils import compute_date_params, build_quality_flags
from scripts.monthly_plan.collectors.pnl import collect_pnl
from scripts.monthly_plan.collectors.pricing import collect_pricing
from scripts.monthly_plan.collectors.advertising import collect_advertising
from scripts.monthly_plan.collectors.inventory import collect_inventory
from scripts.monthly_plan.collectors.abc import collect_abc
from scripts.monthly_plan.collectors.traffic import collect_traffic
from scripts.monthly_plan.collectors.sheets import collect_sheets


def run_collection(plan_month: str) -> dict:
    """Run all collectors and merge results into single dict.

    Args:
        plan_month: target month "YYYY-MM" to plan for.

    Returns:
        Complete data bundle as JSON-serializable dict.
    """
    t0 = time.time()
    params = compute_date_params(plan_month)

    cs = params["current_month_start"]
    ce = params["current_month_end"]
    ps = params["prev_month_start"]
    es = params["elasticity_start"]
    ss = params["stock_window_start"]

    # Define collection tasks
    tasks = {
        "pnl": lambda: collect_pnl(cs, ps, ce),
        "pricing": lambda: collect_pricing(es, ce),
        "advertising": lambda: collect_advertising(cs, ps, ce),
        "inventory": lambda: collect_inventory(ss, ce, cs, ce),
        "abc": lambda: collect_abc(cs, ce),
        "traffic": lambda: collect_traffic(cs, ps, ce),
        "sheets": lambda: collect_sheets(plan_month),
    }

    # Run collectors in parallel
    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                errors[name] = str(e)
                results[name] = {}

    # Merge all results into flat structure
    merged = {}
    for block_result in results.values():
        merged.update(block_result)

    # Compute quality flags
    # Estimate data months per model from pricing data
    pricing_data = merged.get("pricing", {}).get("by_article", [])
    models_data = {}
    for art in pricing_data:
        model = art.get("model", "")
        days = art.get("days_with_data", 0)
        months_approx = days / 30
        if model not in models_data or months_approx > models_data[model].get("data_months", 0):
            models_data[model] = {"data_months": months_approx}

    duration = round(time.time() - t0, 1)

    merged["meta"] = {
        "plan_month": plan_month,
        "base_month": cs[:7],
        "prev_month": ps[:7],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "collection_duration_sec": duration,
        "quality_flags": build_quality_flags(models_data),
        "date_params": params,
        "errors": errors,
    }

    return merged


def main():
    parser = argparse.ArgumentParser(description="Collect data for monthly business plan")
    parser.add_argument("--month", required=True, help="Plan month YYYY-MM (e.g., 2026-05)")
    parser.add_argument("--output", help="Save JSON to file (default: stdout)")
    parser.add_argument("--cached", help="Use cached JSON file instead of collecting")
    args = parser.parse_args()

    if args.cached:
        with open(args.cached) as f:
            data = json.load(f)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    data = run_collection(args.month)

    output = json.dumps(data, ensure_ascii=False, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output} ({len(output)} bytes, {data['meta']['collection_duration_sec']}s)",
              file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/monthly_plan/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/monthly_plan/collect_all.py tests/monthly_plan/test_collect_all.py
git commit -m "feat(monthly-plan): add collect_all orchestrator with parallel execution"
```

---

## Task 9: Plan Structure Template

**Files:**
- Create: `.claude/skills/monthly-plan/templates/plan-structure.md`

- [ ] **Step 1: Create directories**

```bash
mkdir -p .claude/skills/monthly-plan/templates
mkdir -p .claude/skills/monthly-plan/prompts/analysts
mkdir -p .claude/skills/monthly-plan/prompts/critics
```

- [ ] **Step 2: Write plan structure template**

This template defines the 12-section output format based on the April 2026 pilot (`docs/plans/2026-04-business-plan-final.md`).

Create file `.claude/skills/monthly-plan/templates/plan-structure.md` with the full template from the design spec section 8, expanded with column definitions from the April pilot.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/monthly-plan/templates/
git commit -m "feat(monthly-plan): add plan structure template (12 sections A-L)"
```

---

## Task 10: SKILL.md — Skill Orchestrator

**Files:**
- Create: `.claude/skills/monthly-plan/SKILL.md`

This is the core orchestration file. It controls the entire pipeline: questions -> collect -> triage -> 4 waves -> synthesize -> publish.

- [ ] **Step 1: Write SKILL.md**

Create `.claude/skills/monthly-plan/SKILL.md` with:
- Frontmatter (name, description, triggers)
- Stage 0: Context Collection (5 fixed questions via AskUserQuestion)
- Stage 1: Data Collection (Bash: `python scripts/monthly_plan/collect_all.py`)
- Stage 1.5: Triage (read JSON, read `prompts/triage.md`, ask contextual questions)
- Stage 2 Wave 1: Launch 5 analysts in parallel (Agent tool, read each prompt file, inject data slice + user_context)
- Stage 2 Wave 2: Launch 2 critics in parallel (Agent tool, inject all analyst outputs)
- Stage 2 Wave 3: Launch corrector (Agent tool, inject analyst outputs + critic findings)
- Stage 2 Wave 4: Launch CFO (Agent tool, inject corrected findings + critic notes)
- CFO verdict handling: APPROVE -> Stage 3, CORRECT -> apply + Stage 3, REJECT -> re-run (max 1 retry)
- Stage 3: Launch synthesizer (Agent tool, inject CFO output + corrected findings)
- Stage 4: Publish (Write MD file, Notion MCP, gws sheets)

Key implementation detail: SKILL.md reads prompt files from `prompts/` directory using Read tool, then passes their content as the `prompt` parameter to Agent tool, with data injected via string substitution markers (`{{DATA_SLICE}}`, `{{USER_CONTEXT}}`, `{{QUALITY_FLAGS}}`).

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/monthly-plan/SKILL.md
git commit -m "feat(monthly-plan): add SKILL.md orchestrator with 4-wave pipeline"
```

---

## Task 11: Triage Prompt

**Files:**
- Create: `.claude/skills/monthly-plan/prompts/triage.md`

- [ ] **Step 1: Write triage prompt**

The triage prompt reads the collected JSON and identifies anomalies that require user input. It uses the anomaly triggers from the design spec (margin >5pp, DRR > break-even, deficit <14d, overstock >90d, plan divergence >20%, new model <3 months).

Create `.claude/skills/monthly-plan/prompts/triage.md` with:
- Role: Data triage analyst for Wookiee brand
- Input: full JSON data bundle
- Instructions: scan for each anomaly type, generate specific contextual questions
- Output format: list of questions with context, or "NO_ANOMALIES" if none found
- Max 5 questions

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/triage.md
git commit -m "feat(monthly-plan): add triage prompt for anomaly detection"
```

---

## Task 12: Analyst Prompts (5 files)

**Files:**
- Create: `.claude/skills/monthly-plan/prompts/analysts/pnl-analyst.md`
- Create: `.claude/skills/monthly-plan/prompts/analysts/pricing-analyst.md`
- Create: `.claude/skills/monthly-plan/prompts/analysts/ad-analyst.md`
- Create: `.claude/skills/monthly-plan/prompts/analysts/inventory-analyst.md`
- Create: `.claude/skills/monthly-plan/prompts/analysts/traffic-analyst.md`

Each analyst prompt follows the contract from design spec section 5.2: Role, Context, Data, User context, Quality flags, Task, Output format, Analysis rules, Dozapros instructions.

- [ ] **Step 1: Write P&L Analyst prompt**

`prompts/analysts/pnl-analyst.md`:
- Sections to produce: A (P&L Total), B (Active models), C (Exiting models)
- Must show both M-1 and M-2
- Must compare m/m with Δ%
- Must build two scenarios (optimal/aggressive) for plan month
- Dozapros: if model margin anomaly -> request daily breakdown via `python -c "from shared.data_layer.finance import ..."`
- Output: structured markdown with tables matching April pilot format

- [ ] **Step 2: Write Pricing Analyst prompt**

`prompts/analysts/pricing-analyst.md`:
- Sections to produce: I (Elasticity), part of D (price hypotheses)
- Must compute E and r per article, volume-weighted per model
- Must classify: inelastic (|E|<1), elastic (|E|>2), medium
- Must assign confidence: HIGH (|r|>0.5, >30 days), MED (0.3<|r|<0.5), LOW (<0.3 or <15 days)
- Must calculate effect in rubles for each hypothesis
- Critical rule: article-level E, not model-level (model-level inflates 2-13x)
- Dozapros: specific articles for deeper analysis

- [ ] **Step 3: Write Ad Analyst prompt**

`prompts/analysts/ad-analyst.md`:
- Sections to produce: H (Ad efficiency), E (Budget scenarios), part of D (ad recommendations)
- Must show DRR with internal/external split
- Must compute break-even DRR = M-2%
- Must flag models where DRR > break-even
- Must build two budget scenarios (optimal/aggressive)
- Must analyze ad->orders link (effective vs ineffective)
- Dozapros: Google Sheets external ads detail via gws CLI

- [ ] **Step 4: Write Inventory Analyst prompt**

`prompts/analysts/inventory-analyst.md`:
- Sections to produce: F (Inventory), G (ABC + financier reconciliation)
- Must assess risk per model: DEFICIT/OK/WARNING/OVERSTOCK/DEAD_STOCK
- Must check MoySklad for replenishment potential
- Must do ABC: A-article in "Выводим" = flag, C-article in "Продаётся" = cleanup candidate
- Must reconcile financier plan vs fact (from Sheets data)
- Dozapros: daily stock changes, specific warehouse breakdown

- [ ] **Step 5: Write Traffic Analyst prompt**

`prompts/analysts/traffic-analyst.md`:
- Sections to produce: part of D (traffic/conversion hypotheses)
- Must build funnel per model: shows -> clicks -> cart -> orders
- Must compute CR by funnel stage
- Must note WB-only limitation and PowerBI gap
- Must note WB glue effect (Wendy -> Audrey/Lana attribution)
- Dozapros: specific model funnel data

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/analysts/
git commit -m "feat(monthly-plan): add 5 analyst prompt templates"
```

---

## Task 13: Critics + Corrector + CFO + Synthesizer Prompts

**Files:**
- Create: `.claude/skills/monthly-plan/prompts/critics/data-quality-critic.md`
- Create: `.claude/skills/monthly-plan/prompts/critics/strategy-critic.md`
- Create: `.claude/skills/monthly-plan/prompts/corrector.md`
- Create: `.claude/skills/monthly-plan/prompts/cfo.md`
- Create: `.claude/skills/monthly-plan/prompts/synthesizer.md`

- [ ] **Step 1: Write Data Quality Critic prompt**

`prompts/critics/data-quality-critic.md`:
- Input: all analyst outputs
- Checks: arithmetic (models sum = total <1%), DRR calculation, SPP weighted average, GROUP BY LOWER, elasticity not inflated, dates exclusive, both M-1 and M-2 present, buyout % not used as daily driver
- Output: list of errors with severity (critical/warning) + fix instructions

- [ ] **Step 2: Write Strategy Critic prompt**

`prompts/critics/strategy-critic.md`:
- Input: all analyst outputs
- Checks: contradictions between analysts (price cut + deficit, budget increase + DRR > BE, growth + overstock), completeness (all active models have recommendations), realism (scenarios vs trend), LOW confidence recommendations not aggressive
- Output: list of contradictions + resolution proposals

- [ ] **Step 3: Write Corrector prompt**

`prompts/corrector.md`:
- Input: analyst outputs + critic findings
- Task: fix arithmetic errors (may dorequest via Bash), resolve factual contradictions, mark strategic contradictions as REQUIRES_CFO_DECISION
- Output: corrected analyst findings + CFO question list

- [ ] **Step 4: Write CFO prompt**

`prompts/cfo.md`:
- Input: corrected findings + critic notes + user_context
- Task: validate each recommendation, arbitrate REQUIRES_CFO_DECISION items, prioritize by week, final verdict per model
- Three verdicts: APPROVE, CORRECT (inline edits), REJECT (specify which analysts, what to fix)
- REJECT format: `{"verdict": "REJECT", "rerun_analysts": ["pricing"], "feedback": "..."}`
- On Pass 2: must APPROVE or CORRECT, no REJECT allowed
- Output: structured decisions document

- [ ] **Step 5: Write Synthesizer prompt**

`prompts/synthesizer.md`:
- Input: CFO decisions + corrected analyst findings + user_context + quality_flags
- Task: assemble 12-section document (A-L) following plan-structure.md template
- Must use tables matching April pilot format (see `docs/plans/2026-04-business-plan-final.md`)
- Must include verification metadata in header (N analysts, M checks, CFO verdict)
- Output: complete markdown document ready for publication

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/monthly-plan/prompts/
git commit -m "feat(monthly-plan): add critic, corrector, CFO, and synthesizer prompts"
```

---

## Task 14: Smoke Test

**Files:**
- No new files

- [ ] **Step 1: Verify collector runs against real DB**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/monthly_plan/collect_all.py --month 2026-05 --output /tmp/monthly-plan-may-2026.json
```

Expected: JSON file created with all 7 blocks + meta. Check stderr for timing and errors.

- [ ] **Step 2: Verify JSON is valid and complete**

```bash
python -c "
import json
with open('/tmp/monthly-plan-may-2026.json') as f:
    data = json.load(f)
for key in ['meta', 'pnl_total', 'pnl_models', 'pricing', 'advertising', 'inventory', 'abc', 'traffic', 'sheets']:
    print(f'{key}: {\"OK\" if key in data else \"MISSING\"}')"
```

Expected: all OK

- [ ] **Step 3: Verify skill files exist**

```bash
ls -la .claude/skills/monthly-plan/SKILL.md
ls -la .claude/skills/monthly-plan/prompts/analysts/*.md | wc -l  # should be 5
ls -la .claude/skills/monthly-plan/prompts/critics/*.md | wc -l  # should be 2
ls -la .claude/skills/monthly-plan/prompts/corrector.md
ls -la .claude/skills/monthly-plan/prompts/cfo.md
ls -la .claude/skills/monthly-plan/prompts/synthesizer.md
ls -la .claude/skills/monthly-plan/prompts/triage.md
ls -la .claude/skills/monthly-plan/templates/plan-structure.md
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/monthly_plan/ -v
```

Expected: all PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(monthly-plan): complete skill implementation with all prompts and collectors"
```
