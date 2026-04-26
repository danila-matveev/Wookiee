# Analytics Report Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/analytics-report` skill — a 12-subagent analytics pipeline that replaces Oleg v2 for financial+marketing analysis of the Wookiee brand across WB+OZON.

**Architecture:** Python collector (8 parallel modules via ThreadPoolExecutor → JSON) feeds into Claude Code skill orchestrator (SKILL.md) that dispatches 8 analyst subagents in parallel, then 3 verifier subagents, then 1 synthesizer. Output: MD file + Notion page.

**Tech Stack:** Python 3.11 (data_layer, gws CLI), Claude Code skills (SKILL.md + prompt templates), Notion MCP

**Spec:** `docs/superpowers/specs/2026-04-07-analytics-report-design.md`

---

## File Map

### Python Collector (`scripts/analytics_report/`)

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker |
| `utils.py` | Date params, quality flags, helpers (tuples_to_dicts, safe_float) |
| `collect_all.py` | Orchestrator: ThreadPoolExecutor → 8 collectors → JSON |
| `collectors/__init__.py` | Package marker |
| `collectors/finance.py` | WB+OZON P&L: brand, channel, model, article |
| `collectors/advertising.py` | Ad ROI, DRR, daily series, campaigns, budget |
| `collectors/external_marketing.py` | Google Sheets: bloggers, VK, Yandex, SMM |
| `collectors/traffic.py` | Funnels: organic vs paid, by model, by status |
| `collectors/inventory.py` | Stocks: WB FBO + OZON FBO + MoySklad + turnover |
| `collectors/pricing.py` | Prices, SPP, changes, period aggregates |
| `collectors/plan_fact.py` | Google Sheets plan + data_layer fact |
| `collectors/sku_statuses.py` | Supabase: model statuses, article mappings |

### Skill Files (`.claude/skills/analytics-report/`)

| File | Responsibility |
|---|---|
| `SKILL.md` | Main orchestrator: 5 stages, placeholder injection, wave dispatch |
| `prompts/analysts/financial.md` | Subagent 1: Full financial funnel |
| `prompts/analysts/internal-ads.md` | Subagent 2: MP advertising efficiency |
| `prompts/analysts/external-marketing.md` | Subagent 3: Bloggers, VK, Yandex, SMM |
| `prompts/analysts/traffic-funnel.md` | Subagent 4: Traffic funnel analysis |
| `prompts/analysts/inventory.md` | Subagent 5: Stock & turnover |
| `prompts/analysts/pricing.md` | Subagent 6: Prices & hypotheses |
| `prompts/analysts/plan-fact.md` | Subagent 7: Plan vs fact |
| `prompts/analysts/anomaly-detector.md` | Subagent 8: Anomaly detection |
| `prompts/verifiers/marketplace-expert.md` | Subagent 9: WB specialist |
| `prompts/verifiers/cfo.md` | Subagent 10: CFO verification |
| `prompts/verifiers/data-quality-critic.md` | Subagent 11: Data quality checks |
| `prompts/synthesizer.md` | Subagent 12: Executive Summary + full report |
| `templates/report-structure.md` | 13-section report skeleton |
| `templates/notion-formatting-guide.md` | Notion table/color/callout rules |
| `references/data-sources.md` | DB tables, API endpoints, Sheets reference |
| `references/analytics-rules.md` | Rules KB: benchmarks, decision trees |

### Tests (`tests/analytics_report/`)

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker |
| `test_utils.py` | Date params, quality flags |
| `test_collectors.py` | All 8 collectors (mocked data_layer) |
| `test_collect_all.py` | Orchestrator integration test |

---

## Task 1: Utilities and Project Scaffold

**Files:**
- Create: `scripts/analytics_report/__init__.py`
- Create: `scripts/analytics_report/utils.py`
- Create: `scripts/analytics_report/collectors/__init__.py`
- Create: `tests/analytics_report/__init__.py`
- Create: `tests/analytics_report/test_utils.py`

- [ ] **Step 1: Write tests for date parameter computation**

```python
# tests/analytics_report/test_utils.py
"""Tests for analytics report date utilities."""
import pytest
from scripts.analytics_report.utils import compute_date_params, build_quality_flags


class TestComputeDateParams:
    """Test date parameter computation for all report depths."""

    def test_single_date_daily(self):
        """Single date → daily report, prev = yesterday."""
        p = compute_date_params("2026-04-05")
        assert p["start_date"] == "2026-04-05"
        assert p["end_date"] == "2026-04-05"
        assert p["prev_start"] == "2026-04-04"
        assert p["prev_end"] == "2026-04-04"
        assert p["depth"] == "day"

    def test_two_dates_weekly(self):
        """Two dates 7 days apart → weekly."""
        p = compute_date_params("2026-03-30", "2026-04-05")
        assert p["start_date"] == "2026-03-30"
        assert p["end_date"] == "2026-04-05"
        assert p["prev_start"] == "2026-03-23"
        assert p["prev_end"] == "2026-03-29"
        assert p["depth"] == "week"

    def test_two_dates_monthly(self):
        """Two dates ~30 days apart → monthly."""
        p = compute_date_params("2026-03-01", "2026-03-31")
        assert p["start_date"] == "2026-03-01"
        assert p["end_date"] == "2026-03-31"
        assert p["prev_start"] == "2026-02-01"
        assert p["prev_end"] == "2026-02-28"
        assert p["depth"] == "month"

    def test_cross_month_boundary(self):
        """Period crossing month boundary."""
        p = compute_date_params("2026-01-01", "2026-01-07")
        assert p["prev_start"] == "2025-12-25"
        assert p["prev_end"] == "2025-12-31"

    def test_period_label_format(self):
        """Labels in Russian date format."""
        p = compute_date_params("2026-03-30", "2026-04-05")
        assert "марта" in p["period_label"] or "апреля" in p["period_label"]

    def test_month_start_date(self):
        """month_start for plan-fact MTD calculation."""
        p = compute_date_params("2026-04-02", "2026-04-05")
        assert p["month_start"] == "2026-04-01"


class TestBuildQualityFlags:
    def test_returns_expected_keys(self):
        flags = build_quality_flags({})
        assert "traffic_gap" in flags
        assert "buyout_lag" in flags
        assert "fan_out_detected" in flags
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/analytics_report/test_utils.py -v`
Expected: ModuleNotFoundError — `scripts.analytics_report.utils` not found

- [ ] **Step 3: Create package scaffolds and implement utils.py**

```python
# scripts/analytics_report/__init__.py
"""Analytics report data collection package."""
```

```python
# scripts/analytics_report/collectors/__init__.py
"""Analytics report data collectors."""
```

```python
# tests/analytics_report/__init__.py
"""Analytics report tests."""
```

```python
# scripts/analytics_report/utils.py
"""Date computation, quality flags, and helpers for analytics report collector."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Optional

MONTHS_RU_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def compute_date_params(start_str: str, end_str: str | None = None) -> dict:
    """Compute all date parameters for the analytics report.

    Args:
        start_str: Start date "YYYY-MM-DD". If end_str is None, this is the single day.
        end_str: End date "YYYY-MM-DD" or None for daily report.

    Returns:
        Dict with keys: start_date, end_date, prev_start, prev_end, depth,
        period_label, prev_period_label, month_start, days_in_period.
    """
    start = date.fromisoformat(start_str)

    if end_str is None:
        # Daily report
        end = start
        prev_end = start - timedelta(days=1)
        prev_start = prev_end
        depth = "day"
    else:
        end = date.fromisoformat(end_str)
        days = (end - start).days + 1

        if days <= 1:
            depth = "day"
        elif days <= 14:
            depth = "week"
        else:
            depth = "month"

        # Previous period = same length, immediately before
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days - 1)

    # Month start for plan-fact MTD
    month_start = date(end.year, end.month, 1).isoformat()

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "prev_start": prev_start.isoformat(),
        "prev_end": prev_end.isoformat(),
        "depth": depth,
        "period_label": _format_period_label(start, end),
        "prev_period_label": _format_period_label(prev_start, prev_end),
        "month_start": month_start,
        "days_in_period": (end - start).days + 1,
    }


def _format_period_label(start: date, end: date) -> str:
    """Format period as Russian label: '30 марта — 05 апреля 2026'."""
    if start == end:
        return f"{start.day} {MONTHS_RU_GENITIVE[start.month]} {start.year}"
    if start.month == end.month:
        return (f"{start.day}-{end.day} "
                f"{MONTHS_RU_GENITIVE[start.month]} {end.year}")
    return (f"{start.day} {MONTHS_RU_GENITIVE[start.month]} — "
            f"{end.day} {MONTHS_RU_GENITIVE[end.month]} {end.year}")


def build_quality_flags(errors: dict, ad_totals_check: dict | None = None) -> dict:
    """Build quality flags from collection errors and checks.

    Args:
        errors: dict of collector_name → error message for failed collectors.
        ad_totals_check: result of get_wb_ad_totals_check (fan-out detection).
    """
    fan_out = False
    if ad_totals_check:
        raw = ad_totals_check.get("raw_total", 0)
        model = ad_totals_check.get("model_total", 0)
        if raw > 0 and model > 0:
            fan_out = abs(model / raw - 1) > 0.05

    return {
        "traffic_gap": "~20% расхождение с PowerBI — использовать как тренд",
        "buyout_lag": "Выкуп % — лаг 3-21 дней, не использовать как причину в дневном",
        "fan_out_detected": fan_out,
        "ozon_organic_unavailable": True,
        "collection_errors": errors,
    }


def tuples_to_dicts(rows: list, columns: list) -> list:
    """Convert list of tuples (cursor.fetchall) to list of dicts."""
    return [dict(zip(columns, row)) for row in rows]


def safe_float(val) -> Optional[float]:
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/analytics_report/test_utils.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/analytics_report/__init__.py scripts/analytics_report/utils.py \
  scripts/analytics_report/collectors/__init__.py \
  tests/analytics_report/__init__.py tests/analytics_report/test_utils.py
git commit -m "feat(analytics-report): add utils scaffold with date params and quality flags"
```

---

## Task 2: Finance Collector

**Files:**
- Create: `scripts/analytics_report/collectors/finance.py`

- [ ] **Step 1: Write the finance collector**

