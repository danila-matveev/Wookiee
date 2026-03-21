"""Tests for two-step delete route (428 challenge → archive)."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_delete_without_challenge_returns_428():
    """Step 1: DELETE without X-Confirm-Challenge returns 428 with challenge."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.delete.ValidationService") as mock_vs, \
         patch("services.product_matrix_api.routes.delete.ArchiveService") as mock_as:

        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "id": 1, "kod": "WK-001"
        }

        mock_vs.check_delete_impact.return_value = {
            "strategy": "cascade_archive",
            "children": {"modeli": 2},
            "blocked_by": None,
        }
        mock_vs.generate_challenge.return_value = ("5 × 3", "hash123", "salt123")
        mock_as.build_impact_message.return_value = "Будут архивированы: 2 подмоделей"

        resp = client.delete("/api/matrix/modeli_osnova/1")
        assert resp.status_code == 428
        data = resp.json()
        assert data["requires_confirmation"] is True
        assert "challenge" in data
        assert "impact" in data


def test_delete_blocked_returns_409():
    """block_if_active entities return 409 Conflict."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.delete.ValidationService") as mock_vs, \
         patch("services.product_matrix_api.routes.delete.ArchiveService") as mock_as:

        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "id": 5, "color_code": "BLK"
        }

        mock_vs.check_delete_impact.return_value = {
            "strategy": "block_if_active",
            "children": {},
            "blocked_by": {"artikuly": 12},
        }
        mock_as.build_impact_message.return_value = "Нельзя удалить"

        resp = client.delete("/api/matrix/cveta/5")
        assert resp.status_code == 409


def test_delete_not_found_returns_404():
    """DELETE on non-existent record returns 404."""
    with patch("services.product_matrix_api.routes.delete.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        resp = client.delete("/api/matrix/modeli_osnova/99999")
        assert resp.status_code == 404
