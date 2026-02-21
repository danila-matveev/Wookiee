"""Export Vasily localization report data to Google Sheets."""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from shared.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
    clear_and_write,
    write_range,
    get_moscow_datetime,
    to_number,
    _cell_ref,
)
from services.wb_localization.config import GOOGLE_SA_FILE, VASILY_SPREADSHEET_ID, REPORT_PERIOD_DAYS

logger = logging.getLogger(__name__)

# ============================================================================
# Color palette & formatting constants
# ============================================================================
_HEADER_BG = {"red": 0.098, "green": 0.325, "blue": 0.647}
_HEADER_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
_META_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}
_ALT_ROW = {"red": 0.929, "green": 0.945, "blue": 0.976}


def export_to_sheets(result: dict) -> str:
    """Write a single cabinet report to Google Sheets.

    Creates/updates 5 worksheets per cabinet + appends to shared "История":
      - "Перемещения {cabinet}" — откуда, куда, сколько переставить
      - "Допоставки {cabinet}" — что довезти с собственного склада
      - "Сводка {cabinet}"
      - "Регионы {cabinet}"
      - "Проблемные SKU {cabinet}"
      - "История" (append-only)

    Returns:
        Spreadsheet URL.
    """
    if not VASILY_SPREADSHEET_ID:
        logger.warning("VASILY_SPREADSHEET_ID не задан — пропуск экспорта в Sheets")
        return ""

    cabinet = result.get("cabinet", "?")
    summary = result.get("summary", {})
    regions = result.get("regions", [])
    top_problems = result.get("top_problems", [])
    comparison = result.get("comparison")

    moves_df: pd.DataFrame = result.get("_moves_df", pd.DataFrame())
    supply_df: pd.DataFrame = result.get("_supply_df", pd.DataFrame())

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(VASILY_SPREADSHEET_ID)
    date_str, time_str = get_moscow_datetime()

    meta = [
        (1, 1, "Дата"),
        (1, 2, date_str),
        (2, 1, "Время"),
        (2, 2, time_str),
    ]

    # --- Перемещения (главная таблица) ---
    _write_moves(spreadsheet, cabinet, moves_df, meta)

    # --- Допоставки ---
    _write_supplies(spreadsheet, cabinet, supply_df, meta)

    # --- Сводка ---
    _write_summary(spreadsheet, cabinet, summary, comparison, meta)

    # --- Регионы ---
    _write_regions(spreadsheet, cabinet, regions, meta)

    # --- Проблемные SKU ---
    _write_top_problems(spreadsheet, cabinet, top_problems, meta)

    # --- История (append) ---
    _append_history(spreadsheet, result, date_str, time_str)

    # --- Форматирование всех листов кабинета ---
    _apply_formatting(spreadsheet, cabinet)

    url = f"https://docs.google.com/spreadsheets/d/{VASILY_SPREADSHEET_ID}"
    logger.info("Экспорт в Sheets: %s (%s)", cabinet, url)
    return url


def _write_moves(spreadsheet, cabinet: str, moves_df: pd.DataFrame, meta):
    """Лист «Перемещения {cabinet}» — откуда, куда, сколько переставить."""
    ws = get_or_create_worksheet(spreadsheet, f"Перемещения {cabinet}")

    headers = [
        "Приоритет", "Артикул", "Размер", "Статус",
        "Откуда регион", "Откуда склад", "Куда регион", "Куда склад",
        "Кол-во", "Индекс SKU, %", "Заказов", "Балл",
    ]

    data = []
    if not moves_df.empty:
        for _, row in moves_df.iterrows():
            data.append([
                str(row.get("Приоритет", "")),
                str(row.get("Артикул", row.get("Артикул продавца", ""))),
                str(row.get("Размер", "")),
                str(row.get("Статус", "")),
                str(row.get("Откуда регион", "")),
                str(row.get("Откуда склад", "")),
                str(row.get("Куда регион", "")),
                str(row.get("Куда склад", "")),
                to_number(row.get("Кол-во", 0)),
                to_number(row.get("Индекс SKU, %", 0)),
                to_number(row.get("Заказов", 0)),
                to_number(row.get("Балл", 0)),
            ])

    clear_and_write(ws, headers, data, meta_cells=meta)


