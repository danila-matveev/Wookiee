"""Shared fixtures for Oleg v2 tests."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def mock_llm_client():
    """Mock OpenRouter LLM client."""
    client = AsyncMock()
    # Default: return a simple text response
    client.complete.return_value = {"content": "Test response"}
    # Default: return no tool calls (stop)
    client.complete_with_tools.return_value = {
        "content": "Analysis complete.",
        "tool_calls": [],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "finish_reason": "stop",
    }
    client.health_check.return_value = True
    return client


@pytest.fixture
def temp_sqlite_path():
    """Temporary SQLite database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_playbook(tmp_path):
    """Temporary playbook.md file."""
    playbook = tmp_path / "playbook.md"
    playbook.write_text(
        "# Playbook\n\n"
        "## Аналитические правила\n\n"
        "- Правило 1: всегда проверяй данные\n"
    )
    return str(playbook)


@pytest.fixture
def pricing():
    """Test pricing dict."""
    return {
        "test-model": {"input": 0.001, "output": 0.002},
    }
