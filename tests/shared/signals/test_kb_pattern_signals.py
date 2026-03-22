"""Tests for _detect_kb_pattern_signals (generic evaluator)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _pattern(name, metric, operator, threshold, **kwargs):
    return {
        "pattern_name": name,
        "description": f"Test pattern {name}",
        "category": kwargs.get("category", "margin"),
        "trigger_condition": {"metric": metric, "operator": operator, "threshold": threshold, **kwargs.get("extra_cond", {})},
        "action_hint": kwargs.get("action_hint", "test action"),
        "impact_on": kwargs.get("impact_on", "margin"),
        "severity": kwargs.get("severity", "warning"),
        "source_tag": "base",
        "confidence": "high",
    }


def test_simple_gt_fires():
    data = {"_source": "brand_finance", "brand": {"current": {"drr_pct": 15.0}}}
    patterns = [_pattern("high_drr", "brand.current.drr_pct", ">", 12)]
    signals = detect_signals(data, kb_patterns=patterns)
    types = {s.type for s in signals}
    assert "kb_high_drr" in types


def test_simple_gt_does_not_fire():
    data = {"_source": "brand_finance", "brand": {"current": {"drr_pct": 10.0}}}
    patterns = [_pattern("high_drr", "brand.current.drr_pct", ">", 12)]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 0


def test_gap_gt_fires():
    data = {
        "_source": "plan_vs_fact",
        "brand_total": {"metrics": {
            "orders_count": {"completion_mtd_pct": 120},
            "margin": {"completion_mtd_pct": 100},
        }},
    }
    patterns = [_pattern(
        "order_margin_gap", "", "gap_gt", 10,
        extra_cond={"metric_pair": [
            "brand_total.metrics.orders_count.completion_mtd_pct",
            "brand_total.metrics.margin.completion_mtd_pct",
        ]},
    )]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 1


def test_missing_metric_does_not_fire():
    data = {"_source": "brand_finance", "brand": {"current": {}}}
    patterns = [_pattern("missing", "brand.current.nonexistent", ">", 0)]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 0


def test_lt_operator():
    data = {"_source": "brand_finance", "brand": {"current": {"margin_pct": 8.0}}}
    patterns = [_pattern("low_margin", "brand.current.margin_pct", "<", 10, severity="critical")]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 1
    assert kb_signals[0].severity == "critical"
