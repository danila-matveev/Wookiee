"""Handler for voice:<candidate_id>:disabled callback — Phase 1 placeholder.

In Phase 1 all three voice-trigger buttons (Создать / Поправить / Игнор)
share the same disabled callback_data. This handler sends a friendly
placeholder explaining that Phase 2 is not yet active.

Phase 2 will replace this handler with real Bitrix write handlers.
"""
from __future__ import annotations

from services.telemost_recorder_api.telegram_client import tg_send_message

_PLACEHOLDER_TEXT = (
    "⏳ Voice-triggers Phase 2 ещё не активирован.\n\n"
    "Кнопки появились в саммари, но действия (создать задачу / встречу / заметку) "
    "пока недоступны. Они станут активными в следующем обновлении."
)


async def handle_voice_disabled(chat_id: int, candidate_id: str) -> None:
    """Send a Phase 2 placeholder message to the user.

    Args:
        chat_id:      Telegram chat to reply to.
        candidate_id: The candidate id extracted from callback_data (for logging).
    """
    await tg_send_message(chat_id, _PLACEHOLDER_TEXT, parse_mode=None)
