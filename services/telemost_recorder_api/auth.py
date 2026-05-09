"""Bitrix24 user sync + auth lookup by telegram_id.

Bitrix custom field UF_USR_1774019332169 (discovered 2026-05-08) holds the
Telegram identifier. Format depends on what the employee filled in:
- Numeric telegram_id (already-known): "123456789"
- Username with or without @: "@petrov"
- t.me link: "https://t.me/petrov"
- Empty / unset: skip the user

Phase 0 stores only resolved numeric telegram_ids. Usernames are resolved
via Telegram getChat — works only if the user has DM'd the bot at least
once (Telegram privacy rule).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from services.telemost_recorder_api.config import BITRIX24_WEBHOOK_URL
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import TelegramAPIError, tg_call

logger = logging.getLogger(__name__)

_TELEGRAM_FIELD_KEYS = ("UF_USR_1774019332169",)  # discovered 2026-05-08
_USERNAME_RE = re.compile(r"(?:t\.me/|@)([A-Za-z0-9_]{3,32})", re.IGNORECASE)
_NUMERIC_RE = re.compile(r"^\d+$")


async def _fetch_bitrix_users() -> list[dict]:
    """Fetch active employees from Bitrix24 user.get."""
    url = BITRIX24_WEBHOOK_URL.rstrip("/") + "/user.get.json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params={"ACTIVE": "Y"})
    resp.raise_for_status()
    return resp.json().get("result", [])


def _extract_telegram_raw(user_record: dict) -> Optional[str]:
    """Return the first non-empty telegram-field value, stripped."""
    for key in _TELEGRAM_FIELD_KEYS:
        value = user_record.get(key)
        if value is None:
            continue
        stripped = str(value).strip()
        if stripped:
            return stripped
    return None


async def _resolve_telegram_id(raw: str) -> Optional[int]:
    """Resolve a raw Bitrix telegram-field value to numeric telegram_id."""
    raw = raw.strip()
    if _NUMERIC_RE.fullmatch(raw):
        return int(raw)
    match = _USERNAME_RE.search(raw)
    if not match:
        return None
    username = match.group(1)
    try:
        chat = await tg_call("getChat", chat_id=f"@{username}")
        return int(chat["id"])
    except TelegramAPIError as exc:
        logger.warning("Could not resolve @%s to telegram_id: %s", username, exc)
        return None


async def sync_users_from_bitrix() -> int:
    """Pull users from Bitrix, upsert into telemost.users.

    Returns the count of users with successfully resolved telegram_id.
    """
    raw_users = await _fetch_bitrix_users()
    pool = await get_pool()
    synced = 0
    async with pool.acquire() as conn:
        for u in raw_users:
            tg_raw = _extract_telegram_raw(u)
            if not tg_raw:
                continue
            tg_id = await _resolve_telegram_id(tg_raw)
            if not tg_id:
                continue
            full_name = " ".join(filter(None, [u.get("NAME"), u.get("LAST_NAME")])) or "—"
            short_name = u.get("NAME") or full_name
            is_active = u.get("ACTIVE") in (True, "Y", "y", 1, "1")
            await conn.execute(
                """
                INSERT INTO telemost.users
                    (telegram_id, bitrix_id, name, short_name, is_active, synced_at)
                VALUES ($1, $2, $3, $4, $5, now())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    bitrix_id  = EXCLUDED.bitrix_id,
                    name       = EXCLUDED.name,
                    short_name = EXCLUDED.short_name,
                    is_active  = EXCLUDED.is_active,
                    synced_at  = now()
                """,
                tg_id,
                str(u["ID"]),
                full_name,
                short_name,
                is_active,
            )
            synced += 1
    logger.info("Synced %d users from Bitrix", synced)
    return synced


async def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
    """Return active user record by telegram_id, or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT telegram_id, bitrix_id, name, short_name, is_active
            FROM telemost.users
            WHERE telegram_id = $1 AND is_active = true
            """,
            telegram_id,
        )
    return dict(row) if row else None
