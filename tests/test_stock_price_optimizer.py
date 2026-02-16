"""
Tests for stock_price_optimizer.py — stock-aware price constraints.
"""
import pytest

from agents.oleg.services.price_analysis.stock_price_optimizer import (
    assess_stock_health,
    generate_stock_aware_recommendation,
    generate_stock_price_matrix,
    CRITICAL_LOW_WEEKS,
    LOW_STOCK_WEEKS,
    HEALTHY_MAX_WEEKS,
    OVERSTOCKED_WEEKS,
)


class TestAssessStockHealth:
    def test_critical_low(self):
        # 3 days stock, 10 sales/day -> 3/(10*7) = 0.043 weeks
        result = assess_stock_health(turnover_days=0.3, avg_stock=3, daily_sales=10)
        assert result['status'] == 'critical_low'
        assert result['price_constraint'] == 'no_decrease'

    def test_low_stock(self):
        # ~10 days stock, 1 week = 7 days -> 10/(7*7) = 0.2? No.
        # weeks_supply = avg_stock / (daily_sales * 7)
        # Let's say avg_stock=100, daily_sales=10 -> 100/70 = 1.43 weeks -> low
        result = assess_stock_health(turnover_days=10, avg_stock=100, daily_sales=10)
        assert result['status'] == 'low'
        assert result['price_constraint'] == 'no_decrease'

    def test_healthy(self):
        # avg_stock=350, daily_sales=10 -> 350/70 = 5 weeks -> healthy
        result = assess_stock_health(turnover_days=35, avg_stock=350, daily_sales=10)
        assert result['status'] == 'healthy'
        assert result['price_constraint'] == 'no_constraint'

    def test_overstocked(self):
        # avg_stock=700, daily_sales=10 -> 700/70 = 10 weeks -> overstocked
        result = assess_stock_health(turnover_days=70, avg_stock=700, daily_sales=10)
        assert result['status'] == 'overstocked'
        assert result['price_constraint'] == 'prefer_decrease'

    def test_severely_overstocked(self):
        # avg_stock=1400, daily_sales=10 -> 1400/70 = 20 weeks -> severely_overstocked
        result = assess_stock_health(turnover_days=140, avg_stock=1400, daily_sales=10)
        assert result['status'] == 'severely_overstocked'
        assert result['price_constraint'] == 'force_decrease'

    def test_zero_sales(self):
        result = assess_stock_health(turnover_days=0, avg_stock=100, daily_sales=0)
        assert result['status'] == 'severely_overstocked'

    def test_zero_stock_zero_sales(self):
        result = assess_stock_health(turnover_days=0, avg_stock=0, daily_sales=0)
        assert result['weeks_supply'] == 0.0

    def test_returns_required_keys(self):
        result = assess_stock_health(turnover_days=10, avg_stock=100, daily_sales=10)
        assert 'weeks_supply' in result
        assert 'status' in result
        assert 'price_constraint' in result
        assert 'reasoning' in result
        assert 'turnover_days' in result
        assert 'avg_stock' in result
        assert 'daily_sales' in result


class TestGenerateStockAwareRecommendation:
    def test_override_increase_to_decrease(self):
        """When recommendation says 'increase_price' but stock is severely overstocked -> override."""
        price_rec = {
            'action': 'increase_price',
            'change_pct': 5.0,
            'reasoning': 'Inelastic demand',
        }
        stock_health = {
            'status': 'severely_overstocked',
            'price_constraint': 'force_decrease',
            'weeks_supply': 20.0,
        }
        result = generate_stock_aware_recommendation(price_rec, stock_health, 140.0)
        assert result['action'] == 'decrease_price'
        assert result['stock_override'] is True

    def test_no_override_healthy(self):
        """When stock is healthy, recommendation passes through."""
        price_rec = {
            'action': 'increase_price',
            'change_pct': 5.0,
            'reasoning': 'Inelastic demand',
        }
        stock_health = {
            'status': 'healthy',
            'price_constraint': 'no_constraint',
            'weeks_supply': 5.0,
        }
        result = generate_stock_aware_recommendation(price_rec, stock_health, 35.0)
        assert result['action'] == 'increase_price'
        assert result.get('stock_override') is not True

    def test_block_decrease_critical_low(self):
        """When stock is critical_low, block price decrease."""
        price_rec = {
            'action': 'decrease_price',
            'change_pct': -5.0,
            'reasoning': 'Elastic demand',
        }
        stock_health = {
            'status': 'critical_low',
            'price_constraint': 'no_decrease',
            'weeks_supply': 0.5,
        }
        result = generate_stock_aware_recommendation(price_rec, stock_health, 3.0)
        assert result['action'] in ('hold', 'increase_price')
        assert result['stock_override'] is True


class TestGenerateStockPriceMatrix:
    def test_returns_structure(self):
        models = [
            {'model': 'wendy', 'margin_pct': 25.0, 'sales_count': 3000, 'price_per_unit': 2500},
            {'model': 'ruby', 'margin_pct': 20.0, 'sales_count': 2000, 'price_per_unit': 2000},
        ]
        stock_data = {'wendy': 250, 'ruby': 1400}
        turnover = {
            'wendy': {'turnover_days': 5.0, 'avg_stock': 250, 'daily_sales': 50},
            'ruby': {'turnover_days': 70.0, 'avg_stock': 1400, 'daily_sales': 20},
        }
        result = generate_stock_price_matrix(models, stock_data, turnover)
        assert isinstance(result, dict)
        assert 'matrix' in result
        assert 'urgent_actions' in result
        assert isinstance(result['matrix'], list)

    def test_urgent_actions_detected(self):
        models = [
            {'model': 'joy', 'margin_pct': 10.0, 'sales_count': 100, 'price_per_unit': 1500},
        ]
        stock_data = {'joy': 2000}
        turnover = {
            'joy': {'turnover_days': 200.0, 'avg_stock': 2000, 'daily_sales': 10},
        }
        result = generate_stock_price_matrix(models, stock_data, turnover)
        # joy is severely overstocked -> should have urgent action
        assert len(result['urgent_actions']) >= 1
