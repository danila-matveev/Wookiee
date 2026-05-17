"""Voice-triggers pipeline — detects 'Саймон, ...' commands in transcript.

Two-stage pipeline:
  Stage 1 (LIGHT model): find candidate phrases → JSON list.
  Stage 2 (HEAVY model): slot-fill each candidate with confidence >= 0.5.

Public API:
  extract(transcript, team_users) -> list[VoiceCandidate]

Feature flag: VOICE_TRIGGERS_ENABLED (default false). When false, extract()
returns [] immediately without any LLM calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from services.telemost_recorder_api.config import (
    MODEL_HEAVY,
    MODEL_LIGHT,
    VOICE_TRIGGERS_ENABLED,
)
from services.telemost_recorder_api.llm_postprocess import _call_openrouter

logger = logging.getLogger(__name__)

# Stage 2 timeout is longer because slot-filling with HEAVY model is slower.
_STAGE1_TIMEOUT = 30
_STAGE2_TIMEOUT = 60

# Minimum confidence from Stage 1 to proceed to Stage 2.
_CONFIDENCE_THRESHOLD = 0.5

# ============================================================================
# Data model
# ============================================================================


@dataclass
class VoiceCandidate:
    """Single detected 'Саймон, ...' command with extracted slot data."""

    speaker: str
    timestamp: str
    raw_text: str
    intent: str  # 'task' | 'meeting' | 'note' | 'attention' | 'reminder'
    confidence: float
    extracted_fields: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.speaker, self.timestamp, self.raw_text, self.intent))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VoiceCandidate):
            return NotImplemented
        return (
            self.speaker == other.speaker
            and self.timestamp == other.timestamp
            and self.raw_text == other.raw_text
            and self.intent == other.intent
        )


# ============================================================================
# Stage 1 prompt — LIGHT model
# ============================================================================

_STAGE1_PROMPT = """\
Найди в транскрипте все фразы где собеседник обращается к ассистенту
по имени Саймон.

ASR-варианты имени: Саймон, Симон, Сайман, Семён, Семёна, Сын мой, Пай-мон.

Кандидат = первое слово после паузы (или в начале фразы) + дальше команда
(глагол в повелительном или ключевые слова: запомни, заметка, задача, поставь,
напомни).

НЕ кандидат = если 'Саймон' — это начало обычной фразы без команды.

Верни JSON-массив (и ТОЛЬКО его, без пояснений):
[
  {{
    "speaker": "Данила",
    "timestamp": "14:23",
    "raw_text": "<цитата фрагмента 1-2 предложения>",
    "intent_guess": "task" | "meeting" | "note" | "attention" | "reminder",
    "confidence": 0.0
  }}
]

Если обращений нет — верни пустой массив [].

Транскрипт:
{transcript}
"""


# ============================================================================
# Stage 2 prompts — HEAVY model, per intent
# ============================================================================

_STAGE2_TASK_PROMPT = """\
В этом фрагменте {speaker} попросил Саймона поставить задачу.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"
Команда Wookiee (для резолва имён в bitrix_id):
{team_users}

Извлеки структурированную задачу. Верни JSON (только его, без пояснений):
{{
  "title": "<краткое название 5-10 слов>",
  "responsible": "<имя из команды или null>",
  "created_by": "<от кого. Если не сказано явно — спикер {speaker}>",
  "auditors": [],
  "accomplices": [],
  "description": "<цитата из транскрипта + контекст>",
  "deadline": "<ISO datetime или null>"
}}
"""

_STAGE2_MEETING_PROMPT = """\
В этом фрагменте {speaker} попросил Саймона запланировать встречу.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"
Команда Wookiee:
{team_users}

Извлеки данные встречи. Верни JSON (только его, без пояснений):
{{
  "name": "<название встречи>",
  "from": "<ISO datetime начала или null>",
  "to": "<ISO datetime конца или null>",
  "attendees": ["<имя>"],
  "description": "<цитата повестки или null>"
}}
"""

_STAGE2_NOTE_PROMPT = """\
В этом фрагменте {speaker} попросил Саймона запомнить/записать заметку.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"

Верни JSON (только его, без пояснений):
{{
  "quote": "<точная цитата или краткое изложение заметки>"
}}
"""

_STAGE2_ATTENTION_PROMPT = """\
В этом фрагменте {speaker} попросил Саймона обратить внимание на что-то важное.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"

Верни JSON (только его, без пояснений):
{{
  "quote": "<точная цитата или краткое изложение важного момента>"
}}
"""

_STAGE2_REMINDER_PROMPT = """\
В этом фрагменте {speaker} попросил Саймона поставить напоминание.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"
Команда Wookiee:
{team_users}

