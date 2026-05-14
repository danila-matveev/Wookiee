"""Batch CellUpdate / RowAppend / RowDelete operations into Sheets API calls."""
from __future__ import annotations

import logging
import time
from typing import Sequence

import gspread
from google.oauth2.service_account import Credentials

from services.sheets_sync.hub_to_sheets.config import (
    CATALOG_MIRROR_SHEET_ID,
    GOOGLE_SA_FILE,
)
from services.sheets_sync.hub_to_sheets.diff import (
    CellUpdate,
    RowAppend,
    RowDelete,
)

logger = logging.getLogger(__name__)

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# How many cells fit in one batchUpdate. Google's hard limit is 10M cells per
# request; we stay well below to keep payloads predictable and recoverable.
CELL_UPDATE_BATCH_SIZE = 200


def _client() -> gspread.Client:
    creds = Credentials.from_service_account_file(GOOGLE_SA_FILE, scopes=SHEETS_SCOPES)
    return gspread.authorize(creds)


def _col_letter(col: int) -> str:
    """Convert a 1-based column index to A1 letters."""
    letters = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _a1(sheet_name: str, row: int, col: int) -> str:
    return f"'{sheet_name}'!{_col_letter(col)}{row}"


class SheetsBatchWriter:
    """Apply CellUpdate / RowAppend / RowDelete operations to a spreadsheet.

    One instance ≡ one open spreadsheet. Re-uses a single gspread client.
    Retries on 429/5xx with exponential backoff.
    """

    def __init__(
        self,
        spreadsheet_id: str = "",
        *,
        dry_run: bool = False,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id or CATALOG_MIRROR_SHEET_ID
        if not self.spreadsheet_id:
            raise RuntimeError("CATALOG_MIRROR_SHEET_ID is not set in .env")
        self.dry_run = dry_run
        self._sh: gspread.Spreadsheet | None = None

    @property
    def spreadsheet(self) -> gspread.Spreadsheet:
        if self._sh is None:
            self._sh = _client().open_by_key(self.spreadsheet_id)
        return self._sh

    def read_sheet(self, sheet_name: str) -> tuple[list[str], list[list[str]]]:
        """Return (header, data_rows) for a single tab.

        Header is the first row. Every subsequent row is returned in its
        original sheet position — including fully blank rows — so that the
        index in the returned list maps 1-to-1 to a physical sheet row
        (row_index = header_row + 1 + list_offset). Blank rows are still
        skipped at the anchor-index level (see anchor.build_anchor_index),
        so they don't generate phantom updates.

        Rows are normalised to the header's width (shorter rows are padded
        with "" and longer rows are truncated).
        """
        ws = self.spreadsheet.worksheet(sheet_name)
        all_values = ws.get_all_values()
        if not all_values:
            return [], []
        header = all_values[0]
        width = len(header)
        rows: list[list[str]] = []
        for row in all_values[1:]:
            if len(row) < width:
                row = row + [""] * (width - len(row))
            rows.append(row[:width])
        return header, rows

    def apply_updates(
        self,
        updates: Sequence[CellUpdate],
        appends: Sequence[RowAppend],
        deletes: Sequence[RowDelete],
    ) -> dict:
        """Apply the three ops lists. Returns a metrics dict."""
        cells_updated = 0
        rows_appended = 0
        rows_deleted = 0

        if self.dry_run:
            logger.info(
                "DRY-RUN: would touch %d cells, append %d rows, delete %d rows",
                len(updates) + sum(len(a.values) for a in appends),
                len(appends),
                len(deletes),
            )
            return {
                "cells_updated": len(updates) + sum(len(a.values) for a in appends),
                "rows_appended": len(appends),
                "rows_deleted": len(deletes),
            }

        # 1) Cell updates — batched.
        if updates:
            cells_updated += self._batch_cell_updates(updates)

        # 2) Appends — grouped per sheet.
        if appends:
            rows_appended += self._apply_appends(appends)
            cells_updated += sum(len(a.values) for a in appends)

        # 3) Deletes — descending row order, per sheet, so row indices stay valid.
        if deletes:
            rows_deleted += self._apply_deletes(deletes)

        return {
            "cells_updated": cells_updated,
            "rows_appended": rows_appended,
            "rows_deleted": rows_deleted,
        }

    # --- internal helpers --------------------------------------------------

    def _batch_cell_updates(self, updates: Sequence[CellUpdate]) -> int:
        total = 0
        for chunk_start in range(0, len(updates), CELL_UPDATE_BATCH_SIZE):
            chunk = updates[chunk_start : chunk_start + CELL_UPDATE_BATCH_SIZE]
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {
                        "range": _a1(u.sheet_name, u.row, u.col),
                        "values": [[u.value]],
                    }
                    for u in chunk
                ],
            }
            self._retry(lambda: self.spreadsheet.values_batch_update(body))
            total += len(chunk)
            logger.debug("batch_update: %d cells", len(chunk))
        return total

    def _apply_appends(self, appends: Sequence[RowAppend]) -> int:
        # Group by sheet for a single append-call per sheet.
        by_sheet: dict[str, list[tuple[str, ...]]] = {}
        for a in appends:
            by_sheet.setdefault(a.sheet_name, []).append(a.values)
        total = 0
        for sheet_name, value_rows in by_sheet.items():
            ws = self.spreadsheet.worksheet(sheet_name)
            self._retry(
                lambda ws=ws, vr=value_rows: ws.append_rows(
                    [list(r) for r in vr],
                    value_input_option="USER_ENTERED",
                )
            )
            total += len(value_rows)
            logger.debug("append: %d rows → %s", len(value_rows), sheet_name)
        return total

    def _apply_deletes(self, deletes: Sequence[RowDelete]) -> int:
        by_sheet: dict[str, list[int]] = {}
        for d in deletes:
            by_sheet.setdefault(d.sheet_name, []).append(d.row)
        total = 0
        for sheet_name, rows in by_sheet.items():
            # Delete from the bottom up so earlier indices stay valid.
            rows_desc = sorted(rows, reverse=True)
            ws = self.spreadsheet.worksheet(sheet_name)
            # Build a single batchUpdate with deleteDimension requests.
            requests = [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": ws.id,
                            "dimension": "ROWS",
                            "startIndex": r - 1,  # 0-based, inclusive
                            "endIndex":   r,      # exclusive
                        }
                    }
                }
                for r in rows_desc
            ]
            # Sheets API accepts at most ~100 requests per batchUpdate; chunk if larger.
            for i in range(0, len(requests), 100):
                self._retry(
                    lambda chunk=requests[i : i + 100]: self.spreadsheet.batch_update(
                        {"requests": chunk}
                    )
                )
            total += len(rows_desc)
            logger.debug("delete: %d rows ← %s", len(rows_desc), sheet_name)
        return total

    def _retry(self, fn, attempts: int = 5, base_delay: float = 1.0):
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                return fn()
            except gspread.exceptions.APIError as exc:
                last_exc = exc
                status = getattr(exc.response, "status_code", None)
                # Retry on rate-limit and 5xx; raise on other 4xx.
                if status not in (429, 500, 502, 503, 504):
                    raise
                delay = base_delay * (2 ** i)
                logger.warning("Sheets API %s — retrying in %.1fs", status, delay)
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc
