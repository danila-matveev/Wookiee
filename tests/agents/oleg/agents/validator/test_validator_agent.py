"""Smoke tests for ValidatorAgent."""
from unittest.mock import MagicMock
from agents.oleg.agents.validator.agent import ValidatorAgent
from agents.oleg.agents.validator.prompts import get_validator_system_prompt


def test_validator_agent_instantiation():
    mock_llm = MagicMock()
    agent = ValidatorAgent(mock_llm, "test-model")
    assert agent.agent_name == "validator"


def test_validator_system_prompt_contains_checks():
    prompt = get_validator_system_prompt()
    assert "check_numbers" in prompt or "validate_numbers" in prompt
    assert "verdict" in prompt


def test_validator_has_4_tools():
    mock_llm = MagicMock()
    agent = ValidatorAgent(mock_llm, "test-model")
    tools = agent.get_tool_definitions()
    assert len(tools) == 4
    tool_names = {t["function"]["name"] for t in tools}
    assert tool_names == {"validate_numbers", "validate_coverage", "validate_direction", "validate_kb_rules"}
