"""Sync WB warehouse remains -> sheet 'WB остатки'."""

import logging

from shared.clients.sheets_client import (
    clear_and_write,
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    set_checkbox,
)
from shared.clients.wb_client import WBClient
from services.sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "WB остатки"


def sync() -> int:
    """Fetch warehouse remains from WB and write to Google Sheet.

    Returns number of rows written.
    """
    logger.info("=== sync_wb_stocks: start ===")

    # 1. Fetch data from both cabinets
    all_items = []
    for cabinet in ALL_CABINETS:
        client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
        try:
            items = client.get_warehouse_remains()
            for item in items:
                item["source"] = cabinet.name
            all_items.extend(items)
            logger.info("[%s] Got %d items", cabinet.name, len(items))
        finally:
            client.close()

    if not all_items:
        logger.warning("No data from WB API")
        return 0

    # 2. Collect unique barcodes and warehouse names
    all_warehouses = set()
    for item in all_items:
        for wh in item.get("warehouses", []):
            all_warehouses.add(wh.get("warehouseName", ""))

    # Sort warehouses: special ones first, then alphabetical
    special = [
        "В пути до получателей",
        "В пути возвраты на склад WB",
        "Всего находится на складах",
    ]
    regular = sorted(wh for wh in all_warehouses if wh not in special)
    warehouse_names = [s for s in special if s in all_warehouses] + regular

    # 3. Build pivot table: unique barcodes as rows, warehouses as columns
    unique_barcodes = list(dict.fromkeys(item.get("barcode", "") for item in all_items))

    data_rows = []
    for barcode in unique_barcodes:
        # Find all items with this barcode (may span cabinets)
        matching = [item for item in all_items if item.get("barcode") == barcode]
        if not matching:
            continue

        main = matching[0]
        nm_id_raw = main.get("nmId", "")
        nm_id = int(nm_id_raw) if nm_id_raw and str(nm_id_raw).isdigit() else nm_id_raw
        volume_raw = main.get("volume", "")
        try:
            volume = float(volume_raw) if volume_raw else 0.0
        except (ValueError, TypeError):
            volume = volume_raw
        row = [
            main.get("barcode", ""),
            main.get("vendorCode", ""),
            main.get("techSize", ""),
            nm_id,
            main.get("subjectName", ""),
            main.get("brand", ""),
            volume,
            main.get("source", ""),
        ]

        # Sum quantities per warehouse across all matching items
        for wh_name in warehouse_names:
            qty = 0
            for item in matching:
                for wh in item.get("warehouses", []):
                    if wh.get("warehouseName") == wh_name:
                        qty += wh.get("quantity", 0)
                        break
            row.append(qty)

        data_rows.append(row)

    # 4. Write to Google Sheet
    headers = [
        "Баркод", "Артикул", "Размер", "NMID",
        "Категория", "Бренд", "Объем", "Кабинет",
    ] + warehouse_names

    date_str, time_str = get_moscow_datetime()
    sheet_name = get_sheet_name(SHEET_NAME)

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    row_count = clear_and_write(
        worksheet=ws,
        headers=headers,
        data=data_rows,
        meta_cells=[
            (1, 1, f"Обновлено: {date_str} {time_str}"),
        ],
        header_row=2,
        data_start_row=3,
    )

    # Checkbox for refresh
    set_checkbox(ws, "C1")

    logger.info("=== sync_wb_stocks: done (%d rows) ===", row_count)
    return row_count
