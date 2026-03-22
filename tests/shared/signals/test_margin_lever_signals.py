"""Tests for _detect_margin_lever_signals (margin_levers source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_lever_data(channel="WB", **lever_overrides) -> dict:
    base = {
        "_source": "margin_levers",
        "channel": channel,
        "levers": {
            "spp_pct": {"current": 15.0, "previous": 15.0},
            "drr_pct": {"current": 8.0, "previous": 7.0},
            "logistics_per_unit": {"current": 120, "previous": 115},
            "cogs_per_unit": {"current": 300, "previous": 290},
            "price_before_spp_per_unit": {"current": 2000, "previous": 1950},
        },
        "waterfall": {
            "revenue_change": 50000,
            "advertising_change": -10000,
        },
    }
    for k, v in lever_overrides.items():
        keys = k.split("__")
        if len(keys) == 2:
            base["levers"][keys[0]][keys[1]] = v
        else:
            base["levers"][k] = v
    return base


def test_spp_shift_up():
    data = _make_lever_data(spp_pct__current=18.0, spp_pct__previous=15.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "spp_shift_up" in types


def test_spp_shift_down():
    data = _make_lever_data(spp_pct__current=12.0, spp_pct__previous=15.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "spp_shift_down" in types


def test_adv_overspend_wb():
    data = _make_lever_data(channel="WB", drr_pct__current=14.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "adv_overspend" in types


def test_adv_overspend_ozon_higher_threshold():
    data = _make_lever_data(channel="OZON", drr_pct__current=15.0)
    signals = detect_signals(data)
    # 15% < 18% threshold for Ozon — should NOT fire
    types = {s.type for s in signals}
    assert "adv_overspend" not in types


def test_adv_underspend():
    data = _make_lever_data(drr_pct__current=2.0)
    data["waterfall"]["revenue_change"] = -5000  # revenue declining
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "adv_underspend" in types


def test_no_signals_healthy_levers():
    data = _make_lever_data()
    signals = detect_signals(data)
    assert len(signals) == 0
