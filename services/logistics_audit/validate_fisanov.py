"""Validate logistics audit fixes against Fisanov reference data.

Reads the Fisanov Excel reference (ИП, 05.01–01.02.2026, 144,901 rub),
runs our calculator with cumulative fixes, and decomposes the discrepancy.

Usage:
    python -m services.logistics_audit.validate_fisanov
"""
from __future__ import annotations
import logging
from datetime import date, datetime
from pathlib import Path

import openpyxl

from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
)
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

FISANOV_PATH = Path(__file__).parent / "ИП Фисанов. Проверка логистики 05.01.2026 г. - 01.02.2026 г._Итоговый.xlsx"

# Fisanov IL values by week (from ИЛ sheet)
FISANOV_IL: dict[date, float] = {
    date(2025, 12, 1): 1.29,
    date(2025, 12, 8): 1.33,
    date(2025, 12, 15): 1.34,
    date(2025, 12, 22): 1.37,
    date(2025, 12, 29): 1.37,
    date(2026, 1, 5): 1.36,
    date(2026, 1, 12): 1.34,
    date(2026, 1, 19): 1.35,
    date(2026, 1, 26): 1.33,
}


def _monday(d: date) -> date:
    from datetime import timedelta
    return d - timedelta(days=d.weekday())


def _to_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def load_fisanov_rows() -> list[dict]:
    """Load rows from Fisanov 'Переплата по логистике' sheet."""
    logger.info(f"Loading {FISANOV_PATH.name}...")
    wb = openpyxl.load_workbook(str(FISANOV_PATH), read_only=True, data_only=True)
    ws = wb["Переплата по логистике"]

    # Headers from spec: row 1 is headers, row 2 is summary, data starts row 3
    # Col mapping (from output):
    # 1=Номер отчета, 2=Номер поставки, 3=Код номенклатуры, 4=Дата заказа,
    # 5=Услуги по доставке, 6=Дата начала фиксации, 7=Дата конца фиксации,
    # 8=Склад, 9=ШК, 10=Srid, 11=Фикс коэф, 12=Коэф для расчета,
    # 13=Объем, 14=КТР, 15=Стоимость 1л, 16=Стоимость доп.л,
    # 17=Стоимость логистики, 18=Разница

    rows = []
    for i, row_vals in enumerate(ws.iter_rows(values_only=True)):
        if i < 2:  # skip header + summary
            continue
        if row_vals[0] is None and row_vals[2] is None:
            continue  # skip empty rows

        try:
            rows.append({
                "report_id": row_vals[0],
                "gi_id": row_vals[1],
                "nm_id": row_vals[2],
                "order_dt": _to_date(row_vals[3]),
                "delivery_rub": float(row_vals[4] or 0),
                "fix_date_from": _to_date(row_vals[5]),
                "fix_date_to": _to_date(row_vals[6]),
                "warehouse": row_vals[7],
                "shk_id": row_vals[8],
                "srid": row_vals[9],
                "fixed_coef": float(row_vals[10] or 0),
                "calc_coef": float(row_vals[11] or 0),
                "volume": float(row_vals[12] or 0),
                "ktr_ref": float(row_vals[13] or 0),
                "base_1l_ref": float(row_vals[14] or 0),
                "extra_l_ref": float(row_vals[15] or 0),
                "calc_cost_ref": float(row_vals[16] or 0),
                "difference_ref": float(row_vals[17] or 0),
            })
        except (TypeError, ValueError, IndexError):
            continue

    wb.close()
    logger.info(f"Loaded {len(rows)} data rows")
    return rows


