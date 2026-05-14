"""Upload recorded audio to Supabase Storage bucket telemost-audio + signed URL."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import (
    SUPABASE_SERVICE_KEY,
    SUPABASE_STORAGE_TIMEOUT_SECONDS,
    SUPABASE_URL,
)

logger = logging.getLogger(__name__)

_BUCKET = "telemost-audio"
# Mirror the retry posture used by _call_openrouter and _notion_request:
# transient 5xx/429/network blips on Supabase Storage shouldn't drop the
# meeting audio. 1s → 2s → 4s gives ≤7s extra latency in the worst case.
_UPLOAD_RETRIES = 3
_UPLOAD_BACKOFF_BASE = 1.0


class UploadResult(TypedDict):
    signed_url: str
    expires_at: datetime
    object_key: str


def _is_retryable_status(code: int) -> bool:
    return code == 429 or code >= 500


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict,
    label: str,
    content: bytes | None = None,
    json: dict | None = None,
) -> httpx.Response:
    """POST with retry on transient errors (5xx, 429, network).

    Returns the final response; raises the last network error if every
    attempt blew up before getting any HTTP response. 4xx responses are
    returned as-is — the caller decides whether to raise.
    """
    last_error: Exception | None = None
    for attempt in range(_UPLOAD_RETRIES):
        try:
            kwargs: dict = {"headers": headers}
            if content is not None:
                kwargs["content"] = content
            if json is not None:
                kwargs["json"] = json
            resp = await client.post(url, **kwargs)
        except httpx.HTTPError as e:
            last_error = e
            logger.warning(
                "Supabase Storage %s network error attempt %d/%d: %s",
                label, attempt + 1, _UPLOAD_RETRIES, e,
            )
            if attempt < _UPLOAD_RETRIES - 1:
                await asyncio.sleep(_UPLOAD_BACKOFF_BASE * (2 ** attempt))
            continue
        if not _is_retryable_status(resp.status_code):
            return resp
        last_error = RuntimeError(
            f"Supabase Storage {label} {resp.status_code}: {resp.text[:200]}"
        )
        logger.warning(
            "Supabase Storage %s %d on attempt %d/%d, retrying",
            label, resp.status_code, attempt + 1, _UPLOAD_RETRIES,
        )
        if attempt < _UPLOAD_RETRIES - 1:
            await asyncio.sleep(_UPLOAD_BACKOFF_BASE * (2 ** attempt))
    assert last_error is not None
    raise RuntimeError(
        f"Supabase Storage {label} unavailable after {_UPLOAD_RETRIES} retries: {last_error}"
    )


async def upload_audio_to_storage(
    audio_path: Path,
    *,
    meeting_id: UUID,
    ttl_days: int,
) -> UploadResult:
    """Upload audio file to Supabase Storage and return a signed URL."""
    object_key = f"meetings/{meeting_id}/audio.opus"
    headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}

    async with httpx.AsyncClient(timeout=SUPABASE_STORAGE_TIMEOUT_SECONDS) as client:
        with audio_path.open("rb") as f:
            audio_bytes = f.read()
        upload_url = f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{object_key}"
        resp = await _post_with_retry(
            client,
            upload_url,
            headers={
                **headers,
                "Content-Type": "audio/ogg",
                "x-upsert": "true",
            },
            label="upload",
            content=audio_bytes,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Storage upload failed [{resp.status_code}]: {resp.text}"
            )

        ttl_seconds = ttl_days * 86400
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{_BUCKET}/{object_key}"
        sign_resp = await _post_with_retry(
            client,
            sign_url,
            headers={**headers, "Content-Type": "application/json"},
            label="sign",
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
