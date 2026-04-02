"""WB/OZON finance + internal ad breakdown collector."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_external_ad_breakdown,
    get_wb_model_ad_roi,
)


def _prev_start(start: str, end: str) -> str:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    return (s - timedelta(days=(e - s).days)).strftime("%Y-%m-%d")


def _extract_by_period(rows: list, label: str) -> list:
    return [r for r in rows if r and r[0] == label]


def _parse_wb_finance(rows: list) -> dict:
    """Parse WB finance row (19 columns):
    period, orders_count, sales_count, revenue_before_spp, revenue_after_spp,
    adv_internal, adv_external, cost_of_goods, logistics, storage,
    commission, spp_amount, nds, penalty, retention, deduction, margin,
    returns_revenue, revenue_before_spp_gross
    """
    result = {}
    for r in rows:
        if len(r) >= 17:
            result = {
                "orders_count": int(r[1] or 0),
                "sales_count": int(r[2] or 0),
                "revenue_before_spp": float(r[3] or 0),
                "revenue_after_spp": float(r[4] or 0),
                "adv_internal": float(r[5] or 0),
                "adv_external": float(r[6] or 0),
                "cost_of_goods": float(r[7] or 0),
                "logistics": float(r[8] or 0),
                "storage": float(r[9] or 0),
                "commission": float(r[10] or 0),
                "spp_amount": float(r[11] or 0),
                "nds": float(r[12] or 0),
                "penalty": float(r[13] or 0),
                "retention": float(r[14] or 0),
                "deduction": float(r[15] or 0),
                "margin": float(r[16] or 0),
            }
            if len(r) >= 19:
                result["returns_revenue"] = float(r[17] or 0)
                result["revenue_before_spp_gross"] = float(r[18] or 0)
    return result


def _parse_wb_orders(rows: list) -> dict:
    """Parse WB orders: (period, orders_count, orders_rub)."""
    for r in rows:
        if len(r) >= 3:
            return {"orders_count": int(r[1] or 0), "orders_rub": float(r[2] or 0)}
    return {}


def _parse_ozon_finance(rows: list) -> dict:
    """Parse OZON finance row (13 columns):
    period, sales_count, revenue_before_spp, revenue_after_spp,
    adv_internal, adv_external, margin, cost_of_goods, logistics,
    storage, commission, spp_amount, nds
    """
    for r in rows:
        if len(r) >= 13:
            return {
                "sales_count": int(r[1] or 0),
                "revenue_before_spp": float(r[2] or 0),
                "revenue_after_spp": float(r[3] or 0),
                "adv_internal": float(r[4] or 0),
                "adv_external": float(r[5] or 0),
                "margin": float(r[6] or 0),
                "cost_of_goods": float(r[7] or 0),
                "logistics": float(r[8] or 0),
                "storage": float(r[9] or 0),
                "commission": float(r[10] or 0),
                "spp_amount": float(r[11] or 0),
                "nds": float(r[12] or 0),
            }
    return {}


def _parse_ad_breakdown(rows: list) -> dict:
    """Parse ad breakdown: (period, adv_internal, adv_bloggers, adv_vk, adv_creators, adv_total)."""
    for r in rows:
        if len(r) >= 6:
            return {
                "adv_internal": float(r[1] or 0),
                "adv_bloggers": float(r[2] or 0),
                "adv_vk": float(r[3] or 0),
                "adv_creators": float(r[4] or 0),
                "adv_total": float(r[5] or 0),
            }
    return {}


def _parse_ad_roi(rows: list) -> list[dict]:
    """Parse ad ROI by model: (period, model, ad_spend, ad_orders, revenue, margin, drr_pct, romi)."""
    result = []
    for r in rows:
        if len(r) >= 8:
            result.append({
                "model": r[1],
                "ad_spend": float(r[2] or 0),
                "ad_orders": int(r[3] or 0),
                "revenue": float(r[4] or 0),
                "margin": float(r[5] or 0),
                "drr_pct": float(r[6] or 0) if r[6] else None,
                "romi": float(r[7] or 0) if r[7] else None,
            })
    return result


def collect_finance(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect WB and OZON financial data for two periods."""
    prev_b = _prev_start(b_start, b_end)

    # WB Finance — returns (results, orders_results)
    wb_results_a, wb_orders_a = get_wb_finance(a_start, b_start, a_end)
    wb_results_b, wb_orders_b = get_wb_finance(b_start, prev_b, b_end)

    # OZON Finance — returns (results, orders_results)
    try:
        ozon_results_a, ozon_orders_a = get_ozon_finance(a_start, b_start, a_end)
        ozon_results_b, ozon_orders_b = get_ozon_finance(b_start, prev_b, b_end)
    except Exception:
        ozon_results_a, ozon_orders_a = [], []
        ozon_results_b, ozon_orders_b = [], []

    # WB Ad Breakdown — returns flat list
    wb_ads_raw_a = get_wb_external_ad_breakdown(a_start, b_start, a_end)
    wb_ads_raw_b = get_wb_external_ad_breakdown(b_start, prev_b, b_end)

    # WB Ad ROI by model — returns flat list
    wb_roi_raw_a = get_wb_model_ad_roi(a_start, b_start, a_end)
    wb_roi_raw_b = get_wb_model_ad_roi(b_start, prev_b, b_end)

    return {
        "wb_finance": {
            "period_a": _parse_wb_finance(_extract_by_period(wb_results_a, 'current')),
            "period_b": _parse_wb_finance(_extract_by_period(wb_results_b, 'current')),
        },
        "wb_orders": {
            "period_a": _parse_wb_orders(_extract_by_period(wb_orders_a, 'current')),
            "period_b": _parse_wb_orders(_extract_by_period(wb_orders_b, 'current')),
        },
        "ozon_finance": {
            "period_a": _parse_ozon_finance(_extract_by_period(ozon_results_a, 'current')),
            "period_b": _parse_ozon_finance(_extract_by_period(ozon_results_b, 'current')),
        },
        "ozon_orders": {
            "period_a": _parse_wb_orders(_extract_by_period(ozon_orders_a, 'current')),
            "period_b": _parse_wb_orders(_extract_by_period(ozon_orders_b, 'current')),
        },
        "wb_ads": {
            "period_a": _parse_ad_breakdown(_extract_by_period(wb_ads_raw_a, 'current')),
            "period_b": _parse_ad_breakdown(_extract_by_period(wb_ads_raw_b, 'current')),
        },
        "ad_roi": {
            "period_a": _parse_ad_roi(_extract_by_period(wb_roi_raw_a, 'current')),
            "period_b": _parse_ad_roi(_extract_by_period(wb_roi_raw_b, 'current')),
        },
    }