def run_validation():
    """Run cumulative fix validation against Fisanov reference."""
    rows = load_fisanov_rows()
    if not rows:
        logger.error("No rows loaded!")
        return

    # Reference totals
    ref_total_overpay = sum(r["difference_ref"] for r in rows)
    ref_total_charged = sum(r["delivery_rub"] for r in rows)
    ref_total_calc = sum(r["calc_cost_ref"] for r in rows)
    logger.info(f"\n{'='*60}")
    logger.info(f"Reference (Fisanov): {len(rows)} rows")
    logger.info(f"  WB charged:    {ref_total_charged:>12,.2f} rub")
    logger.info(f"  Calculated:    {ref_total_calc:>12,.2f} rub")
    logger.info(f"  Overpayment:   {ref_total_overpay:>12,.2f} rub")

    # === Baseline: old logic (hardcoded tariff=46, ktr=1.0, no forward filter, no coef fix) ===
    baseline_overpay = 0.0
    baseline_count = 0
    for r in rows:
        res = calculate_row_overpayment(
            delivery_rub=r["delivery_rub"],
            volume=r["volume"],
            coef=r["calc_coef"],
            base_1l=46.0,
            extra_l=14.0,
            order_dt=r["order_dt"],
            ktr_manual=1.0,
            is_fixed_rate=False,
            is_forward_delivery=True,  # old code didn't filter
        )
        if res:
            baseline_overpay += res.overpayment
            baseline_count += 1

    logger.info(f"\n--- Baseline (old logic: tariff=46, KTR=1.0) ---")
    logger.info(f"  Rows calculated: {baseline_count}")
    logger.info(f"  Overpayment:     {baseline_overpay:>12,.2f} rub")
    logger.info(f"  Discrepancy vs Fisanov: {baseline_overpay - ref_total_overpay:>+12,.2f} rub")

    # === Fix 1: Forward delivery filter (all Fisanov rows ARE forward, so no change expected) ===
    fix1_overpay = baseline_overpay  # All Fisanov rows are forward deliveries
    logger.info(f"\n--- + Fix 1: Forward delivery filter ---")
    logger.info(f"  Delta: {fix1_overpay - baseline_overpay:>+12,.2f} rub (all rows are forward)")

    # === Fix 2: Period-based tariffs ===
    fix2_overpay = 0.0
    fix2_count = 0
    for r in rows:
        base_1l, extra_l = get_base_tariffs(
            order_date=r["order_dt"],
            fixation_start=r["fix_date_from"],
            fixation_end=r["fix_date_to"],
            volume=r["volume"],
        )
        res = calculate_row_overpayment(
            delivery_rub=r["delivery_rub"],
            volume=r["volume"],
            coef=r["calc_coef"],
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=r["order_dt"],
            ktr_manual=1.0,
            is_fixed_rate=False,
            is_forward_delivery=True,
        )
        if res:
            fix2_overpay += res.overpayment
            fix2_count += 1

    logger.info(f"\n--- + Fix 2: Period-based tariffs ---")
    logger.info(f"  Delta: {fix2_overpay - fix1_overpay:>+12,.2f} rub")
    logger.info(f"  Overpayment: {fix2_overpay:>12,.2f} rub")

    # === Fix 3: Warehouse coefficient (use fixed_coef from Fisanov when fixation active) ===
    fix3_overpay = 0.0
    for r in rows:
        base_1l, extra_l = get_base_tariffs(
            order_date=r["order_dt"],
            fixation_start=r["fix_date_from"],
            fixation_end=r["fix_date_to"],
            volume=r["volume"],
        )
        # Apply Fix 3: use fixed_coef when fixation active
        coef = r["calc_coef"]
        if r["fixed_coef"] > 0 and r["fix_date_to"] and r["order_dt"] and r["fix_date_to"] > r["order_dt"]:
            coef = r["fixed_coef"]

        res = calculate_row_overpayment(
            delivery_rub=r["delivery_rub"],
            volume=r["volume"],
            coef=coef,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=r["order_dt"],
            ktr_manual=1.0,
            is_fixed_rate=False,
            is_forward_delivery=True,
        )
        if res:
            fix3_overpay += res.overpayment

    logger.info(f"\n--- + Fix 3: Warehouse coefficient resolution ---")
    logger.info(f"  Delta: {fix3_overpay - fix2_overpay:>+12,.2f} rub")
    logger.info(f"  Overpayment: {fix3_overpay:>12,.2f} rub")

    # === Fix 4: IL calibration (use Fisanov IL values) ===
    fix4_overpay = 0.0
    for r in rows:
        base_1l, extra_l = get_base_tariffs(
            order_date=r["order_dt"],
            fixation_start=r["fix_date_from"],
            fixation_end=r["fix_date_to"],
            volume=r["volume"],
        )
        coef = r["calc_coef"]
        if r["fixed_coef"] > 0 and r["fix_date_to"] and r["order_dt"] and r["fix_date_to"] > r["order_dt"]:
            coef = r["fixed_coef"]

        # Fix 4: use Fisanov IL values
        il = 1.0
        if r["order_dt"]:
            mon = _monday(r["order_dt"])
            il = FISANOV_IL.get(mon, r.get("ktr_ref", 1.0))

        res = calculate_row_overpayment(
            delivery_rub=r["delivery_rub"],
            volume=r["volume"],
            coef=coef,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=r["order_dt"],
            ktr_manual=il,
            is_fixed_rate=False,
            is_forward_delivery=True,
        )
        if res:
            fix4_overpay += res.overpayment

    logger.info(f"\n--- + Fix 4: IL calibration (Fisanov values) ---")
    logger.info(f"  Delta: {fix4_overpay - fix3_overpay:>+12,.2f} rub")
    logger.info(f"  Overpayment: {fix4_overpay:>12,.2f} rub")

    # === Fix 5: Exclude negative differences ===
    fix5_overpay = 0.0
    negative_total = 0.0
    negative_count = 0
    for r in rows:
        base_1l, extra_l = get_base_tariffs(
            order_date=r["order_dt"],
            fixation_start=r["fix_date_from"],
            fixation_end=r["fix_date_to"],
            volume=r["volume"],
        )
        coef = r["calc_coef"]
        if r["fixed_coef"] > 0 and r["fix_date_to"] and r["order_dt"] and r["fix_date_to"] > r["order_dt"]:
            coef = r["fixed_coef"]

        il = 1.0
        if r["order_dt"]:
            mon = _monday(r["order_dt"])
            il = FISANOV_IL.get(mon, r.get("ktr_ref", 1.0))

        res = calculate_row_overpayment(
            delivery_rub=r["delivery_rub"],
            volume=r["volume"],
            coef=coef,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=r["order_dt"],
            ktr_manual=il,
            is_fixed_rate=False,
            is_forward_delivery=True,
        )
        if res:
            if res.overpayment >= 0:
                fix5_overpay += res.overpayment
            else:
                negative_total += res.overpayment
                negative_count += 1

    logger.info(f"\n--- + Fix 5: Exclude negative differences ---")
    logger.info(f"  Negative rows excluded: {negative_count} ({negative_total:,.2f} rub)")
    logger.info(f"  Delta: {fix5_overpay - fix4_overpay:>+12,.2f} rub")
    logger.info(f"  Overpayment: {fix5_overpay:>12,.2f} rub")

    # === Summary ===
    logger.info(f"\n{'='*60}")
    logger.info(f"DISCREPANCY DECOMPOSITION REPORT")
    logger.info(f"{'='*60}")
    logger.info(f"{'Error source':<40} {'Delta (rub)':>12} {'Rows':>8}")
    logger.info(f"{'-'*60}")
    logger.info(f"{'Fix 1: Reverse logistics filter':<40} {fix1_overpay - baseline_overpay:>+12,.2f} {'0':>8}")
    logger.info(f"{'Fix 2: Wrong base tariffs':<40} {fix2_overpay - fix1_overpay:>+12,.2f} {fix2_count:>8}")
    logger.info(f"{'Fix 3: Wrong warehouse coefficient':<40} {fix3_overpay - fix2_overpay:>+12,.2f} {len(rows):>8}")
    logger.info(f"{'Fix 4: Wrong IL values':<40} {fix4_overpay - fix3_overpay:>+12,.2f} {len(rows):>8}")
    logger.info(f"{'Fix 5: Negative differences included':<40} {fix5_overpay - fix4_overpay:>+12,.2f} {negative_count:>8}")
    logger.info(f"{'-'*60}")

    total_explained = fix5_overpay - baseline_overpay
    remainder = fix5_overpay - ref_total_overpay
    logger.info(f"{'Total correction':<40} {total_explained:>+12,.2f}")
    logger.info(f"{'Our result':<40} {fix5_overpay:>12,.2f}")
    logger.info(f"{'Fisanov reference':<40} {ref_total_overpay:>12,.2f}")
    logger.info(f"{'Unexplained remainder':<40} {remainder:>+12,.2f}")
    logger.info(f"{'='*60}")

    if abs(remainder) < 1.0:
        logger.info("✓ TARGET MET: unexplained remainder ≈ 0 rub")
    else:
        logger.info(f"✗ REMAINDER: {remainder:,.2f} rub still unexplained")

    return remainder


if __name__ == "__main__":
    run_validation()
