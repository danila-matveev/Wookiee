"""Collector: market category trends from MPStats."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from shared.config import MPSTATS_API_TOKEN
from scripts.market_review.config import CATEGORIES

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


def _aggregate_daily(data: dict) -> dict:
    """Aggregate daily trend data into totals.

    MPStats category trends return a dict with 'days' list, each having
    'revenue', 'sales', etc.
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


def collect_market_categories(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect category-level market data from MPStats.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (YYYY-MM-DD).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"categories": {"Комплекты белья": {"path": ..., "current": ..., ...}}}
    """
    client = MPStatsClient(MPSTATS_API_TOKEN)
    categories = {}

    try:
        for cat_path in CATEGORIES:
            name = cat_path.split("/")[-1]
            logger.info("Fetching category: %s", name)

            current_data = client.get_category_trends(cat_path, period_start, period_end)
            previous_data = client.get_category_trends(cat_path, prev_start, prev_end)

            current_agg = _aggregate_daily(current_data)
            previous_agg = _aggregate_daily(previous_data)
            delta = _calc_delta_pct(current_agg, previous_agg)

            categories[name] = {
                "path": cat_path,
                "current": current_agg,
                "previous": previous_agg,
                "delta_pct": delta,
            }
    finally:
        client.close()

    return {"categories": categories}
