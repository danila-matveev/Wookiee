"""
Tests for price_tools.py — tool definitions and handler registration.
"""
import asyncio
import inspect
from unittest.mock import patch

import pytest

from agents.oleg.services.price_tools import (
    PRICE_TOOL_DEFINITIONS,
    PRICE_TOOL_HANDLERS,
    _handle_price_elasticity,
    _handle_price_margin_correlation,
    _handle_price_recommendation,
    _handle_simulate_price_change,
    _handle_price_counterfactual,
    _handle_analyze_promotion,
    _handle_price_trend,
    _handle_recommendation_history,
    _handle_price_changes_detected,
)


EXPECTED_TOOL_NAMES = {
    "get_price_elasticity",
    "get_price_margin_correlation",
    "get_price_recommendation",
    "simulate_price_change",
    "get_price_counterfactual",
    "analyze_promotion",
    "get_price_trend",
    "get_recommendation_history",
    "get_price_changes_detected",
}


class TestToolRegistration:
    def test_all_definitions_registered(self):
        """9 tool definitions exist."""
        assert len(PRICE_TOOL_DEFINITIONS) == 9

    def test_all_handlers_registered(self):
        """9 handlers exist."""
        assert len(PRICE_TOOL_HANDLERS) == 9

    def test_names_match(self):
        """Definition names match handler names."""
        definition_names = {
            d['function']['name'] for d in PRICE_TOOL_DEFINITIONS
        }
        handler_names = set(PRICE_TOOL_HANDLERS.keys())
        assert definition_names == handler_names == EXPECTED_TOOL_NAMES

    def test_all_handlers_are_async(self):
        """Every handler is an async function."""
        for name, handler in PRICE_TOOL_HANDLERS.items():
            assert asyncio.iscoroutinefunction(handler), \
                f"Handler {name} is not async"

    def test_handlers_accept_kwargs(self):
        """Every handler uses keyword arguments (not a single dict arg)."""
        for name, handler in PRICE_TOOL_HANDLERS.items():
            sig = inspect.signature(handler)
            params = list(sig.parameters.values())
            # Should NOT have a single 'args: dict' parameter
            if len(params) == 1 and params[0].name == 'args':
                pytest.fail(f"Handler {name} takes single 'args' param — should use **kwargs")

    def test_definitions_have_required_structure(self):
        """Each definition has type, function.name, function.parameters."""
        for d in PRICE_TOOL_DEFINITIONS:
            assert d['type'] == 'function'
            func = d['function']
            assert 'name' in func
            assert 'description' in func
            assert 'parameters' in func
            params = func['parameters']
            assert params['type'] == 'object'
            assert 'properties' in params


class TestHandlersNoData:
    """Test handlers return error dicts when no data is available."""

    @pytest.mark.asyncio
    async def test_elasticity_no_data(self):
        with patch('agents.oleg.services.price_tools._get_data', return_value=[]):
            result = await _handle_price_elasticity(model='test', channel='wb')
            assert isinstance(result, dict)
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_correlation_no_data(self):
        with patch('agents.oleg.services.price_tools._get_data', return_value=[]):
            result = await _handle_price_margin_correlation(
                channel='wb', start_date='2026-01-01', end_date='2026-01-30'
            )
            assert isinstance(result, dict)
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_recommendation_no_data(self):
        with patch('agents.oleg.services.price_tools._get_data', return_value=[]):
            result = await _handle_price_recommendation(model='test', channel='wb')
            assert isinstance(result, dict)
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_simulate_no_data(self):
        with patch('agents.oleg.services.price_tools._get_data', return_value=[]):
            result = await _handle_simulate_price_change(
                model='test', channel='wb', price_change_pct=10.0
            )
            assert isinstance(result, dict)
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_trend_no_data(self):
        with patch('agents.oleg.services.price_tools._get_data', return_value=[]):
            result = await _handle_price_trend(model='test', channel='wb')
            assert isinstance(result, dict)
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_price_changes_returns_dict(self):
        with patch('agents.oleg.services.price_tools.get_wb_price_changes', return_value=[]):
            result = await _handle_price_changes_detected(
                channel='wb', start_date='2026-01-01', end_date='2026-01-30'
            )
            assert isinstance(result, dict)
            assert result['changes_count'] == 0


class TestHandlersWithData:
    """Test handlers return correct structure when data is available."""

    @pytest.mark.asyncio
    async def test_elasticity_with_data(self, sample_daily_data):
        with patch('agents.oleg.services.price_tools._get_data', return_value=sample_daily_data):
            result = await _handle_price_elasticity(model='wendy', channel='wb')
            assert isinstance(result, dict)
            assert result['model'] == 'wendy'
            assert result['channel'] == 'wb'
            # Should have elasticity OR error
            assert 'elasticity' in result or 'error' in result

    @pytest.mark.asyncio
    async def test_trend_with_data(self, sample_daily_data):
        with patch('agents.oleg.services.price_tools._get_data', return_value=sample_daily_data):
            result = await _handle_price_trend(model='wendy', channel='wb')
            assert isinstance(result, dict)
            assert result['model'] == 'wendy'
            assert 'price_trend' in result

    @pytest.mark.asyncio
    async def test_recommendation_history_no_store(self):
        """Without learning store → error."""
        with patch('agents.oleg.services.price_tools._learning_store', None):
            result = await _handle_recommendation_history()
            assert isinstance(result, dict)
            assert 'error' in result
