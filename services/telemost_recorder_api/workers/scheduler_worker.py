"""Bitrix calendar scheduler — auto-queues a recording shortly before each
Telemost meeting starts.

How it works:
1. Once per `SCHEDULER_TICK_SECONDS`, pull calendar events for all active
   users in telemost.users (or a single legacy user from env if configured).
2. For each event, parse `DATE_FROM` *with `TZ_FROM`* (Bitrix returns wall
   time in the event's own timezone, not the owner's). Convert to UTC.
3. Extract a Telemost URL from LOCATION first, then DESCRIPTION. Skip
   Bitrix-Видеоконференция events whose LOCATION is `calendar_<n>` —
   the actual Telemost URL is generated lazily on the Bitrix UI side and
   isn't returned by `calendar.event.get`.
4. Skip events whose name contains `#nobot` (case-insensitive opt-out).
5. If now is in [start − LEAD, start + GRACE], insert a `meetings` row
   with `source='calendar'`, `source_event_id=<Bitrix event ID>`,
   `scheduled_at=<UTC start>`, `status='queued'`. The recorder worker
   picks it up just like a Telegram-triggered recording.

Idempotency:
- In-memory dedup: (meeting_url, scheduled_at) within a single tick — so the
  same team meeting seen in 12 calendars only produces 1 INSERT attempt.
- DB-level: partial unique index on (source, source_event_id, scheduled_at)
  where source='calendar' — ON CONFLICT DO NOTHING handles the rest.

Multi-user mode (default when TELEMOST_SCHEDULER_BITRIX_USER_ID is unset):
  Iterates over telemost.users WHERE is_active=true, polling each user's
  Bitrix calendar. triggered_by is set to the telegram_id of the first user
  in whose calendar the meeting URL was found.

Legacy single-user mode (when TELEMOST_SCHEDULER_BITRIX_USER_ID is set):
  Polls only that user — same behaviour as before T4.

Master switch: TELEMOST_SCHEDULER_ENABLED=false (default) → worker returns
immediately without starting the loop. Operator sets to true to activate.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from services.telemost_recorder_api.config import (
    BITRIX24_WEBHOOK_URL,
    BITRIX_TIMEOUT_SECONDS,
    SCHEDULER_BITRIX_USER_ID,
    SCHEDULER_ENABLED,
    SCHEDULER_GRACE_SECONDS,
    SCHEDULER_LEAD_SECONDS,
    SCHEDULER_TELEGRAM_ID,
    SCHEDULER_TICK_SECONDS,
)
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.url_canon import (
    canonicalize_telemost_url,
    is_valid_telemost_url,
)

logger = logging.getLogger(__name__)

_LOOKAHEAD_HOURS = 24
_TELEMOST_URL_RE = re.compile(
    r"https://telemost(?:\.360)?\.yandex\.ru/j/[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
# When the scheduler can't activate (env unset), idle this long between
# "still disabled" log lines so we don't flood the log.
_DISABLED_IDLE_SECONDS = 3600


@dataclass
class _Candidate:
    """In-memory record of a deduplicated meeting candidate within one tick."""

    url: str
    title: str | None
    scheduled_at: datetime
    triggered_by: int
    source_event_id: str


def _parse_event_start(ev: dict[str, Any]) -> datetime | None:
    """Bitrix returns wall time in the event's own TZ, not the owner's.
    Treat TZ_FROM as authoritative; fall back to UTC if missing or unknown."""
    raw = ev.get("DATE_FROM")
    if not raw:
        return None
    tz_name = (ev.get("TZ_FROM") or "").strip() or "UTC"
    try:
        tz: timezone | ZoneInfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown TZ_FROM %r on Bitrix event %s, using UTC", tz_name, ev.get("ID"))
        tz = timezone.utc
    # All-day events arrive as just `dd.mm.yyyy` (no time). They're never
    # video calls and have no meaningful "start within the next 90 seconds"
    # — skip silently instead of warning every tick.
    if len(raw) <= 10:
        return None
    try:
        naive = datetime.strptime(raw, "%d.%m.%Y %H:%M:%S")
    except ValueError:
        logger.warning("Bad DATE_FROM %r on Bitrix event %s", raw, ev.get("ID"))
        return None
    return naive.replace(tzinfo=tz).astimezone(timezone.utc)


def _extract_telemost_url(ev: dict[str, Any]) -> str | None:
    """Look in LOCATION first (most reliable), then DESCRIPTION. Returns
    canonicalized URL, or None if event uses Bitrix-Видеоконференция
    (LOCATION='calendar_NN') with no embedded Telemost link."""
    loc = (ev.get("LOCATION") or "").strip()
    if is_valid_telemost_url(loc):
        return canonicalize_telemost_url(loc)
    desc = ev.get("DESCRIPTION") or ""
    m = _TELEMOST_URL_RE.search(desc)
    if m:
        return canonicalize_telemost_url(m.group(0))
    return None


async def _fetch_bitrix_events(bitrix_user_id: str) -> list[dict[str, Any]]:
    """Calendar window: now → +24h. Bitrix returns events overlapping with
    this range, including their recurring occurrences as separate rows."""
    now = datetime.now(timezone.utc)
    frm = now.strftime("%Y-%m-%dT%H:%M:%S")
    to = (now + timedelta(hours=_LOOKAHEAD_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    base = BITRIX24_WEBHOOK_URL.rstrip("/")
    params = {"type": "user", "ownerId": bitrix_user_id, "from": frm, "to": to}
    try:
        async with httpx.AsyncClient(timeout=BITRIX_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{base}/calendar.event.get.json", params=params)
    except httpx.HTTPError as e:
        logger.warning("Scheduler: Bitrix fetch network error: %s", e)
        return []
    if not resp.is_success:
        logger.warning(
            "Scheduler: Bitrix fetch failed %d: %s", resp.status_code, resp.text[:200],
        )
        return []
    try:
        payload = resp.json()
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Scheduler: Bitrix returned non-JSON: %s", e)
        return []
    items = payload.get("result") or []
    return items if isinstance(items, list) else []


async def _queue_meeting(
    *,
    bitrix_event_id: str,
    title: str | None,
    meeting_url: str,
    scheduled_at_utc: datetime,
    triggered_by: int,
) -> bool:
    """Insert a queued row. Returns True if it was actually inserted (new),
    False if the partial unique index already had it.

    We rely on the partial unique index `uniq_meetings_calendar_event_slot`
    (migration 005) keyed on (source, source_event_id, scheduled_at) so
    daily-recurring meetings still get queued every day, but two scheduler
    ticks fighting over the same occurrence don't double-queue.
    """
    pool = await get_pool()
    seed_invitees = json.dumps([], ensure_ascii=False)
    async with pool.acquire() as conn:
        new_id = await conn.fetchval(
            """
            INSERT INTO telemost.meetings
                (source, source_event_id, triggered_by, meeting_url,
                 title, scheduled_at, invitees, status)
            VALUES ('calendar', $1, $2, $3, $4, $5, $6::jsonb, 'queued')
            ON CONFLICT (source, source_event_id, scheduled_at)
                WHERE source = 'calendar' AND source_event_id IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            bitrix_event_id,
            triggered_by,
            meeting_url,
            title,
            scheduled_at_utc,
            seed_invitees,
        )
    return new_id is not None


