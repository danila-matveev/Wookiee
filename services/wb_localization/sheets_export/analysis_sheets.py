"""Analysis sheet writers for WB Localization.

Contains:
- ИЛ Анализ (per-article localization index analysis, 37 columns)
- Справочник (static reference tables for КТР/КРП coefficients)
- Экономика (legacy scenario comparison — to be replaced by scenario_sheet in Task 8)
- История (append-only trend row)
"""
from __future__ import annotations

import logging

from shared.clients.sheets_client import (
    get_or_create_worksheet,
    write_range,
    to_number,
)

from .formatters import (
    _HEADER_BG,
    _HEADER_FG,
    _META_BG,
    _GREEN_BG,
    _RED_BG,
    _YELLOW_BG,
    _header_fmt,
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


def write_il_analysis(il_irp: dict, cabinet: str, spreadsheet) -> None:
    """Write per-article ИЛ analysis sheet (37 columns)."""
    sheet_name = f"ИЛ Анализ {cabinet}"
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=2000, cols=37)

    summary = il_irp["summary"]
    articles = il_irp["articles"]
    meta = summary.get("metadata", {})

    # --- Passport block (rows 1-11) ---
    passport_data = [
        ["ПАСПОРТ ОТЧЁТА", "", ""],
        ["Дата формирования", meta.get("generated_at", "—"), ""],
        [
            "Период анализа",
            f"{meta.get('period_from', '—')} — {meta.get('period_to', '—')} "
            f"({meta.get('period_days', '—')} дн.)",
            "",
        ],
        ["Источник данных", meta.get("data_source", "—"), ""],
        ["Всего заказов", meta.get("total_orders_loaded", "—"), ""],
        ["Отменённые", meta.get("cancelled_orders", "—"), ""],
        ["Пропущенные", meta.get("skipped_orders", "—"), "(не удалось определить регион)"],
        ["РФ заказов", meta.get("rf_orders_analyzed", "—"), ""],
        ["СНГ заказов", meta.get("cis_orders", "—"), ""],
        ["Артикулов", meta.get("articles_analyzed", "—"), ""],
        ["", "", ""],
    ]

    # --- KPI block (rows 12-21) ---
    kpi_data = [
        ["МЕТРИКИ", "Метрика", "Значение"],
        ["", "ИЛ (Индекс Локализации)", summary["overall_il"]],
        ["", "ИРП", f"{summary['overall_irp_pct']:.2f}%"],
        ["", "Локальных заказов WB (РФ)", summary["local_orders"]],
        ["", "Нелокальных заказов WB (РФ)", summary["nonlocal_orders"]],
        ["", "% локализации (всего)", f"{summary['loc_pct']:.1f}%"],
        ["", "Всего FBW заказов (РФ)", summary["total_rf_orders"]],
        ["", "Артикулов в расчёте", summary["total_articles"]],
        ["", "Артикулов в ИРП-зоне", summary["irp_zone_articles"]],
        ["", "ИРП-нагрузка ₽/мес", f"{summary['irp_monthly_cost_rub']:,.0f}"],
    ]

    # Region names for column headers
    region_short = ["Центр.", "Юж.+СК", "Привол.", "Урал.", "Дальн.+Сиб.", "С-Зап."]
    region_keys = [
        "Центральный", "Южный + Северо-Кавказский", "Приволжский",
        "Уральский", "Дальневосточный + Сибирский", "Северо-Западный",
    ]

    # Column headers (row 23)
    col_headers = [
        "Артикул", "ВБ Лок. (РФ)", "ВБ Нелок. (РФ)", "Всего WB (РФ)",
        "% лок.", "КТР", "КРП,%", "Вклад шт×КТР", "Статус",
    ]
    for rn in region_short:
        col_headers.extend([f"Лок. {rn}", f"Нелок. {rn}", f"Всего {rn}", f"% лок. {rn}"])
    col_headers.extend(["Вклад в ИЛ", "ИРП ₽/мес"])

    # Data rows
    data_rows = []
    for art in articles:
        row = [
            art["article"],
            art["wb_local"], art["wb_nonlocal"], art["wb_total"],
            art["loc_pct"], art["ktr"], art["krp_pct"],
            art["weighted"], art["status"],
        ]
        for rk in region_keys:
            rg = art.get("regions", {}).get(rk, {"local": 0, "nonlocal": 0, "total": 0, "pct": 0})
            row.extend([rg["local"], rg["nonlocal"], rg["total"], rg["pct"]])
        row.extend([art["contribution"], art.get("irp_per_month", 0)])
        data_rows.append(row)

    ws.clear()
    write_range(ws, 1, 1, passport_data)
    write_range(ws, 12, 1, kpi_data)
    write_range(ws, 23, 1, [col_headers])
    if data_rows:
        write_range(ws, 24, 1, data_rows)
    logger.info("Записан лист '%s': %d артикулов", sheet_name, len(articles))


