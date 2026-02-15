from __future__ import annotations

"""МойСклад JSON API 1.2 client."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)


class MoySkladClient:
    """Client for МойСклад API."""

    BASE_URL = "https://api.moysklad.ru/api/remap/1.2"

    # Store IDs from GAS config
    STORE_MAIN = "4c51ead2-2731-11ef-0a80-07b100450c6a"
    STORE_ACCEPTANCE = "6281f079-8ae2-11ef-0a80-148c00124916"

    # Attribute names in the exact order from GAS CONFIG.attributesOrder (32 items)
    ATTRIBUTES_ORDER = [
        "Артикул Ozon",
        "Баркод",
        "Нуменклатура",
        "Модель",
        "Название для Этикетки",
        "Ozon >>",
        "Ozon Product ID",
        "FBO OZON SKU ID",
        "Размер",
        "Цвет",
        "О товаре >>>",
        "Продавец",
        "Фабрика",
        "Состав",
        "ТНВЭД",
        "SKU",
        "Сolor",
        "Color code",
        "Price",
        "Длина",
        "Ширина",
        "Высота",
        "Объем",
        "Кратность короба",
        "Импортер",
        "Адрес Импортера",
        "Статус WB",
        "Статус OZON",
        "Склейка на WB",
        "Категория",
        "Модель основа",
        "Коллекция",
    ]

    # Additional data column start (column 39 = AM in the sheet)
    ADDITIONAL_COLUMNS_START = 39
    ADDITIONAL_COLUMNS = [
        "Остатки в офисе",
        "Товары с приемкой",
        "Товары в пути",
        "Себестоимость",
    ]

    def __init__(self, token: str):
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept-Encoding": "gzip",
            },
            timeout=300.0,
        )

    def close(self):
        self.client.close()

    # ---- Assortment ----

    def fetch_assortment(self, moment: str = "", store_url: str = "") -> list[dict]:
        """Fetch paginated assortment from /entity/assortment.

        Args:
            moment: Optional stockMoment filter (ISO datetime).
            store_url: Optional store URL for stock filtering.

        Returns:
            List of product dicts.
        """
        all_rows = []
        offset = 0
        limit = 500

        for _ in range(20):  # Max 10000 items
            url = f"{self.BASE_URL}/entity/assortment?limit={limit}&offset={offset}"
            if moment:
                url += f"&filter=stockMoment={moment}"
            if store_url:
                url += f";stockStore={store_url}"

            data = self._get(url)
            if not data or "rows" not in data:
                break

            rows = data["rows"]
            all_rows.extend(rows)
            logger.info("Fetched assortment page: %d items (offset=%d)", len(rows), offset)

            if len(rows) < limit:
                break

            offset += limit
            time.sleep(0.5)

        return all_rows

    # ---- Stock by store ----

    def fetch_stock_by_store(self, store_id: str) -> list[dict]:
        """Fetch stock for a specific store from /report/stock/bystore."""
        all_rows = []
        offset = 0
        limit = 1000
        store_url = f"{self.BASE_URL}/entity/store/{store_id}"

        for _ in range(20):
            url = (
                f"{self.BASE_URL}/report/stock/bystore"
                f"?filter=store={store_url}"
                f"&limit={limit}&offset={offset}"
            )
            data = self._get(url)
            if not data or "rows" not in data:
                break

            rows = data["rows"]
            all_rows.extend(rows)

            if len(rows) < limit:
                break

            offset += limit
            time.sleep(0.3)

        return all_rows

    # ---- Stock all (for cost/sebstoimost) ----

    def fetch_stock_all(self) -> list[dict]:
        """Fetch /report/stock/all for cost data."""
        all_rows = []
        offset = 0
        limit = 1000

        for _ in range(20):
            url = f"{self.BASE_URL}/report/stock/all?limit={limit}&offset={offset}"
            data = self._get(url)
            if not data or "rows" not in data:
                break

            rows = data["rows"]
            all_rows.extend(rows)

            if len(rows) < limit:
                break

            offset += limit
            time.sleep(0.3)

        return all_rows

    # ---- Purchase orders ----

    # State ID for "Выполнен" (completed) — exclude these orders
    STATE_COMPLETED_HREF = (
        "https://api.moysklad.ru/api/remap/1.2/entity/purchaseorder"
        "/metadata/states/75199f67-2f9f-11ef-0a80-02fb00081527"
    )

    def fetch_purchase_orders(self) -> list[dict]:
        """Fetch active (non-completed) purchase orders (paginated)."""
        all_orders = []
        offset = 0
        limit = 100

        for _ in range(20):
            url = f"{self.BASE_URL}/entity/purchaseorder?limit={limit}&offset={offset}"
            data = self._get(url)
            if not data or "rows" not in data:
                break

            rows = data["rows"]
            all_orders.extend(rows)

            if len(rows) < limit:
                break
            offset += limit
            time.sleep(0.3)

        # Filter: GAS requires order.state to exist AND not be the completed state
        return [
            order for order in all_orders
            if order.get("state") and order["state"].get("meta", {}).get("href") != self.STATE_COMPLETED_HREF
        ]

    def fetch_order_positions(self, order_id: str) -> list[dict]:
        """Fetch positions (line items) for a purchase order (paginated)."""
        all_positions = []
        offset = 0
        limit = 1000

        for _ in range(10):
            url = (
                f"{self.BASE_URL}/entity/purchaseorder/{order_id}/positions"
                f"?limit={limit}&offset={offset}"
            )
            data = self._get(url)
            if not data or "rows" not in data:
                break

            rows = data["rows"]
            all_positions.extend(rows)

            if len(rows) < limit:
                break
            offset += limit
            time.sleep(0.3)

        return all_positions

    # ---- Helpers ----

    def extract_attributes(self, product: dict) -> list[str]:
        """Extract 32 attributes from product in the correct order.

        Returns list of 32 values (empty string if attribute not found).
        """
        attrs = product.get("attributes", [])
        attr_map = {}
        for attr in attrs:
            name = attr.get("name", "")
            value = attr.get("value", "")
            # Handle custom entity types (value is a dict with 'name')
            if isinstance(value, dict):
                value = value.get("name", "")
            attr_map[name] = str(value) if value else ""

        return [attr_map.get(name, "") for name in self.ATTRIBUTES_ORDER]

    def extract_barcodes(self, product: dict) -> tuple[str, str]:
        """Extract EAN13 and GTIN barcodes from product.

        Returns (ean13, gtin) tuple.
        """
        barcodes = product.get("barcodes", [])
        ean13 = ""
        gtin = ""
        if len(barcodes) > 1:
            ean13_obj = barcodes[1] if len(barcodes) > 1 else {}
            ean13 = ean13_obj.get("ean13", "") or ean13_obj.get("ean8", "")
        if len(barcodes) > 2:
            gtin = barcodes[2].get("gtin", "")
        return ean13, gtin

    def _get(self, url: str) -> dict | None:
        """Make GET request with basic error handling."""
        try:
            resp = self.client.get(url)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401:
                logger.error("MoySklad 401 Unauthorized")
                raise PermissionError("MoySklad API 401")
            logger.error("MoySklad HTTP %d: %s", resp.status_code, resp.text[:200])
        except httpx.RequestError as e:
            logger.error("MoySklad request error: %s", e)
        return None
