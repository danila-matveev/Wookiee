"""Deterministic number validation: signal.data vs recommendation fields."""

from __future__ import annotations

import re


def _number_found(value: float, text: str) -> bool:
    """Check if number appears in text with word-boundary matching."""
    str_val = str(round(value, 1))
    # Word boundary regex: prevents 113.9 matching inside 1113.9
    pattern = r'(?<!\d)' + re.escape(str_val) + r'(?!\d)'
    if re.search(pattern, text):
        return True
    # Also check integer form for whole numbers (e.g., 114 for 114.0)
    if value == int(value):
        str_int = str(int(value))
        pattern_int = r'(?<!\d)' + re.escape(str_int) + r'(?!\d)'
        if re.search(pattern_int, text):
            return True
    return False


def check_numbers(signal_data: dict, recommendation: dict) -> dict:
    """Check that numbers in recommendation match signal data (field-by-field)."""
    mismatches = []
    diagnosis = recommendation.get("diagnosis", "")

    for field, expected_value in signal_data.items():
        if not isinstance(expected_value, (int, float)):
            continue
        if not _number_found(expected_value, diagnosis):
            mismatches.append({
                "field": field,
                "signal": expected_value,
                "not_found_in": "diagnosis",
            })

    return {
        "match": len(mismatches) == 0,
        "mismatches": mismatches,
    }
