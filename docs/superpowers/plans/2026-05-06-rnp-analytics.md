# РНП — Рука на пульсе: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live weekly analytics dashboard in Wookiee Hub that replicates Artem's GAS/Sheets RNP_Daily script — model selector, date range picker, 77 metrics across 6 chart tabs, powered by WB PostgreSQL + Google Sheets.

**Architecture:** New FastAPI service `services/analytics_api/` on port 8005 reads WB DB via `shared/data_layer/rnp.py` and Google Sheets via existing `shared/clients/sheets_client.py`. Hub React frontend calls the service, stores filter state in URL params, renders Recharts ComposedChart with phase coloring.

**Tech Stack:** Python 3.11 + FastAPI + psycopg2 + gspread; React + Recharts ^2.0.0 + shadcn/ui + Tailwind; React Router v6 useSearchParams

**Spec:** `docs/superpowers/specs/2026-05-06-rnp-analytics-design.md`

---

## File Map

**New files:**
- `shared/data_layer/rnp.py` — WB SQL queries + week aggregation + all derived metrics
- `services/analytics_api/__init__.py`
- `services/analytics_api/app.py` — FastAPI: /health, /api/rnp/models, /api/rnp/weeks
- `services/analytics_api/requirements.txt`
- `tests/analytics_api/__init__.py` — empty, makes pytest discover the module
- `tests/analytics_api/test_rnp_metrics.py` — unit tests for derived metric logic
- `wookiee-hub/src/types/rnp.ts` — TypeScript types for API response
- `wookiee-hub/src/api/rnp.ts` — API client (fetch wrapper)
- `wookiee-hub/src/pages/analytics/rnp.tsx` — main page
- `wookiee-hub/src/components/analytics/rnp-help-block.tsx`
- `wookiee-hub/src/components/analytics/rnp-filters.tsx`
- `wookiee-hub/src/components/analytics/rnp-summary-cards.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-orders.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-funnel.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-total.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-internal.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-external.tsx`
- `wookiee-hub/src/components/analytics/rnp-tabs/tab-margin.tsx`

**Modified files:**
- `shared/data_layer/__init__.py` — add `from shared.data_layer.rnp import *`
- `wookiee-hub/src/config/navigation.ts` — add "analytics" group
- `wookiee-hub/src/router.tsx` — add /analytics/rnp route

---

## Task 1: WB PostgreSQL raw data fetching

**Files:**
- Create: `shared/data_layer/rnp.py`

- [ ] **Step 1: Write the test first**

Create `tests/analytics_api/test_rnp_metrics.py`:

```python
"""Unit tests for RNP metric helpers — no DB required."""
import pytest
from shared.data_layer.rnp import _safe_div, _week_start, _detect_phase
from datetime import date

def test_safe_div_normal():
    assert abs(_safe_div(10.0, 4.0) - 2.5) < 0.001

def test_safe_div_zero_denominator():
    assert _safe_div(10.0, 0) is None

def test_safe_div_none_inputs():
    assert _safe_div(None, 5) is None
    assert _safe_div(5, None) is None

def test_week_start_monday():
    assert _week_start(date(2025, 3, 5)) == date(2025, 3, 3)   # Wednesday → Monday

def test_week_start_already_monday():
    assert _week_start(date(2025, 3, 3)) == date(2025, 3, 3)

def test_detect_phase_norm():
    assert _detect_phase(15.0) == "norm"
    assert _detect_phase(25.0) == "norm"

def test_detect_phase_decline():
    assert _detect_phase(9.9) == "decline"
    assert _detect_phase(-5.0) == "decline"

def test_detect_phase_recovery():
    assert _detect_phase(12.0) == "recovery"

def test_detect_phase_none():
    assert _detect_phase(None) == "recovery"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/danilamatveev/Projects/Wookiee
python -m pytest tests/analytics_api/test_rnp_metrics.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'shared.data_layer.rnp'`

- [ ] **Step 3: Create `shared/data_layer/rnp.py` with helpers and raw DB query**

```python
"""РНП (Рука на Пульсе) — data layer: WB PostgreSQL queries + week aggregation."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from shared.data_layer._connection import _get_wb_connection

logger = logging.getLogger(__name__)

__all__ = [
    "fetch_rnp_wb_daily",
    "fetch_rnp_models_wb",
    "aggregate_to_weeks",
    "_safe_div",
    "_week_start",
    "_detect_phase",
]


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _week_start(d: date) -> date:
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _detect_phase(margin_pct: Optional[float]) -> str:
    if margin_pct is None:
        return "recovery"
    if margin_pct >= 15:
        return "norm"
    if margin_pct < 10:
        return "decline"
    return "recovery"


def fetch_rnp_models_wb() -> list[str]:
    """Sorted list of distinct WB model names available in abc_date."""
    conn = _get_wb_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT LOWER(SPLIT_PART(article, '/', 1)) AS model
                FROM abc_date
                ORDER BY 1
            """)
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_rnp_wb_daily(
    model: str,
    date_from: date,
    date_to: date,
) -> list[dict]:
    """
    Fetch daily WB data for one model across 4 tables.
    Returns list of dicts keyed by date; missing days from any table → None fields.
    """
    m = model.lower()
    conn = _get_wb_connection()
    try:
        with conn.cursor() as cur:
            # ── abc_date: orders, sales, adv_internal, margin ──────────────────
            cur.execute("""
                SELECT
                    date::date AS dt,
                    SUM(count_orders)                                       AS orders_qty,
                    SUM(full_counts - returns)                              AS sales_qty,
                    SUM(revenue_spp - COALESCE(revenue_return_spp, 0))     AS sales_rub,
                    SUM(reclama)                                            AS adv_internal_rub,
                    SUM(
                        marga - nds - reclama_vn
                        - COALESCE(reclama_vn_vk, 0)
                        - COALESCE(reclama_vn_creators, 0)
                    )                                                       AS margin_rub
                FROM abc_date
                WHERE LOWER(SPLIT_PART(article, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            abc = {r[0]: r for r in cur.fetchall()}

            # ── orders: orders_rub, orders_spp_rub ─────────────────────────────
            cur.execute("""
                SELECT
                    date::date           AS dt,
                    SUM(pricewithdisc)   AS orders_rub,
                    SUM(finishedprice)   AS orders_spp_rub
                FROM orders
                WHERE LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            ord_ = {r[0]: r for r in cur.fetchall()}

            # ── content_analysis: funnel clicks + cart ─────────────────────────
            cur.execute("""
                SELECT
                    date::date              AS dt,
                    SUM(opencardcount)      AS clicks_total,
                    SUM(addtocartcount)     AS cart_total
                FROM content_analysis
                WHERE LOWER(SPLIT_PART(vendorcode, '/', 1)) = %s
                  AND date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            ca = {r[0]: r for r in cur.fetchall()}

            # ── wb_adv: internal ad views/clicks/orders ────────────────────────
            # nmid→model resolved via `nomenclature` table (confirmed pattern from advertising.py)
            cur.execute("""
                SELECT
                    wa.date::date   AS dt,
                    SUM(wa.views)   AS adv_views,
                    SUM(wa.clicks)  AS adv_clicks,
                    SUM(wa.orders)  AS adv_orders
                FROM wb_adv wa
                JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n
                  ON wa.nmid = n.nmid
                WHERE LOWER(SPLIT_PART(n.vendorcode, '/', 1)) = %s
                  AND wa.date::date BETWEEN %s AND %s
                GROUP BY 1
            """, (m, date_from, date_to))
            adv = {r[0]: r for r in cur.fetchall()}

    finally:
        conn.close()

    all_dates = sorted(set(abc) | set(ord_) | set(ca) | set(adv))
    result = []
    for dt in all_dates:
        a = abc.get(dt, (None,) * 6)
        o = ord_.get(dt, (None,) * 3)
        c = ca.get(dt, (None,) * 3)
        w = adv.get(dt, (None,) * 4)
        result.append({
            "date": dt,
            "orders_qty":      a[1],
            "sales_qty":       a[2],
            "sales_rub":       a[3],
            "adv_internal_rub": a[4],
            "margin_rub":      a[5],
            "orders_rub":      o[1],
            "orders_spp_rub":  o[2],
            "clicks_total":    c[1],
            "cart_total":      c[2],
            "adv_views":       w[1],
            "adv_clicks":      w[2],
            "adv_orders":      w[3],
        })
    return result
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/analytics_api/test_rnp_metrics.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/rnp.py tests/analytics_api/test_rnp_metrics.py
git commit -m "feat(rnp): data layer — WB DB queries + metric helpers"
```

---

## Task 2: Week aggregation + all 77 derived metrics

**Files:**
- Modify: `shared/data_layer/rnp.py` (append `aggregate_to_weeks`)

