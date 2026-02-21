"""
Создание встреч с ИИ-ассистентом

Флоу:
1. Описание → ИИ → структурирование + обогащение (повестка, подготовка)
2. Если не хватает данных → уточняющие вопросы
3. Резолвинг участников
4. Превью → Создать / Изменить / Отмена
5. Создание в Bitrix24 calendar
6. Fallback: если ИИ недоступен → пошаговый ввод
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents.lyudmila.handlers.common import (
    build_keyboard, menu_only_keyboard, send_error_message, safe_callback_answer,
)
from agents.lyudmila.models.meeting import MeetingStructure

logger = logging.getLogger(__name__)

router = Router()


async def _get_team_structure(user_cache, supabase) -> str:
    """Получить оргструктуру для LLM-промпта (Supabase → fallback на кеш)"""
    supabase_employees = None
    if supabase and supabase._pool:
        try:
            supabase_employees = await supabase.get_all_active_employees()
        except Exception:
            pass
    return user_cache.get_team_structure_for_prompt(supabase_employees)


class MeetingStates(StatesGroup):
    waiting_for_description = State()
    clarification = State()
    reviewing_structure = State()
    editing = State()
    # Fallback (без ИИ)
    manual_title = State()
    manual_attendees = State()
    manual_datetime = State()


# ─── Точка входа ──────────────────────────────────────────────

@router.callback_query(F.data == "action_meeting")
async def start_meeting_creation(callback: CallbackQuery, state: FSMContext, auth_service):
    """Начало создания встречи"""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "📅 <b>Создание встречи</b>\n\n"
        "Опишите встречу текстом. Укажите:\n"
        "• С кем (участники)\n"
        "• Тема / цель\n"
        "• Когда (дата и время)\n\n"
        "<i>Например: «Созвон с поставщиком тканей в четверг в 14:00, "
        "обсудить новую партию»</i>",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(MeetingStates.waiting_for_description)
    await safe_callback_answer(callback)


# ─── Получение описания ──────────────────────────────────────

@router.message(MeetingStates.waiting_for_description)
async def process_meeting_description(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase,
):
    """Обработка описания встречи через ИИ"""
    if not auth_service.is_authenticated(message.from_user.id):
        await message.answer("Вы не авторизованы. /start")
        return

    user_text = message.text
    if not user_text:
        await message.answer(
            "Я понимаю только текст. Опишите встречу словами.",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    processing_msg = await message.answer("🔄 Анализирую встречу...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        user = auth_service.get_user(message.from_user.id)
        creator_name = user.full_name if user else ""
        meeting = await lyuda_ai.structure_meeting(
            user_text, available_users, creator_name=creator_name, team_structure=team_structure,
        )
    except Exception as e:
        logger.exception(f"AI meeting structuring failed: {e}")
        try:
            await processing_msg.delete()
        except Exception:
            pass
        # Fallback: пошаговый ввод без ИИ
        await state.update_data(original_text=user_text)
        await message.answer(
            "⚠️ ИИ-помощник сейчас недоступен. Давайте заполним встречу по шагам.\n\n"
            f"📅 <b>Шаг 1/3:</b> Какая тема встречи?\n"
            f"<i>(ваш запрос: «{user_text}»)</i>\n\n"
            "Напишите тему встречи:",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        await state.set_state(MeetingStates.manual_title)
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    await state.update_data(meeting=meeting.to_dict(), original_text=user_text)

    # Уточнения?
    if meeting.clarification_needed:
        questions = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(meeting.clarification_needed))
        await message.answer(
            f"❓ <b>Уточните, пожалуйста:</b>\n\n{questions}\n\nНапишите ответ:",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        await state.set_state(MeetingStates.clarification)
        return

    # Резолвим участников и показываем превью
    await _resolve_attendees_and_preview(message, state, meeting, user_cache, auth_service)


# ─── Уточнения ───────────────────────────────────────────────

@router.message(MeetingStates.clarification)
async def process_meeting_clarification(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase,
):
    """Ответ на уточняющие вопросы"""
    data = await state.get_data()
    original_text = data.get('original_text', '')
    combined = f"{original_text}\n\nУточнение: {message.text}"

    processing_msg = await message.answer("🔄 Обрабатываю...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        user = auth_service.get_user(message.from_user.id)
        creator_name = user.full_name if user else ""
        meeting = await lyuda_ai.structure_meeting(
            combined, available_users, creator_name=creator_name, team_structure=team_structure,
        )
    except Exception as e:
        logger.exception(f"Meeting clarification failed: {e}")
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await send_error_message(message, "Не удалось обработать. Попробуйте ещё раз.")
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    await state.update_data(meeting=meeting.to_dict(), original_text=combined)

    if meeting.clarification_needed:
        questions = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(meeting.clarification_needed))
        await message.answer(
            f"❓ Ещё нужно уточнить:\n\n{questions}\n\nНапишите ответ:",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    await _resolve_attendees_and_preview(message, state, meeting, user_cache, auth_service)


# ─── Fallback: пошаговый ввод без ИИ ─────────────────────────

@router.message(MeetingStates.manual_title)
async def manual_meeting_title(message: Message, state: FSMContext):
    """Шаг 1/3: Тема встречи"""
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("Напишите тему встречи текстом:")
        return

    await state.update_data(manual_title=title)
    await message.answer(
        f"✅ Тема: <b>{title}</b>\n\n"
        "📅 <b>Шаг 2/3:</b> Кого пригласить?\n"
        "Напишите имена участников через запятую:",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(MeetingStates.manual_attendees)


@router.message(MeetingStates.manual_attendees)
async def manual_meeting_attendees(
    message: Message, state: FSMContext, user_cache,
):
    """Шаг 2/3: Участники"""
    names_text = message.text.strip() if message.text else ""
    if not names_text:
        await message.answer("Напишите имена участников:")
        return

    # Разбираем имена через запятую
    raw_names = [n.strip() for n in names_text.split(",") if n.strip()]
    resolved_names = []
    resolved_ids = []
    not_found = []

    for name in raw_names:
        matches = user_cache.find_by_name(name)
        if matches:
            resolved_names.append(matches[0]['full_name'])
            resolved_ids.append(matches[0]['id'])
        else:
            not_found.append(name)

    if not_found and not resolved_names:
        await message.answer(
            f"❓ Не нашла сотрудников: {', '.join(not_found)}.\n"
            "Попробуйте другие имена или фамилии:",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    warning = ""
    if not_found:
        warning = f"\n⚠️ Не найдены: {', '.join(not_found)}"

    await state.update_data(
        manual_attendees=resolved_names,
        manual_attendee_ids=resolved_ids,
    )
    attendees_text = ", ".join(resolved_names)
    await message.answer(
        f"✅ Участники: <b>{attendees_text}</b>{warning}\n\n"
        "📅 <b>Шаг 3/3:</b> Когда?\n"
        "Напишите дату и время (например: «завтра в 14:00», «четверг 10:00», «15.02.2026 15:30»):",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(MeetingStates.manual_datetime)


@router.message(MeetingStates.manual_datetime)
async def manual_meeting_datetime(
    message: Message, state: FSMContext, auth_service, user_cache,
):
    """Шаг 3/3: Дата/время → собираем MeetingStructure → превью"""
    dt_text = message.text.strip() if message.text else ""
    if not dt_text:
        await message.answer("Напишите дату и время:")
        return

    data = await state.get_data()

    meeting = MeetingStructure(
        title=data.get('manual_title', data.get('original_text', '')),
        description=data.get('original_text', ''),
        datetime_text=dt_text,
        attendees=data.get('manual_attendees', []),
        attendee_bitrix_ids=data.get('manual_attendee_ids', []),
    )

    # Добавляем автора как участника
    user = auth_service.get_user(message.from_user.id)
    if user:
        if user.full_name not in meeting.attendees:
            meeting.attendees.append(user.full_name)
            meeting.attendee_bitrix_ids.append(user.bitrix_user_id)

    await state.update_data(meeting=meeting.to_dict())
    await _show_meeting_preview(message, meeting, state)


# ─── Резолвинг участников ────────────────────────────────────

async def _resolve_attendees_and_preview(
    target, state: FSMContext, meeting: MeetingStructure, user_cache, auth_service,
):
    """Резолвинг имён участников + превью"""
    resolved_ids = []
    resolved_names = []

    for name in meeting.attendees:
        matches = user_cache.find_by_name(name)
        if matches:
            resolved_names.append(matches[0]['full_name'])
            resolved_ids.append(matches[0]['id'])
        else:
            resolved_names.append(name)

    # Добавляем автора как участника
    user = auth_service.get_user(
        target.from_user.id if isinstance(target, (Message, CallbackQuery)) else 0
    )
    if user:
        if user.full_name not in resolved_names:
            resolved_names.append(user.full_name)
            resolved_ids.append(user.bitrix_user_id)

    meeting.attendees = resolved_names
    meeting.attendee_bitrix_ids = resolved_ids

    await state.update_data(meeting=meeting.to_dict())
    await _show_meeting_preview(target, meeting, state)


async def _show_meeting_preview(target, meeting: MeetingStructure, state: FSMContext):
    """Показать превью встречи"""
    preview = meeting.format_preview()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="meeting_submit"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="meeting_edit"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")],
    ])

    await state.set_state(MeetingStates.reviewing_structure)

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(preview, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await target.message.answer(preview, parse_mode="HTML", reply_markup=keyboard)
        await safe_callback_answer(target)
    else:
        await target.answer(preview, parse_mode="HTML", reply_markup=keyboard)


# ─── Отправка в Bitrix24 ─────────────────────────────────────

@router.callback_query(MeetingStates.reviewing_structure, F.data == "meeting_submit")
async def submit_meeting(
    callback: CallbackQuery, state: FSMContext,
    auth_service, bitrix_service, db_service, supabase, context_service,
):
    """Создать встречу в Bitrix24"""
    data = await state.get_data()
    meeting = MeetingStructure.from_dict(data.get('meeting', {}))
    user = auth_service.get_user(callback.from_user.id)

    if not user:
        await send_error_message(callback, "Сессия истекла. /start")
        await state.clear()
        return

    await callback.message.edit_text("🔄 Создаю встречу в Bitrix24...")

    try:
        # Формируем описание с подготовкой
        description = meeting.description
        if meeting.preparation:
            description += f"\n\n📚 Подготовить к встрече:\n{meeting.preparation}"
        if meeting.pre_reading:
            description += f"\n\n📖 Изучить заранее:\n{meeting.pre_reading}"

        fields = {
            'type': 'user',
            'ownerId': user.bitrix_user_id,
            'name': meeting.title,
            'description': description,
            'from': meeting.datetime_text or '',
            'to': meeting.datetime_text or '',
            'attendees': meeting.attendee_bitrix_ids,
        }

        if meeting.link:
            fields['description'] += f"\n\n🔗 Ссылка: {meeting.link}"

        result = await bitrix_service.create_calendar_event(fields)
        event_id = result.get('id') if isinstance(result, dict) else result

        # Лог
        db_service.log_action(
            callback.from_user.id,
            "meeting_created",
            int(event_id) if event_id else None,
            {"title": meeting.title, "attendees": meeting.attendees},
        )

        # Логируем подсказки
        if meeting.suggestions and supabase and supabase._pool:
            for s in meeting.suggestions:
                try:
                    await supabase.log_suggestion(
                        callback.from_user.id, "meeting", s,
                        suggestion_type="meeting_creation", accepted=True,
                    )
                except Exception:
                    pass
            try:
                await context_service.update_preferences(callback.from_user.id)
            except Exception:
                pass

        attendees_text = ", ".join(meeting.attendees) if meeting.attendees else "—"
        await callback.message.edit_text(
            f"✅ <b>Встреча создана!</b>\n\n"
            f"📅 {meeting.title}\n"
            f"🕐 {meeting.datetime_text or 'время не указано'}\n"
            f"👥 Участники: {attendees_text}\n\n"
            f"Участники получат уведомление в Bitrix24.",
            parse_mode="HTML",
            reply_markup=menu_only_keyboard(),
        )

    except Exception as e:
        logger.exception(f"Meeting creation failed: {e}")
        await callback.message.edit_text(
            f"❌ Не удалось создать встречу.\n\n"
            f"Ошибка: {str(e)[:200]}\n\nПопробуйте позже.",
            reply_markup=menu_only_keyboard(),
        )

    await state.clear()
    await safe_callback_answer(callback)


# ─── Редактирование ──────────────────────────────────────────

@router.callback_query(MeetingStates.reviewing_structure, F.data == "meeting_edit")
async def edit_meeting(callback: CallbackQuery, state: FSMContext):
    """Переход к редактированию"""
    await callback.message.edit_text(
        "✏️ <b>Что изменить?</b>\n\n"
        "Напишите текстом, например:\n"
        "• «Время — 15:00 вместо 14:00»\n"
        "• «Добавь участника Мишу»\n"
        "• «Длительность 30 минут»",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="meeting_back_to_preview"),
    )
    await state.set_state(MeetingStates.editing)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "meeting_back_to_preview")
async def back_to_meeting_preview(callback: CallbackQuery, state: FSMContext):
    """Вернуться к превью встречи"""
    data = await state.get_data()
    meeting = MeetingStructure.from_dict(data.get('meeting', {}))
    await _show_meeting_preview(callback, meeting, state)


@router.message(MeetingStates.editing)
async def process_meeting_edit(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase,
):
    """Обработка редактирования через ИИ"""
    data = await state.get_data()
    meeting = MeetingStructure.from_dict(data.get('meeting', {}))

    processing_msg = await message.answer("🔄 Обновляю...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        updated = await lyuda_ai.refine_meeting(
            meeting, message.text, available_users, team_structure=team_structure,
        )
    except Exception as e:
        logger.exception(f"Meeting refine failed: {e}")
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await send_error_message(message)
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    await _resolve_attendees_and_preview(message, state, updated, user_cache, auth_service)
