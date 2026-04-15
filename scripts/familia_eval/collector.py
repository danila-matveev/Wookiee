"""Collector: pulls MoySklad stock + DB pricing/finance/turnover data."""

import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.data_layer.inventory import (
    get_moysklad_stock_by_article,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
)
from shared.data_layer.pricing import (
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
)
from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.sku_mapping import get_artikuly_statuses

from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

WB_FINANCE_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]


def collect_all() -> dict:
    """Run all data collection in parallel. Returns raw data dict."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=CONFIG["lookback_days"])).strftime("%Y-%m-%d")
    prev_start = (datetime.now() - timedelta(days=CONFIG["lookback_days"] * 2)).strftime("%Y-%m-%d")

    tasks = {
        "ms_stock": lambda: get_moysklad_stock_by_article(),
        "statuses": lambda: get_artikuly_statuses(),
        "wb_pricing": lambda: get_wb_price_margin_by_model_period(start, end),
        "ozon_pricing": lambda: get_ozon_price_margin_by_model_period(start, end),
        "wb_turnover": lambda: get_wb_turnover_by_model(start, end),
        "ozon_turnover": lambda: get_ozon_turnover_by_model(start, end),
        "wb_finance": lambda: get_wb_by_model(start, prev_start, end),
        "ozon_finance": lambda: get_ozon_by_model(start, prev_start, end),
    }

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                log.error("Collector %s failed: %s", name, e)
                errors[name] = str(e)
                results[name] = {} if name not in ("wb_finance", "ozon_finance") else []

    articles = merge_article_data(
        ms_stock=results["ms_stock"],
        statuses=results["statuses"],
        status_filter=CONFIG["status_filter"],
        min_stock=CONFIG["min_stock_moysklad"],
        wb_pricing=results["wb_pricing"],
        ozon_pricing=results["ozon_pricing"],
        wb_turnover=results["wb_turnover"],
        ozon_turnover=results["ozon_turnover"],
        wb_finance=results["wb_finance"],
        ozon_finance=results["ozon_finance"],
        finance_cols=WB_FINANCE_COLS,
    )

    return {
        "articles": articles,
        "meta": {
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "period": f"{start} — {end}",
            "errors": errors,
        },
    }


def merge_article_data(
    ms_stock: dict,
    statuses: dict,
    status_filter: list,
    min_stock: int,
    wb_pricing: list,
    ozon_pricing: list,
    wb_turnover: dict,
    ozon_turnover: dict,
    wb_finance: list,
    ozon_finance: list,
    finance_cols: list,
) -> list:
    """Merge all data sources into a list of article dicts for Calculator."""
    # Build model-level lookups
    pricing_by_model = {}
    for row in wb_pricing:
        pricing_by_model[row["model"].lower()] = row
    for row in ozon_pricing:
        m = row["model"].lower()
        if m not in pricing_by_model:
            pricing_by_model[m] = row

    # Finance: extract COGS per unit by model
    cogs_by_model = {}
    for fin_data in (wb_finance, ozon_finance):
        for row in fin_data:
            if isinstance(row, (list, tuple)) and len(row) >= len(finance_cols):
                d = dict(zip(finance_cols, row))
            elif isinstance(row, dict):
                d = row
            else:
                continue
            if d.get("period") != "current":
                continue
            model = d.get("model", "").lower()
            sales = d.get("sales_count", 0) or 0
            cogs_total = d.get("cost_of_goods", 0) or 0
            if model and sales > 0:
                cogs_by_model[model] = cogs_total / sales

    # Turnover: merge WB + OZON (sum daily_sales, take min turnover)
    turnover_by_model = {}
    for src in (wb_turnover, ozon_turnover):
        for model, data in src.items():
            m = model.lower()
            if m not in turnover_by_model:
                turnover_by_model[m] = data
            else:
                existing = turnover_by_model[m]
                turnover_by_model[m] = {
                    "daily_sales": existing["daily_sales"] + data.get("daily_sales", 0),
                    "turnover_days": min(
                        existing.get("turnover_days", 999),
                        data.get("turnover_days", 999),
                    ),
                }

    # Build article list
    articles = []
    for article, stock_data in ms_stock.items():
        art_lower = article.lower()
        status = statuses.get(art_lower)
        if status not in status_filter:
            continue
        stock = stock_data.get("total", 0) or stock_data.get("stock_main", 0)
        if stock < min_stock:
            continue

        model = art_lower.split("/")[0] if "/" in art_lower else art_lower
        pricing = pricing_by_model.get(model, {})
        turnover = turnover_by_model.get(model, {})
        cogs = cogs_by_model.get(model, 0)

        articles.append({
            "article": art_lower,
            "model": model,
            "status": status,
            "stock_moysklad": stock,
            "cogs_per_unit": round(cogs, 2),
            "rrc": pricing.get("avg_price_per_unit", 0),
            "daily_sales_mp": turnover.get("daily_sales", 0),
            "turnover_days": turnover.get("turnover_days", 0),
            "margin_pct_mp": pricing.get("margin_pct", 0),
            "spp_pct": pricing.get("spp_pct", 0),
            "drr_pct": pricing.get("drr_pct", 0),
        })

    articles.sort(key=lambda x: x["turnover_days"], reverse=True)
    return articles