- [ ] **Step 1: Write aggregation tests**

Add to `tests/analytics_api/test_rnp_metrics.py`:

```python
from shared.data_layer.rnp import aggregate_to_weeks

def _make_day(dt_str, **kwargs):
    defaults = {
        "date": date.fromisoformat(dt_str),
        "orders_qty": 100, "sales_qty": 87, "sales_rub": 500000,
        "adv_internal_rub": 50000, "margin_rub": 80000,
        "orders_rub": 600000, "orders_spp_rub": 540000,
        "clicks_total": 5000, "cart_total": 300,
        "adv_views": 2000, "adv_clicks": 150, "adv_orders": 20,
    }
    defaults.update(kwargs)
    return defaults

def test_aggregate_single_week_orders():
    rows = [_make_day("2025-03-03"), _make_day("2025-03-04")]
    result = aggregate_to_weeks(rows, {})
    assert len(result) == 1
    week = result[0]
    assert week["week_start"] == "2025-03-03"
    assert week["orders_qty"] == 200
    assert week["sales_qty"] == 174

def test_aggregate_null_safe_division_zero_clicks():
    rows = [_make_day("2025-03-03", clicks_total=0, cart_total=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["cr_card_to_cart"] is None
    assert week["cr_total"] is None

def test_aggregate_phase_norm():
    # margin_rub=200k, sales_rub=1M → margin_pct=20% → norm
    rows = [_make_day("2025-03-03", margin_rub=200000, sales_rub=1000000,
                      adv_internal_rub=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["phase"] == "norm"

def test_aggregate_phase_decline():
    rows = [_make_day("2025-03-03", margin_rub=50000, sales_rub=1000000,
                      adv_internal_rub=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["phase"] == "decline"

def test_aggregate_margin_before_ads():
    rows = [_make_day("2025-03-03", margin_rub=80000, adv_internal_rub=50000,
                      sales_rub=500000)]
    week = aggregate_to_weeks(rows, {})[0]
    # margin_before_ads = 80000 + 50000 (internal) + 0 (no sheets) = 130000
    assert week["margin_before_ads_rub"] == pytest.approx(130000)
```

- [ ] **Step 2: Run — expect failures**

```bash
python -m pytest tests/analytics_api/test_rnp_metrics.py::test_aggregate_single_week_orders -v
```

Expected: `AttributeError: module has no attribute 'aggregate_to_weeks'`

- [ ] **Step 3: Append `aggregate_to_weeks` to `shared/data_layer/rnp.py`**

