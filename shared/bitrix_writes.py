"""Bitrix24 write API wrapper — Саймон (T7).

Thin layer over two REST endpoints that we use to act on voice-trigger
candidates extracted by ``services/telemost_recorder_api/voice_triggers.py``:

  * ``tasks.task.add.json``      — create a task (intent='task')
  * ``calendar.event.add.json``  — create an event (intent='meeting')

Field shapes mirror the canonical templates in
``.claude/skills/bitrix-task/SKILL.md`` and ``.claude/skills/calendar/SKILL.md``
so a voice-extracted task feels indistinguishable from one created via the
manual skill flow.

Webhook URL is read once at import time from the existing project env var
``BITRIX24_WEBHOOK_URL`` (defined in ``services/telemost_recorder_api/config.py``).
Read-only — no new env vars introduced.

Timeout: 15 s on every call (asyncio.wait_for not needed — httpx enforces it).
On HTTP-level failure or Bitrix-level ``{"error": ...}`` payload we raise
:class:`BitrixWriteError` so the caller can surface a friendly message to the
operator and leave ``voice_trigger_candidates.status='pending'`` for retry.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Reuse the same webhook URL the read client (bitrix_calendar.py) already uses.
# We resolve at import time but keep it patchable in tests via
# `patch("shared.bitrix_writes._WEBHOOK_URL", ...)`.
_WEBHOOK_URL: str = os.getenv("BITRIX24_WEBHOOK_URL", "")

_TIMEOUT = httpx.Timeout(15.0)

# Bitrix expects DEADLINE / from / to as naive strings in the calendar
# owner's timezone (Wookiee kabinet = Europe/Moscow). We do NOT do any tz
# conversion here — the caller is responsible for passing a datetime that
# already represents the right wall-clock time in the kabinet TZ. The
# matching `bitrix_calendar._parse_bitrix_date` reads strings the same way.
_DEADLINE_FORMAT = "%Y-%m-%dT%H:%M:%S"     # used by tasks.task.add DEADLINE
_CALENDAR_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # used by calendar.event.add from/to

# Bitrix priority levels — same numeric scale as /bitrix-task SKILL.md.
PRIORITY_NORMAL = 1


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BitrixWriteError(RuntimeError):
    """Raised on any non-success outcome from a Bitrix write call.

    Covers two failure shapes:
      1. Transport / HTTP status non-2xx (network, 5xx, 4xx).
      2. HTTP 200 with a Bitrix-level ``{"error": "...", "error_description": "..."}``
         payload (e.g. invalid RESPONSIBLE_ID, missing field).

    Network timeouts propagate as ``httpx.TimeoutException`` so the caller
    can distinguish "Bitrix said no" from "Bitrix never answered".
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _webhook_base() -> str:
    """Return the webhook base URL with no trailing slash."""
    if not _WEBHOOK_URL:
        raise BitrixWriteError("BITRIX24_WEBHOOK_URL is not configured")
    return _WEBHOOK_URL.rstrip("/")


