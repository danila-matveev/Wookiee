"""Postprocess worker.

Loop:
1. Pick a meeting with status='postprocessing' (FOR UPDATE SKIP LOCKED).
2. If raw_segments is empty -> mark done with empty-fallback summary, notify.
3. Else: call LLM postprocess, update fields, mark done, notify.
4. On exception: mark failed, notify with error message.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.llm_postprocess import (
    LLMPostprocessError,
    postprocess_meeting,
)
from services.telemost_recorder_api.notifier import notify_meeting_result

logger = logging.getLogger(__name__)

_BUSY_SLEEP_SECONDS = 2
_IDLE_SLEEP_SECONDS = 5

_JSONB_FIELDS = {
    "summary",
    "speakers_map",
    "processed_paragraphs",
    "raw_segments",
    "invitees",
}


async def _pick_postprocessing() -> dict[str, Any] | None:
    """Select one row in 'postprocessing' status.

    Picking does NOT mutate status; the worker reads, processes, then
    `_update_meeting` flips to 'done' or 'failed'. FOR UPDATE SKIP LOCKED
    keeps concurrent workers from grabbing the same row when Phase 1 raises
    the parallelism cap.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, raw_segments, triggered_by, title, invitees
                FROM telemost.meetings
                WHERE status = 'postprocessing'
                ORDER BY ended_at NULLS LAST
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
            )
    if not row:
        return None
    out = dict(row)
    if isinstance(out.get("raw_segments"), str):
        out["raw_segments"] = json.loads(out["raw_segments"])
    if isinstance(out.get("invitees"), str):
        out["invitees"] = json.loads(out["invitees"])
    return out


async def _update_meeting(meeting_id: UUID, status: str, **fields: Any) -> None:
    """Update meeting row with dynamic SET clause.

    `_JSONB_FIELDS` are encoded via `json.dumps(..., ensure_ascii=False)`
    and cast to ::jsonb. Other fields (e.g. `tags text[]`, `error text`)
    pass through directly — asyncpg adapts python list[str] to text[] natively.
    """
    pool = await get_pool()
    set_clauses = ["status = $2"]
    args: list[Any] = [meeting_id, status]
    idx = 3
    for k, v in fields.items():
        if k in _JSONB_FIELDS:
            args.append(json.dumps(v, ensure_ascii=False))
            set_clauses.append(f"{k} = ${idx}::jsonb")
        else:
            args.append(v)
            set_clauses.append(f"{k} = ${idx}")
        idx += 1
    query = f"UPDATE telemost.meetings SET {', '.join(set_clauses)} WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, *args)


async def process_one() -> bool:
    """Pick one postprocessing meeting and run it through. Returns True if processed."""
    pick = await _pick_postprocessing()
    if not pick:
        return False
    meeting_id = pick["id"]
    segments = pick["raw_segments"] or []
    invitees = pick["invitees"] or []
    logger.info("Postprocessing meeting %s (segments=%d)", meeting_id, len(segments))

    try:
        if not segments:
            await _update_meeting(
                meeting_id,
                "done",
                summary={"empty": True, "note": "no_speech_detected"},
                tags=[],
            )
        else:
            result = await postprocess_meeting(segments, invitees)
            await _update_meeting(
                meeting_id,
                "done",
                processed_paragraphs=result["paragraphs"],
                speakers_map=result["speakers_map"],
                tags=result["tags"],
                summary=result["summary"],
            )
        await notify_meeting_result(meeting_id)
    except LLMPostprocessError as e:
        logger.exception("LLM failed for meeting %s", meeting_id)
        await _update_meeting(meeting_id, "failed", error=f"LLM: {e}")
        await notify_meeting_result(meeting_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Postprocess crashed for meeting %s", meeting_id)
        await _update_meeting(meeting_id, "failed", error=f"unexpected: {e}")
        await notify_meeting_result(meeting_id)
    return True


async def run_forever() -> None:
    """Worker loop. Phase 0 keeps a single instance."""
    logger.info("Postprocess worker starting")
    while True:
        try:
            processed = await process_one()
        except Exception:  # noqa: BLE001
            logger.exception("postprocess_worker.process_one crashed")
            processed = False
        await asyncio.sleep(
            _BUSY_SLEEP_SECONDS if processed else _IDLE_SLEEP_SECONDS
        )
