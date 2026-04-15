"""Collector: deep dive into competitor growth drivers — top SKUs per brand.

For each competitor from config, fetches their top-selling items to understand
which specific products drive their growth. Also identifies recently launched SKUs.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from shared.config import MPSTATS_API_TOKEN
from scripts.market_review.config import COMPETITORS

logger = logging.getLogger(__name__)

TOP_SKUS_PER_BRAND = 5


def collect_competitor_deep_dive(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Deep-dive analysis of competitor product portfolios.

    For each competitor brand:
    1. Fetch top SKUs by revenue for current period
    2. Identify recently launched items (first_date in last 2 months)
    3. Calculate each SKU's share of brand total revenue

    Returns:
        {"competitor_skus": {
            "SOGU": {
                "total_revenue": ...,
                "top_skus": [...],
                "new_launches": [...],  # items launched in current or prev period
                "growth_driver_categories": {"Боди": 42%, "Комплекты": 35%, ...}
            }
        }}
    """
    client = MPStatsClient(token=MPSTATS_API_TOKEN)
    result = {}

    for brand_name, brand_cfg in COMPETITORS.items():
        mpstats_path = brand_cfg["mpstats_path"]
        logger.info("[CompetitorDeepDive] Analyzing: %s", brand_name)

        # Fetch brand items for current period
        items_raw = client.get_brand_items(
            path=mpstats_path, d1=period_start, d2=period_end,
            start_row=0, end_row=100
        )
        items = items_raw.get("data", [])

        if not items:
            result[brand_name] = {
                "total_revenue": 0,
                "top_skus": [],
                "new_launches": [],
                "growth_driver_categories": {},
                "note": "no data from MPStats",
            }
            time.sleep(0.3)
            continue

        # Parse items
        all_skus = []
        category_revenue = {}
        total_revenue = 0
        new_launches = []

        for item in items:
            revenue = item.get("revenue", 0) or 0
            total_revenue += revenue

            cat = item.get("category", "") or item.get("subject", "") or "Unknown"
            category_revenue[cat] = category_revenue.get(cat, 0) + revenue

            sku_data = {
                "sku": str(item.get("id", "")),
                "name": item.get("name", ""),
                "revenue": round(revenue),
                "sales": item.get("sales", 0) or 0,
                "price": item.get("price", 0) or 0,
                "rating": item.get("rating", 0) or 0,
                "reviews": item.get("reviews_count", 0) or 0,
                "category": cat,
                "first_date": item.get("start_date", "") or item.get("first_date", ""),
            }
            all_skus.append(sku_data)

            # Check if recently launched (first seen in current or previous period)
            first_date = sku_data["first_date"]
            if first_date and first_date >= prev_start:
                new_launches.append(sku_data)

        # Sort by revenue
        all_skus.sort(key=lambda x: x["revenue"], reverse=True)
        new_launches.sort(key=lambda x: x["revenue"], reverse=True)

        # Category breakdown as percentages
        growth_drivers = {}
        if total_revenue > 0:
            for cat, rev in sorted(category_revenue.items(), key=lambda x: x[1], reverse=True):
                pct = round(rev / total_revenue * 100, 1)
                if pct >= 5:  # only show categories with >5% share
                    growth_drivers[cat] = pct

        result[brand_name] = {
            "total_revenue": round(total_revenue),
            "top_skus": all_skus[:TOP_SKUS_PER_BRAND],
            "new_launches": new_launches[:5],
            "growth_driver_categories": growth_drivers,
        }

        time.sleep(0.5)

    client.close()
    return {"competitor_skus": result}
