"""Sync financial data -> sheet 'Фин данные NEW'.

Reads barcodes from column A (rows 3+) — filled by user.
Writes only financial columns H-V (15 metrics) from DB.
Does NOT touch columns A-G (reference data managed by user).
"""

from __future__ import annotations

import logging

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    set_checkbox,
)
from shared.data_layer import (
    get_wb_fin_data_by_barcode,
    get_wb_orders_by_barcode,
    get_ozon_fin_data_by_barcode,
    get_ozon_orders_by_barcode,
    get_wb_barcode_to_marketplace_mapping,
)
from services.sheets_sync.config import GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name
from services.sheets_sync.sync.sync_fin_data import (
    _resolve_dates,
    _merge_data,
    _calculate_derived_metrics,
    _safe_div,
    _num_fmt_req,
)

logger = logging.getLogger(__name__)

SHEET_NAME = "Фин данные NEW"

# Financial columns H-V (0-indexed: 7-21)
# H(7) Себест  I(8) Ср.чек до СПП  J(9) Ср.чек после СПП  K(10) Заказы/день
# L(11) Выкуп  M(12) Маржа₽  N(13) Маржин.доСПП  O(14) Логист  P(15) Ост.расх
# Q(16) НДС  R(17) Реклама  S(18) МаржаБезДРР  T(19) ДРРитого  U(20) ДРРвн  V(21) ДРРвнеш
_RUB_COLS = {7, 8, 9, 12, 14, 15, 16, 17}          # H,I,J,M,O,P,Q,R
_PCT_COLS = {11, 13, 18, 19, 20, 21}                # L,N,S,T,U,V
_DEC_COLS = {10}                                     # K (заказы в день)

_FIN_COLS = 15          # Number of financial columns (H through V)
_EMPTY_FIN_ROW = [0] * _FIN_COLS


# ---- Helpers ----

def _num0(val):
    """Return numeric value, 0 if zero/None (never empty)."""
    if val is None:
        return 0
    return round(val, 2) if isinstance(val, float) else val


def _frac0(val):
    """Return fraction, 0 if zero/None (never empty)."""
    if val is None:
        return 0
    return val


# ---- Sheet readers ----

def _read_barcodes_from_sheet(ws) -> list[str]:
    """Read barcodes from column A, rows 3+. Preserves row alignment."""
    col_a = ws.col_values(1)  # 1-indexed column
    barcodes = []
    for val in col_a[2:]:     # Skip rows 1 (meta) and 2 (headers)
        bc = str(val).strip()
        barcodes.append(bc)   # Keep even empty to preserve row alignment
    return barcodes


# ---- Row building ----

def _build_fin_row(item):
    """Build financial-only row (columns H-V, 15 values)."""
    sales = item.get('sales_count', 0)
    margin = item.get('margin', 0)
    rev_aspp = item.get('revenue_after_spp', 0)
    adv_int = item.get('adv_internal', 0)
    adv_ext = item.get('adv_external', 0)
    adv_vk = item.get('adv_vk', 0)
    adv_creators = item.get('adv_creators', 0)
    adv_total = adv_int + adv_ext + adv_vk + adv_creators
    adv_ext_total = adv_ext + adv_vk + adv_creators

    return [
        _num0(item.get('cogs_per_unit', 0)),                    # H  Себестоимость PB
        _num0(item.get('avg_check_orders_bspp', 0)),            # I  Ср.чек до СПП
        _num0(item.get('avg_check_orders_aspp', 0)),            # J  Ср.чек после СПП
        _num0(item.get('orders_per_day', 0)),                   # K  Заказы в день
        _frac0(item.get('buyout_frac', 0)),                     # L  Выкупаемость
        _num0(margin),                                          # M  Маржа ₽
        _frac0(item.get('margin_before_spp_frac', 0)),          # N  Маржинальность до СПП
        _num0(item.get('logistics_per_unit', 0)),               # O  Логистика на ед.
        _num0(item.get('other_per_unit', 0)),                   # P  Ост. расходы на ед.
        _num0(item.get('nds_per_unit', 0)),                     # Q  НДС на ед.
        _num0(round(_safe_div(adv_total, sales), 2)),           # R  Реклама на ед.
        _frac0(item.get('margin_before_spp_no_ads_frac', 0)),   # S  Маржа без ДРР (%)
        _frac0(_safe_div(adv_total, rev_aspp)),                 # T  ДРР итого
        _frac0(_safe_div(adv_int, rev_aspp)),                   # U  ДРР внутр
        _frac0(_safe_div(adv_ext_total, rev_aspp)),             # V  ДРР внеш
    ]


# ---- Sheet writing ----

