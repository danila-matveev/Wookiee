"""/list — последние 10 встреч с твоим участием (privacy scope §15.8)."""
from __future__ import annotations

import json

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.handlers._format import fmt_history_row
from services.telemost_recorder_api.telegram_client import tg_send_message

_EMPTY = (
    "📭 *Не нашёл ни одной твоей встречи*\n\n"
    "Пришли мне ссылку на Я.Телемост или /help для справки."
)


async def handle_list(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "🔒 Сначала /start.")
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
        await tg_send_message(chat_id, _EMPTY)
        return
    lines = ["📋 *Последние 10 встреч*", ""]
    lines.extend(fmt_history_row(r) for r in rows)
    await tg_send_message(chat_id, "\n".join(lines))
