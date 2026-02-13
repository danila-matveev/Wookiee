"""
Общий слой данных: DB-запросы и утилиты.

Извлечено из period_analytics.py для переиспользования
в period_analytics.py и daily_analytics.py.
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2
from dotenv import load_dotenv

from oleg_bot.services.db_config import DB_CONFIG, DB_WB, DB_OZON, SUPABASE_ENV_PATH


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
"""
# Формула верифицирована: расхождение с OneScreen < 0.001% (0.23 руб на 239 199).
# Предыдущая 11-полевая формула (revenue_spp - comis - logist - sebes - ...)
# завышала маржу на ~2.5%, т.к. НЕ учитывала возвраты.
# Поле `marga` уже включает все возвраты (revenue_return_spp, sebes_return и т.д.).


def get_wb_finance(current_start, prev_start, current_end):
    """WB финансы с ПРАВИЛЬНОЙ формулой маржи (верифицировано против PowerBI)."""
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn) as adv_external,
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
    """WB финансы по моделям. LOWER() на имени модели для корректной группировки."""
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    # LOWER() — в БД встречаются артикулы с разным регистром ("wendy" и "Wendy"),
    # без LOWER() они попадают в разные группы, что искажает суммы.
    query = f"""
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(reclama + reclama_vn) as adv_total,
        {WB_MARGIN_SQL} as margin
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN w.date >= %s THEN 'current' ELSE 'previous' END as period,
        SPLIT_PART(n.vendorcode, '/', 1) as model,
        SUM(w.views) as ad_views,
        SUM(w.clicks) as ad_clicks,
        SUM(w.sum) as ad_spend,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    # LOWER() — OZON хранит артикулы с Capitalized ("Wendy"), WB — с lowercase ("wendy").
    # Для корректного объединения каналов и группировки нужен единый регистр.
    query = """
    SELECT
        CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
        LOWER(SPLIT_PART(article, '/', 1)) as model,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(reclama_end + adv_vn) as adv_total,
        SUM(marga) - SUM(nds) as margin
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    query = """
    SELECT
        CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
        LOWER(SPLIT_PART(offer_id, '/', 1)) as model,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    # LOWER(article) — в БД встречаются артикулы с разным регистром
    # ("Audrey/black" и "audrey/black"), без LOWER() они попадают в разные группы.
    query = f"""
    SELECT
        LOWER(article) as article,
        LOWER(SPLIT_PART(LOWER(article), '/', 1)) as model,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue,
        {WB_MARGIN_SQL} as margin,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn) as adv_external,
        SUM(reclama + reclama_vn) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND article IS NOT NULL AND article != '' AND article != '0'
    GROUP BY LOWER(article)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    # OZON abc_date.article = "Alice/black_L" (с размером).
    # Убираем суффикс размера и приводим к lowercase.
    finance_query = """
    SELECT
        LOWER(REGEXP_REPLACE(article, '_[^_]+$', '')) as artikul,
        SPLIT_PART(LOWER(REGEXP_REPLACE(article, '_[^_]+$', '')), '/', 1) as model,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue,
        SUM(marga) - SUM(nds) as margin,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external,
        SUM(reclama_end + adv_vn) as adv_total
    FROM abc_date
    WHERE date >= %s AND date < %s
      AND article IS NOT NULL AND article != ''
    GROUP BY LOWER(REGEXP_REPLACE(article, '_[^_]+$', ''))
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
        SUM(reclama + reclama_vn) as adv_total,
        SUM(sebes) as cost_of_goods,
        SUM(logist) as logistics,
        SUM(storage) as storage,
        SUM(comis_spp) as commission,
        SUM(spp) as spp_amount,
        {WB_MARGIN_SQL} as margin,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn) as adv_external
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    start = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    end = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    query = """
    SELECT
        date,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(reclama_end + adv_vn) as adv_total,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
    cur = conn.cursor()

    query = f"""
    SELECT
        date,
        SUM(count_orders) as orders_count,
        SUM(full_counts) as sales_count,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
        SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
        SUM(reclama + reclama_vn) as adv_total,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
    cur = conn.cursor()

    query = """
    SELECT
        date,
        SUM(count_end) as sales_count,
        SUM(price_end) as revenue_before_spp,
        SUM(price_end_spp) as revenue_after_spp,
        SUM(reclama_end + adv_vn) as adv_total,
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
    conn = psycopg2.connect(**DB_CONFIG, database=DB_WB)
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
        SUM(reclama + reclama_vn) as adv_total,
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


def get_ozon_weekly_breakdown(month_start, month_end):
    """OZON финансы по неделям внутри месяца."""
    conn = psycopg2.connect(**DB_CONFIG, database=DB_OZON)
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