```python
def aggregate_to_weeks(
    daily_rows: list[dict],
    sheets_data: dict,
    buyout_forecast: Optional[float] = None,
) -> list[dict]:
    """
    Aggregate daily WB rows into weekly buckets and compute all derived metrics.

    sheets_data: dict keyed by ISO week_start string, values are per-channel dicts
                 with keys like blogger_rub, vk_sids_rub, etc.
    buyout_forecast: override buyout %; defaults to period-average sales_qty/orders_qty
    """
    if not daily_rows:
        return []

    # Compute period-level buyout for default forecast
    if buyout_forecast is None:
        tot_orders = sum(r["orders_qty"] or 0 for r in daily_rows)
        tot_sales = sum(r["sales_qty"] or 0 for r in daily_rows)
        buyout_forecast = _safe_div(tot_sales, tot_orders) or 0.87

    # Group days by week_start (Monday)
    buckets: dict[date, list[dict]] = {}
    for row in daily_rows:
        ws = _week_start(row["date"])
        buckets.setdefault(ws, []).append(row)

    result = []
    for week_start, rows in sorted(buckets.items()):
        week_end = week_start + timedelta(days=6)
        wkey = week_start.isoformat()

        # ── DB aggregations ──────────────────────────────────────────────────
        def db_sum(field: str) -> float:
            return sum(r[field] or 0 for r in rows)

        orders_qty          = db_sum("orders_qty")
        sales_qty           = db_sum("sales_qty")
        sales_rub           = db_sum("sales_rub")
        adv_internal_rub    = db_sum("adv_internal_rub")
        margin_rub          = db_sum("margin_rub")
        orders_rub          = db_sum("orders_rub")
        orders_spp_rub      = db_sum("orders_spp_rub")
        clicks_total        = db_sum("clicks_total")
        cart_total          = db_sum("cart_total")
        adv_views           = db_sum("adv_views")
        adv_clicks          = db_sum("adv_clicks")
        orders_internal_qty = db_sum("adv_orders")

        # ── Sheets aggregations ──────────────────────────────────────────────
        sh = sheets_data.get(wkey, {})

        def sh_val(key: str) -> Optional[float]:
            v = sh.get(key)
            return float(v) if v else None

        blogger_rub      = sh_val("blogger_rub") or 0.0
        blogger_views    = sh_val("blogger_views")
        blogger_clicks   = sh_val("blogger_clicks")
        blogger_carts    = sh_val("blogger_carts")
        blogger_orders   = sh_val("blogger_orders")
        blogger_no_stats = bool(sh.get("blogger_no_stats", False))

        vk_sids_rub     = sh_val("vk_sids_rub") or 0.0
        vk_sids_views   = sh_val("vk_sids_views")
        vk_sids_clicks  = sh_val("vk_sids_clicks")
        vk_sids_orders  = sh_val("vk_sids_orders")

        sids_c_rub      = sh_val("sids_contractor_rub") or 0.0
        sids_c_views    = sh_val("sids_contractor_views")
        sids_c_clicks   = sh_val("sids_contractor_clicks")
        sids_c_orders   = sh_val("sids_contractor_orders")

        ya_rub          = sh_val("yandex_contractor_rub") or 0.0
        ya_views        = sh_val("yandex_contractor_views")
        ya_clicks       = sh_val("yandex_contractor_clicks")
        ya_orders       = sh_val("yandex_contractor_orders")

        # ── Derived ──────────────────────────────────────────────────────────
        adv_external_rub = blogger_rub + vk_sids_rub + sids_c_rub + ya_rub
        adv_total_rub    = adv_internal_rub + adv_external_rub

        margin_before_ads_rub = margin_rub + adv_total_rub
        margin_before_ads_pct = _safe_div(margin_before_ads_rub * 100, sales_rub)
        margin_pct            = _safe_div(margin_rub * 100, sales_rub)
        margin_ratio          = _safe_div(margin_before_ads_rub, sales_rub)  # as 0–1

        orders_organic_qty = max(0, orders_qty - orders_internal_qty)
        avg_order_rub      = _safe_div(orders_rub, orders_qty)

        # Internal ad profit forecast
        adv_orders_rub = orders_internal_qty * (avg_order_rub or 0)
        adv_sales_rub  = adv_orders_rub * buyout_forecast
        adv_int_profit = (
            adv_sales_rub * margin_ratio - adv_internal_rub
            if margin_ratio is not None else None
        )

        # Blogger profit forecast
        if blogger_orders and avg_order_rub and margin_ratio is not None and not blogger_no_stats:
            bl_orders_rub   = blogger_orders * avg_order_rub
            bl_sales_rub    = bl_orders_rub * buyout_forecast
            blogger_profit  = bl_sales_rub * margin_ratio - blogger_rub
        else:
            blogger_profit = None

        # Sales + margin forecast
        sales_fc_rub  = orders_rub * buyout_forecast if orders_rub else None
        margin_fc_rub = (
            sales_fc_rub * margin_ratio - adv_total_rub
            if sales_fc_rub and margin_ratio is not None else None
        )

        # Ext totals (sum non-None)
        def _ext_sum(*vals: Optional[float]) -> Optional[float]:
            total = sum(v for v in vals if v is not None)
            return total if total > 0 else None

        ext_views  = _ext_sum(blogger_views, vk_sids_views, sids_c_views, ya_views)
        ext_clicks = _ext_sum(blogger_clicks, vk_sids_clicks, sids_c_clicks, ya_clicks)

        result.append({
            "week_start": wkey,
            "week_end":   week_end.isoformat(),
            "week_label": f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m')}",
            "phase":      _detect_phase(margin_pct),
            # Заказы
            "orders_qty":        orders_qty or None,
            "orders_rub":        orders_rub or None,
            "orders_spp_rub":    orders_spp_rub or None,
            "avg_order_rub":     avg_order_rub,
            "avg_order_spp_rub": _safe_div(orders_spp_rub, orders_qty),
            "spp_pct": _safe_div((orders_rub - orders_spp_rub) * 100, orders_rub) if orders_rub else None,
            # Продажи
            "sales_qty":    sales_qty or None,
            "buyout_pct":   _safe_div(sales_qty * 100, orders_qty),
            "sales_rub":    sales_rub or None,
            "avg_sale_rub": _safe_div(sales_rub, sales_qty),
            # Воронка
            "clicks_total":     clicks_total or None,
            "cart_total":       cart_total or None,
            "cr_card_to_cart":  _safe_div(cart_total * 100, clicks_total),
            "cr_cart_to_order": _safe_div(orders_qty * 100, cart_total),
            "cr_total":         _safe_div(orders_qty * 100, clicks_total),
            # Реклама итого
            "adv_total_rub":           adv_total_rub or None,
            "drr_total_from_sales":    _safe_div(adv_total_rub * 100, sales_rub),
            "drr_total_from_orders":   _safe_div(adv_total_rub * 100, orders_rub),
            # Внутренняя реклама
            "adv_internal_rub":          adv_internal_rub or None,
            "drr_internal_from_sales":   _safe_div(adv_internal_rub * 100, sales_rub),
            "drr_internal_from_orders":  _safe_div(adv_internal_rub * 100, orders_rub),
            "orders_organic_qty":        orders_organic_qty or None,
            "orders_internal_qty":       orders_internal_qty or None,
            "adv_views":   adv_views or None,
            "adv_clicks":  adv_clicks or None,
            "ctr_internal": _safe_div(adv_clicks * 100, adv_views),
            "cpc_internal": _safe_div(adv_internal_rub, adv_clicks),
            "cpo_internal": _safe_div(adv_internal_rub, orders_internal_qty),
            "cpm_internal": _safe_div(adv_internal_rub * 1000, adv_views),
            "adv_internal_profit_forecast": adv_int_profit,
            "romi_internal": _safe_div((adv_int_profit or 0) * 100, adv_internal_rub) if adv_int_profit else None,
            # Внешняя реклама итого
            "adv_external_rub":          adv_external_rub or None,
            "drr_external_from_sales":   _safe_div(adv_external_rub * 100, sales_rub),
            "drr_external_from_orders":  _safe_div(adv_external_rub * 100, orders_rub),
            "ext_views":    ext_views,
            "ext_clicks":   ext_clicks,
            "ctr_external": _safe_div((ext_clicks or 0) * 100, ext_views) if ext_views else None,
            # Блогеры
            "blogger_rub":             blogger_rub or None,
            "drr_blogger_from_sales":  _safe_div(blogger_rub * 100, sales_rub),
            "drr_blogger_from_orders": _safe_div(blogger_rub * 100, orders_rub),
            "blogger_views":   blogger_views,
            "blogger_clicks":  blogger_clicks,
            "ctr_blogger":     _safe_div((blogger_clicks or 0) * 100, blogger_views) if blogger_views else None,
            "blogger_carts":   blogger_carts,
            "blogger_orders":  blogger_orders,
            "blogger_profit_forecast": blogger_profit,
            "romi_blogger": _safe_div((blogger_profit or 0) * 100, blogger_rub) if blogger_profit and blogger_rub else None,
            "blogger_no_stats": blogger_no_stats,
            # ВК SIDS
            "vk_sids_rub":            vk_sids_rub or None,
            "drr_vk_sids_from_sales": _safe_div(vk_sids_rub * 100, sales_rub),
            "drr_vk_sids_from_orders":_safe_div(vk_sids_rub * 100, orders_rub),
            "vk_sids_views":   vk_sids_views,
            "vk_sids_clicks":  vk_sids_clicks,
            "ctr_vk_sids":     _safe_div((vk_sids_clicks or 0) * 100, vk_sids_views) if vk_sids_views else None,
            "vk_sids_orders":  vk_sids_orders,
            "cpo_vk_sids":     _safe_div(vk_sids_rub, vk_sids_orders),
            # SIDS Contractor
            "sids_contractor_rub":            sids_c_rub or None,
            "drr_sids_contractor_from_sales": _safe_div(sids_c_rub * 100, sales_rub),
            "drr_sids_contractor_from_orders":_safe_div(sids_c_rub * 100, orders_rub),
            "sids_contractor_views":  sids_c_views,
            "sids_contractor_clicks": sids_c_clicks,
            "ctr_sids_contractor":    _safe_div((sids_c_clicks or 0) * 100, sids_c_views) if sids_c_views else None,
            "sids_contractor_orders": sids_c_orders,
            "cpo_sids_contractor":    _safe_div(sids_c_rub, sids_c_orders),
            # Яндекс
            "yandex_contractor_rub":            ya_rub or None,
            "drr_yandex_contractor_from_sales": _safe_div(ya_rub * 100, sales_rub),
            "drr_yandex_contractor_from_orders":_safe_div(ya_rub * 100, orders_rub),
            "yandex_contractor_views":  ya_views,
            "yandex_contractor_clicks": ya_clicks,
            "ctr_yandex_contractor":    _safe_div((ya_clicks or 0) * 100, ya_views) if ya_views else None,
            "yandex_contractor_orders": ya_orders,
            "cpo_yandex_contractor":    _safe_div(ya_rub, ya_orders),
            # Маржа
            "margin_before_ads_rub": margin_before_ads_rub,
            "margin_before_ads_pct": margin_before_ads_pct,
            "margin_rub":            margin_rub,
            "margin_pct":            margin_pct,
            # Прогноз
            "sales_forecast_rub":  sales_fc_rub,
            "margin_forecast_rub": margin_fc_rub,
            "margin_forecast_pct": _safe_div((margin_fc_rub or 0) * 100, sales_fc_rub) if margin_fc_rub and sales_fc_rub else None,
        })

    return result
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/analytics_api/test_rnp_metrics.py -v
```

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/rnp.py tests/analytics_api/test_rnp_metrics.py
git commit -m "feat(rnp): week aggregation + all 77 derived metrics"
```

---

## Task 3: Google Sheets readers (digital channels + bloggers)

**Files:**
- Modify: `shared/data_layer/rnp.py` (append two functions)

- [ ] **Step 1: Append `fetch_rnp_sheets_digital` to `shared/data_layer/rnp.py`**

```python
def _parse_sheet_date(raw: str) -> Optional[date]:
    """Parse DD.MM.YYYY or YYYY-MM-DD sheet date strings."""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(raw) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def fetch_rnp_sheets_digital(
    date_from: date,
    date_to: date,
    model: str,
    sa_file: str,
    spreadsheet_id: str,
) -> dict[str, dict]:
    """
    Read ADS/ADB/EPS sheets from the external-ads spreadsheet.
    Returns dict keyed by ISO week_start string; values accumulate channel spend/views/clicks/orders.

    Column layout (confirmed for ADS, assumed identical for ADB/EPS):
      0=Дата, 1=Артикул, 2=Товар (model filter), 3=Цвет,
      4=Spend(E), 5=Views(F), 6=Clicks(G), 11=Orders(L)
    """
    from shared.clients.sheets_client import get_client

    SHEET_TO_PREFIX = {
        "Отчет ADS ежедневный": "vk_sids",
        "Отчет ADB ежедневный": "sids_contractor",
        "Отчет EPS ежедневный": "yandex_contractor",
    }
    COL = {"date": 0, "model": 2, "spend": 4, "views": 5, "clicks": 6, "orders": 11}

    weekly: dict[str, dict] = {}
    try:
        gc = get_client(sa_file)
        ss = gc.open_by_key(spreadsheet_id)
    except Exception as exc:
        logger.warning("Sheets digital: failed to open spreadsheet: %s", exc)
        return weekly

    for sheet_name, prefix in SHEET_TO_PREFIX.items():
        try:
            ws = ss.worksheet(sheet_name)
            rows = ws.get_all_values()
        except Exception as exc:
            logger.warning("Sheets digital: sheet '%s' unavailable: %s", sheet_name, exc)
            continue

        for row in rows[1:]:  # skip header row
            if len(row) <= COL["orders"]:
                continue
            row_date = _parse_sheet_date(row[COL["date"]])
            if row_date is None or not (date_from <= row_date <= date_to):
                continue
            if row[COL["model"]].lower().strip() != model.lower():
                continue

            wk = _week_start(row_date).isoformat()
            if wk not in weekly:
                weekly[wk] = {}
            b = weekly[wk]

            for field, col_idx in [
                (f"{prefix}_rub",    COL["spend"]),
                (f"{prefix}_views",  COL["views"]),
                (f"{prefix}_clicks", COL["clicks"]),
                (f"{prefix}_orders", COL["orders"]),
            ]:
                val = _to_float(row[col_idx])
                if val is not None:
                    b[field] = b.get(field, 0.0) + val

    return weekly


