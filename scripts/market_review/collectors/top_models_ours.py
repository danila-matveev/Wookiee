"""Collector: our top model sales from MPStats item-level API."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from shared.config import MPSTATS_API_TOKEN
from scripts.market_review.config import OUR_TOP_MODELS

logger = logging.getLogger(__name__)


def _calc_delta_pct(current: dict, previous: dict) -> dict:
    """Compute (cur - prev) / prev * 100 for each shared numeric key."""
    result = {}
    for key in current:
        cur = current.get(key, 0) or 0
        prev = previous.get(key, 0) or 0
        if prev:
            result[key] = round((cur - prev) / prev * 100, 2)
        else:
            result[key] = None
    return result


def _aggregate_item_sales(data: dict) -> dict:
    """Aggregate item sales data.

    MPStats item sales returns dict with 'days' list containing
    'revenue', 'sales', 'price' per day.
    """
    days = data.get("days", [])
    if not days:
        return {"revenue": 0, "sales": 0, "avg_price": 0}

    total_revenue = sum(d.get("revenue", 0) or 0 for d in days)
    total_sales = sum(d.get("sales", 0) or 0 for d in days)
    avg_price = round(total_revenue / total_sales, 2) if total_sales else 0

    return {
        "revenue": total_revenue,
        "sales": total_sales,
        "avg_price": avg_price,
    }


def _sum_dicts(dicts: list[dict]) -> dict:
    """Sum numeric values across multiple dicts with same keys."""
    if not dicts:
        return {"revenue": 0, "sales": 0, "avg_price": 0}
    result = {}
    for key in dicts[0]:
        if key == "avg_price":
            continue
        result[key] = sum(d.get(key, 0) for d in dicts)
    # Recalculate avg_price from totals
    result["avg_price"] = (
        round(result["revenue"] / result["sales"], 2) if result.get("sales") else 0
    )
    return result


def collect_top_models_ours(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect sales data for our top models from MPStats.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (YYYY-MM-DD).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"our_models": {"Wendy": {"skus": [...], "current": ..., ...}}}
    """
    client = MPStatsClient(MPSTATS_API_TOKEN)
    our_models = {}

    try:
        for model_name, skus in OUR_TOP_MODELS.items():
            logger.info("Fetching model: %s (%d SKUs)", model_name, len(skus))

            if not skus:
                our_models[model_name] = {
                    "skus": [],
                    "note": "no SKUs configured",
                    "current": {"revenue": 0, "sales": 0, "avg_price": 0},
                    "previous": {"revenue": 0, "sales": 0, "avg_price": 0},
                    "delta_pct": {"revenue": None, "sales": None, "avg_price": None},
                }
                continue

            current_parts = []
            previous_parts = []

            for sku in skus:
                cur_data = client.get_item_sales(sku, period_start, period_end)
                prev_data = client.get_item_sales(sku, prev_start, prev_end)

                current_parts.append(_aggregate_item_sales(cur_data))
                previous_parts.append(_aggregate_item_sales(prev_data))

                time.sleep(0.3)  # Rate limiting between SKUs

            current_total = _sum_dicts(current_parts)
            previous_total = _sum_dicts(previous_parts)
            delta = _calc_delta_pct(current_total, previous_total)

            our_models[model_name] = {
                "skus": skus,
                "current": current_total,
                "previous": previous_total,
                "delta_pct": delta,
            }
    finally:
        client.close()

    return {"our_models": our_models}
