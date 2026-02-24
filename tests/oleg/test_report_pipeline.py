"""Tests for ReportPipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.oleg.pipeline.report_pipeline import ReportPipeline
from agents.oleg.pipeline.report_types import ReportType, ReportRequest
from agents.oleg.pipeline.gate_checker import GateCheckResult, GateResult
from agents.oleg.orchestrator.chain import ChainResult, AgentStep


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.run_chain.return_value = ChainResult(
        summary="Test report summary.",
        detailed="Detailed report.",
        steps=[AgentStep(agent="reporter", instruction="test", result="ok",
                         cost_usd=0.01, duration_ms=500, iterations=2)],
        total_steps=1,
        total_cost=0.01,
        total_duration_ms=500,
        task_type="daily",
    )
    return orch


@pytest.fixture
def gate_checker_all_pass():
    gc = MagicMock()
    gc.check_all.return_value = GateCheckResult(
        gates=[
            GateResult(name="ETL", passed=True, is_hard=True),
            GateResult(name="Data", passed=True, is_hard=True),
            GateResult(name="Logistics", passed=True, is_hard=True),
            GateResult(name="Orders", passed=True, is_hard=False),
            GateResult(name="Revenue", passed=True, is_hard=False),
            GateResult(name="Margin", passed=True, is_hard=False),
        ],
        can_generate=True,
        has_caveats=False,
        caveats=[],
    )
    return gc


@pytest.fixture
def gate_checker_hard_fail():
    gc = MagicMock()
    gc.check_all.return_value = GateCheckResult(
        gates=[
            GateResult(name="ETL", passed=False, is_hard=True, detail="ETL not run"),
        ],
        can_generate=False,
        has_caveats=False,
        caveats=[],
    )
    return gc


@pytest.fixture
def gate_checker_soft_fail():
    gc = MagicMock()
    gc.check_all.return_value = GateCheckResult(
        gates=[
            GateResult(name="ETL", passed=True, is_hard=True),
            GateResult(name="Data", passed=True, is_hard=True),
            GateResult(name="Logistics", passed=True, is_hard=True),
            GateResult(name="Orders", passed=False, is_hard=False, detail="No orders data"),
        ],
        can_generate=True,
        has_caveats=True,
        caveats=["No orders data"],
    )
    return gc


@pytest.mark.asyncio
async def test_hard_gate_fail_returns_none(mock_orchestrator, gate_checker_hard_fail):
    """Hard gate failure → pipeline returns None."""
    pipeline = ReportPipeline(
        orchestrator=mock_orchestrator,
        gate_checker=gate_checker_hard_fail,
    )

    request = ReportRequest(
        report_type=ReportType.DAILY,
        start_date="2026-02-23",
        end_date="2026-02-23",
    )

    result = await pipeline.generate_report(request)
    assert result is None
    mock_orchestrator.run_chain.assert_not_called()


@pytest.mark.asyncio
async def test_soft_gate_fail_returns_caveats(mock_orchestrator, gate_checker_soft_fail):
    """Soft gate failure → report with caveats."""
    pipeline = ReportPipeline(
        orchestrator=mock_orchestrator,
        gate_checker=gate_checker_soft_fail,
    )

    request = ReportRequest(
        report_type=ReportType.DAILY,
        start_date="2026-02-23",
        end_date="2026-02-23",
    )

    result = await pipeline.generate_report(request)
    assert result is not None
    assert result.caveats == ["No orders data"]
    assert result.brief_summary == "Test report summary."


@pytest.mark.asyncio
async def test_full_success(mock_orchestrator, gate_checker_all_pass):
    """All gates pass → full report, no caveats."""
    pipeline = ReportPipeline(
        orchestrator=mock_orchestrator,
        gate_checker=gate_checker_all_pass,
    )

    request = ReportRequest(
        report_type=ReportType.DAILY,
        start_date="2026-02-23",
        end_date="2026-02-23",
    )

    result = await pipeline.generate_report(request)
    assert result is not None
    assert result.caveats == []
    assert result.brief_summary == "Test report summary."
    assert result.cost_usd == 0.01


@pytest.mark.asyncio
async def test_query_bypasses_gates(mock_orchestrator, gate_checker_hard_fail):
    """User queries bypass gate checks."""
    pipeline = ReportPipeline(
        orchestrator=mock_orchestrator,
        gate_checker=gate_checker_hard_fail,
    )

    request = ReportRequest(
        report_type=ReportType.QUERY,
        start_date="2026-02-23",
        end_date="2026-02-23",
        user_query="What was revenue yesterday?",
    )

    result = await pipeline.generate_report(request)
    assert result is not None  # Gates not checked for queries
