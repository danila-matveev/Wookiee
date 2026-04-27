"""Wildberries Statistics API v5 — reportDetailByPeriod paginator."""
from __future__ import annotations

import logging
import time
from datetime import date

import httpx

logger = logging.getLogger(__name__)

WB_REPORT_URL = (
    "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
)
PAGE_LIMIT = 50000
RATE_LIMIT_SLEEP = 62
MAX_RETRIES = 5


def fetch_report(api_key: str, cabinet_name: str,
                 date_from: date, date_to: date) -> list[dict]:
    """Paginate reportDetailByPeriod for [date_from, date_to] inclusive."""
    logger.info("[%s] Fetching %s → %s", cabinet_name, date_from, date_to)
    all_rows: list[dict] = []
    rrd_id = 0
    page = 0
    with httpx.Client(timeout=300.0) as client:
        while True:
            page += 1
            params = {
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
                "limit": PAGE_LIMIT,
                "rrdid": rrd_id,
            }
            data = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = client.get(
                        WB_REPORT_URL, params=params,
                        headers={"Authorization": api_key},
                    )
                    if resp.status_code == 429:
                        logger.warning("[%s] 429, sleep %ss",
                                       cabinet_name, RATE_LIMIT_SLEEP)
                        time.sleep(RATE_LIMIT_SLEEP)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as e:
                    wait = 15 * attempt
                    logger.warning(
                        "[%s] page %d attempt %d: %s (retry in %ss)",
                        cabinet_name, page, attempt, e, wait,
                    )
                    time.sleep(wait)
            if data is None:
                logger.error("[%s] page %d failed after retries", cabinet_name, page)
                break
            if not data:
                break
            all_rows.extend(data)
            rrd_id = data[-1].get("rrd_id", 0)
            logger.info("[%s] page %d: %d rows (total=%d)",
                        cabinet_name, page, len(data), len(all_rows))
            if len(data) < PAGE_LIMIT:
                break
            time.sleep(RATE_LIMIT_SLEEP)
    logger.info("[%s] total: %d rows", cabinet_name, len(all_rows))
    return all_rows
