"""Bitrix24 calendar lookup — find a calendar event by meeting URL.

Used at /record-time to enrich telemost.meetings.title + invitees so the DM
shows a real subject and Bitrix-mapped participant list (rather than the
generic "(без названия)" + Speaker 0/1/2).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from services.telemost_recorder_api.config import (
    BITRIX24_WEBHOOK_URL,
    BITRIX_TIMEOUT_SECONDS,
)
from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)

_LOOKUP_WINDOW_HOURS = 4  # ±2 ч от now()
_BITRIX_RETRIES = 3
_BITRIX_BACKOFF_BASE = 1.0
# Bitrix returns DATE_FROM as a naive string in the calendar owner's TZ.
# Wookiee's kabinet is Europe/Moscow — hard-coded here because there's no
# per-user TZ in the webhook payload we use.
_BITRIX_TZ = ZoneInfo("Europe/Moscow")


def _extract_attendee_ids(codes: list[Any] | None) -> list[int]:
    out: list[int] = []
    for c in codes or []:
        if isinstance(c, str) and c.startswith("U"):
            try:
                out.append(int(c[1:]))
            except ValueError:
                continue
    return out


def _event_mentions_url(ev: dict, url: str) -> bool:
    haystacks = (
        str(ev.get("LOCATION") or ""),
        str(ev.get("DESCRIPTION") or ""),
        str(ev.get("NAME") or ""),
    )
    return any(url in h for h in haystacks)


def _parse_bitrix_date(s: str | None) -> datetime | None:
    """Parse Bitrix DATE_FROM ('13.05.2026 08:30:00') to UTC datetime.

    Bitrix returns dates as naive strings in the calendar owner's TZ
    (Europe/Moscow for Wookiee). Pre-fix we tagged the parsed datetime
    as UTC, which made every event look 3 hours earlier than it was —
    enough to make _pick_closest_meeting choose the wrong neighbour.

    We attach Europe/Moscow explicitly, then convert to UTC for
    storage and comparisons.
    """
    if not s:
        return None
    for fmt in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=_BITRIX_TZ).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _is_real_meeting(ev: dict) -> bool:
    """Heuristic: a 'real' meeting with people, not personal time-block.

    - Has ≥2 attendees (otherwise it's a self-block like 'няня' / 'обед').
    - IS_MEETING flag is true (covers Bitrix-видеосвязь where LOCATION is a code).
    """
    if ev.get("IS_MEETING") is True:
        return True
    return len(ev.get("ATTENDEES_CODES") or []) >= 2


def _pick_closest_meeting(events: list[dict], now: datetime) -> Optional[dict]:
    """From a list of events, return the one closest to `now` that looks like a real meeting."""
    best: Optional[dict] = None
    best_delta: float = float("inf")
    for ev in events:
        if not _is_real_meeting(ev):
            continue
        start = _parse_bitrix_date(ev.get("DATE_FROM"))
        if start is None:
            continue
        delta = abs((start - now).total_seconds())
        if delta < best_delta:
            best_delta = delta
            best = ev
    return best


def _normalize_event(ev: dict) -> dict[str, Any]:
    return {
        "title": (ev.get("NAME") or "").strip() or None,
        "bitrix_attendee_ids": _extract_attendee_ids(ev.get("ATTENDEES_CODES")),
        # parse into datetime so asyncpg accepts it for timestamptz column
        "scheduled_at": _parse_bitrix_date(ev.get("DATE_FROM")),
        "source_event_id": str(ev.get("ID")) if ev.get("ID") else None,
    }


async def find_event_by_url(
    bitrix_user_id: str,
    meeting_url: str,
    window_hours: int = _LOOKUP_WINDOW_HOURS,
) -> Optional[dict[str, Any]]:
    """Return normalized event matching meeting_url, with time-proximity fallback.

    First tries URL match in LOCATION/DESCRIPTION/NAME. If nothing matches —
    falls back to the calendar event closest in time to now() that looks like a
    real meeting (≥2 attendees or IS_MEETING flag). This covers events that use
    Bitrix-видеосвязь codes (`calendar_357_22673`) instead of plain Telemost URLs.
    """
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    to = (now + timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    base = BITRIX24_WEBHOOK_URL.rstrip("/")
    params = {"type": "user", "ownerId": bitrix_user_id, "from": frm, "to": to}

    resp = None
    for attempt in range(_BITRIX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=BITRIX_TIMEOUT_SECONDS) as c:
                resp = await c.get(f"{base}/calendar.event.get.json", params=params)
        except httpx.HTTPError as e:
            logger.warning(
                "Bitrix calendar.event.get attempt %d/%d failed: %s",
                attempt + 1, _BITRIX_RETRIES, e,
            )
            resp = None
            if attempt < _BITRIX_RETRIES - 1:
                await asyncio.sleep(_BITRIX_BACKOFF_BASE * (2 ** attempt))
            continue
        if resp.is_success:
            break
        # 4xx is unlikely to succeed on retry — bail out
        if resp.status_code < 500 and resp.status_code != 429:
            logger.warning(
                "Bitrix calendar.event.get failed %d: %s",
                resp.status_code, resp.text[:200],
            )
            return None
        logger.warning(
            "Bitrix calendar.event.get %d on attempt %d/%d, retrying",
            resp.status_code, attempt + 1, _BITRIX_RETRIES,
        )
        if attempt < _BITRIX_RETRIES - 1:
            await asyncio.sleep(_BITRIX_BACKOFF_BASE * (2 ** attempt))

    if resp is None or not resp.is_success:
        return None

    try:
        items = resp.json().get("result") or []
    except (ValueError, json.JSONDecodeError) as e:  # json.JSONDecodeError is a ValueError subclass
        logger.warning("Bitrix calendar.event.get returned non-JSON: %s", e)
        return None
    if not isinstance(items, list):
        return None

    for ev in items:
        if _event_mentions_url(ev, meeting_url):
            logger.info("Bitrix match by URL for event %s", ev.get("ID"))
            return _normalize_event(ev)

    fallback = _pick_closest_meeting(items, now)
    if fallback is not None:
        logger.info(
            "Bitrix URL not found, falling back to closest-in-time event %s (%r)",
            fallback.get("ID"), fallback.get("NAME"),
        )
        return _normalize_event(fallback)

    return None


async def enrich_meeting_from_bitrix(
    meeting_id: UUID,
    meeting_url: str,
    triggered_by_bitrix_id: str,
) -> bool:
    """Find Bitrix event by URL, write title + invitees into telemost.meetings.

    Returns True if a matching event was found and the row was updated.
    """
    ev = await find_event_by_url(
        bitrix_user_id=triggered_by_bitrix_id,
        meeting_url=meeting_url,
    )
    if not ev:
        return False

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Empty bitrix_attendee_ids → ANY($1::text[]) returns zero rows → invitees='[]'.
        # We still UPDATE so title/scheduled_at land even without resolved invitees.
        rows = await conn.fetch(
            """
            SELECT telegram_id, name, bitrix_id
            FROM telemost.users
            WHERE bitrix_id = ANY($1::text[]) AND is_active = true
            """,
            [str(i) for i in ev["bitrix_attendee_ids"]],
        )
        invitees = [
            {"telegram_id": r["telegram_id"], "name": r["name"], "bitrix_id": r["bitrix_id"]}
            for r in rows
        ]
        await conn.execute(
            """
            UPDATE telemost.meetings
            SET title = $1,
                invitees = $2::jsonb,
                source_event_id = COALESCE(source_event_id, $3),
                scheduled_at = COALESCE(scheduled_at, $4::timestamptz)
            WHERE id = $5
            """,
            ev["title"],
            json.dumps(invitees, ensure_ascii=False),
            ev["source_event_id"],
            ev["scheduled_at"],
            meeting_id,
        )
    logger.info(
        "Enriched meeting %s: title=%r invitees=%d",
        meeting_id, ev["title"], len(invitees),
    )
    return True
