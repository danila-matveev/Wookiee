"""Checkbox-based sync trigger + daily auto-run.

Polls data-sheet checkboxes (C1/D1) every ~60s.
When a checkbox is TRUE, resets it and runs the corresponding sync.
Also runs all syncs daily at 6:00 MSK.

Usage:
    python -m services.sheets_sync.control_panel          # poll continuously
    python -m services.sheets_sync.control_panel --once    # single check
"""

import argparse
import logging
import time

from services.sheets_sync.clients.sheets_client import get_client, get_moscow_now
from services.sheets_sync.config import GOOGLE_SA_FILE, LOG_LEVEL, SPREADSHEET_IDS, get_sheet_name
from services.sheets_sync.runner import run_all, run_sync
from services.sheets_sync.status import update_status

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 15  # seconds
CHECKBOX_CHECK_INTERVAL = 4  # check data-sheet checkboxes every N poll cycles (~60s)

# Mapping: data sheet base name -> sync name (for C1 checkbox detection)
SHEET_TO_SYNC = {
    "МойСклад_АПИ": "moysklad",
    "WB остатки": "wb_stocks",
    "WB цены": "wb_prices",
    "Ozon остатки и цены": "ozon",
    "Отзывы ООО": {"sync": "wb_feedbacks", "date_cells": ("A5", "B5")},
    "Отзывы ИП": {"sync": "wb_feedbacks", "date_cells": ("A5", "B5")},
    "Фин данные": {"sync": "fin_data", "checkbox": "D1"},
    "Склейки WB": "wb_bundles",
    "Склейки Озон": "ozon_bundles",
    "Фин данные NEW": {"sync": "fin_data_new", "checkbox": "D1"},
}


def check_data_sheet_checkboxes() -> list:
    """Check checkbox on each data sheet across all configured spreadsheets.

    Supports custom checkbox cell via dict format in SHEET_TO_SYNC:
    - str value: sync name, checkbox in C1 (default)
    - dict value: {"sync": name, "checkbox": "D1"} for custom cell

    Returns list of SyncResult.
    """
    results = []
    gc = None

    for sid in SPREADSHEET_IDS:
        try:
            if gc is None:
                gc = get_client(GOOGLE_SA_FILE)
            spreadsheet = gc.open_by_key(sid)
        except Exception as e:
            logger.error("Cannot open spreadsheet %s for checkbox check: %s", sid[:8], e)
            continue

        already_run = set()  # avoid running wb_feedbacks twice (ООО + ИП) per spreadsheet

        for base_name, entry in SHEET_TO_SYNC.items():
            # Support both str and dict formats
            if isinstance(entry, dict):
                sync_name = entry["sync"]
                checkbox_cell = entry.get("checkbox", "C1")
            else:
                sync_name = entry
                checkbox_cell = "C1"

            sheet_name = get_sheet_name(base_name)
            try:
                ws = spreadsheet.worksheet(sheet_name)
            except Exception:
                continue  # sheet doesn't exist yet

            try:
                cb_val = str(ws.acell(checkbox_cell).value or "").strip().upper()
            except Exception:
                continue

            if cb_val != "TRUE":
                continue

            # Reset checkbox immediately
            try:
                ws.update_acell(checkbox_cell, "FALSE")
            except Exception:
                pass

            if sync_name in already_run:
                continue
            already_run.add(sync_name)

            # Read dates from configured cells (fin_data: B1/C1, feedbacks: A5/B5)
            start_date = None
            end_date = None
            if sync_name in ("fin_data", "fin_data_new"):
                try:
                    b1 = (ws.acell("B1").value or "").strip()
                    c1 = (ws.acell("C1").value or "").strip()
                    if b1 and c1:
                        start_date = b1
                        end_date = c1
                except Exception:
                    pass
            elif isinstance(entry, dict) and "date_cells" in entry:
                try:
                    cell_start, cell_end = entry["date_cells"]
                    v_start = (ws.acell(cell_start).value or "").strip()
                    v_end = (ws.acell(cell_end).value or "").strip()
                    if v_start:
                        start_date = v_start
                    if v_end:
                        end_date = v_end
                except Exception:
                    pass

            logger.info("Checkbox triggered on sheet '%s' [%s] -> running %s", sheet_name, sid[:8], sync_name)
            result = run_sync(sync_name, start_date=start_date, end_date=end_date, spreadsheet_id=sid)
            results.append(result)

    if results:
        try:
            update_status(results)
        except Exception as e:
            logger.error("Failed to update status: %s", e)

    return results


def poll_loop(interval: int = POLL_INTERVAL) -> None:
    """Continuously poll data-sheet checkboxes and run daily sync at 6:00 MSK."""
    logger.info("Polling started (interval=%ds)", interval)

    last_daily_run_date = None
    cycle_count = 0

    while True:
        try:
            # --- Daily auto-run at 6:00 MSK ---
            now = get_moscow_now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour == 6 and now.minute < 2 and last_daily_run_date != today_str:
                logger.info("Daily 6:00 MSK auto-run triggered")
                daily_results = run_all()
                last_daily_run_date = today_str
                try:
                    update_status(daily_results)
                except Exception as e:
                    logger.error("Failed to update status after daily run: %s", e)
                for r in daily_results:
                    logger.info("  Daily: %s -> %s (%d rows)", r.name, r.status, r.rows)

            # --- Data-sheet checkbox detection (every ~60s) ---
            cycle_count += 1
            if cycle_count >= CHECKBOX_CHECK_INTERVAL:
                cycle_count = 0
                cb_results = check_data_sheet_checkboxes()
                if cb_results:
                    for r in cb_results:
                        logger.info("  Checkbox: %s -> %s (%d rows)", r.name, r.status, r.rows)

        except KeyboardInterrupt:
            logger.info("Polling stopped by user")
            break
        except Exception as e:
            logger.error("Poll error: %s", e)

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Sync trigger: checkbox polling + daily auto-run")
    parser.add_argument("--once", action="store_true", help="Single checkbox check, then exit")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help=f"Poll interval in seconds (default: {POLL_INTERVAL})")

    args = parser.parse_args()

    if args.once:
        results = check_data_sheet_checkboxes()
        for r in results:
            print(f"  {r.name}: {r.status} ({r.rows} rows, {r.duration_sec:.1f}s)")
        if not results:
            print("No pending checkbox triggers")
    else:
        poll_loop(interval=args.interval)


if __name__ == "__main__":
    main()
