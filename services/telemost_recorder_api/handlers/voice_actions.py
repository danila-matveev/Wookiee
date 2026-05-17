"""Handlers for Phase 2 voice-trigger callback_data.

Routed from ``services/telemost_recorder_api/handlers/__init__.py``:

  * task_create:<uuid>    → create a Bitrix task
  * task_edit:<uuid>      → Phase 2 placeholder asking the user to edit in Bitrix
  * task_ignore:<uuid>    → mark candidate ignored
  * meeting_create:<uuid> → create a Bitrix calendar event
  * meeting_edit:<uuid>   → Phase 2 placeholder
  * meeting_ignore:<uuid> → mark candidate ignored

Resolution rules for human names → Bitrix ids:
  * Try ``short_name`` match (case-insensitive) against ``telemost.users``.
  * Fall back to ``name`` match.
  * Fall back to a substring search inside ``name``.
  * Если совпадений > 1 — отказываемся (двусмысленно).

Errors are surfaced to the chat in plain Russian so the operator can choose
to fix the data manually in Bitrix and not re-trigger the bot.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message
from services.telemost_recorder_api.voice_candidates_repo import (
    get_candidate,
    mark_created,
    mark_edited,
    mark_ignored,
)
from shared.bitrix_writes import (
    BitrixWriteError,
    create_calendar_event,
    create_task,
)

logger = logging.getLogger(__name__)

# Bitrix task URL template — matches /bitrix-task SKILL.md Step 7.
_TASK_URL_TEMPLATE = "https://wookiee.bitrix24.ru/workgroups/group/0/tasks/task/view/{task_id}/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_team_users() -> list[dict[str, Any]]:
    """SELECT all active users — used to resolve human-name → bitrix_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT telegram_id, bitrix_id, name, short_name
            FROM telemost.users
            WHERE is_active = true
            """,
        )
    return [dict(r) for r in rows]


def _resolve_bitrix_id(
    name: str | None,
    speaker: str | None,
    team_users: list[dict[str, Any]],
) -> int | None:
    """Map a human name (or speaker fallback) to a Bitrix user id.

    Returns ``None`` when the name doesn't resolve to exactly one teammate.
    """
    raw = (name or speaker or "").strip().lower()
    if not raw:
        return None

    exact: list[dict[str, Any]] = []
    sub: list[dict[str, Any]] = []
    for u in team_users:
        sh = (u.get("short_name") or "").strip().lower()
        full = (u.get("name") or "").strip().lower()
        if sh == raw or full == raw:
            exact.append(u)
        elif raw in full or raw in sh:
            sub.append(u)

    candidates = exact or sub
    if len(candidates) != 1:
        return None
    try:
        return int(candidates[0]["bitrix_id"])
    except (TypeError, ValueError):
        return None


def _resolve_bitrix_ids(
    names: list[str] | None,
    team_users: list[dict[str, Any]],
) -> list[int]:
    """Resolve a list of human names to Bitrix ids — silently drop ambiguous ones."""
    if not names:
        return []
    out: list[int] = []
    for n in names:
        bid = _resolve_bitrix_id(n, None, team_users)
        if bid is not None:
            out.append(bid)
    return out


def _parse_iso(value: Any) -> datetime | None:
    """Try to parse an ISO 8601 datetime string. Returns None on failure."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _candidate_extracted(cand: dict[str, Any]) -> dict[str, Any]:
    """Return the candidate's extracted_fields as a dict, parsing JSON if needed."""
    fields = cand.get("extracted_fields") or {}
    if isinstance(fields, str):
        try:
            return json.loads(fields)
        except json.JSONDecodeError:
            return {}
    return fields


async def _send(chat_id: int, text: str) -> None:
    """tg_send_message wrapper that swallows non-fatal API errors."""
    try:
        await tg_send_message(chat_id, text, parse_mode=None)
    except Exception:
        logger.exception("voice_actions: tg_send_message failed for chat_id=%d", chat_id)


# ---------------------------------------------------------------------------
# task_create
# ---------------------------------------------------------------------------


