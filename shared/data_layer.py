"""
Общий слой данных: DB-запросы и утилиты.

Извлечено из period_analytics.py для переиспользования
в period_analytics.py и daily_analytics.py.
"""

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from dotenv import load_dotenv

from shared.config import DB_CONFIG, DB_WB, DB_OZON, SUPABASE_ENV_PATH, MARKETPLACE_DB_CONFIG
from shared.model_mapping import get_osnova_sql, map_to_osnova

# =============================================================================
# CONNECTION FACTORY — переключение legacy / managed БД
# =============================================================================
_DATA_SOURCE = os.getenv('DATA_SOURCE', 'legacy')  # 'legacy' | 'managed'


def _get_wb_connection():
    """Get WB database connection (legacy or managed)."""
    if _DATA_SOURCE == 'managed' and MARKETPLACE_DB_CONFIG.get('host'):
        conn = psycopg2.connect(**MARKETPLACE_DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SET search_path TO wb, public")
        return conn
    return psycopg2.connect(**DB_CONFIG, database=DB_WB)


def _get_ozon_connection():
    """Get Ozon database connection (legacy or managed)."""
    if _DATA_SOURCE == 'managed' and MARKETPLACE_DB_CONFIG.get('host'):
        conn = psycopg2.connect(**MARKETPLACE_DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("SET search_path TO ozon, public")
        return conn
    return psycopg2.connect(**DB_CONFIG, database=DB_OZON)


@contextmanager
def _db_cursor(conn_factory):
    """Context manager: гарантирует закрытие cursor и connection при исключении.

    Использование::

        with _db_cursor(_get_wb_connection) as (conn, cur):
            cur.execute(...)
            results = cur.fetchall()
        # cur и conn закрываются автоматически, даже при исключении
    """
    conn = conn_factory()
    cur = conn.cursor()
    try:
        yield conn, cur
    finally:
        cur.close()
        conn.close()


# =============================================================================
# УТИЛИТЫ
# =============================================================================

def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def format_num(num, decimals=0):
    if num is None:
        return "0"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", " ")
    return f"{num:,.{decimals}f}".replace(",", " ")


def format_pct(num):
    if num is None:
        return "0.0%"
    return f"{num:.1f}%"


def get_arrow(change):
    if change > 0.5:
        return "↑"
    elif change < -0.5:
        return "↓"
    return "→"


def calc_change(current, previous):
    if previous == 0 or previous is None:
        return 0
    return ((current - previous) / abs(previous)) * 100


def calc_change_pp(current, previous):
    if current is None or previous is None:
        return 0
    return current - previous


# =============================================================================
# WB ДАННЫЕ
# =============================================================================

WB_MARGIN_SQL = """
    SUM(marga) - SUM(nds) - SUM(reclama_vn)
    - COALESCE(SUM(reclama_vn_vk), 0)
    - COALESCE(SUM(reclama_vn_creators), 0)
"""
# reclama = внутренняя реклама МП (Поиск/Автореклама), reclama_vn = внешняя (блогеры/ВК), reclama_vn_vk = ВК,
# reclama_vn_creators = блогеры — отдельные поля.
# Верифицировано 18.02.2026: расхождение с OneScreen 0.03 руб на 14.9 млн (< 0.001%).
# Поле `marga` уже включает все возвраты (revenue_return_spp, sebes_return и т.д.).


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
    JOIN nomenclature n ON w.nmid = n.nmid
    WHERE w.date >= %s AND w.date < %s
    GROUP BY 1, 2
    ORDER BY 1, 5 DESC;
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


# =============================================================================
# SUPABASE — СТАТУСЫ ТОВАРОВ
# =============================================================================

def get_artikuly_statuses():
    """Получение статусов артикулов из Supabase."""
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT
            a.artikul,
            s.nazvanie as status,
            mo.kod as model_osnova
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        """
        cur.execute(query)
        results = cur.fetchall()

        cur.close()
        conn.close()

        statuses = {}
        for row in results:
            article = row[0]
            status = row[1]
            # Lowercase ключи — WB хранит "wendy/black", Supabase "Wendy/black"
            statuses[article.lower()] = status

        return statuses
    except Exception as e:
        print(f"Предупреждение: не удалось подключиться к Supabase: {e}")
        return {}


# =============================================================================
# ABC-АНАЛИЗ — PER-ARTICLE ДАННЫЕ
# =============================================================================

def get_wb_by_article(start_date, end_date):
    """WB финансы по артикулам (не агрегировано по модели). LOWER() на артикуле и модели."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    # LOWER(article) — в БД встречаются артикулы с разным регистром
    # ("Audrey/black" и "audrey/black"), без LOWER() они попадают в разные группы.
    query = f"""
    SELECT
        LOWER(article) as article,
        {get_osnova_sql("SPLIT_PART(article, '/', 1)")} as model,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue,
        {WB_MARGIN_SQL} as margin,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
        SUM(reclama + reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND article IS NOT NULL AND article != '' AND article != '0'
    GROUP BY 1
    ORDER BY 6 DESC;
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = []
    for r in rows:
        results.append({
            'article': r[0],
            'model': r[1],
            'orders_count': to_float(r[2]),
            'sales_count': to_float(r[3]),
        'revenue': to_float(r[4]),
        'margin': to_float(r[5]),
        'adv_internal': to_float(r[6]),
        'adv_external': to_float(r[7]),
        'adv_total': to_float(r[8]),
    })
    return results


def get_ozon_by_article(start_date, end_date):
    """OZON финансы по артикулам. OZON article содержит размер — агрегируем до уровня артикула."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    # OZON abc_date.article = "Alice/black_L" (с размером).
    # Убираем суффикс размера и приводим к lowercase.
    finance_query = f"""
    SELECT
        LOWER(REGEXP_REPLACE(article, '_[^_]+$', '')) as artikul,
        {get_osnova_sql("SPLIT_PART(REGEXP_REPLACE(article, '_[^_]+$', ''), '/', 1)")} as model,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue,
        SUM(marga) - SUM(nds) as margin,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        SUM(reclama_end + adv_vn) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND article IS NOT NULL AND article != ''
    GROUP BY 1
    ORDER BY 5 DESC;
    """
    cur.execute(finance_query, (start_date, end_date))
    finance_rows = cur.fetchall()

    # Заказы из отдельной таблицы orders
    orders_query = """
    SELECT
        LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) as artikul,
        COUNT(*) as orders_count,
        SUM(price) as orders_rub
    FROM orders
    WHERE in_process_at::date >= %s AND in_process_at::date < %s
    GROUP BY LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', ''));
    """
    cur.execute(orders_query, (start_date, end_date))
    orders_rows = cur.fetchall()

    cur.close()
    conn.close()

    orders_map = {}
    for r in orders_rows:
        orders_map[r[0]] = {'orders_count': to_float(r[1]), 'orders_rub': to_float(r[2])}

    results = []
    for r in finance_rows:
        artikul = r[0]
        om = orders_map.get(artikul, {'orders_count': 0, 'orders_rub': 0})
        results.append({
            'article': artikul,
            'model': r[1],
            'orders_count': om['orders_count'],
            'sales_count': to_float(r[2]),
            'revenue': to_float(r[3]),
            'margin': to_float(r[4]),
            'adv_internal': to_float(r[5]),
            'adv_external': to_float(r[6]),
            'adv_total': to_float(r[7]),
        })
    return results


def get_wb_orders_by_article(start_date, end_date):
    """WB заказы по артикулам (для ср.чека заказов). LOWER() на артикуле."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    SELECT
        LOWER(supplierarticle) as article,
        COUNT(*) as orders_count,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
      AND supplierarticle IS NOT NULL AND supplierarticle != ''
    GROUP BY LOWER(supplierarticle);
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = {}
    for r in rows:
        results[r[0]] = {'orders_count': to_float(r[1]), 'orders_rub': to_float(r[2])}
    return results


def get_wb_avg_stock(start_date, end_date):
    """Средние остатки WB на складах МП за период, по артикулам. LOWER() на артикуле."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    SELECT
        LOWER(supplierarticle) as article,
        AVG(quantityfull) as avg_stock
    FROM stocks
    WHERE lastchangedate >= %s AND lastchangedate < %s
      AND supplierarticle IS NOT NULL AND supplierarticle != ''
    GROUP BY LOWER(supplierarticle);
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {r[0]: to_float(r[1]) for r in rows}


def get_ozon_avg_stock(start_date, end_date):
    """Средние остатки OZON на складах МП за период, по артикулам. LOWER() на артикуле."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    # OZON offer_id содержит размер — агрегируем до артикула
    query = """
    SELECT
        LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) as artikul,
        AVG(stockspresent) as avg_stock
    FROM stocks
    WHERE dateupdate >= %s AND dateupdate < %s
      AND offer_id IS NOT NULL AND offer_id != ''
    GROUP BY LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', ''));
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {r[0]: to_float(r[1]) for r in rows}


def get_total_avg_stock(channel, start_date, end_date):
    """Total average stocks for a channel across all models.

    If no data for the exact period, uses last 7 days before end_date (fallback for ETL delay).
    """
    if channel == "wb":
        conn = _get_wb_connection()
        date_col = "lastchangedate"
        stock_col = "quantityfull"
    else:
        conn = _get_ozon_connection()
        date_col = "dateupdate"
        stock_col = "stockspresent"
    
    cur = conn.cursor()
    query = f"""
    SELECT AVG(daily_total)
    FROM (
        SELECT {date_col}::date, SUM({stock_col}) as daily_total
        FROM stocks
        WHERE {date_col} >= %s AND {date_col} < %s
        GROUP BY 1
    ) t
    """
    cur.execute(query, (start_date, end_date))
    res = cur.fetchone()
    val = to_float(res[0]) if res and res[0] is not None else 0.0
    # Fallback: if no data in period (e.g. single day, ETL delay), use last 7 days
    if val <= 0:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            fallback_start = (end_dt - timedelta(days=7)).strftime('%Y-%m-%d')
            cur.execute(query, (fallback_start, end_date))
            res2 = cur.fetchone()
            val = to_float(res2[0]) if res2 and res2[0] is not None else 0.0
        except (ValueError, Exception):
            pass
    cur.close()
    conn.close()
    return val


def get_artikuly_full_info():
    """Расширенная информация об артикулах из Supabase: статус, цвет, склейка."""
    if os.path.exists(SUPABASE_ENV_PATH):
        load_dotenv(SUPABASE_ENV_PATH)

    supabase_config = {
        'host': os.getenv('POSTGRES_HOST', 'aws-0-eu-central-1.pooler.supabase.com'),
        'port': int(os.getenv('POSTGRES_PORT', 6543)),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

    try:
        conn = psycopg2.connect(**supabase_config)
        cur = conn.cursor()

        query = """
        SELECT DISTINCT ON (a.artikul)
            a.artikul,
            s.nazvanie as status,
            m.kod as model_kod,
            mo.kod as model_osnova,
            c.color_code,
            c.cvet,
            c.color,
            sw.nazvanie as skleyka_wb,
            mo.tip_kollekcii
        FROM artikuly a
        LEFT JOIN statusy s ON a.status_id = s.id
        LEFT JOIN modeli m ON a.model_id = m.id
        LEFT JOIN modeli_osnova mo ON m.model_osnova_id = mo.id
        LEFT JOIN cveta c ON a.cvet_id = c.id
        LEFT JOIN tovary t ON t.artikul_id = a.id
        LEFT JOIN tovary_skleyki_wb tsw ON tsw.tovar_id = t.id
        LEFT JOIN skleyki_wb sw ON tsw.skleyka_id = sw.id
        ORDER BY a.artikul, sw.nazvanie
        """
        cur.execute(query)
        rows = cur.fetchall()

        cur.close()
        conn.close()

        result = {}
        for r in rows:
            artikul = r[0]
            result[artikul.lower()] = {
                'status': r[1],
                'model_kod': r[2],
                'model_osnova': r[3],
                'color_code': r[4],
                'cvet': r[5],
                'color': r[6],
                'skleyka_wb': r[7],
                'tip_kollekcii': r[8],
            }
        return result
    except Exception as e:
        print(f"Предупреждение: не удалось подключиться к Supabase: {e}")
        return {}


# =============================================================================
# ПРОВЕРКА КАЧЕСТВА ДАННЫХ
# =============================================================================

def validate_wb_data_quality(target_date):
    """
    Проверяет WB данные на известные проблемы качества.
    Возвращает dict с предупреждениями и корректировками маржи.

    Известные проблемы:
    - retention == deduction (дубликация пайплайна) → маржа занижена на SUM(deduction)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    warnings = []
    margin_adjustment = 0.0

    # Проверка: retention == deduction в каждой строке
    cur.execute("""
    SELECT
        COUNT(*) as total_rows,
        COUNT(*) FILTER (WHERE retention = deduction AND retention != 0) as dup_rows,
        COUNT(*) FILTER (WHERE retention != 0 OR deduction != 0) as nonzero_rows,
        SUM(retention) as total_retention,
        SUM(deduction) as total_deduction
    FROM abc_date
    WHERE date = %s;
    """, (target_date,))
    row = cur.fetchone()

    total_rows = row[0]
    dup_rows = row[1]
    nonzero_rows = row[2]
    total_retention = to_float(row[3])
    total_deduction = to_float(row[4])

    if nonzero_rows > 0 and dup_rows == nonzero_rows and total_retention == total_deduction and total_retention > 0:
        margin_adjustment = total_deduction  # добавляем обратно дубль
        warnings.append({
            'type': 'retention_deduction_dup',
            'severity': 'CRITICAL',
            'message': f"retention == deduction ({format_num(total_retention)} руб) во всех {dup_rows} строках — дубликация пайплайна. Маржа скорректирована на +{format_num(margin_adjustment)} руб",
            'explanation': (
                'retention — удержания МП (возвраты/брак), deduction — вычеты (штрафы/корректировки). '
                'Одинаковые значения = баг ETL-пайплайна (один столбец скопирован в другой). '
                'Маржа занижена на SUM(deduction). Корректировка: +deduction к марже, deduction обнулён.'
            ),
            'etl_status': 'Требуется исправление на стороне ETL-пайплайна',
            'comparison_note': 'Предыдущий день проверен отдельно — если аналогичная проблема, тоже скорректирован',
            'adjustment': margin_adjustment,
        })

    cur.close()
    conn.close()

    return {'warnings': warnings, 'margin_adjustment': margin_adjustment}


# =============================================================================
# DAILY SERIES — для расчёта volatility и трендов
# =============================================================================

def get_wb_daily_series(target_date, lookback_days=7):
    """Ежедневные метрики WB за N дней (для расчёта volatility, трендов и confidence)."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    start = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    query = f"""
    SELECT
        date,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama + reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_total,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        SUM(spp) as spp_amount,
        {WB_MARGIN_SQL} as margin,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, (start, end))
    results = cur.fetchall()

    cur.close()
    conn.close()

    series = []
    for row in results:
        series.append({
            'date': row[0],
            'orders_count': to_float(row[1]),
            'sales_count': to_float(row[2]),
            'revenue_before_spp': to_float(row[3]),
            'revenue_after_spp': to_float(row[4]),
            'adv_total': to_float(row[5]),
            'cost_of_goods': to_float(row[6]),
            'logistics': to_float(row[7]),
            'storage': to_float(row[8]),
            'commission': to_float(row[9]),
            'spp_amount': to_float(row[10]),
            'margin': to_float(row[11]),
            'adv_internal': to_float(row[12]),
            'adv_external': to_float(row[13]),
        })
    return series


def get_ozon_daily_series(target_date, lookback_days=7):
    """Ежедневные метрики OZON за N дней."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    start = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    query = """
    SELECT
        date,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(reclama_end + adv_vn + COALESCE(adv_vn_vk, 0)) as adv_total,
        SUM(sebes_end) as cost_of_goods,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(comission_end) as commission,
        SUM(spp) as spp_amount,
        SUM(marga) - SUM(nds) as margin
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, (start, end))
    results = cur.fetchall()

    cur.close()
    conn.close()

    series = []
    for row in results:
        series.append({
            'date': row[0],
            'sales_count': to_float(row[1]),
            'revenue_before_spp': to_float(row[2]),
            'revenue_after_spp': to_float(row[3]),
            'adv_total': to_float(row[4]),
            'cost_of_goods': to_float(row[5]),
            'logistics': to_float(row[6]),
            'storage': to_float(row[7]),
            'commission': to_float(row[8]),
            'spp_amount': to_float(row[9]),
            'margin': to_float(row[10]),
        })
    return series


