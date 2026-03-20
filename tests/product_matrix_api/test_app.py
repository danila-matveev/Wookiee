import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.anyio
async def test_cors_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.options(
            "/health",
            headers={"Origin": "http://localhost:25000", "Access-Control-Request-Method": "GET"},
        )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
