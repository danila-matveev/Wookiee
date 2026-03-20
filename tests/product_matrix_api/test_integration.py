# tests/product_matrix_api/test_integration.py
"""Smoke tests for Product Matrix API endpoints (mock DB)."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_all_routes_registered():
    """Verify all expected route prefixes are registered."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Health
        r = await ac.get("/health")
        assert r.status_code == 200

        # Models route exists
        r = await ac.get("/api/matrix/models")
        assert r.status_code != 404, "Models route not found"

        # Lookups route exists
        r = await ac.get("/api/matrix/lookups/kategorii")
        assert r.status_code != 404, "Lookups route not found"

        # OpenAPI docs
        r = await ac.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "Product Matrix API" in spec["info"]["title"]
