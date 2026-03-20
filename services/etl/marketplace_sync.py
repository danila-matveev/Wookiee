"""Marketplace ETL sync — daily cron job.

Wraps existing ETLOperator from agents/ibrahim/tasks/etl_operator.py.
Not an agent — deterministic script safe to run from cron or CLI.
"""

import asyncio
import logging

from agents.ibrahim.tasks.etl_operator import ETLOperator

logger = logging.getLogger(__name__)


async def run_marketplace_sync(date_from: str = None, date_to: str = None) -> dict:
    """Run marketplace ETL sync for WB and OZON.

    Args:
        date_from: Start date YYYY-MM-DD. Defaults to yesterday.
        date_to: End date YYYY-MM-DD. Defaults to yesterday.

    Returns:
        dict with 'wb', 'ozon', 'date_from', 'date_to' keys.
        Each channel is a list of {lk, status} dicts.
    """
    operator = ETLOperator()
    if date_from and date_to:
        logger.info("Running marketplace sync: %s → %s", date_from, date_to)
        return operator.sync_range(date_from, date_to)
    logger.info("Running marketplace sync for yesterday")
    return operator.sync_yesterday()


if __name__ == "__main__":
    import sys

    date_from_arg = sys.argv[1] if len(sys.argv) > 1 else None
    date_to_arg = sys.argv[2] if len(sys.argv) > 2 else None
    result = asyncio.run(run_marketplace_sync(date_from_arg, date_to_arg))
    print(result)
