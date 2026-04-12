"""Plan-fact data collector: plan from DB (plan_article) + MTD info."""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date

from shared.data_layer.planning import get_plan_by_period

logger = logging.getLogger(__name__)


def collect_plan_fact(start: str, end: str, month_start: str) -> dict:
    """Collect plan data from DB and compute MTD ratios.

    Args:
        start: period start (YYYY-MM-DD)
        end: period end (YYYY-MM-DD)
        month_start: first day of the month (YYYY-MM-DD)

    Returns:
        {"plan_fact": {...}} with plan data and MTD info.
    """
    # Compute MTD info
    ms = date.fromisoformat(month_start)
    end_date = date.fromisoformat(end)
    dim = monthrange(ms.year, ms.month)[1]
    days_elapsed = (end_date - ms).days + 1  # inclusive
    mtd_ratio = days_elapsed / dim if dim > 0 else 0

    # Month boundaries for plan query
    month_end_str = f"{ms.year}-{ms.month:02d}-{dim:02d}"

    # Get plan from DB
    plan_wb = []
    plan_ozon = []
    try:
        rows = get_plan_by_period(month_start, month_end_str)
        for mp, lk, artikul, pokazatel, znachenie in rows:
            entry = {
                "mp": (mp or "").strip(),
                "lk": (lk or "").strip(),
                "artikul": (artikul or "").strip(),
                "pokazatel": (pokazatel or "").strip(),
                "znachenie": (znachenie or "").replace("\xa0", "").strip(),
            }
            if "ozon" in entry["mp"].lower() or "озон" in entry["mp"].lower():
                plan_ozon.append(entry)
            else:
                plan_wb.append(entry)
        logger.info(f"Plan data: {len(plan_wb)} WB rows, {len(plan_ozon)} OZON rows")
    except Exception as e:
        logger.warning(f"Failed to get plan from DB: {e}")

    return {
        "plan_fact": {
            "plan_wb": plan_wb,
            "plan_ozon": plan_ozon,
            "mtd": {
                "days_in_month": dim,
                "days_elapsed": days_elapsed,
                "mtd_ratio": round(mtd_ratio, 4),
            },
        }
    }
