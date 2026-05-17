"""scheduler_worker — Bitrix calendar polling, TZ handling, idempotent enqueue.

Extended in T4 to cover multi-user expansion:
- TELEMOST_SCHEDULER_ENABLED=false → loop doesn't start
- Legacy single-user mode (env vars set) → polls only that user
- Multi-user: fetches active users from DB, deduplicates by (url, scheduled_at)
- #nobot filter
- Bitrix failure on one user → loop continues for the rest
- triggered_by = first user's telegram_id where URL was found
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

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


# ---------------------------------------------------------------------------
# T4 — Multi-user expansion tests
# ---------------------------------------------------------------------------

class _FakeUser:
    """Mimics an asyncpg Record — supports both attribute and item access."""

    def __init__(self, telegram_id: int, bitrix_id: str) -> None:
        self._data = {"telegram_id": telegram_id, "bitrix_id": bitrix_id}

    def __getitem__(self, key: str):  # type: ignore[override]
        return self._data[key]

    def __getattr__(self, name: str):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None


def _make_user(telegram_id: int, bitrix_id: str) -> _FakeUser:
    """Helper: creates a minimal active user record as returned by fetch_active_users."""
    return _FakeUser(telegram_id=telegram_id, bitrix_id=bitrix_id)


def _bitrix_event_in_window(**overrides):
    """A Bitrix event that lands inside the scheduling window (30s from now)."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(seconds=30)
    base = {
        "ID": 1,
        "NAME": "Daily standup",
        "DATE_FROM": start.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S"),
        "DATE_TO": "",
        "TZ_FROM": "Europe/Moscow",
        "TZ_TO": "Europe/Moscow",
        "LOCATION": "https://telemost.yandex.ru/j/99999",
        "DESCRIPTION": "",
        "IS_MEETING": True,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_disabled_by_env():
    """TELEMOST_SCHEDULER_ENABLED=false → run_forever returns immediately without looping."""
    with patch.dict(
        "os.environ",
        {"TELEMOST_SCHEDULER_ENABLED": "false"},
        clear=False,
    ):
        # Reload config constant inside the module
        with patch.object(scheduler_worker, "SCHEDULER_ENABLED", False):
            # run_forever should return (not block in while True)
            task = asyncio.create_task(scheduler_worker.run_forever())
            await asyncio.sleep(0.05)
            assert task.done(), "run_forever should have returned when SCHEDULER_ENABLED=false"


@pytest.mark.asyncio
async def test_legacy_single_user_mode():
    """If SCHEDULER_BITRIX_USER_ID is set, only that single user is polled
    (legacy mode) and fetch_active_users is never called."""
    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", "42"),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", 100),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._tick",
            new=AsyncMock(return_value=0),
        ) as mock_tick,
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=[]),
        ) as mock_fetch_users,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    # legacy path calls _tick, not fetch_active_users
    mock_tick.assert_awaited_once_with(telegram_id=100, bitrix_user_id="42")
    mock_fetch_users.assert_not_awaited()


@pytest.mark.asyncio
async def test_multi_user_all_active():
    """3 active users → 3 Bitrix calendar requests (_tick_all_users runs per-user)."""
    users = [
        _make_user(101, "1"),
        _make_user(102, "2"),
        _make_user(103, "3"),
    ]
    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=users),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            new=AsyncMock(return_value=[]),
        ) as mock_fetch,
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=False),
        ),
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    assert mock_fetch.await_count == 3
    called_ids = {c.args[0] for c in mock_fetch.await_args_list}
    assert called_ids == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_dedup_same_url_across_users():
    """Same meeting URL in N users' calendars → exactly 1 INSERT (in-memory dedup)."""
    users = [_make_user(100 + i, str(i + 1)) for i in range(12)]
    ev = _bitrix_event_in_window(ID=77, NAME="Big standup")

    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=users),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            new=AsyncMock(return_value=[ev]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=True),
        ) as mock_queue,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    # Despite 12 users all seeing the same event, only 1 INSERT should happen
    assert mock_queue.await_count == 1


@pytest.mark.asyncio
async def test_nobot_filter():
    """Event with '#nobot' in name is skipped — no INSERT."""
    user = _make_user(101, "1")
    ev = _bitrix_event_in_window(ID=55, NAME="Secret meeting #nobot")

    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=[user]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            new=AsyncMock(return_value=[ev]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=True),
        ) as mock_queue,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    mock_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_event_without_telemost_url():
    """Event with no Telemost URL (e.g. calendar_NN) is skipped."""
    user = _make_user(101, "1")
    ev = _bitrix_event_in_window(ID=88, LOCATION="calendar_357", DESCRIPTION="")

    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=[user]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            new=AsyncMock(return_value=[ev]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=True),
        ) as mock_queue,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    mock_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_bitrix_fails_for_one_user():
    """If Bitrix raises for user #2, users #1 and #3 are still processed."""
    users = [
        _make_user(101, "1"),
        _make_user(102, "2"),  # will raise
        _make_user(103, "3"),
    ]
    ev = _bitrix_event_in_window(ID=10)

    async def _fetch_side_effect(bitrix_id: str):
        if bitrix_id == "2":
            raise RuntimeError("Bitrix down for user 2")
        return [ev]

    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=users),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            side_effect=_fetch_side_effect,
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=True),
        ) as mock_queue,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    # Users 1 and 3 each have the same event URL → dedup → 1 unique insert
    assert mock_queue.await_count == 1


@pytest.mark.asyncio
async def test_triggered_by_first_owner():
    """triggered_by is set to telegram_id of the FIRST user where the URL appeared."""
    users = [
        _make_user(201, "1"),  # first — should be triggered_by
        _make_user(202, "2"),
        _make_user(203, "3"),
    ]
    ev = _bitrix_event_in_window(ID=20)

    with (
        patch.object(scheduler_worker, "SCHEDULER_ENABLED", True),
        patch.object(scheduler_worker, "SCHEDULER_BITRIX_USER_ID", ""),
        patch.object(scheduler_worker, "SCHEDULER_TELEGRAM_ID", None),
        patch.object(scheduler_worker, "SCHEDULER_TICK_SECONDS", 10000),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker.fetch_active_users",
            new=AsyncMock(return_value=users),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._fetch_bitrix_events",
            new=AsyncMock(return_value=[ev]),
        ),
        patch(
            "services.telemost_recorder_api.workers.scheduler_worker._queue_meeting",
            new=AsyncMock(return_value=True),
        ) as mock_queue,
        patch("asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scheduler_worker.run_forever()

    mock_queue.assert_awaited_once()
    kwargs = mock_queue.await_args.kwargs
    # triggered_by must be the FIRST user's telegram_id (201), not 202 or 203
    assert kwargs["triggered_by"] == 201
