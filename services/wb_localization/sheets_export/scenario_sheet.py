"""Запись листа «Экономика сценариев {cabinet}».

Структура листа (5 блоков):
    1. Паспорт отчёта (период, текущий ИЛ, текущая логистика+ИРП)
    2. Сводная таблица сценариев 30-90% + anchor «Сейчас»
       (цветовое кодирование по `color`: red/yellow/green)
    3. KPI-плитки (текущая переплата, макс. потенциал, чистая выгода)
    4. Топ-артикулы, тянущие индекс вниз
    5. Экономика перестановок (комиссия, breakeven, lock-in)

Строки-описания под заголовками берутся из SHEET_COLUMN_DOCS.
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


_HEADER_BG = {"red": 0.098, "green": 0.325, "blue": 0.647}
_HEADER_FG = {"red": 1.0, "green": 1.0, "blue": 1.0}
_META_BG = {"red": 0.937, "green": 0.937, "blue": 0.937}
_DESC_FG = {"red": 0.35, "green": 0.35, "blue": 0.35}
_KPI_BG = {"red": 0.929, "green": 0.945, "blue": 0.976}


def scenario_sheet_name(cabinet: str) -> str:
    """Имя листа для кабинета."""
    return f"Экономика сценариев {cabinet}"


def _get_or_create_worksheet(
    spreadsheet: Spreadsheet,
    name: str,
    rows: int = 100,
    cols: int = 12,
):
    """Вернуть существующий лист или создать новый."""
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _color_for_scenario(color: str) -> dict:
    """Map «red/yellow/green» сценария в RGB."""
    return {
        "red": {"red": 0.96, "green": 0.80, "blue": 0.80},
        "yellow": {"red": 0.98, "green": 0.90, "blue": 0.60},
        "green": {"red": 0.85, "green": 0.92, "blue": 0.83},
    }.get(color, {"red": 1.0, "green": 1.0, "blue": 1.0})


def _title_row_fmt(sheet_id: int, row_idx: int, num_cols: int, font_size: int = 12) -> dict:
    """Формат строки-заголовка блока: тёмно-синий фон, белый жирный текст."""
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
                    "textFormat": {
                        "bold": True,
                        "fontSize": font_size,
                        "foregroundColor": _HEADER_FG,
                    },
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    }


def _desc_row_fmt(sheet_id: int, row_idx: int, num_cols: int) -> dict:
    """Формат строки-описания: курсив, серый, мелкий шрифт."""
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
                    "backgroundColor": _META_BG,
                    "textFormat": {
                        "italic": True,
                        "fontSize": 8,
                        "foregroundColor": _DESC_FG,
                    },
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy)",
        }
    }


def _column_header_fmt(sheet_id: int, row_idx: int, num_cols: int) -> dict:
    """Жирный синий заголовок колонок."""
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
                    "textFormat": {
                        "bold": True,
                        "fontSize": 10,
                        "foregroundColor": _HEADER_FG,
                    },
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    }


def write_scenario_sheet(
    spreadsheet: Spreadsheet,
    cabinet: str,
    payload: dict[str, Any],
) -> None:
    """Пишет лист «Экономика сценариев {cabinet}» с градацией 30-90%.

    Args:
        spreadsheet: gspread Spreadsheet.
        cabinet: Код кабинета.
        payload: Результат `analyze_scenarios()` со структурой:
            - period_days (int)
            - current_il (float)
            - current_loc_pct (float)
            - current_scenario (dict): label, level_pct, logistics_monthly,
              irp_monthly, total_monthly
            - scenarios (list[dict]): 7 сценариев 30..90% с level_pct, ktr,
              krp_pct, logistics_monthly, irp_monthly, total_monthly,
              delta_vs_current, delta_vs_worst, color
            - top_articles (list[dict])
            - relocation_economics (dict)
    """
    worksheet = _get_or_create_worksheet(spreadsheet, scenario_sheet_name(cabinet))
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    current = payload["current_scenario"]
    econ = payload["relocation_economics"]

    # ------------------------------------------------------------------
    # БЛОК 1: Паспорт (rows 1-10)
    # ------------------------------------------------------------------
    rows.append(["ПАСПОРТ ОТЧЁТА"])
    rows.append([f"Кабинет: {cabinet}"])
    rows.append([f"Период анализа: {payload['period_days']} дней"])
    rows.append([
        f"Текущий ИЛ: {payload['current_il']:.2f} "
        f"(≈ {payload['current_loc_pct']:.1f}% локализации)"
    ])
    rows.append([f"Текущая логистика: {current['logistics_monthly']:,.0f} ₽/мес"])
    rows.append([f"Текущая переплата ИРП: {current['irp_monthly']:,.0f} ₽/мес"])
    rows.append([f"Итого сейчас: {current['total_monthly']:,.0f} ₽/мес"])
    rows.append([])
    rows.append([])
    rows.append([])

    passport_title_row = 0  # 0-indexed row of «ПАСПОРТ ОТЧЁТА»

    # ------------------------------------------------------------------
    # БЛОК 2: Сводная таблица сценариев
    # ------------------------------------------------------------------
    scenarios_title_row = len(rows)
    rows.append(["СРАВНЕНИЕ СЦЕНАРИЕВ ЛОКАЛИЗАЦИИ"])
    rows.append([])

    scenario_headers = [
        "Сценарий", "Целевая лок.%", "КТР", "КРП%",
        "Логистика ₽/мес", "ИРП ₽/мес", "Итого ₽/мес",
        "Δ vs Сейчас", "Δ vs Худший",
    ]
    scenario_header_row = len(rows)
    rows.append(scenario_headers)
    scenario_desc_row = len(rows)
    rows.append([SHEET_COLUMN_DOCS["scenarios"].get(h, "") for h in scenario_headers])

    # Anchor «Сейчас» объединяется со сценариями и сортируется по level_pct
    current_anchor = {
        **current,
        "level_pct": payload["current_loc_pct"],
        "ktr": payload["current_il"],
        "krp_pct": 0.0,
        "delta_vs_current": 0.0,
        "delta_vs_worst": 0.0,
        "color": "yellow",
        "label": current.get("label", "Сейчас"),
    }
    all_scenarios = sorted(
        list(payload["scenarios"]) + [current_anchor],
        key=lambda s: s.get("level_pct", 0),
    )

    scenario_data_start = len(rows)
    for sc in all_scenarios:
        label = sc.get("label") or f"{sc['level_pct']:.0f}%"
        rows.append([
            label,
            f"{sc['level_pct']:.0f}%",
            f"{sc.get('ktr', 0):.2f}",
            f"{sc.get('krp_pct', 0):.2f}%",
            round(sc.get("logistics_monthly", 0)),
            round(sc.get("irp_monthly", 0)),
            round(sc.get("total_monthly", 0)),
            round(sc.get("delta_vs_current", 0)),
            round(sc.get("delta_vs_worst", 0)),
        ])
    scenario_data_end = len(rows)  # exclusive
    rows.append([])

    # ------------------------------------------------------------------
    # БЛОК 3: KPI-плитки
    # ------------------------------------------------------------------
    kpi_title_row = len(rows)
    rows.append(["KPI"])
    kpi_tiles_row = len(rows)
    rows.append([
        f"Сейчас платите: {current['total_monthly']:,.0f} ₽/мес",
        f"Макс. потенциал: {econ['max_savings_monthly']:,.0f} ₽/мес",
        f"Чистая выгода: {econ['net_benefit_monthly']:,.0f} ₽/мес",
    ])
    rows.append([])

    # ------------------------------------------------------------------
    # БЛОК 4: Топ-артикулы
    # ------------------------------------------------------------------
    top_title_row = len(rows)
    rows.append(["ТОП АРТИКУЛОВ ТЯНУЩИХ ИНДЕКС ВНИЗ"])
    rows.append([])

    top_headers = [
        "#", "Артикул", "Лок.% сейчас", "КТР", "КРП%", "Заказов/мес",
        "Логистика ₽/мес", "ИРП ₽/мес", "Вклад в ИЛ",
        "Экономия при 80% ₽/мес", "Статус",
    ]
    top_header_row = len(rows)
    rows.append(top_headers)
    top_desc_row = len(rows)
    rows.append([SHEET_COLUMN_DOCS["top_articles"].get(h, "") for h in top_headers])

    top_articles = payload.get("top_articles", []) or []
    top_data_start = len(rows)
    for i, art in enumerate(top_articles, 1):
        rows.append([
            i,
            art["article"],
            f"{art['loc_pct']:.0f}%",
            f"{art['ktr']:.2f}",
            f"{art['krp_pct']:.2f}%",
            art["orders_monthly"],
            round(art["logistics_fact_monthly"]),
            round(art["irp_current_monthly"]),
            f"{art['contribution_to_il']:+.1f}",
            round(art["savings_if_80_monthly"]),
            art["status"],
        ])
    top_data_end = len(rows)
    rows.append([])

    # ------------------------------------------------------------------
    # БЛОК 5: Экономика перестановок
    # ------------------------------------------------------------------
    econ_title_row = len(rows)
    rows.append(["ЭКОНОМИКА ПЕРЕСТАНОВОК"])
    rows.append([])

    econ_header_row = len(rows)
    rows.append(["Метрика", "Значение", "Описание"])
    econ_data_start = len(rows)
    rows.append([
        "Оборот кабинета ₽/мес",
        f"{econ['turnover_monthly']:,.0f}",
        "Общая выручка, из данных о заказах",
    ])
    rows.append([
        "Комиссия (+0.5%)",
        f"{econ['commission_monthly']:,.0f}",
        "Платится пока опция включена",
    ])
    rows.append([
        "Точка окупаемости",
        f"{econ['breakeven_monthly']:,.0f}",
        "Экономия должна быть выше",
    ])
    rows.append([
        "Макс. экономия при 80%",
        f"{econ['max_savings_monthly']:,.0f}",
        "Потенциал из сводной таблицы",
    ])
    rows.append([
        "ЧИСТАЯ ВЫГОДА",
        f"{econ['net_benefit_monthly']:,.0f}",
        "✅ если > 0 — перестановки выгодны",
    ])
    rows.append([
        "Lock-in период",
        f"{econ['lock_in_days']} дней",
        "Нельзя отключить раньше",
    ])
    econ_data_end = len(rows)

    # ------------------------------------------------------------------
    # Запись данных
    # ------------------------------------------------------------------
    max_cols = max((len(r) for r in rows if r), default=9)
    max_cols = max(max_cols, 9)
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update(range_name="A1", values=normalized)

    # ------------------------------------------------------------------
    # Форматирование
    # ------------------------------------------------------------------
    sid = worksheet.id

    # Ширины колонок
    format_requests.extend(_col_widths(sid, [
        (0, 160), (1, 110), (2, 80), (3, 80),
        (4, 140), (5, 140), (6, 140), (7, 120), (8, 120),
        (9, 180), (10, 130),
    ]))

    # Заголовок паспорта
    format_requests.append(_title_row_fmt(sid, passport_title_row, max_cols, font_size=13))
    format_requests.append(_row_height(sid, passport_title_row, passport_title_row + 1, 32))
    # Паспорт: строки 2-7 — светло-серый
    for r in range(1, 7):
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": r,
                    "endRowIndex": r + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": max_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _META_BG,
                        "textFormat": {"fontSize": 10},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # Заголовок «СРАВНЕНИЕ СЦЕНАРИЕВ»
    format_requests.append(_title_row_fmt(sid, scenarios_title_row, max_cols, font_size=12))
    format_requests.append(_row_height(sid, scenarios_title_row, scenarios_title_row + 1, 28))
    # Заголовки колонок сценариев
    format_requests.append(_column_header_fmt(sid, scenario_header_row, len(scenario_headers)))
    # Строка-описание
    format_requests.append(_desc_row_fmt(sid, scenario_desc_row, len(scenario_headers)))
    format_requests.append(_row_height(sid, scenario_desc_row, scenario_desc_row + 1, 30))

    # Цветовое кодирование строк сценариев
    for i, sc in enumerate(all_scenarios):
        color = _color_for_scenario(sc.get("color", "yellow"))
        row_idx = scenario_data_start + i
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(scenario_headers),
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    # Границы таблицы сценариев
    if scenario_data_end > scenario_data_start:
        format_requests.append(_borders(
            sid,
            scenario_header_row,
            scenario_data_end,
            0,
            len(scenario_headers),
        ))

    # KPI-плитки
    format_requests.append(_title_row_fmt(sid, kpi_title_row, max_cols, font_size=12))
    format_requests.append({
        "repeatCell": {
            "range": {
                "sheetId": sid,
                "startRowIndex": kpi_tiles_row,
                "endRowIndex": kpi_tiles_row + 1,
                "startColumnIndex": 0,
                "endColumnIndex": 3,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _KPI_BG,
                    "textFormat": {"bold": True, "fontSize": 11},
                    "horizontalAlignment": "CENTER",
                    "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }
    })
    format_requests.append(_row_height(sid, kpi_tiles_row, kpi_tiles_row + 1, 48))

    # Топ-артикулы
    format_requests.append(_title_row_fmt(sid, top_title_row, max_cols, font_size=12))
    format_requests.append(_row_height(sid, top_title_row, top_title_row + 1, 28))
    format_requests.append(_column_header_fmt(sid, top_header_row, len(top_headers)))
    format_requests.append(_desc_row_fmt(sid, top_desc_row, len(top_headers)))
    format_requests.append(_row_height(sid, top_desc_row, top_desc_row + 1, 30))

    if top_data_end > top_data_start:
        format_requests.append(_borders(
            sid,
            top_header_row,
            top_data_end,
            0,
            len(top_headers),
        ))
        format_requests.append(_banding(sid, top_data_start, top_data_end, len(top_headers)))

    # Экономика перестановок
    format_requests.append(_title_row_fmt(sid, econ_title_row, max_cols, font_size=12))
    format_requests.append(_row_height(sid, econ_title_row, econ_title_row + 1, 28))
    format_requests.append(_column_header_fmt(sid, econ_header_row, 3))
    if econ_data_end > econ_data_start:
        format_requests.append(_borders(sid, econ_header_row, econ_data_end, 0, 3))

    # Фиксируем верхнюю строку (паспорт-заголовок)
    format_requests.append(_freeze(sid, rows=1, cols=0))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})

    logger.info(
        "Записан лист '%s': %d сценариев, %d топ-артикулов",
        scenario_sheet_name(cabinet),
        len(all_scenarios),
        len(top_articles),
    )
