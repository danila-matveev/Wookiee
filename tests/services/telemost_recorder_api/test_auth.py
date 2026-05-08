"""Tests for Bitrix user sync + telegram_id auth."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.telemost_recorder_api.auth import (
    get_user_by_telegram_id,
    sync_users_from_bitrix,
)


@pytest.mark.asyncio
async def test_sync_inserts_active_users_with_telegram_id():
    bitrix_response = [
        {
            "ID": "1",
            "NAME": "Полина",
            "LAST_NAME": "Ермилова",
            "UF_USR_1774019332169": "123456",
            "ACTIVE": True,
        },
        {
            "ID": "2",
            "NAME": "Иван",
            "LAST_NAME": "Петров",
            "UF_USR_1774019332169": "@petrov",
            "ACTIVE": True,
        },
        {
            "ID": "3",
            "NAME": "Без",
            "LAST_NAME": "Телеграма",
            "UF_USR_1774019332169": "",
            "ACTIVE": True,
        },
    ]
    captured_rows = []

    class FakeConn:
        async def execute(self, query, *args):
            captured_rows.append((query, args))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.auth._fetch_bitrix_users",
        AsyncMock(return_value=bitrix_response),
    ), patch(
        "services.telemost_recorder_api.auth.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.auth._resolve_telegram_id",
        AsyncMock(side_effect=[123456, 999111, None]),
    ):
        count = await sync_users_from_bitrix()

    assert count == 2
    assert len(captured_rows) == 2


@pytest.mark.asyncio
async def test_get_user_by_telegram_id_returns_active():
    class FakeConn:
        async def fetchrow(self, query, *args):
            if args[0] == 123:
                return {
                    "telegram_id": 123,
                    "bitrix_id": "1",
                    "name": "Полина",
                    "short_name": "Полина",
                    "is_active": True,
                }
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    with patch(
        "services.telemost_recorder_api.auth.get_pool",
        AsyncMock(return_value=FakePool()),
    ):
        user = await get_user_by_telegram_id(123)
        none_user = await get_user_by_telegram_id(456)

    assert user["name"] == "Полина"
    assert none_user is None


@pytest.mark.asyncio
async def test_extract_telegram_raw_returns_none_for_empty():
    """The first telegram-field key is checked; empty/missing returns None."""
    from services.telemost_recorder_api.auth import _extract_telegram_raw

    assert _extract_telegram_raw({"UF_USR_1774019332169": ""}) is None
    assert _extract_telegram_raw({"UF_USR_1774019332169": "   "}) is None
    assert _extract_telegram_raw({}) is None
    assert _extract_telegram_raw({"UF_USR_1774019332169": "123456"}) == "123456"
    assert _extract_telegram_raw({"UF_USR_1774019332169": "  @user  "}) == "@user"


@pytest.mark.asyncio
async def test_resolve_telegram_id_numeric_passthrough():
    from services.telemost_recorder_api.auth import _resolve_telegram_id

    assert await _resolve_telegram_id("123456") == 123456
    assert await _resolve_telegram_id("  789  ") == 789


@pytest.mark.asyncio
async def test_resolve_telegram_id_username_via_get_chat():
    from services.telemost_recorder_api.auth import _resolve_telegram_id

    with patch(
        "services.telemost_recorder_api.auth.tg_call",
        AsyncMock(return_value={"id": 555, "type": "private"}),
    ):
        assert await _resolve_telegram_id("@petrov") == 555


@pytest.mark.asyncio
async def test_resolve_telegram_id_returns_none_on_unresolvable():
    from services.telemost_recorder_api.auth import _resolve_telegram_id
    from services.telemost_recorder_api.telegram_client import TelegramAPIError

    # Random string that doesn't match @username or t.me/ pattern
    assert await _resolve_telegram_id("not-a-handle") is None

    # Username that getChat fails on
    with patch(
        "services.telemost_recorder_api.auth.tg_call",
        AsyncMock(side_effect=TelegramAPIError("user not found")),
    ):
        assert await _resolve_telegram_id("@ghost") is None
