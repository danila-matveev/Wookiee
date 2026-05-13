"""meet:<short_id>:<action> callback handlers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from services.telemost_recorder_api.handlers.meeting_actions import handle_meet


@pytest.mark.asyncio
async def test_meet_show_renders_summary_with_action_keyboard():
    mid = uuid4()
    meeting = {
        "id": mid, "title": "Daily", "started_at": None,
        "duration_seconds": 1800, "status": "done", "tags": [],
        "summary": {"topics": [], "decisions": [], "tasks": []},
        "processed_paragraphs": [],
    }
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="show")

    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert any(c.endswith(":transcript") for c in cbs)
    assert any(c.endswith(":delete") for c in cbs)


@pytest.mark.asyncio
async def test_meet_transcript_sends_document():
    mid = uuid4()
    meeting = {
        "id": mid, "title": "T", "started_at": None,
        "duration_seconds": 60, "status": "done",
        "processed_paragraphs": [
            {"start_ms": 0, "speaker": "Иван", "text": "Привет"},
        ],
        "summary": {}, "tags": [],
    }
    docs = []

    async def fake_doc(chat_id, file_bytes, *, filename, caption=None):
        docs.append({"filename": filename, "bytes": file_bytes})

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_document",
        AsyncMock(side_effect=fake_doc),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="transcript")

    assert len(docs) == 1
    assert docs[0]["filename"].startswith("transcript_")
    assert "Иван".encode() in docs[0]["bytes"]


@pytest.mark.asyncio
async def test_meet_delete_asks_confirmation_not_deletes():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append({"text": text, "reply_markup": reply_markup})

    deleted = []

    async def fake_delete(*a, **kw):
        deleted.append((a, kw))

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.delete_meeting_for_owner",
        AsyncMock(side_effect=fake_delete),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="delete")

    assert deleted == []
    assert len(sent) == 1
    kb = sent[0]["reply_markup"]
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert any(c.endswith(":confirm_delete") for c in cbs)


@pytest.mark.asyncio
async def test_meet_delete_escapes_title_markdown():
    """Titles with Markdown specials must not break Telegram parse_mode."""
    mid = uuid4()
    meeting = {"id": mid, "title": "Sync *2* [draft]", "status": "done",
               "started_at": None, "duration_seconds": 0, "summary": {},
               "tags": [], "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="delete")

    assert len(sent) == 1
    # Backslash-escaped Markdown specials in the title (matches notifier._md_escape)
    assert "\\*2\\*" in sent[0]
    assert "\\[draft\\]" in sent[0]


@pytest.mark.asyncio
async def test_meet_confirm_delete_actually_deletes():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.delete_meeting_for_owner",
        AsyncMock(return_value=True),
    ):
        await handle_meet(
            chat_id=1, user_id=111, short_id=str(mid)[:8], action="confirm_delete"
        )

    assert any("Удалено" in s or "удалена" in s.lower() for s in sent)


@pytest.mark.asyncio
async def test_meet_notion_export_sends_page_url():
    mid = uuid4()
    meeting = {
        "id": mid, "title": "T", "status": "done", "started_at": None,
        "duration_seconds": 0, "summary": {}, "tags": [],
        "processed_paragraphs": [],
    }
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **kw):
        sent.append({"text": text, "parse_mode": kw.get("parse_mode", "Markdown")})

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.export_meeting_to_notion",
        AsyncMock(return_value=("p_123", "https://www.notion.so/page-abc")),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="notion")

    assert len(sent) == 1
    assert "https://www.notion.so/page-abc" in sent[0]["text"]
    # URL must not be parsed as Markdown (underscores in slugs break parse)
    assert sent[0]["parse_mode"] is None


@pytest.mark.asyncio
async def test_meet_notion_export_handles_error():
    from services.telemost_recorder_api.notion_export import NotionExportError
    mid = uuid4()
    meeting = {
        "id": mid, "title": "T", "status": "done", "started_at": None,
        "duration_seconds": 0, "summary": {}, "tags": [],
        "processed_paragraphs": [],
    }
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.export_meeting_to_notion",
        AsyncMock(side_effect=NotionExportError("boom")),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="notion")

    assert len(sent) == 1
    assert "не получилось" in sent[0].lower() or "notion" in sent[0].lower()


@pytest.mark.asyncio
async def test_meet_unknown_action_returns_silently():
    mid = uuid4()
    meeting = {"id": mid, "title": "T", "status": "done", "started_at": None,
               "duration_seconds": 0, "summary": {}, "tags": [],
               "processed_paragraphs": []}
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=meeting),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=111, short_id=str(mid)[:8], action="banana")

    assert sent == []


@pytest.mark.asyncio
async def test_meet_not_owner_responds_not_found():
    sent = []

    async def fake_send(chat_id, text, *, reply_markup=None, **_):
        sent.append(text)

    with patch(
        "services.telemost_recorder_api.handlers.meeting_actions.load_meeting_by_short_id",
        AsyncMock(return_value=None),
    ), patch(
        "services.telemost_recorder_api.handlers.meeting_actions.tg_send_message",
        AsyncMock(side_effect=fake_send),
    ):
        await handle_meet(chat_id=1, user_id=999, short_id="deadbeef", action="show")

    assert len(sent) == 1
    assert "не нашёл" in sent[0].lower() or "не найдена" in sent[0].lower()
