import pytest
from agents.oleg.agents.validator.scripts.check_numbers import check_numbers
from agents.oleg.agents.validator.scripts.check_coverage import check_coverage
from agents.oleg.agents.validator.scripts.check_direction import check_direction
from agents.oleg.agents.validator.scripts.check_kb_rules import check_kb_rules


# --- check_numbers ---
def test_check_numbers_match():
    signal_data = {"orders_completion_pct": 113.9, "margin_completion_pct": 106.1}
    rec = {"diagnosis": "Заказы +113.9% к плану, маржа +106.1%", "signal_id": "test"}
    result = check_numbers(signal_data, rec)
    assert result["match"] is True


def test_check_numbers_mismatch():
    signal_data = {"orders_completion_pct": 113.9}
    rec = {"diagnosis": "Заказы +6% к плану", "signal_id": "test"}
    result = check_numbers(signal_data, rec)
    assert result["match"] is False
    assert len(result["mismatches"]) > 0


# --- check_coverage ---
def test_check_coverage_all_covered():
    signals = [
        {"id": "s1", "severity": "warning"},
        {"id": "s2", "severity": "critical"},
        {"id": "s3", "severity": "info"},
    ]
    recs = [{"signal_id": "s1"}, {"signal_id": "s2"}]
    result = check_coverage(signals, recs)
    assert len(result["missed"]) == 0  # info can be skipped


def test_check_coverage_missed_warning():
    signals = [{"id": "s1", "severity": "warning"}, {"id": "s2", "severity": "warning"}]
    recs = [{"signal_id": "s1"}]
    result = check_coverage(signals, recs)
    assert "s2" in result["missed"]


# --- check_direction ---
def test_check_direction_valid():
    result = check_direction("adv_overspend", "reduce_budget")
    assert result["valid"] is True


def test_check_direction_invalid():
    result = check_direction("adv_overspend", "increase_budget")
    assert result["valid"] is False


# --- check_kb_rules ---
def test_check_kb_rules_no_conflict():
    rec = {"action": "поднять цену", "action_category": "raise_price"}
    kb_patterns = [
        {
            "pattern_name": "no_price_drop_low_stock",
            "trigger_condition": {"metric": "stock_days", "operator": "<", "threshold": 14},
            "action_hint": "не снижать цену",
        }
    ]
    # This recommendation raises price, not lowers — no conflict
    result = check_kb_rules(rec, kb_patterns)
    assert len(result["conflicts"]) == 0
