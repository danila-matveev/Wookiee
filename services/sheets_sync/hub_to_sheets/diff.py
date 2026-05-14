"""Build the list of cell/row operations needed to bring a sheet in line with the DB."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from services.sheets_sync.hub_to_sheets.anchor import (
    build_anchor_index,
    db_row_anchor,
)


@dataclass(frozen=True)
class CellUpdate:
    """A single cell write."""

    sheet_name: str
    row: int            # 1-based
    col: int            # 1-based
    value: str


@dataclass(frozen=True)
class RowAppend:
    """A new row to push at the end of the sheet."""

    sheet_name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class RowDelete:
    """A row to physically remove (used only for skleyki)."""

    sheet_name: str
    row: int            # 1-based


@dataclass
class DiffResult:
    """Aggregated set of operations + counters."""

    cell_updates:  list[CellUpdate]    = field(default_factory=list)
    row_appends:   list[RowAppend]     = field(default_factory=list)
    row_deletes:   list[RowDelete]     = field(default_factory=list)
    seen_in_db:    int = 0
    matched:       int = 0
    appended:      int = 0
    archived:      int = 0
    deleted:       int = 0

    def total_cells_touched(self) -> int:
        return (
            len(self.cell_updates)
            + sum(len(a.values) for a in self.row_appends)
        )


def diff_sheet(
    *,
    sheet_name: str,
    db_columns: Sequence[str],
    db_rows: Sequence[Sequence[str]],
    sheet_columns: Sequence[str],
    sheet_rows: Sequence[Sequence[str]],
    anchor_cols: Sequence[str],
    status_col: str | None,
    archive_value: str,
    header_row: int = 1,
) -> DiffResult:
    """Compare DB view rows vs current sheet rows; return ops list.

    Rules (mirrors PLAN §6 Phase 2):
      * For each DB row:
          - matched in sheet → for each shared column, if DB value != sheet
            value AND DB value is non-empty → CellUpdate.
            DB empty values do NOT overwrite (rule #2).
          - not matched → RowAppend at the end of the sheet, projecting DB
            values onto sheet column order; unknown sheet columns get "".
      * For each sheet row whose anchor is not in DB:
          - status_col is None → RowDelete (skleyki).
          - status_col present → set that column to `archive_value` (only
            if it isn't already archived).
      * Idempotent: a no-op run produces zero ops.
    """
    result = DiffResult()
    if not db_columns:
        return result

    # Build sheet → column-index map and the column intersection.
    sheet_col_idx = {name: i for i, name in enumerate(sheet_columns)}
    shared_columns = [c for c in db_columns if c in sheet_col_idx]

    # Anchor index for the sheet.
    sheet_anchor_index = build_anchor_index(
        sheet_columns, sheet_rows, anchor_cols, header_row=header_row
    )

    # Set of DB anchors so we can detect deleted rows.
    db_anchors: set[tuple[str, ...]] = set()

    # Track next free row at the end of the sheet (1-based).
    next_free_row = header_row + 1 + len(sheet_rows)

    # Map DB columns to indices once.
    db_col_idx = {name: i for i, name in enumerate(db_columns)}

    for db_row in db_rows:
        anchor = db_row_anchor(db_columns, db_row, anchor_cols)
        if not any(k for k in anchor):
            continue
        db_anchors.add(anchor)
        result.seen_in_db += 1

        sheet_row_idx = sheet_anchor_index.get(anchor)
        if sheet_row_idx is None:
            # New row → append (project DB → sheet column order).
            projected = tuple(
                db_row[db_col_idx[c]] if c in db_col_idx else ""
                for c in sheet_columns
            )
            result.row_appends.append(RowAppend(sheet_name, projected))
            # Reserve a row slot so the anchor index for subsequent appends is correct.
            sheet_anchor_index[anchor] = next_free_row
            next_free_row += 1
            result.appended += 1
            continue

        result.matched += 1

        # Compare shared columns and emit cell updates where needed.
        sheet_row = sheet_rows[sheet_row_idx - (header_row + 1)] if 0 <= (sheet_row_idx - (header_row + 1)) < len(sheet_rows) else []
        for col_name in shared_columns:
            db_value = (db_row[db_col_idx[col_name]] or "").strip()
            if not db_value:
                # Rule #2: empty DB doesn't overwrite the sheet.
                continue
            sheet_col_i = sheet_col_idx[col_name]
            sheet_value = (sheet_row[sheet_col_i] if sheet_col_i < len(sheet_row) else "").strip()
            if db_value != sheet_value:
                result.cell_updates.append(
                    CellUpdate(
                        sheet_name=sheet_name,
                        row=sheet_row_idx,
                        col=sheet_col_i + 1,
                        value=db_value,
                    )
                )

    # Sweep: rows in the sheet that are not in DB.
    for anchor, row_idx in sheet_anchor_index.items():
        if anchor in db_anchors:
            continue
        # Sheet has this anchor; DB does not.
        if status_col is None:
            result.row_deletes.append(RowDelete(sheet_name, row_idx))
            result.deleted += 1
        else:
            if status_col not in sheet_col_idx:
                continue  # nothing we can do — column missing in the sheet
            sheet_row = sheet_rows[row_idx - (header_row + 1)] if 0 <= (row_idx - (header_row + 1)) < len(sheet_rows) else []
            sheet_col_i = sheet_col_idx[status_col]
            current = (sheet_row[sheet_col_i] if sheet_col_i < len(sheet_row) else "").strip()
            if current == archive_value:
                continue  # already archived
            result.cell_updates.append(
                CellUpdate(
                    sheet_name=sheet_name,
                    row=row_idx,
                    col=sheet_col_i + 1,
                    value=archive_value,
                )
            )
            result.archived += 1

    return result
