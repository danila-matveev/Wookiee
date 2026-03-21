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
