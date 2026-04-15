"""Traffic & funnel routes — organic + paid traffic metrics."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import (
    AdMetrics,
    ExternalBreakdownResponse,
    ExternalBreakdownRow,
    OrganicFunnel,
    OrganicVsPaidResponse,
    OrganicVsPaidRow,
    PaidFunnelRow,
    TrafficByModelRow,
    TrafficSummaryResponse,
)
from shared.data_layer import (
    get_ozon_traffic,
    get_wb_external_ad_breakdown,
    get_wb_organic_vs_paid_funnel,
    get_wb_traffic,
    get_wb_traffic_by_model,
)

logger = logging.getLogger("dashboard_api.traffic")

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _merge_ad_metrics(wb_rows: list, ozon_rows: list) -> list[AdMetrics]:
    """Merge WB and OZON ad metrics by period. Sums for absolutes, recompute ratios."""
    by_period: dict[str, dict] = {}

    # WB ad rows: (period, ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend, ctr, cpc)
    for r in wb_rows:
        p = r[0]
        d = by_period.setdefault(p, {"ad_views": 0, "ad_clicks": 0, "ad_to_cart": 0,
                                      "ad_orders": 0, "ad_spend": 0})
        d["ad_views"] += _to_float(r[1])
        d["ad_clicks"] += _to_float(r[2])
        d["ad_to_cart"] += _to_float(r[3])
        d["ad_orders"] += _to_float(r[4])
        d["ad_spend"] += _to_float(r[5])

    # OZON ad rows: (period, ad_views, ad_clicks, ad_orders, ad_spend, ctr, cpc)
    # Note: OZON has no ad_to_cart in get_ozon_traffic
    for r in ozon_rows:
        p = r[0]
        d = by_period.setdefault(p, {"ad_views": 0, "ad_clicks": 0, "ad_to_cart": 0,
                                      "ad_orders": 0, "ad_spend": 0})
        d["ad_views"] += _to_float(r[1])
        d["ad_clicks"] += _to_float(r[2])
        d["ad_orders"] += _to_float(r[3])
        d["ad_spend"] += _to_float(r[4])

    result = []
    for period, d in sorted(by_period.items(), key=lambda x: x[0], reverse=True):
        ctr = d["ad_clicks"] / d["ad_views"] * 100 if d["ad_views"] > 0 else 0
        cpc = d["ad_spend"] / d["ad_clicks"] if d["ad_clicks"] > 0 else 0
        result.append(AdMetrics(
            period=period,
            ad_views=d["ad_views"],
            ad_clicks=d["ad_clicks"],
            ad_to_cart=d["ad_to_cart"],
            ad_orders=d["ad_orders"],
            ad_spend=d["ad_spend"],
            ctr=round(ctr, 4),
            cpc=round(cpc, 2),
        ))
    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=TrafficSummaryResponse)
def traffic_summary(params: CommonParams = Depends()):
    """Aggregated organic funnel + ad metrics for the period."""
    mp = params.mp
    start = params.start_date
    end = params.end_date
    prev = params.prev_start

    organic_list: list[OrganicFunnel] = []
    ad_rows_wb: list = []
    ad_rows_ozon: list = []

    if mp in ("wb", "all"):
        content_results, adv_results = get_wb_traffic(start, prev, end)
        # content_results: (period, card_opens, add_to_cart, funnel_orders, buyouts)
        for r in content_results:
            organic_list.append(OrganicFunnel(
                period=r[0],
                card_opens=_to_float(r[1]),
                add_to_cart=_to_float(r[2]),
                funnel_orders=_to_float(r[3]),
                buyouts=_to_float(r[4]),
            ))
        ad_rows_wb = adv_results

    # OZON has no organic data — only ads
    if mp in ("ozon", "all"):
        ozon_adv = get_ozon_traffic(start, prev, end)
        ad_rows_ozon = ozon_adv

    # Build ad metrics
    if mp == "wb":
        ads = [AdMetrics(
            period=r[0],
            ad_views=_to_float(r[1]),
            ad_clicks=_to_float(r[2]),
            ad_to_cart=_to_float(r[3]),
            ad_orders=_to_float(r[4]),
            ad_spend=_to_float(r[5]),
            ctr=_to_float(r[6]),
            cpc=_to_float(r[7]),
        ) for r in ad_rows_wb]
    elif mp == "ozon":
        ads = [AdMetrics(
            period=r[0],
            ad_views=_to_float(r[1]),
            ad_clicks=_to_float(r[2]),
            ad_to_cart=0,
            ad_orders=_to_float(r[3]),
            ad_spend=_to_float(r[4]),
            ctr=_to_float(r[5]),
            cpc=_to_float(r[6]),
        ) for r in ad_rows_ozon]
    else:
        ads = _merge_ad_metrics(ad_rows_wb, ad_rows_ozon)

    return TrafficSummaryResponse(organic=organic_list, ads=ads)


@router.get("/by-model", response_model=list[TrafficByModelRow])
def traffic_by_model(params: CommonParams = Depends()):
    """Per-model ad traffic breakdown (WB only — OZON lacks per-model traffic)."""
    # get_wb_traffic_by_model returns tuples:
    # (period, model, ad_views, ad_clicks, ad_spend, ad_to_cart, ad_orders, ctr, cpc)
    results = get_wb_traffic_by_model(params.start_date, params.prev_start, params.end_date)

    return [
        TrafficByModelRow(
            period=r[0],
            model=r[1] or "Unknown",
            ad_views=_to_float(r[2]),
            ad_clicks=_to_float(r[3]),
            ad_spend=_to_float(r[4]),
            ad_to_cart=_to_float(r[5]),
            ad_orders=_to_float(r[6]),
            ctr=_to_float(r[7]),
            cpc=_to_float(r[8]),
        )
        for r in results
    ]


@router.get("/organic-vs-paid", response_model=OrganicVsPaidResponse)
def organic_vs_paid(params: CommonParams = Depends()):
    """WB organic vs paid funnel comparison. OZON has no organic data."""
    organic_results, paid_results = get_wb_organic_vs_paid_funnel(
        params.start_date, params.prev_start, params.end_date,
    )

    # organic: (period, card_opens, add_to_cart, funnel_orders, buyouts,
    #           card_to_cart_pct, cart_to_order_pct, order_to_buyout_pct)
    organic = [
        OrganicVsPaidRow(
            period=r[0],
            card_opens=_to_float(r[1]),
            add_to_cart=_to_float(r[2]),
            funnel_orders=_to_float(r[3]),
            buyouts=_to_float(r[4]),
            card_to_cart_pct=_to_float(r[5]),
            cart_to_order_pct=_to_float(r[6]),
            order_to_buyout_pct=_to_float(r[7]),
        )
        for r in organic_results
    ]

    # paid: (period, ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend, ctr, cpc)
    paid = [
        PaidFunnelRow(
            period=r[0],
            ad_views=_to_float(r[1]),
            ad_clicks=_to_float(r[2]),
            ad_to_cart=_to_float(r[3]),
            ad_orders=_to_float(r[4]),
            ad_spend=_to_float(r[5]),
            ctr=_to_float(r[6]),
            cpc=_to_float(r[7]),
        )
        for r in paid_results
    ]

    return OrganicVsPaidResponse(organic=organic, paid=paid)


@router.get("/external-breakdown", response_model=ExternalBreakdownResponse)
def external_breakdown(params: CommonParams = Depends()):
    """Breakdown of ad spend by channel: internal MP, bloggers, VK, creators."""
    mp = params.mp
    start = params.start_date
    end = params.end_date
    prev = params.prev_start

    wb_rows: list[ExternalBreakdownRow] = []
    ozon_rows: list[ExternalBreakdownRow] = []

    if mp in ("wb", "all"):
        # (period, adv_internal, adv_bloggers, adv_vk, adv_creators, adv_total)
        raw = get_wb_external_ad_breakdown(start, prev, end)
        wb_rows = [
            ExternalBreakdownRow(
                period=r[0],
                adv_internal=_to_float(r[1]),
                adv_bloggers=_to_float(r[2]),
                adv_vk=_to_float(r[3]),
                adv_creators=_to_float(r[4]),
                adv_total=_to_float(r[5]),
            )
            for r in raw
        ]

    if mp in ("ozon", "all"):
        # OZON breakdown: (period, adv_internal, adv_external, adv_vk, adv_total)
        # Note: OZON has no creators/bloggers split — map adv_external to bloggers field
        from shared.data_layer import get_ozon_external_ad_breakdown
        raw = get_ozon_external_ad_breakdown(start, prev, end)
        ozon_rows = [
            ExternalBreakdownRow(
                period=r[0],
                adv_internal=_to_float(r[1]),
                adv_bloggers=_to_float(r[2]),  # adv_external in OZON
                adv_vk=_to_float(r[3]),
                adv_creators=0,
                adv_total=_to_float(r[4]),
            )
            for r in raw
        ]

    return ExternalBreakdownResponse(wb=wb_rows, ozon=ozon_rows)
