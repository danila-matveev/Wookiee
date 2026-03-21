"""Shared fixtures for v3 tests."""
import json
from unittest.mock import AsyncMock

import pytest

from agents.v3.state import StateStore


@pytest.fixture
def state_store(tmp_path):
    """Fresh SQLite StateStore in temp directory."""
    db_path = str(tmp_path / "test_state.db")
    return StateStore(db_path)


@pytest.fixture
def mock_notion():
    """Mock NotionDelivery with get_recent_feedback and add_comment."""
    notion = AsyncMock()
    notion.enabled = True
    notion.get_recent_feedback.return_value = []
    notion.add_comment.return_value = None
    return notion
