from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from services.telemost_recorder_api.notifier import (
    notify_meeting_result,
    format_summary_message,
    build_transcript_text,
)


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_format_summary_message_normal():
    meeting = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "summary": {
            "participants": ["Полина", "Иван"],
            "topics": [{"title": "Релиз", "anchor": "[01:23]"}],
            "decisions": ["Релизим в пятницу"],
            "tasks": [{"assignee": "Иван", "what": "Подготовить чейнджлог", "when": "до четверга"}],
        },
        "tags": ["разработка"],
    }
    msg = format_summary_message(meeting)
    assert "Дейли" in msg
    assert "Полина" in msg
    assert "Релиз" in msg
    assert "Релизим в пятницу" in msg
    # Assignee bold + dash + task
    assert "*Иван* — Подготовить чейнджлог" in msg
    assert "разработка" in msg


def test_format_summary_message_renders_task_context_and_conditions():
    """Развёрнутые задачи (context, conditions) — главная фича промт-апгрейда v2."""
    meeting = {
        "id": _MEETING_ID,
        "title": "Продакт",
        "started_at": datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 7200,
        "summary": {
            "participants": ["Данила", "Алина"],
            "topics": [],
            "decisions": [],
            "tasks": [{
                "assignee": "Алина",
                "what": "Переписать карточку Wendy с акцентом на гипоаллергенность ткани",
                "when": "до 20.05",
                "context": "Текущая версия не упоминает сертификаты, целевая аудитория задаёт вопросы",
                "conditions": "Только если новые фото со съёмки придут до 18.05",
            }],
        },
        "tags": [],
    }
    msg = format_summary_message(meeting)
    assert "*Алина* — Переписать карточку Wendy" in msg
    assert "Зачем:" in msg
    assert "не упоминает сертификаты" in msg
    assert "Условия:" in msg
    assert "новые фото" in msg


def test_format_summary_message_empty():
    meeting = {
        "id": _MEETING_ID, "title": None,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 600,
        "summary": {"empty": True, "note": "no_speech_detected"},
        "tags": [],
    }
    msg = format_summary_message(meeting)
    assert "никто не говорил" in msg.lower() or "пуст" in msg.lower()


def test_build_transcript_text():
    paragraphs = [
        {"speaker": "Полина", "start_ms": 0, "text": "Привет, команда."},
        {"speaker": "Иван", "start_ms": 25000, "text": "Привет."},
    ]
    text = build_transcript_text(paragraphs)
    assert "[00:00] Полина: Привет, команда." in text
    assert "[00:25] Иван: Привет." in text


@pytest.mark.asyncio
async def test_notify_idempotent_skips_already_notified():
    """Если notified_at уже не NULL → не шлём."""
    class FakeConn:
        async def fetchval(self, query, *args):
            return None  # ничего не вернулось — уже нотифицировано

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    sent = []
    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: sent.append(t)),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert sent == []


@pytest.mark.asyncio
async def test_notify_sends_summary_and_transcript():
    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {
            "participants": ["Полина"], "topics": [],
            "decisions": ["реш"], "tasks": [],
        },
        "tags": ["прочее"],
        "processed_paragraphs": [
            {"speaker": "Полина", "start_ms": 0, "text": "Привет."},
        ],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)

        async def fetchrow(self, query, *args):
            return meeting_row

        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    msgs = []
    docs = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append((c, t))),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=lambda c, file_bytes, filename, **k: docs.append((c, filename))),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert msgs[0][0] == 555
    assert "Дейли" in msgs[0][1]
    assert docs[0][0] == 555
    assert docs[0][1].endswith(".txt")


