"""Traffic-related queries for WB and OZON (funnel, ads, clicks)."""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection
from shared.model_mapping import get_osnova_sql

__all__ = [
    "get_wb_traffic",
    "get_wb_traffic_by_model",
    "get_ozon_traffic",
]


def get_wb_traffic(current_start, prev_start, current_end):
    """WB воронка и рекламный трафик."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Фильтруем content_analysis только по артикулам, которые есть в abc_date (финансовых данных).
    # Без фильтра content_analysis может содержать vendorcode'ы не принадлежащие бренду,
    # что завышает просмотры/корзины/заказы по сравнению с PowerBI.
    content_query = """
    SELECT
        CASE WHEN ca.date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(ca.opencardcount) as card_opens,
        SUM(ca.addtocartcount) as add_to_cart,
        SUM(ca.orderscount) as funnel_orders,
        SUM(ca.buyoutscount) as buyouts
    FROM content_analysis ca
    WHERE ca.date >= %s AND ca.date < %s
        AND ca.vendorcode IN (SELECT DISTINCT article FROM abc_date WHERE date >= %s AND date < %s)
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(content_query, (current_start, prev_start, current_end, prev_start, current_end))
    content_results = cur.fetchall()

    adv_query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(views) as ad_views,
        SUM(clicks) as ad_clicks,
        SUM(atbs) as ad_to_cart,
        SUM(orders) as ad_orders,
        SUM(sum) as ad_spend,
        CASE WHEN SUM(views) > 0 THEN SUM(clicks)::float / SUM(views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(clicks) > 0 THEN SUM(sum) / SUM(clicks) ELSE 0 END as cpc
    FROM wb_adv
    WHERE date >= %s AND date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(adv_query, (current_start, prev_start, current_end))
    adv_results = cur.fetchall()

    cur.close()
    conn.close()
    return content_results, adv_results


def get_wb_traffic_by_model(current_start, prev_start, current_end):
    """WB рекламный трафик по моделям через JOIN с nomenclature."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN w.date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(n.vendorcode, '/', 1)")} as model,
        SUM(w.views) as ad_views,
        SUM(w.clicks) as ad_clicks,
        SUM(w.sum) as ad_spend,
        SUM(w.atbs) as ad_to_cart,
        SUM(w.orders) as ad_orders,
        CASE WHEN SUM(w.views) > 0 THEN SUM(w.clicks)::float / SUM(w.views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(w.clicks) > 0 THEN SUM(w.sum) / SUM(w.clicks) ELSE 0 END as cpc
    FROM wb_adv w
    JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n ON w.nmid = n.nmid
    WHERE w.date >= %s AND w.date < %s
    GROUP BY 1, 2
    ORDER BY 1, 5 DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_traffic(current_start, prev_start, current_end):
    """OZON рекламный трафик."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN operation_date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(views) as ad_views,
        SUM(clicks) as ad_clicks,
        SUM(orders_count) as ad_orders,
        SUM(rk_expense) as ad_spend,
        CASE WHEN SUM(views) > 0 THEN SUM(clicks)::float / SUM(views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(clicks) > 0 THEN SUM(rk_expense) / SUM(clicks) ELSE 0 END as cpc
    FROM adv_stats_daily
    WHERE operation_date >= %s AND operation_date < %s
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
