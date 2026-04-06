"""Collector: competitor brand trends from MPStats."""

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


def _aggregate_brand(data: dict) -> dict:
    """Aggregate brand trend data into totals.

    MPStats brand trends return a dict with 'days' list.
    """
    days = data.get("days", [])
    if not days:
        return {"revenue": 0, "sales": 0, "avg_price": 0, "sku_count": 0}

    total_revenue = sum(d.get("revenue", 0) or 0 for d in days)
    total_sales = sum(d.get("sales", 0) or 0 for d in days)
    avg_price = round(total_revenue / total_sales, 2) if total_sales else 0
    # SKU count from the last day
    sku_count = days[-1].get("items_count", 0) or 0

    return {
        "revenue": total_revenue,
        "sales": total_sales,
        "avg_price": avg_price,
        "sku_count": sku_count,
    }


def collect_competitors_brands(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect competitor brand data from MPStats.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (YYYY-MM-DD).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"competitors": {"Birka Art": {"current": ..., "previous": ..., ...}}}
    """
    client = MPStatsClient(MPSTATS_API_TOKEN)
    competitors = {}

    try:
        for i, (brand_name, config) in enumerate(COMPETITORS.items()):
            if i > 0:
                time.sleep(0.5)  # Rate limiting between brands

            mpstats_path = config["mpstats_path"]
            logger.info("Fetching brand: %s", brand_name)

            current_data = client.get_brand_trends(mpstats_path, period_start, period_end)
            previous_data = client.get_brand_trends(mpstats_path, prev_start, prev_end)

            current_agg = _aggregate_brand(current_data)
            previous_agg = _aggregate_brand(previous_data)
            delta = _calc_delta_pct(current_agg, previous_agg)

            competitors[brand_name] = {
                "current": current_agg,
                "previous": previous_agg,
                "delta_pct": delta,
                "segment": config.get("segment", "unknown"),
                "instagram": config.get("instagram"),
            }
    finally:
        client.close()

    return {"competitors": competitors}
