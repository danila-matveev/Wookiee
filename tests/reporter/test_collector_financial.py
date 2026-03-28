# tests/reporter/test_collector_financial.py
"""Tests for FinancialCollector with mocked data_layer."""
from datetime import date
from unittest.mock import patch, MagicMock

from agents.reporter.collector.financial import FinancialCollector
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _mock_wb_finance():
    """Simulate get_wb_finance return: (abc_rows, orders_rows)."""
    abc_rows = [
        # period, sales_count, revenue_before_spp, spp_amount, revenue_after_spp,
        # adv_internal, adv_vk, adv_bloggers, adv_creators, cost_of_goods,
        # logistics, storage, commission, margin, nds, orders_count, orders_rub
        ("current", 100, 500000, 50000, 450000, 30000, 5000, 3000, 2000,
         150000, 40000, 10000, 25000, 135000, 0, 120, 600000),
        ("previous", 90, 450000, 45000, 405000, 25000, 4000, 2000, 1000,
         135000, 38000, 9000, 22000, 129000, 0, 110, 540000),
    ]
    orders_rows = [
        ("current", 120, 600000),
        ("previous", 110, 540000),
    ]
    return abc_rows, orders_rows


def _mock_wb_by_model():
    return [
        ("current", "wendy", 50, 250000, 15000, 3000, 70000, 75000),
        ("previous", "wendy", 45, 220000, 12000, 2000, 63000, 68000),
        ("current", "vuki", 30, 150000, 10000, 1000, 40000, 50000),
        ("previous", "vuki", 28, 140000, 9000, 800, 38000, 47000),
    ]


@patch("agents.reporter.collector.financial.get_wb_finance")
@patch("agents.reporter.collector.financial.get_ozon_finance")
@patch("agents.reporter.collector.financial.get_wb_by_model")
@patch("agents.reporter.collector.financial.get_ozon_by_model")
@patch("agents.reporter.collector.financial.get_wb_daily_series")
@patch("agents.reporter.collector.financial.get_ozon_daily_series")
@patch("agents.reporter.collector.financial.get_wb_avg_stock")
@patch("agents.reporter.collector.financial.get_ozon_avg_stock")
@patch("agents.reporter.collector.financial.get_wb_turnover_by_model")
@patch("agents.reporter.collector.financial.get_wb_price_changes")
@patch("agents.reporter.collector.financial.get_wb_external_ad_breakdown")
@patch("agents.reporter.collector.financial.validate_wb_data_quality")
def test_financial_collector_daily(
    mock_quality, mock_ad_breakdown, mock_price_changes,
    mock_turnover, mock_ozon_stock, mock_wb_stock,
    mock_ozon_series, mock_wb_series,
    mock_ozon_model, mock_wb_model,
    mock_ozon_finance, mock_wb_finance,
):
    mock_wb_finance.return_value = _mock_wb_finance()
    mock_ozon_finance.return_value = ([], [])
    mock_wb_model.return_value = _mock_wb_by_model()
    mock_ozon_model.return_value = []
    mock_wb_series.return_value = []
    mock_ozon_series.return_value = []
    mock_wb_stock.return_value = {}
    mock_ozon_stock.return_value = {}
    mock_turnover.return_value = {}
    mock_price_changes.return_value = []
    mock_ad_breakdown.return_value = []
    mock_quality.return_value = {"warnings": []}

    collector = FinancialCollector()
    data = collector._collect_sync(_scope())

    assert data.current.revenue_before_spp == 500000
    assert data.previous.revenue_before_spp == 450000
    assert len(data.marketplace_breakdown) >= 1
    assert len(data.model_breakdown) >= 1
    assert data.model_breakdown[0].model == "wendy"
