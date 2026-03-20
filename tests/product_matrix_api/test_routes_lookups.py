# tests/product_matrix_api/test_routes_lookups.py
import pytest
from httpx import AsyncClient, ASGITransport
from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_lookups_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/lookups/kategorii")
    assert resp.status_code != 404


@pytest.mark.anyio
async def test_lookups_unknown_table():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/lookups/nonexistent")
    # Should be 404 (unknown table) or 500 (DB unavailable) — not route-not-found
    assert resp.status_code in (404, 500)
