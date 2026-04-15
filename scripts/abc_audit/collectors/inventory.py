"""Коллектор запасов: WB + OZON + МойСклад, оборачиваемость, ROI."""
from __future__ import annotations

from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_article,
)

MOQ = 500  # Минимальный заказ, шт (будет в Supabase позже)


def calc_turnover_metrics(
    stock_total: float,
    daily_sales: float,
    margin_pct: float = 0.0,
) -> dict:
    """Считает оборачиваемость, месяцы на MOQ, годовой ROI."""
    if daily_sales <= 0:
        return {
            "turnover_days": 999.0,
            "moq_months": 999.0,
            "roi_annual": 0.0,
        }

    turnover_days = round(stock_total / daily_sales, 1)
    moq_months = round(MOQ / (daily_sales * 30), 2)
    roi_annual = round(margin_pct * (365 / turnover_days), 1) if turnover_days > 0 else 0.0

    return {
        "turnover_days": turnover_days,
        "moq_months": moq_months,
        "roi_annual": roi_annual,
    }


def collect_inventory(start_date: str, end_date: str) -> dict:
    """Собирает стоки со всех складов."""
    wb_stocks = get_wb_avg_stock(start_date, end_date)
    ozon_stocks = get_ozon_avg_stock(start_date, end_date)
    ms_stocks = get_moysklad_stock_by_article()

    moysklad_stale = any(v.get("is_stale", False) for v in ms_stocks.values())

    all_articles = set(wb_stocks) | set(ozon_stocks) | set(ms_stocks)
    result: dict[str, dict] = {}

    for article in all_articles:
        s_wb = wb_stocks.get(article, 0.0)
        s_ozon = ozon_stocks.get(article, 0.0)
        ms_data = ms_stocks.get(article, {})
        s_ms = ms_data.get("total", 0) if isinstance(ms_data, dict) else 0

        result[article] = {
            "stock_wb": s_wb,
            "stock_ozon": s_ozon,
            "stock_moysklad": s_ms,
            "stock_total": s_wb + s_ozon + s_ms,
        }

    return {
        "inventory": result,
        "meta": {"moysklad_stale": moysklad_stale},
    }
