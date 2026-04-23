"""Запись листа «Перестановки Roadmap {cabinet}».

Структура листа (3 блока):
    1. Объяснение механики + ссылка на лист «Справочник»
    2. Паспорт прогноза (параметры симуляции + milestones 60%/80%)
    3. Понедельный roadmap (14 строк = неделя 0 + 13 прогноза),
       подсветка вех: неделя 0 (жёлтый), неделя 60% (светло-зелёный),
       неделя 80% (тёмно-зелёный).

Строки-описания под заголовками таблиц берутся из SHEET_COLUMN_DOCS.
"""
from __future__ import annotations

import logging
from typing import Any

from gspread import Spreadsheet
from gspread.exceptions import WorksheetNotFound

from .formatters import (
    _col_widths,
    _row_height,
    _freeze,
    _borders,
    _banding,
    _clear_banding,
    SHEET_COLUMN_DOCS,
)

logger = logging.getLogger(__name__)


_YELLOW_ANCHOR = {"red": 0.98, "green": 0.90, "blue": 0.60}
_LIGHT_GREEN = {"red": 0.85, "green": 0.92, "blue": 0.83}
_DARK_GREEN = {"red": 0.70, "green": 0.88, "blue": 0.70}


def roadmap_sheet_name(cabinet: str) -> str:
    """Имя листа для кабинета."""
    return f"Перестановки Roadmap {cabinet}"


def _get_or_create_worksheet(
    spreadsheet: Spreadsheet,
    name: str,
    rows: int = 200,
    cols: int = 13,
):
    """Вернуть существующий лист или создать новый."""
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _highlight_color(week_num: int, milestones: dict) -> dict | None:
    """Подсветка строки roadmap по номеру недели и milestone'ам.

    Возвращает RGB dict или None. Приоритет: 80% > 60% > week 0.
    Если milestone значение None — пропускаем.
    """
    w60 = milestones.get("week_60pct") if milestones else None
    w80 = milestones.get("week_80pct") if milestones else None
    if w80 is not None and week_num == w80:
        return _DARK_GREEN
    if w60 is not None and week_num == w60:
        return _LIGHT_GREEN
    if week_num == 0:
        return _YELLOW_ANCHOR
    return None


