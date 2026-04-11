"""Tests for ABC audit collector."""
from __future__ import annotations

import pytest
from datetime import date


def test_compute_abc_date_params_default():
    """30/90/180 day windows from reference date."""
    from scripts.abc_audit.utils import compute_abc_date_params

    params = compute_abc_date_params("2026-04-11")

    assert params["cut_date"] == "2026-04-11"
    assert params["p30_start"] == "2026-03-12"
    assert params["p90_start"] == "2026-01-11"
    assert params["p180_start"] == "2025-10-13"
    assert params["p30_end_exclusive"] == "2026-04-12"
    assert params["year_ago_start"] == "2025-03-12"
    assert params["year_ago_end"] == "2025-04-11"
    assert params["days_30"] == 30
    assert params["days_90"] == 90
    assert params["days_180"] == 180


def test_compute_abc_date_params_custom_date():
    """Custom reference date."""
    from scripts.abc_audit.utils import compute_abc_date_params

    params = compute_abc_date_params("2026-01-15")

    assert params["cut_date"] == "2026-01-15"
    assert params["p30_start"] == "2025-12-16"
    assert params["p90_start"] == "2025-10-17"


def test_build_abc_quality_flags_no_errors():
    """No errors → clean flags."""
    from scripts.abc_audit.utils import build_abc_quality_flags

    flags = build_abc_quality_flags(errors={}, article_count=142, supabase_count=142)

    assert flags["collector_errors"] == {}
    assert flags["coverage_pct"] == 100.0
    assert flags["ozon_buyout_available"] is False


def test_build_abc_quality_flags_with_errors():
    """Errors tracked, coverage calculated."""
    from scripts.abc_audit.utils import build_abc_quality_flags

    flags = build_abc_quality_flags(
        errors={"finance": "connection timeout"},
        article_count=120,
        supabase_count=142,
    )

    assert "finance" in flags["collector_errors"]
    assert abs(flags["coverage_pct"] - 84.5) < 0.1
