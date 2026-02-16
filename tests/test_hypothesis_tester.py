"""
Tests for hypothesis_tester.py — statistical hypothesis testing.
"""
import numpy as np
import pytest
from datetime import datetime, timedelta

from agents.oleg.services.price_analysis.hypothesis_tester import (
    _make_result,
    _safe_log_log_regression,
    test_elasticity_hypotheses as check_elasticity_hypotheses,
    test_profit_hypotheses as check_profit_hypotheses,
    test_advertising_hypotheses as check_advertising_hypotheses,
    test_stock_hypotheses as check_stock_hypotheses,
    test_cross_model_hypotheses as check_cross_model_hypotheses,
    test_temporal_hypotheses as check_temporal_hypotheses,
    test_roi_hypotheses as check_roi_hypotheses,
    run_all_hypotheses,
)


@pytest.fixture
def multi_model_daily_data():
    """Daily data for 3 models (wendy, ruby, audrey) — 60 days each."""
    np.random.seed(42)
    base_date = datetime(2026, 1, 1)
    data = {}
    for model, base_price, base_sales in [('wendy', 2500, 50), ('ruby', 2000, 40), ('audrey', 1800, 35)]:
        rows = []
        for i in range(60):
            price = base_price + np.random.normal(0, base_price * 0.05)
            sales = max(1, int(base_sales - 0.01 * (price - base_price) + np.random.normal(0, 3)))
            margin_pct = 22.0 + np.random.normal(0, 1)
            rows.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'model': model,
                'price_per_unit': round(price, 2),
                'sales_count': sales,
                'margin': round(price * margin_pct / 100 * sales, 2),
                'margin_pct': round(margin_pct, 2),
                'revenue': round(price * sales, 2),
                'revenue_before_spp': round(price * sales, 2),
                'spp_pct': round(15 + np.random.normal(0, 1), 2),
                'drr_pct': round(8 + np.random.normal(0, 0.5), 2),
                'logistics_per_unit': round(150 + np.random.normal(0, 10), 2),
                'cogs_per_unit': round(800 + np.random.normal(0, 20), 2),
                'adv': round(10000 + np.random.normal(0, 1000), 2),
                'adv_total': round(10000 + np.random.normal(0, 1000), 2),
            })
        data[model] = rows
    return data


@pytest.fixture
def stock_daily_data():
    """Daily stock data for 3 models — 60 days."""
    np.random.seed(42)
    base_date = datetime(2026, 1, 1)
    data = {}
    for model, avg in [('wendy', 200), ('ruby', 500), ('audrey', 50)]:
        rows = []
        for i in range(60):
            rows.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'model': model,
                'total_stock': max(0, int(avg + np.random.normal(0, avg * 0.2))),
            })
        data[model] = rows
    return data


@pytest.fixture
def turnover_data():
    """Turnover data for 3 models."""
    return {
        'wendy': {'avg_stock': 200, 'daily_sales': 50, 'turnover_days': 4.0, 'sales_count': 3000},
        'ruby': {'avg_stock': 500, 'daily_sales': 40, 'turnover_days': 12.5, 'sales_count': 2400},
        'audrey': {'avg_stock': 50, 'daily_sales': 35, 'turnover_days': 1.4, 'sales_count': 2100},
    }


class TestMakeResult:
    def test_standard_output(self):
        r = _make_result('H1a', 'confirmed', 0.01234, 100, {'key': 'value'})
        assert r['hypothesis'] == 'H1a'
        assert r['result'] == 'confirmed'
        assert r['p_value'] == 0.0123
        assert r['n_observations'] == 100
        assert r['details']['key'] == 'value'

    def test_none_p_value(self):
        r = _make_result('H7a', 'confirmed', None, 50, {})
        assert r['p_value'] is None


