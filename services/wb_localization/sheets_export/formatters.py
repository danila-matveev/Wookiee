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


# ============================================================================
# Column descriptions — centralized strings for description rows under headers
# ============================================================================
SHEET_COLUMN_DOCS = {
    "scenarios": {
        "Сценарий": "Уровень локализации и оценка относительно текущего",
        "Целевая лок.%": "Локализация в этом сценарии (30, 40, ..., 90%)",
        "КТР": "Коэффициент логистики для этого уровня (из таблицы WB)",
        "КРП%": "Процент надбавки к цене (0% если ИЛ≥60%)",
        "Логистика ₽/мес": "Объёмная часть логистики при этом уровне ИЛ",
        "ИРП ₽/мес": "Ценовая надбавка: Σ(цена × КРП%) по артикулам",
        "Итого ₽/мес": "Сумма логистики и ИРП за месяц",
        "Δ vs Сейчас": "Разница с текущим состоянием (- = экономия, + = переплата)",
        "Δ vs Худший": "Разница с худшим сценарием (всегда <= 0)",
    },
    "top_articles": {
        "#": "Ранг по потенциалу экономии",
        "Артикул": "Артикул продавца (supplierArticle)",
        "Лок.% сейчас": "Текущая локализация артикула (локальные/всего заказов × 100)",
        "КТР": "Текущий коэффициент логистики артикула",
        "КРП%": "Текущая надбавка к цене в %",
        "Заказов/мес": "Среднемесячный объём заказов",
        "Логистика ₽/мес": "Текущая факт. логистика артикула в месяц",
        "ИРП ₽/мес": "Текущая надбавка артикула в месяц",
        "Вклад в ИЛ": "Вклад артикула во взвеш. ИЛ кабинета (п.п., < 0 = тянет вниз)",
        "Экономия при 80% ₽/мес": "Потенциал экономии если довести до 80% локализации",
        "Статус": "🟢 Отличная / 🟡 Нейтральная / 🟠 Слабая / 🔴 Критическая",
    },
    "roadmap": {
        "Неделя": "Номер недели с начала перестановок, 0 = старт",
        "Дата": "Календарная дата начала этой недели",
        "Перемещено шт (кумулятив)": "Сколько единиц суммарно перенесли к этой неделе",
        "% плана": "% выполнения плана перестановок (кумулятив / всего)",
        "ИЛ прогноз": "Расчётный % локализации с учётом 13-нед. скольз. окна",
        "КТР взвеш.": "Взвешенный КТР по всем артикулам кабинета",
        "Логистика ₽/мес": "Прогноз логистики + ИРП на эту неделю",
        "Экономия vs Сейчас": "Разница с неделей 0 (зелёный = экономим)",
        "Статус": "Вехи: 🎯 порог 60% (КРП→0), 🎯 цель 80% (КТР=0.80)",
    },
    "plan": {
        "#": "Приоритет (1 = самый важный по impact ₽)",
        "Приоритет": "P1 (лок<60%) / P2 (60-75%) / P3 (мониторинг)",
        "Артикул": "Артикул продавца",
        "Размер": "Размер SKU",
        "Лок.% текущая": "Текущая локализация артикула",
        "Откуда (ФО + склад)": "Исходный регион и склад-донор (с избытком)",
        "Куда (ФО + склад)": "Целевой регион и склад-получатель (с дефицитом)",
        "Кол-во шт": "Рекомендуемое количество для перемещения",
        "Импакт на ИЛ (п.п.)": "На сколько вырастет индекс кабинета после переноса",
        "Экономия ₽/мес": "Прогнозная экономия при успешном переносе",
        "Склад-лимит": "✅ хватает capacity / ⚠️ впритык / ❌ не хватает",
        "Неделя старта": "В какую неделю запланировано в schedule",
    },
}


def write_column_descriptions(
    rows: list,
    column_headers: list[str],
    category: str,
) -> list:
    """Вставляет строку-описание под заголовком таблицы.

    Args:
        rows: Существующие строки (список списков).
        column_headers: Заголовки колонок.
        category: Ключ в SHEET_COLUMN_DOCS.

    Returns:
        rows с добавленной строкой описаний.
    """
    docs = SHEET_COLUMN_DOCS.get(category, {})
    desc_row = [docs.get(h, "") for h in column_headers]
    rows.append(desc_row)
    return rows
