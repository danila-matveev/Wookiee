"""Pricing & margin functions aggregated by article."""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql, map_to_osnova

__all__ = [
    "get_wb_price_margin_daily_by_article",
    "get_ozon_price_margin_daily_by_article",
]


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
    params_orders = []
    params_abc = []
    if article:
        filters_abc.append("AND LOWER(a.article) = %s")
        filters_orders.append("AND LOWER(supplierarticle) = %s")
        params_orders.append(article.lower())
        params_abc.append(article.lower())
    if model:
        filters_abc.append("AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s")
        filters_orders.append("AND LOWER(SPLIT_PART(supplierarticle, '/', 1)) = %s")
        params_orders.append(model.lower())
        params_abc.append(model.lower())

    filter_abc_sql = " ".join(filters_abc)
    filter_orders_sql = " ".join(filters_orders)
    params = [start_date, end_date] + params_orders + [start_date, end_date] + params_abc

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
        SPLIT_PART(LOWER(a.article), '/', 1) as model,
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
    params_orders = []
    params_abc = []
    if article:
        filters_abc.append("AND LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', '')) = %s")
        filters_orders.append("AND LOWER(REGEXP_REPLACE(offer_id, '_[^_]+$', '')) = %s")
        params_orders.append(article.lower())
        params_abc.append(article.lower())
    if model:
        filters_abc.append("AND LOWER(SPLIT_PART(a.article, '/', 1)) = %s")
        filters_orders.append("AND LOWER(SPLIT_PART(offer_id, '/', 1)) = %s")
        params_orders.append(model.lower())
        params_abc.append(model.lower())

    filter_abc_sql = " ".join(filters_abc)
    params = [start_date, end_date] + params_orders + [start_date, end_date] + params_abc
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
    GROUP BY a.date, LOWER(REGEXP_REPLACE(a.article, '_[^_]+$', '')),
             LOWER(SPLIT_PART(a.article, '/', 1))
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
