import pytest
from shared.signals.detector import detect_signals, Signal


def test_detect_signals_empty_data_returns_empty():
    result = detect_signals(data={}, kb_patterns=[])
    assert result == []


def test_signal_dataclass_fields():
    s = Signal(
        id="test_2026-03-21",
        type="margin_lags_orders",
        category="margin",
        severity="warning",
        impact_on="margin",
        data={"gap_pct": 7.8},
        hint="Test hint",
        source="plan_vs_fact",
    )
    assert s.category == "margin"
    assert s.severity == "warning"
