"""Time-series routes: daily and weekly aggregations."""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends

from services.dashboard_api.cache import cached
from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import (
    DailyDataPoint,
    DailySeriesResponse,
    WeeklyDataPoint,
    WeeklySeriesResponse,
)
from shared.data_layer import (
    get_ozon_daily_series_range,
    get_ozon_weekly_breakdown,
    get_wb_daily_series_range,
    get_wb_weekly_breakdown,
)

logger = logging.getLogger("dashboard_api.series")
router = APIRouter(prefix="/api/series", tags=["series"])

_DAILY_SUM_KEYS = (
    "orders_count", "sales_count", "revenue_before_spp", "revenue_after_spp",
    "adv_total", "cost_of_goods", "logistics", "storage", "commission",
    "spp_amount", "margin",
)

_WEEKLY_SUM_KEYS = (
    "orders_count", "sales_count", "revenue_before_spp", "adv_total",
    "cost_of_goods", "logistics", "storage", "commission", "margin", "orders_rub",
)


def _date_str(val) -> str:
    """Normalise date to YYYY-MM-DD string."""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)


# ── Daily ────────────────────────────────────────────────────────────────────

@cached
def _fetch_daily(start_date: str, end_date: str, mp: str):
    merged: dict[str, dict] = defaultdict(lambda: {k: 0.0 for k in _DAILY_SUM_KEYS})

    if mp in ("wb", "all"):
        for row in get_wb_daily_series_range(start_date, end_date):
            d = _date_str(row["date"])
            for k in _DAILY_SUM_KEYS:
                merged[d][k] += row.get(k, 0) or 0

    if mp in ("ozon", "all"):
        for row in get_ozon_daily_series_range(start_date, end_date):
            d = _date_str(row["date"])
            for k in _DAILY_SUM_KEYS:
                merged[d][k] += row.get(k, 0) or 0

    series = [
        DailyDataPoint(date=d, **vals)
        for d, vals in sorted(merged.items())
    ]
    return DailySeriesResponse(series=series)


@router.get("/daily", response_model=DailySeriesResponse)
def daily_series(params: CommonParams = Depends()):
    return _fetch_daily(params.start_date, params.end_date, params.mp)


# ── Weekly ───────────────────────────────────────────────────────────────────

@cached
def _fetch_weekly(start_date: str, end_date: str, mp: str):
    # Key by week_start string for merging
    merged: dict[str, dict] = {}

    def _add_weeks(weeks: list[dict]):
        for w in weeks:
            ws = _date_str(w["week_start"])
            if ws not in merged:
                merged[ws] = {
                    "week_start": ws,
                    "week_end": _date_str(w["week_end"]),
                    "days": w.get("days", 0),
                    **{k: 0.0 for k in _WEEKLY_SUM_KEYS},
                }
            for k in _WEEKLY_SUM_KEYS:
                merged[ws][k] += w.get(k, 0) or 0
            # days: take max (weeks should align, but guard against mismatch)
            merged[ws]["days"] = max(merged[ws]["days"], w.get("days", 0))
            merged[ws]["week_end"] = max(merged[ws]["week_end"], _date_str(w["week_end"]))

    if mp in ("wb", "all"):
        _add_weeks(get_wb_weekly_breakdown(start_date, end_date))

    if mp in ("ozon", "all"):
        _add_weeks(get_ozon_weekly_breakdown(start_date, end_date))

    weeks = [
        WeeklyDataPoint(**vals)
        for vals in sorted(merged.values(), key=lambda v: v["week_start"])
    ]
    return WeeklySeriesResponse(weeks=weeks)


@router.get("/weekly", response_model=WeeklySeriesResponse)
def weekly_series(params: CommonParams = Depends()):
    return _fetch_weekly(params.start_date, params.end_date, params.mp)
