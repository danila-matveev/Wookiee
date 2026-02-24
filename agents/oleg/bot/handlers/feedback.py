"""
Feedback handler — /feedback command and reply-to-report feedback.

Routes feedback through Quality Agent via orchestrator.
"""
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

router = Router()


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()


@router.message(Command("feedback"))
async def cmd_feedback(message: Message, state: FSMContext):
    """Start feedback flow."""
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await message.answer(
        "📝 <b>Обратная связь</b>\n\n"
        "Напишите замечание или предложение по последнему отчёту.\n"
        "Quality Agent проверит ваш feedback через данные и обновит правила.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu_feedback")
async def callback_feedback(callback: CallbackQuery, state: FSMContext):
    """Start feedback from menu."""
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await callback.message.edit_text(
        "📝 <b>Обратная связь</b>\n\n"
        "Напишите замечание или предложение по отчёту.\n"
        "Quality Agent проверит через данные и обновит правила при необходимости.",
        parse_mode="HTML",
    )


@router.message(FeedbackStates.waiting_for_feedback)
async def process_feedback(message: Message, state: FSMContext, orchestrator=None):
    """Process feedback text through Quality Agent."""
    await state.clear()
    feedback_text = message.text.strip()

    if not feedback_text:
        await message.answer("Пустое сообщение. Попробуйте ещё раз.")
        return

    if not orchestrator:
        await message.answer("❌ Оркестратор не настроен.")
        return

    await message.answer("🔄 Обрабатываю feedback через Quality Agent...")

    try:
        result = await orchestrator.run_chain(
            task=f"Обработка feedback: {feedback_text}",
            task_type="feedback",
        )

        from agents.oleg.bot.formatter import (
            split_html_message, format_cost_footer,
        )
        response = result.summary
        response += format_cost_footer(
            result.total_cost, result.total_steps, result.total_duration_ms,
        )

        for chunk in split_html_message(response):
            await message.answer(chunk, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Feedback processing error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при обработке feedback: {e}")
