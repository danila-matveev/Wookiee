"""
Researcher Agent tools — API access + statistical analysis.

New tools for deep analysis: WB/OZON API, correlations, elasticity.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

RESEARCHER_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_wb_analytics",
            "description": (
                "Аналитика WB: заказы поставщика за период. "
                "Позволяет проверить объёмы заказов по регионам, артикулам, размерам."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "Начало периода ISO datetime (2026-02-01T00:00:00)"},
                },
                "required": ["date_from"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wb_feedbacks",
            "description": (
                "Отзывы покупателей WB. Показывает текст отзывов, оценки. "
                "Используй для анализа причин возвратов или низкого выкупа."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_moysklad_inventory",
            "description": (
                "Остатки на складах МойСклад. Показывает текущий сток по товарам. "
                "Используй для анализа out-of-stock и затоваривания."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_correlation",
            "description": (
                "Рассчитать корреляцию (Pearson) между двумя метриками за период. "
                "Например: корреляция рекламного расхода и заказов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "metric_a": {"type": "string", "description": "Первая метрика (adv_total, margin, revenue_before_spp, sales_count)"},
                    "metric_b": {"type": "string", "description": "Вторая метрика"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["channel", "metric_a", "metric_b", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_price_elasticity",
            "description": (
                "Анализ ценовой эластичности для модели: как изменение цены влияет на спрос. "
                "Эластичность < -1 = эластичный спрос (нельзя повышать). "
                "Эластичность > -1 = неэластичный (можно повышать)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Модель (wendy, ruby и т.д.)"},
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "lookback_days": {"type": "integer", "description": "Период в днях (по умолчанию 90)", "default": 90},
                },
                "required": ["model", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_periods_deep",
            "description": (
                "Структурированное сравнение двух периодов: финансы, реклама, модели. "
                "Используй для ответа на 'что изменилось между неделями'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "period1_start": {"type": "string", "description": "Начало периода 1 YYYY-MM-DD"},
                    "period1_end": {"type": "string", "description": "Конец периода 1 YYYY-MM-DD"},
                    "period2_start": {"type": "string", "description": "Начало периода 2 YYYY-MM-DD"},
                    "period2_end": {"type": "string", "description": "Конец периода 2 YYYY-MM-DD"},
                },
                "required": ["channel", "period1_start", "period1_end", "period2_start", "period2_end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_traffic_funnel",
            "description": (
                "Воронка трафика: показы → клики → корзина → заказ → выкуп. "
                "С конверсиями на каждом шаге. Используй для анализа эффективности трафика."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_brand_finance",
            "description": (
                "Общая финансовая сводка бренда (WB + OZON) с автосравнением периодов. "
                "Researcher может использовать для получения базовых цифр."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_margin_levers",
            "description": (
                "Декомпозиция маржи по 5 рычагам. Researcher использует для понимания "
                "какие рычаги двигают маржу."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_trend",
            "description": (
                "Дневная динамика метрик канала для поиска аномальных дней и трендов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def _handle_search_wb_analytics(date_from: str) -> dict:
    """Get WB supplier orders."""
    try:
        from shared.clients.wb_client import WBClient
        from agents.oleg_v2 import config
        client = WBClient(
            api_key=config._env_first(["WB_API_KEY_STATS", "WB_API_KEY"], ""),
            cabinet_name="Wookiee",
        )
        orders = client.get_supplier_orders(date_from)
        if orders is None:
            return {"error": "WB API returned no data"}
        return {
            "total_orders": len(orders),
            "sample": orders[:20],
        }
    except Exception as e:
        return {"error": f"WB API error: {e}"}


async def _handle_get_wb_feedbacks() -> dict:
    """Get WB feedbacks."""
    try:
        from shared.clients.wb_client import WBClient
        from agents.oleg_v2 import config
        client = WBClient(
            api_key=config._env_first(["WB_API_KEY_FEEDBACKS", "WB_API_KEY"], ""),
            cabinet_name="Wookiee",
        )
        feedbacks = client.get_all_feedbacks()
        if feedbacks is None:
            return {"error": "WB feedbacks API returned no data"}
        return {
            "total": len(feedbacks),
            "sample": feedbacks[:10],
        }
    except Exception as e:
        return {"error": f"WB feedbacks API error: {e}"}


async def _handle_get_moysklad_inventory() -> dict:
    """Get МойСклад inventory."""
    try:
        from shared.clients.moysklad_client import MoySkladClient
        from agents.oleg_v2 import config
        token = config._env_first(["MOYSKLAD_TOKEN"], "")
        if not token:
            return {"error": "MOYSKLAD_TOKEN not configured"}
        client = MoySkladClient(token=token)
        assortment = client.fetch_assortment()
        return {
            "total_items": len(assortment),
            "sample": assortment[:20],
        }
    except Exception as e:
        return {"error": f"МойСклад API error: {e}"}


async def _handle_calculate_correlation(
    channel: str, metric_a: str, metric_b: str,
    start_date: str, end_date: str,
) -> dict:
    """Calculate Pearson correlation between two metrics."""
    try:
        from shared.data_layer import (
            get_wb_daily_series_range, get_ozon_daily_series_range,
        )
        end_exclusive = (
            datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        ).strftime('%Y-%m-%d')

        if channel == "wb":
            series = await asyncio.to_thread(
                get_wb_daily_series_range, start_date, end_exclusive
            )
        else:
            series = await asyncio.to_thread(
                get_ozon_daily_series_range, start_date, end_exclusive
            )

        if len(series) < 7:
            return {"error": "Insufficient data points for correlation (need >= 7 days)"}

        values_a = [float(d.get(metric_a, 0)) for d in series]
        values_b = [float(d.get(metric_b, 0)) for d in series]

        # Pearson correlation
        from scipy import stats
        corr, p_value = stats.pearsonr(values_a, values_b)

        interpretation = "слабая"
        if abs(corr) > 0.7:
            interpretation = "сильная"
        elif abs(corr) > 0.4:
            interpretation = "умеренная"

        return {
            "metric_a": metric_a,
            "metric_b": metric_b,
            "correlation": round(corr, 3),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "interpretation": interpretation,
            "data_points": len(series),
            "period": f"{start_date} — {end_date}",
        }
    except ImportError:
        return {"error": "scipy not installed"}
    except Exception as e:
        return {"error": f"Correlation calculation failed: {e}"}


async def _handle_analyze_price_elasticity(
    model: str, channel: str, lookback_days: int = 90,
) -> dict:
    """Delegate to v1 price elasticity tool."""
    from agents.oleg.services.price_tools import _handle_price_elasticity
    return await _handle_price_elasticity(model, channel, lookback_days)


async def _handle_compare_periods_deep(
    channel: str,
    period1_start: str, period1_end: str,
    period2_start: str, period2_end: str,
) -> dict:
    """Deep comparison of two periods."""
    from agents.oleg.services.agent_tools import (
        _handle_channel_finance,
        _handle_margin_levers,
    )
    # Get finance for both periods
    p1_finance = await _handle_channel_finance(channel, period1_start, period1_end)
    p2_finance = await _handle_channel_finance(channel, period2_start, period2_end)

    p1_levers = await _handle_margin_levers(channel, period1_start, period1_end)
    p2_levers = await _handle_margin_levers(channel, period2_start, period2_end)

    return {
        "period_1": {
            "dates": f"{period1_start} — {period1_end}",
            "finance": p1_finance,
            "levers": p1_levers,
        },
        "period_2": {
            "dates": f"{period2_start} — {period2_end}",
            "finance": p2_finance,
            "levers": p2_levers,
        },
    }


async def _handle_get_traffic_funnel(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Get traffic funnel data."""
    from agents.oleg.services.agent_tools import _handle_advertising_stats
    return await _handle_advertising_stats(channel, start_date, end_date)


