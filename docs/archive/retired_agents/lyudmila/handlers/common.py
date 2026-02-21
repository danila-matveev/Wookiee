"""
Common UI utilities for Lyudmila Bot
Back buttons, menu buttons, error handling — available on EVERY screen
"""
import logging
from typing import Optional, Union
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

logger = logging.getLogger(__name__)


def back_button(callback_data: str = "go_back") -> InlineKeyboardButton:
    """Кнопка «Назад» — есть ВСЕГДА"""
    return InlineKeyboardButton(text="← Назад", callback_data=callback_data)


def menu_button() -> InlineKeyboardButton:
    """Кнопка «В меню» — есть ВСЕГДА"""
    return InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")


def build_keyboard(
    *rows: list,
    back_to: str = "main_menu",
) -> InlineKeyboardMarkup:
    """
    Строит клавиатуру с обязательной кнопкой навигации внизу.

    Args:
        *rows: Списки кнопок (каждый список — строка клавиатуры)
        back_to: callback_data для кнопки навигации
    """
    keyboard = [list(row) for row in rows]
    if back_to == "main_menu":
        keyboard.append([menu_button()])
    else:
        keyboard.append([back_button(back_to)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def menu_only_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура только с кнопкой «В меню»"""
    return InlineKeyboardMarkup(inline_keyboard=[[menu_button()]])


async def send_error_message(
    target: Union[Message, CallbackQuery],
    text: str = "Произошла ошибка. Попробуйте ещё раз.",
) -> None:
    """
    Отправляет сообщение об ошибке с кнопкой «В меню».
    Работает и с Message, и с CallbackQuery.
    """
    keyboard = menu_only_keyboard()
    error_text = f"⚠️ {text}"

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(
                error_text, parse_mode="HTML", reply_markup=keyboard
            )
        except Exception:
            await target.message.answer(
                error_text, parse_mode="HTML", reply_markup=keyboard
            )
        try:
            await target.answer()
        except Exception:
            pass
    else:
        await target.answer(error_text, parse_mode="HTML", reply_markup=keyboard)


async def safe_callback_answer(callback: CallbackQuery) -> None:
    """Безопасно ответить на callback (не падает если уже отвечено)"""
    try:
        await callback.answer()
    except Exception:
        pass
