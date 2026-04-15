"""Finance data collector: WB + OZON totals, by-model, by-article, buyouts."""
from __future__ import annotations

from shared.data_layer.finance import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_by_model,
    get_ozon_by_model,
    get_wb_orders_by_model,
    get_ozon_orders_by_model,
    get_wb_buyouts_returns_by_model,
)
from shared.data_layer.article import get_wb_by_article, get_ozon_by_article
from scripts.analytics_report.utils import tuples_to_dicts, safe_float

# Column definitions matching data_layer query output
WB_FINANCE_COLS = [
    "period", "orders_count", "sales_count", "revenue_before_spp",
    "revenue_after_spp", "adv_internal", "adv_external", "cost_of_goods",
    "logistics", "storage", "commission", "spp_amount", "nds",
    "penalty", "retention", "deduction", "margin",
    "returns_revenue", "revenue_before_spp_gross",
]
WB_ORDERS_COLS = ["period", "orders_count", "orders_rub"]

OZON_FINANCE_COLS = [
    "period", "sales_count", "revenue_before_spp", "revenue_after_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
    "logistics", "storage", "commission", "spp_amount", "nds",
]
OZON_ORDERS_COLS = ["period", "orders_count", "orders_rub"]

MODEL_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]
MODEL_ORDERS_COLS = ["period", "model", "orders_count", "orders_rub"]

BUYOUT_COLS = ["period", "model", "orders_count", "buyout_count", "return_count"]


def _to_period_dict(rows, columns, period_label):
    """Convert rows to dicts, filter by period, cast numerics."""
    dicts = tuples_to_dicts(rows, columns)
    return [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in d.items()}
        for d in dicts if d["period"] == period_label
    ]


def collect_finance(start: str, prev_start: str, end: str, depth: str) -> dict:
    """Collect all finance data.

    Args:
        start: current period start (YYYY-MM-DD)
        prev_start: previous period start (YYYY-MM-DD)
        end: current period end exclusive (YYYY-MM-DD)
        depth: "daily", "weekly", or "monthly"

    Returns:
        {"finance": {...}} with wb/ozon totals, models, articles, buyouts.
    """
    # --- Totals ---
    wb_fin, wb_orders = get_wb_finance(start, prev_start, end)
    ozon_fin, ozon_orders = get_ozon_finance(start, prev_start, end)

    wb_total = {
        "current": _to_period_dict(wb_fin, WB_FINANCE_COLS, "current"),
        "current_orders": _to_period_dict(wb_orders, WB_ORDERS_COLS, "current"),
        "previous": _to_period_dict(wb_fin, WB_FINANCE_COLS, "previous"),
        "previous_orders": _to_period_dict(wb_orders, WB_ORDERS_COLS, "previous"),
    }
    ozon_total = {
        "current": _to_period_dict(ozon_fin, OZON_FINANCE_COLS, "current"),
        "current_orders": _to_period_dict(ozon_orders, OZON_ORDERS_COLS, "current"),
        "previous": _to_period_dict(ozon_fin, OZON_FINANCE_COLS, "previous"),
        "previous_orders": _to_period_dict(ozon_orders, OZON_ORDERS_COLS, "previous"),
    }

    # --- By model ---
    wb_models_raw = get_wb_by_model(start, prev_start, end)
    ozon_models_raw = get_ozon_by_model(start, prev_start, end)
    wb_orders_model = get_wb_orders_by_model(start, prev_start, end)
    ozon_orders_model = get_ozon_orders_by_model(start, prev_start, end)

    wb_models = {
        "current": _to_period_dict(wb_models_raw, MODEL_COLS, "current"),
        "current_orders": _to_period_dict(wb_orders_model, MODEL_ORDERS_COLS, "current"),
        "previous": _to_period_dict(wb_models_raw, MODEL_COLS, "previous"),
        "previous_orders": _to_period_dict(wb_orders_model, MODEL_ORDERS_COLS, "previous"),
    }
    ozon_models = {
        "current": _to_period_dict(ozon_models_raw, MODEL_COLS, "current"),
        "current_orders": _to_period_dict(ozon_orders_model, MODEL_ORDERS_COLS, "current"),
        "previous": _to_period_dict(ozon_models_raw, MODEL_COLS, "previous"),
        "previous_orders": _to_period_dict(ozon_orders_model, MODEL_ORDERS_COLS, "previous"),
    }

    # --- By article (only for week/month depth) ---
    wb_articles = []
    ozon_articles = []
    if depth in ("weekly", "monthly"):
        wb_articles = get_wb_by_article(start, end)
        ozon_articles = get_ozon_by_article(start, end)

    # --- Buyouts ---
    wb_buyouts_raw = get_wb_buyouts_returns_by_model(start, prev_start, end)
    wb_buyouts = {
        "current": _to_period_dict(wb_buyouts_raw, BUYOUT_COLS, "current"),
        "previous": _to_period_dict(wb_buyouts_raw, BUYOUT_COLS, "previous"),
    }

    return {
        "finance": {
            "wb_total": wb_total,
            "ozon_total": ozon_total,
            "wb_models": wb_models,
            "ozon_models": ozon_models,
            "wb_articles": wb_articles,
            "ozon_articles": ozon_articles,
            "wb_buyouts": wb_buyouts,
        }
    }
