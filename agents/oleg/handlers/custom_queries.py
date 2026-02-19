"""
Custom Queries Handler
LLM-assisted natural language queries with Oleg agent analysis.

Flow:
1. User types a question
2. Basic parser extracts dates, channels, models
3. Bot shows: "Я понял вашу задачу: ..." + directions + data highlights → [Подтвердить] [Уточнить] [Отмена]
4. User confirms → Oleg agent runs ReAct loop with tool-use
5. Sends brief summary + reasoning steps + cost
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import logging
import re
import calendar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from agents.oleg.services.report_storage import ReportStorage
from agents.oleg.services.report_formatter import ReportFormatter
from agents.oleg.services.time_utils import get_today_msk, get_now_msk

logger = logging.getLogger(__name__)

# Create router
router = Router()

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

# --- Constants for parsing ---

_MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
    "мая": 5, "май": 5, "мае": 5, "июн": 6, "июл": 7,
    "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}

_CHANNELS_MAP = {
    r"озон|ozon": "ozon",
    r"вайлдберри|wildberries|вб\b|wb\b": "wb",
}

_KNOWN_MODELS = [
    "wendy", "ruby", "set_vuki", "joy", "vuki", "moon", "audrey", "bella",
]


class QueryStates(StatesGroup):
    """FSM states for custom queries"""
    waiting_for_query = State()
    confirming_parameters = State()
    waiting_for_comment = State()
    waiting_for_clarification = State()  # LLM asked smart questions, waiting for answer


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for query confirmation with proposed query."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Запустить", callback_data="custom_confirm"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="custom_comment"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")],
        ]
    )


# =====================================================================
# Data-aware highlights
# =====================================================================

def _get_data_highlights(params: dict) -> str:
    """Load data_context.json and extract anomaly highlights."""
    try:
        context = _load_data_context(params)
        if not context:
            return ""

        highlights = []

        for channel_key, channel_name in [("wb", "WB"), ("ozon", "OZON")]:
            ch = context.get(channel_key, {})
            changes = ch.get("changes", {})

            margin_pct = changes.get("margin_pct")
            if margin_pct is not None:
                if margin_pct < -20:
                    highlights.append(f"⚠️ {channel_name}: маржа упала на {abs(margin_pct):.0f}%")
                elif margin_pct > 30:
                    highlights.append(f"📈 {channel_name}: маржа выросла на {margin_pct:.0f}%")

            drr_pct = changes.get("drr_pct") or changes.get("adv_total_pct")
            if drr_pct is not None and drr_pct > 20:
                highlights.append(f"⚠️ {channel_name}: рекламные расходы выросли на {drr_pct:.0f}%")

        total_changes = context.get("total", {}).get("changes", {})
        margin_pct = total_changes.get("margin_pct")
        if margin_pct is not None:
            if margin_pct < -15:
                highlights.append(f"⚠️ Бренд: маржа упала на {abs(margin_pct):.0f}%")
            elif margin_pct > 25:
                highlights.append(f"📈 Бренд: маржа выросла на {margin_pct:.0f}%")

        for models_key, label in [("wb_top_models", "WB"), ("ozon_top_models", "OZON")]:
            models = context.get(models_key, [])
            for m in models[:5]:
                change = m.get("change_pct") or m.get("margin_change_pct")
                name = m.get("name") or m.get("model", "")
                if change is not None and name:
                    if change > 100:
                        highlights.append(f"🚀 {name} ({label}): +{change:.0f}%")
                    elif change < -30:
                        highlights.append(f"📉 {name} ({label}): {change:.0f}%")

        if not highlights:
            return ""

        lines = "\n".join(f"• {h}" for h in highlights[:3])
        return f"\n\n📊 <b>На основе данных:</b>\n{lines}"

    except Exception as e:
        logger.debug(f"Data highlights unavailable: {e}")
        return ""


def _load_data_context(params: dict) -> Optional[dict]:
    """Try to load data_context.json for the requested period or latest available."""
    if not REPORTS_DIR.exists():
        return None

    start_date = params.get("start_date", "")
    end_date = params.get("end_date", "")

    if start_date and end_date and start_date == end_date:
        path = REPORTS_DIR / f"{start_date}_data_context.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    if start_date and end_date and start_date != end_date:
        path = REPORTS_DIR / f"{start_date}_{end_date}_data_context.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    context_files = sorted(REPORTS_DIR.glob("*_data_context.json"), reverse=True)
    for f in context_files:
        if f.stat().st_size > 100:
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

    return None


# =====================================================================
# Enhanced basic parser (fallback when LLM unavailable)
# =====================================================================

def _parse_month_name(text: str) -> Optional[int]:
    text_lower = text.lower()
    for prefix, month_num in _MONTHS_RU.items():
        if text_lower.startswith(prefix):
            return month_num
    return None


def _parse_date_range(query: str) -> tuple:
    """Extract date range from Russian natural language query."""
    current_year = get_today_msk().year
    query_lower = query.lower()

    # Pattern 1: "1-7 февраля [2026]"
    m = re.search(
        r'(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?',
        query_lower
    )
    if m:
        day1, day2 = int(m.group(1)), int(m.group(2))
        month = _parse_month_name(m.group(3))
        year = int(m.group(4)) if m.group(4) else current_year
        if month:
            try:
                start = datetime(year, month, day1).strftime("%Y-%m-%d")
                end = datetime(year, month, day2).strftime("%Y-%m-%d")
                return start, end
            except ValueError:
                pass

    # Pattern 2: "с 1 по 7 февраля [2026]"
    m = re.search(
        r'с\s+(\d{1,2})\s+по\s+(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?',
        query_lower
    )
    if m:
        day1, day2 = int(m.group(1)), int(m.group(2))
        month = _parse_month_name(m.group(3))
        year = int(m.group(4)) if m.group(4) else current_year
        if month:
            try:
                start = datetime(year, month, day1).strftime("%Y-%m-%d")
                end = datetime(year, month, day2).strftime("%Y-%m-%d")
                return start, end
            except ValueError:
                pass

    # Pattern 3: "за январь [2026]" — full month
    m = re.search(r'за\s+([а-яё]+)(?:\s+(\d{4}))?', query_lower)
    if m:
        month = _parse_month_name(m.group(1))
        year = int(m.group(2)) if m.group(2) else current_year
        if month:
            last_day = calendar.monthrange(year, month)[1]
            start = datetime(year, month, 1).strftime("%Y-%m-%d")
            end = datetime(year, month, last_day).strftime("%Y-%m-%d")
            return start, end

    return None, None


def _detect_channels(query: str) -> list:
    channels = []
    query_lower = query.lower()
    for pattern, channel in _CHANNELS_MAP.items():
        if re.search(pattern, query_lower):
            channels.append(channel)
    return channels if channels else ["wb", "ozon"]


def _detect_models(query: str) -> list:
    query_lower = query.lower()
    return [m for m in _KNOWN_MODELS if m in query_lower]


def _basic_parse(query: str) -> dict:
    """Fallback keyword-based parameter extraction (no LLM)."""
    query_lower = query.lower()
    yesterday = (get_today_msk() - timedelta(days=1)).strftime("%Y-%m-%d")
    channels = _detect_channels(query)
    models = _detect_models(query)
    channels_str = ", ".join(c.upper() for c in channels)
    models_str = f", модели: {', '.join(models)}" if models else ""

    if any(w in query_lower for w in ["вчера", "вчерашн", "за день"]):
        return {
            "report_type": "daily",
            "start_date": yesterday,
            "end_date": yesterday,
            "channels": channels,
            "models": models,
            "question": query,
            "reformulated_query": (
                f"Анализ за вчера ({yesterday}): маржа, выручка, заказы, "
                f"реклама по {channels_str}{models_str}"
            ),
            "suggested_directions": [
                "Общий анализ ключевых метрик с day-over-day сравнением",
                "Декомпозиция маржи по 5 рычагам — какой фактор повлиял больше всего",
                "Эффективность рекламы: ДРР и ROMI по каналам",
            ],
        }

    if any(w in query_lower for w in ["неделю", "недел", "7 дней"]):
        end = get_today_msk() - timedelta(days=1)
        start = end - timedelta(days=6)
        s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        return {
            "report_type": "period",
            "start_date": s,
            "end_date": e,
            "channels": channels,
            "models": models,
            "question": query,
            "reformulated_query": (
                f"Анализ за неделю {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}: "
                f"маржа, выручка, заказы, реклама по {channels_str}{models_str}"
            ),
            "suggested_directions": [
                "Дневная динамика внутри недели — какие дни были лучшими/худшими",
                "Тренд маржи: растёт, падает или стабильно",
                "Связка реклама → заказы: как менялась эффективность",
            ],
        }

    if any(w in query_lower for w in ["месяц", "30 дней"]):
        end = get_today_msk() - timedelta(days=1)
        start = end - timedelta(days=29)
        s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        return {
            "report_type": "period",
            "start_date": s,
            "end_date": e,
            "channels": channels,
            "models": models,
            "question": query,
            "reformulated_query": (
                f"Анализ за месяц {start.strftime('%d.%m')}–{end.strftime('%d.%m.%Y')}: "
                f"маржа, выручка, заказы, реклама по {channels_str}{models_str}"
            ),
            "suggested_directions": [
                "Понедельная динамика — тренды и аномалии",
                "Статус vs бизнес-целей (маржа 5М/20% min → 10М/30% super)",
                "Какие модели росли, какие падали — ABC-анализ",
            ],
        }

    # Date range parsing
    start_date, end_date = _parse_date_range(query)
    if start_date and end_date:
        report_type = "daily" if start_date == end_date else "period"
        return {
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "channels": channels,
            "models": models,
            "question": query,
            "reformulated_query": (
                f"Анализ за {start_date} — {end_date}: "
                f"маржа, выручка, заказы, реклама по {channels_str}{models_str}"
            ),
            "suggested_directions": [
                "Общий анализ ключевых метрик за период",
                "Причины изменения маржи — декомпозиция по факторам",
                "Эффективность рекламы и динамика ДРР",
            ],
        }

    # Fallback
    return {
        "needs_clarification": True,
        "clarifying_questions": [
            "За какой период нужен анализ? (вчера, неделя, месяц, конкретные даты)",
            "Какие метрики интересуют? (маржа, выручка, заказы, ДРР)",
        ],
    }


# =====================================================================
# Message handlers
# =====================================================================

@router.message(QueryStates.waiting_for_query, F.text)
async def process_custom_query(
    message: Message,
    state: FSMContext,
    auth_service=None,
    oleg_agent=None,
    report_storage: ReportStorage = None,
    query_understanding=None,
):
    """Process user's custom query with LLM-based understanding."""
    if auth_service and not auth_service.is_authenticated(message.from_user.id):
        await state.clear()
        await message.answer(
            "❌ Вы не авторизованы. Используйте /start",
            reply_markup=_back_keyboard(),
        )
        return

    user_query = message.text

    processing_msg = await message.answer(
        "🤔 <b>Анализирую запрос...</b>",
        parse_mode="HTML",
    )

    try:
        # Get conversation history for multi-turn clarification
        data = await state.get_data()
        conversation_history = data.get("conversation_history", [])

        # LLM-based parsing with regex fallback
        if query_understanding:
            params = await query_understanding.parse(
                query=user_query,
                conversation_history=conversation_history if conversation_history else None,
            )
        else:
            params = _basic_parse(user_query)

        status = params.get("status", "")

        # --- Scenario "unclear": nothing understood ---
        if status == "unclear" or (params.get("needs_clarification") and not params.get("proposed_query")):
            questions = params.get("clarifying_questions", [])
            questions_text = "\n".join(f"• {q}" for q in questions)

            await processing_msg.edit_text(
                "🤔 <b>Помогите сформировать запрос:</b>\n\n"
                f"{questions_text}\n\n"
                "✍️ Напишите уточнение:",
                parse_mode="HTML",
                reply_markup=_back_keyboard(),
            )
            conversation_history.append({"role": "user", "content": user_query})
            conversation_history.append({
                "role": "assistant",
                "content": f"Вопросы: {'; '.join(questions)}",
            })
            await state.update_data(
                original_query=user_query,
                conversation_history=conversation_history,
            )
            await state.set_state(QueryStates.waiting_for_clarification)
            return

        # --- Scenario "needs_clarification": partially understood ---
        if status == "needs_clarification":
            understood = params.get("understood_parts", {})
            proposed = params.get("proposed_query", "")
            questions = params.get("clarifying_questions", [])
            questions_text = "\n".join(f"• {q}" for q in questions)

            text_parts = ["🤔 <b>Я понял часть запроса:</b>\n"]
            if understood.get("partial_intent"):
                text_parts.append(f"<i>{understood['partial_intent']}</i>\n")
            if proposed:
                text_parts.append(f"\n📋 <b>Предлагаю:</b>\n<i>«{proposed}»</i>\n")
            if questions_text:
                text_parts.append(f"\n<b>Уточните:</b>\n{questions_text}")
            text_parts.append("\n\n✍️ Напишите уточнение:")

            await processing_msg.edit_text(
                "".join(text_parts),
                parse_mode="HTML",
                reply_markup=_back_keyboard(),
            )
            conversation_history.append({"role": "user", "content": user_query})
            conversation_history.append({
                "role": "assistant",
                "content": f"Понял: {understood.get('partial_intent', '')}. Вопросы: {'; '.join(questions)}",
            })
            await state.update_data(
                original_query=user_query,
                conversation_history=conversation_history,
            )
            await state.set_state(QueryStates.waiting_for_clarification)
            return

        # --- Scenario "ready": fully understood → show proposed query for confirmation ---
        proposed = params.get("proposed_query", "")
        reformulated = params.get("reformulated_query", "")

        # Use proposed_query as the main display, fall back to reformulated
        display_query = proposed or reformulated
        if not display_query:
            report_type = params.get("report_type", "period")
            start_date = params.get("start_date", "")
            end_date = params.get("end_date", "")
            display_query = f"Анализ ({report_type})"
            if start_date and end_date:
                display_query += f" за {start_date} — {end_date}"
            display_query += f": {user_query}"

        await state.update_data(
            extracted_params=params,
            original_query=user_query,
        )
        await state.set_state(QueryStates.confirming_parameters)

        text_parts = [
            f"📋 <b>Я предлагаю такой анализ:</b>\n\n<i>«{display_query}»</i>",
        ]

        directions = params.get("suggested_directions", [])
        if directions:
            dir_lines = "\n".join(f"• {d}" for d in directions[:3])
            text_parts.append(f"\n\n💡 <b>Направления:</b>\n{dir_lines}")

        data_hints = _get_data_highlights(params)
        if data_hints:
            text_parts.append(data_hints)

        text_parts.append("\n\nЗапустить анализ или изменить запрос?")

        await processing_msg.edit_text(
            "".join(text_parts),
            parse_mode="HTML",
            reply_markup=_confirm_keyboard(),
        )

    except Exception as e:
        logger.error(f"Custom query processing failed: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуйте позже или используйте шаблонные отчёты.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
        await state.clear()


@router.callback_query(F.data == "custom_comment", QueryStates.confirming_parameters)
async def callback_add_comment(callback: CallbackQuery, state: FSMContext):
    """User wants to add a comment to refine the query."""
    await state.set_state(QueryStates.waiting_for_comment)

    await callback.message.answer(
        "✍️ Напишите, что уточнить или изменить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")],
        ]),
    )
    await callback.answer()


