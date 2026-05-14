"""Anchor index: map (anchor-value tuple) → 1-based sheet row index."""
from __future__ import annotations

from typing import Sequence


def _norm(value: str) -> str:
    """Case-insensitive, trimmed comparison key. Empty strings become ''."""
    return (value or "").strip().lower()


def build_anchor_index(
    sheet_columns: Sequence[str],
    sheet_rows: Sequence[Sequence[str]],
    anchor_cols: Sequence[str],
    header_row: int = 1,
) -> dict[tuple[str, ...], int]:
    """Return {anchor-tuple → 1-based row index} for rows in the sheet.

    Args:
        sheet_columns: Header row values, in order. Must contain every name
            in `anchor_cols` (KeyError otherwise).
        sheet_rows: Data rows (header NOT included).
        anchor_cols: Column names that compose the anchor key.
        header_row: 1-based row number of the header in the actual sheet
            (defaults to 1; the first data row is `header_row + 1`).

    Empty anchors (all components blank) are skipped.
    Duplicate anchors keep the FIRST occurrence; subsequent rows are ignored
    so we never overwrite stable rows.
    """
    try:
        anchor_indices = [sheet_columns.index(col) for col in anchor_cols]
    except ValueError as exc:
        raise KeyError(f"Anchor column missing in sheet header: {exc}") from exc

    out: dict[tuple[str, ...], int] = {}
    for offset, row in enumerate(sheet_rows):
        key = tuple(_norm(row[i]) if i < len(row) else "" for i in anchor_indices)
        if not any(k for k in key):
            continue
        if key in out:
            continue
        # +1 to convert 0-based enumeration → 1-based sheet row, then add header offset.
        out[key] = header_row + 1 + offset
    return out


def db_row_anchor(
    db_columns: Sequence[str],
    db_row: Sequence[str],
    anchor_cols: Sequence[str],
) -> tuple[str, ...]:
    """Return the normalised anchor tuple for a single DB row."""
    out: list[str] = []
    for col in anchor_cols:
        try:
            i = db_columns.index(col)
        except ValueError as exc:
            raise KeyError(f"Anchor column '{col}' missing in DB result") from exc
        out.append(_norm(db_row[i] if i < len(db_row) else ""))
    return tuple(out)
