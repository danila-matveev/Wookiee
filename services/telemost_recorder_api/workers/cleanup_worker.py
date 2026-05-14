"""Cleanup old recording artefacts.

Runs hourly. Deletes DATA_DIR/<meeting_id>/ folders older than
AUDIO_RETENTION_DAYS. Aligned with Supabase Storage signed URL TTL.

The recorder pipeline finishes by ingesting raw_segments.json into Postgres
and uploading the opus file to Supabase Storage. After that, the on-disk
folder is dead weight — only useful for forensics within the retention
window. Sweeping it keeps the data volume from growing unbounded across
months of meetings.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from services.telemost_recorder_api.config import AUDIO_RETENTION_DAYS, DATA_DIR

logger = logging.getLogger(__name__)

_TICK_SECONDS = 3600


def _sweep_sync(data_dir: Path, max_age_days: int) -> int:
    """Synchronously remove meeting folders older than max_age_days.

    Returns the number of folders deleted. Missing data_dir is treated as
    a no-op (returns 0) so first-boot doesn't spam errors.
    """
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    if not data_dir.exists():
        return 0
    for meeting_dir in data_dir.iterdir():
        if not meeting_dir.is_dir():
            continue
        try:
            mtime = meeting_dir.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            shutil.rmtree(meeting_dir, ignore_errors=True)
            removed += 1
    return removed


async def run_forever() -> None:
    """Tick once an hour, sweeping old meeting folders.

    File IO is dispatched to a thread so a slow filesystem (e.g. NFS) can't
    block the event loop. Errors are logged and the loop continues — a
    transient OS error shouldn't take the worker down permanently.
    """
    logger.info(
        "Cleanup worker starting (retention=%d days, tick=%ds)",
        AUDIO_RETENTION_DAYS, _TICK_SECONDS,
    )
    while True:
        try:
            removed = await asyncio.to_thread(
                _sweep_sync, DATA_DIR, AUDIO_RETENTION_DAYS
            )
        except Exception:  # noqa: BLE001
            logger.exception("cleanup sweep failed")
            removed = 0
        if removed:
            logger.info("Cleanup removed %d meeting folder(s)", removed)
        await asyncio.sleep(_TICK_SECONDS)
