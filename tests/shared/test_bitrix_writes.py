"""Tests for shared.bitrix_writes — Bitrix24 write API wrapper.

All httpx calls are mocked. We never reach the real Bitrix webhook.

Covers:
- create_task → POST to tasks.task.add.json with correct fields, returns int id
- create_task with optional auditors/accomplices/deadline/priority
- create_task error → raises BitrixWriteError
- create_calendar_event → POST to calendar.event.add.json, returns int id
- create_calendar_event minimum fields (no location, no attendees)
- create_calendar_event error → raises BitrixWriteError
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_body: dict | None = None, text: str = "") -> MagicMock:
    """Build a fake httpx.Response-like mock."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    else:
        resp.json = MagicMock(return_value={})
    resp.text = text or (str(json_body) if json_body else "")
    return resp


def _async_client_ctx(mock_response: MagicMock) -> tuple[MagicMock, MagicMock]:
    """Return (ctx_manager, client_mock) — patch httpx.AsyncClient to ctx."""
    client_mock = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client_mock


_WEBHOOK_PATCH = "https://wookiee.bitrix24.ru/rest/1/test-token/"


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_task_success_minimum_fields():
    """POST 200 with TITLE/RESPONSIBLE_ID/CREATED_BY/DESCRIPTION → returns task id."""
    from shared.bitrix_writes import create_task

    resp = _make_response(
        200,
        {"result": {"task": {"id": "12345"}}},
    )
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        task_id = await create_task(
            title="Test task",
            responsible_id=25,
            created_by=1,
            description="Test description",
        )

    assert task_id == 12345
    call = client_mock.post.call_args
    # URL ends with tasks.task.add.json
    assert call.args[0].endswith("/tasks.task.add.json")
    # Body must have fields wrapper
    body = call.kwargs["json"]
    assert "fields" in body
    fields = body["fields"]
    assert fields["TITLE"] == "Test task"
    assert fields["RESPONSIBLE_ID"] == 25
    assert fields["CREATED_BY"] == 1
    assert fields["DESCRIPTION"] == "Test description"
    # PRIORITY defaults to 1 (normal)
    assert fields["PRIORITY"] == 1


@pytest.mark.asyncio
async def test_create_task_with_all_fields():
    """All optional fields (deadline, auditors, accomplices, priority) are passed through."""
    from shared.bitrix_writes import create_task

    resp = _make_response(
        200,
        {"result": {"task": {"id": "777"}}},
    )
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    deadline = datetime(2026, 5, 22, 18, 0, 0)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        task_id = await create_task(
            title="Full task",
            responsible_id=1625,
            created_by=1,
            description="Описание",
            deadline=deadline,
            auditors=[1, 25],
            accomplices=[2223],
            priority=2,
        )

    assert task_id == 777
    body = client_mock.post.call_args.kwargs["json"]
    fields = body["fields"]
    assert fields["DEADLINE"] == "2026-05-22T18:00:00"
    assert fields["AUDITORS"] == [1, 25]
    assert fields["ACCOMPLICES"] == [2223]
    assert fields["PRIORITY"] == 2


@pytest.mark.asyncio
async def test_create_task_deadline_none_not_sent():
    """When deadline=None, DEADLINE key must not be present in fields."""
    from shared.bitrix_writes import create_task

    resp = _make_response(200, {"result": {"task": {"id": "1"}}})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        await create_task(
            title="No deadline",
            responsible_id=1,
            created_by=1,
            description="x",
            deadline=None,
        )

    body = client_mock.post.call_args.kwargs["json"]
    # DEADLINE should not appear at all (Bitrix interprets null differently than absence)
    assert "DEADLINE" not in body["fields"]


@pytest.mark.asyncio
async def test_create_task_http_error_raises():
    """Non-2xx response → BitrixWriteError."""
    from shared.bitrix_writes import BitrixWriteError, create_task

    resp = _make_response(500, text="Internal error")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        with pytest.raises(BitrixWriteError):
            await create_task(
                title="boom",
                responsible_id=1,
                created_by=1,
                description="x",
            )


