from __future__ import annotations

"""Google Sheets client wrapper (gspread)."""

import logging
from datetime import datetime

import gspread
import pytz
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client(sa_file: str) -> gspread.Client:
    """Create authenticated gspread client from Service Account JSON."""
    creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return gspread.authorize(creds)


def get_moscow_now() -> datetime:
    """Return current datetime in Moscow timezone."""
    return datetime.now(pytz.timezone("Europe/Moscow"))


def get_moscow_datetime() -> tuple[str, str]:
    """Return (date_str DD.MM.YYYY, time_str HH:MM) in Moscow timezone."""
    now = get_moscow_now()
    return now.strftime("%d.%m.%Y"), now.strftime("%H:%M")


def to_number(value):
    """Convert a string value to int or float if possible.

    Critical for Google Sheets: Python float -> Sheets stores as number -> displays with comma.
    Python string "4.90" -> Sheets stores as text -> displays with dot.
    """
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return value
    s = value.strip().lstrip("'")
    if not s:
        return ""
    s = s.replace(",", ".").replace("\xa0", "").replace(" ", "")
    try:
        f = float(s)
        return int(f) if f == int(f) and "." not in s else f
    except (ValueError, TypeError):
        return value


def set_checkbox(ws: gspread.Worksheet, cell: str = "C1") -> None:
    """Create a checkbox (Data Validation Boolean) in the given cell."""
    row, col = gspread.utils.a1_to_rowcol(cell)
    ws.spreadsheet.batch_update({
        "requests": [{
            "setDataValidation": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": col - 1,
                    "endColumnIndex": col,
                },
                "rule": {
                    "condition": {"type": "BOOLEAN"},
                    "showCustomUi": True,
                },
            }
        }]
    })
    ws.update_acell(cell, "FALSE")


def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet, name: str, rows: int = 1000, cols: int = 50
) -> gspread.Worksheet:
    """Get worksheet by name, create if it doesn't exist."""
    try:
        return spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        logger.info("Sheet '%s' not found, creating...", name)
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def clear_and_write(
    worksheet: gspread.Worksheet,
    headers: list[str],
    data: list[list],
    meta_cells: list[tuple[int, int, str]] | None = None,
    header_row: int = 3,
    data_start_row: int = 4,
) -> int:
    """Clear sheet from header_row down, write headers + data, return row count.

    Args:
        worksheet: Target worksheet.
        headers: Column headers.
        data: List of rows (each row is a list of values).
        meta_cells: Optional list of (row, col, value) for metadata (date/time).
        header_row: Row number for headers (1-indexed).
        data_start_row: Row number where data starts.

    Returns:
        Number of data rows written.
    """
    # Clear old data from header_row down
    last_row = worksheet.row_count
    last_col = max(len(headers), worksheet.col_count)
    if last_row >= header_row:
        worksheet.batch_clear(
            [f"{_cell_ref(header_row, 1)}:{_cell_ref(last_row, last_col)}"]
        )

    # Write metadata cells
    if meta_cells:
        cells_to_update = []
        for row, col, value in meta_cells:
            cells_to_update.append(
                gspread.Cell(row=row, col=col, value=value)
            )
        if cells_to_update:
            worksheet.update_cells(cells_to_update)

    # Write headers
    if headers:
        worksheet.update(
            range_name=f"{_cell_ref(header_row, 1)}:{_cell_ref(header_row, len(headers))}",
            values=[headers],
        )

    # Write data in batches (gspread handles up to ~50k cells per call)
    if data:
        num_cols = len(data[0]) if data else len(headers)
        end_row = data_start_row + len(data) - 1
        worksheet.update(
            range_name=f"{_cell_ref(data_start_row, 1)}:{_cell_ref(end_row, num_cols)}",
            values=data,
        )

    logger.info("Written %d rows to sheet '%s'", len(data), worksheet.title)
    return len(data)


def write_range(
    worksheet: gspread.Worksheet,
    start_row: int,
    start_col: int,
    data: list[list],
) -> None:
    """Write a block of data starting at (start_row, start_col)."""
    if not data:
        return
    num_rows = len(data)
    num_cols = len(data[0])
    end_row = start_row + num_rows - 1
    end_col = start_col + num_cols - 1
    worksheet.update(
        range_name=f"{_cell_ref(start_row, start_col)}:{_cell_ref(end_row, end_col)}",
        values=data,
    )


def _cell_ref(row: int, col: int) -> str:
    """Convert (row, col) to A1 notation. E.g. (1, 1) -> 'A1', (3, 27) -> 'AA3'."""
    result = ""
    c = col
    while c > 0:
        c, remainder = divmod(c - 1, 26)
        result = chr(65 + remainder) + result
    return f"{result}{row}"
