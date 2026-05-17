"""Tests for Phase 2 voice-trigger action handlers.

Covers handlers under ``services/telemost_recorder_api/handlers/voice_actions.py``:

  * handle_task_create   — INSERT bitrix task, mark candidate created
  * handle_task_ignore   — mark candidate ignored, send confirmation
  * handle_task_edit     — Phase 2 placeholder (operator asked to dozapolnit' v bitrix руками)
  * handle_meeting_create / handle_meeting_ignore / handle_meeting_edit
  * deadline missing → friendly placeholder + bitrix link (when responsible present)

All Bitrix writes are mocked — no real HTTP.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

# Set env so config import doesn't fail when modules transitively import config
os.environ.setdefault("TELEMOST_BOT_TOKEN", "test123")
os.environ.setdefault("TELEMOST_BOT_ID", "1")
os.environ.setdefault("TELEMOST_BOT_USERNAME", "testbot")
os.environ.setdefault("TELEMOST_WEBHOOK_SECRET", "secret")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fakekey")
os.environ.setdefault("SUPABASE_HOST", "localhost")
os.environ.setdefault("SUPABASE_USER", "postgres")
os.environ.setdefault("SUPABASE_PASSWORD", "password")
os.environ.setdefault("SPEECHKIT_API_KEY", "sk")
os.environ.setdefault("YANDEX_FOLDER_ID", "folder")
os.environ.setdefault("OPENROUTER_API_KEY", "orkey")
os.environ.setdefault("BITRIX24_WEBHOOK_URL", "https://bitrix.example.com/rest/1/token/")
os.environ.setdefault("TELEMOST_DISABLE_DOTENV", "1")


_TEAM_USERS = [
    {"bitrix_id": "1", "name": "Данила Матвеев", "short_name": "Данила", "telegram_id": 100},
    {"bitrix_id": "1625", "name": "Алина Сотникова", "short_name": "Алина", "telegram_id": 200},
    {"bitrix_id": "25", "name": "Полина Медведева", "short_name": "Полина", "telegram_id": 300},
]


def _task_candidate(cand_id: UUID, with_deadline: bool = True) -> dict:
    """Build a fake voice_trigger_candidates row for a task intent."""
    fields = {
        "title": "Собрать выкупаемость по бомберам за октябрь",
        "responsible": "Алина",
        "created_by": "Данила",
        "description": "Алина собирает выкупаемость по бомберам за октябрь.",
        "auditors": [],
        "accomplices": [],
    }
    if with_deadline:
        fields["deadline"] = "2026-05-22T18:00:00"
    else:
        fields["deadline"] = None
    return {
        "id": cand_id,
        "meeting_id": uuid4(),
        "intent": "task",
        "speaker": "Данила",
        "raw_text": "Саймон, поставь задачу...",
        "extracted_fields": fields,
        "status": "pending",
        "bitrix_id": None,
    }


def _meeting_candidate(cand_id: UUID) -> dict:
    return {
        "id": cand_id,
        "meeting_id": uuid4(),
        "intent": "meeting",
        "speaker": "Данила",
        "raw_text": "Саймон, запланируй встречу с Леной",
        "extracted_fields": {
            "name": "Встреча с Леной",
            "from": "2026-05-25T14:00:00",
            "to": "2026-05-25T15:00:00",
            "attendees": ["Лена", "Данила"],
            "description": "Обзор поставок",
        },
        "status": "pending",
        "bitrix_id": None,
    }


# ---------------------------------------------------------------------------
# handle_task_create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_create_happy_path():
    """Task with full slots → Bitrix task created, status='created', confirmation sent."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id, with_deadline=True)

    with (
        patch.object(
            voice_actions,
            "get_candidate",
            new=AsyncMock(return_value=cand),
        ),
        patch.object(
            voice_actions,
            "create_task",
            new=AsyncMock(return_value=12345),
        ) as mock_create,
        patch.object(
            voice_actions,
            "mark_created",
            new=AsyncMock(return_value=True),
        ) as mock_mark,
        patch.object(
            voice_actions,
            "_fetch_team_users",
            new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(
            voice_actions,
            "tg_send_message",
            new=AsyncMock(),
        ) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=cand_id,
        )

    # Bitrix called with resolved RESPONSIBLE_ID (Алина = 1625) and CREATED_BY=1
    mock_create.assert_awaited_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["title"] == "Собрать выкупаемость по бомберам за октябрь"
    assert kwargs["responsible_id"] == 1625
    assert kwargs["created_by"] == 1
    assert kwargs["deadline"] is not None

    # DB transitioned to created
    mock_mark.assert_awaited_once_with(cand_id, "12345")

    # User got success message with Bitrix link
    mock_send.assert_awaited()
    args = mock_send.call_args.args
    assert args[0] == 999
    text = args[1]
    assert "12345" in text or "Готово" in text or "Создал" in text


@pytest.mark.asyncio
async def test_task_create_missing_deadline_sends_placeholder():
    """LLM didn't extract deadline → user gets warn + task is still created with no DEADLINE."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id, with_deadline=False)

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(
            voice_actions, "create_task", new=AsyncMock(return_value=999),
        ) as mock_create,
        patch.object(voice_actions, "mark_created", new=AsyncMock(return_value=True)),
        patch.object(
            voice_actions, "_fetch_team_users", new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=cand_id,
        )

    # Bitrix still called (deadline=None means create without it)
    mock_create.assert_awaited_once()
    assert mock_create.call_args.kwargs.get("deadline") is None

    # User got a warning about missing deadline
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "дедлайн" in sent_text.lower() or "deadline" in sent_text.lower()


@pytest.mark.asyncio
async def test_task_create_missing_responsible_aborts():
    """LLM didn't extract responsible → handler refuses to create, asks user to fill in Bitrix."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id, with_deadline=True)
    cand["extracted_fields"]["responsible"] = None

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(
            voice_actions, "create_task", new=AsyncMock(return_value=1),
        ) as mock_create,
        patch.object(voice_actions, "mark_created", new=AsyncMock()),
        patch.object(
            voice_actions, "_fetch_team_users", new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=cand_id,
        )

    # No Bitrix call when there is no resolvable responsible
    mock_create.assert_not_awaited()

    # User got the placeholder message
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "исполнител" in sent_text.lower() or "responsible" in sent_text.lower()


@pytest.mark.asyncio
async def test_task_create_unknown_candidate():
    """Candidate not in DB → user gets 'не нашёл' message, no Bitrix call."""
    from services.telemost_recorder_api.handlers import voice_actions

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=None)),
        patch.object(voice_actions, "create_task", new=AsyncMock()) as mock_create,
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=uuid4(),
        )

    mock_create.assert_not_awaited()
    mock_send.assert_awaited()