@router.message(QueryStates.waiting_for_clarification, F.text)
async def process_clarification(
    message: Message,
    state: FSMContext,
    auth_service=None,
    oleg_agent=None,
    report_storage: ReportStorage = None,
    query_understanding=None,
):
    """Process user's clarification — re-run LLM parsing with conversation context."""
    data = await state.get_data()
    original = data.get("original_query", "")
    conversation_history = data.get("conversation_history", [])
    clarification = message.text

    # Add clarification to conversation history
    conversation_history.append({"role": "user", "content": clarification})

    combined_query = f"{original}. {clarification}"
    await state.update_data(
        original_query=combined_query,
        conversation_history=conversation_history,
    )
    await state.set_state(QueryStates.waiting_for_query)

    # Re-run the main handler with conversation context
    message.text = combined_query
    await process_custom_query(
        message, state, auth_service, oleg_agent, report_storage, query_understanding,
    )


@router.message(QueryStates.waiting_for_comment, F.text)
async def process_comment(
    message: Message,
    state: FSMContext,
    auth_service=None,
    oleg_agent=None,
    report_storage: ReportStorage = None,
    query_understanding=None,
):
    """Process user's comment — re-run with combined query."""
    data = await state.get_data()
    original = data.get("original_query", "")
    comment = message.text

    combined_query = f"{original}. Уточнение: {comment}"
    await state.update_data(original_query=combined_query)
    await state.set_state(QueryStates.waiting_for_query)

    message.text = combined_query
    await process_custom_query(
        message, state, auth_service, oleg_agent, report_storage, query_understanding,
    )


