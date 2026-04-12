from __future__ import annotations
from collections import defaultdict
from services.wb_localization.wb_localization_mappings import (
    WAREHOUSE_TO_FD,
    OBLAST_TO_FD,
)


def calculate_sku_localization(orders: list[dict]) -> dict[int, float]:
    """
    Calculate per-SKU localization % from WB orders.

    An order is "local" if the warehouse's federal district matches
    the delivery oblast's federal district.

    Returns: {nm_id: localization_pct}
    """
    sku_local: dict[int, int] = defaultdict(int)
    sku_total: dict[int, int] = defaultdict(int)

    for order in orders:
        nm_id = order.get("nmId", 0)
        if not nm_id:
            continue

        wh_name = order.get("warehouseName", "")
        oblast = order.get("oblastOkrugName", "")

        wh_fd = WAREHOUSE_TO_FD.get(wh_name, "")
        delivery_fd = OBLAST_TO_FD.get(oblast, "")

        if not wh_fd or not delivery_fd:
            continue

        sku_total[nm_id] += 1
        if wh_fd == delivery_fd:
            sku_local[nm_id] += 1

    result = {}
    for nm_id, total in sku_total.items():
        if total > 0:
            result[nm_id] = round(sku_local[nm_id] / total * 100, 2)
    return result
