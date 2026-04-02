"""Advertising data collector: ROAS, DRR, external breakdown."""
from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.advertising import get_wb_external_ad_breakdown
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

MODEL_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]
EXTERNAL_COLS = [
    "period", "adv_internal", "adv_bloggers", "adv_vk",
    "adv_creators", "adv_total",
]


def collect_advertising(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect advertising data: per-model ROAS/DRR + external breakdown.

    Uses get_wb_by_model (not get_wb_model_ad_roi) to avoid fan-out bug.
    """
    wb_models = tuples_to_dicts(
        get_wb_by_model(current_start, prev_start, current_end),
        MODEL_COLS,
    )
    ozon_models = tuples_to_dicts(
        get_ozon_by_model(current_start, prev_start, current_end),
        MODEL_COLS,
    )

    # External ad breakdown (WB only)
    external_raw = get_wb_external_ad_breakdown(current_start, prev_start, current_end)
    external = tuples_to_dicts(external_raw, EXTERNAL_COLS)

    # Build per-model ad metrics
    by_model = []
    for row in wb_models:
        if row["period"] != "current":
            continue
        rev = safe_float(row["revenue_before_spp"]) or 0
        adv_int = safe_float(row["adv_internal"]) or 0
        adv_ext = safe_float(row["adv_external"]) or 0
        margin = safe_float(row["margin"]) or 0
        adv_total = adv_int + adv_ext

        # Break-even DRR = margin2 % (margin after external ads / revenue)
        margin2 = margin - adv_ext  # margin from get_wb_by_model is M-1
        margin2_pct = (margin2 / rev * 100) if rev > 0 else 0
        drr = (adv_total / rev * 100) if rev > 0 else 0
        drr_internal = (adv_int / rev * 100) if rev > 0 else 0
        drr_external = (adv_ext / rev * 100) if rev > 0 else 0
        roas = (rev / adv_total) if adv_total > 0 else None

        by_model.append({
            "model": row["model"],
            "channel": "wb",
            "revenue": rev,
            "adv_internal": adv_int,
            "adv_external": adv_ext,
            "adv_total": adv_total,
            "margin1": margin,
            "margin2": margin2,
            "margin2_pct": round(margin2_pct, 1),
            "drr_total": round(drr, 1),
            "drr_internal": round(drr_internal, 1),
            "drr_external": round(drr_external, 1),
            "break_even_drr": round(margin2_pct, 1),
            "roas": round(roas, 1) if roas else None,
            "is_ad_loss": drr > margin2_pct if rev > 0 else False,
        })

    for row in ozon_models:
        if row["period"] != "current":
            continue
        rev = safe_float(row["revenue_before_spp"]) or 0
        adv_int = safe_float(row["adv_internal"]) or 0
        margin = safe_float(row["margin"]) or 0
        drr = (adv_int / rev * 100) if rev > 0 else 0
        roas = (rev / adv_int) if adv_int > 0 else None

        by_model.append({
            "model": row["model"],
            "channel": "ozon",
            "revenue": rev,
            "adv_internal": adv_int,
            "adv_external": 0,  # OZON external not tracked
            "adv_total": adv_int,
            "margin1": margin,
            "margin2": margin,  # OZON M2 = M1
            "margin2_pct": round((margin / rev * 100) if rev > 0 else 0, 1),
            "drr_total": round(drr, 1),
            "drr_internal": round(drr, 1),
            "drr_external": 0,
            "break_even_drr": round((margin / rev * 100) if rev > 0 else 0, 1),
            "roas": round(roas, 1) if roas else None,
            "is_ad_loss": False,  # Can't determine without external ads
        })

    # External breakdown (current period)
    external_current = [e for e in external if e["period"] == "current"]

    return {
        "advertising": {
            "by_model": by_model,
            "external_breakdown": [
                {k: safe_float(v) if k != "period" else v for k, v in e.items()}
                for e in external_current
            ],
            "channels": ["МП_внутр", "блогеры", "ВК", "creators"],
        }
    }
