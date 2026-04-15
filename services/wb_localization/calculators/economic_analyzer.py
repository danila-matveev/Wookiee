"""Economic scenario analyzer for WB localization index.

Combines per-article ИЛ/ИРП analysis with actual logistics costs
from WB reportDetailByPeriod to produce 3 scenarios:
1. "Без контроля" — what if all articles drop to 40% localization
2. "Сейчас" — current state with actual costs
3. "Оптимизированный" — all articles at 80%+ localization
"""
from __future__ import annotations

import logging
from typing import Any

from services.wb_localization.irp_coefficients import get_ktr_krp

logger = logging.getLogger(__name__)

# Scenario constants
NO_CONTROL_LOC_PCT = 40.0  # worst-case localization %
OPTIMIZED_LOC_PCT = 80.0   # target localization %


def analyze_economics(
    il_irp: dict[str, Any],
    logistics_costs: dict[str, float],
    period_days: int = 30,
) -> dict[str, Any]:
    """Produce economic scenario analysis.

    Args:
        il_irp: Output from ``analyze_il_irp`` (keys: summary, articles).
        logistics_costs: ``{article_lower: total_delivery_rub}`` from WB API.
        period_days: Length of the observed period in days.

    Returns:
        Dict with scenarios, top_savings, and aggregate numbers.
    """
    articles = il_irp.get("articles", [])
    monthly_factor = 30 / period_days if period_days > 0 else 1.0

    # KTR/KRP for scenario extremes (precompute once)
    no_ctrl_ktr, no_ctrl_krp = get_ktr_krp(NO_CONTROL_LOC_PCT)
    opt_ktr, opt_krp = get_ktr_krp(OPTIMIZED_LOC_PCT)

    # Accumulators
    total_logistics_fact = 0.0
    total_logistics_base = 0.0
    total_irp_current = 0.0

    # Scenario sums
    no_ctrl_logistics = 0.0
    no_ctrl_irp = 0.0
    current_logistics = 0.0
    current_irp = 0.0
    opt_logistics = 0.0
    opt_irp = 0.0

    # Per-article savings for top_savings
    savings_list: list[dict[str, Any]] = []

    matched = 0
    skipped = 0

    for art in articles:
        article: str = art["article"]
        ktr: float = art["ktr"]
        krp_pct: float = art["krp_pct"]
        loc_pct: float = art["loc_pct"]
        wb_total: int = art["wb_total"]
        price: float = art.get("price", 0.0)
        irp_month: float = art.get("irp_per_month", 0.0)

        actual = logistics_costs.get(article)
        if actual is None:
            skipped += 1
            continue

        matched += 1
        actual = abs(actual)

        # Base cost (at КТР=1.0): reverse the КТР multiplier
        base_cost = actual / ktr if ktr > 0 else actual

        total_logistics_fact += actual
        total_logistics_base += base_cost
        total_irp_current += irp_month

        # Monthly extrapolation of actual logistics
        actual_monthly = actual * monthly_factor
        base_monthly = base_cost * monthly_factor
        irp_monthly = irp_month  # already monthly from il_irp

        # --- Scenario 1: No control (40% loc) ---
        sc1_logistics = base_cost * no_ctrl_ktr * monthly_factor
        sc1_irp = price * no_ctrl_krp / 100 * wb_total * monthly_factor if price > 0 else 0.0
        no_ctrl_logistics += sc1_logistics
        no_ctrl_irp += sc1_irp

        # --- Scenario 2: Current ---
        current_logistics += actual_monthly
        current_irp += irp_monthly

        # --- Scenario 3: Optimized (80% loc) ---
        if loc_pct >= OPTIMIZED_LOC_PCT:
            # Already at or above target — keep current КТР
            target_ktr = ktr
        else:
            target_ktr = opt_ktr
        sc3_logistics = base_cost * target_ktr * monthly_factor
        sc3_irp = 0.0  # All ≥ 60% → no КРП
        opt_logistics += sc3_logistics
        opt_irp += sc3_irp

        # Savings potential for this article
        savings = (actual_monthly + irp_monthly) - (sc3_logistics + sc3_irp)
        savings_list.append({
            "article": article,
            "current_loc_pct": loc_pct,
            "current_ktr": ktr,
            "current_krp_pct": krp_pct,
            "logistics_fact_monthly": round(actual_monthly),
            "irp_current_monthly": round(irp_monthly),
            "savings_if_80_monthly": round(savings),
        })

    if skipped > 0:
        logger.warning(
            "Экономический анализ: %d артикулов без данных по логистике (пропущены)",
            skipped,
        )

    # Current weighted-average ИЛ
    current_il = il_irp.get("summary", {}).get("overall_il", 1.0)

    # IL savings = how much less we pay vs ИЛ=1.0 baseline
    il_savings_rub = round((total_logistics_base - total_logistics_fact) * monthly_factor)

    # Scenario totals
    no_ctrl_total = no_ctrl_logistics + no_ctrl_irp
    current_total = current_logistics + current_irp
    opt_total = opt_logistics + opt_irp

    # Top-10 by savings potential (descending)
    savings_list.sort(key=lambda x: x["savings_if_80_monthly"], reverse=True)
    top_savings = savings_list[:10]

    return {
        "period_days": period_days,
        "matched_articles": matched,
        "skipped_articles": skipped,
        "total_logistics_fact": round(total_logistics_fact),
        "total_logistics_base": round(total_logistics_base),
        "total_irp_current": round(total_irp_current),
        "current_il": round(current_il, 2),
        "il_savings_rub": il_savings_rub,
        "scenarios": {
            "no_control": {
                "label": "Без контроля",
                "description": "Если бы не следили за индексом (все артикулы ~40% лок.)",
                "simulated_il": no_ctrl_ktr,
                "logistics_monthly": round(no_ctrl_logistics),
                "irp_monthly": round(no_ctrl_irp),
                "total_monthly": round(no_ctrl_total),
                "vs_current_monthly": round(no_ctrl_total - current_total),
            },
            "current": {
                "label": "Сейчас",
                "description": f"Ваш текущий ИЛ: {current_il:.2f}",
                "simulated_il": round(current_il, 2),
                "logistics_monthly": round(current_logistics),
                "irp_monthly": round(current_irp),
                "total_monthly": round(current_total),
                "vs_current_monthly": 0,
            },
            "optimized": {
                "label": "Оптимизированный",
                "description": "Все артикулы ≥ 80% локализации",
                "simulated_il": opt_ktr,
                "logistics_monthly": round(opt_logistics),
                "irp_monthly": round(opt_irp),
                "total_monthly": round(opt_total),
                "vs_current_monthly": round(opt_total - current_total),
            },
        },
        "top_savings": top_savings,
    }
