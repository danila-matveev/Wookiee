"""
Свободный ввод — Людмила реагирует на любое сообщение.

Определяет intent (задача / встреча / непонятно) через LLM
и направляет в соответствующий флоу.

Регистрируется ПОСЛЕДНИМ — ловит только необработанные сообщения.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from lyudmila_bot.handlers.common import menu_only_keyboard
from lyudmila_bot.handlers.menu import create_main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text)
async def handle_free_message(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase, context_service,
):
    """
    Catch-all для текстовых сообщений вне FSM-состояния.

    1. Определяет intent через LLM
    2. task → process_task_description()
    3. meeting → process_meeting_description()
    4. unknown → fallback с кнопками меню
    """
    # Не авторизован — игнорируем
    if not auth_service.is_authenticated(message.from_user.id):
        return

    # Если пользователь в активном FSM-состоянии — не мешаем
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer(
            "Вы сейчас в процессе создания. "
            "Используйте кнопки или /menu для возврата в главное меню.",
            reply_markup=menu_only_keyboard(),
        )
        return

    # Определяем intent через быстрый LLM-вызов
    processing_msg = await message.answer("🔄 Анализирую...")

    try:
        intent = await lyuda_ai.detect_intent(message.text)
    except Exception as e:
        logger.warning(f"Intent detection failed: {e}")
        intent = "unknown"

    try:
        await processing_msg.delete()
    except Exception:
        pass

    # Маршрутизация по intent
    if intent == "task":
        logger.info(f"Free input → task for {message.from_user.id}")
        from lyudmila_bot.handlers.task_creation import process_task_description
        await process_task_description(
            message, state,
            auth_service, lyuda_ai, user_cache, supabase, context_service,
        )

    elif intent == "meeting":
        logger.info(f"Free input → meeting for {message.from_user.id}")
        from lyudmila_bot.handlers.meeting_creation import process_meeting_description
        await process_meeting_description(
            message, state,
            auth_service, lyuda_ai, user_cache, supabase,
        )

    else:
        logger.info(f"Free input → unknown for {message.from_user.id}")
        await message.answer(
            "Я могу помочь с двумя вещами:\n\n"
            "📋 <b>Поставить задачу</b> — опишите что нужно сделать, кому и к какому сроку\n"
            "📅 <b>Создать встречу</b> — опишите тему, участников и время\n\n"
            "Пришлите описание задачи или встречи текстом — "
            "либо нажмите кнопку ниже:",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard(),
        )
