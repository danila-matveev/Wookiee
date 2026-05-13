"""Tests for /record command."""
from __future__ import annotations

import asyncio
import logging
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

    class FakeTxn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            return "SELECT 1"

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
    # New UX ack: friendly "Принял ссылку / Иду на встречу" — no raw ID exposed
    assert sent
    assert "принял" in sent[0].lower() or "иду" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_duplicate_concurrent_returns_already():
    sent: list[str] = []

    class FakeTxn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            return "SELECT 1"

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
async def test_record_acquires_advisory_lock_before_insert():
    """Advisory xact lock must run BEFORE the INSERT so two parallel webhooks
    on the same URL serialize on the lock instead of both passing
    ON CONFLICT DO NOTHING in the gap before the partial unique index sees
    the first row."""
    new_id = uuid4()
    sent: list[str] = []
    call_log: list[str] = []

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, query: str, *args):
            call_log.append(f"execute:{query.strip().split()[0].upper()}:{query}")
            return "SELECT 1"

        async def fetchval(self, query: str, *args):
            call_log.append(f"fetchval:{query.strip().split()[0].upper()}")
            return new_id

        async def fetchrow(self, query: str, *args):
            call_log.append(f"fetchrow:{query.strip().split()[0].upper()}")
            return None

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

    # First DB call must be the advisory lock acquisition.
    assert call_log, "expected at least one DB call"
    first = call_log[0]
    assert "pg_advisory_xact_lock" in first, (
        f"first DB call must take advisory lock, got: {first}"
    )
    # INSERT must come after the lock.
    insert_idx = next(
        (i for i, c in enumerate(call_log) if c.startswith("fetchval:INSERT")),
        None,
    )
    assert insert_idx is not None and insert_idx > 0, (
        f"INSERT must run after advisory lock, call_log={call_log}"
    )
    assert sent


@pytest.mark.asyncio
async def test_record_strips_whitespace_and_extra_args():
    """`/record   <url>   extra-text` should still parse the URL correctly."""
    new_id = uuid4()
    sent: list[str] = []

    class FakeTxn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            return "SELECT 1"

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
    assert "принял" in sent[0].lower() or "иду" in sent[0].lower()


@pytest.mark.asyncio
async def test_record_sends_telegram_outside_transaction():
    """tg_send_message must run AFTER the transaction's __aexit__ — otherwise
    a slow Telegram HTTP call (hundreds of ms — seconds) would hold the DB
    connection from the pool and the advisory lock, throttling parallel
    webhooks on the same URL. We assert ordering via a shared call_log:
    every tg_send_message call must be appended AFTER the 'txn_exit' marker.
    """
    new_id = uuid4()
    call_log: list[str] = []

    class FakeTxn:
        async def __aenter__(self):
            call_log.append("txn_enter")
            return self

        async def __aexit__(self, *_):
            call_log.append("txn_exit")
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            call_log.append("db:execute")
            return "SELECT 1"

        async def fetchval(self, query: str, *args):
            call_log.append("db:fetchval")
            return new_id

        async def fetchrow(self, query: str, *args):
            call_log.append("db:fetchrow")
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    async def fake_send(chat_id, text, **kwargs):
        call_log.append("tg_send_message")

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))

    # Sanity: both markers appeared.
    assert "txn_exit" in call_log, f"txn_exit missing from call_log={call_log}"
    assert "tg_send_message" in call_log, (
        f"tg_send_message missing from call_log={call_log}"
    )

    # The critical invariant: every tg_send_message must be AFTER txn_exit.
    txn_exit_idx = call_log.index("txn_exit")
    tg_indices = [i for i, c in enumerate(call_log) if c == "tg_send_message"]
    for idx in tg_indices:
        assert idx > txn_exit_idx, (
            "tg_send_message must run AFTER transaction exit, "
            f"but found tg_send_message at idx={idx} before txn_exit at "
            f"idx={txn_exit_idx}. call_log={call_log}"
        )


@pytest.mark.asyncio
async def test_record_duplicate_sends_telegram_outside_transaction():
    """Same invariant as above, but for the duplicate-concurrent path:
    when INSERT returns None and we fetch the existing row, the
    "уже в работе" Telegram message must still go out AFTER the
    transaction commits."""
    call_log: list[str] = []

    class FakeTxn:
        async def __aenter__(self):
            call_log.append("txn_enter")
            return self

        async def __aexit__(self, *_):
            call_log.append("txn_exit")
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            call_log.append("db:execute")
            return "SELECT 1"

        async def fetchval(self, query: str, *args):
            call_log.append("db:fetchval")
            return None  # ON CONFLICT DO NOTHING — duplicate

        async def fetchrow(self, query: str, *args):
            call_log.append("db:fetchrow")
            return {
                "id": UUID("22222222-2222-2222-2222-222222222222"),
                "status": "queued",
            }

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    async def fake_send(chat_id, text, **kwargs):
        call_log.append("tg_send_message")

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=_AUTHED_USER),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))

    assert "txn_exit" in call_log
    assert "tg_send_message" in call_log
    txn_exit_idx = call_log.index("txn_exit")
    tg_indices = [i for i, c in enumerate(call_log) if c == "tg_send_message"]
    assert tg_indices, "expected duplicate-path tg_send_message call"
    for idx in tg_indices:
        assert idx > txn_exit_idx, (
            "duplicate-path tg_send_message must run AFTER transaction exit, "
            f"call_log={call_log}"
        )


@pytest.mark.asyncio
async def test_record_alerts_on_bitrix_enrichment_failure(caplog):
    """If enrich_meeting_from_bitrix() raises, the failure must surface as an
    ERROR-level log with the exception attached — that's what the global
    TelegramAlertHandler routes to @wookiee_alerts_bot. Before this fix the
    callback only logged WARNING, so a broken Bitrix integration was invisible
    to the operator and users got empty-title meetings silently.
    """
    new_id = uuid4()

    class FakeTxn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakeConn:
        def transaction(self):
            return FakeTxn()

        async def execute(self, query: str, *args):
            return "SELECT 1"

        async def fetchval(self, query: str, *args):
            return new_id

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    authed_with_bitrix = {**_AUTHED_USER, "bitrix_id": "42"}

    async def boom(*a, **kw):
        raise RuntimeError("bitrix down")

    with patch(
        "services.telemost_recorder_api.handlers.record.get_user_by_telegram_id",
        AsyncMock(return_value=authed_with_bitrix),
    ), patch(
        "services.telemost_recorder_api.handlers.record.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.handlers.record.tg_send_message",
        AsyncMock(),
    ), patch(
        "services.telemost_recorder_api.handlers.record.enrich_meeting_from_bitrix",
        AsyncMock(side_effect=boom),
    ):
        with caplog.at_level(
            logging.ERROR,
            logger="services.telemost_recorder_api.handlers.record",
        ):
            await handle_update(_msg("/record https://telemost.yandex.ru/j/abc"))
            # Enrichment is fire-and-forget; yield until the background task
            # finishes and the done-callback fires.
            for _ in range(20):
                await asyncio.sleep(0)

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert error_records, (
        "Bitrix enrichment failure must log at ERROR level so the global "
        "TelegramAlertHandler delivers it to @wookiee_alerts_bot — "
        f"got: {[(r.levelname, r.message) for r in caplog.records]}"
    )
    joined = " ".join(r.getMessage() for r in error_records).lower()
    assert "bitrix" in joined or "enrich" in joined, (
        f"alert message should mention Bitrix/enrich, got: {joined}"
    )
