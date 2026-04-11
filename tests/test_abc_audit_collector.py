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


# ── Finance collector tests ──────────────────────────────────────────

from unittest.mock import patch, MagicMock


def test_collect_finance_merges_wb_ozon():
    """Finance collector merges WB + OZON article data by article key."""
    from scripts.abc_audit.collectors.finance import collect_finance

    wb_articles = [
        {
            "article": "wendy/black",
            "model": "wendy",
            "orders_count": 100,
            "sales_count": 85,
            "revenue": 50000.0,
            "margin": 12000.0,
            "adv_internal": 2000.0,
            "adv_external": 1000.0,
            "adv_total": 3000.0,
        }
    ]
    ozon_articles = [
        {
            "article": "wendy/black",
            "model": "wendy",
            "orders_count": 20,
            "sales_count": 15,
            "revenue": 9000.0,
            "margin": 2200.0,
            "adv_internal": 400.0,
            "adv_external": 0.0,
            "adv_total": 400.0,
        }
    ]

    with (
        patch(
            "scripts.abc_audit.collectors.finance.get_wb_by_article",
            return_value=wb_articles,
        ),
        patch(
            "scripts.abc_audit.collectors.finance.get_ozon_by_article",
            return_value=ozon_articles,
        ),
    ):
        result = collect_finance(
            "2026-03-12", "2026-04-12",
            "2026-01-11", "2026-04-12",
            "2025-10-13", "2026-04-12",
        )

    data = result["finance"]
    assert "wendy/black" in data
    art = data["wendy/black"]
    assert art["revenue_30d"] == 50000.0 + 9000.0
    assert art["margin_30d"] == 12000.0 + 2200.0
    assert art["adv_internal_30d"] == 2000.0 + 400.0
    assert art["sales_count_30d"] == 85 + 15


def test_collect_finance_ozon_only_article():
    """Article present only on OZON should still appear."""
    from scripts.abc_audit.collectors.finance import collect_finance

    ozon_articles = [
        {
            "article": "audrey/red",
            "model": "audrey",
            "orders_count": 8,
            "sales_count": 5,
            "revenue": 3000.0,
            "margin": 800.0,
            "adv_internal": 100.0,
            "adv_external": 0.0,
            "adv_total": 100.0,
        }
    ]

    with (
        patch(
            "scripts.abc_audit.collectors.finance.get_wb_by_article",
            return_value=[],
        ),
        patch(
            "scripts.abc_audit.collectors.finance.get_ozon_by_article",
            return_value=ozon_articles,
        ),
    ):
        result = collect_finance(
            "2026-03-12", "2026-04-12",
            "2026-01-11", "2026-04-12",
            "2025-10-13", "2026-04-12",
        )

    data = result["finance"]
    assert "audrey/red" in data
    assert data["audrey/red"]["margin_30d"] == 800.0
