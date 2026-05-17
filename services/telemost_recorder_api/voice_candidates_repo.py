"""Persistence layer for voice-trigger candidates (T7).

Single source of truth for ``telemost.voice_trigger_candidates`` CRUD.
Used by:

  * ``voice_triggers.py`` — INSERTs a row per Stage 2 result so the keyboard
    callback_data can reference a stable UUID.
  * ``handlers/voice_actions.py`` — fetches by id when the operator clicks
    a button, then transitions ``status`` (``created`` / ``ignored`` /
    ``edited``) and records the resulting ``bitrix_id``.

Idempotency: the migration uses ``gen_random_uuid()`` for ids so multiple
inserts of the same logical candidate are distinct rows. We rely on the
caller (Stage 2 pipeline) to not double-insert within one extract() run —
deduplication on transcript content is out of scope.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)


async def insert_candidate(
    *,
    meeting_id: UUID | None,
    intent: str,
    speaker: str,
    raw_text: str,
    extracted_fields: dict[str, Any],
) -> UUID:
    """INSERT a new voice-trigger candidate. Returns the freshly minted UUID.

    Args:
        meeting_id: Owning meeting (FK to telemost.meetings.id). May be None
                    for unit-tests / dry-runs where no meeting row exists.
        intent: One of 'task', 'meeting', 'note', 'attention', 'reminder'.
                Validated by the table CHECK constraint.
        speaker: Display name of the person who issued the command.
        raw_text: Verbatim quote of the trigger from the transcript.
        extracted_fields: Per-intent JSON blob returned by Stage 2 slot-fill.

    Returns:
        UUID assigned by the database.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO telemost.voice_trigger_candidates
                (meeting_id, intent, speaker, raw_text, extracted_fields)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
            """,
            meeting_id,
            intent,
            speaker,
            raw_text,
            json.dumps(extracted_fields, ensure_ascii=False),
        )
    return row["id"]


async def get_candidate(candidate_id: UUID) -> dict[str, Any] | None:
    """Fetch a candidate row by id. Returns None when not found.

    The returned dict has keys: id, meeting_id, intent, speaker, raw_text,
    extracted_fields (parsed dict), status, bitrix_id, created_at.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, meeting_id, intent, speaker, raw_text,
                   extracted_fields, status, bitrix_id, created_at
            FROM telemost.voice_trigger_candidates
            WHERE id = $1
            """,
            candidate_id,
        )
    if row is None:
        return None
    out = dict(row)
    if isinstance(out.get("extracted_fields"), str):
        out["extracted_fields"] = json.loads(out["extracted_fields"])
    return out


async def mark_created(candidate_id: UUID, bitrix_id: str) -> bool:
    """Transition status pending → created and store the resulting Bitrix id.

    Returns True iff exactly one row was updated. False means the candidate
    was already created / ignored / edited — typical race when the operator
    double-clicks the button before Telegram debounces.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE telemost.voice_trigger_candidates
            SET status = 'created', bitrix_id = $2
            WHERE id = $1 AND status = 'pending'
            """,
            candidate_id,
            bitrix_id,
        )
    return result.endswith(" 1")


async def mark_ignored(candidate_id: UUID) -> bool:
    """Transition status pending → ignored. Returns True iff one row updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE telemost.voice_trigger_candidates
            SET status = 'ignored'
            WHERE id = $1 AND status = 'pending'
            """,
            candidate_id,
        )
    return result.endswith(" 1")


async def mark_edited(candidate_id: UUID) -> bool:
    """Transition status pending → edited (Phase 2 placeholder for inline form)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE telemost.voice_trigger_candidates
            SET status = 'edited'
            WHERE id = $1 AND status = 'pending'
            """,
            candidate_id,
        )
    return result.endswith(" 1")
