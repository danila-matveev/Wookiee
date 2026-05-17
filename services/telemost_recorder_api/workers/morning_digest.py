"""Morning digest worker — daily 09:00 MSK DM for each active Wookiee user.

Трек C2 (SPEC §4.3).

How it works:
1. Loop calculates seconds until the next MORNING_DIGEST_HOUR_MSK in
   Europe/Moscow, sleeps, then sends digests to all active users.
2. For each active user, fetches today's Bitrix calendar events and
   classifies them into three groups:
     🎙 has_link  — event has a Telemost URL (scheduler will record it)
     ⚠️ needs_link — real meeting (≥2 attendees or IS_MEETING) but no URL
     ⏭ personal   — personal time-block (single person, IS_MEETING=False)
3. If there are no has_link + needs_link events → skip (don't send).
4. Sends a formatted DM with an inline keyboard: one «➕ Добавить Telemost»
   button per needs_link event.

Master switch:
  MORNING_DIGEST_ENABLED=false (default) → returns immediately without
  starting the loop. Operator sets to true to activate.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from services.telemost_recorder_api.config import (
    BITRIX24_WEBHOOK_URL,
    BITRIX_TIMEOUT_SECONDS,
    MORNING_DIGEST_ENABLED,
    MORNING_DIGEST_HOUR_MSK,
)
from services.telemost_recorder_api.keyboards import digest_keyboard
from services.telemost_recorder_api.telegram_client import tg_send_message
from services.telemost_recorder_api.workers.scheduler_worker import fetch_active_users

logger = logging.getLogger(__name__)

_MSK = ZoneInfo("Europe/Moscow")

# Reuse the same URL pattern as scheduler_worker for consistency.
_TELEMOST_URL_RE = re.compile(
    r"https://telemost(?:\.360)?\.yandex\.ru/j/[A-Za-z0-9_-]+",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def compute_next_msk_hour(
    hour: int,
    *,
    _now_msk: datetime | None = None,
) -> datetime:
    """Return the next occurrence of ``hour:00:00`` in Europe/Moscow.

    If the current MSK time is *before* ``hour`` → today at ``hour:00:00``.
    Otherwise (at or after ``hour``) → tomorrow at ``hour:00:00``.

    Args:
        hour: Target hour (0-23) in MSK.
        _now_msk: Injected for testing; defaults to datetime.now(_MSK).

    Returns:
        Timezone-aware datetime in Europe/Moscow.
    """
    now = _now_msk if _now_msk is not None else datetime.now(_MSK)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


# ---------------------------------------------------------------------------
# Bitrix helpers (digest-specific)
# ---------------------------------------------------------------------------


def _extract_telemost_url(ev: dict[str, Any]) -> str | None:
    """Return Telemost URL from LOCATION or DESCRIPTION, or None."""
    loc = (ev.get("LOCATION") or "").strip()
    # Reject Bitrix-Видеоконференция codes (e.g. "calendar_357_22673")
    if loc.startswith("https://telemost") or loc.startswith("https://telemost.360"):
        return loc
    m = _TELEMOST_URL_RE.search(loc)
    if m:
        return m.group(0)
    desc = ev.get("DESCRIPTION") or ""
    m = _TELEMOST_URL_RE.search(desc)
    if m:
        return m.group(0)
    return None


def _is_real_meeting(ev: dict[str, Any]) -> bool:
    """True if event is a real meeting with ≥2 people (not a personal block)."""
    if ev.get("IS_MEETING") is True:
        return True
    return len(ev.get("ATTENDEES_CODES") or []) >= 2


def _parse_time_label(ev: dict[str, Any]) -> str:
    """Format DATE_FROM as HH:MM string for display in the digest."""
    raw = (ev.get("DATE_FROM") or "").strip()
    # Bitrix format: "16.05.2026 11:00:00"
    parts = raw.split(" ")
    if len(parts) == 2:
        time_part = parts[1]
        return time_part[:5]  # "11:00"
    return raw[:5] if raw else "?"


def _classify_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split events into (has_link, needs_link, personal)."""
    has_link: list[dict] = []
    needs_link: list[dict] = []
    personal: list[dict] = []

    for ev in events:
        if not _is_real_meeting(ev):
            personal.append(ev)
            continue
        url = _extract_telemost_url(ev)
        if url:
            has_link.append(ev)
        else:
            needs_link.append(ev)

    return has_link, needs_link, personal


