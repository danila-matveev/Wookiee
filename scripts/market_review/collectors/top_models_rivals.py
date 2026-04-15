"""Collector: rival analogs for our top models via MPStats similar items."""

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


def _aggregate_item_sales(data: dict) -> dict:
    """Aggregate item sales data into totals."""
    days = data.get("days", [])
    if not days:
        return {"revenue": 0, "sales": 0}

    total_revenue = sum(d.get("revenue", 0) or 0 for d in days)
    total_sales = sum(d.get("sales", 0) or 0 for d in days)

    return {"revenue": total_revenue, "sales": total_sales}


def collect_top_models_rivals(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect rival analogs for our top models.

    For each model, uses the first SKU to find similar items via MPStats,
    then fetches sales for the top 10, keeps the top 3 by revenue.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (YYYY-MM-DD).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"rival_models": {"Wendy": {"analogs": [...]}}}
    """
    client = MPStatsClient(MPSTATS_API_TOKEN)
    rival_models = {}

    try:
        for model_name, skus in OUR_TOP_MODELS.items():
            logger.info("Finding rivals for model: %s", model_name)

            if not skus:
                rival_models[model_name] = {
                    "analogs": [],
                    "note": "no SKUs configured",
                }
                continue

            # Use first SKU to find similar items
            first_sku = skus[0]
            similar_data = client.get_item_similar(first_sku)

            # MPStats returns list of similar items or dict with 'data' key
            similar_items = similar_data
            if isinstance(similar_data, dict):
                similar_items = similar_data.get("data", similar_data.get("items", []))
            if not isinstance(similar_items, list):
                similar_items = []

            # Take top 10, fetch sales for each
            candidates = []
            for item in similar_items[:10]:
                sku = item.get("id") or item.get("sku") or item.get("nmID")
                if not sku:
                    continue

                sales_data = _aggregate_item_sales(
                    client.get_item_sales(int(sku), period_start, period_end)
                )

                candidates.append({
                    "sku": int(sku),
                    "brand": item.get("brand", ""),
                    "price": item.get("price", 0),
                    "revenue": sales_data["revenue"],
                    "sales": sales_data["sales"],
                    "rating": item.get("rating", 0),
                    "reviews": item.get("reviews", item.get("feedbacks", 0)),
                })

                time.sleep(0.3)  # Rate limiting

            # Sort by revenue, keep top 3
            candidates.sort(key=lambda x: x["revenue"], reverse=True)
            rival_models[model_name] = {
                "analogs": candidates[:3],
            }
    finally:
        client.close()

    return {"rival_models": rival_models}
