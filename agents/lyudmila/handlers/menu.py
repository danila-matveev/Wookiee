"""
Главное меню Людмилы — постоянное навигационное меню
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents.lyudmila.handlers.common import menu_only_keyboard, send_error_message

logger = logging.getLogger(__name__)

router = Router()


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню Людмилы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Поставить задачу", callback_data="action_task")],
        [InlineKeyboardButton(text="📅 Создать встречу", callback_data="action_meeting")],
        [InlineKeyboardButton(text="📊 Мой дайджест", callback_data="action_digest")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="action_settings")],
    ])


async def show_main_menu(target, text: str = None) -> None:
    """
    Показать главное меню.
    Работает и с Message, и с CallbackQuery.
    """
    menu_text = text or (
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:"
    )
    keyboard = create_main_menu_keyboard()

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(
                menu_text, parse_mode="HTML", reply_markup=keyboard,
            )
        except Exception:
            await target.message.answer(
                menu_text, parse_mode="HTML", reply_markup=keyboard,
            )
        try:
            await target.answer()
        except Exception:
            pass
    else:
        await target.answer(
            menu_text, parse_mode="HTML", reply_markup=keyboard,
        )


# ─── Команда /menu — возврат из любого состояния ──────────────

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, auth_service):
    """Сброс FSM + главное меню"""
    if not auth_service.is_authenticated(message.from_user.id):
        await message.answer(
            "Вы не авторизованы. Используйте /start",
        )
        return
    await state.clear()
    await show_main_menu(message)


# ─── Callback: main_menu ─────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext, auth_service):
    """Возврат в главное меню по кнопке"""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return
    await state.clear()
    await show_main_menu(callback)


# ─── Настройки ───────────────────────────────────────────────

@router.callback_query(F.data == "action_settings")
async def callback_settings(callback: CallbackQuery, auth_service, db_service):
    """Показать настройки"""
    user = auth_service.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🕐 Таймзон: {user.timezone}",
            callback_data="settings_timezone",
        )],
        [InlineKeyboardButton(
            text=f"⏰ Дайджест: {user.digest_time} {'✅' if user.digest_enabled else '❌'}",
            callback_data="settings_digest",
        )],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
    ])

    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"👤 {user.full_name}\n"
        f"📧 {user.email}\n"
        f"🕐 Таймзон: {user.timezone}\n"
        f"⏰ Дайджест: {user.digest_time} {'(вкл)' if user.digest_enabled else '(выкл)'}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "settings_timezone")
async def callback_timezone(callback: CallbackQuery, auth_service):
    """Выбор таймзона"""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Москва (МСК)", callback_data="tz_Europe/Moscow")],
        [InlineKeyboardButton(text="🇷🇺 Калининград", callback_data="tz_Europe/Kaliningrad")],
        [InlineKeyboardButton(text="🇷🇺 Екатеринбург", callback_data="tz_Asia/Yekaterinburg")],
        [InlineKeyboardButton(text="🇷🇺 Новосибирск", callback_data="tz_Asia/Novosibirsk")],
        [InlineKeyboardButton(text="← Назад", callback_data="action_settings")],
    ])

    await callback.message.edit_text(
        "🕐 <b>Выберите таймзон:</b>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz_"))
async def callback_set_timezone(callback: CallbackQuery, auth_service, db_service):
    """Установить таймзон"""
    tz = callback.data.removeprefix("tz_")
    user = auth_service.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    user.timezone = tz
    db_service.update_user_settings(callback.from_user.id, timezone=tz)

    await callback.answer(f"Таймзон изменён: {tz}", show_alert=True)
    # Показать настройки
    await callback_settings(callback, auth_service, db_service)


@router.callback_query(F.data == "settings_digest")
async def callback_toggle_digest(callback: CallbackQuery, auth_service, db_service):
    """Переключить дайджест вкл/выкл"""
    user = auth_service.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    new_state = not user.digest_enabled
    user.digest_enabled = new_state
    db_service.update_user_settings(callback.from_user.id, digest_enabled=new_state)

    status = "включён" if new_state else "выключен"
    await callback.answer(f"Дайджест {status}", show_alert=True)
    await callback_settings(callback, auth_service, db_service)


# ─── Обработка голосовых и нетекстовых сообщений ─────────────

@router.message(F.voice)
async def handle_voice(message: Message, auth_service):
    """Голосовые — пока не поддерживаем"""
    await message.answer(
        "Я пока работаю только с текстом. "
        "Напишите, пожалуйста, текстом — и я помогу!",
        reply_markup=menu_only_keyboard(),
    )


@router.message(F.sticker | F.photo | F.document | F.video | F.animation)
async def handle_non_text(message: Message, auth_service):
    """Стикеры, фото, документы"""
    await message.answer(
        "Я понимаю только текст. Опишите задачу словами!",
        reply_markup=menu_only_keyboard(),
    )
