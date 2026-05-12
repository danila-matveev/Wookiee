"""Internal routes — dev-loop spawn endpoint.

Used by scripts/telemost_dev_loop.sh to re-enqueue the same meeting URL on a
schedule, so UX iterations on DM/handlers don't require live meetings.

Auth: X-API-Key header must match TELEMOST_INTERNAL_KEY env. If the env var
is unset, the route returns 503 — not enabled in production by default.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


class SpawnRequest(BaseModel):
    meeting_url: str
    triggered_by: int


@router.post("/spawn_recorder")
async def spawn_recorder(
    body: SpawnRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict:
    expected = os.environ.get("TELEMOST_INTERNAL_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Internal routes not enabled")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not is_valid_telemost_url(body.meeting_url):
        raise HTTPException(status_code=400, detail="Invalid Telemost URL")
    canonical = canonicalize_telemost_url(body.meeting_url)

    pool = await get_pool()
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            """
            INSERT INTO telemost.meetings
                (source, triggered_by, meeting_url, organizer_id, invitees, status)
            VALUES ('dev-loop', $1, $2, $1, '[]'::jsonb, 'queued')
            RETURNING id
            """,
            body.triggered_by,
            canonical,
        )
    logger.info("dev-loop enqueued meeting %s for %d", new_id, body.triggered_by)
    return {"meeting_id": str(new_id), "status": "queued"}