Разбери напоминание. Если в речи «через X» / «к Y» — вычисли ISO datetime
относительно текущего момента. Верни JSON (только его, без пояснений):
{{
  "remind_at": "<ISO datetime или null>",
  "text": "<что напомнить>",
  "recipient": "<кому напомнить — имя из команды или спикер {speaker}>"
}}
"""

_STAGE2_PROMPTS: dict[str, str] = {
    "task": _STAGE2_TASK_PROMPT,
    "meeting": _STAGE2_MEETING_PROMPT,
    "note": _STAGE2_NOTE_PROMPT,
    "attention": _STAGE2_ATTENTION_PROMPT,
    "reminder": _STAGE2_REMINDER_PROMPT,
}


# ============================================================================
# Internal helpers
# ============================================================================

def _format_team_users(team_users: list[dict[str, Any]]) -> str:
    lines = []
    for u in team_users:
        lines.append(
            f"- {u.get('name', '?')} (short: {u.get('short_name', '?')}, "
            f"bitrix_id: {u.get('bitrix_id', '?')}, "
            f"telegram_id: {u.get('telegram_id', '?')})"
        )
    return "\n".join(lines) if lines else "(нет данных)"


def _prev_context(transcript: str, timestamp: str) -> str:
    """Roughly extract ~30 seconds of context before the timestamp line.

    This is a best-effort extraction. If the transcript has no recognisable
    timestamps or the target line is not found, return an empty string.
    """
    if not timestamp:
        return ""
    lines = transcript.splitlines()
    target_idx: int | None = None
    for i, line in enumerate(lines):
        if timestamp in line:
            target_idx = i
            break
    if target_idx is None:
        return ""
    start = max(0, target_idx - 5)
    return "\n".join(lines[start:target_idx]).strip()


def _strip_json_fence(text: str) -> str:
    """Remove ```json ... ``` fence if present."""
    import re
    stripped = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if m:
        return m.group(1)
    return stripped


async def _run_stage1(transcript: str) -> list[dict[str, Any]]:
    """Call Stage 1 (LIGHT model) and return parsed candidate list."""
    prompt = _STAGE1_PROMPT.format(transcript=transcript)
    try:
        raw = await _call_openrouter(prompt, MODEL_LIGHT, _STAGE1_TIMEOUT)
    except Exception:
        logger.warning("voice_triggers Stage 1 LLM call failed", exc_info=True)
        return []

    cleaned = _strip_json_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("voice_triggers Stage 1 returned malformed JSON: %r", cleaned[:300])
        return []

    if not isinstance(data, list):
        logger.warning("voice_triggers Stage 1 returned non-list: %r", type(data))
        return []

    return data


async def _run_stage2(
    candidate: dict[str, Any],
    team_users: list[dict[str, Any]],
    transcript: str,
) -> dict[str, Any] | None:
    """Call Stage 2 (HEAVY model) for a single candidate. Returns extracted fields or None."""
    intent = candidate.get("intent_guess", "note")
    prompt_template = _STAGE2_PROMPTS.get(intent, _STAGE2_NOTE_PROMPT)

    prev_ctx = _prev_context(transcript, candidate.get("timestamp", ""))
    team_str = _format_team_users(team_users)

    prompt = prompt_template.format(
        speaker=candidate.get("speaker", "?"),
        raw_text=candidate.get("raw_text", ""),
        prev_context=prev_ctx,
        team_users=team_str,
    )

    try:
        raw = await _call_openrouter(prompt, MODEL_HEAVY, _STAGE2_TIMEOUT)
    except Exception:
        logger.warning(
            "voice_triggers Stage 2 failed for candidate ts=%s intent=%s",
            candidate.get("timestamp"), intent,
            exc_info=True,
        )
        return None

    cleaned = _strip_json_fence(raw)
    try:
        fields = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(
            "voice_triggers Stage 2 malformed JSON for ts=%s: %r",
            candidate.get("timestamp"), cleaned[:200],
        )
        return None

    if not isinstance(fields, dict):
        logger.warning("voice_triggers Stage 2 returned non-dict: %r", type(fields))
        return None

    return fields


# ============================================================================
# Public API
# ============================================================================


async def extract(
    transcript: str,
    team_users: list[dict[str, Any]],
) -> list[VoiceCandidate]:
    """Two-stage detection of 'Саймон, ...' voice-trigger commands.

    Returns an empty list when VOICE_TRIGGERS_ENABLED is false.
    Never raises — all errors are logged and the empty/partial list is returned.
    """
    if not VOICE_TRIGGERS_ENABLED:
        return []

    # Stage 1 — find candidates
    raw_candidates = await _run_stage1(transcript)
    if not raw_candidates:
        return []

    # Filter by confidence threshold before Stage 2
    passing = [c for c in raw_candidates if c.get("confidence", 0.0) >= _CONFIDENCE_THRESHOLD]
    if not passing:
        logger.info(
            "voice_triggers: all %d candidates below confidence threshold %.1f",
            len(raw_candidates), _CONFIDENCE_THRESHOLD,
        )
        return []

    # Stage 2 — slot-fill each passing candidate in parallel (gather)
    stage2_tasks = [_run_stage2(raw, team_users, transcript) for raw in passing]
    stage2_results = await asyncio.gather(*stage2_tasks)

    results: list[VoiceCandidate] = []
    for raw, fields in zip(passing, stage2_results):
        if fields is None:
            # Stage 2 failed for this candidate — skip it
            continue
        results.append(
            VoiceCandidate(
                speaker=raw.get("speaker", ""),
                timestamp=raw.get("timestamp", ""),
                raw_text=raw.get("raw_text", ""),
                intent=raw.get("intent_guess", "note"),
                confidence=raw.get("confidence", 0.0),
                extracted_fields=fields,
            )
        )

    logger.info(
        "voice_triggers: %d candidates → %d passed threshold → %d extracted",
        len(raw_candidates), len(passing), len(results),
    )
    return results
