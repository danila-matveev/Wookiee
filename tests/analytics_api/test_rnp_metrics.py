"""Unit tests for RNP metric helpers — no DB required."""
import pytest
from shared.data_layer.rnp import _safe_div, _week_start, _detect_phase
from datetime import date


def test_safe_div_normal():
    assert abs(_safe_div(10.0, 4.0) - 2.5) < 0.001


def test_safe_div_zero_denominator():
    assert _safe_div(10.0, 0) is None


def test_safe_div_none_inputs():
    assert _safe_div(None, 5) is None
    assert _safe_div(5, None) is None


def test_week_start_monday():
    assert _week_start(date(2025, 3, 5)) == date(2025, 3, 3)   # Wednesday → Monday


def test_week_start_already_monday():
    assert _week_start(date(2025, 3, 3)) == date(2025, 3, 3)


def test_detect_phase_norm():
    assert _detect_phase(15.0) == "norm"
    assert _detect_phase(25.0) == "norm"


def test_detect_phase_decline():
    assert _detect_phase(9.9) == "decline"
    assert _detect_phase(-5.0) == "decline"


def test_detect_phase_recovery():
    assert _detect_phase(12.0) == "recovery"


def test_detect_phase_none():
    assert _detect_phase(None) == "recovery"


from shared.data_layer.rnp import aggregate_to_weeks


def _make_day(dt_str, **kwargs):
    defaults = {
        "date": date.fromisoformat(dt_str),
        "orders_qty": 100, "sales_qty": 87, "sales_rub": 500000,
        "adv_internal_rub": 50000, "margin_rub": 80000,
        "orders_rub": 600000, "orders_spp_rub": 540000,
        "clicks_total": 5000, "cart_total": 300,
        "funnel_orders_qty": 100, "funnel_buyouts_qty": 87,
        "adv_views": 2000, "adv_clicks": 150, "adv_orders": 20,
    }
    defaults.update(kwargs)
    return defaults


def test_aggregate_single_week_orders():
    rows = [_make_day("2025-03-03"), _make_day("2025-03-04")]
    result = aggregate_to_weeks(rows, {})
    assert len(result) == 1
    week = result[0]
    assert week["week_start"] == "2025-03-03"
    assert week["orders_qty"] == 200
    assert week["sales_qty"] == 174


def test_aggregate_null_safe_division_zero_clicks():
    rows = [_make_day("2025-03-03", clicks_total=0, cart_total=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["cr_card_to_cart"] is None
    assert week["cr_total"] is None


def test_aggregate_phase_norm():
    # margin_rub=200k, sales_rub=1M → margin_pct=20% → norm
    rows = [_make_day("2025-03-03", margin_rub=200000, sales_rub=1000000,
                      adv_internal_rub=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["phase"] == "norm"


def test_aggregate_phase_decline():
    rows = [_make_day("2025-03-03", margin_rub=50000, sales_rub=1000000,
                      adv_internal_rub=0)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["phase"] == "decline"


def test_aggregate_margin_before_ads():
    rows = [_make_day("2025-03-03", margin_rub=80000, adv_internal_rub=50000,
                      sales_rub=500000)]
    week = aggregate_to_weeks(rows, {})[0]
    # margin_before_ads = 80000 + 50000 (internal) + 0 (no sheets) = 130000
    assert week["margin_before_ads_rub"] == pytest.approx(130000)


def test_aggregate_cr_uses_funnel_orders_not_financial():
    """CR должен считаться от funnel_orders_qty (CA), НЕ от orders_qty (abc_date).

    Это методологический фикс: до правки cr_total использовал orders_qty из
    abc_date, что давало смешанный источник (числитель abc / знаменатель CA).
    """
    # 600 финансовых заказов (abc_date) vs 685 воронка (CA) — реальный кейс Wendy
    rows = [_make_day("2025-03-03",
                      orders_qty=600, funnel_orders_qty=685,
                      clicks_total=57622, cart_total=3549)]
    week = aggregate_to_weeks(rows, {})[0]
    # cr_total = funnel_orders / clicks * 100 = 685/57622*100 ≈ 1.189
    assert week["cr_total"] == pytest.approx(685 / 57622 * 100, rel=0.001)
    # cr_cart_to_order = funnel_orders / cart * 100 = 685/3549*100 ≈ 19.30
    assert week["cr_cart_to_order"] == pytest.approx(685 / 3549 * 100, rel=0.001)
    # cr_card_to_cart не зависит от orders — 3549/57622*100 ≈ 6.16
    assert week["cr_card_to_cart"] == pytest.approx(3549 / 57622 * 100, rel=0.001)


def test_aggregate_exposes_both_order_counts():
    """Воронка и финансы — два разных источника, оба видны в API."""
    rows = [_make_day("2025-03-03", orders_qty=600, funnel_orders_qty=685)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["orders_qty"] == 600              # abc_date — деньги
    assert week["funnel_orders_qty"] == 685       # CA — воронка
    assert week["funnel_buyouts_qty"] == 87       # из defaults


def test_aggregate_funnel_buyout_visible():
    rows = [_make_day("2025-03-03", funnel_buyouts_qty=42)]
    week = aggregate_to_weeks(rows, {})[0]
    assert week["funnel_buyouts_qty"] == 42
