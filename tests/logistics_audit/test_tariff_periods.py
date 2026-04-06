"""Tests for period-based tariff lookup + sub-liter tiers."""
from datetime import date
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs


class TestStandardPeriods:
    """Tariff lookup by order_date when no fixation is active."""

    def test_period_aug_2024(self):
        assert get_base_tariffs(date(2024, 10, 1), None, None, 2.0) == (33.0, 8.0)

    def test_period_dec_2024(self):
        assert get_base_tariffs(date(2025, 1, 15), None, None, 2.0) == (35.0, 8.5)

    def test_period_mar_2025(self):
        assert get_base_tariffs(date(2025, 5, 1), None, None, 2.0) == (38.0, 9.5)

    def test_period_current(self):
        assert get_base_tariffs(date(2026, 1, 15), None, None, 2.0) == (46.0, 14.0)

    def test_before_earliest_period(self):
        assert get_base_tariffs(date(2024, 1, 1), None, None, 2.0) == (33.0, 8.0)

    def test_none_order_date_uses_latest(self):
        assert get_base_tariffs(None, None, None, 2.0) == (46.0, 14.0)


class TestSubLiterTiers:
    """Sub-liter pricing for volume < 1L, order_date >= 22.09.2025."""

    def test_tier_0_200(self):
        assert get_base_tariffs(date(2026, 1, 1), None, None, 0.15) == (23.0, 0.0)

    def test_tier_0_400(self):
        assert get_base_tariffs(date(2026, 1, 1), None, None, 0.3) == (26.0, 0.0)

    def test_tier_0_600(self):
        assert get_base_tariffs(date(2026, 1, 1), None, None, 0.5) == (29.0, 0.0)

    def test_tier_0_800(self):
        assert get_base_tariffs(date(2026, 1, 1), None, None, 0.7) == (30.0, 0.0)

    def test_tier_1_000(self):
        assert get_base_tariffs(date(2026, 1, 1), None, None, 0.98) == (32.0, 0.0)

    def test_no_subliter_before_sep_2025(self):
        """Before 22.09.2025, sub-liter tiers don't apply."""
        assert get_base_tariffs(date(2025, 5, 1), None, None, 0.5) == (38.0, 9.5)

    def test_no_subliter_for_1L_exactly(self):
        """volume == 1.0 uses standard rate (not sub-liter)."""
        assert get_base_tariffs(date(2026, 1, 1), None, None, 1.0) == (46.0, 14.0)

    def test_extra_liter_always_zero_for_subliter(self):
        for vol in [0.1, 0.25, 0.45, 0.65, 0.85]:
            _, extra = get_base_tariffs(date(2026, 1, 1), None, None, vol)
            assert extra == 0.0, f"extra_l should be 0 for volume={vol}"


class TestFixationAware:
    """When fixation is active, use fixation_start for period lookup."""

    def test_fixation_active_uses_fixation_start(self):
        """Fixation started in Dec 2024 period, still active → use Dec 2024 rates."""
        result = get_base_tariffs(
            order_date=date(2026, 1, 15),
            fixation_start=date(2024, 12, 15),
            fixation_end=date(2026, 6, 1),
            volume=2.0,
        )
        assert result == (35.0, 8.5)

    def test_fixation_expired_uses_order_date(self):
        """Fixation expired → use order_date."""
        result = get_base_tariffs(
            order_date=date(2026, 1, 15),
            fixation_start=date(2024, 12, 15),
            fixation_end=date(2025, 6, 1),
            volume=2.0,
        )
        assert result == (46.0, 14.0)

    def test_subliter_uses_order_date_not_fixation(self):
        """Sub-liter check uses order_date, not fixation_start."""
        result = get_base_tariffs(
            order_date=date(2026, 1, 15),
            fixation_start=date(2025, 1, 1),
            fixation_end=date(2026, 6, 1),
            volume=0.5,
        )
        assert result == (29.0, 0.0)
