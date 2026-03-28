# tests/reporter/test_types.py
"""Tests for ReportType, ReportScope, compute_scope, get_today_reports."""
from datetime import date

from agents.reporter.types import (
    ReportScope,
    ReportType,
    compute_scope,
    get_today_reports,
)


def test_report_type_collector_kind():
    assert ReportType.FINANCIAL_DAILY.collector_kind == "financial"
    assert ReportType.MARKETING_WEEKLY.collector_kind == "marketing"
    assert ReportType.FUNNEL_MONTHLY.collector_kind == "funnel"


def test_report_type_period_kind():
    assert ReportType.FINANCIAL_DAILY.period_kind == "daily"
    assert ReportType.FINANCIAL_WEEKLY.period_kind == "weekly"
    assert ReportType.FINANCIAL_MONTHLY.period_kind == "monthly"


def test_scope_hash_deterministic():
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    assert scope.scope_hash == scope.scope_hash
    assert len(scope.scope_hash) == 12


def test_scope_hash_differs_with_marketplace():
    base = dict(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    s1 = ReportScope(**base, marketplace="wb")
    s2 = ReportScope(**base, marketplace="ozon")
    assert s1.scope_hash != s2.scope_hash


def test_compute_scope_daily():
    scope = compute_scope(ReportType.FINANCIAL_DAILY, date(2026, 3, 28))
    assert scope.period_from == date(2026, 3, 27)
    assert scope.period_to == date(2026, 3, 27)
    assert scope.comparison_from == date(2026, 3, 26)
    assert scope.comparison_to == date(2026, 3, 26)


def test_compute_scope_weekly():
    # Monday March 30 2026
    scope = compute_scope(ReportType.FINANCIAL_WEEKLY, date(2026, 3, 30))
    assert scope.period_from == date(2026, 3, 23)  # last Monday
    assert scope.period_to == date(2026, 3, 29)    # last Sunday
    assert scope.comparison_from == date(2026, 3, 16)
    assert scope.comparison_to == date(2026, 3, 22)


def test_compute_scope_monthly():
    scope = compute_scope(ReportType.FINANCIAL_MONTHLY, date(2026, 4, 6))
    assert scope.period_from == date(2026, 3, 1)
    assert scope.period_to == date(2026, 3, 31)
    assert scope.comparison_from == date(2026, 2, 1)
    assert scope.comparison_to == date(2026, 2, 28)


def test_get_today_reports_tuesday():
    reports = get_today_reports(date(2026, 3, 24))  # Tuesday
    assert reports == [ReportType.FINANCIAL_DAILY]


def test_get_today_reports_monday():
    reports = get_today_reports(date(2026, 3, 30))  # Monday, not first of month
    assert ReportType.FINANCIAL_WEEKLY in reports
    assert ReportType.MARKETING_WEEKLY in reports
    assert ReportType.FUNNEL_WEEKLY in reports
    assert ReportType.FINANCIAL_MONTHLY not in reports


def test_get_today_reports_first_monday():
    reports = get_today_reports(date(2026, 4, 6))  # First Monday of April
    assert ReportType.FINANCIAL_MONTHLY in reports
    assert ReportType.MARKETING_MONTHLY in reports
    assert ReportType.FUNNEL_MONTHLY in reports


def test_scope_to_dict_roundtrip():
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
        marketplace="wb",
        model="wendy",
    )
    d = scope.to_dict()
    assert d["marketplace"] == "wb"
    assert d["model"] == "wendy"
    assert d["report_type"] == "financial_daily"
