"""
Main Menu Navigation Handler for Wookiee Bot
Provides intuitive navigation between bot features
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

from agents.oleg.handlers.auth import check_auth

logger = logging.getLogger(__name__)

# Create router for menu handlers
router = Router()


def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Create main menu keyboard with all bot features

    Returns:
        Inline keyboard with main menu options
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Шаблонные отчеты", callback_data="menu_reports")
            ],
            [
                InlineKeyboardButton(text="🤔 Кастомный запрос", callback_data="menu_custom_query")
            ],
            [
                InlineKeyboardButton(text="💰 Ценовой анализ", callback_data="menu_price_analysis")
            ],
            [
                InlineKeyboardButton(text="📚 История отчетов", callback_data="menu_history")
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
            ],
            [
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")
            ]
        ]
    )
    return keyboard


def create_reports_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for template reports menu

    Returns:
        Inline keyboard with report options
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Ежедневная сводка", callback_data="report_daily")
            ],
            [
                InlineKeyboardButton(text="📆 Еженедельная сводка", callback_data="report_weekly")
            ],
            [
                InlineKeyboardButton(text="📊 Периодическая сводка", callback_data="report_period")
            ],
            [
                InlineKeyboardButton(text="📈 ABC-анализ", callback_data="report_abc")
            ],
            [
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")
            ]
        ]
    )
    return keyboard


def create_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard with back to main menu button

    Returns:
        Inline keyboard with back button
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")
            ]
        ]
    )
    return keyboard


@router.message(Command("menu"))
async def cmd_menu(message: Message, auth_service):
    """
    Handle /menu command - show main menu
    """
    if not await check_auth(message, auth_service):
        await message.answer(
            "❌ Вы не авторизованы.\n\n"
            "Используйте /start для входа."
        )
        return

    await message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )


@router.callback_query(F.data == "menu_main")
async def callback_main_menu(callback: CallbackQuery, auth_service):
    """
    Handle main menu callback - show main menu
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_reports")
async def callback_reports_menu(callback: CallbackQuery, auth_service):
    """
    Handle reports menu callback
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "📊 <b>Шаблонные отчеты</b>\n\n"
        "Выберите тип отчета:\n\n"
        "• <b>Ежедневная сводка</b> — анализ за вчера (ИИ Рома)\n"
        "• <b>Еженедельная сводка</b> — анализ за прошлую неделю\n"
        "• <b>Периодическая сводка</b> — за произвольный период\n"
        "• <b>ABC-анализ</b> — классификация товаров",
        parse_mode="HTML",
        reply_markup=create_reports_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_custom_query")
async def callback_custom_query_menu(callback: CallbackQuery, state: FSMContext, auth_service):
    """
    Handle custom query menu callback
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    # Import QueryStates here to avoid circular dependency
    from agents.oleg.handlers.custom_queries import QueryStates

    await callback.message.edit_text(
        "🤔 <b>Кастомный запрос</b>\n\n"
        "Напишите запрос текстом, и бот сформирует отчёт.\n\n"
        "<b>Примеры:</b>\n"
        "• Сводка за вчера\n"
        "• Отчёт за прошлую неделю\n"
        "• Показатели за месяц\n\n"
        "✍️ Введите запрос:",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )

    # Set state to wait for query
    await state.set_state(QueryStates.waiting_for_query)

    await callback.answer()


