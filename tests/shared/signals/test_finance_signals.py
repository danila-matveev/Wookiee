"""Tests for _detect_finance_signals (brand_finance source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals, Signal


def _make_finance_data(**overrides) -> dict:
    """Build brand_finance data with sensible defaults."""
    base = {
        "_source": "brand_finance",
        "brand": {
            "current": {
                "margin_pct": 22.0,
                "revenue_before_spp": 1_000_000,
                "revenue_after_spp": 850_000,
                "logistics": 60_000,
                "cogs_per_unit": 300,
                "orders_rub": 1_200_000,
                "sales_count": 500,
            },
            "previous": {
                "margin_pct": 24.0,
                "revenue_before_spp": 900_000,
                "revenue_after_spp": 770_000,
                "logistics": 50_000,
                "cogs_per_unit": 280,
                "orders_rub": 1_000_000,
                "sales_count": 450,
            },
            "changes": {
                "cogs_per_unit_change_pct": 7.14,
                "revenue_before_spp_change_pct": 11.1,
            },
        },
    }
    for k, v in overrides.items():
        if k.startswith("prev_"):
            base["brand"]["previous"][k[5:]] = v
        elif k.startswith("change_"):
            base["brand"]["changes"][k[7:]] = v
        else:
            base["brand"]["current"][k] = v
    return base


def test_margin_pct_drop_detected():
    """margin_pct drops > 2 pp while revenue grows."""
    data = _make_finance_data(margin_pct=20.0, prev_margin_pct=24.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "margin_pct_drop" in types


def test_cogs_anomaly_detected():
    """cogs_per_unit change > 5%."""
    data = _make_finance_data(change_cogs_per_unit_change_pct=8.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cogs_anomaly" in types


def test_logistics_overweight_detected():
    """logistics / revenue > 8%."""
    data = _make_finance_data(logistics=90_000, revenue_after_spp=850_000)
    # 90_000 / 850_000 = 10.6%
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "logistics_overweight" in types


def test_price_signal_detected():
    """avg check orders vs avg check sales differ > 5%."""
    data = _make_finance_data(
        orders_rub=1_200_000, sales_count=500,
        prev_orders_rub=1_000_000, prev_sales_count=450,
    )
    data["brand"]["current"]["orders_count"] = 400
    data["brand"]["current"]["sales_count"] = 500
    # avg_order = 1_200_000/400 = 3000, avg_sale = 850_000/500 = 1700
    # diff = |3000-1700|/1700 = 76% >> 5%
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "price_signal" in types


def test_no_signals_on_healthy_finance():
    """No signals when all metrics are within normal range."""
    data = _make_finance_data(
        margin_pct=24.5, prev_margin_pct=24.0,
        logistics=50_000, revenue_after_spp=850_000,
    )
    data["brand"]["changes"]["cogs_per_unit_change_pct"] = 2.0
    signals = detect_signals(data)
    critical_warning = [s for s in signals if s.severity in ("critical", "warning")]
    assert len(critical_warning) == 0
