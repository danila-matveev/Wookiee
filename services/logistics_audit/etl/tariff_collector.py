"""
Daily ETL: fetch WB box tariffs and upsert into Supabase wb_tariffs table.

Usage:
    python -m services.logistics_audit.etl.tariff_collector              # today
    python -m services.logistics_audit.etl.tariff_collector --date 2026-03-20
    python -m services.logistics_audit.etl.tariff_collector --backfill 30
    python -m services.logistics_audit.etl.tariff_collector --cabinet IP  # default: OOO
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from shared.data_layer.logistics import upsert_wb_tariffs
from shared.tool_logger import ToolLogger

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

from services.logistics_audit.api.wb_tariffs import fetch_tariffs_box

logger = logging.getLogger(__name__)
tool_logger = ToolLogger("wb-tariffs-collector")


def _get_api_key(cabinet: str) -> str:
    key = os.getenv(f"WB_API_KEY_{cabinet.upper()}")
    if not key:
        raise ValueError(f"Missing WB_API_KEY_{cabinet.upper()} in .env")
    return key


def build_tariff_rows(dt: date, tariffs: dict[str, object]) -> list[tuple]:
    """Convert tariff snapshots to wb_tariffs upsert rows."""
    return [
        (
            dt,
            snap.warehouse_name,
            snap.delivery_coef_pct,
            snap.box_delivery_base,
            snap.box_delivery_liter,
            snap.box_storage_base,
            0,
            snap.storage_coef_pct,
            snap.geo_name,
        )
        for snap in tariffs.values()
    ]


def collect_tariffs(dt: date, api_key: str) -> int:
    """Fetch tariffs for a single date and upsert into Supabase. Returns row count."""
    date_str = dt.isoformat()
    logger.info("Fetching tariffs for %s", date_str)

    tariffs = fetch_tariffs_box(api_key, date_str)
    if not tariffs:
        logger.warning("No tariffs returned for %s", date_str)
        return 0

    rows = build_tariff_rows(dt, tariffs)
    count = upsert_wb_tariffs(rows)
    logger.info("Upserted %d warehouse tariffs for %s", count, date_str)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="WB Tariff Collector → Supabase")
    parser.add_argument("--date", type=str, default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--backfill", type=int, default=None, help="Backfill last N days")
    parser.add_argument("--cabinet", type=str, default="OOO", help="WB cabinet: IP or OOO (default: OOO)")
    parser.add_argument("--trigger", type=str, default="manual", help="Trigger type: cron or manual")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    api_key = _get_api_key(args.cabinet)

    env = os.getenv("WOOKIEE_ENV", "local")
    run_id = tool_logger.start(
        trigger=args.trigger,
        user="cron" if args.trigger == "cron" else "danila",
        version="1.0",
        environment=env,
    )

    try:
        if args.backfill:
            total = 0
            for i in range(args.backfill):
                dt = date.today() - timedelta(days=i)
                total += collect_tariffs(dt, api_key)
            logger.info("Backfill complete: %d total rows across %d days", total, args.backfill)
            tool_logger.finish(
                run_id, status="success",
                items_processed=total,
                details={"mode": "backfill", "days": args.backfill, "cabinet": args.cabinet},
            )
        else:
            dt = date.fromisoformat(args.date) if args.date else date.today()
            rows = collect_tariffs(dt, api_key)
            tool_logger.finish(
                run_id, status="success",
                items_processed=rows,
                details={"mode": "daily", "date": dt.isoformat(), "cabinet": args.cabinet},
            )
    except Exception as exc:
        tool_logger.error(run_id, stage="collect_tariffs", message=str(exc))
        raise


if __name__ == "__main__":
    main()