# =============================================================================
# DAILY SERIES (RANGE) — для месячных отчётов
# =============================================================================

def get_wb_daily_series_range(start_date, end_date):
    """Ежедневные метрики WB за произвольный диапазон дат."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        date,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama + reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_total,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        SUM(spp) as spp_amount,
        {WB_MARGIN_SQL} as margin
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, (start_date, end_date))
    results = cur.fetchall()

    cur.close()
    conn.close()

    series = []
    for row in results:
        series.append({
            'date': row[0],
            'orders_count': to_float(row[1]),
            'sales_count': to_float(row[2]),
            'revenue_before_spp': to_float(row[3]),
            'revenue_after_spp': to_float(row[4]),
            'adv_total': to_float(row[5]),
            'cost_of_goods': to_float(row[6]),
            'logistics': to_float(row[7]),
            'storage': to_float(row[8]),
            'commission': to_float(row[9]),
            'spp_amount': to_float(row[10]),
            'margin': to_float(row[11]),
        })
    return series


def get_ozon_daily_series_range(start_date, end_date):
    """Ежедневные метрики OZON за произвольный диапазон дат."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        date,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(reclama_end + adv_vn + COALESCE(adv_vn_vk, 0)) as adv_total,
        SUM(sebes_end) as cost_of_goods,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(comission_end) as commission,
        SUM(spp) as spp_amount,
        SUM(marga) - SUM(nds) as margin
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, (start_date, end_date))
    results = cur.fetchall()

    cur.close()
    conn.close()

    series = []
    for row in results:
        series.append({
            'date': row[0],
            'sales_count': to_float(row[1]),
            'revenue_before_spp': to_float(row[2]),
            'revenue_after_spp': to_float(row[3]),
            'adv_total': to_float(row[4]),
            'cost_of_goods': to_float(row[5]),
            'logistics': to_float(row[6]),
            'storage': to_float(row[7]),
            'commission': to_float(row[8]),
            'spp_amount': to_float(row[9]),
            'margin': to_float(row[10]),
        })
    return series