async def handle_task_create(*, chat_id: int, candidate_id: UUID) -> None:
    """Read candidate, create Bitrix task, mark status='created'."""
    cand = await get_candidate(candidate_id)
    if cand is None:
        await _send(chat_id, "⚠ Не нашёл голосовой триггер в базе — возможно он уже истёк.")
        return

    if cand["status"] != "pending":
        bitrix_id = cand.get("bitrix_id")
        if cand["status"] == "created" and bitrix_id:
            url = _TASK_URL_TEMPLATE.format(task_id=bitrix_id)
            await _send(chat_id, f"ℹ Эта задача уже создана: {url}")
        else:
            await _send(
                chat_id,
                f"ℹ Этот голосовой триггер уже обработан (статус: {cand['status']}).",
            )
        return

    fields = _candidate_extracted(cand)
    team_users = await _fetch_team_users()

    # responsible — required. If LLM didn't extract or it doesn't resolve to a
    # single teammate, refuse and tell the user to edit in Bitrix.
    responsible_id = _resolve_bitrix_id(
        fields.get("responsible"), None, team_users,
    )
    if responsible_id is None:
        await _send(
            chat_id,
            "⚠ Не понял на кого ставить задачу. "
            "Допиши исполнителя в Bitrix24 руками или нажми «Игнор».",
        )
        return

    created_by = _resolve_bitrix_id(
        fields.get("created_by"), cand.get("speaker"), team_users,
    ) or 1  # Bitrix CEO fallback per /bitrix-task SKILL.md дефолт

    deadline = _parse_iso(fields.get("deadline"))
    deadline_warning = ""
    if deadline is None:
        deadline_warning = (
            "\n⚠ Дедлайн в речи не прозвучал — задача создана без дедлайна. "
            "Поправь в Bitrix руками если нужно."
        )

    auditors = _resolve_bitrix_ids(fields.get("auditors") or [], team_users)
    accomplices = _resolve_bitrix_ids(fields.get("accomplices") or [], team_users)

    title = fields.get("title") or cand["raw_text"][:80]
    description = fields.get("description") or cand["raw_text"]

    try:
        task_id = await create_task(
            title=title,
            responsible_id=responsible_id,
            created_by=created_by,
            description=description,
            deadline=deadline,
            auditors=auditors,
            accomplices=accomplices,
        )
    except BitrixWriteError as exc:
        logger.warning("voice_actions: create_task failed for %s: %s", candidate_id, exc)
        await _send(
            chat_id,
            f"❌ Не получилось создать задачу в Bitrix: {exc}. "
            "Попробуй ещё раз позже или создай вручную.",
        )
        return

    await mark_created(candidate_id, str(task_id))

    url = _TASK_URL_TEMPLATE.format(task_id=task_id)
    await _send(
        chat_id,
        f"✅ Готово! Задача создана: {url}{deadline_warning}",
    )


# ---------------------------------------------------------------------------
# task_ignore
# ---------------------------------------------------------------------------


async def handle_task_ignore(*, chat_id: int, candidate_id: UUID) -> None:
    """Mark candidate as ignored, send acknowledgment."""
    updated = await mark_ignored(candidate_id)
    if updated:
        await _send(chat_id, "❌ Пропущено. Кандидат помечен как «игнор».")
    else:
        await _send(chat_id, "ℹ Этот голосовой триггер уже обработан.")


# ---------------------------------------------------------------------------
# task_edit — Phase 2 placeholder
# ---------------------------------------------------------------------------


async def handle_task_edit(*, chat_id: int, candidate_id: UUID) -> None:
    """Phase 2: send instruction to fill missing fields manually in Bitrix."""
    cand = await get_candidate(candidate_id)
    if cand is None:
        await _send(chat_id, "⚠ Не нашёл голосовой триггер в базе.")
        return
    if cand["status"] != "pending":
        await _send(chat_id, f"ℹ Триггер уже обработан (статус: {cand['status']}).")
        return

    await mark_edited(candidate_id)
    await _send(
        chat_id,
        "✏️ Ручную правку полей пока сделать через бота нельзя. "
        "Нажми «Создать» — Саймон поставит задачу с теми полями что распознал, "
        "а ты допишешь недостающее прямо в Bitrix24.",
    )


