# agents/reporter/playbook/updater.py
"""Save LLM-discovered patterns to Supabase as pending_review."""
from __future__ import annotations

import logging
from typing import Any

from agents.reporter.analyst.schemas import DiscoveredPattern
from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


def save_discovered_patterns(
    state: Any,
    patterns: list[DiscoveredPattern],
    scope: ReportScope,
) -> int:
    """Save discovered patterns to Supabase. Returns count saved."""
    saved = 0
    for p in patterns:
        if p.confidence < 0.6:
            continue  # Skip low-confidence patterns

        row = {
            "rule_text": p.pattern,
            "category": scope.report_type.collector_kind,
            "source": "llm_discovered",
            "status": "pending_review",
            "confidence": p.confidence,
            "evidence": p.evidence,
            "report_types": [scope.report_type.value],
        }
        try:
            state.save_pending_pattern(row)
            saved += 1
        except Exception as e:
            logger.warning("Failed to save pattern: %s", e)

    if saved:
        logger.info("Saved %d discovered patterns for review", saved)
    return saved
