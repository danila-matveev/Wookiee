"""Планирование и ABC-классификация моделей.

Функции для получения ABC-классифицированных моделей и плановых показателей.
"""

from datetime import datetime

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, _db_cursor, to_float
from shared.model_mapping import get_osnova_sql, map_to_osnova

__all__ = [
    "get_active_models_with_abc",
    "get_plan_by_period",
]


def get_active_models_with_abc(start_date, end_date):
    """Models with ABC-classified articles (Pareto by margin).

    Returns list of dicts:
      [{model, total_margin, articles: [{artikul, abc_class, margin, margin_share_pct, orders, opens}]}]
    Only models with at least one A or B article and positive total margin.
    """
    osnova_sql = get_osnova_sql("SPLIT_PART(a.article, '/', 1)")
    osnova_sql_ca = get_osnova_sql("SPLIT_PART(ca.vendorcode, '/', 1)")

    query = f"""
    WITH finance AS (
        SELECT
            {osnova_sql} as model,
            LOWER(a.article) as artikul,
            SUM(a.revenue_spp) - SUM(a.comis_spp) - SUM(a.logist) - SUM(a.sebes)
                - SUM(a.reclama) - SUM(a.reclama_vn) - SUM(a.storage)
                - SUM(a.nds) - SUM(a.penalty) - SUM(a.retention)
                - SUM(a.deduction) as margin,
            SUM(a.count_orders) as orders
        FROM abc_date a
        WHERE a.date >= %s AND a.date < %s
        GROUP BY {osnova_sql}, LOWER(a.article)
    ),
    traffic AS (
        SELECT
            LOWER(ca.vendorcode) as artikul,
            SUM(ca.opencardcount) as opens
        FROM content_analysis ca
        WHERE ca.date >= %s AND ca.date < %s
        GROUP BY LOWER(ca.vendorcode)
    )
    SELECT f.model, f.artikul, f.margin, f.orders, COALESCE(t.opens, 0) as opens
    FROM finance f
    LEFT JOIN traffic t ON f.artikul = t.artikul
    WHERE f.margin IS NOT NULL
    ORDER BY f.model, f.margin DESC
    """

    with _db_cursor(_get_wb_connection) as (conn, cur):
        cur.execute(query, [start_date, end_date, start_date, end_date])
        rows = cur.fetchall()

    # Group by model
    models = {}
    for model, artikul, margin, orders, opens in rows:
        if not model:
            continue
        if model not in models:
            models[model] = []
        models[model].append({
            'artikul': artikul,
            'margin': float(margin) if margin else 0,
            'orders': int(orders) if orders else 0,
            'opens': int(opens) if opens else 0,
        })

    # ABC classification per model (Pareto)
    result = []
    for model, articles in models.items():
        sorted_arts = sorted(articles, key=lambda x: x['margin'], reverse=True)
        total_margin = sum(a['margin'] for a in sorted_arts)

        if total_margin <= 0:
            continue  # Skip models with zero/negative margin

        cumulative = 0
        has_ab = False
        for art in sorted_arts:
            share = art['margin'] / total_margin
            cumulative += share
            art['margin_share_pct'] = round(share * 100, 1)

            if cumulative <= 0.80:
                art['abc_class'] = 'A'
                has_ab = True
            elif cumulative <= 0.95:
                art['abc_class'] = 'B'
                has_ab = True
            else:
                art['abc_class'] = 'C'

        if has_ab:
            result.append({
                'model': model,
                'total_margin': round(total_margin, 0),
                'articles': sorted_arts,
            })

    # Sort models by total margin descending
    result.sort(key=lambda x: x['total_margin'], reverse=True)
    return result


def get_plan_by_period(month_start: str, month_end: str):
    """Плановые показатели из plan_article за месячный период.

    Таблица plan_article (WB-база): все колонки TEXT, даты DD.MM.YYYY,
    значения с неразрывными пробелами (\\xa0).
    Содержит планы WB + Ozon в одной таблице.

    Args:
        month_start: '2026-03-01' (YYYY-MM-DD) — первый день месяца
        month_end: '2026-03-31' (YYYY-MM-DD) — последний день месяца
    Returns:
        list of tuples (МП, ЛК, Артикул, Показатель, Значение)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    # Конвертация YYYY-MM-DD → DD.MM.YYYY для WHERE
    start_dt = datetime.strptime(month_start, '%Y-%m-%d')
    end_dt = datetime.strptime(month_end, '%Y-%m-%d')
    start_ddmm = start_dt.strftime('%d.%m.%Y')
    end_ddmm = end_dt.strftime('%d.%m.%Y')

    query = """
    SELECT "МП", "ЛК", "Артикул", "Показатель", "Значение"
    FROM plan_article
    WHERE "Дата начала" = %s AND "Дата окончания" = %s;
    """
    cur.execute(query, (start_ddmm, end_ddmm))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