def _write_supplies(spreadsheet, cabinet: str, supply_df: pd.DataFrame, meta):
    """Лист «Допоставки {cabinet}» — что довезти с собственного склада."""
    ws = get_or_create_worksheet(spreadsheet, f"Допоставки {cabinet}")

    headers = [
        "Артикул", "Размер", "Статус",
        "Регион", "Склад",
        "Кол-во", "К допоставке (факт)", "На своём складе",
    ]

    data = []
    if not supply_df.empty:
        for _, row in supply_df.iterrows():
            data.append([
                str(row.get("Артикул", row.get("Артикул продавца", ""))),
                str(row.get("Размер", "")),
                str(row.get("Статус", "")),
                str(row.get("Регион", "")),
                str(row.get("Склад", "")),
                to_number(row.get("Кол-во", 0)),
                to_number(row.get("К допоставке (факт)", 0)),
                to_number(row.get("На своём складе", 0)),
            ])

    clear_and_write(ws, headers, data, meta_cells=meta)


def _write_summary(spreadsheet, cabinet: str, summary: dict, comparison, meta):
    """Лист «Сводка {cabinet}» — ключевые метрики."""
    ws = get_or_create_worksheet(spreadsheet, f"Сводка {cabinet}")

    headers = ["Метрика", "Значение", "Изменение"]

    delta_index = ""
    if comparison:
        change = comparison.get("index_change", 0)
        delta_index = f"{change:+.1f} п.п."

    data = [
        ["Индекс локализации, %", to_number(summary.get("overall_index", 0)), delta_index],
        ["Всего SKU", to_number(summary.get("total_sku", 0)), ""],
        ["SKU с заказами", to_number(summary.get("sku_with_orders", 0)), ""],
        ["Перемещений", to_number(summary.get("movements_count", 0)), ""],
        ["Кол-во перемещений, шт.", to_number(summary.get("movements_qty", 0)), ""],
        ["Допоставок", to_number(summary.get("supplies_count", 0)), ""],
        ["Кол-во допоставок, шт.", to_number(summary.get("supplies_qty", 0)), ""],
    ]

    clear_and_write(ws, headers, data, meta_cells=meta)


def _write_regions(spreadsheet, cabinet: str, regions: list, meta):
    """Лист «Регионы {cabinet}» — индексы по регионам."""
    ws = get_or_create_worksheet(spreadsheet, f"Регионы {cabinet}")

    headers = ["Регион", "Индекс, %", "Доля остатков, %", "Доля заказов, %", "Рекомендация"]

    data = []
    for r in regions:
        data.append([
            r.get("region", ""),
            to_number(r.get("index", 0)),
            to_number(r.get("stock_share", 0)),
            to_number(r.get("order_share", 0)),
            r.get("recommendation", ""),
        ])

    clear_and_write(ws, headers, data, meta_cells=meta)


def _write_top_problems(spreadsheet, cabinet: str, top_problems: list, meta):
    """Лист «Проблемные SKU {cabinet}» — топ проблемных артикулов."""
    ws = get_or_create_worksheet(spreadsheet, f"Проблемные SKU {cabinet}")

    headers = ["Артикул", "Размер", "Индекс, %", "Заказов", "Impact"]

    data = []
    for p in top_problems:
        data.append([
            p.get("article", ""),
            p.get("size", ""),
            to_number(p.get("index", 0)),
            to_number(p.get("orders", 0)),
            to_number(p.get("impact", 0)),
        ])

    clear_and_write(ws, headers, data, meta_cells=meta)


_HISTORY_TITLE = "ИСТОРИЯ РАСЧЁТОВ ЛОКАЛИЗАЦИИ"
_HISTORY_HEADERS = [
    "Дата", "Кабинет", "Индекс", "Всего SKU", "С заказами",
    "Перемещений", "Шт. перемещений", "Допоставок", "Шт. допоставок",
    "Δ индекса",
]


