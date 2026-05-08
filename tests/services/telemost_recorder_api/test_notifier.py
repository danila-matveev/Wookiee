from datetime import datetime, timezone
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
    assert "Иван — Подготовить чейнджлог" in msg
    assert "разработка" in msg


def test_format_summary_message_empty():
    meeting = {
        "id": _MEETING_ID, "title": None,
        "started_at": datetime(2026, 5, 8, 10, 0, tzinfo=timezone.utc),
        "duration_seconds": 600,
        "summary": {"empty": True, "note": "no_speech_detected"},
        "tags": [],
    }
    msg = format_summary_message(meeting)
    assert "речь" in msg.lower() or "тишин" in msg.lower()


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
