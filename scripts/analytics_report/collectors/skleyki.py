"""Склейки (card group) performance collector.

Aggregates WB article-level data by card groups (склейки) from Supabase.
Cross-model groups are flagged for ad attribution analysis.
"""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.sku_mapping import get_artikuly_full_info
from shared.data_layer.finance import get_wb_finance, get_wb_by_model
from shared.model_mapping import map_to_osnova


def collect_skleyki(finance_wb_articles: list[dict]) -> dict:
    """Build склейки performance from pre-collected WB article data.

    Args:
        finance_wb_articles: list of article dicts from finance collector
            (keys: article, revenue, margin, adv_internal, adv_external, orders_count, sales_count)

    Returns:
        {"skleyki": {"wb": [...]}} with per-group aggregates.
    """
    meta = get_artikuly_full_info()

    groups: dict[str, dict] = {}

    for art in finance_wb_articles:
        article = (art.get("article") or "").lower()
        info = meta.get(article, {})
        sk = info.get("skleyka_wb", "")
        if not sk:
            continue

        model = map_to_osnova(
            (info.get("model_osnova") or article.split("/")[0]).lower()
        )

        if sk not in groups:
            groups[sk] = {
                "skleyka": sk,
                "models": set(),
                "articles": [],
                "revenue": 0,
                "margin": 0,
                "adv_internal": 0,
                "adv_external": 0,
                "adv_total": 0,
                "orders": 0,
                "sales": 0,
            }

        g = groups[sk]
        g["models"].add(model)

        rev = art.get("revenue", 0) or 0
        margin = art.get("margin", 0) or 0
        adv_int = art.get("adv_internal", 0) or 0
        adv_ext = art.get("adv_external", 0) or 0
        orders = art.get("orders_count", 0) or 0
        sales = art.get("sales_count", 0) or 0

        g["revenue"] += rev
        g["margin"] += margin
        g["adv_internal"] += adv_int
        g["adv_external"] += adv_ext
        g["adv_total"] += adv_int + adv_ext
        g["orders"] += orders
        g["sales"] += sales

        g["articles"].append({
            "article": article,
            "model": model,
            "revenue": round(rev, 2),
            "margin": round(margin, 2),
            "adv_total": round(adv_int + adv_ext, 2),
            "orders": orders,
        })

    # Finalize: convert sets, compute ROMI, flag cross-model
    result = []
    for g in groups.values():
        models = sorted(g.pop("models"))
        adv = g["adv_total"]

        g["models"] = models
        g["model_count"] = len(models)
        g["is_cross_model"] = len(models) > 1
        g["article_count"] = len(g["articles"])
        g["revenue"] = round(g["revenue"], 2)
        g["margin"] = round(g["margin"], 2)
        g["adv_internal"] = round(g["adv_internal"], 2)
        g["adv_external"] = round(g["adv_external"], 2)
        g["adv_total"] = round(adv, 2)
        g["romi_group"] = (
            round((g["margin"] - adv) / adv * 100, 1) if adv > 0 else None
        )
        g["margin_pct"] = (
            round(g["margin"] / g["revenue"] * 100, 1)
            if g["revenue"] > 0
            else None
        )

        # Sort articles by adv desc
        g["articles"].sort(key=lambda a: -a["adv_total"])

        result.append(g)

    # Sort: cross-model with ads first, then by ad spend desc
    result.sort(key=lambda g: (-int(g["is_cross_model"]), -g["adv_total"]))

    return {
        "skleyki": {
            "wb": result,
            "total_groups": len(result),
            "cross_model_groups": sum(1 for g in result if g["is_cross_model"]),
            "cross_model_adv": round(
                sum(g["adv_total"] for g in result if g["is_cross_model"]), 2
            ),
            "total_adv": round(sum(g["adv_total"] for g in result), 2),
        }
    }
