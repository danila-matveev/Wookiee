"""Tests for saved views CRUD routes."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_views():
    """GET /api/matrix/views?entity_type=modeli_osnova → 200, list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/views", params={"entity_type": "modeli_osnova"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_list_views_requires_entity():
    """GET /api/matrix/views (no param) → 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/views")
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_view():
    """POST /api/matrix/views with valid body → not 404/405."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/views",
            json={
                "entity_type": "modeli_osnova",
                "name": "Test View",
                "config": {"columns": ["kod"], "filters": [], "sort": [], "group_by": None},
            },
        )
    assert r.status_code not in (404, 405), f"Route not registered, got {r.status_code}"


@pytest.mark.anyio
async def test_update_view_route_exists():
    """PATCH /api/matrix/views/999 → not 405."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.patch(
            "/api/matrix/views/999",
            json={"name": "Updated"},
        )
    assert r.status_code != 405, f"PATCH route not registered, got {r.status_code}"


@pytest.mark.anyio
async def test_delete_view_route_exists():
    """DELETE /api/matrix/views/999 → not 405."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete("/api/matrix/views/999")
    assert r.status_code != 405, f"DELETE route not registered, got {r.status_code}"
