# tests/reporter/test_collector_marketing.py
"""Tests for MarketingCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch

from agents.reporter.collector.marketing import MarketingCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.MARKETING_WEEKLY,
        period_from=date(2026, 3, 23),
        period_to=date(2026, 3, 29),
        comparison_from=date(2026, 3, 16),
        comparison_to=date(2026, 3, 22),
    )


@patch("agents.reporter.collector.marketing.get_wb_finance", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_ozon_finance", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_wb_external_ad_breakdown", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_external_ad_breakdown", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_campaign_stats", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_model_ad_roi", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_model_ad_roi", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_organic_vs_paid_funnel", return_value=([], []))
@patch("agents.reporter.collector.marketing.get_wb_traffic_by_model", return_value=[])
@patch("agents.reporter.collector.marketing.get_wb_ad_daily_series", return_value=[])
@patch("agents.reporter.collector.marketing.get_ozon_ad_daily_series", return_value=[])
def test_marketing_collector_returns_collected_data(*mocks):
    collector = MarketingCollector()
    data = collector._collect_sync(_scope())
    assert data.scope["report_type"] == "marketing_weekly"
    assert isinstance(data.warnings, list)
