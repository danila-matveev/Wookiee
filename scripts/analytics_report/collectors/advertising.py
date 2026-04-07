"""Advertising data collector: breakdowns, ROI, daily series, campaigns."""
from __future__ import annotations

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
from scripts.analytics_report.utils import tuples_to_dicts, safe_float


def collect_advertising(start: str, prev_start: str, end: str) -> dict:
    """Collect all advertising data from both channels.

    Returns {"advertising": {...}} with raw results from each function.
    """
    return {
        "advertising": {
            "wb_external_breakdown": get_wb_external_ad_breakdown(start, prev_start, end),
            "ozon_external_breakdown": get_ozon_external_ad_breakdown(start, prev_start, end),
            "wb_model_ad_roi": get_wb_model_ad_roi(start, prev_start, end),
            "ozon_model_ad_roi": get_ozon_model_ad_roi(start, prev_start, end),
            "wb_ad_daily_series": get_wb_ad_daily_series(start, end),
            "ozon_ad_daily_series": get_ozon_ad_daily_series(start, end),
            "wb_campaign_stats": get_wb_campaign_stats(start, prev_start, end),
            "wb_ad_budget_utilization": get_wb_ad_budget_utilization(start, end),
            "wb_ad_totals_check": get_wb_ad_totals_check(start, end),
            "ozon_ad_by_sku": get_ozon_ad_by_sku(start, prev_start, end),
        }
    }
