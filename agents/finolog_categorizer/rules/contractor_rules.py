"""
Contractor → category rules loader.

Builds stable contractor→category mappings by analyzing historical transactions.
A contractor is considered "stable" if >90% of their transactions go to one category
and they have at least 5 transactions.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Path to historical transaction data
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "finolog_analysis"
_TXN_PATH = _DATA_DIR / "all_transactions.json"

# Cache
_contractor_rules: Optional[dict[int, tuple[int, str]]] = None


def load_contractor_rules(
    min_transactions: int = 5,
    min_consistency: float = 0.90,
) -> dict[int, tuple[int, str]]:
    """
    Load contractor → (category_id, rule_name) mapping from historical data.

    Returns dict: contractor_id → (category_id, "contractor_{contractor_id}")
    Only includes contractors with >=min_transactions and >=min_consistency.
    Excludes transfers (cat 1) and uncategorized (cat 3/4).
    """
    global _contractor_rules
    if _contractor_rules is not None:
        return _contractor_rules

    if not _TXN_PATH.exists():
        logger.warning(f"Contractor rules: {_TXN_PATH} not found, returning empty")
        _contractor_rules = {}
        return _contractor_rules

    try:
        with open(_TXN_PATH) as f:
            txns = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load transactions: {e}")
        _contractor_rules = {}
        return _contractor_rules

    # Count category distribution per contractor
    contractor_cats: dict[int, Counter] = defaultdict(Counter)
    for t in txns:
        ctr = t.get("contractor_id")
        cat = t.get("category_id")
        if not ctr or not cat or cat in (1, 3, 4):
            continue
        contractor_cats[ctr][cat] += 1

    # Filter to stable mappings
    rules: dict[int, tuple[int, str]] = {}
    for ctr_id, cat_counts in contractor_cats.items():
        total = sum(cat_counts.values())
        if total < min_transactions:
            continue
        top_cat, top_count = cat_counts.most_common(1)[0]
        if top_count / total >= min_consistency:
            rules[ctr_id] = (top_cat, f"contractor_{ctr_id}")

    logger.info(f"Loaded {len(rules)} contractor rules (from {len(contractor_cats)} contractors)")
    _contractor_rules = rules
    return _contractor_rules


def reset_cache():
    """Reset cached contractor rules (for testing)."""
    global _contractor_rules
    _contractor_rules = None
