from __future__ import annotations

"""Sync WB bundle prices -> sheet 'Склейки WB'."""

import logging

from shared.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    write_range,
)
from shared.clients.wb_client import WBClient
from services.sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Склейки WB"


def sync() -> int:
    """Fetch WB prices and write to 'Склейки WB' columns S-V.

    Reads nmIDs from column D (D3+), looks up prices from both cabinets,
    writes price/discount/discountedPrice/clubDiscount to columns S-V (19-22).

    Returns number of nmIDs processed.
    """
    logger.info("=== sync_wb_bundles: start ===")

    # 1. Fetch prices from both cabinets
    all_prices = []
    for cabinet in ALL_CABINETS:
        client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=cabinet.name)
        try:
            items = client.get_prices()
            all_prices.extend(items)
            logger.info("[%s] Got %d price items", cabinet.name, len(items))
        finally:
            client.close()

    # 2. Build lookup map: nmID -> {price, discount, discountedPrice, clubDiscount}
    price_map: dict[int, dict] = {}
    for item in all_prices:
        nm_id = item.get("nmID", 0)
        if not nm_id:
            continue
        sizes = item.get("sizes", [])
        price = sizes[0].get("price", 0) if sizes else 0
        discounted_price = sizes[0].get("discountedPrice", 0) if sizes else 0
        club_discounted_price = sizes[0].get("clubDiscountedPrice", 0) if sizes else 0
        price_map[nm_id] = {
            "price": price,
            "discount": item.get("discount", 0),
            "discountedPrice": round(discounted_price) if discounted_price else "",
            "clubDiscount": item.get("clubDiscount", 0),
        }

    logger.info("Price map: %d items", len(price_map))

    # 3. Open sheet and read nmIDs from column D (D3+)
    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    col_d = ws.col_values(4)  # Column D
    nm_ids = col_d[2:]  # Skip rows 1-2 (headers), start from D3

    if not nm_ids:
        logger.info("Sheet '%s' has no nmIDs in column D — skipping", sheet_name)
        return 0

    # 4. Build data for columns S-V
    values_to_write = []
    for nm_id_str in nm_ids:
        nm_id_str = str(nm_id_str).strip()
        if not nm_id_str or not nm_id_str.isdigit():
            values_to_write.append(["", "", "", ""])
            continue

        nm_id = int(nm_id_str)
        data = price_map.get(nm_id)
        if data:
            values_to_write.append([
                data["price"],
                data["discount"],
                data["discountedPrice"],
                data["clubDiscount"],
            ])
        else:
            values_to_write.append(["", "", "", ""])

    # 5. Clear old data in S-V and write new
    last_row = ws.row_count
    if last_row >= 3:
        ws.batch_clear([f"S3:V{last_row}"])

    if values_to_write:
        write_range(ws, start_row=3, start_col=19, data=values_to_write)

    # 6. Write timestamp to S1
    date_str, time_str = get_moscow_datetime()
    ws.update_acell("S1", f"{time_str} {date_str}")

    logger.info("=== sync_wb_bundles: done (%d nmIDs) ===", len(nm_ids))
    return len(nm_ids)
