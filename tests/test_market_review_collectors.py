"""Tests for market review data collectors."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_days(n: int, revenue: int = 1000, sales: int = 10) -> list[dict]:
    """Create a list of fake daily data dicts."""
    return [{"revenue": revenue, "sales": sales, "items_count": 50} for _ in range(n)]


def _mock_mpstats_client():
    """Create a fully mocked MPStatsClient."""
    client = MagicMock()
    client.BASE_URL = "https://mpstats.io/api/wb"
    client.close = MagicMock()
    return client


# ---------------------------------------------------------------------------
# market_categories
# ---------------------------------------------------------------------------

class TestMarketCategories:

    @patch("scripts.market_review.collectors.market_categories.MPStatsClient")
    def test_returns_expected_structure(self, MockClient):
        from scripts.market_review.collectors.market_categories import collect_market_categories

        client = _mock_mpstats_client()
        MockClient.return_value = client
        client.get_category_trends.return_value = {"days": _make_days(7)}

        result = collect_market_categories("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "categories" in result
        for cat_name, cat_data in result["categories"].items():
            assert "path" in cat_data
            assert "current" in cat_data
            assert "previous" in cat_data
            assert "delta_pct" in cat_data
            assert "revenue" in cat_data["current"]
            assert "sales" in cat_data["current"]
            assert "avg_price" in cat_data["current"]

    @patch("scripts.market_review.collectors.market_categories.MPStatsClient")
    def test_empty_api_response(self, MockClient):
        from scripts.market_review.collectors.market_categories import collect_market_categories

        client = _mock_mpstats_client()
        MockClient.return_value = client
        client.get_category_trends.return_value = {}

        result = collect_market_categories("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "categories" in result
        for cat_data in result["categories"].values():
            assert cat_data["current"]["revenue"] == 0
            assert cat_data["current"]["sales"] == 0

    @patch("scripts.market_review.collectors.market_categories.MPStatsClient")
    def test_delta_calculation(self, MockClient):
        from scripts.market_review.collectors.market_categories import collect_market_categories

        client = _mock_mpstats_client()
        MockClient.return_value = client

        # Current: 7 days * 2000 = 14000 revenue
        # Previous: 7 days * 1000 = 7000 revenue
        # Delta: +100%
        def side_effect(path, d1, d2):
            if d1 == "2026-03-01":
                return {"days": _make_days(7, revenue=2000, sales=20)}
            return {"days": _make_days(7, revenue=1000, sales=10)}

        client.get_category_trends.side_effect = side_effect

        result = collect_market_categories("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        first_cat = list(result["categories"].values())[0]
        assert first_cat["delta_pct"]["revenue"] == 100.0
        assert first_cat["delta_pct"]["sales"] == 100.0


# ---------------------------------------------------------------------------
# our_performance
# ---------------------------------------------------------------------------

class TestOurPerformance:

    @patch("scripts.market_review.collectors.our_performance.get_ozon_finance")
    @patch("scripts.market_review.collectors.our_performance.get_wb_finance")
    def test_returns_expected_structure(self, mock_wb, mock_ozon):
        from scripts.market_review.collectors.our_performance import collect_our_performance

        # WB row: period + 18 values
        wb_current = ("current", 100, 80, 500000, 400000, 10000, 5000, 200000,
                       30000, 15000, 25000, 50000, 20000, 1000, 500, 200, 150000,
                       10000, 510000)
        wb_previous = ("previous", 90, 70, 450000, 360000, 9000, 4500, 180000,
                        27000, 13000, 22000, 45000, 18000, 900, 450, 180, 135000,
                        9000, 459000)
        mock_wb.return_value = ([wb_current, wb_previous], [])

        # OZON row: period + 12 values
        ozon_current = ("current", 30, 150000, 120000, 5000, 2000, 50000,
                         60000, 10000, 5000, 8000, 15000, 6000)
        ozon_previous = ("previous", 25, 130000, 104000, 4000, 1500, 42000,
                          52000, 8000, 4000, 7000, 13000, 5000)
        mock_ozon.return_value = ([ozon_current, ozon_previous], [])

        result = collect_our_performance("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "our" in result
        our = result["our"]
        assert "current" in our
        assert "previous" in our
        assert "delta_pct" in our
        assert "revenue" in our["current"]
        assert "wb_revenue" in our["current"]
        assert "ozon_revenue" in our["current"]
        assert our["current"]["revenue"] == 500000 + 150000

    @patch("scripts.market_review.collectors.our_performance.get_ozon_finance")
    @patch("scripts.market_review.collectors.our_performance.get_wb_finance")
    def test_empty_db_response(self, mock_wb, mock_ozon):
        from scripts.market_review.collectors.our_performance import collect_our_performance

        mock_wb.return_value = ([], [])
        mock_ozon.return_value = ([], [])

        result = collect_our_performance("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "our" in result
        assert result["our"]["current"]["revenue"] == 0
        assert result["our"]["current"]["sales_count"] == 0


# ---------------------------------------------------------------------------
# competitors_brands
# ---------------------------------------------------------------------------

class TestCompetitorsBrands:

    @patch("scripts.market_review.collectors.competitors_brands.time.sleep")
    @patch("scripts.market_review.collectors.competitors_brands.MPStatsClient")
    def test_returns_expected_structure(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.competitors_brands import collect_competitors_brands

        client = _mock_mpstats_client()
        MockClient.return_value = client
        client.get_brand_trends.return_value = {"days": _make_days(7)}

        result = collect_competitors_brands("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "competitors" in result
        for brand_data in result["competitors"].values():
            assert "current" in brand_data
            assert "previous" in brand_data
            assert "delta_pct" in brand_data
            assert "segment" in brand_data
            assert "instagram" in brand_data
            assert "revenue" in brand_data["current"]
            assert "sku_count" in brand_data["current"]

    @patch("scripts.market_review.collectors.competitors_brands.time.sleep")
    @patch("scripts.market_review.collectors.competitors_brands.MPStatsClient")
    def test_empty_api_response(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.competitors_brands import collect_competitors_brands

        client = _mock_mpstats_client()
        MockClient.return_value = client
        client.get_brand_trends.return_value = {}

        result = collect_competitors_brands("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "competitors" in result
        for brand_data in result["competitors"].values():
            assert brand_data["current"]["revenue"] == 0


# ---------------------------------------------------------------------------
# top_models_ours
# ---------------------------------------------------------------------------

class TestTopModelsOurs:

    @patch("scripts.market_review.collectors.top_models_ours.MPStatsClient")
    def test_returns_note_when_no_skus(self, MockClient):
        from scripts.market_review.collectors.top_models_ours import collect_top_models_ours

        client = _mock_mpstats_client()
        MockClient.return_value = client

        result = collect_top_models_ours("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "our_models" in result
        # All OUR_TOP_MODELS have empty SKU lists
        for model_data in result["our_models"].values():
            assert model_data.get("note") == "no SKUs configured"
            assert model_data["current"]["revenue"] == 0

    @patch("scripts.market_review.collectors.top_models_ours.OUR_TOP_MODELS", {"TestModel": [12345, 67890]})
    @patch("scripts.market_review.collectors.top_models_ours.time.sleep")
    @patch("scripts.market_review.collectors.top_models_ours.MPStatsClient")
    def test_aggregates_multiple_skus(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.top_models_ours import collect_top_models_ours

        client = _mock_mpstats_client()
        MockClient.return_value = client
        # Each SKU: 7 days * 1000 = 7000 revenue, 7 * 10 = 70 sales
        client.get_item_sales.return_value = {"days": _make_days(7)}

        result = collect_top_models_ours("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        model = result["our_models"]["TestModel"]
        assert model["skus"] == [12345, 67890]
        # 2 SKUs * 7000 = 14000
        assert model["current"]["revenue"] == 14000
        assert model["current"]["sales"] == 140


# ---------------------------------------------------------------------------
# top_models_rivals
# ---------------------------------------------------------------------------

class TestTopModelsRivals:

    @patch("scripts.market_review.collectors.top_models_rivals.MPStatsClient")
    def test_returns_note_when_no_skus(self, MockClient):
        from scripts.market_review.collectors.top_models_rivals import collect_top_models_rivals

        client = _mock_mpstats_client()
        MockClient.return_value = client

        result = collect_top_models_rivals("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "rival_models" in result
        for model_data in result["rival_models"].values():
            assert model_data.get("note") == "no SKUs configured"
            assert model_data["analogs"] == []

    @patch("scripts.market_review.collectors.top_models_rivals.OUR_TOP_MODELS", {"TestModel": [12345]})
    @patch("scripts.market_review.collectors.top_models_rivals.time.sleep")
    @patch("scripts.market_review.collectors.top_models_rivals.MPStatsClient")
    def test_fetches_similar_and_sorts(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.top_models_rivals import collect_top_models_rivals

        client = _mock_mpstats_client()
        MockClient.return_value = client

        # Similar items response
        similar_items = [
            {"id": 111, "brand": "Brand A", "price": 1500, "rating": 4.5, "feedbacks": 100},
            {"id": 222, "brand": "Brand B", "price": 2000, "rating": 4.0, "feedbacks": 50},
            {"id": 333, "brand": "Brand C", "price": 1800, "rating": 4.2, "feedbacks": 75},
            {"id": 444, "brand": "Brand D", "price": 1200, "rating": 3.8, "feedbacks": 30},
        ]
        client.get_item_similar.return_value = {"data": similar_items}

        # Different revenues for each SKU to test sorting
        call_count = [0]
        def sales_side_effect(sku, d1, d2):
            call_count[0] += 1
            rev = {111: 5000, 222: 15000, 333: 10000, 444: 3000}.get(sku, 1000)
            return {"days": [{"revenue": rev, "sales": rev // 100}]}
        client.get_item_sales.side_effect = sales_side_effect

        result = collect_top_models_rivals("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        analogs = result["rival_models"]["TestModel"]["analogs"]
        assert len(analogs) == 3
        # Should be sorted by revenue: 222 (15000), 333 (10000), 111 (5000)
        assert analogs[0]["sku"] == 222
        assert analogs[1]["sku"] == 333
        assert analogs[2]["sku"] == 111


# ---------------------------------------------------------------------------
# new_items
# ---------------------------------------------------------------------------

class TestNewItems:

    @patch("scripts.market_review.collectors.new_items.time.sleep")
    @patch("scripts.market_review.collectors.new_items.MPStatsClient")
    def test_returns_expected_structure(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.new_items import collect_new_items

        client = _mock_mpstats_client()
        MockClient.return_value = client

        items = [
            {"id": 111, "brand": "BrandX", "name": "Item 1", "price": 2000,
             "revenue": 600000, "sales": 300, "first_seen": "2026-02-15",
             "rating": 4.5, "feedbacks": 100},
            {"id": 222, "brand": "BrandY", "name": "Item 2", "price": 1500,
             "revenue": 200000, "sales": 100, "first_seen": "2026-02-20",
             "rating": 4.0, "feedbacks": 50},  # below revenue threshold
        ]
        client._request.return_value = {"data": items}

        result = collect_new_items("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "new_items" in result
        # Item 111 passes revenue threshold (500k), returned once per category (4 categories)
        assert len(result["new_items"]) == 4
        assert all(item["sku"] == 111 for item in result["new_items"])
        assert result["new_items"][0]["category"] is not None

    @patch("scripts.market_review.collectors.new_items.time.sleep")
    @patch("scripts.market_review.collectors.new_items.MPStatsClient")
    def test_empty_api_response(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.new_items import collect_new_items

        client = _mock_mpstats_client()
        MockClient.return_value = client
        client._request.return_value = None

        result = collect_new_items("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        assert "new_items" in result
        assert result["new_items"] == []

    @patch("scripts.market_review.collectors.new_items.time.sleep")
    @patch("scripts.market_review.collectors.new_items.MPStatsClient")
    def test_filters_by_first_seen_date(self, MockClient, mock_sleep):
        from scripts.market_review.collectors.new_items import collect_new_items

        client = _mock_mpstats_client()
        MockClient.return_value = client

        items = [
            {"id": 111, "brand": "New", "name": "New item", "price": 2000,
             "revenue": 700000, "sales": 350, "first_seen": "2026-02-15",
             "rating": 4.5, "feedbacks": 100},
            {"id": 222, "brand": "Old", "name": "Old item", "price": 1800,
             "revenue": 800000, "sales": 400, "first_seen": "2025-12-01",
             "rating": 4.0, "feedbacks": 200},  # first_seen before prev_start
        ]
        client._request.return_value = {"data": items}

        result = collect_new_items("2026-03-01", "2026-03-31", "2026-02-01", "2026-02-28")

        # Only item 111 should pass (first_seen >= 2026-02-01), once per category (4)
        assert len(result["new_items"]) == 4
        assert all(item["sku"] == 111 for item in result["new_items"])
