"""Telegram update dispatch — messages + callback_query.

Phase 0 commands: /start, /help, /record, /status, /list.
Inline buttons (callback_query): menu:list, menu:status, menu:help.
"""
from __future__ import annotations

import logging

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.handlers.add_telemost import handle_add_telemost
from services.telemost_recorder_api.handlers.voice_actions import (
    handle_meeting_create,
    handle_meeting_edit,
    handle_meeting_ignore,
    handle_task_create,
    handle_task_edit,
    handle_task_ignore,
)
from services.telemost_recorder_api.handlers.voice_trigger_disabled import handle_voice_disabled
from services.telemost_recorder_api.handlers.help import handle_help
from services.telemost_recorder_api.handlers.list_meetings import handle_list
from services.telemost_recorder_api.handlers.meeting_actions import handle_meet
from services.telemost_recorder_api.handlers.record import handle_record
from services.telemost_recorder_api.handlers.start import handle_start
from services.telemost_recorder_api.handlers.status import handle_status
from services.telemost_recorder_api.keyboards import PLAIN_TEXT_HINT
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_answer_callback_query,
    tg_send_message,
)
from services.telemost_recorder_api.url_canon import is_valid_telemost_url

logger = logging.getLogger(__name__)

_PLAIN_TEXT_HINT = (
    "🤔 *Не нашёл ссылку на Я.Телемост*\n\n"
    "Пришли URL вида:\n"
    "`https://telemost.yandex.ru/j/...`\n\n"
    "Или используй /help для справки."
)


async def handle_update(update: dict) -> None:
    if "callback_query" in update:
        await _handle_callback_query(update["callback_query"])
        return

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
    elif cmd == "/status":
        await handle_status(chat_id, user_id)
    elif cmd == "/list":
        await handle_list(chat_id, user_id)
    elif is_valid_telemost_url(text):
        # UX: bare Telemost link → treat as /record <text>
        await handle_record(chat_id, user_id, text)
    elif text.startswith("/"):
        # Typo'd or unknown slash-command — stay silent (no spam).
        return
    else:
        await tg_send_message(
            chat_id,
            _PLAIN_TEXT_HINT,
            reply_markup=PLAIN_TEXT_HINT,
        )


async def _handle_callback_query(cq: dict) -> None:
    """Route inline-button taps. Always answerCallbackQuery to dismiss spinner."""
    cq_id = cq.get("id")
    sender = cq.get("from") or {}
    user_id = sender.get("id")
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    data = cq.get("data") or ""
    if not cq_id or not user_id or chat_id is None:
        return

    user = await get_user_by_telegram_id(user_id)
    if not user:
        try:
            await tg_answer_callback_query(
                cq_id,
                "Доступ закрыт. Напиши /start.",
                show_alert=True,
            )
        except TelegramAPIError:
            logger.warning("Failed to answer rejected cq %s", cq_id)
        return

    try:
        await tg_answer_callback_query(cq_id)
    except TelegramAPIError:
        logger.warning("Failed to ack cq %s", cq_id)

    if data == "menu:list":
        await handle_list(chat_id, user_id)
    elif data == "menu:status":
        await handle_status(chat_id, user_id)
    elif data == "menu:help":
        await handle_help(chat_id)
    elif data.startswith("meet:"):
        parts = data.split(":", 2)
        if len(parts) == 3:
            _, short_id, action = parts
            await handle_meet(
                chat_id=chat_id, user_id=user_id,
                short_id=short_id, action=action,
            )
        else:
            logger.info("Malformed meet callback: %s", data)
    elif data.startswith("add_telemost:"):
        parts = data.split(":", 1)
        if len(parts) == 2:
            event_id = parts[1]
            await handle_add_telemost(
                chat_id=chat_id,
                user_telegram_id=user_id,
                event_id=event_id,
            )
        else:
            logger.info("Malformed add_telemost callback: %s", data)
    elif data.startswith("voice:") and data.endswith(":disabled"):
        # Phase 1 legacy callback — kept as fallback for candidates that
        # were rendered before T7 (no UUID assigned) or for which Phase 2
        # persistence failed at the LLM stage.
        parts = data.split(":")
        candidate_id = parts[1] if len(parts) >= 3 else "unknown"
        await handle_voice_disabled(chat_id=chat_id, candidate_id=candidate_id)
    elif (
        data.startswith(("task_create:", "task_edit:", "task_ignore:"))
        or data.startswith(("meeting_create:", "meeting_edit:", "meeting_ignore:"))
    ):
        # Phase 2 voice-trigger action callbacks. Shape: <action_kind>:<uuid>
        action, _, raw_uuid = data.partition(":")
        try:
            from uuid import UUID
            cand_uuid = UUID(raw_uuid)
        except ValueError:
            logger.info("Malformed voice-action callback %s (bad UUID %r)", data, raw_uuid)
            return
        dispatch = {
            "task_create": handle_task_create,
            "task_edit": handle_task_edit,
            "task_ignore": handle_task_ignore,
            "meeting_create": handle_meeting_create,
            "meeting_edit": handle_meeting_edit,
            "meeting_ignore": handle_meeting_ignore,
        }
        handler = dispatch.get(action)
        if handler is None:
            logger.info("Unknown voice action: %s", action)
            return
        await handler(chat_id=chat_id, candidate_id=cand_uuid)
    else:
        logger.info("Unknown callback data: %s", data)
