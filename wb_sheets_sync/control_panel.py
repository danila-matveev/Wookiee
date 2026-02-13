"""Polling-based control panel via Google Sheets.

Reads 'Панель управления' sheet every N seconds.
When a checkbox (column B) is TRUE, runs the corresponding sync script.

Usage:
    python -m wb_sheets_sync.control_panel          # poll every 15s
    python -m wb_sheets_sync.control_panel --once    # single check
"""

import argparse
import logging
import time

from wb_sheets_sync.clients.sheets_client import get_client, get_moscow_datetime, get_moscow_now, get_or_create_worksheet
from wb_sheets_sync.config import GOOGLE_SA_FILE, LOG_LEVEL, SPREADSHEET_ID, get_sheet_name
from wb_sheets_sync.runner import SYNC_REGISTRY, run_all, run_sync
from wb_sheets_sync.status import update_status

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SHEET_NAME = "Панель управления"
POLL_INTERVAL = 15  # seconds
CHECKBOX_CHECK_INTERVAL = 4  # check data-sheet checkboxes every N poll cycles (~60s)

# Mapping: data sheet base name -> sync name (for C1 checkbox detection)
SHEET_TO_SYNC = {
    "МойСклад_АПИ": "moysklad",
    "WB остатки": "wb_stocks",
    "WB Цены": "wb_prices",
    "Ozon остатки и цены": "ozon",
    "Отзывы ООО": "wb_feedbacks",
    "Отзывы ИП": "wb_feedbacks",
    "Склейки WB": "wb_bundles",
    "Склейки Озон": "ozon_bundles",
}

# Mapping from row label (column A) to sync name
LABEL_TO_SYNC = {
    "МойСклад остатки": "moysklad",
    "WB остатки": "wb_stocks",
    "WB цены": "wb_prices",
    "Ozon остатки и цены": "ozon",
    "WB отзывы": "wb_feedbacks",
    "Склейки WB": "wb_bundles",
    "Склейки Озон": "ozon_bundles",
    "Аналитика запросов": "search_analytics",
}


def setup_panel(spreadsheet) -> None:
    """Create 'Панель управления' sheet with initial layout if empty."""
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=15, cols=7)

    # Check if already set up
    a1 = ws.acell("A1").value
    if a1:
        return

    # Write headers
    headers = [["Скрипт", "Запустить", "Дата от", "Дата до", "Статус", "Последний запуск", "Строк"]]
    ws.update(range_name="A1:G1", values=headers)

    # Write script names
    rows = [
        ["МойСклад остатки", "FALSE", "", "", "Ожидание", "", ""],
        ["WB остатки", "FALSE", "", "", "Ожидание", "", ""],
        ["WB цены", "FALSE", "", "", "Ожидание", "", ""],
        ["Ozon остатки и цены", "FALSE", "", "", "Ожидание", "", ""],
        ["WB отзывы", "FALSE", "", "", "Ожидание", "", ""],
        ["Склейки WB", "FALSE", "", "", "Ожидание", "", ""],
        ["Склейки Озон", "FALSE", "", "", "Ожидание", "", ""],
        ["Аналитика запросов", "FALSE", "", "", "Ожидание", "", ""],
        ["Запустить все", "FALSE", "", "", "", "", ""],
    ]
    ws.update(range_name=f"A2:G{len(rows) + 1}", values=rows)

    logger.info("Control panel initialized")