def _append_history(spreadsheet, result: dict, date_str: str, time_str: str):
    """Лист «История» — дописывание строки (тренд).

    Структура:
      Row 1: заголовок «ИСТОРИЯ РАСЧЁТОВ ЛОКАЛИЗАЦИИ»
      Row 2: пустая
      Row 3: заголовки колонок
      Row 4+: данные
    """
    ws = get_or_create_worksheet(spreadsheet, "История")

    summary = result.get("summary", {})
    comparison = result.get("comparison")
    delta = comparison.get("index_change", "") if comparison else ""

    row = [
        date_str,
        result.get("cabinet", ""),
        to_number(summary.get("overall_index", 0)),
        to_number(summary.get("total_sku", 0)),
        to_number(summary.get("sku_with_orders", 0)),
        to_number(summary.get("movements_count", 0)),
        to_number(summary.get("movements_qty", 0)),
        to_number(summary.get("supplies_count", 0)),
        to_number(summary.get("supplies_qty", 0)),
        to_number(delta) if delta != "" else "",
    ]

    all_values = ws.get_all_values()

    # Если лист пустой или структура сбита — пересоздаём шапку
    if len(all_values) < 3 or all_values[0][0] != _HISTORY_TITLE:
        ws.clear()
        ws.update(range_name="A1", values=[[_HISTORY_TITLE]])
        ws.update(range_name="A3", values=[_HISTORY_HEADERS])
        next_row = 4
    else:
        next_row = len(all_values) + 1

    ws.update(range_name=f"A{next_row}", values=[row])
    logger.info("История: добавлена строка %d для %s", next_row, result.get("cabinet"))


# ============================================================================
# Formatting helpers
# ============================================================================

def _header_fmt(sheet_id: int, row_idx: int, num_cols: int) -> dict:
    """Bold white text on dark-blue background for header row."""
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_idx,
                "endRowIndex": row_idx + 1,
                "startColumnIndex": 0,
                "endColumnIndex": num_cols,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    }


def _meta_fmt(sheet_id: int) -> list[dict]:
    """Format meta cells (rows 0-1, cols 0-1): grey background, bold labels."""
    reqs = []
    for col, bold in [(0, True), (1, False)]:
        reqs.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": 2,
                    "startColumnIndex": col, "endColumnIndex": col + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": bold, "fontSize": 9},
                        "backgroundColor": _META_BG,
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        })
    return reqs


def _col_widths(sheet_id: int, widths: list[tuple[int, int]]) -> list[dict]:
    """Set column widths: [(col_index, pixel_width), ...]."""
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": c, "endIndex": c + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        }
        for c, px in widths
    ]


def _row_height(sheet_id: int, start: int, end: int, px: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": start, "endIndex": end,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def _freeze(sheet_id: int, rows: int = 0, cols: int = 0) -> dict:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": rows, "frozenColumnCount": cols},
            },
            "fields": "gridProperties(frozenRowCount,frozenColumnCount)",
        }
    }


def _borders(sheet_id: int, sr: int, er: int, sc: int, ec: int) -> dict:
    border = {"style": "SOLID", "color": {"red": 0.8, "green": 0.8, "blue": 0.8}}
    return {
        "updateBorders": {
            "range": {"sheetId": sheet_id, "startRowIndex": sr, "endRowIndex": er,
                       "startColumnIndex": sc, "endColumnIndex": ec},
            "top": border, "bottom": border, "left": border, "right": border,
            "innerHorizontal": border, "innerVertical": border,
        }
    }


def _banding(sheet_id: int, sr: int, er: int, nc: int) -> dict:
    return {
        "addBanding": {
            "bandedRange": {
                "range": {"sheetId": sheet_id, "startRowIndex": sr, "endRowIndex": er,
                           "startColumnIndex": 0, "endColumnIndex": nc},
                "rowProperties": {
                    "firstBandColor": {"red": 1, "green": 1, "blue": 1},
                    "secondBandColor": _ALT_ROW,
                },
            }
        }
    }


