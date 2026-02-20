"""Sync financial data from DB -> sheet 'Фин данные'.

Replaces manual Power BI export. Queries WB + OZON abc_date by barcode,
calculates derived metrics, and writes to Google Sheet with period selection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    set_checkbox,
    to_number,
)
from shared.data_layer import (
    get_wb_fin_data_by_barcode,
    get_wb_orders_by_barcode,
    get_ozon_fin_data_by_barcode,
    get_ozon_orders_by_barcode,
)
from services.sheets_sync.config import GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Фин данные"

# Reference sheet for INDEX/MATCH formulas in A/B columns
REF_SHEET = "Все товары"

# Поля для суммирования при объединении WB + OZON
SUMMABLE_FIELDS = [
    'orders_count', 'sales_count',
    'revenue_before_spp_gross', 'revenue_before_spp', 'revenue_after_spp',
    'spp_amount', 'returns_revenue', 'returns_count',
    'commission', 'logistics', 'cost_of_goods',
    'adv_internal', 'adv_external', 'adv_vk', 'adv_creators',
    'storage', 'nds', 'penalty', 'retention', 'deduction',
    'margin', 'self_purchase_count',
]

# Заголовки строки 2 (для MATCH в VLOOKUP с "Все товары" — с запятыми)
HEADERS_ROW2 = [
    'БАРКОД', 'Нуменклатура', 'Артикул+размер', 'Фото',
    'Мин, дата продажи', 'Статус', 'Модель', 'Импортер',
    'Color code', 'Склейка на WB', 'Категория МС', 'Модель основа', 'Коллекция',
    'Заказы шт п2', 'Заказы в день шт п2',
    'Ср,чек заказа до СПП ₽ п2', 'Ср,чек заказа после СПП ₽ п2',
    'Выкупы  п2', 'Заказы до СПП ₽ п2',
    'Продажи шт п2', 'Возвраты шт п2', 'Возвраты  п2',
    'Ср,чек продажи до СПП ₽ п2', 'Ср,чек продажи после СПП ₽ п2',
    'СПП WB продажи  п2', 'Продажи до СПП ₽ п2',
    'ABC продажи п2', 'ABC маржа п2', 'ABC маржа  п2',
    'Маржа ₽ п2', 'Маржа до СПП  п2', 'Маржа до СПП без РР  п2', 'Маржа после СПП  п2',
    'ABC оборот п2', 'Оборот продаж дни п2',
    'Остатки ₽ п2', 'Заморожено ₽ п2', 'Остатки шт п2',
    'Маржа на ед ₽ п2',
    'Комиссия до СПП ₽ п2', 'Комиссия до СПП  п2', 'Комиссия до СПП на ед ₽ п2',
    'Логистика ₽ п2', 'Логистика  п2', 'Логистика на ед ₽ п2',
    'Себес-ть ₽ п2', 'Себес-ть  п2', 'Себес-ть на ед ₽ п2',
    'Реклама ₽ п2', 'Реклама  п2', 'Реклама на ед ₽ п2',
    'Хранение ₽ п2', 'Хранение  п2', 'Хранение на ед ₽ п2',
    'Ост, расходы МП ₽ п2', 'Ост, расходы МП  п2', 'Ост, расходы МП на ед ₽ п2',
    'НДС ₽ п2', 'НДС  п2', 'НДС на ед ₽ п2',
    'Реклама внеш, ₽ п2', 'Реклама внеш,  п2', 'Реклама внеш, на ед ₽ п2',
    'Реклама блогеры ₽ п2', 'Реклама креаторы ₽ п2', 'Реклама ВК ₽ п2',
    'Реклама итого ₽ п2',
    'ДРР рекл,  п2', 'ДРР рекл, (внутр,)  п2',
    'ДРР от заказов (после СПП)  п2', 'ДРР от заказов (до СПП)  п2',
    'ДРР от продаж (после СПП)  п2', 'ДРР от продаж (до СПП)  п2',
    'ДРР блогеры от продаж (до СПП)  п2', 'ДРР креаторы от продаж (до СПП)  п2',
    'ДРР ВК от продаж (до СПП)  п2', 'ДРР внутр, от продаж (до СПП)  п2',
]

# Column format types (0-indexed)
_RUB_COLS = {15, 16, 18, 22, 23, 25, 29, 35, 36, 38,
             39, 41, 42, 44, 45, 47, 48, 50, 51, 53,
             54, 56, 57, 59, 60, 62, 63, 64, 65, 66}
_PCT_COLS = {17, 21, 24, 30, 31, 32, 40, 43, 46, 49,
             52, 55, 58, 61, 67, 68, 69, 70, 71, 72,
             73, 74, 75, 76}
_INT_COLS = {13, 19, 20, 37}
_DEC_COLS = {14, 34}  # decimal (1 digit)


def sync(start_date: str | None = None, end_date: str | None = None) -> int:
    """Sync financial data for the given period to 'Фин данные' sheet.

    Args:
        start_date: Period start DD.MM.YYYY.
        end_date: Period end DD.MM.YYYY.

    Returns:
        Number of data rows written.
    """
    logger.info("=== sync_fin_data: start ===")

    # 1. Google Sheets
    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=5000, cols=80)

    # 2. Resolve dates
    iso_start, iso_end, display_start, display_end = _resolve_dates(
        ws, start_date, end_date
    )
    days_in_period = max((
        datetime.strptime(iso_end, '%Y-%m-%d') -
        datetime.strptime(iso_start, '%Y-%m-%d')
    ).days, 1)
    logger.info("Period: %s — %s (%d days)", display_start, display_end, days_in_period)

    # 3. Fetch WB data
    logger.info("Fetching WB financial data...")
    wb_fin = get_wb_fin_data_by_barcode(iso_start, iso_end)
    wb_orders = get_wb_orders_by_barcode(iso_start, iso_end)
    logger.info("WB: %d barcodes, %d order barcodes", len(wb_fin), len(wb_orders))

    # 4. Fetch OZON data
    logger.info("Fetching OZON financial data...")
    ozon_fin = get_ozon_fin_data_by_barcode(iso_start, iso_end)
    ozon_orders = get_ozon_orders_by_barcode(iso_start, iso_end)
    logger.info("OZON: %d barcodes, %d order barcodes", len(ozon_fin), len(ozon_orders))

    # 5. Load reference data from "Все товары"
    logger.info("Loading reference data from 'Все товары'...")
    reference = _load_reference_data(spreadsheet)
    logger.info("Reference: %d barcodes", len(reference))

    # 6. Build combined dict by barcode
    combined = _merge_data(wb_fin, wb_orders, ozon_fin, ozon_orders)
    logger.info("Combined: %d unique barcodes", len(combined))

    if not combined:
        logger.warning("No financial data for period %s — %s", display_start, display_end)
        return 0

    # 7. Calculate derived metrics
    items = list(combined.values())
    for item in items:
        _calculate_derived_metrics(item, days_in_period)

    # 8. ABC classification
    abc_sales = _calculate_abc(items, 'sales_count')
    abc_margin = _calculate_abc(items, 'margin')
    abc_margin_pct = _calculate_abc(items, 'margin_before_spp_pct')
    abc_turnover = _calculate_abc(items, 'turnover_days', reverse=True)

    # 9. Build output rows (with formulas in A/B)
    data_rows = []
    for idx, item in enumerate(items):
        bc = item['barcode']
        row_num = idx + 4  # data starts at row 4
        row = _build_row(
            item,
            reference.get(str(bc), {}),
            abc_sales.get(bc, 'C'),
            abc_margin.get(bc, 'C'),
            abc_margin_pct.get(bc, 'C'),
            abc_turnover.get(bc, ''),
            row_num=row_num,
        )
        data_rows.append(row)

    # 10. Build totals row (no formulas — plain values)
    totals_row = _build_totals_row(items, days_in_period)

    # 11. Write to sheet + formatting + checkbox
    logger.info("Writing %d rows to sheet '%s'...", len(data_rows), sheet_name)
    _write_to_sheet(ws, spreadsheet, display_start, display_end, totals_row, data_rows)

    logger.info("=== sync_fin_data: done (%d rows) ===", len(data_rows))
    return len(data_rows)


# ---- Date resolution ----

def _resolve_dates(ws, start_date, end_date):
    """Resolve period dates. Returns (iso_start, iso_end, display_start, display_end).

    iso_end is EXCLUSIVE (+1 day) because SQL uses ``date < end``.
    User picks inclusive range (01.02—03.02 = 3 days), so we add one day.
    """
    if start_date and end_date:
        iso_start = _dd_mm_to_iso(start_date)
        iso_end = _dd_mm_to_iso(end_date)
        iso_end = _next_day(iso_end)
        return iso_start, iso_end, start_date, end_date

    # Try reading from sheet B1/C1
    try:
        b1 = (ws.acell("B1").value or "").strip()
        c1 = (ws.acell("C1").value or "").strip()
        if b1 and c1:
            iso_start = _dd_mm_to_iso(b1)
            iso_end = _next_day(_dd_mm_to_iso(c1))
            return iso_start, iso_end, b1, c1
    except Exception:
        pass

    # Default: last full month
    today = datetime.now()
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    ds = last_month_start.strftime('%d.%m.%Y')
    de = first_this_month.strftime('%d.%m.%Y')
    return last_month_start.strftime('%Y-%m-%d'), first_this_month.strftime('%Y-%m-%d'), ds, de


def _dd_mm_to_iso(date_str: str) -> str:
    """Convert DD.MM.YYYY to YYYY-MM-DD."""
    parts = date_str.strip().split('.')
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


def _next_day(iso_date: str) -> str:
    """Return the next day in YYYY-MM-DD format (for exclusive end in SQL)."""
    return (datetime.strptime(iso_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')


# ---- Reference data ----

def _load_reference_data(spreadsheet) -> dict:
    """Read 'Все товары' sheet for reference data by barcode."""
    try:
        ws_ref = spreadsheet.worksheet("Все товары")
    except Exception:
        try:
            ws_ref = spreadsheet.worksheet(get_sheet_name("Все товары"))
        except Exception:
            logger.warning("Sheet 'Все товары' not found, reference data unavailable")
            return {}

    all_values = ws_ref.get_all_values()
    if len(all_values) < 2:
        return {}

    headers = all_values[0]

    # Find column indices
    col_map = {}
    target_cols = {
        'БАРКОД ': 'barcode', 'БАРКОД': 'barcode',
        'Фото': 'photo',
        'Статус товара': 'status',
        'Модель': 'model',
        'Импортер': 'importer',
        'Color code': 'color_code',
        'Склейка на WB': 'skleyka_wb',
        'Категория': 'category',
        'Модель основа': 'model_osnova',
        'Коллекция': 'collection',
        'Наличие итого': 'stock_total',
    }
    for i, h in enumerate(headers):
        h_stripped = h.strip()
        if h_stripped in target_cols:
            col_map[target_cols[h_stripped]] = i

    barcode_col = col_map.get('barcode')
    if barcode_col is None:
        logger.warning("'БАРКОД' column not found in 'Все товары'")
        return {}

    result = {}
    for row in all_values[1:]:
        if len(row) <= barcode_col:
            continue
        bc = str(row[barcode_col]).strip()
        if not bc:
            continue
        ref = {}
        for key, col_idx in col_map.items():
            if key != 'barcode' and col_idx < len(row):
                ref[key] = str(row[col_idx]).strip()
        result[bc] = ref

    return result


# ---- Data merging ----

def _merge_data(wb_fin, wb_orders, ozon_fin, ozon_orders) -> dict:
    """Merge WB and OZON data by barcode."""
    combined = {}

    # WB financial data
    for item in wb_fin:
        bc = str(item.get('barcode', ''))
        if not bc:
            continue
        entry = combined.get(bc)
        if entry is None:
            entry = _empty_entry(bc)
            combined[bc] = entry

        entry['nm_id'] = item.get('nm_id', '')
        article = item.get('article', '')
        ts = item.get('ts_name', '')
        entry['article_size'] = f"{article}_{ts}" if ts else article
        entry['model'] = item.get('model', '')
        entry['min_sale_date'] = item.get('min_sale_date', '')

        for field in SUMMABLE_FIELDS:
            val = item.get(field, 0)
            entry[field] = entry.get(field, 0) + (val if val else 0)

    # WB orders
    for bc, orders in wb_orders.items():
        bc = str(bc)
        entry = combined.get(bc)
        if entry:
            entry['orders_table_count'] = entry.get('orders_table_count', 0) + orders.get('orders_count', 0)
            entry['orders_table_rub'] = entry.get('orders_table_rub', 0) + orders.get('orders_rub', 0)

    # OZON financial data
    for item in ozon_fin:
        bc = str(item.get('barcode', ''))
        if not bc:
            continue
        entry = combined.get(bc)
        if entry is None:
            entry = _empty_entry(bc)
            combined[bc] = entry
            # Fill model/article from OZON if not set by WB
            entry['model'] = item.get('model', '')
            ozon_art = item.get('ozon_article', '')
            entry['article_size'] = ozon_art
            entry['min_sale_date'] = item.get('min_sale_date', '')

        for field in SUMMABLE_FIELDS:
            if field in ('penalty', 'retention', 'deduction', 'self_purchase_count',
                         'revenue_before_spp_gross'):
                # WB-only fields, OZON doesn't have them
                continue
            val = item.get(field, 0)
            entry[field] = entry.get(field, 0) + (val if val else 0)

        # NB: returns_count already summed via SUMMABLE_FIELDS loop above

    # OZON orders
    for bc, orders in ozon_orders.items():
        bc = str(bc)
        entry = combined.get(bc)
        if entry:
            entry['orders_table_count'] = entry.get('orders_table_count', 0) + orders.get('orders_count', 0)
            entry['orders_table_rub'] = entry.get('orders_table_rub', 0) + orders.get('orders_rub', 0)
            # OZON abc_date не имеет count_orders → берём из orders table
            entry['orders_count'] = entry.get('orders_count', 0) + orders.get('orders_count', 0)

    return combined


def _empty_entry(barcode: str) -> dict:
    """Create an empty entry for a barcode."""
    entry = {'barcode': barcode, 'nm_id': '', 'article_size': '', 'model': '',
             'min_sale_date': '', 'orders_table_count': 0, 'orders_table_rub': 0,
             'returns_count': 0}
    for field in SUMMABLE_FIELDS:
        entry[field] = 0
    return entry


# ---- Derived metrics ----

def _safe_div(a, b):
    """Safe division, returns 0 if b is 0."""
    return a / b if b else 0


def _calculate_derived_metrics(item, days_in_period):
    """Calculate all percentage and per-unit metrics for an item."""
    sales = item.get('sales_count', 0)
    orders = item.get('orders_count', 0)
    rev_bspp = item.get('revenue_before_spp', 0)  # net (minus returns)
    rev_aspp = item.get('revenue_after_spp', 0)
    # Gross = net + returns (works for both WB and OZON combined)
    rev_gross = rev_bspp + item.get('returns_revenue', 0)
    margin = item.get('margin', 0)
    adv_int = item.get('adv_internal', 0)
    adv_ext = item.get('adv_external', 0)
    adv_vk = item.get('adv_vk', 0)
    adv_creators = item.get('adv_creators', 0)
    # reclama_vn = блогеры, reclama_vn_vk = ВК, reclama_vn_creators — ОТДЕЛЬНЫЕ каналы
    adv_bloggers = adv_ext  # adv_external (reclama_vn / adv_vn) IS bloggers
    adv_total = adv_int + adv_ext + adv_vk + adv_creators
    commission = item.get('commission', 0)
    logistics = item.get('logistics', 0)
    cogs = item.get('cost_of_goods', 0)
    storage = item.get('storage', 0)
    nds = item.get('nds', 0)
    penalty = item.get('penalty', 0)
    retention = item.get('retention', 0)
    deduction = item.get('deduction', 0)
    other_expenses = penalty + retention + deduction
    spp_amount = item.get('spp_amount', 0)
    returns_count = item.get('returns_count', 0)
    stock_qty = item.get('stock_qty', 0)

    orders_rub = item.get('orders_table_rub', 0)
    orders_tbl = item.get('orders_table_count', 0)

    # Orders
    item['orders_per_day'] = round(_safe_div(orders, days_in_period), 1)
    item['avg_check_orders_bspp'] = round(_safe_div(orders_rub, orders_tbl), 2)
    item['avg_check_orders_aspp'] = round(
        _safe_div(orders_rub, orders_tbl) * (1 - _safe_div(spp_amount, rev_gross)), 2
    ) if orders_tbl else 0

    # Buyout rate (stored as fraction for %)
    item['buyout_frac'] = min(_safe_div(sales, orders), 1.0) if orders > 0 else 0

    # Returns (fraction)
    item['returns_frac'] = _safe_div(returns_count, sales + returns_count)

    # Average checks (sales)
    item['avg_check_sales_bspp'] = round(_safe_div(rev_bspp, sales), 2)
    item['avg_check_sales_aspp'] = round(_safe_div(rev_aspp, sales), 2)

    # SPP % (fraction)
    item['spp_frac'] = _safe_div(spp_amount, rev_gross)

    # Margin % (fractions)
    item['margin_before_spp_pct'] = round(_safe_div(margin, rev_bspp) * 100, 2)  # keep for ABC
    item['margin_before_spp_frac'] = _safe_div(margin, rev_bspp)
    item['margin_before_spp_no_ads_frac'] = _safe_div(margin + adv_total, rev_bspp)
    item['margin_after_spp_frac'] = _safe_div(margin, rev_aspp)

    # Turnover
    daily_sales = _safe_div(sales, days_in_period)
    item['turnover_days'] = round(_safe_div(stock_qty, daily_sales), 1) if stock_qty > 0 else 0

    # Stock value
    cost_per_unit = _safe_div(cogs, sales) if sales > 0 else 0
    item['stock_rub'] = round(stock_qty * cost_per_unit, 2)
    item['frozen_rub'] = round(item['stock_rub'], 2) if item['turnover_days'] > 90 else 0

    # Per-unit metrics
    item['margin_per_unit'] = round(_safe_div(margin, sales), 2)
    item['commission_frac'] = _safe_div(commission, rev_bspp)
    item['commission_per_unit'] = round(_safe_div(commission, sales), 2)
    item['logistics_frac'] = _safe_div(logistics, rev_bspp)
    item['logistics_per_unit'] = round(_safe_div(logistics, sales), 2)
    item['cogs_frac'] = _safe_div(cogs, rev_bspp)
    item['cogs_per_unit'] = round(_safe_div(cogs, sales), 2)
    item['adv_internal_frac'] = _safe_div(adv_int, rev_bspp)
    item['adv_internal_per_unit'] = round(_safe_div(adv_int, sales), 2)
    item['storage_frac'] = _safe_div(storage, rev_bspp)
    item['storage_per_unit'] = round(_safe_div(storage, sales), 2)
    item['other_expenses'] = other_expenses
    item['other_frac'] = _safe_div(other_expenses, rev_bspp)
    item['other_per_unit'] = round(_safe_div(other_expenses, sales), 2)
    item['nds_frac'] = _safe_div(nds, rev_bspp)
    item['nds_per_unit'] = round(_safe_div(nds, sales), 2)
    # "Реклама внеш." = total non-internal (bloggers + VK + creators)
    adv_ext_total = adv_ext + adv_vk + adv_creators
    item['adv_ext_total'] = round(adv_ext_total, 2)
    item['adv_external_frac'] = _safe_div(adv_ext_total, rev_bspp)
    item['adv_external_per_unit'] = round(_safe_div(adv_ext_total, sales), 2)

    # External ads breakdown
    item['adv_bloggers'] = round(adv_bloggers, 2)
    item['adv_total'] = round(adv_total, 2)

    # DRR metrics (fractions)
    item['drr_total_frac'] = _safe_div(adv_total, rev_aspp)
    item['drr_internal_frac'] = _safe_div(adv_int, rev_aspp)
    item['drr_orders_aspp_frac'] = _safe_div(adv_total, orders_rub) if orders_rub else 0
    item['drr_orders_bspp_frac'] = _safe_div(adv_total, orders_rub) if orders_rub else 0
    item['drr_sales_aspp_frac'] = _safe_div(adv_total, rev_aspp)
    item['drr_sales_bspp_frac'] = _safe_div(adv_total, rev_bspp)
    item['drr_bloggers_bspp_frac'] = _safe_div(adv_bloggers, rev_bspp)
    item['drr_creators_bspp_frac'] = _safe_div(adv_creators, rev_bspp)
    item['drr_vk_bspp_frac'] = _safe_div(adv_vk, rev_bspp)
    item['drr_internal_bspp_frac'] = _safe_div(adv_int, rev_bspp)


# ---- ABC classification ----

def _calculate_abc(items, field, reverse=False):
    """Calculate ABC classification. A=top 80%, B=next 15%, C=bottom 5%.

    Returns dict[barcode -> 'A'|'B'|'C'].
    """
    valid = [(item, abs(item.get(field, 0))) for item in items if item.get(field, 0)]
    if not valid:
        return {item['barcode']: 'C' for item in items}

    sorted_items = sorted(valid, key=lambda x: x[1], reverse=not reverse)
    total = sum(v for _, v in sorted_items)
    if total == 0:
        return {item['barcode']: 'C' for item in items}

    cumulative = 0
    result = {}
    for item, val in sorted_items:
        cumulative += val
        pct = cumulative / total
        if pct <= 0.80:
            result[item['barcode']] = 'A'
        elif pct <= 0.95:
            result[item['barcode']] = 'B'
        else:
            result[item['barcode']] = 'C'

    # Items with 0 value -> C
    for item in items:
        if item['barcode'] not in result:
            result[item['barcode']] = 'C'

    return result


# ---- Row building ----

def _num(val):
    """Return numeric value or empty string if zero/None."""
    if val is None or val == 0:
        return ''
    return round(val, 2) if isinstance(val, float) else val


def _frac(val):
    """Return fraction for percentage column (e.g., 0.3635 for 36.35%). Empty if zero."""
    if val is None or val == 0:
        return ''
    return val


def _fmt_date(val):
    """Format date for sheet display."""
    if not val:
        return ''
    if hasattr(val, 'strftime'):
        return val.strftime('%d.%m.%Y %H:%M')
    return str(val)


def _formula_a(row_num: int) -> str:
    """INDEX/MATCH formula for column A (БАРКОД from 'Все товары')."""
    s = REF_SHEET
    return (f"=IF(ISNA(INDEX('{s}'!$A:$A;MATCH($C{row_num};"
            f"INDEX('{s}'!$O:$O;;);0)));;INDEX('{s}'!$A:$A;"
            f"MATCH($C{row_num};INDEX('{s}'!$O:$O;;);0)))")


def _formula_b(row_num: int) -> str:
    """INDEX/MATCH formula for column B (Нуменклатура from 'Все товары')."""
    s = REF_SHEET
    return (f"=IF(ISNA(INDEX('{s}'!$L:$L;MATCH($C{row_num};"
            f"INDEX('{s}'!$O:$O;;);0)));;INDEX('{s}'!$L:$L;"
            f"MATCH($C{row_num};INDEX('{s}'!$O:$O;;);0)))")


def _build_row(item, ref, abc_sales, abc_margin, abc_margin_pct, abc_turnover,
               row_num=None):
    """Build a 77-column row for the sheet.

    If row_num is given, A/B columns get INDEX/MATCH formulas.
    Otherwise (totals row), A/B are empty.
    """
    a_val = _formula_a(row_num) if row_num else ''
    b_val = _formula_b(row_num) if row_num else ''

    return [
        a_val,                                                     # A  БАРКОД (formula)
        b_val,                                                     # B  Нуменклатура (formula)
        item.get('article_size', ''),                              # C  Артикул+размер
        ref.get('photo', ''),                                      # D  Фото
        _fmt_date(item.get('min_sale_date', '')),                  # E  Мин. дата продажи
        ref.get('status', ''),                                     # F  Статус
        item.get('model', ''),                                     # G  Модель
        ref.get('importer', ''),                                   # H  Импортер
        ref.get('color_code', ''),                                 # I  Color code
        ref.get('skleyka_wb', ''),                                 # J  Склейка на WB
        ref.get('category', ''),                                   # K  Категория МС
        ref.get('model_osnova', ''),                               # L  Модель основа
        ref.get('collection', ''),                                 # M  Коллекция
        _num(item.get('orders_count', 0)),                         # N  Заказы шт
        _num(item.get('orders_per_day', 0)),                       # O  Заказы в день
        _num(item.get('avg_check_orders_bspp', 0)),                # P  Ср.чек заказа до СПП ₽
        _num(item.get('avg_check_orders_aspp', 0)),                # Q  Ср.чек заказа после СПП ₽
        _frac(item.get('buyout_frac', 0)),                         # R  Выкупы %
        _num(item.get('orders_table_rub', 0)),                     # S  Заказы до СПП ₽
        _num(item.get('sales_count', 0)),                          # T  Продажи шт
        _num(item.get('returns_count', 0)),                        # U  Возвраты шт
        _frac(item.get('returns_frac', 0)),                        # V  Возвраты %
        _num(item.get('avg_check_sales_bspp', 0)),                 # W  Ср.чек продажи до СПП ₽
        _num(item.get('avg_check_sales_aspp', 0)),                 # X  Ср.чек продажи после СПП ₽
        _frac(item.get('spp_frac', 0)),                            # Y  СПП %
        _num(item.get('revenue_before_spp', 0)),                   # Z  Продажи до СПП ₽
        abc_sales,                                                 # AA ABC продажи
        abc_margin,                                                # AB ABC маржа
        abc_margin_pct,                                            # AC ABC маржа %
        _num(item.get('margin', 0)),                               # AD Маржа ₽
        _frac(item.get('margin_before_spp_frac', 0)),              # AE Маржа до СПП %
        _frac(item.get('margin_before_spp_no_ads_frac', 0)),      # AF Маржа до СПП без РР %
        _frac(item.get('margin_after_spp_frac', 0)),               # AG Маржа после СПП %
        abc_turnover,                                              # AH ABC оборот
        _num(item.get('turnover_days', 0)),                        # AI Оборот дни
        _num(item.get('stock_rub', 0)),                            # AJ Остатки ₽
        _num(item.get('frozen_rub', 0)),                           # AK Заморожено ₽
        _num(item.get('stock_qty', 0)),                            # AL Остатки шт
        _num(item.get('margin_per_unit', 0)),                      # AM Маржа на ед ₽
        _num(item.get('commission', 0)),                           # AN Комиссия ₽
        _frac(item.get('commission_frac', 0)),                     # AO Комиссия %
        _num(item.get('commission_per_unit', 0)),                  # AP Комиссия на ед ₽
        _num(item.get('logistics', 0)),                            # AQ Логистика ₽
        _frac(item.get('logistics_frac', 0)),                      # AR Логистика %
        _num(item.get('logistics_per_unit', 0)),                   # AS Логистика на ед ₽
        _num(item.get('cost_of_goods', 0)),                        # AT Себес-ть ₽
        _frac(item.get('cogs_frac', 0)),                           # AU Себес-ть %
        _num(item.get('cogs_per_unit', 0)),                        # AV Себес-ть на ед ₽
        _num(item.get('adv_internal', 0)),                         # AW Реклама ₽
        _frac(item.get('adv_internal_frac', 0)),                   # AX Реклама %
        _num(item.get('adv_internal_per_unit', 0)),                # AY Реклама на ед ₽
        _num(item.get('storage', 0)),                              # AZ Хранение ₽
        _frac(item.get('storage_frac', 0)),                        # BA Хранение %
        _num(item.get('storage_per_unit', 0)),                     # BB Хранение на ед ₽
        _num(item.get('other_expenses', 0)),                       # BC Ост. расходы МП ₽
        _frac(item.get('other_frac', 0)),                          # BD Ост. расходы МП %
        _num(item.get('other_per_unit', 0)),                       # BE Ост. расходы МП на ед ₽
        _num(item.get('nds', 0)),                                  # BF НДС ₽
        _frac(item.get('nds_frac', 0)),                            # BG НДС %
        _num(item.get('nds_per_unit', 0)),                         # BH НДС на ед ₽
        _num(item.get('adv_ext_total', 0)),                         # BI Реклама внеш. ₽
        _frac(item.get('adv_external_frac', 0)),                   # BJ Реклама внеш. %
        _num(item.get('adv_external_per_unit', 0)),                # BK Реклама внеш. на ед ₽
        _num(item.get('adv_bloggers', 0)),                         # BL Реклама блогеры ₽
        _num(item.get('adv_creators', 0)),                         # BM Реклама креаторы ₽
        _num(item.get('adv_vk', 0)),                               # BN Реклама ВК ₽
        _num(item.get('adv_total', 0)),                            # BO Реклама итого ₽
        _frac(item.get('drr_total_frac', 0)),                     # BP ДРР рекл. %
        _frac(item.get('drr_internal_frac', 0)),                  # BQ ДРР рекл. (внутр.) %
        _frac(item.get('drr_orders_aspp_frac', 0)),               # BR ДРР от заказов (после СПП) %
        _frac(item.get('drr_orders_bspp_frac', 0)),               # BS ДРР от заказов (до СПП) %
        _frac(item.get('drr_sales_aspp_frac', 0)),                # BT ДРР от продаж (после СПП) %
        _frac(item.get('drr_sales_bspp_frac', 0)),                # BU ДРР от продаж (до СПП) %
        _frac(item.get('drr_bloggers_bspp_frac', 0)),             # BV ДРР блогеры %
        _frac(item.get('drr_creators_bspp_frac', 0)),             # BW ДРР креаторы %
        _frac(item.get('drr_vk_bspp_frac', 0)),                   # BX ДРР ВК %
        _frac(item.get('drr_internal_bspp_frac', 0)),             # BY ДРР внутр. %
    ]


def _build_totals_row(items, days_in_period):
    """Build the totals (summary) row."""
    total = _empty_entry('')
    for item in items:
        for field in SUMMABLE_FIELDS:
            total[field] = total.get(field, 0) + item.get(field, 0)
        total['orders_table_count'] = total.get('orders_table_count', 0) + item.get('orders_table_count', 0)
        total['orders_table_rub'] = total.get('orders_table_rub', 0) + item.get('orders_table_rub', 0)
        # NB: returns_count already summed via SUMMABLE_FIELDS loop above

    _calculate_derived_metrics(total, days_in_period)

    return _build_row(total, {}, '', '', '', '', row_num=None)


# ---- Sheet writing ----

def _write_to_sheet(ws, spreadsheet, display_start, display_end, totals_row, data_rows):
    """Write period, headers, totals, and data to sheet. Apply formatting."""
    # Clear everything
    last_row = ws.row_count
    num_cols = len(HEADERS_ROW2)
    if last_row >= 1:
        ws.batch_clear([f"A1:{_col_letter(num_cols)}{last_row}"])

    # Row 1: A1 = update text with period, B1/C1 = date pickers, D1 = checkbox
    iso_start = _dd_mm_to_iso(display_start)
    iso_end = _dd_mm_to_iso(display_end)
    msk_date, msk_time = get_moscow_datetime()
    ds_short = display_start[:5] if len(display_start) == 10 else display_start
    period_label = f"{ds_short} — {display_end}"
    period_row = [
        f"Обновлено: {msk_date} {msk_time} | Период: {period_label}",
        iso_start, iso_end, '',  # B1/C1 = date pickers, D1 = checkbox
    ] + [''] * (num_cols - 4)
    ws.update(
        range_name=f"A1:{_col_letter(num_cols)}1",
        values=[period_row],
        value_input_option='USER_ENTERED',
    )

    # Rows 2+: headers, totals, data — write with USER_ENTERED (for formulas in A/B)
    all_values = []
    all_values.append(HEADERS_ROW2)
    all_values.append(totals_row)
    all_values.extend(data_rows)

    end_row = len(all_values) + 1  # +1 because data starts at row 2
    ws.update(
        range_name=f"A2:{_col_letter(num_cols)}{end_row}",
        values=all_values,
        value_input_option='USER_ENTERED',
    )

    # Apply formatting
    _apply_formatting(spreadsheet, ws, len(data_rows), num_cols)

    # Checkbox in D1 for refresh trigger
    set_checkbox(ws, "D1")
    ws.update('D1', [[False]], value_input_option='USER_ENTERED')


def _apply_formatting(spreadsheet, ws, num_data_rows, num_cols):
    """Apply formatting: yellow headers, number formats, freeze, autofilter."""
    sheet_id = ws.id
    total_rows = 3 + num_data_rows  # 1 meta + 1 headers + 1 totals + data

    yellow_bg = {"red": 1.0, "green": 1.0, "blue": 0.0}
    reqs = []

    # --- Row 1: Yellow background + bold ---
    reqs.append({
        "repeatCell": {
            "range": _grid(sheet_id, 0, 1, 0, num_cols),
            "cell": {"userEnteredFormat": {
                "backgroundColor": yellow_bg,
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat.bold)",
        }
    })

    # --- Row 2 (headers): Yellow background + bold ---
    reqs.append({
        "repeatCell": {
            "range": _grid(sheet_id, 1, 2, 0, num_cols),
            "cell": {"userEnteredFormat": {
                "backgroundColor": yellow_bg,
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat.bold)",
        }
    })

    # --- Row 3 (totals): bold ---
    reqs.append({
        "repeatCell": {
            "range": _grid(sheet_id, 2, 3, 0, num_cols),
            "cell": {"userEnteredFormat": {
                "textFormat": {"bold": True},
            }},
            "fields": "userEnteredFormat(textFormat.bold)",
        }
    })

    # --- Number formats for data rows (rows 3+, 0-indexed: 2+) ---
    data_start = 2  # totals row (0-indexed)
    data_end = total_rows

    # Currency columns: #,##0.00" ₽"
    for col in sorted(_RUB_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '#,##0.00" ₽"'))

    # Percentage columns: 0.00%
    for col in sorted(_PCT_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '0.00%'))

    # Integer columns: #,##0
    for col in sorted(_INT_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '#,##0'))

    # Decimal columns: #,##0.0
    for col in sorted(_DEC_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '#,##0.0'))

    # --- Date format for B1:C1 (dd.mm.yyyy) ---
    reqs.append(_num_fmt_req(sheet_id, 0, 1, 1, 3, 'dd.mm.yyyy'))

    # --- Date validation for B1:C1 (enables date-picker) ---
    reqs.append({
        "setDataValidation": {
            "range": _grid(sheet_id, 0, 1, 1, 3),
            "rule": {
                "condition": {"type": "DATE_IS_VALID"},
                "showCustomUi": True,
            }
        }
    })

    # --- Freeze rows 1-3, column A ---
    reqs.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 3, "frozenColumnCount": 1},
            },
            "fields": "gridProperties(frozenRowCount,frozenColumnCount)",
        }
    })

    # --- AutoFilter on row 2 ---
    reqs.append({
        "setBasicFilter": {
            "filter": {
                "range": _grid(sheet_id, 1, total_rows, 0, num_cols),
            }
        }
    })

    spreadsheet.batch_update({"requests": reqs})


def _grid(sheet_id, sr, er, sc, ec):
    """Build a GridRange dict."""
    return {
        "sheetId": sheet_id,
        "startRowIndex": sr,
        "endRowIndex": er,
        "startColumnIndex": sc,
        "endColumnIndex": ec,
    }


def _num_fmt_req(sheet_id, sr, er, sc, ec, pattern):
    """Build a repeatCell request for numberFormat."""
    return {
        "repeatCell": {
            "range": _grid(sheet_id, sr, er, sc, ec),
            "cell": {"userEnteredFormat": {
                "numberFormat": {"type": "NUMBER", "pattern": pattern},
            }},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _col_letter(col_num: int) -> str:
    """Convert 1-based column number to letter(s). E.g. 1->A, 27->AA."""
    result = ""
    c = col_num
    while c > 0:
        c, remainder = divmod(c - 1, 26)
        result = chr(65 + remainder) + result
    return result