def fetch_rnp_sheets_bloggers(
    date_from: date,
    date_to: date,
    model: str,
    sa_file: str,
    spreadsheet_id: str,
    sheet_name: str = "Блогеры",
) -> dict[str, dict]:
    """
    Read the Bloggers sheet. Returns dict keyed by ISO week_start.
    Column layout (from GAS script):
      5=Дата кампании, 6=Модель, 13=Бюджет,
      23=Просмотры, 25=Клики, 28=Корзины, 30=Заказы
    """
    from shared.clients.sheets_client import get_client

    COL = {
        "date": 5, "model": 6, "spend": 13,
        "views": 23, "clicks": 25, "carts": 28, "orders": 30,
    }
    weekly: dict[str, dict] = {}
    try:
        gc = get_client(sa_file)
        ws = gc.open_by_key(spreadsheet_id).worksheet(sheet_name)
        rows = ws.get_all_values()
    except Exception as exc:
        logger.warning("Sheets bloggers: unavailable: %s", exc)
        return weekly

    for row in rows[1:]:
        max_col = max(COL.values())
        if len(row) <= max_col:
            continue
        row_date = _parse_sheet_date(row[COL["date"]])
        if row_date is None or not (date_from <= row_date <= date_to):
            continue
        if row[COL["model"]].lower().strip() != model.lower():
            continue

        wk = _week_start(row_date).isoformat()
        b = weekly.setdefault(wk, {})

        spend = _to_float(row[COL["spend"]]) or 0.0
        b["blogger_rub"] = b.get("blogger_rub", 0.0) + spend

        has_stats = False
        for field, col_idx in [
            ("blogger_views", COL["views"]),
            ("blogger_clicks", COL["clicks"]),
            ("blogger_carts", COL["carts"]),
            ("blogger_orders", COL["orders"]),
        ]:
            val = _to_float(row[col_idx])
            if val is not None:
                b[field] = b.get(field, 0.0) + val
                has_stats = True

        # no_stats = budget exists but all stats columns empty
        if spend > 0 and not has_stats:
            b["blogger_no_stats"] = b.get("blogger_no_stats", True)
        else:
            b["blogger_no_stats"] = False

    return weekly
```

- [ ] **Step 2: Update `shared/data_layer/__init__.py`**

Add at the end:

```python
from shared.data_layer.rnp import *          # noqa: F401,F403
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from shared.data_layer import aggregate_to_weeks, fetch_rnp_wb_daily; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add shared/data_layer/rnp.py shared/data_layer/__init__.py
git commit -m "feat(rnp): Google Sheets readers — digital channels + bloggers"
```

---

## Task 4: FastAPI service scaffold

**Files:**
- Create: `services/analytics_api/__init__.py`
- Create: `services/analytics_api/app.py`
- Create: `services/analytics_api/requirements.txt`

- [ ] **Step 1: Create `services/analytics_api/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Create `services/analytics_api/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
gspread>=6.0.0
google-auth>=2.20.0
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
pytz>=2023.3
```

- [ ] **Step 3: Create `services/analytics_api/app.py` with health + auth + models endpoint**

```python
"""Analytics API — РНП (Рука на Пульсе) weekly analytics dashboard backend.

    GET /health              — healthcheck
    GET /api/rnp/models      — list of available WB models
    GET /api/rnp/weeks       — weekly analytics for one model
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

ANALYTICS_API_KEY = os.getenv("ANALYTICS_API_KEY", "")
GOOGLE_SA_FILE    = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "services/sheets_sync/credentials/google_sa.json")
RNP_EXT_ADS_SHEET_ID  = os.getenv("RNP_EXT_ADS_SHEET_ID", "")
RNP_BLOGGERS_SHEET_ID = os.getenv("RNP_BLOGGERS_SHEET_ID", "")

app = FastAPI(title="Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("analytics_api")

MAX_PERIOD_DAYS = 91  # 13 weeks


def _verify_key(x_api_key: str = Header(...)) -> None:
    if not ANALYTICS_API_KEY:
        raise HTTPException(500, "ANALYTICS_API_KEY not configured")
    if x_api_key != ANALYTICS_API_KEY:
        raise HTTPException(403, "Invalid API key")


def _align_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _align_sunday(d: date) -> date:
    return d + timedelta(days=(6 - d.weekday()))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/rnp/models")
def rnp_models(
    marketplace: str = Query("wb"),
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)
    if marketplace != "wb":
        raise HTTPException(501, "Only marketplace=wb supported in Phase 1")
    from shared.data_layer.rnp import fetch_rnp_models_wb
    models = fetch_rnp_models_wb()
    return {"marketplace": marketplace, "models": models}


@app.get("/api/rnp/weeks")
def rnp_weeks(
    model: str = Query(...),
    date_from: date = Query(...),
    date_to: date   = Query(...),
    marketplace: str          = Query("wb"),
    buyout_forecast: Optional[float] = Query(None, ge=0.0, le=1.0),
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)

    if marketplace != "wb":
        raise HTTPException(501, "Only marketplace=wb supported in Phase 1")

    # Align to week boundaries
    date_from = _align_monday(date_from)
    date_to   = _align_sunday(date_to)

    if (date_to - date_from).days > MAX_PERIOD_DAYS:
        raise HTTPException(400, "Period exceeds 13 weeks maximum")

    from shared.data_layer.rnp import (
        fetch_rnp_wb_daily,
        fetch_rnp_sheets_digital,
        fetch_rnp_sheets_bloggers,
        aggregate_to_weeks,
    )

    # Fetch WB DB data
    daily_rows = fetch_rnp_wb_daily(model, date_from, date_to)

    # Fetch Sheets data (fail gracefully)
    ext_ads_available = True
    sheets_data: dict = {}
    try:
        if RNP_EXT_ADS_SHEET_ID:
            digital = fetch_rnp_sheets_digital(
                date_from, date_to, model, GOOGLE_SA_FILE, RNP_EXT_ADS_SHEET_ID
            )
            for wk, ch_data in digital.items():
                sheets_data.setdefault(wk, {}).update(ch_data)

        if RNP_BLOGGERS_SHEET_ID:
            bloggers = fetch_rnp_sheets_bloggers(
                date_from, date_to, model, GOOGLE_SA_FILE, RNP_BLOGGERS_SHEET_ID
            )
            for wk, bl_data in bloggers.items():
                sheets_data.setdefault(wk, {}).update(bl_data)
    except Exception as exc:
        logger.warning("Sheets unavailable, returning DB-only data: %s", exc)
        ext_ads_available = False
        sheets_data = {}

    weeks = aggregate_to_weeks(daily_rows, sheets_data, buyout_forecast)

    # Compute period-level buyout used
    tot_orders = sum(w.get("orders_qty") or 0 for w in weeks)
    tot_sales  = sum(w.get("sales_qty") or 0 for w in weeks)
    buyout_used = (tot_sales / tot_orders) if tot_orders > 0 else buyout_forecast or 0.87

    return {
        "model":              model,
        "marketplace":        marketplace,
        "date_from":          date_from.isoformat(),
        "date_to":            date_to.isoformat(),
        "buyout_forecast_used": round(buyout_used, 4),
        "ext_ads_available":  ext_ads_available,
        "weeks":              weeks,
    }
```

- [ ] **Step 4: Test health endpoint locally**

```bash
cd /Users/danilamatveev/Projects/Wookiee
uvicorn services.analytics_api.app:app --port 8005 &
sleep 2
curl -s http://localhost:8005/health
```

Expected: `{"status":"ok"}`

```bash
curl -s -H "X-Api-Key: test" http://localhost:8005/api/rnp/models 2>&1 | head -5
# Expected: 500 (key not configured) — that's correct for local test without env
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add services/analytics_api/
git commit -m "feat(rnp): FastAPI service — health, models, weeks endpoints"
```

---

## Task 5: Deployment

**Files:**
- Modify: `.env` (add new vars)
- Modify: `/etc/caddy/Caddyfile` on server (via SSH)
- Create: systemd service file (or update existing supervisor config)

- [ ] **Step 1: Add env vars to `.env`**

```bash
# Add to .env (not .env.example):
ANALYTICS_API_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
RNP_EXT_ADS_SHEET_ID=1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU
RNP_BLOGGERS_SHEET_ID=<id of bloggers spreadsheet>
```

- [ ] **Step 2: Deploy to server**

```bash
ssh timeweb "cd /path/to/Wookiee && git pull && pip install -r services/analytics_api/requirements.txt"
```

- [ ] **Step 3: Add Caddy block on server**

On the server, add to Caddyfile:
```
analytics-api.os.wookiee.shop {
    reverse_proxy localhost:8005
}
```

Then: `sudo systemctl reload caddy`

- [ ] **Step 4: Start service (follow existing pattern)**

Check how other services are started:
```bash
ssh timeweb "ls /etc/systemd/system/ | grep wookiee"
```