def write_roadmap_sheet(
    spreadsheet: Spreadsheet,
    cabinet: str,
    payload: dict[str, Any],
) -> None:
    """Пишет лист «Перестановки Roadmap {cabinet}» с 3 блоками.

    Args:
        spreadsheet: gspread Spreadsheet.
        cabinet: Код кабинета.
        payload: Результат `simulate_roadmap()`:
            - params (dict): realistic_limit_pct, target_localization,
              period_days, total_plan_qty, articles_with_movements
            - roadmap (list[dict]): 14 записей с week, date,
              moved_units_cumulative, plan_pct, il_forecast,
              ktr_weighted, logistics_monthly, irp_monthly,
              total_monthly, savings_vs_current
            - schedule (dict[str, list])
            - milestones (dict): week_60pct, week_80pct (int|None)
    """
    worksheet = _get_or_create_worksheet(spreadsheet, roadmap_sheet_name(cabinet))
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    params = payload.get("params", {}) or {}
    milestones = payload.get("milestones", {}) or {}
    w60 = milestones.get("week_60pct")
    w80 = milestones.get("week_80pct")

    # ------------------------------------------------------------------
    # БЛОК 1: Объяснение
    # ------------------------------------------------------------------
    rows.append(["🚚 ПЕРЕСТАНОВКИ + ROADMAP"])
    rows.append([f"Кабинет: {cabinet}"])
    rows.append([])
    rows.append([
        "Перестановки — опт-ин сервис WB. Комиссия +0.5% на все продажи, "
        "lock-in 90 дней."
    ])
    rows.append(["Подробнее — см. лист «Справочник» → блок 5."])
    rows.append([])

    # ------------------------------------------------------------------
    # БЛОК 2: Паспорт прогноза
    # ------------------------------------------------------------------
    passport_title_row = len(rows)
    rows.append(["ПАСПОРТ ПРОГНОЗА"])
    passport_header_row = len(rows)
    rows.append(["Параметр", "Значение", "Описание"])
    passport_data_start = len(rows)
    rows.append([
        "Реалистичный % лимитов",
        f"{params.get('realistic_limit_pct', 0) * 100:.0f}%",
        "Сколько слотов получаем по факту",
    ])
    rows.append([
        "Целевая лок. после переноса",
        f"{params.get('target_localization', 85):.0f}%",
        "Локализация артикула после успешного перемещения",
    ])
    rows.append([
        "Артикулов с перестановками",
        params.get("articles_with_movements", 0),
        "loc% < 80% и есть заказы",
    ])
    rows.append([
        "Всего единиц к перемещению",
        params.get("total_plan_qty", 0),
        "Суммарный план в шт",
    ])
    rows.append([
        "Неделя пересечения 60% (КРП→0)",
        w60 if w60 is not None else "—",
        "Quick win: КРП обнуляется",
    ])
    rows.append([
        "Неделя достижения 80% (КТР=0.80)",
        w80 if w80 is not None else "—",
        "Максимальная скидка логистики",
    ])
    passport_data_end = len(rows)
    rows.append([])

    # ------------------------------------------------------------------
    # БЛОК 3: Понедельный roadmap
    # ------------------------------------------------------------------
    roadmap_title_row = len(rows)
    rows.append(["ПОНЕДЕЛЬНЫЙ ROADMAP"])
    rows.append([])

    roadmap_headers = [
        "Неделя", "Дата", "Перемещено шт (кумулятив)", "% плана",
        "ИЛ прогноз", "КТР взвеш.", "Логистика ₽/мес",
        "Экономия vs Сейчас", "Статус",
    ]
    roadmap_header_row = len(rows)
    rows.append(roadmap_headers)
    roadmap_desc_row = len(rows)
    rows.append([SHEET_COLUMN_DOCS["roadmap"].get(h, "") for h in roadmap_headers])

    roadmap_data_start = len(rows)
    roadmap_entries = payload.get("roadmap", []) or []
    for week_data in roadmap_entries:
        week_num = week_data.get("week", 0)
        savings = week_data.get("savings_vs_current", 0)
        if week_num == 0:
            status = "🟡 Сейчас"
        elif w80 is not None and week_num == w80:
            status = "🎯 Цель 80%!"
        elif w60 is not None and week_num == w60:
            status = "🎯 Порог 60% (КРП→0)"
        else:
            # savings_vs_current = current_total_monthly - total_new:
            # положительное = экономим; отрицательное = платим больше.
            status = "🟢 В процессе" if savings > 0 else "🔴 Хуже текущего"

        rows.append([
            week_num,
            week_data.get("date", ""),
            week_data.get("moved_units_cumulative", 0),
            f"{week_data.get('plan_pct', 0):.1f}%",
            f"{week_data.get('il_forecast', 0):.1f}%",
            f"{week_data.get('ktr_weighted', 0):.3f}",
            round(week_data.get("logistics_monthly", 0)),
            round(savings),
            status,
        ])
    roadmap_data_end = len(rows)
    rows.append([])

    # ------------------------------------------------------------------
    # Запись данных одним вызовом
    # ------------------------------------------------------------------
    max_cols = max((len(r) for r in rows if r), default=9)
    max_cols = max(max_cols, 9)
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update(range_name="A1", values=normalized)

    # ------------------------------------------------------------------
    # Форматирование
    # ------------------------------------------------------------------
    sid = worksheet.id

    # Ширины колонок (подогнаны под roadmap-таблицу)
    format_requests.extend(_col_widths(sid, [
        (0, 70), (1, 90), (2, 180), (3, 80), (4, 110),
        (5, 110), (6, 150), (7, 160), (8, 180),
    ]))

    # Подсветка milestone строк roadmap
    for i, week_data in enumerate(roadmap_entries):
        color = _highlight_color(week_data.get("week", 0), milestones)
        if color:
            row_idx = roadmap_data_start + i
            is_milestone = (
                (w60 is not None and week_data.get("week") == w60)
                or (w80 is not None and week_data.get("week") == w80)
            )
            format_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sid,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(roadmap_headers),
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"bold": is_milestone},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

    # Границы таблиц
    if passport_data_end > passport_data_start:
        format_requests.append(_borders(
            sid, passport_header_row, passport_data_end, 0, 3,
        ))
    if roadmap_data_end > roadmap_data_start:
        format_requests.append(_borders(
            sid, roadmap_header_row, roadmap_data_end, 0, len(roadmap_headers),
        ))

    # Freeze верхней строки (чтобы заголовок был виден при прокрутке)
    format_requests.append(_freeze(sid, rows=1, cols=0))

    # Высота строки описания под заголовком roadmap
    format_requests.append(_row_height(sid, roadmap_desc_row, roadmap_desc_row + 1, 30))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})

    logger.info(
        "Записан лист '%s': %d недель roadmap",
        roadmap_sheet_name(cabinet),
        len(roadmap_entries),
    )