def _write_reference_sheet(spreadsheet) -> None:
    """Write static reference sheet with КТР/КРП tables and formulas."""
    from services.wb_localization.irp_coefficients import COEFF_TABLE

    ws = get_or_create_worksheet(spreadsheet, "Справочник", rows=40, cols=10)

    data = [
        ["Таблица КТР (с 23.03.2026)", "", "", "", "Таблица КРП (с 23.03.2026)", "", ""],
        ["Доля лок., %", "КТР", "Описание", "", "Доля лок., %", "КРП, %", "Описание"],
    ]

    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        ktr_desc = "Скидка" if ktr < 1.0 else ("Базовый" if ktr == 1.0 else "Штраф")
        krp_desc = "Нет надбавки" if krp == 0 else f"{krp}% от цены"
        data.append([
            f"{min_loc:.0f}–{max_loc:.0f}%", ktr, ktr_desc,
            "", f"{min_loc:.0f}–{max_loc:.0f}%", f"{krp:.2f}%", krp_desc,
        ])

    _pad = lambda row: row + [""] * (7 - len(row))
    data.append(_pad([]))
    data.append(_pad(["Формулы:"]))
    data.append(_pad(["ИЛ = Σ(заказы × КТР) / Σ(заказы)  — средневзвешенный КТР"]))
    data.append(_pad(["ИРП = Σ(заказы × КРП%) / (РФ + СНГ заказы)  — СНГ в знаменателе с КРП=0"]))
    data.append(_pad([]))
    data.append(_pad(["Статусы:"]))
    data.append(_pad(["КТР ≤ 0.90 → Отличная | 0.91–1.05 → Нейтральная | 1.06–1.30 → Слабая | ≥ 1.31 → Критическая"]))

    ws.clear()
    write_range(ws, 1, 1, data)
    logger.info("Записан лист 'Справочник'")


