"""Tests for inline-button callback_query routing."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.handlers import handle_update


def _cq(data: str, user_id: int = 555, cq_id: str = "cq-1") -> dict:
    return {
        "callback_query": {
            "id": cq_id,
            "from": {"id": user_id, "is_bot": False, "first_name": "X"},
            "message": {
                "message_id": 42,
                "chat": {"id": user_id, "type": "private"},
            },
            "data": data,
        }
    }


_USER = {"telegram_id": 555, "name": "X", "short_name": "X", "is_active": True}


@pytest.mark.asyncio
async def test_callback_menu_list_routes_to_handle_list():
    forwarded: list = []
    answered: list = []

    async def fake_list(chat_id, user_id):
        forwarded.append(("list", chat_id, user_id))

    async def fake_answer(cq_id, *a, **kw):
        answered.append(cq_id)

    with patch(
        "services.telemost_recorder_api.handlers.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_list",
        AsyncMock(side_effect=fake_list),
    ), patch(
        "services.telemost_recorder_api.handlers.tg_answer_callback_query",
        AsyncMock(side_effect=fake_answer),
    ):
        await handle_update(_cq("menu:list"))
    assert forwarded == [("list", 555, 555)]
    assert answered == ["cq-1"]


@pytest.mark.asyncio
async def test_callback_menu_status_routes_to_handle_status():
    forwarded: list = []

    async def fake_status(chat_id, user_id):
        forwarded.append(("status", chat_id, user_id))

    with patch(
        "services.telemost_recorder_api.handlers.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_status",
        AsyncMock(side_effect=fake_status),
    ), patch(
        "services.telemost_recorder_api.handlers.tg_answer_callback_query",
        AsyncMock(),
    ):
        await handle_update(_cq("menu:status"))
    assert forwarded == [("status", 555, 555)]


@pytest.mark.asyncio
async def test_callback_menu_help_routes_to_handle_help():
    forwarded: list = []

    async def fake_help(chat_id):
        forwarded.append(("help", chat_id))

    with patch(
        "services.telemost_recorder_api.handlers.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_help",
        AsyncMock(side_effect=fake_help),
    ), patch(
        "services.telemost_recorder_api.handlers.tg_answer_callback_query",
        AsyncMock(),
    ):
        await handle_update(_cq("menu:help"))
    assert forwarded == [("help", 555)]


@pytest.mark.asyncio
async def test_callback_unknown_user_gets_alert_and_no_handler():
    forwarded: list = []
    answered: list = []

    async def fake_answer(cq_id, text=None, show_alert=False):
        answered.append((cq_id, text, show_alert))

    with patch(
        "services.telemost_recorder_api.handlers.get_user_by_telegram_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_list",
        AsyncMock(side_effect=lambda *a, **kw: forwarded.append("LEAK")),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_help",
        AsyncMock(side_effect=lambda *a, **kw: forwarded.append("LEAK")),
    ), patch(
        "services.telemost_recorder_api.handlers.tg_answer_callback_query",
        AsyncMock(side_effect=fake_answer),
    ):
        await handle_update(_cq("menu:list"))
    assert forwarded == []  # no handler called
    assert len(answered) == 1
    cq_id, text, show_alert = answered[0]
    assert cq_id == "cq-1"
    assert show_alert is True
    assert text and "доступ" in text.lower()


@pytest.mark.asyncio
async def test_callback_unknown_data_acks_but_does_nothing():
    """Unknown callback data must still ack (Telegram shows spinner forever otherwise)."""
    forwarded: list = []
    answered: list = []

    async def fake_answer(cq_id, *a, **kw):
        answered.append(cq_id)

    with patch(
        "services.telemost_recorder_api.handlers.get_user_by_telegram_id",
        AsyncMock(return_value=_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.handle_list",
        AsyncMock(side_effect=lambda *a, **kw: forwarded.append("LEAK")),
    ), patch(
        "services.telemost_recorder_api.handlers.tg_answer_callback_query",
        AsyncMock(side_effect=fake_answer),
    ):
        await handle_update(_cq("totally:bogus"))
    assert forwarded == []
    assert answered == ["cq-1"]
