"""Date computation, quality flags, and helpers for monthly plan collector."""
from __future__ import annotations
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional


def compute_date_params(plan_month: str) -> dict:
    """Compute all date parameters from target plan month (YYYY-MM).

    plan_month is the month we're PLANNING FOR.
    Base month (current) = plan_month - 1 (data we analyze).
    Prev month = plan_month - 2 (for m/m comparison).
    """
    year, month = map(int, plan_month.split("-"))

    # Base month = plan_month - 1
    if month == 1:
        base_year, base_month = year - 1, 12
    else:
        base_year, base_month = year, month - 1

    # Prev month = plan_month - 2
    if base_month == 1:
        prev_year, prev_month = base_year - 1, 12
    else:
        prev_year, prev_month = base_year, base_month - 1

    # Elasticity start = 3 months before base month end
    elast_month = base_month
    elast_year = base_year
    for _ in range(3):
        if elast_month == 1:
            elast_month = 12
            elast_year -= 1
        else:
            elast_month -= 1

    # Stock window = last week of base month
    # Go back 5 days from last day; if that lands on a weekday, step back one more day
    last_day = monthrange(base_year, base_month)[1]
    stock_start = date(base_year, base_month, last_day) - timedelta(days=5)
    if stock_start.weekday() < 5:  # Mon=0 .. Fri=4 → step back to weekend
        stock_start -= timedelta(days=1)

    return {
        "plan_month": plan_month,
        "current_month_start": f"{base_year}-{base_month:02d}-01",
        "current_month_end": f"{year}-{month:02d}-01",
        "prev_month_start": f"{prev_year}-{prev_month:02d}-01",
        "elasticity_start": f"{elast_year}-{elast_month:02d}-01",
        "stock_window_start": stock_start.isoformat(),
    }


def build_quality_flags(models_data: dict) -> dict:
    """Build quality flags dict for JSON output.

    Args:
        models_data: {model_name: {"data_months": int}} for elasticity data availability
    """
    low_data = [
        model for model, info in models_data.items()
        if info.get("data_months", 0) < 3
    ]
    return {
        "fan_out_bug": True,
        "db_vs_sheets_external_ads_gap": True,
        "ozon_no_external_ads": True,
        "traffic_powerbi_gap_20pct": True,
        "models_with_low_data": sorted(low_data),
    }


def tuples_to_dicts(rows: list, columns: list) -> list:
    """Convert list of tuples (from cursor.fetchall) to list of dicts."""
    return [dict(zip(columns, row)) for row in rows]


def safe_float(val) -> Optional[float]:
    """Convert value to float, returning None for non-numeric."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def model_from_article(article: str) -> str:
    """Extract model name from article: 'wendy/black' -> 'wendy'."""
    return article.split("/")[0].lower() if article else ""
