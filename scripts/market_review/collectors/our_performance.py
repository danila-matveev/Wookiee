"""Collector: our WB + OZON financial performance from internal DB."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer.finance import get_wb_finance, get_ozon_finance

logger = logging.getLogger(__name__)


def _calc_delta_pct(current: dict, previous: dict) -> dict:
    """Compute (cur - prev) / prev * 100 for each shared numeric key."""
    result = {}
    for key in current:
        cur = current.get(key, 0) or 0
        prev = previous.get(key, 0) or 0
        if prev:
            result[key] = round((cur - prev) / prev * 100, 2)
        else:
            result[key] = None
    return result


def _to_float(val) -> float:
    """Safely convert DB value to float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _parse_wb_row(row) -> dict:
    """Parse a WB finance row (19 columns after period)."""
    # row[0] = period label, row[1:] = values
    return {
        "orders_count": _to_float(row[1]),
        "sales_count": _to_float(row[2]),
        "revenue_before_spp": _to_float(row[3]),
        "revenue_after_spp": _to_float(row[4]),
        "adv_internal": _to_float(row[5]),
        "adv_external": _to_float(row[6]),
        "cost_of_goods": _to_float(row[7]),
        "logistics": _to_float(row[8]),
        "storage": _to_float(row[9]),
        "commission": _to_float(row[10]),
        "spp_amount": _to_float(row[11]),
        "nds": _to_float(row[12]),
        "penalty": _to_float(row[13]),
        "retention": _to_float(row[14]),
        "deduction": _to_float(row[15]),
        "margin": _to_float(row[16]),
        "returns_revenue": _to_float(row[17]),
        "revenue_before_spp_gross": _to_float(row[18]),
    }


def _parse_ozon_row(row) -> dict:
    """Parse an OZON finance row (13 columns after period)."""
    return {
        "sales_count": _to_float(row[1]),
        "revenue_before_spp": _to_float(row[2]),
        "revenue_after_spp": _to_float(row[3]),
        "adv_internal": _to_float(row[4]),
        "adv_external": _to_float(row[5]),
        "margin": _to_float(row[6]),
        "cost_of_goods": _to_float(row[7]),
        "logistics": _to_float(row[8]),
        "storage": _to_float(row[9]),
        "commission": _to_float(row[10]),
        "spp_amount": _to_float(row[11]),
        "nds": _to_float(row[12]),
    }


def _combine_channels(wb: dict, ozon: dict) -> dict:
    """Combine WB and OZON data into unified metrics."""
    wb_rev = wb.get("revenue_before_spp", 0)
    ozon_rev = ozon.get("revenue_before_spp", 0)
    total_rev = wb_rev + ozon_rev

    wb_sales = wb.get("sales_count", 0)
    ozon_sales = ozon.get("sales_count", 0)
    total_sales = wb_sales + ozon_sales

    return {
        "revenue": total_rev,
        "sales_count": total_sales,
        "avg_check": round(total_rev / total_sales, 2) if total_sales else 0,
        "margin": wb.get("margin", 0) + ozon.get("margin", 0),
        "wb_revenue": wb_rev,
        "ozon_revenue": ozon_rev,
    }


def _extract_by_period(rows, parser) -> tuple[dict, dict]:
    """Extract current and previous period data from DB result rows."""
    current = {}
    previous = {}
    for row in rows:
        period_label = row[0]
        parsed = parser(row)
        if period_label == "current":
            current = parsed
        elif period_label == "previous":
            previous = parsed
    return current, previous


def collect_our_performance(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect our WB + OZON financial performance.

    Args:
        period_start: Current period start (YYYY-MM-DD).
        period_end: Current period end (YYYY-MM-DD).
        prev_start: Previous period start (YYYY-MM-DD).
        prev_end: Previous period end (YYYY-MM-DD).

    Returns:
        {"our": {"current": {...}, "previous": {...}, "delta_pct": {...}}}
    """
    logger.info("Fetching WB finance data...")
    wb_results, _ = get_wb_finance(period_start, prev_start, period_end)
    wb_current, wb_previous = _extract_by_period(wb_results or [], _parse_wb_row)

    logger.info("Fetching OZON finance data...")
    ozon_results, _ = get_ozon_finance(period_start, prev_start, period_end)
    ozon_current, ozon_previous = _extract_by_period(ozon_results or [], _parse_ozon_row)

    current_combined = _combine_channels(wb_current, ozon_current)
    previous_combined = _combine_channels(wb_previous, ozon_previous)
    delta = _calc_delta_pct(current_combined, previous_combined)

    return {
        "our": {
            "current": current_combined,
            "previous": previous_combined,
            "delta_pct": delta,
        }
    }