# =============================================================================
# WEEKLY BREAKDOWN — для месячных отчётов
# =============================================================================

def get_wb_weekly_breakdown(month_start, month_end):
    """WB финансы по неделям внутри месяца."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        date_trunc('week', date)::date as week_start,
        MIN(date) as actual_start,
        MAX(date) as actual_end,
        COUNT(DISTINCT date) as days_in_week,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(reclama + reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_total,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        {WB_MARGIN_SQL} as margin
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date_trunc('week', date)
    ORDER BY week_start;
    """
    cur.execute(query, (month_start, month_end))
    results = cur.fetchall()

    orders_query = """
    SELECT
        date_trunc('week', date)::date as week_start,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
    GROUP BY date_trunc('week', date)
    ORDER BY week_start;
    """
    cur.execute(orders_query, (month_start, month_end))
    orders_results = cur.fetchall()

    cur.close()
    conn.close()

    orders_map = {row[0]: to_float(row[1]) for row in orders_results}

    weeks = []
    for row in results:
        ws = row[0]
        weeks.append({
            'week_start': row[1],
            'week_end': row[2],
            'days': int(row[3]),
            'orders_count': to_float(row[4]),
            'sales_count': to_float(row[5]),
            'revenue_before_spp': to_float(row[6]),
            'adv_total': to_float(row[7]),
            'cost_of_goods': to_float(row[8]),
            'logistics': to_float(row[9]),
            'storage': to_float(row[10]),
            'commission': to_float(row[11]),
            'margin': to_float(row[12]),
            'orders_rub': orders_map.get(ws, 0),
        })
    return weeks


# =============================================================================
# ЦЕНОВАЯ АНАЛИТИКА — данные для регрессии и анализа цен
# =============================================================================

def get_wb_price_margin_daily(start_date, end_date, model=None):
    """
    WB ежедневные данные цена+маржа+объём по моделям — основной датасет для регрессии.

    Гибридный источник:
    - Заказы (qty, суммы, цены) — из таблицы orders (первоисточник API).
    - Расходы, реклама, маржа — из abc_date (таблица подрядчика).

    Для эластичности использовать: orders_count, orders_price_after_spp,
    adv_internal, adv_external.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    model_filter_abc = ""
    model_filter_orders = ""
    params = [start_date, end_date, start_date, end_date]
    if model:
        model_filter_abc = "AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s"
        model_filter_orders = "AND LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s"
        # Добавляем дважды: первый %s — в CTE raw_orders, второй %s — в основном WHERE
        params.append(model.lower())  # для CTE
        params.append(model.lower())  # для abc_date

    query = f"""
    WITH raw_orders AS (
        SELECT
            date::date as dt,
            LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
            COUNT(*) as qty_orders,
            SUM(pricewithdisc::numeric) as sum_before_spp,
            SUM(finishedprice::numeric) as sum_after_spp
        FROM orders
        WHERE date >= %s AND date < %s
            {model_filter_orders}
        GROUP BY 1, 2
    )
    SELECT
        a.date,
        LOWER(SPLIT_PART(a.article, '/', 1)) as model,
        -- Цена за единицу (реализованная, из abc_date для обратной совместимости)
        CASE WHEN SUM(a.full_counts) > 0
            THEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0))
                 / SUM(a.full_counts)
            ELSE NULL END as price_per_unit,
        -- Продажи (выкупы) из abc_date
        SUM(a.full_counts) as sales_count,
        -- Заказы из ПЕРВОИСТОЧНИКА (orders)
        COALESCE(MAX(o.qty_orders), 0) as orders_count,
        COALESCE(MAX(o.sum_before_spp), 0) as orders_sum_before_spp,
        COALESCE(MAX(o.sum_after_spp), 0) as orders_sum_after_spp,
        CASE WHEN COALESCE(MAX(o.qty_orders), 0) > 0
            THEN MAX(o.sum_after_spp) / MAX(o.qty_orders)
            ELSE NULL END as orders_price_after_spp,
        -- Маржа
        {WB_MARGIN_SQL} as margin,
        CASE WHEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) > 0
            THEN ({WB_MARGIN_SQL}) /
                 (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) * 100
            ELSE NULL END as margin_pct,
        -- Выручка
        SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0) as revenue_before_spp,
        -- СПП
        CASE WHEN SUM(a.revenue_spp) > 0
            THEN SUM(a.spp) / SUM(a.revenue_spp) * 100
            ELSE NULL END as spp_pct,
        -- ДРР
        CASE WHEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) > 0
            THEN SUM(a.reclama + a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) /
                 (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) * 100
            ELSE NULL END as drr_pct,
        -- Логистика на единицу
        CASE WHEN SUM(a.full_counts) > 0
            THEN SUM(a.logist) / SUM(a.full_counts)
            ELSE NULL END as logistics_per_unit,
        -- Себестоимость на единицу
        CASE WHEN SUM(a.full_counts) > 0
            THEN SUM(a.sebes) / SUM(a.full_counts)
            ELSE NULL END as cogs_per_unit,
        -- Реклама (из abc_date подрядчика)
        SUM(a.reclama + a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) as adv_total,
        SUM(a.reclama) as adv_internal,
        SUM(a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) as adv_external
    FROM abc_date a
    LEFT JOIN raw_orders o
        ON a.date = o.dt
        AND LOWER(SPLIT_PART(a.article, '/', 1)) = o.model
    WHERE a.date >= %s AND a.date < %s
        {model_filter_abc}
    GROUP BY a.date, LOWER(SPLIT_PART(a.article, '/', 1))
    HAVING SUM(a.full_counts) > 0
    ORDER BY a.date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'date' and key != 'model':
                row[key] = to_float(val)

    return results