```python
# scripts/analytics_report/collectors/finance.py
"""Finance data collector: P&L totals + by model + by article (WB+OZON)."""
from shared.data_layer.finance import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_by_model,
    get_ozon_by_model,
    get_wb_orders_by_model,
    get_ozon_orders_by_model,
    get_wb_buyouts_returns_by_model,
)
from shared.data_layer.article import get_wb_by_article, get_ozon_by_article
from scripts.analytics_report.utils import tuples_to_dicts, safe_float

# Column names matching data_layer query outputs
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


def _rows_by_period(rows, columns, period_label):
    """Filter rows by period, convert to dicts with safe_float."""
    dicts = tuples_to_dicts(rows, columns)
    return [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in d.items()}
        for d in dicts if d["period"] == period_label
    ]


def _merge_model_finance_orders(fin_rows, orders_rows, period_label):
    """Merge finance + orders by model for a given period."""
    fin = tuples_to_dicts(fin_rows, MODEL_COLS)
    ords = tuples_to_dicts(orders_rows, MODEL_ORDERS_COLS)

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
        entry = {k: safe_float(v) if k not in ("period", "model") else v for k, v in f.items()}
        entry.update(orders_map.get(f["model"], {"orders_count": 0, "orders_rub": 0}))
        result.append(entry)
    return result


def collect_finance(start: str, prev_start: str, end: str, depth: str) -> dict:
    """Collect financial data at all hierarchy levels.

    Args:
        start: current period start (YYYY-MM-DD)
        prev_start: previous period start
        end: current period end (exclusive, next day after period)
        depth: 'day', 'week', or 'month'

    Returns:
        Dict with keys: wb_total, ozon_total, wb_models, ozon_models,
        wb_articles (week/month only), ozon_articles (week/month only),
        wb_buyouts.
    """
    # Brand-level P&L
    wb_fin = get_wb_finance(start, prev_start, end)
    ozon_fin = get_ozon_finance(start, prev_start, end)

    wb_total = {
        "current": _rows_by_period(wb_fin, WB_FINANCE_COLS, "current"),
        "previous": _rows_by_period(wb_fin, WB_FINANCE_COLS, "previous"),
    }
    ozon_total = {
        "current": _rows_by_period(ozon_fin, OZON_FINANCE_COLS, "current"),
        "previous": _rows_by_period(ozon_fin, OZON_FINANCE_COLS, "previous"),
    }

    # Model-level
    wb_by_model = get_wb_by_model(start, prev_start, end)
    ozon_by_model = get_ozon_by_model(start, prev_start, end)
    wb_orders = get_wb_orders_by_model(start, prev_start, end)
    ozon_orders = get_ozon_orders_by_model(start, prev_start, end)

    wb_models = {
        "current": _merge_model_finance_orders(wb_by_model, wb_orders, "current"),
        "previous": _merge_model_finance_orders(wb_by_model, wb_orders, "previous"),
    }
    ozon_models = {
        "current": _merge_model_finance_orders(ozon_by_model, ozon_orders, "current"),
        "previous": _merge_model_finance_orders(ozon_by_model, ozon_orders, "previous"),
    }

    result = {
        "wb_total": wb_total,
        "ozon_total": ozon_total,
        "wb_models": wb_models,
        "ozon_models": ozon_models,
    }

    # Article-level (week/month only — too granular for daily)
    if depth in ("week", "month"):
        wb_articles = get_wb_by_article(start, end)
        ozon_articles = get_ozon_by_article(start, end)
        result["wb_articles"] = wb_articles
        result["ozon_articles"] = ozon_articles

    # Buyouts/returns
    wb_buyouts = get_wb_buyouts_returns_by_model(start, end)
    result["wb_buyouts"] = wb_buyouts

    return {"finance": result}
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -c "from scripts.analytics_report.collectors.finance import collect_finance; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collectors/finance.py
git commit -m "feat(analytics-report): add finance collector (WB+OZON P&L, models, articles)"
```

---

## Task 3: Advertising Collector

**Files:**
- Create: `scripts/analytics_report/collectors/advertising.py`

- [ ] **Step 1: Write the advertising collector**

```python
# scripts/analytics_report/collectors/advertising.py
"""Advertising data collector: ROI, DRR, daily series, campaigns, budget."""
from shared.data_layer.advertising import (
    get_wb_external_ad_breakdown,
    get_ozon_external_ad_breakdown,
    get_wb_model_ad_roi,
    get_ozon_model_ad_roi,
    get_wb_ad_daily_series,
    get_ozon_ad_daily_series,
    get_wb_campaign_stats,
    get_wb_ad_budget_utilization,
    get_wb_ad_totals_check,
    get_ozon_ad_by_sku,
)
from scripts.analytics_report.utils import safe_float


def collect_advertising(start: str, prev_start: str, end: str) -> dict:
    """Collect advertising data: breakdown, ROI by model, daily series, campaigns.

    Returns dict with key 'advertising' containing:
        wb_breakdown, ozon_breakdown, wb_model_roi, ozon_model_roi,
        wb_daily, ozon_daily, wb_campaigns, wb_budget, ad_totals_check.
    """
    # External ad breakdown (internal vs bloggers vs VK vs creators)
    wb_breakdown = get_wb_external_ad_breakdown(start, prev_start, end)
    ozon_breakdown = get_ozon_external_ad_breakdown(start, prev_start, end)

    # ROI by model
    wb_model_roi = get_wb_model_ad_roi(start, prev_start, end)
    ozon_model_roi = get_ozon_model_ad_roi(start, prev_start, end)

    # Daily series
    wb_daily = get_wb_ad_daily_series(start, end)
    ozon_daily = get_ozon_ad_daily_series(start, end)

    # Campaigns
    wb_campaigns = get_wb_campaign_stats(start, prev_start, end)

    # Budget utilization
    wb_budget = get_wb_ad_budget_utilization(start, end)

    # Fan-out check (quality)
    ad_totals_check = get_wb_ad_totals_check(start, end)

    # OZON by SKU
    ozon_by_sku = get_ozon_ad_by_sku(start, prev_start, end)

    return {
        "advertising": {
            "wb_breakdown": wb_breakdown,
            "ozon_breakdown": ozon_breakdown,
            "wb_model_roi": wb_model_roi,
            "ozon_model_roi": ozon_model_roi,
            "wb_daily": wb_daily,
            "ozon_daily": ozon_daily,
            "wb_campaigns": wb_campaigns,
            "wb_budget": wb_budget,
            "ad_totals_check": ad_totals_check,
            "ozon_by_sku": ozon_by_sku,
        }
    }
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -c "from scripts.analytics_report.collectors.advertising import collect_advertising; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collectors/advertising.py
git commit -m "feat(analytics-report): add advertising collector (ROI, DRR, daily, campaigns)"
```

---

## Task 4: External Marketing Collector (Google Sheets)

**Files:**
- Create: `scripts/analytics_report/collectors/external_marketing.py`

- [ ] **Step 1: Write the external marketing collector**

```python
# scripts/analytics_report/collectors/external_marketing.py
"""External marketing collector: bloggers, VK, Yandex, SMM from Google Sheets."""
from __future__ import annotations

import json as json_mod
import subprocess
from datetime import date

# Sheet IDs (stable, from spec)
BLOGGERS_SHEET_ID = "1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk"
EXTERNAL_TRAFFIC_SHEET_ID = "1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU"
SMM_SHEET_ID = "19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU"

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


def _gws_read(sheet_id: str, range_str: str) -> list:
    """Read Google Sheet range via gws CLI. Returns list of rows."""
    try:
        result = subprocess.run(
            ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json_mod.loads(result.stdout)
            return data.get("values", [])
    except (subprocess.TimeoutExpired, json_mod.JSONDecodeError, FileNotFoundError):
        pass
    return []


def _safe_float(val) -> float:
    """Parse Russian-formatted numbers: '1 234,56 ₽' -> 1234.56."""
    if not val:
        return 0.0
    try:
        cleaned = (str(val)
                   .replace(",", ".")
                   .replace(" ", "")
                   .replace("\xa0", "")
                   .replace("₽", "")
                   .replace("р.", "")
                   .replace("%", "")
                   .strip())
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def collect_external_marketing(start: str, end: str) -> dict:
    """Collect external marketing data from Google Sheets.

    Args:
        start: period start "YYYY-MM-DD"
        end: period end "YYYY-MM-DD"

    Returns:
        Dict with key 'external_marketing' containing: bloggers, vk_yandex, smm.
    """
    end_date = date.fromisoformat(end)
    month_name = MONTHS_RU.get(end_date.month, "")

    # 1. Bloggers + seeds
    bloggers = _gws_read(BLOGGERS_SHEET_ID, "блогеры!A1:Z100")
    seeds = _gws_read(BLOGGERS_SHEET_ID, f"'посевы'!A1:Z100")

    # 2. External traffic (VK, Yandex)
    vk_yandex = _gws_read(EXTERNAL_TRAFFIC_SHEET_ID, "A1:Z100")

    # 3. SMM
    smm_monthly = _gws_read(SMM_SHEET_ID, "'Отчёт месяц'!A1:Z50")
    smm_weekly = _gws_read(SMM_SHEET_ID, "'Понедельный отчёт'!A1:Z100")

    return {
        "external_marketing": {
            "bloggers": bloggers,
            "seeds": seeds,
            "vk_yandex": vk_yandex,
            "smm_monthly": smm_monthly,
            "smm_weekly": smm_weekly,
            "period_month": month_name,
        }
    }
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -c "from scripts.analytics_report.collectors.external_marketing import collect_external_marketing; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collectors/external_marketing.py
git commit -m "feat(analytics-report): add external marketing collector (bloggers, VK, SMM)"
```

---

## Task 5: Traffic Collector

**Files:**
- Create: `scripts/analytics_report/collectors/traffic.py`

- [ ] **Step 1: Write the traffic collector**

```python
# scripts/analytics_report/collectors/traffic.py
"""Traffic and funnel data collector: organic vs paid, by model, by status."""
from shared.data_layer.traffic import (
    get_wb_traffic,
    get_wb_traffic_by_model,
    get_ozon_traffic,
)
from shared.data_layer.advertising import (
    get_wb_organic_vs_paid_funnel,
    get_wb_organic_by_status,
    get_ozon_organic_estimated,
)


def collect_traffic(start: str, prev_start: str, end: str) -> dict:
    """Collect traffic and funnel data for WB and OZON.

    Returns dict with key 'traffic' containing:
        wb_funnel, wb_by_model, ozon_funnel,
        wb_organic_vs_paid, wb_organic_by_status, ozon_organic_estimated.
    """
    # WB full funnel (impressions → card → cart → order → buyout)
    wb_funnel = get_wb_traffic(start, prev_start, end)

    # WB by model
    wb_by_model = get_wb_traffic_by_model(start, prev_start, end)

    # OZON funnel
    ozon_funnel = get_ozon_traffic(start, prev_start, end)

    # Organic vs Paid breakdown
    wb_organic_vs_paid = get_wb_organic_vs_paid_funnel(start, prev_start, end)

    # Organic by model status (Продается/Выводим/Архив)
    wb_organic_by_status = get_wb_organic_by_status(start, prev_start, end)

    # OZON organic estimated
    ozon_organic_est = get_ozon_organic_estimated(start, prev_start, end)

    return {
        "traffic": {
            "wb_funnel": wb_funnel,
            "wb_by_model": wb_by_model,
            "ozon_funnel": ozon_funnel,
            "wb_organic_vs_paid": wb_organic_vs_paid,
            "wb_organic_by_status": wb_organic_by_status,
            "ozon_organic_estimated": ozon_organic_est,
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/analytics_report/collectors/traffic.py
git commit -m "feat(analytics-report): add traffic collector (funnels, organic vs paid)"
```

