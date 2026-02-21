"""
Создание задач с ИИ-ассистентом — КЛЮЧЕВАЯ ФУНКЦИЯ Людмилы

Флоу:
1. Пользователь описывает задачу текстом
2. Людмила (ZAI) анализирует, структурирует, УЛУЧШАЕТ
3. Если процесс → объясняет разницу, просит конкретизировать
4. Если не хватает данных → задаёт уточняющие вопросы
5. Резолвинг имён (нечёткий поиск)
6. Превью → Поставить / Изменить / Отмена
7. Создание в Bitrix24 с чеклистом
8. Fallback: если ИИ недоступен → пошаговый ввод
"""
import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents.lyudmila.handlers.common import (
    build_keyboard, menu_only_keyboard, send_error_message, safe_callback_answer,
)
from agents.lyudmila.models.task import TaskStructure

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


class TaskStates(StatesGroup):
    waiting_for_description = State()
    clarification = State()
    reviewing_structure = State()
    editing = State()
    resolving_assignee = State()
    # Fallback (без ИИ)
    manual_title = State()
    manual_assignee = State()
    manual_deadline = State()


# ─── Точка входа ──────────────────────────────────────────────

@router.callback_query(F.data == "action_task")
async def start_task_creation(callback: CallbackQuery, state: FSMContext, auth_service):
    """Начало создания задачи"""
    if not auth_service.is_authenticated(callback.from_user.id):
        await callback.answer("Вы не авторизованы", show_alert=True)
        return

    await callback.message.edit_text(
        "📋 <b>Создание задачи</b>\n\n"
        "Опишите задачу текстом. Укажите:\n"
        "• Кому (имя сотрудника)\n"
        "• Что сделать\n"
        "• К какому сроку\n\n"
        "<i>Например: «Поставь задачу Насте — опубликовать 3 поста "
        "в блог о коллекции Moon к пятнице»</i>",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(TaskStates.waiting_for_description)
    await safe_callback_answer(callback)


# ─── Получение описания задачи ────────────────────────────────

@router.message(TaskStates.waiting_for_description)
async def process_task_description(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase, context_service,
):
    """Обработка описания задачи через ИИ"""
    if not auth_service.is_authenticated(message.from_user.id):
        await message.answer("Вы не авторизованы. /start")
        return

    user_text = message.text
    if not user_text:
        await message.answer(
            "Я понимаю только текст. Опишите задачу словами.",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    # Индикатор загрузки
    processing_msg = await message.answer("🔄 Анализирую задачу...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        user = auth_service.get_user(message.from_user.id)
        creator_name = user.full_name if user else ""
        user_context = await context_service.get_task_context(
            message.from_user.id, user.bitrix_user_id if user else 0,
        )
        task = await lyuda_ai.structure_task(
            user_text, available_users,
            creator_name=creator_name,
            team_structure=team_structure,
            user_context=user_context,
        )
    except Exception as e:
        logger.exception(f"AI task structuring failed: {e}")
        try:
            await processing_msg.delete()
        except Exception:
            pass
        # Fallback: пошаговый ввод без ИИ
        await state.update_data(original_text=user_text)
        await message.answer(
            "⚠️ ИИ-помощник сейчас недоступен. Давайте заполним задачу по шагам.\n\n"
            f"📋 <b>Шаг 1/3:</b> Что нужно сделать?\n"
            f"<i>(ваш запрос: «{user_text}»)</i>\n\n"
            "Напишите название задачи (глагол + что сделать):",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        await state.set_state(TaskStates.manual_title)
        return

    try:
        await processing_msg.delete()
    except Exception:
        pass

    # Сохраняем структуру в FSM
    await state.update_data(task=task.to_dict(), original_text=user_text)

    # Проверка: это процесс, а не задача?
    if not task.is_valid_task:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Попробовать ещё раз", callback_data="task_retry")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
        ])
        await message.answer(
            f"⚠️ <b>Это похоже на процесс, а не задачу</b>\n\n"
            f"{task.feedback}\n\n"
            f"Опишите задачу конкретнее — с измеримым результатом и сроком.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    # Проверка: нужны уточнения?
    if task.clarification_needed:
        questions = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(task.clarification_needed))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
        ])
        await message.answer(
            f"❓ <b>Уточните, пожалуйста:</b>\n\n{questions}\n\n"
            f"Напишите ответ текстом:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await state.set_state(TaskStates.clarification)
        return

    # Всё заполнено — резолвим имя и показываем превью
    await _resolve_and_preview(message, state, task, user_cache, auth_service)


# ─── Уточняющие вопросы ──────────────────────────────────────

@router.message(TaskStates.clarification)
async def process_clarification(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase,
):
    """Обработка ответа на уточняющие вопросы"""
    data = await state.get_data()
    original_text = data.get('original_text', '')
    clarification = message.text

    # Объединяем оригинальное описание с уточнением
    combined_text = f"{original_text}\n\nУточнение: {clarification}"

    processing_msg = await message.answer("🔄 Обрабатываю...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        user = auth_service.get_user(message.from_user.id)
        creator_name = user.full_name if user else ""
        task = await lyuda_ai.structure_task(
            combined_text, available_users, creator_name=creator_name, team_structure=team_structure,
        )
    except Exception as e:
        logger.exception(f"AI clarification failed: {e}")
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

    await state.update_data(task=task.to_dict(), original_text=combined_text)

    if not task.is_valid_task:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Попробовать ещё раз", callback_data="task_retry")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
        ])
        await message.answer(
            f"⚠️ {task.feedback}\n\nОпишите задачу конкретнее.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    if task.clarification_needed:
        questions = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(task.clarification_needed))
        await message.answer(
            f"❓ Ещё нужно уточнить:\n\n{questions}\n\nНапишите ответ:",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    await _resolve_and_preview(message, state, task, user_cache, auth_service)


# ─── Fallback: пошаговый ввод без ИИ ─────────────────────────

@router.message(TaskStates.manual_title)
async def manual_task_title(message: Message, state: FSMContext):
    """Шаг 1/3: Название задачи"""
    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("Напишите название задачи текстом:")
        return

    await state.update_data(manual_title=title)
    await message.answer(
        f"✅ Название: <b>{title}</b>\n\n"
        "📋 <b>Шаг 2/3:</b> Кому поставить задачу?\n"
        "Напишите имя сотрудника:",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(TaskStates.manual_assignee)


@router.message(TaskStates.manual_assignee)
async def manual_task_assignee(
    message: Message, state: FSMContext, user_cache,
):
    """Шаг 2/3: Исполнитель"""
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("Напишите имя сотрудника:")
        return

    matches = user_cache.find_by_name(name)

    if len(matches) == 0:
        await message.answer(
            f"❓ Не нашла сотрудника «{name}». Попробуйте другое имя или фамилию:",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        return

    if len(matches) == 1:
        await state.update_data(
            manual_assignee_name=matches[0]['full_name'],
            manual_assignee_id=matches[0]['id'],
        )
        await message.answer(
            f"✅ Исполнитель: <b>{matches[0]['full_name']}</b>\n\n"
            "📋 <b>Шаг 3/3:</b> К какому сроку?\n"
            "Напишите дедлайн (например: «завтра», «пятница 18:00», «15.02.2026»):",
            parse_mode="HTML",
            reply_markup=build_keyboard(back_to="main_menu"),
        )
        await state.set_state(TaskStates.manual_deadline)
    else:
        # Несколько совпадений — кнопки
        buttons = []
        for m in matches[:5]:
            buttons.append([InlineKeyboardButton(
                text=f"{m['full_name']} ({m.get('position', '')})",
                callback_data=f"manual_assign_{m['id']}_{m['full_name'][:20]}",
            )])
        buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")])
        await message.answer(
            f"❓ Кого вы имеете в виду?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


@router.callback_query(TaskStates.manual_assignee, F.data.startswith("manual_assign_"))
async def manual_assignee_callback(callback: CallbackQuery, state: FSMContext, user_cache):
    """Выбор исполнителя из кнопок (fallback)"""
    parts = callback.data.removeprefix("manual_assign_").split("_", 1)
    bitrix_id = int(parts[0])
    user_data = user_cache.get_by_id(bitrix_id)
    full_name = user_data['full_name'] if user_data else parts[1] if len(parts) > 1 else "?"

    await state.update_data(manual_assignee_name=full_name, manual_assignee_id=bitrix_id)
    await callback.message.edit_text(
        f"✅ Исполнитель: <b>{full_name}</b>\n\n"
        "📋 <b>Шаг 3/3:</b> К какому сроку?\n"
        "Напишите дедлайн (например: «завтра», «пятница 18:00», «15.02.2026»):",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(TaskStates.manual_deadline)
    await safe_callback_answer(callback)


@router.message(TaskStates.manual_deadline)
async def manual_task_deadline(
    message: Message, state: FSMContext, auth_service, user_cache,
):
    """Шаг 3/3: Дедлайн → собираем TaskStructure → превью"""
    deadline = message.text.strip() if message.text else ""
    if not deadline:
        await message.answer("Напишите дедлайн:")
        return

    data = await state.get_data()
    task = TaskStructure(
        is_valid_task=True,
        title=data.get('manual_title', data.get('original_text', '')),
        description=data.get('original_text', ''),
        target_result="",
        assignee_name=data.get('manual_assignee_name'),
        assignee_bitrix_id=data.get('manual_assignee_id'),
        deadline_text=deadline,
    )

    await state.update_data(task=task.to_dict())
    await _show_task_preview(message, task, state)


# ─── Резолвинг имён и превью ─────────────────────────────────

async def _resolve_and_preview(
    target, state: FSMContext, task: TaskStructure, user_cache, auth_service,
):
    """Резолвинг имени исполнителя + показ превью"""
    # Резолвинг исполнителя
    if task.assignee_name:
        matches = user_cache.find_by_name(task.assignee_name)

        if len(matches) == 0:
            # Не найден — спрашиваем
            await state.update_data(task=task.to_dict())
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")],
            ])

            if isinstance(target, CallbackQuery):
                await target.message.edit_text(
                    f"❓ Не нашла сотрудника «{task.assignee_name}».\n"
                    "Уточните имя или фамилию:",
                    reply_markup=keyboard,
                )
            else:
                await target.answer(
                    f"❓ Не нашла сотрудника «{task.assignee_name}».\n"
                    "Уточните имя или фамилию:",
                    reply_markup=keyboard,
                )
            await state.set_state(TaskStates.resolving_assignee)
            return

        elif len(matches) == 1:
            # Один вариант — подставляем
            task.assignee_name = matches[0]['full_name']
            task.assignee_bitrix_id = matches[0]['id']

        else:
            # Несколько — предлагаем выбрать
            buttons = []
            for m in matches[:5]:
                buttons.append([InlineKeyboardButton(
                    text=f"{m['full_name']} ({m.get('position', '')})",
                    callback_data=f"assign_{m['id']}",
                )])
            buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await state.update_data(task=task.to_dict())

            text = f"❓ Кого вы имеете в виду ({task.assignee_name})?"
            if isinstance(target, CallbackQuery):
                await target.message.edit_text(text, reply_markup=keyboard)
            else:
                await target.answer(text, reply_markup=keyboard)
            await state.set_state(TaskStates.resolving_assignee)
            return

    # Автоматически добавляем постановщика как наблюдателя
    user = auth_service.get_user(
        target.from_user.id if isinstance(target, (Message, CallbackQuery)) else 0
    )
    if user and user.full_name not in task.observers:
        task.observers.append(user.full_name)
        task.observer_bitrix_ids.append(user.bitrix_user_id)

    await state.update_data(task=task.to_dict())
    await _show_task_preview(target, task, state)


@router.message(TaskStates.resolving_assignee)
async def resolve_assignee_text(
    message: Message, state: FSMContext,
    auth_service, user_cache,
):
    """Текстовый ввод имени для резолвинга"""
    data = await state.get_data()
    task = TaskStructure.from_dict(data.get('task', {}))
    task.assignee_name = message.text.strip()

    await _resolve_and_preview(message, state, task, user_cache, auth_service)


@router.callback_query(TaskStates.resolving_assignee, F.data.startswith("assign_"))
async def resolve_assignee_callback(
    callback: CallbackQuery, state: FSMContext,
    auth_service, user_cache,
):
    """Выбор исполнителя из кнопок"""
    bitrix_id = int(callback.data.removeprefix("assign_"))
    data = await state.get_data()
    task = TaskStructure.from_dict(data.get('task', {}))

    user_data = user_cache.get_by_id(bitrix_id)
    if user_data:
        task.assignee_name = user_data['full_name']
        task.assignee_bitrix_id = bitrix_id

    await _resolve_and_preview(callback, state, task, user_cache, auth_service)


# ─── Превью задачи ───────────────────────────────────────────

async def _show_task_preview(target, task: TaskStructure, state: FSMContext):
    """Показать превью задачи с кнопками действий"""
    preview = task.format_preview()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Поставить", callback_data="task_submit"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="task_edit"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")],
    ])

    await state.set_state(TaskStates.reviewing_structure)

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(preview, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await target.message.answer(preview, parse_mode="HTML", reply_markup=keyboard)
        await safe_callback_answer(target)
    else:
        await target.answer(preview, parse_mode="HTML", reply_markup=keyboard)


# ─── Действия с превью ───────────────────────────────────────

@router.callback_query(TaskStates.reviewing_structure, F.data == "task_submit")
async def submit_task(
    callback: CallbackQuery, state: FSMContext,
    auth_service, bitrix_service, db_service, user_cache, supabase, context_service,
):
    """Поставить задачу в Bitrix24"""
    data = await state.get_data()
    task = TaskStructure.from_dict(data.get('task', {}))
    user = auth_service.get_user(callback.from_user.id)

    if not user:
        await send_error_message(callback, "Сессия истекла. /start")
        await state.clear()
        return

    processing_msg = await callback.message.edit_text("🔄 Создаю задачу в Bitrix24...")

    try:
        # Формируем описание с целевым результатом
        description = task.description
        if task.target_result:
            description += f"\n\n🎯 Целевой результат:\n{task.target_result}"

        fields = {
            'TITLE': task.title,
            'DESCRIPTION': description,
            'CREATED_BY': user.bitrix_user_id,
        }

        if task.assignee_bitrix_id:
            fields['RESPONSIBLE_ID'] = task.assignee_bitrix_id
        if task.deadline_text:
            fields['DEADLINE'] = task.deadline_text
        if task.observer_bitrix_ids:
            fields['AUDITORS'] = task.observer_bitrix_ids
        if task.co_executor_bitrix_ids:
            fields['ACCOMPLICES'] = task.co_executor_bitrix_ids

        result = await bitrix_service.create_task(fields)
        task_id = result.get('task', {}).get('id') or result.get('id')

        # Добавляем чеклист
        if task_id and task.checklist:
            for item in task.checklist:
                try:
                    await bitrix_service.add_checklist_item(int(task_id), item)
                except Exception as e:
                    logger.warning(f"Failed to add checklist item: {e}")

        # Лог действия
        db_service.log_action(
            callback.from_user.id,
            "task_created",
            int(task_id) if task_id else None,
            {"title": task.title, "assignee": task.assignee_name},
        )

        # Логируем подсказки как «принятые» (пользователь создал задачу с ними)
        if task.suggestions and supabase and supabase._pool:
            for s in task.suggestions:
                try:
                    await supabase.log_suggestion(
                        callback.from_user.id, "task", s,
                        suggestion_type="task_creation", accepted=True,
                    )
                except Exception:
                    pass
            try:
                await context_service.update_preferences(callback.from_user.id)
            except Exception:
                pass

        await callback.message.edit_text(
            f"✅ <b>Задача #{task_id} поставлена!</b>\n\n"
            f"📋 {task.title}\n"
            f"👤 Исполнитель: {task.assignee_name or 'не назначен'}\n\n"
            f"Исполнитель получит уведомление в Bitrix24.",
            parse_mode="HTML",
            reply_markup=menu_only_keyboard(),
        )

    except Exception as e:
        logger.exception(f"Task creation failed: {e}")
        await callback.message.edit_text(
            f"❌ Не удалось создать задачу.\n\n"
            f"Ошибка: {str(e)[:200]}\n\n"
            f"Попробуйте позже.",
            reply_markup=menu_only_keyboard(),
        )

    await state.clear()
    await safe_callback_answer(callback)


@router.callback_query(TaskStates.reviewing_structure, F.data == "task_edit")
async def edit_task(callback: CallbackQuery, state: FSMContext):
    """Переход к редактированию задачи"""
    await callback.message.edit_text(
        "✏️ <b>Что изменить?</b>\n\n"
        "Напишите текстом, например:\n"
        "• «Исполнитель — Миша»\n"
        "• «Дедлайн — следующий понедельник»\n"
        "• «Добавь в чеклист: согласовать макет»",
        parse_mode="HTML",
        reply_markup=build_keyboard(back_to="task_back_to_preview"),
    )
    await state.set_state(TaskStates.editing)
    await safe_callback_answer(callback)


@router.callback_query(F.data == "task_back_to_preview")
async def back_to_preview(callback: CallbackQuery, state: FSMContext):
    """Вернуться к превью задачи"""
    data = await state.get_data()
    task = TaskStructure.from_dict(data.get('task', {}))
    await _show_task_preview(callback, task, state)


@router.message(TaskStates.editing)
async def process_task_edit(
    message: Message, state: FSMContext,
    auth_service, lyuda_ai, user_cache, supabase,
):
    """Обработка редактирования задачи через ИИ"""
    data = await state.get_data()
    task = TaskStructure.from_dict(data.get('task', {}))
    user_feedback = message.text

    processing_msg = await message.answer("🔄 Обновляю...")

    try:
        available_users = user_cache.get_all_names_for_prompt()
        team_structure = await _get_team_structure(user_cache, supabase)
        updated_task = await lyuda_ai.refine_task(
            task, user_feedback, available_users, team_structure=team_structure,
        )
    except Exception as e:
        logger.exception(f"Task refine failed: {e}")
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

    # Пере-резолвим имя если изменилось
    if updated_task.assignee_name and updated_task.assignee_name != task.assignee_name:
        await _resolve_and_preview(message, state, updated_task, user_cache, auth_service)
    else:
        # Сохраняем старый bitrix_id
        updated_task.assignee_bitrix_id = task.assignee_bitrix_id
        updated_task.observer_bitrix_ids = task.observer_bitrix_ids
        updated_task.co_executor_bitrix_ids = task.co_executor_bitrix_ids
        await state.update_data(task=updated_task.to_dict())
        await _show_task_preview(message, updated_task, state)


# ─── Retry (после отклонения как процесс) ────────────────────

@router.callback_query(F.data == "task_retry")
async def task_retry(callback: CallbackQuery, state: FSMContext):
    """Попробовать описать задачу заново"""
    await callback.message.edit_text(
        "📋 Опишите задачу конкретнее — с измеримым результатом и сроком:\n",
        reply_markup=build_keyboard(back_to="main_menu"),
    )
    await state.set_state(TaskStates.waiting_for_description)
    await safe_callback_answer(callback)