def get_ozon_price_margin_daily(start_date, end_date, model=None):
    """
    OZON ежедневные данные цена+маржа+объём по моделям — основной датасет для регрессии.

    Гибридный источник:
    - Заказы (qty, суммы) — из таблицы orders (первоисточник, in_process_at).
    - Расходы, реклама, маржа — из abc_date.

    Для эластичности использовать: orders_count (заказы), sales_count (выкупы).
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    model_filter_abc = ""
    model_filter_orders = ""
    params = [start_date, end_date, start_date, end_date]
    if model:
        model_filter_abc = "AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s"
        model_filter_orders = "AND LOWER(SPLIT_PART(offer_id, '/', 1)) = %s"
        # Добавляем дважды: первый %s — в CTE raw_orders, второй %s — в основном WHERE
        params.append(model.lower())  # для CTE
        params.append(model.lower())  # для abc_date

    query = f"""
    WITH raw_orders AS (
        SELECT
            in_process_at::date as dt,
            LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
            COUNT(*) as qty_orders,
            SUM(price::numeric) as sum_orders
        FROM orders
        WHERE in_process_at::date >= %s AND in_process_at::date < %s
            {model_filter_orders}
        GROUP BY 1, 2
    )
    SELECT
        a.date,
        LOWER(SPLIT_PART(a.article, '/', 1)) as model,
        -- Цена за единицу (реализованная, из abc_date)
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.price_end) / SUM(a.count_end)
            ELSE NULL END as price_per_unit,
        -- Продажи (выкупы) из abc_date
        SUM(a.count_end) as sales_count,
        -- Заказы из ПЕРВОИСТОЧНИКА (orders)
        COALESCE(MAX(o.qty_orders), 0) as orders_count,
        COALESCE(MAX(o.sum_orders), 0) as orders_sum,
        -- Маржа
        SUM(a.marga) - SUM(a.nds) as margin,
        CASE WHEN SUM(a.price_end) > 0
            THEN (SUM(a.marga) - SUM(a.nds)) / SUM(a.price_end) * 100
            ELSE NULL END as margin_pct,
        -- Выручка
        SUM(a.price_end) as revenue_before_spp,
        -- СПП
        CASE WHEN SUM(a.price_end) > 0
            THEN SUM(a.spp) / SUM(a.price_end) * 100
            ELSE NULL END as spp_pct,
        -- ДРР
        CASE WHEN SUM(a.price_end) > 0
            THEN SUM(a.reclama_end + a.adv_vn + COALESCE(a.adv_vn_vk, 0)) / SUM(a.price_end) * 100
            ELSE NULL END as drr_pct,
        -- Логистика на единицу
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.logist_end) / SUM(a.count_end)
            ELSE NULL END as logistics_per_unit,
        -- Себестоимость на единицу
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.sebes_end) / SUM(a.count_end)
            ELSE NULL END as cogs_per_unit,
        -- Реклама (абсолют)
        SUM(a.reclama_end + a.adv_vn + COALESCE(a.adv_vn_vk, 0)) as adv_total,
        SUM(a.reclama_end) as adv_internal,
        SUM(a.adv_vn + COALESCE(a.adv_vn_vk, 0)) as adv_external
    FROM abc_date a
    LEFT JOIN raw_orders o
        ON o.dt = a.date
        AND o.model = LOWER(SPLIT_PART(a.article, '/', 1))
    WHERE a.date >= %s AND a.date < %s
        {model_filter_abc}
    GROUP BY a.date, LOWER(SPLIT_PART(a.article, '/', 1))
    HAVING SUM(a.count_end) > 0
    ORDER BY a.date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'date' and key != 'model':
                row[key] = to_float(val)

    return results


def get_wb_price_changes(start_date, end_date, model=None):
    """
    WB: детекция значимых изменений цены (>3%) через LAG().
    Возвращает дни, когда цена за единицу изменилась более чем на 3%.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    model_filter = ""
    params = [start_date, end_date]
    if model:
        model_filter = "AND LOWER(SPLIT_PART(article, '/', 1)) = %s"
        params.append(model.lower())

    query = f"""
    WITH daily_prices AS (
        SELECT
            date,
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0))
                / NULLIF(SUM(full_counts), 0) as avg_price
        FROM abc_date
        WHERE date >= %s AND date < %s
            {model_filter}
        GROUP BY date, LOWER(SPLIT_PART(article, '/', 1))
        HAVING SUM(full_counts) > 0
    ),
    with_lag AS (
        SELECT
            date, model, avg_price,
            LAG(avg_price) OVER (PARTITION BY model ORDER BY date) as prev_price
        FROM daily_prices
    )
    SELECT
        date, model, avg_price, prev_price,
        (avg_price - prev_price) / NULLIF(prev_price, 0) * 100 as change_pct
    FROM with_lag
    WHERE prev_price IS NOT NULL
      AND ABS(avg_price - prev_price) / NULLIF(prev_price, 0) > 0.03
    ORDER BY date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'date' and key != 'model':
                row[key] = to_float(val)

    return results


def get_ozon_price_changes(start_date, end_date, model=None):
    """
    OZON: детекция значимых изменений цены (>3%) через LAG().
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    model_filter = ""
    params = [start_date, end_date]
    if model:
        model_filter = "AND LOWER(SPLIT_PART(article, '/', 1)) = %s"
        params.append(model.lower())

    query = f"""
    WITH daily_prices AS (
        SELECT
            date,
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            SUM(price_end) / NULLIF(SUM(count_end), 0) as avg_price
        FROM abc_date
        WHERE date >= %s AND date < %s
            {model_filter}
        GROUP BY date, LOWER(SPLIT_PART(article, '/', 1))
        HAVING SUM(count_end) > 0
    ),
    with_lag AS (
        SELECT
            date, model, avg_price,
            LAG(avg_price) OVER (PARTITION BY model ORDER BY date) as prev_price
        FROM daily_prices
    )
    SELECT
        date, model, avg_price, prev_price,
        (avg_price - prev_price) / NULLIF(prev_price, 0) * 100 as change_pct
    FROM with_lag
    WHERE prev_price IS NOT NULL
      AND ABS(avg_price - prev_price) / NULLIF(prev_price, 0) > 0.03
    ORDER BY date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'date' and key != 'model':
                row[key] = to_float(val)

    return results


def get_wb_spp_history_by_model(start_date, end_date, model=None):
    """WB: динамика СПП% по модели по дням."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    model_filter = ""
    params = [start_date, end_date]
    if model:
        model_filter = "AND LOWER(SPLIT_PART(article, '/', 1)) = %s"
        params.append(model.lower())

    query = f"""
    SELECT
        date,
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        CASE WHEN SUM(revenue_spp) > 0
            THEN SUM(spp) / SUM(revenue_spp) * 100
            ELSE 0 END as spp_pct,
        SUM(spp) as spp_amount,
        SUM(revenue_spp) as revenue_gross
    FROM abc_date
    WHERE date >= %s AND date < %s
        {model_filter}
    GROUP BY date, LOWER(SPLIT_PART(article, '/', 1))
    ORDER BY date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'date' and key != 'model':
                row[key] = to_float(val)

    return results


def get_wb_price_margin_by_model_period(start_date, end_date):
    """
    WB: агрегированные цена+маржа по моделям за весь период.
    Используется для quick overview / сравнения моделей.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    model_expr = get_osnova_sql("SPLIT_PART(article, '/', 1)")
    query = f"""
    SELECT
        {model_expr} as model,
        CASE WHEN SUM(full_counts) > 0
            THEN (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0))
                 / SUM(full_counts)
            ELSE NULL END as avg_price_per_unit,
        SUM(full_counts) as sales_count,
        {{WB_MARGIN_SQL}} as margin,
        CASE WHEN (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) > 0
            THEN ({{WB_MARGIN_SQL}}) /
                 (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) * 100
            ELSE NULL END as margin_pct,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue,
        CASE WHEN SUM(revenue_spp) > 0
            THEN SUM(spp) / SUM(revenue_spp) * 100
            ELSE NULL END as spp_pct,
        CASE WHEN (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) > 0
            THEN SUM(reclama + reclama_vn) /
                 (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) * 100
            ELSE NULL END as drr_pct
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY {model_expr}
    HAVING SUM(full_counts) > 0
    ORDER BY margin DESC;
    """
    cur.execute(query, (start_date, end_date))
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'model':
                row[key] = to_float(val)

    return results


def get_ozon_price_margin_by_model_period(start_date, end_date):
    """
    OZON: агрегированные цена+маржа по моделям за весь период.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    model_expr = get_osnova_sql("SPLIT_PART(article, '/', 1)")
    query = f"""
    SELECT
        {model_expr} as model,
        CASE WHEN SUM(count_end) > 0
            THEN SUM(price_end) / SUM(count_end)
            ELSE NULL END as avg_price_per_unit,
        SUM(count_end) as sales_count,
        SUM(marga) - SUM(nds) as margin,
        CASE WHEN SUM(price_end) > 0
            THEN (SUM(marga) - SUM(nds)) / SUM(price_end) * 100
            ELSE NULL END as margin_pct,
        SUM(price_end) as revenue,
        CASE WHEN SUM(price_end) > 0
            THEN SUM(spp) / SUM(price_end) * 100
            ELSE NULL END as spp_pct,
        CASE WHEN SUM(price_end) > 0
            THEN SUM(reclama_end + adv_vn) / SUM(price_end) * 100
            ELSE NULL END as drr_pct
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY {model_expr}
    HAVING SUM(count_end) > 0
    ORDER BY margin DESC;
    """
    cur.execute(query, (start_date, end_date))
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key != 'model':
                row[key] = to_float(val)

    return results


