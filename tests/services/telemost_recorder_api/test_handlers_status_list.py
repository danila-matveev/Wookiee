"""Tests for /status and /list commands."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _msg(text: str, user_id: int = 555) -> dict:
    return {
        "message": {
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "text": text,
        },
    }


_USER = {"telegram_id": 555, "name": "X", "short_name": "X", "is_active": True}


@pytest.mark.asyncio
async def test_status_shows_active_and_recent():
    rows = [
        {
            "id": UUID("11111111-1111-1111-1111-111111111111"),
            "status": "recording",
            "title": "Дейли",
            "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
            "ended_at": None,
        },
        {
            "id": UUID("22222222-2222-2222-2222-222222222222"),
            "status": "done",
            "title": "Бренд-стратегия",
            "started_at": datetime(2026, 5, 7, 14, 0, tzinfo=timezone.utc),
            "ended_at": datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc),
        },
    ]

    class FakeConn:
        async def fetch(self, query, *args):
            return rows

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.status.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.status.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.status.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/status"))

    assert sent
    assert "Дейли" in sent[0]
    assert "recording" in sent[0]
    assert "Бренд-стратегия" in sent[0]


@pytest.mark.asyncio
async def test_status_empty():
    class FakeConn:
        async def fetch(self, query, *args):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.status.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.status.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.status.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/status"))

    assert sent
    assert "нет" in sent[0].lower() or "пусто" in sent[0].lower()


@pytest.mark.asyncio
async def test_status_unauthed_says_start():
    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.status.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.status.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/status"))
    assert sent
    assert "/start" in sent[0].lower()


@pytest.mark.asyncio
async def test_list_uses_privacy_filter():
    captured: list = []

    class FakeConn:
        async def fetch(self, query, *args):
            captured.append((query, args))
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/list"))

    q, args = captured[0]
    assert "triggered_by" in q
    assert "organizer_id" in q
    assert "invitees" in q
    assert args[0] == 555


@pytest.mark.asyncio
async def test_list_empty_returns_friendly():
    class FakeConn:
        async def fetch(self, query, *args):
            return []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.list_meetings.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/list"))

    assert sent
    assert "не нашёл" in sent[0].lower() or "нет" in sent[0].lower()
