from __future__ import annotations
import logging
import httpx

logger = logging.getLogger(__name__)

ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru/api"


def fetch_measurement_penalties(
    api_key: str, date_to: str, timeout: float = 30.0,
) -> list[dict]:
    """Fetch measurement penalties. date_to in RFC3339: '2026-03-25T23:59:59Z'."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/analytics/v1/measurement-penalties",
            params={"dateTo": date_to, "limit": 1000},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def fetch_deductions(
    api_key: str, date_to: str, timeout: float = 30.0,
) -> list[dict]:
    """Fetch deductions (substitutions, incorrect items)."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/analytics/v1/deductions",
            params={"dateTo": date_to, "limit": 1000, "sort": "dtBonus", "order": "desc"},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])


def fetch_antifraud(api_key: str, timeout: float = 30.0) -> list[dict]:
    """Fetch antifraud details."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{ANALYTICS_BASE}/v1/analytics/antifraud-details",
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
