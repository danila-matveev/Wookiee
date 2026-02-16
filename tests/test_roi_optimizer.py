"""
Tests for roi_optimizer.py — ROI-based price optimization.
"""
import pytest

from agents.oleg.services.price_analysis.roi_optimizer import (
    compute_annual_roi,
    find_optimal_price_for_roi,
    compute_model_roi_dashboard,
    generate_roi_optimization_plan,
    ROI_LEADER_THRESHOLD,
    ROI_HEALTHY_THRESHOLD,
    ROI_UNDERPERFORMER_THRESHOLD,
    MIN_MARGIN_PCT,
)


class TestComputeAnnualROI:
    def test_basic_calculation(self):
        # 30% margin, 30 days turnover -> 30 * (365/30) = 365%
        roi = compute_annual_roi(30.0, 30.0)
        assert abs(roi - 365.0) < 0.1

    def test_high_turnover(self):
        # 20% margin, 5 days turnover -> 20 * (365/5) = 1460%
        roi = compute_annual_roi(20.0, 5.0)
        assert abs(roi - 1460.0) < 0.1

    def test_zero_turnover(self):
        roi = compute_annual_roi(20.0, 0.0)
        assert roi == 0.0

    def test_negative_turnover(self):
        roi = compute_annual_roi(20.0, -5.0)
        assert roi == 0.0

    def test_zero_margin(self):
        roi = compute_annual_roi(0.0, 30.0)
        assert roi == 0.0


class TestFindOptimalPriceForROI:
    @pytest.fixture
    def current_data(self):
        return {
            'price_per_unit': 2500.0,
            'sales_per_day': 50.0,
            'margin_per_day': 27500.0,  # 2500 * 0.22 * 50
            'margin_pct': 22.0,
        }

    def test_returns_structure(self, current_data):
        result = find_optimal_price_for_roi(
            current_data=current_data,
            elasticity=-0.5,
            turnover_days=10.0,
            avg_stock=500.0,
        )
        assert isinstance(result, dict)
        assert 'optimal_price_change_pct' in result
        assert 'current_annual_roi' in result
        assert 'optimal_annual_roi' in result
        assert 'all_scenarios' in result

    def test_inelastic_favors_increase(self, current_data):
        result = find_optimal_price_for_roi(
            current_data=current_data,
            elasticity=-0.3,  # very inelastic
            turnover_days=10.0,
            avg_stock=500.0,
        )
        # Inelastic demand -> raising price should be optimal
        assert result['optimal_price_change_pct'] >= 0

    def test_zero_stock(self, current_data):
        result = find_optimal_price_for_roi(
            current_data=current_data,
            elasticity=-0.5,
            turnover_days=10.0,
            avg_stock=0.0,
        )
        assert isinstance(result, dict)


class TestComputeModelROIDashboard:
    @pytest.fixture
    def models_data(self):
        return [
            {'model': 'wendy', 'margin_pct': 25.0, 'sales_count': 3000, 'margin': 1875000},
            {'model': 'ruby', 'margin_pct': 20.0, 'sales_count': 2000, 'margin': 800000},
            {'model': 'joy', 'margin_pct': 10.0, 'sales_count': 500, 'margin': 50000},
        ]

    @pytest.fixture
    def turnover(self):
        return {
            'wendy': {'turnover_days': 5.0, 'avg_stock': 250, 'daily_sales': 50},
            'ruby': {'turnover_days': 15.0, 'avg_stock': 600, 'daily_sales': 40},
            'joy': {'turnover_days': 60.0, 'avg_stock': 1000, 'daily_sales': 16.7},
        }

    def test_returns_list(self, models_data, turnover):
        dashboard = compute_model_roi_dashboard(models_data, turnover)
        assert isinstance(dashboard, list)
        assert len(dashboard) == 3

    def test_categories(self, models_data, turnover):
        dashboard = compute_model_roi_dashboard(models_data, turnover)
        categories = {d['model']: d['category'] for d in dashboard}
        # wendy: 25 * (365/5) = 1825 -> roi_leader
        assert categories['wendy'] == 'roi_leader'
        # joy: 10 * (365/60) = 60.8 -> underperformer
        assert categories['joy'] == 'underperformer'

    def test_sorted_by_roi(self, models_data, turnover):
        dashboard = compute_model_roi_dashboard(models_data, turnover)
        rois = [d['annual_roi'] for d in dashboard]
        assert rois == sorted(rois, reverse=True)

    def test_no_turnover(self, models_data):
        dashboard = compute_model_roi_dashboard(models_data, {})
        assert isinstance(dashboard, list)
        # Models without turnover data should still appear
        assert len(dashboard) == 3


class TestGenerateROIOptimizationPlan:
    def test_returns_structure(self):
        models_data = [
            {'model': 'wendy', 'margin_pct': 25.0, 'price_per_unit': 2500, 'sales_count': 3000, 'margin': 1875000},
        ]
        elasticities = {'wendy': {'elasticity': -0.5, 'is_significant': True}}
        turnover = {'wendy': {'turnover_days': 5.0, 'avg_stock': 250, 'daily_sales': 50}}
        stock_data = {'wendy': {'avg_stock': 250}}

        result = generate_roi_optimization_plan(models_data, elasticities, turnover, stock_data)
        assert isinstance(result, dict)
        assert 'models' in result
