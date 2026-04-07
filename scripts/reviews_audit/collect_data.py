"""Data collector for reviews audit skill.

Fetches feedbacks, questions, chats from WB API and
orders/buyouts/returns from DB. Saves everything to JSON.

Usage:
    python scripts/reviews_audit/collect_data.py \
        --date-from 2025-04-01 \
        --date-to 2026-04-01 \
        --output /tmp/reviews_audit_data.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.clients.wb_client import WBClient
from shared.data_layer import get_wb_buyouts_returns_by_model

logger = logging.getLogger(__name__)


def _filter_by_date(items: list[dict], date_from: str, date_to: str, date_field: str = "createdDate") -> list[dict]:
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


def collect_reviews_data(
    date_from: str,
    date_to: str,
    output_path: str,
    api_key: str | None = None,
) -> dict:
    """Collect all data for reviews audit.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        output_path: Path to save JSON output
        api_key: WB API key (defaults to WB_API_KEY_IP env var)

    Returns:
        Dict with collected data.
    """
    key = api_key or os.getenv("WB_API_KEY_IP", "")
    client = WBClient(api_key=key, cabinet_name="reviews-audit")

    # 1. Fetch feedbacks
    logger.info("Fetching feedbacks from WB API...")
    all_feedbacks = client.get_all_feedbacks()
    feedbacks = _filter_by_date(all_feedbacks, date_from, date_to)
    logger.info(f"Feedbacks: {len(feedbacks)} in period (of {len(all_feedbacks)} total)")

    # 2. Fetch questions
    logger.info("Fetching questions from WB API...")
    all_questions = client.get_all_questions()
    questions = _filter_by_date(all_questions, date_from, date_to)
    logger.info(f"Questions: {len(questions)} in period (of {len(all_questions)} total)")

    # 3. Fetch seller chats
    logger.info("Fetching seller chats from WB API...")
    all_chats = client.get_seller_chats(date_from=date_from)
    chats = _filter_by_date(all_chats, date_from, date_to, date_field="createdAt")
    logger.info(f"Chats: {len(chats)} in period")

    # 4. Fetch orders/buyouts/returns from DB
    logger.info("Fetching orders/buyouts/returns from DB...")
    try:
        raw_orders = get_wb_buyouts_returns_by_model(
            current_start=date_from,
            prev_start=date_from,
            current_end=date_to,
        )
        orders_stats = [
            {
                "period": row[0],
                "model": row[1],
                "orders_count": row[2],
                "buyout_count": row[3],
                "return_count": row[4],
            }
            for row in raw_orders
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders from DB: {e}")
        orders_stats = []

    # 5. Build output
    result = {
        "metadata": {
            "date_from": date_from,
            "date_to": date_to,
            "collected_at": datetime.now().isoformat(),
            "counts": {
                "feedbacks": len(feedbacks),
                "questions": len(questions),
                "chats": len(chats),
                "models_with_orders": len(orders_stats),
            },
        },
        "feedbacks": feedbacks,
        "questions": questions,
        "chats": chats,
        "orders_stats": orders_stats,
    }

    # 6. Save to JSON
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Data saved to {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Collect data for reviews audit")
    parser.add_argument("--date-from", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        default="/tmp/reviews_audit_data.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_reviews_data(
        date_from=args.date_from,
        date_to=args.date_to,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
