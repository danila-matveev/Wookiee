"""Daily and weekly time-series retrieval for WB and OZON."""

from __future__ import annotations

from datetime import datetime, timedelta

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL

__all__ = [
    'get_wb_daily_series',
    'get_ozon_daily_series',
    'get_wb_daily_series_range',
    'get_ozon_daily_series_range',
    'get_wb_weekly_breakdown',
    'get_ozon_weekly_breakdown',
]


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
