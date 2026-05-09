"""/status — твои active + recent meetings."""
from __future__ import annotations

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.handlers._format import (
    fmt_active_row,
    fmt_history_row,
)
from services.telemost_recorder_api.telegram_client import tg_send_message

_ACTIVE_STATUSES = ("queued", "recording", "postprocessing")
_HISTORY_STATUSES = ("done", "failed")

_EMPTY = (
    "📭 *У тебя пока нет записей*\n\n"
    "Пришли мне ссылку на Я.Телемост или /help для справки."
)


async def handle_status(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if not user:
        await tg_send_message(chat_id, "🔒 Сначала /start.")
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
        await tg_send_message(chat_id, _EMPTY)
        return

    active = [r for r in rows if r["status"] in _ACTIVE_STATUSES]
    history = [r for r in rows if r["status"] in _HISTORY_STATUSES]

    lines = ["📊 *Твои записи*"]
    if active:
        lines.append("")
        lines.append("🔴 *Активные:*")
        lines.extend(fmt_active_row(r) for r in active)
    if history:
        lines.append("")
        lines.append("📁 *Последние:*")
        lines.extend(fmt_history_row(r) for r in history)
    await tg_send_message(chat_id, "\n".join(lines))
