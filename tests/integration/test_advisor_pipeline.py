"""Integration tests for the advisor pipeline: signals → advisor → validator."""
from __future__ import annotations

from shared.signals.detector import detect_signals, Signal
from shared.signals.direction_map import DIRECTION_MAP
from shared.signals.patterns import BASE_PATTERNS


def _make_plan_fact_data(
    orders_pct: float = 120,
    margin_pct: float = 95,
    sales_pct: float = 110,
    revenue_pct: float = 115,
    adv_int_pct: float = 130,
    adv_ext_pct: float = 100,
    days_elapsed: int = 15,
) -> dict:
    """Build a plan_vs_fact payload that triggers multiple signals."""
    return {
        "_source": "plan_vs_fact",
        "days_elapsed": days_elapsed,
        "brand_total": {
            "metrics": {
                "orders_count": {"completion_mtd_pct": orders_pct},
                "margin": {"completion_mtd_pct": margin_pct},
                "sales_count": {"completion_mtd_pct": sales_pct},
                "revenue": {"completion_mtd_pct": revenue_pct},
                "adv_internal": {"completion_mtd_pct": adv_int_pct},
                "adv_external": {"completion_mtd_pct": adv_ext_pct},
            }
        },
    }


def test_plan_fact_to_signals_to_recommendations_shape():
    """Verifies signals from plan-fact data have correct structure and fields."""
    data = _make_plan_fact_data()
    signals = detect_signals(data)

    assert len(signals) >= 2, f"Expected at least 2 signals, got {len(signals)}"

    for sig in signals:
        assert isinstance(sig, Signal)
        assert sig.id, "Signal must have non-empty id"
        assert sig.type, "Signal must have non-empty type"
        assert sig.category in ("margin", "turnover", "funnel", "adv", "price", "model"), (
            f"Unknown category: {sig.category}"
        )
        assert sig.severity in ("info", "warning", "critical"), (
            f"Unknown severity: {sig.severity}"
        )
        assert sig.impact_on in ("margin", "turnover", "both"), (
            f"Unknown impact_on: {sig.impact_on}"
        )
        assert isinstance(sig.data, dict), "Signal.data must be a dict"
        assert sig.hint, "Signal must have non-empty hint"
        assert sig.source == "plan_vs_fact"

    # Check that known triggers fired
    signal_types = {s.type for s in signals}
    assert "margin_lags_orders" in signal_types, "Expected margin_lags_orders signal (gap=25 pp)"
    assert "adv_overspend" in signal_types, "Expected adv_overspend signal (130%)"
    assert "margin_pct_drop" in signal_types, "Expected margin_pct_drop signal (revenue 115% but margin 95%)"


def test_direction_map_covers_all_signal_types():
    """Verifies every pattern in BASE_PATTERNS has a DIRECTION_MAP entry."""
    direction_keys = set(DIRECTION_MAP.keys())
    for pattern in BASE_PATTERNS:
        name = pattern["pattern_name"]
        assert name in direction_keys, (
            f"BASE_PATTERNS pattern '{name}' has no DIRECTION_MAP entry"
        )
        # Each entry must have at least one valid action
        actions = DIRECTION_MAP[name]
        assert isinstance(actions, list) and len(actions) >= 1, (
            f"DIRECTION_MAP['{name}'] must be a non-empty list, got {actions}"
        )
