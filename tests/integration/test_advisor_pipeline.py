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


def test_finance_data_produces_signals():
    """Brand finance data with anomalies produces correct signal types."""
    data = {
        "_source": "brand_finance",
        "brand": {
            "current": {
                "margin_pct": 18.0, "revenue_before_spp": 1_000_000,
                "revenue_after_spp": 850_000, "logistics": 90_000,
                "cogs_per_unit": 320, "orders_rub": 1_200_000,
                "orders_count": 400, "sales_count": 500,
            },
            "previous": {
                "margin_pct": 24.0, "revenue_before_spp": 900_000,
                "revenue_after_spp": 770_000, "logistics": 50_000,
                "cogs_per_unit": 280, "orders_rub": 1_000_000,
                "orders_count": 380, "sales_count": 450,
            },
            "changes": {
                "cogs_per_unit_change_pct": 14.3,
                "revenue_before_spp_change_pct": 11.1,
            },
        },
    }
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "margin_pct_drop" in types
    assert "cogs_anomaly" in types
    assert "logistics_overweight" in types


def test_model_breakdown_detects_romi():
    """Model breakdown with low ROMI model produces romi_critical signal."""
    data = {
        "_source": "model_breakdown",
        "channel": "WB",
        "models": [
            {"model": "Good", "margin_pct": 25, "drr_pct": 5, "turnover_days": 20,
             "roi_annual": 300, "margin": 100000, "adv_total": 15000,
             "orders_count": 200, "sales_count": 180, "revenue_before_spp": 500000},
            {"model": "Bad", "margin_pct": 8, "drr_pct": 25, "turnover_days": 45,
             "roi_annual": 30, "margin": 5000, "adv_total": 25000,
             "orders_count": 50, "sales_count": 40, "revenue_before_spp": 100000},
        ],
    }
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "romi_critical" in types
    romi_sig = [s for s in signals if s.type == "romi_critical"][0]
    assert "Bad" in romi_sig.hint


def test_multiple_sources_all_detected():
    """Signals from different sources are all collected."""
    plan_fact = {
        "_source": "plan_vs_fact",
        "days_elapsed": 15,
        "brand_total": {"metrics": {
            "orders_count": {"completion_mtd_pct": 130},
            "margin": {"completion_mtd_pct": 95},
            "sales_count": {"completion_mtd_pct": 110},
            "revenue": {"completion_mtd_pct": 115},
            "adv_internal": {"completion_mtd_pct": 100},
            "adv_external": {"completion_mtd_pct": 100},
        }},
    }
    margin_levers = {
        "_source": "margin_levers",
        "channel": "WB",
        "levers": {
            "spp_pct": {"current": 20.0, "previous": 15.0},
            "drr_pct": {"current": 8.0, "previous": 7.0},
        },
        "waterfall": {"revenue_change": 50000},
    }

    signals_pf = detect_signals(plan_fact)
    signals_ml = detect_signals(margin_levers)
    all_signals = signals_pf + signals_ml

    sources = {s.source for s in all_signals}
    assert "plan_vs_fact" in sources
    assert "margin_levers" in sources
    types = {s.type for s in all_signals}
    assert "margin_lags_orders" in types
    assert "spp_shift_up" in types
