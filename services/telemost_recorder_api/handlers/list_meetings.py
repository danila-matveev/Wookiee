"""/list — последние 10 встреч с твоим участием (privacy scope §15.8)."""
from __future__ import annotations

import json
from typing import Any

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message


def _format_row(row: dict[str, Any]) -> str:
    title = row["title"] or "(без названия)"
    started = row["started_at"].strftime("%d.%m %H:%M") if row["started_at"] else "—"
    return f"• `{str(row['id'])[:8]}` [{row['status']}] {title} ({started})"


async def handle_list(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "Сначала /start.")
        return
    pool = await get_pool()
    invitee_filter = json.dumps([{"telegram_id": user_id}])
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, status, title, started_at
            FROM telemost.meetings
            WHERE triggered_by = $1
               OR organizer_id = $1
               OR invitees @> $2::jsonb
            ORDER BY COALESCE(started_at, created_at) DESC
            LIMIT 10
            """,
            user_id,
            invitee_filter,
        )
    if not rows:
        await tg_send_message(chat_id, "Не нашёл ни одной твоей встречи.")
        return
    lines = ["*Последние 10 встреч:*"]
    lines.extend(_format_row(r) for r in rows)
    await tg_send_message(chat_id, "\n".join(lines))