def _num_fmt(sheet_id: int, sr: int, er: int, sc: int, ec: int, pattern: str) -> dict:
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": sr, "endRowIndex": er,
                       "startColumnIndex": sc, "endColumnIndex": ec},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": pattern}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _bold_col(sheet_id: int, sr: int, er: int, col: int) -> dict:
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": sr, "endRowIndex": er,
                       "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    }


def _clear_banding(spreadsheet, sheet_id: int) -> None:
    """Remove existing banded ranges for a sheet to avoid duplicates."""
    metadata = spreadsheet.fetch_sheet_metadata()
    for sheet in metadata.get("sheets", []):
        if sheet["properties"]["sheetId"] == sheet_id:
            for br in sheet.get("bandedRanges", []):
                spreadsheet.batch_update({"requests": [
                    {"deleteBanding": {"bandedRangeId": br["bandedRangeId"]}}
                ]})
            break


def _apply_formatting(spreadsheet, cabinet: str) -> None:
    """Apply visual formatting to all sheets for the given cabinet."""
    ws_map = {ws.title: ws for ws in spreadsheet.worksheets()}
    reqs: list[dict] = []

    # --- Перемещения ---
    title = f"Перемещения {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 12
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3, cols=2))
        reqs.extend(_col_widths(sid, [
            (0, 90), (1, 200), (2, 80), (3, 100), (4, 120), (5, 140),
            (6, 120), (7, 140), (8, 80), (9, 110), (10, 80), (11, 70),
        ]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))
            reqs.append(_num_fmt(sid, 3, nr, 9, 10, "0.0"))

    # --- Допоставки ---
    title = f"Допоставки {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 8
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3, cols=1))
        reqs.extend(_col_widths(sid, [
            (0, 200), (1, 80), (2, 100), (3, 120), (4, 140),
            (5, 80), (6, 150), (7, 140),
        ]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))

    # --- Сводка ---
    title = f"Сводка {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 3
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3))
        reqs.extend(_col_widths(sid, [(0, 220), (1, 120), (2, 120)]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_bold_col(sid, 3, nr, 0))

    # --- Регионы ---
    title = f"Регионы {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 5
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3))
        reqs.extend(_col_widths(sid, [(0, 160), (1, 100), (2, 130), (3, 130), (4, 250)]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))
            reqs.append(_num_fmt(sid, 3, nr, 1, 4, "0.0"))

    # --- Проблемные SKU ---
    title = f"Проблемные SKU {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 5
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3))
        reqs.extend(_col_widths(sid, [(0, 250), (1, 80), (2, 100), (3, 80), (4, 80)]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))
            reqs.append(_num_fmt(sid, 3, nr, 2, 3, "0.0"))

    # --- История (format only, shared across cabinets) ---
    ws = ws_map.get("История")
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 10
        _clear_banding(spreadsheet, sid)
        # Title row
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": nc},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _HEADER_BG,
                        "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": _HEADER_FG},
                        "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        })
        reqs.append(_row_height(sid, 0, 1, 36))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3))
        reqs.extend(_col_widths(sid, [
            (0, 110), (1, 100), (2, 80), (3, 90), (4, 100),
            (5, 110), (6, 130), (7, 100), (8, 120), (9, 90),
        ]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))
            reqs.append(_num_fmt(sid, 3, nr, 2, 3, "0.0"))

    # Apply all at once
    if reqs:
        spreadsheet.batch_update({"requests": reqs})
        logger.info("Форматирование применено: %d запросов для %s", len(reqs), cabinet)


# ============================================================================
# Dashboard — лист «Обновление»
# ============================================================================

_DASHBOARD_TITLE = "ОБНОВЛЕНИЕ ДАННЫХ ЛОКАЛИЗАЦИИ"
_DASHBOARD_HISTORY_LIMIT = 20

_METRIC_ROWS = [
    ("Индекс, %", "overall_index", True),
    ("Всего SKU", "total_sku", False),
    ("SKU с заказами", "sku_with_orders", False),
    ("Перемещений", "movements_count", False),
    ("Шт. перемещений", "movements_qty", False),
    ("Допоставок", "supplies_count", False),
    ("Шт. допоставок", "supplies_qty", False),
]


