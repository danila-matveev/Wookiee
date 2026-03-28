"""Smoke tests for all Phase 3 API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/articles",
    "/api/matrix/products",
    "/api/matrix/colors",
    "/api/matrix/factories",
    "/api/matrix/importers",
    "/api/matrix/cards-wb",
    "/api/matrix/cards-ozon",
    "/api/matrix/certs",
])
async def test_entity_list_routes(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code != 404, f"Route {path} not registered"


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/articles/999999",
    "/api/matrix/products/999999",
    "/api/matrix/colors/999999",
    "/api/matrix/factories/999999",
    "/api/matrix/importers/999999",
    "/api/matrix/cards-wb/999999",
    "/api/matrix/cards-ozon/999999",
    "/api/matrix/certs/999999",
])
async def test_entity_get_404(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code == 404


@pytest.mark.anyio
@pytest.mark.skip(reason="Requires migration 004 (status_id on modeli_osnova) to be applied on DB first")
async def test_search_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/search?q=test")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "total" in data
    assert "by_entity" in data


@pytest.mark.anyio
async def test_search_requires_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/search")
    assert r.status_code == 422, "Should require 'q' parameter"


@pytest.mark.anyio
async def test_bulk_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/bulk/modeli_osnova",
            json={"ids": [], "action": "update", "changes": {}},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_bulk_unknown_entity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/bulk/unknown_entity",
            json={"ids": [1], "action": "update", "changes": {}},
        )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_openapi_includes_all_tags():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = list(spec["paths"].keys())
    expected_prefixes = [
        "/api/matrix/articles",
        "/api/matrix/products",
        "/api/matrix/colors",
        "/api/matrix/factories",
        "/api/matrix/importers",
        "/api/matrix/cards-wb",
        "/api/matrix/cards-ozon",
        "/api/matrix/certs",
        "/api/matrix/search",
        "/api/matrix/bulk",
    ]
    for prefix in expected_prefixes:
        assert any(p.startswith(prefix) for p in paths), f"Missing route prefix: {prefix}"
