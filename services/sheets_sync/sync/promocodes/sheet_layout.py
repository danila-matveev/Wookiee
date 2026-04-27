"""Pivot-layout constants and tiny pure helpers shared across promocodes modules."""
from __future__ import annotations

from datetime import date

DASHBOARD_HEADER_ROWS = 8   # rows 1-8: dashboard + GAS button
WEEK_LABELS_ROW = 9         # merged week date labels (e.g. "06.04–12.04.2026")
METRIC_HEADERS_ROW = 10     # metric column names per week + fixed column names
DATA_START_ROW = 11         # data rows start here

FIXED_HEADERS = ["Название", "UUID", "Канал", "Скидка %"]
FIXED_NCOLS = len(FIXED_HEADERS)  # 4  (cols A-D)

WEEK_METRICS = [
    "Продажи, ₽", "К перечислению, ₽",
    "Заказов, шт", "Возвратов, шт", "Ср. чек, ₽", "Топ модель",
]
WEEK_NCOLS = len(WEEK_METRICS)  # 6

DEFAULT_DICT_SHEET = "Промокоды_справочник"
DEFAULT_DATA_SHEET = "Промокоды_аналитика"


def _col_letter(col: int) -> str:
    """Convert 1-based column number to spreadsheet letter (A, B, ..., AA, ...)."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _week_label(week_start: date, week_end: date) -> str:
    return f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}"