---

## Task 6: Inventory Collector

**Files:**
- Create: `scripts/analytics_report/collectors/inventory.py`

- [ ] **Step 1: Write the inventory collector**

```python
# scripts/analytics_report/collectors/inventory.py
"""Inventory data collector: stocks (WB/OZON/MoySklad), turnover, risk assessment."""
from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_model,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
    get_wb_sales_trend_by_model,
    get_ozon_sales_trend_by_model,
)
from scripts.analytics_report.utils import model_from_article

# Risk thresholds (days of stock)
DEFICIT_DAYS = 14
OK_MAX_DAYS = 60
WARNING_MAX_DAYS = 90
OVERSTOCK_MAX_DAYS = 250


def _assess_risk(turnover_days: float) -> str:
    """Assess inventory risk based on days of stock."""
    if turnover_days < DEFICIT_DAYS:
        return "DEFICIT"
    elif turnover_days <= OK_MAX_DAYS:
        return "OK"
    elif turnover_days <= WARNING_MAX_DAYS:
        return "WARNING"
    elif turnover_days <= OVERSTOCK_MAX_DAYS:
        return "OVERSTOCK"
    else:
        return "DEAD_STOCK"


def collect_inventory(start: str, end: str) -> dict:
    """Collect inventory data: stocks, turnover, risk assessment, sales trends.

    Returns dict with key 'inventory' containing:
        wb_stocks_by_model, ozon_stocks_by_model, moysklad_stocks,
        wb_turnover, ozon_turnover, wb_sales_trend, ozon_sales_trend.
    """
    # Raw stocks (article-level → aggregate to model)
    wb_raw = get_wb_avg_stock(start, end)
    ozon_raw = get_ozon_avg_stock(start, end)

    # Aggregate WB stocks by model
    wb_stocks_by_model = {}
    for article, stock_val in wb_raw.items():
        model = model_from_article(article)
        if model:
            wb_stocks_by_model[model] = wb_stocks_by_model.get(model, 0) + (stock_val or 0)

    # Aggregate OZON stocks by model
    ozon_stocks_by_model = {}
    for article, stock_val in ozon_raw.items():
        model = model_from_article(article)
        if model:
            ozon_stocks_by_model[model] = ozon_stocks_by_model.get(model, 0) + (stock_val or 0)

    # MoySklad (already model-level)
    moysklad = get_moysklad_stock_by_model()

    # Turnover (days of stock)
    wb_turnover = get_wb_turnover_by_model(start, end)
    ozon_turnover = get_ozon_turnover_by_model(start, end)

    # Add risk assessment to turnover data
    if isinstance(wb_turnover, list):
        for item in wb_turnover:
            days = item.get("turnover_days", 999)
            item["risk"] = _assess_risk(days)
    if isinstance(ozon_turnover, list):
        for item in ozon_turnover:
            days = item.get("turnover_days", 999)
            item["risk"] = _assess_risk(days)

    # Sales trends
    wb_trend = get_wb_sales_trend_by_model(start, end)
    ozon_trend = get_ozon_sales_trend_by_model(start, end)

    return {
        "inventory": {
            "wb_stocks_by_model": wb_stocks_by_model,
            "ozon_stocks_by_model": ozon_stocks_by_model,
            "moysklad_stocks": moysklad,
            "wb_turnover": wb_turnover,
            "ozon_turnover": ozon_turnover,
            "wb_sales_trend": wb_trend,
            "ozon_sales_trend": ozon_trend,
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/analytics_report/collectors/inventory.py
git commit -m "feat(analytics-report): add inventory collector (stocks, turnover, risk)"
```

---

## Task 7: Pricing Collector

**Files:**
- Create: `scripts/analytics_report/collectors/pricing.py`

- [ ] **Step 1: Write the pricing collector**

```python
# scripts/analytics_report/collectors/pricing.py
"""Pricing data collector: prices, SPP, changes, period aggregates."""
from shared.data_layer.pricing import (
    get_wb_price_changes,
    get_ozon_price_changes,
    get_wb_spp_history_by_model,
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
)


def collect_pricing(start: str, prev_start: str, end: str) -> dict:
    """Collect pricing data: changes, SPP dynamics, period aggregates.

    Returns dict with key 'pricing' containing:
        wb_price_changes, ozon_price_changes, wb_spp_history,
        wb_price_margin, ozon_price_margin.
    """
    # Significant price changes (>3%)
    wb_changes = get_wb_price_changes(start, end)
    ozon_changes = get_ozon_price_changes(start, end)

    # SPP history by model (WB only)
    wb_spp = get_wb_spp_history_by_model(start, end)

    # Period aggregates (price + margin by model)
    wb_price_margin = get_wb_price_margin_by_model_period(start, end)
    ozon_price_margin = get_ozon_price_margin_by_model_period(start, end)

    return {
        "pricing": {
            "wb_price_changes": wb_changes,
            "ozon_price_changes": ozon_changes,
            "wb_spp_history": wb_spp,
            "wb_price_margin": wb_price_margin,
            "ozon_price_margin": ozon_price_margin,
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/analytics_report/collectors/pricing.py
git commit -m "feat(analytics-report): add pricing collector (prices, SPP, changes)"
```

---

## Task 8: Plan-Fact Collector

**Files:**
- Create: `scripts/analytics_report/collectors/plan_fact.py`

- [ ] **Step 1: Write the plan-fact collector**

```python
# scripts/analytics_report/collectors/plan_fact.py
"""Plan-fact collector: Google Sheets plan + data_layer fact."""
from __future__ import annotations

import json as json_mod
import subprocess
from datetime import date
from calendar import monthrange

# Plan sheet
PLAN_SHEET_ID = "1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk"
PLAN_GID = "1957404595"


def _gws_read(sheet_id: str, range_str: str) -> list:
    """Read Google Sheet range via gws CLI."""
    try:
        result = subprocess.run(
            ["gws", "sheets", "+read", "--spreadsheet", sheet_id, "--range", range_str],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json_mod.loads(result.stdout)
            return data.get("values", [])
    except (subprocess.TimeoutExpired, json_mod.JSONDecodeError, FileNotFoundError):
        pass
    return []


def collect_plan_fact(start: str, end: str, month_start: str) -> dict:
    """Collect plan-fact data: plan from Sheets, compute MTD metrics.

    Args:
        start: period start
        end: period end
        month_start: first day of the month (for MTD calculation)

    Returns:
        Dict with key 'plan_fact' containing: plan_raw, mtd_info.
    """
    end_date = date.fromisoformat(end)

    # Read plan from Google Sheets
    plan_wb = _gws_read(PLAN_SHEET_ID, "WB!A1:Z50")
    plan_ozon = _gws_read(PLAN_SHEET_ID, "OZON!A1:Z50")

    # MTD calculation info
    month_start_date = date.fromisoformat(month_start)
    _, days_in_month = monthrange(end_date.year, end_date.month)
    days_elapsed = (end_date - month_start_date).days + 1
    mtd_ratio = days_elapsed / days_in_month

    return {
        "plan_fact": {
            "plan_wb": plan_wb,
            "plan_ozon": plan_ozon,
            "mtd_info": {
                "month_start": month_start,
                "days_in_month": days_in_month,
                "days_elapsed": days_elapsed,
                "mtd_ratio": round(mtd_ratio, 4),
            },
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/analytics_report/collectors/plan_fact.py
git commit -m "feat(analytics-report): add plan-fact collector (Sheets plan + MTD calc)"
```

---

## Task 9: SKU Statuses Collector

**Files:**
- Create: `scripts/analytics_report/collectors/sku_statuses.py`

- [ ] **Step 1: Write the SKU statuses collector**

```python
# scripts/analytics_report/collectors/sku_statuses.py
"""SKU statuses collector: model statuses and article mappings from Supabase."""
from shared.data_layer.sku_mapping import (
    get_model_statuses_mapped,
    get_artikuly_statuses,
)


def collect_sku_statuses() -> dict:
    """Collect SKU statuses and mappings.

    Returns dict with key 'sku_statuses' containing:
        model_statuses (model → status), artikuly_statuses.
    """
    model_statuses = get_model_statuses_mapped()
    artikuly = get_artikuly_statuses()

    return {
        "sku_statuses": {
            "model_statuses": model_statuses,
            "artikuly_statuses": artikuly,
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add scripts/analytics_report/collectors/sku_statuses.py
git commit -m "feat(analytics-report): add SKU statuses collector (model statuses, mappings)"
```

---

## Task 10: collect_all.py Orchestrator

**Files:**
- Create: `scripts/analytics_report/collect_all.py`

- [ ] **Step 1: Write the orchestrator**

```python
# scripts/analytics_report/collect_all.py
"""Analytics report data collection orchestrator.

Usage:
    python scripts/analytics_report/collect_all.py --start 2026-04-05
    python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05
    python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05 --output /tmp/data.json
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from scripts.analytics_report.utils import compute_date_params, build_quality_flags
from scripts.analytics_report.collectors.finance import collect_finance
from scripts.analytics_report.collectors.advertising import collect_advertising
from scripts.analytics_report.collectors.external_marketing import collect_external_marketing
from scripts.analytics_report.collectors.traffic import collect_traffic
from scripts.analytics_report.collectors.inventory import collect_inventory
from scripts.analytics_report.collectors.pricing import collect_pricing
from scripts.analytics_report.collectors.plan_fact import collect_plan_fact
from scripts.analytics_report.collectors.sku_statuses import collect_sku_statuses


def run_collection(start: str, end: str | None = None) -> dict:
    """Run all collectors in parallel and merge results.

    Args:
        start: Start date "YYYY-MM-DD"
        end: End date "YYYY-MM-DD" or None for daily

    Returns:
        Complete data bundle as JSON-serializable dict.
    """
    t0 = time.time()
    params = compute_date_params(start, end)

    cs = params["start_date"]
    ce = params["end_date"]
    ps = params["prev_start"]
    depth = params["depth"]
    ms = params["month_start"]

    # Need end+1 day for exclusive date ranges in data_layer
    ce_exclusive = (date.fromisoformat(ce) + timedelta(days=1)).isoformat()
    ps_for_query = ps  # prev_start is used as-is

    tasks = {
        "finance": lambda: collect_finance(cs, ps_for_query, ce_exclusive, depth),
        "advertising": lambda: collect_advertising(cs, ps_for_query, ce_exclusive),
        "external_marketing": lambda: collect_external_marketing(cs, ce),
        "traffic": lambda: collect_traffic(cs, ps_for_query, ce_exclusive),
        "inventory": lambda: collect_inventory(cs, ce_exclusive),
        "pricing": lambda: collect_pricing(cs, ps_for_query, ce_exclusive),
        "plan_fact": lambda: collect_plan_fact(cs, ce, ms),
        "sku_statuses": lambda: collect_sku_statuses(),
    }

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"
                results[name] = {}

    # Merge all results into flat structure
    merged = {}
    for block_result in results.values():
        merged.update(block_result)

    # Build quality flags
    ad_totals = merged.get("advertising", {}).get("ad_totals_check")
    quality_flags = build_quality_flags(errors, ad_totals)

    duration = round(time.time() - t0, 1)

    return {
        "meta": {
            "start_date": cs,
            "end_date": ce,
            "prev_start": ps,
            "prev_end": params["prev_end"],
            "depth": depth,
            "period_label": params["period_label"],
            "prev_period_label": params["prev_period_label"],
            "month_start": ms,
            "days_in_period": params["days_in_period"],
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_sec": duration,
            "errors": errors,
        },
        **merged,
        "quality_flags": quality_flags,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect analytics report data")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (omit for daily)")
    parser.add_argument("--output", default=None, help="Output JSON path (default: stdout)")

    args = parser.parse_args()
    bundle = run_collection(args.start, args.end)

    output = json.dumps(bundle, ensure_ascii=False, default=str, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Saved to {args.output} ({len(output)} bytes, {bundle['meta']['duration_sec']}s)",
              file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -c "from scripts.analytics_report.collect_all import run_collection; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collect_all.py
git commit -m "feat(analytics-report): add collect_all.py orchestrator (8 parallel collectors)"
```

