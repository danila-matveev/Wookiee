"""Inventory data collector: FBO stocks, MoySklad, turnover, risk assessment."""
from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_model,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
)
from scripts.monthly_plan.utils import model_from_article

# Risk thresholds (days of stock)
DEFICIT_DAYS = 14
OK_MAX_DAYS = 60
OVERSTOCK_DAYS = 90
DEAD_STOCK_DAYS = 250


def _assess_risk(turnover_days: float) -> str:
    """Assess inventory risk based on days of stock."""
    if turnover_days < DEFICIT_DAYS:
        return "DEFICIT"
    elif turnover_days <= OK_MAX_DAYS:
        return "OK"
    elif turnover_days <= OVERSTOCK_DAYS:
        return "WARNING"
    elif turnover_days <= DEAD_STOCK_DAYS:
        return "OVERSTOCK"
    else:
        return "DEAD_STOCK"


def collect_inventory(
    stock_start: str,
    stock_end: str,
    turnover_start: str,
    turnover_end: str,
) -> dict:
    """Collect inventory data: stocks, turnover, risk assessment.

    Args:
        stock_start: start of stock window (last week of month)
        stock_end: end of stock window (= current_month_end)
        turnover_start: start of turnover period (= current_month_start)
        turnover_end: end of turnover period (= current_month_end)
    """
    # Raw stock data (article-level)
    wb_stocks = get_wb_avg_stock(stock_start, stock_end)
    ozon_stocks = get_ozon_avg_stock(stock_start, stock_end)

    # MoySklad (model-level)
    ms_stocks = get_moysklad_stock_by_model()

    # Turnover (model-level, includes daily sales and days)
    wb_turnover = get_wb_turnover_by_model(turnover_start, turnover_end)
    ozon_turnover = get_ozon_turnover_by_model(turnover_start, turnover_end)

    # Aggregate WB stocks by model
    wb_by_model = {}
    for article, stock_val in wb_stocks.items():
        model = model_from_article(article)
        wb_by_model[model] = wb_by_model.get(model, 0) + (stock_val or 0)

    # Aggregate OZON stocks by model
    ozon_by_model = {}
    for article, stock_val in ozon_stocks.items():
        model = model_from_article(article)
        ozon_by_model[model] = ozon_by_model.get(model, 0) + (stock_val or 0)

    # Build unified model inventory with risks
    all_models = set(wb_by_model) | set(ozon_by_model) | set(wb_turnover) | set(ozon_turnover)

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
            "wb_fbo_stock": wb_by_model.get(model, 0),
            "ozon_fbo_stock": ozon_by_model.get(model, 0),
            "moysklad_stock": ms.get("total", 0) if ms else 0,
            "moysklad_transit": ms.get("stock_transit", 0) if ms else 0,
            "wb_daily_sales": wb_turn.get("daily_sales", 0),
            "ozon_daily_sales": ozon_turn.get("daily_sales", 0),
            "wb_turnover_days": round(wb_days, 1),
            "ozon_turnover_days": round(ozon_days, 1),
            "wb_risk": _assess_risk(wb_days),
            "ozon_risk": _assess_risk(ozon_days),
        }
        inventory_models.append(entry)

        # Collect risks for triage
        if entry["wb_risk"] in ("DEFICIT", "OVERSTOCK", "DEAD_STOCK"):
            risks.append({
                "model": model, "channel": "wb",
                "risk": entry["wb_risk"], "days": wb_days,
            })
        if entry["ozon_risk"] in ("DEFICIT", "OVERSTOCK", "DEAD_STOCK"):
            risks.append({
                "model": model, "channel": "ozon",
                "risk": entry["ozon_risk"], "days": ozon_days,
            })

    return {
        "inventory": {
            "by_model": inventory_models,
            "risks": risks,
        }
    }
