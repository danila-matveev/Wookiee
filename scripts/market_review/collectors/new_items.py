"""Collector: new items in target categories from MPStats."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from shared.config import MPSTATS_API_TOKEN
from scripts.market_review.config import CATEGORIES, NEW_ITEMS_MIN_REVENUE

logger = logging.getLogger(__name__)


def collect_new_items(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect new items across all monitored categories.

    For each category, fetches items via POST to /api/wb/get/category
    with pagination, filters by revenue and first_seen date.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (used as first_seen threshold).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"new_items": [{"sku": ..., "brand": ..., "category": ..., ...}]}
    """
    client = MPStatsClient(MPSTATS_API_TOKEN)
    all_new_items = []

    try:
        for cat_path in CATEGORIES:
            cat_name = cat_path.split("/")[-1]
            logger.info("Fetching new items for category: %s", cat_name)

            # POST request with pagination
            url = f"{client.BASE_URL}/get/category"
            payload = {
                "startRow": 0,
                "endRow": 500,
                "filterModel": {},
                "sortModel": [],
            }
            params = {"path": cat_path, "d1": period_start, "d2": period_end}

            result = client._request("POST", url, params=params, json=payload)

            if not result:
                logger.warning("No data for category: %s", cat_name)
                continue

            # Result can be a list of items or dict with 'data' key
            items = result
            if isinstance(result, dict):
                items = result.get("data", result.get("items", []))
            if not isinstance(items, list):
                items = []

            for item in items:
                revenue = item.get("revenue", 0) or 0
                first_seen = item.get("first_seen", "") or ""

                # Filter: revenue threshold + first_seen after prev_start
                if revenue < NEW_ITEMS_MIN_REVENUE:
                    continue
                if first_seen and first_seen < prev_start:
                    continue

                all_new_items.append({
                    "sku": item.get("id") or item.get("sku") or item.get("nmID"),
                    "brand": item.get("brand", ""),
                    "category": cat_name,
                    "name": item.get("name", ""),
                    "price": item.get("price", 0),
                    "revenue": revenue,
                    "sales": item.get("sales", 0) or 0,
                    "first_seen": first_seen,
                    "rating": item.get("rating", 0),
                    "reviews": item.get("reviews", item.get("feedbacks", 0)),
                })

            time.sleep(0.5)  # Rate limiting between categories

    finally:
        client.close()

    # Sort by revenue desc, keep top 30
    all_new_items.sort(key=lambda x: x.get("revenue", 0), reverse=True)
    return {"new_items": all_new_items[:30]}
