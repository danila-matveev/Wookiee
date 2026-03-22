"""Tests for structured_data extraction from tool call history."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from agents.oleg.executor.react_loop import AgentStep as ToolStep, AgentResult
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator


def _make_agent_result(*tool_calls: tuple) -> AgentResult:
    """Create AgentResult with given tool calls: (tool_name, result_dict)."""
    steps = []
    for name, result in tool_calls:
        steps.append(ToolStep(
            tool_name=name,
            tool_args={},
            tool_result=json.dumps(result, ensure_ascii=False),
            iteration=1,
        ))
    return AgentResult(content="markdown report", steps=steps)


def _make_orchestrator() -> OlegOrchestrator:
    """Create orchestrator with minimal config for testing."""
    return OlegOrchestrator(
        agents={},
        llm_client=MagicMock(),
        model="test",
    )


def test_extract_plan_vs_fact():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_plan_vs_fact", {"brand_total": {"metrics": {}}, "days_elapsed": 15}),
    )
    data = orch._extract_structured_data(result)
    assert "plan_vs_fact" in data
    assert data["plan_vs_fact"]["_source"] == "plan_vs_fact"
    assert data["plan_vs_fact"]["days_elapsed"] == 15


def test_extract_multiple_sources():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_brand_finance", {"brand": {"current": {"margin": 100}}}),
        ("get_plan_vs_fact", {"brand_total": {}, "days_elapsed": 10}),
        ("get_margin_levers", {"levers": {}, "waterfall": {}}),
    )
    data = orch._extract_structured_data(result)
    assert len(data) == 3
    assert "brand_finance" in data
    assert "plan_vs_fact" in data
    assert "margin_levers" in data


def test_extract_duplicate_tool_becomes_list():
    """When same tool called twice (WB + Ozon), results become a list."""
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_margin_levers", {"channel": "WB", "levers": {}}),
        ("get_margin_levers", {"channel": "OZON", "levers": {}}),
    )
    data = orch._extract_structured_data(result)
    assert isinstance(data["margin_levers"], list)
    assert len(data["margin_levers"]) == 2
    assert data["margin_levers"][0]["channel"] == "WB"


def test_extract_ignores_unknown_tools():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("validate_data_quality", {"status": "ok"}),
        ("search_knowledge_base", {"results": []}),
    )
    data = orch._extract_structured_data(result)
    assert data == {}


def test_extract_handles_malformed_json():
    orch = _make_orchestrator()
    steps = [ToolStep(
        tool_name="get_brand_finance",
        tool_args={},
        tool_result="not json at all",
        iteration=1,
    )]
    result = AgentResult(content="report", steps=steps)
    data = orch._extract_structured_data(result)
    assert data == {}