def _apply_il_formatting(spreadsheet, cabinet: str, num_articles: int) -> None:
    """Apply conditional formatting to ИЛ Анализ sheet.

    - Header row: dark blue bg, white text
    - Status column (I): colored by status text
    - Alternating rows
    - Borders
    """
    ws_map = {ws.title: ws for ws in spreadsheet.worksheets()}
    title = f"ИЛ Анализ {cabinet}"
    ws = ws_map.get(title)
    if not ws:
        return

    sid = ws.id
    nc = 35  # approximate number of columns
    # Layout after passport addition:
    #   rows 1-11  → passport block (0-indexed 0-10)
    #   rows 12-21 → KPI block     (0-indexed 11-20)
    #   row  22    → empty separator (0-indexed 21) – unused
    #   row  23    → column headers  (0-indexed 22)
    #   row  24+   → data rows       (0-indexed 23+)
    col_header_row = 22  # 0-indexed
    data_start = 23       # 0-indexed: row 24 is first data row
    data_end = data_start + num_articles

    reqs: list[dict] = []
    _clear_banding(spreadsheet, sid)

    # Passport block (rows 1-11, 0-indexed 0-10): title + light grey rows
    # Row 1 (0-indexed 0): passport title — dark blue header
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                       "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _HEADER_FG},
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })
    # Rows 2-11 (0-indexed 1-10): passport data — light grey
    for r in range(1, 11):
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                           "startColumnIndex": 0, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _META_BG,
                        "textFormat": {"bold": False, "fontSize": 10},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # KPI block title (row 12, 0-indexed 11): dark blue header
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 11, "endRowIndex": 12,
                       "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _HEADER_FG},
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })
    # KPI data rows (rows 13-21, 0-indexed 12-20): light grey
    for r in range(12, 21):
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                           "startColumnIndex": 1, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _META_BG,
                        "textFormat": {"bold": False, "fontSize": 10},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # Row 23 (0-indexed 22): column headers — dark blue
    reqs.append(_header_fmt(sid, col_header_row, nc))
    reqs.append(_row_height(sid, col_header_row, col_header_row + 1, 32))

    # Freeze to include passport + KPI + column header row
    reqs.append(_freeze(sid, rows=23, cols=1))

    # Column widths
    reqs.extend(_col_widths(sid, [
        (0, 200),  # Артикул
        (1, 80), (2, 80), (3, 80),  # local/nonlocal/total
        (4, 70),  # % лок
        (5, 60), (6, 60),  # КТР, КРП%
        (7, 100),  # Вклад
        (8, 110),  # Статус
    ]))

    # Borders around data area
    if num_articles > 0:
        reqs.append(_borders(sid, col_header_row, data_end, 0, nc))
        reqs.append(_banding(sid, data_start, data_end, nc))

        # Number format: % лок (col 4), КТР (col 5)
        reqs.append(_num_fmt(sid, data_start, data_end, 4, 5, "0.0"))
        reqs.append(_num_fmt(sid, data_start, data_end, 5, 6, "0.00"))
        reqs.append(_num_fmt(sid, data_start, data_end, 6, 7, "0.00"))

        # Bold article column
        reqs.append(_bold_col(sid, data_start, data_end, 0))

    # Status column conditional formatting (col 8 = index 8)
    # Using addConditionalFormatRule for text-based coloring
    status_colors = [
        ("Отличная", {"red": 0.263, "green": 0.545, "blue": 0.318}),
        ("Нейтральная", {"red": 0.412, "green": 0.545, "blue": 0.671}),
        ("Слабая", {"red": 0.886, "green": 0.600, "blue": 0.200}),
        ("Критическая", {"red": 0.698, "green": 0.133, "blue": 0.133}),
    ]
    for idx, (status_text, fg_color) in enumerate(status_colors):
        reqs.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sid,
                        "startRowIndex": data_start,
                        "endRowIndex": data_end,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": status_text}],
                        },
                        "format": {
                            "textFormat": {"bold": True, "foregroundColor": fg_color},
                        },
                    },
                },
                "index": idx,
            }
        })

    if reqs:
        spreadsheet.batch_update({"requests": reqs})
        logger.info("Форматирование '%s': %d запросов", title, len(reqs))


# ============================================================================
# Economics sheet (LEGACY — to be replaced by scenario_sheet in Task 8)
# ============================================================================

