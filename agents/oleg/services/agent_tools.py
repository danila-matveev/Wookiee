"""
Agent Tools — инструменты агента Олег для доступа к данным.

Обёртки над scripts/data_layer.py в формате OpenAI function calling.
Все SQL-запросы остаются в data_layer.py — здесь только парсинг и агрегация.
"""
import ast
import asyncio
import json
import logging
import operator
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Data layer imports (all SQL queries live in data_layer.py)
from shared.data_layer import (
    get_wb_finance, get_wb_by_model, get_wb_traffic, get_wb_traffic_by_model,
    get_wb_orders_by_model, get_wb_daily_series, get_wb_daily_series_range,
    get_wb_weekly_breakdown,
    get_ozon_finance, get_ozon_by_model, get_ozon_orders_by_model,
    get_ozon_traffic, get_ozon_daily_series, get_ozon_daily_series_range,
    get_ozon_weekly_breakdown,
    get_artikuly_statuses, validate_wb_data_quality,
    to_float, calc_change,
)


from shared.model_mapping import map_to_osnova as _map_to_osnova


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_brand_finance",
            "description": (
                "Общая финансовая сводка бренда (WB + OZON): маржа (₽, %), выручка до СПП, "
                "заказы (шт, ₽), продажи шт, реклама (внутр + внешн), ДРР% (от продаж и от заказов), СПП%. "
                "Автоматически сравнивает с предыдущим аналогичным периодом. "
                "Используй ПЕРВЫМ для общей картины."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_channel_finance",
            "description": (
                "Детальные финансы одного канала (wb или ozon): маржа, выручка, заказы, продажи, "
                "реклама (внутренняя/внешняя отдельно), логистика, хранение, себестоимость, "
                "комиссия, СПП%, ДРР% (от продаж и от заказов), НДС, штрафы, удержания. Используй для углублённого анализа канала."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"], "description": "Канал"},
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_model_breakdown",
            "description": (
                "Полная декомпозиция по моделям (Vuki, Moon, Ruby, Wendy и др.) для канала. "
                "Возвращает маржу, продажи, рекламу и ДРР. ОБЯЗАТЕЛЬНО выводи все полученные модели "
                "в таблицу отчета (4.1.2/4.2.2), не пропуская убыточные модели, такие как Ruby."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
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
                "Дневная динамика метрик канала: маржа, выручка, заказы, продажи, реклама "
                "по каждому дню. Используй для поиска аномальных дней и трендов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_advertising_stats",
            "description": (
                "Рекламная статистика канала: показы, клики, CTR, CPC, расход, "
                "заказы через рекламу, корзины + производные: CPM, CPL, CPO, "
                "конверсии по шагам воронки (рекламной и органической). "
                "Для WB также органическая воронка: "
                "переходы на карточку → корзина → заказы → выкупы с конверсиями."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_model_advertising",
            "description": (
                "Рекламная статистика WB по моделям: показы, клики, расход, "
                "корзины (atbs), заказы, CTR, CPC + производные: CPM, CPL, CPO, "
                "конверсии (клик→корзина, корзина→заказ, клик→заказ). "
                "Доступно только для WB (для OZON нет разбивки по моделям)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders_by_model",
            "description": (
                "Заказы по моделям для расчёта ДРР заказов (CPO). "
                "Модель, количество заказов, сумма заказов ₽ + сравнение с предыдущим периодом."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_margin_levers",
            "description": (
                "Декомпозиция маржи по 5 рычагам: цена до СПП, СПП%, ДРР (внутр/внешн), "
                "логистика ₽/ед, себестоимость ₽/ед. Показывает рублёвый вклад каждого фактора "
                "в изменение маржи. Используй для ответа на вопрос 'почему упала/выросла маржа'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_breakdown",
            "description": (
                "Понедельная разбивка финансов канала внутри периода. "
                "Для каждой недели: маржа, выручка, заказы, реклама, логистика. "
                "Используй для месячных отчётов и поиска лучшей/худшей недели."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["wb", "ozon"]},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD (начало месяца/периода)"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD (конец, включительно)"},
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_data_quality",
            "description": (
                "Проверка качества данных WB за конкретную дату. "
                "Обнаруживает: retention==deduction (дубликация пайплайна), "
                "корректировку маржи. ОБЯЗАТЕЛЬНО вызывай перед финальным ответом."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Дата для проверки YYYY-MM-DD"},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_statuses",
            "description": (
                "Статусы всех товаров из Supabase: артикул → статус (активный, архив, и т.д.). "
                "Используй для проверки, какие модели активны."
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
            "name": "calculate_metric",
            "description": (
                "Калькулятор для проверки расчётов. Подставляет значения в формулу "
                "и вычисляет результат. Используй для верификации своих расчётов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "formula": {
                        "type": "string",
                        "description": "Формула с именованными переменными, напр. '(revenue - costs) / revenue * 100'",
                    },
                    "values": {
                        "type": "object",
                        "description": "Словарь значений переменных, напр. {\"revenue\": 1000000, \"costs\": 800000}",
                    },
                },
                "required": ["formula", "values"],
            },
        },
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _calc_comparison_dates(start_date: str, end_date: str) -> tuple:
    """
    Calculate (current_start, prev_start, current_end) for data_layer functions.

    data_layer uses: WHERE date >= prev_start AND date < current_end
    CASE WHEN date >= current_start THEN 'current' ELSE 'previous'
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (end - start).days + 1
    current_end = (end + timedelta(days=1)).strftime('%Y-%m-%d')
    prev_start = (start - timedelta(days=period_days)).strftime('%Y-%m-%d')
    return start_date, prev_start, current_end


def _split_periods(rows: list, field_count: int) -> dict:
    """Split data_layer rows into current/previous dicts by first column (period)."""
    result = {"current": None, "previous": None}
    for row in rows:
        period = row[0]
        if period in ("current", "previous"):
            result[period] = row
    return result


def _safe_div(a, b, default=0.0):
    """Safe division, returns default if divisor is 0 or None."""
    if b is None or b == 0:
        return default
    return a / b


def _pct_change(current, previous):
    """Calculate percentage change."""
    if previous is None or previous == 0:
        return 0.0
    return round(((current - previous) / abs(previous)) * 100, 1)


def _enrich_ad_metrics(ads: dict) -> dict:
    """Add derived marketing metrics: CPM, CPL, CPO, funnel conversions."""
    views = ads.get("ad_views", 0)
    clicks = ads.get("ad_clicks", 0)
    to_cart = ads.get("ad_to_cart", 0)
    orders = ads.get("ad_orders", 0)
    spend = ads.get("ad_spend", 0)

    ads["cpm_rub"] = round(_safe_div(spend, views) * 1000, 1)
    ads["cpl_rub"] = round(_safe_div(spend, to_cart), 1)
    ads["cpo_rub"] = round(_safe_div(spend, orders), 1)
    ads["cart_conversion_pct"] = round(_safe_div(to_cart, clicks) * 100, 2)
    ads["order_from_cart_pct"] = round(_safe_div(orders, to_cart) * 100, 2)
    ads["cr_full_pct"] = round(_safe_div(orders, clicks) * 100, 2)
    return ads


# =============================================================================
# WB FINANCE PARSER
# =============================================================================

def _parse_wb_finance_row(row) -> dict:
    """Parse a single WB finance row (from get_wb_finance results)."""
    if not row:
        return {}
    return {
        "orders_count": to_float(row[1]),
        "sales_count": to_float(row[2]),
        "revenue_before_spp": to_float(row[3]),
        "revenue_after_spp": to_float(row[4]),
        "adv_internal": to_float(row[5]),
        "adv_external": to_float(row[6]),
        "cost_of_goods": to_float(row[7]),
        "logistics": to_float(row[8]),
        "storage": to_float(row[9]),
        "commission": to_float(row[10]),
        "spp_amount": to_float(row[11]),
        "nds": to_float(row[12]),
        "penalty": to_float(row[13]),
        "retention": to_float(row[14]),
        "deduction": to_float(row[15]),
        "margin": to_float(row[16]),
        "returns_revenue": to_float(row[17]),
        "revenue_before_spp_gross": to_float(row[18]),
    }


def _parse_ozon_finance_row(row) -> dict:
    """Parse a single OZON finance row (from get_ozon_finance results)."""
    if not row:
        return {}
    return {
        "sales_count": to_float(row[1]),
        "revenue_before_spp": to_float(row[2]),
        "revenue_after_spp": to_float(row[3]),
        "adv_internal": to_float(row[4]),
        "adv_external": to_float(row[5]),
        "margin": to_float(row[6]),
        "cost_of_goods": to_float(row[7]),
        "logistics": to_float(row[8]),
        "storage": to_float(row[9]),
        "commission": to_float(row[10]),
        "spp_amount": to_float(row[11]),
        "nds": to_float(row[12]),
        # OZON abc_date не содержит penalty/retention/deduction,
        # но waterfall (_handle_margin_levers) обращается к ним — без этих ключей
        # waterfall не балансируется (сумма компонентов ≠ margin_change_total).
        "penalty": 0.0,
        "retention": 0.0,
        "deduction": 0.0,
    }


def _parse_orders_row_wb(row) -> dict:
    """Parse WB orders row: (period, orders_count, orders_rub)."""
    if not row:
        return {"orders_count": 0, "orders_rub": 0}
    return {"orders_count": to_float(row[1]), "orders_rub": to_float(row[2])}


def _parse_orders_row_ozon(row) -> dict:
    """Parse OZON orders row: (period, orders_count, orders_rub)."""
    if not row:
        return {"orders_count": 0, "orders_rub": 0}
    return {"orders_count": to_float(row[1]), "orders_rub": to_float(row[2])}


def _enrich_finance(data: dict) -> dict:
    """Add derived metrics to finance dict."""
    rev = data.get("revenue_before_spp", 0)
    margin = data.get("margin", 0)
    adv_int = data.get("adv_internal", 0)
    adv_ext = data.get("adv_external", 0)
    adv_total = adv_int + adv_ext
    sales = data.get("sales_count", 0)
    spp = data.get("spp_amount", 0)

    data["adv_total"] = adv_total
    data["margin_pct"] = round(_safe_div(margin, rev) * 100, 1)
    data["drr_pct"] = round(_safe_div(adv_total, rev) * 100, 1)
    data["drr_orders_pct"] = round(_safe_div(adv_total, data.get("orders_rub", 0)) * 100, 1)
    data["spp_pct"] = round(_safe_div(spp, data.get("revenue_before_spp_gross", rev)) * 100, 1)
    data["logistics_per_unit"] = round(_safe_div(data.get("logistics", 0), sales), 0)
    data["cogs_per_unit"] = round(_safe_div(data.get("cost_of_goods", 0), sales), 0)
    data["storage_per_unit"] = round(_safe_div(data.get("storage", 0), sales), 0)
    data["margin_per_unit"] = round(_safe_div(margin, sales), 0)
    data["turnover_days"] = 0  # Placeholder: stock data not yet available in finance aggregation
    return data


def _build_changes(current: dict, previous: dict) -> dict:
    """Calculate changes between current and previous periods."""
    changes = {}
    for key in current:
        if key in previous and isinstance(current[key], (int, float)):
            prev_val = previous.get(key, 0)
            curr_val = current.get(key, 0)
            if key.endswith("_pct"):
                changes[f"{key}_change_pp"] = round(curr_val - prev_val, 1)
            else:
                changes[f"{key}_change_pct"] = _pct_change(curr_val, prev_val)
                changes[f"{key}_change_abs"] = round(curr_val - prev_val, 0)
    return changes


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def _handle_brand_finance(start_date: str, end_date: str) -> dict:
    """Get brand (WB + OZON) financial summary."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    # Run both channels in parallel
    wb_data, ozon_data = await asyncio.gather(
        asyncio.to_thread(get_wb_finance, current_start, prev_start, current_end),
        asyncio.to_thread(get_ozon_finance, current_start, prev_start, current_end),
    )

    wb_results, wb_orders = wb_data
    ozon_results, ozon_orders = ozon_data

    # Parse WB
    wb_periods = _split_periods(wb_results, 19)
    wb_orders_periods = _split_periods(wb_orders, 3)
    wb_current = _parse_wb_finance_row(wb_periods["current"])
    wb_previous = _parse_wb_finance_row(wb_periods["previous"])
    wb_orders_curr = _parse_orders_row_wb(wb_orders_periods.get("current"))
    wb_orders_prev = _parse_orders_row_wb(wb_orders_periods.get("previous"))

    # Parse OZON
    ozon_periods = _split_periods(ozon_results, 13)
    ozon_orders_periods = _split_periods(ozon_orders, 3)
    ozon_current = _parse_ozon_finance_row(ozon_periods["current"])
    ozon_previous = _parse_ozon_finance_row(ozon_periods["previous"])
    ozon_orders_curr = _parse_orders_row_ozon(ozon_orders_periods.get("current"))
    ozon_orders_prev = _parse_orders_row_ozon(ozon_orders_periods.get("previous"))

    # Combine brand totals
    def _sum_channels(wb: dict, ozon: dict) -> dict:
        combined = {}
        all_keys = set(list(wb.keys()) + list(ozon.keys()))
        for k in all_keys:
            wb_val = wb.get(k, 0)
            ozon_val = ozon.get(k, 0)
            if isinstance(wb_val, (int, float)) and isinstance(ozon_val, (int, float)):
                combined[k] = wb_val + ozon_val
            else:
                combined[k] = wb_val
        return combined

    brand_current = _sum_channels(wb_current, ozon_current)
    brand_previous = _sum_channels(wb_previous, ozon_previous)

    # Add orders (count + rub)
    brand_current["orders_count"] = wb_orders_curr.get("orders_count", 0) + ozon_orders_curr.get("orders_count", 0)
    brand_current["orders_rub"] = wb_orders_curr.get("orders_rub", 0) + ozon_orders_curr.get("orders_rub", 0)
    brand_previous["orders_count"] = wb_orders_prev.get("orders_count", 0) + ozon_orders_prev.get("orders_count", 0)
    brand_previous["orders_rub"] = wb_orders_prev.get("orders_rub", 0) + ozon_orders_prev.get("orders_rub", 0)

    # Enrich with derived metrics
    brand_current = _enrich_finance(brand_current)
    brand_previous = _enrich_finance(brand_previous)
    wb_current = _enrich_finance(wb_current)
    ozon_current = _enrich_finance(ozon_current)

    changes = _build_changes(brand_current, brand_previous)

    return {
        "period": f"{start_date} — {end_date}",
        "comparison_period": f"{prev_start} — {(datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')}",
        "brand": {"current": brand_current, "previous": brand_previous, "changes": changes},
        "wb_summary": {
            "margin": wb_current.get("margin", 0),
            "margin_pct": wb_current.get("margin_pct", 0),
            "revenue": wb_current.get("revenue_before_spp", 0),
            "orders_count": wb_orders_curr.get("orders_count", 0),
            "orders_rub": wb_orders_curr.get("orders_rub", 0),
        },
        "ozon_summary": {
            "margin": ozon_current.get("margin", 0),
            "margin_pct": ozon_current.get("margin_pct", 0),
            "revenue": ozon_current.get("revenue_before_spp", 0),
            "orders_rub": ozon_orders_curr.get("orders_rub", 0),
        },
    }


async def _handle_channel_finance(channel: str, start_date: str, end_date: str) -> dict:
    """Get detailed finance for a single channel."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        results, orders = await asyncio.to_thread(
            get_wb_finance, current_start, prev_start, current_end
        )
        periods = _split_periods(results, 19)
        orders_periods = _split_periods(orders, 3)
        current = _parse_wb_finance_row(periods["current"])
        previous = _parse_wb_finance_row(periods["previous"])
        orders_curr = _parse_orders_row_wb(orders_periods.get("current"))
        orders_prev = _parse_orders_row_wb(orders_periods.get("previous"))
        current["orders_count"] = orders_curr.get("orders_count", 0)
        current["orders_rub"] = orders_curr.get("orders_rub", 0)
        previous["orders_count"] = orders_prev.get("orders_count", 0)
        previous["orders_rub"] = orders_prev.get("orders_rub", 0)
    else:
        results, orders = await asyncio.to_thread(
            get_ozon_finance, current_start, prev_start, current_end
        )
        periods = _split_periods(results, 13)
        orders_periods = _split_periods(orders, 3)
        current = _parse_ozon_finance_row(periods["current"])
        previous = _parse_ozon_finance_row(periods["previous"])
        orders_curr = _parse_orders_row_ozon(orders_periods.get("current"))
        orders_prev = _parse_orders_row_ozon(orders_periods.get("previous"))
        current["orders_count"] = orders_curr.get("orders_count", 0)
        current["orders_rub"] = orders_curr.get("orders_rub", 0)
        previous["orders_count"] = orders_prev.get("orders_count", 0)
        previous["orders_rub"] = orders_prev.get("orders_rub", 0)

    current = _enrich_finance(current)
    previous = _enrich_finance(previous)
    changes = _build_changes(current, previous)

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "current": current,
        "previous": previous,
        "changes": changes,
    }


async def _handle_model_breakdown(channel: str, start_date: str, end_date: str) -> dict:
    """Get model breakdown for a channel."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        results, orders_results = await asyncio.gather(
            asyncio.to_thread(get_wb_by_model, current_start, prev_start, current_end),
            asyncio.to_thread(get_wb_orders_by_model, current_start, prev_start, current_end)
        )
    else:
        results, orders_results = await asyncio.gather(
            asyncio.to_thread(get_ozon_by_model, current_start, prev_start, current_end),
            asyncio.to_thread(get_ozon_orders_by_model, current_start, prev_start, current_end)
        )

    # Index orders data: (period, model) -> {orders_count, orders_rub}
    orders_map = {}
    for row in orders_results:
        key = (row[0], row[1])
        orders_map[key] = {
            "orders_count": to_float(row[2]),
            "orders_rub": to_float(row[3]),
        }

    # Parse: (period, model, sales_count, revenue_before_spp, adv_total, margin)
    current_models = {}
    previous_models = {}
    for row in results:
        period, raw_model = row[0], row[1]
        model = _map_to_osnova(raw_model)
        
        # We also need to get orders_data. The orders_data is keyed by (period, raw_model)
        orders_data = orders_map.get((period, raw_model), {"orders_count": 0, "orders_rub": 0})
        
        target_dict = current_models if period == "current" else previous_models
        if model not in target_dict:
            target_dict[model] = {
                "model": model, "sales_count": 0, "revenue_before_spp": 0,
                "adv_total": 0, "margin": 0, "orders_count": 0, "orders_rub": 0
            }
        
        target_dict[model]["sales_count"] += to_float(row[2])
        target_dict[model]["revenue_before_spp"] += to_float(row[3])
        target_dict[model]["adv_total"] += to_float(row[4])
        target_dict[model]["margin"] += to_float(row[5])
        target_dict[model]["orders_count"] += orders_data["orders_count"]
        target_dict[model]["orders_rub"] += orders_data["orders_rub"]

    for d in (current_models, previous_models):
        for model in list(d.keys()):
            data = d[model]
            rev = data["revenue_before_spp"]
            orders_sum = data["orders_rub"]
            data["margin_pct"] = round(_safe_div(data["margin"], rev) * 100, 1)
            data["drr_pct"] = round(_safe_div(data["adv_total"], rev) * 100, 1)
            data["drr_orders_pct"] = round(_safe_div(data["adv_total"], orders_sum) * 100, 1)

    # Build list with changes
    models_list = []
    all_models = set(current_models.keys()) | set(previous_models.keys())
    
    for model in sorted(all_models): 
        curr = current_models.get(model, {
            "model": model, "sales_count": 0, "revenue_before_spp": 0, 
            "adv_total": 0, "margin": 0, "orders_count": 0, "orders_rub": 0,
            "margin_pct": 0, "drr_pct": 0, "drr_orders_pct": 0
        })
        prev = previous_models.get(model, {})
        
        entry = {**curr}
        
        # Calculate changes regardless of whether prev exists (defaults to 0 if empty)
        entry["margin_change_pct"] = _pct_change(curr["margin"], prev.get("margin", 0))
        entry["margin_change_abs"] = round(curr["margin"] - prev.get("margin", 0), 0)
        entry["revenue_change_pct"] = _pct_change(curr["revenue_before_spp"], prev.get("revenue_before_spp", 0))
        entry["sales_change_pct"] = _pct_change(curr["sales_count"], prev.get("sales_count", 0))
        entry["orders_rub_change"] = round(curr["orders_rub"] - prev.get("orders_rub", 0), 0)
        entry["margin_pct_change_pp"] = round(curr.get("margin_pct", 0) - prev.get("margin_pct", 0), 1)
        
        models_list.append(entry)
    
    # Sort by margin descending after building the full list
    models_list.sort(key=lambda x: x["margin"], reverse=True)

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "models": models_list,
        "total_models": len(models_list),
    }


async def _handle_daily_trend(channel: str, start_date: str, end_date: str) -> dict:
    """Get daily series for a channel."""
    # Use the range version (no comparison period needed)
    end_exclusive = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    if channel == "wb":
        series = await asyncio.to_thread(
            get_wb_daily_series_range, start_date, end_exclusive
        )
    else:
        series = await asyncio.to_thread(
            get_ozon_daily_series_range, start_date, end_exclusive
        )

    # Convert date objects to strings
    for day in series:
        if hasattr(day.get("date"), "strftime"):
            day["date"] = day["date"].strftime("%Y-%m-%d")
        # Add derived metrics
        rev = day.get("revenue_before_spp", 0)
        margin = day.get("margin", 0)
        sales = day.get("sales_count", 0)
        adv = day.get("adv_total", 0)
        day["margin_pct"] = round(_safe_div(margin, rev) * 100, 1)
        day["drr_pct"] = round(_safe_div(adv, rev) * 100, 1)

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "days": series,
        "total_days": len(series),
    }


async def _handle_advertising_stats(channel: str, start_date: str, end_date: str) -> dict:
    """Get advertising statistics for a channel."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        content_results, adv_results = await asyncio.to_thread(
            get_wb_traffic, current_start, prev_start, current_end
        )

        # Parse content (funnel) with conversions
        funnel = {"current": {}, "previous": {}}
        for row in content_results:
            period = row[0]
            card_opens = to_float(row[1])
            add_to_cart = to_float(row[2])
            funnel_orders = to_float(row[3])
            buyouts = to_float(row[4])
            funnel[period] = {
                "card_opens": card_opens,
                "add_to_cart": add_to_cart,
                "funnel_orders": funnel_orders,
                "buyouts": buyouts,
                "card_to_cart_pct": round(_safe_div(add_to_cart, card_opens) * 100, 2),
                "cart_to_order_pct": round(_safe_div(funnel_orders, add_to_cart) * 100, 2),
                "order_to_buyout_pct": round(_safe_div(buyouts, funnel_orders) * 100, 2),
                "cr_full_pct": round(_safe_div(funnel_orders, card_opens) * 100, 2),
                "full_conversion_pct": round(_safe_div(buyouts, card_opens) * 100, 2),
            }

        # Parse ads + enrich with derived metrics (CPM, CPL, CPO, conversions)
        ads = {"current": {}, "previous": {}}
        for row in adv_results:
            period = row[0]
            ads[period] = {
                "ad_views": to_float(row[1]),
                "ad_clicks": to_float(row[2]),
                "ad_to_cart": to_float(row[3]),
                "ad_orders": to_float(row[4]),
                "ad_spend": to_float(row[5]),
                "ctr_pct": round(to_float(row[6]), 2),
                "cpc_rub": round(to_float(row[7]), 1),
            }
            ads[period] = _enrich_ad_metrics(ads[period])

        return {
            "channel": "WB",
            "period": f"{start_date} — {end_date}",
            "funnel": funnel,
            "advertising": ads,
        }

    else:  # ozon
        results = await asyncio.to_thread(
            get_ozon_traffic, current_start, prev_start, current_end
        )
        ads = {"current": {}, "previous": {}}
        for row in results:
            period = row[0]
            ads[period] = {
                "ad_views": to_float(row[1]),
                "ad_clicks": to_float(row[2]),
                "ad_orders": to_float(row[3]),
                "ad_spend": to_float(row[4]),
                "ctr_pct": round(to_float(row[5]), 2),
                "cpc_rub": round(to_float(row[6]), 1),
                "ad_to_cart": 0,  # OZON не предоставляет atbs
            }
            ads[period] = _enrich_ad_metrics(ads[period])

        return {
            "channel": "OZON",
            "period": f"{start_date} — {end_date}",
            "advertising": ads,
        }


async def _handle_model_advertising(start_date: str, end_date: str) -> dict:
    """Get WB advertising stats by model."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    results = await asyncio.to_thread(
        get_wb_traffic_by_model, current_start, prev_start, current_end
    )

    # Parse: (period, model, ad_views, ad_clicks, ad_spend, ad_to_cart, ad_orders, ctr, cpc)
    current_models = {}
    previous_models = {}
    for row in results:
        period, raw_model = row[0], row[1]
        model = _map_to_osnova(raw_model)
        
        target_dict = current_models if period == "current" else previous_models
        if model not in target_dict:
            target_dict[model] = {
                "model": model, "ad_views": 0, "ad_clicks": 0,
                "ad_spend": 0, "ad_to_cart": 0, "ad_orders": 0
            }
        
        target_dict[model]["ad_views"] += to_float(row[2])
        target_dict[model]["ad_clicks"] += to_float(row[3])
        target_dict[model]["ad_spend"] += to_float(row[4])
        target_dict[model]["ad_to_cart"] += to_float(row[5])
        target_dict[model]["ad_orders"] += to_float(row[6])

    for d in (current_models, previous_models):
        for model in list(d.keys()):
            data = d[model]
            data["ctr_pct"] = round(_safe_div(data["ad_clicks"], data["ad_views"]) * 100, 2)
            data["cpc_rub"] = round(_safe_div(data["ad_spend"], data["ad_clicks"]), 1)
            d[model] = _enrich_ad_metrics(data)

    models_list = []
    for model, curr in sorted(current_models.items(), key=lambda x: x[1]["ad_spend"], reverse=True):
        prev = previous_models.get(model, {})
        entry = {**curr}
        if prev:
            entry["spend_change_pct"] = _pct_change(curr["ad_spend"], prev.get("ad_spend", 0))
            entry["ctr_change_pp"] = round(curr.get("ctr_pct", 0) - prev.get("ctr_pct", 0), 2)
            entry["cpm_change_pct"] = _pct_change(curr.get("cpm_rub", 0), prev.get("cpm_rub", 0))
            entry["cpo_change_pct"] = _pct_change(curr.get("cpo_rub", 0), prev.get("cpo_rub", 0))
        models_list.append(entry)

    return {
        "channel": "WB",
        "period": f"{start_date} — {end_date}",
        "models": models_list,
    }


async def _handle_orders_by_model(channel: str, start_date: str, end_date: str) -> dict:
    """Get orders breakdown by model."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        results = await asyncio.to_thread(
            get_wb_orders_by_model, current_start, prev_start, current_end
        )
    else:
        results = await asyncio.to_thread(
            get_ozon_orders_by_model, current_start, prev_start, current_end
        )

    # Parse: (period, model, orders_count, orders_rub)
    current_models = {}
    previous_models = {}
    for row in results:
        period, raw_model = row[0], row[1]
        model = _map_to_osnova(raw_model)
        
        target_dict = current_models if period == "current" else previous_models
        if model not in target_dict:
            target_dict[model] = {
                "model": model, "orders_count": 0, "orders_rub": 0
            }
        
        target_dict[model]["orders_count"] += to_float(row[2])
        target_dict[model]["orders_rub"] += to_float(row[3])

    models_list = []
    for model, curr in sorted(current_models.items(), key=lambda x: x[1]["orders_rub"], reverse=True):
        prev = previous_models.get(model, {})
        entry = {**curr}
        if prev:
            entry["orders_count_change_pct"] = _pct_change(curr["orders_count"], prev.get("orders_count", 0))
            entry["orders_rub_change_pct"] = _pct_change(curr["orders_rub"], prev.get("orders_rub", 0))
        models_list.append(entry)

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "models": models_list,
    }


async def _handle_margin_levers(channel: str, start_date: str, end_date: str) -> dict:
    """Decompose margin into 5 levers with absolute contribution."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        results, orders = await asyncio.to_thread(
            get_wb_finance, current_start, prev_start, current_end
        )
        periods = _split_periods(results, 19)
        current = _parse_wb_finance_row(periods["current"])
        previous = _parse_wb_finance_row(periods["previous"])
    else:
        results, orders = await asyncio.to_thread(
            get_ozon_finance, current_start, prev_start, current_end
        )
        periods = _split_periods(results, 13)
        current = _parse_ozon_finance_row(periods["current"])
        previous = _parse_ozon_finance_row(periods["previous"])

    if not current or not previous:
        return {"error": f"Нет данных за один из периодов для {channel.upper()}"}

    # Per-unit metrics
    c_sales = current.get("sales_count", 0) or 1
    p_sales = previous.get("sales_count", 0) or 1

    c_rev = current.get("revenue_before_spp", 0)
    p_rev = previous.get("revenue_before_spp", 0)

    levers = {
        "price_before_spp_per_unit": {
            "current": round(c_rev / c_sales, 0),
            "previous": round(p_rev / p_sales, 0),
        },
        "spp_pct": {
            "current": round(_safe_div(current.get("spp_amount", 0), c_rev) * 100, 1),
            "previous": round(_safe_div(previous.get("spp_amount", 0), p_rev) * 100, 1),
        },
        "drr_pct": {
            "current": round(_safe_div(
                current.get("adv_internal", 0) + current.get("adv_external", 0), c_rev
            ) * 100, 1),
            "previous": round(_safe_div(
                previous.get("adv_internal", 0) + previous.get("adv_external", 0), p_rev
            ) * 100, 1),
        },
        "logistics_per_unit": {
            "current": round(current.get("logistics", 0) / c_sales, 0),
            "previous": round(previous.get("logistics", 0) / p_sales, 0),
        },
        "cogs_per_unit": {
            "current": round(current.get("cost_of_goods", 0) / c_sales, 0),
            "previous": round(previous.get("cost_of_goods", 0) / p_sales, 0),
        },
    }

    # Absolute contribution to margin change (waterfall)
    c_adv = current.get("adv_internal", 0) + current.get("adv_external", 0)
    p_adv = previous.get("adv_internal", 0) + previous.get("adv_external", 0)

    waterfall = {
        "revenue_change": round(c_rev - p_rev, 0),
        "commission_change": -round(current.get("commission", 0) - previous.get("commission", 0), 0),
        "spp_change": -round(current.get("spp_amount", 0) - previous.get("spp_amount", 0), 0),
        "advertising_change": -round(c_adv - p_adv, 0),
        "adv_internal_change": -round(current.get("adv_internal", 0) - previous.get("adv_internal", 0), 0),
        "adv_external_change": -round(current.get("adv_external", 0) - previous.get("adv_external", 0), 0),
        "logistics_change": -round(current.get("logistics", 0) - previous.get("logistics", 0), 0),
        "cogs_change": -round(current.get("cost_of_goods", 0) - previous.get("cost_of_goods", 0), 0),
        "storage_change": -round(current.get("storage", 0) - previous.get("storage", 0), 0),
        "nds_change": -round(current.get("nds", 0) - previous.get("nds", 0), 0),
        "other_change": -round(
            (current.get("penalty", 0) + current.get("retention", 0) + current.get("deduction", 0)) -
            (previous.get("penalty", 0) + previous.get("retention", 0) + previous.get("deduction", 0)),
            0,
        ),
        "margin_change_total": round(current.get("margin", 0) - previous.get("margin", 0), 0),
    }

    # Counterfactual: "if X hadn't changed, margin would be..."
    c_margin = current.get("margin", 0)
    counterfactual = {}
    if waterfall["advertising_change"] < 0:
        counterfactual["without_adv_increase"] = {
            "margin_would_be": round(c_margin + abs(waterfall["advertising_change"]), 0),
            "description": f"Если бы реклама осталась на уровне пред. периода, маржа была бы {round(c_margin + abs(waterfall['advertising_change']), 0):,.0f}₽",
        }

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "levers": levers,
        "waterfall": waterfall,
        "counterfactual": counterfactual,
        "current_margin": round(c_margin, 0),
        "previous_margin": round(previous.get("margin", 0), 0),
    }