@pytest.mark.asyncio
async def test_notify_failed_meeting_sends_error():
    meeting_row = {
        "id": _MEETING_ID,
        "title": None,
        "triggered_by": 555,
        "started_at": None,
        "duration_seconds": None,
        "status": "failed",
        "summary": None,
        "tags": None,
        "processed_paragraphs": None,
        "error": "recorder exit_code=1",
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime.now(timezone.utc)
        async def fetchrow(self, query, *args):
            return meeting_row
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakePool:
        def acquire(self): return FakeConn()

    msgs = []
    docs = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append((c, t))),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=lambda *a, **k: docs.append(1)),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert any("ошибк" in m[1].lower() or "fail" in m[1].lower() for m in msgs)
    assert docs == []  # для failed transcript не шлём


def test_format_summary_message_escapes_markdown_specials_in_title():
    """Title with `*` / `_` / backticks must be escaped so Telegram parser doesn't fail."""
    meeting = {
        "id": _MEETING_ID,
        "title": "*HOT* `release_v2` _draft_",
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 600,
        "summary": {
            "participants": ["A*B"],
            "topics": [],
            "decisions": ["foo`bar`"],
            "tasks": [],
        },
        "tags": ["sales_growth"],
    }
    msg = format_summary_message(meeting)
    # Each special char must be backslash-escaped in the rendered string.
    assert "\\*HOT\\*" in msg
    assert "\\`release_v2\\`".replace("_", "\\_") in msg or "\\`release\\_v2\\`" in msg
    assert "A\\*B" in msg
    assert "foo\\`bar\\`" in msg
    assert "sales\\_growth" in msg


@pytest.mark.asyncio
async def test_notify_skips_transcript_when_summary_send_fails():
    """If summary send raises, we must NOT attempt transcript send."""
    from services.telemost_recorder_api.telegram_client import TelegramAPIError

    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {"participants": ["Полина"], "topics": [], "decisions": [], "tasks": []},
        "tags": [],
        "processed_paragraphs": [{"speaker": "Полина", "start_ms": 0, "text": "ok"}],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)

        async def fetchrow(self, query, *args):
            return meeting_row

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    docs: list = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=TelegramAPIError("400 parse error")),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=lambda *a, **k: docs.append(1)),
    ):
        await notify_meeting_result(_MEETING_ID)

    assert docs == []  # transcript must not be attempted after summary fails


@pytest.mark.asyncio
async def test_notify_continues_when_transcript_send_fails():
    """Summary already delivered — a transcript-send failure must be logged, not raised."""
    from services.telemost_recorder_api.telegram_client import TelegramAPIError

    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {"participants": ["Полина"], "topics": [], "decisions": [], "tasks": []},
        "tags": [],
        "processed_paragraphs": [{"speaker": "Полина", "start_ms": 0, "text": "ok"}],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)

        async def fetchrow(self, query, *args):
            return meeting_row

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    msgs: list = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append(t)),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(side_effect=TelegramAPIError("413 too large")),
    ):
        # Must not raise — summary was already sent.
        await notify_meeting_result(_MEETING_ID)

    assert len(msgs) == 1  # summary delivered


@pytest.mark.asyncio
async def test_bot_blocked_logs_error_for_alert(caplog):
    """Telegram 403 (bot blocked) на summary-send → logger.error,
    чтобы install_telegram_alerts поднял alert оператору.
    Раньше это был logger.warning → молчаливый таймаут на стороне юзера."""
    import logging
    from services.telemost_recorder_api.telegram_client import TelegramAPIError

    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {"participants": ["Полина"], "topics": [], "decisions": [], "tasks": []},
        "tags": [],
        "processed_paragraphs": [{"speaker": "Полина", "start_ms": 0, "text": "ok"}],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            return datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)

        async def fetchrow(self, query, *args):
            return meeting_row

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    err = TelegramAPIError("Forbidden: bot was blocked by the user", error_code=403)

    caplog.set_level(logging.WARNING, logger="services.telemost_recorder_api.notifier")

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=err),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(),
    ):
        await notify_meeting_result(_MEETING_ID)

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, (
        f"expected at least one ERROR-level record so the alert handler "
        f"picks it up; got levels={[r.levelno for r in caplog.records]}"
    )
    assert any("unreachable" in r.getMessage() for r in error_records)