def write_economics_sheet(economics: dict, cabinet: str, spreadsheet) -> None:
    """Write economic scenario analysis sheet.

    LEGACY — to be replaced by scenario_sheet in Task 8.
    """
    import datetime as _dt

    sheet_name = f"Экономика {cabinet}"
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=120, cols=10)
    ws.clear()

    sc = economics["scenarios"]
    no_ctrl = sc["no_control"]
    current = sc["current"]
    optimized = sc["optimized"]
    period_days = economics.get("period_days", 30)

    _now = _dt.datetime.now()
    _period_from = (_now - _dt.timedelta(days=period_days)).strftime('%d.%m.%Y')
    _period_to = _now.strftime('%d.%m.%Y')
    _generated_at = _now.strftime('%d.%m.%Y %H:%M')

    # --- Passport block (rows 1-12) ---
    passport = [
        ["ПАСПОРТ ОТЧЁТА", "", "", ""],
        ["Дата формирования", _generated_at, "", ""],
        [
            "Период анализа",
            f"{_period_from} — {_period_to} ({period_days} дн.)",
            "", "",
        ],
        ["Источник заказов", "WB supplier/orders API (v1)", "", ""],
        ["Источник логистики", "WB reportDetailByPeriod API (v5)", "", ""],
        ["Точность", "Расхождение с WB ≤ 3 п.п. (orders vs deliveries)", "", ""],
        ["Артикулов проанализировано", economics.get("matched_articles", "—"), "", ""],
        ["Артикулов пропущено", economics.get("skipped_articles", "—"), "", "(нет данных о цене)"],
        ["Текущий ИЛ", economics.get("current_il", "—"), "", ""],
        ["", "", "", ""],
    ]
    write_range(ws, 1, 1, passport)

    # --- Block A: Current situation (rows 11-22) ---
    block_a_start = 11
    block_a = [
        ["ЭКОНОМИЧЕСКИЙ АНАЛИЗ ЛОГИСТИКИ", "", "", ""],
        ["", "", "", ""],
        ["Метрика", "Значение", "₽/мес", "Комментарий"],
        [
            "Логистика (факт за период)",
            economics["total_logistics_fact"],
            current["logistics_monthly"],
            f"За {economics['period_days']} дн.",
        ],
        [
            "Логистика (базовая, ИЛ=1.0)",
            economics["total_logistics_base"],
            round(economics["total_logistics_base"] * 30 / economics["period_days"]),
            "Если бы КТР=1.0",
        ],
        [
            "Экономия от ИЛ < 1.0",
            "",
            economics["il_savings_rub"],
            "Благодаря высокой локализации" if economics["il_savings_rub"] > 0 else "ИЛ ≥ 1.0, нет экономии",
        ],
        [
            "ИРП-нагрузка (текущая)",
            "",
            current["irp_monthly"],
            "Штраф за артикулы < 60% лок.",
        ],
        [
            "ИТОГО затраты (логистика + ИРП)",
            "",
            current["total_monthly"],
            "",
        ],
        ["", "", "", ""],
        [
            "Текущий ИЛ",
            economics["current_il"],
            "",
            "",
        ],
        [
            "Артикулов в расчёте",
            economics["matched_articles"],
            "",
            f"(пропущено: {economics['skipped_articles']})",
        ],
        ["", "", "", ""],
    ]
    write_range(ws, block_a_start, 1, block_a)

    # --- Block B: Scenarios comparison (rows 23-32) ---
    block_b_start = block_a_start + len(block_a)
    block_b = [
        ["СРАВНЕНИЕ СЦЕНАРИЕВ", "", "", "", "", ""],
        [
            "Сценарий", "ИЛ", "Логистика ₽/мес", "ИРП ₽/мес",
            "Итого ₽/мес", "Δ vs Сейчас ₽/мес",
        ],
    ]
    for key in ("no_control", "current", "optimized"):
        s = sc[key]
        block_b.append([
            s["label"],
            s["simulated_il"],
            s["logistics_monthly"],
            s["irp_monthly"],
            s["total_monthly"],
            s["vs_current_monthly"],
        ])
    block_b.append(["", "", "", "", "", ""])
    block_b.append([
        f"Разница «{no_ctrl['label']}» vs «{optimized['label']}»",
        "",
        no_ctrl["logistics_monthly"] - optimized["logistics_monthly"],
        no_ctrl["irp_monthly"] - optimized["irp_monthly"],
        no_ctrl["total_monthly"] - optimized["total_monthly"],
        "",
    ])
    write_range(ws, block_b_start, 1, block_b)

    # --- Block C: Top-10 articles for optimization ---
    top = economics.get("top_savings", [])
    block_c_start = block_b_start + len(block_b)
    block_c = [
        ["", "", "", "", "", "", ""],
        ["ТОП-10 АРТИКУЛОВ ДЛЯ ОПТИМИЗАЦИИ", "", "", "", "", "", ""],
        [
            "Артикул", "Лок.%", "КТР", "КРП%",
            "Логистика ₽/мес", "ИРП ₽/мес", "Экономия при 80% ₽/мес",
        ],
    ]
    for item in top:
        block_c.append([
            item["article"],
            item["current_loc_pct"],
            item["current_ktr"],
            item["current_krp_pct"],
            item["logistics_fact_monthly"],
            item["irp_current_monthly"],
            item["savings_if_80_monthly"],
        ])
    write_range(ws, block_c_start, 1, block_c)

    # --- Formatting ---
    _apply_economics_formatting(spreadsheet, ws, len(top))
    logger.info("Записан лист '%s': %d сценариев, %d топ-артикулов", sheet_name, 3, len(top))


