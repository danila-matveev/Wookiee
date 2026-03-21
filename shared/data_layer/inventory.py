"""Inventory queries: stocks, turnover, daily stock levels.

Functions for WB / OZON / MoySklad stock snapshots, turnover by model /
submodel, sales-trend analysis, and daily-stock breakdowns.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from shared.data_layer._connection import (
    _get_wb_connection,
    _get_ozon_connection,
    to_float,
)
from shared.data_layer._sql_fragments import MAX_TURNOVER_DAYS, MIN_DAILY_SALES
from shared.model_mapping import get_osnova_sql, map_to_osnova

logger = logging.getLogger(__name__)

__all__ = [
    "get_wb_avg_stock",
    "get_ozon_avg_stock",
    "get_moysklad_stock_by_article",
    "get_total_avg_stock",
    "get_wb_sales_trend_by_model",
    "get_ozon_sales_trend_by_model",
    "_get_days_in_stock_by_model",
    "get_wb_turnover_by_model",
    "get_ozon_turnover_by_model",
    "get_wb_turnover_by_submodel",
    "get_wb_stock_daily_by_model",
    "get_ozon_stock_daily_by_model",
    "get_moysklad_stock_by_model",
]


def get_wb_avg_stock(start_date, end_date):
    """Остатки WB FBO на последнюю дату периода, по артикулам. LOWER() на артикуле.

    Берём последний доступный снапшот за период, дедуплицируем по
    (barcode, warehousename) и суммируем до артикула.
    Фильтруем tip='FBO' (исключаем FBS).
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    query = """
    WITH latest_date AS (
        SELECT MAX(lastchangedate::date) as d
        FROM stocks
        WHERE lastchangedate >= %s AND lastchangedate < %s
    ),
    deduped AS (
        SELECT
            LOWER(supplierarticle) as article,
            barcode,
            warehousename,
            MAX(quantityfull) as qty
        FROM stocks, latest_date
        WHERE lastchangedate::date = latest_date.d
          AND supplierarticle IS NOT NULL AND supplierarticle != ''
          AND tip = 'FBO'
        GROUP BY LOWER(supplierarticle), barcode, warehousename
    )
    SELECT article, SUM(qty) as stock
    FROM deduped
    GROUP BY article;
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {r[0]: to_float(r[1]) for r in rows}


def get_ozon_avg_stock(start_date, end_date):
    """Остатки OZON FBO на последнюю дату периода, по артикулам. LOWER() на артикуле.

    Берём последний доступный снапшот за период, дедуплицируем по
    (offer_id, warehouse_id) и суммируем до артикула.
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    # OZON offer_id содержит размер — агрегируем до артикула
    query = """
    WITH latest_date AS (
        SELECT MAX(dateupdate::date) as d
        FROM stocks
        WHERE dateupdate >= %s AND dateupdate < %s
    ),
    deduped AS (
        SELECT
            LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) as artikul,
            offer_id,
            warehouse_id,
            MAX(stockspresent) as qty
        FROM stocks, latest_date
        WHERE dateupdate::date = latest_date.d
          AND offer_id IS NOT NULL AND offer_id != ''
        GROUP BY 1, offer_id, warehouse_id
    )
    SELECT artikul, SUM(qty) as stock
    FROM deduped
    GROUP BY artikul;
    """
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {r[0]: to_float(r[1]) for r in rows}


