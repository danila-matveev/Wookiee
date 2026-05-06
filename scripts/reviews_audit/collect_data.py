"""Data collector v2 for reviews audit skill.

Fetches feedbacks, questions from WB API (both cabinets with dedup)
and orders/buyouts/returns from DB. Saves to expanded JSON.

Usage:
    python scripts/reviews_audit/collect_data.py \
        --date-from 2025-04-07 \
        --date-to 2026-04-07 \
        --cabinet both \
        --output /tmp/reviews_audit_data.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.clients.wb_client import WBClient
from shared.tool_logger import ToolLogger
from shared.data_layer import (
    get_wb_buyouts_returns_by_model,
    get_wb_buyouts_returns_by_artikul,
    get_wb_buyouts_returns_monthly,
)

logger = logging.getLogger(__name__)


def _filter_by_date(
    items: list[dict], date_from: str, date_to: str, date_field: str = "createdDate"
) -> list[dict]:
    """Filter items by date range."""
    filtered = []
    for item in items:
        created = item.get(date_field, "")
        if not created:
            continue
        date_str = created[:10]
        if date_from <= date_str < date_to:
            filtered.append(item)
    return filtered


def _deduplicate(items: list[dict], key: str = "id") -> list[dict]:
    """Remove duplicates by key, keeping first occurrence."""
    seen = set()
    result = []
    for item in items:
        k = item.get(key)
        if k and k not in seen:
            seen.add(k)
            result.append(item)
        elif not k:
            result.append(item)
    return result


def _fetch_from_cabinet(api_key: str, cabinet_name: str) -> tuple[list, list]:
    """Fetch feedbacks + questions from one WB cabinet."""
    client = WBClient(api_key=api_key, cabinet_name=cabinet_name)
    feedbacks = client.get_all_feedbacks()
    questions = client.get_all_questions()
    logger.info(f"[{cabinet_name}] Fetched {len(feedbacks)} feedbacks, {len(questions)} questions")
    return feedbacks, questions


def collect_reviews_data(
    date_from: str,
    date_to: str,
    output_path: str,
    cabinet: str = "both",
    api_key_ip: str | None = None,
    api_key_ooo: str | None = None,
) -> dict:
    """Collect all data for reviews audit v2.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        output_path: Path to save JSON output
        cabinet: 'ip', 'ooo', or 'both'
        api_key_ip: WB API key for IP cabinet
        api_key_ooo: WB API key for OOO cabinet

    Returns:
        Dict with collected data.
    """
    key_ip = api_key_ip or os.getenv("WB_API_KEY_IP", "")
    key_ooo = api_key_ooo or os.getenv("WB_API_KEY_OOO", "")

    all_feedbacks = []
    all_questions = []

    if cabinet in ("ip", "both") and key_ip:
        fb, q = _fetch_from_cabinet(key_ip, "IP")
        all_feedbacks.extend(fb)
        all_questions.extend(q)

    if cabinet in ("ooo", "both") and key_ooo:
        fb, q = _fetch_from_cabinet(key_ooo, "OOO")
        all_feedbacks.extend(fb)
        all_questions.extend(q)

    # Deduplicate (WB API returns same data for same brand across cabinets)
    all_feedbacks = _deduplicate(all_feedbacks, key="id")
    all_questions = _deduplicate(all_questions, key="id")

    # Filter by date
    feedbacks = _filter_by_date(all_feedbacks, date_from, date_to)
    questions = _filter_by_date(all_questions, date_from, date_to)
    logger.info(f"After dedup + date filter: {len(feedbacks)} feedbacks, {len(questions)} questions")

    # Fetch orders data from DB
    orders_by_model = []
    orders_by_artikul = []
    orders_monthly = []

    try:
        raw = get_wb_buyouts_returns_by_model(
            current_start=date_from, prev_start=date_from, current_end=date_to
        )
        orders_by_model = [
            {"period": r[0], "model": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_by_model: {e}")

    try:
        raw = get_wb_buyouts_returns_by_artikul(date_from=date_from, date_to=date_to)
        orders_by_artikul = [
            {"model": r[0], "artikul": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_by_artikul: {e}")

    try:
        raw = get_wb_buyouts_returns_monthly(date_from=date_from, date_to=date_to)
        orders_monthly = [
            {"month": str(r[0]), "model": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_monthly: {e}")

    # Build output
    result = {
        "metadata": {
            "date_from": date_from,
            "date_to": date_to,
            "cabinet": cabinet,
            "collected_at": datetime.now().isoformat(),
            "counts": {
                "feedbacks": len(feedbacks),
                "questions": len(questions),
                "models_with_orders": len(orders_by_model),
            },
        },
        "feedbacks": feedbacks,
        "questions": questions,
        "orders_by_model": orders_by_model,
        "orders_by_artikul": orders_by_artikul,
        "orders_monthly": orders_monthly,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Data saved to {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Collect data for reviews audit v2")
    parser.add_argument("--date-from", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--cabinet", default="both", choices=["ip", "ooo", "both"], help="WB cabinet")
    parser.add_argument("--output", default="/tmp/reviews_audit_data.json", help="Output JSON path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    tl = ToolLogger("/reviews-audit")
    with tl.run(period_start=args.date_from, period_end=args.date_to) as run_meta:
        result = collect_reviews_data(
            date_from=args.date_from,
            date_to=args.date_to,
            output_path=args.output,
            cabinet=args.cabinet,
        )
        if isinstance(result, dict):
            run_meta["items"] = result.get("total_reviews", 0) + result.get("total_questions", 0)


if __name__ == "__main__":
    main()