---

## Task 11: Reference Documents

**Files:**
- Create: `.claude/skills/analytics-report/references/data-sources.md`
- Create: `.claude/skills/analytics-report/references/analytics-rules.md`

- [ ] **Step 1: Write data sources reference**

```markdown
# Справочник источников данных

## Базы данных (read-only)

### WB (`pbi_wb_wookiee`)

| Таблица | Строк | Основные метрики |
|---|---|---|
| `abc_date` | 853K, 94 поля | Финансовая воронка: revenue, margin, logistics, commission, ads |
| `orders` | 285K | Заказы: дата, артикул, количество, сумма |
| `sales` | 250K | Продажи (выкупы): дата, артикул, количество, сумма |
| `stocks` | 1.3M | Снапшоты остатков FBO: дата, артикул, количество |
| `content_analysis` | 61K | Воронка: показы → карточка → корзина → заказ |
| `wb_adv` | 308K | Рекламная статистика: показы, клики, расход, заказы |
| `adv_budget` | 7K | Бюджеты рекламных кампаний |
| `ms_stocks` | 177K | Снапшоты МойСклад |
| `paid_storage` | 6.3M | Платное хранение WB |
| `stat_words` | 11.6M | Ключевые слова и позиции |

### OZON (`pbi_ozon_wookiee`)

| Таблица | Строк | Основные метрики |
|---|---|---|
| `abc_date` | 156K, 72 поля | Финансовая воронка OZON |
| `adv_stats_daily` | 1.3K | Реклама по дням |
| `ozon_adv_api` | 3.8K | Реклама по SKU |
| `ozon_services` | 375K | 34 типа комиссий OZON |

### Supabase
- SKU-матрица: статусы моделей, привязки артикулов
- Таблицы: `artikuly`, `models`

## Google Sheets

| Назначение | Sheet ID | Листы |
|---|---|---|
| План поартикульно WB+OZON | `1Dsz7s_mZ0wUhviGFho89lyhtjce1V0Cmv_RPL1aLxnk` | WB, OZON |
| Блогеры + посевы | `1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk` | блогеры, посевы |
| Внешний трафик (ВК, Яндекс) | `1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU` | gid=1032273459 |
| SMM бренда | `19NXHQGWSFjeWiPE12R3YAy5u2IsLpTISrECpysPSdPU` | Отчёт месяц, Понедельный отчёт |

## Data Layer функции (shared/data_layer)

### finance.py
- `get_wb_finance(cs, ps, ce)` — WB P&L итого (current+previous)
- `get_ozon_finance(cs, ps, ce)` — OZON P&L итого
- `get_wb_by_model(cs, ps, ce)` — WB по моделям
- `get_ozon_by_model(cs, ps, ce)` — OZON по моделям
- `get_wb_orders_by_model(cs, ps, ce)` — Заказы WB
- `get_ozon_orders_by_model(cs, ps, ce)` — Заказы OZON
- `get_wb_buyouts_returns_by_model(cs, ce)` — Выкупы/возвраты

### advertising.py
- `get_wb_external_ad_breakdown` — Разбивка внутр/внешн
- `get_ozon_external_ad_breakdown` — То же для OZON
- `get_wb_organic_vs_paid_funnel` — Органик vs платный
- `get_wb_model_ad_roi` — ROMI по моделям
- `get_ozon_model_ad_roi` — ROMI OZON
- `get_wb_ad_daily_series` — Дневная динамика
- `get_ozon_ad_daily_series` — Дневная OZON
- `get_wb_campaign_stats` — По кампаниям
- `get_wb_ad_budget_utilization` — Бюджет vs факт
- `get_wb_ad_totals_check` — QA: fan-out detection
- `get_wb_organic_by_status` — Органика по статусам
- `get_ozon_organic_estimated` — OZON органика (оценка)

### inventory.py
- `get_wb_avg_stock` — Остатки WB FBO
- `get_ozon_avg_stock` — Остатки OZON FBO
- `get_moysklad_stock_by_model` — МойСклад
- `get_wb_turnover_by_model` — Оборачиваемость WB
- `get_ozon_turnover_by_model` — Оборачиваемость OZON
- `get_wb_sales_trend_by_model` — Тренд продаж WB
- `get_ozon_sales_trend_by_model` — Тренд OZON

### pricing.py
- `get_wb_price_changes` — Значимые изменения цен (>3%)
- `get_ozon_price_changes` — То же OZON
- `get_wb_spp_history_by_model` — Динамика СПП
- `get_wb_price_margin_by_model_period` — Агрегат цены+маржа
- `get_ozon_price_margin_by_model_period` — То же OZON

### traffic.py
- `get_wb_traffic` — WB воронка
- `get_wb_traffic_by_model` — WB трафик по моделям
- `get_ozon_traffic` — OZON трафик
```

- [ ] **Step 2: Write analytics rules reference**

```markdown
# Правила аналитики — Knowledge Base

## Жёсткие правила (НАРУШЕНИЕ = ОШИБКА)

1. **GROUP BY модели** = `LOWER(SPLIT_PART(article, '/', 1))` — ВСЕГДА
2. **Процентные метрики** при объединении каналов = ТОЛЬКО средневзвешенные: `sum(X) / sum(Y) × 100`
3. **ДРР** = ВСЕГДА с разбивкой: внутренняя (МП) + внешняя (блогеры, ВК) ОТДЕЛЬНО
4. **Единая маржа** = включает ВСЮ рекламу (internal + external). Никаких M-1/M-2
5. **WB маржа** = `SUM(marga) - SUM(nds) - SUM(reclama_vn) - COALESCE(SUM(reclama_vn_vk), 0) - COALESCE(SUM(reclama_vn_creators), 0)`
6. **OZON маржа** = `SUM(marga) - SUM(nds)`
7. **Органик + Paid** = НЕ суммировать (несравнимые метрики)
8. **Числа** — ТОЛЬКО из данных, никогда не придумывать
9. **Факт vs Гипотеза** — ВСЕГДА разделять
10. **Рекомендации** = только через ЦЕНУ или МАРКЕТИНГ (единственные инструменты)
11. **Формат чисел** — `1 234 567 ₽`, проценты `24.1%`, доли `8.0% → 11.2% (+3.2 п.п.)`
12. **Даты в тексте** — "17 марта 2026". В таблицах "17.03.2026". ЗАПРЕЩЁН YYYY-MM-DD

## Лаговые/неуправляемые показатели

| Показатель | Ограничение | В дневном | В недельном | В месячном |
|---|---|---|---|---|
| Выкуп % | Лаг 3-21 дней | ЗАПРЕЩЁН как причина | С оговоркой | Полностью надёжен |
| СПП | НЕ управляемый | Информационно | Информационно | Информационно |
| Комиссия | НЕ управляемая | Фиксируем | Фиксируем | Фиксируем |

## Бенчмарки рекламы

| Метрика | Отлично | Норма | Плохо |
|---|---|---|---|
| CTR % | > 5% | 2-3% | < 1% |
| CPC ₽ | < 5₽ | 5-10₽ | > 15₽ |
| CPM ₽ | < 100₽ | 100-300₽ | > 500₽ |
| CR % | > 5% | 2-5% | < 1% |

## Двойной KPI рекламы

1. **ДРР продаж** = ad / sales_revenue × 100 — текущая маржа
2. **ДРР заказов (CPO)** = ad / orders_revenue × 100 — будущая эффективность

| ДРР продаж | ДРР заказов | Интерпретация | Действие |
|---|---|---|---|
| Высокий | Нормальный | Инвестиция | НЕ отключать |
| Нормальный | Высокий | Неэффективна | Снижать |
| Высокий | Высокий | Критично | СТОП + диагностика |

## Матрица эффективности рекламы

| Категория | ROMI | Действие |
|---|---|---|
| Growth | > 1000% | Масштабировать |
| Harvest | 60-300% | Поддерживать |
| Optimize | < 100% | Оптимизировать |
| Cut | Отрицательный | Отключить |

## Пороги риска остатков

| Статус | Оборачиваемость | Действие |
|---|---|---|
| ДЕФИЦИТ | < 14 дней | Пополнить WB FBO |
| OK | 14-60 дней | Без действий |
| ВНИМАНИЕ | 60-90 дней | Мониторинг |
| OVERSTOCK | 90-250 дней | Снизить цену / FREEZE |
| МЁРТВЫЙ СТОК | > 250 дней | Маркдаун / ликвидация |

## Ценовая логика

1. Overstock + маржа > 15% → снизить цену (ускорить продажи)
2. Дефицит + маржа ок → повысить цену (спрос > предложение)
3. Маржа < 15% → НЕ снижать (даже при слабых продажах)
4. Мёртвый сток > 250д → маркдаун / ликвидация
5. Мало данных → держать, наблюдать

## Confidence discipline

| Уровень | Условие | Допустимые действия |
|---|---|---|
| HIGH | \|r\| > 0.5, > 30 дней данных | CUT допустим |
| MEDIUM | 15-30 дней | Только HOLD или тест 1 SKU на 2 недели |
| LOW | < 15 дней | Всегда HOLD |

## Годовой ROI

| Категория | ROI | Интерпретация |
|---|---|---|
| roi_leader | > 500% | Отлично |
| healthy | 200-500% | Норма |
| underperformer | 50-200% | Проблема |
| deadstock_risk | < 50% | Критично |

Формула: `margin% × (365 / turnover_days)`

## Системность внешних каналов

| Канал | Системность | Лаг ROI | Дневной анализ |
|---|---|---|---|
| Блогеры | Случайный (спайки) | 3-7 дней | ЗАПРЕЩЁН |
| ВК/Яндекс | Системный (ежедневный) | 1-3 дня | РАЗРЕШЁН |
| Паблики | Системный | 2-5 дней | Ограничен |

## Запрещённые формулировки (внешняя реклама)

- ❌ "Внешняя реклама прекратилась" → ✅ "Сегодня без внешней рекламы"
- ❌ "Экономия на внешней рекламе +X" → нельзя считать отсутствие несистемного расхода экономией
- ❌ "ДРР внешний 45%" в день размещения блогера → ✅ "Размещение X₽. ДРР считать рано"

## Аналитические принципы

- **Системное мышление:** каскадные эффекты (цена↓ → конверсия↑ → заказы↑ → риск OOS)
- **Evidence-based:** гипотеза начинается с факт-триггера из текущих данных
- **Эффект в деньгах:** "Ожидаемый эффект" = влияние на маржу в ₽ по конкретной модели
- **Последствия 2-го порядка:** заполнять "Риски" у каждого действия
- **Приоритизация по ₽:** рекомендации отсортированы по рублёвому эффекту
- **Тон:** сухой финансовый директор. Без оценочных суждений. Факты + ₽ эффект.

## Data Quality

- retention == deduction на одних датах = дубликат, нужна коррекция маржи
- Fan-out JOIN nomenclature = рекламный расход ×4, использовать SELECT DISTINCT nmid
- Трафик: ~20% gap с PowerBI — использовать как ТРЕНД
- OZON search_stat organic_data = 0 — органика OZON недоступна

## Диагностика аномалий воронки

| Симптом | Проверить |
|---|---|
| CR карточка→корзина < 5% | Контент/фото, цена, конкуренты |
| CR корзина→заказ < 15% | Ценовая конкурентоспособность |
| Переходы ↓ >20% | Позиции, рекламный бюджет, сезонность |
| ДРР ↑ >3пп | Стоимость клика, конверсия рекламы |
| Органика ↓ >10пп | Позиции, новые конкуренты |
| Выкупы ↓ (заказы стабильны) | Качество товара, размеры |
```

