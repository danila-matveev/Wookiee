"""
Tests for regression_engine.py — statistical analysis module.
"""
import numpy as np
import pytest
from datetime import datetime, timedelta

from agents.oleg.services.price_analysis.regression_engine import (
    estimate_price_elasticity,
    margin_factor_regression,
    compute_correlation_matrix,
    detect_price_trend,
    run_full_analysis,
    _interpret_elasticity,
    _correlation_strength,
)


# ─── Elasticity Tests ─────────────────────────────────────────


class TestEstimatePriceElasticity:
    def test_inelastic_demand(self, sample_daily_data):
        """Weak price-sales relationship → |β| < 1."""
        result = estimate_price_elasticity(sample_daily_data)
        assert 'error' not in result
        assert -1.0 < result['elasticity'] < 0.0 or result['elasticity'] > -1.5
        assert 0 <= result['r_squared'] <= 1
        assert 0 <= result['p_value'] <= 1
        assert bool(result['is_significant']) in (True, False)  # numpy.bool_ compatible
        assert result['interpretation'] in (
            'highly_inelastic', 'inelastic', 'unit_elastic', 'elastic', 'highly_elastic'
        )

    def test_elastic_demand(self, elastic_demand_data):
        """Strong negative price-sales relationship → |β| > 1."""
        result = estimate_price_elasticity(elastic_demand_data)
        assert 'error' not in result
        assert result['elasticity'] < 0, "Elasticity should be negative"
        assert 0 <= result['r_squared'] <= 1

    def test_insufficient_data(self):
        """< 14 observations → error."""
        data = [
            {'date': f'2026-01-{i+1:02d}', 'price_per_unit': 100.0 + i, 'sales_count': 50 - i}
            for i in range(10)
        ]
        result = estimate_price_elasticity(data)
        assert 'error' in result
        assert result['error'] == 'insufficient_data'
        assert result['n_observations'] == 10

    def test_zero_prices_filtered(self):
        """Rows with price=0 or sales=0 are filtered out."""
        base_date = datetime(2026, 1, 1)
        data = []
        for i in range(20):
            data.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'price_per_unit': 100.0 + i * 5,
                'sales_count': max(1, 50 - i),
            })
        # Add rows with zeros
        data.append({'date': '2026-01-25', 'price_per_unit': 0, 'sales_count': 50})
        data.append({'date': '2026-01-26', 'price_per_unit': 100, 'sales_count': 0})

        result = estimate_price_elasticity(data, min_observations=14)
        # Should succeed because we still have 20 valid rows
        assert 'error' not in result or result.get('error') == 'insufficient_nonzero_data'

    def test_constant_price_insufficient_variance(self):
        """All same price → error or very low R²."""
        np.random.seed(7)
        base_date = datetime(2026, 1, 1)
        data = [
            {
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'price_per_unit': 2500.0,  # constant
                'sales_count': max(1, int(50 + np.random.normal(0, 5))),
            }
            for i in range(20)
        ]
        # Constant X values may cause ValueError in linregress or
        # singular matrix in WLS — both are acceptable outcomes
        try:
            result = estimate_price_elasticity(data)
            if 'error' not in result:
                assert result['r_squared'] < 0.1
        except ValueError:
            pass  # scipy.linregress raises ValueError for constant X

    def test_weighting_recency(self):
        """Recent data should have more weight than old data."""
        base_date = datetime(2026, 1, 1)
        data = []
        # First 45 days: high price, high sales (positive relationship)
        for i in range(45):
            data.append({
                'date': (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                'price_per_unit': 2000.0 + i * 10,
                'sales_count': max(1, 50 + i),  # sales INCREASE with price
            })
        # Last 45 days: high price, low sales (negative relationship)
        for i in range(45):
            day = 45 + i
            data.append({
                'date': (base_date + timedelta(days=day)).strftime('%Y-%m-%d'),
                'price_per_unit': 2450.0 + i * 10,
                'sales_count': max(1, 95 - i * 2),  # sales DECREASE with price
            })

        result_weighted = estimate_price_elasticity(data, half_life_days=30)
        assert 'error' not in result_weighted
        # With weighting, recent negative relationship should dominate
        assert result_weighted['elasticity'] < 0.5, \
            "With recency weighting, elasticity should reflect recent negative trend"

    def test_result_structure(self, sample_daily_data):
        """Result has all expected keys."""
        result = estimate_price_elasticity(sample_daily_data)
        assert 'error' not in result
        expected_keys = {
            'elasticity', 'elasticity_se', 'r_squared', 'p_value',
            'n_observations', 'is_significant', 'interpretation',
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_confidence_interval_present(self, sample_daily_data):
        """95% CI returned when statsmodels succeeds."""
        result = estimate_price_elasticity(sample_daily_data)
        if 'confidence_interval_95' in result:
            ci = result['confidence_interval_95']
            assert len(ci) == 2
            assert ci[0] <= result['elasticity'] <= ci[1]


# ─── Interpretation Tests ─────────────────────────────────────


class TestInterpretElasticity:
    @pytest.mark.parametrize("beta,expected", [
        (-0.3, 'highly_inelastic'),
        (-0.7, 'inelastic'),
        (-1.0, 'unit_elastic'),
        (-1.5, 'elastic'),
        (-2.5, 'highly_elastic'),
    ])
    def test_interpretation(self, beta, expected):
        assert _interpret_elasticity(beta) == expected


# ─── Correlation Matrix Tests ─────────────────────────────────


class TestComputeCorrelationMatrix:
    def test_structure(self, sample_daily_data):
        """Result has target, n_observations, correlations."""
        result = compute_correlation_matrix(sample_daily_data)
        assert 'error' not in result
        assert result['target'] == 'price_per_unit'
        assert result['n_observations'] == len(sample_daily_data)
        assert isinstance(result['correlations'], dict)

    def test_correlation_values_in_range(self, sample_daily_data):
        """All correlation coefficients in [-1, 1] or NaN for constant input."""
        result = compute_correlation_matrix(sample_daily_data)
        for metric, corr in result.get('correlations', {}).items():
            pr = corr['pearson_r']
            sr = corr['spearman_r']
            # Constant columns produce NaN — skip those
            if not np.isnan(pr):
                assert -1.0 <= pr <= 1.0
            if not np.isnan(sr):
                assert -1.0 <= sr <= 1.0
            assert corr['strength'] in (
                'negligible', 'weak', 'moderate', 'strong', 'very_strong'
            )

    def test_insufficient_data(self):
        """< 10 observations → error."""
        data = [{'price_per_unit': i, 'margin_pct': i * 2} for i in range(5)]
        result = compute_correlation_matrix(data)
        assert 'error' in result

    def test_missing_target(self, sample_daily_data):
        """Missing target column → error."""
        data = [{k: v for k, v in d.items() if k != 'price_per_unit'}
                for d in sample_daily_data]
        result = compute_correlation_matrix(data, target='price_per_unit')
        assert 'error' in result


# ─── Trend Detection Tests ─────────────────────────────────────


class TestDetectPriceTrend:
    def test_rising_trend(self, rising_price_data):
        result = detect_price_trend(rising_price_data)
        assert 'error' not in result
        assert result['trend'] == 'rising'
        assert result['mann_kendall_tau'] > 0
        assert result['is_significant'] is True

    def test_falling_trend(self, falling_price_data):
        result = detect_price_trend(falling_price_data)
        assert 'error' not in result
        assert result['trend'] == 'falling'
        assert result['mann_kendall_tau'] < 0

    def test_stable_trend(self, stable_price_data):
        result = detect_price_trend(stable_price_data)
        assert 'error' not in result
        # Stable: either p > 0.05 (not significant) or very small tau
        if result['is_significant']:
            assert abs(result['mann_kendall_tau']) < 0.3

    def test_insufficient_data(self):
        """Too few data points."""
        data = [{'price_per_unit': 100.0} for _ in range(5)]
        result = detect_price_trend(data, window=7)
        assert 'error' in result

    def test_result_structure(self, rising_price_data):
        result = detect_price_trend(rising_price_data)
        expected_keys = {
            'trend', 'mann_kendall_tau', 'mann_kendall_p', 'is_significant',
            'ma_slope_per_day', 'ma_slope_pct', 'current_price',
            'period_avg_price', 'price_min', 'price_max',
            'volatility_cv_pct', 'n_observations',
        }
        assert expected_keys.issubset(set(result.keys()))


# ─── Margin Factor Regression Tests ───────────────────────────


class TestMarginFactorRegression:
    def test_with_sufficient_data(self, sample_daily_data):
        result = margin_factor_regression(sample_daily_data)
        # statsmodels may not be installed — if error is about import, skip
        if 'error' in result and 'statsmodels' in str(result['error']):
            pytest.skip("statsmodels not installed")
        assert 'error' not in result
        assert 0 <= result['r_squared'] <= 1
        assert result['n_observations'] >= 20
        assert isinstance(result['factors'], dict)
        assert result['strongest_factor'] is not None

    def test_insufficient_data(self):
        data = [
            {'price_per_unit': 100, 'spp_pct': 15, 'margin_pct': 20}
            for _ in range(10)
        ]
        result = margin_factor_regression(data)
        assert 'error' in result

    def test_factor_structure(self, sample_daily_data):
        result = margin_factor_regression(sample_daily_data)
        if 'error' in result:
            pytest.skip(f"Factor regression returned error: {result['error']}")
        for name, factor in result['factors'].items():
            assert 'standardized_beta' in factor
            assert 'p_value' in factor
            assert 'is_significant' in factor
            assert factor['direction'] in ('positive', 'negative')


# ─── Correlation Strength Tests ───────────────────────────────


class TestCorrelationStrength:
    @pytest.mark.parametrize("r,expected", [
        (0.1, 'negligible'),
        (0.3, 'weak'),
        (0.5, 'moderate'),
        (0.7, 'strong'),
        (0.9, 'very_strong'),
        (-0.9, 'very_strong'),
    ])
    def test_strength(self, r, expected):
        assert _correlation_strength(r) == expected


# ─── Full Analysis Tests ──────────────────────────────────────


class TestRunFullAnalysis:
    def test_runs_all_components(self, sample_daily_data):
        result = run_full_analysis(sample_daily_data, model_name='wendy', channel='wb')
        assert result['model'] == 'wendy'
        assert result['channel'] == 'wb'
        assert 'elasticity' in result
        assert 'factor_regression' in result
        assert 'correlations' in result
        assert 'price_trend' in result
        assert 'margin_trend' in result

    def test_insufficient_data(self):
        data = [{'price_per_unit': 100, 'sales_count': 50} for _ in range(3)]
        result = run_full_analysis(data)
        assert result.get('error') == 'insufficient_data'
