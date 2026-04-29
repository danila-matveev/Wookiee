"""
Bootstrap wb_tariffs schema, historical import, and one-time gap backfill.

Usage:
    python -m services.logistics_audit.etl.setup_wb_tariffs
"""
from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from shared.data_layer._connection import _get_supabase_connection
from services.logistics_audit.etl.import_historical_tariffs import (
    DEFAULT_WORKBOOK_PATH,
    import_historical_tariffs,
)
from services.logistics_audit.etl.tariff_collector import _get_api_key, collect_tariffs

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)
MIGRATION_PATH = PROJECT_ROOT / "database" / "sku" / "scripts" / "migrations" / "007_create_wb_tariffs.py"


@dataclass(frozen=True)
class VerificationStats:
    row_count: int
    min_date: date | None
    max_date: date | None


def load_migration_007():
    """Load migration 007 from its numeric filename."""
    spec = importlib.util.spec_from_file_location("migration_007_create_wb_tariffs", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load migration module from {MIGRATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compute_gap_dates(last_loaded_date: date | None, today: date) -> list[date]:
    """Return an inclusive list of dates that still need API backfill."""
    start_date = today if last_loaded_date is None else last_loaded_date + timedelta(days=1)
    if start_date > today:
        return []
    return [start_date + timedelta(days=offset) for offset in range((today - start_date).days + 1)]


def fetch_verification_stats() -> VerificationStats:
    """Read wb_tariffs row count and date bounds."""
    conn = _get_supabase_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MIN(dt), MAX(dt) FROM public.wb_tariffs")
        row_count, min_dt, max_dt = cur.fetchone()
        cur.close()
    finally:
        conn.close()

    return VerificationStats(
        row_count=int(row_count),
        min_date=min_dt,
        max_date=max_dt,
    )


def setup_wb_tariffs(today: date | None = None) -> VerificationStats:
    """Run schema setup, historical import, and gap backfill."""
    effective_today = today or date.today()

    logger.info("Applying migration 007 from %s", MIGRATION_PATH)
    migration = load_migration_007()
    migration.run()

    logger.info("Importing historical wb_tariffs from %s", DEFAULT_WORKBOOK_PATH)
    import_historical_tariffs(DEFAULT_WORKBOOK_PATH)

    verification = fetch_verification_stats()
    gap_dates = compute_gap_dates(verification.max_date, effective_today)
    if gap_dates:
        api_key = _get_api_key("OOO")
        logger.info(
            "Running one-time API backfill for %s dates: %s..%s",
            len(gap_dates),
            gap_dates[0],
            gap_dates[-1],
        )
        for gap_date in gap_dates:
            collect_tariffs(gap_date, api_key)
    else:
        logger.info("No wb_tariffs gap detected after historical import")

    final_stats = fetch_verification_stats()
    logger.info(
        "wb_tariffs verification: row_count=%s min_dt=%s max_dt=%s",
        final_stats.row_count,
        final_stats.min_date,
        final_stats.max_date,
    )
    return final_stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    setup_wb_tariffs()


if __name__ == "__main__":
    main()
