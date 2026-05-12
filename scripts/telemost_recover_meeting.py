"""Recover a meeting whose transcript exists on disk but isn't in Supabase.

Usage:
    python scripts/telemost_recover_meeting.py <meeting_id>

Reads <DATA_DIR>/<meeting_id>/raw_segments.json (falls back to
transcript.json), loads into telemost.meetings.raw_segments, flips
status to 'postprocessing' so the worker picks it up, and reset
notified_at so the user gets the new DM with real summary.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from services.telemost_recorder_api.config import DATA_DIR
from services.telemost_recorder_api.db import get_pool


async def recover(meeting_id: str) -> None:
    artefact_dir = DATA_DIR / meeting_id
    candidate = artefact_dir / "raw_segments.json"
    if not candidate.exists():
        candidate = artefact_dir / "transcript.json"
    if not candidate.exists():
        print(
            f"ERROR: neither raw_segments.json nor transcript.json in {artefact_dir}",
            file=sys.stderr,
        )
        sys.exit(2)

    payload = candidate.read_text()
    segments = json.loads(payload)
    print(f"Loaded {len(segments)} segments from {candidate.name}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE telemost.meetings
            SET raw_segments = $2::jsonb,
                status = 'postprocessing',
                notified_at = NULL
            WHERE id = $1
            """,
            meeting_id,
            payload,
        )
    print(f"UPDATE result: {result}")
    print("Postprocess worker will pick up within ~5 sec. Notifier will resend DM.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/telemost_recover_meeting.py <meeting_id>",
            file=sys.stderr,
        )
        sys.exit(1)
    asyncio.run(recover(sys.argv[1]))
