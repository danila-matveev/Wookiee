#!/usr/bin/env python3
"""Weekly sync of WB search query analytics.

Usage:
    python scripts/run_search_queries_sync.py              # auto last week
    python scripts/run_search_queries_sync.py 07.04.2026 13.04.2026  # specific dates

Designed to run as a weekly cron job (Monday morning after the week ends).
Writes to spreadsheet 1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY.
"""

import os
import sys
import logging

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Configure for the search queries spreadsheet
os.environ['SYNC_TEST_MODE'] = 'false'

from services.sheets_sync import config
config.TEST_MODE = False
config._active_spreadsheet_id = '1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("search_queries_sync")


def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else None
    end_date = sys.argv[2] if len(sys.argv) > 2 else None

    if start_date:
        logger.info("Manual dates: %s - %s", start_date, end_date)
    else:
        logger.info("Auto mode: last full week")

    from services.sheets_sync.sync.sync_search_queries import sync
    rows = sync(start_date, end_date)
    logger.info("Done: %d rows written", rows)


if __name__ == "__main__":
    main()
