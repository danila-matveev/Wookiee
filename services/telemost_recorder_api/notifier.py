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
from services.telemost_recorder_api.keyboards import (
    empty_meeting_actions,
    meeting_actions,
)
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
# Send transcript as a separate file only for substantial meetings.
# Short conversations (a few paragraphs) already fit in the summary message,
# and a 1.8 KB attached file feels like noise. Users still have the
# "Транскрипт" button to pull it on demand.
_TRANSCRIPT_FILE_MIN_PARAGRAPHS = 15


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


def _resolve_title(meeting: dict[str, Any]) -> str:
    """Pick the best available title in priority order.

    1. summary.title — LLM-generated from meeting content. Most descriptive,
       reflects what was actually discussed.
    2. meeting.title — set by Bitrix calendar enrichment. Reliable for events
       in the Bitrix calendar with the meeting URL in LOCATION, but falls
       through to a time-proximity match (e.g. "Dayli") that may not be
       what the user actually recorded.
    3. Fallback to "Встреча".
    """
    summary = meeting.get("summary") or {}
    llm_title = (summary.get("title") or "").strip()
    if llm_title:
        return llm_title
    bitrix_title = (meeting.get("title") or "").strip()
    if bitrix_title:
        return bitrix_title
    return "Встреча"


def _header(meeting: dict[str, Any]) -> str:
    """Build the `📝 *Title* (date · duration · N уч.)` header — skip parts that are empty."""
    title = _md_escape(_resolve_title(meeting))
    parts: list[str] = []
    if meeting.get("started_at"):
        parts.append(meeting["started_at"].strftime("%d.%m %H:%M"))
    duration_secs = meeting.get("duration_seconds")
    if duration_secs:
        parts.append(_fmt_duration(duration_secs))
    summary = meeting.get("summary") or {}
    participants = summary.get("participants") or []
    if participants:
        parts.append(f"{len(participants)} уч.")
    suffix = f" ({' · '.join(parts)})" if parts else ""
    return f"*{title}*{suffix}"


def format_summary_message(meeting: dict[str, Any]) -> str:
    summary = meeting.get("summary") or {}
    header = _header(meeting)

    if summary.get("empty"):
        return (
            f"📭 {header}\n\n"
            f"На встрече никто не говорил — запись пустая. "
            f"Возможно, никто не подключился, или микрофоны были выключены."
        )

    lines = [f"📝 {header}"]

    # partial=True означает: chunked summary прошёл, а paragraphs chunk упал
    # (см. llm_postprocess._call_paragraphs_chunked fallback). Транскрипт-файл
    # в этом случае не присылается, и без warning юзер не поймёт почему.
    if summary.get("partial"):
        lines.append(
            "\n⚠ Транскрипт собрать не удалось целиком — "
            "ниже только итоги встречи."
        )

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
        except TelegramAPIError as e:
            if e.error_code in (400, 403):
                # logger.error (not .warning) so install_telegram_alerts
                # bubbles it to the operator — when a user blocks the bot
                # we still need a human signal that their meeting failed
                # and the failure DM never landed.
                logger.error(
                    "Cannot notify failure for %s — user unreachable (Telegram %d): %s",
                    meeting_id, e.error_code, e,
                )
            else:
                logger.exception("Failed to notify failure for %s", meeting_id)
        return

    summary = meeting.get("summary") or {}
    is_empty = bool(summary.get("empty"))
    summary_text = format_summary_message(meeting)
    short_id = str(meeting_id)[:_ID_PREFIX_LEN]
    try:
        await tg_send_message(
            triggered_by,
            summary_text,
            reply_markup=empty_meeting_actions(short_id)
            if is_empty
            else meeting_actions(short_id),
        )
    except TelegramAPIError as e:
        if e.error_code in (400, 403):
            logger.error(
                "Cannot send summary for %s — user unreachable (Telegram %d): %s",
                meeting_id, e.error_code, e,
            )
        else:
            logger.exception("Failed to send summary for %s", meeting_id)
        return

    paragraphs = meeting.get("processed_paragraphs") or []
    if (
        paragraphs
        and not is_empty
        and len(paragraphs) >= _TRANSCRIPT_FILE_MIN_PARAGRAPHS
    ):
        transcript = build_transcript_text(paragraphs)
        filename = f"transcript_{str(meeting_id)[:_ID_PREFIX_LEN]}.txt"
        try:
            await tg_send_document(
                triggered_by,
                transcript.encode("utf-8"),
                filename=filename,
                caption=f"Полный transcript ({len(paragraphs)} параграфов)",
            )
        except TelegramAPIError as e:
            if e.error_code in (400, 403):
                logger.error(
                    "Cannot send transcript for %s — user unreachable (Telegram %d): %s",
                    meeting_id, e.error_code, e,
                )
            else:
                logger.exception("Failed to send transcript for %s", meeting_id)