# ---------------------------------------------------------------------------
# meeting_create
# ---------------------------------------------------------------------------


async def handle_meeting_create(*, chat_id: int, candidate_id: UUID) -> None:
    """Read candidate, create Bitrix calendar event, mark status='created'."""
    cand = await get_candidate(candidate_id)
    if cand is None:
        await _send(chat_id, "⚠ Не нашёл голосовой триггер в базе.")
        return

    if cand["status"] != "pending":
        bitrix_id = cand.get("bitrix_id")
        if cand["status"] == "created" and bitrix_id:
            await _send(chat_id, f"ℹ Это событие уже создано в Bitrix (id={bitrix_id}).")
        else:
            await _send(
                chat_id,
                f"ℹ Этот голосовой триггер уже обработан (статус: {cand['status']}).",
            )
        return

    fields = _candidate_extracted(cand)
    team_users = await _fetch_team_users()

    from_ts = _parse_iso(fields.get("from"))
    if from_ts is None:
        await _send(
            chat_id,
            "⚠ Не понял дату/время встречи. "
            "Создай событие в Bitrix24 руками или нажми «Игнор».",
        )
        return

    to_ts = _parse_iso(fields.get("to"))
    if to_ts is None:
        # Default to 1h duration when LLM only caught the start time.
        from datetime import timedelta
        to_ts = from_ts + timedelta(hours=1)

    # Event lands on the speaker's calendar (CEO=1 fallback for unknown speakers).
    owner_id = _resolve_bitrix_id(
        cand.get("speaker"), None, team_users,
    ) or 1

    attendees = _resolve_bitrix_ids(fields.get("attendees") or [], team_users)
    # Make sure the owner appears in attendees so the event is visible to them.
    if owner_id not in attendees:
        attendees = [owner_id] + attendees

    name = fields.get("name") or cand["raw_text"][:80]
    description = fields.get("description") or cand["raw_text"]

    try:
        event_id = await create_calendar_event(
            owner_id=owner_id,
            name=name,
            from_ts=from_ts,
            to_ts=to_ts,
            description=description,
            attendees=attendees,
        )
    except BitrixWriteError as exc:
        logger.warning(
            "voice_actions: create_calendar_event failed for %s: %s", candidate_id, exc,
        )
        await _send(
            chat_id,
            f"❌ Не получилось создать встречу в Bitrix: {exc}. "
            "Попробуй ещё раз позже или создай вручную.",
        )
        return

    await mark_created(candidate_id, str(event_id))
    await _send(chat_id, f"✅ Готово! Встреча создана в Bitrix (id={event_id}).")


# ---------------------------------------------------------------------------
# meeting_ignore
# ---------------------------------------------------------------------------


async def handle_meeting_ignore(*, chat_id: int, candidate_id: UUID) -> None:
    """Mark meeting candidate as ignored."""
    updated = await mark_ignored(candidate_id)
    if updated:
        await _send(chat_id, "❌ Пропущено. Встреча помечена как «игнор».")
    else:
        await _send(chat_id, "ℹ Этот голосовой триггер уже обработан.")


# ---------------------------------------------------------------------------
# meeting_edit — Phase 2 placeholder
# ---------------------------------------------------------------------------


async def handle_meeting_edit(*, chat_id: int, candidate_id: UUID) -> None:
    """Phase 2 placeholder for the meeting edit form."""
    cand = await get_candidate(candidate_id)
    if cand is None:
        await _send(chat_id, "⚠ Не нашёл голосовой триггер в базе.")
        return
    if cand["status"] != "pending":
        await _send(chat_id, f"ℹ Триггер уже обработан (статус: {cand['status']}).")
        return

    await mark_edited(candidate_id)
    await _send(
        chat_id,
        "✏️ Ручную правку через бота пока не сделать. "
        "Нажми «Создать» — Саймон создаст встречу с теми полями что распознал, "
        "а ты допишешь недостающее прямо в Bitrix24.",
    )
