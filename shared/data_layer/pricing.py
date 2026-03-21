"""Pricing & margin functions aggregated by model."""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql, map_to_osnova

__all__ = [
    "get_wb_price_margin_daily",
    "get_ozon_price_margin_daily",
    "get_wb_price_changes",
    "get_ozon_price_changes",
    "get_wb_spp_history_by_model",
    "get_wb_price_margin_by_model_period",
    "get_wb_price_margin_by_submodel_period",
    "get_ozon_price_margin_by_model_period",
]


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
    # Normalize model: 'Set Wendy' or 'set_wendy' → 'set wendy' (matching mapping normalization)
    model_val = model.lower().replace('_', ' ') if model else None
    # Params must match placeholder order: CTE dates, [CTE model], main dates, [main model]
    params = [start_date, end_date]
    if model:
        model_filter_orders = "AND REPLACE(LOWER(SPLIT_PART(supplierarticle, '/', 1)), '_', ' ') = %s"
        params.append(model_val)
    params.extend([start_date, end_date])
    if model:
        model_filter_abc = "AND REPLACE(LOWER(SPLIT_PART(a.article, '/', 1)), '_', ' ') = %s"
        params.append(model_val)

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
    # Normalize model: 'Set Wendy' or 'set_wendy' → 'set wendy' (matching mapping normalization)
    model_val = model.lower().replace('_', ' ') if model else None
    # Params must match placeholder order: CTE dates, [CTE model], main dates, [main model]
    params = [start_date, end_date]
    if model:
        model_filter_orders = "AND REPLACE(LOWER(SPLIT_PART(offer_id, '/', 1)), '_', ' ') = %s"
        params.append(model_val)
    params.extend([start_date, end_date])
    if model:
        model_filter_abc = "AND REPLACE(LOWER(SPLIT_PART(a.article, '/', 1)), '_', ' ') = %s"
        params.append(model_val)

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
        {WB_MARGIN_SQL} as margin,
        CASE WHEN (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) > 0
            THEN ({WB_MARGIN_SQL}) /
                 (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) * 100
            ELSE NULL END as margin_pct,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue,
        CASE WHEN SUM(revenue_spp) > 0
            THEN SUM(spp) / SUM(revenue_spp) * 100
            ELSE NULL END as spp_pct,
        CASE WHEN (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) > 0
            THEN SUM(reclama + reclama_vn) /
                 (SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0)) * 100
            ELSE NULL END as drr_pct,
        SUM(logist) as logistics,
        SUM(reclama) as adv_internal,
        SUM(reclama_vn) as adv_bloggers,
        COALESCE(SUM(reclama_vn_vk), 0) as adv_vk,
        COALESCE(SUM(reclama_vn_creators), 0) as adv_creators
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


def get_wb_price_margin_by_submodel_period(start_date, end_date):
    """
    WB: агрегированные цена+маржа по ПОДМОДЕЛЯМ (VukiN, VukiW, VukiP, ...) за период.

    Подмодель определяется через маппинг артикулов из Supabase (artikuly → modeli).
    Артикулы без маппинга группируются по osnova.

    Возвращает список dict с ключами: model (osnova), submodel (model_kod),
    avg_price_per_unit, sales_count, margin, margin_pct, revenue.
    """
    # Import here to avoid circular dependency (defined in shared.data_layer parent)
    from shared.data_layer import get_artikul_to_submodel_mapping

    # 1. Получаем маппинг артикул → подмодель из Supabase
    art_mapping = get_artikul_to_submodel_mapping()

    # 2. Получаем данные из abc_date по артикулам
    conn = _get_wb_connection()
    cur = conn.cursor()
    query = f"""
    SELECT
        LOWER(article) as article,
        SUM(full_counts) as sales_count,
        {WB_MARGIN_SQL} as margin,
        SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue,
        SUM(spp) as spp_total,
        SUM(revenue_spp) as revenue_spp_total,
        SUM(reclama + reclama_vn) as reclama_total
    FROM abc_date
    WHERE date >= %s AND date < %s
    GROUP BY LOWER(article)
    HAVING SUM(full_counts) > 0;
    """
    cur.execute(query, (start_date, end_date))
    columns = [desc[0] for desc in cur.description]
    raw_rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    # 3. Группировка по подмодели
    submodel_agg = {}  # key: (osnova, model_kod)
    for row in raw_rows:
        article = row['article']
        info = art_mapping.get(article)
        if info:
            osnova = info['osnova_kod']
            model_kod = info['model_kod']
        else:
            raw_model = article.split('/')[0].strip()
            osnova = map_to_osnova(raw_model)
            model_kod = osnova  # Без маппинга — osnova = submodel

        key = (osnova, model_kod)
        if key not in submodel_agg:
            submodel_agg[key] = {
                'sales_count': 0, 'margin': 0, 'revenue': 0,
                'spp_total': 0, 'revenue_spp_total': 0, 'reclama_total': 0,
            }
        agg = submodel_agg[key]
        agg['sales_count'] += to_float(row['sales_count']) or 0
        agg['margin'] += to_float(row['margin']) or 0
        agg['revenue'] += to_float(row['revenue']) or 0
        agg['spp_total'] += to_float(row['spp_total']) or 0
        agg['revenue_spp_total'] += to_float(row['revenue_spp_total']) or 0
        agg['reclama_total'] += to_float(row['reclama_total']) or 0

    # 4. Финальный расчёт метрик
    results = []
    for (osnova, model_kod), agg in submodel_agg.items():
        sales = agg['sales_count']
        revenue = agg['revenue']
        margin = agg['margin']
        margin_pct = (margin / revenue * 100) if revenue > 0 else None
        avg_price = (revenue / sales) if sales > 0 else None
        spp_pct = (agg['spp_total'] / agg['revenue_spp_total'] * 100) if agg['revenue_spp_total'] > 0 else None
        drr_pct = (agg['reclama_total'] / revenue * 100) if revenue > 0 else None

        results.append({
            'model': osnova,
            'submodel': model_kod,
            'avg_price_per_unit': avg_price,
            'sales_count': sales,
            'margin': margin,
            'margin_pct': margin_pct,
            'revenue': revenue,
            'spp_pct': spp_pct,
            'drr_pct': drr_pct,
        })

    results.sort(key=lambda r: (r['model'], -(r['revenue'] or 0)))
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
            ELSE NULL END as drr_pct,
        SUM(logist_end) as logistics,
        SUM(reclama_end) as adv_internal,
        SUM(adv_vn) as adv_external
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
