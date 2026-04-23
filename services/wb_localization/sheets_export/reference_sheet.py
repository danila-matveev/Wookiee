"""Запись листа «Справочник» (расширенная документация WB локализации).

Пишет 8 тематических блоков:
    1. Обложка + оглавление
    2. Формула логистики
    3. ИЛ (КТР-таблица)
    4. ИРП (КРП-таблица)
    5. Исключения (КГТ/СГТ/КБТ/FBS, правило 35%)
    6. Перестановки (комиссия, склады, экономика)
    7. Скользящее окно 13 недель
    8. Disclaimer (наш расчёт vs WB)

Данные берутся только из `build_reference_content()`. Никаких вычислений.
"""
from __future__ import annotations

from typing import Any

from gspread.exceptions import WorksheetNotFound

from .formatters import (
    _col_widths,
    _row_height,
    _freeze,
    _clear_banding,
)

REFERENCE_SHEET_NAME = "Справочник"


def _get_or_create_worksheet(spreadsheet, name: str, rows: int = 200, cols: int = 10):
    """Return existing worksheet by name or create a new one."""
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _color_to_rgb(color: str) -> dict:
    """Map semantic color name to Google Sheets RGB dict."""
    colors = {
        "green": {"red": 0.85, "green": 0.92, "blue": 0.83},
        "yellow": {"red": 0.98, "green": 0.90, "blue": 0.60},
        "red": {"red": 0.96, "green": 0.80, "blue": 0.80},
        "blue_header": {"red": 0.20, "green": 0.25, "blue": 0.45},
    }
    return colors.get(color, {"red": 1.0, "green": 1.0, "blue": 1.0})


