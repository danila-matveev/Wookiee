# tests/reporter/test_playbook.py
"""Tests for playbook loader and updater."""
from unittest.mock import MagicMock

from agents.reporter.analyst.schemas import DiscoveredPattern
from agents.reporter.playbook.loader import _parse_base_rules, load_rules_from_state
from agents.reporter.playbook.updater import save_discovered_patterns
from agents.reporter.types import ReportScope, ReportType
from datetime import date


def test_parse_base_rules():
    rules = _parse_base_rules()
    assert len(rules) > 0
    assert all(r["source"] == "manual" for r in rules)
    assert all(r["status"] == "active" for r in rules)


def test_load_rules_fallback():
    mock_state = MagicMock()
    mock_state.get_active_rules.side_effect = Exception("DB down")
    rules = load_rules_from_state(mock_state)
    assert len(rules) > 0  # Falls back to base_rules.md


def test_save_discovered_patterns():
    mock_state = MagicMock()
    patterns = [
        DiscoveredPattern(
            pattern="Test pattern",
            evidence="Test evidence",
            suggested_action="Test action",
            confidence=0.8,
        ),
        DiscoveredPattern(
            pattern="Low confidence",
            evidence="Weak",
            suggested_action="Skip",
            confidence=0.3,  # Below 0.6 threshold
        ),
    ]
    scope = ReportScope(
        report_type=ReportType.FINANCIAL_DAILY,
        period_from=date(2026, 3, 27),
        period_to=date(2026, 3, 27),
        comparison_from=date(2026, 3, 26),
        comparison_to=date(2026, 3, 26),
    )
    count = save_discovered_patterns(mock_state, patterns, scope)
    assert count == 1  # Only the high-confidence one
    assert mock_state.save_pending_pattern.call_count == 1