@pytest.mark.asyncio
async def test_task_create_already_handled():
    """Candidate.status != 'pending' (race) → no Bitrix call, friendly response."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id)
    cand["status"] = "created"
    cand["bitrix_id"] = "111"

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(voice_actions, "create_task", new=AsyncMock()) as mock_create,
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=cand_id,
        )

    mock_create.assert_not_awaited()
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "уже" in sent_text.lower() or "already" in sent_text.lower()


# ---------------------------------------------------------------------------
# handle_task_ignore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_ignore_marks_ignored():
    """Click ignore → status='ignored', user sees acknowledgment."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    with (
        patch.object(
            voice_actions, "mark_ignored", new=AsyncMock(return_value=True),
        ) as mock_mark,
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_ignore(
            chat_id=999, candidate_id=cand_id,
        )

    mock_mark.assert_awaited_once_with(cand_id)
    mock_send.assert_awaited()
    text = mock_send.call_args.args[1]
    assert "Пропущено" in text or "игнор" in text.lower() or "❌" in text


# ---------------------------------------------------------------------------
# handle_task_edit (Phase 2 placeholder)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_edit_sends_placeholder():
    """Edit button in Phase 2 sends an instructional placeholder."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id)

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(voice_actions, "mark_edited", new=AsyncMock(return_value=True)),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_edit(chat_id=999, candidate_id=cand_id)

    mock_send.assert_awaited()
    text = mock_send.call_args.args[1]
    assert "ручную" in text.lower() or "правк" in text.lower() or "поправ" in text.lower()


# ---------------------------------------------------------------------------
# handle_meeting_create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meeting_create_happy_path():
    """Meeting candidate → calendar.event.add called with resolved owner + name + from/to."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _meeting_candidate(cand_id)

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(
            voice_actions, "create_calendar_event", new=AsyncMock(return_value=7777),
        ) as mock_create,
        patch.object(voice_actions, "mark_created", new=AsyncMock(return_value=True)),
        patch.object(
            voice_actions, "_fetch_team_users", new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_meeting_create(
            chat_id=999, candidate_id=cand_id,
        )

    mock_create.assert_awaited_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["name"] == "Встреча с Леной"
    # owner_id defaults to Данила (1) — speaker fallback
    assert kwargs["owner_id"] == 1
    assert kwargs["description"]
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "7777" in sent_text or "создал" in sent_text.lower()


@pytest.mark.asyncio
async def test_meeting_create_missing_from_aborts():
    """Meeting without from datetime → no API call, user asked to fix in Bitrix."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _meeting_candidate(cand_id)
    cand["extracted_fields"]["from"] = None

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(
            voice_actions, "create_calendar_event", new=AsyncMock(return_value=1),
        ) as mock_create,
        patch.object(voice_actions, "mark_created", new=AsyncMock()),
        patch.object(
            voice_actions, "_fetch_team_users", new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_meeting_create(
            chat_id=999, candidate_id=cand_id,
        )

    mock_create.assert_not_awaited()
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "врем" in sent_text.lower() or "from" in sent_text.lower() or "дат" in sent_text.lower()


# ---------------------------------------------------------------------------
# handle_meeting_ignore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meeting_ignore_marks_ignored():
    """Click ignore on meeting → status='ignored', no API call."""
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    with (
        patch.object(
            voice_actions, "mark_ignored", new=AsyncMock(return_value=True),
        ) as mock_mark,
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()),
    ):
        await voice_actions.handle_meeting_ignore(
            chat_id=999, candidate_id=cand_id,
        )

    mock_mark.assert_awaited_once_with(cand_id)


# ---------------------------------------------------------------------------
# Bitrix write failure surfaces gracefully
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_create_bitrix_failure_surfaces_error():
    """BitrixWriteError → candidate stays pending, user sees error message."""
    from shared.bitrix_writes import BitrixWriteError
    from services.telemost_recorder_api.handlers import voice_actions

    cand_id = uuid4()
    cand = _task_candidate(cand_id, with_deadline=True)

    with (
        patch.object(voice_actions, "get_candidate", new=AsyncMock(return_value=cand)),
        patch.object(
            voice_actions, "create_task",
            new=AsyncMock(side_effect=BitrixWriteError("UNKNOWN")),
        ),
        patch.object(
            voice_actions, "mark_created", new=AsyncMock(return_value=True),
        ) as mock_mark,
        patch.object(
            voice_actions, "_fetch_team_users", new=AsyncMock(return_value=_TEAM_USERS),
        ),
        patch.object(voice_actions, "tg_send_message", new=AsyncMock()) as mock_send,
    ):
        await voice_actions.handle_task_create(
            chat_id=999, candidate_id=cand_id,
        )

    # candidate NOT marked created when API failed
    mock_mark.assert_not_awaited()
    # user sees error
    sent_text = "".join(call.args[1] for call in mock_send.call_args_list)
    assert "ошибк" in sent_text.lower() or "❌" in sent_text


# ---------------------------------------------------------------------------
# Keyboard wires real callbacks when intent='task' / 'meeting'
# ---------------------------------------------------------------------------

def test_keyboard_uuid_wires_real_task_callbacks():
    """voice_trigger_keyboard with intent='task' produces task_create/edit/ignore callbacks."""
    from services.telemost_recorder_api.keyboards import voice_trigger_keyboard

    cid = "11111111-2222-3333-4444-555555555555"
    kb = voice_trigger_keyboard(cid, intent="task")
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert f"task_create:{cid}" in cbs
    assert f"task_edit:{cid}" in cbs
    assert f"task_ignore:{cid}" in cbs


def test_keyboard_uuid_wires_real_meeting_callbacks():
    """voice_trigger_keyboard with intent='meeting' → meeting_create/edit/ignore."""
    from services.telemost_recorder_api.keyboards import voice_trigger_keyboard

    cid = "11111111-2222-3333-4444-555555555555"
    kb = voice_trigger_keyboard(cid, intent="meeting")
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert f"meeting_create:{cid}" in cbs
    assert f"meeting_edit:{cid}" in cbs
    assert f"meeting_ignore:{cid}" in cbs


def test_keyboard_legacy_fallback_when_no_intent():
    """Without intent, keyboard stays on the Phase 1 placeholder callback."""
    from services.telemost_recorder_api.keyboards import voice_trigger_keyboard

    kb = voice_trigger_keyboard("legacy123")
    cbs = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert all(c == "voice:legacy123:disabled" for c in cbs)
