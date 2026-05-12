"""Inline keyboard factories for per-meeting actions."""
from __future__ import annotations

from services.telemost_recorder_api.keyboards import (
    confirm_delete,
    list_row_button,
    meeting_actions,
)


def test_list_row_button_contains_callback():
    btn = list_row_button(short_id="abcdef12", title="Daily sync", when_str="12.05 10:00")
    assert btn["text"].startswith("✅") or "📝" in btn["text"]
    assert "Daily sync" in btn["text"]
    assert "12.05 10:00" in btn["text"]
    assert btn["callback_data"] == "meet:abcdef12:show"


def test_meeting_actions_has_3_buttons():
    kb = meeting_actions(short_id="abcdef12")
    flat = [b for row in kb["inline_keyboard"] for b in row]
    cbs = [b["callback_data"] for b in flat]
    assert "meet:abcdef12:transcript" in cbs
    assert "meet:abcdef12:summary" in cbs
    assert "meet:abcdef12:delete" in cbs


def test_confirm_delete_has_yes_and_no():
    kb = confirm_delete(short_id="abcdef12")
    flat = [b for row in kb["inline_keyboard"] for b in row]
    cbs = [b["callback_data"] for b in flat]
    assert "meet:abcdef12:confirm_delete" in cbs
    assert "meet:abcdef12:show" in cbs  # cancel returns to show
