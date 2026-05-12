"""Internal /spawn_recorder endpoint — auth + URL validation."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from services.telemost_recorder_api.internal_routes import (
    SpawnRequest,
    spawn_recorder,
)


def _fake_pool(fetchval_return):
    fake_pool = MagicMock()
    fake_conn = AsyncMock()
    fake_conn.fetchval.return_value = fetchval_return
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    ctx.__aexit__ = AsyncMock(return_value=None)
    fake_pool.acquire = MagicMock(return_value=ctx)
    return fake_pool


@pytest.mark.asyncio
async def test_spawn_recorder_rejects_when_key_not_set(monkeypatch):
    monkeypatch.delenv("TELEMOST_INTERNAL_KEY", raising=False)
    body = SpawnRequest(
        meeting_url="https://telemost.360.yandex.ru/j/abc",
        triggered_by=111,
    )
    with pytest.raises(HTTPException) as exc:
        await spawn_recorder(body, x_api_key="anything")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_spawn_recorder_rejects_bad_key(monkeypatch):
    monkeypatch.setenv("TELEMOST_INTERNAL_KEY", "secret")
    body = SpawnRequest(
        meeting_url="https://telemost.360.yandex.ru/j/abc",
        triggered_by=111,
    )
    with pytest.raises(HTTPException) as exc:
        await spawn_recorder(body, x_api_key="wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_spawn_recorder_rejects_invalid_url(monkeypatch):
    monkeypatch.setenv("TELEMOST_INTERNAL_KEY", "secret")
    body = SpawnRequest(meeting_url="https://google.com", triggered_by=111)
    with pytest.raises(HTTPException) as exc:
        await spawn_recorder(body, x_api_key="secret")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_spawn_recorder_enqueues_on_happy_path(monkeypatch):
    monkeypatch.setenv("TELEMOST_INTERNAL_KEY", "secret")
    fake_uuid = uuid4()
    pool = _fake_pool(fake_uuid)
    body = SpawnRequest(
        meeting_url="https://telemost.360.yandex.ru/j/abc",
        triggered_by=111,
    )
    with patch(
        "services.telemost_recorder_api.internal_routes.get_pool",
        AsyncMock(return_value=pool),
    ):
        result = await spawn_recorder(body, x_api_key="secret")

    assert result == {"meeting_id": str(fake_uuid), "status": "queued"}
