"""Repo helpers: load by short id, delete with ownership check, transcript text."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.meetings_repo import (
    build_transcript_text,
    delete_meeting_for_owner,
    load_meeting_by_short_id,
)


def _fake_pool(fake_conn):
    """Build a pool whose acquire() returns an async context manager around fake_conn.
    Matches the pattern used in test_bitrix_calendar.py (asyncpg's PoolAcquireContext
    is a sync ctx manager with async __aenter__/__aexit__)."""
    fake_pool = MagicMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_pool.acquire = MagicMock(return_value=acquire_ctx)
    return fake_pool


@pytest.mark.asyncio
async def test_load_by_short_id_returns_row_if_owner_matches():
    mid = uuid4()
    row = {"id": mid, "title": "X", "triggered_by": 111, "status": "done"}
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = row
    fake_pool = _fake_pool(fake_conn)

    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        got = await load_meeting_by_short_id(str(mid)[:8], owner_telegram_id=111)
    assert got["id"] == mid


@pytest.mark.asyncio
async def test_load_by_short_id_returns_none_if_not_found():
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = None
    fake_pool = _fake_pool(fake_conn)
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        got = await load_meeting_by_short_id("00000000", owner_telegram_id=111)
    assert got is None


@pytest.mark.asyncio
async def test_delete_meeting_blocks_when_active():
    mid = uuid4()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = {"id": mid, "status": "recording", "triggered_by": 111}
    fake_pool = _fake_pool(fake_conn)
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        ok = await delete_meeting_for_owner(mid, owner_telegram_id=111)
    assert ok is False


@pytest.mark.asyncio
async def test_delete_meeting_succeeds_when_done():
    mid = uuid4()
    fake_conn = AsyncMock()
    fake_conn.fetchrow.return_value = {"id": mid, "status": "done", "triggered_by": 111}
    fake_pool = _fake_pool(fake_conn)
    with patch(
        "services.telemost_recorder_api.meetings_repo.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        ok = await delete_meeting_for_owner(mid, owner_telegram_id=111)
    assert ok is True
    fake_conn.execute.assert_called_once()
    sql = fake_conn.execute.call_args.args[0]
    assert "deleted_at" in sql


def test_build_transcript_text_renders():
    text = build_transcript_text([
        {"start_ms": 0, "speaker": "Иван", "text": "Привет"},
        {"start_ms": 65000, "speaker": "Алина", "text": "Хай"},
    ])
    assert "[00:00] Иван: Привет" in text
    assert "[01:05] Алина: Хай" in text


def test_build_transcript_text_empty():
    assert build_transcript_text([]) == "(пустой transcript)"
