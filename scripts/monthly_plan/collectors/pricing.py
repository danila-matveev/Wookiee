"""Price elasticity data collector: daily article-level for 3 months."""
from shared.data_layer.pricing_article import (
    get_wb_price_margin_daily_by_article,
    get_ozon_price_margin_daily_by_article,
)
from scripts.monthly_plan.utils import model_from_article


def collect_pricing(elasticity_start: str, current_end: str) -> dict:
    """Collect pricing data for elasticity analysis.

    Returns dict with by_article list and summary by model.
    """
    wb_data = get_wb_price_margin_daily_by_article(elasticity_start, current_end)
    ozon_data = get_ozon_price_margin_daily_by_article(elasticity_start, current_end)

    # Group by article, compute data availability
    articles = {}
    for row in wb_data:
        art = row["article"]
        if art not in articles:
            articles[art] = {
                "article": art,
                "model": row["model"] or model_from_article(art),
                "channel": "wb",
                "days_with_data": 0,
                "days_with_sales": 0,
                "price_min": None,
                "price_max": None,
                "daily_data": [],
            }
        entry = articles[art]
        entry["days_with_data"] += 1
        if (row.get("sales_count") or 0) > 0:
            entry["days_with_sales"] += 1
        price = row.get("price_per_unit")
        if price and price > 0:
            if entry["price_min"] is None or price < entry["price_min"]:
                entry["price_min"] = price
            if entry["price_max"] is None or price > entry["price_max"]:
                entry["price_max"] = price
        entry["daily_data"].append(row)

    for row in ozon_data:
        art = f"ozon:{row['article']}"
        if art not in articles:
            articles[art] = {
                "article": row["article"],
                "model": row["model"] or model_from_article(row["article"]),
                "channel": "ozon",
                "days_with_data": 0,
                "days_with_sales": 0,
                "price_min": None,
                "price_max": None,
                "daily_data": [],
            }
        entry = articles[art]
        entry["days_with_data"] += 1
        if (row.get("sales_count") or 0) > 0:
            entry["days_with_sales"] += 1
        price = row.get("price_per_unit")
        if price and price > 0:
            if entry["price_min"] is None or price < entry["price_min"]:
                entry["price_min"] = price
            if entry["price_max"] is None or price > entry["price_max"]:
                entry["price_max"] = price
        entry["daily_data"].append(row)

    # Compute price variation flag per article
    by_article = []
    for art_data in articles.values():
        has_variation = (
            art_data["price_min"] is not None
            and art_data["price_max"] is not None
            and art_data["price_max"] > art_data["price_min"] * 1.05
        )
        by_article.append({
            "article": art_data["article"],
            "model": art_data["model"],
            "channel": art_data["channel"],
            "days_with_data": art_data["days_with_data"],
            "days_with_sales": art_data["days_with_sales"],
            "price_variation": has_variation,
            "price_min": art_data["price_min"],
            "price_max": art_data["price_max"],
            "daily_data": art_data["daily_data"],
        })

    return {"pricing": {"by_article": by_article}}