- [ ] **Step 3: Create directories and commit**

```bash
mkdir -p .claude/skills/analytics-report/references
git add .claude/skills/analytics-report/references/data-sources.md \
  .claude/skills/analytics-report/references/analytics-rules.md
git commit -m "docs(analytics-report): add data sources and analytics rules reference"
```

---

## Task 12: Templates

**Files:**
- Create: `.claude/skills/analytics-report/templates/report-structure.md`
- Create: `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

- [ ] **Step 1: Write report structure template**

```markdown
# Структура аналитического отчёта

Используй этот скелет как обязательную структуру. Каждая секция — toggle в Notion.

---

## Секция 0: Executive Summary

> Синтез ВСЕХ findings. 10-15 строк.

**Обязательные пункты:**
- Маржинальность: текущая ₽, Δ vs пред. период, тренд
- Скорость развития: заказы Δ%, выручка Δ%, доли каналов WB/OZON
- План-факт: статус ключевых KPI (заказы, выручка, маржа)
- Здоровье бренда: средняя оборачиваемость, ценовая позиция, остатки
- ТОП-3 риска с ₽ эффектом
- ТОП-3 возможности с ₽ эффектом

Формат: callout-блок, сухой тон.

## Секция 1: Топ-выводы и действия

3-5 ключевых находок. Формат каждой:

> **[±X XXX ₽]** Что произошло → Гипотеза почему → Действие

Отсортировано по |₽ эффект| (максимальный первый).

## Секция 2: План-факт

Таблица:

| Метрика | План (месяц) | Факт MTD | План MTD | Выполнение MTD % | Прогноз (месяц) | Статус |
|---|---|---|---|---|---|---|

Метрики: Заказы шт, Заказы ₽, Продажи шт, Продажи ₽, Выручка, Маржа, Реклама внутр, Реклама внешн.

Статусы: ✅ >105% | ⚠️ 95-105% | ❌ <95%

## Секция 3: Ключевые изменения (Бренд)

ПОЛНАЯ таблица (15 строк, БЕЗ СОКРАЩЕНИЙ):

| Показатель | Текущий | Прошлый | Δ | Δ% |
|---|---|---|---|---|

Строки: Маржинальная прибыль, Маржинальность %, Продажи шт, Продажи руб, Заказы руб, Заказы шт, Реклама внутр, Реклама внешн, ДРР от заказов, ДРР от продаж, Средний чек заказов, Средний чек продаж, Оборачиваемость дн, Годовой ROI %, СПП %

## Секция 4: Цены, СПП, ценовые гипотезы

- Динамика СПП по каналам (таблица)
- Средние цены по моделям + Δ
- Ценовые рекомендации: Модель | Текущая цена | Предлагаемая | Δ маржи ₽ | Confidence | Окно

## Секция 5: Сведение ΔМаржи (Reconciliation)

| Статья | Текущий,К | Прошлый,К | Δ,К | Влияние на маржу,К |
|---|---|---|---|---|

Строки: Выручка, Себестоимость/ед, Комиссия до СПП, Логистика/ед, Хранение/ед, Реклама внутр, Реклама внешн, НДС, Прочие, **Невязка**

## Секция 6: По маркетплейсам

### 6.1 Wildberries

#### 6.1.1 Объём и прибыльность WB
Таблица: основные метрики WB (заказы, выручка, маржа, маржинальность)

#### 6.1.2 Модельная декомпозиция WB
ВСЕ модели. Таблица:

| Модель | Статус | Маржа,К | Маржа% | Остаток FBO | МойСклад | Оборач.дн | ROI% | ДРР% | Комментарий |

#### 6.1.2.1 Анализ по статусам WB
Группировка: Продается / Выводим / Архив / Новинки

#### 6.1.3 Воронка продаж WB
ASCII-визуализация + таблица объёма + таблица эффективности

#### 6.1.4 Структура затрат WB
Все статьи: доля от выручки + Δ в п.п.

#### 6.1.5 Реклама WB
Внутр/внешн, ДРР, кампании

### 6.2 OZON
(Аналогичная структура)

## Секция 7: Маркетинг

- Исполнительная сводка маркетинга
- Органика vs Платное (WB): доли, динамика, конверсии
- Внешняя реклама: блогеры, ВК, Яндекс, SMM
- Матрица эффективности: Growth / Harvest / Optimize / Cut
- Чёрные дыры (ROMI < 100%)
- Дневная динамика рекламы

## Секция 8: Оборачиваемость и остатки

| Модель | WB FBO | OZON FBO | МойСклад | Итого шт | Оборач.дн | Риск | Действие |
|---|---|---|---|---|---|---|---|

## Секция 9: Модели — драйверы/антидрайверы

**Драйверы** (модели с наибольшим вкладом в рост маржи):
| Модель | Доля продаж | ΔМаржа,К | Маржа% | Остаток | Оборач | ДРР | Комментарий |

**Антидрайверы** (аналогично)

## Секция 10: Гипотезы → Действия → Метрики контроля

| # | Приоритет | Объект | Гипотеза | Действие | Метрика контроля | Эффект,К | Окно | Риски |

День: 3-5 штук. Неделя: 5-10 штук. Месяц: 10-15 штук.
Отсортировано по |₽ эффект|.

## Секция 11: Рекомендации Advisor

🔴 **Критичные:** (действие требуется немедленно)
- Сигнал → Действие. Эффект: X. Confidence: Y.

🟡 **Внимание:** (мониторинг или плановое действие)

🟢 **Позитивные сигналы:** (что работает хорошо)

## Секция 12: Итог

10-20 строк:
1. Что изменилось (ключевые цифры)
2. Почему (основные драйверы)
3. Что двигало больше всего (модели, каналы)
4. Что делать первым (1-3 действия с приоритетом)
```

- [ ] **Step 2: Write Notion formatting guide**

```markdown
# Notion Formatting Guide for Analytics Reports

## Table Format

```html
<table fit-page-width="true" header-row="true" header-column="true">
<tr color="blue_bg">
<td>Показатель</td>
<td>Текущий</td>
<td>Прошлый</td>
<td>Δ</td>
</tr>
<tr>
<td>Выручка, тыс.₽</td>
<td>36 482</td>
<td>31 200</td>
<td color="green_bg">+5 282 (+16.9%)</td>
</tr>
<tr color="gray_bg">
<td>**ИТОГО**</td>
<td>**43 077**</td>
<td>**37 500**</td>
<td color="green_bg">**+5 577 (+14.9%)**</td>
</tr>
</table>
```

## Row Colors

| Color | Usage |
|---|---|
| `blue_bg` | Header rows |
| `gray_bg` | Total/summary rows |
| `green_bg` | Positive highlight rows |
| `red_bg` | Negative/warning rows |
| `yellow_bg` | Caution / lagged metrics |

## Cell Colors

| Color | Usage |
|---|---|
| `green_bg` | Positive values (growth, OK status, ROMI >300%) |
| `red_bg` | Negative values (losses, DEFICIT, DEAD_STOCK) |
| `yellow_bg` | Warning (OVERSTOCK, FREEZE, lagged) |

## Callout Blocks

```html
<callout icon="📊" color="blue_bg">
Executive Summary — ключевые цифры периода.
</callout>

<callout icon="⚠️" color="yellow_bg">
Выкуп % — лаговый показатель (3-21 дней). Не использовать как причину изменений.
</callout>

<callout icon="🔴" color="red_bg">
КРИТИЧНО: Модель X — маржинальность ниже 10%, рекомендуется немедленное действие.
</callout>
```

## Toggle Headings

ВСЕ заголовки должны быть toggle (сворачиваемые):

```html
<toggle>
<heading level="2">6.1 Wildberries</heading>

Content inside the toggle...

</toggle>
```

## Number Formatting

| Тип | Формат | Пример |
|---|---|---|
| Деньги (>1000) | Пробелы + ₽ | `1 234 567 ₽` |
| Деньги (тысячи) | тыс.₽ | `1 234 тыс.₽` |
| Проценты | 1 десятичный | `24.1%` |
| Доли (с изменением) | п.п. | `8.0% → 11.2% (+3.2 п.п.)` |
| Штуки | Пробелы | `1 234 шт` |
| Дни | Целое | `45 дн` |

## Date Formatting

