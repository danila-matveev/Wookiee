"""Tests for WBClient.get_seller_chats() method."""
from unittest.mock import patch, MagicMock
import pytest

from shared.clients.wb_client import WBClient


@pytest.fixture
def client():
    with patch("shared.clients.wb_client.httpx.Client"):
        return WBClient(api_key="test-key", cabinet_name="test")


class TestGetSellerChats:
    """Tests for get_seller_chats method."""

    def test_method_exists(self, client):
        """WBClient should have get_seller_chats method."""
        assert hasattr(client, "get_seller_chats")
        assert callable(client.get_seller_chats)

    def test_returns_list(self, client):
        """get_seller_chats should return a list."""
        with patch.object(client, "_request", return_value={"chats": []}):
            result = client.get_seller_chats()
            assert isinstance(result, list)

    def test_returns_chats_from_response(self, client):
        """Should extract chats from API response."""
        chat_data = [
            {
                "chatId": "abc123",
                "createdAt": "2026-01-15T10:00:00Z",
                "messages": [
                    {"text": "Здравствуйте, подскажите размер", "direction": "in"},
                    {"text": "Добрый день! Рекомендуем размер M", "direction": "out"},
                ],
            }
        ]
        with patch.object(client, "_request", return_value={"chats": chat_data}):
            result = client.get_seller_chats()
            assert len(result) == 1
            assert result[0]["chatId"] == "abc123"
            assert len(result[0]["messages"]) == 2

    def test_empty_response(self, client):
        """Should return empty list when no chats."""
        with patch.object(client, "_request", return_value={"chats": []}):
            result = client.get_seller_chats()
            assert result == []

    def test_pagination(self, client):
        """Should paginate when batch equals limit."""
        batch1 = [{"chatId": f"chat-{i}"} for i in range(1000)]
        batch2 = [{"chatId": "chat-last"}]

        with patch.object(
            client, "_request", side_effect=[{"chats": batch1}, {"chats": batch2}]
        ):
            result = client.get_seller_chats()
            assert len(result) == 1001

    def test_stops_on_none_response(self, client):
        """Should stop and return empty list when _request returns None."""
        with patch.object(client, "_request", return_value=None):
            result = client.get_seller_chats()
            assert result == []

    def test_date_from_param(self, client):
        """Should pass dateFrom parameter when provided."""
        with patch.object(client, "_request", return_value={"chats": []}) as mock_req:
            client.get_seller_chats(date_from="2026-01-01")
            call_args = mock_req.call_args
            assert "dateFrom=2026-01-01" in call_args[0][1]