def poll_once() -> list:
    """Single poll cycle: check for TRUE checkboxes and run syncs.

    Returns list of SyncResult.
    """
    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=15, cols=7)

    # Ensure panel is set up
    setup_panel(spreadsheet)

    # Read all data
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        return []

    results = []
    run_all_flag = False

    for row_idx, row in enumerate(all_values[1:], start=2):  # Skip header
        if len(row) < 2:
            continue

        label = str(row[0]).strip()
        checked = str(row[1]).strip().upper() == "TRUE"

        if not checked:
            continue

        # Immediately uncheck and set "Выполняется..."
        ws.update_acell(f"B{row_idx}", "FALSE")

        if label == "Запустить все":
            run_all_flag = True
            ws.update_acell(f"E{row_idx}", "Выполняется...")
            continue

        sync_name = LABEL_TO_SYNC.get(label)
        if not sync_name:
            logger.warning("Unknown label: %s", label)
            continue

        # Check if already running
        status_val = str(row[4]).strip() if len(row) > 4 else ""
        if status_val == "Выполняется...":
            logger.info("Skipping %s (already running)", label)
            ws.update_acell(f"B{row_idx}", "FALSE")
            continue

        ws.update_acell(f"E{row_idx}", "Выполняется...")

        # Get optional dates
        start_date = str(row[2]).strip() if len(row) > 2 else ""
        end_date = str(row[3]).strip() if len(row) > 3 else ""

        # Run sync
        result = run_sync(
            sync_name,
            start_date=start_date or None,
            end_date=end_date or None,
        )
        results.append(result)

        # Update panel row
        date_str, time_str = get_moscow_datetime()
        status = "Готово" if result.status == "ok" else f"Ошибка: {result.error[:50]}"
        ws.update(range_name=f"E{row_idx}:G{row_idx}", values=[[
            status,
            f"{date_str} {time_str}",
            str(result.rows),
        ]])

    if run_all_flag:
        # Find the "Запустить все" row
        all_row_idx = None
        for row_idx, row in enumerate(all_values[1:], start=2):
            if str(row[0]).strip() == "Запустить все":
                all_row_idx = row_idx
                break

        all_results = run_all()
        results.extend(all_results)

        # Update each row with results
        for r in all_results:
            # Find the row for this sync
            for row_idx, row in enumerate(all_values[1:], start=2):
                label = str(row[0]).strip()
                if LABEL_TO_SYNC.get(label) == r.name:
                    date_str, time_str = get_moscow_datetime()
                    status = "Готово" if r.status == "ok" else f"Ошибка: {r.error[:50]}"
                    ws.update(range_name=f"E{row_idx}:G{row_idx}", values=[[
                        status,
                        f"{date_str} {time_str}",
                        str(r.rows),
                    ]])
                    break

        if all_row_idx:
            ws.update_acell(f"E{all_row_idx}", "Готово")

    # Update status sheet
    if results:
        try:
            update_status(results)
        except Exception as e:
            logger.error("Failed to update status sheet: %s", e)

    return results


def check_data_sheet_checkboxes() -> list:
    """Check C1 checkbox on each data sheet. If TRUE, reset and run sync.

    Returns list of SyncResult.
    """
    results = []
    try:
        gc = get_client(GOOGLE_SA_FILE)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        logger.error("Cannot open spreadsheet for checkbox check: %s", e)
        return results

    already_run = set()  # avoid running wb_feedbacks twice (ООО + ИП)

    for base_name, sync_name in SHEET_TO_SYNC.items():
        sheet_name = get_sheet_name(base_name)
        try:
            ws = spreadsheet.worksheet(sheet_name)
        except Exception:
            continue  # sheet doesn't exist yet

        try:
            c1 = str(ws.acell("C1").value or "").strip().upper()
        except Exception:
            continue

        if c1 != "TRUE":
            continue

        # Reset checkbox immediately
        try:
            ws.update_acell("C1", "FALSE")
        except Exception:
            pass

        if sync_name in already_run:
            continue
        already_run.add(sync_name)

        logger.info("Checkbox triggered on sheet '%s' -> running %s", sheet_name, sync_name)
        result = run_sync(sync_name)
        results.append(result)

    if results:
        try:
            update_status(results)
        except Exception as e:
            logger.error("Failed to update status: %s", e)

    return results


def poll_loop(interval: int = POLL_INTERVAL) -> None:
    """Continuously poll the control panel sheet.

    Also checks data-sheet checkboxes every ~60s and runs daily sync at 6:00 MSK.
    """
    logger.info("Control panel polling started (interval=%ds)", interval)

    # Reset any stale checkboxes on startup
    try:
        gc = get_client(GOOGLE_SA_FILE)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        setup_panel(spreadsheet)
    except Exception as e:
        logger.error("Failed to initialize panel: %s", e)

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

            # --- Control panel polling ---
            results = poll_once()
            if results:
                for r in results:
                    logger.info("  Completed: %s -> %s (%d rows)", r.name, r.status, r.rows)

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
    parser = argparse.ArgumentParser(description="Control panel for sync scripts (polling-based)")
    parser.add_argument("--once", action="store_true", help="Single poll cycle, then exit")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help=f"Poll interval in seconds (default: {POLL_INTERVAL})")

    args = parser.parse_args()

    if args.once:
        results = poll_once()
        for r in results:
            print(f"  {r.name}: {r.status} ({r.rows} rows, {r.duration_sec:.1f}s)")
        if not results:
            print("No pending tasks in control panel")
    else:
        poll_loop(interval=args.interval)


if __name__ == "__main__":
    main()
