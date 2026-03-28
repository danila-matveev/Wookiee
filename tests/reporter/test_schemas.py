# tests/reporter/test_schemas.py
"""Tests for Pydantic schema validation."""
from agents.reporter.analyst.schemas import (
    DiscoveredPattern,
    MetricChange,
    ReportInsights,
    RootCause,
    SectionInsight,
)


def test_metric_change_valid():
    mc = MetricChange(
        metric="revenue",
        current=1_000_000,
        previous=900_000,
        delta_pct=11.1,
        direction="up",
    )
    assert mc.metric == "revenue"


def test_section_insight_defaults():
    si = SectionInsight(
        section_id=1,
        title="Executive Summary",
        summary="Тестовый раздел",
    )
    assert si.key_changes == []
    assert si.root_causes == []
    assert si.anomalies == []


def test_report_insights_full():
    ri = ReportInsights(
        executive_summary="Выручка выросла на 11%",
        sections=[
            SectionInsight(
                section_id=0,
                title="Паспорт",
                summary="Период: 27.03.2026",
            ),
        ],
        discovered_patterns=[
            DiscoveredPattern(
                pattern="ДРР > 20% коррелирует с падением маржи",
                evidence="Wendy: DRR 22%, margin -6%",
                suggested_action="Снизить ставки",
                confidence=0.8,
            ),
        ],
        overall_confidence=0.85,
    )
    assert len(ri.sections) == 1
    assert len(ri.discovered_patterns) == 1
    assert ri.overall_confidence == 0.85


def test_report_insights_json_schema():
    schema = ReportInsights.model_json_schema()
    assert "properties" in schema
    assert "executive_summary" in schema["properties"]
    assert "sections" in schema["properties"]
