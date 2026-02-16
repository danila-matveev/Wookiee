#!/usr/bin/env python3
"""
Integration tests for price analysis system.
Requires real PostgreSQL connection (reads from .env).

Usage:
    python scripts/test_price_analysis.py --test all
    python scripts/test_price_analysis.py --test data_layer
    python scripts/test_price_analysis.py --test regression --model wendy
    python scripts/test_price_analysis.py --test recommendations
    python scripts/test_price_analysis.py --test scenarios --model wendy
    python scripts/test_price_analysis.py --test learning
"""
import argparse
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Setup path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

MODELS = ['wendy', 'ruby', 'set_vuki']
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


def _status(ok: bool) -> str:
    return PASS if ok else FAIL


def test_data_layer(model: str = None):
    """Test all 8 price SQL functions against real DB."""
    print("\n=== Test: Data Layer SQL Functions ===\n")

    from shared.data_layer import (
        get_wb_price_margin_daily,
        get_ozon_price_margin_daily,
        get_wb_price_changes,
        get_ozon_price_changes,
        get_wb_spp_history_by_model,
        get_wb_price_margin_by_model_period,
        get_ozon_price_margin_by_model_period,
    )

    end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    tests = [
        ("get_wb_price_margin_daily", lambda: get_wb_price_margin_daily(start, end, model)),
        ("get_ozon_price_margin_daily", lambda: get_ozon_price_margin_daily(start, end, model)),
        ("get_wb_price_changes", lambda: get_wb_price_changes(start, end, model)),
        ("get_ozon_price_changes", lambda: get_ozon_price_changes(start, end, model)),
        ("get_wb_spp_history_by_model", lambda: get_wb_spp_history_by_model(start, end, model)),
        ("get_wb_price_margin_by_model_period", lambda: get_wb_price_margin_by_model_period(start, end)),
        ("get_ozon_price_margin_by_model_period", lambda: get_ozon_price_margin_by_model_period(start, end)),
    ]

    passed = 0
    for name, func in tests:
        try:
            data = func()
            ok = isinstance(data, list)
            has_data = len(data) > 0
            print(f"  [{_status(ok and has_data)}] {name}: {len(data)} rows")

            if has_data and 'price_per_unit' in (data[0] if isinstance(data[0], dict) else {}):
                prices = [d['price_per_unit'] for d in data if d.get('price_per_unit')]
                if prices:
                    assert all(p > 0 for p in prices), "Prices must be > 0"
                    print(f"         price range: {min(prices):.0f} — {max(prices):.0f}")

            if ok and has_data:
                passed += 1
            elif ok:
                print(f"         [WARNING] No data returned for period {start} — {end}")
                passed += 1  # empty is ok for some queries
        except Exception as e:
            print(f"  [{FAIL}] {name}: {type(e).__name__}: {e}")

    print(f"\nData Layer: {passed}/{len(tests)} passed")
    return passed == len(tests)


def test_regression(model: str = 'wendy'):
    """Test regression engine with real data."""
    print(f"\n=== Test: Regression Engine (model={model}) ===\n")

    from shared.data_layer import get_wb_price_margin_daily
    from agents.oleg.services.price_analysis.regression_engine import (
        estimate_price_elasticity,
        compute_correlation_matrix,
        detect_price_trend,
        margin_factor_regression,
    )

    end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    data = get_wb_price_margin_daily(start, end, model)
    print(f"  Data points: {len(data)}")

    if not data:
        print(f"  [{SKIP}] No data for {model} on WB")
        return True

    passed = 0
    total = 4

    # 1. Elasticity
    e = estimate_price_elasticity(data)
    if 'error' in e:
        print(f"  [{SKIP}] Elasticity: {e['error']}")
    else:
        ok_beta = -5.0 <= e['elasticity'] <= 1.0
        ok_r2 = 0 <= e['r_squared'] <= 1
        ok_p = 0 <= e['p_value'] <= 1
        ok = ok_beta and ok_r2 and ok_p
        print(f"  [{_status(ok)}] Elasticity: β={e['elasticity']}, R²={e['r_squared']}, "
              f"p={e['p_value']}, {e['interpretation']}")
        if ok:
            passed += 1

    # 2. Correlation matrix
    corr = compute_correlation_matrix(data)
    if 'error' in corr:
        print(f"  [{SKIP}] Correlations: {corr['error']}")
    else:
        n_corr = len(corr.get('correlations', {}))
        all_valid = all(
            -1 <= c['pearson_r'] <= 1
            for c in corr['correlations'].values()
        )
        print(f"  [{_status(all_valid)}] Correlations: {n_corr} metrics, all in [-1, 1]")
        if all_valid:
            passed += 1

    # 3. Price trend
    trend = detect_price_trend(data)
    if 'error' in trend:
        print(f"  [{SKIP}] Trend: {trend['error']}")
    else:
        ok = trend['trend'] in ('rising', 'falling', 'stable')
        print(f"  [{_status(ok)}] Trend: {trend['trend']} "
              f"(τ={trend['mann_kendall_tau']}, p={trend['mann_kendall_p']})")
        if ok:
            passed += 1

    # 4. Factor regression
    factors = margin_factor_regression(data)
    if 'error' in factors:
        print(f"  [{SKIP}] Factor regression: {factors['error']}")
    else:
        ok = 0 <= factors['r_squared'] <= 1
        strongest = factors.get('strongest_factor', '?')
        print(f"  [{_status(ok)}] Factor regression: R²={factors['r_squared']}, "
              f"strongest={strongest}")
        if ok:
            passed += 1

    print(f"\nRegression ({model}): {passed}/{total} passed")
    return passed >= 2  # at least 2 should pass