def get_ozon_weekly_breakdown(month_start, month_end):
    """OZON финансы по неделям внутри месяца."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        date_trunc('week', date)::date as week_start,
        MIN(date) as actual_start,
        MAX(date) as actual_end,
        COUNT(DISTINCT date) as days_in_week,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(reclama_end + adv_vn) as adv_total,
        SUM(sebes_end) as cost_of_goods,
        SUM(logist_end) as logistics,
        SUM(storage_end) as storage,
        SUM(comission_end) as commission,
        SUM(marga) - SUM(nds) as margin
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY date_trunc('week', date)
    ORDER BY week_start;
    """
    cur.execute(query, (month_start, month_end))
    results = cur.fetchall()

    orders_query = """
    SELECT
        date_trunc('week', in_process_at::date)::date as week_start,
        COUNT(*) as orders_count,
        SUM(price) as orders_rub
    FROM orders
    WHERE in_process_at::date >= %s AND in_process_at::date < %s
    GROUP BY date_trunc('week', in_process_at::date)
    ORDER BY week_start;
    """
    cur.execute(orders_query, (month_start, month_end))
    orders_results = cur.fetchall()

    cur.close()
    conn.close()

    orders_map = {row[0]: {'count': to_float(row[1]), 'rub': to_float(row[2])} for row in orders_results}

    weeks = []
    for row in results:
        ws = row[0]
        om = orders_map.get(ws, {'count': 0, 'rub': 0})
        weeks.append({
            'week_start': row[1],
            'week_end': row[2],
            'days': int(row[3]),
            'orders_count': om['count'],
            'sales_count': to_float(row[4]),
            'revenue_before_spp': to_float(row[5]),
            'adv_total': to_float(row[6]),
            'cost_of_goods': to_float(row[7]),
            'logistics': to_float(row[8]),
            'storage': to_float(row[9]),
            'commission': to_float(row[10]),
            'margin': to_float(row[11]),
            'orders_rub': om['rub'],
        })
    return weeks


# =============================================================================
# АРТИКУЛЬНЫЕ ДНЕВНЫЕ ДАННЫЕ (для поартикульного регрессионного анализа)
# =============================================================================

def get_wb_price_margin_daily_by_article(start_date, end_date, article=None, model=None):
    """
    WB ежедневные данные цена+маржа+объём по АРТИКУЛАМ (не по модели).

    Гибридный источник:
    - Заказы (qty, суммы, цены) — из таблицы orders (первоисточник API).
    - Расходы, реклама, маржа — из abc_date (таблица подрядчика).

    Для поартикульной эластичности: цветовые варианты внутри модели
    могут иметь разную ценовую чувствительность.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    filters_abc = []
    filters_orders = []
    params = [start_date, end_date, start_date, end_date]
    if article:
        filters_abc.append("AND LOWER(a.article) = %s")
        filters_orders.append("AND LOWER(supplierarticle) = %s")
        params.append(article.lower())
    if model:
        filters_abc.append("AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s")
        filters_orders.append("AND LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s")
        params.append(model.lower())

    filter_abc_sql = " ".join(filters_abc)
    filter_orders_sql = " ".join(filters_orders)

    query = f"""
    WITH raw_orders AS (
        SELECT
            date::date as dt,
            LOWER(supplierarticle) as article,
            COUNT(*) as qty_orders,
            SUM(pricewithdisc::numeric) as sum_before_spp,
            SUM(finishedprice::numeric) as sum_after_spp
        FROM orders
        WHERE date >= %s AND date < %s
            {filter_orders_sql}
        GROUP BY 1, 2
    )
    SELECT
        a.date,
        LOWER(a.article) as article,
        LOWER(SPLIT_PART(a.article, '/', 1)) as model,
        -- Цена за единицу (реализованная, из abc_date)
        CASE WHEN SUM(a.full_counts) > 0
            THEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0))
                 / SUM(a.full_counts)
            ELSE NULL END as price_per_unit,
        -- Продажи (выкупы) из abc_date
        SUM(a.full_counts) as sales_count,
        -- Заказы из ПЕРВОИСТОЧНИКА (orders)
        COALESCE(MAX(o.qty_orders), 0) as orders_count,
        COALESCE(MAX(o.sum_before_spp), 0) as orders_sum_before_spp,
        COALESCE(MAX(o.sum_after_spp), 0) as orders_sum_after_spp,
        CASE WHEN COALESCE(MAX(o.qty_orders), 0) > 0
            THEN MAX(o.sum_after_spp) / MAX(o.qty_orders)
            ELSE NULL END as orders_price_after_spp,
        -- Маржа
        {WB_MARGIN_SQL} as margin,
        CASE WHEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) > 0
            THEN ({WB_MARGIN_SQL}) /
                 (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) * 100
            ELSE NULL END as margin_pct,
        -- Выручка
        SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0) as revenue_before_spp,
        -- СПП
        CASE WHEN SUM(a.revenue_spp) > 0
            THEN SUM(a.spp) / SUM(a.revenue_spp) * 100
            ELSE NULL END as spp_pct,
        -- ДРР
        CASE WHEN (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) > 0
            THEN SUM(a.reclama + a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) /
                 (SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0)) * 100
            ELSE NULL END as drr_pct,
        -- Логистика на единицу
        CASE WHEN SUM(a.full_counts) > 0
            THEN SUM(a.logist) / SUM(a.full_counts)
            ELSE NULL END as logistics_per_unit,
        -- Себестоимость на единицу
        CASE WHEN SUM(a.full_counts) > 0
            THEN SUM(a.sebes) / SUM(a.full_counts)
            ELSE NULL END as cogs_per_unit,
        -- Реклама (из abc_date подрядчика)
        SUM(a.reclama + a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) as adv_total,
        SUM(a.reclama) as adv_internal,
        SUM(a.reclama_vn + COALESCE(a.reclama_vn_vk, 0)) as adv_external
    FROM abc_date a
    LEFT JOIN raw_orders o
        ON a.date = o.dt
        AND LOWER(a.article) = o.article
    WHERE a.date >= %s AND a.date < %s
        AND a.article IS NOT NULL AND a.article != '' AND a.article != '0'
        {filter_abc_sql}
    GROUP BY a.date, LOWER(a.article)
    HAVING SUM(a.full_counts) > 0
    ORDER BY a.date, article;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key not in ('date', 'article', 'model'):
                row[key] = to_float(val)

    return results


def get_ozon_price_margin_daily_by_article(start_date, end_date, article=None, model=None):
    """
    OZON ежедневные данные цена+маржа+объём по АРТИКУЛАМ.

    Гибридный источник:
    - Заказы (qty) — из таблицы orders (первоисточник, in_process_at).
    - Расходы, маржа — из abc_date.

    OZON article содержит размер (_L, _M) — убираем суффикс.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    filters_abc = []
    filters_orders = []
    params = [start_date, end_date, start_date, end_date]
    if article:
        filters_abc.append("AND LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', '')) = %s")
        filters_orders.append("AND LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) = %s")
        params.append(article.lower())
    if model:
        filters_abc.append("AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s")
        filters_orders.append("AND LOWER(SPLIT_PART(offer_id, '/', 1)) = %s")
        params.append(model.lower())

    filter_abc_sql = " ".join(filters_abc)
    filter_orders_sql = " ".join(filters_orders)

    query = f"""
    WITH raw_orders AS (
        SELECT
            in_process_at::date as dt,
            LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) as article,
            COUNT(*) as qty_orders,
            SUM(price::numeric) as sum_orders
        FROM orders
        WHERE in_process_at::date >= %s AND in_process_at::date < %s
            AND offer_id IS NOT NULL AND offer_id != ''
            {filter_orders_sql}
        GROUP BY 1, 2
    )
    SELECT
        a.date,
        LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', '')) as article,
        LOWER(SPLIT_PART(a.article, '/', 1)) as model,
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.price_end) / SUM(a.count_end)
            ELSE NULL END as price_per_unit,
        SUM(a.count_end) as sales_count,
        -- Заказы из ПЕРВОИСТОЧНИКА (orders)
        COALESCE(MAX(o.qty_orders), 0) as orders_count,
        COALESCE(MAX(o.sum_orders), 0) as orders_sum,
        SUM(a.marga) - SUM(a.nds) as margin,
        CASE WHEN SUM(a.price_end) > 0
            THEN (SUM(a.marga) - SUM(a.nds)) / SUM(a.price_end) * 100
            ELSE NULL END as margin_pct,
        SUM(a.price_end) as revenue_before_spp,
        CASE WHEN SUM(a.price_end) > 0
            THEN SUM(a.spp) / SUM(a.price_end) * 100
            ELSE NULL END as spp_pct,
        CASE WHEN SUM(a.price_end) > 0
            THEN SUM(a.reclama_end + a.adv_vn) / SUM(a.price_end) * 100
            ELSE NULL END as drr_pct,
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.logist_end) / SUM(a.count_end)
            ELSE NULL END as logistics_per_unit,
        CASE WHEN SUM(a.count_end) > 0
            THEN SUM(a.sebes_end) / SUM(a.count_end)
            ELSE NULL END as cogs_per_unit,
        SUM(a.reclama_end + a.adv_vn) as adv_total
    FROM abc_date a
    LEFT JOIN raw_orders o
        ON o.dt = a.date
        AND o.article = LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', ''))
    WHERE a.date >= %s AND a.date < %s
        AND a.article IS NOT NULL AND a.article != ''
        {filter_abc_sql}
    GROUP BY a.date, LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', ''))
    HAVING SUM(a.count_end) > 0
    ORDER BY a.date, article;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        for key, val in row.items():
            if key not in ('date', 'article', 'model'):
                row[key] = to_float(val)

    return results


