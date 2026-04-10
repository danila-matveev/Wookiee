"""Promo / advertising routes — ad ROI, daily series, budget utilization."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import (
    ActualSpendRow,
    AdDailyRow,
    BudgetRow,
    BudgetUtilizationResponse,
    ModelAdRoiRow,
)
from shared.data_layer import (
    get_ozon_ad_daily_series,
    get_ozon_model_ad_roi,
    get_wb_ad_budget_utilization,
    get_wb_ad_daily_series,
    get_wb_model_ad_roi,
)

logger = logging.getLogger("dashboard_api.promo")

router = APIRouter(prefix="/api/promo", tags=["promo"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/model-ad-roi", response_model=list[ModelAdRoiRow])
def model_ad_roi(params: CommonParams = Depends()):
    """Per-model advertising ROI: DRR, ROMI, spend, orders."""
    mp = params.mp
    start = params.start_date
    end = params.end_date
    prev = params.prev_start

    rows: list[ModelAdRoiRow] = []

    if mp in ("wb", "all"):
        # Returns: (period, model, ad_spend, ad_orders, revenue, margin, drr_pct, romi)
        wb = get_wb_model_ad_roi(start, prev, end)
        for r in wb:
            rows.append(ModelAdRoiRow(
                period=r[0],
                model=r[1] or "Unknown",
                ad_spend=_to_float(r[2]),
                ad_orders=_to_float(r[3]),
                revenue=_to_float(r[4]),
                margin=_to_float(r[5]),
                drr_pct=float(r[6]) if r[6] is not None else None,
                romi=float(r[7]) if r[7] is not None else None,
            ))

    if mp in ("ozon", "all"):
        # Same tuple structure as WB
        ozon = get_ozon_model_ad_roi(start, prev, end)
        for r in ozon:
            rows.append(ModelAdRoiRow(
                period=r[0],
                model=r[1] or "Unknown",
                ad_spend=_to_float(r[2]),
                ad_orders=_to_float(r[3]),
                revenue=_to_float(r[4]),
                margin=_to_float(r[5]),
                drr_pct=float(r[6]) if r[6] is not None else None,
                romi=float(r[7]) if r[7] is not None else None,
            ))

    # When mp=all, we do NOT merge models across WB/OZON — the frontend can
    # distinguish by the combination of period + model (same model may appear
    # twice, once from each MP).  If merging is needed later, it should use
    # weighted averages for DRR/ROMI and sums for absolutes.

    return rows


@router.get("/ad-daily", response_model=list[AdDailyRow])
def ad_daily(params: CommonParams = Depends()):
    """Daily ad metrics time-series."""
    mp = params.mp
    start = params.start_date
    end = params.end_date

    if mp == "ozon":
        # OZON: (date, views, clicks, orders, spend, avg_bid, ctr, cpc)
        raw = get_ozon_ad_daily_series(start, end)
        return [
            AdDailyRow(
                date=str(r[0]),
                views=_to_float(r[1]),
                clicks=_to_float(r[2]),
                spend=_to_float(r[4]),
                to_cart=0,  # OZON daily series has no to_cart
                orders=_to_float(r[3]),
                ctr=_to_float(r[6]),
                cpc=_to_float(r[7]),
            )
            for r in raw
        ]

    if mp == "wb":
        # WB: (date, views, clicks, spend, to_cart, orders, ctr, cpc)
        raw = get_wb_ad_daily_series(start, end)
        return [
            AdDailyRow(
                date=str(r[0]),
                views=_to_float(r[1]),
                clicks=_to_float(r[2]),
                spend=_to_float(r[3]),
                to_cart=_to_float(r[4]),
                orders=_to_float(r[5]),
                ctr=_to_float(r[6]),
                cpc=_to_float(r[7]),
            )
            for r in raw
        ]

    # mp=all — merge WB + OZON by date, recompute ratios
    wb_raw = get_wb_ad_daily_series(start, end)
    ozon_raw = get_ozon_ad_daily_series(start, end)

    by_date: dict[str, dict] = {}

    for r in wb_raw:
        d = str(r[0])
        entry = by_date.setdefault(d, {"views": 0, "clicks": 0, "spend": 0,
                                        "to_cart": 0, "orders": 0})
        entry["views"] += _to_float(r[1])
        entry["clicks"] += _to_float(r[2])
        entry["spend"] += _to_float(r[3])
        entry["to_cart"] += _to_float(r[4])
        entry["orders"] += _to_float(r[5])

    for r in ozon_raw:
        d = str(r[0])
        entry = by_date.setdefault(d, {"views": 0, "clicks": 0, "spend": 0,
                                        "to_cart": 0, "orders": 0})
        entry["views"] += _to_float(r[1])
        entry["clicks"] += _to_float(r[2])
        entry["spend"] += _to_float(r[4])  # index 4 in OZON
        entry["orders"] += _to_float(r[3])  # index 3 in OZON

    result = []
    for d in sorted(by_date):
        e = by_date[d]
        ctr = e["clicks"] / e["views"] * 100 if e["views"] > 0 else 0
        cpc = e["spend"] / e["clicks"] if e["clicks"] > 0 else 0
        result.append(AdDailyRow(
            date=d,
            views=e["views"],
            clicks=e["clicks"],
            spend=e["spend"],
            to_cart=e["to_cart"],
            orders=e["orders"],
            ctr=round(ctr, 4),
            cpc=round(cpc, 2),
        ))

    return result


@router.get("/budget-utilization", response_model=BudgetUtilizationResponse)
def budget_utilization(params: CommonParams = Depends()):
    """Budget vs actual ad spend (WB only — OZON has no budget table)."""
    budget_rows, actual_rows = get_wb_ad_budget_utilization(
        params.start_date, params.end_date,
    )

    budget = [
        BudgetRow(date=str(r[0]), budget=_to_float(r[1]))
        for r in budget_rows
    ]

    actual = [
        ActualSpendRow(
            date=str(r[0]),
            actual_spend=_to_float(r[1]),
            views=_to_float(r[2]),
            clicks=_to_float(r[3]),
            orders=_to_float(r[4]),
        )
        for r in actual_rows
    ]

    return BudgetUtilizationResponse(budget=budget, actual=actual)
