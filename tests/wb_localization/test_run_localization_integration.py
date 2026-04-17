"""Интеграционный smoke-тест run_localization.

Покрывает helper-функции, добавленные в Task 10:
- _calculate_turnover_from_orders (несколько источников)
- _extract_weekly_snapshots (агрегация по артикул+регион)
- _enrich_movements_with_impact (добавление impact_rub)
- _build_movements_plan (приоритизация и сортировка)

И один смоук на build_reference_content (используется в --only-reference).
"""
from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# build_reference_content
# ---------------------------------------------------------------------------

def test_only_reference_mode_skips_full_analysis():
    """В режиме --only-reference build_reference_content работает сам по себе."""
    from services.wb_localization.calculators.reference_builder import (
        build_reference_content,
    )

    result = build_reference_content()
    assert "cover" in result
    assert "il_section" in result
    assert "irp_section" in result
    assert "relocation_section" in result


# ---------------------------------------------------------------------------
# helper functions exist
# ---------------------------------------------------------------------------

def test_helper_functions_are_defined():
    """Все новые helper-функции должны импортироваться."""
    from services.wb_localization.run_localization import (
        _build_movements_plan,
        _calculate_turnover_from_orders,
        _enrich_movements_with_impact,
        _extract_weekly_snapshots,
        _movements_df_to_dicts,
    )

    assert callable(_calculate_turnover_from_orders)
    assert callable(_extract_weekly_snapshots)
    assert callable(_enrich_movements_with_impact)
    assert callable(_build_movements_plan)
    assert callable(_movements_df_to_dicts)


# ---------------------------------------------------------------------------
# _calculate_turnover_from_orders
# ---------------------------------------------------------------------------

def test_calculate_turnover_from_orders_with_total_price():
    from services.wb_localization.run_localization import (
        _calculate_turnover_from_orders,
    )

    df = pd.DataFrame([{"totalPrice": 1000}, {"totalPrice": 500}])
    assert _calculate_turnover_from_orders(df) == 1500.0


def test_calculate_turnover_handles_empty_df():
    from services.wb_localization.run_localization import (
        _calculate_turnover_from_orders,
    )

    assert _calculate_turnover_from_orders(pd.DataFrame()) == 0.0
    assert _calculate_turnover_from_orders(None) == 0.0
    assert _calculate_turnover_from_orders([]) == 0.0


def test_calculate_turnover_from_wb_api_list():
    """WB API возвращает список dict'ов — тоже должен работать."""
    from services.wb_localization.run_localization import (
        _calculate_turnover_from_orders,
    )

    orders = [
        {"totalPrice": 1000, "isCancel": False},
        {"totalPrice": 500, "isCancel": False},
        {"totalPrice": 999, "isCancel": True},  # отменён — не считаем
    ]
    assert _calculate_turnover_from_orders(orders) == 1500.0


def test_calculate_turnover_price_disc_fallback():
    from services.wb_localization.run_localization import (
        _calculate_turnover_from_orders,
    )

    df = pd.DataFrame([{"priceWithDisc": 300}, {"priceWithDisc": 200}])
    assert _calculate_turnover_from_orders(df) == 500.0


# ---------------------------------------------------------------------------
# _extract_weekly_snapshots
# ---------------------------------------------------------------------------

def test_extract_weekly_snapshots_basic():
    from services.wb_localization.run_localization import (
        _extract_weekly_snapshots,
    )

    df = pd.DataFrame(
        [
            {
                "Артикул продавца": "wendy/xl",
                "Регион": "Центральный",
                "Заказы со склада ВБ локально, шт": 5,
                "Заказы со склада ВБ не локально, шт": 3,
            },
            {
                "Артикул продавца": "wendy/xl",
                "Регион": "Центральный",
                "Заказы со склада ВБ локально, шт": 2,
                "Заказы со склада ВБ не локально, шт": 1,
            },
            {
                "Артикул продавца": "vuki/black",
                "Регион": "Поволжье",
                "Заказы со склада ВБ локально, шт": 10,
                "Заказы со склада ВБ не локально, шт": 0,
            },
        ]
    )
    snapshots = _extract_weekly_snapshots(df, "ip")
    # wendy/xl должен быть склеен в одну запись
    assert len(snapshots) == 2
    wendy = next(s for s in snapshots if s["article"] == "wendy/xl")
    assert wendy["local_orders"] == 7
    assert wendy["nonlocal_orders"] == 4
    assert wendy["region"] == "Центральный"


def test_extract_weekly_snapshots_empty_df():
    from services.wb_localization.run_localization import (
        _extract_weekly_snapshots,
    )

    assert _extract_weekly_snapshots(pd.DataFrame(), "ip") == []
    assert _extract_weekly_snapshots(None, "ip") == []


# ---------------------------------------------------------------------------
# _build_movements_plan
# ---------------------------------------------------------------------------

