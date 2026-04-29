"""gspread access helpers: open spreadsheet, read dictionary, ensure analytics sheet."""
from __future__ import annotations

import logging
import os

import gspread

from shared.clients.sheets_client import get_client, get_or_create_worksheet

from .dictionary import parse_dictionary
from .sheet_layout import (
    DEFAULT_DATA_SHEET,
    DEFAULT_DICT_SHEET,
    FIXED_HEADERS,
    FIXED_NCOLS,
    METRIC_HEADERS_ROW,
    _col_letter,
)

logger = logging.getLogger(__name__)


def _open_spreadsheet():
    sa_file = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "services/sheets_sync/credentials/google_sa.json",
    )
    sid = os.getenv("PROMOCODES_SPREADSHEET_ID", "")
    if not sid:
        raise RuntimeError("PROMOCODES_SPREADSHEET_ID is not set")
    gc = get_client(sa_file)
    return gc.open_by_key(sid)


def read_dictionary_sheet() -> dict[str, dict]:
    """Open spreadsheet and parse the dictionary sheet."""
    sheet_name = os.getenv("PROMOCODES_DICT_SHEET", DEFAULT_DICT_SHEET)
    ss = _open_spreadsheet()
    try:
        ws = ss.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        logger.warning("Dictionary sheet '%s' not found — empty mapping", sheet_name)
        return {}
    return parse_dictionary(ws.get_all_values())


def _clear_conditional_formats(ws: gspread.Worksheet) -> None:
    for _ in range(10):
        try:
            ws.spreadsheet.batch_update({
                "requests": [
                    {"deleteConditionalFormatRule": {"sheetId": ws.id, "index": 0}}
                ]
            })
        except Exception:
            break


def ensure_analytics_sheet() -> gspread.Worksheet:
    """Ensure analytics sheet exists in pivot layout with fixed column headers."""
    sheet_name = os.getenv("PROMOCODES_DATA_SHEET", DEFAULT_DATA_SHEET)
    ss = _open_spreadsheet()
    ws = get_or_create_worksheet(ss, sheet_name, rows=2000, cols=200)

    # get_or_create_worksheet only sets cols at creation; existing sheets keep original count
    if getattr(ws, "col_count", 0) < 200:
        ws.resize(rows=2000, cols=200)

    current_row10 = ws.row_values(METRIC_HEADERS_ROW)
    needs_init = current_row10[:FIXED_NCOLS] != FIXED_HEADERS

    if needs_init:
        logger.info("Initialising pivot sheet (clearing old data)...")
        ws.clear()
        ws.resize(rows=2000, cols=200)
        _clear_conditional_formats(ws)

        end_col = _col_letter(FIXED_NCOLS)
        ws.update(
            range_name=f"A{METRIC_HEADERS_ROW}:{end_col}{METRIC_HEADERS_ROW}",
            values=[FIXED_HEADERS],
        )
        try:
            from services.sheets_sync.sync.format_promocodes_sheet import apply_base_formatting
            apply_base_formatting(ws)
        except Exception as e:
            logger.warning("Base formatting failed (sheet still usable): %s", e)

    return ws
