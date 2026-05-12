#!/usr/bin/env python3
"""WB Promocodes weekly sync — CLI wrapper.

Usage:
    python scripts/run_wb_promocodes_sync.py                          # last closed week
    python scripts/run_wb_promocodes_sync.py --mode last_week
    python scripts/run_wb_promocodes_sync.py --mode specific --from 2026-04-13 --to 2026-04-19
    python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


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


def main() -> int:
    args = _parse_args()
    from services.sheets_sync.sync.sync_promocodes import run
    from shared.tool_logger import ToolLogger

    tl = ToolLogger("wb-promocodes-sync")
    period = args.date_from.isoformat() if args.date_from else ""
    with tl.run(
        trigger=os.getenv("RUN_TRIGGER", "manual"),
        user=os.getenv("USER_EMAIL", "unknown"),
        period_start=period,
        period_end=args.date_to.isoformat() if args.date_to else period,
    ) as run_meta:
        result = run(
            mode=args.mode,
            week_from=args.date_from,
            week_to=args.date_to,
            weeks_back=args.weeks_back,
            write_to_db=not args.skip_db,
            write_to_sheets=not args.skip_sheets,
        )

        print(f"status={result['status']}  added={result.get('rows_added', 0)}  "
              f"updated={result.get('rows_updated', 0)}  "
              f"db_written={result.get('db_rows_written', 0)}  "
              f"unknown={len(result.get('unknown_uuids', []))}")

        run_meta["items"] = result.get("rows_added", 0) + result.get("rows_updated", 0)
        if result.get("status") != "ok":
            run_meta["stage"] = "sync"
            raise RuntimeError(f"sync failed: status={result['status']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
