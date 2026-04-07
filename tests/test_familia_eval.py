"""Tests for Familia evaluation pipeline."""

from scripts.familia_eval.collector import merge_article_data


def test_merge_article_data_basic():
    """Merge MoySklad stock with pricing and status data."""
    ms_stock = {
        "vuki/black": {"stock_main": 450, "stock_transit": 0, "total": 450},
    }
    statuses = {
        "vuki/black": "Выводим",
    }
    wb_pricing = [
        {
            "model": "vuki",
            "avg_price_per_unit": 1180,
            "margin_pct": 22.9,
            "spp_pct": 15.0,
            "drr_pct": 2.8,
        }
    ]
    wb_turnover = {
        "vuki": {"daily_sales": 2.3, "turnover_days": 196},
    }
    wb_finance = [
        ("current", "vuki", 69, 81420, 2279, 0, 18645, 26148),
    ]
    finance_cols = [
        "period", "model", "sales_count", "revenue_before_spp",
        "adv_internal", "adv_external", "margin", "cost_of_goods",
    ]

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=wb_pricing,
        ozon_pricing=[],
        wb_turnover=wb_turnover,
        ozon_turnover={},
        wb_finance=wb_finance,
        ozon_finance=[],
        finance_cols=finance_cols,
    )

    assert len(result) == 1
    art = result[0]
    assert art["article"] == "vuki/black"
    assert art["stock_moysklad"] == 450
    assert art["status"] == "Выводим"
    assert art["model"] == "vuki"
    assert art["rrc"] == 1180
    assert art["margin_pct_mp"] == 22.9
    assert art["daily_sales_mp"] == 2.3
    assert art["turnover_days"] == 196
    assert art["cogs_per_unit"] > 0


def test_merge_filters_by_status():
    """Only articles with status in filter list are included."""
    ms_stock = {
        "wendy/black": {"stock_main": 200, "stock_transit": 0, "total": 200},
    }
    statuses = {
        "wendy/black": "Продается",
    }

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=[], ozon_pricing=[],
        wb_turnover={}, ozon_turnover={},
        wb_finance=[], ozon_finance=[],
        finance_cols=[],
    )

    assert len(result) == 0


def test_merge_filters_by_min_stock():
    """Articles below min_stock threshold are excluded."""
    ms_stock = {
        "alice/pink": {"stock_main": 5, "stock_transit": 0, "total": 5},
    }
    statuses = {"alice/pink": "Архив"}

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=[], ozon_pricing=[],
        wb_turnover={}, ozon_turnover={},
        wb_finance=[], ozon_finance=[],
        finance_cols=[],
    )

    assert len(result) == 0
