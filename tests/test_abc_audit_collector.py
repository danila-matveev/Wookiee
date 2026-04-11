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


# ── Inventory collector tests ───────────────────────────────────────


def test_collect_inventory_total_stock():
    """Inventory collector sums WB + OZON + MoySklad stocks."""
    from scripts.abc_audit.collectors.inventory import collect_inventory

    with (
        patch(
            "scripts.abc_audit.collectors.inventory.get_wb_avg_stock",
            return_value={"wendy/black": 200.0, "audrey/red": 50.0},
        ),
        patch(
            "scripts.abc_audit.collectors.inventory.get_ozon_avg_stock",
            return_value={"wendy/black": 80.0},
        ),
        patch(
            "scripts.abc_audit.collectors.inventory.get_moysklad_stock_by_article",
            return_value={
                "wendy/black": {
                    "stock_main": 150, "stock_transit": 50,
                    "total": 200, "snapshot_date": "2026-04-11", "is_stale": False,
                },
            },
        ),
    ):
        result = collect_inventory("2026-03-12", "2026-04-12")

    data = result["inventory"]
    assert data["wendy/black"]["stock_wb"] == 200.0
    assert data["wendy/black"]["stock_ozon"] == 80.0
    assert data["wendy/black"]["stock_moysklad"] == 200
    assert data["wendy/black"]["stock_total"] == 480.0
    assert data["audrey/red"]["stock_total"] == 50.0
    assert result["meta"]["moysklad_stale"] is False


def test_collect_inventory_turnover_calc():
    """Turnover = total_stock / daily_sales. MOQ months calc."""
    from scripts.abc_audit.collectors.inventory import calc_turnover_metrics

    metrics = calc_turnover_metrics(stock_total=480.0, daily_sales=16.0)

    assert metrics["turnover_days"] == 30.0
    assert metrics["moq_months"] == pytest.approx(500 / (16.0 * 30), rel=0.01)
    assert metrics["roi_annual"] == pytest.approx(0, abs=1)  # needs margin_pct


def test_calc_turnover_with_margin():
    """ROI annual = margin_pct * (365 / turnover_days)."""
    from scripts.abc_audit.collectors.inventory import calc_turnover_metrics

    metrics = calc_turnover_metrics(
        stock_total=480.0, daily_sales=16.0, margin_pct=25.0,
    )

    # turnover_days = 480/16 = 30
    # ROI = 25 * (365/30) = 304.2
    assert metrics["roi_annual"] == pytest.approx(304.2, rel=0.01)


# ── Hierarchy collector tests ──────────────────────────────────────


