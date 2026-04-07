# scripts/familia_eval/calculator.py
"""Calculator: scenario matrix, breakeven, delta vs MP."""

from scripts.familia_eval.config import CONFIG


def calculate_scenarios(articles: list) -> list:
    """For each article, compute P&L at each discount level.

    Returns articles list enriched with 'scenarios' and 'breakeven_discount'.
    """
    results = []
    for art in articles:
        cogs = art["cogs_per_unit"]
        rrc = art["rrc"]
        stock = art["stock_moysklad"]

        if rrc <= 0:
            continue

        scenarios = []
        for discount in CONFIG["discount_range"]:
            price = round(rrc * (1 - discount))
            costs = _calc_costs(cogs, price)
            margin = round(price - costs, 2)
            margin_pct = round(margin / price * 100, 1) if price > 0 else 0

            profit_familia = round(stock * margin)
            profit_mp = _estimate_mp_profit(art)
            delta = round(profit_familia - profit_mp)

            scenarios.append({
                "discount": discount,
                "price": price,
                "costs_total": round(costs, 2),
                "margin": margin,
                "margin_pct": margin_pct,
                "profit_familia_total": profit_familia,
                "profit_mp_total": profit_mp,
                "delta": delta,
            })

        breakeven = _calc_breakeven(cogs, rrc)

        results.append({
            **art,
            "scenarios": scenarios,
            "breakeven_discount": round(breakeven, 4),
        })

    return results


def _calc_costs(cogs: float, familia_price: float) -> float:
    """Total cost per unit for Familia channel."""
    logistics = CONFIG["logistics_to_rc"]
    packaging = CONFIG["packaging_cost"]
    loss = familia_price * CONFIG["loss_reserve_pct"]
    freeze = familia_price * (CONFIG["annual_rate"] / 365) * CONFIG["payment_delay_days"]
    return cogs + logistics + packaging + loss + freeze


def _calc_breakeven(cogs: float, rrc: float) -> float:
    """Max discount where margin >= 0.

    Solve: rrc*(1-d) - cogs - logistics - packaging - rrc*(1-d)*loss - rrc*(1-d)*freeze_rate = 0
    Let P = rrc*(1-d), fixed = cogs + logistics + packaging
    P - fixed - P*loss - P*freeze = 0
    P*(1 - loss - freeze) = fixed
    P = fixed / (1 - loss - freeze)
    d = 1 - P/rrc
    """
    if rrc <= 0:
        return 0.0
    fixed = cogs + CONFIG["logistics_to_rc"] + CONFIG["packaging_cost"]
    variable_rate = CONFIG["loss_reserve_pct"] + (CONFIG["annual_rate"] / 365) * CONFIG["payment_delay_days"]
    price_breakeven = fixed / (1 - variable_rate)
    return max(0.0, min(1.0, 1 - price_breakeven / rrc))


def _estimate_mp_profit(art: dict) -> float:
    """Estimate total profit if continuing to sell on MP.

    Simplified: stock * rrc * (1 - spp) * margin_pct / 100
    Minus: storage cost on MP warehouses (estimated from turnover).
    Note: own warehouse storage = 0 (fixed rent).
    """
    stock = art["stock_moysklad"]
    rrc = art["rrc"]
    spp = art.get("spp_pct", 0) / 100
    margin_pct = art["margin_pct_mp"] / 100
    daily_sales = max(art["daily_sales_mp"], 0.05)

    days_to_sell = stock / daily_sales
    revenue = stock * rrc * (1 - spp)
    gross_profit = revenue * margin_pct

    # Estimated MP storage cost (from WB FBO rates, ~5 руб/шт/день average)
    storage_cost_per_day = 5.0
    # Only count MP warehouse stock (assume ~30% of stock is on MP)
    mp_stock_share = 0.3
    storage_total = storage_cost_per_day * stock * mp_stock_share * days_to_sell

    return round(gross_profit - storage_total)
