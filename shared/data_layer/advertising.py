"""Рекламные запросы WB и OZON.

Функции для получения рекламных данных, ROI, органических воронок,
бюджетов и сравнения метрик по моделям для обоих маркетплейсов.
"""

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql, map_to_osnova

__all__ = [
    "get_wb_external_ad_breakdown",
    "get_ozon_external_ad_breakdown",
    "get_wb_organic_vs_paid_funnel",
    "get_wb_ad_daily_series",
    "get_ozon_ad_daily_series",
    "get_wb_model_ad_roi",
    "get_ozon_model_ad_roi",
    "get_ozon_ad_by_sku",
    "get_wb_campaign_stats",
    "get_wb_ad_budget_utilization",
    "get_wb_ad_totals_check",
    "get_wb_organic_by_status",
    "get_ozon_organic_estimated",
    "get_wb_model_metrics_comparison",
]


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
    lk фильтр применяется к обеим таблицам.

    Returns (organic_results, paid_results).
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    org_lk_clause = ""
    organic_params = [current_start, prev_start, current_end, prev_start, current_end]
    if lk is not None:
        org_lk_clause = "AND ca.lk = %s"
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
        {org_lk_clause}
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(organic_query, organic_params)
    organic_results = cur.fetchall()

    paid_lk_clause = ""
    paid_params = [current_start, prev_start, current_end]
    if lk is not None:
        paid_lk_clause = "AND lk = %s"
        paid_params.append(lk)

    paid_query = f"""
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
        {paid_lk_clause}
    GROUP BY 1
    ORDER BY period DESC;
    """
    cur.execute(paid_query, paid_params)
    paid_results = cur.fetchall()

    cur.close()
    conn.close()
    return organic_results, paid_results


def get_wb_ad_daily_series(start_date, end_date, lk=None):
    """Дневной ряд рекламных метрик WB из wb_adv: date, views, clicks, spend,
    to_cart, orders, CTR, CPC. Одна строка на день.

    lk фильтр поддерживается (wb_adv имеет колонку lk).
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [start_date, end_date]
    if lk is not None:
        lk_clause = "AND lk = %s"
        params.append(lk)

    query = f"""
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
        {lk_clause}
    GROUP BY date
    ORDER BY date;
    """
    cur.execute(query, params)
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
    с abc_date (выручка, маржа по модели). lk фильтр на обе таблицы.

    Возвращает: period, model, ad_spend, ad_orders, revenue, margin, DRR%, ROMI.
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    abc_lk_clause = ""
    adv_lk_clause = ""
    params = [current_start, prev_start, current_end,
              current_start, prev_start, current_end]
    if lk is not None:
        adv_lk_clause = "AND w.lk = %s"
        abc_lk_clause = "AND a.lk = %s"
        params.insert(3, lk)  # after first 3 params (for ad CTE)
        params.append(lk)  # for fin CTE

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
        JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n ON w.nmid = n.nmid
        WHERE w.date >= %s AND w.date < %s
            {adv_lk_clause}
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
            {abc_lk_clause}
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


def get_wb_campaign_stats(current_start, prev_start, current_end, lk=None):
    """WB статистика по рекламным кампаниям (name_rk). По периодам current/previous.

    Возвращает: period, campaign, views, clicks, spend, to_cart, orders, CTR, CPC.
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
        {lk_clause}
    GROUP BY 1, 2
    ORDER BY period DESC, SUM(sum) DESC;
    """
    cur.execute(query, params)
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


def get_wb_ad_totals_check(start_date, end_date):
    """Sanity check: сравнение raw SUM(sum) из wb_adv (без JOIN)
    с model-aggregated суммой (через JOIN nomenclature).
    Используется для обнаружения fan-out в JOINах.

    Returns: (raw_total, model_total, discrepancy_pct)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Raw total (no JOINs)
    cur.execute(
        "SELECT COALESCE(SUM(sum), 0) FROM wb_adv WHERE date >= %s AND date < %s",
        (start_date, end_date),
    )
    raw_total = to_float(cur.fetchone()[0])

    # Model-aggregated total (with deduplicated nomenclature JOIN)
    cur.execute("""
        SELECT COALESCE(SUM(w.sum), 0) FROM wb_adv w
        JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n
        ON w.nmid = n.nmid
        WHERE w.date >= %s AND w.date < %s
    """, (start_date, end_date))
    model_total = to_float(cur.fetchone()[0])

    cur.close()
    conn.close()

    discrepancy_pct = round(abs(raw_total - model_total) / max(raw_total, 1) * 100, 2)
    return raw_total, model_total, discrepancy_pct


