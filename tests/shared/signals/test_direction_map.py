from shared.signals.direction_map import DIRECTION_MAP, is_valid_direction


def test_adv_overspend_allows_reduce():
    assert is_valid_direction("adv_overspend", "reduce_budget")


def test_adv_overspend_rejects_increase():
    assert not is_valid_direction("adv_overspend", "increase_budget")


def test_unknown_signal_allows_anything():
    assert is_valid_direction("unknown_signal_type", "anything")


def test_all_signal_types_have_valid_actions():
    for signal_type, actions in DIRECTION_MAP.items():
        assert len(actions) > 0, f"{signal_type} has no valid actions"
