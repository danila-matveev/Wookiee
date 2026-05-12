"""Bitrix24 calendar lookup — find a calendar event by meeting URL.

Used at /record-time to enrich telemost.meetings.title + invitees so the DM
shows a real subject and Bitrix-mapped participant list (rather than the
generic "(без названия)" + Speaker 0/1/2).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import httpx

from services.telemost_recorder_api.config import BITRIX24_WEBHOOK_URL
from services.telemost_recorder_api.db import get_pool

logger = logging.getLogger(__name__)

_LOOKUP_WINDOW_HOURS = 4  # ±2 ч от now()
_HTTP_TIMEOUT = 15.0


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


async def find_event_by_url(
    bitrix_user_id: str,
    meeting_url: str,
    window_hours: int = _LOOKUP_WINDOW_HOURS,
) -> Optional[dict[str, Any]]:
    """Return normalized event dict matching meeting_url, or None."""
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    to = (now + timedelta(hours=window_hours / 2)).strftime("%Y-%m-%dT%H:%M:%S")
    base = BITRIX24_WEBHOOK_URL.rstrip("/")
    params = {"type": "user", "ownerId": bitrix_user_id, "from": frm, "to": to}

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
            resp = await c.get(f"{base}/calendar.event.get.json", params=params)
    except httpx.HTTPError as e:
        logger.warning("Bitrix calendar.event.get HTTP error: %s", e)
        return None

    if not resp.is_success:
        logger.warning(
            "Bitrix calendar.event.get failed %d: %s",
            resp.status_code, resp.text[:200],
        )
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
            return {
                "title": (ev.get("NAME") or "").strip() or None,
                "bitrix_attendee_ids": _extract_attendee_ids(
                    ev.get("ATTENDEES_CODES")
                ),
                "scheduled_at": ev.get("DATE_FROM"),
                "source_event_id": str(ev.get("ID")) if ev.get("ID") else None,
            }
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
