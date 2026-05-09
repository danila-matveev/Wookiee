"""Tests for /start and /help command handlers + plain-text dispatch."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _msg(text: str, user_id: int = 555) -> dict:
    return {
        "message": {
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False, "first_name": "Test"},
            "text": text,
        },
    }


class _EmptyConn:
    async def fetch(self, query, *args):
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class _EmptyPool:
    def acquire(self):
        return _EmptyConn()


@pytest.mark.asyncio
async def test_start_known_user_gets_welcome_with_keyboard():
    sent: list[tuple[int, str, dict | None]] = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value={
            "telegram_id": 555,
            "name": "Полина Ермилова",
            "short_name": "Полина",
            "is_active": True,
        }),
    ), patch(
        "services.telemost_recorder_api.handlers.start.get_pool",
        AsyncMock(return_value=_EmptyPool()),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append((chat_id, text, kw.get("reply_markup")))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    chat_id, text, markup = sent[0]
    assert chat_id == 555
    assert "Полина" in text
    assert "Wookiee Recorder" in text
    assert "/record" in text
    # Inline keyboard with 3 navigation buttons
    assert markup is not None
    buttons = [b for row in markup["inline_keyboard"] for b in row]
    assert any(b.get("callback_data") == "menu:list" for b in buttons)
    assert any(b.get("callback_data") == "menu:status" for b in buttons)
    assert any(b.get("callback_data") == "menu:help" for b in buttons)


@pytest.mark.asyncio
async def test_start_known_user_with_active_recording_shows_banner():
    from datetime import datetime, timezone
    from uuid import UUID

    active_row = {
        "id": UUID("11111111-1111-1111-1111-111111111111"),
        "title": "Дейли",
        "started_at": datetime(2026, 5, 9, 10, 0, tzinfo=timezone.utc),
        "status": "recording",
    }

    class FakeConn:
        async def fetch(self, query, *args):
            return [active_row]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value={"telegram_id": 555, "name": "X", "short_name": "X", "is_active": True}),
    ), patch(
        "services.telemost_recorder_api.handlers.start.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    assert "Сейчас в работе" in sent[0]
    assert "Дейли" in sent[0]
    assert "🔴" in sent[0]


@pytest.mark.asyncio
async def test_start_unknown_user_gets_auth_instructions_with_contact_button():
    sent: list[tuple[str, dict | None]] = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **kw: sent.append((t, kw.get("reply_markup")))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    text, markup = sent[0]
    assert "Bitrix24" in text
    assert "Telegram" in text
    assert markup is not None
    buttons = [b for row in markup["inline_keyboard"] for b in row]
    assert any("matveev_danila" in (b.get("url") or "") for b in buttons)


@pytest.mark.asyncio
async def test_help_returns_command_list():
    sent: list[str] = []
    with patch(
        "services.telemost_recorder_api.handlers.help.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append(text)),
    ):
        await handle_update(_msg("/help"))
    assert len(sent) == 1
    assert "/record" in sent[0]
    assert "/status" in sent[0]
    assert "/list" in sent[0]


@pytest.mark.asyncio
async def test_unknown_command_no_action():
    """Unknown slash-commands are silently ignored — no spam."""
    sent: list = []

    async def fake_send(chat_id, text, **kw):
        sent.append((chat_id, text))

    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.help.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_update(_msg("/unknown_command"))
    assert sent == []


@pytest.mark.asyncio
async def test_command_with_at_bot_username_is_normalized():
    """Telegram sometimes sends '/start@wookiee_recorder_bot' in groups."""
    sent: list = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value={
            "telegram_id": 555,
            "name": "X",
            "short_name": "X",
            "is_active": True,
        }),
    ), patch(
        "services.telemost_recorder_api.handlers.start.get_pool",
        AsyncMock(return_value=_EmptyPool()),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/start@wookiee_recorder_bot"))
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_bare_telemost_url_routes_to_record():
    """If user sends a Telemost link without /record, treat it as /record <link>."""
    forwarded: list = []

    async def fake_record(chat_id, user_id, args):
        forwarded.append((chat_id, user_id, args))

    with patch(
        "services.telemost_recorder_api.handlers.handle_record",
        AsyncMock(side_effect=fake_record),
    ):
        await handle_update(_msg("https://telemost.360.yandex.ru/j/5655083346"))

    assert len(forwarded) == 1
    assert forwarded[0][2] == "https://telemost.360.yandex.ru/j/5655083346"


@pytest.mark.asyncio
async def test_plain_text_gets_hint_with_help_button():
    """Random non-command, non-URL text gets a usage hint + Help inline button."""
    sent: list[tuple[str, dict | None]] = []
    with patch(
        "services.telemost_recorder_api.handlers.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append((t, k.get("reply_markup")))),
    ):
        await handle_update(_msg("привет, можешь записать встречу?"))

    assert len(sent) == 1
    text, markup = sent[0]
    assert "ссылк" in text.lower() or "telemost" in text.lower() or "url" in text.lower()
    assert markup is not None
    buttons = [b for row in markup["inline_keyboard"] for b in row]
    assert any(b.get("callback_data") == "menu:help" for b in buttons)