@router.callback_query(F.data == "custom_confirm", QueryStates.confirming_parameters)
async def callback_confirm_params(
    callback: CallbackQuery,
    state: FSMContext,
    report_storage,
    notion_service,
    oleg_agent,
):
    """User confirmed query — run Oleg agent analysis."""
    data = await state.get_data()
    params = data.get("extracted_params", {})
    user_query = data.get("original_query", "")
    await state.clear()

    await callback.message.edit_text(
        "⏳ <b>Запускаю анализ...</b>\n\nОлег анализирует данные...",
        parse_mode="HTML",
    )
    await callback.answer()

    try:
        report_type = params.get("report_type", "period")
        start_date = params.get("start_date")
        end_date = params.get("end_date")

        # Determine dates if not provided
        if not start_date or not end_date:
            if report_type == "daily":
                yesterday = (get_today_msk() - timedelta(days=1)).strftime("%Y-%m-%d")
                start_date = yesterday
                end_date = yesterday
            elif report_type == "monthly":
                today = get_today_msk()
                first_of_month = today.replace(day=1)
                last_month_end = first_of_month - timedelta(days=1)
                start_date = last_month_end.replace(day=1).strftime("%Y-%m-%d")
                end_date = last_month_end.strftime("%Y-%m-%d")
            else:
                yesterday = get_today_msk() - timedelta(days=1)
                start_date = (yesterday - timedelta(days=6)).strftime("%Y-%m-%d")
                end_date = yesterday.strftime("%Y-%m-%d")

        reformulated = params.get("reformulated_query", user_query)
        result = await oleg_agent.analyze_deep(
            user_query=reformulated,
            params={
                "start_date": start_date,
                "end_date": end_date,
                "channels": params.get("channels", ["wb", "ozon"]),
                "models": params.get("models", []),
                "report_type": report_type,
                "suggested_directions": params.get("suggested_directions", []),
            },
        )

        if not result.get("brief_summary"):
            await callback.message.edit_text(
                "❌ <b>Ошибка анализа</b>\n\n"
                "Попробуйте шаблонный отчёт или повторите позже.",
                parse_mode="HTML",
                reply_markup=_back_keyboard(),
            )
            return

        # Save to storage
        try:
            report_storage.save_report(
                user_id=callback.from_user.id,
                report_type="custom",
                title=f"Запрос: {user_query[:50]}",
                content=result.get("detailed_report", ""),
                metadata=params,
            )
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

        # Notion sync
        notion_url = await notion_service.sync_report(
            start_date=start_date,
            end_date=end_date,
            report_md=result.get("detailed_report", ""),
        )

        # Build cost info
        cost_parts = []
        if result.get("cost_usd"):
            cost_parts.append(f"~${result['cost_usd']:.4f}")
        if result.get("iterations"):
            cost_parts.append(f"{result['iterations']} шагов")
        if result.get("duration_ms"):
            cost_parts.append(f"{result['duration_ms'] / 1000:.1f}с")
        cost_info = " | ".join(cost_parts) if cost_parts else None

        # Send formatted result
        html_text = ReportFormatter.format_for_telegram(
            brief_summary=result["brief_summary"],
            notion_url=notion_url,
            cost_info=cost_info,
        )

        # Add reasoning steps summary
        reasoning = result.get("reasoning_steps", [])
        if reasoning:
            steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(reasoning[:8]))
            html_text += f"\n\n<i>🧠 Шаги анализа Олега:\n{steps_text}</i>"

        keyboard = ReportFormatter.create_report_keyboard("custom")

        if len(html_text) > 4000:
            chunks = [html_text[i:i + 4000] for i in range(0, len(html_text), 4000)]
            await callback.message.edit_text(chunks[0], parse_mode="HTML")
            for chunk in chunks[1:-1]:
                await callback.message.answer(chunk, parse_mode="HTML")
            await callback.message.answer(
                chunks[-1], parse_mode="HTML", reply_markup=keyboard,
            )
        else:
            await callback.message.edit_text(
                html_text, parse_mode="HTML", reply_markup=keyboard,
            )

    except Exception as e:
        logger.error(f"Custom query execution failed: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуйте позже или используйте шаблонные отчёты.",
            parse_mode="HTML",
            reply_markup=_back_keyboard(),
        )
