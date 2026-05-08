"""Telegram command dispatch.

Phase 0 will eventually handle: /start /help /record /status /list. This
file is intentionally thin in Task 9 — Task 10+ flesh it out per command.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def handle_update(update: dict) -> None:
    """Top-level dispatcher. Logs the message and returns. Real routing
    arrives in subsequent tasks.
    """
    msg = update.get("message")
    if not msg:
        return
    text = (msg.get("text") or "").strip()
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    chat_type = msg["chat"]["type"]
    if chat_type != "private":
        # Phase 1 will handle group-chat leave; Phase 0 just ignores.
        return
    logger.info("Received from user_id=%d chat_id=%d text=%r", user_id, chat_id, text[:100])
