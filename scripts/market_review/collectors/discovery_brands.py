"""Collector: discover fast-growing brands NOT in our competitor list.

Fetches top brands in each category, compares current vs previous period,
identifies brands with >30% growth that are NOT in COMPETITORS config.
Also fetches top SKUs for each discovered brand to understand growth drivers.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from shared.config import MPSTATS_API_TOKEN
from scripts.market_review.config import CATEGORIES, COMPETITORS

logger = logging.getLogger(__name__)

GROWTH_THRESHOLD_PCT = 30  # only flag brands growing >30%
MIN_REVENUE = 3_000_000    # ignore tiny brands below 3M RUB


def collect_discovery_brands(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Discover fast-growing brands outside our competitor list.

    For each category:
    1. Fetch brand list for current and previous periods
    2. Compare revenue, find brands with >30% growth and >3M revenue
    3. Filter out brands already in COMPETITORS
    4. For each discovered brand, fetch top SKUs to understand drivers

    Returns:
        {"discovery_brands": [
            {
                "brand": "...", "category": "...",
                "current_revenue": ..., "prev_revenue": ..., "growth_pct": ...,
                "top_skus": [{"sku": ..., "name": ..., "revenue": ..., "price": ..., ...}]
            }
        ]}
    """
    client = MPStatsClient(token=MPSTATS_API_TOKEN)
    known_brands = set(COMPETITORS.keys())
    known_brands.add("Wookiee")

    all_discoveries = []

    for cat_path in CATEGORIES:
        cat_name = cat_path.split("/")[-1]
        logger.info("[DiscoveryBrands] Scanning category: %s", cat_path)

        # Fetch brands for current period
        current_brands_raw = client.get_category_brands(
            path=cat_path, d1=period_start, d2=period_end
        )
        current_brands = {}
        for item in current_brands_raw.get("data", []):
            name = item.get("brand") or item.get("name", "")
            if name:
                current_brands[name] = item.get("revenue", 0) or 0

        # Fetch brands for previous period
        prev_brands_raw = client.get_category_brands(
            path=cat_path, d1=prev_start, d2=prev_end
        )
        prev_brands = {}
        for item in prev_brands_raw.get("data", []):
            name = item.get("brand") or item.get("name", "")
            if name:
                prev_brands[name] = item.get("revenue", 0) or 0

        time.sleep(0.5)

        # Find fast growers not in our list
        for brand_name, cur_rev in current_brands.items():
            if brand_name in known_brands:
                continue
            if cur_rev < MIN_REVENUE:
                continue

            prev_rev = prev_brands.get(brand_name, 0)
            if prev_rev > 0:
                growth = round((cur_rev - prev_rev) / prev_rev * 100, 1)
            elif cur_rev > MIN_REVENUE:
                growth = 999.0  # new brand
            else:
                continue

            if growth < GROWTH_THRESHOLD_PCT:
                continue

            # Fetch top SKUs for this brand
            logger.info("[DiscoveryBrands] Deep-dive: %s (growth +%.1f%%)", brand_name, growth)
            top_skus = _fetch_brand_top_skus(
                client, brand_name, period_start, period_end
            )

            all_discoveries.append({
                "brand": brand_name,
                "category": cat_name,
                "current_revenue": round(cur_rev),
                "prev_revenue": round(prev_rev),
                "growth_pct": growth,
                "top_skus": top_skus,
            })

            time.sleep(0.3)

    client.close()

    # Sort by growth desc, deduplicate by brand (keep highest growth)
    seen_brands = set()
    unique = []
    all_discoveries.sort(key=lambda x: x["growth_pct"], reverse=True)
    for d in all_discoveries:
        if d["brand"] not in seen_brands:
            seen_brands.add(d["brand"])
            unique.append(d)

    return {"discovery_brands": unique[:15]}  # top 15


def _fetch_brand_top_skus(
    client: MPStatsClient,
    brand_name: str,
    d1: str,
    d2: str,
    top_n: int = 5,
) -> list[dict]:
    """Fetch top SKUs of a brand by revenue."""
    result = client.get_brand_items(path=brand_name, d1=d1, d2=d2, start_row=0, end_row=50)
    items = result.get("data", [])

    skus = []
    for item in items:
        skus.append({
            "sku": str(item.get("id", "")),
            "name": item.get("name", ""),
            "revenue": round(item.get("revenue", 0) or 0),
            "sales": item.get("sales", 0) or 0,
            "price": item.get("price", 0) or 0,
            "rating": item.get("rating", 0) or 0,
            "reviews": item.get("reviews_count", 0) or 0,
            "first_date": item.get("start_date", "") or item.get("first_date", ""),
        })

    skus.sort(key=lambda x: x["revenue"], reverse=True)
    return skus[:top_n]
