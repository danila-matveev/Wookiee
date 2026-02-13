"""
Scheduled Reports Handler
Reports: daily, weekly, period — all via Oleg agent (tool-use).
Feedback FSM for collecting user feedback on reports.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from datetime import datetime, timedelta
import logging

from oleg_bot.services.report_formatter import ReportFormatter

logger = logging.getLogger(__name__)

router = Router()


class ReportStates(StatesGroup):
    selecting_start_date = State()
    selecting_end_date = State()


class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()


def _back_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with back to reports and main menu buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Ещё отчёт", callback_data="menu_reports")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")],
        ]
    )


def _period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗓 Последние 7 дней", callback_data="period_last_7")],
            [InlineKeyboardButton(text="📆 Последние 30 дней", callback_data="period_last_30")],
            [InlineKeyboardButton(text="📅 Выбрать даты", callback_data="period_manual")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_reports")],
        ]
    )


# ─────────────────────────────────────────────────────────
# Daily report (Oleg agent)
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "report_daily")
async def callback_daily_report(
    callback: CallbackQuery,
    oleg_agent,
    report_storage,
    notion_service,
    auth_service,
):
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text("⏳ Олег готовит ежедневную сводку...")
    await callback.answer()

    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")

    result = await oleg_agent.analyze(
        user_query="Ежедневная аналитическая сводка",
        params={
            "start_date": date_str,
            "end_date": date_str,
            "channels": ["wb", "ozon"],
            "report_type": "daily",
        },
    )

    if not result.get("brief_summary") or not result.get("success", True):
        await callback.message.edit_text(
            "❌ Не удалось сгенерировать отчёт. Попробуйте позже.",
            reply_markup=_back_keyboard(),
        )
        return

    # Save
    try:
        report_storage.save_report(
            user_id=callback.from_user.id,
            report_type="daily",
            title=f"Ежедневная сводка за {yesterday.strftime('%d.%m.%Y')}",
            content=result.get("detailed_report", ""),
            start_date=yesterday,
            end_date=yesterday,
        )
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    # Notion sync
    notion_url = await notion_service.sync_report(
        start_date=date_str,
        end_date=date_str,
        report_md=result.get("detailed_report", ""),
    )

    # Format and send
    cost_info = _build_cost_info(result)
    html_text = ReportFormatter.format_for_telegram(
        brief_summary=result["brief_summary"],
        notion_url=notion_url,
        cost_info=cost_info,
    )
    keyboard = ReportFormatter.create_report_keyboard("daily")
    await _send_html_report(callback, html_text, keyboard)


# ─────────────────────────────────────────────────────────
# Weekly report (Oleg agent)
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "report_weekly")
async def callback_weekly_report(
    callback: CallbackQuery,
    oleg_agent,
    report_storage,
    notion_service,
    auth_service,
):
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text("⏳ Олег готовит еженедельную сводку...")
    await callback.answer()

    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=6)
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    result = await oleg_agent.analyze(
        user_query="Еженедельная аналитическая сводка",
        params={
            "start_date": s,
            "end_date": e,
            "channels": ["wb", "ozon"],
            "report_type": "weekly",
        },
    )

    if not result.get("brief_summary") or not result.get("success", True):
        await callback.message.edit_text(
            "❌ Не удалось сгенерировать отчёт. Попробуйте позже.",
            reply_markup=_back_keyboard(),
        )
        return

    try:
        report_storage.save_report(
            user_id=callback.from_user.id,
            report_type="weekly",
            title=f"Еженедельная сводка {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}",
            content=result.get("detailed_report", ""),
        )
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    notion_url = await notion_service.sync_report(
        start_date=s, end_date=e,
        report_md=result.get("detailed_report", ""),
    )

    cost_info = _build_cost_info(result)
    html_text = ReportFormatter.format_for_telegram(
        brief_summary=result["brief_summary"],
        notion_url=notion_url,
        cost_info=cost_info,
    )
    keyboard = ReportFormatter.create_report_keyboard("weekly")
    await _send_html_report(callback, html_text, keyboard)


# ─────────────────────────────────────────────────────────
# Period report (Oleg agent)
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "report_period")
async def callback_period_report(callback: CallbackQuery):
    await callback.message.edit_text(
        "📆 <b>Периодическая сводка</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=_period_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"period_last_7", "period_last_30"}))
async def callback_quick_period(
    callback: CallbackQuery,
    oleg_agent,
    report_storage,
    notion_service,
    auth_service,
):
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    days = 7 if callback.data == "period_last_7" else 30
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    s, e = start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    await callback.message.edit_text(f"⏳ Олег готовит отчёт за {days} дней...")
    await callback.answer()

    result = await oleg_agent.analyze(
        user_query=f"Аналитическая сводка за {days} дней",
        params={
            "start_date": s,
            "end_date": e,
            "channels": ["wb", "ozon"],
            "report_type": "period",
        },
    )

    if not result.get("brief_summary") or not result.get("success", True):
        await callback.message.edit_text(
            "❌ Не удалось сгенерировать отчёт. Попробуйте позже.",
            reply_markup=_back_keyboard(),
        )
        return

    try:
        report_storage.save_report(
            user_id=callback.from_user.id,
            report_type="period",
            title=f"Сводка {start_date.strftime('%d.%m')}–{end_date.strftime('%d.%m.%Y')}",
            content=result.get("detailed_report", ""),
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    notion_url = await notion_service.sync_report(
        start_date=s, end_date=e,
        report_md=result.get("detailed_report", ""),
    )

    cost_info = _build_cost_info(result)
    html_text = ReportFormatter.format_for_telegram(
        brief_summary=result["brief_summary"],
        notion_url=notion_url,
        cost_info=cost_info,
    )
    keyboard = ReportFormatter.create_report_keyboard("period")
    await _send_html_report(callback, html_text, keyboard)


# ─────────────────────────────────────────────────────────
# Manual calendar selection
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "period_manual")
async def callback_manual_period(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📅 Выберите начальную дату:",
        reply_markup=await SimpleCalendar().start_calendar(),
    )
    await state.set_state(ReportStates.selecting_start_date)
    await callback.answer()


@router.callback_query(SimpleCalendarCallback.filter())
async def callback_calendar(
    callback: CallbackQuery,
    callback_data: SimpleCalendarCallback,
    state: FSMContext,
    oleg_agent,
    report_storage,
    notion_service,
):
    calendar = SimpleCalendar()
    selected, date = await calendar.process_selection(callback, callback_data)

    if not selected:
        await callback.answer()
        return

    current_state = await state.get_state()

    if current_state == ReportStates.selecting_start_date.state:
        await state.update_data(start_date=date)
        await callback.message.edit_text(
            f"✅ Начало: {date.strftime('%d.%m.%Y')}\n\n📅 Выберите конечную дату:",
            reply_markup=await calendar.start_calendar(),
        )
        await state.set_state(ReportStates.selecting_end_date)

    elif current_state == ReportStates.selecting_end_date.state:
        data = await state.get_data()
        start_date = data["start_date"]
        end_date = date
        await state.clear()

        if end_date < start_date:
            await callback.message.edit_text(
                "❌ Конечная дата раньше начальной. Попробуйте снова.",
                reply_markup=_back_keyboard(),
            )
            await callback.answer()
            return

        s, e = start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
        await callback.message.edit_text(
            f"⏳ Олег готовит отчёт за {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}..."
        )

        result = await oleg_agent.analyze(
            user_query=f"Аналитическая сводка за период {s} — {e}",
            params={
                "start_date": s,
                "end_date": e,
                "channels": ["wb", "ozon"],
                "report_type": "period",
            },
        )

        if not result.get("brief_summary"):
            await callback.message.edit_text(
                "❌ Не удалось сгенерировать отчёт. Попробуйте позже.",
                reply_markup=_back_keyboard(),
            )
            await callback.answer()
            return

        try:
            report_storage.save_report(
                user_id=callback.from_user.id,
                report_type="period",
                title=f"Сводка {start_date.strftime('%d.%m')}–{end_date.strftime('%d.%m.%Y')}",
                content=result.get("detailed_report", ""),
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

        notion_url = await notion_service.sync_report(
            start_date=s, end_date=e,
            report_md=result.get("detailed_report", ""),
        )

        cost_info = _build_cost_info(result)
        html_text = ReportFormatter.format_for_telegram(
            brief_summary=result["brief_summary"],
            notion_url=notion_url,
            cost_info=cost_info,
        )
        keyboard = ReportFormatter.create_report_keyboard("period")
        await _send_html_report(callback, html_text, keyboard)

    await callback.answer()


# ─────────────────────────────────────────────────────────
# Feedback
# ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("feedback_start:"))
async def callback_feedback_start(callback: CallbackQuery, state: FSMContext):
    """Start feedback flow — ask user to type their feedback."""
    report_type = callback.data.split(":")[1] if ":" in callback.data else "unknown"
    await state.update_data(feedback_report_type=report_type)
    await state.set_state(FeedbackStates.waiting_for_feedback)

    await callback.message.answer(
        "✍️ <b>Обратная связь</b>\n\n"
        "Напишите текстом, что не так или что улучшить.\n\n"
        "<b>Примеры:</b>\n"
        "• «Сводку сделай короче»\n"
        "• «Всегда показывай ДРР от заказов»\n"
        "• «Маржа OZON считается неправильно — вот формула...»\n\n"
        "Или нажмите «Отмена»:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="feedback_cancel")],
        ]),
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_cancel")
async def callback_feedback_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel feedback."""
    await state.clear()
    await callback.message.edit_text(
        "Обратная связь отменена.",
        reply_markup=_back_keyboard(),
    )
    await callback.answer()


