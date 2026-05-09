from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scripts.telemost_setup_webhook import setup, tg_set_photo_if_missing


@pytest.mark.asyncio
async def test_setup_calls_all_endpoints():
    captured: list[str] = []

    async def fake_call(method, **payload):
        captured.append(method)
        return {}

    with patch(
        "scripts.telemost_setup_webhook.tg_call",
        AsyncMock(side_effect=fake_call),
    ), patch(
        "scripts.telemost_setup_webhook.tg_set_photo_if_missing",
        AsyncMock(),
    ):
        await setup(webhook_url="https://recorder.os.wookiee.shop/telegram/webhook")

    assert "setWebhook" in captured
    assert "setMyCommands" in captured
    assert "setMyDescription" in captured


@pytest.mark.asyncio
async def test_set_photo_skips_when_avatar_already_set(tmp_path):
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    posts: list[str] = []

    async def fake_post(url, **kw):
        posts.append(url)
        return httpx.Response(200, json={"ok": True})

    with patch(
        "scripts.telemost_setup_webhook.tg_call",
        AsyncMock(return_value={"total_count": 1}),
    ), patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        await tg_set_photo_if_missing(avatar)

    assert posts == []  # skipped because total_count > 0


@pytest.mark.asyncio
async def test_set_photo_uploads_when_missing(tmp_path):
    avatar = tmp_path / "avatar.png"
    avatar.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    posts: list[str] = []

    async def fake_post(url, **kw):
        posts.append(url)
        return httpx.Response(200, json={"ok": True})

    with patch(
        "scripts.telemost_setup_webhook.tg_call",
        AsyncMock(return_value={"total_count": 0}),
    ), patch("httpx.AsyncClient.post", AsyncMock(side_effect=fake_post)):
        await tg_set_photo_if_missing(avatar)

    assert len(posts) == 1
    assert "setMyPhoto" in posts[0]
