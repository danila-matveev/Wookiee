import pytest
from datetime import date
from services.logistics_audit.calculators.logistics_overpayment import (
    calculate_row_overpayment,
    OverpaymentResult,
    FORMULA_CHANGE_DATE,
)


def test_old_formula_above_1l_wookiee():
    """Before 23.03: nm_id=257131227, Коледино, volume=2.904L, KTR=1.04."""
    result = calculate_row_overpayment(
        delivery_rub=147.23,
        volume=2.904,
        coef=1.95,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 2, 28),
        ktr_manual=1.04,
        is_fixed_rate=False,
    )
    assert result.calculated_cost == pytest.approx(147.35, abs=0.1)


def test_old_formula_below_1l_fisanov():
    """Before 23.03: nm_id=169516610, volume=0.98L, base=32₽, KTR=1.37."""
    result = calculate_row_overpayment(
        delivery_rub=268.93,
        volume=0.98,
        coef=2.0,
        base_1l=32.0,
        extra_l=14.0,
        order_dt=date(2026, 1, 15),
        ktr_manual=1.37,
        is_fixed_rate=False,
    )
    assert result.calculated_cost == pytest.approx(87.68, abs=0.01)
    assert result.overpayment == pytest.approx(268.93 - 87.68, abs=0.01)


def test_new_formula_high_localization():
    """From 23.03: SKU with 80% localization → IL=0.80, IRP=0%."""
    result = calculate_row_overpayment(
        delivery_rub=100.0,
        volume=2.0,
        coef=1.5,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 3, 25),
        ktr_manual=1.04,
        is_fixed_rate=False,
        sku_localization_pct=80.0,
        retail_price=1000.0,
    )
    assert result.calculated_cost == pytest.approx(72.0, abs=0.1)


def test_new_formula_low_localization_irp():
    """From 23.03: SKU with 30% localization → IL=1.60, IRP=2.15%."""
    result = calculate_row_overpayment(
        delivery_rub=200.0,
        volume=0.9,
        coef=1.5,
        base_1l=46.0,
        extra_l=14.0,
        order_dt=date(2026, 3, 25),
        ktr_manual=1.04,
        is_fixed_rate=False,
        sku_localization_pct=30.0,
        retail_price=2000.0,
    )
    assert result.calculated_cost == pytest.approx(153.4, abs=0.5)


def test_fixed_rate_excluded():
    """Fixed-rate rows (50₽ return) have 0 overpayment."""
    result = calculate_row_overpayment(
        delivery_rub=50.0, volume=0.9, coef=1.6,
        base_1l=33.0, extra_l=14.0,
        order_dt=date(2026, 3, 1),
        ktr_manual=1.04, is_fixed_rate=True,
    )
    assert result.calculated_cost == 50.0
    assert result.overpayment == 0.0


def test_zero_coef_skipped():
    """Rows with coef=0 are not logistics — skip."""
    result = calculate_row_overpayment(
        delivery_rub=100.0, volume=0.9, coef=0.0,
        base_1l=33.0, extra_l=14.0,
        order_dt=date(2026, 3, 1),
        ktr_manual=1.04, is_fixed_rate=False,
    )
    assert result is None
