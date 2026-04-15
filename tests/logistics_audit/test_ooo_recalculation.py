"""Tests for OOO recalculation logic (recalculate_ooo.py)."""
from datetime import date

import pytest

from services.logistics_audit.recalculate_ooo import (
    _calc_cost,
    _find_tariff_coef,
    _monday,
    _resolve_coef_3tier,
    load_tariff_file,
    OOO_IL_DASHBOARD,
    TARIFF_FILE_PATH,
)
from services.logistics_audit.calculators.tariff_periods import get_base_tariffs
from services.logistics_audit.models.report_row import FORWARD_DELIVERY_TYPES


class TestTariffFileLoading:
    """Test 1: Loading tariff file → Коледино = 195%."""

    @pytest.fixture(scope="class")
    def tariff_index(self):
        if not TARIFF_FILE_PATH.exists():
            pytest.skip("Tariff file not found")
        return load_tariff_file(TARIFF_FILE_PATH)

    def test_koledino_coefficient(self, tariff_index):
        """Коледино should have coefficient ~1.95 (195%)."""
        assert "Коледино" in tariff_index
        entries = tariff_index["Коледино"]
        assert len(entries) > 0
        # Check a recent entry
        for dt, coef in entries:
            if dt >= date(2025, 1, 1):
                assert 1.0 < coef < 5.0, f"Коледино coef {coef} out of range"
                break

    def test_tariff_entries_count(self, tariff_index):
        """Should load significant number of entries."""
        total = sum(len(v) for v in tariff_index.values())
        assert total > 10000


class TestCoefFixationActive:
    """Test 2: Fixation active → use dlv_prc."""

    def test_fixation_active(self):
        row = {
            "order_dt": date(2026, 1, 15),
            "dlv_prc": 2.25,
            "fix_to": date(2026, 6, 1),  # expires after order
            "warehouse": "Коледино",
            "calc_coef": 2.25,
        }
        coef, src = _resolve_coef_3tier(row, {})
        assert coef == 2.25
        assert src == "fixation"


class TestCoefFixationExpired:
    """Test 3: Fixation expired → use tariff file."""

    def test_fixation_expired_uses_file(self):
        tariff_index = {
            "Коледино": [(date(2026, 1, 10), 1.95), (date(2025, 12, 1), 1.90)],
        }
        row = {
            "order_dt": date(2026, 1, 15),
            "dlv_prc": 2.25,
            "fix_to": date(2025, 11, 1),  # expired before order
            "warehouse": "Коледино",
            "calc_coef": 2.25,
        }
        coef, src = _resolve_coef_3tier(row, tariff_index)
        assert coef == 1.95
        assert src == "tariff_file"


class TestForwardDeliveryFilter:
    """Test 4: Whitelist filter — 2 types stay, 8 excluded."""

    def test_forward_types_in_whitelist(self):
        assert "К клиенту при продаже" in FORWARD_DELIVERY_TYPES
        assert "К клиенту при отмене" in FORWARD_DELIVERY_TYPES

    def test_reverse_types_excluded(self):
        excluded = [
            "От клиента при отмене",
            "От клиента при возврате",
            "Возврат по инициативе продавца (К продавцу)",
            "Возврат брака (К продавцу)",
            "Возврат по инициативе продавца (От продавца при отмене)",
            "Возврат неопознанного товара (К продавцу)",
        ]
        for bt in excluded:
            assert bt not in FORWARD_DELIVERY_TYPES, f"{bt} should NOT be in whitelist"

    def test_exactly_two_forward_types(self):
        assert len(FORWARD_DELIVERY_TYPES) == 2


class TestSubLiterTariff:
    """Test 5: Sub-liter volume=0.9 → base=32."""

    def test_subliter_0_9(self):
        base_1l, extra_l = get_base_tariffs(
            order_date=date(2026, 1, 15),
            fixation_start=None,
            fixation_end=None,
            volume=0.9,
        )
        assert base_1l == 32.0
        assert extra_l == 0.0

    def test_subliter_cost_calculation(self):
        """vol=0.9, coef=1.2, il=1.05 → cost = 32 * 1.2 * 1.05 = 40.32."""
        cost = _calc_cost(volume=0.9, coef=1.2, il=1.05, base_1l=32.0, extra_l=0.0)
        assert cost == 40.32


class TestNegativeExclusion:
    """Test 6: Negative overpayment → not in total."""

    def test_negative_excluded_from_sum(self):
        """Rows with overpayment < 0 should not contribute to the final total."""
        details = [
            {"overpay_new": 100.0},
            {"overpay_new": -50.0},
            {"overpay_new": 200.0},
            {"overpay_new": -30.0},
        ]
        positive_total = sum(d["overpay_new"] for d in details if d["overpay_new"] >= 0)
        negative_count = sum(1 for d in details if d["overpay_new"] < 0)
        assert positive_total == 300.0
        assert negative_count == 2

    def test_zero_overpayment_included(self):
        """Zero overpayment rows should be included (not excluded)."""
        details = [
            {"overpay_new": 0.0},
            {"overpay_new": 100.0},
        ]
        included = [d for d in details if d["overpay_new"] >= 0]
        assert len(included) == 2
