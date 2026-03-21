"""Smoke tests for AdvisorAgent."""
import pytest
from unittest.mock import MagicMock

from agents.oleg.agents.advisor.agent import AdvisorAgent
from agents.oleg.agents.advisor.prompts import get_advisor_system_prompt


def test_advisor_agent_instantiation():
    mock_llm = MagicMock()
    agent = AdvisorAgent(mock_llm, "test-model")
    assert agent.agent_name == "advisor"


def test_advisor_system_prompt_not_empty():
    prompt = get_advisor_system_prompt()
    assert len(prompt) > 100
    assert "action_category" in prompt
    assert "оборачиваемости" in prompt.lower() or "маржинальност" in prompt.lower()


def test_advisor_tool_definitions_is_list():
    mock_llm = MagicMock()
    agent = AdvisorAgent(mock_llm, "test-model")
    tools = agent.get_tool_definitions()
    assert isinstance(tools, list)


def test_advisor_default_params():
    mock_llm = MagicMock()
    agent = AdvisorAgent(mock_llm, "test-model")
    assert agent.max_iterations == 5
    assert agent.total_timeout_sec == 90.0
