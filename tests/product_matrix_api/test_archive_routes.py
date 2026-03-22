"""Tests for archive CRUD routes."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.product_matrix_api.app import app

client = TestClient(app)


def test_list_archive_returns_200():
    """GET /api/matrix/archive returns paginated list."""
    with patch("services.product_matrix_api.routes.archive.get_db") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_session.execute.return_value.scalar.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        resp = client.get("/api/matrix/archive")
        assert resp.status_code == 200


def test_restore_not_found_returns_404():
    """POST /api/matrix/archive/99999/restore returns 404 for missing archive."""
    with patch("services.product_matrix_api.routes.archive.get_db") as mock_db, \
         patch("services.product_matrix_api.routes.archive.ArchiveService") as mock_as:

        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_as.restore_record.side_effect = ValueError("Archive record #99999 not found")

        resp = client.post("/api/matrix/archive/99999/restore")
        assert resp.status_code == 404
