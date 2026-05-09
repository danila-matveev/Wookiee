"""/help command."""
from __future__ import annotations

from services.telemost_recorder_api.telegram_client import tg_send_message

_HELP = (
    "🎙 *Wookiee Recorder*\n\n"
    "📝 *Команды:*\n"
    "• `/record <ссылка>` — записать встречу\n"
    "• `/status` — активные + последние записи\n"
    "• `/list` — последние 10 встреч\n"
    "• `/start` — главное меню\n"
    "• `/help` — эта справка\n\n"
    "💡 *Лайфхак:* можешь не писать `/record` — "
    "просто пришли ссылку на Я.Телемост, я сам всё пойму.\n\n"
    "🔁 *Что я возвращаю после встречи:*\n"
    "• краткий summary с темами, решениями и задачами\n"
    "• полный transcript как `.txt` файл\n\n"
    "🔒 *Хранение:*\n"
    "• Аудио — 30 дней\n"
    "• Текст и summary — бессрочно\n\n"
    "❓ Вопросы → @matveev\\_danila"
)


async def handle_help(chat_id: int) -> None:
    await tg_send_message(chat_id, _HELP)
