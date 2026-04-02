"""Tests for monthly plan date utilities and quality flags."""
import pytest
from scripts.monthly_plan.utils import compute_date_params, build_quality_flags


class TestComputeDateParams:
    def test_may_plan(self):
        params = compute_date_params("2026-05")
        assert params["plan_month"] == "2026-05"
        assert params["current_month_start"] == "2026-04-01"
        assert params["current_month_end"] == "2026-05-01"
        assert params["prev_month_start"] == "2026-03-01"
        assert params["elasticity_start"] == "2026-01-01"
        assert params["stock_window_start"] == "2026-04-25"

    def test_january_plan(self):
        """January plan uses December as base, November as prev."""
        params = compute_date_params("2026-01")
        assert params["current_month_start"] == "2025-12-01"
        assert params["current_month_end"] == "2026-01-01"
        assert params["prev_month_start"] == "2025-11-01"
        assert params["elasticity_start"] == "2025-09-01"

    def test_stock_window_always_last_week(self):
        params = compute_date_params("2026-03")
        # February base month, stock window = last week of Feb
        assert params["stock_window_start"] == "2026-02-22"


class TestBuildQualityFlags:
    def test_static_flags_present(self):
        flags = build_quality_flags(models_data={})
        assert flags["fan_out_bug"] is True
        assert flags["ozon_no_external_ads"] is True
        assert flags["traffic_powerbi_gap_20pct"] is True

    def test_low_data_models_detected(self):
        models_data = {
            "charlotte": {"data_months": 2},
            "wendy": {"data_months": 12},
        }
        flags = build_quality_flags(models_data)
        assert "charlotte" in flags["models_with_low_data"]
        assert "wendy" not in flags["models_with_low_data"]
