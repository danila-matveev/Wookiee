"""Tests for admin routes (logs, stats, health)."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_admin_health_returns_ok():
    """GET /api/matrix/admin/health returns ok."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 1

        resp = client.get("/api/matrix/admin/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_admin_logs_returns_200():
    """GET /api/matrix/admin/logs returns paginated audit log."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        resp = client.get("/api/matrix/admin/logs")
        assert resp.status_code == 200


def test_admin_stats_returns_200():
    """GET /api/matrix/admin/stats returns DB statistics."""
    with patch("services.product_matrix_api.routes.admin.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.fetchall.return_value = []

        resp = client.get("/api/matrix/admin/stats")
        assert resp.status_code == 200
