"""Tests for OlegOrchestrator."""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
from agents.oleg.orchestrator.chain import ChainResult, AgentStep
from agents.oleg.executor.react_loop import AgentResult


@pytest.fixture
def mock_reporter():
    agent = AsyncMock()
    agent.agent_name = "reporter"
    agent.analyze.return_value = AgentResult(
        content="Revenue: 1M, margin: 25%.",
        total_cost=0.01,
        iterations=3,
    )
    return agent


@pytest.fixture
def mock_researcher():
    agent = AsyncMock()
    agent.agent_name = "researcher"
    agent.analyze.return_value = AgentResult(
        content="Hypothesis: logistics cost spike.",
        total_cost=0.02,
        iterations=2,
    )
    return agent


@pytest.mark.asyncio
async def test_daily_starts_with_reporter(mock_llm_client, mock_reporter, pricing):
    """Scheduled daily report always starts with reporter."""
    # LLM decides done=True after first step
    mock_llm_client.complete.return_value = {
        "content": json.dumps({"done": True, "reasoning": "enough data"}),
    }

    orchestrator = OlegOrchestrator(
        llm_client=mock_llm_client,
        model="test-model",
        agents={"reporter": mock_reporter},
        pricing=pricing,
    )

    result = await orchestrator.run_chain(task="Daily report", task_type="daily")
    assert isinstance(result, ChainResult)
    assert result.total_steps >= 1
    assert result.steps[0].agent == "reporter"


@pytest.mark.asyncio
async def test_single_agent_synthesizes_directly(mock_llm_client, mock_reporter, pricing):
    """With only reporter, skip LLM decision and use reporter output directly."""
    orchestrator = OlegOrchestrator(
        llm_client=mock_llm_client,
        model="test-model",
        agents={"reporter": mock_reporter},
        pricing=pricing,
    )

    result = await orchestrator.run_chain(task="Daily report", task_type="daily")
    # Single agent → shortcut → reporter output used directly
    assert "Revenue" in result.summary


@pytest.mark.asyncio
async def test_multi_step_chain(mock_llm_client, mock_reporter, mock_researcher, pricing):
    """Orchestrator runs reporter then researcher."""
    # After reporter step, LLM decides to call researcher
    mock_llm_client.complete.side_effect = [
        {"content": json.dumps({
            "done": False, "next_agent": "researcher",
            "instruction": "Investigate margin drop", "reasoning": "margin anomaly"
        })},
        {"content": json.dumps({
            "done": True, "reasoning": "enough data"
        })},
        # Synthesis call
        {"content": "Combined report: revenue + investigation."},
    ]

    orchestrator = OlegOrchestrator(
        llm_client=mock_llm_client,
        model="test-model",
        agents={"reporter": mock_reporter, "researcher": mock_researcher},
        pricing=pricing,
    )

    result = await orchestrator.run_chain(task="Daily report", task_type="daily")
    assert result.total_steps == 2
    assert result.steps[0].agent == "reporter"
    assert result.steps[1].agent == "researcher"


@pytest.mark.asyncio
async def test_decision_failure_defaults_to_done(mock_llm_client, mock_reporter, pricing):
    """If LLM decision fails, defaults to done=True and synthesizes."""
    mock_llm_client.complete.side_effect = Exception("LLM timeout")

    orchestrator = OlegOrchestrator(
        llm_client=mock_llm_client,
        model="test-model",
        agents={"reporter": mock_reporter, "researcher": AsyncMock()},
        pricing=pricing,
    )

    result = await orchestrator.run_chain(task="Daily report", task_type="daily")
    # Reporter ran (shortcut), then LLM decision failed → done
    assert result.total_steps >= 1
