from __future__ import annotations

"""Sync МойСклад -> sheet 'МойСклад_АПИ'."""

import logging

from wb_sheets_sync.clients.moysklad_client import MoySkladClient
from wb_sheets_sync.clients.sheets_client import (
    get_client,
    get_moscow_datetime,
    get_moscow_now,
    get_or_create_worksheet,
    set_checkbox,
    write_range,
)
from wb_sheets_sync.config import GOOGLE_SA_FILE, MOYSKLAD_TOKEN, SPREADSHEET_ID, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "МойСклад_АПИ"

HEADERS = [
    "Артикул Ozon", "Product ID", "Баркод (атрибут)", "Barcode EAN13", "Barcode GTIN",
    "Нуменклатура", "Артикул", "Модель", "Название для Этикетки", "Ozon >>",
    "Артикул Ozon (2)", "Ozon Product ID", "FBO OZON SKU ID", "Размер", "Цвет",
    "О товаре >>>", "Продавец", "Фабрика", "Состав", "ТНВЭД", "SKU", "Сolor",
    "Color code", "Price", "Вес", "Длина", "Ширина", "Высота", "Объем",
    "Кратность короба", "Импортер", "Адрес Импортера", "Статус WB", "Статус OZON",
    "Склейка на WB", "Категория", "Модель основа", "Коллекция",
    "Остатки в офисе", "Товары с приемкой", "Товары в пути", "Себестоимость",
]


def sync() -> int:
    """Fetch assortment from MoySklad and write to Google Sheet.

    Returns number of rows written.
    """
    logger.info("=== sync_moysklad: start ===")

    ms = MoySkladClient(MOYSKLAD_TOKEN)
    try:
        # 1. Get formatted datetime in Moscow timezone
        now = get_moscow_now()
        formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")

        # 2. Fetch assortment (paginated)
        all_rows = ms.fetch_assortment(moment=formatted_date)
        logger.info("Fetched %d assortment rows", len(all_rows))

        if not all_rows:
            logger.warning("No data from MoySklad API")
            return 0

        # 3. Filter: only items with attributes AND barcodes.length > 1
        # Note: in JS `[]` is truthy, so GAS includes items with empty attributes array.
        # Match GAS: check `"attributes" in row` (not falsiness of the list).
        filtered = [
            row for row in all_rows
            if "attributes" in row and len(row.get("barcodes", [])) > 1
        ]
        logger.info("Filtered to %d items (have attributes + barcodes)", len(filtered))

        # 4. Process each row into 38-column format
        data_rows = []
        for row in filtered:
            processed = _process_row(row, ms)
            if processed:
                data_rows.append(processed)

        if not data_rows:
            logger.warning("No valid rows after processing")
            return 0

        # 5. Write to Google Sheet
        sheet_name = get_sheet_name(SHEET_NAME)
        gc = get_client(GOOGLE_SA_FILE)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        ws = get_or_create_worksheet(spreadsheet, sheet_name)

        # Clear data from row 3 down (preserve rows 1-2: datetime, headers, manual button)
        last_row = ws.row_count
        last_col = max(ws.col_count, len(HEADERS))
        if last_row >= 3:
            ws.batch_clear([f"A3:{_col_letter(last_col)}{last_row}"])

        # Row 1, A1: datetime only (like original GAS: single cell)
        now_dt = get_moscow_now()
        ws.update_acell("A1", now_dt.strftime("%Y-%m-%d %H:%M:%S"))

        # Row 2: All 42 headers (safe to overwrite — keeps them in sync)
        write_range(ws, start_row=2, start_col=1, data=[HEADERS])

        # Checkbox for refresh in C1
        set_checkbox(ws, "C1")

        # Row 3+: Main data
        if data_rows:
            write_range(ws, start_row=3, start_col=1, data=data_rows)

        logger.info("Written %d main rows", len(data_rows))

        # 6. Fetch and write additional data
        product_ids = [row[1] for row in data_rows if row[1]]  # Column B = product ID
        _write_additional_data(ms, ws, product_ids, formatted_date)

        logger.info("=== sync_moysklad: done (%d rows) ===", len(data_rows))
        return len(data_rows)

    finally:
        ms.close()


def _process_row(row: dict, ms: MoySkladClient) -> list | None:
    """Process a single MoySklad assortment row into 38-column format."""
    try:
        attr_values = ms.extract_attributes(row)
        ean13, gtin = ms.extract_barcodes(row)
        weight = row.get("weight", 0)

        # Normalize price (attr index 18 = "Price")
        price_raw = attr_values[18]
        price = _normalize_price(price_raw)

        # Build 38-column row (A through AL)
        return [
            attr_values[0],   # A: Артикул Ozon
            row.get("id", ""),  # B: Product ID (critical for additional data)
            attr_values[1],   # C: Баркод (attribute)
            ean13,            # D: Barcode EAN13
            gtin,             # E: Barcode GTIN
            attr_values[2],   # F: Нуменклатура
            row.get("article", ""),  # G: Артикул
            attr_values[3],   # H: Модель
            attr_values[4],   # I: Название для Этикетки
            attr_values[5],   # J: Ozon >>
            attr_values[0],   # K: Артикул Ozon (duplicate)
            attr_values[6],   # L: Ozon Product ID
            attr_values[7],   # M: FBO OZON SKU ID
            attr_values[8],   # N: Размер
            attr_values[9],   # O: Цвет
            attr_values[10],  # P: О товаре >>>
            attr_values[11],  # Q: Продавец
            attr_values[12],  # R: Фабрика
            attr_values[13],  # S: Состав
            attr_values[14],  # T: ТНВЭД
            attr_values[15],  # U: SKU
            attr_values[16],  # V: Сolor
            attr_values[17],  # W: Color code
            price,            # X: Price (normalized)
            weight,           # Y: Вес
            attr_values[19],  # Z: Длина
            attr_values[20],  # AA: Ширина
            attr_values[21],  # AB: Высота
            attr_values[22],  # AC: Объем
            attr_values[23],  # AD: Кратность короба
            attr_values[24],  # AE: Импортер
            attr_values[25],  # AF: Адрес Импортера
            attr_values[26],  # AG: Статус WB
            attr_values[27],  # AH: Статус OZON
            attr_values[28],  # AI: Склейка на WB
            attr_values[29],  # AJ: Категория
            attr_values[30],  # AK: Модель основа
            attr_values[31],  # AL: Коллекция
        ]
    except Exception as e:
        logger.error("Error processing row: %s", e)
        return None


