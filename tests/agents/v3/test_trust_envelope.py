"""Tests for Trust Envelope and Cost Tracking."""
import pytest


# --- Cost Calculation ---

def test_calc_cost_known_model():
    from agents.v3.config import calc_cost
    # z-ai/glm-4.7: input=0.00006/1K, output=0.0004/1K
    cost = calc_cost(
        model="z-ai/glm-4.7",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    # 1000/1000 * 0.00006 + 500/1000 * 0.0004 = 0.00006 + 0.0002 = 0.00026
    assert cost == pytest.approx(0.00026, abs=1e-6)


def test_calc_cost_unknown_model_uses_default():
    from agents.v3.config import calc_cost
    cost = calc_cost(
        model="unknown/model",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    # default: input=0.001, output=0.001
    # 1000/1000 * 0.001 + 1000/1000 * 0.001 = 0.002
    assert cost == pytest.approx(0.002, abs=1e-6)


def test_calc_cost_zero_tokens():
    from agents.v3.config import calc_cost
    assert calc_cost("z-ai/glm-4.7", 0, 0) == 0.0


# --- Token Extraction ---

def test_extract_usage_from_ai_messages():
    """Verify we sum token usage across all AIMessages in a ReAct chain."""
    from agents.v3.runner import extract_token_usage
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    messages = [
        HumanMessage(content="query"),
        AIMessage(
            content="thinking...",
            response_metadata={"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}},
        ),
        ToolMessage(content="tool result", tool_call_id="1"),
        AIMessage(
            content="final answer",
            response_metadata={"token_usage": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280}},
        ),
    ]
    usage = extract_token_usage(messages)
    assert usage["prompt_tokens"] == 300
    assert usage["completion_tokens"] == 130
    assert usage["total_tokens"] == 430


def test_extract_usage_no_metadata():
    """If no response_metadata, return zeros."""
    from agents.v3.runner import extract_token_usage
    from langchain_core.messages import AIMessage

    messages = [AIMessage(content="answer")]
    usage = extract_token_usage(messages)
    assert usage["prompt_tokens"] == 0
    assert usage["completion_tokens"] == 0
    assert usage["total_tokens"] == 0


def test_extract_usage_empty_messages():
    from agents.v3.runner import extract_token_usage
    usage = extract_token_usage([])
    assert usage["total_tokens"] == 0


# --- Meta Sanity Check ---

def test_sanitize_meta_low_coverage_caps_confidence():
    from agents.v3.runner import sanitize_meta
    meta = {"confidence": 0.9, "data_coverage": 0.3, "limitations": []}
    sanitize_meta(meta)
    assert meta["confidence"] <= 0.5
    assert "data_coverage < 50%" in meta["limitations"][0]


def test_sanitize_meta_ok_coverage_keeps_confidence():
    from agents.v3.runner import sanitize_meta
    meta = {"confidence": 0.9, "data_coverage": 0.8, "limitations": []}
    sanitize_meta(meta)
    assert meta["confidence"] == 0.9
    assert meta["limitations"] == []


def test_sanitize_meta_missing_fields_no_mutation():
    from agents.v3.runner import sanitize_meta
    meta = {}
    sanitize_meta(meta)  # should not raise
    # Empty dict should not be mutated (coverage=1.0 default, no cap triggered)
    assert "confidence" not in meta
    assert "limitations" not in meta


# --- Confidence Aggregation ---

def test_aggregate_confidence_weighted():
    from agents.v3.orchestrator import aggregate_confidence
    confidences = {
        "margin-analyst": 0.9,     # weight 1.0
        "revenue-decomposer": 0.8, # weight 1.0
        "hypothesis-tester": 0.5,  # weight 0.5
    }
    result = aggregate_confidence(confidences)
    # (1.0*0.9 + 1.0*0.8 + 0.5*0.5) / (1.0+1.0+0.5) = 1.95/2.5 = 0.78
    assert result == pytest.approx(0.78, abs=0.01)


def test_aggregate_confidence_empty():
    from agents.v3.orchestrator import aggregate_confidence
    assert aggregate_confidence({}) == 0.0


def test_aggregate_confidence_unknown_agent_gets_default_weight():
    from agents.v3.orchestrator import aggregate_confidence
    confidences = {"some-new-agent": 0.7}
    result = aggregate_confidence(confidences)
    assert result == pytest.approx(0.7, abs=0.01)


def test_worst_limitation_picks_lowest_confidence():
    from agents.v3.orchestrator import worst_limitation
    artifacts = {
        "margin-analyst": {
            "_meta": {"confidence": 0.9, "limitations": []},
        },
        "ad-efficiency": {
            "_meta": {"confidence": 0.5, "limitations": ["OZON кабинет не обновлялся"]},
        },
    }
    result = worst_limitation(artifacts)
    assert "ad-efficiency" in result
    assert "OZON" in result


def test_worst_limitation_all_green():
    from agents.v3.orchestrator import worst_limitation
    artifacts = {
        "margin-analyst": {"_meta": {"confidence": 0.9, "limitations": []}},
    }
    assert worst_limitation(artifacts) is None


def test_failed_agent_meta_injected():
    from agents.v3.orchestrator import FAILED_AGENT_META
    assert FAILED_AGENT_META["confidence"] == 0.0
    assert FAILED_AGENT_META["conclusions"] == []


# --- Integration: full pipeline mock ---

def test_full_trust_envelope_pipeline():
    """Verify _meta flows from agent artifact through aggregation."""
    from agents.v3.orchestrator import (
        aggregate_confidence, worst_limitation, FAILED_AGENT_META,
    )

    # Simulate 3 agent results
    artifacts = {
        "margin-analyst": {
            "_meta": {"confidence": 0.9, "data_coverage": 0.98, "limitations": [], "conclusions": []},
            "artifact": {"margin_rub": 847200},
        },
        "ad-efficiency": {
            "_meta": {"confidence": 0.64, "data_coverage": 0.78, "limitations": ["OZON кабинет лаг 2 дня"], "conclusions": []},
            "artifact": {"drr_pct": 8.2},
        },
        "hypothesis-tester": {
            "_meta": FAILED_AGENT_META.copy(),
            "artifact": {},
        },
    }

    # Aggregate
    confidences = {n: a["_meta"]["confidence"] for n, a in artifacts.items()}
    agg = aggregate_confidence(confidences)
    worst = worst_limitation(artifacts)

    # margin-analyst: 1.0 * 0.9 = 0.9
    # ad-efficiency: 1.0 * 0.64 = 0.64
    # hypothesis-tester: 0.5 * 0.0 = 0.0
    # total weights: 1.0 + 1.0 + 0.5 = 2.5
    # weighted sum: 0.9 + 0.64 + 0.0 = 1.54
    # agg = 1.54 / 2.5 = 0.616 → 0.62
    assert 0.5 < agg < 0.7

    # Worst should be hypothesis-tester (confidence=0.0)
    assert worst is not None
    assert "hypothesis-tester" in worst
