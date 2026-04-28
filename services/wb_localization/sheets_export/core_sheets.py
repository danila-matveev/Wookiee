"""Core per-cabinet sheet writers for WB Localization.

Handles the 5 main sheets (Перемещения, Допоставки, Сводка, Регионы,
Проблемные SKU), their formatting, the shared «История» sheet formatting,
and the «Обновление» dashboard across cabinets.
"""
from __future__ import annotations

import logging

import pandas as pd

from shared.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
    clear_and_write,
    write_range,
    get_moscow_datetime,
    to_number,
)
from services.wb_localization.config import GOOGLE_SA_FILE, WB_LOGISTICS_SPREADSHEET_ID, REPORT_PERIOD_DAYS

from .formatters import (
    _HEADER_BG,
    _HEADER_FG,
    _META_BG,
    _header_fmt,
    _meta_fmt,
    _col_widths,
    _row_height,
    _freeze,
    _borders,
    _banding,
    _num_fmt,
    _bold_col,
    _clear_banding,
)

logger = logging.getLogger(__name__)


def write_moves(spreadsheet, cabinet: str, moves_df: pd.DataFrame, meta):
    """Лист «Перемещения {cabinet}» — откуда, куда, сколько переставить."""
    ws = get_or_create_worksheet(spreadsheet, f"Перемещения {cabinet}")

    headers = [
        "Приоритет", "Артикул", "Размер", "Артикул WB", "Статус",
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
                to_number(row.get("Артикул WB", "")),
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


def write_supplies(spreadsheet, cabinet: str, supply_df: pd.DataFrame, meta):
    """Лист «Допоставки {cabinet}» — что довезти с собственного склада."""
    ws = get_or_create_worksheet(spreadsheet, f"Допоставки {cabinet}")

    headers = [
        "Артикул", "Размер", "Артикул WB", "Статус",
        "Регион", "Склад",
        "Кол-во", "К допоставке (факт)", "На своём складе",
    ]

    data = []
    if not supply_df.empty:
        for _, row in supply_df.iterrows():
            data.append([
                str(row.get("Артикул", row.get("Артикул продавца", ""))),
                str(row.get("Размер", "")),
                to_number(row.get("Артикул WB", "")),
                str(row.get("Статус", "")),
                str(row.get("Регион", "")),
                str(row.get("Склад", "")),
                to_number(row.get("Кол-во", 0)),
                to_number(row.get("К допоставке (факт)", 0)),
                to_number(row.get("На своём складе", 0)),
            ])

    clear_and_write(ws, headers, data, meta_cells=meta)


def write_summary(spreadsheet, cabinet: str, summary: dict, comparison, meta):
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


def write_regions(spreadsheet, cabinet: str, regions: list, meta):
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


def write_top_problems(spreadsheet, cabinet: str, top_problems: list, meta):
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
        nc = 13
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3, cols=2))
        reqs.extend(_col_widths(sid, [
            (0, 90), (1, 200), (2, 80), (3, 100), (4, 100), (5, 120),
            (6, 140), (7, 120), (8, 140), (9, 80), (10, 110), (11, 80),
            (12, 70),
        ]))
        if nr > 3:
            reqs.append(_borders(sid, 2, nr, 0, nc))
            reqs.append(_banding(sid, 3, nr, nc))
            reqs.append(_num_fmt(sid, 3, nr, 10, 11, "0.0"))

    # --- Допоставки ---
    title = f"Допоставки {cabinet}"
    ws = ws_map.get(title)
    if ws:
        sid = ws.id
        nr = len(ws.get_all_values())
        nc = 9
        _clear_banding(spreadsheet, sid)
        reqs.extend(_meta_fmt(sid))
        reqs.append(_header_fmt(sid, 2, nc))
        reqs.append(_row_height(sid, 2, 3, 32))
        reqs.append(_freeze(sid, rows=3, cols=1))
        reqs.extend(_col_widths(sid, [
            (0, 200), (1, 80), (2, 100), (3, 100), (4, 120),
            (5, 140), (6, 80), (7, 150), (8, 140),
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
    if not WB_LOGISTICS_SPREADSHEET_ID:
        return

    if period_days is None:
        period_days = REPORT_PERIOD_DAYS

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(WB_LOGISTICS_SPREADSHEET_ID)
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