def _write_additional_data(
    ms: MoySkladClient,
    ws,
    product_ids: list[str],
    formatted_date: str,
) -> None:
    """Fetch and write 4 additional columns (AM-AP) to the sheet."""
    start_col = MoySkladClient.ADDITIONAL_COLUMNS_START

    # Headers are already written at row 2 in sync() via HEADERS constant

    if not product_ids:
        return

    # 1. Office stock
    logger.info("Fetching office stock...")
    office_data = ms.fetch_assortment(
        moment=formatted_date,
        store_url=f"https://api.moysklad.ru/api/remap/1.2/entity/store/{ms.STORE_MAIN}",
    )
    office_map = _build_id_value_map(office_data, "quantity")
    office_col = [[office_map.get(pid, 0)] for pid in product_ids]
    write_range(ws, start_row=3, start_col=start_col, data=office_col)

    # 2. Acceptance stock (combined main + acceptance stores)
    logger.info("Fetching acceptance stock...")
    try:
        acceptance_data = ms.fetch_stock_by_store(ms.STORE_ACCEPTANCE)
        main_data = ms.fetch_stock_by_store(ms.STORE_MAIN)
        acceptance_map = _build_stock_map(acceptance_data + main_data)
        acceptance_col = [[acceptance_map.get(pid, 0)] for pid in product_ids]
    except Exception as e:
        logger.error("Error fetching acceptance stock: %s", e)
        acceptance_col = [[0] for _ in product_ids]
    write_range(ws, start_row=3, start_col=start_col + 1, data=acceptance_col)

    # 3. Orders in transit
    logger.info("Fetching orders in transit...")
    orders = ms.fetch_purchase_orders()
    logger.info("Active purchase orders: %d", len(orders))
    transit_map: dict[str, int] = {}
    total_positions = 0
    for order in orders:
        positions = ms.fetch_order_positions(order.get("id", ""))
        total_positions += len(positions)
        for pos in positions:
            href = pos.get("assortment", {}).get("meta", {}).get("href", "")
            assort_id = href.split("/")[-1] if href else ""
            if assort_id:
                transit_map[assort_id] = transit_map.get(assort_id, 0) + pos.get("quantity", 0)
    transit_total = sum(v for v in transit_map.values())
    logger.info("Transit: %d positions across %d products, total qty=%d", total_positions, len(transit_map), transit_total)
    transit_col = [[transit_map.get(pid, 0)] for pid in product_ids]
    write_range(ws, start_row=3, start_col=start_col + 2, data=transit_col)

    # 4. Cost (sebstoimost)
    logger.info("Fetching cost data...")
    stock_all = ms.fetch_stock_all()
    cost_map = _build_id_value_map(stock_all, "price", is_cost=True)
    cost_col = [[cost_map.get(pid, 0)] for pid in product_ids]
    write_range(ws, start_row=3, start_col=start_col + 3, data=cost_col)

    logger.info("Additional data written for %d products", len(product_ids))


def _build_id_value_map(data: list[dict], field: str, is_cost: bool = False) -> dict:
    """Build {product_id: value} map from API response."""
    result = {}
    for item in data:
        href = item.get("meta", {}).get("href", "")
        item_id = href.split("/")[-1].split("?")[0] if href else ""
        if not item_id:
            continue
        value = item.get(field, 0)
        if value is None:
            value = 0
        if is_cost and value:
            # Cost is in kopecks, convert to rubles as float
            value = round(int(value) / 100, 2)
        result[item_id] = value
    return result


def _build_stock_map(data: list[dict]) -> dict:
    """Build {product_id: stock} map from stock by store response."""
    result = {}
    for item in data:
        href = item.get("meta", {}).get("href", "")
        item_id = href.split("/")[-1].split("?")[0] if href else ""
        if item_id:
            result[item_id] = result.get(item_id, 0) + item.get("stock", 0)
    return result


def _normalize_price(value) -> float:
    """Normalize price value to float."""
    if not value:
        return 0.0
    s = str(value).replace("¥", "").replace("€", "").replace("$", "").replace("₽", "").strip()
    s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except (ValueError, TypeError):
        return 0.0


def _col_letter(col: int) -> str:
    """Convert column number to letter(s). E.g. 1->A, 27->AA."""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result
