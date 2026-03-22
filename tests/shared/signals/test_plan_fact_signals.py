import pytest
from shared.signals.detector import detect_signals

PLAN_FACT_DATA = {
    "_source": "plan_vs_fact",
    "brand_total": {
        "metrics": {
            "orders_count": {"completion_mtd_pct": 113.9, "forecast_vs_plan_pct": 10.2},
            "margin": {"completion_mtd_pct": 106.1, "forecast_vs_plan_pct": 4.8},
            "sales_count": {"completion_mtd_pct": 101.3, "forecast_vs_plan_pct": 1.5},
            "revenue": {"completion_mtd_pct": 120.4, "forecast_vs_plan_pct": 15.0},
            "adv_internal": {"completion_mtd_pct": 108.9, "forecast_vs_plan_pct": 12.0},
            "adv_external": {"completion_mtd_pct": 126.3, "forecast_vs_plan_pct": 30.0},
        },
    },
    "days_elapsed": 19,
    "days_in_month": 31,
}

def test_margin_lags_orders_detected():
    """Orders +13.9% but margin only +6.1% — gap > 5 pp."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "margin_lags_orders" in types

    signal = next(s for s in signals if s.type == "margin_lags_orders")
    assert signal.severity == "warning"
    assert signal.category == "margin"
    assert signal.data["gap_pct"] == pytest.approx(7.8, abs=0.1)

def test_sales_lag_expected_detected():
    """Orders +13.9% but sales only +1.3% — buyout lag."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "sales_lag_expected" in types

def test_adv_external_overspend_detected():
    """External ads +26.3% over plan — overspend."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "adv_overspend" in types

def test_no_false_signals_on_healthy_data():
    """All metrics ~100% — no signals."""
    healthy = {
        "_source": "plan_vs_fact",
        "brand_total": {
            "metrics": {
                "orders_count": {"completion_mtd_pct": 101.0, "forecast_vs_plan_pct": 1.0},
                "margin": {"completion_mtd_pct": 100.5, "forecast_vs_plan_pct": 0.5},
                "sales_count": {"completion_mtd_pct": 99.8, "forecast_vs_plan_pct": -0.2},
                "revenue": {"completion_mtd_pct": 100.2, "forecast_vs_plan_pct": 0.2},
                "adv_internal": {"completion_mtd_pct": 98.0, "forecast_vs_plan_pct": -2.0},
                "adv_external": {"completion_mtd_pct": 100.0, "forecast_vs_plan_pct": 0.0},
            },
        },
        "days_elapsed": 19,
        "days_in_month": 31,
    }
    signals = detect_signals(data=healthy)
    assert len(signals) == 0
