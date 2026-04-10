"""Финансовые запросы WB и OZON.

Функции для получения финансовых данных, данных по моделям и заказов
по моделям для обоих маркетплейсов.
"""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql

__all__ = [
    "get_wb_finance",
    "get_wb_by_model",
    "get_wb_orders_by_model",
    "get_ozon_finance",
    "get_ozon_by_model",
    "get_ozon_orders_by_model",
    "get_wb_buyouts_returns_by_model",
    "get_wb_buyouts_returns_by_artikul",
    "get_wb_buyouts_returns_monthly",
]


def get_wb_finance(current_start, prev_start, current_end):
    """WB финансы с ПРАВИЛЬНОЙ формулой маржи (верифицировано против PowerBI)."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        SUM(spp) as spp_amount,
        SUM(nds) as nds,
        SUM(penalty) as penalty,
        SUM(retention) as retention,
        SUM(deduction) as deduction,
        {WB_MARGIN_SQL} as margin,
        COALESCE(SUM(revenue_return_spp), 0) as returns_revenue,
        SUM(revenue_spp) as revenue_before_spp_gross
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    orders_query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        COUNT(*) as orders_count,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(orders_query, (current_start, prev_start, current_end))
    orders_results = cur.fetchall()

    cur.close()
    conn.close()
    return results, orders_results


def get_wb_by_model(current_start, prev_start, current_end):
    """WB финансы по моделям. LOWER() на имени модели для корректной группировки.

    Реклама: в источнике WB внутренняя реклама (МП) приходит в reclama,
    внешняя (блогеры, ВК) — в reclama_vn; маппинг adv_internal/adv_external приведён в соответствие.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # LOWER() — в БД встречаются артикулы с разным регистром ("wendy" и "Wendy"),
    # без LOWER() они попадают в разные группы, что искажает суммы.
    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(article, '/', 1)")} as model,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
        {WB_MARGIN_SQL} as margin,
        SUM(sebes) as cost_of_goods
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY 1, 2
    ORDER BY 1, 6 DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_orders_by_model(current_start, prev_start, current_end):
    """WB заказы по моделям для расчёта ДРР заказов. LOWER() на модели."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
        COUNT(*) as orders_count,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
    GROUP BY 1, 2
    ORDER BY 1, 4 DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_buyouts_returns_by_model(
    current_start: str, prev_start: str, current_end: str
) -> list[tuple]:
    """Get buyout and return counts by model for WB.

    Uses the orders table to compute:
    - orders_count: total orders
    - buyout_count: orders where isCancel == 0 (not cancelled/returned)
    - return_count: orders where isCancel == 1 (cancelled/returned)

    Args:
        current_start: Start of current period (YYYY-MM-DD)
        prev_start: Start of previous period (YYYY-MM-DD)
        current_end: End of analysis window (YYYY-MM-DD)

    Returns:
        List of (period, model, orders_count, buyout_count, return_count)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC;
    """
    cur.execute(sql, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_buyouts_returns_by_artikul(
    date_from: str, date_to: str
) -> list[tuple]:
    """Get buyout and return counts by artikul (model + color) for WB.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        List of (model, artikul, orders_count, buyout_count, return_count)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            LOWER(supplierarticle) as artikul,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC;
    """
    cur.execute(sql, (date_from, date_to))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_buyouts_returns_monthly(
    date_from: str, date_to: str
) -> list[tuple]:
    """Get buyout and return counts by month and model for WB.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        List of (month, model, orders_count, buyout_count, return_count)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            DATE_TRUNC('month', date)::date as month,
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 2;
    """
    cur.execute(sql, (date_from, date_to))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


# =============================================================================
# OZON ДАННЫЕ
# =============================================================================

def get_ozon_finance(current_start, prev_start, current_end):
    """OZON финансы. Маржа = marga - nds (верифицировано)."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        SUM(marga) - SUM(nds) as margin,
        SUM(sebes_end) as cost_of_goods,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(comission_end) as commission,
        SUM(spp) as spp_amount,
        SUM(nds) as nds
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    orders_query = """
    SELECT
        CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
        COUNT(*) as orders_count,
        SUM(price) as orders_rub
    FROM orders
    WHERE in_process_at::date >= %s AND in_process_at::date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(orders_query, (current_start, prev_start, current_end))
    orders_results = cur.fetchall()

    cur.close()
    conn.close()
    return results, orders_results


def get_ozon_by_model(current_start, prev_start, current_end):
    """OZON финансы по моделям. LOWER() на имени модели для корректной группировки."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    # LOWER() — OZON хранит артикулы с Capitalized ("Wendy"), WB — с lowercase ("wendy").
    # Для корректного объединения каналов и группировки нужен единый регистр.
    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(article, '/', 1)")} as model,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        SUM(marga) - SUM(nds) as margin,
        SUM(sebes_end) as cost_of_goods
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY 1, 2
    ORDER BY 1, 6 DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_orders_by_model(current_start, prev_start, current_end):
    """OZON заказы по моделям для расчёта ДРР заказов. LOWER() на модели."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(offer_id, '/', 1)")} as model,
        COUNT(*) as orders_count,
        SUM(price) as orders_rub
    FROM orders
    WHERE in_process_at::date >= %s AND in_process_at::date < %s
    GROUP BY 1, 2
    ORDER BY 1, 4 DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