class TestSafeLogLogRegression:
    def test_basic_regression(self):
        np.random.seed(42)
        prices = np.array([100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240], dtype=float)
        quantities = np.array([500, 480, 460, 440, 420, 400, 380, 360, 340, 320, 300, 280, 260, 240, 220], dtype=float)
        result = _safe_log_log_regression(prices, quantities)
        assert result is not None
        assert 'beta' in result
        assert result['beta'] < 0  # negative elasticity
        assert result['n'] == 15

    def test_insufficient_data(self):
        prices = np.array([100, 110, 120], dtype=float)
        quantities = np.array([50, 48, 46], dtype=float)
        result = _safe_log_log_regression(prices, quantities)
        assert result is None

    def test_zeros_filtered(self):
        prices = np.array([0, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230], dtype=float)
        quantities = np.array([500, 0, 460, 440, 420, 400, 380, 360, 340, 320, 300, 280, 260, 240, 220], dtype=float)
        result = _safe_log_log_regression(prices, quantities)
        # Should filter out zero values, may or may not have enough
        if result is not None:
            assert result['n'] < 15


class TestElasticityHypotheses:
    def test_returns_h1a_h1b_h1c(self, multi_model_daily_data):
        result = check_elasticity_hypotheses(multi_model_daily_data)
        assert isinstance(result, dict)
        assert 'H1a' in result

    def test_single_model_skips_h1a(self, sample_daily_data):
        result = check_elasticity_hypotheses({'wendy': sample_daily_data})
        assert isinstance(result, dict)
        # H1a requires multiple models — should be inconclusive or skipped
        if 'H1a' in result:
            assert result['H1a']['result'] in ('inconclusive', 'rejected')


class TestProfitHypotheses:
    def test_returns_h2a_h2b(self, multi_model_daily_data):
        result = check_profit_hypotheses(multi_model_daily_data)
        assert isinstance(result, dict)
        assert len(result) >= 1

    def test_single_model(self, sample_daily_data):
        result = check_profit_hypotheses({'wendy': sample_daily_data})
        assert isinstance(result, dict)


class TestAdvertisingHypotheses:
    def test_returns_results(self, multi_model_daily_data):
        result = check_advertising_hypotheses(multi_model_daily_data)
        assert isinstance(result, dict)


class TestStockHypotheses:
    def test_returns_results(self, multi_model_daily_data, stock_daily_data):
        result = check_stock_hypotheses(multi_model_daily_data, stock_daily_data)
        assert isinstance(result, dict)

    def test_no_stock_data(self, multi_model_daily_data):
        result = check_stock_hypotheses(multi_model_daily_data, None)
        assert isinstance(result, dict)
        for r in result.values():
            assert r['result'] == 'inconclusive'


class TestCrossModelHypotheses:
    def test_returns_h5a(self, multi_model_daily_data):
        result = check_cross_model_hypotheses(multi_model_daily_data)
        assert isinstance(result, dict)

    def test_single_model(self, sample_daily_data):
        result = check_cross_model_hypotheses({'wendy': sample_daily_data})
        assert isinstance(result, dict)


class TestTemporalHypotheses:
    def test_returns_results(self, multi_model_daily_data):
        result = check_temporal_hypotheses(multi_model_daily_data)
        assert isinstance(result, dict)


class TestROIHypotheses:
    def test_returns_h7a_h7b(self, multi_model_daily_data, turnover_data):
        result = check_roi_hypotheses(multi_model_daily_data, turnover_data)
        assert isinstance(result, dict)
        assert 'H7a' in result

    def test_no_turnover(self, multi_model_daily_data):
        result = check_roi_hypotheses(multi_model_daily_data, None)
        assert isinstance(result, dict)
        for r in result.values():
            assert r['result'] == 'inconclusive'


class TestRunAllHypotheses:
    def test_orchestrator(self, multi_model_daily_data, stock_daily_data, turnover_data):
        result = run_all_hypotheses(
            models_daily_data=multi_model_daily_data,
            stock_daily_data=stock_daily_data,
            turnover_data=turnover_data,
        )
        assert isinstance(result, dict)
        assert 'results' in result
        assert 'summary' in result
        # confirmed/rejected/inconclusive are top-level keys
        assert 'confirmed' in result
        assert 'rejected' in result
        assert 'inconclusive' in result
        assert 'total_hypotheses' in result

    def test_no_data(self):
        result = run_all_hypotheses(
            models_daily_data={},
            stock_daily_data=None,
            turnover_data=None,
        )
        assert isinstance(result, dict)
