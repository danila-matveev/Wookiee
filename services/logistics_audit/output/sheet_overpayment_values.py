"""Sheet 2: 'Переплата по логистике' — pre-calculated values, no formulas."""
from __future__ import annotations
from openpyxl.worksheet.worksheet import Worksheet
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult

HEADERS = [
    "№ отчёта", "Номер поставки", "Код номенклатуры", "Дата заказа",
    "Услуги по доставке", "Склад", "ШК", "Srid", "Фикс. коэф.",
    "Коэф. для расчёта", "Объём", "КТР", "Расчётная стоимость",
    "Разница (переплата)", "Включено в итог",
]


def write_overpayment_values(
    ws: Worksheet,
    rows: list[ReportRow],
    results: list[OverpaymentResult | None],
    volumes: dict[int, float],
    coefs: list[float],
    row_ils: list[float] | None = None,
) -> None:
    """Write Sheet 2 with pre-calculated overpayment values."""
    for col, h in enumerate(HEADERS, 1):
        ws.cell(1, col, h)

    total_overpayment = 0.0
    for i, (row, res, coef) in enumerate(zip(rows, results, coefs), 2):
        if res is None:
            continue
        idx = i - 2
        included = res.overpayment >= 0
        ws.cell(i, 1, row.realizationreport_id)
        ws.cell(i, 2, row.gi_id)
        ws.cell(i, 3, row.nm_id)
        ws.cell(i, 4, str(row.order_dt) if row.order_dt else "")
        ws.cell(i, 5, row.delivery_rub)
        ws.cell(i, 6, row.office_name)
        ws.cell(i, 7, row.shk_id)
        ws.cell(i, 8, row.srid)
        ws.cell(i, 9, row.dlv_prc)
        ws.cell(i, 10, coef)
        ws.cell(i, 11, volumes.get(row.nm_id, 0))
        if row_ils is not None and idx < len(row_ils):
            ws.cell(i, 12, row_ils[idx])
        else:
            ws.cell(i, 12, res.calculated_cost)
        ws.cell(i, 13, res.calculated_cost)
        ws.cell(i, 14, res.overpayment)
        ws.cell(i, 15, "Да" if included else "Нет")
        if included:
            total_overpayment += res.overpayment

    # Summary row at top
    ws.insert_rows(1)
    ws.cell(1, 1, "ИТОГО переплата:")
    ws.cell(1, 14, round(total_overpayment, 2))
    ws.cell(1, 15, "(только положительные)")
