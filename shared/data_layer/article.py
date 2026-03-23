"""Article & barcode-level queries for WB and OZON.

Functions that pull financial / order data grouped by article or barcode.
"""

from __future__ import annotations

from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql, map_to_osnova

__all__ = [
    "get_wb_by_article",
    "get_ozon_by_article",
    "get_wb_orders_by_article",
    "get_wb_barcode_to_marketplace_mapping",
    "get_wb_gs2_to_marketplace_mapping",
    "get_wb_fin_data_by_barcode",
    "get_wb_orders_by_barcode",
    "get_ozon_fin_data_by_barcode",
    "get_ozon_orders_by_barcode",
]


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
    GROUP BY 1, 2
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
    GROUP BY 1, 2
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


def get_wb_barcode_to_marketplace_mapping():
    """Build barcode → canonical barcode mapping from WB nomenclature.

    Products can have multiple barcodes per (nmid, techsize, lk) group:
    - Marketplace (20xx): sales + financial data
    - GS2 (468xx): orders data
    - GS1/EAN (460-467xx): additional sales/financial data

    This mapping remaps ALL alternative barcodes to a single canonical barcode
    so data merges into one entry per product. Canonical barcode priority:
    marketplace (20xx) > first barcode alphabetically.

    Returns dict[barcode_str -> canonical_barcode_str].
    """
    conn = _get_wb_connection()
    cur = conn.cursor()
    query = """
    WITH grouped AS (
        SELECT nmid, techsize, lk,
               array_agg(DISTINCT barcod ORDER BY barcod) AS all_bcs,
               array_agg(DISTINCT barcod ORDER BY barcod)
                   FILTER (WHERE LEFT(barcod, 2) = '20') AS mkt
        FROM nomenclature
        WHERE barcod IS NOT NULL AND barcod != ''
        GROUP BY nmid, techsize, lk
        HAVING COUNT(DISTINCT barcod) > 1
    )
    SELECT unnest(all_bcs) AS src_bc,
           COALESCE(mkt[1], all_bcs[1]) AS canonical_bc
    FROM grouped;
    """
    cur.execute(query)
    # Exclude self-mappings to keep dict lean.
    # When a barcode appears in multiple (nmid, techsize, lk) groups
    # (e.g. different LKs), prefer the mapping to a marketplace barcode.
    mapping = {}
    for r in cur.fetchall():
        src, canonical = str(r[0]), str(r[1])
        if src == canonical:
            continue
        existing = mapping.get(src)
        if existing is None:
            mapping[src] = canonical
        elif canonical.startswith('20') and not existing.startswith('20'):
            mapping[src] = canonical

    # Resolve chains: if A→B and B→C, collapse to A→C.
    # This happens when a barcode belongs to multiple nomenclature groups
    # and intermediate mappings form a chain instead of direct links.
    changed = True
    while changed:
        changed = False
        for src in list(mapping):
            target = mapping[src]
            if target in mapping:
                mapping[src] = mapping[target]
                changed = True

    cur.close()
    conn.close()
    print(f"[data_layer] barcode→canonical mapping: {len(mapping)} entries")
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