| Контекст | Формат | Пример |
|---|---|---|
| В тексте | Русский полный | 17 марта 2026 |
| В таблицах | DD.MM.YYYY | 17.03.2026 |
| ЗАПРЕЩЁН | ISO | ~~2026-03-17~~ |

## Headers

- Русский язык
- Без аббревиатур (кроме WB, OZON, ДРР, СПП, ROI)
- Модели — с заглавной буквы (Wendy, Audrey, Ruby)
```

- [ ] **Step 3: Create directories and commit**

```bash
mkdir -p .claude/skills/analytics-report/templates
git add .claude/skills/analytics-report/templates/report-structure.md \
  .claude/skills/analytics-report/templates/notion-formatting-guide.md
git commit -m "docs(analytics-report): add report structure template and Notion formatting guide"
```

---

## Task 13: Analyst Prompt — Financial (Subagent 1)

**Files:**
- Create: `.claude/skills/analytics-report/prompts/analysts/financial.md`

- [ ] **Step 1: Write the financial analyst prompt**

```markdown
# Финансовый аналитик

Ты финансовый аналитик бренда Wookiee (WB + OZON, ~35-40М₽/мес). Твоя задача — полная финансовая воронка на всех уровнях иерархии.

## Входные данные

**Твой data slice:**
{{DATA_SLICE}}

**Краткий summary других блоков (для cross-reference):**
{{SUMMARY}}

**Глубина:** {{DEPTH}} (day/week/month)
**Период:** {{PERIOD_LABEL}}
**Пред. период:** {{PREV_PERIOD_LABEL}}
**Quality flags:** {{QUALITY_FLAGS}}

## Иерархия анализа

Ты ОБЯЗАН предоставить данные на ВСЕХ уровнях:

1. **Бренд** (WB + OZON суммарно)
2. **Канал** (WB отдельно, OZON отдельно)
3. **Модель** (ВСЕ модели, группировка LOWER())
4. **Статус** (Продается / Выводим / Архив / Новинки)
5. **Артикул** (если depth = week/month: топ/анти-топ по маржинальности)

## Задачи

### A. Финансовая воронка (Бренд + по каналам)

Таблица 15 строк (ПОЛНАЯ, без сокращений):

| Показатель | WB текущий | WB прошлый | Δ WB | OZON текущий | OZON прошлый | Δ OZON | Бренд текущий | Бренд прошлый | Δ Бренд |
|---|---|---|---|---|---|---|---|---|---|

Строки:
1. Выручка до СПП
2. СПП (сумма)
3. Выручка после СПП
4. Себестоимость
5. Комиссия
6. Логистика
7. Хранение
8. Реклама внутренняя (МП)
9. Реклама внешняя (блогеры+ВК)
10. НДС
11. Штрафы
12. Удержания/вычеты
13. **Маржинальная прибыль**
14. Маржинальность %
15. Заказы шт / ₽

ВСЕ метрики в: **₽ + доля от выручки (%) + Δ vs пред. период + Δ п.п.**

### B. Сведение ΔМаржи

Таблица: какая статья расходов как повлияла на изменение маржи:

| Статья | Текущий | Прошлый | Δ | Влияние на маржу ₽ |
|---|---|---|---|---|

Строки: Выручка, Себестоимость/ед, Комиссия, Логистика/ед, Хранение/ед, Реклама внутр, Реклама внешн, НДС, Прочие, **Невязка** (должна быть < 1%).

### C. Модельная декомпозиция

ВСЕ модели, таблица:

| Модель | Статус | Маржа ₽ | Маржа % | Δ Маржа | Заказы шт | Δ Заказы | ДРР % | Комментарий |
|---|---|---|---|---|---|---|---|---|

Группировка по статусам:
- **Продается** — целевая маржа ≥ 20-25%
- **Выводим** — приоритет скорости распродажи, можно жертвовать маржой
- **Архив** — минимальная активность
- **Новинки** — инвестиционная фаза

### D. Драйверы / Антидрайверы маржи

ТОП-5 моделей по вкладу в рост маржи и ТОП-5 по снижению.

## Жёсткие правила

- **WB маржа** = `SUM(marga) - SUM(nds) - SUM(reclama_vn) - COALESCE(SUM(reclama_vn_vk), 0) - COALESCE(SUM(reclama_vn_creators), 0)`
- **OZON маржа** = `SUM(marga) - SUM(nds)`
- **Единая маржа** — включает ВСЮ рекламу. Никаких M-1/M-2.
- GROUP BY модели = LOWER()
- СПП при объединении = средневзвешенный: `sum(spp_amount) / sum(revenue_before_spp) × 100`
- Формат: `1 234 567 ₽`, `24.1%`, `8.0% → 11.2% (+3.2 п.п.)`
- Даты: "17 марта 2026" в тексте. "17.03.2026" в таблицах.
- Тон: сухой финансовый директор. Факты + ₽ эффект. Без оценочных суждений.

## Выход

Markdown с разделами A, B, C, D. Каждый раздел — готовый текст для вставки в финальный отчёт.
```

- [ ] **Step 2: Create directories and commit**

```bash
mkdir -p .claude/skills/analytics-report/prompts/analysts
git add .claude/skills/analytics-report/prompts/analysts/financial.md
git commit -m "feat(analytics-report): add financial analyst prompt (subagent 1)"
```

---

## Task 14: Analyst Prompts — Subagents 2-8

**Files:**
- Create: `.claude/skills/analytics-report/prompts/analysts/internal-ads.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/external-marketing.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/traffic-funnel.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/inventory.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/pricing.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/plan-fact.md`
- Create: `.claude/skills/analytics-report/prompts/analysts/anomaly-detector.md`

Each prompt follows the same structure as Task 13 (financial.md) but with domain-specific content from the spec sections 3.1 (Subagents 2-8). The full content for each is specified in `docs/superpowers/specs/2026-04-07-analytics-report-full-spec.md` sections for each subagent.

- [ ] **Step 1: Write internal-ads.md** — Subagent 2: Internal advertising analyst. Includes: DRR split (internal+external), double KPI (DRR sales + DRR orders), ROMI/CPC/CTR/CPO/CPM by model, efficiency matrix (Growth/Harvest/Optimize/Cut), black holes (ROMI<100%), ad→orders correlation, daily dynamics, budget vs fact. Benchmarks: CTR >5% excellent, CPC <5₽ excellent. Input: `advertising` block + finance summary.

- [ ] **Step 2: Write external-marketing.md** — Subagent 3: External marketing analyst. Includes: bloggers (spend, traffic, ROI with 3-7d lag), VK/Yandex daily dynamics, SMM brand metrics, channel effectiveness. Forbidden phrases enforced. Systematicity matrix applied. Input: `external_marketing` block.

- [ ] **Step 3: Write traffic-funnel.md** — Subagent 4: Traffic and funnel analyst. Includes: full funnel (impressions→card→cart→order→buyout), CR at each step + Δ + benchmarks, ASCII funnel visualization, organic vs paid (NEVER sum), ad-dependent vs organic models, anomaly diagnostics table. Warnings: buyouts lagged, traffic ~20% gap. Input: `traffic` block + advertising summary.

- [ ] **Step 4: Write inventory.md** — Subagent 5: Inventory analyst. Includes: stocks (WB FBO + OZON FBO + MoySklad + transit), turnover = stock/daily_sales, risk thresholds (<14d DEFICIT, 14-60 OK, 60-90 WARNING, 90-250 OVERSTOCK, >250 DEAD), recommendations per model, stock-price constraints. Input: `inventory` block + finance summary.

- [ ] **Step 5: Write pricing.md** — Subagent 6: Price analyst. Includes: price dynamics by model/article, SPP (not controllable, but affects demand), "what if" hypotheses with ₽ effect, annual ROI = margin% × (365/turnover_days), confidence discipline (HIGH/MEDIUM/LOW), price logic decision tree. Input: `pricing` block + inventory/finance summary.

- [ ] **Step 6: Write plan-fact.md** — Subagent 7: Plan-fact analyst. Includes: plan by article WB+OZON (from Sheets), fact MTD, plan MTD (proportional), completion MTD %, forecast, statuses (✅>105% ⚠️95-105% ❌<95%). Metrics: orders qty/₽, sales qty/₽, revenue, margin, ads. Input: `plan_fact` block.

- [ ] **Step 7: Write anomaly-detector.md** — Subagent 8: Anomaly detector. Includes: share change >3pp → flag, cost_of_goods jump → likely error, significant changes by ₽ equivalent, logistics tariff analysis, data quality (retention==deduction, fan-out JOIN). Severity: high (>5pp or >100K₽), medium (3-5pp). Deep model diagnostics when orders Δ >10%. Input: ALL block summaries.

- [ ] **Step 8: Commit all 7 prompts**

```bash
git add .claude/skills/analytics-report/prompts/analysts/
git commit -m "feat(analytics-report): add analyst prompts for subagents 2-8"
```

**Note for implementer:** Each prompt must follow the exact template structure from financial.md: role intro → input data (with {{placeholders}}) → hierarchy requirements → tasks with tables → hard rules → output format. The domain content for each subagent is fully specified in the original spec (`docs/superpowers/specs/2026-04-07-analytics-report-full-spec.md` sections 3.1.2 through 3.1.8). Transcribe those sections into the prompt template format, adding `{{DATA_SLICE}}`, `{{SUMMARY}}`, `{{DEPTH}}`, `{{PERIOD_LABEL}}`, `{{PREV_PERIOD_LABEL}}`, `{{QUALITY_FLAGS}}` placeholders.

---

## Task 15: Verifier Prompts (Subagents 9-11)

**Files:**
- Create: `.claude/skills/analytics-report/prompts/verifiers/marketplace-expert.md`
- Create: `.claude/skills/analytics-report/prompts/verifiers/cfo.md`
- Create: `.claude/skills/analytics-report/prompts/verifiers/data-quality-critic.md`

- [ ] **Step 1: Write marketplace-expert.md** — Subagent 9

```markdown
# Эксперт по маркетплейсам (WB-специалист)

Ты эксперт по маркетплейсам с 5+ годами опыта работы с Wildberries и OZON. Проверяешь корректность интерпретации данных аналитиками.

## Входные данные

**Все findings аналитиков:**
{{ALL_FINDINGS}}

**Quality flags:**
{{QUALITY_FLAGS}}

**Глубина:** {{DEPTH}}

## Что проверяешь

### 1. Лаговые и неуправляемые метрики
- [ ] СПП НЕ управляемый → нет рекомендаций "снизить/повысить СПП"
- [ ] Выкуп % лаговый (3-21 дн) → НЕ используется как причина в дневном анализе
- [ ] Комиссия фиксирована → нет рекомендаций "договориться о комиссии"

