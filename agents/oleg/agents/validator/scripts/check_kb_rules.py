"""Check recommendation against KB pattern rules for conflicts."""

from __future__ import annotations

# Action categories that conflict with each other
OPPOSING_ACTIONS: dict[str, set[str]] = {
    "raise_price": {"lower_price", "reduce_price", "liquidate"},
    "lower_price": {"raise_price"},
    "increase_budget": {"reduce_budget", "pause_campaign"},
    "reduce_budget": {"increase_budget", "scale_up"},
    "pause_campaign": {"increase_budget", "scale_up"},
    "scale_up": {"reduce_budget", "pause_campaign", "withdraw"},
    "withdraw": {"scale_up", "return_to_sale", "increase_stock"},
}


def check_kb_rules(recommendation: dict, kb_patterns: list[dict]) -> dict:
    """Check if recommendation conflicts with known KB rules."""
    conflicts = []
    rec_action = recommendation.get("action_category", "")

    for pattern in kb_patterns:
        hint = (pattern.get("action_hint", "") or "").lower()
        pattern_name = pattern.get("pattern_name", "")

        # Check if the pattern's action hint opposes the recommendation
        opposing = OPPOSING_ACTIONS.get(rec_action, set())
        for opp_action in opposing:
            if opp_action.replace("_", " ") in hint:
                conflicts.append({
                    "pattern_name": pattern_name,
                    "rule": pattern.get("description", ""),
                    "conflict": (
                        f"Рекомендация '{rec_action}' конфликтует с правилом: "
                        f"{pattern.get('action_hint', '')}"
                    ),
                })

    return {"conflicts": conflicts}
