"""Tests for _detect_model_signals (model_breakdown source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_model_data(models: list[dict]) -> dict:
    return {
        "_source": "model_breakdown",
        "channel": "WB",
        "models": models,
    }


def _model(name="TestModel", margin_pct=20, drr_pct=5, turnover_days=30,
           roi_annual=200, margin=50000, adv_total=10000, orders_count=100,
           sales_count=80, revenue_before_spp=300000, status=None, abc=None):
    d = {
        "model": name, "margin_pct": margin_pct, "drr_pct": drr_pct,
        "turnover_days": turnover_days, "roi_annual": roi_annual,
        "margin": margin, "adv_total": adv_total, "orders_count": orders_count,
        "sales_count": sales_count, "revenue_before_spp": revenue_before_spp,
    }
    if status is not None:
        d["status"] = status
    if abc is not None:
        d["abc"] = abc
    return d


def test_low_roi_article():
    models = [
        _model("Good", turnover_days=20, margin_pct=25, roi_annual=300),
        _model("Mid", turnover_days=30, margin_pct=20, roi_annual=200),
        _model("Bad", turnover_days=61, margin_pct=10, roi_annual=30),
    ]
    # sorted = [20,30,61], median = 30 (idx 1). Bad: 61 > 30*1.5=45
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "low_roi_article" in types
    bad_signal = [s for s in signals if s.type == "low_roi_article"][0]
    assert "Bad" in bad_signal.hint


def test_high_roi_opportunity():
    models = [
        _model("Slow", turnover_days=40),
        _model("Mid", turnover_days=30),
        _model("Fast", turnover_days=10, margin_pct=30, roi_annual=500),
    ]
    # sorted = [10,30,40], median=30, Fast=10 < 30*0.5=15, margin>25
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "high_roi_opportunity" in types


def test_big_inefficient():
    models = [
        _model(f"Model{i}", revenue_before_spp=1000000 - i * 100000, margin_pct=8)
        for i in range(6)
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "big_inefficient" in types


def test_romi_critical():
    models = [
        _model("Romi_bad", margin=5000, adv_total=15000, drr_pct=20),
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "romi_critical" in types


def test_cac_exceeds_profit():
    models = [
        _model("Cac_bad", adv_total=20000, orders_count=10, margin=8000, sales_count=8, drr_pct=15),
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "cac_exceeds_profit" in types


def test_no_signals_healthy_models():
    models = [
        _model("A", margin_pct=25, drr_pct=5, turnover_days=25, roi_annual=250, margin=100000, adv_total=15000),
        _model("B", margin_pct=22, drr_pct=6, turnover_days=30, roi_annual=200, margin=80000, adv_total=12000),
    ]
    signals = detect_signals(_make_model_data(models))
    critical = [s for s in signals if s.severity in ("critical", "warning")]
    assert len(critical) == 0


def test_status_mismatch_fires():
    """Model marked Выводим with ABC=A and high margin → status_mismatch."""
    models = [
        _model("Vuki", margin_pct=25, margin=200000, status="Выводим", abc="A"),
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "status_mismatch" in types
    sm = [s for s in signals if s.type == "status_mismatch"][0]
    assert sm.severity == "critical"
    assert "Vuki" in sm.hint


def test_status_mismatch_not_fires_low_margin():
    """Model marked Выводим but low margin → no status_mismatch."""
    models = [
        _model("Luna", margin_pct=10, margin=5000, status="Выводим", abc="B"),
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "status_mismatch" not in types


def test_status_mismatch_not_fires_active():
    """Active model with ABC=A → no status_mismatch."""
    models = [
        _model("Ruby", margin_pct=30, margin=300000, status="Продается", abc="A"),
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "status_mismatch" not in types
