"""Inventory data collector: FBO stocks, MoySklad, turnover, risk assessment."""
from __future__ import annotations

from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_model,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
    get_wb_sales_trend_by_model,
    get_ozon_sales_trend_by_model,
)
from scripts.analytics_report.utils import model_from_article

# Risk thresholds (days of stock)
DEFICIT_DAYS = 14
OK_MAX_DAYS = 60
WARNING_MAX_DAYS = 90
OVERSTOCK_MAX_DAYS = 250


def _assess_risk(turnover_days: float) -> str:
    """Assess inventory risk based on days of stock."""
    if turnover_days < DEFICIT_DAYS:
        return "DEFICIT"
    elif turnover_days <= OK_MAX_DAYS:
        return "OK"
    elif turnover_days <= WARNING_MAX_DAYS:
        return "WARNING"
    elif turnover_days <= OVERSTOCK_MAX_DAYS:
        return "OVERSTOCK"
    else:
        return "DEAD_STOCK"


def _aggregate_stocks_by_model(stocks: dict) -> dict:
    """Aggregate article-level stock dict to model level."""
    by_model: dict[str, float] = {}
    for article, stock_val in stocks.items():
        model = model_from_article(article)
        by_model[model] = by_model.get(model, 0) + (stock_val or 0)
    return by_model


def collect_inventory(start: str, end: str) -> dict:
    """Collect inventory data: stocks, turnover, trends, risk assessment.

    Args:
        start: period start (YYYY-MM-DD)
        end: period end (YYYY-MM-DD)

    Returns:
        {"inventory": {...}} with by_model list and risks.
    """
    # Article-level stocks -> aggregate to model
    wb_stocks = _aggregate_stocks_by_model(get_wb_avg_stock(start, end))
    ozon_stocks = _aggregate_stocks_by_model(get_ozon_avg_stock(start, end))

    # Model-level data
    ms_stocks = get_moysklad_stock_by_model()
    wb_turnover = get_wb_turnover_by_model(start, end)
    ozon_turnover = get_ozon_turnover_by_model(start, end)
    wb_trend = get_wb_sales_trend_by_model(start, end)
    ozon_trend = get_ozon_sales_trend_by_model(start, end)

    # Build unified model inventory
    all_models = (
        set(wb_stocks) | set(ozon_stocks)
        | set(wb_turnover) | set(ozon_turnover)
    )

    inventory_models = []
    risks = []

    for model in sorted(all_models):
        wb_turn = wb_turnover.get(model, {})
        ozon_turn = ozon_turnover.get(model, {})
        ms = ms_stocks.get(model, {})

        wb_days = wb_turn.get("turnover_days", 0) or 0
        ozon_days = ozon_turn.get("turnover_days", 0) or 0

        entry = {
            "model": model,
            "wb_fbo_stock": wb_stocks.get(model, 0),
            "ozon_fbo_stock": ozon_stocks.get(model, 0),
            "moysklad_stock": ms.get("total", 0) if ms else 0,
            "moysklad_transit": ms.get("stock_transit", 0) if ms else 0,
            "wb_daily_sales": wb_turn.get("daily_sales", 0),
            "ozon_daily_sales": ozon_turn.get("daily_sales", 0),
            "wb_turnover_days": round(wb_days, 1),
            "ozon_turnover_days": round(ozon_days, 1),
            "wb_risk": _assess_risk(wb_days),
            "ozon_risk": _assess_risk(ozon_days),
            "wb_trend": wb_trend.get(model),
            "ozon_trend": ozon_trend.get(model),
        }
        inventory_models.append(entry)

        # Collect actionable risks
        for channel, risk, days in [
            ("wb", entry["wb_risk"], wb_days),
            ("ozon", entry["ozon_risk"], ozon_days),
        ]:
            if risk in ("DEFICIT", "OVERSTOCK", "DEAD_STOCK"):
                risks.append({
                    "model": model,
                    "channel": channel,
                    "risk": risk,
                    "days": days,
                })

    return {
        "inventory": {
            "by_model": inventory_models,
            "risks": risks,
        }
    }