# =============================================================================
# ОБОРАЧИВАЕМОСТЬ ПО МОДЕЛЯМ
# =============================================================================

def get_wb_turnover_by_model(start_date, end_date):
    """
    WB оборачиваемость по моделям = avg_stock / daily_sales.

    Композиция: get_wb_avg_stock() + get_wb_by_article() → агрегация по модели.
    """
    stock_by_article = get_wb_avg_stock(start_date, end_date)
    articles = get_wb_by_article(start_date, end_date)

    days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days)

    # Агрегация по модели
    model_data = {}
    for art in articles:
        model_name = map_to_osnova(art['model'])
        if model_name not in model_data:
            model_data[model_name] = {'sales_count': 0, 'stock_total': 0, 'revenue': 0, 'margin': 0}
        model_data[model_name]['sales_count'] += art['sales_count']
        model_data[model_name]['revenue'] += art['revenue']
        model_data[model_name]['margin'] += art['margin']

    # Добавить остатки (stock по артикулам → агрегация по модели)
    for art_key, stock_val in stock_by_article.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_total'] += stock_val

    result = {}
    for model_name, md in model_data.items():
        daily_sales = md['sales_count'] / days if md['sales_count'] > 0 else 0
        turnover_days = md['stock_total'] / daily_sales if daily_sales > 0 else 0
        result[model_name] = {
            'avg_stock': round(md['stock_total'], 0),
            'daily_sales': round(daily_sales, 1),
            'turnover_days': round(turnover_days, 1),
            'sales_count': md['sales_count'],
            'revenue': round(md['revenue'], 0),
            'margin': round(md['margin'], 0),
        }

    return result


def get_ozon_turnover_by_model(start_date, end_date):
    """
    OZON оборачиваемость по моделям = avg_stock / daily_sales.

    Композиция: get_ozon_avg_stock() + get_ozon_by_article() → агрегация по модели.
    """
    stock_by_article = get_ozon_avg_stock(start_date, end_date)
    articles = get_ozon_by_article(start_date, end_date)

    days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days)

    model_data = {}
    for art in articles:
        model_name = map_to_osnova(art['model'])
        if model_name not in model_data:
            model_data[model_name] = {'sales_count': 0.0, 'stock_total': 0.0, 'revenue': 0.0, 'margin': 0.0}
        model_data[model_name]['sales_count'] += art['sales_count']
        model_data[model_name]['revenue'] += art['revenue']
        model_data[model_name]['margin'] += art['margin']

    for art_key, stock_val in stock_by_article.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_total'] += stock_val

    result = {}
    for model_name, md in model_data.items():
        daily_sales = md['sales_count'] / days if md['sales_count'] > 0 else 0
        turnover_days = md['stock_total'] / daily_sales if daily_sales > 0 else 0
        result[model_name] = {
            'avg_stock': round(md['stock_total'], 0),
            'daily_sales': round(daily_sales, 1),
            'turnover_days': round(turnover_days, 1),
            'sales_count': md['sales_count'],
            'revenue': round(md['revenue'], 0),
            'margin': round(md['margin'], 0),
        }

    return result


# =============================================================================
# ДНЕВНЫЕ ОСТАТКИ ПО МОДЕЛЯМ
# =============================================================================

def get_wb_stock_daily_by_model(start_date, end_date, model=None):
    """
    WB ежедневные остатки по моделям из таблицы stocks.

    Для анализа гипотезы H4: влияние остатков на продажи.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    model_filter = ""
    params = [start_date, end_date]
    if model:
        model_filter = "AND LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s"
        params.append(model.lower())

    query = f"""
    SELECT
        lastchangedate::date as date,
        LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
        SUM(quantityfull) as total_stock
    FROM stocks
    WHERE lastchangedate >= %s AND lastchangedate < %s
        AND supplierarticle IS NOT NULL AND supplierarticle != ''
        {model_filter}
    GROUP BY lastchangedate::date, LOWER(SPLIT_PART(supplierarticle, '/', 1))
    ORDER BY date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        row['total_stock'] = to_float(row['total_stock'])

    return results


def get_ozon_stock_daily_by_model(start_date, end_date, model=None):
    """
    OZON ежедневные остатки по моделям из таблицы stocks.

    Для анализа гипотезы H4: влияние остатков на продажи.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    model_filter = ""
    params = [start_date, end_date]
    if model:
        model_filter = "AND LOWER(SPLIT_PART(offer_id, '/', 1)) = %s"
        params.append(model.lower())

    query = f"""
    SELECT
        dateupdate::date as date,
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
        SUM(stockspresent) as total_stock
    FROM stocks
    WHERE dateupdate >= %s AND dateupdate < %s
        AND offer_id IS NOT NULL AND offer_id != ''
        {model_filter}
    GROUP BY dateupdate::date, LOWER(SPLIT_PART(offer_id, '/', 1))
    ORDER BY date, model;
    """
    cur.execute(query, params)
    columns = [desc[0] for desc in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    for row in results:
        row['total_stock'] = to_float(row['total_stock'])

    return results


# ============================================================
# Фин данные: WB + OZON по баркодам (для листа "Фин данные")
# ============================================================


def get_wb_barcode_to_marketplace_mapping():
    """Build non-marketplace → marketplace barcode mapping from WB nomenclature.

    abc_date splits data across multiple barcode formats per product:
    - Marketplace (20xx): sales + financial data
    - GS2 (468xx): orders data
    - GS1/EAN (460-467xx): additional sales/financial data

    This mapping remaps ALL non-marketplace barcodes to their marketplace
    equivalent so data merges into a single entry per product.

    Returns dict[non_marketplace_barcode_str -> marketplace_barcode_str].
    """
    conn = _get_wb_connection()
    cur = conn.cursor()
    query = """
    WITH grouped AS (
        SELECT nmid, techsize, lk,
               array_agg(DISTINCT barcod) FILTER (WHERE LEFT(barcod, 2) = '20') AS mkt,
               array_agg(DISTINCT barcod) FILTER (WHERE LEFT(barcod, 2) != '20') AS non_mkt
        FROM nomenclature
        WHERE barcod IS NOT NULL AND barcod != ''
        GROUP BY nmid, techsize, lk
        HAVING array_length(array_agg(DISTINCT barcod) FILTER (WHERE LEFT(barcod, 2) = '20'), 1) > 0
           AND array_length(array_agg(DISTINCT barcod) FILTER (WHERE LEFT(barcod, 2) != '20'), 1) > 0
    )
    SELECT unnest(non_mkt) as src_bc, mkt[1] as mkt_bc
    FROM grouped;
    """
    cur.execute(query)
    mapping = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    cur.close()
    conn.close()
    print(f"[data_layer] barcode→marketplace mapping: {len(mapping)} entries")
    return mapping


# Backward-compatible alias
get_wb_gs2_to_marketplace_mapping = get_wb_barcode_to_marketplace_mapping


def get_wb_fin_data_by_barcode(start_date, end_date):
    """WB финансы по баркодам для листа 'Фин данные'. LOWER() на артикуле и модели."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = f"""
    SELECT
        barcode,
        nm_id,
        MIN(LOWER(article)) as article,
        MIN(LOWER(ts_name)) as ts_name,
        lk,
        SPLIT_PART(MIN(LOWER(article)), '/', 1) as model,
        MIN(date) as min_sale_date,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) as revenue_before_spp_gross,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(spp) as spp_amount,
        COALESCE(SUM(revenue_return_spp), 0) as returns_revenue,
        SUM(comis_spp) as commission,
        SUM(logist) as logistics,
        SUM(sebes) as cost_of_goods,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
        COALESCE(SUM(reclama_vn_vk), 0) as adv_vk,
        COALESCE(SUM(reclama_vn_creators), 0) as adv_creators,
        SUM(storage) as storage,
        SUM(nds) as nds,
        SUM(penalty) as penalty,
        SUM(retention) as retention,
        SUM(deduction) as deduction,
        {WB_MARGIN_SQL} as margin,
        SUM(counts_sam) as self_purchase_count
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND barcode IS NOT NULL AND barcode != ''
    GROUP BY barcode, nm_id, lk
    ORDER BY {WB_MARGIN_SQL} DESC;
    """
    cur.execute(query, (start_date, end_date))
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = []
    for r in rows:
        row = dict(zip(columns, r))
        for key in row:
            if key not in ('barcode', 'article', 'ts_name', 'lk', 'model', 'min_sale_date'):
                row[key] = to_float(row[key])
        results.append(row)
    return results


def get_wb_orders_by_barcode(start_date, end_date):
    """WB заказы по баркодам (для ср.чека заказов). Возвращает dict[barcode -> {...}]."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    SELECT
        barcode,
        COUNT(*) as orders_count,
        SUM(pricewithdisc) as orders_rub
    FROM orders
    WHERE date >= %s AND date < %s
      AND barcode IS NOT NULL AND barcode != ''
      AND (iscancel IS NULL OR iscancel = '0' OR iscancel = 'false')
    GROUP BY barcode;
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = {}
    for r in rows:
        result[str(r[0])] = {
            'orders_count': to_float(r[1]),
            'orders_rub': to_float(r[2]),
        }
    return result


