from __future__ import annotations

"""Sync OZON stocks & prices -> sheet 'Ozon остатки и цены'."""

import logging

from shared.clients.ozon_client import OzonClient
from shared.clients.sheets_client import (
    clear_and_write,
    get_client,
    get_moscow_datetime,
    get_or_create_worksheet,
    set_checkbox,
    to_number,
)
from services.sheets_sync.config import ALL_CABINETS, GOOGLE_SA_FILE, SPREADSHEET_ID, get_sheet_name

logger = logging.getLogger(__name__)

SHEET_NAME = "Ozon остатки и цены"

# Headers from GAS (30 columns: 29 CSV + Cabinet)
HEADERS = [
    "Артикул",
    "Ozon Product ID",
    "SKU",
    "Barcode",
    "Название товара",
    "Контент-рейтинг",
    "Бренд",
    "Статус товара",
    "Метки",
    "Отзывы",
    "Рейтинг",
    "Видимость на Ozon",
    "Причины скрытия",
    "Дата создания",
    "Категория",
    "Тип",
    "Объем товара, л",
    "Объемный вес, кг",
    "Доступно к продаже по схеме FBO, шт.",
    "Зарезервировано, шт",
    "Доступно к продаже по схеме FBS, шт.",
    "Доступно к продаже по схеме realFBS, шт.",
    "Зарезервировано на моих складах, шт",
    "Текущая цена с учетом скидки, ₽",
    "Цена до скидки (перечеркнутая цена), ₽",
    "Цена Premium, ₽",
    "Размер НДС, %",
    "Ошибки",
    "Предупреждения",
    "Кабинет",
]


def sync() -> int:
    """Fetch OZON report for both cabinets and write to Google Sheet.

    Returns number of rows written.
    """
    logger.info("=== sync_ozon: start ===")

    gc = get_client(GOOGLE_SA_FILE)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    # 1. Read "Все товары" sheet to get SKUs split by cabinet
    skus_by_cabinet = _get_skus_from_all_products(spreadsheet)

    all_data = []
    for cabinet in ALL_CABINETS:
        skus = skus_by_cabinet.get(cabinet.name, [])
        if not skus:
            logger.info("[%s] No SKUs found, skipping", cabinet.name)
            continue

        logger.info("[%s] Processing %d SKUs", cabinet.name, len(skus))

        ozon = OzonClient(
            client_id=cabinet.ozon_client_id,
            api_key=cabinet.ozon_api_key,
            cabinet_name=cabinet.name,
        )
        try:
            rows = ozon.get_stocks_and_prices_report(skus)
            if rows:
                # Skip header row (first row), add cabinet name to each data row
                for row in rows[1:]:
                    row.append(cabinet.name)
                    all_data.append(row)
                logger.info("[%s] Got %d data rows", cabinet.name, len(rows) - 1)
        finally:
            ozon.close()

    if not all_data:
        logger.warning("No data from OZON API")
        return 0

    # 2. Ensure all rows have 30 columns
    normalized = []
    for row in all_data:
        if len(row) >= 30:
            normalized.append(row[:30])
        else:
            # Pad with empty strings
            normalized.append(row + [""] * (30 - len(row)))

    # 3. Convert numeric columns to actual numbers
    # Indices (0-based): 1=Product ID, 2=SKU, 5=Контент-рейтинг, 9=Отзывы, 10=Рейтинг,
    # 16=Объем, 17=Вес, 18-22=Остатки, 23-25=Цены, 26=НДС
    numeric_indices = {1, 2, 5, 9, 10, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26}
    for row in normalized:
        for idx in numeric_indices:
            if idx < len(row):
                row[idx] = to_number(row[idx])

    # 4. Write to Google Sheet
    date_str, time_str = get_moscow_datetime()
    sheet_name = get_sheet_name(SHEET_NAME)
    ws = get_or_create_worksheet(spreadsheet, sheet_name)

    row_count = clear_and_write(
        worksheet=ws,
        headers=HEADERS,
        data=normalized,
        meta_cells=[
            (1, 1, f"Обновлено: {date_str} {time_str}"),
        ],
        header_row=2,
        data_start_row=3,
    )

    # Checkbox for refresh
    set_checkbox(ws, "C1")

    logger.info("=== sync_ozon: done (%d rows) ===", row_count)
    return row_count


def _get_skus_from_all_products(spreadsheet) -> dict[str, list[int]]:
    """Read 'Все товары' sheet and split FBO OZON SKU IDs by cabinet.

    Returns dict: {'ИП': [sku1, ...], 'ООО': [sku2, ...]}
    """
    result: dict[str, list[int]] = {"ИП": [], "ООО": []}

    try:
        ws = spreadsheet.worksheet("Все товары")
    except Exception:
        # Try test mode name
        try:
            ws = spreadsheet.worksheet(get_sheet_name("Все товары"))
        except Exception:
            logger.error("Sheet 'Все товары' not found")
            return result

    headers = ws.row_values(1)

    # Find column indices
    sku_col = None
    cabinet_col = None
    for i, h in enumerate(headers):
        h_stripped = str(h).strip()
        if h_stripped == "FBO OZON SKU ID":
            sku_col = i
        elif h_stripped == "Импортер":
            cabinet_col = i

    if sku_col is None or cabinet_col is None:
        logger.error("Required columns not found in 'Все товары' (sku=%s, cabinet=%s)", sku_col, cabinet_col)
        return result

    # Read all data
    all_values = ws.get_all_values()
    for row in all_values[1:]:  # Skip header
        if len(row) <= max(sku_col, cabinet_col):
            continue

        sku_str = str(row[sku_col]).strip()
        cabinet_str = str(row[cabinet_col]).strip()

        if not sku_str or not sku_str.isdigit():
            continue

        sku = int(sku_str)

        if "ИП" in cabinet_str or "Медведева" in cabinet_str:
            result["ИП"].append(sku)
        elif "ООО" in cabinet_str or "Вуки" in cabinet_str:
            result["ООО"].append(sku)

    logger.info("SKUs from 'Все товары': ИП=%d, ООО=%d", len(result["ИП"]), len(result["ООО"]))
    return result
