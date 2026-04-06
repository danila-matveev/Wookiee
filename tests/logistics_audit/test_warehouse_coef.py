"""Tests for 3-tier warehouse coefficient resolution."""
from datetime import date
from services.logistics_audit.calculators.warehouse_coef_resolver import (
    resolve_warehouse_coef,
    CoefResult,
)


class TestFixationTier:
    """Tier 1: Fixed coefficient when fixation is active."""

    def test_fixation_active(self):
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=2.0,
            fixation_end=date(2026, 6, 1), order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs={},
        )
        assert r == CoefResult(value=2.0, source="fixation", verified=True)

    def test_fixation_expired(self):
        """Fixation expired → skip to next tier."""
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=2.0,
            fixation_end=date(2025, 6, 1), order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs={},
        )
        assert r.source != "fixation"

    def test_fixation_zero_coef(self):
        """fixed_coef=0 → skip fixation tier."""
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=0.0,
            fixation_end=date(2026, 6, 1), order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs={},
        )
        assert r.source != "fixation"


class TestSupabaseTier:
    """Tier 2: Supabase historical tariffs."""

    def test_supabase_exact_date(self):
        # Values in supabase_tariffs are already decimal (divided by 100 in load_supabase_tariffs)
        sb = {"Склад": {date(2026, 1, 15): 1.5}}
        r = resolve_warehouse_coef(
            dlv_prc=1.0, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Склад", supabase_tariffs=sb,
        )
        assert r == CoefResult(value=1.5, source="supabase", verified=True)

    def test_supabase_closest_date(self):
        sb = {"Склад": {date(2026, 1, 10): 2.0, date(2026, 1, 14): 2.5}}
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Склад", supabase_tariffs=sb,
        )
        assert r.value == 2.5
        assert r.source == "supabase"

    def test_supabase_no_match(self):
        sb = {"Другой": {date(2026, 1, 10): 200.0}}
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Склад", supabase_tariffs=sb,
        )
        assert r.source == "dlv_prc"


class TestFallbackTier:
    """Tier 3: dlv_prc fallback (not verified)."""

    def test_dlv_prc_fallback(self):
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs={},
        )
        assert r == CoefResult(value=1.5, source="dlv_prc", verified=False)

    def test_zero_dlv_prc(self):
        r = resolve_warehouse_coef(
            dlv_prc=0.0, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs={},
        )
        assert r.value == 0.0
        assert r.verified is False


class TestPriority:
    """Priority chain: fixation > supabase > dlv_prc."""

    def test_fixation_beats_supabase(self):
        sb = {"Test": {date(2026, 1, 15): 300.0}}
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=2.0,
            fixation_end=date(2026, 6, 1), order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs=sb,
        )
        assert r.source == "fixation"
        assert r.value == 2.0

    def test_supabase_beats_dlv_prc(self):
        sb = {"Test": {date(2026, 1, 14): 200.0}}
        r = resolve_warehouse_coef(
            dlv_prc=1.5, fixed_coef=0.0,
            fixation_end=None, order_date=date(2026, 1, 15),
            warehouse_name="Test", supabase_tariffs=sb,
        )
        assert r.source == "supabase"
