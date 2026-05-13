"""Callback-handlers for inline buttons: meet:<short_id>:<action>.

Actions:
- show          — send summary message + action keyboard
- transcript    — send transcript_<id>.txt as document
- summary       — re-send summary message (no keyboard)
- delete        — ask confirmation (no actual delete)
- confirm_delete — actually soft-delete + DM "Удалено"
"""
from __future__ import annotations

import logging
from typing import Any

from services.telemost_recorder_api.keyboards import (
    confirm_delete,
    meeting_actions,
)
from services.telemost_recorder_api.meetings_repo import (
    build_transcript_text,
    delete_meeting_for_owner,
    load_meeting_by_short_id,
)
from services.telemost_recorder_api.notifier import _md_escape, format_summary_message
from services.telemost_recorder_api.notion_export import (
    NotionExportError,
    export_meeting_to_notion,
)
from services.telemost_recorder_api.telegram_client import (
    tg_send_document,
    tg_send_message,
)

logger = logging.getLogger(__name__)


_NOT_FOUND = "🤔 Не нашёл такую встречу или у тебя нет прав на неё."


async def handle_meet(
    *, chat_id: int, user_id: int, short_id: str, action: str
) -> None:
    meeting = await load_meeting_by_short_id(short_id, owner_telegram_id=user_id)
    if not meeting:
        await tg_send_message(chat_id, _NOT_FOUND)
        return

    if action == "show":
        await _send_show(chat_id, meeting)
    elif action == "summary":
        await tg_send_message(chat_id, format_summary_message(meeting))
    elif action == "transcript":
        await _send_transcript(chat_id, meeting)
    elif action == "notion":
        await _export_to_notion(chat_id, meeting)
    elif action == "delete":
        await _ask_delete_confirm(chat_id, meeting, short_id)
    elif action == "confirm_delete":
        await _do_delete(chat_id, meeting, user_id)
    else:
        logger.info("Unknown meet action: %s", action)


async def _send_show(chat_id: int, meeting: dict[str, Any]) -> None:
    short_id = str(meeting["id"])[:8]
    await tg_send_message(
        chat_id,
        format_summary_message(meeting),
        reply_markup=meeting_actions(short_id),
    )


async def _send_transcript(chat_id: int, meeting: dict[str, Any]) -> None:
    paragraphs = meeting.get("processed_paragraphs") or []
    text = build_transcript_text(paragraphs)
    filename = f"transcript_{str(meeting['id'])[:8]}.txt"
    await tg_send_document(
        chat_id,
        text.encode("utf-8"),
        filename=filename,
        caption=f"Полный transcript ({len(paragraphs)} параграфов)",
    )


async def _ask_delete_confirm(chat_id: int, meeting: dict[str, Any], short_id: str) -> None:
    title = _md_escape(meeting.get("title") or "(без названия)")
    await tg_send_message(
        chat_id,
        f"🗑 Точно удалить встречу *{title}*?\n\nЭто действие необратимо.",
        reply_markup=confirm_delete(short_id),
    )


async def _export_to_notion(chat_id: int, meeting: dict[str, Any]) -> None:
    try:
        _page_id, page_url = await export_meeting_to_notion(meeting["id"])
    except NotionExportError as e:
        logger.warning("Notion export failed for %s: %s", meeting["id"], e)
        await tg_send_message(
            chat_id,
            "❌ Не получилось выгрузить в Notion. "
            "Проверь NOTION_TOKEN/NOTION_MEETINGS_DB_ID в .env.",
            parse_mode=None,
        )
        return
    if page_url:
        await tg_send_message(
            chat_id,
            f"📤 Выгрузил в Notion:\n{page_url}",
            parse_mode=None,
        )
    else:
        await tg_send_message(chat_id, "📤 Выгрузил в Notion.", parse_mode=None)


async def _do_delete(chat_id: int, meeting: dict[str, Any], user_id: int) -> None:
    ok = await delete_meeting_for_owner(meeting["id"], owner_telegram_id=user_id)
    if ok:
        await tg_send_message(chat_id, "✅ Удалено.")
    else:
        await tg_send_message(chat_id, "❌ Не получилось удалить (встреча активна или нет прав).")
