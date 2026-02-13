"""
Authentication Handler for Wookiee Bot
Manages user login and authorization flow
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

# Create router for auth handlers
router = Router()


class AuthStates(StatesGroup):
    """FSM states for authentication flow"""
    waiting_for_password = State()


async def check_auth(message: Message, auth_service) -> bool:
    """
    Check if user is authenticated

    Args:
        message: Telegram message
        auth_service: AuthService instance

    Returns:
        True if authenticated, False otherwise
    """
    return auth_service.is_authenticated(message.from_user.id)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, auth_service):
    """
    Handle /start command - entry point to bot

    Shows welcome message and requests authentication if needed
    """
    user_id = message.from_user.id

    # Check if already authenticated
    if auth_service.is_authenticated(user_id):
        await message.answer(
            "🔓 Вы уже авторизованы!\n\n"
            "Используйте /menu для доступа к функциям бота."
        )
        return

    # Show welcome message and request password
    welcome_text = (
        "👋 Добро пожаловать в <b>Wookiee Analytics Bot</b>!\n\n"
        "🤖 <b>Что я умею:</b>\n"
        "• 📊 Ежедневные, еженедельные, месячные отчеты\n"
        "• 📈 ABC-анализ товаров с рекомендациями\n"
        "• 🤔 Кастомные запросы на естественном языке\n"
        "• 📚 История всех отчетов с поиском\n"
        "• ⏰ Автоматическая ежедневная рассылка после 10:00 МСК\n\n"
        "🔐 <b>Для начала работы введите пароль:</b>"
    )

    await message.answer(welcome_text, parse_mode="HTML")
    await state.set_state(AuthStates.waiting_for_password)


@router.message(AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext, auth_service):
    """
    Process password input from user
    """
    user_id = message.from_user.id
    password = message.text

    # Delete user's password message for security
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Could not delete password message: {e}")

    # Verify password
    if auth_service.authenticate_user(user_id, password):
        # Import menu keyboard to show main menu
        from oleg_bot.handlers.menu import create_main_menu_keyboard

        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            "🏠 <b>Главное меню</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        await state.clear()
    else:
        await message.answer(
            "❌ <b>Неверный пароль!</b>\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
            parse_mode="HTML"
        )


@router.message(Command("logout"))
async def cmd_logout(message: Message, auth_service):
    """
    Handle /logout command - log out current user
    """
    user_id = message.from_user.id

    if auth_service.is_authenticated(user_id):
        auth_service.logout_user(user_id)
        await message.answer(
            "👋 Вы вышли из системы.\n\n"
            "Для повторного входа используйте /start"
        )
    else:
        await message.answer("❌ Вы не авторизованы.")


def create_auth_required_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for unauthorized users

    Returns:
        Inline keyboard with login button
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Войти", callback_data="auth_login")]
        ]
    )
    return keyboard


@router.callback_query(F.data == "auth_login")
async def callback_auth_login(callback: CallbackQuery, state: FSMContext):
    """
    Handle login button callback
    """
    await callback.message.edit_text(
        "🔐 <b>Введите пароль для доступа к боту:</b>",
        parse_mode="HTML"
    )
    await state.set_state(AuthStates.waiting_for_password)
    await callback.answer()
