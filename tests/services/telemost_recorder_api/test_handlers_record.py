"""Tests for /record command."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

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


_AUTHED_USER = {
    "telegram_id": 555,
    "name": "Полина",
    "short_name": "Полина",
    "is_active": True,
}


@pytest.mark.asyncio
async def test_record_rejects_unknown_user():
    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))
    assert sent
    assert "/start" in sent[0].lower() or "не нашёл" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_no_args_shows_usage():
    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record"))
    assert any("/record <" in s for s in sent)


@pytest.mark.asyncio
async def test_record_rejects_invalid_url():
    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record not-a-url"))
    assert sent
    assert "ссылк" in sent[0].lower() or "telemost" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_enqueues_meeting():
    new_id = uuid4()
    sent: list[str] = []

    class FakeConn:
        async def fetchval(self, query: str, *args):
            assert "INSERT" in query.upper()
            return new_id

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(
            _msg("/record https://telemost.360.yandex.ru/j/abc")
        )
    # Confirmation should mention the new id (truncated) and that it's queued
    assert any(str(new_id)[:8] in s for s in sent)
    assert any("очередь" in s.lower() for s in sent)


@pytest.mark.asyncio
async def test_record_duplicate_concurrent_returns_already():
    sent: list[str] = []

    class FakeConn:
        async def fetchval(self, query: str, *args):
            return None  # ON CONFLICT DO NOTHING

        async def fetchrow(self, query: str, *args):
            return {
                "id": UUID("11111111-1111-1111-1111-111111111111"),
                "status": "recording",
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))
    assert sent
    assert "уже" in sent[0].lower()
    assert "recording" in sent[0]


@pytest.mark.asyncio
async def test_record_strips_whitespace_and_extra_args():
    """`/record   <url>   extra-text` should still parse the URL correctly."""
    new_id = uuid4()
    sent: list[str] = []

    class FakeConn:
        async def fetchval(self, query: str, *args):
            return new_id

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/record   https://telemost.yandex.ru/j/abc   trailing"))
    assert sent
    assert str(new_id)[:8] in sent[0]
