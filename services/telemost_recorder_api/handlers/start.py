"""/start command — auth check + welcome."""
from __future__ import annotations

from services.telemost_recorder_api.auth import get_user_by_telegram_id
from services.telemost_recorder_api.telegram_client import tg_send_message

_WELCOME = """Привет, {name}!

Я Wookiee Recorder — записываю встречи Я.Телемоста и присылаю summary.

Команды:
• `/record <ссылка>` — записать встречу
• `/status` — твои активные/последние записи
• `/list` — последние 10 встреч с твоим участием
• `/help` — справка
"""

_AUTH_FAIL = """Не нашёл твой Telegram-ID в Bitrix-roster.

Чтобы получить доступ:
1. Открой свой профиль в Bitrix24 → «Контактная информация» → «Telegram»
2. Введи `@matveev_danila` (либо свой numeric ID)
3. Сохрани
4. Через час напиши мне `/start` снова

Если что-то не работает — скинь скриншот @matveev_danila."""


async def handle_start(chat_id: int, user_id: int) -> None:
    user = await get_user_by_telegram_id(user_id)
    if user is None:
        await tg_send_message(chat_id, _AUTH_FAIL)
        return
    name = user.get("short_name") or user["name"]
    await tg_send_message(chat_id, _WELCOME.format(name=name))
