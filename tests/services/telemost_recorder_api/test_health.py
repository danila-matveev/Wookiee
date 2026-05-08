"""Tests for the /health route + app factory."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from services.telemost_recorder_api.app import create_app


class _FakeConn:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def fetchval(self, query: str):
        if self._fail:
            raise RuntimeError("db unreachable")
        if "queued" in query:
            return 3
        if "recording" in query:
            return 1
        return 1  # SELECT 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _FakePool:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    def acquire(self):
        return _FakeConn(self._fail)


def test_health_returns_ok_when_db_reachable():
    with patch(
        "services.telemost_recorder_api.routes.health.get_pool",
        AsyncMock(return_value=_FakePool()),
    ), patch(
        "services.telemost_recorder_api.app.get_pool",
        AsyncMock(return_value=_FakePool()),
    ), patch(
        "services.telemost_recorder_api.app.close_pool",
        AsyncMock(),
    ), patch(
        "services.telemost_recorder_api.app.recorder_loop",
        AsyncMock(return_value=None),
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body
    assert body["checks"]["db_ping_ms"] >= 0
    assert body["checks"]["queue_size"] == 3
    assert body["checks"]["recording_count"] == 1


def test_health_returns_down_when_db_fails():
    async def boom(*_a, **_kw):
        raise RuntimeError("db unreachable")

    with patch(
        "services.telemost_recorder_api.routes.health.get_pool",
        AsyncMock(side_effect=boom),
    ), patch(
        "services.telemost_recorder_api.app.get_pool",
        AsyncMock(return_value=_FakePool()),
    ), patch(
        "services.telemost_recorder_api.app.close_pool",
        AsyncMock(),
    ), patch(
        "services.telemost_recorder_api.app.recorder_loop",
        AsyncMock(return_value=None),
    ):
        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "down"


def test_create_app_returns_fastapi_with_health_route():
    """Smoke test: app exposes /health and only /health for now."""
    with patch(
        "services.telemost_recorder_api.app.get_pool",
        AsyncMock(return_value=_FakePool()),
    ), patch(
        "services.telemost_recorder_api.app.close_pool",
        AsyncMock(),
    ), patch(
        "services.telemost_recorder_api.app.recorder_loop",
        AsyncMock(return_value=None),
    ):
        app = create_app()

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/health" in paths
