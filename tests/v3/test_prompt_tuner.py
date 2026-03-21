"""Tests for prompt-tuner tool handlers."""
import json

import pytest
from unittest.mock import AsyncMock, patch

from agents.v3.state import StateStore
from agents.v3 import prompt_tuner


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons before each test."""
    prompt_tuner._state = None
    prompt_tuner._notion = None
    yield
    prompt_tuner._state = None
    prompt_tuner._notion = None


def _inject_state(state_store):
    """Inject a test StateStore into the module."""
    prompt_tuner._state = state_store


def _inject_notion(mock_notion):
    """Inject a mock Notion into the module."""
    prompt_tuner._notion = mock_notion


# ── get_notion_feedback ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_notion_feedback_returns_pages(mock_notion):
    """Should return feedback from Notion."""
    _inject_notion(mock_notion)
    mock_notion.enabled = True
    mock_notion.get_recent_feedback.return_value = [
        {"page_id": "p1", "page_title": "Report", "comments": [{"id": "c1", "text": "Fix this"}]}
    ]

    result = await prompt_tuner._handle_get_notion_feedback(days=7)
    assert result["total_pages"] == 1
    assert len(result["feedback"]) == 1
    mock_notion.get_recent_feedback.assert_called_once_with(days=7)


@pytest.mark.asyncio
async def test_get_notion_feedback_disabled(mock_notion):
    """Should return error when Notion not configured."""
    _inject_notion(mock_notion)
    mock_notion.enabled = False

    result = await prompt_tuner._handle_get_notion_feedback()
    assert "error" in result


# ── save_instruction ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_instruction_stores_in_state(state_store):
    """Should save instruction to StateStore."""
    _inject_state(state_store)

    result = await prompt_tuner._handle_save_instruction(
        agent_name="report-compiler",
        instruction="Показывай суммы в рублях",
        source_comment_id="c-1",
        source_page="Test Report",
    )

    assert result["status"] == "saved"
    assert result["active_instructions"] == 1

    raw = state_store.get("pi:report-compiler")
    instructions = json.loads(raw)
    assert len(instructions) == 1
    assert instructions[0]["instruction"] == "Показывай суммы в рублях"
    assert instructions[0]["active"] is True
    assert instructions[0]["source_comment_id"] == "c-1"


@pytest.mark.asyncio
async def test_save_instruction_fifo_eviction(state_store):
    """When max instructions reached, oldest should be deactivated."""
    _inject_state(state_store)

    # Pre-fill with 10 instructions
    existing = [
        {"instruction": f"instr_{i}", "source_comment_id": f"c-old-{i}",
         "source_page": "old", "created_at": f"2026-03-{10+i:02d}T08:00:00", "active": True}
        for i in range(10)
    ]
    state_store.set("pi:report-compiler", json.dumps(existing))

    result = await prompt_tuner._handle_save_instruction(
        agent_name="report-compiler",
        instruction="new instruction",
        source_comment_id="c-new",
    )

    assert result["status"] == "saved"
    assert result["active_instructions"] == 10  # still 10 (new one replaced oldest)

    raw = state_store.get("pi:report-compiler")
    instructions = json.loads(raw)
    assert instructions[0]["active"] is False  # oldest deactivated
    assert instructions[-1]["instruction"] == "new instruction"
    assert instructions[-1]["active"] is True


# ── deactivate_instruction ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deactivate_instruction_matches_and_deactivates(state_store):
    """Should find and deactivate matching instruction."""
    _inject_state(state_store)

    existing = [
        {"instruction": "Показывай суммы в рублях", "source_comment_id": "c-1",
         "source_page": "page", "created_at": "2026-03-19T08:00:00", "active": True}
    ]
    state_store.set("pi:report-compiler", json.dumps(existing))

    result = await prompt_tuner._handle_deactivate_instruction(
        agent_name="report-compiler",
        query="суммы в рублях",
    )

    assert result["status"] == "deactivated"
    assert "Показывай суммы в рублях" in result["deactivated_instruction"]

    raw = state_store.get("pi:report-compiler")
    instructions = json.loads(raw)
    assert instructions[0]["active"] is False


@pytest.mark.asyncio
async def test_deactivate_instruction_rejects_short_query(state_store):
    """Query shorter than 10 chars should be rejected."""
    _inject_state(state_store)

    result = await prompt_tuner._handle_deactivate_instruction(
        agent_name="report-compiler",
        query="short",
    )

    assert result["status"] == "error"


# ── mark_comment_processed ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_comment_processed(state_store):
    """Should add comment ID to processed list."""
    _inject_state(state_store)

    await prompt_tuner._handle_mark_comment_processed("c-1")
    await prompt_tuner._handle_mark_comment_processed("c-2")

    raw = state_store.get("pt:processed_ids")
    ids = json.loads(raw)
    assert "c-1" in ids
    assert "c-2" in ids


@pytest.mark.asyncio
async def test_mark_comment_processed_deduplicates(state_store):
    """Should not add duplicate IDs."""
    _inject_state(state_store)

    await prompt_tuner._handle_mark_comment_processed("c-1")
    await prompt_tuner._handle_mark_comment_processed("c-1")

    raw = state_store.get("pt:processed_ids")
    ids = json.loads(raw)
    assert ids.count("c-1") == 1


# ── reply_notion_comment ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reply_notion_comment(mock_notion):
    """Should post comment via Notion."""
    _inject_notion(mock_notion)
    mock_notion.enabled = True

    result = await prompt_tuner._handle_reply_notion_comment("page-1", "Hello")
    assert result["status"] == "posted"
    mock_notion.add_comment.assert_called_once_with("page-1", "Hello")


# ── get_active_instructions ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_active_instructions_by_agent(state_store):
    """Should return only active instructions for specified agent."""
    _inject_state(state_store)

    state_store.set("pi:report-compiler", json.dumps([
        {"instruction": "Active one", "active": True, "source_comment_id": "c1",
         "source_page": "p1", "created_at": "2026-03-20"},
        {"instruction": "Inactive one", "active": False, "source_comment_id": "c2",
         "source_page": "p2", "created_at": "2026-03-19"},
    ]))

    result = await prompt_tuner._handle_get_active_instructions(agent_name="report-compiler")
    assert result["count"] == 1
    assert result["instructions"][0]["instruction"] == "Active one"


@pytest.mark.asyncio
async def test_get_active_instructions_all(state_store):
    """Should return instructions across all agents when no filter."""
    _inject_state(state_store)

    state_store.set("pi:margin-analyst", json.dumps([
        {"instruction": "Margin rule", "active": True, "source_comment_id": "c1",
         "source_page": "p1", "created_at": "2026-03-20"},
    ]))
    state_store.set("pi:report-compiler", json.dumps([
        {"instruction": "Compiler rule", "active": True, "source_comment_id": "c2",
         "source_page": "p2", "created_at": "2026-03-20"},
    ]))

    result = await prompt_tuner._handle_get_active_instructions(agent_name="")
    assert result["total_active"] == 2
    assert "margin-analyst" in result["instructions_by_agent"]
    assert "report-compiler" in result["instructions_by_agent"]
