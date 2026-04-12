"""Коллектор выкупов и размерного распределения."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.finance import get_wb_buyouts_returns_by_artikul
from shared.data_layer.article import get_wb_fin_data_by_barcode


def collect_buyouts(start_date: str, end_date: str, ozon_finance: dict | None = None) -> dict:
    """Собирает данные по выкупам (WB) + аппроксимацию OZON из finance."""
    wb_data = get_wb_buyouts_returns_by_artikul(start_date, end_date)
    result: dict[str, dict] = {}

    for row in wb_data:
        # row = (model, artikul, orders_count, buyout_count, return_count)
        article = row[1].lower() if row[1] else ""
        if not article:
            continue

        orders = row[2] or 0
        buyouts = row[3] or 0
        returns = row[4] or 0
        buyout_pct = round(buyouts / orders * 100, 1) if orders > 0 else 0.0

        result[article] = {
            "orders": orders,
            "buyouts": buyouts,
            "returns": returns,
            "buyout_pct": buyout_pct,
        }

    # Merge OZON approximation if finance data provided
    if ozon_finance:
        ozon_approx = approximate_ozon_buyout(ozon_finance)
        ozon_data = ozon_approx["ozon_buyouts"]
        for article, ozon_info in ozon_data.items():
            if article in result:
                # WB data is primary, add OZON buyout as extra field
                result[article]["ozon_buyout_pct"] = ozon_info["buyout_pct"]
            else:
                result[article] = ozon_info

    return {"buyouts": result}


def approximate_ozon_buyout(ozon_finance: dict[str, dict]) -> dict[str, dict]:
    """Аппроксимация выкупа OZON: sales_count / orders_count.

    Args:
        ozon_finance: Dict from finance collector — {article: {orders_count_30d, sales_count_30d, ...}}

    Returns:
        {"ozon_buyouts": {article: {"buyout_pct": float, "orders": int, "sales": int, "approximate": True}}}
    """
    result: dict[str, dict] = {}
    for article, data in ozon_finance.items():
        orders = data.get("orders_count_30d", 0) or 0
        sales = data.get("sales_count_30d", 0) or 0
        if orders > 0:
            buyout_pct = round(sales / orders * 100, 1)
            result[article] = {
                "orders": int(orders),
                "sales": int(sales),
                "buyout_pct": buyout_pct,
                "approximate": True,
            }
    return {"ozon_buyouts": result}


def collect_size_data(start_date: str, end_date: str) -> dict:
    """Собирает распределение продаж по размерам (из barcode-level данных WB)."""
    wb_barcodes = get_wb_fin_data_by_barcode(start_date, end_date)
    result: dict[str, dict] = defaultdict(dict)

    for row in wb_barcodes:
        article = (row.get("article") or "").lower()
        size = row.get("ts_name", "")
        sales = row.get("sales_count", 0) or 0

        if article and size:
            result[article][size] = result[article].get(size, 0) + sales

    return {"sizes": dict(result)}