def get_wb_organic_by_status(current_start, prev_start, current_end, lk=None):
    """WB органическая воронка с разбивкой по статусу товара (Продается/Выводим/Архив).

    Двухшаговый подход: Supabase (статусы) + content_analysis (органика).
    Статусы из Supabase через get_artikuly_statuses().

    Returns: dict {status_name: {period: {card_opens, add_to_cart, orders, buyouts, CRs}}}
    """
    from shared.data_layer import get_artikuly_statuses

    statuses = get_artikuly_statuses()  # {article_lower: status}

    conn = _get_wb_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND ca.lk = %s"
        params.append(lk)

    query = f"""
    SELECT
        CASE WHEN ca.date >= %s THEN 'current' ELSE 'previous' END as period,
        LOWER(ca.vendorcode) as vendorcode,
        SUM(ca.opencardcount) as card_opens,
        SUM(ca.addtocartcount) as add_to_cart,
        SUM(ca.orderscount) as funnel_orders,
        SUM(ca.buyoutscount) as buyouts
    FROM content_analysis ca
    WHERE ca.date >= %s AND ca.date < %s
        AND ca.vendorcode IN (SELECT DISTINCT article FROM abc_date WHERE date >= %s AND date < %s)
        {lk_clause}
    GROUP BY 1, 2;
    """
    cur.execute(query, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # Classify by status and aggregate
    result = {}
    for row in rows:
        period = row[0]
        vendorcode = row[1]
        status = statuses.get(vendorcode, "Продается")  # default to active
        if status not in result:
            result[status] = {}
        if period not in result[status]:
            result[status][period] = {
                "card_opens": 0, "add_to_cart": 0, "orders": 0, "buyouts": 0,
            }
        bucket = result[status][period]
        bucket["card_opens"] += to_float(row[2])
        bucket["add_to_cart"] += to_float(row[3])
        bucket["orders"] += to_float(row[4])
        bucket["buyouts"] += to_float(row[5])

    # Compute CRs
    for status_data in result.values():
        for period_data in status_data.values():
            co = period_data["card_opens"]
            atc = period_data["add_to_cart"]
            orders = period_data["orders"]
            buyouts = period_data["buyouts"]
            period_data["card_to_cart_pct"] = round(atc / co * 100, 2) if co > 0 else 0
            period_data["cart_to_order_pct"] = round(orders / atc * 100, 2) if atc > 0 else 0
            period_data["order_to_buyout_pct"] = round(buyouts / orders * 100, 2) if orders > 0 else 0

    return result


def get_ozon_organic_estimated(current_start, prev_start, current_end, lk=None):
    """Расчётная органика OZON по моделям.

    organic_orders = total_orders (abc_date.count_end) - ad_orders (ozon_adv_api.orders)
    organic_revenue = total_revenue (abc_date.price_end) - ad-attributed revenue (estimated)

    Returns: list of (period, model, total_orders, ad_orders, organic_orders,
                       total_revenue, ad_spend)
    """
    conn = _get_ozon_connection()
    cur = conn.cursor()

    lk_clause = ""
    params = [current_start, prev_start, current_end,
              current_start, prev_start, current_end]
    if lk is not None:
        lk_clause = "AND a.lk = %s"
        params.append(lk)

    model_sql = get_osnova_sql("SPLIT_PART(a.article, '/', 1)")

    query = f"""
    WITH total_by_model AS (
        SELECT
            CASE WHEN a.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql} as model,
            SUM(a.count_end) as total_orders,
            SUM(a.price_end) as total_revenue
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
            {lk_clause}
        GROUP BY 1, 2
    ),
    ad_by_sku AS (
        SELECT
            CASE WHEN o.operation_date >= %s THEN 'current' ELSE 'previous' END as period,
            o.sku,
            SUM(o.orders) as ad_orders,
            SUM(o.sum_rev) as ad_spend
        FROM ozon_adv_api o
        WHERE o.operation_date >= %s AND o.operation_date < %s
        GROUP BY 1, 2
    ),
    ad_sku_with_model AS (
        SELECT
            ad.period,
            {model_sql} as model,
            ad.ad_orders,
            ad.ad_spend
        FROM ad_by_sku ad
        JOIN abc_date a ON ad.sku = a.sku
            AND a.date >= CASE WHEN ad.period = 'current' THEN %s::date ELSE %s::date END
            AND a.date < %s::date
            {lk_clause}
    ),
    ad_by_model AS (
        SELECT period, model,
            SUM(ad_orders) as ad_orders,
            SUM(ad_spend) as ad_spend
        FROM ad_sku_with_model
        GROUP BY 1, 2
    )
    SELECT
        COALESCE(t.period, a.period) as period,
        COALESCE(t.model, a.model) as model,
        COALESCE(t.total_orders, 0) as total_orders,
        COALESCE(a.ad_orders, 0) as ad_orders,
        GREATEST(COALESCE(t.total_orders, 0) - COALESCE(a.ad_orders, 0), 0) as organic_orders,
        COALESCE(t.total_revenue, 0) as total_revenue,
        COALESCE(a.ad_spend, 0) as ad_spend
    FROM total_by_model t
    FULL OUTER JOIN ad_by_model a ON t.period = a.period AND t.model = a.model
    ORDER BY period DESC, total_orders DESC;
    """
    # Extra params for the date case in ad_sku_with_model
    extra_params = [current_start, prev_start, current_end]
    if lk is not None:
        extra_params.append(lk)
    all_params = params + extra_params
    cur.execute(query, all_params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results


def get_wb_model_metrics_comparison(current_start, prev_start, current_end, lk=None):
    """WB метрики по моделям для current и previous периодов: органика + реклама.

    Объединяет content_analysis (органическая воронка) и wb_adv (рекламная воронка)
    с группировкой по модели через nomenclature/abc_date.

    Returns: list of tuples:
        (period, model, organic_card_opens, organic_add_to_cart, organic_orders, organic_buyouts,
         ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    org_lk_clause = ""
    adv_lk_clause = ""
    params = [current_start, prev_start, current_end,
              current_start, prev_start, current_end]
    if lk is not None:
        org_lk_clause = "AND ca.lk = %s"
        adv_lk_clause = "AND w.lk = %s"
        params.insert(3, lk)  # after first 3 params (for organic CTE)
        params.append(lk)  # for ad CTE

    model_sql_ca = get_osnova_sql("SPLIT_PART(ca.vendorcode, '/', 1)")
    model_sql_adv = get_osnova_sql("SPLIT_PART(n.vendorcode, '/', 1)")

    query = f"""
    WITH organic_by_model AS (
        SELECT
            CASE WHEN ca.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql_ca} as model,
            SUM(ca.opencardcount) as card_opens,
            SUM(ca.addtocartcount) as add_to_cart,
            SUM(ca.orderscount) as orders,
            SUM(ca.buyoutscount) as buyouts
        FROM content_analysis ca
        WHERE ca.date >= %s AND ca.date < %s
            {org_lk_clause}
        GROUP BY 1, 2
    ),
    ad_by_model AS (
        SELECT
            CASE WHEN w.date >= %s THEN 'current' ELSE 'previous' END as period,
            {model_sql_adv} as model,
            SUM(w.views) as ad_views,
            SUM(w.clicks) as ad_clicks,
            SUM(w.atbs) as ad_to_cart,
            SUM(w.orders) as ad_orders,
            SUM(w.sum) as ad_spend
        FROM wb_adv w
        JOIN (SELECT DISTINCT nmid, vendorcode FROM nomenclature) n ON w.nmid = n.nmid
        WHERE w.date >= %s AND w.date < %s
            {adv_lk_clause}
        GROUP BY 1, 2
    )
    SELECT
        COALESCE(o.period, a.period) as period,
        COALESCE(o.model, a.model) as model,
        COALESCE(o.card_opens, 0),
        COALESCE(o.add_to_cart, 0),
        COALESCE(o.orders, 0),
        COALESCE(o.buyouts, 0),
        COALESCE(a.ad_views, 0),
        COALESCE(a.ad_clicks, 0),
        COALESCE(a.ad_to_cart, 0),
        COALESCE(a.ad_orders, 0),
        COALESCE(a.ad_spend, 0)
    FROM organic_by_model o
    FULL OUTER JOIN ad_by_model a ON o.period = a.period AND o.model = a.model
    ORDER BY period DESC, COALESCE(o.card_opens, 0) + COALESCE(a.ad_spend, 0) DESC;
    """
    cur.execute(query, params)
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
