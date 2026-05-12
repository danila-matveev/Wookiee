"""Repository helpers: load, delete, transcript render."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)

_ID_PREFIX_LEN = 8
_BLOCK_STATUSES = {"queued", "recording", "postprocessing"}


def _ms_to_mmss(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def build_transcript_text(paragraphs: list[dict[str, Any]]) -> str:
    if not paragraphs:
        return "(пустой transcript)"
    out = []
    for p in paragraphs:
        ts = _ms_to_mmss(p.get("start_ms", 0))
        speaker = p.get("speaker", "?")
        text = p.get("text", "")
        out.append(f"[{ts}] {speaker}: {text}")
    return "\n".join(out)


async def load_meeting_by_short_id(
    short_id: str,
    owner_telegram_id: int,
) -> Optional[dict[str, Any]]:
    """Find a non-deleted meeting whose UUID starts with short_id AND user is owner/invitee."""
    if not short_id or len(short_id) < 4:
        return None
    pool = await get_pool()
    invitee_filter = json.dumps([{"telegram_id": owner_telegram_id}])
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, triggered_by, organizer_id, status, started_at,
                   duration_seconds, summary, tags, processed_paragraphs, error,
                   invitees, deleted_at
            FROM telemost.meetings
            WHERE deleted_at IS NULL
              AND id::text LIKE $1 || '%'
              AND (
                triggered_by = $2
                OR organizer_id = $2
                OR invitees @> $3::jsonb
              )
            LIMIT 1
            """,
            short_id,
            owner_telegram_id,
            invitee_filter,
        )
    if not row:
        return None
    out = dict(row)
    for k in ("summary", "processed_paragraphs", "invitees"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


async def delete_meeting_for_owner(
    meeting_id: UUID,
    owner_telegram_id: int,
) -> bool:
    """Soft-delete (deleted_at=now()) iff owner matches and status not in active set."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, triggered_by
            FROM telemost.meetings
            WHERE id = $1 AND deleted_at IS NULL AND triggered_by = $2
            """,
            meeting_id,
            owner_telegram_id,
        )
        if not row:
            return False
        if row["status"] in _BLOCK_STATUSES:
            return False
        await conn.execute(
            "UPDATE telemost.meetings SET deleted_at = now() WHERE id = $1",
            meeting_id,
        )
    logger.info("Soft-deleted meeting %s by user %s", meeting_id, owner_telegram_id)
    return True
