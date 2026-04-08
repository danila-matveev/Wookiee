"""Tests for WBClient.get_return_claims() method."""
from unittest.mock import patch
import pytest

from shared.clients.wb_client import WBClient


@pytest.fixture
def client():
    with patch("shared.clients.wb_client.httpx.Client"):
        return WBClient(api_key="test-key", cabinet_name="test")


class TestGetReturnClaims:
    def test_method_exists(self, client):
        assert hasattr(client, "get_return_claims")
        assert callable(client.get_return_claims)

    def test_returns_list(self, client):
        with patch.object(client, "_request", return_value={"claims": []}):
            result = client.get_return_claims()
            assert isinstance(result, list)

    def test_returns_claims_from_response(self, client):
        claims_data = [
            {
                "id": "claim-001",
                "nm_id": 12345,
                "dt": "2026-04-01T10:00:00Z",
                "order_dt": "2026-03-20T08:00:00Z",
                "status": "new",
                "status_ex": "",
                "claim_type": "refund",
                "user_comment": "Товар не подошёл по размеру",
                "wb_comment": "",
                "imt_name": "Платье Wendy",
                "photos": ["https://photo1.jpg"],
            }
        ]
        with patch.object(client, "_request", return_value={"claims": claims_data}):
            result = client.get_return_claims()
            assert len(result) == 1
            assert result[0]["id"] == "claim-001"
            assert result[0]["nm_id"] == 12345
            assert len(result[0]["photos"]) == 1

    def test_empty_response(self, client):
        with patch.object(client, "_request", return_value={"claims": []}):
            result = client.get_return_claims()
            assert result == []

    def test_none_response(self, client):
        with patch.object(client, "_request", return_value=None):
            result = client.get_return_claims()
            assert result == []

    def test_uses_returns_base_url(self, client):
        with patch.object(client, "_request", return_value={"claims": []}) as mock_req:
            client.get_return_claims()
            call_url = mock_req.call_args[0][1]
            assert "returns-api.wildberries.ru" in call_url
            assert "/api/v1/claims" in call_url
            assert "is_archive=false" in call_url

    def test_returns_base_constant(self):
        assert hasattr(WBClient, "RETURNS_BASE")
        assert WBClient.RETURNS_BASE == "https://returns-api.wildberries.ru"
