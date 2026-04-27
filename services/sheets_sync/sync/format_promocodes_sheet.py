"""Visual formatting for the WB Promocodes analytics sheet — pivot layout.

Two entry points:
  apply_base_formatting(ws)          — called once at sheet initialisation
  format_week_columns(ws, first_col) — called each time a new week is added

Both are idempotent.
"""
from __future__ import annotations

import gspread

# Mirror of sync_promocodes layout constants — hardcoded to avoid circular import
WEEK_LABELS_ROW = 9
METRIC_HEADERS_ROW = 10
DATA_START_ROW = 11
FIXED_NCOLS = 4
WEEK_NCOLS = 6
WEEK_METRICS = [
    "Продажи, ₽", "К перечислению, ₽",
    "Заказов, шт", "Возвратов, шт", "Ср. чек, ₽", "Топ модель",
]

# ── Color palette (RGB 0..1) ─────────────────────────────────────────────────
_HEADER_BG = {"red": 0.098, "green": 0.325, "blue": 0.647}      # dark blue
_HEADER_FG = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
_METRIC_HDR_BG = {"red": 0.255, "green": 0.455, "blue": 0.698}  # medium blue
_DASHBOARD_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}   # light grey
_BUTTON_BG = {"red": 0.918, "green": 0.961, "blue": 0.918}      # light green
_YELLOW_BG = {"red": 1.0,   "green": 0.972, "blue": 0.847}      # soft yellow

# Alternating week-block backgrounds for data rows (pastel cream / pastel blue)
_WEEK_ALT_BG = [
    {"red": 1.000, "green": 0.953, "blue": 0.882},  # peachy cream (even weeks)
    {"red": 0.882, "green": 0.937, "blue": 0.984},  # pastel blue (odd weeks)
]


def apply_base_formatting(ws: gspread.Worksheet) -> None:
    """Apply base formatting: dashboard, fixed column headers, freeze, column widths.

    Does NOT touch week-column areas — those are handled by format_week_columns().
    """
    sid = ws.id
    requests: list[dict] = []

    # Row 1: reserved for GAS «🔄 ОБНОВИТЬ» drawing button
    requests.append({
        "repeatCell": {
            "range": _range(sid, 0, 1, 0, 10),
            "cell": {"userEnteredFormat": {"backgroundColor": _BUTTON_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })
    requests.append(_set_row_height(sid, 0, 1, 36))

    # Rows 2-8: dashboard header area
    requests.append({
        "repeatCell": {
            "range": _range(sid, 1, WEEK_LABELS_ROW - 1, 0, 6),
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
    requests.append({
        "repeatCell": {
            "range": _range(sid, 1, WEEK_LABELS_ROW - 1, 0, 1),
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 10}}},
            "fields": "userEnteredFormat.textFormat",
        }
    })

    # Row 9 (WEEK_LABELS_ROW): height for week date labels
    requests.append(_set_row_height(sid, WEEK_LABELS_ROW - 1, WEEK_LABELS_ROW, 30))

    # Row 10 (METRIC_HEADERS_ROW): dark blue for fixed cols A-D
    requests.append({
        "repeatCell": {
            "range": _range(sid, METRIC_HEADERS_ROW - 1, METRIC_HEADERS_ROW, 0, FIXED_NCOLS),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {
                        "bold": True, "fontSize": 10, "foregroundColor": _HEADER_FG,
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    })
    requests.append(_set_row_height(sid, METRIC_HEADERS_ROW - 1, METRIC_HEADERS_ROW, 40))

    # Freeze: 10 rows (through row 10) + 4 fixed columns (A-D)
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sid,
                "gridProperties": {
                    "frozenRowCount": METRIC_HEADERS_ROW,
                    "frozenColumnCount": FIXED_NCOLS,
                },
            },
            "fields": "gridProperties(frozenRowCount,frozenColumnCount)",
        }
    })

    # Fixed column widths (A-D)
    for col, px in [(0, 200), (1, 280), (2, 70), (3, 80)]:
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # Conditional format: highlight rows where Название (col A) = "неизвестный"
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [_range(sid, DATA_START_ROW - 1, 1000, 0, 200)],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [
                            {"userEnteredValue": f"=$A{DATA_START_ROW}=\"неизвестный\""}
                        ],
                    },
                    "format": {"backgroundColor": _YELLOW_BG},
                },
            },
            "index": 0,
        }
    })

    ws.spreadsheet.batch_update({"requests": requests})


def format_week_columns(ws: gspread.Worksheet, first_col: int, week_index: int = 0) -> None:
    """Apply formatting to a week block (first_col is 1-based, week_index is 0-based).

    Formats:
      - Row 9 (merged week date label): dark blue bg, white bold, centered
      - Row 10 (metric names): medium blue bg, white bold, centered
      - Data rows: currency/integer number formats + alternating pastel bg per week
      - Column width: 110px each

    week_index is used to alternate data-row background (cream / pastel blue).
    """
    sid = ws.id
    c0 = first_col - 1               # 0-based start
    c1 = first_col - 1 + WEEK_NCOLS  # 0-based end (exclusive)
    block_bg = _WEEK_ALT_BG[week_index % 2]

    requests: list[dict] = []

    # Data-row alternating background for this entire week block
    requests.append({
        "repeatCell": {
            "range": _range(sid, DATA_START_ROW - 1, 1000, c0, c1),
            "cell": {"userEnteredFormat": {"backgroundColor": block_bg}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Merge week date label across all metric columns in row 9
    requests.append({
        "mergeCells": {
            "range": {
                "sheetId": sid,
                "startRowIndex": WEEK_LABELS_ROW - 1,
                "endRowIndex": WEEK_LABELS_ROW,
                "startColumnIndex": c0,
                "endColumnIndex": c1,
            },
            "mergeType": "MERGE_ALL",
        }
    })

    # Row 9: dark blue, white bold, centered
    requests.append({
        "repeatCell": {
            "range": _range(sid, WEEK_LABELS_ROW - 1, WEEK_LABELS_ROW, c0, c1),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {
                        "bold": True, "fontSize": 10, "foregroundColor": _HEADER_FG,
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    })

    # Row 10: medium blue, white bold, centered, wrap
    requests.append({
        "repeatCell": {
            "range": _range(sid, METRIC_HEADERS_ROW - 1, METRIC_HEADERS_ROW, c0, c1),
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _METRIC_HDR_BG,
                    "textFormat": {
                        "bold": True, "fontSize": 9, "foregroundColor": _HEADER_FG,
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    })

    # Number formats for data rows
    currency_fmt = "#,##0\" ₽\""
    int_fmt = "0"
    for i, metric in enumerate(WEEK_METRICS):
        col = c0 + i
        if metric in ("Продажи, ₽", "К перечислению, ₽", "Ср. чек, ₽"):
            fmt = currency_fmt
        elif metric in ("Заказов, шт", "Возвратов, шт"):
            fmt = int_fmt
        else:
            continue
        requests.append({
            "repeatCell": {
                "range": _range(sid, DATA_START_ROW - 1, 1000, col, col + 1),
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": fmt}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        })

    # Column widths: 110px per metric column
    for i in range(WEEK_NCOLS):
        col = c0 + i
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "COLUMNS",
                          "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": 110},
                "fields": "pixelSize",
            }
        })

    ws.spreadsheet.batch_update({"requests": requests})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _range(sheet_id: int, r0: int, r1: int, c0: int, c1: int) -> dict:
    return {
        "sheetId": sheet_id,
        "startRowIndex": r0, "endRowIndex": r1,
        "startColumnIndex": c0, "endColumnIndex": c1,
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