@router.callback_query(F.data == "menu_history")
async def callback_history_menu(callback: CallbackQuery, auth_service):
    """
    Handle history menu callback
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "📚 <b>История отчетов</b>\n\n"
        "Здесь будут отображаться все ваши отчеты.\n\n"
        "🔍 Вы можете искать отчеты по:\n"
        "• Дате создания\n"
        "• Типу отчета\n"
        "• Ключевым словам\n\n"
        "⚠️ <i>Функция в разработке</i>",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_settings")
async def callback_settings_menu(callback: CallbackQuery, auth_service):
    """
    Handle settings menu callback
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "🔔 <b>Автоматические отчеты:</b>\n"
        "• Ежедневная рассылка: ✅ Включена (10:05 МСК)\n\n"
        "🔐 <b>Безопасность:</b>\n"
        "• Выйти из системы: /logout\n\n"
        "⚠️ <i>Дополнительные настройки в разработке</i>",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def callback_help_menu(callback: CallbackQuery, auth_service):
    """
    Handle help menu callback
    """
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("❌ Вы не авторизованы", show_alert=True)
        return

    help_text = (
        "ℹ️ <b>Помощь по использованию бота</b>\n\n"
        "<b>📋 Основные команды:</b>\n"
        "• /start - Вход в систему\n"
        "• /menu - Главное меню\n"
        "• /logout - Выход из системы\n\n"
        "<b>📊 Шаблонные отчеты:</b>\n"
        "Готовые отчеты с автоматическим расчетом метрик и гипотез.\n\n"
        "<b>🤔 Кастомные запросы:</b>\n"
        "AI-агент поможет сформулировать вопрос и получить нужные данные.\n\n"
        "<b>📚 История отчетов:</b>\n"
        "Все отчеты сохраняются и доступны для поиска.\n\n"
        "<b>⚠️ Обратная связь:</b>\n"
        "Если нашли ошибку в отчете, нажмите кнопку 'Сообщить об ошибке'.\n\n"
        "<b>🔐 Безопасность:</b>\n"
        "Все данные защищены, доступ только по паролю."
    )

    await callback.message.edit_text(
        help_text,
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()


# ─── Price Analysis Menu ─────────────────────────────────────

def create_price_analysis_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for price analysis submenu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Ценовой обзор", callback_data="price_review")
            ],
            [
                InlineKeyboardButton(text="🏷 Анализ акций МП", callback_data="price_promotions")
            ],
            [
                InlineKeyboardButton(text="🔮 Сценарий цены", callback_data="price_scenario")
            ],
            [
                InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu_main")
            ]
        ]
    )


@router.callback_query(F.data == "menu_price_analysis")
async def callback_price_analysis_menu(callback: CallbackQuery, auth_service):
    """Handle price analysis menu callback."""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 <b>Ценовой анализ</b>\n\n"
        "Выберите тип анализа:\n\n"
        "• <b>Ценовой обзор</b> — эластичность, тренды, рекомендации по ценам\n"
        "• <b>Анализ акций МП</b> — сканирование акций WB/OZON, расчёт эффекта\n"
        "• <b>Сценарий цены</b> — моделирование \"что если цену изменить на X%\"",
        parse_mode="HTML",
        reply_markup=create_price_analysis_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "price_review")
async def callback_price_review(callback: CallbackQuery, state: FSMContext, auth_service):
    """Trigger price review via custom query flow."""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    from agents.oleg.handlers.custom_queries import QueryStates
    await state.set_state(QueryStates.waiting_for_query)
    await state.update_data(prefilled_query="Ценовой обзор за последнюю неделю: эластичность, рекомендации по ценам, тренды")

    await callback.message.edit_text(
        "📈 <b>Ценовой обзор</b>\n\n"
        "Запрос сформирован: <i>Ценовой обзор за последнюю неделю</i>\n\n"
        "Отправьте любое сообщение для запуска или напишите свой запрос.",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "price_promotions")
async def callback_price_promotions(callback: CallbackQuery, state: FSMContext, auth_service):
    """Trigger promotion analysis via custom query flow."""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    from agents.oleg.handlers.custom_queries import QueryStates
    await state.set_state(QueryStates.waiting_for_query)
    await state.update_data(prefilled_query="Проанализируй текущие акции на WB и OZON, рекомендуй участие")

    await callback.message.edit_text(
        "🏷 <b>Анализ акций МП</b>\n\n"
        "Запрос сформирован: <i>Анализ текущих акций WB и OZON</i>\n\n"
        "Отправьте любое сообщение для запуска или напишите свой запрос.",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "price_scenario")
async def callback_price_scenario(callback: CallbackQuery, state: FSMContext, auth_service):
    """Trigger price scenario via custom query flow."""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    from agents.oleg.handlers.custom_queries import QueryStates
    await state.set_state(QueryStates.waiting_for_query)

    await callback.message.edit_text(
        "🔮 <b>Сценарий цены</b>\n\n"
        "Напишите запрос в формате:\n\n"
        "• <i>Что будет если поднять цену Wendy на WB на 10%?</i>\n"
        "• <i>Смоделируй снижение цены Ruby на 5% на OZON</i>\n"
        "• <i>Что было бы если мы подняли цену на 7% на прошлой неделе?</i>\n\n"
        "✍️ Введите запрос:",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )
    await callback.answer()
