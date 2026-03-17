from __future__ import annotations

"""OZON Seller API client (report-based)."""

import csv
import io
import logging
import time

import httpx

logger = logging.getLogger(__name__)


class OzonClient:
    """Client for OZON Seller API."""

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self, client_id: str, api_key: str, cabinet_name: str):
        self.cabinet_name = cabinet_name
        self.client = httpx.Client(
            headers={
                "Client-Id": client_id,
                "Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def close(self):
        self.client.close()

    def get_stocks_and_prices_report(self, skus: list[int]) -> list[list[str]]:
        """Full flow: create report -> poll -> download CSV -> parse.

        Args:
            skus: List of FBO OZON SKU IDs.

        Returns:
            List of rows (each row is a list of string values), including header row.
        """
        if not skus:
            return []

        all_rows = []
        headers_row = None

        # OZON limits report to 1000 SKUs per request
        for batch_start in range(0, len(skus), 1000):
            batch = skus[batch_start : batch_start + 1000]
            logger.info(
                "[%s] Creating report for %d SKUs (batch %d)...",
                self.cabinet_name,
                len(batch),
                batch_start // 1000 + 1,
            )

            report_code = self._create_report(batch)
            if not report_code:
                logger.error("[%s] Failed to create report", self.cabinet_name)
                continue

            # Poll for completion
            file_url = None
            for attempt in range(12):
                time.sleep(5)
                file_url = self._check_report(report_code)
                if file_url:
                    break
                logger.info(
                    "[%s] Polling report %s (attempt %d)...",
                    self.cabinet_name,
                    report_code,
                    attempt + 1,
                )

            if not file_url:
                logger.error("[%s] Report timeout: %s", self.cabinet_name, report_code)
                continue

            rows = self._download_and_parse_csv(file_url)
            if rows:
                if headers_row is None and rows:
                    headers_row = rows[0]
                # Skip header row in subsequent batches
                data_rows = rows[1:] if headers_row else rows
                all_rows.extend(data_rows)

        if headers_row:
            return [headers_row] + all_rows
        return all_rows

    def _create_report(self, skus: list[int]) -> str | None:
        """POST /v1/report/products/create -> report code."""
        url = f"{self.BASE_URL}/v1/report/products/create"
        payload = {
            "sku": skus,
            "language": "DEFAULT",
            "visibility": "ALL",
        }
        try:
            resp = self.client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("code")
            logger.error("[%s] Create report HTTP %d: %s", self.cabinet_name, resp.status_code, resp.text[:200])
        except httpx.RequestError as e:
            logger.error("[%s] Create report error: %s", self.cabinet_name, e)
        return None

    def _check_report(self, code: str) -> str | None:
        """POST /v1/report/info -> file URL if ready, else None."""
        url = f"{self.BASE_URL}/v1/report/info"
        try:
            resp = self.client.post(url, json={"code": code})
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result", {})
                if result.get("status") == "success":
                    return result.get("file")
            return None
        except httpx.RequestError as e:
            logger.error("[%s] Check report error: %s", self.cabinet_name, e)
            return None

    # ---- Reviews ----

    def get_all_reviews(self) -> list[dict]:
        """Fetch all reviews with cursor-based pagination.

        POST /v1/review/list — returns reviews with product info, rating, text.
        """
        all_reviews = []
        cursor = ""

        while True:
            payload: dict = {"limit": 100, "sort_direction": "DESC"}
            if cursor:
                payload["cursor"] = cursor

            url = f"{self.BASE_URL}/v1/review/list"
            try:
                resp = self.client.post(url, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    reviews = data.get("reviews", [])
                    all_reviews.extend(reviews)

                    cursor = data.get("cursor", "")
                    has_next = data.get("has_next", False)

                    logger.info(
                        "[%s] Ozon reviews batch: %d (total: %d)",
                        self.cabinet_name, len(reviews), len(all_reviews),
                    )

                    if not has_next or not reviews:
                        break

                    time.sleep(0.2)
                elif resp.status_code == 429:
                    logger.warning("[%s] 429 Rate limited, waiting 60s...", self.cabinet_name)
                    time.sleep(60)
                    continue
                else:
                    logger.error(
                        "[%s] Ozon reviews HTTP %d: %s",
                        self.cabinet_name, resp.status_code, resp.text[:200],
                    )
                    break

            except httpx.RequestError as e:
                logger.error("[%s] Ozon reviews error: %s", self.cabinet_name, e)
                break

        logger.info("[%s] Total Ozon reviews: %d", self.cabinet_name, len(all_reviews))
        return all_reviews

    # ---- Promotions ----

    def get_promotions(self) -> list[dict]:
        """POST /v1/actions — список доступных акций.

        Returns list of promotions with id, title, date_start, date_end.
        """
        url = f"{self.BASE_URL}/v1/actions"
        try:
            resp = self.client.post(url, json={})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", [])
            logger.error("[%s] GET promotions HTTP %d", self.cabinet_name, resp.status_code)
        except httpx.RequestError as e:
            logger.error("[%s] GET promotions error: %s", self.cabinet_name, e)
        return []

    def get_promotion_candidates(self, action_id: int, offset: int = 0, limit: int = 100) -> list[dict]:
        """POST /v1/actions/candidates — товары, которые можно добавить в акцию.

        Returns list of product candidates with action_price, max_action_price, stock.
        """
        url = f"{self.BASE_URL}/v1/actions/candidates"
        payload = {"action_id": action_id, "offset": offset, "limit": limit}
        try:
            resp = self.client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("products", [])
            logger.error("[%s] GET promo candidates HTTP %d", self.cabinet_name, resp.status_code)
        except httpx.RequestError as e:
            logger.error("[%s] GET promo candidates error: %s", self.cabinet_name, e)
        return []

    def get_promotion_products(self, action_id: int, offset: int = 0, limit: int = 100) -> list[dict]:
        """POST /v1/actions/products — товары, уже участвующие в акции.

        Returns list of products currently in the promotion.
        """
        url = f"{self.BASE_URL}/v1/actions/products"
        payload = {"action_id": action_id, "offset": offset, "limit": limit}
        try:
            resp = self.client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("products", [])
            logger.error("[%s] GET promo products HTTP %d", self.cabinet_name, resp.status_code)
        except httpx.RequestError as e:
            logger.error("[%s] GET promo products error: %s", self.cabinet_name, e)
        return []

    # ---- CSV Reports ----

    def _download_and_parse_csv(self, url: str) -> list[list[str]]:
        """Download CSV from URL, parse semicolon-delimited with BOM handling.

        Returns list of rows (first row is headers).
        """
        try:
            resp = httpx.get(url, timeout=60.0)
            if resp.status_code != 200:
                logger.error("[%s] CSV download HTTP %d", self.cabinet_name, resp.status_code)
                return []

            # Decode and strip BOM
            text = resp.content.decode("utf-8-sig")

            # Parse semicolon-delimited CSV
            reader = csv.reader(io.StringIO(text), delimiter=";")
            rows = []
            for row in reader:
                # Strip apostrophe prefix from values (OZON quirk: '100 means 100)
                cleaned = [v.lstrip("'") if v.startswith("'") else v for v in row]
                rows.append(cleaned)

            logger.info("[%s] Parsed %d rows from CSV", self.cabinet_name, len(rows))
            return rows

        except Exception as e:
            logger.error("[%s] CSV parse error: %s", self.cabinet_name, e)
            return []
