# tests/reporter/test_conductor.py
"""Tests for conductor orchestration."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.conductor import data_ready_check, deadline_check


@pytest.mark.asyncio
@patch("agents.reporter.conductor.run_pipeline", new_callable=AsyncMock)
@patch("agents.reporter.conductor.send_data_ready_notification", new_callable=AsyncMock)
async def test_data_ready_generates_pending_reports(mock_notify, mock_pipeline):
    from agents.reporter.pipeline import PipelineResult

    mock_pipeline.return_value = PipelineResult(success=True)

    gate_checker = MagicMock()
    gate_result = MagicMock()
    gate_result.can_generate = True
    gate_result.gates = []
    gate_checker.check_both.return_value = gate_result

    state = MagicMock()
    state.get_successful_today.return_value = set()
    state.get_attempt_count.return_value = 0

    await data_ready_check(gate_checker, state, today=date(2026, 3, 24))  # Tuesday
    mock_pipeline.assert_called_once()  # Only FINANCIAL_DAILY on Tuesday


@pytest.mark.asyncio
@patch("agents.reporter.conductor.run_pipeline", new_callable=AsyncMock)
@patch("agents.reporter.conductor.send_data_ready_notification", new_callable=AsyncMock)
async def test_data_ready_skips_done_reports(mock_notify, mock_pipeline):
    gate_checker = MagicMock()
    gate_result = MagicMock()
    gate_result.can_generate = True
    gate_result.gates = []
    gate_checker.check_both.return_value = gate_result

    state = MagicMock()
    state.get_successful_today.return_value = {"financial_daily"}  # Already done
    state.get_attempt_count.return_value = 0

    await data_ready_check(gate_checker, state, today=date(2026, 3, 24))
    mock_pipeline.assert_not_called()


@pytest.mark.asyncio
@patch("agents.reporter.conductor.send_error_notification", new_callable=AsyncMock)
async def test_deadline_alerts_missing_daily(mock_notify):
    state = MagicMock()
    state.get_successful_today.return_value = set()  # Nothing done

    await deadline_check(state, today=date(2026, 3, 28))
    mock_notify.assert_called_once()