async def _handle_weekly_breakdown(channel: str, start_date: str, end_date: str) -> dict:
    """Get weekly breakdown for a channel within a period."""
    end_exclusive = (datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    if channel == "wb":
        weeks = await asyncio.to_thread(
            get_wb_weekly_breakdown, start_date, end_exclusive
        )
    else:
        weeks = await asyncio.to_thread(
            get_ozon_weekly_breakdown, start_date, end_exclusive
        )

    # Convert dates and add derived metrics
    for w in weeks:
        for key in ("week_start", "week_end"):
            if hasattr(w.get(key), "strftime"):
                w[key] = w[key].strftime("%Y-%m-%d")
        rev = w.get("revenue_before_spp", 0)
        margin = w.get("margin", 0)
        adv = w.get("adv_total", 0)
        w["margin_pct"] = round(_safe_div(margin, rev) * 100, 1)
        w["drr_pct"] = round(_safe_div(adv, rev) * 100, 1)

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "weeks": weeks,
        "total_weeks": len(weeks),
    }


async def _handle_validate_data_quality(date: str) -> dict:
    """Validate WB data quality for a specific date."""
    result = await asyncio.to_thread(validate_wb_data_quality, date)
    warnings = result.get("warnings", [])

    # Дополнительная проверка на идентичность ДРР (равенство выручки и заказов)
    try:
        finance = await _handle_brand_finance(date, date)
        wb_data = next((c for c in finance.get("channels", []) if c["channel"] == "WB"), None)
        if wb_data:
            rev = wb_data.get("revenue_before_spp", 0)
            orders = wb_data.get("orders_rub", 0)
            if rev > 0 and rev == orders:
                warnings.append({
                    'type': 'drr_metrics_identity',
                    'severity': 'WARNING',
                    'message': f"Выручка и заказы за {date} идентичны ({rev} руб). Проверьте корректность ДРР от заказов vs ДРР от продаж.",
                    'explanation': 'В реальных данных выручка и заказы практически никогда не совпадают до рубля. Это может указывать на ошибку подгрузки данных.'
                })
    except Exception as e:
        logger.error(f"Error during extended DQ check: {e}")

    return {
        "date": date,
        "warnings": warnings,
        "margin_adjustment": result.get("margin_adjustment", 0),
        "data_quality": "OK" if not warnings else "WARNINGS",
    }


