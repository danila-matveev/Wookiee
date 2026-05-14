"""Entry point: fetch → calculate → generate Excel."""
from __future__ import annotations
import logging
import os
from datetime import timedelta
from pathlib import Path
from services.logistics_audit.models.audit_config import AuditConfig
from services.logistics_audit.api.wb_reports import fetch_report
from services.logistics_audit.api.wb_tariffs import fetch_tariffs_box, fetch_tariffs_pallet
from services.logistics_audit.api.wb_content import fetch_all_cards
from services.logistics_audit.api.wb_warehouse_remains import fetch_warehouse_remains
from services.logistics_audit.api.wb_penalties import (
    fetch_measurement_penalties, fetch_deductions,
)
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs
from services.logistics_audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    load_supabase_tariffs,
)
from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
)
from services.logistics_audit.calculators.weekly_il_calculator import (
    calculate_weekly_il,
    get_il_for_date,
)
from services.logistics_audit.output.excel_generator import generate_workbook

logger = logging.getLogger(__name__)


def run_audit(config: AuditConfig, output_dir: str = ".") -> str:
    """
    Run full logistics audit pipeline.
    Returns path to generated Excel file.
    """
    # Tool logging
    try:
        from shared.tool_logger import ToolLogger
        _tl = ToolLogger("logistics-audit")
        _run_id = _tl.start(
            trigger=os.getenv("RUN_TRIGGER", "manual"), user=os.getenv("USER_EMAIL", "unknown"),
            period_start=config.date_from.isoformat(),
            period_end=config.date_to.isoformat(),
        )
    except Exception:
        _tl, _run_id = None, None
    df = config.date_from.isoformat()
    dt = config.date_to.isoformat()
    logger.info(f"Starting audit: {df} → {dt}, KTR={config.ktr}")

    # === Step 1: Fetch data ===
    logger.info("Fetching reportDetailByPeriod...")
    all_rows = fetch_report(config.api_key, df, dt)
    logger.info(f"Total rows: {len(all_rows)}")

    logger.info("Fetching tariffs...")
    tariffs_box = fetch_tariffs_box(config.api_key, dt)
    tariffs_pallet = fetch_tariffs_pallet(config.api_key, dt)

    logger.info("Fetching card dimensions...")
    card_dims = fetch_all_cards(config.api_key)

    logger.info("Fetching warehouse remains...")
    wb_volumes = fetch_warehouse_remains(config.api_key)

    logger.info("Fetching penalties...")
    dt_rfc3339 = f"{dt}T23:59:59Z"
    penalties = fetch_measurement_penalties(config.api_key, dt_rfc3339)
    deductions = fetch_deductions(config.api_key, dt_rfc3339)
    logger.info(f"Penalties: {len(penalties)}, Deductions: {len(deductions)}")

    # === Step 2: Filter logistics rows ===
    logistics_rows = [r for r in all_rows if r.is_logistics]
    logger.info(f"Logistics rows: {len(logistics_rows)}")

    # === Step 2b: Fetch orders & calculate weekly IL ===
    from shared.clients.wb_client import WBClient
    logger.info("Fetching orders for weekly IL calculation...")
    wb_client = WBClient(api_key=config.api_key, cabinet_name="audit")
    # Fetch orders covering the full audit period (with buffer for week alignment)
    orders_from = (config.date_from - timedelta(days=7)).isoformat()
    orders = wb_client.get_supplier_orders(date_from=orders_from)
    logger.info(f"Orders fetched: {len(orders)}")

    # Load IL overrides
    from services.logistics_audit.config import load_il_overrides
    il_overrides = load_il_overrides()
    if il_overrides:
        logger.info(f"IL overrides loaded: {len(il_overrides)} weeks")

    week_to_il, il_data = calculate_weekly_il(
        orders, config.date_from, config.date_to, il_overrides=il_overrides,
    )
    il_values = sorted(week_to_il.items())
    for mon, il in il_values:
        logger.info(f"  Week {mon}: IL={il:.2f}")

    # === Step 2c: Per-SKU localization & prices (for new formula, orders from 23.03.2026+) ===
    from services.logistics_audit.calculators.logistics_overpayment import FORMULA_CHANGE_DATE
    has_new_formula_rows = any(
        r.order_dt and r.order_dt >= FORMULA_CHANGE_DATE for r in logistics_rows
    )
    sku_localization: dict[int, float] = {}
    prices: dict[int, float] = {}
    if has_new_formula_rows:
        logger.info("New formula rows detected (>=23.03.2026), fetching per-SKU localization...")
        from services.logistics_audit.calculators.localization_resolver import (
            calculate_sku_localization,
        )
        sku_localization = calculate_sku_localization(orders)
        logger.info(f"Localization data for {len(sku_localization)} SKUs")

        # Fetch prices for IRP calculation
        prices_raw = wb_client.get_prices()
        for p in prices_raw:
            nm_id = p.get("nmId", 0)
            price = p.get("price", 0) * (1 - p.get("discount", 0) / 100)
            if nm_id:
                prices[nm_id] = price
        logger.info(f"Prices for {len(prices)} SKUs")

    wb_client.close()

    # === Step 2d: Load Supabase historical tariffs for coefficient resolution ===
    logger.info("Loading Supabase historical tariffs...")
    supabase_tariffs = load_supabase_tariffs(config.date_from, config.date_to)

    # === Step 3: Calculate overpayments (per-row tariffs) ===
    results: list[OverpaymentResult | None] = []
    coefs: list[float] = []
    row_ils: list[float] = []
    for row in logistics_rows:
        vol = card_dims.get(row.nm_id, {}).get("volume", 0)

        # Resolve coefficient with 3-tier priority
        coef_result = resolve_warehouse_coef(
            dlv_prc=row.dlv_prc,
            fixed_coef=row.dlv_prc,  # WB API: dlv_prc contains fixation coef when fixation is active
            fixation_end=row.fix_tariff_date_to,
            order_date=row.order_dt,
            warehouse_name=row.office_name,
            supabase_tariffs=supabase_tariffs,
        )
        coef = coef_result.value

        coefs.append(coef)

        # Per-row tariffs based on period + sub-liter tiers
        base_1l, extra_l = get_base_tariffs(
            order_date=row.order_dt,
            fixation_start=row.fix_tariff_date_from,
            fixation_end=row.fix_tariff_date_to,
            volume=vol,
        )

        # Per-row IL from weekly calculation
        row_il = get_il_for_date(week_to_il, row.order_dt)
        if row_il is None:
            row_il = config.ktr if config.ktr > 0 else 1.0
        row_ils.append(row_il)

        result = calculate_row_overpayment(
            delivery_rub=row.delivery_rub,
            volume=vol,
            coef=coef,
            base_1l=base_1l,
            extra_l=extra_l,
            order_dt=row.order_dt,
            ktr_manual=row_il,
            is_fixed_rate=row.is_fixed_rate,
            is_forward_delivery=row.is_forward_delivery,
            sku_localization_pct=sku_localization.get(row.nm_id),
            retail_price=prices.get(row.nm_id, 0),
        )
        results.append(result)

    # Summary
    total_charged = sum(r.delivery_rub for r in logistics_rows)
    if total_charged == 0:
        logger.warning("No logistics charges found")
        total_calculated = 0
        total_overpay = 0
    else:
        total_calculated = sum(
            res.calculated_cost for res in results if res is not None
        )
        total_overpay = sum(
            res.overpayment for res in results if res is not None
        )
    logger.info(f"WB charged: {total_charged:,.2f}₽")
    logger.info(f"Calculated: {total_calculated:,.2f}₽")
    logger.info(f"Overpayment: {total_overpay:,.2f}₽ ({total_overpay/total_charged*100:.1f}%)" if total_charged else "")

    # === Step 5: Generate Excel ===
    wb = generate_workbook(
        config=config,
        all_rows=all_rows,
        logistics_rows=logistics_rows,
        overpayment_results=results,
        coefs=coefs,
        card_dims=card_dims,
        tariffs_box=tariffs_box,
        tariffs_pallet=tariffs_pallet,
        wb_volumes=wb_volumes,
        il_data=il_data,
        row_ils=row_ils,
    )

    filename = f"Аудит логистики {df} — {dt}.xlsx"
    filepath = str(Path(output_dir) / filename)
    wb.save(filepath)
    logger.info(f"Excel saved: {filepath}")

    # Finish logging
    if _tl and _run_id:
        _tl.finish(
            _run_id, status="success",
            result_url=filepath,
            items_processed=len(all_rows),
            details={"cabinet": config.cabinet, "overpayment_rows": len(results)},
        )

    return filepath


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from services.logistics_audit.config import load_config, load_il_overrides
    from services.logistics_audit.calculators.weekly_il_calculator import print_calibration_table

    # Parse args
    args = sys.argv[1:]
    calibrate_mode = "--calibrate" in args
    args = [a for a in args if a != "--calibrate"]

    cabinet = args[0] if len(args) > 0 else "OOO"
    date_from = args[1] if len(args) > 1 else None
    date_to = args[2] if len(args) > 2 else None
    ktr = float(args[3]) if len(args) > 3 else 1.0

    cfg = load_config(cabinet, date_from, date_to, ktr)

    if calibrate_mode:
        from shared.clients.wb_client import WBClient
        wb_client = WBClient(api_key=cfg.api_key, cabinet_name="audit")
        orders_from = (cfg.date_from - timedelta(days=7)).isoformat()
        orders = wb_client.get_supplier_orders(date_from=orders_from)
        wb_client.close()
        il_overrides = load_il_overrides()
        print_calibration_table(orders, cfg.date_from, cfg.date_to, il_overrides)
    else:
        output = run_audit(cfg)
        print(f"Done: {output}")