def write_reference_sheet(spreadsheet, content: dict[str, Any]) -> None:
    """Пишет расширенный лист «Справочник» со всеми 8 блоками.

    Args:
        spreadsheet: gspread Spreadsheet объект.
        content: Результат `build_reference_content()`.
    """
    worksheet = _get_or_create_worksheet(spreadsheet, REFERENCE_SHEET_NAME)
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    # --- Блок 1: обложка ---
    rows.append([content["cover"]["title"]])
    rows.append([content["cover"]["subtitle"]])
    rows.append([])
    rows.append(["Оглавление:"])
    rows.append(["→ 1. Формула логистики"])
    rows.append(["→ 2. Индекс локализации (ИЛ)"])
    rows.append(["→ 3. Индекс распределения продаж (ИРП)"])
    rows.append(["→ 4. Исключения"])
    rows.append(["→ 5. Перестановки"])
    rows.append(["→ 6. Скользящее окно"])
    rows.append([])

    # --- Блок 2: формула логистики ---
    rows.append(["1. ОСНОВНАЯ ФОРМУЛА ЛОГИСТИКИ"])
    rows.append([])
    rows.append([content["formula_block"]["formula"]])
    rows.append([])
    rows.append(["Компонент", "Описание"])
    for c in content["formula_block"]["components"]:
        rows.append([c["name"], c["desc"]])
    rows.append([])
    ex = content["formula_block"]["example"]
    rows.append([
        f"💡 Пример: цена {ex['price']}₽, объём {ex['volume_liters']}л, "
        f"лок. {ex['article_loc_pct']}%"
    ])
    rows.append([f"   Объёмная часть: {ex['volume_part']}₽"])
    rows.append([f"   Ценовая часть: {ex['price_part']}₽"])
    rows.append([f"   ИТОГО: {ex['total']}₽"])
    rows.append([])

    # --- Блок 3: ИЛ ---
    rows.append(["2. ИНДЕКС ЛОКАЛИЗАЦИИ (ИЛ)"])
    rows.append([])
    rows.append([content["il_section"]["definition"]])
    rows.append([content["il_section"]["formula"]])
    rows.append([content["il_section"]["period_note"]])
    rows.append([])
    rows.append(["Мин. %", "Макс. %", "КТР", "Описание"])
    ktr_start_row = len(rows)
    for row in content["il_section"]["table"]:
        rows.append([row["min_loc"], row["max_loc"], row["ktr"], row["description"]])
    rows.append([])

    # --- Блок 4: ИРП ---
    rows.append(["3. ИНДЕКС РАСПРЕДЕЛЕНИЯ ПРОДАЖ (ИРП)"])
    rows.append([])
    rows.append([content["irp_section"]["formula"]])
    rows.append([f"⚠️ КЛЮЧЕВОЙ ПОРОГ: {content['irp_section']['critical_threshold']['value']}%"])
    rows.append([content["irp_section"]["critical_threshold"]["note"]])
    rows.append([])
    rows.append(["Мин. %", "Макс. %", "КРП %", "Описание"])
    krp_start_row = len(rows)
    for row in content["irp_section"]["table"]:
        rows.append([row["min_loc"], row["max_loc"], row["krp_pct"], row["description"]])
    rows.append([])

    # --- Блок 5: исключения ---
    rows.append(["4. ИСКЛЮЧЕНИЯ"])
    rows.append([])
    rows.append(["Категории-исключения:"])
    for cat in content["exceptions"]["categories"]:
        rows.append([f"  • {cat}"])
    rows.append([])
    rows.append(["⚠️ Правило 35%:"])
    rows.append([content["exceptions"]["rule_35"]])
    rows.append([])

    # --- Блок 6: перестановки ---
    rows.append(["5. ПЕРЕСТАНОВКИ (ПЕРЕРАСПРЕДЕЛЕНИЕ)"])
    rows.append([])
    rows.append([content["relocation_section"]["description"]])
    rows.append([])
    rows.append([f"Комиссия: +{content['relocation_section']['commission_pct']}% на все продажи"])
    rows.append([f"Lock-in: {content['relocation_section']['lock_in_days']} дней"])
    rows.append([])
    rows.append(["Склады и дневные лимиты:"])
    rows.append(["Склад", "Лимит шт/день"])
    for wh in content["relocation_section"]["warehouses"][:25]:
        rows.append([wh["name"], wh["limit_per_day"]])
    rows.append([])
    econ = content["relocation_section"]["economics_example"]
    rows.append(["💡 Экономика перестановок:"])
    rows.append([
        f"  Оборот {econ['turnover_monthly']:,} ₽/мес → "
        f"комиссия {econ['commission_monthly']:,.0f} ₽/мес"
    ])
    rows.append([f"  Окупается если: {econ['breakeven']}"])
    rows.append([])

    # --- Блок 7: скользящее окно ---
    rows.append(["6. СКОЛЬЗЯЩЕЕ ОКНО 13 НЕДЕЛЬ"])
    rows.append([])
    rows.append([content["sliding_window"]["explanation"]])
    rows.append([content["sliding_window"]["formula"]])
    rows.append([])
    rows.append(["От локализации (%)", "До порога (%)", "Недель"])
    for row in content["sliding_window"]["weeks_to_threshold"]:
        rows.append([row["from_loc"], row["to_loc"], row["weeks"]])
    rows.append([])
    rows.append([f"🚨 {content['sliding_window']['call_to_action']}"])
    rows.append([])

    # --- Блок 8: disclaimer ---
    rows.append(["НАШ РАСЧЁТ vs WB"])
    rows.append([content["disclaimer"]["note"]])

    # --- Запись данных одним вызовом ---
    max_cols = max((len(r) for r in rows if r), default=4)
    max_cols = max(max_cols, 4)
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update("A1", normalized)

    # --- Форматирование ---
    # Column widths
    format_requests.extend(_col_widths(worksheet.id, [
        (0, 180), (1, 180), (2, 120), (3, 280),
    ]))

    # Block title rows: first cell is UPPERCASE string, длиной > 5
    block_title_rows = [
        i for i, r in enumerate(rows)
        if r and isinstance(r[0], str) and r[0].isupper() and len(r[0]) > 5
    ]
    for row_idx in block_title_rows:
        format_requests.append(_row_height(worksheet.id, row_idx, row_idx + 1, 32))
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": max_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _color_to_rgb("blue_header"),
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                            "fontSize": 13,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # Раскраска строк КТР по цветам
    for i, row_data in enumerate(content["il_section"]["table"]):
        row_idx = ktr_start_row + i
        color = _color_to_rgb(row_data["color"])
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    # Раскраска строк КРП
    for i, row_data in enumerate(content["irp_section"]["table"]):
        row_idx = krp_start_row + i
        color = _color_to_rgb(row_data["color"])
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    # Freeze top cover row
    format_requests.append(_freeze(worksheet.id, rows=1, cols=0))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})
