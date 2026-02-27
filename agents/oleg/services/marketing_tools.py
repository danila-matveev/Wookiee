"""
Marketing Tools — инструменты маркетинговой аналитики для агента Олег.

Обёртки над shared/data_layer.py в формате OpenAI function calling.
Все SQL-запросы остаются в data_layer.py — здесь только парсинг, агрегация
и делегирование к существующим handler-ам из agent_tools.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Helpers from agent_tools ────────────────────────────────────
from agents.oleg.services.agent_tools import (
    _calc_comparison_dates,
    _safe_div,
    _pct_change,
    _enrich_ad_metrics,
    _handle_channel_finance,
    _handle_margin_levers,
    _handle_model_breakdown,
    _handle_advertising_stats,
)
from shared.data_layer import to_float
from shared.model_mapping import map_to_osnova as _map_to_osnova

# ── New data_layer functions (marketing-specific) ───────────────
from shared.data_layer import (
    get_wb_external_ad_breakdown,
    get_ozon_external_ad_breakdown,
    get_wb_organic_vs_paid_funnel,
    get_wb_ad_daily_series,
    get_ozon_ad_daily_series,
    get_wb_model_ad_roi,
    get_ozon_model_ad_roi,
    get_ozon_ad_by_sku,
    get_wb_campaign_stats,
    get_wb_ad_budget_utilization,
)


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

MARKETING_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_marketing_overview",
            "description": (
                "Маркетинговая сводка: расход на рекламу, ДРР%, CPO, заказы по каналам. "
                "Объединяет финансовые данные и рекламную статистику в единый обзор. "
                "Используй ПЕРВЫМ для общей маркетинговой картины."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon", "both"],
                        "description": "Канал: wb, ozon или both для обоих",
                    },
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "lk": {
                        "type": "string",
                        "enum": ["ООО", "ИП"],
                        "description": "Юрлицо (опционально)",
                    },
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_funnel_analysis",
            "description": (
                "Анализ рекламной воронки канала: показы → клики → корзина → заказы. "
                "CTR, CPC, CPM, CPL, CPO, конверсии по каждому шагу. "
                "Для WB также органическая воронка: карточка → корзина → заказ → выкуп."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon", "both"],
                        "description": "Канал",
                    },
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "lk": {
                        "type": "string",
                        "enum": ["ООО", "ИП"],
                        "description": "Юрлицо (опционально)",
                    },
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_organic_vs_paid",
            "description": (
                "Сравнение органической и рекламной воронки WB: доля трафика, "
                "конверсии, заказы из органики vs рекламы. Только для WB."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "lk": {
                        "type": "string",
                        "enum": ["ООО", "ИП"],
                        "description": "Юрлицо (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_external_ad_breakdown",
            "description": (
                "Разбивка внешней рекламы: блогеры, ВК, креаторы и др. "
                "Расход, заказы, ДРР по каждому типу с сравнением периодов."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon", "both"],
                        "description": "Канал",
                    },
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "lk": {
                        "type": "string",
                        "enum": ["ООО", "ИП"],
                        "description": "Юрлицо (опционально)",
                    },
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_performance",
            "description": (
                "Эффективность рекламных кампаний. Для WB — разбивка по кампаниям "
                "(расход, показы, клики, заказы, CTR, CPC). Для OZON — общая статистика."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon"],
                        "description": "Канал",
                    },
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
            "name": "get_model_ad_efficiency",
            "description": (
                "Эффективность рекламы по моделям: расход, заказы через рекламу, "
                "ДРР%, ROMI%, CTR%, CPC. Позволяет найти модели с лучшим/худшим ROI рекламы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon", "both"],
                        "description": "Канал",
                    },
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "lk": {
                        "type": "string",
                        "enum": ["ООО", "ИП"],
                        "description": "Юрлицо (опционально)",
                    },
                },
                "required": ["channel", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ad_daily_trend",
            "description": (
                "Дневная динамика рекламных метрик: расход, показы, клики, "
                "CTR, CPC, заказы по каждому дню. Для поиска аномалий и трендов в рекламе."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon", "both"],
                        "description": "Канал",
                    },
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
            "name": "get_ad_budget_utilization",
            "description": (
                "Утилизация рекламного бюджета WB: план vs факт, "
                "дневное распределение расхода, пиковые/провальные дни. Только для WB."
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
            "name": "get_ad_spend_correlation",
            "description": (
                "Корреляция рекламного расхода с заказами и маржой по моделям. "
                "Pearson correlation показывает связь: >0.5 сильная, 0.3-0.5 средняя, <0.3 слабая. "
                "Помогает оценить эффективность рекламы на уровне моделей."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["wb", "ozon"],
                        "description": "Канал",
                    },
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
            "name": "get_channel_finance",
            "description": (
                "Детальные финансы одного канала (wb или ozon): маржа, выручка, заказы, продажи, "
                "реклама (внутренняя/внешняя отдельно), логистика, хранение, себестоимость, "
                "комиссия, СПП%, ДРР%. Делегирует к основному get_channel_finance."
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
            "name": "get_margin_levers",
            "description": (
                "Декомпозиция маржи по 5 рычагам: цена до СПП, СПП%, ДРР (внутр/внешн), "
                "логистика ₽/ед, себестоимость ₽/ед. Рублёвый вклад каждого фактора. "
                "Делегирует к основному get_margin_levers."
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
                "Полная декомпозиция по моделям для канала: маржа, продажи, реклама, ДРР. "
                "Делегирует к основному get_model_breakdown."
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
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def _handle_marketing_overview(
    channel: str, start_date: str, end_date: str, lk: str = None,
) -> dict:
    """Marketing overview: spend, DRR, CPO, orders across channels."""

    async def _build_channel_overview(ch: str) -> dict:
        finance_data, ad_data = await asyncio.gather(
            _handle_channel_finance(ch, start_date, end_date),
            _handle_advertising_stats(ch, start_date, end_date),
        )
        current = finance_data.get("current", {})
        ads_current = ad_data.get("advertising", {}).get("current", {})
        ads_previous = ad_data.get("advertising", {}).get("previous", {})

        return {
            "channel": ch.upper(),
            "current": {
                "ad_spend_internal": current.get("adv_internal", 0),
                "ad_spend_external": current.get("adv_external", 0),
                "ad_spend_total": current.get("adv_total", 0),
                "drr_pct": current.get("drr_pct", 0),
                "revenue_before_spp": current.get("revenue_before_spp", 0),
                "orders_count": current.get("orders_count", 0),
                "orders_rub": current.get("orders_rub", 0),
                "margin": current.get("margin", 0),
                "margin_pct": current.get("margin_pct", 0),
                "cpo_rub": ads_current.get("cpo_rub", 0),
                "cpm_rub": ads_current.get("cpm_rub", 0),
                "ctr_pct": ads_current.get("ctr_pct", 0),
                "cpc_rub": ads_current.get("cpc_rub", 0),
                "ad_orders": ads_current.get("ad_orders", 0),
            },
            "previous": {
                "ad_spend_total": (
                    finance_data.get("previous", {}).get("adv_internal", 0)
                    + finance_data.get("previous", {}).get("adv_external", 0)
                ),
                "drr_pct": finance_data.get("previous", {}).get("drr_pct", 0),
                "orders_count": finance_data.get("previous", {}).get("orders_count", 0),
                "cpo_rub": ads_previous.get("cpo_rub", 0),
                "margin": finance_data.get("previous", {}).get("margin", 0),
            },
            "changes": finance_data.get("changes", {}),
        }

    if channel == "both":
        wb_overview, ozon_overview = await asyncio.gather(
            _build_channel_overview("wb"),
            _build_channel_overview("ozon"),
        )
        # Build combined totals
        wb_c = wb_overview["current"]
        oz_c = ozon_overview["current"]
        combined_spend = wb_c["ad_spend_total"] + oz_c["ad_spend_total"]
        combined_rev = wb_c["revenue_before_spp"] + oz_c["revenue_before_spp"]
        combined_orders = wb_c["orders_count"] + oz_c["orders_count"]
        combined_margin = wb_c["margin"] + oz_c["margin"]

        return {
            "period": f"{start_date} — {end_date}",
            "brand_totals": {
                "ad_spend_total": combined_spend,
                "drr_pct": round(_safe_div(combined_spend, combined_rev) * 100, 1),
                "orders_count": combined_orders,
                "revenue_before_spp": combined_rev,
                "margin": combined_margin,
                "margin_pct": round(_safe_div(combined_margin, combined_rev) * 100, 1),
            },
            "wb": wb_overview,
            "ozon": ozon_overview,
        }
    else:
        overview = await _build_channel_overview(channel)
        return {
            "period": f"{start_date} — {end_date}",
            channel: overview,
        }


async def _handle_funnel_analysis(
    channel: str, start_date: str, end_date: str, lk: str = None,
) -> dict:
    """Funnel analysis — delegates to _handle_advertising_stats."""
    if channel == "both":
        wb_data, ozon_data = await asyncio.gather(
            _handle_advertising_stats("wb", start_date, end_date),
            _handle_advertising_stats("ozon", start_date, end_date),
        )
        return {
            "period": f"{start_date} — {end_date}",
            "wb": wb_data,
            "ozon": ozon_data,
        }
    else:
        result = await _handle_advertising_stats(channel, start_date, end_date)
        return result


async def _handle_organic_vs_paid(
    start_date: str, end_date: str, lk: str = None,
) -> dict:
    """Organic vs Paid funnel for WB."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    organic_results, paid_results = await asyncio.to_thread(
        get_wb_organic_vs_paid_funnel, current_start, prev_start, current_end, lk
    )

    current = {}
    previous = {}

    # Parse organic funnel (content_analysis):
    # period, card_opens, add_to_cart, funnel_orders, buyouts,
    # card_to_cart_pct, cart_to_order_pct, order_to_buyout_pct
    organic_by_period: dict = {}
    for row in organic_results:
        organic_by_period[row[0]] = {
            "card_opens": to_float(row[1]),
            "add_to_cart": to_float(row[2]),
            "funnel_orders": to_float(row[3]),
            "buyouts": to_float(row[4]),
            "card_to_cart_pct": to_float(row[5]),
            "cart_to_order_pct": to_float(row[6]),
            "order_to_buyout_pct": to_float(row[7]),
        }

    # Parse paid funnel (wb_adv):
    # period, ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend, ctr, cpc
    paid_by_period: dict = {}
    for row in paid_results:
        paid_by_period[row[0]] = {
            "ad_views": to_float(row[1]),
            "ad_clicks": to_float(row[2]),
            "ad_to_cart": to_float(row[3]),
            "ad_orders": to_float(row[4]),
            "ad_spend": to_float(row[5]),
            "ctr": to_float(row[6]),
            "cpc": to_float(row[7]),
        }

    # Merge organic + paid into unified per-period dicts
    for period_key in ("current", "previous"):
        org = organic_by_period.get(period_key, {})
        paid = paid_by_period.get(period_key, {})
        parsed = {
            "organic_views": org.get("card_opens", 0),
            "organic_add_to_cart": org.get("add_to_cart", 0),
            "organic_orders": org.get("funnel_orders", 0),
            "organic_buyouts": org.get("buyouts", 0),
            "organic_card_to_cart_pct": org.get("card_to_cart_pct", 0),
            "organic_cart_to_order_pct": org.get("cart_to_order_pct", 0),
            "organic_order_to_buyout_pct": org.get("order_to_buyout_pct", 0),
            "paid_views": paid.get("ad_views", 0),
            "paid_clicks": paid.get("ad_clicks", 0),
            "paid_to_cart": paid.get("ad_to_cart", 0),
            "paid_orders": paid.get("ad_orders", 0),
            "paid_spend": paid.get("ad_spend", 0),
            "paid_ctr_pct": paid.get("ctr", 0),
        }
        total_views = parsed["organic_views"] + parsed["paid_views"]
        total_orders = parsed["organic_orders"] + parsed["paid_orders"]

        parsed["organic_share_views_pct"] = round(
            _safe_div(parsed["organic_views"], total_views) * 100, 1
        )
        parsed["paid_share_views_pct"] = round(
            _safe_div(parsed["paid_views"], total_views) * 100, 1
        )
        parsed["organic_share_orders_pct"] = round(
            _safe_div(parsed["organic_orders"], total_orders) * 100, 1
        )
        parsed["paid_share_orders_pct"] = round(
            _safe_div(parsed["paid_orders"], total_orders) * 100, 1
        )
        parsed["organic_cr_pct"] = round(
            _safe_div(parsed["organic_orders"], parsed["organic_views"]) * 100, 2
        )
        parsed["paid_cr_pct"] = round(
            _safe_div(parsed["paid_orders"], parsed["paid_clicks"]) * 100, 2
        )
        parsed["paid_cpo_rub"] = round(
            _safe_div(parsed["paid_spend"], parsed["paid_orders"]), 1
        )
        parsed["total_views"] = total_views
        parsed["total_orders"] = total_orders

        if period_key == "current":
            current = parsed
        else:
            previous = parsed

    changes = {}
    if current and previous:
        changes["organic_views_change_pct"] = _pct_change(
            current.get("organic_views", 0), previous.get("organic_views", 0)
        )
        changes["paid_views_change_pct"] = _pct_change(
            current.get("paid_views", 0), previous.get("paid_views", 0)
        )
        changes["organic_orders_change_pct"] = _pct_change(
            current.get("organic_orders", 0), previous.get("organic_orders", 0)
        )
        changes["paid_orders_change_pct"] = _pct_change(
            current.get("paid_orders", 0), previous.get("paid_orders", 0)
        )
        changes["organic_share_views_change_pp"] = round(
            current.get("organic_share_views_pct", 0)
            - previous.get("organic_share_views_pct", 0),
            1,
        )

    return {
        "channel": "WB",
        "period": f"{start_date} — {end_date}",
        "current": current,
        "previous": previous,
        "changes": changes,
    }


