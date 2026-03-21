import pytest
from agents.v3.conductor.messages import format_data_ready, format_alert
from agents.v3.conductor.schedule import ReportType


def test_format_data_ready_basic():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 0.68},
        pending=[ReportType.DAILY],
        report_date="20 марта",
    )
    assert "Данные за 20 марта готовы" in msg
    assert "WB" in msg
    assert "OZON" in msg
    assert "Daily фин" in msg


def test_format_data_ready_low_revenue_warning():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 0.68},
        pending=[ReportType.DAILY],
        report_date="20 марта",
    )
    assert "⚠️" in msg


def test_format_data_ready_multiple_reports():
    msg = format_data_ready(
        wb_info={"updated_at": "06:41", "orders": 1350, "revenue_ratio": 1.04},
        ozon_info={"updated_at": "07:06", "orders": 152, "revenue_ratio": 1.0},
        pending=[ReportType.DAILY, ReportType.WEEKLY, ReportType.MARKETING_WEEKLY],
        report_date="16 марта",
    )
    assert "Daily фин" in msg
    assert "Weekly фин" in msg
    assert "Weekly маркетинг" in msg


def test_format_alert_basic():
    msg = format_alert(
        report_type=ReportType.DAILY,
        reason="LLM timeout (OpenRouter 504)",
        attempt=3,
        max_attempts=3,
    )
    assert "Проблема" in msg
    assert "Daily фин" in msg
    assert "3/3" in msg
    assert "LLM timeout" in msg
