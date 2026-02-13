"""
Дайджест — ручной вызов по кнопке + автоматическая рассылка
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from lyudmila_bot.handlers.common import menu_only_keyboard, send_error_message, safe_callback_answer

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == "action_digest")
async def manual_digest(
    callback: CallbackQuery,
    auth_service, digest_service,
):
    """Ручной вызов дайджеста по кнопке"""
    user = auth_service.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text("🔄 Собираю дайджест...")

    try:
        digest_text = await digest_service.generate_digest(user)

        await callback.message.edit_text(
            digest_text,
            parse_mode="HTML",
            reply_markup=menu_only_keyboard(),
        )

    except Exception as e:
        logger.exception(f"Manual digest failed: {e}")
        await send_error_message(callback, "Не удалось собрать дайджест. Попробуйте позже.")

    await safe_callback_answer(callback)