def test_recommendations():
    """Test recommendation engine with real data."""
    print("\n=== Test: Recommendation Engine ===\n")

    from shared.data_layer import get_wb_price_margin_daily
    from agents.oleg.services.price_analysis.recommendation_engine import generate_recommendations

    end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    passed = 0
    for model in MODELS:
        data = get_wb_price_margin_daily(start, end, model)
        if not data or len(data) < 14:
            print(f"  [{SKIP}] {model}: insufficient data ({len(data)} days)")
            continue

        rec = generate_recommendations(data, model, 'wb')
        if 'error' in rec and 'elasticity_error' in str(rec.get('error', '')):
            print(f"  [{SKIP}] {model}: {rec['error']}")
            continue

        ok_action = rec.get('action') in ('increase_price', 'decrease_price', 'hold')
        ok_confidence = rec.get('confidence') in ('high', 'medium', 'low')
        ok_scenarios = len(rec.get('scenarios', [])) == 6

        ok = ok_action and ok_confidence
        status = _status(ok)
        print(f"  [{status}] {model}: action={rec.get('action')}, "
              f"confidence={rec.get('confidence')}, scenarios={len(rec.get('scenarios', []))}")

        if rec.get('action') != 'hold' and 'recommended' in rec:
            impact = rec['recommended'].get('predicted_impact', {})
            print(f"         margin_change={impact.get('margin_rub_change_per_day')}₽/day, "
                  f"volume_change={impact.get('volume_change_pct')}%")

        if ok:
            passed += 1

    print(f"\nRecommendations: {passed}/{len(MODELS)} passed")
    return passed >= 1


def test_scenarios(model: str = 'wendy'):
    """Test scenario modeler with real data."""
    print(f"\n=== Test: Scenario Modeler (model={model}) ===\n")

    from shared.data_layer import get_wb_price_margin_daily
    from agents.oleg.services.price_analysis.scenario_modeler import (
        simulate_price_change,
        counterfactual_analysis,
    )

    end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    data = get_wb_price_margin_daily(start, end, model)
    if not data or len(data) < 14:
        print(f"  [{SKIP}] No data for {model}")
        return True

    passed = 0

    # +10%
    sim_up = simulate_price_change(data, price_change_pct=10.0, model=model, channel='wb')
    if 'error' not in sim_up:
        ok = sim_up['predicted']['price_per_unit'] > sim_up['baseline']['price_per_unit']
        print(f"  [{_status(ok)}] +10%: price {sim_up['baseline']['price_per_unit']:.0f} → "
              f"{sim_up['predicted']['price_per_unit']:.0f}")
        if ok:
            passed += 1
    else:
        print(f"  [{SKIP}] +10%: {sim_up['error']}")

    # -10%
    sim_down = simulate_price_change(data, price_change_pct=-10.0, model=model, channel='wb')
    if 'error' not in sim_down:
        ok = sim_down['predicted']['price_per_unit'] < sim_down['baseline']['price_per_unit']
        print(f"  [{_status(ok)}] -10%: price {sim_down['baseline']['price_per_unit']:.0f} → "
              f"{sim_down['predicted']['price_per_unit']:.0f}")
        if ok:
            passed += 1
    else:
        print(f"  [{SKIP}] -10%: {sim_down['error']}")

    # Counterfactual
    cf_start = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    cf_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cf = counterfactual_analysis(data, 5.0, cf_start, cf_end, model, 'wb')
    if 'error' not in cf:
        ok = 'actual' in cf and 'hypothetical' in cf and 'delta' in cf
        print(f"  [{_status(ok)}] Counterfactual: actual margin={cf['actual']['total_margin']:.0f}, "
              f"hypothetical={cf['hypothetical']['total_margin']:.0f}, "
              f"delta={cf['delta']['margin_difference']:.0f}")
        if ok:
            passed += 1
    else:
        print(f"  [{SKIP}] Counterfactual: {cf['error']}")

    print(f"\nScenarios ({model}): {passed}/3 passed")
    return passed >= 1


