"""/status — твои active + recent meetings."""
from __future__ import annotations

from typing import Any

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.telegram_client import tg_send_message


def _format_row(row: dict[str, Any]) -> str:
    title = row["title"] or "(без названия)"
    started = row["started_at"].strftime("%d.%m %H:%M") if row["started_at"] else "—"
    return f"• `{str(row['id'])[:8]}` [{row['status']}] {title} ({started})"


async def handle_status(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "Сначала /start.")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            (SELECT id, status, title, started_at, ended_at
             FROM telemost.meetings
             WHERE triggered_by = $1
                AND status IN ('queued','recording','postprocessing'))
            UNION ALL
            (SELECT id, status, title, started_at, ended_at
             FROM telemost.meetings
             WHERE triggered_by = $1
                AND status IN ('done','failed')
             ORDER BY ended_at DESC NULLS LAST
             LIMIT 5)
            """,
            user_id,
        )
    if not rows:
        await tg_send_message(chat_id, "У тебя пока нет записей.")
        return
    lines = ["*Твои записи:*"]
    lines.extend(_format_row(r) for r in rows)
    await tg_send_message(chat_id, "\n".join(lines))