Create `/etc/systemd/system/wookiee-analytics-api.service` following existing pattern, then:
```bash
ssh timeweb "sudo systemctl enable wookiee-analytics-api && sudo systemctl start wookiee-analytics-api"
```

- [ ] **Step 5: Smoke test deployed endpoint**

```bash
curl -s -H "X-Api-Key: $ANALYTICS_API_KEY" \
  "https://analytics-api.os.wookiee.shop/health"
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit env example update**

```bash
# Add placeholder to .env.example:
echo "ANALYTICS_API_KEY=" >> .env.example
echo "RNP_EXT_ADS_SHEET_ID=" >> .env.example
echo "RNP_BLOGGERS_SHEET_ID=" >> .env.example
git add .env.example
git commit -m "chore: add analytics API env vars to .env.example"
```

---

## Task 6: TypeScript types + API client

**Files:**
- Create: `wookiee-hub/src/types/rnp.ts`
- Create: `wookiee-hub/src/api/rnp.ts`

- [ ] **Step 1: Create `wookiee-hub/src/types/rnp.ts`**

```typescript
export type RnpPhase = "norm" | "decline" | "recovery"

export interface RnpWeek {
  week_start: string
  week_end: string
  week_label: string
  phase: RnpPhase
  // Заказы
  orders_qty: number | null
  orders_rub: number | null
  orders_spp_rub: number | null
  avg_order_rub: number | null
  avg_order_spp_rub: number | null
  spp_pct: number | null
  // Продажи
  sales_qty: number | null
  buyout_pct: number | null
  sales_rub: number | null
  avg_sale_rub: number | null
  // Воронка
  clicks_total: number | null
  cart_total: number | null
  cr_card_to_cart: number | null
  cr_cart_to_order: number | null
  cr_total: number | null
  // Реклама итого
  adv_total_rub: number | null
  drr_total_from_sales: number | null
  drr_total_from_orders: number | null
  // Внутренняя реклама
  adv_internal_rub: number | null
  drr_internal_from_sales: number | null
  drr_internal_from_orders: number | null
  orders_organic_qty: number | null
  orders_internal_qty: number | null
  adv_views: number | null
  adv_clicks: number | null
  ctr_internal: number | null
  cpc_internal: number | null
  cpo_internal: number | null
  cpm_internal: number | null
  adv_internal_profit_forecast: number | null
  romi_internal: number | null
  // Внешняя реклама итого
  adv_external_rub: number | null
  drr_external_from_sales: number | null
  drr_external_from_orders: number | null
  ext_views: number | null
  ext_clicks: number | null
  ctr_external: number | null
  // Блогеры
  blogger_rub: number | null
  drr_blogger_from_sales: number | null
  drr_blogger_from_orders: number | null
  blogger_views: number | null
  blogger_clicks: number | null
  ctr_blogger: number | null
  blogger_carts: number | null
  blogger_orders: number | null
  blogger_profit_forecast: number | null
  romi_blogger: number | null
  blogger_no_stats: boolean
  // ВК SIDS
  vk_sids_rub: number | null
  drr_vk_sids_from_sales: number | null
  drr_vk_sids_from_orders: number | null
  vk_sids_views: number | null
  vk_sids_clicks: number | null
  ctr_vk_sids: number | null
  vk_sids_orders: number | null
  cpo_vk_sids: number | null
  // SIDS Contractor
  sids_contractor_rub: number | null
  drr_sids_contractor_from_sales: number | null
  drr_sids_contractor_from_orders: number | null
  sids_contractor_views: number | null
  sids_contractor_clicks: number | null
  ctr_sids_contractor: number | null
  sids_contractor_orders: number | null
  cpo_sids_contractor: number | null
  // Яндекс
  yandex_contractor_rub: number | null
  drr_yandex_contractor_from_sales: number | null
  drr_yandex_contractor_from_orders: number | null
  yandex_contractor_views: number | null
  yandex_contractor_clicks: number | null
  ctr_yandex_contractor: number | null
  yandex_contractor_orders: number | null
  cpo_yandex_contractor: number | null
  // Маржа
  margin_before_ads_rub: number | null
  margin_before_ads_pct: number | null
  margin_rub: number | null
  margin_pct: number | null
  // Прогноз
  sales_forecast_rub: number | null
  margin_forecast_rub: number | null
  margin_forecast_pct: number | null
}

export interface RnpResponse {
  model: string
  marketplace: string
  date_from: string
  date_to: string
  buyout_forecast_used: number
  ext_ads_available: boolean
  weeks: RnpWeek[]
}

export interface RnpModelsResponse {
  marketplace: string
  models: string[]
}
```

- [ ] **Step 2: Create `wookiee-hub/src/api/rnp.ts`**

```typescript
import type { RnpResponse, RnpModelsResponse } from "@/types/rnp"

const BASE = import.meta.env.VITE_ANALYTICS_API_URL ?? "https://analytics-api.os.wookiee.shop"
const KEY  = import.meta.env.VITE_ANALYTICS_API_KEY ?? ""

const headers = { "X-Api-Key": KEY }

export async function fetchRnpModels(): Promise<RnpModelsResponse> {
  const res = await fetch(`${BASE}/api/rnp/models?marketplace=wb`, { headers })
  if (!res.ok) throw new Error(`fetchRnpModels: ${res.status}`)
  return res.json()
}

