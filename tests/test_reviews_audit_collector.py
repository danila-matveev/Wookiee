"""Tests for reviews audit data collection."""
import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from unittest.mock import patch, MagicMock


class TestGetWbBuyoutsReturnsByModel:
    """Tests for get_wb_buyouts_returns_by_model function."""

    def test_function_exists(self):
        """Function should be importable from data_layer."""
        from shared.data_layer import get_wb_buyouts_returns_by_model
        assert callable(get_wb_buyouts_returns_by_model)

    def test_returns_list(self):
        """Should return a list of tuples."""
        from shared.data_layer import get_wb_buyouts_returns_by_model

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("current", "wendy", 100, 85, 15),
            ("current", "lola", 50, 45, 5),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "shared.data_layer.finance._get_wb_connection", return_value=mock_conn
        ):
            result = get_wb_buyouts_returns_by_model(
                "2026-03-01", "2026-02-01", "2026-04-01"
            )
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0][0] == "current"
            assert result[0][1] == "wendy"


class TestCollectData:
    """Tests for the data collection script."""

    def test_script_importable(self):
        """Collector module should be importable."""
        from scripts.reviews_audit.collect_data import collect_reviews_data
        assert callable(collect_reviews_data)

    def test_output_structure(self):
        """Output JSON should have expected top-level keys."""
        from scripts.reviews_audit.collect_data import collect_reviews_data

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            mock_feedbacks = [
                {
                    "id": "fb1",
                    "text": "Отличное белье!",
                    "productValuation": 5,
                    "createdDate": "2026-03-15T10:00:00Z",
                    "answer": {"text": "Спасибо!"},
                    "productDetails": {"nmId": 12345},
                }
            ]
            mock_questions = [
                {
                    "id": "q1",
                    "text": "Какой размер выбрать?",
                    "createdDate": "2026-03-16T10:00:00Z",
                    "answer": {"text": "Рекомендуем M"},
                    "productDetails": {"nmId": 12345},
                }
            ]
            mock_chats = []
            mock_orders = [("current", "wendy", 100, 85, 15)]

            with patch(
                "scripts.reviews_audit.collect_data.WBClient"
            ) as MockClient, patch(
                "scripts.reviews_audit.collect_data.get_wb_buyouts_returns_by_model",
                return_value=mock_orders,
            ):
                instance = MockClient.return_value
                instance.get_all_feedbacks.return_value = mock_feedbacks
                instance.get_all_questions.return_value = mock_questions
                instance.get_seller_chats.return_value = mock_chats

                collect_reviews_data(
                    date_from="2026-03-01",
                    date_to="2026-04-01",
                    output_path=output_path,
                )

            with open(output_path) as f:
                data = json.load(f)

            assert "feedbacks" in data
            assert "questions" in data
            assert "chats" in data
            assert "orders_stats" in data
            assert "metadata" in data
            assert data["metadata"]["date_from"] == "2026-03-01"
            assert data["metadata"]["date_to"] == "2026-04-01"
            assert len(data["feedbacks"]) == 1
            assert len(data["questions"]) == 1
        finally:
            os.unlink(output_path)


class TestGetWbBuyoutsReturnsByArtikul:
    """Tests for get_wb_buyouts_returns_by_artikul function."""

    def test_function_exists(self):
        from shared.data_layer import get_wb_buyouts_returns_by_artikul
        assert callable(get_wb_buyouts_returns_by_artikul)

    def test_returns_list(self):
        from shared.data_layer import get_wb_buyouts_returns_by_artikul

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("wendy", "wendy/розовый", 50, 40, 10),
            ("wendy", "wendy/чёрный", 30, 25, 5),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "shared.data_layer.finance._get_wb_connection", return_value=mock_conn
        ):
            result = get_wb_buyouts_returns_by_artikul("2025-04-07", "2026-04-07")
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0][0] == "wendy"
            assert result[0][1] == "wendy/розовый"
            assert result[0][2] == 50
            assert result[0][3] == 40
            assert result[0][4] == 10


class TestFilterByDate:
    """Tests for _filter_by_date helper."""

    def test_filters_within_range(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [
            {"createdDate": "2026-01-15T10:00:00Z"},
            {"createdDate": "2026-02-15T10:00:00Z"},
            {"createdDate": "2026-03-15T10:00:00Z"},
            {"createdDate": "2026-04-15T10:00:00Z"},
        ]
        result = _filter_by_date(items, "2026-02-01", "2026-04-01")
        assert len(result) == 2
        assert result[0]["createdDate"].startswith("2026-02")
        assert result[1]["createdDate"].startswith("2026-03")

    def test_empty_input(self):
        from scripts.reviews_audit.collect_data import _filter_by_date
        assert _filter_by_date([], "2026-01-01", "2026-12-31") == []

    def test_no_matches(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"createdDate": "2025-01-01T10:00:00Z"}]
        result = _filter_by_date(items, "2026-01-01", "2026-12-31")
        assert result == []

    def test_custom_date_field(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"createdAt": "2026-03-15T10:00:00Z"}]
        result = _filter_by_date(items, "2026-03-01", "2026-04-01", date_field="createdAt")
        assert len(result) == 1

    def test_missing_date_field_skipped(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"text": "no date here"}]
        result = _filter_by_date(items, "2026-01-01", "2026-12-31")
        assert result == []