def _apply_economics_formatting(spreadsheet, ws, num_top: int) -> None:
    """Apply visual formatting to economics sheet.

    Layout (1-indexed rows):
      1      — passport title
      2-9    — passport data rows
      10     — empty
      11     — block A title (ЭКОНОМИЧЕСКИЙ АНАЛИЗ ЛОГИСТИКИ)
      12     — empty
      13     — block A header (Метрика / Значение / ₽/мес / Комментарий)
      14-22  — block A data rows
      23     — block B title (СРАВНЕНИЕ СЦЕНАРИЕВ)
      24     — block B headers
      25-27  — scenario rows (no_control, current, optimized)
      28-29  — empty + diff row
      30     — empty  ← block C begins
      31     — block C title
      32     — block C headers
      33+    — top-10 data rows
    All 0-indexed = row - 1.
    """
    # Row offsets (0-indexed)
    PASSPORT_TITLE = 0       # row 1
    BLOCK_A_TITLE  = 10      # row 11
    BLOCK_A_HEADER = 12      # row 13
    BLOCK_A_SAVINGS = 15     # row 16 (Экономия)
    BLOCK_A_IRP    = 16      # row 17 (ИРП)
    BLOCK_A_TOTAL  = 17      # row 18 (ИТОГО)
    BLOCK_A_END    = 22      # exclusive end for num fmt
    BLOCK_B_TITLE  = 22      # row 23
    BLOCK_B_HEADER = 23      # row 24
    BLOCK_B_NO_CTRL = 24     # row 25
    BLOCK_B_CURRENT = 25     # row 26
    BLOCK_B_OPT    = 26      # row 27
    BLOCK_B_END    = 30      # exclusive
    # Block C depends on dynamic block sizes; use approximate +10 offset
    BLOCK_C_TITLE  = 31      # row 32 (approx)
    BLOCK_C_HEADER = 32      # row 33
    BLOCK_C_DATA   = 33      # row 34

    sid = ws.id
    reqs: list[dict] = []

    _clear_banding(spreadsheet, sid)

    # Column widths
    reqs.extend(_col_widths(sid, [
        (0, 280), (1, 140), (2, 140), (3, 180),
        (4, 140), (5, 160), (6, 180),
    ]))

    # --- Passport block ---
    # Row 1: passport title — dark blue
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": PASSPORT_TITLE,
                       "endRowIndex": PASSPORT_TITLE + 1,
                       "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    })
    reqs.append(_row_height(sid, PASSPORT_TITLE, PASSPORT_TITLE + 1, 30))
    # Rows 2-9: passport data — light grey
    for r in range(1, 10):
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                           "startColumnIndex": 0, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"backgroundColor": _META_BG,
                                               "textFormat": {"fontSize": 10}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # --- Block A ---
    # Row 11: block A title — dark blue
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_A_TITLE,
                       "endRowIndex": BLOCK_A_TITLE + 1,
                       "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 13, "foregroundColor": _HEADER_FG},
                    "horizontalAlignment": "LEFT",
                    "verticalAlignment": "MIDDLE",
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    })
    reqs.append(_row_height(sid, BLOCK_A_TITLE, BLOCK_A_TITLE + 1, 36))

    # Row 13: header for Block A
    reqs.append(_header_fmt(sid, BLOCK_A_HEADER, 4))

    # Row 16: green bg for IL savings
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_A_SAVINGS,
                       "endRowIndex": BLOCK_A_SAVINGS + 1,
                       "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": _GREEN_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Row 17: red bg for IRP load
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_A_IRP,
                       "endRowIndex": BLOCK_A_IRP + 1,
                       "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": _RED_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Row 18: bold total
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_A_TOTAL,
                       "endRowIndex": BLOCK_A_TOTAL + 1,
                       "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": _META_BG}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    })

    # Number format for currency columns in Block A
    reqs.append(_num_fmt(sid, BLOCK_A_HEADER, BLOCK_A_END, 1, 3, "#,##0"))

    # --- Block B ---
    # Row 23: scenarios title
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_B_TITLE,
                       "endRowIndex": BLOCK_B_TITLE + 1,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": _HEADER_FG},
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })

    # Row 24: scenario headers
    reqs.append(_header_fmt(sid, BLOCK_B_HEADER, 6))

    # Row 25: no_control — red bg
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_B_NO_CTRL,
                       "endRowIndex": BLOCK_B_NO_CTRL + 1,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"backgroundColor": _RED_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Row 26: current — yellow bg
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_B_CURRENT,
                       "endRowIndex": BLOCK_B_CURRENT + 1,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"backgroundColor": _YELLOW_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Row 27: optimized — green bg
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_B_OPT,
                       "endRowIndex": BLOCK_B_OPT + 1,
                       "startColumnIndex": 0, "endColumnIndex": 6},
            "cell": {"userEnteredFormat": {"backgroundColor": _GREEN_BG}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

    # Number format for scenario table
    reqs.append(_num_fmt(sid, BLOCK_B_NO_CTRL, BLOCK_B_END, 2, 6, "#,##0"))

    # Borders for scenario table
    reqs.append(_borders(sid, BLOCK_B_HEADER, BLOCK_B_END, 0, 6))

    # --- Block C ---
    # Top-10 title
    reqs.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": BLOCK_C_TITLE,
                       "endRowIndex": BLOCK_C_TITLE + 1,
                       "startColumnIndex": 0, "endColumnIndex": 7},
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": _HEADER_BG,
                    "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": _HEADER_FG},
                }
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    })

    # Top-10 headers
    reqs.append(_header_fmt(sid, BLOCK_C_HEADER, 7))

    # Top-10 data rows
    if num_top > 0:
        data_end = BLOCK_C_DATA + num_top
        reqs.append(_borders(sid, BLOCK_C_HEADER, data_end, 0, 7))
        reqs.append(_banding(sid, BLOCK_C_DATA, data_end, 7))
        reqs.append(_num_fmt(sid, BLOCK_C_DATA, data_end, 1, 2, "0.0"))  # Лок.%
        reqs.append(_num_fmt(sid, BLOCK_C_DATA, data_end, 4, 7, "#,##0"))  # ₽ columns

    # Freeze top portion including passport
    reqs.append(_freeze(sid, rows=1, cols=1))

    if reqs:
        spreadsheet.batch_update({"requests": reqs})


