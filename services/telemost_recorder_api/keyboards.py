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
            [{"text": "📤 Выгрузить в Notion", "callback_data": f"meet:{short_id}:notion"}],
            [{"text": "🗑 Удалить", "callback_data": f"meet:{short_id}:delete"}],
        ]
    }


def empty_meeting_actions(short_id: str) -> dict:
    """Keyboard for an 'empty' meeting (никто не говорил).

    Only the delete button — transcript/summary/Notion are meaningless when
    there's no content, but leaving the row entirely buttonless meant the
    operator had no way to clear pollution from the list without DM-ing the
    bot. Uses the same `meet:<short_id>:delete` callback as meeting_actions
    so it flows through the existing confirm-delete handler.
    """
    return {
        "inline_keyboard": [
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


def voice_trigger_keyboard(candidate_id: str, intent: str | None = None) -> dict:
    """Three action buttons for a voice-trigger candidate.

    Phase 2 (T7): when ``intent`` is one of 'task' or 'meeting' AND the
    ``candidate_id`` looks like a UUID, callbacks are wired to the live
    handlers:

      ✅ Создать  → ``{intent}_create:<uuid>``
      ✏️ Поправить → ``{intent}_edit:<uuid>``
      ❌ Игнор    → ``{intent}_ignore:<uuid>``

    Legacy fallback (Phase 1 / tests / persistence failure): when ``intent``
    is missing or unsupported, all three buttons share ``voice:<id>:disabled``
    and the placeholder handler explains Phase 2 isn't active for this row.

    Args:
        candidate_id: UUID of the persisted candidate (Phase 2) or a short
            placeholder like ``task0`` (Phase 1).
        intent: 'task', 'meeting' — anything else degrades to placeholder.

    Returns:
        Telegram inline_keyboard dict with exactly 3 buttons on one row.
    """
    if intent in ("task", "meeting"):
        prefix = intent  # task_create / meeting_create
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Создать", "callback_data": f"{prefix}_create:{candidate_id}"},
                    {"text": "✏️ Поправить", "callback_data": f"{prefix}_edit:{candidate_id}"},
                    {"text": "❌ Игнор", "callback_data": f"{prefix}_ignore:{candidate_id}"},
                ]
            ]
        }

    # Phase 1 placeholder — all three buttons share the disabled callback.
    disabled_data = f"voice:{candidate_id}:disabled"
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Создать", "callback_data": disabled_data},
                {"text": "✏️ Поправить", "callback_data": disabled_data},
                {"text": "❌ Игнор", "callback_data": disabled_data},
            ]
        ]
    }


def digest_keyboard(needs_link_events: list[dict]) -> dict:
    """Inline keyboard for morning digest — one button per needs-link event.

    Each button has callback_data ``add_telemost:<bitrix_event_id>`` and
    is placed on its own row so the label stays readable.

    Args:
        needs_link_events: List of raw Bitrix event dicts that lack a
            Telemost URL and are real meetings (attendees≥2 or IS_MEETING).

    Returns:
        Telegram inline_keyboard dict ready for ``reply_markup`` parameter.
    """
    rows = []
    for ev in needs_link_events:
        event_id = str(ev.get("ID") or "").strip()
        name = (ev.get("NAME") or "Встреча").strip()
        label = f"➕ Добавить Telemost: {name}"
        if len(label) > 64:
            label = label[:61] + "..."
        rows.append([{"text": label, "callback_data": f"add_telemost:{event_id}"}])
    return {"inline_keyboard": rows}
