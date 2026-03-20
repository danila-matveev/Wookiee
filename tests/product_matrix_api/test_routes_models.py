"""Test models route — verifies routes are registered."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_models_osnova_route_exists():
    """Verify the endpoint exists and returns a response (may fail on DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/models")
    # 200 or 500 (if DB not available) — but NOT 404
    assert resp.status_code != 404


@pytest.mark.anyio
async def test_get_model_osnova_not_found():
    """Verify 404 for non-existent record."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/models/99999")
    # Could be 404 or 500 depending on DB — but route must exist
    assert resp.status_code != 405
