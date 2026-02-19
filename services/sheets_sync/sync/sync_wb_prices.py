"""Sync WB prices -> sheet 'WB Цены'."""

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

SHEET_NAME = "WB Цены"


def sync() -> int:
    """Fetch prices from WB and write to Google Sheet.

    Returns number of rows written.
    """
    logger.info("=== sync_wb_prices: start ===")

    # 1. Fetch prices from both cabinets (with pagination)
    all_rows = []
    for cabinet in ALL_CABINETS:
        client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
        try:
            items = client.get_prices()
            for item in items:
                nm_id = item.get("nmID", "")
                vendor_code = item.get("vendorCode", "")
                price = 0
                sizes = item.get("sizes", [])
                if sizes:
                    price = sizes[0].get("price", 0)
                discount = item.get("discount", 0)
                all_rows.append([nm_id, vendor_code, cabinet.name, price, discount])
            logger.info("[%s] Got %d prices", cabinet.name, len(items))
        finally:
            client.close()

    if not all_rows:
        logger.warning("No price data from WB API")
        return 0

    # 2. Write to Google Sheet
    headers = ["nmID", "Артикул", "Кабинет", "Цена", "Скидка %"]

    date_str, time_str = get_moscow_datetime()
    sheet_name = get_sheet_name(SHEET_NAME)

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    row_count = clear_and_write(
        worksheet=ws,
        headers=headers,
        data=all_rows,
        meta_cells=[
            (1, 1, f"Обновлено: {date_str} {time_str}"),
        ],
        header_row=2,
        data_start_row=3,
    )

    # Checkbox for refresh
    set_checkbox(ws, "C1")

    logger.info("=== sync_wb_prices: done (%d rows) ===", row_count)
    return row_count
