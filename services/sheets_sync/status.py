from __future__ import annotations

"""Update 'Статус синхронизации' sheet after sync runs."""

import logging

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    write_range,
)
from services.sheets_sync.config import GOOGLE_SA_FILE, SPREADSHEET_ID, TEST_MODE, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Статус синхронизации"

HEADERS = ["Скрипт", "Лист", "Последний запуск", "Статус", "Строк", "Длительность", "Ошибка"]


def update_status(results: list) -> None:
    """Write sync results to status sheet.

    Args:
        results: List of SyncResult objects (from runner.py).
    """
    if not results:
        return

    try:
        gc = get_client(GOOGLE_SA_FILE)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        sheet_name = get_sheet_name(SHEET_NAME)
        ws = get_or_create_worksheet(spreadsheet, sheet_name)

        date_str, time_str = get_moscow_datetime()
        timestamp = f"{date_str} {time_str}"

        # Read existing data to merge with new results
        existing = _read_existing_status(ws)

        # Update with new results
        for r in results:
            suffix = "_TEST" if TEST_MODE else ""
            existing[r.name] = [
                r.name,
                f"{r.sheet_name}{suffix}",
                timestamp,
                r.status,
                str(r.rows),
                f"{r.duration_sec:.1f}s",
                r.error[:100] if r.error else "",
            ]

        # Write headers + all data
        ws.clear()
        write_range(ws, start_row=1, start_col=1, data=[HEADERS])

        rows = list(existing.values())
        if rows:
            write_range(ws, start_row=2, start_col=1, data=rows)

        logger.info("Status sheet updated with %d entries", len(rows))

    except Exception as e:
        logger.error("Failed to update status sheet: %s", e)


def _read_existing_status(ws) -> dict[str, list]:
    """Read existing status entries, keyed by script name."""
    result = {}
    try:
        all_values = ws.get_all_values()
        for row in all_values[1:]:  # Skip header
            if row and row[0]:
                result[row[0]] = row
    except Exception:
        pass
    return result
