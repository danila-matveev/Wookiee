from __future__ import annotations

"""MPStats API client for Wildberries market analytics."""

import logging
import time
from typing import Union

import httpx

logger = logging.getLogger(__name__)


class MPStatsClient:
    """Client for MPStats WB analytics API.

    Auth via X-Mpstats-TOKEN header.
    Rate-limit handling: retry on 429 with 30s * attempt backoff.
    """

    BASE_URL = "https://mpstats.io/api/wb"

    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(
            headers={
                "X-Mpstats-TOKEN": token,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def close(self):
        self.client.close()

    # ---- Category & Brand analytics ----

    def get_category_trends(self, path: str, d1: str, d2: str) -> dict:
        """Get category trends for a given category path.

        Args:
            path: Category path (e.g. "shoes").
            d1: Start date (YYYY-MM-DD).
            d2: End date (YYYY-MM-DD).

        Returns:
            Trend data dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/get/category"
        params = {"path": path, "d1": d1, "d2": d2}
        result = self._request("GET", url, params=params)
        return result if isinstance(result, dict) else {}

    def get_brand_trends(self, path: str, d1: str, d2: str) -> dict:
        """Get brand trends for a given category path.

        Args:
            path: Category path.
            d1: Start date (YYYY-MM-DD).
            d2: End date (YYYY-MM-DD).

        Returns:
            Brand data dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/get/brand"
        params = {"path": path, "d1": d1, "d2": d2}
        result = self._request("GET", url, params=params)
        return result if isinstance(result, dict) else {}

    # ---- Item-level analytics ----

    def get_item_sales(self, sku: int, d1: str, d2: str) -> dict:
        """Get sales history for a specific SKU.

        Args:
            sku: Wildberries nmID.
            d1: Start date (YYYY-MM-DD).
            d2: End date (YYYY-MM-DD).

        Returns:
            Sales data dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/get/item/{sku}/sales"
        params = {"d1": d1, "d2": d2}
        result = self._request("GET", url, params=params)
        return result if isinstance(result, dict) else {}

    def get_item_info(self, sku: int) -> dict:
        """Get item info for a specific SKU.

        Args:
            sku: Wildberries nmID.

        Returns:
            Item info dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/get/item/{sku}"
        result = self._request("GET", url)
        return result if isinstance(result, dict) else {}

    def get_item_similar(self, sku: int) -> dict:
        """Get similar items for a specific SKU.

        Args:
            sku: Wildberries nmID.

        Returns:
            Similar items dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/get/item/{sku}/similar"
        result = self._request("GET", url)
        return result if isinstance(result, dict) else {}

    # ---- Brand items (paginated) ----

    def get_brand_items(self, path: str, d1: str, d2: str, start_row: int = 0, end_row: int = 500) -> dict:
        """POST /api/wb/get/brand — get items of a brand with pagination.

        Returns list of items with revenue, sales, price, etc.
        """
        url = f"{self.BASE_URL}/get/brand"
        result = self._request("POST", url, json={
            "startRow": start_row,
            "endRow": end_row,
            "path": path,
            "d1": d1,
            "d2": d2,
        })
        return result if isinstance(result, dict) else {"data": []}

    def get_category_items(self, path: str, d1: str, d2: str, start_row: int = 0, end_row: int = 500) -> dict:
        """POST /api/wb/get/category — get items in a category with pagination.

        Returns list of items with revenue, sales, price, first_date, etc.
        """
        url = f"{self.BASE_URL}/get/category"
        result = self._request("POST", url, json={
            "startRow": start_row,
            "endRow": end_row,
            "path": path,
            "d1": d1,
            "d2": d2,
        })
        return result if isinstance(result, dict) else {"data": []}

    def get_category_brands(self, path: str, d1: str, d2: str) -> dict:
        """GET /api/wb/get/category/brands — brands in a category with revenue."""
        url = f"{self.BASE_URL}/get/category/brands"
        params = {"path": path, "d1": d1, "d2": d2}
        result = self._request("GET", url, params=params)
        return result if isinstance(result, dict) else {"data": []}

    # ---- Search ----

    def search_brands(self, query: str) -> dict:
        """Search brands by query string.

        Args:
            query: Search query.

        Returns:
            Search results dict, or empty dict on failure.
        """
        url = f"{self.BASE_URL}/search/brands"
        params = {"query": query}
        result = self._request("GET", url, params=params)
        return result if isinstance(result, dict) else {}

    # ---- Common request handler ----

    def _request(
        self,
        method: str,
        url: str,
        retries: int = 3,
        **kwargs,
    ) -> Union[dict, list, None]:
        """Make HTTP request with retry on 429 rate limit.

        429 backoff: 30s * attempt number.
        401: log error, return None immediately.
        """
        for attempt in range(1, retries + 1):
            try:
                resp = self.client.request(method, url, **kwargs)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 401:
                    logger.error("MPStats 401 Unauthorized: %s", url)
                    return None

                if resp.status_code == 429:
                    wait = 30 * attempt
                    logger.warning(
                        "MPStats 429 rate limited, waiting %ds (attempt %d/%d)...",
                        wait,
                        attempt,
                        retries,
                    )
                    time.sleep(wait)
                    continue

                logger.error(
                    "MPStats HTTP %d: %s — %s",
                    resp.status_code,
                    url,
                    resp.text[:200],
                )

            except httpx.RequestError as e:
                logger.error("MPStats request error: %s", e)
                if attempt < retries:
                    time.sleep(5)

        return None
