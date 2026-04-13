"""Traffic and funnel data collector: WB + OZON, organic vs paid."""
from __future__ import annotations

from shared.data_layer.traffic import (
    get_wb_traffic,
    get_wb_traffic_by_model,
    get_wb_content_analysis_by_model,
    get_wb_skleyka_halo,
    get_ozon_traffic,
)
from shared.data_layer.advertising import (
    get_wb_organic_vs_paid_funnel,
    get_wb_organic_by_status,
    get_ozon_organic_estimated,
)


def collect_traffic(start: str, prev_start: str, end: str) -> dict:
    """Collect traffic data from both channels.

    Returns {"traffic": {...}} with raw results from each function.

    Note: content_analysis has ~20% gap vs PowerBI — use as trend only.
    """
    return {
        "traffic": {
            "wb_total": get_wb_traffic(start, prev_start, end),
            "wb_by_model": get_wb_traffic_by_model(start, prev_start, end),
            "wb_content_by_model": get_wb_content_analysis_by_model(start, prev_start, end),
            "ozon_total": get_ozon_traffic(start, prev_start, end),
            "wb_organic_vs_paid": get_wb_organic_vs_paid_funnel(start, prev_start, end),
            "wb_organic_by_status": get_wb_organic_by_status(start, prev_start, end),
            "ozon_organic_estimated": get_ozon_organic_estimated(start, prev_start, end),
            "wb_skleyka_halo": get_wb_skleyka_halo(start, end),
            "limitations": [
                "WB content_analysis: ~20% gap with PowerBI",
                "Buyout % is lagging (3-21 days delay)",
                "wb_by_model: ADS ONLY (wb_adv). Use wb_content_by_model for full funnel CRO.",
            ],
        }
    }
