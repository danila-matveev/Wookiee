"""
Daily sync script.

Syncs yesterday's data from both marketplaces, then optionally runs reconciliation.
Designed to be called by scheduler or cron.
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

from services.marketplace_etl.etl.wb_etl import run_all_accounts as wb_sync
from services.marketplace_etl.etl.ozon_etl import run_all_accounts as ozon_sync
from services.marketplace_etl.etl.reconciliation import DataReconciliation

logger = logging.getLogger(__name__)


def run_daily_sync(target_date=None, skip_reconciliation=False):
    """
    Run daily sync for a specific date.

    Args:
        target_date: Date string (YYYY-MM-DD). Default: yesterday.
        skip_reconciliation: Skip reconciliation step.
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    logger.info(f"Daily sync started for {target_date}")

    errors = []

    # WB sync
    try:
        logger.info("Running WB ETL...")
        wb_sync(target_date, target_date)
        logger.info("WB ETL completed")
    except Exception as e:
        logger.error(f"WB ETL failed: {e}")
        errors.append(f"WB: {e}")

    # OZON sync
    try:
        logger.info("Running Ozon ETL...")
        ozon_sync(target_date, target_date)
        logger.info("Ozon ETL completed")
    except Exception as e:
        logger.error(f"Ozon ETL failed: {e}")
        errors.append(f"Ozon: {e}")

    # Reconciliation
    if not skip_reconciliation:
        try:
            logger.info("Running reconciliation...")
            recon = DataReconciliation()
            recon.run(target_date, target_date)
        except Exception as e:
            logger.warning(f"Reconciliation failed (non-critical): {e}")

    # Summary
    if errors:
        logger.error(f"Daily sync completed with {len(errors)} error(s): {'; '.join(errors)}")
    else:
        logger.info(f"Daily sync completed successfully for {target_date}")

    return len(errors) == 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    parser = argparse.ArgumentParser(description='Daily data sync')
    parser.add_argument('--date', help='Target date (YYYY-MM-DD, default: yesterday)')
    parser.add_argument('--skip-reconciliation', action='store_true', help='Skip reconciliation')

    args = parser.parse_args()

    success = run_daily_sync(
        target_date=args.date,
        skip_reconciliation=args.skip_reconciliation,
    )
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
