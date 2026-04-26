"""Visual formatting for the WB Promocodes analytics sheet.

Single entry point: `apply_visual_formatting(ws)`. Runs once on the worksheet
to set up dashboard styling, header colors, currency formats, banding, freeze,
and conditional formatting (yellow for unknown promocodes).

Idempotent — safe to re-run.
"""
from __future__ import annotations

import gspread


# ── Color palette (RGB 0..1) ─────────────────────────────────────────────────
_HEADER_BG = {"red": 0.098, "green": 0.325, "blue": 0.647}   # dark blue
_HEADER_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
_DASHBOARD_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}  # light grey
_BUTTON_BG = {"red": 0.918, "green": 0.961, "blue": 0.918}     # light green
_ALT_ROW = {"red": 0.961, "green": 0.969, "blue": 0.984}      # very-light blue
_YELLOW_BG = {"red": 1.0, "green": 0.972, "blue": 0.847}       # soft yellow

# Layout constants must match sync_promocodes.DATA_START_ROW etc.
_DASHBOARD_FROM_ROW = 2   # 1-based: row with «Последнее обновление»
_DASHBOARD_TO_ROW = 7
_HEADERS_ROW = 9
_DATA_FROM_ROW = 10
_NUM_COLS = 12   # len(ANALYTICS_HEADERS)


def apply_visual_formatting(ws: gspread.Worksheet) -> None:
    """Apply all visual formatting to the analytics worksheet.

    Layout:
      Row 1     — reserved for «🔄 ОБНОВИТЬ» drawing button (no formatting)
      Rows 2-7  — dashboard header (bold labels, grey bg)
      Row 9     — column headers (white-on-blue, bold)
      Rows 10+  — data rows (alternating bg, currency formats)
                  + conditional: row.C == "неизвестный" → yellow bg

    Also: freeze rows 1-9, freeze column A, set column widths.
    """
    sid = ws.id
    requests: list[dict] = []

    # ── Row 1: reserved for the GAS button drawing (light green tint) ───────
    requests.append({
        "repeatCell": {
            "range": _range(sid, 0, 1, 0, 5),
            "cell": {"userEnteredFormat": {"backgroundColor": _BUTTON_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })
    # Row 1 height — taller for the button
    requests.append(_set_row_height(sid, 0, 1, 36))

    # ── Rows 2-7: dashboard labels + values ────────────────────────────────
    requests.append({
        "repeatCell": {
            "range": _range(sid, _DASHBOARD_FROM_ROW - 1, _DASHBOARD_TO_ROW, 0, 5),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _DASHBOARD_BG,
                    "textFormat": {"fontSize": 10},
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)",
        }
    })
    # Bold the label column (A) in dashboard
    requests.append({
        "repeatCell": {
            "range": _range(sid, _DASHBOARD_FROM_ROW - 1, _DASHBOARD_TO_ROW, 0, 1),
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # ── Row 9: column headers ─────────────────────────────────────────────
    requests.append({
        "repeatCell": {
            "range": _range(sid, _HEADERS_ROW - 1, _HEADERS_ROW, 0, _NUM_COLS),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    })
    requests.append(_set_row_height(sid, _HEADERS_ROW - 1, _HEADERS_ROW, 40))

    # ── Data rows: number formats per column ───────────────────────────────
    # Column index (0-based): A=0,B=1,C=2,D=3,E=4,F=5,G=6,H=7,I=8,J=9,K=10,L=11
    # E (4)  Скидка %        → percent-like integer
    # F (5)  Продажи ₽       → currency
    # G (6)  К перечислению ₽ → currency
    # H (7)  Заказов шт      → integer
    # I (8)  Возвратов шт    → integer
    # J (9)  Ср. чек ₽       → currency
    requests.append(_num_fmt(sid, _DATA_FROM_ROW - 1, 1000, 4, 5, "0\"%\""))
    for col in (5, 6, 9):
        requests.append(_num_fmt(sid, _DATA_FROM_ROW - 1, 1000, col, col + 1,
                                 "#,##0.00\" ₽\""))
    for col in (7, 8):
        requests.append(_num_fmt(sid, _DATA_FROM_ROW - 1, 1000, col, col + 1, "0"))

    # ── Banding (alternating row colors) for data area ─────────────────────
    requests.append({
        "addBanding": {
            "bandedRange": {
                "range": _range(sid, _HEADERS_ROW - 1, 1000, 0, _NUM_COLS),
                "rowProperties": {
                    "headerColor": _HEADER_BG,
                    "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                    "secondBandColor": _ALT_ROW,
                },
            }
        }
    })

    # ── Freeze rows 1-9 + first column ─────────────────────────────────────
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {"frozenRowCount": _HEADERS_ROW, "frozenColumnCount": 1},
            },
            "fields": "gridProperties(frozenRowCount,frozenColumnCount)",
        }
    })

    # ── Column widths ──────────────────────────────────────────────────────
    widths = [
        (0, 130),   # Неделя
        (1, 70),    # Кабинет
        (2, 200),   # Название
        (3, 280),   # UUID
        (4, 80),    # Скидка %
        (5, 130),   # Продажи ₽
        (6, 130),   # К перечислению ₽
        (7, 90),    # Заказов
        (8, 100),   # Возвратов
        (9, 110),   # Ср. чек
        (10, 360),  # Топ-3 модели
        (11, 140),  # Обновлено
    ]
    for col, px in widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # ── Conditional formatting: «неизвестный» rows highlighted yellow ──────
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [_range(sid, _DATA_FROM_ROW - 1, 1000, 0, _NUM_COLS)],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": f"=$C{_DATA_FROM_ROW}=\"неизвестный\""}],
                    },
                    "format": {"backgroundColor": _YELLOW_BG},
                },
            },
            "index": 0,
        }
    })

    ws.spreadsheet.batch_update({"requests": requests})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _range(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict:
    return {
        "sheetId": sheet_id,
        "startRowIndex": r0,
        "endRowIndex": r1,
        "startColumnIndex": c0,
        "endColumnIndex": c1,
    }


def _num_fmt(sheet_id: int, r0: int, r1: int, c0: int, c1: int, pattern: str) -> dict:
    return {
        "repeatCell": {
            "range": _range(sheet_id, r0, r1, c0, c1),
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": pattern}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _set_row_height(sheet_id: int, r0: int, r1: int, px: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": r0, "endIndex": r1},
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }
