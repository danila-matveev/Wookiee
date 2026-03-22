"""Tests for _detect_advertising_signals (advertising source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_ad_data(channel="WB", **overrides) -> dict:
    base = {
        "_source": "advertising",
        "channel": channel,
        "advertising": {
            "current": {
                "ctr_pct": 3.0,
                "cr_full_pct": 2.5,
                "ad_orders": 100,
                "ad_spend": 50000,
            },
            "previous": {
                "ctr_pct": 3.2,
                "cr_full_pct": 2.3,
                "ad_orders": 90,
                "ad_spend": 45000,
            },
        },
        "funnel": {
            "current": {
                "cart_to_order_pct": 30.0,
                "order_to_buyout_pct": 55.0,
            },
            "previous": {
                "cart_to_order_pct": 32.0,
                "order_to_buyout_pct": 58.0,
            },
        },
    }
    for k, v in overrides.items():
        parts = k.split("__")
        if len(parts) == 3:
            base[parts[0]][parts[1]][parts[2]] = v
        elif len(parts) == 2:
            base[parts[0]][parts[1]] = v
    return base


def test_ctr_drop_wb():
    data = _make_ad_data(channel="WB", advertising__current__ctr_pct=1.5)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "ctr_drop" in types


def test_ctr_ok_wb():
    data = _make_ad_data(channel="WB", advertising__current__ctr_pct=2.5)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "ctr_drop" not in types


def test_cart_to_order_drop():
    data = _make_ad_data(
        funnel__current__cart_to_order_pct=24.0,
        funnel__previous__cart_to_order_pct=32.0,
    )
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cart_to_order_drop" in types


def test_cro_improvement():
    data = _make_ad_data(
        advertising__current__cr_full_pct=4.0,
        advertising__previous__cr_full_pct=2.5,
    )
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cro_improvement" in types


def test_buyout_drop():
    data = _make_ad_data(funnel__current__order_to_buyout_pct=40.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "buyout_drop" in types


def test_no_funnel_signals_for_ozon():
    """OZON has no funnel data — funnel-dependent signals should not fire."""
    data = _make_ad_data(channel="OZON")
    del data["funnel"]
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cart_to_order_drop" not in types
    assert "buyout_drop" not in types
