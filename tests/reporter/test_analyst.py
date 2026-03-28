# tests/reporter/test_analyst.py
"""Tests for LLM analyst with mocked OpenRouter."""
import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from agents.reporter.analyst.analyst import analyze
from agents.reporter.analyst.schemas import ReportInsights
from agents.reporter.collector.base import CollectedData, TopLevelMetrics
from agents.reporter.types import ReportScope, ReportType


def _scope():
    return ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )


def _collected_data():
    return CollectedData(
        scope=_scope().to_dict(),
        collected_at="2026-03-28T10:00:00",
        current=TopLevelMetrics(revenue_before_spp=500000, margin=100000),
        previous=TopLevelMetrics(revenue_before_spp=450000, margin=90000),
    )


def _mock_insights_json():
    return json.dumps({
        "executive_summary": "Выручка выросла на 11%",
        "sections": [{
            "section_id": 0,
            "title": "Паспорт",
            "summary": "Отчёт за 27.03.2026",
        }],
        "discovered_patterns": [],
        "overall_confidence": 0.85,
        "analysis_notes": [],
    })


@pytest.mark.asyncio
@patch("agents.reporter.analyst.analyst._call_llm")
async def test_analyze_returns_report_insights(mock_llm):
    mock_llm.return_value = {
        "content": _mock_insights_json(),
        "usage": {"input_tokens": 1000, "output_tokens": 500},
        "model": "google/gemini-2.5-flash",
    }
    insights, meta = await analyze(_collected_data(), _scope(), [])
    assert isinstance(insights, ReportInsights)
    assert insights.overall_confidence == 0.85
    assert meta["model"] == "google/gemini-2.5-flash"


@pytest.mark.asyncio
@patch("agents.reporter.analyst.analyst._call_llm")
async def test_analyze_fallback_on_failure(mock_llm):
    mock_llm.side_effect = [
        Exception("Primary failed"),
        {
            "content": _mock_insights_json(),
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "model": "openrouter/free",
        },
    ]
    insights, meta = await analyze(_collected_data(), _scope(), [])
    assert isinstance(insights, ReportInsights)
    assert mock_llm.call_count == 2
