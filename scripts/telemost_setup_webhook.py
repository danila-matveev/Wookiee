"""Bot setup runbook: setWebhook + setMyCommands + setMyDescription + (optional) setMyPhoto.

One-shot operator script. Idempotent: re-runs are safe — Telegram overwrites
webhook/commands/description on each call. Avatar is only uploaded if the
bot has no profile photo yet (getUserProfilePhotos check).

Usage:
    .venv/bin/python -m scripts.telemost_setup_webhook \\
        --webhook-url https://recorder.os.wookiee.shop/telegram/webhook
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import httpx

from services.telemost_recorder_api.config import (
    ASSETS_DIR,
    TELEMOST_BOT_ID,
    TELEMOST_BOT_TOKEN,
    TELEMOST_WEBHOOK_SECRET,
)
from services.telemost_recorder_api.telegram_client import tg_call

logger = logging.getLogger(__name__)


_COMMANDS = [
    {"command": "start", "description": "Начать работу"},
    {"command": "help", "description": "Справка"},
    {"command": "record", "description": "Записать встречу: /record <ссылка>"},
    {"command": "status", "description": "Твои активные/последние записи"},
    {"command": "list", "description": "Последние 10 встреч с твоим участием"},
]

_DESCRIPTION = (
    "Саймон — хожу на ваши Telemost-встречи и записываю их. "
    "Расшифровка, саммари в DM, экспорт в Notion. Доступ через Bitrix24-roster."
)


async def tg_set_photo_if_missing(avatar_path: Path) -> None:
    """Upload bot avatar via setMyPhoto, but only if the bot has no profile photo yet.

    Telegram caches bot avatars aggressively; we don't want to overwrite a
    manually-set avatar on every re-run.
    """
    photos = await tg_call("getUserProfilePhotos", user_id=TELEMOST_BOT_ID, limit=1)
    if photos.get("total_count", 0) > 0:
        logger.info("Bot already has avatar, skip setMyPhoto")
        return

    url = f"https://api.telegram.org/bot{TELEMOST_BOT_TOKEN}/setMyPhoto"
    with avatar_path.open("rb") as fh:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                files={"photo": ("avatar.png", fh, "image/png")},
            )
    body = resp.json()
    if not body.get("ok"):
        logger.warning("setMyPhoto failed: %s", body.get("description"))
    else:
        logger.info("Avatar set")


async def setup(webhook_url: str) -> None:
    """Run the full bot configuration flow against the Telegram Bot API."""
    await tg_call(
        "setWebhook",
        url=webhook_url,
        secret_token=TELEMOST_WEBHOOK_SECRET,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Webhook set: %s", webhook_url)

    await tg_call("setMyCommands", commands=_COMMANDS)
    logger.info("Commands set: %d entries", len(_COMMANDS))

    await tg_call("setMyDescription", description=_DESCRIPTION)
    logger.info("Description set")

    avatar = ASSETS_DIR / "avatar.png"
    if avatar.exists():
        await tg_set_photo_if_missing(avatar)
    else:
        logger.warning("Avatar not found at %s", avatar)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--webhook-url",
        default="https://recorder.os.wookiee.shop/telegram/webhook",
        help="Public HTTPS endpoint that Telegram will POST updates to",
    )
    args = parser.parse_args()
    asyncio.run(setup(args.webhook_url))


if __name__ == "__main__":
    main()
