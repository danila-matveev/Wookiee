from __future__ import annotations
import logging
import time
import httpx
from services.logistics_audit.models.report_row import ReportRow

logger = logging.getLogger(__name__)

BASE_URL = "https://statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod"
RATE_LIMIT_SEC = 62  # 1 req/min with buffer


def parse_report_rows(raw_data: list[dict]) -> tuple[list[ReportRow], int]:
    """Parse raw API JSON into ReportRow list. Returns (rows, last_rrd_id)."""
    if not raw_data:
        return [], 0
    rows = [ReportRow.from_api(d) for d in raw_data]
    last_rrd_id = raw_data[-1].get("rrd_id", 0)
    return rows, last_rrd_id


def fetch_report(
    api_key: str,
    date_from: str,
    date_to: str,
    timeout: float = 120.0,
) -> list[ReportRow]:
    """
    Fetch all pages of reportDetailByPeriod v5.
    Paginates by rrd_id until empty response.
    """
    all_rows: list[ReportRow] = []
    rrd_id = 0
    page = 0

    with httpx.Client(timeout=timeout) as client:
        while True:
            page += 1
            logger.info(f"Fetching report page {page}, rrd_id={rrd_id}")
            resp = client.get(
                BASE_URL,
                params={
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "limit": 100000,
                    "rrdid": rrd_id,
                },
                headers={"Authorization": api_key},
            )

            if resp.status_code == 429:
                logger.warning("Rate limited, sleeping 60s")
                time.sleep(60)
                continue

            resp.raise_for_status()
            data = resp.json()

            if not data:
                logger.info(f"Report complete: {len(all_rows)} total rows")
                break

            rows, rrd_id = parse_report_rows(data)
            all_rows.extend(rows)
            logger.info(f"Page {page}: {len(rows)} rows, rrd_id={rrd_id}")

            if len(data) < 100000:
                break

            time.sleep(RATE_LIMIT_SEC)

    return all_rows
