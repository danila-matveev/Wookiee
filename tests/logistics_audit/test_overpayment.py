"""Tests for overpayment calculation with Fix 1 (forward delivery filter)."""
from datetime import date
from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
)
from services.logistics_audit.models.report_row import (
    FORWARD_DELIVERY_TYPES,
    FIXED_RATE_TYPES,
)


class TestForwardDeliveryFilter:
    """Fix 1: Only forward deliveries are auditable."""

    def test_whitelist_contains_exactly_two_types(self):
        assert FORWARD_DELIVERY_TYPES == frozenset({
            "К клиенту при продаже",
            "К клиенту при отмене",
        })

    def test_non_forward_returns_none(self):
        res = calculate_row_overpayment(
            delivery_rub=50.0, volume=1.0, coef=1.5,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.0, is_fixed_rate=False,
            is_forward_delivery=False,
        )
        assert res is None

    def test_forward_returns_result(self):
        res = calculate_row_overpayment(
            delivery_rub=100.0, volume=1.0, coef=1.5,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.0, is_fixed_rate=False,
            is_forward_delivery=True,
        )
        assert res is not None
        assert isinstance(res, OverpaymentResult)

    def test_default_is_forward(self):
        """Backward compatibility: default is_forward_delivery=True."""
        res = calculate_row_overpayment(
            delivery_rub=100.0, volume=1.0, coef=1.5,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.0, is_fixed_rate=False,
        )
        assert res is not None


class TestFixedRate:
    def test_fixed_rate_returns_zero_overpayment(self):
        res = calculate_row_overpayment(
            delivery_rub=50.0, volume=1.0, coef=1.5,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.0, is_fixed_rate=True,
            is_forward_delivery=True,
        )
        assert res is not None
        assert res.overpayment == 0.0
        assert res.calculated_cost == 50.0


class TestCalculation:
    def test_volume_under_1l(self):
        """cost = base_1l * coef * ktr"""
        res = calculate_row_overpayment(
            delivery_rub=100.0, volume=0.9, coef=1.5,
            base_1l=32.0, extra_l=0.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.09, is_fixed_rate=False,
            is_forward_delivery=True,
        )
        expected_cost = round(32.0 * 1.5 * 1.09, 2)
        assert res.calculated_cost == expected_cost
        assert res.overpayment == round(100.0 - expected_cost, 2)

    def test_volume_over_1l(self):
        """cost = (base_1l + (vol-1)*extra_l) * coef * ktr"""
        res = calculate_row_overpayment(
            delivery_rub=200.0, volume=3.0, coef=1.5,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.05, is_fixed_rate=False,
            is_forward_delivery=True,
        )
        expected_cost = round((46.0 + 2 * 14.0) * 1.5 * 1.05, 2)
        assert res.calculated_cost == expected_cost

    def test_zero_coef_returns_none(self):
        res = calculate_row_overpayment(
            delivery_rub=100.0, volume=1.0, coef=0.0,
            base_1l=46.0, extra_l=14.0, order_dt=date(2026, 1, 15),
            ktr_manual=1.0, is_fixed_rate=False,
            is_forward_delivery=True,
        )
        assert res is None


class TestILOverrides:
    """Fix 4: IL overrides in weekly_il_calculator."""

    def test_overrides_applied(self):
        from services.logistics_audit.calculators.weekly_il_calculator import (
            calculate_weekly_il,
            get_il_for_date,
        )
        # Empty orders → all IL = default from get_ktr_krp(0%)
        overrides = {"2026-01-05": 1.09}
        week_to_il, il_data = calculate_weekly_il(
            orders=[], date_from=date(2026, 1, 5), date_to=date(2026, 1, 11),
            il_overrides=overrides,
        )
        assert week_to_il[date(2026, 1, 5)] == 1.09

    def test_override_priority_over_calculated(self):
        from services.logistics_audit.calculators.weekly_il_calculator import (
            calculate_weekly_il,
        )
        overrides = {"2026-01-05": 99.0}
        week_to_il, _ = calculate_weekly_il(
            orders=[], date_from=date(2026, 1, 5), date_to=date(2026, 1, 11),
            il_overrides=overrides,
        )
        assert week_to_il[date(2026, 1, 5)] == 99.0


class TestILOverridesConfig:
    """Fix 4: il_overrides.json loading."""

    def test_load_empty_overrides(self):
        from services.logistics_audit.config import load_il_overrides
        from pathlib import Path
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"_comment": "test"}, f)
            f.flush()
            result = load_il_overrides(Path(f.name))
        assert result == {}

    def test_load_with_values(self):
        from services.logistics_audit.config import load_il_overrides
        from pathlib import Path
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"_comment": "test", "2026-01-05": 1.09, "2026-01-12": 1.08}, f)
            f.flush()
            result = load_il_overrides(Path(f.name))
        assert result == {"2026-01-05": 1.09, "2026-01-12": 1.08}
