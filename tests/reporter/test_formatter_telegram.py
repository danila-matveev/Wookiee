# tests/reporter/test_formatter_telegram.py
"""Tests for Telegram HTML formatter."""
from datetime import date

from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
from agents.reporter.collector.base import CollectedData, TopLevelMetrics
from agents.reporter.formatter.telegram import render_telegram
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def test_render_telegram_basic():
    html = render_telegram(
        insights=ReportInsights(
            executive_summary="Выручка выросла на 11%",
            sections=[],
            overall_confidence=0.85,
        ),
        data=CollectedData(
            scope=_scope().to_dict(),
            collected_at="2026-03-28T10:00:00",
            current=TopLevelMetrics(revenue_before_spp=500000, margin=100000, margin_pct=20.0, orders_count=120),
            previous=TopLevelMetrics(revenue_before_spp=450000, margin=90000, margin_pct=20.0, orders_count=110),
        ),
        scope=_scope(),
    )
    assert "Дневной фин. отчёт" in html
    assert "500 000" in html
    assert "🟢" in html  # confidence 0.85 >= 0.8


def test_render_telegram_with_notion_url():
    html = render_telegram(
        insights=ReportInsights(executive_summary="Test", sections=[], overall_confidence=0.5),
        data=CollectedData(
            scope=_scope().to_dict(), collected_at="",
            current=TopLevelMetrics(), previous=TopLevelMetrics(),
        ),
        scope=_scope(),
        notion_url="https://notion.so/page123",
    )
    assert "notion.so/page123" in html
    assert "🟡" in html  # confidence 0.5


def test_render_telegram_max_length():
    long_summary = "A" * 5000
    html = render_telegram(
        insights=ReportInsights(executive_summary=long_summary, sections=[], overall_confidence=0.9),
        data=CollectedData(
            scope=_scope().to_dict(), collected_at="",
            current=TopLevelMetrics(), previous=TopLevelMetrics(),
        ),
        scope=_scope(),
    )
    assert len(html) <= 4000
