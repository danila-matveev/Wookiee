"""Notifier — sends meeting result DM with idempotent claim.

Idempotency: атомарный UPDATE ... WHERE notified_at IS NULL RETURNING.
Если RETURNING ничего не вернул → уже нотифицировано, skip.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.keyboards import meeting_actions
from services.telemost_recorder_api.meetings_repo import (
    build_transcript_text,  # re-export for back-compat
)
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_send_document,
    tg_send_message,
)

__all__ = ["build_transcript_text", "format_summary_message", "notify_meeting_result"]

logger = logging.getLogger(__name__)


_MD_SPECIAL = ("\\", "_", "*", "[", "]", "`")

_TOPIC_LIMIT = 15
_DECISION_LIMIT = 12
_TASK_LIMIT = 20
_ERROR_PREVIEW_LEN = 500
_ID_PREFIX_LEN = 8


def _md_escape(s: str) -> str:
    """Escape Telegram Markdown V1 specials so user-controlled text can't break parse_mode.

    Telegram MarkdownV1 only treats *_[]` as syntax; backslash-escape works.
    """
    for ch in _MD_SPECIAL:
        s = s.replace(ch, "\\" + ch)
    return s


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    m = seconds // 60
    if m < 60:
        return f"{m} мин"
    return f"{m // 60} ч {m % 60} мин"


def _header(meeting: dict[str, Any]) -> str:
    """Build the `📝 *Title* (date · duration)` header — skip parts that are empty."""
    raw_title = meeting.get("title")
    title = _md_escape(raw_title) if raw_title else "Встреча"
    parts: list[str] = []
    if meeting.get("started_at"):
        parts.append(meeting["started_at"].strftime("%d.%m %H:%M"))
    duration_secs = meeting.get("duration_seconds")
    if duration_secs:
        parts.append(_fmt_duration(duration_secs))
    suffix = f" ({' · '.join(parts)})" if parts else ""
    return f"*{title}*{suffix}"


def format_summary_message(meeting: dict[str, Any]) -> str:
    summary = meeting.get("summary") or {}
    header = _header(meeting)

    if summary.get("empty"):
        return (
            f"📭 {header}\n\n"
            f"Запись завершена, речь не была распознана (тишина)."
        )

    lines = [f"📝 {header}"]

    participants = summary.get("participants") or []
    if participants:
        joined = ", ".join(_md_escape(p) for p in participants)
        lines.append(f"\n👥 *Участники:* {joined}")

    topics = summary.get("topics") or []
    if topics:
        lines.append("\n🎯 *Темы:*")
        for t in topics[:_TOPIC_LIMIT]:
            anchor = _md_escape(t.get("anchor") or "")
            title_t = _md_escape(t.get("title", "?"))
            lines.append(f"• {title_t} {anchor}")

    decisions = summary.get("decisions") or []
    if decisions:
        lines.append("\n✅ *Решения:*")
        for d in decisions[:_DECISION_LIMIT]:
            lines.append(f"• {_md_escape(d)}")

    tasks = summary.get("tasks") or []
    if tasks:
        lines.append("\n📋 *Задачи:*")
        for t in tasks[:_TASK_LIMIT]:
            assignee = _md_escape(t.get("assignee") or "—")
            when = f" ({_md_escape(t['when'])})" if t.get("when") else ""
            what = _md_escape(t.get("what", "?"))
            lines.append(f"• *{assignee}* — {what}{when}")
            context = t.get("context")
            if context:
                lines.append(f"   _Зачем:_ {_md_escape(context)}")
            conditions = t.get("conditions")
            if conditions:
                lines.append(f"   _Условия:_ {_md_escape(conditions)}")

    tags = meeting.get("tags") or []
    if tags:
        joined_tags = ", ".join(_md_escape(t) for t in tags)
        lines.append(f"\n🏷 {joined_tags}")

    return "\n".join(lines)


async def _claim_notification(meeting_id: UUID) -> datetime | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            UPDATE telemost.meetings SET notified_at = now()
            WHERE id = $1 AND notified_at IS NULL
            RETURNING notified_at
            """,
            meeting_id,
        )


async def _load_meeting(meeting_id: UUID) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, triggered_by, started_at, duration_seconds,
                   status, summary, tags, processed_paragraphs, error
            FROM telemost.meetings WHERE id = $1
            """,
            meeting_id,
        )
    if not row:
        return None
    out = dict(row)
    for k in ("summary", "processed_paragraphs"):
        if isinstance(out.get(k), str):
            out[k] = json.loads(out[k])
    return out


async def notify_meeting_result(meeting_id: UUID) -> None:
    """Idempotent: only one notification per meeting."""
    claimed = await _claim_notification(meeting_id)
    if claimed is None:
        logger.info("Meeting %s already notified, skipping", meeting_id)
        return

    meeting = await _load_meeting(meeting_id)
    if not meeting:
        logger.warning("Meeting %s vanished after claim", meeting_id)
        return

    triggered_by = meeting["triggered_by"]
    if not triggered_by:
        logger.warning("Meeting %s has no triggered_by, skip notify", meeting_id)
        return

    if meeting["status"] == "failed":
        err = meeting.get("error") or "unknown"
        try:
            await tg_send_message(
                triggered_by,
                f"❌ Запись {str(meeting_id)[:_ID_PREFIX_LEN]} завершилась ошибкой:\n\n{err[:_ERROR_PREVIEW_LEN]}",
                parse_mode=None,
            )
        except TelegramAPIError:
            logger.exception("Failed to notify failure for %s", meeting_id)
        return

    summary_text = format_summary_message(meeting)
    short_id = str(meeting_id)[:_ID_PREFIX_LEN]
    try:
        await tg_send_message(
            triggered_by,
            summary_text,
            reply_markup=meeting_actions(short_id),
        )
    except TelegramAPIError:
        logger.exception("Failed to send summary for %s", meeting_id)
        return

    paragraphs = meeting.get("processed_paragraphs") or []
    if paragraphs:
        transcript = build_transcript_text(paragraphs)
        filename = f"transcript_{str(meeting_id)[:_ID_PREFIX_LEN]}.txt"
        try:
            await tg_send_document(
                triggered_by,
                transcript.encode("utf-8"),
                filename=filename,
                caption=f"Полный transcript ({len(paragraphs)} параграфов)",
            )
        except TelegramAPIError:
            logger.exception("Failed to send transcript for %s", meeting_id)
