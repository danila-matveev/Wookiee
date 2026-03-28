# tests/reporter/test_state.py
"""Tests for Supabase state manager (mocked)."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.state import ReporterState
from agents.reporter.types import ReportScope, ReportType


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    client.table = MagicMock(return_value=client)
    client.insert = MagicMock(return_value=client)
    client.upsert = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.execute = MagicMock(return_value=MagicMock(data=[]))
    return client


@pytest.fixture
def scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def test_create_run(mock_supabase, scope):
    state = ReporterState(client=mock_supabase)
    run_id = state.create_run(scope)
    mock_supabase.table.assert_called_with("report_runs")
    assert mock_supabase.upsert.called


def test_update_run(mock_supabase, scope):
    state = ReporterState(client=mock_supabase)
    state.update_run(scope, status="success", confidence=0.85)
    mock_supabase.table.assert_called_with("report_runs")


def test_was_notified(mock_supabase):
    mock_supabase.execute.return_value = MagicMock(data=[])
    state = ReporterState(client=mock_supabase)
    result = state.was_notified("error:financial_daily:2026-03-28")
    assert result is False


def test_was_notified_true(mock_supabase):
    mock_supabase.execute.return_value = MagicMock(data=[{"id": "123"}])
    state = ReporterState(client=mock_supabase)
    result = state.was_notified("error:financial_daily:2026-03-28")
    assert result is True