async def _fetch_today_events(bitrix_user_id: str) -> list[dict[str, Any]]:
    """Fetch today's events from Bitrix for the given user (MSK day window)."""
    now_msk = datetime.now(_MSK)
    day_start = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    frm = day_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    to = day_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    base = BITRIX24_WEBHOOK_URL.rstrip("/")
    params = {"type": "user", "ownerId": bitrix_user_id, "from": frm, "to": to}
    try:
        async with httpx.AsyncClient(timeout=BITRIX_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{base}/calendar.event.get.json", params=params)
    except httpx.HTTPError as e:
        logger.warning(
            "morning_digest: Bitrix fetch failed for user %s: %s", bitrix_user_id, e
        )
        return []
    if not resp.is_success:
        logger.warning(
            "morning_digest: Bitrix returned %d for user %s",
            resp.status_code, bitrix_user_id,
        )
        return []
    try:
        payload = resp.json()
    except ValueError:
        return []
    items = payload.get("result") or []
    return items if isinstance(items, list) else []


# ---------------------------------------------------------------------------
# Message rendering
# ---------------------------------------------------------------------------


def _render_digest(
    user: Any,
    has_link: list[dict],
    needs_link: list[dict],
    personal: list[dict],
) -> str:
    """Build the morning digest message text."""
    short_name = (
        user.get("short_name") if hasattr(user, "get") else getattr(user, "short_name", None)
    ) or (
        user.get("name") if hasattr(user, "get") else getattr(user, "name", "")
    ) or ""

    total = len(has_link) + len(needs_link)
    lines: list[str] = [
        f"Доброе утро, {short_name}.",
        "",
        f"Сегодня у тебя {total} {'встреча' if total == 1 else 'встречи' if 2 <= total <= 4 else 'встреч'}:",
        "",
    ]

    if has_link:
        lines.append("🎙 Запишу (есть Telemost-ссылка):")
        for ev in has_link:
            t = _parse_time_label(ev)
            name = (ev.get("NAME") or "Встреча").strip()
            lines.append(f"   • {t} — {name}")
        lines.append("")

    if needs_link:
        lines.append("⚠️ Нет ссылки — добавлю если нажмёшь:")
        for ev in needs_link:
            t = _parse_time_label(ev)
            name = (ev.get("NAME") or "Встреча").strip()
            lines.append(f"   • {t} — {name}")
        lines.append("")

    if personal:
        lines.append("⏭ Личное (не приду):")
        for ev in personal:
            t = _parse_time_label(ev)
            name = (ev.get("NAME") or "Встреча").strip()
            lines.append(f"   • {t} — {name}")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Public send functions
# ---------------------------------------------------------------------------


async def send_daily_digest_to_user(user: Any) -> None:
    """Fetch today's events and send a digest DM to ``user``.

    If there are no real meetings (has_link + needs_link == 0) → skip.

    Args:
        user: asyncpg Record or any object with ``telegram_id``,
              ``bitrix_id``, ``name`` / ``short_name`` attributes.
    """
    bitrix_id = user["bitrix_id"] if hasattr(user, "__getitem__") else user.bitrix_id
    telegram_id = user["telegram_id"] if hasattr(user, "__getitem__") else user.telegram_id

    events = await _fetch_today_events(bitrix_id)
    has_link, needs_link, personal = _classify_events(events)

    if not has_link and not needs_link:
        logger.debug("morning_digest: no real meetings for user %d — skipping", telegram_id)
        return

    text = _render_digest(user, has_link, needs_link, personal)
    keyboard = digest_keyboard(needs_link) if needs_link else None

    await tg_send_message(
        telegram_id,
        text,
        reply_markup=keyboard,
        parse_mode=None,  # plain text — emoji don't need MarkdownV2
    )
    logger.info(
        "morning_digest: sent to user %d — has_link=%d needs_link=%d personal=%d",
        telegram_id, len(has_link), len(needs_link), len(personal),
    )


async def send_digests_to_all_users() -> None:
    """Fetch all active users and send morning digest to each one."""
    users = await fetch_active_users()
    logger.info("morning_digest: sending digests to %d active users", len(users))
    for u in users:
        try:
            await send_daily_digest_to_user(u)
        except Exception:  # noqa: BLE001
            logger.exception(
                "morning_digest: failed to send digest to user %s",
                u["telegram_id"] if hasattr(u, "__getitem__") else getattr(u, "telegram_id", "?"),
            )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def morning_digest_loop() -> None:
    """Async loop — wakes at MORNING_DIGEST_HOUR_MSK every day and sends digests.

    Master switch: MORNING_DIGEST_ENABLED=false (default) → returns
    immediately without sleeping or sending anything.
    """
    if not MORNING_DIGEST_ENABLED:
        logger.info(
            "morning_digest disabled (MORNING_DIGEST_ENABLED=false). "
            "Set to 'true' to activate."
        )
        return

    logger.info(
        "morning_digest starting — will fire daily at %02d:00 MSK",
        MORNING_DIGEST_HOUR_MSK,
    )
    while True:
        next_run = compute_next_msk_hour(MORNING_DIGEST_HOUR_MSK)
        now_utc = datetime.now(timezone.utc)
        delay = (next_run.astimezone(timezone.utc) - now_utc).total_seconds()
        logger.info(
            "morning_digest: sleeping %.0f s until %s",
            delay,
            next_run.strftime("%Y-%m-%d %H:%M MSK"),
        )
        await asyncio.sleep(max(delay, 0))
        try:
            await send_digests_to_all_users()
        except Exception:  # noqa: BLE001
            logger.exception("morning_digest tick failed")
