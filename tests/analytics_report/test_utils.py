"""Tests for scripts.analytics_report.utils."""
from __future__ import annotations

import pytest

from scripts.analytics_report.utils import (
    MONTHS_RU_GENITIVE,
    _format_period_label,
    build_quality_flags,
    compute_date_params,
    model_from_article,
    safe_float,
    tuples_to_dicts,
)
from datetime import date


# ---------- compute_date_params ----------


class TestComputeDateParamsDaily:
    """Single date -> daily report, prev = yesterday."""

    def test_daily_depth(self):
        p = compute_date_params("2026-04-05")
        assert p["depth"] == "daily"

    def test_daily_dates(self):
        p = compute_date_params("2026-04-05")
        assert p["start_date"] == "2026-04-05"
        assert p["end_date"] == "2026-04-05"
        assert p["prev_start"] == "2026-04-04"
        assert p["prev_end"] == "2026-04-04"

    def test_daily_days_in_period(self):
        p = compute_date_params("2026-04-05")
        assert p["days_in_period"] == 1


class TestComputeDateParamsWeekly:
    """Two dates 7 days apart -> weekly."""

    def test_weekly_depth(self):
        # 7-day span: Apr 1-7 inclusive
        p = compute_date_params("2026-04-01", "2026-04-07")
        assert p["depth"] == "weekly"
        assert p["days_in_period"] == 7

    def test_weekly_prev_period(self):
        p = compute_date_params("2026-04-01", "2026-04-07")
        assert p["prev_start"] == "2026-03-25"
        assert p["prev_end"] == "2026-03-31"


class TestComputeDateParamsMonthly:
    """Two dates ~30 days apart -> monthly."""

    def test_monthly_depth(self):
        p = compute_date_params("2026-03-01", "2026-03-31")
        assert p["depth"] == "monthly"
        assert p["days_in_period"] == 31

    def test_monthly_prev_period_handles_feb(self):
        # March full month -> prev = 31 days ending Feb 28
        p = compute_date_params("2026-03-01", "2026-03-31")
        assert p["prev_end"] == "2026-02-28"
        assert p["prev_start"] == "2026-01-29"


class TestCrossMonthBoundary:
    """Period crossing month boundary."""

    def test_cross_month(self):
        p = compute_date_params("2026-03-28", "2026-04-03")
        assert p["depth"] == "weekly"
        assert p["days_in_period"] == 7
        assert p["prev_start"] == "2026-03-21"
        assert p["prev_end"] == "2026-03-27"

    def test_month_start_is_first_of_end_month(self):
        p = compute_date_params("2026-03-28", "2026-04-03")
        assert p["month_start"] == "2026-04-01"


class TestMonthStartCrossMonth:
    def test_cross_month_uses_end_date(self):
        """month_start should be first day of END date's month."""
        p = compute_date_params("2026-03-30", "2026-04-05")
        assert p["month_start"] == "2026-04-01"

    def test_same_month_unchanged(self):
        """When start and end in same month, month_start = first of that month."""
        p = compute_date_params("2026-04-01", "2026-04-07")
        assert p["month_start"] == "2026-04-01"


# ---------- _format_period_label ----------


class TestFormatPeriodLabel:
    """Russian period labels."""

    def test_single_day(self):
        label = _format_period_label(date(2026, 4, 5), date(2026, 4, 5))
        assert label == "5 апреля 2026"

    def test_same_month(self):
        label = _format_period_label(date(2026, 4, 1), date(2026, 4, 7))
        assert label == "01 -- 07 апреля 2026"

    def test_cross_month(self):
        label = _format_period_label(date(2026, 3, 28), date(2026, 4, 3))
        assert "марта" in label
        assert "апреля" in label
        assert "2026" in label


# ---------- month_start ----------


class TestMonthStart:
    def test_month_start_mid_month(self):
        p = compute_date_params("2026-04-15")
        assert p["month_start"] == "2026-04-01"

    def test_month_start_first_day(self):
        p = compute_date_params("2026-04-01")
        assert p["month_start"] == "2026-04-01"


# ---------- build_quality_flags ----------


class TestBuildQualityFlags:
    def test_always_has_standard_warnings(self):
        flags = build_quality_flags(errors={})
        assert flags["traffic_powerbi_gap_20pct"] is True
        assert flags["buyout_lag_3_21_days"] is True

    def test_collector_errors_populated(self):
        flags = build_quality_flags(errors={"finance": "timeout"})
        assert flags["collector_errors"] == {"finance": "timeout"}

    def test_empty_errors(self):
        flags = build_quality_flags(errors={})
        assert flags["collector_errors"] == {}

    def test_ad_totals_check(self):
        ad = {"delta_pct": 5.2}
        flags = build_quality_flags(errors={}, ad_totals_check=ad)
        assert flags["ad_totals_check"] == ad

    def test_no_ad_totals_key_when_none(self):
        flags = build_quality_flags(errors={})
        assert "ad_totals_check" not in flags


# ---------- helpers ----------


class TestTuplesToDicts:
    def test_basic(self):
        rows = [(1, "a"), (2, "b")]
        cols = ["id", "name"]
        result = tuples_to_dicts(rows, cols)
        assert result == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

    def test_empty(self):
        assert tuples_to_dicts([], ["x"]) == []


class TestSafeFloat:
    def test_int(self):
        assert safe_float(42) == 42.0

    def test_str_number(self):
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_none(self):
        assert safe_float(None) is None

    def test_non_numeric(self):
        assert safe_float("abc") is None


class TestModelFromArticle:
    def test_basic(self):
        assert model_from_article("wendy/black") == "wendy"

    def test_uppercase(self):
        assert model_from_article("Wendy/Black") == "wendy"

    def test_no_slash(self):
        assert model_from_article("wendy") == "wendy"

    def test_empty(self):
        assert model_from_article("") == ""
