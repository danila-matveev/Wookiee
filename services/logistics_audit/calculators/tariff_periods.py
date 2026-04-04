"""Period-based base tariffs and sub-liter pricing tiers for WB logistics."""
from __future__ import annotations
from datetime import date


# Standard tariffs by period: (start_date, first_liter, extra_liter)
# Sorted newest-first for lookup efficiency
TARIFF_PERIODS: list[tuple[date, float, float]] = [
    (date(2025, 9, 22), 46.0, 14.0),
    (date(2025, 2, 28), 38.0, 9.5),
    (date(2024, 12, 11), 35.0, 8.5),
    (date(2024, 8, 14), 33.0, 8.0),
]

# Sub-liter tiers (only for order_date >= 22.09.2025 AND volume < 1L)
# (max_volume, first_liter, extra_liter)
SUB_LITER_TIERS: list[tuple[float, float, float]] = [
    (0.200, 23.0, 0.0),
    (0.400, 26.0, 0.0),
    (0.600, 29.0, 0.0),
    (0.800, 30.0, 0.0),
    (1.000, 32.0, 0.0),
]

SUB_LITER_START = date(2025, 9, 22)


def get_base_tariffs(
    order_date: date | None,
    fixation_start: date | None,
    fixation_end: date | None,
    volume: float,
) -> tuple[float, float]:
    """Determine (first_liter, extra_liter) tariffs for a row.

    Tariff period selection:
    - If fixation is active (fixation_end > order_date): use fixation_start
    - Otherwise: use order_date

    Sub-liter tiers apply when order_date >= 22.09.2025 AND volume < 1L.
    """
    if order_date is None:
        # Fallback to latest period
        return TARIFF_PERIODS[0][1], TARIFF_PERIODS[0][2]

    # Determine reference date for period selection
    if (
        fixation_start
        and fixation_end
        and fixation_end > order_date
    ):
        ref_date = fixation_start
    else:
        ref_date = order_date

    # Sub-liter check (uses order_date, not ref_date)
    if order_date >= SUB_LITER_START and 0 < volume < 1.0:
        for max_vol, first_l, extra_l in SUB_LITER_TIERS:
            if volume <= max_vol:
                return first_l, extra_l
        # volume between 0.8 and 1.0 → last tier
        return SUB_LITER_TIERS[-1][1], SUB_LITER_TIERS[-1][2]

    # Standard period lookup
    for period_start, first_l, extra_l in TARIFF_PERIODS:
        if ref_date >= period_start:
            return first_l, extra_l

    # Before earliest known period — use earliest rates
    return TARIFF_PERIODS[-1][1], TARIFF_PERIODS[-1][2]
