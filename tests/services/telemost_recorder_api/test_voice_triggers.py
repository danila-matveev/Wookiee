"""Tests for voice_triggers — Stage 1 (detection) + Stage 2 (slot-fill).

All OpenRouter calls are mocked — no real LLM calls in tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Ensure env vars are set so config imports don't fail
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

from services.telemost_recorder_api import voice_triggers  # noqa: E402
from services.telemost_recorder_api.voice_triggers import VoiceCandidate, extract  # noqa: E402

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts"

_TEAM_USERS: list[dict[str, Any]] = [
    {"bitrix_id": 1, "name": "Данила Матвеев", "short_name": "Данила", "telegram_id": 100},
    {"bitrix_id": 1625, "name": "Алина Иванова", "short_name": "Алина", "telegram_id": 200},
]

# ---------------------------------------------------------------------------
# Stage 1 mock responses
# ---------------------------------------------------------------------------

_STAGE1_EMPTY = json.dumps([])

_STAGE1_ONE_TASK = json.dumps([
    {
        "speaker": "Данила",
        "timestamp": "00:45",
        "raw_text": "Саймон, поставь задачу: Алина собирает выкупаемость по бомберам за октябрь. Дедлайн пятница.",
        "intent_guess": "task",
        "confidence": 0.92,
    }
])

_STAGE1_MEETING_AND_NOTE = json.dumps([
    {
        "speaker": "Данила",
        "timestamp": "00:40",
        "raw_text": "Саймон, запланируй встречу с Леной на понедельник в 14:00. Повестка: обзор поставок.",
        "intent_guess": "meeting",
        "confidence": 0.88,
    },
    {
        "speaker": "Данила",
        "timestamp": "01:15",
        "raw_text": "Саймон, запомни: обсуждали цену на Wendy — не ниже 4500 рублей.",
        "intent_guess": "note",
        "confidence": 0.95,
    },
])

_STAGE1_LOW_CONFIDENCE = json.dumps([
    {
        "speaker": "Данила",
        "timestamp": "00:45",
        "raw_text": "Саймон или кто-то там...",
        "intent_guess": "attention",
        "confidence": 0.3,  # below threshold
    }
])

_STAGE1_REMINDER = json.dumps([
    {
        "speaker": "Данила",
        "timestamp": "00:30",
        "raw_text": "Саймон, напомни мне через два дня перезвонить Сергею по поводу тиража.",
        "intent_guess": "reminder",
        "confidence": 0.91,
    }
])

# ---------------------------------------------------------------------------
# Stage 2 mock responses
# ---------------------------------------------------------------------------

_STAGE2_TASK = json.dumps({
    "title": "Собрать выкупаемость по бомберам за октябрь",
    "responsible": "Алина",
    "created_by": "Данила",
    "auditors": [],
    "accomplices": [],
    "description": "Алина собирает выкупаемость по бомберам за октябрь.",
    "deadline": "2026-05-22T18:00:00",
})

_STAGE2_MEETING = json.dumps({
    "name": "Встреча с Леной",
    "from": "2026-05-25T14:00:00",
    "to": "2026-05-25T15:00:00",
    "attendees": ["Лена", "Данила"],
    "description": "Повестка: обзор поставок",
})

_STAGE2_NOTE = json.dumps({
    "quote": "обсуждали цену на Wendy — не ниже 4500 рублей",
})

_STAGE2_REMINDER = json.dumps({
    "remind_at": "2026-05-18T09:00:00",
    "text": "Перезвонить Сергею по поводу тиража",
    "recipient": "Данила",
})


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _read_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests — VOICE_TRIGGERS_ENABLED=false
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disabled_returns_empty() -> None:
    """When VOICE_TRIGGERS_ENABLED is false, extract() returns [] without calling LLM."""
    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", False):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
        ) as mock_call:
            result = await extract(_read_fixture("one_task.txt"), _TEAM_USERS)

    assert result == []
    mock_call.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — clean transcript → 0 candidates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clean_transcript_no_candidates() -> None:
    """Transcript without Саймон references → 0 candidates."""
    stage1_resp = _STAGE1_EMPTY

    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
            return_value=stage1_resp,
        ):
            result = await extract(_read_fixture("clean.txt"), _TEAM_USERS)

    assert result == []


# ---------------------------------------------------------------------------
# Tests — one task transcript → 1 candidate with extracted_fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_one_task_transcript() -> None:
    """Transcript with 1 task command → 1 VoiceCandidate with filled extracted_fields."""
    side_effects = [_STAGE1_ONE_TASK, _STAGE2_TASK]

    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
            side_effect=side_effects,
        ):
            result = await extract(_read_fixture("one_task.txt"), _TEAM_USERS)

    assert len(result) == 1
    cand = result[0]
    assert isinstance(cand, VoiceCandidate)
    assert cand.intent == "task"
    assert cand.speaker == "Данила"
    assert cand.confidence == pytest.approx(0.92)
    assert "title" in cand.extracted_fields
    assert "deadline" in cand.extracted_fields


# ---------------------------------------------------------------------------
# Tests — meeting + note transcript → 2 candidates of different intents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meeting_and_note_transcript() -> None:
    """Transcript with meeting + note commands → 2 candidates with correct intents."""
    side_effects = [_STAGE1_MEETING_AND_NOTE, _STAGE2_MEETING, _STAGE2_NOTE]

    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
            side_effect=side_effects,
        ):
            result = await extract(_read_fixture("meeting_and_note.txt"), _TEAM_USERS)

    assert len(result) == 2
    intents = {c.intent for c in result}
    assert intents == {"meeting", "note"}


# ---------------------------------------------------------------------------
# Tests — low confidence candidate filtered before Stage 2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_filtered() -> None:
    """Candidate with confidence < 0.5 must not reach Stage 2."""
    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
            side_effect=[_STAGE1_LOW_CONFIDENCE],
        ) as mock_call:
            result = await extract("...", _TEAM_USERS)

    # Stage 1 called once, Stage 2 never called (only 1 call total)
    assert mock_call.call_count == 1
    assert result == []


# ---------------------------------------------------------------------------
# Tests — Stage 1 malformed JSON → empty list, no exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage1_malformed_json() -> None:
    """Malformed JSON from Stage 1 → returns [] without raising."""
    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            new_callable=AsyncMock,
            return_value="THIS IS NOT JSON {{{",
        ):
            result = await extract("some transcript", _TEAM_USERS)

    assert result == []


# ---------------------------------------------------------------------------
# Tests — Stage 2 failure → candidate skipped, others continue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage2_fails_skips_candidate() -> None:
    """If Stage 2 raises for one candidate, that candidate is skipped but others succeed."""
    # Two candidates from Stage 1; Stage 2 fails for first, succeeds for second
    stage1 = json.dumps([
        {
            "speaker": "Данила",
            "timestamp": "00:45",
            "raw_text": "Саймон, поставь задачу: Алина собирает...",
            "intent_guess": "task",
            "confidence": 0.9,
        },
        {
            "speaker": "Данила",
            "timestamp": "01:15",
            "raw_text": "Саймон, запомни: цена не ниже 4500",
            "intent_guess": "note",
            "confidence": 0.85,
        },
    ])

    call_count = 0

    async def _mock_call(prompt: str, model: str, timeout_seconds: int) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return stage1
        if call_count == 2:
            raise RuntimeError("Stage 2 LLM failure")
        # Third call (second Stage 2) succeeds
        return _STAGE2_NOTE

    with patch.object(voice_triggers, "VOICE_TRIGGERS_ENABLED", True):
        with patch(
            "services.telemost_recorder_api.voice_triggers._call_openrouter",
            side_effect=_mock_call,
        ):
            result = await extract("transcript text", _TEAM_USERS)

    # Only the successful candidate remains
    assert len(result) == 1
    assert result[0].intent == "note"


# ---------------------------------------------------------------------------
# Tests — notifier renders voice_trigger sections
# ---------------------------------------------------------------------------

def test_render_sections_in_notifier() -> None:
    """format_summary_message renders voice_trigger sections correctly."""
    from services.telemost_recorder_api.notifier import format_summary_message

    task_cand = VoiceCandidate(
        speaker="Данила",
        timestamp="00:45",
        raw_text="Саймон, поставь задачу...",
        intent="task",
        confidence=0.92,
        extracted_fields={
            "title": "Собрать выкупаемость по бомберам",
            "responsible": "Алина",
            "created_by": "Данила",
            "deadline": "2026-05-22T18:00:00",
            "auditors": [],
            "accomplices": [],
            "description": "...",
        },
    )
    note_cand = VoiceCandidate(
        speaker="Данила",
        timestamp="01:15",
        raw_text="Саймон, запомни: цена Wendy...",
        intent="note",
        confidence=0.95,
        extracted_fields={"quote": "цена на Wendy — не ниже 4500 рублей"},
    )
    attention_cand = VoiceCandidate(
        speaker="Алина",
        timestamp="02:00",
        raw_text="Саймон, обрати внимание: конкурент снизил цену",
        intent="attention",
        confidence=0.80,
        extracted_fields={"quote": "конкурент снизил цену на 15%"},
    )
    meeting_cand = VoiceCandidate(
        speaker="Данила",
        timestamp="00:40",
        raw_text="Саймон, запланируй встречу с Леной",
        intent="meeting",
        confidence=0.88,
        extracted_fields={
            "name": "Встреча с Леной",
            "from": "2026-05-25T14:00:00",
            "to": "2026-05-25T15:00:00",
            "attendees": ["Лена", "Данила"],
            "description": "Обзор поставок",
        },
    )
    reminder_cand = VoiceCandidate(
        speaker="Данила",
        timestamp="00:30",
        raw_text="Саймон, напомни через два дня...",
        intent="reminder",
        confidence=0.91,
        extracted_fields={
            "remind_at": "2026-05-18T09:00:00",
            "text": "Перезвонить Сергею",
            "recipient": "Данила",
        },
    )

    meeting: dict[str, Any] = {
        "id": "aaaabbbb-0000-0000-0000-000000000001",
        "title": "Тест встречи",
        "triggered_by": 100,
        "started_at": None,
        "duration_seconds": None,
        "status": "done",
        "summary": {
            "title": "Тестовая встреча",
            "participants": ["Данила", "Алина"],
            "topics": [],
            "decisions": [],
            "tasks": [],
        },
        "tags": [],
        "voice_triggers": [
            task_cand, note_cand, attention_cand, meeting_cand, reminder_cand
        ],
    }

    text = format_summary_message(meeting)

    assert "📌" in text and "Задачи" in text
    assert "📝" in text and "Заметки" in text
    assert "🔖" in text and "Важные моменты" in text
    assert "📅" in text and "Предлагаемые встречи" in text
    assert "🔔" in text and "Напоминания" in text
    # Check specific content appears
    assert "Собрать выкупаемость" in text
    assert "Wendy" in text


# ---------------------------------------------------------------------------
# Tests — keyboard produces correct callback_data for disabled phase 1
# ---------------------------------------------------------------------------

def test_keyboard_placeholder_callback() -> None:
    """voice_trigger_keyboard returns buttons with voice:<id>:disabled callback_data."""
    from services.telemost_recorder_api.keyboards import voice_trigger_keyboard

    kb = voice_trigger_keyboard("abc123")
    rows = kb["inline_keyboard"]
    # Must have at least 1 row with 3 buttons
    assert len(rows) >= 1
    all_buttons = [btn for row in rows for btn in row]
    assert len(all_buttons) == 3
    for btn in all_buttons:
        assert btn["callback_data"] == "voice:abc123:disabled"


# ---------------------------------------------------------------------------
# Tests — handler for voice:*:disabled sends placeholder response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_disabled_responds_placeholder() -> None:
    """Clicking a voice:*:disabled button sends the Phase 2 placeholder message."""
    from services.telemost_recorder_api.handlers.voice_trigger_disabled import (
        handle_voice_disabled,
    )

    with patch(
        "services.telemost_recorder_api.handlers.voice_trigger_disabled.tg_send_message",
        new_callable=AsyncMock,
    ) as mock_send:
        await handle_voice_disabled(chat_id=12345, candidate_id="abc123")

    mock_send.assert_called_once()
    call_args = mock_send.call_args
    # chat_id must match
    assert call_args[0][0] == 12345
    # Message must mention Phase 2
    sent_text: str = call_args[0][1]
    assert "Phase 2" in sent_text or "недоступно" in sent_text.lower()
