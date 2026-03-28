# agents/reporter/playbook/loader.py
"""Load playbook rules from Supabase, with fallback to base_rules.md."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_RULES_PATH = Path(__file__).parent / "base_rules.md"


def load_rules_from_state(state, report_type: Optional[str] = None) -> list[dict]:
    """Load active rules from Supabase. Fallback to base_rules.md on failure."""
    try:
        rules = state.get_active_rules(report_type)
        if rules:
            logger.info("Loaded %d playbook rules from Supabase", len(rules))
            return rules
    except Exception as e:
        logger.warning("Failed to load rules from Supabase: %s", e)

    # Fallback: parse base_rules.md
    return _parse_base_rules()


def _parse_base_rules() -> list[dict]:
    """Parse base_rules.md into rule dicts."""
    if not _BASE_RULES_PATH.exists():
        return []

    text = _BASE_RULES_PATH.read_text(encoding="utf-8")
    rules = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            rules.append({
                "rule_text": line[2:],
                "category": "general",
                "source": "manual",
                "status": "active",
            })
    logger.info("Loaded %d fallback rules from base_rules.md", len(rules))
    return rules