def _write_fin_data(ws, spreadsheet, display_start, display_end, fin_rows, num_barcodes):
    """Write financial data only (H3:V) + update meta A1. Do NOT touch A-G."""
    last_row = ws.row_count
    data_start_row = 3

    # 1. Clear only financial columns H3:V{last_row}
    if last_row >= data_start_row:
        ws.batch_clear([f"H{data_start_row}:V{last_row}"])

    # 2. Write financial data H3:V{end}
    if fin_rows:
        end_row = data_start_row + len(fin_rows) - 1
        ws.update(
            range_name=f"H{data_start_row}:V{end_row}",
            values=fin_rows,
            value_input_option='USER_ENTERED',
        )

    # 3. Update meta label in A1
    msk_date, msk_time = get_moscow_datetime()
    ds_short = display_start[:5] if len(display_start) == 10 else display_start
    period_label = f"{ds_short} — {display_end}"
    ws.update(
        range_name='A1',
        values=[[f"Обновлено: {msk_date} {msk_time} | Период: {period_label}"]],
        value_input_option='USER_ENTERED',
    )

    # 4. Apply number formatting to financial columns
    _apply_formatting(spreadsheet, ws, num_barcodes)

    # 5. Reset checkbox
    set_checkbox(ws, "D1")
    ws.update('D1', [[False]], value_input_option='USER_ENTERED')


def _apply_formatting(spreadsheet, ws, num_data_rows):
    """Apply number formats to financial columns H-V, rows 3+."""
    sheet_id = ws.id
    data_start = 2              # 0-indexed row 3
    data_end = 2 + num_data_rows

    reqs = []

    # Currency: H,I,J,M,O,P,Q,R
    for col in sorted(_RUB_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '#,##0.00" ₽"'))

    # Percentage: L,N,S,T,U,V
    for col in sorted(_PCT_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '0.00%'))

    # Decimal: K
    for col in sorted(_DEC_COLS):
        reqs.append(_num_fmt_req(sheet_id, data_start, data_end, col, col + 1,
                                 '#,##0.0'))

    if reqs:
        spreadsheet.batch_update({"requests": reqs})


# ---- Main sync ----

def sync(start_date: str | None = None, end_date: str | None = None) -> int:
    """Sync financial data for the given period to 'Фин данные NEW' sheet.

    Reads barcodes from column A (rows 3+), fetches financial data from DB,
    and writes only to columns H-V. Does NOT modify columns A-G.
    """
    from datetime import datetime

    # 1. Connect to Google Sheets
    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet_id = get_active_spreadsheet_id()
    spreadsheet = gc.open_by_key(spreadsheet_id)
    sheet_name = get_sheet_name(SHEET_NAME)
    logger.info("Target sheet: '%s' in spreadsheet %s", sheet_name, spreadsheet_id[:8])

    ws = get_or_create_worksheet(spreadsheet, sheet_name, rows=5000, cols=25)

    # 2. Resolve dates from B1/C1
    iso_start, iso_end, display_start, display_end = _resolve_dates(
        ws, start_date, end_date
    )
    days_in_period = max((
        datetime.strptime(iso_end, '%Y-%m-%d') -
        datetime.strptime(iso_start, '%Y-%m-%d')
    ).days, 1)
    logger.info("Period: %s — %s (%d days)", display_start, display_end, days_in_period)

    # 3. Read barcodes from column A (rows 3+)
    sheet_barcodes = _read_barcodes_from_sheet(ws)
    if not sheet_barcodes:
        logger.warning("No barcodes found in column A (rows 3+)")
        return 0
    logger.info("Sheet barcodes: %d rows in column A", len(sheet_barcodes))

    # 4. Fetch WB data
    logger.info("Fetching WB financial data...")
    wb_fin = get_wb_fin_data_by_barcode(iso_start, iso_end)
    wb_orders = get_wb_orders_by_barcode(iso_start, iso_end)
    logger.info("WB: %d fin barcodes, %d order barcodes", len(wb_fin), len(wb_orders))

    # 5. Fetch OZON data
    logger.info("Fetching OZON financial data...")
    ozon_fin = get_ozon_fin_data_by_barcode(iso_start, iso_end)
    ozon_orders = get_ozon_orders_by_barcode(iso_start, iso_end)
    logger.info("OZON: %d fin barcodes, %d order barcodes", len(ozon_fin), len(ozon_orders))

    # 6. Load barcode mapping (GS2/GS1 → marketplace)
    gs2_mapping = get_wb_barcode_to_marketplace_mapping()

    # 7. Merge all data by barcode + calculate metrics
    combined = _merge_data(wb_fin, wb_orders, ozon_fin, ozon_orders, gs2_mapping=gs2_mapping)
    logger.info("Combined: %d unique barcodes from DB", len(combined))

    for item in combined.values():
        _calculate_derived_metrics(item, days_in_period)

    # 8. Build financial rows aligned to sheet barcodes
    fin_rows = []
    matched = 0
    for bc in sheet_barcodes:
        item = combined.get(bc)
        if item:
            fin_rows.append(_build_fin_row(item))
            matched += 1
        else:
            fin_rows.append(list(_EMPTY_FIN_ROW))  # copy to avoid shared mutation

    logger.info("Matched: %d / %d barcodes", matched, len(sheet_barcodes))

    # 9. Write only financial columns H-V
    logger.info("Writing financial data to '%s'...", sheet_name)
    _write_fin_data(ws, spreadsheet, display_start, display_end, fin_rows, len(sheet_barcodes))

    logger.info("Done: %d/%d barcodes matched in '%s'", matched, len(sheet_barcodes), sheet_name)
    return matched
