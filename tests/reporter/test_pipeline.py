# tests/reporter/test_pipeline.py
"""Tests for the full pipeline (all components mocked)."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.reporter.pipeline import run_pipeline
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _mock_state():
    state = MagicMock()
    state.create_run = MagicMock()
    state.update_run = MagicMock()
    state.get_active_rules = MagicMock(return_value=[])
    state.get_telegram_message_id = MagicMock(return_value=None)
    state.was_notified = MagicMock(return_value=False)
    state.mark_notified = MagicMock()
    state.save_pending_pattern = MagicMock()
    return state


@pytest.mark.asyncio
@patch("agents.reporter.pipeline.analyze")
@patch("agents.reporter.pipeline.upsert_notion", new_callable=AsyncMock)
@patch("agents.reporter.pipeline.send_or_edit_telegram", new_callable=AsyncMock)
@patch("agents.reporter.pipeline.send_error_notification", new_callable=AsyncMock)
async def test_pipeline_success(mock_err, mock_tg, mock_notion, mock_analyze):
    from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
    from agents.reporter.collector.base import CollectedData, TopLevelMetrics

    # Setup mocks — patch _COLLECTORS dict directly so the pipeline uses our mock
    mock_collector = MagicMock()
    mock_collector.collect = AsyncMock(return_value=CollectedData(
        scope=_scope().to_dict(), collected_at="",
        current=TopLevelMetrics(revenue_before_spp=500000),
        previous=TopLevelMetrics(revenue_before_spp=450000),
    ))
    mock_collector_cls = MagicMock(return_value=mock_collector)

    mock_analyze.return_value = (
        ReportInsights(
            executive_summary="Test",
            sections=[SectionInsight(section_id=i, title=f"S{i}", summary=f"Sum{i}") for i in range(13)],
            overall_confidence=0.85,
        ),
        {"model": "test", "input_tokens": 100, "output_tokens": 50},
    )
    mock_notion.return_value = "https://notion.so/page123"
    mock_tg.return_value = 42

    state = _mock_state()
    with patch("agents.reporter.pipeline._COLLECTORS", {"financial": mock_collector_cls}):
        result = await run_pipeline(_scope(), state)

    assert result.success is True
    assert result.notion_url == "https://notion.so/page123"
    assert result.telegram_message_id == 42
    state.update_run.assert_called()
