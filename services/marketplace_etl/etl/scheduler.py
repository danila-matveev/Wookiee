"""
ETL Scheduler.

Runs daily synchronization at a scheduled time (default 05:00 MSK).
Uses the `schedule` library for simplicity.
"""

import argparse
import logging
import signal
import time
from datetime import datetime, timedelta

import schedule

from services.marketplace_etl.etl.wb_etl import run_all_accounts as wb_sync
from services.marketplace_etl.etl.ozon_etl import run_all_accounts as ozon_sync
from services.marketplace_etl.etl.reconciliation import DataReconciliation
from services.marketplace_etl.config.database import SYNC_SCHEDULE

logger = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    global _shutdown
    logger.info(f"Received signal {signum}, shutting down...")
    _shutdown = True


def daily_sync():
    """
    Daily synchronization job.

    Syncs yesterday's data from both marketplaces and runs reconciliation.
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    logger.info(f"Daily sync started for {yesterday}")

    errors = []

    # WB
    try:
        logger.info("Running WB ETL...")
        wb_sync(yesterday, yesterday)
        logger.info("WB ETL completed")
    except Exception as e:
        logger.error(f"WB ETL failed: {e}")
        errors.append(f"WB: {e}")

    # Ozon
    try:
        logger.info("Running Ozon ETL...")
        ozon_sync(yesterday, yesterday)
        logger.info("Ozon ETL completed")
    except Exception as e:
        logger.error(f"Ozon ETL failed: {e}")
        errors.append(f"Ozon: {e}")

    # Reconciliation (non-critical)
    try:
        logger.info("Running reconciliation...")
        recon = DataReconciliation()
        recon.run(yesterday, yesterday)
    except Exception as e:
        logger.warning(f"Reconciliation failed (non-critical): {e}")

    # Summary
    if errors:
        logger.error(f"Daily sync completed with {len(errors)} error(s): {'; '.join(errors)}")
    else:
        logger.info(f"Daily sync completed successfully for {yesterday}")


def run_scheduler(sync_time=None):
    """
    Run scheduler loop until shutdown signal.

    Args:
        sync_time: Time string (HH:MM). Default from SYNC_SCHEDULE config.
    """
    global _shutdown

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if sync_time is None:
        sync_time = SYNC_SCHEDULE

    logger.info(f"Scheduler started, daily sync at {sync_time} MSK")

    schedule.every().day.at(sync_time).do(daily_sync)

    while not _shutdown:
        schedule.run_pending()
        time.sleep(30)

    logger.info("Scheduler stopped")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    parser = argparse.ArgumentParser(description='ETL Scheduler')
    parser.add_argument('--now', action='store_true', help='Run sync immediately')
    parser.add_argument('--time', default=None, help='Sync time (HH:MM, default from config)')

    args = parser.parse_args()

    if args.now:
        logger.info("Running sync immediately (manual trigger)")
        daily_sync()
    else:
        run_scheduler(sync_time=args.time)


if __name__ == '__main__':
    main()
