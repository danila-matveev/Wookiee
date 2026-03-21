"""Check action direction using DIRECTION_MAP."""

from __future__ import annotations

from shared.signals.direction_map import DIRECTION_MAP, is_valid_direction


def check_direction(signal_type: str, action_category: str) -> dict:
    """Check if action_category is valid for the given signal_type."""
    valid = is_valid_direction(signal_type, action_category)
    valid_actions = DIRECTION_MAP.get(signal_type, [])

    reason = ""
    if not valid:
        reason = (
            f"Сигнал '{signal_type}' допускает: {', '.join(valid_actions)}. "
            f"Получено: {action_category} — конфликт"
        )

    return {"valid": valid, "reason": reason}
