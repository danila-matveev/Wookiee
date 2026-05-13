"""Tests for audio_uploader.upload_audio_to_storage."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
import pytest

from services.telemost_recorder_api.audio_uploader import upload_audio_to_storage


_MEETING_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_upload_returns_signed_url(tmp_path):
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake audio")

    upload_resp = httpx.Response(
        200, json={"Key": f"telemost-audio/meetings/{_MEETING_ID}/audio.opus"}
    )
    sign_resp = httpx.Response(
        200,
        json={"signedURL": "/storage/v1/object/sign/telemost-audio/abc?token=xyz"},
    )

    async def fake_post(url, *a, **kw):
        if "object/" in url and "sign" not in url:
            return upload_resp
        if "sign" in url:
            return sign_resp
        raise AssertionError(f"unexpected url {url}")

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        result = await upload_audio_to_storage(
            audio_file, meeting_id=_MEETING_ID, ttl_days=30
        )

    assert result["signed_url"].startswith("https://")
    assert "telemost-audio" in result["signed_url"]
    assert isinstance(result["expires_at"], datetime)


@pytest.mark.asyncio
async def test_upload_raises_on_upload_failure(tmp_path):
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    fail_resp = httpx.Response(500, json={"error": "boom"})

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=fail_resp)):
        with pytest.raises(RuntimeError):
            await upload_audio_to_storage(
                audio_file, meeting_id=_MEETING_ID, ttl_days=30
            )


@pytest.mark.asyncio
async def test_upload_raises_on_sign_failure(tmp_path):
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    upload_resp = httpx.Response(200, json={"Key": "ok"})
    # 403 is a 4xx — not retryable, must bubble up immediately
    sign_fail = httpx.Response(403, json={"error": "forbidden"})

    async def fake_post(url, *a, **kw):
        if "sign" in url:
            return sign_fail
        return upload_resp

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        with pytest.raises(RuntimeError, match="Sign URL failed"):
            await upload_audio_to_storage(
                audio_file, meeting_id=_MEETING_ID, ttl_days=30
            )


@pytest.mark.asyncio
async def test_upload_retries_on_5xx_then_succeeds(tmp_path, monkeypatch):
    """Transient Supabase Storage 5xx must not lose the audio file.

    Mirrors the retry strategy already used for OpenRouter (_call_openrouter)
    and Notion (_notion_request): 3 attempts with exponential backoff on
    5xx and 429 + network errors. Aligning with the rest of the codebase
    keeps the error-handling model predictable.
    """
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    # Make backoff sleeps no-ops so the test stays fast.
    sleeps: list[float] = []

    async def fake_sleep(d):
        sleeps.append(d)

    monkeypatch.setattr(
        "services.telemost_recorder_api.audio_uploader.asyncio.sleep", fake_sleep
    )

    call_log: list[str] = []
    sign_resp = httpx.Response(
        200,
        json={"signedURL": "/storage/v1/object/sign/telemost-audio/abc?t=z"},
    )

    upload_attempts = {"n": 0}

    async def fake_post(url, *a, **kw):
        if "sign" in url:
            call_log.append("sign")
            return sign_resp
        upload_attempts["n"] += 1
        call_log.append(f"upload#{upload_attempts['n']}")
        if upload_attempts["n"] < 3:
            return httpx.Response(503, json={"error": "transient"})
        return httpx.Response(200, json={"Key": "ok"})

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        result = await upload_audio_to_storage(
            audio_file, meeting_id=_MEETING_ID, ttl_days=30
        )

    assert result["signed_url"].startswith("https://")
    assert upload_attempts["n"] == 3, (
        f"upload should have been retried 3 times, got {upload_attempts['n']}"
    )
    # Backoff was actually applied between retries (1.0 then 2.0 by default).
    assert len(sleeps) >= 2, f"expected ≥2 backoff sleeps, got {sleeps}"
    assert sleeps[0] < sleeps[1], (
        f"backoff must be exponential, got {sleeps}"
    )


@pytest.mark.asyncio
async def test_upload_fails_after_all_retries(tmp_path, monkeypatch):
    """If Supabase Storage stays 5xx for all attempts, we surface the error
    so the worker can mark the meeting and retry the whole post-process."""
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    async def fake_sleep(d):
        return None

    monkeypatch.setattr(
        "services.telemost_recorder_api.audio_uploader.asyncio.sleep", fake_sleep
    )

    upload_attempts = {"n": 0}

    async def fake_post(url, *a, **kw):
        upload_attempts["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        with pytest.raises(RuntimeError):
            await upload_audio_to_storage(
                audio_file, meeting_id=_MEETING_ID, ttl_days=30
            )

    assert upload_attempts["n"] >= 3, (
        f"expected ≥3 retry attempts before giving up, got {upload_attempts['n']}"
    )


@pytest.mark.asyncio
async def test_upload_retries_on_network_error(tmp_path, monkeypatch):
    """httpx.ConnectError mid-upload must trigger a retry, not abort."""
    audio_file = tmp_path / "audio.opus"
    audio_file.write_bytes(b"fake")

    async def fake_sleep(d):
        return None

    monkeypatch.setattr(
        "services.telemost_recorder_api.audio_uploader.asyncio.sleep", fake_sleep
    )

    sign_resp = httpx.Response(
        200,
        json={"signedURL": "/storage/v1/object/sign/telemost-audio/abc?t=z"},
    )
    upload_attempts = {"n": 0}

    async def fake_post(url, *a, **kw):
        if "sign" in url:
            return sign_resp
        upload_attempts["n"] += 1
        if upload_attempts["n"] == 1:
            raise httpx.ConnectError("dns")
        return httpx.Response(200, json={"Key": "ok"})

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        result = await upload_audio_to_storage(
            audio_file, meeting_id=_MEETING_ID, ttl_days=30
        )

    assert result["signed_url"].startswith("https://")
    assert upload_attempts["n"] == 2
