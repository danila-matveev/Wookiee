from __future__ import annotations
import logging
import time
import httpx

logger = logging.getLogger(__name__)

CARDS_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"


def parse_cards_dimensions(cards: list[dict]) -> dict[int, dict]:
    """Extract nm_id → {width, height, length, volume} from card list."""
    result = {}
    for card in cards:
        nm_id = card.get("nmID", 0)
        dims = card.get("dimensions", {})
        w = dims.get("width", 0)
        h = dims.get("height", 0)
        l = dims.get("length", 0)
        volume = round(w * h * l / 1000, 3)  # cm³ → liters
        result[nm_id] = {"width": w, "height": h, "length": l, "volume": volume}
    return result


def fetch_all_cards(api_key: str, timeout: float = 30.0) -> dict[int, dict]:
    """Fetch all content cards with dimensions. Cursor-based pagination."""
    all_dims: dict[int, dict] = {}
    cursor = {"limit": 100, "updatedAt": None, "nmID": None}

    with httpx.Client(timeout=timeout) as client:
        while True:
            body: dict = {
                "settings": {
                    "cursor": {"limit": cursor["limit"]},
                    "filter": {"withPhoto": -1},
                },
            }
            if cursor["updatedAt"]:
                body["settings"]["cursor"]["updatedAt"] = cursor["updatedAt"]
                body["settings"]["cursor"]["nmID"] = cursor["nmID"]

            resp = client.post(
                CARDS_URL,
                json=body,
                headers={"Authorization": api_key},
            )

            if resp.status_code == 429:
                time.sleep(5)
                continue

            resp.raise_for_status()
            data = resp.json()
            cards = data.get("cards", [])
            if not cards:
                break

            dims = parse_cards_dimensions(cards)
            all_dims.update(dims)
            logger.info(f"Fetched {len(cards)} cards, total {len(all_dims)}")

            cur = data.get("cursor", {})
            cursor["updatedAt"] = cur.get("updatedAt")
            cursor["nmID"] = cur.get("nmID")

            if len(cards) < 100:
                break
            time.sleep(0.5)

    return all_dims