@router.message(FeedbackStates.waiting_for_feedback, F.text)
async def process_feedback_text(
    message: Message,
    state: FSMContext,
    feedback_service=None,
    oleg_agent=None,
):
    """Process user feedback text via FeedbackService + Oleg verification."""
    feedback_text = message.text
    data = await state.get_data()
    report_type = data.get("feedback_report_type", "unknown")
    await state.clear()

    try:
        if feedback_service and oleg_agent:
            result = await feedback_service.process_feedback(
                feedback_text=feedback_text,
                original_report="",
                query_params={"report_type": report_type},
                oleg_agent=oleg_agent,
                user_id=message.from_user.id,
            )

            verdict = result.get("verdict", "accepted")
            user_message = result.get("user_message", "Обратная связь принята.")

            if verdict == "rejected":
                await message.answer(
                    f"🔍 <b>Олег перепроверил данные</b>\n\n{user_message}",
                    parse_mode="HTML",
                    reply_markup=ReportFormatter.create_feedback_keyboard(),
                )
            elif verdict == "partially_accepted":
                await message.answer(
                    f"⚠️ <b>Частично принято</b>\n\n{user_message}",
                    parse_mode="HTML",
                    reply_markup=ReportFormatter.create_feedback_keyboard(),
                )
            else:
                await message.answer(
                    f"✅ <b>Обратная связь принята</b>\n\n{user_message}",
                    parse_mode="HTML",
                    reply_markup=ReportFormatter.create_feedback_keyboard(),
                )
        else:
            await message.answer(
                "✅ <b>Спасибо за обратную связь!</b>\n\n"
                "Будет учтено в следующих отчётах.",
                parse_mode="HTML",
                reply_markup=ReportFormatter.create_feedback_keyboard(),
            )
    except Exception as e:
        logger.error(f"Feedback processing error: {e}")
        await message.answer(
            "✅ Обратная связь принята. Спасибо!",
            reply_markup=ReportFormatter.create_feedback_keyboard(),
        )


