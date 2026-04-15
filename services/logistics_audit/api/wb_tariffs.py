from __future__ import annotations
import logging
import httpx
from services.logistics_audit.models.tariff_snapshot import TariffSnapshot

logger = logging.getLogger(__name__)

BOX_URL = "https://common-api.wildberries.ru/api/v1/tariffs/box"
PALLET_URL = "https://common-api.wildberries.ru/api/v1/tariffs/pallet"


def parse_tariff_response(raw: dict) -> dict[str, TariffSnapshot]:
    """Parse tariffs/box API response into dict keyed by warehouse name."""
    warehouses = raw.get("response", {}).get("data", {}).get("warehouseList", [])
    result = {}
    for wh in warehouses:
        snap = TariffSnapshot.from_api(wh)
        result[snap.warehouse_name] = snap
    return result


def fetch_tariffs_box(api_key: str, date: str, timeout: float = 30.0) -> dict[str, TariffSnapshot]:
    """Fetch box tariffs for a specific date."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            BOX_URL,
            params={"date": date},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return parse_tariff_response(resp.json())


def fetch_tariffs_pallet(api_key: str, date: str, timeout: float = 30.0) -> dict:
    """Fetch pallet tariffs for a specific date. Returns raw parsed JSON."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            PALLET_URL,
            params={"date": date},
            headers={"Authorization": api_key},
        )
        resp.raise_for_status()
        return resp.json()