async def _handle_external_ad_breakdown(
    channel: str, start_date: str, end_date: str, lk: str = None,
) -> dict:
    """External ad breakdown: bloggers, VK, creators, etc."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    async def _fetch_channel(ch: str) -> dict:
        if ch == "wb":
            rows = await asyncio.to_thread(
                get_wb_external_ad_breakdown, current_start, prev_start, current_end, lk
            )
        else:
            rows = await asyncio.to_thread(
                get_ozon_external_ad_breakdown, current_start, prev_start, current_end, lk
            )

        # SQL returns ONE row per period with spend columns per ad type.
        # WB: period, adv_internal, adv_bloggers, adv_vk, adv_creators, adv_total
        # OZON: period, adv_internal, adv_external, adv_vk, adv_total
        current_types = {}
        previous_types = {}
        for row in rows:
            period = row[0]
            if ch == "wb":
                types_map = {
                    "Внутренняя МП": to_float(row[1]),
                    "Блогеры": to_float(row[2]),
                    "VK Реклама": to_float(row[3]),
                    "Creators": to_float(row[4]),
                }
            else:
                types_map = {
                    "Внутренняя МП": to_float(row[1]),
                    "Внешняя реклама": to_float(row[2]),
                    "VK Реклама": to_float(row[3]),
                }
            target = current_types if period == "current" else previous_types
            for ad_type, spend in types_map.items():
                target[ad_type] = {"ad_type": ad_type, "spend": spend}

        # Build list with changes
        breakdown = []
        all_types = set(current_types.keys()) | set(previous_types.keys())
        for ad_type in sorted(all_types):
            curr = current_types.get(ad_type, {"ad_type": ad_type, "spend": 0})
            prev = previous_types.get(ad_type, {})
            entry = {**curr}
            entry["spend_change_pct"] = _pct_change(
                curr["spend"], prev.get("spend", 0)
            )
            breakdown.append(entry)

        total_spend = sum(d["spend"] for d in current_types.values())
        return {
            "channel": ch.upper(),
            "breakdown": breakdown,
            "total_external_spend": total_spend,
        }

    if channel == "both":
        wb_data, ozon_data = await asyncio.gather(
            _fetch_channel("wb"),
            _fetch_channel("ozon"),
        )
        return {
            "period": f"{start_date} — {end_date}",
            "wb": wb_data,
            "ozon": ozon_data,
            "total_external_spend": wb_data["total_external_spend"] + ozon_data["total_external_spend"],
        }
    else:
        result = await _fetch_channel(channel)
        result["period"] = f"{start_date} — {end_date}"
        return result


async def _handle_campaign_performance(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Campaign-level performance."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        rows = await asyncio.to_thread(
            get_wb_campaign_stats, current_start, prev_start, current_end
        )

        # SQL: period, campaign, views, clicks, spend, to_cart, orders, ctr, cpc
        current_campaigns = {}
        previous_campaigns = {}
        for row in rows:
            period = row[0]
            campaign = row[1]
            data = {
                "campaign": campaign,
                "views": to_float(row[2]),
                "clicks": to_float(row[3]),
                "spend": to_float(row[4]),
                "to_cart": to_float(row[5]),
                "orders": to_float(row[6]),
            }
            data["ctr_pct"] = round(_safe_div(data["clicks"], data["views"]) * 100, 2)
            data["cpc_rub"] = round(_safe_div(data["spend"], data["clicks"]), 1)
            data["cpo_rub"] = round(_safe_div(data["spend"], data["orders"]), 1)
            data["cpm_rub"] = round(_safe_div(data["spend"], data["views"]) * 1000, 1)

            target = current_campaigns if period == "current" else previous_campaigns
            target[campaign] = data

        campaigns_list = []
        for campaign, curr in sorted(
            current_campaigns.items(), key=lambda x: x[1]["spend"], reverse=True
        ):
            prev = previous_campaigns.get(campaign, {})
            entry = {**curr}
            entry["spend_change_pct"] = _pct_change(curr["spend"], prev.get("spend", 0))
            entry["orders_change_pct"] = _pct_change(curr["orders"], prev.get("orders", 0))
            entry["ctr_change_pp"] = round(
                curr.get("ctr_pct", 0) - prev.get("ctr_pct", 0), 2
            )
            campaigns_list.append(entry)

        return {
            "channel": "WB",
            "period": f"{start_date} — {end_date}",
            "campaigns": campaigns_list,
            "total_campaigns": len(campaigns_list),
        }

    else:
        # OZON: return overall advertising stats (no campaign-level breakdown)
        result = await _handle_advertising_stats("ozon", start_date, end_date)
        result["note"] = "OZON не предоставляет разбивку по кампаниям, показана общая статистика"
        return result


async def _handle_model_ad_efficiency(
    channel: str, start_date: str, end_date: str, lk: str = None,
) -> dict:
    """Per-model ad efficiency: spend, orders, DRR, ROMI, CTR, CPC."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    async def _fetch_channel(ch: str) -> dict:
        if ch == "wb":
            rows = await asyncio.to_thread(
                get_wb_model_ad_roi, current_start, prev_start, current_end, lk
            )
        else:
            rows = await asyncio.to_thread(
                get_ozon_model_ad_roi, current_start, prev_start, current_end, lk
            )

        # SQL returns: period, model, ad_spend, ad_orders, revenue, margin,
        #               drr_pct, romi
        current_models = {}
        previous_models = {}
        for row in rows:
            period = row[0]
            raw_model = row[1]
            model = _map_to_osnova(raw_model)

            target = current_models if period == "current" else previous_models
            if model not in target:
                target[model] = {
                    "model": model,
                    "ad_spend": 0,
                    "ad_orders": 0,
                    "revenue": 0,
                    "margin": 0,
                }
            target[model]["ad_spend"] += to_float(row[2])
            target[model]["ad_orders"] += to_float(row[3])
            target[model]["revenue"] += to_float(row[4])
            target[model]["margin"] += to_float(row[5])

        # Enrich with derived metrics
        for d in (current_models, previous_models):
            for model_name in list(d.keys()):
                data = d[model_name]
                spend = data["ad_spend"]
                orders = data["ad_orders"]
                rev = data["revenue"]
                margin = data["margin"]

                data["drr_pct"] = round(_safe_div(spend, rev) * 100, 1)
                data["romi_pct"] = round(_safe_div(margin - spend, spend) * 100, 1)
                data["cpo_rub"] = round(_safe_div(spend, orders), 1)

        # Build list with changes
        models_list = []
        all_models = set(current_models.keys()) | set(previous_models.keys())
        for model_name in sorted(all_models):
            if model_name == "Other":
                continue
            curr = current_models.get(
                model_name,
                {
                    "model": model_name, "ad_spend": 0, "ad_views": 0,
                    "ad_clicks": 0, "ad_orders": 0, "revenue": 0, "margin": 0,
                    "drr_pct": 0, "romi_pct": 0, "ctr_pct": 0, "cpc_rub": 0,
                    "cpo_rub": 0, "cpm_rub": 0,
                },
            )
            prev = previous_models.get(model_name, {})
            entry = {**curr}
            entry["spend_change_pct"] = _pct_change(curr["ad_spend"], prev.get("ad_spend", 0))
            entry["orders_change_pct"] = _pct_change(curr["ad_orders"], prev.get("ad_orders", 0))
            entry["drr_change_pp"] = round(
                curr.get("drr_pct", 0) - prev.get("drr_pct", 0), 1
            )
            entry["romi_change_pp"] = round(
                curr.get("romi_pct", 0) - prev.get("romi_pct", 0), 1
            )
            models_list.append(entry)

        # Sort by spend descending
        models_list.sort(key=lambda x: x["ad_spend"], reverse=True)

        return {
            "channel": ch.upper(),
            "models": models_list,
            "total_models": len(models_list),
        }

    if channel == "both":
        wb_data, ozon_data = await asyncio.gather(
            _fetch_channel("wb"),
            _fetch_channel("ozon"),
        )
        return {
            "period": f"{start_date} — {end_date}",
            "wb": wb_data,
            "ozon": ozon_data,
        }
    else:
        result = await _fetch_channel(channel)
        result["period"] = f"{start_date} — {end_date}"
        return result


