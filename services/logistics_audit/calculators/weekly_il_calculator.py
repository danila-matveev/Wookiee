"""Calculate weekly Localization Index (ИЛ) from WB orders.

For each week in the audit period, determines the seller's overall
localization % and maps it to the IL coefficient via get_ktr_krp().
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from services.wb_localization.wb_localization_mappings import (
    get_warehouse_fd,
    get_delivery_fd,
)
from services.wb_localization.irp_coefficients import get_ktr_krp


def _monday(d: date) -> date:
    """Return the Monday of the week containing *d*."""
    return d - timedelta(days=d.weekday())


def calculate_weekly_il(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> tuple[dict[date, float], list[dict]]:
    """Calculate per-week IL for the audit period.

    Args:
        orders: Raw WB orders (from supplier/orders API).
        date_from: Audit start date.
        date_to: Audit end date.
        il_overrides: Manual IL values by week start date (Monday).
            e.g. {"2026-01-06": 1.09, "2026-01-13": 1.09}

    Returns:
        (week_to_il, il_data)
        - week_to_il: {monday_date: IL_value} — for per-row lookup
        - il_data: list of dicts for the ИЛ Excel sheet
    """
    # --- 1. Classify orders by week ---
    week_local: dict[date, int] = defaultdict(int)
    week_total: dict[date, int] = defaultdict(int)

    for o in orders:
        order_date_str = o.get("date", "")[:10]
        if not order_date_str:
            continue

        try:
            order_date = date.fromisoformat(order_date_str)
        except ValueError:
            continue

        wh_name = o.get("warehouseName", "")
        delivery_region = (
            o.get("oblastOkrugName", "")
            or o.get("oblast", "")
            or o.get("countryName", "")
        )

        wh_fd = get_warehouse_fd(wh_name)
        delivery_fd = get_delivery_fd(delivery_region)

        if not wh_fd or not delivery_fd:
            continue

        mon = _monday(order_date)
        week_total[mon] += 1
        if wh_fd == delivery_fd:
            week_local[mon] += 1

    # --- 2. Build week_to_il mapping ---
    week_to_il: dict[date, float] = {}

    # Ensure every week in the audit range is covered
    mon = _monday(date_from)
    end_mon = _monday(date_to)
    all_mondays: list[date] = []
    while mon <= end_mon:
        all_mondays.append(mon)
        mon += timedelta(days=7)

    for mon in all_mondays:
        total = week_total.get(mon, 0)
        local = week_local.get(mon, 0)
        if total > 0:
            loc_pct = local / total * 100
        else:
            loc_pct = 0.0
        il, _ = get_ktr_krp(loc_pct)
        week_to_il[mon] = il

    # --- 2b. Apply manual overrides ---
    if il_overrides:
        for date_str, override_il in il_overrides.items():
            try:
                override_date = date.fromisoformat(date_str)
                mon = _monday(override_date)
                if mon in week_to_il:
                    week_to_il[mon] = override_il
            except ValueError:
                pass

    # --- 3. Build il_data for Excel sheet ---
    override_mondays: set[date] = set()
    if il_overrides:
        for date_str in il_overrides:
            try:
                override_mondays.add(_monday(date.fromisoformat(date_str)))
            except ValueError:
                pass

    il_data: list[dict] = []
    for mon in sorted(all_mondays, reverse=True):
        sun = mon + timedelta(days=6)
        il_data.append({
            "date": mon.isoformat(),
            "il": week_to_il[mon],
            "date_from": mon.isoformat(),
            "date_to": sun.isoformat(),
            "source": "override" if mon in override_mondays else "calculated",
        })

    return week_to_il, il_data


def get_il_for_date(week_to_il: dict[date, float], order_dt: date | None) -> float | None:
    """Look up the IL value for a specific order date.

    Returns None if no IL data available.
    """
    if order_dt is None or not week_to_il:
        return None
    mon = _monday(order_dt)
    return week_to_il.get(mon)


def print_calibration_table(
    orders: list[dict],
    date_from: date,
    date_to: date,
    il_overrides: dict[str, float] | None = None,
) -> None:
    """Print IL values for comparison with WB dashboard."""
    week_to_il, il_data = calculate_weekly_il(orders, date_from, date_to, il_overrides)

    print(f"\n{'Week':<24} {'IL':>8} {'Source':<12}")
    print("-" * 48)
    for entry in reversed(il_data):
        src = entry.get("source", "calculated")
        marker = " *" if src == "override" else ""
        print(f"{entry['date_from']} — {entry['date_to']}  {entry['il']:>8.4f} {src:<12}{marker}")
    print("\n* = manual override applied")
