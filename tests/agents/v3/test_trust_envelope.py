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
