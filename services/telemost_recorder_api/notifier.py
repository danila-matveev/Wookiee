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
from services.telemost_recorder_api.telegram_client import (
    TelegramAPIError,
    tg_send_document,
    tg_send_message,
)

logger = logging.getLogger(__name__)


def _ms_to_mmss(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    m = seconds // 60
    if m < 60:
        return f"{m} мин"
    return f"{m // 60} ч {m % 60} мин"


def format_summary_message(meeting: dict[str, Any]) -> str:
    title = meeting.get("title") or "(без названия)"
    started = (
        meeting["started_at"].strftime("%d.%m %H:%M")
        if meeting.get("started_at")
        else "—"
    )
    duration = _fmt_duration(meeting.get("duration_seconds"))
    summary = meeting.get("summary") or {}

    if summary.get("empty"):
        return (
            f"📭 *{title}* ({started}, {duration})\n\n"
            f"Запись завершена, речь не была распознана (тишина)."
        )

    lines = [f"📝 *{title}* ({started}, {duration})"]

    participants = summary.get("participants") or []
    if participants:
        lines.append(f"\n👥 *Участники:* {', '.join(participants)}")

    topics = summary.get("topics") or []
    if topics:
        lines.append("\n🎯 *Темы:*")
        for t in topics[:8]:
            anchor = t.get("anchor") or ""
            lines.append(f"• {t.get('title', '?')} {anchor}")

    decisions = summary.get("decisions") or []
    if decisions:
        lines.append("\n✅ *Решения:*")
        for d in decisions[:6]:
            lines.append(f"• {d}")

    tasks = summary.get("tasks") or []
    if tasks:
        lines.append("\n📋 *Задачи:*")
        for t in tasks[:8]:
            assignee = t.get("assignee") or "—"
            when = f" ({t['when']})" if t.get("when") else ""
            lines.append(f"• {assignee} — {t.get('what', '?')}{when}")

    tags = meeting.get("tags") or []
    if tags:
        lines.append(f"\n🏷 {', '.join(tags)}")

    lines.append(f"\n_id_ `{str(meeting['id'])[:8]}`")
    return "\n".join(lines)


def build_transcript_text(paragraphs: list[dict[str, Any]]) -> str:
    if not paragraphs:
        return "(пустой transcript)"
    out = []
    for p in paragraphs:
        ts = _ms_to_mmss(p.get("start_ms", 0))
        speaker = p.get("speaker", "?")
        text = p.get("text", "")
        out.append(f"[{ts}] {speaker}: {text}")
    return "\n".join(out)


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
                f"❌ Запись `{str(meeting_id)[:8]}` завершилась ошибкой:\n```\n{err[:500]}\n```",
            )
        except TelegramAPIError:
            logger.exception("Failed to notify failure for %s", meeting_id)
        return

    summary_text = format_summary_message(meeting)
    try:
        await tg_send_message(triggered_by, summary_text)
    except TelegramAPIError:
        logger.exception("Failed to send summary for %s", meeting_id)
        return

    paragraphs = meeting.get("processed_paragraphs") or []
    if paragraphs:
        transcript = build_transcript_text(paragraphs)
        filename = f"transcript_{str(meeting_id)[:8]}.txt"
        try:
            await tg_send_document(
                triggered_by,
                transcript.encode("utf-8"),
                filename=filename,
                caption=f"Полный transcript ({len(paragraphs)} параграфов)",
            )
        except TelegramAPIError:
            logger.exception("Failed to send transcript for %s", meeting_id)
