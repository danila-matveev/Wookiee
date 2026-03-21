"""
Cascade transaction classifier.

Priority order:
1. Description prefix match  → confidence 0.95
2. Regex match               → confidence 0.90
3. Terminal match             → confidence 0.90
4. Contractor match           → confidence 0.85
5. Learned rules (SQLite)     → confidence 0.75
6. None (LLM fallback — phase 2)
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from .rules.description_rules import (
    DESCRIPTION_RULES, FOT_CATEGORIES,
    CAT_CONTENT_CREATORS, CAT_FOT_MGMT, CAT_UNCLASSIFIED_IN, CAT_UNCLASSIFIED_OUT,
)
from .rules.regex_rules import REGEX_RULES, PAYROLL_PERSON_MAP
from .rules.terminal_rules import match_terminal
from .rules.contractor_rules import load_contractor_rules

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    txn_id: int
    txn_date: str
    txn_description: str
    txn_value: float
    txn_contractor_id: int | None
    category_id: int
    report_date: str
    confidence: float
    rule_name: str


def _resolve_payroll_category(
    description: str,
    contractor_id: int | None = None,
    contractor_rules: dict[int, tuple[int, str]] | None = None,
) -> int:
    """Determine which ФОТ sub-category based on person name or contractor."""
    # Try contractor mapping first (more reliable)
    if contractor_id and contractor_rules and contractor_id in contractor_rules:
        cat_id, _ = contractor_rules[contractor_id]
        if cat_id in FOT_CATEGORIES:
            return cat_id

    # Fallback to name matching
    desc_lower = description.lower()
    for keyword, cat_id in PAYROLL_PERSON_MAP.items():
        if keyword in desc_lower:
            return cat_id

    return CAT_FOT_MGMT  # default


def _last_day_prev_month(d: date) -> date:
    """Return last day of the month before d."""
    first_of_month = d.replace(day=1)
    return first_of_month - timedelta(days=1)


def compute_report_date(txn_date_str: str, category_id: int) -> str:
    """Compute accrual-based report_date for a transaction.

    ФОТ categories → last day of previous month (accrual).
    Everything else → cash-basis (report_date = txn date).
    """
    try:
        txn_date = date.fromisoformat(txn_date_str[:10])
    except (ValueError, TypeError):
        return txn_date_str[:10] if txn_date_str else ""

    if category_id in FOT_CATEGORIES:
        return str(_last_day_prev_month(txn_date))

    return str(txn_date)


def _make_suggestion(
    txn: dict,
    cat_id: int,
    confidence: float,
    rule_name: str,
) -> Suggestion:
    txn_date = (txn.get("date") or "")[:10]
    return Suggestion(
        txn_id=txn.get("id", 0),
        txn_date=txn_date,
        txn_description=(txn.get("description") or "").strip(),
        txn_value=txn.get("value", 0),
        txn_contractor_id=txn.get("contractor_id"),
        category_id=cat_id,
        report_date=compute_report_date(txn_date, cat_id),
        confidence=confidence,
        rule_name=rule_name,
    )


def classify(
    txn: dict,
    learned_rules: list[dict] | None = None,
    contractor_rules: dict[int, tuple[int, str]] | None = None,
) -> Optional[Suggestion]:
    """
    Classify a single transaction using the 5-level cascade.

    Returns Suggestion or None if cannot classify.
    """
    desc = (txn.get("description") or "").strip()
    if not desc:
        return None

    # Load contractor rules if not provided
    if contractor_rules is None:
        contractor_rules = load_contractor_rules()

    contractor_id = txn.get("contractor_id")

    # ── 1. Description prefix match (confidence 0.95) ──
    for prefix, cat_id, rule_name in DESCRIPTION_RULES:
        if desc.startswith(prefix):
            return _make_suggestion(txn, cat_id, 0.95, rule_name)

    # ── 2. Regex match (confidence 0.90) ──
    for pattern, cat_id, rule_name in REGEX_RULES:
        if pattern.search(desc):
            # Resolve category for payroll/content rules that return None
            if cat_id is None:
                if "payroll" in rule_name or "kpi" in rule_name:
                    cat_id = _resolve_payroll_category(desc, contractor_id, contractor_rules)
                elif "content" in rule_name:
                    cat_id = CAT_CONTENT_CREATORS
                else:
                    continue  # skip unresolvable
            return _make_suggestion(txn, cat_id, 0.90, rule_name)

    # ── 3. Contractor match (confidence 0.85) ──
    # Contractor rules are more reliable than terminal for known contractors
    if contractor_id and contractor_id in contractor_rules:
        cat_id, rule_name = contractor_rules[contractor_id]
        return _make_suggestion(txn, cat_id, 0.85, rule_name)

    # ── 4. Terminal match (confidence 0.85) ──
    terminal_match = match_terminal(desc)
    if terminal_match:
        cat_id, rule_name = terminal_match
        return _make_suggestion(txn, cat_id, 0.85, rule_name)

    # ── 5. Learned rules from SQLite (confidence 0.75) ──
    if learned_rules:
        desc_lower = desc[:50].lower()
        for rule in learned_rules:
            if desc_lower.startswith(rule["pattern"]):
                cat_id = rule["category_id"]
                return _make_suggestion(txn, cat_id, 0.75, f"learned:{rule['pattern'][:30]}")

    return None
