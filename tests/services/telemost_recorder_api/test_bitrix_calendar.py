"""Bitrix calendar lookup by meeting_url."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from services.telemost_recorder_api.bitrix_calendar import (
    find_event_by_url,
    enrich_meeting_from_bitrix,
)


@pytest.mark.asyncio
async def test_find_event_by_url_matches_in_location():
    url = "https://telemost.360.yandex.ru/j/abc"
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {
                    "NAME": "Sync с командой",
                    "LOCATION": url,
                    "DATE_FROM": "2026-05-12T10:00:00+03:00",
                    "ATTENDEES_CODES": ["U1", "U42"],
                },
                {
                    "NAME": "Другая встреча",
                    "LOCATION": "https://example.com",
                    "ATTENDEES_CODES": ["U7"],
                },
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(bitrix_user_id="42", meeting_url=url)
    assert ev["title"] == "Sync с командой"
    assert ev["bitrix_attendee_ids"] == [1, 42]


@pytest.mark.asyncio
async def test_find_event_by_url_matches_in_description():
    url = "https://telemost.360.yandex.ru/j/xyz"
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {
                    "NAME": "Встреча",
                    "LOCATION": "",
                    "DESCRIPTION": f"Ссылка: {url}",
                    "ATTENDEES_CODES": ["U9"],
                }
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(bitrix_user_id="42", meeting_url=url)
    assert ev["title"] == "Встреча"


@pytest.mark.asyncio
async def test_find_event_by_url_no_match_returns_none():
    fake_resp = httpx.Response(200, json={"result": []})
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(
            bitrix_user_id="42",
            meeting_url="https://telemost.360.yandex.ru/j/nope",
        )
    assert ev is None


@pytest.mark.asyncio
async def test_find_event_by_url_returns_none_on_http_error():
    with patch(
        "httpx.AsyncClient.get",
        AsyncMock(side_effect=httpx.ConnectError("dns")),
    ):
        ev = await find_event_by_url(
            bitrix_user_id="1",
            meeting_url="https://x",
        )
    assert ev is None


@pytest.mark.asyncio
async def test_enrich_meeting_resolves_attendees_to_telegram_ids():
    meeting_id = uuid4()

    bitrix_event = {
        "title": "Daily",
        "bitrix_attendee_ids": [1, 42, 99],
        "scheduled_at": "2026-05-12T10:00:00+03:00",
        "source_event_id": "BX-EV-7",
    }

    async def fake_find(bitrix_user_id, meeting_url):
        return bitrix_event

    fake_conn = AsyncMock()
    fake_conn.fetch.return_value = [
        {"telegram_id": 111, "name": "Иван Иванов", "bitrix_id": "1"},
        {"telegram_id": 222, "name": "Алина А.", "bitrix_id": "42"},
    ]

    # asyncpg's Pool.acquire() returns a sync PoolAcquireContext that is
    # both awaitable and an async context manager. Model it with a sync Mock
    # whose return value implements __aenter__/__aexit__.
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=fake_conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)
    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=acquire_ctx)

    with patch(
        "services.telemost_recorder_api.bitrix_calendar.find_event_by_url",
        AsyncMock(side_effect=fake_find),
    ), patch(
        "services.telemost_recorder_api.bitrix_calendar.get_pool",
        AsyncMock(return_value=fake_pool),
    ):
        updated = await enrich_meeting_from_bitrix(
            meeting_id=meeting_id,
            meeting_url="https://telemost.360.yandex.ru/j/abc",
            triggered_by_bitrix_id="1",
        )

    assert updated is True
    fake_conn.execute.assert_called_once()
    args = fake_conn.execute.call_args.args
    assert "UPDATE telemost.meetings" in args[0]
    assert args[1] == "Daily"
    invitees_json = args[2]
    assert '"telegram_id": 111' in invitees_json
    assert '"telegram_id": 222' in invitees_json
    assert "Иван Иванов" in invitees_json


@pytest.mark.asyncio
async def test_find_event_falls_back_to_closest_meeting_when_url_absent():
    """Bitrix-встречи с видеосвязью имеют LOCATION='calendar_XXX_YYY' вместо URL.

    В этом случае URL не находится, но есть встреча близко по времени с
    несколькими участниками — её и берём для обогащения title+invitees.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    soon = now.strftime("%d.%m.%Y %H:%M:%S")
    far = (now.replace(year=now.year + 1)).strftime("%d.%m.%Y %H:%M:%S")
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {
                    "ID": "111",
                    "NAME": "Дневная няня",  # single-attendee personal block — must skip
                    "LOCATION": "",
                    "DATE_FROM": soon,
                    "ATTENDEES_CODES": ["U1"],
                    "IS_MEETING": False,
                },
                {
                    "ID": "222",
                    "NAME": "Обсуждаем роли",  # Bitrix-видеосвязь, no URL in LOCATION
                    "LOCATION": "calendar_357_22673",
                    "DATE_FROM": soon,
                    "ATTENDEES_CODES": ["U1", "U11"],
                    "IS_MEETING": True,
                },
                {
                    "ID": "333",
                    "NAME": "Далеко не та",
                    "LOCATION": "",
                    "DATE_FROM": far,
                    "ATTENDEES_CODES": ["U1", "U2"],
                    "IS_MEETING": True,
                },
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(
            bitrix_user_id="1",
            meeting_url="https://telemost.360.yandex.ru/j/whatever",
        )
    assert ev is not None
    assert ev["title"] == "Обсуждаем роли"
    assert ev["source_event_id"] == "222"


@pytest.mark.asyncio
async def test_find_event_no_fallback_if_only_personal_blocks():
    """Если в окне только single-attendee блоки (няня/обед) — fallback не сработает."""
    from datetime import datetime, timezone
    soon = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")
    fake_resp = httpx.Response(
        200,
        json={
            "result": [
                {"ID": "1", "NAME": "Ночная няня", "DATE_FROM": soon,
                 "ATTENDEES_CODES": ["U1"], "IS_MEETING": False},
                {"ID": "2", "NAME": "Обед", "DATE_FROM": soon,
                 "ATTENDEES_CODES": ["U1"], "IS_MEETING": False},
            ]
        },
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=fake_resp)):
        ev = await find_event_by_url(
            bitrix_user_id="1",
            meeting_url="https://telemost.yandex.ru/j/none",
        )
    assert ev is None


@pytest.mark.asyncio
async def test_enrich_meeting_no_event_returns_false():
    with patch(
        "services.telemost_recorder_api.bitrix_calendar.find_event_by_url",
        AsyncMock(return_value=None),
    ):
        updated = await enrich_meeting_from_bitrix(
            meeting_id=uuid4(),
            meeting_url="https://telemost.360.yandex.ru/j/x",
            triggered_by_bitrix_id="1",
        )
    assert updated is False
