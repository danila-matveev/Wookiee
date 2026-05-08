"""Recorder worker.

Phase 0 loop:
1. Pick one queued meeting via UPDATE ... FOR UPDATE SKIP LOCKED -> status='recording'.
2. Spawn telemost_recorder container with meeting_id label.
3. monitor_container with hard limit RECORDING_HARD_LIMIT_HOURS.
4. On exit: stop container if timed_out, then read artefacts and transition to
   'postprocessing' or 'failed'. Postprocess worker (Task 17) picks it up next.
5. Sleep _BUSY_SLEEP_SECONDS if processed, _IDLE_SLEEP_SECONDS if queue empty.

Phase 1 will increase MAX_PARALLEL_RECORDINGS and add orphan reconciliation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from services.telemost_recorder_api.config import (
    DATA_DIR,
    MAX_PARALLEL_RECORDINGS,
    RECORDING_HARD_LIMIT_HOURS,
)
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.docker_client import (
    monitor_container,
    spawn_recorder_container,
    stop_container,
)

logger = logging.getLogger(__name__)

_BUSY_SLEEP_SECONDS = 2
_IDLE_SLEEP_SECONDS = 5


async def _pick_queued() -> Optional[dict]:
    """Atomically grab one queued row and transition to 'recording'.

    Uses FOR UPDATE SKIP LOCKED so concurrent workers don't fight over the
    same row in the future (Phase 1).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE telemost.meetings
                SET status='recording', started_at=now()
                WHERE id = (
                    SELECT id FROM telemost.meetings
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, meeting_url, triggered_by
                """,
            )
    return dict(row) if row else None


async def _finalize_recording(
    meeting_id: UUID,
    exit_code: int,
    logs: str,
    timed_out: bool,
) -> None:
    """Read artefacts, transition meeting to postprocessing/failed."""
    pool = await get_pool()
    artefact_dir = DATA_DIR / str(meeting_id)
    raw_segments_path = artefact_dir / "raw_segments.json"
    audio_path = artefact_dir / "audio.opus"

    raw_segments = None
    if raw_segments_path.exists():
        try:
            raw_segments = json.loads(raw_segments_path.read_text())
        except Exception:  # noqa: BLE001
            logger.exception("Failed to parse raw_segments for %s", meeting_id)

    has_audio = audio_path.exists()
    success = (
        not timed_out
        and exit_code == 0
        and (raw_segments is not None or has_audio)
    )

    async with pool.acquire() as conn:
        if success:
            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='postprocessing',
                    ended_at=now(),
                    raw_segments=$2::jsonb
                WHERE id = $1
                """,
                meeting_id,
                json.dumps(raw_segments or []),
            )
            logger.info(
                "Recording %s ready for postprocess (segments=%d)",
                meeting_id,
                len(raw_segments or []),
            )
        else:
            if timed_out:
                error_msg = (
                    f"recorder timeout after {RECORDING_HARD_LIMIT_HOURS}h; "
                    f"logs tail: {logs[-500:]}"
                )
            else:
                error_msg = f"recorder exit_code={exit_code}; logs tail: {logs[-500:]}"
            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='failed',
                    ended_at=now(),
                    error=$2
                WHERE id = $1
                """,
                meeting_id,
                error_msg,
            )
            logger.warning("Recording %s failed: %s", meeting_id, error_msg)


async def process_one() -> bool:
    """Pick one queued meeting, run it, finalize. Returns True if processed."""
    pick = await _pick_queued()
    if not pick:
        return False
    meeting_id = pick["id"]
    logger.info("Recording meeting %s url=%s", meeting_id, pick["meeting_url"])
    container_id = await asyncio.to_thread(
        spawn_recorder_container,
        meeting_id=meeting_id,
        meeting_url=pick["meeting_url"],
        data_dir=str(DATA_DIR),
    )
    timeout = RECORDING_HARD_LIMIT_HOURS * 3600
    result = await monitor_container(container_id, timeout_seconds=timeout)
    if result.get("timed_out"):
        # Timeout: container is still running, kill it before finalizing.
        await asyncio.to_thread(stop_container, container_id)
    await _finalize_recording(
        meeting_id,
        result["exit_code"],
        result["logs"],
        result.get("timed_out", False),
    )
    return True


async def run_forever() -> None:
    """Worker loop. Phase 0 keeps MAX_PARALLEL_RECORDINGS=1."""
    logger.info(
        "Recorder worker starting (max_parallel=%d, hard_limit=%dh)",
        MAX_PARALLEL_RECORDINGS,
        RECORDING_HARD_LIMIT_HOURS,
    )
    while True:
        try:
            processed = await process_one()
        except Exception:  # noqa: BLE001
            logger.exception("recorder_worker.process_one crashed")
            processed = False
        await asyncio.sleep(
            _BUSY_SLEEP_SECONDS if processed else _IDLE_SLEEP_SECONDS
        )