### 2. Специфика маркетплейсов
- [ ] WB "склейки" учтены — заказы модели могут включать связанные артикулы
- [ ] OZON organic_data = 0 → органика OZON недоступна, используется оценка
- [ ] Рекомендации реалистичны (нет "повысить цену на 50%", "убрать все товары")

### 3. Внешняя реклама — формулировки
- [ ] Нет "реклама прекратилась" (должно быть "сегодня без рекламы")
- [ ] Нет "экономия на внешней рекламе" (несистемный расход)
- [ ] ДРР блогера в день размещения → "размещение X₽, ДРР считать рано"
- [ ] Системность каналов учтена (блогеры = случайный, ВК = системный)

### 4. Маржинальные формулы
- [ ] WB маржа включает: -NDS -reclama_vn -reclama_vn_vk -reclama_vn_creators
- [ ] OZON маржа: marga - nds (внешняя реклама учтена отдельно)
- [ ] Единая маржа (нет M-1/M-2)

## Выход

Структурированный отзыв:

**PASS** — если всё корректно, кратко подтвердить.

**ISSUES** — если найдены проблемы:
```
Проблема: [описание]
Где: [какой аналитик, какая секция]
Что исправить: [конкретное действие]
Severity: HIGH / MEDIUM
```
```

- [ ] **Step 2: Write cfo.md** — Subagent 10

```markdown
# Финансовый директор (CFO)

Ты CFO бренда Wookiee. Главный верификатор — сводишь все findings воедино и проверяешь корректность.

## Входные данные

**Все findings аналитиков:**
{{ALL_FINDINGS}}

**Findings других верификаторов:**
{{VERIFIER_FINDINGS}}

**Quality flags:**
{{QUALITY_FLAGS}}

**Глубина:** {{DEPTH}}

## Проверки

### 1. Точность цифр
Числа в текстовых выводах = числа из данных. Допуск: ±1%.
Если видишь расхождение > 1% — это ОШИБКА.

### 2. Покрытие
Все warning и critical сигналы покрыты рекомендациями.
Нет "проблема обнаружена" без "что делать".

### 3. Направление
Действие логически соответствует проблеме:
- Дефицит → пополнить (НЕ снизить цену)
- Overstock + маржа > 15% → снизить цену
- Маржа < 15% → НЕ снижать цену
- Мёртвый сток → маркдаун / ликвидация

### 4. KB-правила
Нет конфликтов с правилами аналитики:
- ДРР с разбивкой? Да/Нет
- Единая маржа? Да/Нет
- GROUP BY LOWER()? Да/Нет
- Средневзвешенные проценты? Да/Нет

### 5. Реалистичность
Ожидаемые эффекты в гипотезах достоверны:
- "Повышение цены на 5% даст +500К маржи" — проверить калькуляцию
- Нет нереалистичных ожиданий ("+200% за неделю")

## Verdict

Ответь ОДНИМ из:

**APPROVE** — всё корректно, можно публиковать.

**CORRECT** — мелкие правки (перечислить), но в целом корректно.
```
Правка 1: [что исправить]
Правка 2: [что исправить]
```

**REJECT** — серьёзные ошибки, нужен пересчёт.
```
Ошибка 1: [описание + severity]
Какие аналитики пересчитать: [список]
```

Максимум 1 REJECT за отчёт. При повторном запуске — только APPROVE или CORRECT.
```

- [ ] **Step 3: Write data-quality-critic.md** — Subagent 11

```markdown
# Data Quality Critic

Ты специалист по качеству данных. Проверяешь арифметику, консистентность и соблюдение правил.

## Входные данные

**Все findings аналитиков:**
{{ALL_FINDINGS}}

**Quality flags:**
{{QUALITY_FLAGS}}

## Проверки

### 1. Арифметика
- [ ] Сумма моделей = итого бренда (±1%). Проверить для: выручка, маржа, заказы.
- [ ] WB + OZON = Бренд (±1%)
- [ ] Δ вычислены корректно: (текущий - прошлый) / прошлый × 100

### 2. ДРР
- [ ] ОБЯЗАТЕЛЬНО с разбивкой: внутренняя + внешняя отдельно
- [ ] ДРР продаж = ad / sales_revenue × 100
- [ ] ДРР заказов = ad / orders_revenue × 100
- [ ] Оба присутствуют

### 3. СПП
- [ ] При объединении каналов: средневзвешенный = sum(spp_amount) / sum(revenue_before_spp) × 100
- [ ] НЕ среднее арифметическое ((wb_spp + ozon_spp) / 2 — ОШИБКА)

### 4. GROUP BY LOWER()
- [ ] Нет дублей моделей с разным регистром (Wendy и wendy — одна модель)
- [ ] Все модели с заглавной буквы в отображении

### 5. Единая маржа
- [ ] Маржа включает ВСЮ рекламу (internal + external)
- [ ] Нет разделения на M-1 (маржа до рекламы) и M-2 (после)
- [ ] WB формула: marga - nds - reclama_vn - reclama_vn_vk - reclama_vn_creators
- [ ] OZON формула: marga - nds

### 6. Выкуп %
- [ ] Если depth = "day": НЕ используется как причина изменений
- [ ] Если depth = "week": с оговоркой "лаг 3-21 дн"
- [ ] Если depth = "month": без ограничений

### 7. Доли складываются
- [ ] Комиссия% + Логистика% + Хранение% + Себестоимость% + Реклама% + НДС% + Маржа% + Прочие% ≈ 100% (±2%)

### 8. Нет артефактов
- [ ] Нет "0%" где должно быть значение
- [ ] Нет "—" где должно быть число
- [ ] Нет "NaN", "null", "None", "undefined"
- [ ] Нет пустых ячеек в обязательных таблицах

## Выход

**PASS** — все проверки пройдены.

**FAIL** — список найденных проблем:
```
[CRITICAL] Описание проблемы
[WARNING] Описание проблемы
```
```

- [ ] **Step 4: Create directories and commit**

```bash
mkdir -p .claude/skills/analytics-report/prompts/verifiers
git add .claude/skills/analytics-report/prompts/verifiers/
git commit -m "feat(analytics-report): add verifier prompts (marketplace-expert, CFO, data-quality)"
```

---

## Task 16: Synthesizer Prompt

**Files:**
- Create: `.claude/skills/analytics-report/prompts/synthesizer.md`

- [ ] **Step 1: Write the synthesizer prompt**

```markdown
# Synthesizer — Финальная сборка отчёта

Ты собираешь финальный аналитический отчёт из findings всех аналитиков, после проверки верификаторами.

## Входные данные

**CFO Output (verdict + corrections):**
{{CFO_OUTPUT}}

**Все findings аналитиков (после верификации):**
{{ALL_FINDINGS}}

**Quality flags:**
{{QUALITY_FLAGS}}

**Параметры:**
- Глубина: {{DEPTH}}
- Период: {{PERIOD_LABEL}}
- Пред. период: {{PREV_PERIOD_LABEL}}

**Шаблон структуры отчёта:**
{{REPORT_STRUCTURE}}

**Гайд по Notion-форматированию:**
{{NOTION_GUIDE}}

## Задача

Собери ПОЛНЫЙ отчёт из 13 секций. Используй шаблон структуры как скелет.

**Критически важно:**
1. Executive Summary (Секция 0) — это СИНТЕЗ, а не копирование. Ты анализируешь ВСЕ findings и создаёшь 10-15 строк ключевых выводов.
2. Ни одна секция не может быть пустой.
3. Все таблицы — ПОЛНЫЕ (без "и т.д.", "...", "остальные модели").
4. Применить ВСЕ коррекции CFO.
5. Если CFO отметил CORRECT — внести правки перед публикацией.

## Executive Summary (Секция 0) — ОСОБОЕ ВНИМАНИЕ

Это самая важная секция. Она должна содержать:

1. **Маржинальность:** текущая ₽, Δ% vs пред. период, тренд (растёт/падает/стабильно)
2. **Скорость развития:** заказы Δ%, выручка Δ%, распределение WB/OZON
3. **План-факт:** MTD выполнение по ключевым KPI (заказы, выручка, маржа)
4. **Здоровье бренда:** средняя оборачиваемость, количество моделей в DEFICIT/OVERSTOCK
5. **ТОП-3 риска** с ₽ эффектом (из findings всех аналитиков)
6. **ТОП-3 возможности** с ₽ эффектом

Формат: callout-блок, сухой тон. Числа из данных.

## Два формата вывода

### 1. `final_document_md` — стандартный Markdown
- Для сохранения в git: `docs/reports/{start}_{end}_analytics.md`
- Стандартные markdown таблицы
- Без HTML-тегов

### 2. `final_document_notion` — Notion-enhanced
- Для публикации в Notion
- Toggle headings на ВСЕХ уровнях
- `<table fit-page-width header-row header-column>` с colored rows/cells
- `<callout>` блоки
- Цвета по гайду

## Правила форматирования

- Числа: `1 234 567 ₽`, `24.1%`, `8.0% → 11.2% (+3.2 п.п.)`
- Даты в тексте: "17 марта 2026". В таблицах: "17.03.2026"
- Модели: с заглавной буквы
- Заголовки: русский, без аббревиатур
- Тон: сухой финансовый директор
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/prompts/synthesizer.md
git commit -m "feat(analytics-report): add synthesizer prompt (Executive Summary + full report)"
```

---

## Task 17: SKILL.md — Main Orchestrator

**Files:**
- Create: `.claude/skills/analytics-report/SKILL.md`

- [ ] **Step 1: Write the skill orchestrator**

```markdown
---
name: analytics-report
description: Full analytics report for Wookiee brand (WB+OZON) — replaces Oleg v2. 12 subagents analyze finance, marketing, traffic, inventory, prices, plan-fact.
triggers:
  - /analytics-report
  - analytics report
  - аналитический отчёт
  - финансовый отчёт
  - отчёт за период
---

# Analytics Report Skill

Generates a comprehensive analytics report for the Wookiee brand using 12 subagents: 8 analysts (parallel) → 3 verifiers (parallel) → 1 synthesizer.

## Quick Start

```
/analytics-report 2026-04-05                     → дневной (vs вчера)
/analytics-report 2026-03-30 2026-04-05           → недельный
/analytics-report 2026-03-01 2026-03-31           → месячный
```

**Время:** ~15-25 минут (коллектор ~30с, 8 аналитиков ~5-8м, 3 верификатора ~3-5м, синтезайзер ~5-10м)

**Результаты:**
- MD: `docs/reports/{start}_{end}_analytics.md`
- Notion: страница в "Аналитические отчеты"

---

## Stage 0: Parse Arguments

Parse the user's input to extract dates:

- 1 date argument → `start = end = that date` (daily)
- 2 date arguments → `start, end` (weekly or monthly auto-detected)

