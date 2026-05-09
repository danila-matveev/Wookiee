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
