from __future__ import annotations
import logging
import time
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains"


def fetch_warehouse_remains(api_key: str, timeout: float = 120.0) -> dict[int, float]:
    """
    Fetch warehouse remains with WB-measured volumes.
    Async pattern: create task → poll → download.
    Returns dict nm_id → volume (liters).
    """
    with httpx.Client(timeout=timeout) as client:
        # Step 1: Create task
        resp = client.get(
            BASE_URL,
            params={"groupByNm": "true"},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("data", {}).get("taskId")
        if not task_id:
            logger.error("No taskId in response")
            return {}

        logger.info(f"Warehouse remains task created: {task_id}")
        time.sleep(10)

        # Step 2: Poll status
        for attempt in range(100):
            resp = client.get(
                f"{BASE_URL}/tasks/{task_id}/status",
                headers={"Authorization": api_key},
            )
            resp.raise_for_status()
            status = resp.json().get("data", {}).get("status")
            if status == "done":
                break
            logger.info(f"Poll {attempt}: status={status}")
            time.sleep(15)
        else:
            logger.error("Timeout waiting for warehouse_remains")
            return {}

        time.sleep(10)

        # Step 3: Download
        resp = client.get(
            f"{BASE_URL}/tasks/{task_id}/download",
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        items = resp.json()

        nm_volumes: dict[int, float] = {}
        for item in items:
            nm_id = item.get("nmId", 0)
            vol = item.get("volume", 0)
            if nm_id and vol:
                nm_volumes[nm_id] = vol

        logger.info(f"Got {len(nm_volumes)} items with volumes")
        return nm_volumes
