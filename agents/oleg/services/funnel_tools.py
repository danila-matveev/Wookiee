"""
Funnel Tools — инструменты оцифровки маркетинговой воронки WB (Макар).

Обёртки над shared/data_layer.py в формате OpenAI function calling.
Все SQL-запросы остаются в data_layer.py — здесь парсинг, агрегация
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


def _safe_float(val, decimals=1):
    """Safely convert to float with rounding."""
    return round(float(val), decimals) if val else 0


def _safe_int(val):
    """Safely convert to int."""
    return int(val) if val else 0


# =============================================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# =============================================================================

FUNNEL_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_funnel_overview",
            "description": (
                "Обзор модели: полная воронка (переходы→выкупы), конверсии CRO/CRP, "
                "доля органики, маржа, ДРР WoW. Используй ПЕРВЫМ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Название модели (LOWER), например 'wendy'",
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
                        "description": "Количество топ-артикулов (по умолчанию 5)",
                    },
                },
                "required": ["model", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_funnel",
            "description": (
                "Воронка по артикулам WoW: переходы, корзина, заказы, выкупы, "
                "все CR (CRO, CRP), сравнение с предыдущим периодом."
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
                        "description": "Список артикулов для фильтрации",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_economics",
            "description": (
                "Экономика артикулов: выручка, маржа, ДРР, ROMI, CPS, "
                "прибыль на посетителя, CAC."
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
                        "description": "Список артикулов для фильтрации",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_ad_attribution",
            "description": (
                "Органика vs реклама per article: доля органического трафика "
                "и заказов, динамика, влияние на ДРР."
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
                        "description": "Список артикулов для фильтрации",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_search_keywords",
            "description": (
                "Ключевые слова из WB API: по каким запросам находят артикулы, "
                "частотность, переходы, заказы per keyword."
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
                        "description": "Список артикулов для получения nmId (опционально)",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_keyword_positions",
            "description": (
                "Позиции по ключевым словам WoW из kz_off: medianPosition, "
                "frequency, visibility. Дополнение к get_search_keywords."
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
                        "description": "Список артикулов для фильтрации",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_unit_economics",
            "description": (
                "Водопад затрат на единицу товара per article: "
                "выручка/ед → себестоимость/ед → логистика/ед → комиссия/ед → "
                "хранение/ед → НДС/ед → реклама/ед = contribution margin/ед. "
                "Показывает ROAS по contribution margin."
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
            "name": "get_keyword_roi",
            "description": (
                "ROI ключевых слов: какие запросы приносят прибыльные заказы, "
                "а какие — только трафик (пустышки). Комбинирует данные поисковых "
                "запросов и экономику артикулов."
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
                    "model": {
                        "type": "string",
                        "description": "Фильтр по модели (LOWER), например 'wendy'",
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

async def _handle_funnel_overview(
    model: str, start_date: str, end_date: str, top_n: int = 5,
) -> dict:
    """Обзор модели: воронка, CR, органика, экономика WoW."""
    from shared.data_layer import (
        get_wb_article_funnel,
        get_wb_article_funnel_wow,
        get_wb_article_ad_attribution,
        get_wb_article_economics,
    )

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days + 1
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    # Fetch all data in parallel
    funnel_task = asyncio.to_thread(
        get_wb_article_funnel, start_date, end_date, model, top_n,
    )
    wow_task = asyncio.to_thread(
        get_wb_article_funnel_wow, start_date, prev_start, end_date, None,
    )
    ad_task = asyncio.to_thread(
        get_wb_article_ad_attribution, start_date, end_date, None,
    )
    econ_task = asyncio.to_thread(
        get_wb_article_economics, start_date, end_date, None,
    )

    funnel, wow_data, ad_data, econ_data = await asyncio.gather(
        funnel_task, wow_task, ad_task, econ_task,
    )

    # Build top articles with full funnel + economics
    top_articles = []
    for row in funnel:
        # (model, rn, artikul, opens, cart, orders, buyouts,
        #  cr_open_cart, cr_cart_order, cro, crp,
        #  revenue_spp, margin, orders_fin, avg_check, drr)
        top_articles.append({
            "model": row[0],
            "rank": row[1],
            "artikul": row[2],
            "переходы": _safe_int(row[3]),
            "корзина": _safe_int(row[4]),
            "заказы": _safe_int(row[5]),
            "выкупы": _safe_int(row[6]),
            "cr_переход_корзина": _safe_float(row[7]),
            "cr_корзина_заказ": _safe_float(row[8]),
            "cro_переход_заказ": _safe_float(row[9]),
            "crp_переход_выкуп": _safe_float(row[10]),
            "выручка": _safe_float(row[11], 0),
            "маржа": _safe_float(row[12], 0),
            "заказы_фин": _safe_int(row[13]),
            "ср_чек": _safe_float(row[14], 0),
            "дрр": _safe_float(row[15]),
        })

    # Aggregate WoW totals for the model
    model_totals = {"current": {}, "prev": {}}
    model_artikuls = {a["artikul"] for a in top_articles}
    for row in wow_data:
        period, artikul = row[0], row[1]
        if artikul not in model_artikuls and model_artikuls:
            continue
        if period in model_totals:
            for key, idx in [("переходы", 2), ("корзина", 3), ("заказы", 4), ("выкупы", 5)]:
                model_totals[period][key] = model_totals[period].get(key, 0) + _safe_int(row[idx])

    # Calculate model-level CRs
    for p in ("current", "prev"):
        t = model_totals[p]
        opens = t.get("переходы", 0)
        cart = t.get("корзина", 0)
        orders = t.get("заказы", 0)
        buyouts = t.get("выкупы", 0)
        t["cr_переход_корзина"] = round(cart / opens * 100, 2) if opens > 0 else 0
        t["cr_корзина_заказ"] = round(orders / cart * 100, 2) if cart > 0 else 0
        t["cro_переход_заказ"] = round(orders / opens * 100, 2) if opens > 0 else 0
        t["crp_переход_выкуп"] = round(buyouts / opens * 100, 2) if opens > 0 else 0

    # Model-level organic share
    total_organic_opens = 0
    total_ad_clicks = 0
    total_organic_orders = 0
    total_ad_orders = 0
    total_ad_spend = 0
    for row in ad_data:
        artikul = row[0]
        if model_artikuls and artikul not in model_artikuls:
            continue
        total_organic_opens += _safe_int(row[1])
        total_organic_orders += _safe_int(row[2])
        total_ad_clicks += _safe_int(row[4])
        total_ad_orders += _safe_int(row[5])
        total_ad_spend += _safe_float(row[6], 0)

    total_transitions = total_organic_opens + total_ad_clicks
    total_orders = total_organic_orders + total_ad_orders
    organic_share_pct = round(total_organic_opens / total_transitions * 100, 1) if total_transitions > 0 else 0
    organic_share_orders_pct = round(total_organic_orders / total_orders * 100, 1) if total_orders > 0 else 0

    # Model-level economics
    total_revenue = 0
    total_margin = 0
    total_orders_fin = 0
    for row in econ_data:
        artikul = row[0]
        if model_artikuls and artikul not in model_artikuls:
            continue
        total_revenue += _safe_float(row[1], 0)
        total_margin += _safe_float(row[2], 0)
        total_orders_fin += _safe_int(row[3])

    model_drr = round(total_ad_spend / total_revenue * 100, 1) if total_revenue > 0 else 0
    model_romi = round(total_margin / total_ad_spend * 100, 1) if total_ad_spend > 0 else 0

    # WoW deltas
    curr = model_totals.get("current", {})
    prev = model_totals.get("prev", {})
    changes = {
        "переходы_delta_pct": _safe_pct(curr.get("переходы", 0), prev.get("переходы", 0)),
        "заказы_delta_pct": _safe_pct(curr.get("заказы", 0), prev.get("заказы", 0)),
        "cro_delta_pp": round(curr.get("cro_переход_заказ", 0) - prev.get("cro_переход_заказ", 0), 2),
        "crp_delta_pp": round(curr.get("crp_переход_выкуп", 0) - prev.get("crp_переход_выкуп", 0), 2),
    }

    return {
        "model": model,
        "period": f"{start_date} — {end_date}",
        "top_articles": top_articles,
        "model_totals": {
            "current": curr,
            "previous": prev,
            "changes": changes,
        },
        "organic": {
            "доля_органики_переходы_pct": organic_share_pct,
            "доля_органики_заказы_pct": organic_share_orders_pct,
            "расход_реклама": total_ad_spend,
        },
        "economics": {
            "выручка_total": total_revenue,
            "маржа_total": total_margin,
            "дрр_pct": model_drr,
            "romi_pct": model_romi,
        },
    }


async def _handle_article_funnel(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Воронка по артикулам WoW с расчётом CR и дельт."""
    from shared.data_layer import get_wb_article_funnel_wow

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days + 1
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    rows = await asyncio.to_thread(
        get_wb_article_funnel_wow, start_date, prev_start, end_date, artikul_filter,
    )

    articles: Dict[str, dict] = {}
    for row in rows:
        period, artikul = row[0], row[1]
        opens = _safe_int(row[2])
        cart = _safe_int(row[3])
        orders = _safe_int(row[4])
        buyouts = _safe_int(row[5])

        if artikul not in articles:
            articles[artikul] = {"current": {}, "prev": {}}

        articles[artikul][period] = {
            "переходы": opens,
            "корзина": cart,
            "заказы": orders,
            "выкупы": buyouts,
            "cr_переход_корзина": round(cart / opens * 100, 2) if opens > 0 else 0,
            "cr_корзина_заказ": round(orders / cart * 100, 2) if cart > 0 else 0,
            "cro_переход_заказ": round(orders / opens * 100, 2) if opens > 0 else 0,
            "crp_переход_выкуп": round(buyouts / opens * 100, 2) if opens > 0 else 0,
        }

    results = []
    for artikul, data in articles.items():
        curr = data.get("current", {})
        prev = data.get("prev", {})
        results.append({
            "artikul": artikul,
            "current": curr,
            "previous": prev,
            "changes": {
                "переходы_delta_pct": _safe_pct(curr.get("переходы", 0), prev.get("переходы", 0)),
                "заказы_delta_pct": _safe_pct(curr.get("заказы", 0), prev.get("заказы", 0)),
                "выкупы_delta_pct": _safe_pct(curr.get("выкупы", 0), prev.get("выкупы", 0)),
                "cro_delta_pp": round(
                    curr.get("cro_переход_заказ", 0) - prev.get("cro_переход_заказ", 0), 2,
                ),
                "crp_delta_pp": round(
                    curr.get("crp_переход_выкуп", 0) - prev.get("crp_переход_выкуп", 0), 2,
                ),
            },
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": sorted(results, key=lambda x: x["current"].get("заказы", 0), reverse=True),
    }


async def _handle_article_economics(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Экономика артикулов: выручка, маржа, ДРР, ROMI, CPS, прибыль на посетителя."""
    from shared.data_layer import get_wb_article_economics

    rows = await asyncio.to_thread(
        get_wb_article_economics, start_date, end_date, artikul_filter,
    )

    articles = []
    for row in rows:
        # (artikul, revenue_spp, margin, orders_count, buyouts_count,
        #  avg_check, drr, ad_spend, opens,
        #  cps, profit_per_sale, profit_per_visitor, cac, romi)
        artikul = row[0]
        revenue = _safe_float(row[1], 0)
        margin = _safe_float(row[2], 0)
        orders_count = _safe_int(row[3])
        buyouts_count = _safe_int(row[4])
        avg_check = _safe_float(row[5], 0)
        drr = _safe_float(row[6])
        ad_spend = _safe_float(row[7], 0)
        opens = _safe_int(row[8])
        cps = _safe_float(row[9], 0)
        profit_per_sale = _safe_float(row[10], 0)
        profit_per_visitor = _safe_float(row[11], 2)
        cac = _safe_float(row[12], 2)
        romi = _safe_float(row[13])

        margin_pct = round(margin / revenue * 100, 1) if revenue > 0 else 0

        articles.append({
            "artikul": artikul,
            "выручка": revenue,
            "маржа": margin,
            "маржа_pct": margin_pct,
            "заказы": orders_count,
            "выкупы": buyouts_count,
            "ср_чек": avg_check,
            "дрр_pct": drr,
            "расход_реклама": ad_spend,
            "переходы": opens,
            "cps": cps,
            "прибыль_на_продажу": profit_per_sale,
            "прибыль_на_посетителя": profit_per_visitor,
            "cac": cac,
            "romi_pct": romi,
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": articles,
    }


async def _handle_article_ad_attribution(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Органика vs реклама per article."""
    from shared.data_layer import get_wb_article_ad_attribution

    rows = await asyncio.to_thread(
        get_wb_article_ad_attribution, start_date, end_date, artikul_filter,
    )

    articles = []
    for row in rows:
        # (artikul, organic_opens, organic_orders, ad_views, ad_clicks, ad_orders, ad_spend,
        #  organic_share_opens_pct, organic_share_orders_pct, drr_pct)
        artikul = row[0]
        organic_opens = _safe_int(row[1])
        organic_orders = _safe_int(row[2])
        ad_views = _safe_int(row[3])
        ad_clicks = _safe_int(row[4])
        ad_orders = _safe_int(row[5])
        ad_spend = _safe_float(row[6], 0)
        organic_share_opens = _safe_float(row[7])
        organic_share_orders = _safe_float(row[8])

        articles.append({
            "artikul": artikul,
            "органика_переходы": organic_opens,
            "органика_заказы": organic_orders,
            "реклама_показы": ad_views,
            "реклама_клики": ad_clicks,
            "реклама_заказы": ad_orders,
            "расход_реклама": ad_spend,
            "доля_органики_переходы_pct": organic_share_opens,
            "доля_органики_заказы_pct": organic_share_orders,
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": articles,
    }


async def _handle_search_keywords(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Ключевые слова из WB API."""
    from shared.data_layer import get_wb_search_keywords_api

    # If artikul_filter provided, get nmids from nomenclature
    nmids = None
    if artikul_filter:
        from shared.data_layer import _db_cursor, _get_wb_connection
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        lowered = [a.lower() for a in artikul_filter]
        query = f"""
        SELECT DISTINCT nmid FROM nomenclature
        WHERE LOWER(vendorcode) IN ({placeholders})
        """
        with _db_cursor(_get_wb_connection) as (conn, cur):
            cur.execute(query, lowered)
            nmids = [row[0] for row in cur.fetchall()]

    items = await asyncio.to_thread(
        get_wb_search_keywords_api, start_date, end_date, nmids,
    )

    # Group by keyword, aggregate across cabinets
    keyword_map: Dict[str, dict] = {}
    for item in items:
        text = item["text"]
        if text not in keyword_map:
            keyword_map[text] = {
                "запрос": text,
                "частотность": 0,
                "переходы": 0,
                "корзина": 0,
                "заказы": 0,
                "nmIds": set(),
            }
        keyword_map[text]["частотность"] = max(keyword_map[text]["частотность"], item["frequency"])
        keyword_map[text]["переходы"] += item["openCard"]
        keyword_map[text]["корзина"] += item["addToCart"]
        keyword_map[text]["заказы"] += item["orders"]
        keyword_map[text]["nmIds"].add(item["nmId"])

    # Convert sets to lists for JSON serialization
    keywords = []
    for kw in keyword_map.values():
        kw["nmIds"] = list(kw["nmIds"])
        keywords.append(kw)

    # Sort by frequency descending
    keywords.sort(key=lambda x: x["частотность"], reverse=True)

    return {
        "period": f"{start_date} — {end_date}",
        "keywords_count": len(keywords),
        "keywords": keywords[:50],  # Top 50
    }


async def _handle_keyword_positions(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Позиции по ключевым словам WoW из kz_off."""
    from shared.data_layer import get_wb_seo_keyword_positions

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days + 1
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    rows = await asyncio.to_thread(
        get_wb_seo_keyword_positions, start_date, prev_start, end_date, artikul_filter,
    )

    artikul_keywords: Dict[str, Dict[str, dict]] = {}
    for row in rows:
        period, artikul, keyword = row[0], row[1], row[2]
        median_pos = _safe_float(row[3]) if row[3] else None
        freq = _safe_int(row[4])

        if artikul not in artikul_keywords:
            artikul_keywords[artikul] = {}
        if keyword not in artikul_keywords[artikul]:
            artikul_keywords[artikul][keyword] = {"current": {}, "prev": {}}

        artikul_keywords[artikul][keyword][period] = {
            "позиция": median_pos,
            "частотность": freq,
            "переходы": _safe_int(row[5]),
            "корзина": _safe_int(row[6]),
            "заказы": _safe_int(row[7]),
            "видимость": _safe_float(row[8], 2) if row[8] else 0,
        }

    result_articles = []
    for artikul, keywords in artikul_keywords.items():
        kw_results = []
        for keyword, periods in keywords.items():
            curr = periods.get("current", {})
            prev = periods.get("prev", {})
            curr_pos = curr.get("позиция")
            prev_pos = prev.get("позиция")

            pos_delta = None
            if curr_pos is not None and prev_pos is not None:
                pos_delta = round(curr_pos - prev_pos, 1)

            kw_results.append({
                "запрос": keyword,
                "current": curr,
                "previous": prev,
                "position_delta": pos_delta,
            })

        kw_results.sort(key=lambda x: x["current"].get("частотность", 0), reverse=True)
        result_articles.append({
            "artikul": artikul,
            "keywords": kw_results[:20],  # Top 20 per article
        })

    return {
        "period": f"{start_date} — {end_date}",
        "articles": result_articles,
    }


async def _handle_article_unit_economics(
    start_date: str, end_date: str, artikul_filter: list = None,
) -> dict:
    """Водопад затрат на единицу товара per article."""
    from shared.data_layer import get_wb_article_contribution_margin

    e = datetime.strptime(end_date, '%Y-%m-%d')
    end_exclusive = (e + timedelta(days=1)).strftime('%Y-%m-%d')

    rows = await asyncio.to_thread(
        get_wb_article_contribution_margin, start_date, end_exclusive, artikul_filter
    )

    if not rows:
        return {"error": "Нет данных по артикулам за период"}

    articles = []
    for r in rows[:30]:  # Top 30
        articles.append({
            "артикул": r[0],
            "продажи_шт": _safe_int(r[1]),
            "заказы_шт": _safe_int(r[2]),
            "выручка": _safe_float(r[3], 0),
            "выручка_на_ед": _safe_float(r[4]),
            "себестоимость_на_ед": _safe_float(r[5]),
            "логистика_на_ед": _safe_float(r[6]),
            "комиссия_на_ед": _safe_float(r[7]),
            "хранение_на_ед": _safe_float(r[8]),
            "НДС_на_ед": _safe_float(r[9]),
            "реклама_на_ед": _safe_float(r[10]),
            "CM_до_рекламы": _safe_float(r[11], 0),
            "CM_после_рекламы": _safe_float(r[12], 0),
            "CM_до_рекламы_на_ед": _safe_float(r[13]),
            "CM_после_рекламы_на_ед": _safe_float(r[14]),
            "маржинальность_%": _safe_float(r[15]),
            "ROAS_contribution": _safe_float(r[16]),
        })

    return {
        "период": f"{start_date} — {end_date}",
        "всего_артикулов": len(rows),
        "показано": len(articles),
        "articles": articles,
    }


async def _handle_keyword_roi(
    start_date: str, end_date: str, model: str = None,
) -> dict:
    """ROI ключевых слов: прибыльные vs пустышки."""
    from shared.data_layer import (
        get_wb_search_keywords_api,
        get_wb_article_economics,
    )

    e = datetime.strptime(end_date, '%Y-%m-%d')
    end_exclusive = (e + timedelta(days=1)).strftime('%Y-%m-%d')

    # Get keywords
    artikul_filter = None
    if model:
        # We'll filter by model prefix in the keywords
        artikul_filter = None  # Keywords API filters by vendorcode internally

    kw_rows = await asyncio.to_thread(
        get_wb_search_keywords_api, start_date, end_exclusive, artikul_filter
    )

    if not kw_rows:
        return {"error": "Нет данных по ключевым словам за период"}

    # Get article economics for margin context
    econ_rows = await asyncio.to_thread(
        get_wb_article_economics, start_date, end_exclusive, artikul_filter
    )

    # Total margin and orders across all articles
    total_margin = sum(float(r[2] or 0) for r in econ_rows) if econ_rows else 0
    total_orders = sum(int(r[3] or 0) for r in econ_rows) if econ_rows else 1

    # Parse keywords — each row: (artikul, keyword, frequency, opens, add_to_cart, orders)
    keywords = []
    for r in kw_rows:
        artikul = r[0] if r[0] else ""
        keyword = r[1] if r[1] else ""
        frequency = int(r[2] or 0)
        opens = int(r[3] or 0)
        add_to_cart = int(r[4] or 0)
        orders = int(r[5] or 0)

        # Filter by model if specified
        if model and model.lower() not in artikul.lower():
            continue

        conversion = round(orders / opens * 100, 2) if opens > 0 else 0
        # Estimated margin contribution
        est_margin = round((orders / total_orders) * total_margin, 0) if total_orders > 0 else 0

        verdict = "profitable" if orders > 0 and conversion > 0.5 else "wasted"

        keywords.append({
            "артикул": artikul,
            "запрос": keyword,
            "частотность": frequency,
            "переходы": opens,
            "корзина": add_to_cart,
            "заказы": orders,
            "конверсия_%": conversion,
            "ест_маржа_₽": est_margin,
            "вердикт": verdict,
        })

    # Sort: generators (by orders desc), then wasted (by opens desc)
    generators = sorted(
        [k for k in keywords if k["вердикт"] == "profitable"],
        key=lambda x: x["заказы"], reverse=True
    )[:10]

    wasted = sorted(
        [k for k in keywords if k["вердикт"] == "wasted" and k["переходы"] > 5],
        key=lambda x: x["переходы"], reverse=True
    )[:10]

    return {
        "период": f"{start_date} — {end_date}",
        "модель": model or "все",
        "всего_ключевиков": len(keywords),
        "генераторы_прибыли": generators,
        "трафик_пустышки": wasted,
        "общая_маржа_периода": total_margin,
    }


# =============================================================================
# HANDLER REGISTRY
# =============================================================================

FUNNEL_TOOL_HANDLERS: Dict[str, Any] = {
    "get_funnel_overview": _handle_funnel_overview,
    "get_article_funnel": _handle_article_funnel,
    "get_article_economics": _handle_article_economics,
    "get_article_ad_attribution": _handle_article_ad_attribution,
    "get_search_keywords": _handle_search_keywords,
    "get_keyword_positions": _handle_keyword_positions,
    "get_article_unit_economics": _handle_article_unit_economics,
    "get_keyword_roi": _handle_keyword_roi,
}


# =============================================================================
# EXECUTOR
# =============================================================================

async def execute_funnel_tool(tool_name: str, arguments: dict) -> str:
    """Execute a funnel tool by name with given arguments.

    Returns JSON string with result or error.
    """
    handler = FUNNEL_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown funnel tool: {tool_name}"}, ensure_ascii=False)

    try:
        logger.info(f"Funnel tool call: {tool_name}({json.dumps(arguments, ensure_ascii=False)[:200]})")
        result = await handler(**arguments)
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        logger.info(f"Funnel tool result: {tool_name} → {len(result_json)} chars")
        return result_json
    except TypeError as e:
        logger.error(f"Funnel tool {tool_name} argument error: {e}")
        return json.dumps(
            {"error": f"Invalid arguments for {tool_name}: {e}"},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Funnel tool {tool_name} execution error: {e}", exc_info=True)
        return json.dumps(
            {"error": f"Tool execution failed: {e}"},
            ensure_ascii=False,
        )


# =============================================================================
# PRE-FETCH BUNDLE FOR CONSOLIDATED FUNNEL REPORT
# =============================================================================

# Thresholds for significant WoW changes
_SIG_TRAFFIC_PCT = 20.0    # |delta| > 20% opens
_SIG_ORDERS_PCT = 15.0     # |delta| > 15% orders
_SIG_CRO_PP = 2.0          # |delta| > 2 pp CRO
_SIG_DRR_PP = 5.0          # |delta| > 5 pp DRR


async def get_all_models_funnel_bundle(
    start_date: str, end_date: str,
) -> dict:
    """Pre-fetch funnel data for all active models (A/B articles only).

    Called from pipeline / scheduler — NOT an LLM tool.
    Returns a compact data bundle for LLM synthesis.
    """
    from shared.data_layer import (
        get_active_models_with_abc,
        get_wb_article_funnel,
        get_wb_article_funnel_wow,
        get_wb_article_economics,
        get_wb_article_ad_attribution,
    )

    s = datetime.strptime(start_date, '%Y-%m-%d')
    e = datetime.strptime(end_date, '%Y-%m-%d')
    period_days = (e - s).days + 1
    prev_start = (s - timedelta(days=period_days)).strftime('%Y-%m-%d')

    # 1. Get models + ABC classification
    models_abc = await asyncio.to_thread(
        get_active_models_with_abc, start_date, end_date,
    )

    if not models_abc:
        return {"models": [], "brand_totals": {}}

    # 2. For each model, fetch funnel data in parallel
    async def _fetch_model_data(model_info: dict) -> dict:
        model_name = model_info['model']
        ab_articles = [
            a['artikul'] for a in model_info['articles']
            if a['abc_class'] in ('A', 'B')
        ]

        if not ab_articles:
            return None

        # Parallel data fetch for this model
        funnel_task = asyncio.to_thread(
            get_wb_article_funnel, start_date, end_date, model_name, 20,
        )
        wow_task = asyncio.to_thread(
            get_wb_article_funnel_wow, start_date, prev_start, end_date, ab_articles,
        )
        econ_task = asyncio.to_thread(
            get_wb_article_economics, start_date, end_date, ab_articles,
        )
        ad_task = asyncio.to_thread(
            get_wb_article_ad_attribution, start_date, end_date, ab_articles,
        )

        funnel, wow_data, econ_data, ad_data = await asyncio.gather(
            funnel_task, wow_task, econ_task, ad_task,
        )

        # --- Funnel totals (model level) ---
        model_totals = {"current": {}, "prev": {}}
        for row in wow_data:
            period, artikul = row[0], row[1]
            if period in model_totals:
                for key, idx in [("переходы", 2), ("корзина", 3),
                                 ("заказы", 4), ("выкупы", 5)]:
                    model_totals[period][key] = (
                        model_totals[period].get(key, 0) + _safe_int(row[idx])
                    )

        # Calculate CRs
        for p in ("current", "prev"):
            t = model_totals[p]
            opens = t.get("переходы", 0)
            cart = t.get("корзина", 0)
            orders = t.get("заказы", 0)
            buyouts = t.get("выкупы", 0)
            t["cr_переход_корзина"] = round(cart / opens * 100, 2) if opens else 0
            t["cr_корзина_заказ"] = round(orders / cart * 100, 2) if cart else 0
            t["cro"] = round(orders / opens * 100, 2) if opens else 0
            t["crp"] = round(buyouts / opens * 100, 2) if opens else 0

        curr = model_totals["current"]
        prev = model_totals["prev"]
        changes = {
            "переходы_delta_pct": _safe_pct(curr.get("переходы", 0), prev.get("переходы", 0)),
            "заказы_delta_pct": _safe_pct(curr.get("заказы", 0), prev.get("заказы", 0)),
            "выкупы_delta_pct": _safe_pct(curr.get("выкупы", 0), prev.get("выкупы", 0)),
            "cro_delta_pp": round(curr.get("cro", 0) - prev.get("cro", 0), 2),
            "crp_delta_pp": round(curr.get("crp", 0) - prev.get("crp", 0), 2),
        }

        # --- Economics ---
        total_revenue = 0
        total_margin = 0
        total_ad_spend = 0
        total_orders_fin = 0
        for row in econ_data:
            total_revenue += _safe_float(row[1], 0)
            total_margin += _safe_float(row[2], 0)
            total_orders_fin += _safe_int(row[3])
            total_ad_spend += _safe_float(row[7], 0)

        model_drr = round(total_ad_spend / total_revenue * 100, 1) if total_revenue > 0 else 0
        model_romi = round(total_margin / total_ad_spend * 100, 1) if total_ad_spend > 0 else 0

        # --- Organic share ---
        total_organic_opens = 0
        total_ad_clicks = 0
        total_organic_orders = 0
        total_ad_orders = 0
        for row in ad_data:
            total_organic_opens += _safe_int(row[1])
            total_organic_orders += _safe_int(row[2])
            total_ad_clicks += _safe_int(row[4])
            total_ad_orders += _safe_int(row[5])

        total_tr = total_organic_opens + total_ad_clicks
        organic_opens_pct = round(total_organic_opens / total_tr * 100, 1) if total_tr else 0
        total_ord = total_organic_orders + total_ad_orders
        organic_orders_pct = round(total_organic_orders / total_ord * 100, 1) if total_ord else 0

        # --- Significant article changes (WoW) ---
        articles_wow = {}
        for row in wow_data:
            period, artikul = row[0], row[1]
            if artikul not in articles_wow:
                articles_wow[artikul] = {"current": {}, "prev": {}}
            articles_wow[artikul][period] = {
                "переходы": _safe_int(row[2]),
                "заказы": _safe_int(row[4]),
            }

        significant = []
        for artikul, data in articles_wow.items():
            c = data.get("current", {})
            p = data.get("prev", {})
            c_opens = c.get("переходы", 0)
            p_opens = p.get("переходы", 0)
            c_orders = c.get("заказы", 0)
            p_orders = p.get("заказы", 0)

            opens_delta = _safe_pct(c_opens, p_opens)
            orders_delta = _safe_pct(c_orders, p_orders)

            flags = []
            if abs(opens_delta) > _SIG_TRAFFIC_PCT:
                flags.append(f"переходы {opens_delta:+.1f}%")
            if abs(orders_delta) > _SIG_ORDERS_PCT:
                flags.append(f"заказы {orders_delta:+.1f}%")

            if flags:
                significant.append({
                    "artikul": artikul,
                    "переходы": c_opens,
                    "заказы": c_orders,
                    "flags": flags,
                })

        # --- ABC articles summary (A/B only) ---
        abc_summary = [
            {
                "artikul": a['artikul'],
                "abc": a['abc_class'],
                "маржа_доля_pct": a['margin_share_pct'],
            }
            for a in model_info['articles']
            if a['abc_class'] in ('A', 'B')
        ]

        return {
            "model": model_name,
            "abc_articles": abc_summary,
            "funnel_totals": {
                "current": curr,
                "previous": prev,
                "changes": changes,
            },
            "economics": {
                "выручка": round(total_revenue, 0),
                "маржа": round(total_margin, 0),
                "дрр_pct": model_drr,
                "romi_pct": model_romi,
                "расход_реклама": round(total_ad_spend, 0),
            },
            "organic": {
                "доля_органики_переходы_pct": organic_opens_pct,
                "доля_органики_заказы_pct": organic_orders_pct,
            },
            "significant_articles": significant,
        }

    # Fetch all models in parallel
    tasks = [_fetch_model_data(m) for m in models_abc]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    models_data = []
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"Funnel bundle model fetch error: {r}")
            continue
        if r is not None:
            models_data.append(r)

    # Sort by revenue descending
    models_data.sort(key=lambda x: x["economics"]["выручка"], reverse=True)

    # Brand totals
    brand = {
        "переходы": sum(m["funnel_totals"]["current"].get("переходы", 0) for m in models_data),
        "заказы": sum(m["funnel_totals"]["current"].get("заказы", 0) for m in models_data),
        "выкупы": sum(m["funnel_totals"]["current"].get("выкупы", 0) for m in models_data),
        "выручка": sum(m["economics"]["выручка"] for m in models_data),
        "маржа": sum(m["economics"]["маржа"] for m in models_data),
        "расход_реклама": sum(m["economics"]["расход_реклама"] for m in models_data),
    }
    brand["дрр_pct"] = round(brand["расход_реклама"] / brand["выручка"] * 100, 1) if brand["выручка"] else 0

    # Previous period brand totals
    brand_prev = {
        "переходы": sum(m["funnel_totals"]["previous"].get("переходы", 0) for m in models_data),
        "заказы": sum(m["funnel_totals"]["previous"].get("заказы", 0) for m in models_data),
        "выкупы": sum(m["funnel_totals"]["previous"].get("выкупы", 0) for m in models_data),
    }
    brand["changes"] = {
        "переходы_delta_pct": _safe_pct(brand["переходы"], brand_prev["переходы"]),
        "заказы_delta_pct": _safe_pct(brand["заказы"], brand_prev["заказы"]),
        "выкупы_delta_pct": _safe_pct(brand["выкупы"], brand_prev["выкупы"]),
    }

    logger.info(
        f"Funnel bundle: {len(models_data)} models, "
        f"brand revenue={brand['выручка']:.0f}, margin={brand['маржа']:.0f}"
    )

    return {
        "period": f"{start_date} — {end_date}",
        "models": models_data,
        "brand_totals": brand,
    }
