"""morning_digest — утренний дайджест встреч для команды Саймона.

Тест-план (8 сценариев):
1. MORNING_DIGEST_ENABLED=false → loop не стартует (не спит, не рассылает).
2. Юзер без встреч → не шлём сообщение.
3. Юзер только с личными событиями → не шлём (все в группе ⏭).
4. Юзер с 2 ⚠️ → дайджест с 2 кнопками add_telemost.
5. Юзер с 1🎙 + 1⚠️ + 1⏭ → все 3 секции в тексте.
6. Клик add_telemost → create_conference + event_update + сообщение юзеру.
7. Telemost API падает при клике → fallback message юзеру.
8. compute_next_msk_hour → корректно вычисляет время до 09:00 МСК.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from zoneinfo import ZoneInfo

_MSK = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(telegram_id: int = 111, bitrix_id: str = "1", name: str = "Тест") -> dict:
    """Return a dict mimicking an asyncpg Record for morning_digest tests."""
    return {
        "telegram_id": telegram_id,
        "bitrix_id": bitrix_id,
        "name": name,
        "short_name": name,
    }


def _bitrix_event(
    event_id: str = "42",
    name: str = "Планёрка",
    date_from: str = "16.05.2026 11:00:00",
    location: str = "",
    description: str = "",
    attendees_codes: list | None = None,
    is_meeting: bool = True,
) -> dict:
    return {
        "ID": event_id,
        "NAME": name,
        "DATE_FROM": date_from,
        "TZ_FROM": "Europe/Moscow",
        "LOCATION": location,
        "DESCRIPTION": description,
        "ATTENDEES_CODES": attendees_codes if attendees_codes is not None else ["U1", "U2"],
        "IS_MEETING": is_meeting,
    }


# ---------------------------------------------------------------------------
# Test 1: disabled by env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_by_env():
    """MORNING_DIGEST_ENABLED=false → loop возвращается сразу, не спит."""
    with (
        patch(
            "services.telemost_recorder_api.workers.morning_digest.MORNING_DIGEST_ENABLED",
            False,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch(
            "services.telemost_recorder_api.workers.morning_digest.send_digests_to_all_users",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        from services.telemost_recorder_api.workers.morning_digest import morning_digest_loop

        await morning_digest_loop()

        mock_sleep.assert_not_called()
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: user without meetings → no digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_without_meetings_no_digest():
    """0 событий у юзера → tg_send_message не вызывается."""
    user = _make_user()

    with (
        patch(
            "services.telemost_recorder_api.workers.morning_digest._fetch_today_events",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.telemost_recorder_api.workers.morning_digest.tg_send_message",
            new_callable=AsyncMock,
        ) as mock_tg,
    ):
        from services.telemost_recorder_api.workers.morning_digest import send_daily_digest_to_user

        await send_daily_digest_to_user(user)
        mock_tg.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: user with only personal events → no digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_only_private_no_digest():
    """Все события личные (attendees<2, IS_MEETING=False) → не шлём."""
    user = _make_user()
    personal_ev = _bitrix_event(
        name="Терапевт", attendees_codes=[], is_meeting=False
    )

    with (
        patch(
            "services.telemost_recorder_api.workers.morning_digest._fetch_today_events",
            new_callable=AsyncMock,
            return_value=[personal_ev],
        ),
        patch(
            "services.telemost_recorder_api.workers.morning_digest.tg_send_message",
            new_callable=AsyncMock,
        ) as mock_tg,
    ):
        from services.telemost_recorder_api.workers.morning_digest import send_daily_digest_to_user

        await send_daily_digest_to_user(user)
        mock_tg.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: user with 2 needs_link events → digest with 2 buttons
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_needs_link_gets_buttons():
    """2 встречи без ссылки → отправляем дайджест с 2 кнопками add_telemost."""
    user = _make_user()
    ev1 = _bitrix_event(event_id="10", name="Встреча 1", location="", date_from="16.05.2026 16:00:00")
    ev2 = _bitrix_event(event_id="11", name="Встреча 2", location="", date_from="16.05.2026 17:00:00")

    captured_keyboard: list[dict] = []

    async def fake_tg_send(chat_id, text, *, reply_markup=None, **_kw):
        if reply_markup:
            captured_keyboard.append(reply_markup)

    with (
        patch(
            "services.telemost_recorder_api.workers.morning_digest._fetch_today_events",
            new_callable=AsyncMock,
            return_value=[ev1, ev2],
        ),
        patch(
            "services.telemost_recorder_api.workers.morning_digest.tg_send_message",
            side_effect=fake_tg_send,
        ),
    ):
        from services.telemost_recorder_api.workers.morning_digest import send_daily_digest_to_user

        await send_daily_digest_to_user(user)

    assert len(captured_keyboard) == 1
    keyboard = captured_keyboard[0]
    rows = keyboard["inline_keyboard"]
    # Должно быть 2 кнопки (по одной на каждое событие)
    all_buttons = [btn for row in rows for btn in row]
    add_telemost_buttons = [b for b in all_buttons if b["callback_data"].startswith("add_telemost:")]
    assert len(add_telemost_buttons) == 2
    assert add_telemost_buttons[0]["callback_data"] == "add_telemost:10"
    assert add_telemost_buttons[1]["callback_data"] == "add_telemost:11"


# ---------------------------------------------------------------------------
# Test 5: all 3 groups render correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_all_groups_renders_correctly():
    """1🎙 + 1⚠️ + 1⏭ → все 3 секции присутствуют в тексте."""
    user = _make_user(name="Данила")
    ev_link = _bitrix_event(
        event_id="1", name="Стенд-ап", location="https://telemost.yandex.ru/j/abc123",
        date_from="16.05.2026 11:00:00",
    )
    ev_no_link = _bitrix_event(
        event_id="2", name="Встреча с Леной", location="", date_from="16.05.2026 16:00:00"
    )
    ev_personal = _bitrix_event(
        event_id="3", name="Терапевт", attendees_codes=[], is_meeting=False,
        location="", date_from="16.05.2026 08:30:00",
    )

    captured_text: list[str] = []

    async def fake_tg_send(chat_id, text, *, reply_markup=None, **_kw):
        captured_text.append(text)

    with (
        patch(
            "services.telemost_recorder_api.workers.morning_digest._fetch_today_events",
            new_callable=AsyncMock,
            return_value=[ev_link, ev_no_link, ev_personal],
        ),
        patch(
            "services.telemost_recorder_api.workers.morning_digest.tg_send_message",
            side_effect=fake_tg_send,
        ),
    ):
        from services.telemost_recorder_api.workers.morning_digest import send_daily_digest_to_user

        await send_daily_digest_to_user(user)

    assert len(captured_text) == 1
    text = captured_text[0]
    assert "🎙" in text, "Секция '🎙 Запишу' отсутствует"
    assert "⚠️" in text, "Секция '⚠️ Нет ссылки' отсутствует"
    assert "⏭" in text, "Секция '⏭ Личное' отсутствует"
    assert "Стенд-ап" in text
    assert "Встреча с Леной" in text
    assert "Терапевт" in text
    assert "Данила" in text


# ---------------------------------------------------------------------------
# Test 6: add_telemost callback → creates room + updates Bitrix + replies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_telemost_callback_creates_room():
    """Клик add_telemost:<event_id> → create_conference + event_update + DM юзеру."""
    from shared.yandex_telemost import Conference

    mock_conference = Conference(id="conf123", join_url="https://telemost.yandex.ru/j/conf123")

    with (
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.create_conference",
            new_callable=AsyncMock,
            return_value=mock_conference,
        ) as mock_create,
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.event_get_one",
            new_callable=AsyncMock,
            return_value={"ID": "42", "OWNER_ID": "1", "LOCATION": "офис"},
        ) as mock_get,
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.event_update",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_update,
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.tg_send_message",
            new_callable=AsyncMock,
        ) as mock_tg,
    ):
        from services.telemost_recorder_api.handlers.add_telemost import handle_add_telemost

        await handle_add_telemost(chat_id=111, user_telegram_id=111, event_id="42")

        mock_create.assert_called_once()
        mock_get.assert_called_once_with("42")
        # Проверяем что event_update вызван с LOCATION содержащей URL конференции
        mock_update.assert_called_once()
        update_call_kwargs = mock_update.call_args.kwargs
        assert "LOCATION" in update_call_kwargs["fields"]
        assert "conf123" in update_call_kwargs["fields"]["LOCATION"]
        # Проверяем финальный ответ юзеру
        assert mock_tg.call_count >= 1
        last_call_text = mock_tg.call_args_list[-1][0][1]
        assert "conf123" in last_call_text or "telemost" in last_call_text.lower()


# ---------------------------------------------------------------------------
# Test 7: Telemost API down → fallback message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_telemost_callback_telemost_api_down():
    """Telemost API падает → юзер получает fallback-сообщение, не traceback."""
    with (
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.create_conference",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Telemost API error 503"),
        ),
        patch(
            "services.telemost_recorder_api.handlers.add_telemost.tg_send_message",
            new_callable=AsyncMock,
        ) as mock_tg,
    ):
        from services.telemost_recorder_api.handlers.add_telemost import handle_add_telemost

        await handle_add_telemost(chat_id=111, user_telegram_id=111, event_id="42")

        assert mock_tg.call_count >= 1
        # Должно быть сообщение об ошибке с советом добавить руками
        last_text = mock_tg.call_args_list[-1][0][1]
        assert "❌" in last_text or "недоступен" in last_text.lower() or "добавь" in last_text.lower()


# ---------------------------------------------------------------------------
# Test 8: compute_next_msk_hour — sleep until 09:00 MSK
# ---------------------------------------------------------------------------


def test_compute_next_msk_hour_before_target():
    """Если сейчас до 09:00 МСК — следующий запуск сегодня в 09:00."""
    from services.telemost_recorder_api.workers.morning_digest import compute_next_msk_hour

    # 07:00 МСК → следующий 09:00 МСК сегодня
    now_msk = datetime(2026, 5, 16, 7, 0, 0, tzinfo=_MSK)
    next_run = compute_next_msk_hour(9, _now_msk=now_msk)

    assert next_run.hour == 9
    assert next_run.minute == 0
    assert next_run.second == 0
    assert next_run.tzinfo is not None
    # Должен быть тот же день
    assert next_run.date() == now_msk.date()


def test_compute_next_msk_hour_after_target():
    """Если уже позже 09:00 МСК — следующий запуск завтра в 09:00."""
    from services.telemost_recorder_api.workers.morning_digest import compute_next_msk_hour

    # 10:00 МСК → следующий 09:00 МСК завтра
    now_msk = datetime(2026, 5, 16, 10, 0, 0, tzinfo=_MSK)
    next_run = compute_next_msk_hour(9, _now_msk=now_msk)

    assert next_run.hour == 9
    assert next_run.minute == 0
    assert next_run.date() > now_msk.date()


def test_compute_next_msk_hour_exactly_at_target():
    """Если ровно 09:00 МСК — следующий запуск завтра (уже сработало)."""
    from services.telemost_recorder_api.workers.morning_digest import compute_next_msk_hour

    now_msk = datetime(2026, 5, 16, 9, 0, 0, tzinfo=_MSK)
    next_run = compute_next_msk_hour(9, _now_msk=now_msk)

    assert next_run.date() > now_msk.date()
