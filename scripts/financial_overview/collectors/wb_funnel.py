"""WB organic funnel collector — traffic, conversions, organic vs paid split."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer import (
    get_wb_traffic,
    get_wb_article_funnel,
    get_wb_organic_vs_paid_funnel,
)


def _prev_start(start: str, end: str) -> str:
    """Calculate previous period start for the comparison period's 'previous'."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    length = (e - s).days
    return (s - timedelta(days=length)).strftime("%Y-%m-%d")


def _extract_by_period(rows: list, period_label: str) -> list:
    """Filter rows where first column matches period_label."""
    return [r for r in rows if r and r[0] == period_label]


def _parse_content_traffic(rows: list) -> dict:
    """Parse content_results: (period, card_opens, add_to_cart, funnel_orders, buyouts)."""
    result = {"card_opens": 0, "add_to_cart": 0, "orders": 0, "buyouts": 0}
    for row in rows:
        if len(row) >= 5:
            result["card_opens"] += int(row[1] or 0)
            result["add_to_cart"] += int(row[2] or 0)
            result["orders"] += int(row[3] or 0)
            result["buyouts"] += int(row[4] or 0)
    return result


def _calc_conversions(data: dict) -> dict:
    """Calculate conversion rates from funnel data."""
    opens = data.get("card_opens", 0)
    cart = data.get("add_to_cart", 0)
    orders = data.get("orders", 0)
    buyouts = data.get("buyouts", 0)
    return {
        "cr_open_to_cart": round(cart / opens * 100, 2) if opens else 0,
        "cr_cart_to_order": round(orders / cart * 100, 2) if cart else 0,
        "cr_open_to_order": round(orders / opens * 100, 2) if opens else 0,
        "cr_order_to_buyout": round(buyouts / orders * 100, 2) if orders else 0,
    }


def _parse_article_funnel(rows: list) -> list[dict]:
    """Parse article funnel tuples into list of dicts.
    Columns: model, rank, artikul, opens, cart, orders, buyouts,
             cr_open_cart, cr_cart_order, cro, crp,
             revenue_spp, margin, orders_fin, avg_check, drr
    """
    result = []
    for r in rows:
        if len(r) >= 16:
            result.append({
                "model": r[0], "rank": r[1], "artikul": r[2],
                "opens": float(r[3] or 0), "cart": float(r[4] or 0),
                "orders": float(r[5] or 0), "buyouts": float(r[6] or 0),
                "cr_open_cart": float(r[7] or 0), "cr_cart_order": float(r[8] or 0),
                "revenue_spp": float(r[11] or 0), "margin": float(r[12] or 0),
                "avg_check": float(r[14] or 0), "drr": float(r[15] or 0),
            })
    return result


def _parse_organic_vs_paid(organic_rows: list, paid_rows: list) -> dict:
    """Parse organic and paid funnel results into structured dict.
    organic: (period, card_opens, add_to_cart, funnel_orders, buyouts,
              card_to_cart_pct, cart_to_order_pct, order_to_buyout_pct)
    paid: (period, ad_views, ad_clicks, ad_to_cart, ad_orders, ad_spend, ctr, cpc)
    """
    organic = {}
    for r in organic_rows:
        if len(r) >= 5:
            organic = {
                "card_opens": int(r[1] or 0), "add_to_cart": int(r[2] or 0),
                "orders": int(r[3] or 0), "buyouts": int(r[4] or 0),
            }
            if len(r) >= 8:
                organic["cr_open_cart"] = float(r[5] or 0)
                organic["cr_cart_order"] = float(r[6] or 0)
                organic["cr_order_buyout"] = float(r[7] or 0)
    paid = {}
    for r in paid_rows:
        if len(r) >= 8:
            paid = {
                "ad_views": int(r[1] or 0), "ad_clicks": int(r[2] or 0),
                "ad_to_cart": int(r[3] or 0), "ad_orders": int(r[4] or 0),
                "ad_spend": float(r[5] or 0), "ctr": float(r[6] or 0),
                "cpc": float(r[7] or 0),
            }
    return {"organic": organic, "paid": paid}


def collect_funnel(a_start: str, a_end: str, b_start: str, b_end: str) -> dict:
    """Collect WB organic funnel data for two periods."""

    prev_b = _prev_start(b_start, b_end)

    # Traffic funnel — returns (content_results, adv_results)
    content_a, adv_a = get_wb_traffic(a_start, b_start, a_end)
    content_b, adv_b = get_wb_traffic(b_start, prev_b, b_end)

    # Filter by 'current' period label (each call's "current" is the period we want)
    traffic_a = _parse_content_traffic(_extract_by_period(content_a, 'current'))
    traffic_b = _parse_content_traffic(_extract_by_period(content_b, 'current'))

    # Article funnel (top 10 models)
    funnel_a = get_wb_article_funnel(a_start, a_end, top_n=10)
    funnel_b = get_wb_article_funnel(b_start, b_end, top_n=10)

    # Organic vs paid split — returns (organic_results, paid_results)
    org_a, paid_a = get_wb_organic_vs_paid_funnel(a_start, b_start, a_end)
    org_b, paid_b = get_wb_organic_vs_paid_funnel(b_start, prev_b, b_end)

    return {
        "funnel": {
            "period_a": traffic_a,
            "period_b": traffic_b,
        },
        "conversions": {
            "period_a": _calc_conversions(traffic_a),
            "period_b": _calc_conversions(traffic_b),
        },
        "organic_vs_paid": {
            "period_a": _parse_organic_vs_paid(
                _extract_by_period(org_a, 'current'),
                _extract_by_period(paid_a, 'current'),
            ),
            "period_b": _parse_organic_vs_paid(
                _extract_by_period(org_b, 'current'),
                _extract_by_period(paid_b, 'current'),
            ),
        },
        "top_models": {
            "period_a": _parse_article_funnel(funnel_a),
            "period_b": _parse_article_funnel(funnel_b),
        },
    }
