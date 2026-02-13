"""
Email-авторизация для Людмилы
/start → email → подтверждение → главное меню
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from lyudmila_bot.handlers.common import menu_only_keyboard, send_error_message

logger = logging.getLogger(__name__)

router = Router()


class AuthStates(StatesGroup):
    waiting_for_email = State()
    confirming_identity = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, auth_service):
    """Обработка /start — приветствие Людмилы"""
    user_id = message.from_user.id

    # Если уже авторизован
    if auth_service.is_authenticated(user_id):
        from lyudmila_bot.handlers.menu import show_main_menu
        await show_main_menu(message)
        return

    welcome = (
        "Привет! Я — <b>Людмила</b>, ваш офис-менеджер и бизнес-ассистент.\n\n"
        "Моя задача — экономить ваше время и помогать команде работать эффективнее.\n\n"
        "<b>Что я умею:</b>\n"
        "• Утренний дайджест — встречи, задачи, просрочки\n"
        "• Поставить задачу — помогу сформулировать правильно\n"
        "• Создать встречу — с повесткой и подготовкой\n"
        "• Сводка по задачам — что в работе, что горит\n\n"
        "Я работаю только с текстом (голосовые пока не понимаю).\n\n"
        "📧 <b>Для начала отправьте ваш рабочий email:</b>"
    )

    await message.answer(welcome, parse_mode="HTML")
    await state.set_state(AuthStates.waiting_for_email)


@router.message(AuthStates.waiting_for_email)
async def process_email(message: Message, state: FSMContext, auth_service):
    """Обработка email для авторизации"""
    email = message.text.strip().lower()

    # Простая валидация
    if "@" not in email or "." not in email:
        await message.answer(
            "⚠️ Это не похоже на email. Отправьте рабочую почту, например:\n"
            "<code>ivanov@wookiee.ru</code>",
            parse_mode="HTML",
        )
        return

    try:
        bitrix_user = await auth_service.find_user_by_email(email)
    except Exception as e:
        logger.exception(f"Email lookup failed: {e}")
        await send_error_message(message, "Bitrix24 сейчас недоступен. Попробуйте через пару минут.")
        return

    if not bitrix_user:
        await message.answer(
            "❌ Email не найден в системе.\n\n"
            "Используйте рабочую почту, привязанную к Bitrix24.\n"
            "Если проблема сохраняется — обратитесь к администратору.\n\n"
            "📧 Попробуйте другой email:",
        )
        return

    # Проверяем активность
    if not bitrix_user.get('ACTIVE', True):
        await message.answer(
            "🚫 Ваш аккаунт деактивирован в Bitrix24.\n"
            "Обратитесь к администратору."
        )
        await state.clear()
        return

    first_name = bitrix_user.get('NAME', '')
    last_name = bitrix_user.get('LAST_NAME', '')
    position = bitrix_user.get('WORK_POSITION', '')

    # Сохраняем данные в FSM для подтверждения
    await state.update_data(
        bitrix_user=bitrix_user,
        email=email,
    )

    position_text = f"\nДолжность: {position}" if position else ""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, это я", callback_data="auth_confirm")],
        [InlineKeyboardButton(text="❌ Нет, другой email", callback_data="auth_retry")],
    ])

    await message.answer(
        f"Вы — <b>{first_name} {last_name}</b>?{position_text}\n\n"
        f"Email: {email}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await state.set_state(AuthStates.confirming_identity)


@router.callback_query(AuthStates.confirming_identity, F.data == "auth_confirm")
async def confirm_identity(callback: CallbackQuery, state: FSMContext, auth_service):
    """Подтверждение личности — авторизация"""
    data = await state.get_data()
    bitrix_user = data.get('bitrix_user')

    if not bitrix_user:
        await send_error_message(callback, "Сессия истекла. Начните заново: /start")
        await state.clear()
        return

    try:
        bot_user = await auth_service.authenticate(
            telegram_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            bitrix_user=bitrix_user,
        )
    except Exception as e:
        logger.exception(f"Auth failed: {e}")
        await send_error_message(callback, "Ошибка авторизации. Попробуйте /start")
        await state.clear()
        return

    await state.clear()

    # Показываем главное меню
    from lyudmila_bot.handlers.menu import create_main_menu_keyboard
    await callback.message.edit_text(
        f"✅ Добро пожаловать, <b>{bot_user.first_name}</b>!\n\n"
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(AuthStates.confirming_identity, F.data == "auth_retry")
async def retry_email(callback: CallbackQuery, state: FSMContext):
    """Повторный ввод email"""
    await callback.message.edit_text(
        "📧 Отправьте ваш рабочий email:",
    )
    await state.set_state(AuthStates.waiting_for_email)
    await callback.answer()


@router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext, auth_service):
    """Выход из системы"""
    user_id = message.from_user.id

    if auth_service.is_authenticated(user_id):
        auth_service.logout(user_id)
        await state.clear()
        await message.answer(
            "👋 Вы вышли из системы.\n\n"
            "Для повторного входа используйте /start",
        )
    else:
        await message.answer("Вы не авторизованы. Используйте /start")
