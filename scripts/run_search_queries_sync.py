#!/usr/bin/env python3
"""WB Search Queries weekly sync — CLI wrapper (v2.0.0).

Usage:
    python scripts/run_search_queries_sync.py                            # last closed week
    python scripts/run_search_queries_sync.py --mode last_week
    python scripts/run_search_queries_sync.py --mode specific --from 2026-04-13 --to 2026-04-19
    python scripts/run_search_queries_sync.py --mode bootstrap --weeks-back 12
    python scripts/run_search_queries_sync.py --skip-db                  # Sheets-only

v2.0.0 — пишет одновременно в Google Sheets (агрегат) и Supabase
(marketing.search_queries_weekly + marketing.search_query_product_breakdown).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Always target the search queries spreadsheet
os.environ['SYNC_TEST_MODE'] = 'false'
from services.sheets_sync import config  # noqa: E402

config.TEST_MODE = False
config._active_spreadsheet_id = '1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("search_queries_sync")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["last_week", "specific", "bootstrap"],
                   default="last_week")
    p.add_argument("--from", dest="date_from", type=date.fromisoformat,
                   help="YYYY-MM-DD (specific mode)")
    p.add_argument("--to", dest="date_to", type=date.fromisoformat,
                   help="YYYY-MM-DD (specific mode)")
    p.add_argument("--weeks-back", type=int, default=12,
                   help="bootstrap depth (default 12)")
    p.add_argument("--skip-db", action="store_true",
                   help="write to Google Sheets only, skip Supabase write")
    p.add_argument("--skip-sheets", action="store_true",
                   help="write to Supabase only, skip Google Sheets (use for long backfills)")
    return p.parse_args()


def _last_closed_week() -> tuple[date, date]:
    """Return (Mon, Sun) of the most recent fully completed ISO week."""
    today = datetime.now().date()
    days_since_mon = today.weekday()  # Monday=0
    this_monday = today - timedelta(days=days_since_mon)
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday


def _resolve_weeks(args: argparse.Namespace) -> list[tuple[date, date]]:
    if args.mode == "last_week":
        return [_last_closed_week()]
    if args.mode == "specific":
        if not (args.date_from and args.date_to):
            raise SystemExit("specific mode requires --from and --to")
        return [(args.date_from, args.date_to)]
    if args.mode == "bootstrap":
        _, _ = _last_closed_week()
        weeks: list[tuple[date, date]] = []
        for i in range(args.weeks_back):
            mon = _last_closed_week()[0] - timedelta(weeks=i)
            weeks.append((mon, mon + timedelta(days=6)))
        return weeks
    raise SystemExit(f"Unknown mode: {args.mode}")


def _fmt(d: date) -> str:
    """date → DD.MM.YYYY (Sheets/sync convention)."""
    return d.strftime("%d.%m.%Y")


def main() -> int:
    args = _parse_args()
    weeks = _resolve_weeks(args)

    from services.sheets_sync.sync.sync_search_queries import sync
    from shared.tool_logger import ToolLogger

    tl = ToolLogger("wb-search-queries-sync")
    period_start = weeks[-1][0].isoformat()
    period_end = weeks[0][1].isoformat()

    with tl.run(
        trigger=os.getenv("RUN_TRIGGER", "manual"),
        user=os.getenv("USER_EMAIL", "unknown"),
        period_start=period_start,
        period_end=period_end,
    ) as run_meta:
        total_sheet_rows = 0
        # Process oldest week first so Sheets columns grow chronologically L→R.
        for mon, sun in reversed(weeks):
            logger.info("=== Week %s — %s ===", mon, sun)
            rows = sync(
                _fmt(mon), _fmt(sun),
                write_to_db=not args.skip_db,
                write_to_sheets=not args.skip_sheets,
            )
            total_sheet_rows += rows

        run_meta["items"] = total_sheet_rows
        print(f"status=ok  weeks={len(weeks)}  sheet_rows={total_sheet_rows}  "
              f"db={'skipped' if args.skip_db else 'written'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
