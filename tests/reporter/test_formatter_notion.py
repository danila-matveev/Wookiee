# tests/reporter/test_formatter_notion.py
"""Tests for Notion markdown formatter."""
from datetime import date

from agents.reporter.analyst.schemas import ReportInsights, SectionInsight
from agents.reporter.collector.base import CollectedData, TopLevelMetrics, ModelMetrics
from agents.reporter.formatter.notion import render_notion
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _data():
    return CollectedData(
        scope=_scope().to_dict(),
        collected_at="2026-03-28T10:00:00",
        current=TopLevelMetrics(
            revenue_before_spp=500000, margin=100000, margin_pct=20.0,
            orders_count=120, drr_pct=8.0,
        ),
        previous=TopLevelMetrics(
            revenue_before_spp=450000, margin=90000, margin_pct=20.0,
            orders_count=110, drr_pct=7.5,
        ),
        model_breakdown=[
            ModelMetrics(model="wendy", rank=1,
                        metrics=TopLevelMetrics(revenue_before_spp=250000, margin=50000, margin_pct=20.0),
                        prev_metrics=TopLevelMetrics(revenue_before_spp=220000, margin=44000, margin_pct=20.0)),
        ],
    )


def _insights():
    return ReportInsights(
        executive_summary="Выручка выросла на 11%",
        sections=[
            SectionInsight(section_id=i, title=f"Section {i}", summary=f"Summary {i}")
            for i in range(13)
        ],
        overall_confidence=0.85,
    )


def test_render_notion_contains_toggle_sections():
    md = render_notion(_insights(), _data(), _scope())
    assert "## ▶ 0. Паспорт отчёта" in md
    assert "## ▶ 1. Executive Summary" in md
    assert "## ▶ 12. Техническая информация" in md


def test_render_notion_contains_metrics():
    md = render_notion(_insights(), _data(), _scope())
    assert "500 000" in md or "500000" in md
    assert "wendy" in md


def test_render_notion_contains_executive_summary():
    md = render_notion(_insights(), _data(), _scope())
    assert "Выручка выросла на 11%" in md
