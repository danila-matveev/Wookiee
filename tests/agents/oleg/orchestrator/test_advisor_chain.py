"""Test advisor chain integration in orchestrator."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator


@pytest.fixture
def mock_orchestrator():
    llm = MagicMock()
    advisor = MagicMock()
    advisor.analyze = AsyncMock()
    validator = MagicMock()
    validator.analyze = AsyncMock()
    agents = {
        "reporter": MagicMock(),
        "advisor": advisor,
        "validator": validator,
    }
    orch = OlegOrchestrator(llm, "test-model", agents)
    return orch, advisor, validator


@pytest.mark.asyncio
async def test_advisor_chain_no_signals(mock_orchestrator):
    orch, advisor, validator = mock_orchestrator
    with patch("agents.oleg.orchestrator.orchestrator.detect_signals", return_value=[]):
        result = await orch._run_advisor_chain({}, "daily", [])
    assert result["recommendations"] == []
    advisor.analyze.assert_not_called()


@pytest.mark.asyncio
async def test_advisor_chain_pass(mock_orchestrator):
    orch, advisor, validator = mock_orchestrator
    from shared.signals.detector import Signal

    mock_signals = [Signal(
        id="test_1", type="margin_lags_orders", category="margin",
        severity="warning", impact_on="margin",
        data={"gap_pct": 7.8}, hint="Test", source="plan_vs_fact",
    )]

    advisor.analyze.return_value = MagicMock(
        content=json.dumps({"recommendations": [{"signal_id": "test_1", "action": "test"}]}),
        total_cost=0.01,
    )
    validator.analyze.return_value = MagicMock(
        content=json.dumps({"verdict": "pass", "checks": []}),
        total_cost=0.01,
    )

    with patch("agents.oleg.orchestrator.orchestrator.detect_signals", return_value=mock_signals):
        result = await orch._run_advisor_chain(
            {"_source": "plan_vs_fact"}, "daily", [],
        )

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["verified"] is True