def get_moysklad_stock_by_article(max_staleness_days: int = 3):
    """Текущие остатки из МойСклад (ms_stocks): основной склад + товары в пути.

    Берёт ПОСЛЕДНИЙ снэпшот (MAX(dateupdate)).
    Returns: {article_lower: {'stock_main': N, 'stock_transit': M, 'total': N+M,
              'snapshot_date': str, 'is_stale': bool}}
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Проверяем свежесть данных
    cur.execute("SELECT MAX(dateupdate) FROM ms_stocks")
    max_date_row = cur.fetchone()
    snapshot_date = max_date_row[0] if max_date_row else None
    is_stale = True
    if snapshot_date:
        if isinstance(snapshot_date, str):
            snap_dt = datetime.strptime(snapshot_date[:10], '%Y-%m-%d')
        else:
            snap_dt = snapshot_date if isinstance(snapshot_date, datetime) else datetime.combine(snapshot_date, datetime.min.time())
        is_stale = (datetime.now() - snap_dt).days > max_staleness_days
        if is_stale:
            logger.warning(
                "МойСклад данные устарели: снэпшот от %s (> %d дней)",
                snapshot_date, max_staleness_days,
            )

    query = """
    SELECT
        LOWER(article) as art,
        sklad,
        SUM(stock) as total_stock
    FROM ms_stocks
    WHERE dateupdate = (SELECT MAX(dateupdate) FROM ms_stocks)
      AND sklad IN ('Основной склад', 'Товары в пути')
      AND article IS NOT NULL AND article != ''
    GROUP BY LOWER(article), sklad;
    """
    cur.execute(query)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = {}
    for art, sklad, stock in rows:
        if art not in result:
            result[art] = {
                'stock_main': 0.0, 'stock_transit': 0.0, 'total': 0.0,
                'snapshot_date': str(snapshot_date)[:10] if snapshot_date else None,
                'is_stale': is_stale,
            }
        val = to_float(stock)
        if sklad == 'Основной склад':
            result[art]['stock_main'] = val
        else:
            result[art]['stock_transit'] = val
        result[art]['total'] += val

    return result


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


def get_wb_sales_trend_by_model(start_date: str, end_date: str) -> dict:
    """Тренд продаж WB по моделям: сравнение первой и второй половины периода.

    Returns: {model: {'first_half_daily': float, 'second_half_daily': float,
                      'growth_pct': float, 'trend': 'growth'|'decline'|'stable'}}
    """
    conn = _get_wb_connection()
    cur = conn.cursor()
    query = """
    WITH period AS (
        SELECT %s::date as s, %s::date as e,
               %s::date + ((%s::date - %s::date) / 2) as mid
    ),
    weekly AS (
        SELECT
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            CASE WHEN date < (SELECT mid FROM period) THEN 'first' ELSE 'second' END as half,
            SUM(full_counts) as sales,
            COUNT(DISTINCT date) as days
        FROM abc_date, period
        WHERE date >= period.s AND date < period.e
          AND article IS NOT NULL AND article != ''
        GROUP BY 1, 2
    )
    SELECT model, half, sales, days
    FROM weekly
    WHERE days > 0
    ORDER BY model, half;
    """
    cur.execute(query, (start_date, end_date, start_date, end_date, start_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    raw = defaultdict(dict)
    for model, half, sales, days in rows:
        mapped = map_to_osnova(model)
        raw[mapped][half] = {'sales': to_float(sales) + raw[mapped].get(half, {}).get('sales', 0),
                             'days': max(int(days), raw[mapped].get(half, {}).get('days', 0))}

    result = {}
    for model, halves in raw.items():
        first = halves.get('first', {})
        second = halves.get('second', {})
        d1 = first.get('sales', 0) / max(first.get('days', 1), 1)
        d2 = second.get('sales', 0) / max(second.get('days', 1), 1)
        growth = ((d2 - d1) / d1 * 100) if d1 > 0 else (100.0 if d2 > 0 else 0)
        trend = 'growth' if growth > 15 else ('decline' if growth < -15 else 'stable')
        result[model] = {
            'first_half_daily': round(d1, 2),
            'second_half_daily': round(d2, 2),
            'growth_pct': round(growth, 1),
            'trend': trend,
        }
    return result


def get_ozon_sales_trend_by_model(start_date: str, end_date: str) -> dict:
    """Тренд продаж OZON по моделям: сравнение первой и второй половины периода."""
    conn = _get_ozon_connection()
    cur = conn.cursor()
    # OZON abc_date использует count_end (не full_counts как WB)
    query = """
    WITH period AS (
        SELECT %s::date as s, %s::date as e,
               %s::date + ((%s::date - %s::date) / 2) as mid
    ),
    weekly AS (
        SELECT
            LOWER(SPLIT_PART(article, '/', 1)) as model,
            CASE WHEN date < (SELECT mid FROM period) THEN 'first' ELSE 'second' END as half,
            SUM(count_end) as sales,
            COUNT(DISTINCT date) as days
        FROM abc_date, period
        WHERE date >= period.s AND date < period.e
          AND article IS NOT NULL AND article != ''
        GROUP BY 1, 2
    )
    SELECT model, half, sales, days
    FROM weekly
    WHERE days > 0
    ORDER BY model, half;
    """
    cur.execute(query, (start_date, end_date, start_date, end_date, start_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    raw = defaultdict(dict)
    for model, half, sales, days in rows:
        mapped = map_to_osnova(model)
        raw[mapped][half] = {'sales': to_float(sales) + raw[mapped].get(half, {}).get('sales', 0),
                             'days': max(int(days), raw[mapped].get(half, {}).get('days', 0))}

    result = {}
    for model, halves in raw.items():
        first = halves.get('first', {})
        second = halves.get('second', {})
        d1 = first.get('sales', 0) / max(first.get('days', 1), 1)
        d2 = second.get('sales', 0) / max(second.get('days', 1), 1)
        growth = ((d2 - d1) / d1 * 100) if d1 > 0 else (100.0 if d2 > 0 else 0)
        trend = 'growth' if growth > 15 else ('decline' if growth < -15 else 'stable')
        result[model] = {
            'first_half_daily': round(d1, 2),
            'second_half_daily': round(d2, 2),
            'growth_pct': round(growth, 1),
            'trend': trend,
        }
    return result


def _get_days_in_stock_by_model(channel: str, start_date: str, end_date: str) -> dict:
    """Количество дней наличия товара на складе МП, по моделям.

    Считает количество DISTINCT дат, когда у модели был ненулевой остаток.
    Используется для расчёта daily_sales = sales / days_in_stock (а не calendar_days).
    """
    if channel == 'wb':
        conn = _get_wb_connection()
        query = """
        SELECT LOWER(SPLIT_PART(supplierarticle, '/', 1)) as model,
               COUNT(DISTINCT lastchangedate::date) as days_in_stock
        FROM stocks
        WHERE lastchangedate >= %s AND lastchangedate < %s
          AND supplierarticle IS NOT NULL AND supplierarticle != ''
          AND quantityfull > 0
        GROUP BY 1;
        """
    else:
        conn = _get_ozon_connection()
        query = """
        SELECT LOWER(SPLIT_PART(REGEXP_REPLACE(offer_id, '_[^_]+$', ''), '/', 1)) as model,
               COUNT(DISTINCT dateupdate::date) as days_in_stock
        FROM stocks
        WHERE dateupdate >= %s AND dateupdate < %s
          AND offer_id IS NOT NULL AND offer_id != ''
          AND stockspresent > 0
        GROUP BY 1;
        """

    cur = conn.cursor()
    cur.execute(query, (start_date, end_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {}
    for raw_model, days_count in rows:
        model_name = map_to_osnova(raw_model)
        result[model_name] = result.get(model_name, 0) + int(days_count)
    return result


def get_wb_turnover_by_model(start_date, end_date):
    """
    WB оборачиваемость по моделям = available_stock / daily_sales.

    Остатки: МойСклад (Основной склад) + склады WB.
    Продажи: sales_count / days_in_stock (дни наличия, не календарные).
    """
    # Late imports to avoid circular dependency with monolith data_layer.py
    from shared.data_layer import get_wb_by_article

    mp_stock = get_wb_avg_stock(start_date, end_date)
    ms_stock = get_moysklad_stock_by_article()
    articles = get_wb_by_article(start_date, end_date)

    days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days)

    # Агрегация по модели
    model_data = {}
    for art in articles:
        model_name = map_to_osnova(art['model'])
        if model_name not in model_data:
            model_data[model_name] = {
                'sales_count': 0, 'stock_mp': 0, 'stock_ms': 0,
                'stock_transit': 0, 'revenue': 0, 'margin': 0,
            }
        model_data[model_name]['sales_count'] += art['sales_count']
        model_data[model_name]['revenue'] += art['revenue']
        model_data[model_name]['margin'] += art['margin']

    # Остатки WB (склады МП)
    for art_key, stock_val in mp_stock.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_mp'] += stock_val

    # Остатки МойСклад — только Основной склад (без транзита)
    for art_key, ms_info in ms_stock.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_ms'] += ms_info['stock_main']
            model_data[model_name]['stock_transit'] += ms_info['stock_transit']

    # Дни наличия товара на складе МП (для расчёта daily_sales)
    days_in_stock_map = _get_days_in_stock_by_model('wb', start_date, end_date)

    result = {}
    for model_name, md in model_data.items():
        # Оборачиваемость: только по стоку МП (FBO).
        # МойСклад (stock_ms) — контекст, НЕ участвует в turnover
        # (данные stock_ms ненадёжны — проблемы качества данных).
        available_stock = md['stock_mp']
        total_stock = md['stock_mp'] + md.get('stock_ms', 0)
        # daily_sales по дням наличия (fallback — календарные дни)
        model_days = days_in_stock_map.get(model_name, days)
        model_days = max(1, model_days)
        daily_sales = md['sales_count'] / model_days if md['sales_count'] > 0 else 0
        low_sales = daily_sales < MIN_DAILY_SALES
        if daily_sales > 0:
            turnover_days = min(available_stock / daily_sales, MAX_TURNOVER_DAYS)
        else:
            turnover_days = 0
        result[model_name] = {
            'avg_stock': round(available_stock, 0),
            'total_stock': round(total_stock, 0),
            'stock_mp': round(md['stock_mp'], 0),
            'stock_moysklad': round(md['stock_ms'], 0),
            'stock_transit': round(md['stock_transit'], 0),
            'daily_sales': round(daily_sales, 1),
            'turnover_days': round(turnover_days, 1),
            'sales_count': md['sales_count'],
            'days_in_stock': model_days,
            'revenue': round(md['revenue'], 0),
            'margin': round(md['margin'], 0),
            'low_sales': low_sales,
        }

    return result


def get_ozon_turnover_by_model(start_date, end_date):
    """
    OZON оборачиваемость по моделям = total_stock / daily_sales.

    Остатки: общие (OZON + МойСклад), без транзита.
    Продажи: из abc_date за период.
    """
    # Late imports to avoid circular dependency with monolith data_layer.py
    from shared.data_layer import get_ozon_by_article

    mp_stock = get_ozon_avg_stock(start_date, end_date)
    ms_stock = get_moysklad_stock_by_article()
    articles = get_ozon_by_article(start_date, end_date)

    days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days)

    model_data = {}
    for art in articles:
        model_name = map_to_osnova(art['model'])
        if model_name not in model_data:
            model_data[model_name] = {
                'sales_count': 0.0, 'stock_mp': 0.0, 'stock_ms': 0.0,
                'stock_transit': 0.0, 'revenue': 0.0, 'margin': 0.0,
            }
        model_data[model_name]['sales_count'] += art['sales_count']
        model_data[model_name]['revenue'] += art['revenue']
        model_data[model_name]['margin'] += art['margin']

    # Остатки OZON (склады МП)
    for art_key, stock_val in mp_stock.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_mp'] += stock_val

    # Остатки МойСклад — только Основной склад (без транзита)
    for art_key, ms_info in ms_stock.items():
        base_name = art_key.split('/')[0] if '/' in art_key else art_key
        model_name = map_to_osnova(base_name)
        if model_name in model_data:
            model_data[model_name]['stock_ms'] += ms_info['stock_main']
            model_data[model_name]['stock_transit'] += ms_info['stock_transit']

    # Дни наличия товара на складе МП
    days_in_stock_map = _get_days_in_stock_by_model('ozon', start_date, end_date)

    result = {}
    for model_name, md in model_data.items():
        # Оборачиваемость: только по стоку МП (FBO).
        available_stock = md['stock_mp']
        total_stock = md['stock_mp'] + md.get('stock_ms', 0)
        model_days = days_in_stock_map.get(model_name, days)
        model_days = max(1, model_days)
        daily_sales = md['sales_count'] / model_days if md['sales_count'] > 0 else 0
        low_sales = daily_sales < MIN_DAILY_SALES
        if daily_sales > 0:
            turnover_days = min(available_stock / daily_sales, MAX_TURNOVER_DAYS)
        else:
            turnover_days = 0
        result[model_name] = {
            'avg_stock': round(available_stock, 0),
            'total_stock': round(total_stock, 0),
            'stock_mp': round(md['stock_mp'], 0),
            'stock_moysklad': round(md['stock_ms'], 0),
            'stock_transit': round(md['stock_transit'], 0),
            'daily_sales': round(daily_sales, 1),
            'turnover_days': round(turnover_days, 1),
            'sales_count': md['sales_count'],
            'days_in_stock': model_days,
            'revenue': round(md['revenue'], 0),
            'margin': round(md['margin'], 0),
            'low_sales': low_sales,
        }

    return result


def get_wb_turnover_by_submodel(start_date, end_date):
    """
    WB оборачиваемость по ПОДМОДЕЛЯМ (VukiN, VukiW, ...).
    Использует маппинг артикулов из Supabase для определения подмодели.
    """
    # Late imports to avoid circular dependency with monolith data_layer.py
    from shared.data_layer import get_artikul_to_submodel_mapping, get_wb_by_article

    art_mapping = get_artikul_to_submodel_mapping()
    stock_by_article = get_wb_avg_stock(start_date, end_date)
    articles = get_wb_by_article(start_date, end_date)

    days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days)

    submodel_data = {}
    for art in articles:
        article_key = art.get('article', '').lower()
        info = art_mapping.get(article_key)
        if info:
            submodel_name = info['model_kod']
        else:
            submodel_name = art['model']  # fallback to osnova

        if submodel_name not in submodel_data:
            submodel_data[submodel_name] = {'sales_count': 0, 'stock_total': 0, 'revenue': 0, 'margin': 0}
        submodel_data[submodel_name]['sales_count'] += art['sales_count']
        submodel_data[submodel_name]['revenue'] += art['revenue']
        submodel_data[submodel_name]['margin'] += art['margin']

    for art_key, stock_val in stock_by_article.items():
        art_lower = art_key.lower()
        info = art_mapping.get(art_lower)
        if info:
            submodel_name = info['model_kod']
        else:
            base_name = art_key.split('/')[0] if '/' in art_key else art_key
            submodel_name = map_to_osnova(base_name)
        if submodel_name in submodel_data:
            submodel_data[submodel_name]['stock_total'] += stock_val

    result = {}
    for submodel_name, md in submodel_data.items():
        daily_sales = md['sales_count'] / days if md['sales_count'] > 0 else 0
        low_sales = daily_sales < MIN_DAILY_SALES
        if daily_sales > 0:
            turnover_days = min(md['stock_total'] / daily_sales, MAX_TURNOVER_DAYS)
        else:
            turnover_days = 0
        result[submodel_name] = {
            'avg_stock': round(md['stock_total'], 0),
            'daily_sales': round(daily_sales, 1),
            'turnover_days': round(turnover_days, 1),
            'sales_count': md['sales_count'],
            'revenue': round(md['revenue'], 0),
            'margin': round(md['margin'], 0),
            'low_sales': low_sales,
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


def get_moysklad_stock_by_model():
    """Остатки МойСклад агрегированные по model_osnova.

    Использует get_moysklad_stock_by_article() + map_to_osnova().
    Returns:
        {model: {'stock_main': N, 'stock_transit': M, 'total': N+M,
                 'snapshot_date': str, 'is_stale': bool}}
    """
    raw = get_moysklad_stock_by_article()
    result = {}
    snapshot_date = None
    is_stale = False

    for art, data in raw.items():
        base = art.split('/')[0] if '/' in art else art
        model = map_to_osnova(base)
        snapshot_date = data.get('snapshot_date')
        is_stale = data.get('is_stale', False)

        if model not in result:
            result[model] = {
                'stock_main': 0.0, 'stock_transit': 0.0, 'total': 0.0,
                'snapshot_date': snapshot_date,
                'is_stale': is_stale,
            }
        result[model]['stock_main'] += data['stock_main']
        result[model]['stock_transit'] += data['stock_transit']
        result[model]['total'] += data['total']

    return result
