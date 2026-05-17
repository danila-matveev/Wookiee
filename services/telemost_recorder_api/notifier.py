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
    voice_trigger_keyboard,
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

    # Voice-trigger sections (Phase 1: buttons rendered but disabled).
    voice_candidates = meeting.get("voice_triggers") or []
    if voice_candidates:
        _append_voice_sections(lines, voice_candidates)

    return "\n".join(lines)


def _fmt_deadline(deadline: str | None) -> str:
    """Format an ISO datetime string into a short human-readable form."""
    if not deadline:
        return "—"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(deadline)
        day_names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        dow = day_names[dt.weekday()]
        return f"{dow} {dt.strftime('%d.%m')} {dt.strftime('%H:%M')} МСК"
    except (ValueError, AttributeError):
        return _md_escape(str(deadline))


def _append_voice_sections(lines: list[str], candidates: list) -> None:  # type: ignore[type-arg]
    """Append up to 5 voice-trigger sections to the message lines list.

    Sections rendered (only those with at least one candidate):
      🔖 Важные моменты (attention)
      📌 Задачи (task)
      📅 Предлагаемые встречи (meeting)
      🔔 Напоминания (reminder)
      📝 Заметки (note)

    Sections render as inline markdown only. Per-candidate keyboards are
    attached separately by notify_meeting_result() for task/meeting intents via
    individual tg_send_message calls with voice_trigger_keyboard().
    """
    _SEP = "─────────────────────────────────────────────"

    def _by_intent(intent: str) -> list:  # type: ignore[type-arg]
        return [c for c in candidates if c.intent == intent]

    # ── 🔖 Важные моменты (attention) ──────────────────────────────────────
    attention = _by_intent("attention")
    if attention:
        lines.append(f"\n🔖 *Важные моменты (Саймон обратил внимание)*\n{_SEP}")
        for c in attention:
            quote = _md_escape(
                c.extracted_fields.get("quote") or c.raw_text
            )
            lines.append(f"• {_md_escape(c.timestamp)} ({_md_escape(c.speaker)}) \"{quote}\"")

    # ── 📌 Задачи (task) ────────────────────────────────────────────────────
    tasks_v = _by_intent("task")
    if tasks_v:
        lines.append(f"\n📌 *Задачи (готовы к постановке в Битрикс)*\n{_SEP}")
        for idx, c in enumerate(tasks_v):
            f = c.extracted_fields
            title = _md_escape(f.get("title") or c.raw_text[:60])
            responsible = _md_escape(f.get("responsible") or "—")
            created_by = _md_escape(f.get("created_by") or c.speaker)
            deadline = _fmt_deadline(f.get("deadline"))
            auditors = ", ".join(f.get("auditors") or []) or "—"
            accomplices = ", ".join(f.get("accomplices") or []) or "—"
            lines.append(f"• {title}")
            lines.append(f"  Постановщик: {created_by} → Исполнитель: {responsible}")
            lines.append(f"  Наблюдатели: {_md_escape(auditors)}")
            lines.append(f"  Соисполнители: {_md_escape(accomplices)}")
            lines.append(f"  Дедлайн: {deadline}")

    # ── 📅 Предлагаемые встречи (meeting) ──────────────────────────────────
    meetings_v = _by_intent("meeting")
    if meetings_v:
        lines.append(f"\n📅 *Предлагаемые встречи*\n{_SEP}")
        for _idx, c in enumerate(meetings_v):
            f = c.extracted_fields
            name = _md_escape(f.get("name") or c.raw_text[:60])
            from_dt = _fmt_deadline(f.get("from"))
            attendees = ", ".join(f.get("attendees") or []) or "—"
            lines.append(f"• {name}, {from_dt}")
            lines.append(f"  Участники: {_md_escape(attendees)}")

    # ── 🔔 Напоминания (reminder) ───────────────────────────────────────────
    reminders = _by_intent("reminder")
    if reminders:
        lines.append(f"\n🔔 *Напоминания*\n{_SEP}")
        for c in reminders:
            f = c.extracted_fields
            recipient = _md_escape(f.get("recipient") or c.speaker)
            remind_at = _fmt_deadline(f.get("remind_at"))
            text = _md_escape(f.get("text") or c.raw_text[:80])
            lines.append(f"• Напомнить {recipient} в {remind_at} — {text}")

    # ── 📝 Заметки (note) ────────────────────────────────────────────────────
    notes = _by_intent("note")
    if notes:
        lines.append(f"\n📝 *Заметки*\n{_SEP}")
        for c in notes:
            f = c.extracted_fields
            quote = _md_escape(f.get("quote") or c.raw_text[:120])
            lines.append(f"• {_md_escape(c.timestamp)} ({_md_escape(c.speaker)}) \"{quote}\"")


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

    # Send a separate message with real inline keyboard for each task/meeting candidate.
    # Note/attention/reminder are info-only and stay in the summary text only.
    voice_candidates = meeting.get("voice_triggers") or []
    task_idx = 0
    meeting_idx = 0
    for cand in voice_candidates:
        if cand.intent == "task":
            cid = f"task{task_idx}"
            task_idx += 1
            f = cand.extracted_fields
            title = f.get("title") or cand.raw_text[:60]
            text = f"📌 {title}\n\nПодтверди действие:"
        elif cand.intent == "meeting":
            cid = f"meeting{meeting_idx}"
            meeting_idx += 1
            f = cand.extracted_fields
            name = f.get("name") or cand.raw_text[:60]
            text = f"📅 {name}\n\nПодтверди действие:"
        else:
            continue

        try:
            await tg_send_message(
                triggered_by,
                text,
                reply_markup=voice_trigger_keyboard(cid),
            )
        except TelegramAPIError as e:
            if e.error_code in (400, 403):
                logger.error(
                    "Cannot send voice-trigger keyboard for %s cid=%s — user unreachable (Telegram %d): %s",
                    meeting_id, cid, e.error_code, e,
                )
            else:
                logger.exception(
                    "Failed to send voice-trigger keyboard for %s cid=%s", meeting_id, cid
                )

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
