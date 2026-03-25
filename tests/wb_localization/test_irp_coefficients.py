"""Tests for updated KTR coefficients (27.03.2026)."""
import pytest
from services.wb_localization.irp_coefficients import get_ktr_krp, get_zone, IRP_THRESHOLD

@pytest.mark.parametrize("loc_pct, expected_ktr, expected_krp", [
    (97.0, 0.50, 0.00),   # top tier — unchanged
    (72.0, 1.00, 0.00),   # neutral — unchanged
    (62.0, 1.00, 0.00),   # just above IRP threshold — unchanged
    (57.0, 1.05, 2.00),   # was 1.10 → now 1.05
    (52.0, 1.10, 2.05),   # was 1.20 → now 1.10
    (47.0, 1.20, 2.05),   # was 1.30 → now 1.20
    (42.0, 1.30, 2.10),   # was 1.40 → now 1.30
    (37.0, 1.40, 2.10),   # was 1.50 → now 1.40
    (32.0, 1.60, 2.15),   # unchanged (below updated range)
    (2.0,  2.20, 2.50),   # bottom tier — unchanged
])
def test_get_ktr_krp_updated_values(loc_pct, expected_ktr, expected_krp):
    ktr, krp = get_ktr_krp(loc_pct)
    assert ktr == expected_ktr
    assert krp == expected_krp

def test_irp_threshold():
    assert IRP_THRESHOLD == 60.0

def test_zone_boundaries():
    assert get_zone(58.0) == "ИРП-зона"
    assert get_zone(62.0) == "ИЛ-зона"
    assert get_zone(76.0) == "OK"
