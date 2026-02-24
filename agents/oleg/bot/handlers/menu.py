"""
Menu handler — main navigation for Oleg v2 bot.
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

router = Router()


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Шаблонные отчёты", callback_data="menu_reports")],
            [InlineKeyboardButton(text="🤔 Кастомный запрос", callback_data="menu_custom_query")],
            [InlineKeyboardButton(text="💰 Ценовой анализ", callback_data="menu_price_analysis")],
            [InlineKeyboardButton(text="📝 Обратная связь", callback_data="menu_feedback")],
            [InlineKeyboardButton(text="🔍 Здоровье системы", callback_data="menu_health")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")],
        ]
    )


def create_reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Reports sub-menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Дневной отчёт", callback_data="report_daily")],
            [InlineKeyboardButton(text="📆 Недельный отчёт", callback_data="report_weekly")],
            [InlineKeyboardButton(text="🗓 За период", callback_data="report_period")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")],
        ]
    )


@router.callback_query(F.data == "menu_main")
async def callback_main_menu(callback: CallbackQuery):
    """Show main menu."""
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu_reports")
async def callback_reports_menu(callback: CallbackQuery):
    """Show reports sub-menu."""
    await callback.message.edit_text(
        "📊 <b>Шаблонные отчёты</b>\n\nВыберите тип:",
        parse_mode="HTML",
        reply_markup=create_reports_menu_keyboard(),
    )


@router.callback_query(F.data == "menu_help")
async def callback_help(callback: CallbackQuery):
    """Show help."""
    await callback.message.edit_text(
        "<b>Олег v2 — AI-аналитик Wookiee</b>\n\n"
        "📊 <b>Отчёты</b> — дневные, недельные, за период\n"
        "🤔 <b>Запрос</b> — любой аналитический вопрос\n"
        "💰 <b>Ценовой анализ</b> — рекомендации по ценам\n"
        "📝 <b>Обратная связь</b> — улучшение качества\n"
        "🔍 <b>Здоровье</b> — состояние системы\n\n"
        "Или просто напишите вопрос текстом.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")],
            ]
        ),
    )