def export_dashboard(results: list[dict], period_days: int | None = None) -> None:
    """Write dashboard to «Обновление» sheet after all cabinet reports.

    Args:
        results: List of full result dicts from VasilyService.run_report().
        period_days: Report period in days (for display).
    """
    if not VASILY_SPREADSHEET_ID:
        return

    if period_days is None:
        period_days = REPORT_PERIOD_DAYS

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(VASILY_SPREADSHEET_ID)
    ws = get_or_create_worksheet(spreadsheet, "Обновление")

    # Clear data cells (preserves drawings/images)
    ws.clear()

    num_history = _write_dashboard_data(ws, results, period_days, spreadsheet)
    _apply_dashboard_formatting(spreadsheet, ws, num_history)

    logger.info("Дашборд «Обновление» обновлён")


def _write_dashboard_data(
    ws, results: list[dict], period_days: int, spreadsheet
) -> int:
    """Populate dashboard sheet. Returns number of history rows written."""
    date_str, time_str = get_moscow_datetime()

    # --- Row 1-3: title + meta ---
    write_range(ws, 1, 2, [[_DASHBOARD_TITLE]])
    write_range(ws, 2, 2, [["Дата:", date_str, "", "", "Время:", time_str]])
    write_range(ws, 3, 2, [["Период:", f"{period_days} дн.", "", "", "Статус:", "Готово"]])

    # --- Row 5-13: cabinet summaries side by side ---
    # Build a map: cabinet_name -> (summary, delta)
    cab_data = {}
    for r in results:
        cab = r.get("cabinet", "?")
        summary = r.get("summary", {})
        comparison = r.get("comparison")
        delta = comparison.get("index_change", 0) if comparison else 0
        cab_data[cab] = (summary, delta)

    # Determine cabinet order (ИП first, ООО second, then others)
    cab_names = list(cab_data.keys())
    ordered = []
    for pref in ("ip", "ип"):
        for cn in cab_names:
            if cn.lower() == pref and cn not in ordered:
                ordered.append(cn)
    for pref in ("ooo", "ооо"):
        for cn in cab_names:
            if cn.lower() == pref and cn not in ordered:
                ordered.append(cn)
    for cn in cab_names:
        if cn not in ordered:
            ordered.append(cn)

    cab1 = ordered[0] if len(ordered) > 0 else None
    cab2 = ordered[1] if len(ordered) > 1 else None

    # Row 5: cabinet headers
    header_row_5 = ["", ""]  # A, B empty
    header_row_5.append(f"КАБИНЕТ {cab1.upper()}" if cab1 else "")
    header_row_5.append("")
    header_row_5.append("")  # E separator
    header_row_5.append(f"КАБИНЕТ {cab2.upper()}" if cab2 else "")
    header_row_5.append("")
    write_range(ws, 5, 1, [header_row_5])

    # Row 6: sub-headers
    sub_headers = ["", "Метрика", "Значение", "Δ", "", "Значение", "Δ"]
    write_range(ws, 6, 1, [sub_headers])

    # Row 7-13: metric rows
    for i, (label, key, is_index) in enumerate(_METRIC_ROWS):
        row_num = 7 + i
        row_data = ["", label]

        if cab1 and cab1 in cab_data:
            s1, d1 = cab_data[cab1]
            row_data.append(to_number(s1.get(key, 0)))
            if is_index:
                row_data.append(f"{d1:+.1f} п.п." if d1 else "")
            else:
                row_data.append("")
        else:
            row_data.extend(["", ""])

        row_data.append("")  # E separator

        if cab2 and cab2 in cab_data:
            s2, d2 = cab_data[cab2]
            row_data.append(to_number(s2.get(key, 0)))
            if is_index:
                row_data.append(f"{d2:+.1f} п.п." if d2 else "")
            else:
                row_data.append("")
        else:
            row_data.extend(["", ""])

        write_range(ws, row_num, 1, [row_data])

    # --- Row 15+: history ---
    history_rows = _read_history_from_sheet(spreadsheet, _DASHBOARD_HISTORY_LIMIT)

    write_range(ws, 15, 1, [[f"ИСТОРИЯ РАСЧЁТОВ (последние {_DASHBOARD_HISTORY_LIMIT})"]])

    hist_headers = ["Дата", "Кабинет", "Индекс,%", "Всего SKU",
                    "Перемещ.", "Шт.", "Допост.", "Δ индекса"]
    write_range(ws, 16, 1, [hist_headers])

    if history_rows:
        write_range(ws, 17, 1, history_rows)

    return len(history_rows)


