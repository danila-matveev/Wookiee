"""Pricing data collector: price changes, SPP history, price-margin by model."""
from __future__ import annotations

from shared.data_layer.pricing import (
    get_wb_price_changes,
    get_ozon_price_changes,
    get_wb_spp_history_by_model,
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
)


def collect_pricing(start: str, prev_start: str, end: str) -> dict:
    """Collect pricing data from both channels.

    Args:
        start: current period start (YYYY-MM-DD)
        prev_start: previous period start (YYYY-MM-DD)
        end: current period end (YYYY-MM-DD)

    Returns:
        {"pricing": {...}} with price changes, SPP, margin by model.
    """
    return {
        "pricing": {
            "wb_price_changes": get_wb_price_changes(start, end),
            "ozon_price_changes": get_ozon_price_changes(start, end),
            "wb_spp_history": get_wb_spp_history_by_model(start, end),
            "wb_price_margin_by_model": get_wb_price_margin_by_model_period(start, end),
            "ozon_price_margin_by_model": get_ozon_price_margin_by_model_period(start, end),
        }
    }
