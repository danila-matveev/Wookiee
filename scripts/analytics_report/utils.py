"""Date computation, quality flags, and helpers for analytics report."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


MONTHS_RU_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def compute_date_params(start_str: str, end_str: str | None = None) -> dict:
    """Compute all date parameters for the analytics report.

    Single date -> daily (prev = yesterday).
    Two dates -> auto depth: <=1 day daily, <=14 week, >14 month.

    Returns dict with: start_date, end_date, prev_start, prev_end, depth,
    period_label, prev_period_label, month_start, days_in_period.
    """
    start = date.fromisoformat(start_str)

    if end_str is None:
        # Daily report: single day
        end = start
    else:
        end = date.fromisoformat(end_str)

    days_in_period = (end - start).days + 1  # inclusive

    # Determine depth
    if days_in_period <= 1:
        depth = "daily"
    elif days_in_period <= 14:
        depth = "weekly"
    else:
        depth = "monthly"

    # Previous period: same-length window ending the day before start
    delta = end - start  # timedelta
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - delta

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "prev_start": prev_start.isoformat(),
        "prev_end": prev_end.isoformat(),
        "depth": depth,
        "period_label": _format_period_label(start, end),
        "prev_period_label": _format_period_label(prev_start, prev_end),
        "month_start": start.replace(day=1).isoformat(),
        "days_in_period": days_in_period,
    }


def _format_period_label(start: date, end: date) -> str:
    """Format: '30 марта -- 05 апреля 2026' or '5 апреля 2026' for single day."""
    if start == end:
        return f"{start.day} {MONTHS_RU_GENITIVE[start.month]} {start.year}"

    if start.month == end.month and start.year == end.year:
        return (
            f"{start.day:02d} -- {end.day:02d}"
            f" {MONTHS_RU_GENITIVE[end.month]} {end.year}"
        )

    return (
        f"{start.day:02d} {MONTHS_RU_GENITIVE[start.month]}"
        f" \u2014 {end.day:02d} {MONTHS_RU_GENITIVE[end.month]} {end.year}"
    )


def build_quality_flags(
    errors: dict,
    ad_totals_check: dict | None = None,
) -> dict:
    """Build quality flags. Always includes traffic_gap, buyout_lag warnings.

    Args:
        errors: {collector_name: error_message} for any collectors that failed.
        ad_totals_check: optional dict with ad spend cross-check results.
    """
    flags: dict = {
        "traffic_powerbi_gap_20pct": True,
        "buyout_lag_3_21_days": True,
        "collector_errors": {k: v for k, v in errors.items()} if errors else {},
    }
    if ad_totals_check:
        flags["ad_totals_check"] = ad_totals_check
    return flags


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
