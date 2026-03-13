"""Finance routes: summary and by-model breakdowns."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from services.dashboard_api.cache import cached
from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import (
    FinanceByModelResponse,
    FinancePeriodMetrics,
    FinanceSummaryResponse,
    ModelFinanceRow,
)
from shared.data_layer import (
    get_ozon_by_model,
    get_ozon_finance,
    get_ozon_orders_by_model,
    get_wb_by_model,
    get_wb_finance,
    get_wb_orders_by_model,
    to_float,
)

logger = logging.getLogger("dashboard_api.finance")
router = APIRouter(prefix="/api/finance", tags=["finance"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_pct(numerator: float, denominator: float) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def _parse_wb_finance_row(row) -> dict:
    """Parse a single WB finance result tuple into a flat dict."""
    return {
        "orders_count": to_float(row[1]),
        "sales_count": to_float(row[2]),
        "revenue_before_spp": to_float(row[3]),
        "revenue_after_spp": to_float(row[4]),
        "adv_internal": to_float(row[5]),
        "adv_external": to_float(row[6]),
        "cost_of_goods": to_float(row[7]),
        "logistics": to_float(row[8]),
        "storage": to_float(row[9]),
        "commission": to_float(row[10]),
        "spp_amount": to_float(row[11]),
        "nds": to_float(row[12]),
        "penalty": to_float(row[13]),
        "retention": to_float(row[14]),
        "deduction": to_float(row[15]),
        "margin": to_float(row[16]),
        "returns_revenue": to_float(row[17]),
        "revenue_before_spp_gross": to_float(row[18]),
    }


def _parse_ozon_finance_row(row) -> dict:
    """Parse a single OZON finance result tuple into a flat dict."""
    return {
        "orders_count": 0,  # filled from orders_results
        "sales_count": to_float(row[1]),
        "revenue_before_spp": to_float(row[2]),
        "revenue_after_spp": to_float(row[3]),
        "adv_internal": to_float(row[4]),
        "adv_external": to_float(row[5]),
        "margin": to_float(row[6]),
        "cost_of_goods": to_float(row[7]),
        "logistics": to_float(row[8]),
        "storage": to_float(row[9]),
        "commission": to_float(row[10]),
        "spp_amount": to_float(row[11]),
        "nds": to_float(row[12]),
        "penalty": 0,
        "retention": 0,
        "deduction": 0,
        "returns_revenue": 0,
        "revenue_before_spp_gross": to_float(row[2]),  # no separate gross for OZON
    }


def _build_period_metrics(data: dict) -> FinancePeriodMetrics:
    adv_total = data.get("adv_internal", 0) + data.get("adv_external", 0)
    rev = data.get("revenue_before_spp", 0)
    return FinancePeriodMetrics(
        orders_count=data.get("orders_count", 0),
        sales_count=data.get("sales_count", 0),
        revenue_before_spp=rev,
        revenue_after_spp=data.get("revenue_after_spp", 0),
        adv_internal=data.get("adv_internal", 0),
        adv_external=data.get("adv_external", 0),
        adv_total=adv_total,
        cost_of_goods=data.get("cost_of_goods", 0),
        logistics=data.get("logistics", 0),
        storage=data.get("storage", 0),
        commission=data.get("commission", 0),
        spp_amount=data.get("spp_amount", 0),
        nds=data.get("nds", 0),
        penalty=data.get("penalty", 0),
        retention=data.get("retention", 0),
        deduction=data.get("deduction", 0),
        margin=data.get("margin", 0),
        margin_pct=_safe_pct(data.get("margin", 0), rev),
        returns_revenue=data.get("returns_revenue", 0),
        revenue_before_spp_gross=data.get("revenue_before_spp_gross", 0),
        orders_rub=data.get("orders_rub", 0),
        drr_pct=_safe_pct(adv_total, rev),
    )


def _merge_dicts(a: dict, b: dict) -> dict:
    """Sum all numeric values from two dicts. Used when mp=all."""
    merged = {}
    all_keys = set(a) | set(b)
    for k in all_keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            merged[k] = va + vb
        else:
            merged[k] = va or vb
    return merged


@cached
def _fetch_finance(start_date: str, prev_start: str, end_date: str, mp: str):
    """Fetch and structure finance data. Cached 5 min."""
    periods: dict[str, dict] = {"current": {}, "previous": {}}

    if mp in ("wb", "all"):
        wb_results, wb_orders = get_wb_finance(start_date, prev_start, end_date)
        wb_orders_map: dict[str, dict] = {}
        for orow in wb_orders:
            wb_orders_map[orow[0]] = {"orders_count": to_float(orow[1]), "orders_rub": to_float(orow[2])}
        for row in wb_results:
            period = row[0]
            data = _parse_wb_finance_row(row)
            om = wb_orders_map.get(period, {})
            data["orders_count"] = om.get("orders_count", data["orders_count"])
            data["orders_rub"] = om.get("orders_rub", 0)
            if mp == "all":
                periods[period] = _merge_dicts(periods[period], data)
            else:
                periods[period] = data

    if mp in ("ozon", "all"):
        oz_results, oz_orders = get_ozon_finance(start_date, prev_start, end_date)
        oz_orders_map: dict[str, dict] = {}
        for orow in oz_orders:
            oz_orders_map[orow[0]] = {"orders_count": to_float(orow[1]), "orders_rub": to_float(orow[2])}
        for row in oz_results:
            period = row[0]
            data = _parse_ozon_finance_row(row)
            om = oz_orders_map.get(period, {})
            data["orders_count"] = om.get("orders_count", 0)
            data["orders_rub"] = om.get("orders_rub", 0)
            if mp == "all":
                periods[period] = _merge_dicts(periods[period], data)
            else:
                periods[period] = data

    # Build response — percentages recomputed from combined absolute values
    return FinanceSummaryResponse(
        current=_build_period_metrics(periods.get("current", {})),
        previous=_build_period_metrics(periods.get("previous", {})),
    )


@router.get("/summary", response_model=FinanceSummaryResponse)
def finance_summary(params: CommonParams = Depends()):
    return _fetch_finance(params.start_date, params.prev_start, params.end_date, params.mp)


# ── By-model ─────────────────────────────────────────────────────────────────

@cached
def _fetch_by_model(start_date: str, prev_start: str, end_date: str, mp: str):
    rows: list[ModelFinanceRow] = []

    if mp in ("wb", "all"):
        wb_models = get_wb_by_model(start_date, prev_start, end_date)
        wb_orders = get_wb_orders_by_model(start_date, prev_start, end_date)
        # Build orders lookup: (period, model) -> {orders_count, orders_rub}
        wb_om: dict[tuple, dict] = {}
        for orow in wb_orders:
            key = (orow[0], orow[1])
            wb_om[key] = {"orders_count": to_float(orow[2]), "orders_rub": to_float(orow[3])}

        for row in wb_models:
            period, model = row[0], row[1]
            sales = to_float(row[2])
            rev = to_float(row[3])
            adv_int = to_float(row[4])
            adv_ext = to_float(row[5])
            margin = to_float(row[6])
            cogs = to_float(row[7])
            adv_total = adv_int + adv_ext
            om = wb_om.get((period, model), {})
            rows.append(ModelFinanceRow(
                period=period,
                model=model,
                mp="wb",
                sales_count=sales,
                revenue_before_spp=rev,
                adv_internal=adv_int,
                adv_external=adv_ext,
                adv_total=adv_total,
                margin=margin,
                margin_pct=_safe_pct(margin, rev),
                cost_of_goods=cogs,
                orders_count=om.get("orders_count", 0),
                orders_rub=om.get("orders_rub", 0),
                drr_pct=_safe_pct(adv_total, rev),
            ))

    if mp in ("ozon", "all"):
        oz_models = get_ozon_by_model(start_date, prev_start, end_date)
        oz_orders = get_ozon_orders_by_model(start_date, prev_start, end_date)
        oz_om: dict[tuple, dict] = {}
        for orow in oz_orders:
            key = (orow[0], orow[1])
            oz_om[key] = {"orders_count": to_float(orow[2]), "orders_rub": to_float(orow[3])}

        for row in oz_models:
            period, model = row[0], row[1]
            sales = to_float(row[2])
            rev = to_float(row[3])
            adv_int = to_float(row[4])
            adv_ext = to_float(row[5])
            margin = to_float(row[6])
            cogs = to_float(row[7])
            adv_total = adv_int + adv_ext
            om = oz_om.get((period, model), {})
            rows.append(ModelFinanceRow(
                period=period,
                model=model,
                mp="ozon",
                sales_count=sales,
                revenue_before_spp=rev,
                adv_internal=adv_int,
                adv_external=adv_ext,
                adv_total=adv_total,
                margin=margin,
                margin_pct=_safe_pct(margin, rev),
                cost_of_goods=cogs,
                orders_count=om.get("orders_count", 0),
                orders_rub=om.get("orders_rub", 0),
                drr_pct=_safe_pct(adv_total, rev),
            ))

    return FinanceByModelResponse(rows=rows)


@router.get("/by-model", response_model=FinanceByModelResponse)
def finance_by_model(params: CommonParams = Depends()):
    return _fetch_by_model(params.start_date, params.prev_start, params.end_date, params.mp)
