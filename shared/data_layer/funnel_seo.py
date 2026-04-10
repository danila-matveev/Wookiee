"""Воронка артикулов, ad-атрибуция, экономика и SEO-позиции.

Функции для анализа воронки продаж per article, атрибуции рекламы,
экономики артикулов (contribution margin) и SEO-позиций ключевых слов.
"""

import os

from shared.data_layer._connection import _get_wb_connection, _db_cursor
from shared.model_mapping import get_osnova_sql

__all__ = [
    "get_wb_article_funnel",
    "get_wb_article_funnel_wow",
    "get_wb_article_ad_attribution",
    "get_wb_article_economics",
    "get_wb_article_contribution_margin",
    "get_wb_seo_keyword_positions",
    "get_wb_search_keywords_api",
]


def get_wb_article_funnel(start_date, end_date, model_filter=None, top_n=10):
    """Полная воронка per article: content_analysis + abc_date.

    Возвращает переходы, корзину, заказы, выкупы, CR, выручку, маржу.
    TOP-N артикулов по заказам внутри каждой модели.

    Args:
        start_date: начало периода (включительно).
        end_date: конец периода (не включительно).
        model_filter: фильтр по модели (LOWER).
        top_n: количество артикулов на модель.

    Returns:
        list of tuples (model, rank, artikul, opens, cart, orders, buyouts,
                        cr_open_cart, cr_cart_order, cro, crp,
                        revenue_spp, margin, orders_fin, avg_check, drr).
    """
    osnova_sql = get_osnova_sql("SPLIT_PART(ca.vendorcode, '/', 1)")
    osnova_sql_abc = get_osnova_sql("SPLIT_PART(a.article, '/', 1)")

    model_clause = ""
    params = [start_date, end_date, start_date, end_date, start_date, end_date, top_n]
    if model_filter is not None:
        model_clause = f"AND {osnova_sql} = %s"
        params = [start_date, end_date, start_date, end_date,
                  model_filter.lower(), start_date, end_date, top_n]

    query = f"""
    WITH funnel AS (
        SELECT
            {osnova_sql} as model,
            LOWER(ca.vendorcode) as artikul,
            SUM(ca.opencardcount) as opens,
            SUM(ca.addtocartcount) as cart,
            SUM(ca.orderscount) as orders,
            SUM(ca.buyoutscount) as buyouts
        FROM content_analysis ca
        WHERE ca.date >= %s AND ca.date < %s
            AND ca.vendorcode IN (
                SELECT DISTINCT article FROM abc_date
                WHERE date >= %s AND date < %s
            )
            {model_clause}
        GROUP BY {osnova_sql}, LOWER(ca.vendorcode)
    ),
    finance AS (
        SELECT
            LOWER(a.article) as artikul,
            SUM(a.revenue_spp) as revenue_spp,
            SUM(a.revenue_spp) - SUM(a.comis_spp) - SUM(a.logist) - SUM(a.sebes)
                - SUM(a.reclama) - SUM(a.reclama_vn) - SUM(a.storage)
                - SUM(a.nds) - SUM(a.penalty) - SUM(a.retention)
                - SUM(a.deduction) as margin,
            SUM(a.count_orders) as orders_fin,
            SUM(a.revenue_spp) / NULLIF(SUM(a.count_orders), 0) as avg_check,
            (SUM(a.reclama) + SUM(a.reclama_vn)) / NULLIF(SUM(a.revenue_spp), 0) * 100 as drr
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
        GROUP BY LOWER(a.article)
    ),
    ranked AS (
        SELECT
            f.model, f.artikul, f.opens, f.cart, f.orders, f.buyouts,
            ROUND(f.cart * 100.0 / NULLIF(f.opens, 0), 2) as cr_open_cart,
            ROUND(f.orders * 100.0 / NULLIF(f.cart, 0), 2) as cr_cart_order,
            ROUND(f.orders * 100.0 / NULLIF(f.opens, 0), 2) as cro,
            ROUND(f.buyouts * 100.0 / NULLIF(f.opens, 0), 2) as crp,
            fin.revenue_spp, fin.margin, fin.orders_fin, fin.avg_check, fin.drr,
            ROW_NUMBER() OVER (
                PARTITION BY f.model ORDER BY f.orders DESC
            ) as rn
        FROM funnel f
        LEFT JOIN finance fin ON f.artikul = fin.artikul
    )
    SELECT model, rn, artikul, opens, cart, orders, buyouts,
           cr_open_cart, cr_cart_order, cro, crp,
           revenue_spp, margin, orders_fin, avg_check, drr
    FROM ranked
    WHERE rn <= %s
    ORDER BY model, rn;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_article_funnel_wow(current_start, prev_start, current_end, artikul_filter=None):
    """Воронка WoW: два периода (current vs prev) из content_analysis.

    Args:
        current_start: начало текущего периода.
        prev_start: начало предыдущего периода.
        current_end: конец текущего периода.
        artikul_filter: список артикулов для фильтрации.

    Returns:
        list of tuples (period, artikul, opens, cart, orders, buyouts).
    """
    artikul_clause = ""
    params = [current_start, prev_start, current_end, prev_start, current_end]

    if artikul_filter is not None and len(artikul_filter) > 0:
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        artikul_clause = f"AND LOWER(ca.vendorcode) IN ({placeholders})"
        params.extend([a.lower() for a in artikul_filter])

    query = f"""
    SELECT
        CASE WHEN ca.date >= %s THEN 'current' ELSE 'prev' END as period,
        LOWER(ca.vendorcode) as artikul,
        SUM(ca.opencardcount) as opens,
        SUM(ca.addtocartcount) as cart,
        SUM(ca.orderscount) as orders,
        SUM(ca.buyoutscount) as buyouts
    FROM content_analysis ca
    WHERE ca.date >= %s AND ca.date < %s
        AND ca.vendorcode IN (
            SELECT DISTINCT article FROM abc_date
            WHERE date >= %s AND date < %s
        )
        {artikul_clause}
    GROUP BY 1, LOWER(ca.vendorcode)
    ORDER BY period, artikul;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_article_ad_attribution(start_date, end_date, artikul_filter=None):
    """Органика vs реклама per article с расчётом доли органики и ДРР.

    Args:
        start_date: начало периода (включительно).
        end_date: конец периода (не включительно).
        artikul_filter: список артикулов для фильтрации.

    Returns:
        list of tuples (artikul, organic_opens, organic_orders, ad_views,
                        ad_clicks, ad_orders, ad_spend,
                        organic_share_opens_pct, organic_share_orders_pct, drr_pct).
    """
    org_artikul_clause = ""
    adv_artikul_clause = ""
    org_params = [start_date, end_date]
    adv_params = [start_date, end_date]

    if artikul_filter is not None and len(artikul_filter) > 0:
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        lowered = [a.lower() for a in artikul_filter]
        org_artikul_clause = f"AND LOWER(ca.vendorcode) IN ({placeholders})"
        adv_artikul_clause = f"AND LOWER(n.vendorcode) IN ({placeholders})"
        org_params.extend(lowered)
        adv_params.extend(lowered)

    params = org_params + adv_params

    query = f"""
    WITH organic AS (
        SELECT
            LOWER(ca.vendorcode) as artikul,
            SUM(ca.opencardcount) as organic_opens,
            SUM(ca.orderscount) as organic_orders
        FROM content_analysis ca
        WHERE ca.date >= %s AND ca.date < %s
            {org_artikul_clause}
        GROUP BY LOWER(ca.vendorcode)
    ),
    paid AS (
        SELECT
            LOWER(n.vendorcode) as artikul,
            SUM(w.views) as ad_views,
            SUM(w.clicks) as ad_clicks,
            SUM(w.orders) as ad_orders,
            SUM(w.sum) as ad_spend
        FROM wb_adv w
        JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n ON w.nmid = n.nmid
        WHERE w.date >= %s AND w.date < %s
            {adv_artikul_clause}
        GROUP BY LOWER(n.vendorcode)
    )
    SELECT
        COALESCE(o.artikul, p.artikul) as artikul,
        COALESCE(o.organic_opens, 0) as organic_opens,
        COALESCE(o.organic_orders, 0) as organic_orders,
        COALESCE(p.ad_views, 0) as ad_views,
        COALESCE(p.ad_clicks, 0) as ad_clicks,
        COALESCE(p.ad_orders, 0) as ad_orders,
        COALESCE(p.ad_spend, 0) as ad_spend,
        ROUND(
            COALESCE(o.organic_opens, 0) * 100.0
            / NULLIF(COALESCE(o.organic_opens, 0) + COALESCE(p.ad_clicks, 0), 0), 1
        ) as organic_share_opens_pct,
        ROUND(
            COALESCE(o.organic_orders, 0) * 100.0
            / NULLIF(COALESCE(o.organic_orders, 0) + COALESCE(p.ad_orders, 0), 0), 1
        ) as organic_share_orders_pct,
        ROUND(
            COALESCE(p.ad_spend, 0) * 100.0
            / NULLIF(COALESCE(o.organic_opens, 0) + COALESCE(p.ad_clicks, 0), 0), 1
        ) as drr_pct
    FROM organic o
    FULL OUTER JOIN paid p ON o.artikul = p.artikul
    ORDER BY COALESCE(o.organic_opens, 0) + COALESCE(p.ad_views, 0) DESC;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_article_economics(start_date, end_date, artikul_filter=None):
    """Расширенная экономика артикулов: маржа, ДРР, ROMI, CPS, прибыль на посетителя.

    JOIN abc_date + content_analysis для получения переходов.

    Args:
        start_date: начало периода (включительно).
        end_date: конец периода (не включительно).
        artikul_filter: список артикулов для фильтрации.

    Returns:
        list of tuples (artikul, revenue_spp, margin, orders_count, buyouts_count,
                        avg_check, drr, ad_spend, opens,
                        cps, profit_per_sale, profit_per_visitor, cac, romi).
    """
    fin_clause = ""
    ca_clause = ""
    fin_params = [start_date, end_date]
    ca_params = [start_date, end_date]

    if artikul_filter is not None and len(artikul_filter) > 0:
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        lowered = [a.lower() for a in artikul_filter]
        fin_clause = f"AND LOWER(a.article) IN ({placeholders})"
        ca_clause = f"AND LOWER(ca.vendorcode) IN ({placeholders})"
        fin_params.extend(lowered)
        ca_params.extend(lowered)

    params = fin_params + ca_params

    query = f"""
    WITH finance AS (
        SELECT
            LOWER(a.article) as artikul,
            SUM(a.revenue_spp) as revenue_spp,
            SUM(a.revenue_spp) - SUM(a.comis_spp) - SUM(a.logist) - SUM(a.sebes)
                - SUM(a.reclama) - SUM(a.reclama_vn) - SUM(a.storage)
                - SUM(a.nds) - SUM(a.penalty) - SUM(a.retention)
                - SUM(a.deduction) as margin,
            SUM(a.count_orders) as orders_count,
            SUM(a.full_counts) as buyouts_count,
            SUM(a.revenue_spp) / NULLIF(SUM(a.count_orders), 0) as avg_check,
            (SUM(a.reclama) + SUM(a.reclama_vn)) / NULLIF(SUM(a.revenue_spp), 0) * 100 as drr,
            SUM(a.reclama) + SUM(a.reclama_vn) as ad_spend
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
            {fin_clause}
        GROUP BY LOWER(a.article)
    ),
    traffic AS (
        SELECT
            LOWER(ca.vendorcode) as artikul,
            SUM(ca.opencardcount) as opens
        FROM content_analysis ca
        WHERE ca.date >= %s AND ca.date < %s
            {ca_clause}
        GROUP BY LOWER(ca.vendorcode)
    )
    SELECT
        f.artikul,
        f.revenue_spp,
        f.margin,
        f.orders_count,
        f.buyouts_count,
        f.avg_check,
        f.drr,
        f.ad_spend,
        COALESCE(t.opens, 0) as opens,
        -- CPS = ad_spend / orders
        ROUND(f.ad_spend / NULLIF(f.orders_count, 0), 2) as cps,
        -- Прибыль на 1 продажу
        ROUND(f.margin / NULLIF(f.orders_count, 0), 2) as profit_per_sale,
        -- Прибыль на 1 посетителя
        ROUND(f.margin / NULLIF(COALESCE(t.opens, 0), 0), 2) as profit_per_visitor,
        -- CAC = ad_spend / opens
        ROUND(f.ad_spend / NULLIF(COALESCE(t.opens, 0), 0), 2) as cac,
        -- ROMI = margin / ad_spend * 100
        ROUND(f.margin * 100.0 / NULLIF(f.ad_spend, 0), 1) as romi
    FROM finance f
    LEFT JOIN traffic t ON f.artikul = t.artikul
    ORDER BY f.revenue_spp DESC;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_article_contribution_margin(start_date, end_date, artikul_filter=None):
    """Водопад затрат на единицу товара per article (Contribution Margin).

    Показывает структуру: выручка/ед -> себестоимость/ед -> логистика/ед ->
    комиссия/ед -> хранение/ед -> НДС/ед -> реклама/ед = contribution margin/ед.

    Args:
        start_date: начало периода (включительно).
        end_date: конец периода (не включительно).
        artikul_filter: список артикулов для фильтрации.

    Returns:
        list of tuples (artikul, sales_count, orders_count,
                        revenue_spp, revenue_per_unit,
                        sebes_per_unit, logist_per_unit, commission_per_unit,
                        storage_per_unit, nds_per_unit, ad_per_unit,
                        contribution_before_ad, contribution_after_ad,
                        cm_before_ad_per_unit, cm_after_ad_per_unit,
                        margin_pct, roas_contribution).
    """
    fin_clause = ""
    params = [start_date, end_date]

    if artikul_filter is not None and len(artikul_filter) > 0:
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        lowered = [a.lower() for a in artikul_filter]
        fin_clause = f"AND LOWER(a.article) IN ({placeholders})"
        params.extend(lowered)

    query = f"""
    SELECT
        LOWER(a.article) as artikul,
        SUM(a.full_counts) as sales_count,
        SUM(a.count_orders) as orders_count,
        SUM(a.revenue_spp) as revenue_spp,
        -- Per-unit waterfall
        ROUND(SUM(a.revenue_spp) / NULLIF(SUM(a.full_counts), 0), 2) as revenue_per_unit,
        ROUND(SUM(a.sebes) / NULLIF(SUM(a.full_counts), 0), 2) as sebes_per_unit,
        ROUND(SUM(a.logist) / NULLIF(SUM(a.full_counts), 0), 2) as logist_per_unit,
        ROUND(SUM(a.comis_spp) / NULLIF(SUM(a.full_counts), 0), 2) as commission_per_unit,
        ROUND(SUM(a.storage) / NULLIF(SUM(a.full_counts), 0), 2) as storage_per_unit,
        ROUND(SUM(a.nds) / NULLIF(SUM(a.full_counts), 0), 2) as nds_per_unit,
        ROUND((SUM(a.reclama) + SUM(a.reclama_vn)
            + COALESCE(SUM(a.reclama_vn_vk), 0)
            + COALESCE(SUM(a.reclama_vn_creators), 0))
            / NULLIF(SUM(a.full_counts), 0), 2) as ad_per_unit,
        -- Totals: contribution margin before/after ad
        SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds) as contribution_before_ad,
        SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds)
            - SUM(a.reclama) - SUM(a.reclama_vn)
            - COALESCE(SUM(a.reclama_vn_vk), 0)
            - COALESCE(SUM(a.reclama_vn_creators), 0) as contribution_after_ad,
        -- Per-unit contribution margin
        ROUND((SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds))
            / NULLIF(SUM(a.full_counts), 0), 2) as cm_before_ad_per_unit,
        ROUND((SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds)
            - SUM(a.reclama) - SUM(a.reclama_vn)
            - COALESCE(SUM(a.reclama_vn_vk), 0)
            - COALESCE(SUM(a.reclama_vn_creators), 0))
            / NULLIF(SUM(a.full_counts), 0), 2) as cm_after_ad_per_unit,
        -- Margin %
        ROUND((SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds)
            - SUM(a.reclama) - SUM(a.reclama_vn)
            - COALESCE(SUM(a.reclama_vn_vk), 0)
            - COALESCE(SUM(a.reclama_vn_creators), 0))
            * 100.0 / NULLIF(SUM(a.revenue_spp), 0), 1) as margin_pct,
        -- ROAS by contribution = contribution_before_ad / ad_spend * 100
        ROUND((SUM(a.revenue_spp) - SUM(a.sebes) - SUM(a.logist)
            - SUM(a.comis_spp) - SUM(a.storage) - SUM(a.nds))
            * 100.0 / NULLIF(
                SUM(a.reclama) + SUM(a.reclama_vn)
                + COALESCE(SUM(a.reclama_vn_vk), 0)
                + COALESCE(SUM(a.reclama_vn_creators), 0), 0), 1) as roas_contribution
    FROM abc_date a
    WHERE a.date >= %s AND a.date < %s
        {fin_clause}
    GROUP BY LOWER(a.article)
    HAVING SUM(a.full_counts) > 0
    ORDER BY contribution_after_ad DESC;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_seo_keyword_positions(current_start, prev_start, current_end, artikul_filter=None):
    """Позиции ключевых слов WoW из kz_off.

    Два периода: current (current_start..current_end) vs previous (prev_start..current_start).
    Группировка по LOWER(vendorcode), text (ключевое слово).
    Фильтрует только реальные ключевые слова (содержат хотя бы одну букву).

    Args:
        current_start: начало текущего периода.
        prev_start: начало предыдущего периода.
        current_end: конец текущего периода.
        artikul_filter: список артикулов для фильтрации (опционально).

    Returns:
        list of tuples (period, artikul, keyword, median_pos, freq, opens,
                        add_to_cart, orders, visibility).
    """
    artikul_clause = ""
    params = [current_start, prev_start, current_end]

    if artikul_filter is not None and len(artikul_filter) > 0:
        placeholders = ", ".join(["%s"] * len(artikul_filter))
        artikul_clause = f"AND LOWER(k.vendorcode) IN ({placeholders})"
        params.extend([a.lower() for a in artikul_filter])

    query = f"""
    SELECT
        CASE WHEN k.data >= %s THEN 'current' ELSE 'prev' END as period,
        LOWER(k.vendorcode) as artikul,
        k.text as keyword,
        AVG(k.medianposition_current) as median_pos,
        SUM(k.frequency_current) as freq,
        SUM(k.opencard_current) as opens,
        SUM(k.addtocart_current) as add_to_cart,
        SUM(k.orders_current) as orders,
        AVG(k.visibility_current) as visibility
    FROM kz_off k
    WHERE k.data >= %s AND k.data < %s
        AND k.text ~ '[а-яА-Яa-zA-Z]'
        {artikul_clause}
    GROUP BY 1, LOWER(k.vendorcode), k.text
    ORDER BY period, artikul, freq DESC;
    """
    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, params)
        return cur.fetchall()


def get_wb_search_keywords_api(start_date, end_date, nmids=None):
    """Ключевые слова из WB API /api/v2/search-report/product/search-texts.

    Прямой вызов WB API для получения данных по поисковым запросам.
    Агрегирует данные по обоим кабинетам (ИП и ООО).

    Args:
        start_date: начало периода YYYY-MM-DD.
        end_date: конец периода YYYY-MM-DD.
        nmids: список nmId для фильтрации (опционально).

    Returns:
        list of dicts: [{text, nmId, frequency, openCard, addToCart, orders}, ...]
    """
    import httpx

    WB_SEARCH_API = "https://seller-analytics-api.wildberries.ru/api/v2/search-report/product/search-texts"

    def _extract_metric(item, key):
        val = item.get(key, 0)
        if isinstance(val, dict):
            return int(val.get("current", 0) or 0)
        return int(val or 0)

    # Get API keys from env
    api_key_ip = os.getenv("WB_API_KEY_IP", "")
    api_key_ooo = os.getenv("WB_API_KEY_OOO", "")

    cabinets = []
    if api_key_ip:
        cabinets.append(("IP", api_key_ip, 30))
    if api_key_ooo:
        cabinets.append(("OOO", api_key_ooo, 100))

    all_items = []
    for cab_name, api_key, limit in cabinets:
        payload = {
            "currentPeriod": {"start": start_date, "end": end_date},
            "nmIds": nmids or [],
            "topOrderBy": "openCard",
            "includeSubstitutedSKUs": True,
            "includeSearchTexts": True,
            "orderBy": {"field": "visibility", "mode": "asc"},
            "limit": limit,
        }

        try:
            with httpx.Client(
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                timeout=120.0,
            ) as client:
                resp = client.post(WB_SEARCH_API, json=payload)

            if resp.status_code != 200:
                print(f"[{cab_name}] WB Search API HTTP {resp.status_code}: {resp.text[:200]}")
                continue

            data = resp.json()
            items = data.get("data", {}).get("items", [])

            for item in items:
                all_items.append({
                    "text": item.get("text", ""),
                    "nmId": item.get("nmId", 0),
                    "frequency": _extract_metric(item, "frequency"),
                    "openCard": _extract_metric(item, "openCard"),
                    "addToCart": _extract_metric(item, "addToCart"),
                    "orders": _extract_metric(item, "orders"),
                    "cabinet": cab_name,
                })

            print(f"[{cab_name}] WB Search API: got {len(items)} items")

        except Exception as e:
            print(f"[{cab_name}] WB Search API error: {e}")

    return all_items
