"""Tests for reviews audit data collection."""
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
