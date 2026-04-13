"""Traffic-related queries for WB and OZON (funnel, ads, clicks)."""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection
from shared.model_mapping import get_osnova_sql

__all__ = [
    "get_wb_traffic",
    "get_wb_traffic_by_model",
    "get_wb_content_analysis_by_model",
    "get_wb_skleyka_halo",
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


def get_wb_content_analysis_by_model(current_start, prev_start, current_end):
    """WB воронка по моделям из content_analysis (ВСЕ источники трафика).

    Returns per-model funnel: card_opens, add_to_cart, orders, buyouts.
    This is the correct source for CRO calculation (not wb_adv which is ads-only).
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN ca.date >= %s THEN 'current' ELSE 'previous' END as period,
        {get_osnova_sql("SPLIT_PART(ca.vendorcode, '/', 1)")} as model,
        SUM(ca.opencardcount) as card_opens,
        SUM(ca.addtocartcount) as add_to_cart,
        SUM(ca.orderscount) as funnel_orders,
        SUM(ca.buyoutscount) as buyouts
    FROM content_analysis ca
    WHERE ca.date >= %s AND ca.date < %s
        AND ca.vendorcode IN (
            SELECT DISTINCT article FROM abc_date
            WHERE date >= %s AND date < %s
        )
    GROUP BY 1, 2
    ORDER BY 1, SUM(ca.orderscount) DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_skleyka_halo(current_start: str, current_end: str) -> list[dict]:
    """Halo-эффект рекламы через склейки WB.

    Для каждой склейки считает:
    - ad_spend на артикулы внутри склейки (из wb_adv)
    - ad_orders — заказы с рекламы конкретных артикулов
    - total_sales — все продажи по всем артикулам склейки (abc_date)
    - direct_drr = ad_spend / revenue рекламных артикулов
    - skleyka_drr = ad_spend / revenue всей склейки
    - halo_coefficient = direct_drr / skleyka_drr (>1 = реклама эффективнее чем кажется)

    Подключение: Supabase (skleyki_wb, artikuly) + WB DB (wb_adv, abc_date).
    """
    import os
    import psycopg2 as pg2
    from dotenv import load_dotenv
    load_dotenv('sku_database/.env')

    # Step 1: Get skleyka -> artikul mapping from Supabase
    sb_conn = pg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
    )
    sb_cur = sb_conn.cursor()

    sb_cur.execute("""
        SELECT sw.nazvanie, array_agg(DISTINCT LOWER(a.artikul))
        FROM public.skleyki_wb sw
        JOIN public.tovary_skleyki_wb tsw ON sw.id = tsw.skleyka_id
        JOIN public.tovary t ON tsw.tovar_id = t.id
        JOIN public.artikuly a ON a.id = t.artikul_id
        GROUP BY sw.nazvanie
        ORDER BY sw.nazvanie
    """)
    skleyka_map = {row[0]: row[1] for row in sb_cur.fetchall()}
    sb_cur.close()
    sb_conn.close()

    if not skleyka_map:
        return []

    # Step 2: For each skleyka, query WB DB
    wb_conn = _get_wb_connection()
    wb_cur = wb_conn.cursor()

    results = []
    for sk_name, articles in skleyka_map.items():
        if not articles:
            continue

        placeholders = ','.join(['%s'] * len(articles))

        # Ad spend on articles in this skleyka
        wb_cur.execute(f"""
            SELECT
                COALESCE(SUM(w.sum), 0) as ad_spend,
                COALESCE(SUM(w.orders), 0) as ad_orders
            FROM wb_adv w
            JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n ON w.nmid = n.nmid
            WHERE w.date >= %s AND w.date < %s
                AND LOWER(SPLIT_PART(n.vendorcode, '/', 1) || '/' || SPLIT_PART(n.vendorcode, '/', 2))
                    IN ({placeholders})
        """, [current_start, current_end] + articles)
        ad_row = wb_cur.fetchone()
        ad_spend = float(ad_row[0] or 0)
        ad_orders = int(ad_row[1] or 0)

        if ad_spend < 100:
            continue

        # Total orders/revenue/margin across ALL articles in skleyka
        wb_cur.execute(f"""
            SELECT
                COALESCE(SUM(full_counts), 0) as total_orders,
                COALESCE(SUM(revenue_spp), 0) as total_revenue,
                COALESCE(SUM(marga), 0) as total_margin
            FROM abc_date
            WHERE date >= %s AND date < %s
                AND LOWER(SPLIT_PART(article, '/', 1) || '/' || SPLIT_PART(article, '/', 2))
                    IN ({placeholders})
        """, [current_start, current_end] + articles)
        total_row = wb_cur.fetchone()
        total_orders = int(total_row[0] or 0)
        total_revenue = float(total_row[1] or 0)
        total_margin = float(total_row[2] or 0)

        if total_revenue < 1:
            continue

        skleyka_drr = ad_spend / total_revenue * 100
        # Determine dominant models
        models_in_sk = set()
        for art in articles:
            parts = art.split('/')
            if parts:
                models_in_sk.add(parts[0].replace('_', ' ').title())

        results.append({
            'skleyka': sk_name,
            'models': sorted(models_in_sk),
            'articles_count': len(articles),
            'ad_spend': round(ad_spend, 0),
            'ad_orders': ad_orders,
            'total_orders': total_orders,
            'total_revenue': round(total_revenue, 0),
            'total_margin': round(total_margin, 0),
            'skleyka_drr': round(skleyka_drr, 1),
            'halo_note': f'Реклама на {ad_orders} шт из {total_orders} шт заказов склейки',
        })

    wb_cur.close()
    wb_conn.close()

    results.sort(key=lambda x: x['ad_spend'], reverse=True)
    return results


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