export async function fetchRnpWeeks(params: {
  model: string
  dateFrom: string  // YYYY-MM-DD
  dateTo: string
  buyoutForecast?: number
}): Promise<RnpResponse> {
  const url = new URL(`${BASE}/api/rnp/weeks`)
  url.searchParams.set("model", params.model)
  url.searchParams.set("date_from", params.dateFrom)
  url.searchParams.set("date_to", params.dateTo)
  if (params.buyoutForecast !== undefined) {
    url.searchParams.set("buyout_forecast", String(params.buyoutForecast))
  }
  const res = await fetch(url.toString(), { headers })
  if (!res.ok) throw new Error(`fetchRnpWeeks: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Add env vars to Hub**

In `wookiee-hub/.env.local` (create if missing):
```
VITE_ANALYTICS_API_URL=https://analytics-api.os.wookiee.shop
VITE_ANALYTICS_API_KEY=<same key as ANALYTICS_API_KEY>
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/types/rnp.ts wookiee-hub/src/api/rnp.ts
git commit -m "feat(rnp): TypeScript types + API client"
```

---

## Task 7: Navigation + routing + RnpHelpBlock

**Files:**
- Modify: `wookiee-hub/src/config/navigation.ts`
- Modify: `wookiee-hub/src/router.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-help-block.tsx`
- Create: `wookiee-hub/src/pages/analytics/rnp.tsx` (skeleton)

- [ ] **Step 1: Update `wookiee-hub/src/config/navigation.ts`**

Add import at top:
```typescript
import { TrendingUp, Activity } from "lucide-react"
```

Append to `navigationGroups` array:
```typescript
  {
    id: "analytics",
    icon: TrendingUp,
    label: "Аналитика",
    items: [
      { id: "rnp", label: "Рука на пульсе", icon: Activity, path: "/analytics/rnp" },
    ],
  },
```

- [ ] **Step 2: Update `wookiee-hub/src/router.tsx`**

Add import:
```typescript
import { RnpPage } from "@/pages/analytics/rnp"
```

Add routes inside the protected children array:
```typescript
{ path: "/analytics",      element: <Navigate to="/analytics/rnp" replace /> },
{ path: "/analytics/rnp",  element: <RnpPage /> },
```

- [ ] **Step 3: Create `wookiee-hub/src/components/analytics/rnp-help-block.tsx`**

```tsx
import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

export function RnpHelpBlock() {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-lg border bg-muted/30 px-4 py-3">
      <button
        className="flex w-full items-center justify-between text-sm font-medium"
        onClick={() => setOpen(!open)}
      >
        <span>РНП — Рука на пульсе: как читать дашборд</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="mt-3 space-y-2 text-sm text-muted-foreground">
          <p>Дашборд показывает недельную динамику по выбранной модели. Данные обновляются ежедневно (T−1).</p>
          <p>
            <strong>Фазы недель:</strong>{" "}
            <span className="text-[#185FA5] font-medium">■ Норма</span> — маржа ≥ 15% &nbsp;
            <span className="text-[#1D9E75] font-medium">■ Восстановление</span> — 10–15% &nbsp;
            <span className="text-[#E24B4A] font-medium">■ Спад</span> — маржа &lt; 10%
          </p>
          <p>
            <strong>Выкуп %</strong> — лаговый показатель (3–21 дней). Последние недели занижены.
          </p>
          <p>
            <strong>Клики и корзина</strong> (воронка) — данные WB content_analysis, возможно расхождение ~20% с другими отчётами.
          </p>
          <p>
            <strong>Прогноз</strong> — считается на основе прогнозного выкупа (по умолчанию = фактический за период).
          </p>
          <p>Кликните по серии в легенде графика, чтобы скрыть/показать её.</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create skeleton `wookiee-hub/src/pages/analytics/rnp.tsx`**

```tsx
export function RnpPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Рука на пульсе</h1>
      <p className="text-muted-foreground text-sm">Загрузка...</p>
    </div>
  )
}
```

- [ ] **Step 5: Start Hub dev server and check navigation**

```bash
cd wookiee-hub && npm run dev
```

Open http://localhost:5173 → Sidebar should show "Аналитика → Рука на пульсе" → clicking opens the skeleton page.

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/config/navigation.ts wookiee-hub/src/router.tsx \
        wookiee-hub/src/components/analytics/ wookiee-hub/src/pages/analytics/
git commit -m "feat(rnp): navigation, routing, RnpHelpBlock"
```

---

## Task 8: RnpFilters + RnpSummaryCards

**Files:**
- Create: `wookiee-hub/src/components/analytics/rnp-filters.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-summary-cards.tsx`

Phase colors constant (used in multiple components — define once in filters, import elsewhere):

```typescript
export const PHASE_COLORS: Record<string, string> = {
  norm:     "#185FA5",
  decline:  "#E24B4A",
  recovery: "#1D9E75",
}
```

- [ ] **Step 1: Create `wookiee-hub/src/components/analytics/rnp-filters.tsx`**

```tsx
import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { fetchRnpModels } from "@/api/rnp"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const PHASE_COLORS: Record<string, string> = {
  norm: "#185FA5", decline: "#E24B4A", recovery: "#1D9E75",
}

function mondayOf(d: Date): string {
  const day = d.getDay()
  const diff = (day === 0 ? -6 : 1 - day)
  const mon = new Date(d)
  mon.setDate(d.getDate() + diff)
  return mon.toISOString().slice(0, 10)
}

function sundayOf(d: Date): string {
  const mon = new Date(mondayOf(d))
  mon.setDate(mon.getDate() + 6)
  return mon.toISOString().slice(0, 10)
}

function weeksAgo(n: number): { from: string; to: string } {
  const today = new Date()
  const sun = new Date(sundayOf(new Date(today.setDate(today.getDate() - 7))))
  const mon = new Date(sun)
  mon.setDate(sun.getDate() - (n - 1) * 7 - 6)
  return { from: mon.toISOString().slice(0, 10), to: sun.toISOString().slice(0, 10) }
}

interface RnpFiltersProps {
  onApply: (params: { model: string; dateFrom: string; dateTo: string }) => void
  loading: boolean
}

export function RnpFilters({ onApply, loading }: RnpFiltersProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [models, setModels] = useState<string[]>([])

  const model    = searchParams.get("model") ?? ""
  const dateFrom = searchParams.get("from")  ?? weeksAgo(8).from
  const dateTo   = searchParams.get("to")    ?? weeksAgo(8).to

  useEffect(() => {
    fetchRnpModels().then(r => setModels(r.models)).catch(() => {})
  }, [])

  function setParam(key: string, value: string) {
    const p = new URLSearchParams(searchParams)
    p.set(key, value)
    setSearchParams(p)
  }

  function applyPreset(n: number) {
    const { from, to } = weeksAgo(n)
    const p = new URLSearchParams(searchParams)
    p.set("from", from); p.set("to", to)
    setSearchParams(p)
  }

  function handleApply() {
    if (!model) return
    onApply({ model, dateFrom, dateTo })
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Модель</label>
        <Select value={model} onValueChange={v => setParam("model", v)}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Выберите модель" />
          </SelectTrigger>
          <SelectContent>
            {models.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Период</label>
        <div className="flex gap-1">
          {[4, 8, 12].map(n => (
            <Button key={n} variant="outline" size="sm" onClick={() => applyPreset(n)}>
              {n} нед.
            </Button>
          ))}
          <input
            type="date"
            className="h-9 rounded-md border px-2 text-sm"
            value={dateFrom}
            onChange={e => setParam("from", e.target.value)}
          />
          <span className="self-center text-muted-foreground">—</span>
          <input
            type="date"
            className="h-9 rounded-md border px-2 text-sm"
            value={dateTo}
            onChange={e => setParam("to", e.target.value)}
          />
        </div>
      </div>

      <Button onClick={handleApply} disabled={!model || loading}>
        {loading ? "Загрузка..." : "Обновить"}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Create `wookiee-hub/src/components/analytics/rnp-summary-cards.tsx`**

```tsx
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "./rnp-filters"

function fmt(n: number | null, decimals = 0): string {
  if (n === null || n === undefined) return "—"
  return n.toLocaleString("ru-RU", { maximumFractionDigits: decimals })
}

function sumField(weeks: RnpWeek[], field: keyof RnpWeek): number {
  return weeks.reduce((acc, w) => acc + ((w[field] as number) ?? 0), 0)
}

function wavgField(weeks: RnpWeek[], numField: keyof RnpWeek, denomField: keyof RnpWeek): number | null {
  const num = sumField(weeks, numField)
  const den = sumField(weeks, denomField)
  return den > 0 ? (num / den) * 100 : null
}

interface CardProps {
  label: string
  value: string
  sub?: string
  accent?: string
}

function Card({ label, value, sub, accent }: CardProps) {
  return (
    <div className="rounded-lg border bg-card p-4 flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-2xl font-bold" style={accent ? { color: accent } : {}}>
        {value}
      </span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  )
}

interface RnpSummaryCardsProps {
  weeks: RnpWeek[]
}

export function RnpSummaryCards({ weeks }: RnpSummaryCardsProps) {
  if (!weeks.length) return null

  const ordersQty  = sumField(weeks, "orders_qty")
  const ordersRub  = sumField(weeks, "orders_rub")
  const salesQty   = sumField(weeks, "sales_qty")
  const salesRub   = sumField(weeks, "sales_rub")

  const mbaRub = sumField(weeks, "margin_before_ads_rub")
  const mbaPct = salesRub > 0 ? (mbaRub / salesRub) * 100 : null

  const mRub  = sumField(weeks, "margin_rub")
  const mPct  = salesRub > 0 ? (mRub / salesRub) * 100 : null
  const mPhase = mPct !== null
    ? mPct >= 15 ? "norm" : mPct < 10 ? "decline" : "recovery"
    : "recovery"

  const drrPct = wavgField(weeks, "adv_total_rub", "orders_rub")

  const mfRub = sumField(weeks, "margin_forecast_rub")
  const sfRub = sumField(weeks, "sales_forecast_rub")
  const mfPct = sfRub > 0 ? (mfRub / sfRub) * 100 : null

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <Card
        label="Заказы"
        value={fmt(ordersQty)}
        sub={`${fmt(ordersRub / 1000)} тыс. ₽`}
      />
      <Card
        label="Продажи"
        value={fmt(salesQty)}
        sub={`${fmt(salesRub / 1000)} тыс. ₽`}
      />
      <Card
        label="Маржа до рекламы"
        value={mbaPct !== null ? `${fmt(mbaPct, 1)}%` : "—"}
        sub={`${fmt(mbaRub / 1000)} тыс. ₽`}
        accent="#185FA5"
      />
      <Card
        label="Маржа после рекламы"
        value={mPct !== null ? `${fmt(mPct, 1)}%` : "—"}
        sub={`${fmt(mRub / 1000)} тыс. ₽`}
        accent={PHASE_COLORS[mPhase]}
      />
      <Card
        label="ДРР итого (от заказов)"
        value={drrPct !== null ? `${fmt(drrPct, 1)}%` : "—"}
        accent={drrPct !== null && drrPct > 25 ? "#E24B4A" : undefined}
      />
      <Card
        label="Прогноз маржи"
        value={mfPct !== null ? `${fmt(mfPct, 1)}%` : "—"}
        sub={`${fmt(mfRub / 1000)} тыс. ₽`}
      />
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/components/analytics/rnp-filters.tsx \
        wookiee-hub/src/components/analytics/rnp-summary-cards.tsx
git commit -m "feat(rnp): RnpFilters + RnpSummaryCards (6 cards)"
```

---

## Task 9: Chart tabs — Orders & Funnel

**Files:**
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-orders.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-funnel.tsx`

Shared chart boilerplate (used in every tab):

```typescript
// Pattern for all tabs:
// 1. const [hidden, setHidden] = useState<Set<string>>(new Set())
// 2. function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }
// 3. Phase Cell coloring on Bar items
// 4. Dual YAxis: yAxisId="left" and yAxisId="right"
// 5. Tooltip formatter: null values → "—"
```

- [ ] **Step 1: Create `wookiee-hub/src/components/analytics/rnp-tabs/tab-orders.tsx`**

```tsx
import { useState } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Cell, ResponsiveContainer
} from "recharts"
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "../rnp-filters"

function fmt(v: number | null, dec = 0) {
  return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec })
}

function isLagged(weekEnd: string): boolean {
  const d = new Date(weekEnd)
  const now = new Date()
  return (now.getTime() - d.getTime()) / 86400000 < 21
}

interface Props { weeks: RnpWeek[] }

export function TabOrders({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) {
    setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s })
  }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip
            formatter={(val: number | null, name: string) =>
              [val === null ? "—" : typeof val === "number" && name.includes("pct")
                ? `${val.toFixed(1)}%` : val?.toLocaleString("ru-RU"), name]
            }
          />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />

          <Bar yAxisId="left" dataKey="orders_qty" name="Заказы (шт.)" hide={hidden.has("orders_qty")}>
            {weeks.map(w => (
              <Cell
                key={w.week_start}
                fill={PHASE_COLORS[w.phase]}
                stroke={isLagged(w.week_end) ? "#888" : "none"}
                strokeDasharray={isLagged(w.week_end) ? "4 2" : "0"}
                strokeWidth={isLagged(w.week_end) ? 2 : 0}
              />
            ))}
          </Bar>
          <Line yAxisId="left" dataKey="sales_qty" name="Продажи (шт.)" stroke="#f59e0b" dot={false} hide={hidden.has("sales_qty")} />
          <Line yAxisId="right" dataKey="buyout_pct" name="Выкуп %" stroke="#8b5cf6" dot={false} strokeDasharray="5 3" hide={hidden.has("buyout_pct")} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Data table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b">
              {["Неделя","Заказы шт","Заказы ₽","Продажи шт","Продажи ₽","Чек ₽","СПП %","Выкуп % ⚠"].map(h => (
                <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map(w => (
              <tr key={w.week_start} className="border-b hover:bg-muted/30">
                <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
                <td className="py-1 px-2">{fmt(w.orders_qty)}</td>
                <td className="py-1 px-2">{fmt(w.orders_rub)}</td>
                <td className="py-1 px-2">{fmt(w.sales_qty)}</td>
                <td className="py-1 px-2">{fmt(w.sales_rub)}</td>
                <td className="py-1 px-2">{fmt(w.avg_order_rub)}</td>
                <td className="py-1 px-2">{fmt(w.spp_pct, 1)}{w.spp_pct !== null ? "%" : ""}</td>
                <td className="py-1 px-2">
                  {fmt(w.buyout_pct, 1)}{w.buyout_pct !== null ? "%" : ""}
                  {isLagged(w.week_end) && <span className="ml-1 text-amber-500">⚠</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `wookiee-hub/src/components/analytics/rnp-tabs/tab-funnel.tsx`**

```tsx
import { useState } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Cell, ResponsiveContainer
} from "recharts"
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "../rnp-filters"

function fmt(v: number | null, dec = 0) {
  return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec })
}

interface Props { weeks: RnpWeek[] }

export function TabFunnel({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) {
    setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s })
  }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="clicks_total" name="Клики (всего)" hide={hidden.has("clicks_total")}>
            {weeks.map(w => <Cell key={w.week_start} fill={PHASE_COLORS[w.phase]} />)}
          </Bar>
          <Bar yAxisId="left" dataKey="cart_total" name="Корзина" fill="#f59e0b" hide={hidden.has("cart_total")} />
          <Line yAxisId="right" dataKey="cr_total" name="CR клик→заказ %" stroke="#8b5cf6" dot={false} hide={hidden.has("cr_total")} />
          <Line yAxisId="right" dataKey="cr_card_to_cart" name="CR карточка→корзина %" stroke="#10b981" dot={false} hide={hidden.has("cr_card_to_cart")} />
          <Line yAxisId="right" dataKey="cr_cart_to_order" name="CR корзина→заказ %" stroke="#f43f5e" dot={false} hide={hidden.has("cr_cart_to_order")} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b">
              {["Неделя","Клики","Корзина","CR клик→заказ","CR карточка→корзина","CR корзина→заказ"].map(h => (
                <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map(w => (
              <tr key={w.week_start} className="border-b hover:bg-muted/30">
                <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
                <td className="py-1 px-2">{fmt(w.clicks_total)}</td>
                <td className="py-1 px-2">{fmt(w.cart_total)}</td>
                <td className="py-1 px-2">{fmt(w.cr_total, 2)}{w.cr_total !== null ? "%" : ""}</td>
                <td className="py-1 px-2">{fmt(w.cr_card_to_cart, 2)}{w.cr_card_to_cart !== null ? "%" : ""}</td>
                <td className="py-1 px-2">{fmt(w.cr_cart_to_order, 2)}{w.cr_cart_to_order !== null ? "%" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/components/analytics/rnp-tabs/
git commit -m "feat(rnp): TabOrders + TabFunnel with phase coloring and lag markers"
```

---

## Task 10: Chart tabs — Ads (total, internal, external) + Margin

**Files:**
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-total.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-internal.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-ads-external.tsx`
- Create: `wookiee-hub/src/components/analytics/rnp-tabs/tab-margin.tsx`

- [ ] **Step 1: Create `tab-ads-total.tsx`**

```tsx
import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsTotal({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="adv_internal_rub" name="Внутренняя реклама ₽" stackId="adv" fill="#185FA5" hide={hidden.has("adv_internal_rub")} />
          <Bar yAxisId="left" dataKey="adv_external_rub" name="Внешняя реклама ₽" stackId="adv" fill="#f59e0b" hide={hidden.has("adv_external_rub")} />
          <Line yAxisId="right" dataKey="drr_total_from_orders" name="ДРР итого (от заказов) %" stroke="#E24B4A" dot={false} hide={hidden.has("drr_total_from_orders")} />
          <Line yAxisId="right" dataKey="drr_internal_from_orders" name="ДРР внутр. %" stroke="#8b5cf6" dot={false} strokeDasharray="4 2" hide={hidden.has("drr_internal_from_orders")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя","Реклама итого ₽","Внутр. ₽","Внешн. ₽","ДРР итого %","ДРР внутр. %","ДРР внешн. %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.adv_total_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_internal_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_external_rub)}</td>
              <td className="py-1 px-2">{fmt(w.drr_total_from_orders, 1)}{w.drr_total_from_orders !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.drr_internal_from_orders, 1)}{w.drr_internal_from_orders !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.drr_external_from_orders, 1)}{w.drr_external_from_orders !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `tab-ads-internal.tsx`**

```tsx
import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsInternal({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="adv_views" name="Показы" fill="#185FA5" opacity={0.7} hide={hidden.has("adv_views")} />
          <Bar yAxisId="left" dataKey="orders_internal_qty" name="Заказы от рекламы" fill="#1D9E75" hide={hidden.has("orders_internal_qty")} />
          <Line yAxisId="right" dataKey="ctr_internal" name="CTR %" stroke="#f59e0b" dot={false} hide={hidden.has("ctr_internal")} />
          <Line yAxisId="right" dataKey="romi_internal" name="ROMI %" stroke="#8b5cf6" dot={false} hide={hidden.has("romi_internal")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя","Расход ₽","Показы","Клики","CTR %","CPC ₽","CPO ₽","CPM ₽","ROMI %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.adv_internal_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_views)}</td>
              <td className="py-1 px-2">{fmt(w.adv_clicks)}</td>
              <td className="py-1 px-2">{fmt(w.ctr_internal, 2)}{w.ctr_internal !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.cpc_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.cpo_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.cpm_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.romi_internal, 1)}{w.romi_internal !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `tab-ads-external.tsx`**

```tsx
import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsExternal({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="blogger_rub" name="Блогеры ₽" stackId="ext" fill="#185FA5" hide={hidden.has("blogger_rub")} />
          <Bar yAxisId="left" dataKey="vk_sids_rub" name="ВК SIDS ₽" stackId="ext" fill="#1D9E75" hide={hidden.has("vk_sids_rub")} />
          <Bar yAxisId="left" dataKey="sids_contractor_rub" name="SIDS Contractor ₽" stackId="ext" fill="#f59e0b" hide={hidden.has("sids_contractor_rub")} />
          <Bar yAxisId="left" dataKey="yandex_contractor_rub" name="Яндекс ₽" stackId="ext" fill="#8b5cf6" hide={hidden.has("yandex_contractor_rub")} />
          <Line yAxisId="right" dataKey="ctr_external" name="CTR внешн. %" stroke="#E24B4A" dot={false} hide={hidden.has("ctr_external")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя","Блогеры ₽","ROMI %","Просм.","Клики","ВК SIDS ₽","CPO ₽","SIDS C. ₽","Яндекс ₽"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.blogger_rub)}{w.blogger_no_stats ? " ⚠" : ""}</td>
              <td className="py-1 px-2">{fmt(w.romi_blogger, 1)}{w.romi_blogger !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.blogger_views)}</td>
              <td className="py-1 px-2">{fmt(w.blogger_clicks)}</td>
              <td className="py-1 px-2">{fmt(w.vk_sids_rub)}</td>
              <td className="py-1 px-2">{fmt(w.cpo_vk_sids, 0)}</td>
              <td className="py-1 px-2">{fmt(w.sids_contractor_rub)}</td>
              <td className="py-1 px-2">{fmt(w.yandex_contractor_rub)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create `tab-margin.tsx`**

```tsx
import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "../rnp-filters"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabMargin({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          {/* Gray bar = margin before ads (shows "potential") */}
          <Bar yAxisId="left" dataKey="margin_before_ads_rub" name="Маржа до рекламы ₽" fill="#94a3b8" opacity={0.5} hide={hidden.has("margin_before_ads_rub")} />
          {/* Colored bar = actual margin after ads */}
          <Bar yAxisId="left" dataKey="margin_rub" name="Маржа после рекламы ₽" hide={hidden.has("margin_rub")}>
            {weeks.map(w => <Cell key={w.week_start} fill={PHASE_COLORS[w.phase]} />)}
          </Bar>
          <Line yAxisId="right" dataKey="margin_before_ads_pct" name="Маржа до рекл. %" stroke="#185FA5" dot={false} strokeDasharray="5 3" hide={hidden.has("margin_before_ads_pct")} />
          <Line yAxisId="right" dataKey="margin_pct" name="Маржа после рекл. %" stroke="#1D9E75" dot={false} hide={hidden.has("margin_pct")} />
          <Line yAxisId="right" dataKey="margin_forecast_pct" name="Прогноз маржи %" stroke="#f59e0b" dot={false} strokeDasharray="3 3" hide={hidden.has("margin_forecast_pct")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя","Маржа до рекл. ₽","До рекл. %","Маржа после рекл. ₽","После рекл. %","Прогноз ₽","Прогноз %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.margin_before_ads_rub)}</td>
              <td className="py-1 px-2 text-[#185FA5] font-medium">{fmt(w.margin_before_ads_pct, 1)}{w.margin_before_ads_pct !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.margin_rub)}</td>
              <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{fmt(w.margin_pct, 1)}{w.margin_pct !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.margin_forecast_rub)}</td>
              <td className="py-1 px-2">{fmt(w.margin_forecast_pct, 1)}{w.margin_forecast_pct !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/components/analytics/rnp-tabs/
git commit -m "feat(rnp): TabAdsTotal, TabAdsInternal, TabAdsExternal, TabMargin"
```

---

## Task 11: RnpPage — full assembly

**Files:**
- Modify: `wookiee-hub/src/pages/analytics/rnp.tsx`

- [ ] **Step 1: Replace skeleton with full page**

```tsx
import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { fetchRnpWeeks } from "@/api/rnp"
import type { RnpWeek } from "@/types/rnp"
import { RnpHelpBlock } from "@/components/analytics/rnp-help-block"
import { RnpFilters } from "@/components/analytics/rnp-filters"
import { RnpSummaryCards } from "@/components/analytics/rnp-summary-cards"
import { TabOrders } from "@/components/analytics/rnp-tabs/tab-orders"
import { TabFunnel } from "@/components/analytics/rnp-tabs/tab-funnel"
import { TabAdsTotal } from "@/components/analytics/rnp-tabs/tab-ads-total"
import { TabAdsInternal } from "@/components/analytics/rnp-tabs/tab-ads-internal"
import { TabAdsExternal } from "@/components/analytics/rnp-tabs/tab-ads-external"
import { TabMargin } from "@/components/analytics/rnp-tabs/tab-margin"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const TABS = [
  { id: "orders",       label: "Заказы & Продажи" },
  { id: "funnel",       label: "Воронка" },
  { id: "ads-total",    label: "Реклама итого" },
  { id: "ads-internal", label: "Внутренняя" },
  { id: "ads-external", label: "Внешняя" },
  { id: "margin",       label: "Маржа & Прогноз" },
]

export function RnpPage() {
  const [searchParams] = useSearchParams()
  const [weeks, setWeeks] = useState<RnpWeek[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extAdsAvailable, setExtAdsAvailable] = useState(true)

  async function load(params: { model: string; dateFrom: string; dateTo: string }) {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchRnpWeeks(params)
      setWeeks(data.weeks)
      setExtAdsAvailable(data.ext_ads_available)
    } catch (e) {
      setError("Ошибка загрузки данных. Проверьте подключение к API.")
    } finally {
      setLoading(false)
    }
  }

  // Auto-load if URL params already have model+dates (e.g. from bookmarked URL)
  useEffect(() => {
    const model = searchParams.get("model")
    const from  = searchParams.get("from")
    const to    = searchParams.get("to")
    if (model && from && to) {
      load({ model, dateFrom: from, dateTo: to })
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <RnpHelpBlock />

      <RnpFilters onApply={load} loading={loading} />

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!extAdsAvailable && weeks.length > 0 && (
        <div className="rounded-md bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-700">
          Google Sheets недоступен — показаны только данные WB. Реклама из Sheets не отображается.
        </div>
      )}

      {weeks.length > 0 && (
        <>
          <RnpSummaryCards weeks={weeks} />

          <Tabs defaultValue="orders">
            <TabsList>
              {TABS.map(t => (
                <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="orders">    <TabOrders weeks={weeks} /></TabsContent>
            <TabsContent value="funnel">    <TabFunnel weeks={weeks} /></TabsContent>
            <TabsContent value="ads-total"> <TabAdsTotal weeks={weeks} /></TabsContent>
            <TabsContent value="ads-internal"><TabAdsInternal weeks={weeks} /></TabsContent>
            <TabsContent value="ads-external"><TabAdsExternal weeks={weeks} /></TabsContent>
            <TabsContent value="margin">    <TabMargin weeks={weeks} /></TabsContent>
          </Tabs>
        </>
      )}

      {!loading && weeks.length === 0 && !error && (
        <div className="py-12 text-center text-muted-foreground text-sm">
          Выберите модель и период, нажмите «Обновить»
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript build**

```bash
cd wookiee-hub && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors (or only pre-existing unrelated errors)

- [ ] **Step 3: Test in browser**

Start dev server, open `/analytics/rnp`, select a model, pick "8 нед." preset, click "Обновить". Verify:
- Summary cards show 6 values
- All 6 tabs open without crash
- Margin tab shows both gray (before) and colored (after) bars
- Lag ⚠ marker appears on recent weeks in Orders tab

- [ ] **Step 4: Build for production**

```bash
cd wookiee-hub && npm run build 2>&1 | tail -10
```

Expected: build completes, no errors

- [ ] **Step 5: Final commit**

```bash
git add wookiee-hub/src/pages/analytics/rnp.tsx
git commit -m "feat(rnp): RnpPage full assembly — all 6 tabs wired up"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task |
|---|---|
| §3.1–3.4 WB DB queries (4 tables) | Task 1 |
| §3.5–3.6 Sheets digital + bloggers | Task 3 |
| §4 /api/rnp/weeks contract (77 fields) | Tasks 2, 4 |
| §4 /api/rnp/models | Task 4 |
| §4 T6 max 13 weeks | Task 4 (app.py) |
| §4 D1 null-safe division | Task 2 (_safe_div) |
| §5 All 77 metrics | Task 2 (aggregate_to_weeks) |
| §6.1–6.3 Derived formulas | Task 2 |
| §7 Phase detection (margin only) | Task 1 (_detect_phase) |
| §8 Navigation | Task 7 |
| §9.1 Summary cards (6 cards, both margins) | Task 8 |
| §9.2 Filters (presets + date picker, URL state) | Task 8 |
| §9.3 Charts (all 6 tabs, phase colors, legend toggle) | Tasks 9, 10 |
| §10 Help block (D2 caveat, lag caveat) | Task 7 |
| §11 T1 port 8005, T3 X-Api-Key, T4 Sheets fallback | Task 4 |
| §13 OZON → 501, max period → 400 | Task 4 |

**All spec requirements covered.**

**Type consistency check:** `RnpWeek` in `types/rnp.ts` defines all 77+ fields. `aggregate_to_weeks` returns dicts with the same keys. `fmt()` is defined locally in each tab (avoids import chains). `PHASE_COLORS` exported from `rnp-filters.tsx`, imported in tabs.

**Placeholder scan:** No TBDs. All code blocks are complete.
