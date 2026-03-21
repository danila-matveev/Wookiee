"""
SEO Tools — инструменты для SEO-анализа WB.

Обёртки над shared/data_layer.py в формате OpenAI function calling.
Все SQL-запросы остаются в data_layer.py — здесь только парсинг, агрегация
и форматирование результатов.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ── Helper ────────────────────────────────────────────────────────

def _safe_pct(curr, prev):
    """Calculate percentage change: (curr - prev) / prev * 100."""
    if prev and prev > 0:
        return round((curr - prev) / prev * 100, 1)
    return 0


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

SEO_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_seo_overview",
            "description": (
                "Обзор SEO-метрик модели: card_opens, orders, топ-артикулы, "
                "доля органики WoW. Используй ПЕРВЫМ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Название модели (LOWER)",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Начало периода YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Конец периода YYYY-MM-DD (включительно)",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Количество топ-артикулов (по умолчанию 3)",
                    },
                },
                "required": ["model", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seo_card_dynamics",
            "description": (
                "Динамика карточек WoW: card_opens, add_to_cart, orders, CR. "
                "Сравнение с предыдущей неделей."
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
                    "artikul_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список артикулов для фильтрации (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seo_keyword_positions",
            "description": (
                "Позиции по ключевым словам WoW из kz_off: medianPosition, "
                "frequency, visibility."
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
                    "artikul_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список артикулов для фильтрации (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seo_organic_vs_paid",
            "description": (
                "Органика vs реклама per article: доля органического трафика, заказов."
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
                    "artikul_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список артикулов для фильтрации (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seo_financial_impact",
            "description": (
                "Финансовые KPI per article: revenue, margin, DRR + связь с SEO."
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
                    "artikul_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список артикулов для фильтрации (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seo_article_details",
            "description": (
                "Детали по конкретному артикулу: динамика + ключевики + финансы."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artikul": {
                        "type": "string",
                        "description": "Артикул товара",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Начало периода YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Конец периода YYYY-MM-DD (включительно)",
                    },
                },
                "required": ["artikul", "start_date", "end_date"],
            },
        },
    },
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

async def _handle_seo_overview(
    model: str, start_date: str, end_date: str, top_n: int = 3,
) -> dict:
    """SEO overview for a model: top articles, card dynamics, organic share."""
    from shared.data_layer import (
        get_wb_top_articles_by_orders,
        get_wb_card_dynamics_wow,
        get_wb_organic_vs_paid_by_article,
    )

    # Calculate previous period
    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    # Get top articles by orders for the model
    top = await asyncio.to_thread(
        get_wb_top_articles_by_orders, start_date, end_date, model, top_n,
    )

    # Extract artikul list from top articles for filtering
    top_artikuls = [row[2] for row in top] if top else []

    # Get card dynamics for the model's articles
    dynamics = await asyncio.to_thread(
        get_wb_card_dynamics_wow, start_date, prev_start, end_date, top_artikuls or None,
    )

    # Get organic vs paid for the model's articles
    organic = await asyncio.to_thread(
        get_wb_organic_vs_paid_by_article, start_date, end_date, top_artikuls or None,
    )

    # Build top articles summary
    top_articles = []
    for row in top:
        # (model, rank, vendorcode, orders, card_opens, add_to_cart, buyouts)
        top_articles.append({
            "model": row[0],
            "rank": row[1],
            "artikul": row[2],
            "orders": row[3],
            "card_opens": row[4],
            "add_to_cart": row[5],
            "buyouts": row[6],
        })

    # Build dynamics summary (aggregate current period)
    model_totals = {"current": {}, "prev": {}}
    for row in dynamics:
        # (period, artikul, card_opens, add_to_cart, orders, buyouts)
        period = row[0]
        if period in model_totals:
            for key, idx in [("card_opens", 2), ("add_to_cart", 3), ("orders", 4), ("buyouts", 5)]:
                model_totals[period][key] = model_totals[period].get(key, 0) + (row[idx] or 0)

    # Calculate organic share from organic vs paid data
    total_organic_opens = 0
    total_ad_clicks = 0
    total_organic_orders = 0
    total_ad_orders = 0
    for row in organic:
        # (artikul, organic_opens, organic_orders, ad_views, ad_clicks, ad_orders, ad_spend)
        total_organic_opens += row[1] or 0
        total_organic_orders += row[2] or 0
        total_ad_clicks += row[4] or 0
        total_ad_orders += row[5] or 0

    total_transitions = total_organic_opens + total_ad_clicks
    total_orders = total_organic_orders + total_ad_orders
    organic_share_transitions = round(total_organic_opens / total_transitions * 100, 1) if total_transitions > 0 else 0
    organic_share_orders = round(total_organic_orders / total_orders * 100, 1) if total_orders > 0 else 0

    # Interpretations
    interpretations = []
    if organic_share_transitions > 70:
        interpretations.append("Высокая доля органики — хороший SEO")
    elif organic_share_transitions < 30:
        interpretations.append("Зависимость от рекламы — нужна SEO-оптимизация")

    curr = model_totals.get("current", {})
    prev = model_totals.get("prev", {})
    card_opens_delta = _safe_pct(curr.get("card_opens", 0), prev.get("card_opens", 0))
    orders_delta = _safe_pct(curr.get("orders", 0), prev.get("orders", 0))

    if card_opens_delta < -10:
        interpretations.append(f"Падение card_opens на {card_opens_delta}% — проверить позиции")
    if orders_delta > 10:
        interpretations.append(f"Рост заказов на {orders_delta}% — позитивная динамика")

    return {
        "model": model,
        "period": f"{start_date} — {end_date}",
        "top_articles": top_articles,
        "model_totals": {
            "current": curr,
            "previous": prev,
            "changes": {
                "card_opens_delta_pct": card_opens_delta,
                "orders_delta_pct": orders_delta,
            },
        },
        "organic_share": {
            "organic_opens": total_organic_opens,
            "paid_clicks": total_ad_clicks,
            "organic_share_transitions_pct": organic_share_transitions,
            "organic_orders": total_organic_orders,
            "paid_orders": total_ad_orders,
            "organic_share_orders_pct": organic_share_orders,
        },
        "interpretations": interpretations,
    }


async def _handle_seo_card_dynamics(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Card dynamics WoW: card_opens, add_to_cart, orders, CRs, deltas."""
    from shared.data_layer import get_wb_card_dynamics_wow

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    rows = await asyncio.to_thread(
        get_wb_card_dynamics_wow, start_date, prev_start, end_date, artikul_filter,
    )

    # Process into current/prev dicts, calculate CRs and deltas
    articles: Dict[str, dict] = {}
    for row in rows:
        # (period, artikul, card_opens, add_to_cart, orders, buyouts)
        period = row[0]
        artikul = row[1]
        card_opens = row[2] or 0
        add_to_cart = row[3] or 0
        orders = row[4] or 0
        buyouts = row[5] or 0

        if artikul not in articles:
            articles[artikul] = {"current": {}, "prev": {}}
        articles[artikul][period] = {
            "card_opens": card_opens,
            "add_to_cart": add_to_cart,
            "orders": orders,
            "buyouts": buyouts,
            "cr_open_to_cart": round(add_to_cart / card_opens * 100, 1) if card_opens > 0 else 0,
            "cr_cart_to_order": round(orders / add_to_cart * 100, 1) if add_to_cart > 0 else 0,
        }

    # Calculate deltas
    results = []
    for artikul, data in articles.items():
        curr = data.get("current", {})
        prev = data.get("prev", {})
        results.append({
            "artikul": artikul,
            "current": curr,
            "previous": prev,
            "changes": {
                "card_opens_delta_pct": _safe_pct(curr.get("card_opens", 0), prev.get("card_opens", 0)),
                "orders_delta_pct": _safe_pct(curr.get("orders", 0), prev.get("orders", 0)),
                "cr_open_to_cart_delta_pp": round(
                    curr.get("cr_open_to_cart", 0) - prev.get("cr_open_to_cart", 0), 1,
                ),
                "cr_cart_to_order_delta_pp": round(
                    curr.get("cr_cart_to_order", 0) - prev.get("cr_cart_to_order", 0), 1,
                ),
            },
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": sorted(results, key=lambda x: x["current"].get("orders", 0), reverse=True),
    }


async def _handle_seo_keyword_positions(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Keyword positions WoW from kz_off: medianPosition, frequency, visibility."""
    from shared.data_layer import get_wb_seo_keyword_positions

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    rows = await asyncio.to_thread(
        get_wb_seo_keyword_positions, start_date, prev_start, end_date, artikul_filter,
    )

    # Group by artikul -> keyword -> periods
    artikul_keywords: Dict[str, Dict[str, dict]] = {}
    for row in rows:
        # (period, artikul, keyword, median_pos, freq, opens, add_to_cart, orders, visibility)
        period = row[0]
        artikul = row[1]
        keyword = row[2]
        median_pos = round(float(row[3]), 1) if row[3] else None
        freq = int(row[4]) if row[4] else 0
        opens = int(row[5]) if row[5] else 0
        add_to_cart = int(row[6]) if row[6] else 0
        orders = int(row[7]) if row[7] else 0
        visibility = round(float(row[8]), 2) if row[8] else 0

        if artikul not in artikul_keywords:
            artikul_keywords[artikul] = {}
        if keyword not in artikul_keywords[artikul]:
            artikul_keywords[artikul][keyword] = {"current": {}, "prev": {}}

        artikul_keywords[artikul][keyword][period] = {
            "median_position": median_pos,
            "frequency": freq,
            "opens": opens,
            "add_to_cart": add_to_cart,
            "orders": orders,
            "visibility": visibility,
        }

    # Build structured result with deltas and interpretations
    result_articles = []
    for artikul, keywords in artikul_keywords.items():
        kw_results = []
        for keyword, periods in keywords.items():
            curr = periods.get("current", {})
            prev = periods.get("prev", {})
            curr_pos = curr.get("median_position")
            prev_pos = prev.get("median_position")

            # Position delta: negative = improved (lower position number is better)
            pos_delta = None
            interpretation = None
            if curr_pos is not None and prev_pos is not None:
                pos_delta = round(curr_pos - prev_pos, 1)
                if pos_delta < 0:
                    interpretation = "position_improved"
                elif pos_delta > 0:
                    interpretation = "position_declined"
                else:
                    interpretation = "position_stable"

            kw_results.append({
                "keyword": keyword,
                "current": curr,
                "previous": prev,
                "position_delta": pos_delta,
                "interpretation": interpretation,
            })

        # Sort keywords by frequency (current) descending
        kw_results.sort(key=lambda x: x["current"].get("frequency", 0), reverse=True)
        result_articles.append({
            "artikul": artikul,
            "keywords": kw_results,
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": result_articles,
    }


async def _handle_seo_organic_vs_paid(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Organic vs Paid per article: organic share of traffic and orders."""
    from shared.data_layer import get_wb_organic_vs_paid_by_article

    rows = await asyncio.to_thread(
        get_wb_organic_vs_paid_by_article, start_date, end_date, artikul_filter,
    )

    articles = []
    for row in rows:
        # (artikul, organic_opens, organic_orders, ad_views, ad_clicks, ad_orders, ad_spend)
        artikul = row[0]
        organic_opens = row[1] or 0
        organic_orders = row[2] or 0
        ad_views = row[3] or 0
        ad_clicks = row[4] or 0
        ad_orders = row[5] or 0
        ad_spend = float(row[6]) if row[6] else 0

        total_transitions = organic_opens + ad_clicks
        total_orders = organic_orders + ad_orders
        organic_share_transitions = round(organic_opens / total_transitions * 100, 1) if total_transitions > 0 else 0
        organic_share_orders = round(organic_orders / total_orders * 100, 1) if total_orders > 0 else 0
        paid_share_transitions = round(ad_clicks / total_transitions * 100, 1) if total_transitions > 0 else 0
        paid_share_orders = round(ad_orders / total_orders * 100, 1) if total_orders > 0 else 0

        # Interpretation
        if organic_share_transitions > 70:
            interpretation = "Высокая доля органики"
        elif organic_share_transitions < 30:
            interpretation = "Зависимость от рекламы"
        else:
            interpretation = "Сбалансированный трафик"

        articles.append({
            "artikul": artikul,
            "organic_opens": organic_opens,
            "organic_orders": organic_orders,
            "ad_views": ad_views,
            "ad_clicks": ad_clicks,
            "ad_orders": ad_orders,
            "ad_spend": ad_spend,
            "total_transitions": total_transitions,
            "total_orders": total_orders,
            "organic_share_transitions_pct": organic_share_transitions,
            "paid_share_transitions_pct": paid_share_transitions,
            "organic_share_orders_pct": organic_share_orders,
            "paid_share_orders_pct": paid_share_orders,
            "interpretation": interpretation,
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": articles,
    }


async def _handle_seo_financial_impact(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Financial KPI per article: revenue, margin, DRR + link to SEO."""
    from shared.data_layer import get_wb_article_financial_kpi

    rows = await asyncio.to_thread(
        get_wb_article_financial_kpi, start_date, end_date, artikul_filter,
    )

    articles = []
    for row in rows:
        # (artikul, revenue_spp, margin, orders_count, avg_check, drr)
        artikul = row[0]
        revenue_spp = float(row[1]) if row[1] else 0
        margin = float(row[2]) if row[2] else 0
        orders_count = int(row[3]) if row[3] else 0
        avg_check = round(float(row[4]), 1) if row[4] else 0
        drr = round(float(row[5]), 1) if row[5] else 0

        margin_pct = round(margin / revenue_spp * 100, 1) if revenue_spp > 0 else 0

        # Interpretation linking DRR to SEO
        interpretations = []
        if drr > 15:
            interpretations.append("Высокий ДРР — улучшение SEO снизит зависимость от рекламы")
        elif drr < 5:
            interpretations.append("Низкий ДРР — хорошая органическая видимость")
        if margin_pct < 10:
            interpretations.append("Низкая маржа — проверить ценообразование и расходы")

        articles.append({
            "artikul": artikul,
            "revenue_spp": revenue_spp,
            "margin": margin,
            "margin_pct": margin_pct,
            "orders_count": orders_count,
            "avg_check": avg_check,
            "drr_pct": drr,
            "interpretations": interpretations,
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": articles,
    }


async def _handle_seo_article_details(
    artikul: str, start_date: str, end_date: str,
) -> dict:
    """Full details for a single article: dynamics + keywords + organic vs paid + financial."""
    artikul_list = [artikul]

    # Fetch all data sources in parallel
    dynamics_task = _handle_seo_card_dynamics(start_date, end_date, artikul_list)
    keywords_task = _handle_seo_keyword_positions(start_date, end_date, artikul_list)
    organic_task = _handle_seo_organic_vs_paid(start_date, end_date, artikul_list)
    financial_task = _handle_seo_financial_impact(start_date, end_date, artikul_list)

    dynamics, keywords, organic, financial = await asyncio.gather(
        dynamics_task, keywords_task, organic_task, financial_task,
    )

    # Extract article-specific data from each result
    dynamics_article = dynamics.get("articles", [{}])[0] if dynamics.get("articles") else {}
    keywords_article = keywords.get("articles", [{}])[0] if keywords.get("articles") else {}
    organic_article = organic.get("articles", [{}])[0] if organic.get("articles") else {}
    financial_article = financial.get("articles", [{}])[0] if financial.get("articles") else {}

    return {
        "artikul": artikul,
        "period": f"{start_date} — {end_date}",
        "card_dynamics": dynamics_article,
        "keyword_positions": keywords_article,
        "organic_vs_paid": organic_article,
        "financial_kpi": financial_article,
    }


# =============================================================================
# HANDLER REGISTRY
# =============================================================================

SEO_TOOL_HANDLERS: Dict[str, Any] = {
    "get_seo_overview": _handle_seo_overview,
    "get_seo_card_dynamics": _handle_seo_card_dynamics,
    "get_seo_keyword_positions": _handle_seo_keyword_positions,
    "get_seo_organic_vs_paid": _handle_seo_organic_vs_paid,
    "get_seo_financial_impact": _handle_seo_financial_impact,
    "get_seo_article_details": _handle_seo_article_details,
}


# =============================================================================
# EXECUTOR
# =============================================================================

async def execute_seo_tool(tool_name: str, arguments: dict) -> str:
    """
    Execute a SEO tool by name with given arguments.

    Returns JSON string with result or error.
    """
    handler = SEO_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown SEO tool: {tool_name}"}, ensure_ascii=False)

    try:
        logger.info(f"SEO tool call: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")
        result = await handler(**arguments)
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"SEO tool result: {tool_name} → {len(result_json)} chars")
        return result_json
    except TypeError as e:
        logger.error(f"SEO tool {tool_name} argument error: {e}")
        return json.dumps(
            {"error": f"Invalid arguments for {tool_name}: {e}"},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"SEO tool {tool_name} execution error: {e}", exc_info=True)
        return json.dumps(
            {"error": f"Tool execution failed: {e}"},
            ensure_ascii=False,
        )