async def _handle_product_statuses() -> dict:
    """Get product statuses from Supabase."""
    try:
        statuses = await asyncio.to_thread(get_artikuly_statuses)
        # Group by status
        by_status = {}
        for article, status in statuses.items():
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(article)

        return {
            "total_products": len(statuses),
            "by_status": {s: {"count": len(arts), "articles": arts[:10]} for s, arts in by_status.items()},
        }
    except Exception as e:
        return {"error": f"Supabase unavailable: {e}"}


# Безопасные операторы для AST-калькулятора (вместо eval)
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_ast(node):
    """Рекурсивный AST-калькулятор: только числа и +-*/."""
    if isinstance(node, ast.Expression):
        return _safe_eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_safe_eval_ast(node.left), _safe_eval_ast(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_safe_eval_ast(node.operand))
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


async def _handle_calculate_metric(formula: str, values: dict) -> dict:
    """Safe AST-based calculator for metric verification (no eval)."""
    try:
        expr = formula
        for name, val in sorted(values.items(), key=lambda x: -len(x[0])):
            expr = expr.replace(name, str(float(val)))

        tree = ast.parse(expr, mode='eval')
        result = _safe_eval_ast(tree)
        return {
            "formula": formula,
            "values": values,
            "substituted": expr,
            "result": round(float(result), 2),
        }
    except ZeroDivisionError:
        return {"error": "Division by zero", "formula": formula, "values": values}
    except Exception as e:
        return {"error": str(e), "formula": formula, "values": values}


