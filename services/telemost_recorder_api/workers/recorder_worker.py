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
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.audio_uploader import upload_audio_to_storage
from services.telemost_recorder_api.config import (
    AUDIO_RETENTION_DAYS,
    DATA_DIR,
    HOST_DATA_DIR,
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
_LOG_PREVIEW_LEN = 500


async def _pick_queued() -> dict[str, Any] | None:
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

    has_audio = audio_path.exists() and audio_path.stat().st_size > 0
    # `raw_segments=None` means the recorder reached audio but transcription
    # crashed inside the container (or never ran). Treat that as a failure
    # so the user sees a real error message, not a misleading "тишина".
    transcription_lost = has_audio and raw_segments is None
    success = (
        not timed_out
        and exit_code == 0
        and not transcription_lost
        and (raw_segments is not None or has_audio)
    )

    async with pool.acquire() as conn:
        if success:
            audio_signed_url: str | None = None
            audio_expires = None
            if has_audio:
                try:
                    upload = await upload_audio_to_storage(
                        audio_path,
                        meeting_id=meeting_id,
                        ttl_days=AUDIO_RETENTION_DAYS,
                    )
                    audio_signed_url = upload["signed_url"]
                    audio_expires = upload["expires_at"]
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Audio upload failed for %s — leaving local",
                        meeting_id,
                    )
            await conn.execute(
                """
                UPDATE telemost.meetings
                SET status='postprocessing',
                    ended_at=now(),
                    raw_segments=$2::jsonb,
                    audio_path=$3,
                    audio_expires_at=$4
                WHERE id = $1
                """,
                meeting_id,
                json.dumps(raw_segments or []),
                audio_signed_url,
                audio_expires,
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
                    f"logs tail: {logs[-_LOG_PREVIEW_LEN:]}"
                )
            elif transcription_lost:
                error_msg = (
                    f"recorder finished but transcript missing "
                    f"(audio captured, transcription crashed inside container); "
                    f"logs tail: {logs[-_LOG_PREVIEW_LEN:]}"
                )
            else:
                error_msg = (
                    f"recorder exit_code={exit_code}; "
                    f"logs tail: {logs[-_LOG_PREVIEW_LEN:]}"
                )
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
        # HOST_DATA_DIR (not DATA_DIR): when the API is containerised and
        # talks to host docker.sock, the daemon resolves the volume source
        # against the host filesystem. DATA_DIR (=/app/data/telemost inside
        # the API container) would mount an empty/non-existent host dir.
        data_dir=str(HOST_DATA_DIR),
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
    """Worker loop with bounded concurrency.

    Up to MAX_PARALLEL_RECORDINGS process_one() coroutines run in parallel.
    Each holds a semaphore slot for the full lifetime of one recorder
    container (spawn -> monitor -> finalize), so memory/CPU caps on the host
    bound the slot count.
    """
    sem = asyncio.Semaphore(MAX_PARALLEL_RECORDINGS)
    logger.info(
        "Recorder worker starting (max_parallel=%d, hard_limit=%dh)",
        MAX_PARALLEL_RECORDINGS,
        RECORDING_HARD_LIMIT_HOURS,
    )

    async def _slot_runner() -> None:
        while True:
            async with sem:
                try:
                    processed = await process_one()
                except Exception:  # noqa: BLE001
                    logger.exception("recorder_worker.process_one crashed")
                    processed = False
            await asyncio.sleep(
                _BUSY_SLEEP_SECONDS if processed else _IDLE_SLEEP_SECONDS
            )

    runners = [
        asyncio.create_task(_slot_runner())
        for _ in range(MAX_PARALLEL_RECORDINGS)
    ]
    try:
        await asyncio.gather(*runners)
    finally:
        for r in runners:
            r.cancel()
