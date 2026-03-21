"""Test persistent instruction injection into orchestrator task_context."""
import json
import sys
from unittest.mock import MagicMock

import pytest

# Mock heavy dependencies before importing orchestrator
for mod in [
    "langchain_core", "langchain_core.messages", "langchain_core.tools",
    "langchain_openai", "langgraph", "langgraph.prebuilt",
    "services.observability.logger", "services.observability.version_tracker",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from agents.v3.state import StateStore
from agents.v3.orchestrator import load_persistent_instructions


@pytest.fixture
def state_with_instructions(tmp_path):
    """StateStore pre-loaded with persistent instructions."""
    db = str(tmp_path / "pi_test.db")
    state = StateStore(db)
    state.set("pi:margin-analyst", json.dumps([
        {"instruction": "Показывай маржу в рублях, а не процентах", "active": True,
         "source_comment_id": "c1", "source_page": "p1", "created_at": "2026-03-20"},
    ]))
    state.set("pi:report-compiler", json.dumps([
        {"instruction": "Добавь секцию рисков в конец", "active": True,
         "source_comment_id": "c2", "source_page": "p2", "created_at": "2026-03-20"},
        {"instruction": "Старая отменённая инструкция", "active": False,
         "source_comment_id": "c3", "source_page": "p3", "created_at": "2026-03-19"},
    ]))
    return state


def test_load_persistent_instructions_builds_note(state_with_instructions):
    """load_persistent_instructions should return formatted note with active instructions only."""
    note = load_persistent_instructions(
        state_with_instructions,
        ["margin-analyst", "revenue-decomposer", "ad-efficiency", "report-compiler"],
    )

    assert "ПОСТОЯННЫЕ ИНСТРУКЦИИ" in note
    assert "Показывай маржу в рублях" in note
    assert "Добавь секцию рисков" in note
    assert "Старая отменённая" not in note  # inactive, should be excluded


def test_load_persistent_instructions_empty_when_none(tmp_path):
    """Returns empty string when no instructions exist."""
    state = StateStore(str(tmp_path / "empty.db"))
    note = load_persistent_instructions(state, ["margin-analyst"])
    assert note == ""
