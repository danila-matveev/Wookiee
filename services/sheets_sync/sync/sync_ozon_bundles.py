from __future__ import annotations

"""Sync OZON bundle prices -> sheet 'Склейки Озон'."""

import logging

from shared.clients.ozon_client import OzonClient
from shared.clients.sheets_client import (
    get_client,
    get_or_create_worksheet,
    write_range,
)
from services.sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, get_active_spreadsheet_id, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Склейки Озон"

# CSV column headers for lookup
COL_SKU = "SKU"
COL_PRICE = "Цена до скидки (перечеркнутая цена), ₽"
COL_DISCOUNTED = "Текущая цена с учетом скидки, ₽"
COL_FBO_STOCK = "Доступно к продаже по схеме FBO, шт."


def sync() -> int:
    """Fetch OZON prices/stocks for items in 'Склейки Озон' and update columns R, S, V.

    Reads cabinet from column A, artikul from column E (starting row 3).
    For each cabinet, creates OZON report, parses CSV, and writes:
      R (18) = price before discount
      S (19) = discounted price
      V (22) = FBO stock

    Returns number of items processed.
    """
    logger.info("=== sync_ozon_bundles: start ===")

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(get_active_spreadsheet_id())
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    # 1. Read data from sheet (columns A-E, starting row 3)
    last_row = ws.row_count
    if last_row < 3:
        logger.warning("No data in sheet")
        return 0

    all_values = ws.get_all_values()
    if len(all_values) < 3:
        logger.warning("Not enough rows in sheet")
        return 0

    # 2. Group artikuls by cabinet
    cabinet_items: dict[str, list[dict]] = {}
    for row_idx, row in enumerate(all_values[2:], start=3):  # Skip rows 1-2
        if len(row) < 5:
            continue
        cabinet_name = str(row[0]).strip()  # Column A
        artikul = str(row[4]).strip()  # Column E
        if cabinet_name and artikul:
            if cabinet_name not in cabinet_items:
                cabinet_items[cabinet_name] = []
            cabinet_items[cabinet_name].append({
                "artikul": artikul,
                "row_index": row_idx,
            })

    logger.info("Cabinets found: %s", {k: len(v) for k, v in cabinet_items.items()})

    # 3. Clear old data in columns R, S, V (starting row 3)
    data_rows = len(all_values) - 2
    if data_rows > 0:
        ws.batch_clear([
            f"R3:S{len(all_values)}",
            f"V3:V{len(all_values)}",
        ])

    # 4. Process each cabinet
    cabinet_map = {c.name: c for c in ALL_CABINETS}
    total_written = 0

    for cab_name, items in cabinet_items.items():
        cabinet = cabinet_map.get(cab_name)
        if not cabinet:
            logger.warning("Unknown cabinet: %s", cab_name)
            continue

        # Filter to valid numeric artikuls (SKUs)
        valid_skus = []
        for item in items:
            try:
                sku = int(item["artikul"])
                if sku > 0:
                    valid_skus.append(sku)
            except (ValueError, TypeError):
                pass

        if not valid_skus:
            logger.info("[%s] No valid SKUs", cab_name)
            continue

        logger.info("[%s] Processing %d SKUs", cab_name, len(valid_skus))

        ozon = OzonClient(
            client_id=cabinet.ozon_client_id,
            api_key=cabinet.ozon_api_key,
            cabinet_name=cabinet.name,
        )
        try:
            rows = ozon.get_stocks_and_prices_report(valid_skus)
        finally:
            ozon.close()

        if not rows or len(rows) < 2:
            logger.warning("[%s] No report data", cab_name)
            continue

        # 5. Parse CSV headers and build SKU -> data map
        headers = rows[0]
        sku_idx = _find_col(headers, COL_SKU, "SKU")
        price_idx = _find_col(headers, COL_PRICE, "перечеркнутая цена")
        discounted_idx = _find_col(headers, COL_DISCOUNTED, "Текущая цена")
        fbo_idx = _find_col(headers, COL_FBO_STOCK, "FBO")

        if sku_idx is None:
            logger.error("[%s] SKU column not found in CSV headers", cab_name)
            continue

        sku_data: dict[str, dict] = {}
        for row in rows[1:]:
            if sku_idx < len(row):
                sku = row[sku_idx].strip().lstrip("'")
                price = _parse_number(row[price_idx]) if price_idx is not None and price_idx < len(row) else 0
                discounted = _parse_number(row[discounted_idx]) if discounted_idx is not None and discounted_idx < len(row) else 0
                fbo = _parse_int(row[fbo_idx]) if fbo_idx is not None and fbo_idx < len(row) else 0
                sku_data[sku] = {"price": price, "discountedPrice": discounted, "stock": fbo}

        logger.info("[%s] Parsed %d SKU entries from CSV", cab_name, len(sku_data))

        # 6. Write data to sheet for each item
        for item in items:
            data = sku_data.get(item["artikul"])
            if data:
                row_num = item["row_index"]
                write_range(ws, start_row=row_num, start_col=18, data=[[data["price"], data["discountedPrice"]]])
                write_range(ws, start_row=row_num, start_col=22, data=[[data["stock"]]])
                total_written += 1

    logger.info("=== sync_ozon_bundles: done (%d items updated) ===", total_written)
    return total_written


def _find_col(headers: list[str], exact: str, fallback: str) -> int | None:
    """Find column index by exact match or partial match."""
    for i, h in enumerate(headers):
        if h.strip() == exact:
            return i
    for i, h in enumerate(headers):
        if fallback.lower() in h.lower():
            return i
    return None


def _parse_number(value: str) -> float:
    """Parse a number from CSV value, handling apostrophes and commas."""
    s = str(value).lstrip("'").replace(",", ".").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def _parse_int(value: str) -> int:
    """Parse an integer from CSV value, handling apostrophes."""
    s = str(value).lstrip("'").strip()
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0
