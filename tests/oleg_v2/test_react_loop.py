"""Tests for ReactLoop."""
import pytest
from unittest.mock import AsyncMock

from agents.oleg_v2.executor.react_loop import ReactLoop
from agents.oleg_v2.executor.circuit_breaker import CircuitBreaker


@pytest.mark.asyncio
async def test_simple_run_no_tools(mock_llm_client, pricing):
    """LLM returns text without tool calls → single iteration."""
    mock_llm_client.complete_with_tools.return_value = {
        "content": "Here is my analysis.",
        "tool_calls": [],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        "finish_reason": "stop",
    }

    loop = ReactLoop(
        llm_client=mock_llm_client,
        model="test-model",
        tool_definitions=[],
        tool_executor=AsyncMock(),
        pricing=pricing,
        max_iterations=5,
    )

    result = await loop.run(
        system_prompt="You are a test agent.",
        user_message="Analyze something.",
    )

    assert result.content == "Here is my analysis."
    assert result.iterations >= 1
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_tool_call_and_response(mock_llm_client, pricing):
    """LLM calls a tool, gets result, then responds."""
    # First call: tool call
    mock_llm_client.complete_with_tools.side_effect = [
        {
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "get_data", "arguments": {"key": "value"}}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            "finish_reason": "tool_calls",
        },
        # Second call: final response
        {
            "content": "Based on the data: everything is fine.",
            "tool_calls": [],
            "usage": {"prompt_tokens": 200, "completion_tokens": 50},
            "finish_reason": "stop",
        },
    ]

    tool_executor = AsyncMock(return_value='{"result": "ok"}')

    loop = ReactLoop(
        llm_client=mock_llm_client,
        model="test-model",
        tool_definitions=[{"type": "function", "function": {"name": "get_data"}}],
        tool_executor=tool_executor,
        pricing=pricing,
        max_iterations=5,
    )

    result = await loop.run(
        system_prompt="You are a test agent.",
        user_message="Get data.",
    )

    assert "Based on the data" in result.content
    assert len(result.steps) == 1
    assert result.steps[0].tool_name == "get_data"


@pytest.mark.asyncio
async def test_circuit_breaker_blocks(mock_llm_client, pricing):
    """Circuit breaker open → immediate abort."""
    cb = CircuitBreaker(failure_threshold=1, cooldown_sec=60.0)
    cb.record_failure()  # Opens circuit

    loop = ReactLoop(
        llm_client=mock_llm_client,
        model="test-model",
        tool_definitions=[],
        tool_executor=AsyncMock(),
        pricing=pricing,
        max_iterations=5,
        circuit_breaker=cb,
    )

    result = await loop.run(
        system_prompt="Test",
        user_message="Test",
    )

    assert result.finish_reason == "circuit_breaker"
    assert "circuit breaker" in result.content.lower() or "недоступен" in result.content


@pytest.mark.asyncio
async def test_max_iterations(mock_llm_client, pricing):
    """Reaches max iterations → partial result."""
    # Always return tool calls → never finishes naturally
    mock_llm_client.complete_with_tools.return_value = {
        "content": "",
        "tool_calls": [
            {"id": "call_x", "name": "loop_tool", "arguments": {}}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
        "finish_reason": "tool_calls",
    }

    tool_executor = AsyncMock(return_value='{"ok": true}')

    loop = ReactLoop(
        llm_client=mock_llm_client,
        model="test-model",
        tool_definitions=[{"type": "function", "function": {"name": "loop_tool"}}],
        tool_executor=tool_executor,
        pricing=pricing,
        max_iterations=3,
        total_timeout_sec=60.0,
    )

    result = await loop.run(
        system_prompt="Test",
        user_message="Test",
    )

    assert result.iterations == 3
    assert result.finish_reason == "max_iterations"
