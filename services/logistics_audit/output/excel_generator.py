"""Main Excel generator — creates workbook with all 11 sheets."""
from __future__ import annotations
import openpyxl
from services.logistics_audit.models.audit_config import AuditConfig
from services.logistics_audit.models.report_row import ReportRow
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot
from services.logistics_audit.calculators.logistics_overpayment import OverpaymentResult
from services.logistics_audit.output.sheet_overpayment_formulas import write_overpayment_formulas
from services.logistics_audit.output.sheet_overpayment_values import write_overpayment_values
from services.logistics_audit.output.sheet_svod import write_svod
from services.logistics_audit.output.sheet_detail import write_detail
from services.logistics_audit.output.sheet_il import write_il
from services.logistics_audit.output.sheet_pivot_by_article import write_pivot_by_article
from services.logistics_audit.output.sheet_logistics_types import write_logistics_types
from services.logistics_audit.output.sheet_weekly import write_weekly
from services.logistics_audit.output.sheet_dimensions import write_dimensions
from services.logistics_audit.output.sheet_tariffs_box import write_tariffs_box
from services.logistics_audit.output.sheet_tariffs_pallet import write_tariffs_pallet

SHEET_NAMES = [
    "Переплата по логистике (короб)",
    "Переплата по логистике",
    "СВОД",
    "Детализация",
    "ИЛ",
    "Переплата по артикулам",
    "Виды логистики",
    "Еженед. отчет",
    "Габариты в карточке",
    "Тарифы короб",
    "Тариф монопалета",
]


def generate_workbook(
    config: AuditConfig,
    all_rows: list[ReportRow],
    logistics_rows: list[ReportRow],
    overpayment_results: list[OverpaymentResult | None],
    coefs: list[float],
    card_dims: dict[int, dict],
    tariffs_box: dict[str, TariffSnapshot],
    tariffs_pallet: dict,
    wb_volumes: dict[int, float],
    il_data: list[dict] | None = None,
    row_ils: list[float] | None = None,
) -> openpyxl.Workbook:
    """Generate the full 11-sheet Excel workbook."""
    wb = openpyxl.Workbook()

    # Remove default sheet
    wb.remove(wb.active)

    # Create all sheets
    sheets = {}
    for name in SHEET_NAMES:
        sheets[name] = wb.create_sheet(name)

    # Aggregate overpayment by report
    overpay_by_report: dict[int, float] = {}
    for row, res in zip(logistics_rows, overpayment_results):
        if res is not None:
            rid = row.realizationreport_id
            overpay_by_report[rid] = overpay_by_report.get(rid, 0) + res.overpayment

    volumes = {nm: d["volume"] for nm, d in card_dims.items()}

    # Sheet 1: Formulas
    write_overpayment_formulas(
        sheets["Переплата по логистике (короб)"], logistics_rows,
        ktr=config.ktr, base_1l=46.0, extra_l=14.0,
        row_ils=row_ils,
    )

    # Sheet 2: Values
    write_overpayment_values(
        sheets["Переплата по логистике"], logistics_rows,
        overpayment_results, volumes, coefs, row_ils=row_ils,
    )

    # Sheet 3: SVOD
    write_svod(sheets["СВОД"], all_rows, overpay_by_report)

    # Sheet 4: Detail
    write_detail(sheets["Детализация"], all_rows)

    # Sheet 5: IL
    write_il(sheets["ИЛ"], il_data)

    # Sheet 6: Pivot by article
    write_pivot_by_article(sheets["Переплата по артикулам"], logistics_rows, overpayment_results)

    # Sheet 7: Logistics types
    write_logistics_types(sheets["Виды логистики"], logistics_rows)

    # Sheet 8: Weekly
    write_weekly(sheets["Еженед. отчет"], all_rows)

    # Sheet 9: Dimensions
    write_dimensions(sheets["Габариты в карточке"], card_dims)

    # Sheet 10: Tariffs box
    write_tariffs_box(sheets["Тарифы короб"], tariffs_box)

    # Sheet 11: Tariffs pallet
    write_tariffs_pallet(sheets["Тариф монопалета"], tariffs_pallet)

    return wb
