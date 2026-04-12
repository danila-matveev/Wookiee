"""Tests for MPStats API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from shared.clients.mpstats_client import MPStatsClient


@pytest.fixture
def client():
    c = MPStatsClient(token="test-token-123")
    yield c
    c.close()


class TestClientInit:
    def test_init_with_token(self, client: MPStatsClient):
        assert client.token == "test-token-123"

    def test_base_url(self, client: MPStatsClient):
        assert client.BASE_URL == "https://mpstats.io/api/wb"


class TestGetCategoryTrends:
    def test_returns_trend_data(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"category": "shoes", "sales": 1000}],
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.get_category_trends("shoes", "2026-01-01", "2026-01-31")

        assert result == {"data": [{"category": "shoes", "sales": 1000}]}


class TestGetBrandTrends:
    def test_returns_brand_data(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "brands": [{"name": "Wookiee", "revenue": 50000}],
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.get_brand_trends("shoes", "2026-01-01", "2026-01-31")

        assert result == {"brands": [{"name": "Wookiee", "revenue": 50000}]}


class TestGetItemSales:
    def test_returns_item_sales(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sales": [{"date": "2026-01-01", "qty": 10}],
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.get_item_sales(12345, "2026-01-01", "2026-01-31")

        assert result == {"sales": [{"date": "2026-01-01", "qty": 10}]}


class TestGetItemSimilar:
    def test_returns_similar_items(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "similar": [{"sku": 99999, "name": "Similar Item"}],
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.get_item_similar(12345)

        assert result == {"similar": [{"sku": 99999, "name": "Similar Item"}]}


class TestGetItemInfo:
    def test_returns_item_info(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345, "name": "Test Item", "brand": "Wookiee",
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.get_item_info(12345)

        assert result == {"id": 12345, "name": "Test Item", "brand": "Wookiee"}


class TestSearchBrands:
    def test_returns_brand_list(self, client: MPStatsClient):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"name": "Birka Art", "revenue": 3000000}],
        }

        with patch.object(client.client, "request", return_value=mock_response):
            result = client.search_brands("Birka")

        assert result == {"data": [{"name": "Birka Art", "revenue": 3000000}]}


class TestRetryOn429:
    @patch("shared.clients.mpstats_client.time.sleep")
    def test_retries_on_rate_limit(self, mock_sleep, client: MPStatsClient):
        response_429 = MagicMock()
        response_429.status_code = 429

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.json.return_value = {"ok": True}

        with patch.object(
            client.client,
            "request",
            side_effect=[response_429, response_200],
        ):
            result = client.get_item_info(12345)

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(30)  # 30s * attempt 1
