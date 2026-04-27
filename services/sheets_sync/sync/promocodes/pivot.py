"""Pivot-table read/write: state, week-block init, row pre-population, upsert."""
from __future__ import annotations

import logging
from datetime import date

import gspread

from .sheet_layout import (
    DATA_START_ROW,
    FIXED_NCOLS,
    METRIC_HEADERS_ROW,
    WEEK_LABELS_ROW,
    WEEK_METRICS,
    WEEK_NCOLS,
    _col_letter,
    _week_label,
)

logger = logging.getLogger(__name__)


def _read_pivot_state(
    ws: gspread.Worksheet,
) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Read current pivot state from the sheet.

    Returns:
        week_col_map:  {week_label: first_metric_col_1based}
        uuid_row_map:  {(uuid, cabinet): row_number_1based}
    """
    all_vals = ws.get_all_values()

    week_col_map: dict[str, int] = {}
    if len(all_vals) >= WEEK_LABELS_ROW:
        week_row = all_vals[WEEK_LABELS_ROW - 1]
        for i in range(FIXED_NCOLS, len(week_row)):
            val = (week_row[i] or "").strip()
            if val and val not in week_col_map:
                week_col_map[val] = i + 1  # 1-based

    uuid_row_map: dict[tuple[str, str], int] = {}
    for row_0 in range(DATA_START_ROW - 1, len(all_vals)):
        row = all_vals[row_0]
        uuid = (row[1] if len(row) > 1 else "").strip()
        cabinet = (row[2] if len(row) > 2 else "").strip()
        if uuid:
            key = (uuid, cabinet)
            if key not in uuid_row_map:
                uuid_row_map[key] = row_0 + 1  # 1-based

    return week_col_map, uuid_row_map


def _add_week_to_sheet(
    ws: gspread.Worksheet, week_label: str, first_col: int, week_index: int = 0
) -> None:
    """Write week date label (row 9) and metric names (row 10) for a new week block."""
    col_start = _col_letter(first_col)
    col_end = _col_letter(first_col + WEEK_NCOLS - 1)

    ws.update(
        range_name=f"{col_start}{WEEK_LABELS_ROW}:{col_end}{WEEK_LABELS_ROW}",
        values=[[week_label] + [""] * (WEEK_NCOLS - 1)],
    )
    ws.update(
        range_name=f"{col_start}{METRIC_HEADERS_ROW}:{col_end}{METRIC_HEADERS_ROW}",
        values=[WEEK_METRICS],
    )
    try:
        from services.sheets_sync.sync.format_promocodes_sheet import format_week_columns
        format_week_columns(ws, first_col, week_index=week_index)
    except Exception as e:
        logger.warning("Week column formatting failed (data still written): %s", e)


def ensure_analytics_dict_rows(
    ws: gspread.Worksheet,
    dictionary: dict[str, dict],
    uuid_row_map: dict[tuple[str, str], int],
) -> int:
    """Pre-create analytics rows for every (UUID, cabinet) declared in dictionary.

    Rows are appended below the last existing data row. uuid_row_map is mutated
    in-place so subsequent upsert_pivot() calls reuse the new row numbers.
    Returns count of rows added.
    """
    cells: list[gspread.Cell] = []
    added = 0
    for uuid, info in dictionary.items():
        cabinets = info.get("cabinets") or []
        for cab in cabinets:
            key = (uuid, cab)
            if key in uuid_row_map:
                continue
            row_n = DATA_START_ROW + len(uuid_row_map)
            uuid_row_map[key] = row_n
            disc = info.get("discount_pct")
            cells.append(gspread.Cell(row_n, 1, info.get("name") or "неизвестный"))
            cells.append(gspread.Cell(row_n, 2, uuid))
            cells.append(gspread.Cell(row_n, 3, cab))
            cells.append(gspread.Cell(row_n, 4, disc if disc is not None else ""))
            added += 1
    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")
        logger.info("Pre-populated %d analytics rows from dictionary", added)
    return added


def upsert_pivot(
    ws: gspread.Worksheet,
    week_start: date,
    week_end: date,
    week_data: dict[tuple[str, str], dict],
    week_col_map: dict[str, int],
    uuid_row_map: dict[tuple[str, str], int],
) -> tuple[int, int]:
    """Write week data into the pivot table. Mutates week_col_map and uuid_row_map.

    week_data key: (uuid, cabinet)
    week_data value: {metrics, name, channel, discount}

    Returns (rows_added, rows_updated).
    """
    label = _week_label(week_start, week_end)

    if label not in week_col_map:
        n_existing = len(week_col_map)
        first_col = FIXED_NCOLS + 1 + n_existing * WEEK_NCOLS
        _add_week_to_sheet(ws, label, first_col, week_index=n_existing)
        week_col_map[label] = first_col

    week_first_col = week_col_map[label]
    cells: list[gspread.Cell] = []
    added = updated = 0

    for (uuid, cabinet), row_data in week_data.items():
        key = (uuid, cabinet)
        if key in uuid_row_map:
            row_n = uuid_row_map[key]
            updated += 1
        else:
            row_n = DATA_START_ROW + len(uuid_row_map)
            uuid_row_map[key] = row_n
            added += 1
            cells.append(gspread.Cell(row_n, 1, row_data["name"]))
            cells.append(gspread.Cell(row_n, 2, uuid))
            cells.append(gspread.Cell(row_n, 3, cabinet))
            cells.append(gspread.Cell(row_n, 4, row_data["discount"]))

        m = row_data["metrics"]
        avg_check = (
            round(m["sales_rub"] / m["orders_count"], 2)
            if m["orders_count"] else 0.0
        )
        top1 = m["top3_models"][0][0] if m.get("top3_models") else "—"
        metric_vals = [
            round(m["sales_rub"], 2),
            round(m["ppvz_rub"], 2),
            m["orders_count"],
            m["returns_count"],
            avg_check,
            top1,
        ]
        for i, val in enumerate(metric_vals):
            cells.append(gspread.Cell(row_n, week_first_col + i, val))

    if cells:
        ws.update_cells(cells, value_input_option="USER_ENTERED")

    logger.info("Pivot upsert %s: +%d, ~%d", label, added, updated)
    return added, updated