def test_build_movements_plan_sorts_by_impact():
    from services.wb_localization.run_localization import _build_movements_plan

    movements = [
        {"article": "A", "to_warehouse": "W1", "impact_rub": 100, "qty": 10},
        {"article": "B", "to_warehouse": "W1", "impact_rub": 5000, "qty": 20},
    ]
    schedule = {"0": [{"article": "B", "to_warehouse": "W1"}]}
    plan = _build_movements_plan(movements, schedule)
    assert plan[0]["article"] == "B"  # higher impact first
    assert plan[0]["priority"] == "P2"  # impact 5000 → P2 (>1000, ≤10000)
    assert plan[1]["priority"] == "P3"  # impact 100 → P3


def test_build_movements_plan_p1_threshold():
    from services.wb_localization.run_localization import _build_movements_plan

    movements = [
        {"article": "X", "to_warehouse": "W", "impact_rub": 50000, "qty": 100},
    ]
    plan = _build_movements_plan(movements, {})
    assert plan[0]["priority"] == "P1"


def test_build_movements_plan_empty():
    from services.wb_localization.run_localization import _build_movements_plan

    assert _build_movements_plan([], {}) == []


# ---------------------------------------------------------------------------
# _enrich_movements_with_impact
# ---------------------------------------------------------------------------

def test_enrich_movements_with_impact_basic():
    from services.wb_localization.run_localization import (
        _enrich_movements_with_impact,
    )

    il_irp = {
        "articles": [
            {
                "article": "wendy/xl",
                "ktr": 1.2,
                "krp_pct": 1.5,
                "price": 1000,
                "wb_total": 100,
            }
        ]
    }
    movements = [{"article": "wendy/xl", "qty": 10, "to_warehouse": "Коледино"}]
    out = _enrich_movements_with_impact(
        movements, il_irp, logistics_costs={}, period_days=30,
    )
    assert len(out) == 1
    # savings_per_unit = (1000 * 1.5 / 100) / 100 = 0.15
    # impact = 10 * 0.15 * 30 / 30 = 1.5
    assert out[0]["impact_rub"] > 0


def test_enrich_movements_empty():
    from services.wb_localization.run_localization import (
        _enrich_movements_with_impact,
    )

    assert _enrich_movements_with_impact([], {"articles": []}, {}, 30) == []


# ---------------------------------------------------------------------------
# _movements_df_to_dicts
# ---------------------------------------------------------------------------

def test_movements_df_to_dicts_converts_v3_format():
    from services.wb_localization.run_localization import _movements_df_to_dicts

    df = pd.DataFrame(
        [
            {
                "Артикул": "wendy/xl",
                "Размер": "XL",
                "Кол-во": 10,
                "Куда склад": "Коледино",
                "Откуда регион": "Центральный",
                "Куда регион": "Поволжье",
                "Индекс SKU, %": 40.0,
            },
            {  # qty <= 0 — отфильтруется
                "Артикул": "skip",
                "Размер": "",
                "Кол-во": 0,
                "Куда склад": "Коледино",
                "Откуда регион": "",
                "Куда регион": "",
                "Индекс SKU, %": 0,
            },
        ]
    )
    out = _movements_df_to_dicts(df)
    assert len(out) == 1
    assert out[0]["article"] == "wendy/xl"
    assert out[0]["qty"] == 10
    assert out[0]["to_warehouse"] == "Коледино"


def test_movements_df_to_dicts_empty():
    from services.wb_localization.run_localization import _movements_df_to_dicts

    assert _movements_df_to_dicts(pd.DataFrame()) == []
    assert _movements_df_to_dicts(None) == []


# ---------------------------------------------------------------------------
# CLI flags
# ---------------------------------------------------------------------------

def test_cli_flags_defined():
    """Все 4 новых CLI-флага должны быть определены в parse_args."""
    import sys
    from services.wb_localization.run_localization import parse_args

    old_argv = sys.argv
    try:
        sys.argv = [
            "run_localization.py",
            "--cabinet", "ip",
            "--skip-scenarios",
            "--skip-forecast",
            "--realistic-limit-pct", "0.5",
            "--only-reference",
        ]
        args = parse_args()
        assert args.skip_scenarios is True
        assert args.skip_forecast is True
        assert args.realistic_limit_pct == 0.5
        assert args.only_reference is True
    finally:
        sys.argv = old_argv


def test_cli_flags_defaults():
    """Дефолтные значения новых флагов."""
    import sys
    from services.wb_localization.run_localization import parse_args

    old_argv = sys.argv
    try:
        sys.argv = ["run_localization.py"]
        args = parse_args()
        assert args.skip_scenarios is False
        assert args.skip_forecast is False
        assert args.realistic_limit_pct == 0.3
        assert args.only_reference is False
    finally:
        sys.argv = old_argv
