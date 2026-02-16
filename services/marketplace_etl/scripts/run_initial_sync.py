"""
Initial historical data sync script.

Loads data from API in 7-day batches starting from a given date.
Strategy: load 7 days -> verify -> continue until all history loaded.
"""

import argparse
import logging
import time
from datetime import datetime, timedelta

from services.marketplace_etl.etl.wb_etl import WildberriesETL
from services.marketplace_etl.etl.ozon_etl import OzonETL
from services.marketplace_etl.config.database import get_accounts

logger = logging.getLogger(__name__)


def run_initial_sync(date_from, date_to, batch_days=7, marketplace=None, pause_sec=5):
    """
    Run initial historical sync in batches.

    Args:
        date_from: Start date string (YYYY-MM-DD).
        date_to: End date string (YYYY-MM-DD).
        batch_days: Days per batch (default 7).
        marketplace: 'wb', 'ozon', or None (both).
        pause_sec: Pause between batches to respect rate limits.
    """
    start = datetime.strptime(date_from, '%Y-%m-%d')
    end = datetime.strptime(date_to, '%Y-%m-%d')
    accounts = get_accounts()

    total_days = (end - start).days + 1
    total_batches = (total_days + batch_days - 1) // batch_days

    logger.info(f"Initial sync: {date_from} -> {date_to} ({total_days} days, {total_batches} batches of {batch_days} days)")

    batch_num = 0
    current = start

    while current <= end:
        batch_end = min(current + timedelta(days=batch_days - 1), end)
        batch_from = current.strftime('%Y-%m-%d')
        batch_to = batch_end.strftime('%Y-%m-%d')
        batch_num += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"Batch {batch_num}/{total_batches}: {batch_from} -> {batch_to}")
        logger.info(f"{'='*60}")

        # WB
        if marketplace in (None, 'wb'):
            for acc in accounts.get('wb', []):
                try:
                    logger.info(f"WB ETL for {acc['lk']}")
                    etl = WildberriesETL(api_key=acc['api_key'], lk=acc['lk'])
                    etl.run(batch_from, batch_to)
                except Exception as e:
                    logger.error(f"WB ETL failed for {acc['lk']}: {e}")

        # OZON
        if marketplace in (None, 'ozon'):
            for acc in accounts.get('ozon', []):
                try:
                    logger.info(f"Ozon ETL for {acc['lk']}")
                    etl = OzonETL(
                        client_id=acc['client_id'],
                        api_key=acc['api_key'],
                        lk=acc['lk'],
                    )
                    etl.run(batch_from, batch_to)
                except Exception as e:
                    logger.error(f"Ozon ETL failed for {acc['lk']}: {e}")

        current = batch_end + timedelta(days=1)

        if current <= end:
            logger.info(f"Pausing {pause_sec}s between batches...")
            time.sleep(pause_sec)

    logger.info(f"\nInitial sync complete: {batch_num} batches processed")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    parser = argparse.ArgumentParser(description='Initial historical data sync')
    parser.add_argument('--date-from', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--batch-days', type=int, default=7, help='Days per batch (default: 7)')
    parser.add_argument('--marketplace', choices=['wb', 'ozon'], help='Only sync one marketplace')
    parser.add_argument('--pause', type=int, default=5, help='Seconds between batches (default: 5)')

    args = parser.parse_args()

    run_initial_sync(
        date_from=args.date_from,
        date_to=args.date_to,
        batch_days=args.batch_days,
        marketplace=args.marketplace,
        pause_sec=args.pause,
    )


if __name__ == '__main__':
    main()
