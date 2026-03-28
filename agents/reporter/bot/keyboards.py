# agents/reporter/bot/keyboards.py
"""Inline keyboards for Telegram bot."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def playbook_review_keyboard(rule_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"rule:approve:{rule_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"rule:reject:{rule_id}"),
        ],
    ])
