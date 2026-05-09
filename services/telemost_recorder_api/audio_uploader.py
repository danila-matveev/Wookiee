"""Upload recorded audio to Supabase Storage bucket telemost-audio + signed URL."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import (
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)

_BUCKET = "telemost-audio"


async def upload_audio_to_storage(
    audio_path: Path,
    *,
    meeting_id: UUID,
    ttl_days: int,
) -> dict:
    """Upload audio file to Supabase Storage and return a signed URL.

    Returns a dict with keys:
        - signed_url: full https URL to the signed object
        - expires_at: timezone-aware datetime when the signed URL expires
        - object_key: storage path within the bucket
    """
    object_key = f"meetings/{meeting_id}/audio.opus"
    headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}

    async with httpx.AsyncClient(timeout=300) as client:
        with audio_path.open("rb") as f:
            upload_url = f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{object_key}"
            resp = await client.post(
                upload_url,
                headers={
                    **headers,
                    "Content-Type": "audio/ogg",
                    "x-upsert": "true",
                },
                content=f.read(),
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Storage upload failed [{resp.status_code}]: {resp.text}"
            )

        ttl_seconds = ttl_days * 86400
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{_BUCKET}/{object_key}"
        sign_resp = await client.post(
            sign_url,
            headers={**headers, "Content-Type": "application/json"},
            json={"expiresIn": ttl_seconds},
        )
        if sign_resp.status_code >= 400:
            raise RuntimeError(
                f"Sign URL failed [{sign_resp.status_code}]: {sign_resp.text}"
            )
        rel = sign_resp.json()["signedURL"]
        signed = (
            f"{SUPABASE_URL}/storage/v1{rel}" if rel.startswith("/") else rel
        )

    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    logger.info("Uploaded audio for %s, expires %s", meeting_id, expires_at)
    return {
        "signed_url": signed,
        "expires_at": expires_at,
        "object_key": object_key,
    }