def get_ozon_fin_data_by_barcode(start_date, end_date):
    """OZON финансы по баркодам. JOIN с nomenclature для получения barcode."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        COALESCE(n.barcode, a.article) as barcode,
        a.article as ozon_article,
        LOWER(SPLIT_PART(REGEXP_REPLACE(a.article, '_[^_]+$', ''), '/', 1)) as model,
        a.lk,
        MIN(a.date) as min_sale_date,
        SUM(a.count_end) as sales_count,
        SUM(a.price_end) as revenue_before_spp,
        SUM(a.price_end_spp) as revenue_after_spp,
        SUM(a.spp) as spp_amount,
        SUM(a.count_return) as returns_count,
        SUM(a.return_end) as returns_revenue,
        SUM(a.comission_end) as commission,
        SUM(a.logist_end) as logistics,
        SUM(a.sebes_end) as cost_of_goods,
        SUM(a.reclama_end) as adv_internal,
        SUM(a.adv_vn + COALESCE(a.adv_vn_vk, 0)) as adv_external,
        COALESCE(SUM(a.adv_vn_vk), 0) as adv_vk,
        COALESCE(SUM(a.adv_vn_creators), 0) as adv_creators,
        SUM(a.storage_end) as storage,
        SUM(a.nds) as nds,
        SUM(a.marga) - SUM(a.nds)
            - COALESCE(SUM(a.adv_vn_vk), 0)
            - COALESCE(SUM(a.adv_vn_creators), 0) as margin
    FROM abc_date a
    LEFT JOIN nomenclature n ON a.article = n.article AND a.lk = n.lk
    WHERE a.date >= %s AND a.date < %s
      AND a.article IS NOT NULL AND a.article != ''
    GROUP BY COALESCE(n.barcode, a.article), a.article, a.lk
    ORDER BY SUM(a.marga) - SUM(a.nds)
            - COALESCE(SUM(a.adv_vn_vk), 0)
            - COALESCE(SUM(a.adv_vn_creators), 0) DESC;
    """
    cur.execute(query, (start_date, end_date))
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    cur.close()
    conn.close()

    results = []
    for r in rows:
        row = dict(zip(columns, r))
        for key in row:
            if key not in ('barcode', 'ozon_article', 'model', 'lk', 'min_sale_date'):
                row[key] = to_float(row[key])
        results.append(row)
    return results