# Legacy feedback handler (for old ok/error buttons)
@router.callback_query(F.data.in_({"feedback_ok", "feedback_error"}))
async def callback_feedback_legacy(callback: CallbackQuery):
    feedback_type = callback.data.replace("feedback_", "")
    if feedback_type == "ok":
        await callback.answer("Спасибо за обратную связь!", show_alert=True)
    elif feedback_type == "error":
        await callback.message.answer(
            "⚠️ Опишите ошибку текстом — Олег перепроверит данные.",
        )
        await callback.answer()


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _build_cost_info(result: dict) -> str:
    """Build cost info string from analysis result."""
    parts = []
    if result.get("cost_usd"):
        parts.append(f"~${result['cost_usd']:.4f}")
    if result.get("iterations"):
        parts.append(f"{result['iterations']} шагов")
    if result.get("duration_ms"):
        parts.append(f"{result['duration_ms'] / 1000:.1f}с")
    return " | ".join(parts) if parts else ""


async def _send_html_report(
    callback: CallbackQuery,
    html_text: str,
    keyboard: InlineKeyboardMarkup,
):
    """Send HTML-formatted report, split into chunks if needed."""
    MAX_LEN = 4000

    if len(html_text) <= MAX_LEN:
        await callback.message.edit_text(
            html_text, parse_mode="HTML", reply_markup=keyboard,
        )
        return

    chunks = [html_text[i:i + MAX_LEN] for i in range(0, len(html_text), MAX_LEN)]

    await callback.message.edit_text(chunks[0], parse_mode="HTML")

    for chunk in chunks[1:-1]:
        await callback.message.answer(chunk, parse_mode="HTML")

    await callback.message.answer(
        chunks[-1], parse_mode="HTML", reply_markup=keyboard,
    )
