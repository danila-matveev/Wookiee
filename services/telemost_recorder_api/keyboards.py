"""Inline keyboard factories — single source of truth for bot navigation buttons.

Telegram inline keyboards are shown under the message they were sent with and
do not move with the user. We use them sparingly: on /start (main menu),
on auth failure (contact link), and as a tiny "help" hint on plain-text input.
All other commands rely on the persistent blue command menu (setMyCommands).
"""
from __future__ import annotations

WELCOME = {
    "inline_keyboard": [
        [
            {"text": "📋 Мои записи", "callback_data": "menu:list"},
            {"text": "▶ Активные", "callback_data": "menu:status"},
        ],
        [{"text": "❓ Что я умею", "callback_data": "menu:help"}],
    ]
}

AUTH_FAIL = {
    "inline_keyboard": [
        [{"text": "💬 Написать @matveev_danila", "url": "https://t.me/matveev_danila"}],
    ]
}

PLAIN_TEXT_HINT = {
    "inline_keyboard": [
        [{"text": "❓ Помощь", "callback_data": "menu:help"}],
    ]
}


def list_row_button(short_id: str, title: str, when_str: str) -> dict:
    """One row's button: '📝 Title (date)' → meet:<id>:show."""
    label = f"📝 {title} ({when_str})"
    if len(label) > 64:
        label = label[:61] + "..."
    return {"text": label, "callback_data": f"meet:{short_id}:show"}


def meeting_actions(short_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📄 Транскрипт", "callback_data": f"meet:{short_id}:transcript"},
                {"text": "🧾 Сводка", "callback_data": f"meet:{short_id}:summary"},
            ],
            [{"text": "🗑 Удалить", "callback_data": f"meet:{short_id}:delete"}],
        ]
    }


def confirm_delete(short_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да, удалить", "callback_data": f"meet:{short_id}:confirm_delete"},
                {"text": "↩ Отмена", "callback_data": f"meet:{short_id}:show"},
            ]
        ]
    }