def test_collect_hierarchy_groups_by_color_code():
    """Hierarchy collector groups tricot articles by color_code."""
    from scripts.abc_audit.collectors.hierarchy import collect_hierarchy

    fake_info = {
        "vuki/black": {
            "status": "Продается", "model_kod": "VukiN",
            "model_osnova": "Vuki", "color_code": "2",
            "cvet": "черный", "color": "black",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
        "moon/black": {
            "status": "Продается", "model_kod": "MoonN",
            "model_osnova": "Moon", "color_code": "2",
            "cvet": "черный", "color": "black",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
        "wendy/red": {
            "status": "Продается", "model_kod": "WendyN",
            "model_osnova": "Wendy", "color_code": "WE005",
            "cvet": "красный", "color": "red",
            "skleyka_wb": None, "tip_kollekcii": "seamless_wendy",
        },
    }

    with patch(
        "scripts.abc_audit.collectors.hierarchy.get_artikuly_full_info",
        return_value=fake_info,
    ):
        result = collect_hierarchy()

    h = result["hierarchy"]

    # Все артикулы должны быть в articles
    assert "vuki/black" in h["articles"]
    assert h["articles"]["vuki/black"]["tip_kollekcii"] == "tricot"

    # Color_code группы для tricot
    cc_key = "tricot|2"
    assert cc_key in h["color_code_groups"]
    group = h["color_code_groups"][cc_key]
    assert set(group["models"]) == {"Vuki", "Moon"}
    assert len(group["articles"]) == 2

    # Wendy не в tricot color_code группе
    assert "seamless_wendy|WE005" in h["color_code_groups"]

    # Status counts
    assert h["status_counts"]["Продается"] == 3


def test_collect_hierarchy_excludes_archive():
    """Archive articles excluded from active analysis."""
    from scripts.abc_audit.collectors.hierarchy import collect_hierarchy

    fake_info = {
        "old/model": {
            "status": "Архив", "model_kod": "OldN",
            "model_osnova": "Old", "color_code": "99",
            "cvet": "серый", "color": "grey",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
    }

    with patch(
        "scripts.abc_audit.collectors.hierarchy.get_artikuly_full_info",
        return_value=fake_info,
    ):
        result = collect_hierarchy()

    h = result["hierarchy"]
    assert h["articles"]["old/model"]["active"] is False
    assert h["status_counts"]["Архив"] == 1


# ── Buyout + Size collector tests ─────────────────────────────────


def test_collect_buyouts_calculates_pct():
    """Buyout collector returns buyout % per article."""
    from scripts.abc_audit.collectors.buyouts import collect_buyouts

    wb_buyouts = [
        ("wendy", "wendy/black", 100, 85, 15),
        ("audrey", "audrey/red", 50, 30, 20),
    ]

    with patch(
        "scripts.abc_audit.collectors.buyouts.get_wb_buyouts_returns_by_artikul",
        return_value=wb_buyouts,
    ):
        result = collect_buyouts("2026-03-12", "2026-04-12")

    data = result["buyouts"]
    assert data["wendy/black"]["buyout_pct"] == 85.0
    assert data["audrey/red"]["buyout_pct"] == 60.0


def test_collect_size_data():
    """Size collector aggregates sales by size from barcode data."""
    from scripts.abc_audit.collectors.buyouts import collect_size_data

    wb_barcodes = [
        {"barcode": "123", "article": "wendy/black", "ts_name": "S", "sales_count": 30, "model": "wendy"},
        {"barcode": "124", "article": "wendy/black", "ts_name": "M", "sales_count": 50, "model": "wendy"},
        {"barcode": "125", "article": "wendy/black", "ts_name": "L", "sales_count": 35, "model": "wendy"},
    ]

    with patch(
        "scripts.abc_audit.collectors.buyouts.get_wb_fin_data_by_barcode",
        return_value=wb_barcodes,
    ):
        result = collect_size_data("2026-03-12", "2026-04-12")

    sizes = result["sizes"]
    assert "wendy/black" in sizes
    size_dist = sizes["wendy/black"]
    assert size_dist["S"] == 30
    assert size_dist["M"] == 50
    assert size_dist["L"] == 35


# ── Main collector orchestrator tests ────────────────────────────


def test_main_collector_runs_all_collectors():
    """Main collector calls all sub-collectors and merges."""
    from scripts.abc_audit.collect_data import run_collection

    with (
        patch("scripts.abc_audit.collect_data.collect_finance", return_value={"finance": {"a/b": {"margin_30d": 100}}}),
        patch("scripts.abc_audit.collect_data.collect_inventory", return_value={"inventory": {"a/b": {"stock_total": 50}}, "meta": {"moysklad_stale": False}}),
        patch("scripts.abc_audit.collect_data.collect_hierarchy", return_value={"hierarchy": {"articles": {"a/b": {"status": "Продается"}}, "color_code_groups": {}, "status_counts": {"Продается": 1}}}),
        patch("scripts.abc_audit.collect_data.collect_buyouts", return_value={"buyouts": {"a/b": {"buyout_pct": 85.0}}}),
        patch("scripts.abc_audit.collect_data.collect_size_data", return_value={"sizes": {"a/b": {"M": 10}}}),
    ):
        result = run_collection("2026-04-11")

    assert "finance" in result
    assert "inventory" in result
    assert "hierarchy" in result
    assert "buyouts" in result
    assert "sizes" in result
    assert "meta" in result
    assert result["meta"]["cut_date"] == "2026-04-11"
    assert "errors" in result["meta"]


def test_full_collector_json_schema():
    """Smoke test: collector output has all required top-level keys."""
    from scripts.abc_audit.collect_data import run_collection

    with (
        patch("scripts.abc_audit.collect_data.collect_finance", return_value={"finance": {}}),
        patch("scripts.abc_audit.collect_data.collect_inventory", return_value={"inventory": {}, "meta": {"moysklad_stale": False}}),
        patch("scripts.abc_audit.collect_data.collect_hierarchy", return_value={"hierarchy": {"articles": {}, "color_code_groups": {}, "status_counts": {}}}),
        patch("scripts.abc_audit.collect_data.collect_buyouts", return_value={"buyouts": {}}),
        patch("scripts.abc_audit.collect_data.collect_size_data", return_value={"sizes": {}}),
    ):
        result = run_collection("2026-04-11")

    # Top-level keys
    required_keys = {"finance", "inventory", "hierarchy", "buyouts", "sizes", "meta"}
    assert required_keys.issubset(set(result.keys()))

    # Meta structure
    meta = result["meta"]
    assert meta["cut_date"] == "2026-04-11"
    assert "p30_start" in meta
    assert "p90_start" in meta
    assert "p180_start" in meta
    assert "errors" in meta
    assert "quality_flags" in meta
    assert "duration_sec" in meta

    # Quality flags structure
    qf = meta["quality_flags"]
    assert "coverage_pct" in qf
    assert "ozon_buyout_available" in qf
    assert qf["ozon_buyout_available"] is False
