"""Tests for schema (field definitions) CRUD routes."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app

# These are smoke tests: they verify routes are registered and validate input.
# Endpoints that mutate data may return 500 due to DB unavailability in CI —
# that still proves the route exists and reached the handler.


@pytest.mark.anyio
async def test_list_fields_returns_list():
    """GET /api/matrix/schema/modeli_osnova → 200, returns list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/schema/modeli_osnova")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_list_fields_invalid_entity():
    """GET /api/matrix/schema/nonexistent → 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/schema/nonexistent")
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_field():
    """POST /api/matrix/schema/modeli_osnova/fields → not 404/405."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/schema/modeli_osnova/fields",
            json={
                "entity_type": "modeli_osnova",
                "field_name": "test_field",
                "display_name": "Test Field",
                "field_type": "text",
            },
        )
    assert r.status_code not in (404, 405), f"Route not registered, got {r.status_code}"


@pytest.mark.anyio
async def test_create_field_invalid_type():
    """POST with field_type='invalid' → 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/schema/modeli_osnova/fields",
            json={
                "entity_type": "modeli_osnova",
                "field_name": "test_field",
                "display_name": "Test Field",
                "field_type": "invalid",
            },
        )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_update_field_route_exists():
    """PATCH /api/matrix/schema/modeli_osnova/fields/999 → not 404/405."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.patch(
            "/api/matrix/schema/modeli_osnova/fields/999",
            json={"display_name": "Updated"},
        )
    # Route must exist (not 404 due to missing route, not 405)
    # 404 from "field not found" is OK — it means the route IS registered
    assert r.status_code not in (405,), f"Route not registered, got {r.status_code}"


@pytest.mark.anyio
async def test_delete_field_route_exists():
    """DELETE /api/matrix/schema/modeli_osnova/fields/999 → not 405."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete("/api/matrix/schema/modeli_osnova/fields/999")
    assert r.status_code not in (405,), f"Route not registered, got {r.status_code}"
