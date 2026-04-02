"""P&L data collector: total brand + by model, WB + OZON."""
from shared.data_layer.finance import (
    get_wb_finance,
    get_ozon_finance,
    get_wb_by_model,
    get_ozon_by_model,
    get_wb_orders_by_model,
    get_ozon_orders_by_model,
)
from shared.data_layer.sku_mapping import get_model_statuses_mapped
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

# Column names matching finance.py query output
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


def _finance_to_dict(rows, columns, period_label):
    """Convert finance rows to dict, filtering by period label."""
    dicts = tuples_to_dicts(rows, columns)
    return [
        {k: safe_float(v) if k != "period" else v for k, v in d.items()}
        for d in dicts if d["period"] == period_label
    ]


def _model_rows_to_list(fin_rows, orders_rows, period_label):
    """Merge finance + orders rows by model for a given period."""
    fin = tuples_to_dicts(fin_rows, MODEL_COLS)
    ords = tuples_to_dicts(orders_rows, MODEL_ORDERS_COLS)

    # Index orders by model
    orders_map = {}
    for o in ords:
        if o["period"] == period_label:
            orders_map[o["model"]] = {
                "orders_count": safe_float(o["orders_count"]),
                "orders_rub": safe_float(o["orders_rub"]),
            }

    result = []
    for f in fin:
        if f["period"] != period_label:
            continue
        model = f["model"]
        entry = {k: safe_float(v) if k not in ("period", "model") else v for k, v in f.items()}
        entry.update(orders_map.get(model, {"orders_count": 0, "orders_rub": 0}))
        result.append(entry)

    return result


def collect_pnl(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect P&L data for total brand and by model.

    Returns dict with keys: pnl_total, pnl_models.
    """
    # Total P&L
    wb_fin, wb_orders = get_wb_finance(current_start, prev_start, current_end)
    ozon_fin, ozon_orders = get_ozon_finance(current_start, prev_start, current_end)

    # By model
    wb_by_model = get_wb_by_model(current_start, prev_start, current_end)
    ozon_by_model = get_ozon_by_model(current_start, prev_start, current_end)
    wb_orders_model = get_wb_orders_by_model(current_start, prev_start, current_end)
    ozon_orders_model = get_ozon_orders_by_model(current_start, prev_start, current_end)

    # Statuses
    statuses = get_model_statuses_mapped()

    # Build total
    pnl_total = {
        "current": {
            "wb": _finance_to_dict(wb_fin, WB_FINANCE_COLS, "current"),
            "wb_orders": _finance_to_dict(wb_orders, WB_ORDERS_COLS, "current"),
            "ozon": _finance_to_dict(ozon_fin, OZON_FINANCE_COLS, "current"),
            "ozon_orders": _finance_to_dict(ozon_orders, OZON_ORDERS_COLS, "current"),
        },
        "previous": {
            "wb": _finance_to_dict(wb_fin, WB_FINANCE_COLS, "previous"),
            "wb_orders": _finance_to_dict(wb_orders, WB_ORDERS_COLS, "previous"),
            "ozon": _finance_to_dict(ozon_fin, OZON_FINANCE_COLS, "previous"),
            "ozon_orders": _finance_to_dict(ozon_orders, OZON_ORDERS_COLS, "previous"),
        },
    }

    # Build by model
    wb_models_current = _model_rows_to_list(wb_by_model, wb_orders_model, "current")
    wb_models_prev = _model_rows_to_list(wb_by_model, wb_orders_model, "previous")
    ozon_models_current = _model_rows_to_list(ozon_by_model, ozon_orders_model, "current")
    ozon_models_prev = _model_rows_to_list(ozon_by_model, ozon_orders_model, "previous")

    # Index by model for merging
    ozon_idx = {m["model"]: m for m in ozon_models_current}
    ozon_prev_idx = {m["model"]: m for m in ozon_models_prev}
    wb_prev_idx = {m["model"]: m for m in wb_models_prev}

    active, exiting = [], []
    for wb_m in wb_models_current:
        model_name = wb_m["model"]
        status = statuses.get(model_name, statuses.get(model_name.capitalize(), "Unknown"))
        entry = {
            "model": model_name,
            "status": status,
            "current": {
                "wb": wb_m,
                "ozon": ozon_idx.get(model_name, {}),
            },
            "previous": {
                "wb": wb_prev_idx.get(model_name, {}),
                "ozon": ozon_prev_idx.get(model_name, {}),
            },
        }
        if status in ("Выводим", "Архив"):
            exiting.append(entry)
        else:
            active.append(entry)

    # Add OZON-only models
    wb_model_names = {m["model"] for m in wb_models_current}
    for oz_m in ozon_models_current:
        if oz_m["model"] not in wb_model_names:
            model_name = oz_m["model"]
            status = statuses.get(model_name, "Unknown")
            entry = {
                "model": model_name,
                "status": status,
                "current": {"wb": {}, "ozon": oz_m},
                "previous": {"wb": {}, "ozon": ozon_prev_idx.get(model_name, {})},
            }
            if status in ("Выводим", "Архив"):
                exiting.append(entry)
            else:
                active.append(entry)

    pnl_models = {"active": active, "exiting": exiting}

    return {"pnl_total": pnl_total, "pnl_models": pnl_models}
