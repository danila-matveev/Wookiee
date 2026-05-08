"""Telegram command dispatch.

Phase 0 commands: /start, /help, /record. /status /list arrive in subsequent
tasks but the routing skeleton is here.
"""
from __future__ import annotations

import logging

from services.telemost_recorder_api.handlers.help import handle_help
from services.telemost_recorder_api.handlers.record import handle_record
from services.telemost_recorder_api.handlers.start import handle_start

logger = logging.getLogger(__name__)


async def handle_update(update: dict) -> None:
    msg = update.get("message")
    if not msg:
        return
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    sender = msg.get("from") or {}
    chat_id = chat.get("id")
    user_id = sender.get("id")
    chat_type = chat.get("type")
    if chat_id is None or user_id is None:
        return
    if chat_type != "private":
        return  # Phase 1 will handle group leave
    logger.info("Cmd from user_id=%d: %s", user_id, text[:100])

    cmd, _, args = text.partition(" ")
    cmd = cmd.split("@", 1)[0]  # strip @bot_username (group-style mention)
    if cmd == "/start":
        await handle_start(chat_id, user_id)
    elif cmd == "/help":
        await handle_help(chat_id)
    elif cmd == "/record":
        await handle_record(chat_id, user_id, args)
    # /status, /list — later tasks