Compute:
```
If 1 date:
  start = end = date
  prev_start = prev_end = date - 1 day
  depth = "day"

If 2 dates:
  days = (end - start) + 1
  depth = "day" if days <= 1, "week" if days <= 14, "month" otherwise
  prev_end = start - 1 day
  prev_start = prev_end - (days - 1) days

month_start = first day of end's month
```

Store: `START`, `END`, `DEPTH`, `PREV_START`, `PREV_END`, `MONTH_START`

---

## Stage 1: Data Collection

Run the collector:
```bash
python scripts/analytics_report/collect_all.py --start {START} --end {END} --output /tmp/analytics-report-{START}_{END}.json
```

Read the output:
```bash
cat /tmp/analytics-report-{START}_{END}.json
```

Save the full JSON as `data_bundle`.

Check `data_bundle["meta"]["errors"]`:
- If > 3 collectors failed → report error to user and STOP
- If 1-3 failed → note in quality_flags, continue with available data

Store: `data_bundle`, `quality_flags`, `period_label`, `prev_period_label`

---

## Stage 2: Multi-Wave Analysis

### Prepare data slices

For each analyst, prepare their data slice from `data_bundle`:

| Analyst | Primary data | Summary of other blocks |
|---|---|---|
| Financial | `data_bundle["finance"]` | advertising totals, inventory risk counts |
| Internal Ads | `data_bundle["advertising"]` | finance (revenue by model) |
| External Marketing | `data_bundle["external_marketing"]` | finance (total revenue) |
| Traffic Funnel | `data_bundle["traffic"]` | advertising (paid spend) |
| Inventory | `data_bundle["inventory"]` | finance (sales by model for daily_sales) |
| Pricing | `data_bundle["pricing"]` | inventory (turnover), finance (margin by model) |
| Plan-Fact | `data_bundle["plan_fact"]` | finance (MTD fact numbers) |
| Anomaly Detector | Summary of ALL blocks | quality_flags |

**Summary** for each analyst = 5-10 lines of key numbers from other blocks (not full data).

### Wave 1: 8 Analysts (launch ALL 8 in parallel using 8 Agent calls in a SINGLE message)

For each analyst:
1. Read the prompt file: `.claude/skills/analytics-report/prompts/analysts/{name}.md`
2. Replace placeholders:
   - `{{DATA_SLICE}}` → the analyst's data slice (JSON)
   - `{{SUMMARY}}` → summary of other blocks
   - `{{DEPTH}}` → depth value
   - `{{PERIOD_LABEL}}` → period_label
   - `{{PREV_PERIOD_LABEL}}` → prev_period_label
   - `{{QUALITY_FLAGS}}` → quality_flags
3. Launch as Agent subagent with the prompt

**Launch these 8 agents IN PARALLEL (single message, 8 Agent tool calls):**

1. **Financial Analyst** → save output as `financial_findings`
2. **Internal Ads Analyst** → save output as `ads_findings`
3. **External Marketing Analyst** → save output as `external_findings`
4. **Traffic Funnel Analyst** → save output as `traffic_findings`
5. **Inventory Analyst** → save output as `inventory_findings`
6. **Pricing Analyst** → save output as `pricing_findings`
7. **Plan-Fact Analyst** → save output as `plan_fact_findings`
8. **Anomaly Detector** → save output as `anomaly_findings`

Wait for all 8 to complete.

Concatenate ALL findings into `all_findings`:
```
all_findings = """
=== FINANCIAL ANALYST ===
{financial_findings}

=== INTERNAL ADS ANALYST ===
{ads_findings}

=== EXTERNAL MARKETING ANALYST ===
{external_findings}

=== TRAFFIC FUNNEL ANALYST ===
{traffic_findings}

=== INVENTORY ANALYST ===
{inventory_findings}

=== PRICING ANALYST ===
{pricing_findings}

=== PLAN-FACT ANALYST ===
{plan_fact_findings}

=== ANOMALY DETECTOR ===
{anomaly_findings}
"""
```

### Wave 2: 3 Verifiers (launch ALL 3 in parallel)

For each verifier:
1. Read prompt: `.claude/skills/analytics-report/prompts/verifiers/{name}.md`
2. Replace `{{ALL_FINDINGS}}` → all_findings, `{{QUALITY_FLAGS}}` → quality_flags, `{{DEPTH}}` → depth
3. For CFO: also replace `{{VERIFIER_FINDINGS}}` → "" (first pass)

**Launch 3 agents IN PARALLEL:**

1. **Marketplace Expert** → save as `marketplace_review`
2. **CFO** → save as `cfo_verdict`
3. **Data Quality Critic** → save as `dq_review`

Wait for all 3.

### CFO Verdict Handling

Parse `cfo_verdict`:

**If APPROVE or CORRECT:**
- If CORRECT: note corrections to apply in synthesis
- Proceed to Stage 3

**If REJECT:**
- Identify which analysts need re-run from CFO feedback
- Re-run ONLY those analysts (Wave 1b — parallel)
- Re-run Data Quality Critic on new findings
- Re-run CFO with `{{VERIFIER_FINDINGS}}` = marketplace_review + dq_review
- **CFO must APPROVE or CORRECT on Pass 2** — no further REJECT

---

## Stage 3: Synthesis

Read these files:
- `.claude/skills/analytics-report/prompts/synthesizer.md`
- `.claude/skills/analytics-report/templates/report-structure.md`
- `.claude/skills/analytics-report/templates/notion-formatting-guide.md`

Launch Synthesizer subagent (Agent tool):
- Replace `{{CFO_OUTPUT}}` → cfo_verdict
- Replace `{{ALL_FINDINGS}}` → all_findings (or corrected findings if re-run happened)
- Replace `{{QUALITY_FLAGS}}` → quality_flags
- Replace `{{DEPTH}}` → depth
- Replace `{{PERIOD_LABEL}}` → period_label
- Replace `{{PREV_PERIOD_LABEL}}` → prev_period_label
- Replace `{{REPORT_STRUCTURE}}` → content of report-structure.md
- Replace `{{NOTION_GUIDE}}` → content of notion-formatting-guide.md

The synthesizer produces TWO outputs:
1. `final_document_md` — standard markdown
2. `final_document_notion` — Notion-enhanced format

---

## Stage 4: Publication

### 4.1 Save MD file

Save `final_document_md` to `docs/reports/{START}_{END}_analytics.md`:

```bash
cat > docs/reports/{START}_{END}_analytics.md << 'REPORT_EOF'
{final_document_md}
REPORT_EOF
```

### 4.2 Publish to Notion

Use `mcp__claude_ai_Notion__notion-create-pages` tool:
- Parent: `data_source_id = "30158a2b-d587-8091-bfc3-000b83c6b747"`
- Title: Based on depth:
  - day: `Ежедневный фин анализ — {PERIOD_LABEL}`
  - week: `Еженедельный фин анализ — {PERIOD_LABEL}`
  - month: `Ежемесячный фин анализ — {PERIOD_LABEL}`
- Content: `final_document_notion` (FULL content, not summary)
- Properties:
  - Тип анализа: "Ежедневный фин анализ" / "Еженедельный фин анализ" / "Ежемесячный фин анализ"
  - Источник: "Analytics Skill v1"
  - Статус: "Актуальный"
  - Период начала: {START}
  - Период конца: {END}

### 4.3 Chat Summary

After publication, output to user:

```
📊 Аналитический отчёт ({DEPTH}) за {PERIOD_LABEL}

[3-5 строк ключевых цифр из Executive Summary]

📎 Notion: [ссылка]
📎 MD: docs/reports/{START}_{END}_analytics.md
⏱ Время: X минут
```
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/SKILL.md
git commit -m "feat(analytics-report): add SKILL.md orchestrator (5 stages, 12 subagents)"
```

---

## Task 18: Register Skill in Settings

**Files:**
- Modify: `.claude/settings.json` (if skill auto-discovery is not used)

- [ ] **Step 1: Verify skill is discoverable**

Run: `ls -la .claude/skills/analytics-report/SKILL.md`
Expected: file exists

The skill should be auto-discovered by Claude Code from the `.claude/skills/` directory. No manual registration needed if the frontmatter `triggers` are set (which they are in SKILL.md).

- [ ] **Step 2: Final commit with all files**

```bash
git add -A .claude/skills/analytics-report/ scripts/analytics_report/ tests/analytics_report/
git status
git commit -m "feat(analytics-report): complete skill implementation (12 subagents, 8 collectors)"
```

---

## Task 19: End-to-End Test Run

**Files:** No new files — testing the full pipeline.

- [ ] **Step 1: Test collector with real data**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05 --output /tmp/analytics-report-test.json
```

Expected: JSON file created, check `meta.errors` is empty or acceptable.

- [ ] **Step 2: Verify JSON structure**

```bash
python -c "
import json
with open('/tmp/analytics-report-test.json') as f:
    d = json.load(f)
print('Keys:', list(d.keys()))
print('Meta:', d['meta'])
print('Finance keys:', list(d.get('finance', {}).keys()))
print('Errors:', d['meta'].get('errors', {}))
"
```

Expected: All 8 blocks present, minimal errors.

- [ ] **Step 3: Invoke the skill**

```
/analytics-report 2026-03-30 2026-04-05
```

Expected: Full pipeline runs — collectors → 8 analysts → 3 verifiers → synthesizer → MD + Notion.

- [ ] **Step 4: Verify output**

Check:
1. MD file exists at `docs/reports/2026-03-30_2026-04-05_analytics.md`
2. Notion page created with full content
3. All 13 sections present
4. Executive Summary contains: маржинальность, скорость развития, план-факт, здоровье бренда
5. Numbers formatted correctly (spaces, ₽, %)

---

## Summary

| Task | What | Files | Commits |
|---|---|---|---|
| 1 | Utils scaffold | 5 files | 1 |
| 2 | Finance collector | 1 file | 1 |
| 3 | Advertising collector | 1 file | 1 |
| 4 | External marketing collector | 1 file | 1 |
| 5 | Traffic collector | 1 file | 1 |
| 6 | Inventory collector | 1 file | 1 |
| 7 | Pricing collector | 1 file | 1 |
| 8 | Plan-fact collector | 1 file | 1 |
| 9 | SKU statuses collector | 1 file | 1 |
| 10 | collect_all.py orchestrator | 1 file | 1 |
| 11 | Reference docs | 2 files | 1 |
| 12 | Templates | 2 files | 1 |
| 13 | Financial analyst prompt | 1 file | 1 |
| 14 | Analyst prompts 2-8 | 7 files | 1 |
| 15 | Verifier prompts | 3 files | 1 |
| 16 | Synthesizer prompt | 1 file | 1 |
| 17 | SKILL.md orchestrator | 1 file | 1 |
| 18 | Register + final commit | 0 files | 1 |
| 19 | E2E test | 0 files | 0 |
| **Total** | | **~30 files** | **~18 commits** |
