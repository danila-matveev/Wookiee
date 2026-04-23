"""Тесты scenario_engine."""
import pytest
from services.wb_localization.calculators.scenario_engine import analyze_scenarios


@pytest.fixture
def sample_il_irp():
    return {
        "articles": [
            {
                "article": "wendy/xl",
                "loc_pct": 40.0,
                "ktr": 1.30,
                "krp_pct": 2.10,
                "wb_total": 100,
                "price": 1000.0,
                "irp_per_month": 2100.0,
            },
            {
                "article": "sunny/m",
                "loc_pct": 80.0,
                "ktr": 0.80,
                "krp_pct": 0.00,
                "wb_total": 50,
                "price": 2000.0,
                "irp_per_month": 0.0,
            },
        ],
        "summary": {
            "overall_il": 1.13,
            "total_rf_orders": 150,
        },
    }


@pytest.fixture
def sample_logistics_costs():
    return {
        "wendy/xl": 5200.0,
        "sunny/m": 3200.0,
    }


def test_analyze_scenarios_returns_all_levels(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    scenarios = result["scenarios"]
    levels = [s["level_pct"] for s in scenarios]
    assert levels == [30, 40, 50, 60, 70, 80, 90]


def test_scenario_has_required_fields(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    first = result["scenarios"][0]
    assert "level_pct" in first
    assert "ktr" in first
    assert "krp_pct" in first
    assert "logistics_monthly" in first
    assert "irp_monthly" in first
    assert "total_monthly" in first
    assert "delta_vs_current" in first
    assert "color" in first


def test_60pct_scenario_has_zero_irp(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    sc_60 = next(s for s in result["scenarios"] if s["level_pct"] == 60)
    assert sc_60["irp_monthly"] == 0.0


def test_higher_localization_means_lower_total(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    totals = [s["total_monthly"] for s in result["scenarios"]]
    assert totals[0] >= totals[-1]


def test_top_articles_sorted_by_savings(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    top = result["top_articles"]
    assert top[0]["article"] == "wendy/xl"
    savings = [a["savings_if_80_monthly"] for a in top]
    assert savings == sorted(savings, reverse=True)


def test_relocation_economics_calculates_breakeven(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    econ = result["relocation_economics"]
    assert econ["commission_monthly"] == pytest.approx(1000.0, rel=0.01)
    assert econ["lock_in_days"] == 90
    assert "net_benefit_monthly" in econ


def test_current_scenario_matches_current_il(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    current = result["current_scenario"]
    assert current["label"] == "Сейчас"
    assert "logistics_monthly" in current
    assert "irp_monthly" in current


def test_custom_levels(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
        levels=[50, 75, 95],
    )
    levels = [s["level_pct"] for s in result["scenarios"]]
    assert levels == [50, 75, 95]