async def _handle_ad_daily_trend(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Daily ad time-series."""

    async def _fetch_channel(ch: str) -> list:
        if ch == "wb":
            rows = await asyncio.to_thread(
                get_wb_ad_daily_series, start_date, end_date
            )
        else:
            rows = await asyncio.to_thread(
                get_ozon_ad_daily_series, start_date, end_date
            )

        days = []
        for row in rows:
            if ch == "wb":
                # WB SQL: date, views, clicks, spend, to_cart, orders, ctr, cpc
                day = {
                    "date": str(row[0]),
                    "ad_views": to_float(row[1]),
                    "ad_clicks": to_float(row[2]),
                    "ad_spend": to_float(row[3]),
                    "ad_to_cart": to_float(row[4]),
                    "ad_orders": to_float(row[5]),
                }
            else:
                # OZON SQL: date, views, clicks, orders, spend, avg_bid, ctr, cpc
                # NB: orders from adv_stats_daily are per-campaign,
                # may overcount when same order spans multiple campaigns
                day = {
                    "date": str(row[0]),
                    "ad_views": to_float(row[1]),
                    "ad_clicks": to_float(row[2]),
                    "ad_orders": to_float(row[3]),
                    "ad_spend": to_float(row[4]),
                }
            day["ctr_pct"] = round(_safe_div(day["ad_clicks"], day["ad_views"]) * 100, 2)
            day["cpc_rub"] = round(_safe_div(day["ad_spend"], day["ad_clicks"]), 1)
            day["cpo_rub"] = round(_safe_div(day["ad_spend"], day["ad_orders"]), 1)
            day["cpm_rub"] = round(_safe_div(day["ad_spend"], day["ad_views"]) * 1000, 1)
            days.append(day)
        return days

    if channel == "both":
        wb_days, ozon_days = await asyncio.gather(
            _fetch_channel("wb"),
            _fetch_channel("ozon"),
        )
        return {
            "period": f"{start_date} — {end_date}",
            "wb": {"days": wb_days, "total_days": len(wb_days)},
            "ozon": {"days": ozon_days, "total_days": len(ozon_days)},
        }
    else:
        days = await _fetch_channel(channel)
        return {
            "channel": channel.upper(),
            "period": f"{start_date} — {end_date}",
            "days": days,
            "total_days": len(days),
        }


async def _handle_ad_budget_utilization(
    start_date: str, end_date: str,
) -> dict:
    """WB ad budget utilization: daily spend distribution, peaks, lows."""
    # Returns (budget_rows, actual_rows):
    #   budget_rows: (date, budget)
    #   actual_rows: (date, actual_spend, views, clicks, orders)
    budget_rows, actual_rows = await asyncio.to_thread(
        get_wb_ad_budget_utilization, start_date, end_date
    )

    # Build budget lookup by date
    budget_by_date = {}
    for row in budget_rows:
        budget_by_date[str(row[0])] = to_float(row[1])

    days = []
    total_spend = 0.0
    for row in actual_rows:
        date_str = str(row[0])
        actual_spend = to_float(row[1])
        planned = budget_by_date.get(date_str, 0)
        day = {
            "date": date_str,
            "budget_planned": planned,
            "budget_spent": actual_spend,
            "utilization_pct": round(
                _safe_div(actual_spend, planned) * 100, 1
            ),
        }
        total_spend += actual_spend
        days.append(day)

    num_days = len(days) or 1
    avg_daily_spend = round(total_spend / num_days, 0)

    # Find peak and low days
    if days:
        peak_day = max(days, key=lambda d: d["budget_spent"])
        low_day = min(days, key=lambda d: d["budget_spent"])
    else:
        peak_day = {}
        low_day = {}

    total_planned = sum(d.get("budget_planned", 0) for d in days)

    return {
        "channel": "WB",
        "period": f"{start_date} — {end_date}",
        "days": days,
        "total_days": num_days,
        "total_spend": total_spend,
        "total_planned": total_planned,
        "overall_utilization_pct": round(
            _safe_div(total_spend, total_planned) * 100, 1
        ),
        "avg_daily_spend": avg_daily_spend,
        "peak_day": peak_day,
        "low_day": low_day,
    }


async def _handle_ad_spend_correlation(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Pearson correlation between ad spend and orders/margin across models."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        rows = await asyncio.to_thread(
            get_wb_model_ad_roi, current_start, prev_start, current_end
        )
    else:
        rows = await asyncio.to_thread(
            get_ozon_model_ad_roi, current_start, prev_start, current_end
        )

    # Collect current period data per model
    model_data = {}
    for row in rows:
        if row[0] != "current":
            continue
        raw_model = row[1]
        model = _map_to_osnova(raw_model)
        if model == "Other":
            continue

        if model not in model_data:
            model_data[model] = {"ad_spend": 0, "ad_orders": 0, "revenue": 0, "margin": 0}

        # SQL: period, model, ad_spend, ad_orders, revenue, margin, drr_pct, romi
        model_data[model]["ad_spend"] += to_float(row[2])
        model_data[model]["ad_orders"] += to_float(row[3])
        model_data[model]["revenue"] += to_float(row[4])
        model_data[model]["margin"] += to_float(row[5])

    if len(model_data) < 3:
        return {
            "channel": channel.upper(),
            "period": f"{start_date} — {end_date}",
            "error": "Недостаточно моделей для корреляционного анализа (минимум 3)",
            "models_count": len(model_data),
        }

    # Calculate Pearson correlation
    spends = []
    orders_list = []
    margins = []
    model_names = []
    for model_name, data in model_data.items():
        model_names.append(model_name)
        spends.append(data["ad_spend"])
        orders_list.append(data["ad_orders"])
        margins.append(data["margin"])

    def _pearson(x: list, y: list) -> float:
        n = len(x)
        if n < 3:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        std_x = (sum((xi - mean_x) ** 2 for xi in x)) ** 0.5
        std_y = (sum((yi - mean_y) ** 2 for yi in y)) ** 0.5
        denom = std_x * std_y
        if denom == 0:
            return 0.0
        return round(cov / denom, 3)

    corr_spend_orders = _pearson(spends, orders_list)
    corr_spend_margin = _pearson(spends, margins)

    def _interpret(r: float) -> str:
        abs_r = abs(r)
        if abs_r >= 0.7:
            strength = "сильная"
        elif abs_r >= 0.5:
            strength = "заметная"
        elif abs_r >= 0.3:
            strength = "средняя"
        else:
            strength = "слабая"
        direction = "положительная" if r > 0 else "отрицательная"
        return f"{strength} {direction} связь"

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "models_count": len(model_data),
        "correlations": {
            "spend_vs_orders": {
                "pearson_r": corr_spend_orders,
                "interpretation": _interpret(corr_spend_orders),
            },
            "spend_vs_margin": {
                "pearson_r": corr_spend_margin,
                "interpretation": _interpret(corr_spend_margin),
            },
        },
        "models_data": [
            {
                "model": model_names[i],
                "ad_spend": spends[i],
                "ad_orders": orders_list[i],
                "margin": margins[i],
            }
            for i in range(len(model_names))
        ],
    }


# ── Delegation handlers (pass-through to agent_tools) ──────────

async def _handle_mkt_channel_finance(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Delegate to agent_tools._handle_channel_finance."""
    return await _handle_channel_finance(channel, start_date, end_date)


async def _handle_mkt_margin_levers(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Delegate to agent_tools._handle_margin_levers."""
    return await _handle_margin_levers(channel, start_date, end_date)


async def _handle_mkt_model_breakdown(
    channel: str, start_date: str, end_date: str,
) -> dict:
    """Delegate to agent_tools._handle_model_breakdown."""
    return await _handle_model_breakdown(channel, start_date, end_date)


# =============================================================================
# HANDLERS MAP
# =============================================================================

MARKETING_TOOL_HANDLERS: Dict[str, Any] = {
    "get_marketing_overview": _handle_marketing_overview,
    "get_funnel_analysis": _handle_funnel_analysis,
    "get_organic_vs_paid": _handle_organic_vs_paid,
    "get_external_ad_breakdown": _handle_external_ad_breakdown,
    "get_campaign_performance": _handle_campaign_performance,
    "get_model_ad_efficiency": _handle_model_ad_efficiency,
    "get_ad_daily_trend": _handle_ad_daily_trend,
    "get_ad_budget_utilization": _handle_ad_budget_utilization,
    "get_ad_spend_correlation": _handle_ad_spend_correlation,
    "get_channel_finance": _handle_mkt_channel_finance,
    "get_margin_levers": _handle_mkt_margin_levers,
    "get_model_breakdown": _handle_mkt_model_breakdown,
}


# =============================================================================
# EXECUTOR
# =============================================================================

async def execute_marketing_tool(tool_name: str, arguments: dict) -> str:
    """
    Execute a marketing tool by name with given arguments.

    Returns JSON string with result or error.
    """
    handler = MARKETING_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown marketing tool: {tool_name}"}, ensure_ascii=False)

    try:
        logger.info(f"Marketing tool call: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")
        result = await handler(**arguments)
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"Marketing tool result: {tool_name} → {len(result_json)} chars")
        return result_json
    except TypeError as e:
        logger.error(f"Marketing tool {tool_name} argument error: {e}")
        return json.dumps(
            {"error": f"Invalid arguments for {tool_name}: {e}"},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Marketing tool {tool_name} execution error: {e}", exc_info=True)
        return json.dumps(
            {"error": f"Tool execution failed: {e}"},
            ensure_ascii=False,
        )