def test_learning():
    """Test learning store CRUD cycle."""
    print("\n=== Test: Learning Store ===\n")
    import tempfile

    from agents.oleg.services.price_analysis.learning_store import LearningStore

    # Use temp DB for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    store = LearningStore(db_path=db_path)
    passed = 0

    # Save recommendation
    rec = {
        'model': 'wendy', 'channel': 'wb', 'action': 'increase_price',
        'confidence': 'high',
        'current_metrics': {'price_per_unit': 2500},
        'elasticity': {'elasticity': -0.5, 'r_squared': 0.6},
        'recommended': {
            'price_change_pct': 5.0, 'new_price': 2625,
            'predicted_impact': {'margin_rub_change_per_day': 3000, 'volume_change_pct': -2.5},
            'reasoning': 'Test',
        },
    }
    rec_id = store.save_recommendation(rec)
    ok = rec_id > 0
    print(f"  [{_status(ok)}] save_recommendation → id={rec_id}")
    if ok:
        passed += 1

    # Retrieve
    recs = store.get_recommendations(model='wendy')
    ok = len(recs) >= 1
    print(f"  [{_status(ok)}] get_recommendations → {len(recs)} recs")
    if ok:
        passed += 1

    # Record outcome
    store.record_outcome(rec_id, {
        'actual_margin_impact': 2800,
        'actual_volume_impact': -2.0,
    })
    recs_after = store.get_recommendations(model='wendy')
    checked = next((r for r in recs_after if r['id'] == rec_id), {})
    ok = checked.get('outcome_checked') == 1
    print(f"  [{_status(ok)}] record_outcome → checked={checked.get('outcome_checked')}")
    if ok:
        passed += 1

    # Accuracy
    accuracy = store.get_prediction_accuracy()
    ok = accuracy.get('n_checked', 0) >= 1
    print(f"  [{_status(ok)}] get_prediction_accuracy → n={accuracy.get('n_checked')}, "
          f"margin_mape={accuracy.get('margin_mape')}")
    if ok:
        passed += 1

    # Cache elasticity
    store.cache_elasticity('wendy', 'wb', {'elasticity': -0.7, 'r_squared': 0.5}, '2026-01-01', '2026-01-30')
    cached = store.get_elasticity_cached('wendy', 'wb')
    ok = cached is not None and cached['elasticity'] == -0.7
    print(f"  [{_status(ok)}] cache_elasticity → retrieved elasticity={cached.get('elasticity') if cached else None}")
    if ok:
        passed += 1

    # Cleanup
    os.unlink(db_path)

    print(f"\nLearning Store: {passed}/5 passed")
    return passed == 5


def main():
    parser = argparse.ArgumentParser(description='Integration tests for price analysis')
    parser.add_argument('--test', default='all',
                        choices=['all', 'data_layer', 'regression', 'recommendations', 'scenarios', 'learning'])
    parser.add_argument('--model', default='wendy')
    args = parser.parse_args()

    results = {}

    if args.test in ('all', 'data_layer'):
        results['data_layer'] = test_data_layer(args.model)

    if args.test in ('all', 'regression'):
        results['regression'] = test_regression(args.model)

    if args.test in ('all', 'recommendations'):
        results['recommendations'] = test_recommendations()

    if args.test in ('all', 'scenarios'):
        results['scenarios'] = test_scenarios(args.model)

    if args.test in ('all', 'learning'):
        results['learning'] = test_learning()

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for name, passed in results.items():
        print(f"  {name}: {PASS if passed else FAIL}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
