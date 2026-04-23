"""Тесты relocation_forecaster."""
import pytest
from services.wb_localization.calculators.relocation_forecaster import (
    simulate_roadmap,
    schedule_movements_by_week,
)


@pytest.fixture
def sample_articles():
    return [
        {
            "article": "wendy/xl",
            "loc_pct": 40.0,
            "ktr": 1.30,
            "krp_pct": 2.10,
            "wb_total": 100,
            "price": 1000.0,
            "stock_total": 500,
        },
        {
            "article": "sunny/m",
            "loc_pct": 80.0,
            "ktr": 0.80,
            "krp_pct": 0.00,
            "wb_total": 50,
            "price": 2000.0,
            "stock_total": 200,
        },
    ]


@pytest.fixture
def sample_movements():
    return [
        {
            "article": "wendy/xl",
            "qty": 120,
            "from_warehouse": "Коледино",
            "to_warehouse": "Екатеринбург",
            "impact_rub": 5000.0,
        },
    ]


@pytest.fixture
def sample_logistics_costs():
    return {"wendy/xl": 5200.0, "sunny/m": 3200.0}


@pytest.fixture
def redistribution_limits():
    return {"Коледино": 100_000, "Екатеринбург": 100_000}


def test_simulate_returns_14_weeks(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Прогноз на неделю 0 (старт) + 13 недель = 14 строк."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.3,
        period_days=30,
    )
    assert len(result["roadmap"]) == 14


def test_week_0_is_current_state(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Неделя 0 = текущее состояние (0 перемещено, 0 экономии)."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.3,
        period_days=30,
    )
    week_0 = result["roadmap"][0]
    assert week_0["week"] == 0
    assert week_0["moved_units_cumulative"] == 0
    assert week_0["savings_vs_current"] == 0.0


def test_week_13_shows_full_effect(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Неделя 13 = полное выветривание старых данных, максимальный эффект."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    week_13 = result["roadmap"][-1]
    assert week_13["il_forecast"] > result["roadmap"][0]["il_forecast"]


def test_blending_formula(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Проверка монотонности роста индекса."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    week_0_il = result["roadmap"][0]["il_forecast"]
    week_7_il = result["roadmap"][7]["il_forecast"]
    week_13_il = result["roadmap"][-1]["il_forecast"]
    assert week_0_il < week_7_il < week_13_il


def test_detects_milestone_60pct(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Определение недели пересечения порога 60% (когда КРП→0)."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    milestones = result["milestones"]
    assert "week_60pct" in milestones


def test_realistic_limit_pct_affects_schedule(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Меньший % лимитов = движение растягивается на больше недель."""
    result_fast = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    result_slow = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.1,
        period_days=30,
    )
    assert result_fast["roadmap"][1]["moved_units_cumulative"] >= result_slow["roadmap"][1]["moved_units_cumulative"]


def test_schedule_movements_distributes_by_priority():
    """schedule_movements_by_week распределяет по приоритету импакта."""
    movements = [
        {"article": "A", "qty": 1000, "to_warehouse": "Коледино", "impact_rub": 100},
        {"article": "B", "qty": 1000, "to_warehouse": "Коледино", "impact_rub": 10000},
    ]
    limits = {"Коледино": 500}
    schedule = schedule_movements_by_week(movements, limits, realistic_limit_pct=1.0)
    week_0_articles = [m["article"] for m in schedule.get(0, [])]
    assert "B" in week_0_articles
