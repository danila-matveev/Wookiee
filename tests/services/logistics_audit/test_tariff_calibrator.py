from services.logistics_audit.calculators.tariff_calibrator import calibrate_base_tariff


def test_calibrate_with_sub1l_rows():
    """Reverse-calc from ≤1L rows: base*KTR ≈ delivery_rub / dlv_prc."""
    rows = [
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},
        {"delivery_rub": 64.35, "dlv_prc": 1.95, "volume": 0.9},
        {"delivery_rub": 39.6, "dlv_prc": 1.2, "volume": 0.672},
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert 32.9 <= result <= 33.1


def test_calibrate_skips_zero_dlv_prc():
    """Rows with dlv_prc=0 are not logistics and must be skipped."""
    rows = [
        {"delivery_rub": 50.0, "dlv_prc": 0, "volume": 0.9},
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert abs(result - 32.91) < 0.1


def test_calibrate_skips_above_1l():
    """Only ≤1L rows are used for calibration (formula = base * coef * ktr)."""
    rows = [
        {"delivery_rub": 52.65, "dlv_prc": 1.6, "volume": 0.9},
        {"delivery_rub": 147.23, "dlv_prc": 1.95, "volume": 2.904},
    ]
    result = calibrate_base_tariff(rows)
    assert result is not None
    assert abs(result - 32.91) < 0.1


def test_calibrate_no_valid_rows():
    """If no ≤1L rows with dlv_prc>0, return None."""
    rows = [
        {"delivery_rub": 147.23, "dlv_prc": 1.95, "volume": 2.904},
    ]
    result = calibrate_base_tariff(rows)
    assert result is None


def test_calibrate_empty():
    assert calibrate_base_tariff([]) is None
