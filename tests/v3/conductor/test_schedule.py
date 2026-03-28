import pytest
from datetime import date

from agents.v3.conductor.schedule import get_today_reports, ReportType


def test_regular_day_returns_daily():
    # 2026-03-19 is Thursday
    result = get_today_reports(date(2026, 3, 19))
    assert result == [ReportType.DAILY]


def test_monday_returns_weekly_reports():
    # 2026-03-16 is Monday
    result = get_today_reports(date(2026, 3, 16))
    assert ReportType.DAILY in result
    assert ReportType.WEEKLY in result
    assert ReportType.MARKETING_WEEKLY in result
    assert ReportType.FUNNEL_WEEKLY in result
    assert ReportType.PRICE_WEEKLY in result


def test_friday_returns_only_daily():
    # 2026-03-20 is Friday — finolog_weekly was removed from conductor (runs standalone via finolog-cron)
    result = get_today_reports(date(2026, 3, 20))
    assert result == [ReportType.DAILY]


def test_first_monday_of_month_includes_monthly():
    # 2026-04-06 is first Monday of April
    result = get_today_reports(date(2026, 4, 6))
    assert ReportType.MONTHLY in result
    assert ReportType.MARKETING_MONTHLY in result
    assert ReportType.PRICE_MONTHLY in result
    assert ReportType.WEEKLY in result


def test_second_monday_no_monthly():
    # 2026-03-09 is second Monday
    result = get_today_reports(date(2026, 3, 9))
    assert ReportType.WEEKLY in result
    assert ReportType.MONTHLY not in result


def test_weekend_only_daily():
    # 2026-03-21 is Saturday
    result = get_today_reports(date(2026, 3, 21))
    assert result == [ReportType.DAILY]


def test_report_type_to_orchestrator_method():
    """Each ReportType must map to an orchestrator function name."""
    for rt in ReportType:
        assert rt.orchestrator_method is not None
        assert rt.notion_label is not None
