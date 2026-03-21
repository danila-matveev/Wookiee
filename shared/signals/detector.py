"""Universal Signal Detector — finds patterns in any dataset."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Signal:
    id: str
    type: str
    category: str           # margin | turnover | funnel | adv | price | model
    severity: str           # info | warning | critical
    impact_on: str          # margin | turnover | both
    data: dict              # exact numbers for validator
    hint: str               # human-readable description (Russian)
    source: str             # which tool produced the data


def detect_signals(
    data: dict,
    kb_patterns: list[dict] | None = None,
) -> list[Signal]:
    """Detect patterns in data using base rules + KB patterns.

    Pure function: no network calls, no side effects.
    """
    if not data:
        return []

    kb_patterns = kb_patterns or []
    signals: list[Signal] = []

    # Dispatch to source-specific detectors
    source = data.get("_source", "")
    if source == "plan_vs_fact":
        signals.extend(_detect_plan_fact_signals(data))
    if source == "brand_finance":
        signals.extend(_detect_finance_signals(data))
    if source == "margin_levers":
        signals.extend(_detect_margin_lever_signals(data))

    # Apply KB patterns
    signals.extend(_detect_kb_pattern_signals(data, kb_patterns))

    return signals


def _detect_plan_fact_signals(data: dict) -> list[Signal]:
    return []


def _detect_finance_signals(data: dict) -> list[Signal]:
    return []


def _detect_margin_lever_signals(data: dict) -> list[Signal]:
    return []


def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    return []
