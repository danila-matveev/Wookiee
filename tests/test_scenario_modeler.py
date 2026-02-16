"""
Tests for scenario_modeler.py — what-if and counterfactual analysis.
"""
import pytest

from agents.oleg.services.price_analysis.scenario_modeler import (
    simulate_price_change,
    counterfactual_analysis,
    compare_price_change_periods,
)


class TestSimulatePriceChange:
    def test_positive_change(self, sample_daily_data):
        """Price increase → predicted price > baseline."""
        result = simulate_price_change(sample_daily_data, price_change_pct=10.0, model='wendy', channel='wb')
        assert 'error' not in result
        assert result['predicted']['price_per_unit'] > result['baseline']['price_per_unit']
        assert result['price_change_pct'] == 10.0

    def test_negative_change(self, sample_daily_data):
        """Price decrease → predicted price < baseline."""
        result = simulate_price_change(sample_daily_data, price_change_pct=-10.0, model='wendy', channel='wb')
        assert 'error' not in result
        assert result['predicted']['price_per_unit'] < result['baseline']['price_per_unit']

    def test_zero_change(self, sample_daily_data):
        """0% change → predicted ≈ baseline."""
        result = simulate_price_change(sample_daily_data, price_change_pct=0.0, model='wendy', channel='wb')
        assert 'error' not in result
        assert abs(result['predicted']['price_per_unit'] - result['baseline']['price_per_unit']) < 0.1
        assert result['predicted']['volume_change_pct'] == 0.0

    def test_margin_delta_consistency(self, sample_daily_data):
        """margin_delta = forecast_total_margin - baseline_total_margin."""
        result = simulate_price_change(sample_daily_data, price_change_pct=5.0, model='wendy', channel='wb')
        if 'error' not in result:
            f = result['forecast']
            expected_delta = f['forecast_total_margin'] - f['baseline_total_margin']
            assert abs(f['margin_delta'] - expected_delta) < 1.0

    def test_insufficient_data(self):
        """< 14 days → error."""
        data = [
            {'date': f'2026-01-{i+1:02d}', 'price_per_unit': 2500.0,
             'sales_count': 50, 'margin': 25000.0, 'margin_pct': 20.0,
             'revenue_before_spp': 125000.0}
            for i in range(10)
        ]
        result = simulate_price_change(data, price_change_pct=10.0)
        assert 'error' in result

    def test_result_structure(self, sample_daily_data):
        """All expected keys present."""
        result = simulate_price_change(sample_daily_data, price_change_pct=5.0)
        assert 'error' not in result
        assert 'baseline' in result
        assert 'predicted' in result
        assert 'forecast' in result
        assert 'elasticity' in result
        assert 'price_per_unit' in result['baseline']
        assert 'price_per_unit' in result['predicted']


class TestCounterfactualAnalysis:
    def test_structure(self, sample_daily_data):
        """Returns actual, hypothetical, delta."""
        result = counterfactual_analysis(
            sample_daily_data,
            price_change_pct=10.0,
            period_start='2026-01-10',
            period_end='2026-01-25',
            model='wendy',
            channel='wb',
        )
        assert 'error' not in result
        assert 'actual' in result
        assert 'hypothetical' in result
        assert 'delta' in result
        assert 'would_have_been_better' in result['delta']

    def test_no_data_in_period(self, sample_daily_data):
        """Period with no data → error."""
        result = counterfactual_analysis(
            sample_daily_data,
            price_change_pct=10.0,
            period_start='2027-01-01',
            period_end='2027-01-15',
        )
        assert 'error' in result

    def test_actual_totals_positive(self, sample_daily_data):
        """Actual totals should be positive for valid data."""
        result = counterfactual_analysis(
            sample_daily_data,
            price_change_pct=5.0,
            period_start='2026-01-10',
            period_end='2026-01-25',
        )
        if 'error' not in result:
            assert result['actual']['total_margin'] > 0
            assert result['actual']['total_revenue'] > 0
            assert result['actual']['total_sales'] > 0

    def test_delta_math_consistency(self, sample_daily_data):
        """margin_difference = hypothetical - actual."""
        result = counterfactual_analysis(
            sample_daily_data,
            price_change_pct=5.0,
            period_start='2026-01-10',
            period_end='2026-01-25',
        )
        if 'error' not in result:
            expected = result['hypothetical']['total_margin'] - result['actual']['total_margin']
            assert abs(result['delta']['margin_difference'] - expected) < 1.0


class TestComparePriceChangePeriods:
    def test_comparison_structure(self, sample_daily_data):
        result = compare_price_change_periods(
            sample_daily_data,
            change_date='2026-01-15',
            days_before=14,
            days_after=14,
        )
        if 'error' not in result:
            assert 'comparison' in result
            assert 'days_before' in result
            assert 'days_after' in result
            for metric, vals in result['comparison'].items():
                assert 'before' in vals
                assert 'after' in vals
                assert 'change_pct' in vals

    def test_insufficient_data(self):
        """Not enough data around change date."""
        data = [
            {'date': '2026-01-01', 'price_per_unit': 2500.0, 'sales_count': 50,
             'margin': 25000.0, 'margin_pct': 20.0, 'revenue_before_spp': 125000.0}
        ]
        result = compare_price_change_periods(data, '2026-01-01')
        assert 'error' in result