@pytest.mark.asyncio
async def test_resend_after_notified_at_reset():
    """End-to-end semantics: claim → claim again (skip) → reset by
    postprocess_worker._update_meeting(status='postprocessing') → claim again
    succeeds and DM goes out.

    Simulates the manual-recovery flow:
      1. notify_meeting_result fires after first 'done' transition → claims,
         sends DM, notified_at is now NOT NULL.
      2. notify_meeting_result fires again (defensive duplicate call) →
         _claim_notification returns None, nothing sent. Idempotent.
      3. Operator flips meeting back to 'postprocessing' via _update_meeting
         (status='postprocessing'). The SQL clears notified_at to NULL.
      4. After postprocess re-runs and flips back to 'done',
         notify_meeting_result fires again → _claim_notification succeeds
         (notified_at IS NULL again), fresh DM goes out with updated summary.

    The FakeConn here tracks the notified_at value in a shared dict and
    routes execute()/fetchval() based on which SQL came in. That lets us
    exercise both the notifier claim and the worker update against the same
    "row".
    """
    from services.telemost_recorder_api.workers.postprocess_worker import (
        _update_meeting,
    )

    state: dict[str, Any] = {"notified_at": None}

    meeting_row = {
        "id": _MEETING_ID,
        "title": "Дейли",
        "triggered_by": 555,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 1800,
        "status": "done",
        "summary": {
            "participants": ["Полина"],
            "topics": [],
            "decisions": ["реш"],
            "tasks": [],
        },
        "tags": ["прочее"],
        "processed_paragraphs": [
            {"speaker": "Полина", "start_ms": 0, "text": "Привет."},
        ],
        "error": None,
    }

    class FakeConn:
        async def fetchval(self, query, *args):
            # notifier._claim_notification: UPDATE ... WHERE notified_at IS NULL
            # RETURNING notified_at. If state['notified_at'] is None → "claim"
            # by setting it and returning a timestamp. If already set → return
            # None (nothing to claim).
            if state["notified_at"] is None:
                state["notified_at"] = datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)
                return state["notified_at"]
            return None

        async def fetchrow(self, query, *args):
            return meeting_row

        async def execute(self, query, *args):
            # Worker's _update_meeting: when query carries 'notified_at = NULL'
            # we simulate the DB clearing the column.
            if "notified_at = NULL" in query:
                state["notified_at"] = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakePool:
        def acquire(self):
            return FakeConn()

    msgs: list = []

    with patch(
        "services.telemost_recorder_api.notifier.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.workers.postprocess_worker.get_pool",
        AsyncMock(return_value=FakePool()),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_message",
        AsyncMock(side_effect=lambda c, t, **k: msgs.append(t)),
    ), patch(
        "services.telemost_recorder_api.notifier.tg_send_document",
        AsyncMock(),
    ):
        # First notification — claims and sends.
        await notify_meeting_result(_MEETING_ID)
        first_sent = len(msgs)

        # Duplicate fire — must be a no-op (idempotency gate).
        await notify_meeting_result(_MEETING_ID)
        second_sent = len(msgs)

        # Operator flips back to postprocessing → _update_meeting clears
        # notified_at via SQL 'notified_at = NULL' clause.
        await _update_meeting(_MEETING_ID, "postprocessing", error=None)

        # After re-run completes and worker flips status back to done,
        # notifier fires again — should claim again and send fresh DM.
        await notify_meeting_result(_MEETING_ID)
        third_sent = len(msgs)

    assert first_sent == 1, "first notify should deliver the summary"
    assert second_sent == 1, (
        "duplicate notify must be idempotent — no second message"
    )
    assert third_sent == 2, (
        "after notified_at reset, notifier must claim again and resend; "
        f"got msgs={msgs!r}"
    )
