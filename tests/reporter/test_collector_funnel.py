# tests/reporter/test_collector_funnel.py
"""Tests for FunnelCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch

from agents.reporter.collector.funnel import FunnelCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FUNNEL_WEEKLY,
        period_from=date(2026, 3, 23),
        period_to=date(2026, 3, 29),
        comparison_from=date(2026, 3, 16),
        comparison_to=date(2026, 3, 22),
    )


@patch("agents.reporter.collector.funnel.get_wb_finance", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_ozon_finance", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_wb_article_funnel", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_article_funnel_wow", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_traffic", return_value=([], []))
@patch("agents.reporter.collector.funnel.get_ozon_traffic", return_value=[])
@patch("agents.reporter.collector.funnel.get_wb_seo_keyword_positions", return_value=[])
def test_funnel_collector_returns_collected_data(*mocks):
    collector = FunnelCollector()
    data = collector._collect_sync(_scope())
    assert data.scope["report_type"] == "funnel_weekly"