# =============================================================================
# TOOL REGISTRY AND EXECUTOR
# =============================================================================

TOOL_HANDLERS = {
    "get_brand_finance": _handle_brand_finance,
    "get_channel_finance": _handle_channel_finance,
    "get_model_breakdown": _handle_model_breakdown,
    "get_daily_trend": _handle_daily_trend,
    "get_advertising_stats": _handle_advertising_stats,
    "get_model_advertising": _handle_model_advertising,
    "get_orders_by_model": _handle_orders_by_model,
    "get_margin_levers": _handle_margin_levers,
    "get_weekly_breakdown": _handle_weekly_breakdown,
    "validate_data_quality": _handle_validate_data_quality,
    "get_product_statuses": _handle_product_statuses,
    "calculate_metric": _handle_calculate_metric,
}

# ─── Price Analysis Tools ────────────────────────────────────
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS, PRICE_TOOL_HANDLERS

TOOL_DEFINITIONS.extend(PRICE_TOOL_DEFINITIONS)
TOOL_HANDLERS.update(PRICE_TOOL_HANDLERS)


async def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    Execute a tool by name with given arguments.

    Returns JSON string with result or error.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)

    try:
        logger.info(f"Tool call: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")
        result = await handler(**arguments)
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"Tool result: {tool_name} → {len(result_json)} chars")
        return result_json
    except TypeError as e:
        logger.error(f"Tool {tool_name} argument error: {e}")
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {e}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Tool {tool_name} execution error: {e}", exc_info=True)
        return json.dumps({"error": f"Tool execution failed: {e}"}, ensure_ascii=False)
