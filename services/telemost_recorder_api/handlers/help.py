"""/help command."""
from __future__ import annotations

from services.telemost_recorder_api.telegram_client import tg_send_message

_HELP = (
    "🎙 *Саймон — справка*\n\n"
    "📝 *Команды:*\n"
    "• `/record <url>` — записать конкретную встречу прямо сейчас\n"
    "• `/status` — что я сейчас пишу\n"
    "• `/list` — мои последние записи (10 шт)\n"
    "• `/start` — главное меню\n"
    "• `/help` — эта подсказка\n\n"
    "💡 *Лайфхак:* можешь не писать `/record` — "
    "просто пришли ссылку на Я.Телемост, я сам всё пойму.\n\n"
    "🔁 *Что я возвращаю после встречи:*\n"
    "• краткий summary с темами, решениями и задачами\n"
    "• полный transcript как `.txt` файл\n\n"
    "🔒 *Хранение:*\n"
    "• Аудио — 30 дней\n"
    "• Текст и summary — бессрочно\n\n"
    "🚫 *Не хочешь чтобы я пришёл?* Поставь `#nobot` в название встречи в Bitrix.\n\n"
    "❓ Вопросы → @matveev\\_danila"
)


async def handle_help(chat_id: int) -> None:
    await tg_send_message(chat_id, _HELP)