async def _process_event(
    ev: dict[str, Any],
    *,
    now_utc: datetime,
    triggered_by: int,
    lead: int,
    grace: int,
) -> bool:
    bitrix_id = str(ev.get("ID") or "").strip()
    if not bitrix_id:
        return False
    start_utc = _parse_event_start(ev)
    if start_utc is None:
        return False
    delta = (start_utc - now_utc).total_seconds()
    # delta > lead: too early, will catch on a later tick.
    # delta < -grace: too late, skip — don't try to record a 30-min meeting
    # that's already been going for 10 minutes.
    if delta > lead or delta < -grace:
        return False
    url = _extract_telemost_url(ev)
    if not url:
        logger.debug(
            "Scheduler: skipping Bitrix event %s (%s) — no Telemost URL",
            bitrix_id, ev.get("NAME"),
        )
        return False
    title = (ev.get("NAME") or "").strip() or None
    inserted = await _queue_meeting(
        bitrix_event_id=bitrix_id,
        title=title,
        meeting_url=url,
        scheduled_at_utc=start_utc,
        triggered_by=triggered_by,
    )
    if inserted:
        logger.info(
            "Scheduler queued: Bitrix #%s %r -> %s @ %s (in %ds)",
            bitrix_id, title, url, start_utc.isoformat(), int(delta),
        )
    return inserted


async def _tick(*, telegram_id: int, bitrix_user_id: str) -> int:
    events = await _fetch_bitrix_events(bitrix_user_id)
    now_utc = datetime.now(timezone.utc)
    inserted = 0
    for ev in events:
        try:
            if await _process_event(
                ev,
                now_utc=now_utc,
                triggered_by=telegram_id,
                lead=SCHEDULER_LEAD_SECONDS,
                grace=SCHEDULER_GRACE_SECONDS,
            ):
                inserted += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "Scheduler: failed to process Bitrix event %s", ev.get("ID"),
            )
    return inserted


