"""Telegram webhook entry point. Validates secret, hands off to dispatcher.

Returns HTTP 200 even on dispatcher errors (Telegram retries non-2xx for ~24h
which would amplify any bug). The dispatcher itself is responsible for surfacing
errors to the user via DM where appropriate.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from services.telemost_recorder_api.config import TELEMOST_WEBHOOK_SECRET

logger = logging.getLogger(__name__)
router = APIRouter()


async def dispatch_update(update: dict) -> None:
    """Route a Telegram Update to the appropriate command handler.

    Defined here so tests can patch this name; the actual handler lives in
    ``services.telemost_recorder_api.handlers``.
    """
    from services.telemost_recorder_api.handlers import handle_update

    await handle_update(update)


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token,
        TELEMOST_WEBHOOK_SECRET,
    ):
        raise HTTPException(status_code=401, detail="invalid secret token")
    update = await request.json()
    try:
        await dispatch_update(update)
    except Exception:
        logger.exception(
            "dispatch_update failed for update_id=%s",
            update.get("update_id"),
        )
    return {"ok": True}
