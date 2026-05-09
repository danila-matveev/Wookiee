"""Tests for /start and /help command handlers."""
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


@pytest.mark.asyncio
async def test_start_known_user_gets_welcome():
    sent: list[tuple[int, str]] = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value={
            "telegram_id": 555,
            "name": "Полина Ермилова",
            "short_name": "Полина",
            "is_active": True,
        }),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append((chat_id, text))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    assert sent[0][0] == 555  # chat_id
    assert "Полина" in sent[0][1]
    assert "/record" in sent[0][1]
    assert "/help" in sent[0][1]


@pytest.mark.asyncio
async def test_start_unknown_user_gets_auth_instructions():
    sent: list[tuple[int, str]] = []
    with patch(
        "services.telemost_recorder_api.handlers.start.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda chat_id, text, **kw: sent.append((chat_id, text))),
    ):
        await handle_update(_msg("/start"))
    assert len(sent) == 1
    assert "Bitrix24" in sent[0][1]
    assert "Telegram" in sent[0][1]


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
    """Unknown commands are silently ignored in Phase 0."""
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
        "services.telemost_recorder_api.handlers.start.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await handle_update(_msg("/start@wookiee_recorder_bot"))
    assert len(sent) == 1
