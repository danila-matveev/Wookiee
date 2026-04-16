"""Formatting helpers for WB Localization Sheets export.

Colors, low-level batchUpdate request builders, and banding cleanup.
Shared by core_sheets and analysis_sheets modules.
"""
from __future__ import annotations


# ============================================================================
# Color palette & formatting constants
# ============================================================================
_HEADER_BG = {"red": 0.098, "green": 0.325, "blue": 0.647}
_HEADER_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
_META_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}
_ALT_ROW = {"red": 0.929, "green": 0.945, "blue": 0.976}

_GREEN_BG = {"red": 0.851, "green": 0.918, "blue": 0.827}
_RED_BG = {"red": 0.957, "green": 0.800, "blue": 0.800}
_YELLOW_BG = {"red": 1.0, "green": 0.949, "blue": 0.800}
_DARK_GREEN_BG = {"red": 0.263, "green": 0.545, "blue": 0.318}
_DARK_RED_BG = {"red": 0.698, "green": 0.133, "blue": 0.133}


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