# ============================================================================
# История (append-only trend)
# ============================================================================

_HISTORY_TITLE = "ИСТОРИЯ РАСЧЁТОВ ЛОКАЛИЗАЦИИ"
_HISTORY_HEADERS = [
    "Дата", "Кабинет", "Индекс", "Всего SKU", "С заказами",
    "Перемещений", "Шт. перемещений", "Допоставок", "Шт. допоставок",
    "Δ индекса",
]


def append_history(spreadsheet, result: dict, date_str: str, time_str: str):
    """Лист «История» — дописывание строки (тренд).

    Структура:
      Row 1: заголовок «ИСТОРИЯ РАСЧЁТОВ ЛОКАЛИЗАЦИИ»
      Row 2: пустая
      Row 3: заголовки колонок
      Row 4+: данные
    """
    ws = get_or_create_worksheet(spreadsheet, "История")

    summary = result.get("summary", {})
    comparison = result.get("comparison")
    delta = comparison.get("index_change", "") if comparison else ""

    row = [
        date_str,
        result.get("cabinet", ""),
        to_number(summary.get("overall_index", 0)),
        to_number(summary.get("total_sku", 0)),
        to_number(summary.get("sku_with_orders", 0)),
        to_number(summary.get("movements_count", 0)),
        to_number(summary.get("movements_qty", 0)),
        to_number(summary.get("supplies_count", 0)),
        to_number(summary.get("supplies_qty", 0)),
        to_number(delta) if delta != "" else "",
    ]

    all_values = ws.get_all_values()

    # Если лист пустой или структура сбита — пересоздаём шапку
    if len(all_values) < 3 or all_values[0][0] != _HISTORY_TITLE:
        ws.clear()
        ws.update(range_name="A1", values=[[_HISTORY_TITLE]])
        ws.update(range_name="A3", values=[_HISTORY_HEADERS])
        next_row = 4
    else:
        next_row = len(all_values) + 1

    ws.update(range_name=f"A{next_row}", values=[row])
    logger.info("История: добавлена строка %d для %s", next_row, result.get("cabinet"))