@pytest.mark.asyncio
async def test_create_task_bitrix_error_payload_raises():
    """Bitrix returned 200 but body has 'error' key → BitrixWriteError."""
    from shared.bitrix_writes import BitrixWriteError, create_task

    resp = _make_response(
        200,
        {"error": "WRONG_RESPONSIBLE_ID", "error_description": "User not found"},
    )
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        with pytest.raises(BitrixWriteError):
            await create_task(
                title="bad user",
                responsible_id=99999,
                created_by=1,
                description="x",
            )


# ---------------------------------------------------------------------------
# create_calendar_event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_calendar_event_success():
    """POST 200 with type/ownerId/name/from/to → returns event id."""
    from shared.bitrix_writes import create_calendar_event

    resp = _make_response(200, {"result": 4242})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    from_ts = datetime(2026, 5, 25, 14, 0, 0)
    to_ts = datetime(2026, 5, 25, 15, 0, 0)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        event_id = await create_calendar_event(
            owner_id=1,
            name="Встреча с Леной",
            from_ts=from_ts,
            to_ts=to_ts,
            description="Обзор поставок",
            location="https://telemost.360.yandex.ru/j/123",
            attendees=[1, 11],
        )

    assert event_id == 4242
    call = client_mock.post.call_args
    assert call.args[0].endswith("/calendar.event.add.json")
    body = call.kwargs["json"]
    assert body["type"] == "user"
    assert body["ownerId"] == 1
    assert body["name"] == "Встреча с Леной"
    # Bitrix expects "YYYY-MM-DD HH:MM:SS" naive in event timezone
    assert body["from"] == "2026-05-25 14:00:00"
    assert body["to"] == "2026-05-25 15:00:00"
    assert body["description"] == "Обзор поставок"
    assert body["location"] == "https://telemost.360.yandex.ru/j/123"
    assert body["attendees"] == [1, 11]


@pytest.mark.asyncio
async def test_create_calendar_event_minimum_fields():
    """No location, no attendees → still works."""
    from shared.bitrix_writes import create_calendar_event

    resp = _make_response(200, {"result": 99})
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        event_id = await create_calendar_event(
            owner_id=1,
            name="Quick meeting",
            from_ts=datetime(2026, 5, 25, 10, 0, 0),
            to_ts=datetime(2026, 5, 25, 11, 0, 0),
            description="",
        )

    assert event_id == 99
    body = client_mock.post.call_args.kwargs["json"]
    # location optional → not present (or empty)
    assert body.get("location", "") == ""
    # attendees default empty list
    assert body.get("attendees", []) == []


@pytest.mark.asyncio
async def test_create_calendar_event_http_error_raises():
    """Non-2xx response → BitrixWriteError."""
    from shared.bitrix_writes import BitrixWriteError, create_calendar_event

    resp = _make_response(503, text="Service unavailable")
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        with pytest.raises(BitrixWriteError):
            await create_calendar_event(
                owner_id=1,
                name="x",
                from_ts=datetime(2026, 5, 25, 10, 0, 0),
                to_ts=datetime(2026, 5, 25, 11, 0, 0),
                description="",
            )


@pytest.mark.asyncio
async def test_create_calendar_event_bitrix_error_payload_raises():
    """Bitrix returned 200 but with 'error' key → BitrixWriteError."""
    from shared.bitrix_writes import BitrixWriteError, create_calendar_event

    resp = _make_response(
        200,
        {"error": "ERROR_ARGUMENT", "error_description": "Wrong type"},
    )
    ctx, client_mock = _async_client_ctx(resp)
    client_mock.post = AsyncMock(return_value=resp)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        with pytest.raises(BitrixWriteError):
            await create_calendar_event(
                owner_id=1,
                name="x",
                from_ts=datetime(2026, 5, 25, 10, 0, 0),
                to_ts=datetime(2026, 5, 25, 11, 0, 0),
                description="",
            )


# ---------------------------------------------------------------------------
# Timeout test — propagates from httpx.AsyncClient
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_task_timeout_propagates():
    """httpx.TimeoutException propagates so caller can decide to retry."""
    from shared.bitrix_writes import create_task

    client_mock = AsyncMock()
    client_mock.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("shared.bitrix_writes.httpx.AsyncClient", return_value=ctx), \
         patch("shared.bitrix_writes._WEBHOOK_URL", _WEBHOOK_PATCH):
        with pytest.raises(httpx.TimeoutException):
            await create_task(
                title="x",
                responsible_id=1,
                created_by=1,
                description="x",
            )
