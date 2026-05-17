"""/start command — auth check + welcome with active-recording banner."""
from __future__ import annotations

from typing import Any

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.db import get_pool
from services.telemost_recorder_api.handlers._format import fmt_active_row, md_escape
from services.telemost_recorder_api.keyboards import AUTH_FAIL, WELCOME
from services.telemost_recorder_api.telegram_client import tg_send_message

_AUTH_FAIL = (
    "🔒 *Доступ ограничен*\n\n"
    "Я работаю только с командой Wookiee. "
    "Не нашёл твой Telegram в Bitrix24-roster.\n\n"
    "*Как получить доступ:*\n"
    "1️⃣ Открой свой профиль в Bitrix24\n"
    "2️⃣ В поле «Telegram» впиши свой numeric ID или @username\n"
    "3️⃣ Сохрани — синхронизация раз в час\n"
    "4️⃣ Через час напиши мне /start снова\n\n"
    "Если что-то не так — напиши @matveev\\_danila."
)


async def _fetch_active_meetings(user_id: int) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, started_at, status
            FROM telemost.meetings
            WHERE triggered_by = $1
              AND status IN ('queued','recording','postprocessing')
            ORDER BY created_at DESC
            """,
            user_id,
        )
    return [dict(r) for r in rows]


def _format_welcome(name: str, active: list[dict[str, Any]]) -> str:
    name_safe = md_escape(name)
    parts: list[str] = []
    if active:
        parts.append("🔴 *Сейчас в работе:*")
        parts.extend(fmt_active_row(m) for m in active)
        parts.append("")
        parts.append("———")
        parts.append("")
    parts.append(f"Привет, {name_safe}! 👋")
    parts.append("")
    parts.append(
        "Я *Саймон* — хожу на ваши Telemost-встречи и записываю их: "
        "расшифровка, саммари в DM, экспорт в Notion по кнопке."
    )
    parts.append("")
    parts.append("📌 *Команды:*")
    parts.append("• `/record <url>` — записать конкретную встречу прямо сейчас")
    parts.append("• `/status` — что я сейчас пишу")
    parts.append("• `/list` — мои последние записи (10 шт)")
    parts.append("• `/help` — подсказка")
    parts.append("")
    parts.append(
        "Если у вас в Bitrix-календаре есть встречи с Telemost-ссылкой — "
        "я приду сам, ничего делать не надо."
    )
    parts.append("")
    parts.append(
        "Чтобы я *не* приходил на встречу — поставьте `#nobot` в название встречи в Bitrix."
    )
    return "\n".join(parts)


async def handle_start(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if user is None:
        await tg_send_message(chat_id, _AUTH_FAIL, reply_markup=AUTH_FAIL)
        return
    name = user.get("short_name") or user["name"]
    active = await _fetch_active_meetings(user_id)
    text = _format_welcome(name, active)
    await tg_send_message(chat_id, text, reply_markup=WELCOME)