def _read_history_from_sheet(spreadsheet, limit: int = 20) -> list[list]:
    """Read history from «История» sheet, return newest-first rows."""
    try:
        ws = spreadsheet.worksheet("История")
    except Exception:
        return []

    all_values = ws.get_all_values()
    # Data starts at row 4 (index 3): row 1 = title, row 2 = empty, row 3 = headers
    if len(all_values) <= 3:
        return []

    data = all_values[3:]
    # Reverse to show newest first, take limit
    data.reverse()
    return data[:limit]


def _apply_dashboard_formatting(spreadsheet, ws, num_history_rows: int) -> None:
    """Apply visual formatting to the dashboard sheet."""
    sid = ws.id
    reqs: list[dict] = []

    _clear_banding(spreadsheet, sid)

    # Column widths
    reqs.extend(_col_widths(sid, [
        (0, 120), (1, 160), (2, 120), (3, 100),
        (4, 30), (5, 120), (6, 100), (7, 100),
    ]))

    # Row 1: title — dark blue, white bold 14pt
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                       "startColumnIndex": 1, "endColumnIndex": 8},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    })
    reqs.append(_row_height(sid, 0, 1, 40))

    # Rows 2-3: meta — grey background
    for col in range(1, 8):
        bold = col in (1, 5)  # "Дата:", "Время:", "Период:", "Статус:" labels
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 3,
                           "startColumnIndex": col, "endColumnIndex": col + 1},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": bold, "fontSize": 10},
                        "backgroundColor": _META_BG,
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        })

    # Row 5: cabinet headers — dark blue
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 4, "endRowIndex": 5,
                       "startColumnIndex": 2, "endColumnIndex": 4},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 4, "endRowIndex": 5,
                       "startColumnIndex": 5, "endColumnIndex": 7},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "CENTER",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }
    })

    # Row 6: sub-headers
    reqs.append(_header_fmt(sid, 5, 8))
    reqs.append(_row_height(sid, 5, 6, 28))

    # Rows 7-13: metric data
    reqs.append(_bold_col(sid, 6, 13, 1))  # Bold metric names in column B
    reqs.append(_borders(sid, 5, 13, 1, 4))  # Borders for cab1 area
    reqs.append(_borders(sid, 5, 13, 5, 7))  # Borders for cab2 area
    # Number format for index row (row 7, index 6)
    reqs.append(_num_fmt(sid, 6, 7, 2, 3, "0.0"))  # C7
    reqs.append(_num_fmt(sid, 6, 7, 5, 6, "0.0"))  # F7

    # Row 15: history title
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 14, "endRowIndex": 15,
                       "startColumnIndex": 0, "endColumnIndex": 8},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    })
    reqs.append(_row_height(sid, 14, 15, 36))

    # Row 16: history headers
    reqs.append(_header_fmt(sid, 15, 8))
    reqs.append(_row_height(sid, 15, 16, 28))

    # History data rows (17+)
    if num_history_rows > 0:
        hist_end = 16 + num_history_rows
        reqs.append(_borders(sid, 15, hist_end, 0, 8))
        reqs.append(_banding(sid, 16, hist_end, 8))
        reqs.append(_num_fmt(sid, 16, hist_end, 2, 3, "0.0"))  # Index column

    # Freeze row 16 (headers visible when scrolling history)
    reqs.append(_freeze(sid, rows=0, cols=0))

    if reqs:
        spreadsheet.batch_update({"requests": reqs})
        logger.info("Форматирование дашборда: %d запросов", len(reqs))