def _check_bitrix_error(payload: dict, endpoint: str) -> None:
    """Raise BitrixWriteError if the Bitrix response carries an error key."""
    if isinstance(payload, dict) and payload.get("error"):
        desc = payload.get("error_description") or ""
        raise BitrixWriteError(
            f"Bitrix {endpoint} failed: {payload['error']} {desc}".strip()
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_task(
    *,
    title: str,
    responsible_id: int,
    created_by: int,
    description: str,
    deadline: datetime | None = None,
    auditors: list[int] | None = None,
    accomplices: list[int] | None = None,
    priority: int = PRIORITY_NORMAL,
) -> int:
    """Create a Bitrix24 task via ``tasks.task.add.json``.

    Args:
        title: Short imperative-mode name (≤80 chars by /bitrix-task convention).
        responsible_id: Bitrix user id of the assignee.
        created_by: Bitrix user id of the creator (постановщик).
        description: Body of the task. Multi-line is fine.
        deadline: Optional ISO datetime — naive wall-clock in the kabinet TZ.
                  When None, no DEADLINE field is sent (Bitrix treats absence
                  as "no deadline" rather than failing).
        auditors: Optional list of Bitrix user ids set as наблюдатели.
        accomplices: Optional list of Bitrix user ids set as соисполнители.
        priority: 0=low, 1=normal, 2=high. Defaults to normal.

    Returns:
        The new task id as int (parsed from response ``result.task.id``).

    Raises:
        BitrixWriteError: On HTTP non-2xx, malformed response, or Bitrix
            error payload (e.g. unknown RESPONSIBLE_ID).
        httpx.TimeoutException: When the request exceeds 15 s.
    """
    fields: dict[str, object] = {
        "TITLE": title,
        "RESPONSIBLE_ID": responsible_id,
        "CREATED_BY": created_by,
        "DESCRIPTION": description,
        "PRIORITY": priority,
    }
    if deadline is not None:
        fields["DEADLINE"] = deadline.strftime(_DEADLINE_FORMAT)
    if auditors:
        fields["AUDITORS"] = list(auditors)
    if accomplices:
        fields["ACCOMPLICES"] = list(accomplices)

    url = f"{_webhook_base()}/tasks.task.add.json"
    body = {"fields": fields}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(url, json=body)

    if not response.is_success:
        raise BitrixWriteError(
            f"tasks.task.add HTTP {response.status_code}: {response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise BitrixWriteError(f"tasks.task.add non-JSON response: {exc}") from exc

    _check_bitrix_error(payload, "tasks.task.add")

    result = payload.get("result") or {}
    task = result.get("task") if isinstance(result, dict) else None
    task_id_raw = (task or {}).get("id")
    if task_id_raw is None:
        raise BitrixWriteError(f"tasks.task.add missing result.task.id: {payload!r}")

    try:
        return int(task_id_raw)
    except (TypeError, ValueError) as exc:
        raise BitrixWriteError(
            f"tasks.task.add returned non-numeric id: {task_id_raw!r}"
        ) from exc


async def create_calendar_event(
    *,
    owner_id: int,
    name: str,
    from_ts: datetime,
    to_ts: datetime,
    description: str,
    location: str | None = None,
    attendees: list[int] | None = None,
) -> int:
    """Create a Bitrix24 calendar event via ``calendar.event.add.json``.

    Always creates a user-type event (``type='user'``) — group calendars are
    out of scope for voice-triggers in T7.

    Args:
        owner_id: Bitrix user id whose calendar the event lands on.
        name: Event title.
        from_ts: Start wall-clock time in the owner's TZ (naive datetime).
        to_ts: End wall-clock time, same TZ as from_ts.
        description: Body. May be empty.
        location: Optional location/URL string. Empty/None → not sent.
        attendees: Optional list of Bitrix user ids invited.

    Returns:
        The new event id as int (parsed from response ``result``).

    Raises:
        BitrixWriteError: On HTTP non-2xx, malformed response, or Bitrix
            error payload.
        httpx.TimeoutException: When the request exceeds 15 s.
    """
    body: dict[str, object] = {
        "type": "user",
        "ownerId": owner_id,
        "name": name,
        "from": from_ts.strftime(_CALENDAR_TIME_FORMAT),
        "to": to_ts.strftime(_CALENDAR_TIME_FORMAT),
        "description": description,
        "location": location or "",
        "attendees": list(attendees) if attendees else [],
    }

    url = f"{_webhook_base()}/calendar.event.add.json"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(url, json=body)

    if not response.is_success:
        raise BitrixWriteError(
            f"calendar.event.add HTTP {response.status_code}: {response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise BitrixWriteError(
            f"calendar.event.add non-JSON response: {exc}"
        ) from exc

    _check_bitrix_error(payload, "calendar.event.add")

    result = payload.get("result")
    if result is None:
        raise BitrixWriteError(f"calendar.event.add missing result: {payload!r}")

    try:
        return int(result)
    except (TypeError, ValueError) as exc:
        raise BitrixWriteError(
            f"calendar.event.add returned non-numeric id: {result!r}"
        ) from exc
