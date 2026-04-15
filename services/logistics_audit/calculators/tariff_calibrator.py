from __future__ import annotations
import statistics


def calibrate_base_tariff(rows: list[dict]) -> float | None:
    """
    Reverse-calculate base tariff * KTR from logistics rows with volume ≤ 1L.

    For ≤1L items: delivery_rub = base * dlv_prc * KTR
    So: base * KTR = delivery_rub / dlv_prc

    Returns median(delivery_rub / dlv_prc) across all valid ≤1L rows,
    or None if no valid rows exist.
    """
    bases = []
    for r in rows:
        vol = r.get("volume", 0)
        dlv = r.get("dlv_prc", 0)
        delivery = r.get("delivery_rub", 0)
        if 0 < vol <= 1 and dlv > 0 and delivery > 0:
            bases.append(delivery / dlv)
    if not bases:
        return None
    return statistics.median(bases)
