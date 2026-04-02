"""Traffic and funnel data collector: WB ad traffic + organic funnel + SEO."""
from shared.data_layer.traffic import get_wb_traffic_by_model
from shared.data_layer.funnel_seo import get_wb_article_funnel
from scripts.monthly_plan.utils import tuples_to_dicts, safe_float

TRAFFIC_COLS = [
    "period", "model", "ad_views", "ad_clicks", "ad_spend",
    "ad_to_cart", "ad_orders", "ctr", "cpc",
]
FUNNEL_COLS = [
    "model", "rank", "artikul", "opens", "cart", "orders",
    "buyouts", "cr_open_cart", "cr_cart_order", "cro", "crp",
    "revenue_spp", "margin", "orders_fin", "avg_check", "drr",
]


def collect_traffic(current_start: str, prev_start: str, current_end: str) -> dict:
    """Collect traffic, funnel and SEO data (WB only).

    Note: OZON traffic data not available. content_analysis has ~20% gap vs PowerBI.
    """
    # Ad traffic by model
    traffic_raw = get_wb_traffic_by_model(current_start, prev_start, current_end)
    traffic = tuples_to_dicts(traffic_raw, TRAFFIC_COLS)

    traffic_current = [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in t.items()}
        for t in traffic if t["period"] == "current"
    ]
    traffic_prev = [
        {k: safe_float(v) if k not in ("period", "model") else v for k, v in t.items()}
        for t in traffic if t["period"] == "previous"
    ]

    # Organic funnel (top articles per model)
    funnel_raw = get_wb_article_funnel(current_start, current_end, top_n=10)
    funnel = [
        {k: safe_float(v) if k not in ("model", "artikul") else v for k, v in row.items()}
        for row in tuples_to_dicts(funnel_raw, FUNNEL_COLS)
    ]

    return {
        "traffic": {
            "by_model_current": traffic_current,
            "by_model_previous": traffic_prev,
            "funnel": funnel,
            "limitations": [
                "WB only - OZON organic traffic not available",
                "~20% gap with PowerBI - use as trend indicator only",
            ],
        }
    }
