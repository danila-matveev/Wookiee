"""scheduler_worker — Bitrix calendar polling, TZ handling, idempotent enqueue."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zoneinfo import ZoneInfo

from services.telemost_recorder_api.workers import scheduler_worker
from services.telemost_recorder_api.workers.scheduler_worker import (
    _extract_telemost_url,
    _parse_event_start,
    _process_event,
)


def _bitrix_event(**overrides):
    base = {
        "ID": 999,
        "NAME": "Test meeting",
        "DATE_FROM": "14.05.2026 14:00:00",
        "DATE_TO": "14.05.2026 14:30:00",
        "TZ_FROM": "Europe/Moscow",
        "TZ_TO": "Europe/Moscow",
        "LOCATION": "https://telemost.yandex.ru/j/12345",
        "DESCRIPTION": "",
        "IS_MEETING": True,
    }
    base.update(overrides)
    return base


def test_parse_event_start_respects_tz_from():
    """Bitrix returns wall time in the event's own TZ, not the owner's.
    14:00 in Europe/Moscow (UTC+3) -> 11:00 UTC."""
    ev = _bitrix_event(TZ_FROM="Europe/Moscow", DATE_FROM="14.05.2026 14:00:00")
    start = _parse_event_start(ev)
    assert start == datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)


def test_parse_event_start_handles_sao_paulo():
    """América/São_Paulo events (Алина) end up at +3h UTC offset = -3h SP."""
    ev = _bitrix_event(TZ_FROM="America/Sao_Paulo", DATE_FROM="14.05.2026 12:30:00")
    start = _parse_event_start(ev)
    # 12:30 São Paulo (UTC-3) -> 15:30 UTC
    assert start == datetime(2026, 5, 14, 15, 30, tzinfo=timezone.utc)


def test_parse_event_start_falls_back_to_utc_for_unknown_tz():
    ev = _bitrix_event(TZ_FROM="Mars/Olympus", DATE_FROM="14.05.2026 14:00:00")
    start = _parse_event_start(ev)
    assert start == datetime(2026, 5, 14, 14, 0, tzinfo=timezone.utc)


def test_parse_event_start_returns_none_on_bad_date():
    ev = _bitrix_event(DATE_FROM="not a date")
    assert _parse_event_start(ev) is None
    ev2 = _bitrix_event(DATE_FROM=None)
    assert _parse_event_start(ev2) is None


def test_extract_telemost_url_from_location():
    ev = _bitrix_event(LOCATION="https://telemost.yandex.ru/j/12345")
    assert _extract_telemost_url(ev) == "https://telemost.yandex.ru/j/12345"


def test_extract_telemost_url_canonicalizes_360_domain():
    ev = _bitrix_event(LOCATION="https://telemost.360.yandex.ru/j/55555")
    # Canonicalization maps 360.yandex.ru -> yandex.ru.
    assert _extract_telemost_url(ev) == "https://telemost.yandex.ru/j/55555"


def test_extract_telemost_url_from_description():
    ev = _bitrix_event(
        LOCATION="calendar_357_22625",
        DESCRIPTION="[URL=https://telemost.360.yandex.ru/j/5655083346]https://telemost.360.yandex.ru/j/5655083346[/URL]",
    )
    assert _extract_telemost_url(ev) == "https://telemost.yandex.ru/j/5655083346"


def test_extract_telemost_url_skips_bitrix_video_conf():
    """LOCATION='calendar_357' is Bitrix-Видеоконференция — Telemost URL is
    generated lazily on the UI side and isn't available via API. Skip."""
    ev = _bitrix_event(LOCATION="calendar_357", DESCRIPTION="")
    assert _extract_telemost_url(ev) is None


def test_extract_telemost_url_handles_missing_fields():
    ev = _bitrix_event(LOCATION=None, DESCRIPTION=None)
    assert _extract_telemost_url(ev) is None


@pytest.mark.asyncio
async def test_process_event_queues_when_in_lead_window():
    """When event is 60s in the future and lead=90s, queue it now."""
    now = datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)
    start = now + timedelta(seconds=60)
    ev = _bitrix_event(
        ID=42,
        NAME="Dayli",
        DATE_FROM=start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        TZ_FROM="Europe/Moscow",
    )

    with patch(
        "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
        new=AsyncMock(return_value=True),
    ) as queue:
        ok = await _process_event(ev, now_utc=now, triggered_by=123, lead=90, grace=300)

    assert ok is True
    queue.assert_awaited_once()
    kwargs = queue.await_args.kwargs
    assert kwargs["bitrix_event_id"] == "42"
    assert kwargs["title"] == "Dayli"
    assert kwargs["meeting_url"] == "https://telemost.yandex.ru/j/12345"
    assert kwargs["scheduled_at_utc"] == start
    assert kwargs["triggered_by"] == 123


@pytest.mark.asyncio
async def test_process_event_skips_when_too_early():
    """If event is 10 minutes in the future, don't queue — wait for a later tick."""
    now = datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)
    start = now + timedelta(minutes=10)
    ev = _bitrix_event(
        DATE_FROM=start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        TZ_FROM="Europe/Moscow",
    )
    with patch(
        "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
        new=AsyncMock(return_value=True),
    ) as queue:
        ok = await _process_event(ev, now_utc=now, triggered_by=1, lead=90, grace=300)
    assert ok is False
    queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_event_skips_when_past_grace():
    """A meeting that started 10 minutes ago is too late to record usefully."""
    now = datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)
    start = now - timedelta(minutes=10)
    ev = _bitrix_event(
        DATE_FROM=start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        TZ_FROM="Europe/Moscow",
    )
    with patch(
        "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
        new=AsyncMock(return_value=True),
    ) as queue:
        ok = await _process_event(ev, now_utc=now, triggered_by=1, lead=90, grace=300)
    assert ok is False
    queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_event_skips_event_without_telemost_url():
    """Bitrix-Видеоконференция (calendar_NN) has no Telemost URL we can use."""
    now = datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)
    start = now + timedelta(seconds=30)
    ev = _bitrix_event(
        LOCATION="calendar_357",
        DESCRIPTION="",
        DATE_FROM=start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        TZ_FROM="Europe/Moscow",
    )
    with patch(
        "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
        new=AsyncMock(return_value=True),
    ) as queue:
        ok = await _process_event(ev, now_utc=now, triggered_by=1, lead=90, grace=300)
    assert ok is False
    queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_event_handles_duplicate_silently():
    """When _queue_meeting returns False (ON CONFLICT), _process_event
    reports False but doesn't raise — recurring meetings on the next tick
    just re-detect the same row and skip cleanly."""
    now = datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc)
    start = now + timedelta(seconds=30)
    ev = _bitrix_event(
        DATE_FROM=start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        TZ_FROM="Europe/Moscow",
    )
    with patch(
        "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
        new=AsyncMock(return_value=False),
    ):
        ok = await _process_event(ev, now_utc=now, triggered_by=1, lead=90, grace=300)
    assert ok is False


@pytest.mark.asyncio
async def test_fetch_bitrix_events_returns_empty_on_http_error(monkeypatch):
    """Network/HTTP failures must not crash the scheduler loop — return []
    so the tick logs the failure but waits for the next iteration."""
    import httpx

    async def _boom(*a, **kw):
        raise httpx.ConnectError("boom")

    async def _client_ctx(*a, **kw):
        raise httpx.ConnectError("boom")

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **kw):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(
        "services.telemost_recorder_api.workers.scheduler_worker.httpx.AsyncClient",
        _Client,
    )
    out = await scheduler_worker._fetch_bitrix_events("1")
    assert out == []