async def _handle_get_brand_finance(start_date: str, end_date: str) -> dict:
    """Delegate to v1 brand finance tool."""
    from agents.oleg.services.agent_tools import _handle_brand_finance
    return await _handle_brand_finance(start_date, end_date)


async def _handle_get_margin_levers(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Delegate to v1 margin levers tool."""
    from agents.oleg.services.agent_tools import _handle_margin_levers
    return await _handle_margin_levers(channel, start_date, end_date)


async def _handle_get_daily_trend(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Delegate to v1 daily trend tool."""
    from agents.oleg.services.agent_tools import _handle_daily_trend
    return await _handle_daily_trend(channel, start_date, end_date)


# =============================================================================
# TOOL REGISTRY
# =============================================================================

RESEARCHER_TOOL_HANDLERS = {
    "search_wb_analytics": _handle_search_wb_analytics,
    "get_wb_feedbacks": _handle_get_wb_feedbacks,
    "get_moysklad_inventory": _handle_get_moysklad_inventory,
    "calculate_correlation": _handle_calculate_correlation,
    "analyze_price_elasticity": _handle_analyze_price_elasticity,
    "compare_periods_deep": _handle_compare_periods_deep,
    "get_traffic_funnel": _handle_get_traffic_funnel,
    "get_brand_finance": _handle_get_brand_finance,
    "get_margin_levers": _handle_get_margin_levers,
    "get_daily_trend": _handle_get_daily_trend,
}


async def execute_researcher_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a researcher tool."""
    handler = RESEARCHER_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
    try:
        result = await handler(**tool_args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": f"Tool {tool_name} failed: {e}"}, ensure_ascii=False)
