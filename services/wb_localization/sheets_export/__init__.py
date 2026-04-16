"""Export Vasily localization report data to Google Sheets.

Facade package. Preserves the original public API surface:
    from services.wb_localization.sheets_export import (
        export_to_sheets, export_dashboard,
    )

Internal layout:
    formatters.py        — shared styling helpers (colors, batchUpdate ops)
    core_sheets.py       — per-cabinet data sheets + dashboard
    analysis_sheets.py   — ИЛ Анализ, Справочник, Экономика (legacy), История
"""
from __future__ import annotations

import logging

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
)
from services.wb_localization.config import GOOGLE_SA_FILE, VASILY_SPREADSHEET_ID

from .core_sheets import (
    write_moves,
    write_supplies,
    write_summary,
    write_regions,
    write_top_problems,
    _apply_formatting,
    export_dashboard,
)
from .analysis_sheets import (
    write_il_analysis,
    _apply_il_formatting,
    write_economics_sheet,
    append_history,
)
from .reference_sheet import (
    write_reference_sheet,
    REFERENCE_SHEET_NAME,
)
from .scenario_sheet import (
    write_scenario_sheet,
    scenario_sheet_name,
)

# Backward-compat aliases (old underscored names used inside this module
# historically; kept for any external callers that imported them directly).
_write_moves = write_moves
_write_supplies = write_supplies
_write_summary = write_summary
_write_regions = write_regions
_write_top_problems = write_top_problems
_write_il_analysis = write_il_analysis
_write_economics_sheet = write_economics_sheet
_append_history = append_history

logger = logging.getLogger(__name__)


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
    import pandas as pd

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
    write_moves(spreadsheet, cabinet, moves_df, meta)

    # --- Допоставки ---
    write_supplies(spreadsheet, cabinet, supply_df, meta)

    # --- Сводка ---
    write_summary(spreadsheet, cabinet, summary, comparison, meta)

    # --- Регионы ---
    write_regions(spreadsheet, cabinet, regions, meta)

    # --- Проблемные SKU ---
    write_top_problems(spreadsheet, cabinet, top_problems, meta)

    # --- История (append) ---
    append_history(spreadsheet, result, date_str, time_str)

    # --- Форматирование всех листов кабинета ---
    _apply_formatting(spreadsheet, cabinet)

    # --- Module 2: ИЛ/ИРП analysis sheets ---
    il_irp = result.get("il_irp")
    if il_irp:
        write_il_analysis(il_irp, cabinet, spreadsheet)
        _apply_il_formatting(spreadsheet, cabinet, len(il_irp.get("articles", [])))

    # --- Module 3: Economic analysis sheet ---
    # Новый scenario_sheet (30-90% градация) имеет приоритет.
    # Если payload содержит `scenarios` — пишем новый лист.
    # Иначе fallback на legacy `write_economics_sheet` (3-сценарийный).
    scenarios_payload = result.get("scenarios")
    if scenarios_payload:
        write_scenario_sheet(spreadsheet, cabinet, scenarios_payload)
    else:
        economics = result.get("economics")
        if economics:
            write_economics_sheet(economics, cabinet, spreadsheet)

    # --- Reference sheet (Справочник) — расширенная документация ---
    # Пишется только если payload содержит собранный `reference` блок.
    # Backward-compat: если отсутствует — просто пропускаем.
    reference = result.get("reference")
    if reference:
        write_reference_sheet(spreadsheet, reference)

    url = f"https://docs.google.com/spreadsheets/d/{VASILY_SPREADSHEET_ID}"
    logger.info("Экспорт в Sheets: %s (%s)", cabinet, url)
    return url


__all__ = [
    "export_to_sheets",
    "export_dashboard",
    "write_moves",
    "write_supplies",
    "write_summary",
    "write_regions",
    "write_top_problems",
    "write_il_analysis",
    "write_economics_sheet",
    "write_reference_sheet",
    "REFERENCE_SHEET_NAME",
    "write_scenario_sheet",
    "scenario_sheet_name",
    "append_history",
    # Backward-compat underscore aliases:
    "_write_moves",
    "_write_supplies",
    "_write_summary",
    "_write_regions",
    "_write_top_problems",
    "_write_il_analysis",
    "_write_economics_sheet",
    "_append_history",
]