async def fetch_active_users() -> list[Any]:
    """Return all active users from telemost.users WHERE is_active=true.

    Each returned record has `.telegram_id` (int) and `.bitrix_id` (str).
    Uses the existing asyncpg pool pattern from auth.py.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT telegram_id, bitrix_id FROM telemost.users WHERE is_active = true",
        )
    return list(rows)


async def _tick_all_users() -> int:
    """Multi-user tick: poll every active user's Bitrix calendar, deduplicate
    by (meeting_url, scheduled_at) in memory, then INSERT candidates.

    Returns the total number of new meetings queued in this tick.
    """
    users = await fetch_active_users()
    if not users:
        logger.debug("Scheduler: no active users in telemost.users, skipping tick")
        return 0

    now_utc = datetime.now(timezone.utc)
    lead = SCHEDULER_LEAD_SECONDS
    grace = SCHEDULER_GRACE_SECONDS

    # In-memory dedup: (url, scheduled_at) → first-winner _Candidate
    candidates: dict[tuple[str, datetime], _Candidate] = {}

    for u in users:
        bitrix_id: str = u["bitrix_id"]
        telegram_id: int = u["telegram_id"]
        try:
            events = await _fetch_bitrix_events(bitrix_id)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduler: Bitrix fetch failed for user bitrix_id=%s", bitrix_id)
            continue

        for ev in events:
            # #nobot opt-out
            name = (ev.get("NAME") or "").strip()
            if "#nobot" in name.lower():
                logger.debug("Scheduler: skipping #nobot event %s", ev.get("ID"))
                continue

            url = _extract_telemost_url(ev)
            if not url:
                continue

            start_utc = _parse_event_start(ev)
            if start_utc is None:
                continue

            delta = (start_utc - now_utc).total_seconds()
            if delta > lead or delta < -grace:
                continue

            key = (url, start_utc)
            if key not in candidates:
                candidates[key] = _Candidate(
                    url=url,
                    title=name or None,
                    scheduled_at=start_utc,
                    triggered_by=telegram_id,
                    source_event_id=str(ev.get("ID") or "").strip(),
                )

    queued = 0
    for c in candidates.values():
        if not c.source_event_id:
            continue
        try:
            inserted = await _queue_meeting(
                bitrix_event_id=c.source_event_id,
                title=c.title,
                meeting_url=c.url,
                scheduled_at_utc=c.scheduled_at,
                triggered_by=c.triggered_by,
            )
            if inserted:
                logger.info(
                    "Scheduler queued (multi-user): %r -> %s @ %s (triggered_by=%d)",
                    c.title, c.url, c.scheduled_at.isoformat(), c.triggered_by,
                )
                queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("Scheduler: failed to queue meeting %s", c.url)

    return queued


async def run_forever() -> None:
    """Bitrix calendar scheduler — auto-queues a recording for each calendar
    Telemost meeting just before it starts.

    Modes:
    - TELEMOST_SCHEDULER_ENABLED=false (default) → returns immediately.
    - TELEMOST_SCHEDULER_ENABLED=true + legacy env set → single-user mode.
    - TELEMOST_SCHEDULER_ENABLED=true + legacy env empty → multi-user mode:
        iterates telemost.users WHERE is_active=true each tick.
    """
    if not SCHEDULER_ENABLED:
        logger.info(
            "Scheduler disabled (TELEMOST_SCHEDULER_ENABLED=false). "
            "Set to 'true' to activate."
        )
        return

    bitrix_user_id = SCHEDULER_BITRIX_USER_ID
    telegram_id = SCHEDULER_TELEGRAM_ID

    if bitrix_user_id and telegram_id is not None:
        # Legacy single-user mode — preserved for dev / testing.
        logger.info(
            "Scheduler starting in LEGACY single-user mode "
            "(bitrix_user_id=%s, telegram_id=%d, tick=%ds, lead=%ds, grace=%ds)",
            bitrix_user_id, telegram_id,
            SCHEDULER_TICK_SECONDS, SCHEDULER_LEAD_SECONDS, SCHEDULER_GRACE_SECONDS,
        )
        while True:
            try:
                await _tick(telegram_id=telegram_id, bitrix_user_id=bitrix_user_id)
            except Exception:  # noqa: BLE001
                logger.exception("Scheduler tick crashed (legacy)")
            await asyncio.sleep(SCHEDULER_TICK_SECONDS)
    else:
        # Multi-user mode — iterate all active users from telemost.users.
        logger.info(
            "Scheduler starting in MULTI-USER mode "
            "(tick=%ds, lead=%ds, grace=%ds)",
            SCHEDULER_TICK_SECONDS, SCHEDULER_LEAD_SECONDS, SCHEDULER_GRACE_SECONDS,
        )
        while True:
            try:
                await _tick_all_users()
            except Exception:  # noqa: BLE001
                logger.exception("Scheduler tick failed (multi-user)")
            await asyncio.sleep(SCHEDULER_TICK_SECONDS)