def get_ozon_orders_by_barcode(start_date, end_date):
    """OZON заказы по баркодам. JOIN с nomenclature. Возвращает dict[barcode -> {...}]."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        COALESCE(n.barcode, o.offer_id) as barcode,
        COUNT(*) as orders_count,
        SUM(o.price) as orders_rub
    FROM orders o
    LEFT JOIN nomenclature n ON o.offer_id = n.article
    WHERE o.in_process_at::date >= %s AND o.in_process_at::date < %s
    GROUP BY COALESCE(n.barcode, o.offer_id);
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = {}
    for r in rows:
        barcode = str(r[0]) if r[0] else ''
        if barcode:
            result[barcode] = {
                'orders_count': to_float(r[1]),
                'orders_rub': to_float(r[2]),
            }
    return result


# =============================================================================
# МАРКЕТИНГОВАЯ АНАЛИТИКА — рекламные разрезы, воронки, ROI
# =============================================================================

def get_wb_external_ad_breakdown(current_start, prev_start, current_end, lk=None):
    """WB разбивка рекламных расходов: внутренняя МП (reclama), блогеры (reclama_vn),
    ВК (reclama_vn_vk), creators (reclama_vn_creators). По периодам current/previous.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND lk = %s"
        params.append(lk)

    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn) as adv_bloggers,
        COALESCE(SUM(reclama_vn_vk), 0) as adv_vk,
        COALESCE(SUM(reclama_vn_creators), 0) as adv_creators,
        SUM(reclama) + SUM(reclama_vn)
            + COALESCE(SUM(reclama_vn_vk), 0)
            + COALESCE(SUM(reclama_vn_creators), 0) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
        {lk_clause}
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_external_ad_breakdown(current_start, prev_start, current_end, lk=None):
    """OZON разбивка рекламных расходов: внутренняя (reclama_end), внешняя (adv_vn),
    ВК (adv_vn_vk). По периодам current/previous.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND lk = %s"
        params.append(lk)

    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        COALESCE(SUM(adv_vn_vk), 0) as adv_vk,
        SUM(reclama_end) + SUM(adv_vn)
            + COALESCE(SUM(adv_vn_vk), 0) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
        {lk_clause}
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_organic_vs_paid_funnel(current_start, prev_start, current_end, lk=None):
    """WB воронки: органическая (content_analysis) и платная (wb_adv).

    Органика: card_opens, add_to_cart, orders, buyouts из content_analysis.
    Платная: views, clicks, to_cart, orders, spend из wb_adv.
    lk фильтр применяется только к content_analysis (wb_adv не имеет lk).

    Returns (organic_results, paid_results).
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    lk_clause = ""
    organic_params = [current_start, prev_start, current_end, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND ca.lk = %s"
        organic_params.append(lk)

    organic_query = f"""
    SELECT
        CASE WHEN ca.date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(ca.opencardcount) as card_opens,
        SUM(ca.addtocartcount) as add_to_cart,
        SUM(ca.orderscount) as funnel_orders,
        SUM(ca.buyoutscount) as buyouts,
        CASE WHEN SUM(ca.opencardcount) > 0
            THEN SUM(ca.addtocartcount)::float / SUM(ca.opencardcount) * 100
            ELSE 0 END as card_to_cart_pct,
        CASE WHEN SUM(ca.addtocartcount) > 0
            THEN SUM(ca.orderscount)::float / SUM(ca.addtocartcount) * 100
            ELSE 0 END as cart_to_order_pct,
        CASE WHEN SUM(ca.orderscount) > 0
            THEN SUM(ca.buyoutscount)::float / SUM(ca.orderscount) * 100
            ELSE 0 END as order_to_buyout_pct
    FROM content_analysis ca
    WHERE ca.date >= %s AND ca.date < %s
        AND ca.vendorcode IN (SELECT DISTINCT article FROM abc_date WHERE date >= %s AND date < %s)
        {lk_clause}
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(organic_query, organic_params)
    organic_results = cur.fetchall()

    paid_query = """
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
    cur.execute(paid_query, (current_start, prev_start, current_end))
    paid_results = cur.fetchall()

    cur.close()
    conn.close()
    return organic_results, paid_results


def get_wb_ad_daily_series(start_date, end_date, lk=None):
    """Дневной ряд рекламных метрик WB из wb_adv: date, views, clicks, spend,
    to_cart, orders, CTR, CPC. Одна строка на день.

    wb_adv не имеет колонки lk — параметр lk принимается для совместимости
    интерфейса, но не используется в запросе.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    SELECT
        date,
        SUM(views) as views,
        SUM(clicks) as clicks,
        SUM(sum) as spend,
        SUM(atbs) as to_cart,
        SUM(orders) as orders,
        CASE WHEN SUM(views) > 0 THEN SUM(clicks)::float / SUM(views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(clicks) > 0 THEN SUM(sum) / SUM(clicks) ELSE 0 END as cpc
    FROM wb_adv
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, (start_date, end_date))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_ad_daily_series(start_date, end_date):
    """Дневной ряд рекламных метрик OZON из adv_stats_daily: date, views, clicks,
    orders_count, rk_expense, avg_bid, CTR, CPC.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        operation_date as date,
        SUM(views) as views,
        SUM(clicks) as clicks,
        SUM(orders_count) as orders,
        SUM(rk_expense) as spend,
        AVG(avg_bid) as avg_bid,
        CASE WHEN SUM(views) > 0 THEN SUM(clicks)::float / SUM(views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(clicks) > 0 THEN SUM(rk_expense) / SUM(clicks) ELSE 0 END as cpc
    FROM adv_stats_daily
    WHERE operation_date >= %s AND operation_date < %s
    GROUP BY operation_date
    ORDER BY operation_date;
    """
    cur.execute(query, (start_date, end_date))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_model_ad_roi(current_start, prev_start, current_end, lk=None):
    """ROI рекламы WB по моделям: JOIN wb_adv (расход, заказы рекламные через nomenclature)
    с abc_date (выручка, маржа по модели). lk фильтр на abc_date.

    Возвращает: period, model, ad_spend, ad_orders, revenue, margin, DRR%, ROMI.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end,
              current_start, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND a.lk = %s"
        params.append(lk)

    model_sql = get_osnova_sql("SPLIT_PART(n.vendorcode, '/', 1)")
    model_sql_abc = get_osnova_sql("SPLIT_PART(a.article, '/', 1)")

    query = f"""
    WITH ad_by_model AS (
        SELECT
            CASE WHEN w.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql} as model,
            SUM(w.sum) as ad_spend,
            SUM(w.orders) as ad_orders
        FROM wb_adv w
        JOIN nomenclature n ON w.nmid = n.nmid
        WHERE w.date >= %s AND w.date < %s
        GROUP BY 1, 2
    ),
    fin_by_model AS (
        SELECT
            CASE WHEN a.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql_abc} as model,
            SUM(a.revenue_spp) - COALESCE(SUM(a.revenue_return_spp), 0) as revenue,
            {WB_MARGIN_SQL} as margin
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
            {lk_clause}
        GROUP BY 1, 2
    )
    SELECT
        COALESCE(ad.period, fin.period) as period,
        COALESCE(ad.model, fin.model) as model,
        COALESCE(ad.ad_spend, 0) as ad_spend,
        COALESCE(ad.ad_orders, 0) as ad_orders,
        COALESCE(fin.revenue, 0) as revenue,
        COALESCE(fin.margin, 0) as margin,
        CASE WHEN COALESCE(fin.revenue, 0) > 0
            THEN COALESCE(ad.ad_spend, 0) / fin.revenue * 100
            ELSE NULL END as drr_pct,
        CASE WHEN COALESCE(ad.ad_spend, 0) > 0
            THEN (COALESCE(fin.margin, 0) - COALESCE(ad.ad_spend, 0))
                 / COALESCE(ad.ad_spend, 0) * 100
            ELSE NULL END as romi
    FROM ad_by_model ad
    FULL OUTER JOIN fin_by_model fin
        ON ad.period = fin.period AND ad.model = fin.model
    ORDER BY period DESC, COALESCE(ad.ad_spend, 0) DESC;
    """
    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_model_ad_roi(current_start, prev_start, current_end, lk=None):
    """ROI рекламы OZON по моделям: JOIN ozon_adv_api (расход, заказы по SKU)
    с abc_date (выручка, маржа по модели через article). lk фильтр на abc_date.

    Связь: ozon_adv_api.sku = abc_date.sku (прямая).
    Модель: LOWER(SPLIT_PART(article, '/', 1)).

    Возвращает: period, model, ad_spend, ad_orders, revenue, margin, DRR%, ROMI.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end,
              current_start, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND a.lk = %s"
        params.append(lk)

    model_sql_abc = get_osnova_sql("SPLIT_PART(a.article, '/', 1)")

    query = f"""
    WITH ad_by_sku AS (
        SELECT
            CASE WHEN operation_date >= %s THEN 'current' ELSE 'previous' END as period,
            sku,
            SUM(sum_rev) as ad_spend,
            SUM(orders) as ad_orders
        FROM ozon_adv_api
        WHERE operation_date >= %s AND operation_date < %s
        GROUP BY 1, 2
    ),
    fin_by_model AS (
        SELECT
            CASE WHEN a.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql_abc} as model,
            a.sku,
            SUM(a.price_end) as revenue,
            SUM(a.marga) - SUM(a.nds) as margin
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
            {lk_clause}
        GROUP BY 1, 2, 3
    ),
    joined AS (
        SELECT
            COALESCE(ad.period, fin.period) as period,
            COALESCE(fin.model, 'Unknown') as model,
            COALESCE(ad.ad_spend, 0) as ad_spend,
            COALESCE(ad.ad_orders, 0) as ad_orders,
            COALESCE(fin.revenue, 0) as revenue,
            COALESCE(fin.margin, 0) as margin
        FROM ad_by_sku ad
        FULL OUTER JOIN fin_by_model fin
            ON ad.period = fin.period AND ad.sku = fin.sku
    )
    SELECT
        period,
        model,
        SUM(ad_spend) as ad_spend,
        SUM(ad_orders) as ad_orders,
        SUM(revenue) as revenue,
        SUM(margin) as margin,
        CASE WHEN SUM(revenue) > 0
            THEN SUM(ad_spend) / SUM(revenue) * 100
            ELSE NULL END as drr_pct,
        CASE WHEN SUM(ad_spend) > 0
            THEN (SUM(margin) - SUM(ad_spend)) / SUM(ad_spend) * 100
            ELSE NULL END as romi
    FROM joined
    GROUP BY period, model
    ORDER BY period DESC, SUM(ad_spend) DESC;
    """
    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_ozon_ad_by_sku(current_start, prev_start, current_end):
    """OZON рекламная статистика по SKU из ozon_adv_api: clicks, to_cart, orders,
    spend, CPC, CTR. По периодам current/previous.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN operation_date >= %s THEN 'current' ELSE 'previous' END as period,
        sku,
        SUM(clicks) as clicks,
        SUM(to_cart) as to_cart,
        SUM(orders) as orders,
        SUM(sum_rev) as spend,
        CASE WHEN SUM(clicks) > 0 THEN SUM(sum_rev) / SUM(clicks) ELSE 0 END as cpc,
        SUM(ctr) as ctr_raw
    FROM ozon_adv_api
    WHERE operation_date >= %s AND operation_date < %s
    GROUP BY 1, 2
    ORDER BY period DESC, SUM(sum_rev) DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_campaign_stats(current_start, prev_start, current_end):
    """WB статистика по рекламным кампаниям (name_rk). По периодам current/previous.

    Возвращает: period, campaign, views, clicks, spend, to_cart, orders, CTR, CPC.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        name_rk as campaign,
        SUM(views) as views,
        SUM(clicks) as clicks,
        SUM(sum) as spend,
        SUM(atbs) as to_cart,
        SUM(orders) as orders,
        CASE WHEN SUM(views) > 0 THEN SUM(clicks)::float / SUM(views) * 100 ELSE 0 END as ctr,
        CASE WHEN SUM(clicks) > 0 THEN SUM(sum) / SUM(clicks) ELSE 0 END as cpc
    FROM wb_adv
    WHERE date >= %s AND date < %s
    GROUP BY 1, 2
    ORDER BY period DESC, SUM(sum) DESC;
    """
    cur.execute(query, (current_start, prev_start, current_end))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_ad_budget_utilization(start_date, end_date):
    """Сравнение бюджета (adv_budget) с фактическим расходом (wb_adv).

    Структура adv_budget может варьироваться — используется безопасный запрос
    с TRY/EXCEPT и fallback на пустой результат для бюджетной части.

    Returns (budget_rows, actual_rows) — обе части всегда возвращаются.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Фактический расход из wb_adv — надёжный источник
    actual_query = """
    SELECT
        date,
        SUM(sum) as actual_spend,
        SUM(views) as views,
        SUM(clicks) as clicks,
        SUM(orders) as orders
    FROM wb_adv
    WHERE date >= %s AND date < %s
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(actual_query, (start_date, end_date))
    actual_rows = cur.fetchall()

    # Бюджет из adv_budget — структура таблицы может отличаться,
    # поэтому используем безопасный запрос с fallback.
    budget_rows = []
    try:
        budget_query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'adv_budget'
        ORDER BY ordinal_position;
        """
        cur.execute(budget_query)
        columns = [row[0] for row in cur.fetchall()]

        if columns:
            # Определяем колонку даты и суммы по имени
            date_col = next((c for c in columns if c in ('date', 'dt', 'operation_date', 'created_at')), None)
            sum_col = next((c for c in columns if c in ('budget', 'sum', 'total', 'amount', 'cash')), None)

            if date_col and sum_col:
                safe_query = f"""
                SELECT
                    {date_col}::date as date,
                    SUM({sum_col}) as budget
                FROM adv_budget
                WHERE {date_col}::date >= %s AND {date_col}::date < %s
                GROUP BY {date_col}::date
                ORDER BY {date_col}::date;
                """
                cur.execute(safe_query, (start_date, end_date))
                budget_rows = cur.fetchall()
    except Exception:
        # Если таблица не существует или запрос не удался — возвращаем пустой список
        budget_rows = []

    cur.close()
    conn.close()
    return budget_rows, actual_rows
