"""Коллектор выкупов и размерного распределения."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.finance import get_wb_buyouts_returns_by_artikul
from shared.data_layer.article import get_wb_fin_data_by_barcode


def collect_buyouts(start_date: str, end_date: str) -> dict:
    """Собирает данные по выкупам (WB). OZON buyout недоступен."""
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

    return {"buyouts": result}


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
