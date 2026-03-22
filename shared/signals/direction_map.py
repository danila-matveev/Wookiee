"""Maps signal types to valid action categories for Validator."""

from __future__ import annotations

DIRECTION_MAP: dict[str, list[str]] = {
    # Margin signals
    "margin_lags_orders": ["reallocate_budget", "optimize_keywords", "review_pricing"],
    "margin_pct_drop": ["review_pricing", "reduce_costs", "review_assortment"],
    "cogs_anomaly": ["check_supplier", "review_pricing"],

    # Funnel signals
    "sales_lag_expected": ["monitor", "no_action"],
    "sales_lag_problem": ["check_returns", "check_quality", "review_description"],
    "ctr_drop": ["update_photos", "review_pricing", "enter_promotion"],
    "cart_to_order_drop": ["review_pricing", "check_sizes", "review_description"],
    "cro_improvement": ["monitor", "scale_up"],
    "buyout_drop": ["check_quality", "review_description", "check_sizing"],

    # Advertising signals
    "adv_overspend": ["reduce_budget", "optimize_keywords", "pause_campaign"],
    "adv_underspend": ["increase_budget", "expand_keywords"],
    "romi_critical": ["pause_campaign", "optimize_keywords", "reduce_budget"],
    "cac_exceeds_profit": ["pause_campaign", "reduce_budget", "optimize_keywords"],
    "keyword_drain": ["add_negative_keyword", "reduce_bid"],
    "organic_declining": ["check_positions", "increase_budget", "optimize_seo"],
    "ad_no_organic_growth": ["review_card", "optimize_seo", "check_relevance"],

    # Price signals
    "spp_shift_up": ["raise_price", "monitor"],
    "spp_shift_down": ["lower_price", "monitor"],
    "price_signal": ["monitor", "review_pricing"],
    "price_up_rank_risk": ["monitor", "increase_budget"],

    # Turnover / ABC signals
    "low_roi_article": ["withdraw", "reduce_price", "liquidate"],
    "high_roi_opportunity": ["scale_up", "increase_budget", "increase_stock"],
    "big_inefficient": ["review_pricing", "reduce_budget"],
    "status_mismatch": ["return_to_sale", "review_status"],

    # Logistics
    "logistics_overweight": ["optimize_localization", "reduce_returns"],
}


def is_valid_direction(signal_type: str, action_category: str) -> bool:
    """Check if action_category is valid for the given signal_type."""
    valid_actions = DIRECTION_MAP.get(signal_type)
    if valid_actions is None:
        return True  # unknown signal type — allow anything
    return action_category in valid_actions
