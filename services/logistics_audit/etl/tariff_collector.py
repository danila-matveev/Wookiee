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

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

from services.logistics_audit.api.wb_tariffs import fetch_tariffs_box

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase connection (reuse sku_database pattern)
# ---------------------------------------------------------------------------

_SUPABASE_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "postgres"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
    "sslmode": "require",
}

UPSERT_SQL = """
INSERT INTO wb_tariffs (dt, warehouse_name, delivery_coef, logistics_1l,
                        logistics_extra_l, storage_1l_day, acceptance, geo_name)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (dt, warehouse_name) DO UPDATE SET
    delivery_coef     = EXCLUDED.delivery_coef,
    logistics_1l      = EXCLUDED.logistics_1l,
    logistics_extra_l = EXCLUDED.logistics_extra_l,
    storage_1l_day    = EXCLUDED.storage_1l_day,
    acceptance        = EXCLUDED.acceptance,
    geo_name          = EXCLUDED.geo_name
"""


def _get_api_key(cabinet: str) -> str:
    key = os.getenv(f"WB_API_KEY_{cabinet.upper()}")
    if not key:
        raise ValueError(f"Missing WB_API_KEY_{cabinet.upper()} in .env")
    return key


def collect_tariffs(dt: date, api_key: str) -> int:
    """Fetch tariffs for a single date and upsert into Supabase. Returns row count."""
    import psycopg2

    date_str = dt.isoformat()
    logger.info("Fetching tariffs for %s", date_str)

    tariffs = fetch_tariffs_box(api_key, date_str)
    if not tariffs:
        logger.warning("No tariffs returned for %s", date_str)
        return 0

    rows = [
        (
            dt,
            snap.warehouse_name,
            snap.delivery_coef_pct,
            snap.box_delivery_base,
            snap.box_delivery_liter,
            snap.box_storage_base,
            snap.box_storage_liter,
            snap.geo_name,
        )
        for snap in tariffs.values()
    ]

    conn = psycopg2.connect(**_SUPABASE_CONFIG)
    try:
        cur = conn.cursor()
        cur.executemany(UPSERT_SQL, rows)
        conn.commit()
        cur.close()
    finally:
        conn.close()

    logger.info("Upserted %d warehouse tariffs for %s", len(rows), date_str)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="WB Tariff Collector → Supabase")
    parser.add_argument("--date", type=str, default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--backfill", type=int, default=None, help="Backfill last N days")
    parser.add_argument("--cabinet", type=str, default="OOO", help="WB cabinet: IP or OOO (default: OOO)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    api_key = _get_api_key(args.cabinet)

    if args.backfill:
        total = 0
        for i in range(args.backfill):
            dt = date.today() - timedelta(days=i)
            total += collect_tariffs(dt, api_key)
        logger.info("Backfill complete: %d total rows across %d days", total, args.backfill)
    else:
        dt = date.fromisoformat(args.date) if args.date else date.today()
        collect_tariffs(dt, api_key)


if __name__ == "__main__":
    main()
