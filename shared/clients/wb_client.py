from __future__ import annotations

"""Wildberries API client."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)


class WBClient:
    """Client for Wildberries APIs (Statistics, Prices, Feedbacks)."""

    ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"
    STATISTICS_BASE = "https://statistics-api.wildberries.ru"
    PRICES_BASE = "https://discounts-prices-api.wildberries.ru"
    FEEDBACKS_BASE = "https://feedbacks-api.wildberries.ru"

    def __init__(self, api_key: str, cabinet_name: str):
        self.cabinet_name = cabinet_name
        self.client = httpx.Client(
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def close(self):
        self.client.close()

    # ---- Warehouse Remains (async report pattern) ----

    def get_warehouse_remains(self) -> list[dict]:
        """Full flow: create task -> poll -> sleep -> download.

        Returns list of product dicts, each with 'warehouses' array.
        """
        task_id = self._create_remains_task()
        if not task_id:
            return []

        logger.info("[%s] Report task created: %s", self.cabinet_name, task_id)

        # Wait for report to be ready
        time.sleep(10)

        for attempt in range(100):
            time.sleep(15)
            logger.info(
                "[%s] Polling report %s (attempt %d)...",
                self.cabinet_name,
                task_id,
                attempt + 1,
            )

            status = self._check_remains_status(task_id)
            if status == "done":
                logger.info("[%s] Report ready, waiting 60s before download...", self.cabinet_name)
                time.sleep(60)
                data = self._download_remains(task_id)
                logger.info("[%s] Downloaded %d items", self.cabinet_name, len(data))
                return data

        logger.error("[%s] Report timeout after 100 attempts", self.cabinet_name)
        return []

    def _create_remains_task(self) -> str | None:
        """POST to create warehouse remains report. Returns taskId."""
        url = (
            f"{self.ANALYTICS_BASE}/api/v1/warehouse_remains"
            "?groupByBarcode=true&groupByBrand=true&groupBySubject=true"
            "&groupBySa=true&groupByNm=true&groupBySize=true"
        )
        resp = self._request("GET", url)
        if resp and resp.get("data", {}).get("taskId"):
            return resp["data"]["taskId"]
        return None

    def _check_remains_status(self, task_id: str) -> str:
        """Check report status. Returns 'done', 'processing', etc."""
        url = f"{self.ANALYTICS_BASE}/api/v1/warehouse_remains/tasks/{task_id}/status"
        resp = self._request("GET", url)
        if resp:
            return resp.get("data", {}).get("status", "unknown")
        return "error"

    def _download_remains(self, task_id: str) -> list[dict]:
        """Download completed report. Returns list of product dicts."""
        url = f"{self.ANALYTICS_BASE}/api/v1/warehouse_remains/tasks/{task_id}/download"
        resp = self._request("GET", url)
        if isinstance(resp, list):
            return resp
        return []

    # ---- Prices (paginated) ----

    def get_prices(self) -> list[dict]:
        """Fetch all prices with pagination (limit=1000).

        Returns list of dicts with keys: nmID, vendorCode, discount, sizes.
        """
        all_items = []
        offset = 0
        limit = 1000

        while True:
            url = f"{self.PRICES_BASE}/api/v2/list/goods/filter?limit={limit}&offset={offset}"
            resp = self._request("GET", url)

            if not resp or not resp.get("data", {}).get("listGoods"):
                break

            items = resp["data"]["listGoods"]
            all_items.extend(items)
            logger.info("[%s] Prices batch: %d items (offset=%d)", self.cabinet_name, len(items), offset)

            if len(items) < limit:
                break

            offset += limit
            time.sleep(0.5)

        logger.info("[%s] Total prices: %d", self.cabinet_name, len(all_items))
        return all_items

    # ---- Feedbacks ----

    def get_all_feedbacks(self) -> list[dict]:
        """Fetch all feedbacks (answered + unanswered) with pagination.

        Returns list of feedback dicts.
        """
        feedbacks = []
        feedbacks.extend(self._fetch_feedbacks_paged(is_answered=True))
        feedbacks.extend(self._fetch_feedbacks_paged(is_answered=False))
        logger.info("[%s] Total feedbacks: %d", self.cabinet_name, len(feedbacks))
        return feedbacks

    def _fetch_feedbacks_paged(self, is_answered: bool) -> list[dict]:
        """Fetch feedbacks with skip-based pagination (take=5000)."""
        result = []
        skip = 0
        take = 5000

        while True:
            url = (
                f"{self.FEEDBACKS_BASE}/api/v1/feedbacks"
                f"?isAnswered={'true' if is_answered else 'false'}"
                f"&take={take}&skip={skip}"
            )
            resp = self._request("GET", url)

            if not resp or not resp.get("data", {}).get("feedbacks"):
                break

            batch = resp["data"]["feedbacks"]
            result.extend(batch)

            if len(batch) < take:
                break

            skip += take
            time.sleep(0.1)

        return result

    # ---- Questions ----

    def get_all_questions(self) -> list[dict]:
        """Fetch all questions (answered + unanswered) with pagination.

        Returns list of question dicts.
        """
        questions = []
        questions.extend(self._fetch_questions_paged(is_answered=True))
        questions.extend(self._fetch_questions_paged(is_answered=False))
        logger.info("[%s] Total questions: %d", self.cabinet_name, len(questions))
        return questions

    def _fetch_questions_paged(self, is_answered: bool) -> list[dict]:
        """Fetch questions with skip-based pagination (take=5000)."""
        result = []
        skip = 0
        take = 5000

        while True:
            url = (
                f"{self.FEEDBACKS_BASE}/api/v1/questions"
                f"?isAnswered={'true' if is_answered else 'false'}"
                f"&take={take}&skip={skip}"
            )
            resp = self._request("GET", url)

            if not resp or not resp.get("data", {}).get("questions"):
                break

            batch = resp["data"]["questions"]
            result.extend(batch)

            if len(batch) < take:
                break

            skip += take
            time.sleep(0.1)

        return result

    # ---- Seller Chats ----

    def get_seller_chats(self, date_from: str | None = None) -> list[dict]:
        """Fetch seller chats from WB API with pagination.

        Args:
            date_from: ISO date string to filter chats from (e.g. "2026-01-01").
                       If None, fetches all available chats.

        Returns:
            List of chat dicts with messages.
        """
        all_chats: list[dict] = []
        offset = 0
        limit = 1000

        while True:
            url = f"{self.FEEDBACKS_BASE}/api/v1/seller/chats?offset={offset}&limit={limit}"
            if date_from:
                url += f"&dateFrom={date_from}"

            resp = self._request("GET", url)

            if not resp or not resp.get("chats"):
                break

            chats = resp["chats"]
            all_chats.extend(chats)
            logger.info(
                "[%s] Fetched %d chats (total: %d)",
                self.cabinet_name, len(chats), len(all_chats),
            )

            if len(chats) < limit:
                break

            offset += limit
            time.sleep(0.35)

        logger.info("[%s] Total seller chats fetched: %d", self.cabinet_name, len(all_chats))
        return all_chats

    # ---- Answer feedbacks / questions ----

    def answer_feedback(self, feedback_id: str, text: str) -> bool:
        """Respond to a feedback (review). PATCH /api/v1/feedbacks."""
        url = f"{self.FEEDBACKS_BASE}/api/v1/feedbacks"
        resp = self._request("PATCH", url, json={"id": feedback_id, "text": text})
        if resp is not None:
            logger.info("[%s] Answered feedback %s", self.cabinet_name, feedback_id)
            return True
        return False

    def answer_question(self, question_id: str, text: str) -> bool:
        """Respond to a question. PATCH /api/v1/questions."""
        url = f"{self.FEEDBACKS_BASE}/api/v1/questions"
        resp = self._request("PATCH", url, json={"id": question_id, "text": text})
        if resp is not None:
            logger.info("[%s] Answered question %s", self.cabinet_name, question_id)
            return True
        return False

    # ---- Supplier Orders (Statistics API) ----

    def get_supplier_orders(self, date_from: str, flag: int = 0) -> list[dict]:
        """Fetch orders from Statistics API with pagination.

        Each order includes warehouseName, oblast, supplierArticle,
        techSize, nmId, isCancel — used for localization index calculation.

        Args:
            date_from: ISO datetime, e.g. "2026-01-15T00:00:00"
            flag: 0 = all orders since date, 1 = only updates

        Returns:
            List of order dicts.
        """
        all_orders: list[dict] = []
        current_date_from = date_from

        while True:
            url = (
                f"{self.STATISTICS_BASE}/api/v1/supplier/orders"
                f"?dateFrom={current_date_from}&flag={flag}"
            )
            resp = self._request("GET", url)

            if not resp or not isinstance(resp, list):
                break

            all_orders.extend(resp)
            logger.info(
                "[%s] Orders batch: %d items (from %s)",
                self.cabinet_name, len(resp), current_date_from[:10],
            )

            # Pagination: if exactly 60000 rows, there may be more
            if len(resp) < 60000:
                break

            last_date = resp[-1].get("lastChangeDate", "")
            if not last_date or last_date == current_date_from:
                break
            current_date_from = last_date
            time.sleep(60)  # Rate limit

        logger.info("[%s] Total orders: %d", self.cabinet_name, len(all_orders))
        return all_orders

    # ---- Promotions (Seller API) ----

    PROMOTIONS_BASE = "https://dp-calendar-api.wildberries.ru"

    def get_promotions_list(self, days_ahead: int = 60) -> list[dict]:
        """GET /api/v1/calendar/promotions — список доступных акций.

        Required params: allPromo, startDateTime, endDateTime.
        Returns list of promotions with id, name, startDateTime, endDateTime, type.
        """
        from datetime import datetime, timedelta

        url = f"{self.PROMOTIONS_BASE}/api/v1/calendar/promotions"
        now = datetime.utcnow()
        params = {
            "allPromo": "true",
            "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": (now + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = self._request("GET", url, params=params)
        if resp and isinstance(resp, dict):
            return resp.get("data", {}).get("promotions", [])
        if isinstance(resp, list):
            return resp
        return []

    # ---- Common request handler ----

    def _request(self, method: str, url: str, retries: int = 3, **kwargs) -> dict | list | None:
        """Make HTTP request with retry on 429."""
        for attempt in range(retries):
            try:
                resp = self.client.request(method, url, **kwargs)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 401:
                    logger.error("[%s] 401 Unauthorized: %s", self.cabinet_name, url)
                    raise PermissionError(f"WB API 401 for {self.cabinet_name}")

                if resp.status_code == 429:
                    logger.warning("[%s] 429 Rate limited, waiting 60s...", self.cabinet_name)
                    time.sleep(60)
                    continue

                logger.error(
                    "[%s] HTTP %d: %s", self.cabinet_name, resp.status_code, resp.text[:200]
                )

            except httpx.RequestError as e:
                logger.error("[%s] Request error: %s", self.cabinet_name, e)
                if attempt < retries - 1:
                    time.sleep(5)

        return None
