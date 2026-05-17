"""Callback handler for ``add_telemost:<bitrix_event_id>`` inline button.

Triggered when a user taps «➕ Добавить Telemost» in the morning digest.
Flow:
  1. Send an intermediate «⏳ Создаю комнату...» message.
  2. Create a Telemost conference via the Yandex API.
  3. Read the current Bitrix event to get owner_id + existing LOCATION.
  4. Append the join_url to LOCATION and update the event.
  5. Reply to the user with the new URL.

On Telemost API error: reply with a friendly error message so the user
can add the link manually (see SPEC §6.2).
"""
from __future__ import annotations

import logging

from services.telemost_recorder_api.bitrix_calendar import event_get_one, event_update
from services.telemost_recorder_api.telegram_client import tg_send_message
from shared.yandex_telemost import TelemostTokenExpired, create_conference

logger = logging.getLogger(__name__)

# Hard-coded host email per SPEC D6 + §3.1 / §4.3.
# Can be overridden via TELEMOST_HOST_EMAIL env var — see config.py extension.
_HOST_EMAIL = "recorder@wookiee.shop"


async def handle_add_telemost(
    *,
    chat_id: int,
    user_telegram_id: int,
    event_id: str,
) -> None:
    """Create a Telemost room and update the Bitrix event LOCATION.

    Args:
        chat_id: Telegram chat to send replies to.
        user_telegram_id: Telegram user ID for logging / future auth checks.
        event_id: Bitrix calendar event ID extracted from callback_data.
    """
    # Intermediate message — dismiss the button spinner for the user.
    await tg_send_message(chat_id, "⏳ Создаю комнату...")

    # --- Step 1: create Telemost conference ---
    try:
        conference = await create_conference(host_email=_HOST_EMAIL)
    except (TelemostTokenExpired, RuntimeError, Exception) as exc:
        logger.warning(
            "add_telemost: Telemost API error for event_id=%s user=%d: %s",
            event_id, user_telegram_id, exc,
        )
        await tg_send_message(
            chat_id,
            "❌ Telemost API недоступен, добавь ссылку руками.",
        )
        return

    # --- Step 2: read current event to get owner_id + LOCATION ---
    ev = await event_get_one(event_id)
    if ev is None:
        logger.warning(
            "add_telemost: Bitrix event %s not found for user=%d",
            event_id, user_telegram_id,
        )
        # We still have the URL — just send it without updating Bitrix.
        await tg_send_message(
            chat_id,
            f"✅ Создал ссылку, но не смог записать в Битрикс:\n{conference.join_url}",
        )
        return

    owner_id = str(ev.get("OWNER_ID") or ev.get("ownerId") or "").strip()
    current_location = (ev.get("LOCATION") or "").strip()
    new_location = f"{current_location}\n{conference.join_url}".strip()

    # --- Step 3: update Bitrix event LOCATION ---
    updated = await event_update(
        event_id=event_id,
        owner_id=owner_id,
        fields={"LOCATION": new_location},
    )
    if not updated:
        logger.warning(
            "add_telemost: Bitrix event_update failed for event_id=%s, "
            "still delivering URL to user",
            event_id,
        )

    # --- Step 4: notify user ---
    await tg_send_message(
        chat_id,
        f"✅ Добавил ссылку:\n{conference.join_url}\n\nПриду на встречу.",
    )
    logger.info(
        "add_telemost: event_id=%s join_url=%s user=%d bitrix_updated=%s",
        event_id, conference.join_url, user_telegram_id, updated,
    )
