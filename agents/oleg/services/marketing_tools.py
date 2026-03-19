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
    get_wb_organic_by_status,
    get_wb_ad_daily_series,
    get_ozon_ad_daily_series,
    get_wb_model_ad_roi,
    get_ozon_model_ad_roi,
    get_ozon_ad_by_sku,
    get_ozon_organic_estimated,
    get_wb_campaign_stats,
    get_wb_ad_budget_utilization,
    get_wb_traffic_by_model,
    get_wb_model_metrics_comparison,
)


# ── Constants ─────────────────────────────────────────────────────
MIN_AD_SPEND_RUB = 100  # Exclude stopped campaigns with negligible spend

# ── LK (юрлицо) resolution helper ─────────────────────────────────

_LK_MAPPING = {
    "wb": {"ООО": "WB ООО ВУКИ", "ИП": "WB ИП Медведева П.В."},
    "ozon": {"ООО": "Ozon ООО ВУКИ", "ИП": "Ozon ИП Медведева П.В."},
}


def _resolve_lk(channel: str, lk_short: Optional[str]) -> Optional[str]:
    """Convert short lk name (ООО/ИП) to full DB value for a channel."""
    if lk_short is None:
        return None
    return _LK_MAPPING.get(channel, {}).get(lk_short)


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
    {
        "type": "function",
        "function": {
            "name": "get_model_anomalies",
            "description": (
                "Аномалии по моделям WB: сравнение метрик текущего и прошлого периода. "
                "Находит модели с отклонением >30% по CTR, переходам, корзине, заказам, "
                "конверсиям. Генерирует гипотезы причин и рекомендации."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Начало периода YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Конец периода YYYY-MM-DD (включительно)"},
                    "threshold_pct": {
                        "type": "number",
                        "description": "Порог отклонения в % (по умолчанию 30)",
                    },
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
            "name": "get_ozon_organic_estimate",
            "description": (
                "Расчётная органика OZON по моделям: organic_orders = total_orders − ad_orders. "
                "OZON не предоставляет органические показы/переходы напрямую, "
                "но заказы можно оценить через вычитание рекламных из общих."
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
            "name": "get_ad_profitability_alerts",
            "description": (
                "Алерты убыточной рекламы: модели где ROMI < порога или "
                "CAC > прибыли на продажу. Для секции «Чёрные дыры рекламы»."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Начало периода YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Конец периода YYYY-MM-DD (включительно)",
                    },
                    "romi_threshold": {
                        "type": "number",
                        "description": "Порог ROMI (по умолчанию 100). Модели ниже — убыточные",
                    },
                },
                "required": ["start_date", "end_date"],
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

        prev_fin = finance_data.get("previous", {})
        curr_orders_count = current.get("orders_count", 0)
        curr_orders_rub = current.get("orders_rub", 0)
        prev_orders_count = prev_fin.get("orders_count", 0)
        prev_orders_rub = prev_fin.get("orders_rub", 0)
        curr_avg_check = round(_safe_div(curr_orders_rub, curr_orders_count), 1)
        prev_avg_check = round(_safe_div(prev_orders_rub, prev_orders_count), 1)

        return {
            "channel": ch.upper(),
            "current": {
                "ad_spend_internal": current.get("adv_internal", 0),
                "ad_spend_external": current.get("adv_external", 0),
                "ad_spend_total": current.get("adv_total", 0),
                "drr_pct": current.get("drr_pct", 0),
                "revenue_before_spp": current.get("revenue_before_spp", 0),
                "orders_count": curr_orders_count,
                "orders_rub": curr_orders_rub,
                "avg_check_order": curr_avg_check,
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
                    prev_fin.get("adv_internal", 0)
                    + prev_fin.get("adv_external", 0)
                ),
                "drr_pct": prev_fin.get("drr_pct", 0),
                "orders_count": prev_orders_count,
                "avg_check_order": prev_avg_check,
                "cpo_rub": ads_previous.get("cpo_rub", 0),
                "margin": prev_fin.get("margin", 0),
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
        combined_orders_rub = wb_c.get("orders_rub", 0) + oz_c.get("orders_rub", 0)
        combined_margin = wb_c["margin"] + oz_c["margin"]

        return {
            "period": f"{start_date} — {end_date}",
            "brand_totals": {
                "ad_spend_total": combined_spend,
                "drr_pct": round(_safe_div(combined_spend, combined_rev) * 100, 1),
                "orders_count": combined_orders,
                "avg_check_order": round(_safe_div(combined_orders_rub, combined_orders), 1),
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
    """Organic vs Paid funnel for WB.

    IMPORTANT: Органика (card_opens) и реклама (impressions) — разные метрики.
    Сопоставимые пары:
    - Переходы в карточку: organic_card_opens vs paid_clicks
    - Корзина: organic_add_to_cart vs paid_to_cart
    - Заказы: organic_orders vs paid_orders
    Рекламные показы (impressions) — отдельная метрика, не складывается с органикой.
    """
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)
    resolved = _resolve_lk("wb", lk)

    # Fetch organic, paid, and status-split in parallel
    organic_results, paid_results = await asyncio.to_thread(
        get_wb_organic_vs_paid_funnel, current_start, prev_start, current_end, resolved
    )
    status_data = await asyncio.to_thread(
        get_wb_organic_by_status, current_start, prev_start, current_end, resolved
    )

    current = {}
    previous = {}

    # Parse organic funnel (content_analysis):
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

    # Merge organic + paid — COMPARABLE metrics only
    for period_key in ("current", "previous"):
        org = organic_by_period.get(period_key, {})
        paid = paid_by_period.get(period_key, {})

        org_card_opens = org.get("card_opens", 0)
        paid_clicks = paid.get("ad_clicks", 0)
        org_add_to_cart = org.get("add_to_cart", 0)
        paid_to_cart = paid.get("ad_to_cart", 0)
        org_orders = org.get("funnel_orders", 0)
        paid_orders = paid.get("ad_orders", 0)

        # Comparable totals (same metric type)
        total_card_transitions = org_card_opens + paid_clicks
        total_add_to_cart = org_add_to_cart + paid_to_cart
        total_orders = org_orders + paid_orders

        parsed = {
            # Comparable: transitions to card
            "organic_card_opens": org_card_opens,
            "paid_clicks": paid_clicks,
            "total_card_transitions": total_card_transitions,
            "organic_share_transitions_pct": round(
                _safe_div(org_card_opens, total_card_transitions) * 100, 1
            ),
            "paid_share_transitions_pct": round(
                _safe_div(paid_clicks, total_card_transitions) * 100, 1
            ),
            # Comparable: add to cart
            "organic_add_to_cart": org_add_to_cart,
            "paid_to_cart": paid_to_cart,
            "total_add_to_cart": total_add_to_cart,
            "organic_share_cart_pct": round(
                _safe_div(org_add_to_cart, total_add_to_cart) * 100, 1
            ),
            # Comparable: orders
            "organic_orders": org_orders,
            "paid_orders": paid_orders,
            "total_orders": total_orders,
            "organic_share_orders_pct": round(
                _safe_div(org_orders, total_orders) * 100, 1
            ),
            "paid_share_orders_pct": round(
                _safe_div(paid_orders, total_orders) * 100, 1
            ),
            # Organic-only: buyouts
            "organic_buyouts": org.get("buyouts", 0),
            # Organic funnel CRs
            "organic_card_to_cart_pct": org.get("card_to_cart_pct", 0),
            "organic_cart_to_order_pct": org.get("cart_to_order_pct", 0),
            "organic_order_to_buyout_pct": org.get("order_to_buyout_pct", 0),
            "organic_cr_pct": round(
                _safe_div(org_orders, org_card_opens) * 100, 2
            ),
            # Paid-only metrics (NOT comparable to organic)
            "paid_impressions": paid.get("ad_views", 0),
            "paid_ctr_pct": paid.get("ctr", 0),
            "paid_spend": paid.get("ad_spend", 0),
            "paid_cpc_rub": paid.get("cpc", 0),
            # Paid funnel CRs
            "paid_click_to_cart_pct": round(
                _safe_div(paid_to_cart, paid_clicks) * 100, 2
            ),
            "paid_cart_to_order_pct": round(
                _safe_div(paid_orders, paid_to_cart) * 100, 2
            ),
            "paid_cr_pct": round(
                _safe_div(paid_orders, paid_clicks) * 100, 2
            ),
            "paid_cpo_rub": round(
                _safe_div(paid.get("ad_spend", 0), paid_orders), 1
            ),
        }

        if period_key == "current":
            current = parsed
        else:
            previous = parsed

    changes = {}
    if current and previous:
        # Volume changes
        changes["organic_card_opens_change_pct"] = _pct_change(
            current.get("organic_card_opens", 0), previous.get("organic_card_opens", 0)
        )
        changes["paid_clicks_change_pct"] = _pct_change(
            current.get("paid_clicks", 0), previous.get("paid_clicks", 0)
        )
        changes["paid_impressions_change_pct"] = _pct_change(
            current.get("paid_impressions", 0), previous.get("paid_impressions", 0)
        )
        changes["organic_orders_change_pct"] = _pct_change(
            current.get("organic_orders", 0), previous.get("organic_orders", 0)
        )
        changes["paid_orders_change_pct"] = _pct_change(
            current.get("paid_orders", 0), previous.get("paid_orders", 0)
        )
        # Share changes
        changes["organic_share_transitions_change_pp"] = round(
            current.get("organic_share_transitions_pct", 0)
            - previous.get("organic_share_transitions_pct", 0),
            1,
        )
        changes["organic_share_orders_change_pp"] = round(
            current.get("organic_share_orders_pct", 0)
            - previous.get("organic_share_orders_pct", 0),
            1,
        )
        # CR changes (previous vs current)
        changes["organic_card_to_cart_change_pp"] = round(
            current.get("organic_card_to_cart_pct", 0)
            - previous.get("organic_card_to_cart_pct", 0),
            2,
        )
        changes["organic_cart_to_order_change_pp"] = round(
            current.get("organic_cart_to_order_pct", 0)
            - previous.get("organic_cart_to_order_pct", 0),
            2,
        )
        changes["organic_order_to_buyout_change_pp"] = round(
            current.get("organic_order_to_buyout_pct", 0)
            - previous.get("organic_order_to_buyout_pct", 0),
            2,
        )
        changes["organic_cr_change_pp"] = round(
            current.get("organic_cr_pct", 0)
            - previous.get("organic_cr_pct", 0),
            2,
        )
        changes["paid_cr_change_pp"] = round(
            current.get("paid_cr_pct", 0)
            - previous.get("paid_cr_pct", 0),
            2,
        )
        changes["paid_ctr_change_pp"] = round(
            current.get("paid_ctr_pct", 0)
            - previous.get("paid_ctr_pct", 0),
            2,
        )

    return {
        "channel": "WB",
        "period": f"{start_date} — {end_date}",
        "current": current,
        "previous": previous,
        "changes": changes,
        "by_status": status_data,
        "note": (
            "Переходы в карточку: органические (card_opens) + платные (clicks) — сопоставимые метрики. "
            "Рекламные показы (impressions) — отдельная метрика, не складывается с органикой."
        ),
    }


async def _handle_external_ad_breakdown(
    channel: str, start_date: str, end_date: str, lk: str = None,
) -> dict:
    """External ad breakdown: bloggers, VK, creators, etc."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    async def _fetch_channel(ch: str) -> dict:
        resolved = _resolve_lk(ch, lk)
        if ch == "wb":
            rows = await asyncio.to_thread(
                get_wb_external_ad_breakdown, current_start, prev_start, current_end, resolved
            )
        else:
            rows = await asyncio.to_thread(
                get_ozon_external_ad_breakdown, current_start, prev_start, current_end, resolved
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
        filtered_count = 0
        for campaign, curr in sorted(
            current_campaigns.items(), key=lambda x: x[1]["spend"], reverse=True
        ):
            if curr["spend"] < MIN_AD_SPEND_RUB:
                filtered_count += 1
                continue
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
            "filtered_low_spend": filtered_count,
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
        resolved = _resolve_lk(ch, lk)
        if ch == "wb":
            rows = await asyncio.to_thread(
                get_wb_model_ad_roi, current_start, prev_start, current_end, resolved
            )
        else:
            rows = await asyncio.to_thread(
                get_ozon_model_ad_roi, current_start, prev_start, current_end, resolved
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
        filtered_count = 0
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
            if curr["ad_spend"] < MIN_AD_SPEND_RUB:
                filtered_count += 1
                continue
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
            "filtered_low_spend": filtered_count,
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
    """Pearson correlation between ad spend and orders/margin/cart across models."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)

    if channel == "wb":
        rows = await asyncio.to_thread(
            get_wb_model_ad_roi, current_start, prev_start, current_end
        )
        # Also fetch cart data (atbs) per model from wb_adv
        traffic_rows = await asyncio.to_thread(
            get_wb_traffic_by_model, current_start, prev_start, current_end
        )
    else:
        rows = await asyncio.to_thread(
            get_ozon_model_ad_roi, current_start, prev_start, current_end
        )
        traffic_rows = []

    # Cart data per model (WB only, from get_wb_traffic_by_model)
    # SQL: period, model, ad_views, ad_clicks, ad_spend, ad_to_cart, ad_orders, ctr, cpc
    cart_by_model: dict = {}
    for row in traffic_rows:
        if row[0] != "current":
            continue
        model = _map_to_osnova(row[1])
        if model == "Other":
            continue
        cart_by_model[model] = cart_by_model.get(model, 0) + to_float(row[5])  # ad_to_cart

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
            model_data[model] = {"ad_spend": 0, "ad_orders": 0, "revenue": 0, "margin": 0, "ad_to_cart": 0}

        # SQL: period, model, ad_spend, ad_orders, revenue, margin, drr_pct, romi
        model_data[model]["ad_spend"] += to_float(row[2])
        model_data[model]["ad_orders"] += to_float(row[3])
        model_data[model]["revenue"] += to_float(row[4])
        model_data[model]["margin"] += to_float(row[5])

    # Merge cart data into model_data
    for model, cart_count in cart_by_model.items():
        if model in model_data:
            model_data[model]["ad_to_cart"] = cart_count

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
    carts = []
    model_names = []
    for model_name, data in model_data.items():
        model_names.append(model_name)
        spends.append(data["ad_spend"])
        orders_list.append(data["ad_orders"])
        margins.append(data["margin"])
        carts.append(data["ad_to_cart"])

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
    corr_spend_cart = _pearson(spends, carts)

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

    correlations = {
        "spend_vs_orders": {
            "pearson_r": corr_spend_orders,
            "interpretation": _interpret(corr_spend_orders),
        },
        "spend_vs_margin": {
            "pearson_r": corr_spend_margin,
            "interpretation": _interpret(corr_spend_margin),
        },
    }
    # Cart correlation only for WB (OZON doesn't have atbs in ad data)
    if channel == "wb":
        correlations["spend_vs_cart"] = {
            "pearson_r": corr_spend_cart,
            "interpretation": _interpret(corr_spend_cart),
        }

    return {
        "channel": channel.upper(),
        "period": f"{start_date} — {end_date}",
        "models_count": len(model_data),
        "correlations": correlations,
        "models_data": [
            {
                "model": model_names[i],
                "ad_spend": spends[i],
                "ad_orders": orders_list[i],
                "ad_to_cart": carts[i],
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


async def _handle_model_anomalies(
    start_date: str, end_date: str, threshold_pct: float = 30, lk: str = None,
) -> dict:
    """Model-level anomaly detection: find models with significant metric changes."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)
    resolved = _resolve_lk("wb", lk)

    rows = await asyncio.to_thread(
        get_wb_model_metrics_comparison, current_start, prev_start, current_end, resolved
    )

    # Parse into model data by period
    # SQL: period, model, organic_card_opens, organic_add_to_cart, organic_orders,
    #      organic_buyouts, ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend
    model_current = {}
    model_previous = {}
    for row in rows:
        period = row[0]
        model = _map_to_osnova(row[1])
        if model == "Other":
            continue

        data = {
            "organic_card_opens": to_float(row[2]),
            "organic_add_to_cart": to_float(row[3]),
            "organic_orders": to_float(row[4]),
            "organic_buyouts": to_float(row[5]),
            "ad_views": to_float(row[6]),
            "ad_clicks": to_float(row[7]),
            "ad_to_cart": to_float(row[8]),
            "ad_orders": to_float(row[9]),
            "ad_spend": to_float(row[10]),
        }
        # Compute derived CRs
        data["organic_card_to_cart_pct"] = round(
            _safe_div(data["organic_add_to_cart"], data["organic_card_opens"]) * 100, 2
        )
        data["organic_cart_to_order_pct"] = round(
            _safe_div(data["organic_orders"], data["organic_add_to_cart"]) * 100, 2
        )
        data["ad_ctr_pct"] = round(
            _safe_div(data["ad_clicks"], data["ad_views"]) * 100, 2
        )
        data["ad_click_to_cart_pct"] = round(
            _safe_div(data["ad_to_cart"], data["ad_clicks"]) * 100, 2
        )

        target = model_current if period == "current" else model_previous
        if model in target:
            for k, v in data.items():
                target[model][k] = target[model].get(k, 0) + v
        else:
            target[model] = data

    # Recalculate CR after aggregation for models that were merged
    for store in (model_current, model_previous):
        for data in store.values():
            data["organic_card_to_cart_pct"] = round(
                _safe_div(data["organic_add_to_cart"], data["organic_card_opens"]) * 100, 2
            )
            data["organic_cart_to_order_pct"] = round(
                _safe_div(data["organic_orders"], data["organic_add_to_cart"]) * 100, 2
            )
            data["ad_ctr_pct"] = round(
                _safe_div(data["ad_clicks"], data["ad_views"]) * 100, 2
            )
            data["ad_click_to_cart_pct"] = round(
                _safe_div(data["ad_to_cart"], data["ad_clicks"]) * 100, 2
            )

    # Find anomalies
    anomalies = []
    threshold = threshold_pct / 100.0

    # Metrics to check: (key, label, is_rate)
    metrics_to_check = [
        ("organic_card_opens", "Органика: переходы в карточку", False),
        ("organic_add_to_cart", "Органика: корзина", False),
        ("organic_orders", "Органика: заказы", False),
        ("organic_card_to_cart_pct", "Органика: CR карточка→корзина", True),
        ("organic_cart_to_order_pct", "Органика: CR корзина→заказ", True),
        ("ad_views", "Реклама: показы", False),
        ("ad_clicks", "Реклама: клики", False),
        ("ad_ctr_pct", "Реклама: CTR", True),
        ("ad_to_cart", "Реклама: корзина", False),
        ("ad_orders", "Реклама: заказы", False),
        ("ad_spend", "Реклама: расход", False),
        ("ad_click_to_cart_pct", "Реклама: CR клик→корзина", True),
    ]

    all_models = set(model_current.keys()) & set(model_previous.keys())
    for model in sorted(all_models):
        curr = model_current[model]
        prev = model_previous[model]
        model_anomalies = []

        for key, label, is_rate in metrics_to_check:
            c_val = curr.get(key, 0)
            p_val = prev.get(key, 0)

            if is_rate:
                # For rates: absolute difference in pp
                diff_pp = c_val - p_val
                if abs(p_val) > 1:  # Only flag if previous had meaningful value
                    rel_change = diff_pp / p_val
                    if abs(rel_change) >= threshold:
                        model_anomalies.append({
                            "metric": label,
                            "current": c_val,
                            "previous": p_val,
                            "change_pp": round(diff_pp, 2),
                            "change_pct": round(rel_change * 100, 1),
                        })
            else:
                # For volumes: percent change
                if p_val > 0:
                    change = (c_val - p_val) / p_val
                    if abs(change) >= threshold:
                        model_anomalies.append({
                            "metric": label,
                            "current": c_val,
                            "previous": p_val,
                            "change_pct": round(change * 100, 1),
                        })

        if model_anomalies:
            # Generate hypotheses based on anomaly patterns
            hypotheses = _generate_anomaly_hypotheses(curr, prev, model_anomalies)
            anomalies.append({
                "model": model,
                "anomalies_count": len(model_anomalies),
                "anomalies": model_anomalies,
                "hypotheses": hypotheses,
            })

    # Sort by number of anomalies descending
    anomalies.sort(key=lambda x: x["anomalies_count"], reverse=True)

    return {
        "channel": "WB",
        "period": f"{start_date} — {end_date}",
        "threshold_pct": threshold_pct,
        "models_analyzed": len(all_models),
        "models_with_anomalies": len(anomalies),
        "anomalies": anomalies,
    }


def _generate_anomaly_hypotheses(curr: dict, prev: dict, anomalies: list) -> list:
    """Rule-based hypothesis generation from anomaly patterns."""
    hypotheses = []
    anomaly_keys = {a["metric"] for a in anomalies}
    changes = {}
    for a in anomalies:
        changes[a["metric"]] = a["change_pct"]

    # Pattern: CTR down + orders down → competitors / season / outdated listing
    ctr_down = changes.get("Реклама: CTR", 0) < -20
    orders_down = changes.get("Реклама: заказы", 0) < -20 or changes.get("Органика: заказы", 0) < -20
    if ctr_down and orders_down:
        hypotheses.append(
            "CTR↓ + заказы↓: возможные причины — усиление конкурентов, "
            "сезонное снижение спроса, устаревшая карточка товара. "
            "Рекомендация: обновить фото/описание, проверить позиции конкурентов."
        )

    # Pattern: CTR up + orders stable/down → irrelevant traffic
    ctr_up = changes.get("Реклама: CTR", 0) > 20
    orders_stable_or_down = changes.get("Реклама: заказы", 0) <= 5
    if ctr_up and orders_stable_or_down:
        hypotheses.append(
            "CTR↑ + заказы стабильны/↓: вероятно, привлекается нерелевантный трафик. "
            "Рекомендация: проверить ключевые слова, минус-слова, релевантность аудитории."
        )

    # Pattern: Organic down + paid up → losing search positions
    organic_down = changes.get("Органика: переходы в карточку", 0) < -20
    paid_up = changes.get("Реклама: клики", 0) > 20 or changes.get("Реклама: расход", 0) > 20
    if organic_down and paid_up:
        hypotheses.append(
            "Органика↓ + платное↑: модель теряет позиции в органическом поиске, "
            "компенсируется рекламой. Рекомендация: проверить SEO карточки, "
            "рейтинг, отзывы, позиции в выдаче."
        )

    # Pattern: Cart CR down → price / competitor / sizing issue
    cart_cr_down = changes.get("Органика: CR карточка→корзина", 0) < -20
    if cart_cr_down:
        hypotheses.append(
            "CR карточка→корзина↓: возможные причины — неконкурентная цена, "
            "изменение СПП, отсутствие популярных размеров, негативные отзывы. "
            "Рекомендация: проверить цену vs конкуренты, наличие размеров, новые отзывы."
        )

    # Pattern: Organic orders up significantly
    organic_orders_up = changes.get("Органика: заказы", 0) > 50
    if organic_orders_up:
        hypotheses.append(
            "Органика заказы↑↑: рост органических заказов — возможно влияние внешней рекламы "
            "(блогеры/VK), сезонный всплеск, или улучшение позиций в поиске."
        )

    # Pattern: Ad spend up but orders down → efficiency drop
    spend_up = changes.get("Реклама: расход", 0) > 20
    ad_orders_down = changes.get("Реклама: заказы", 0) < -10
    if spend_up and ad_orders_down:
        hypotheses.append(
            "Расход↑ + заказы через рекламу↓: падение эффективности рекламы. "
            "Рекомендация: пересмотреть ставки, отключить неэффективные кампании, "
            "проверить релевантность ключевых слов."
        )

    if not hypotheses:
        hypotheses.append(
            "Значимые отклонения зафиксированы, но паттерн не соответствует типовым сценариям. "
            "Рекомендация: проанализировать детально вручную."
        )

    return hypotheses


async def _handle_ozon_organic_estimate(
    start_date: str, end_date: str, lk: str = None,
) -> dict:
    """Estimated OZON organic: total orders - ad orders per model."""
    current_start, prev_start, current_end = _calc_comparison_dates(start_date, end_date)
    resolved = _resolve_lk("ozon", lk)

    rows = await asyncio.to_thread(
        get_ozon_organic_estimated, current_start, prev_start, current_end, resolved
    )

    # SQL: period, model, total_orders, ad_orders, organic_orders, total_revenue, ad_spend
    current_models = []
    previous_models = []
    totals = {"current": {"total": 0, "ad": 0, "organic": 0, "revenue": 0, "ad_spend": 0},
              "previous": {"total": 0, "ad": 0, "organic": 0, "revenue": 0, "ad_spend": 0}}
    warnings = []

    for row in rows:
        period = row[0]
        model = _map_to_osnova(row[1])
        if model == "Other":
            continue
        total_orders = to_float(row[2])
        ad_orders = to_float(row[3])
        organic_orders = to_float(row[4])
        total_revenue = to_float(row[5])
        ad_spend = to_float(row[6])

        if ad_orders > total_orders and total_orders > 0:
            warnings.append(
                f"{model}: рекламных заказов ({int(ad_orders)}) > общих ({int(total_orders)}), "
                "органика capped на 0"
            )

        entry = {
            "model": model,
            "total_orders": total_orders,
            "ad_orders": ad_orders,
            "organic_orders": organic_orders,
            "organic_share_pct": round(_safe_div(organic_orders, total_orders) * 100, 1),
            "total_revenue": total_revenue,
            "ad_spend": ad_spend,
        }

        target = current_models if period == "current" else previous_models
        target.append(entry)

        t = totals[period]
        t["total"] += total_orders
        t["ad"] += ad_orders
        t["organic"] += organic_orders
        t["revenue"] += total_revenue
        t["ad_spend"] += ad_spend

    # Compute total organic share
    for period_key in ("current", "previous"):
        t = totals[period_key]
        t["organic_share_pct"] = round(_safe_div(t["organic"], t["total"]) * 100, 1)

    result = {
        "channel": "OZON",
        "period": f"{start_date} — {end_date}",
        "current": {
            "totals": totals["current"],
            "models": sorted(current_models, key=lambda x: x["total_orders"], reverse=True),
        },
        "previous": {
            "totals": totals["previous"],
            "models": sorted(previous_models, key=lambda x: x["total_orders"], reverse=True),
        },
        "note": (
            "Расчётная органика: organic_orders = total_orders − ad_orders. "
            "Только уровень заказов — показы/переходы недоступны (OZON search_stat = 0)."
        ),
    }
    if warnings:
        result["warnings"] = warnings

    return result


async def _handle_ad_profitability_alerts(
    start_date: str, end_date: str, romi_threshold: float = 100,
) -> dict:
    """Find models/articles with unprofitable advertising."""
    from shared.data_layer import get_wb_model_ad_roi, get_wb_article_economics
    from datetime import datetime, timedelta

    e = datetime.strptime(end_date, '%Y-%m-%d')
    end_exclusive = (e + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get model-level ad ROI
    model_rows = await asyncio.to_thread(
        get_wb_model_ad_roi, start_date, end_exclusive
    )

    # Get article-level economics
    article_rows = await asyncio.to_thread(
        get_wb_article_economics, start_date, end_exclusive
    )

    alerts = []

    # Check models
    if model_rows:
        for r in model_rows:
            model = r[0] if r[0] else "unknown"
            ad_spend = float(r[1] or 0)
            ad_orders = int(r[2] or 0)
            revenue = float(r[3] or 0)
            margin = float(r[4] or 0)
            drr = float(r[5] or 0)
            romi = float(r[6] or 0)

            if ad_spend > 0 and romi < romi_threshold:
                recommendation = "СТОП" if romi < 50 else "Сокращение"
                alerts.append({
                    "уровень": "модель",
                    "объект": model,
                    "расход_₽": round(ad_spend, 0),
                    "маржа_₽": round(margin, 0),
                    "ROMI": round(romi, 1),
                    "ДРР_%": round(drr, 1),
                    "заказы_с_рекламы": ad_orders,
                    "рекомендация": recommendation,
                })

    # Check articles for CAC > profit_per_sale
    if article_rows:
        for r in article_rows:
            artikul = r[0] if r[0] else "unknown"
            margin = float(r[2] or 0)
            orders = int(r[3] or 0)
            ad_spend = float(r[7] or 0)
            cac = float(r[12] or 0) if r[12] else 0
            profit_per_sale = float(r[10] or 0) if r[10] else 0
            romi = float(r[13] or 0) if r[13] else 0

            if ad_spend > 0 and cac > 0 and profit_per_sale > 0 and cac > profit_per_sale:
                alerts.append({
                    "уровень": "артикул",
                    "объект": artikul,
                    "расход_₽": round(ad_spend, 0),
                    "маржа_₽": round(margin, 0),
                    "CAC": round(cac, 1),
                    "прибыль_на_продажу": round(profit_per_sale, 1),
                    "ROMI": round(romi, 1),
                    "рекомендация": "CAC > прибыль: снизить ставки",
                })

    # Sort by absolute ad spend desc
    alerts.sort(key=lambda x: x.get("расход_₽", 0), reverse=True)

    return {
        "период": f"{start_date} — {end_date}",
        "порог_ROMI": romi_threshold,
        "всего_алертов": len(alerts),
        "алерты": alerts[:20],
    }


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
    "get_model_anomalies": _handle_model_anomalies,
    "get_ozon_organic_estimate": _handle_ozon_organic_estimate,
    "get_channel_finance": _handle_mkt_channel_finance,
    "get_margin_levers": _handle_mkt_margin_levers,
    "get_model_breakdown": _handle_mkt_model_breakdown,
    "get_ad_profitability_alerts": _handle_ad_profitability_alerts,
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
