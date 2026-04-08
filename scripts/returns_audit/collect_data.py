"""Data collector for returns audit skill.

Fetches return claims from WB Returns API (both cabinets with dedup)
and orders from DB for return rate calculation. Saves to JSON.

Usage:
    python scripts/returns_audit/collect_data.py \
        --output /tmp/returns_audit_data.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.clients.wb_client import WBClient
from shared.data_layer import get_wb_buyouts_returns_by_model
from shared.data_layer.sku_mapping import get_nm_to_article_mapping
from shared.model_mapping import map_to_osnova

logger = logging.getLogger(__name__)


def _deduplicate_claims(claims: list[dict]) -> list[dict]:
    """Remove duplicate claims by id, keeping first occurrence.

    Note: similar to scripts/reviews_audit/collect_data._deduplicate.
    """
    seen = set()
    result = []
    for claim in claims:
        cid = claim.get("id")
        if cid and cid not in seen:
            seen.add(cid)
            result.append(claim)
        elif not cid:
            result.append(claim)
    return result


def _map_claims_to_models(
    claims: list[dict], nm_id_to_article: dict[int, str]
) -> list[dict]:
    """Add model and article fields to each claim based on nm_id mapping."""
    for claim in claims:
        nm_id = claim.get("nm_id")
        article = nm_id_to_article.get(nm_id, "")
        if article:
            prefix = article.split("/")[0]
            claim["model"] = map_to_osnova(prefix).lower()
            claim["article"] = article
        else:
            claim["model"] = "unknown"
            claim["article"] = ""
    return claims


def _build_summary(
    claims: list[dict], orders_by_model: dict[str, dict]
) -> dict:
    """Build summary stats: total claims, per-model claims/orders/rate."""
    model_claims = defaultdict(int)
    for claim in claims:
        model_claims[claim.get("model", "unknown")] += 1

    total_orders = sum(m.get("count", 0) for m in orders_by_model.values())

    by_model = {}
    for model, count in sorted(model_claims.items(), key=lambda x: -x[1]):
        orders = orders_by_model.get(model, {}).get("count", 0)
        rate = round(count / orders * 100, 2) if orders > 0 else 0.0
        by_model[model] = {
            "claims": count,
            "orders": orders,
            "rate_pct": rate,
        }

    return {
        "total_claims": len(claims),
        "total_orders": total_orders,
        "return_rate_pct": round(
            len(claims) / total_orders * 100, 2
        ) if total_orders > 0 else 0.0,
        "by_model": by_model,
    }


def _fetch_claims_from_cabinet(api_key: str, cabinet_name: str) -> list[dict]:
    """Fetch return claims from one WB cabinet."""
    client = WBClient(api_key=api_key, cabinet_name=cabinet_name)
    claims = client.get_return_claims()
    logger.info("[%s] Fetched %d return claims", cabinet_name, len(claims))
    return claims


def _fetch_orders_for_period(date_from: str, date_to: str) -> dict[str, dict]:
    """Fetch orders from DB grouped by model for return rate calc."""
    try:
        # prev_start=date_from makes "previous" period empty; we only use "current".
        # Same pattern as reviews_audit collector.
        raw = get_wb_buyouts_returns_by_model(
            current_start=date_from, prev_start=date_from, current_end=date_to
        )
        result = {}
        for row in raw:
            period, model, orders_count, buyout_count, return_count = row
            if period == "current":
                result[model.lower()] = {
                    "count": orders_count,
                    "buyouts": buyout_count,
                    "returns_db": return_count,
                }
        return result
    except Exception as e:
        logger.error("Failed to fetch orders from DB: %s", e)
        return {}


def _build_nm_id_to_article(claims: list[dict]) -> dict[int, str]:
    """Build nm_id → article mapping.

    Primary source: Supabase artikuly table (nm_id → artikul).
    Fallback: supplierArticle/sa_name from claim data (if present).
    """
    # Primary: Supabase mapping covers all known SKUs
    try:
        mapping = get_nm_to_article_mapping()
        logger.info("Loaded %d nm_id→article mappings from Supabase", len(mapping))
    except Exception as e:
        logger.warning("Failed to load Supabase mapping: %s", e)
        mapping = {}

    # Fallback: extract from claim fields (may not be present in WB Returns API)
    for claim in claims:
        nm_id = claim.get("nm_id")
        if not nm_id or nm_id in mapping:
            continue
        article = claim.get("supplierArticle") or claim.get("sa_name") or ""
        if article:
            mapping[nm_id] = article

    return mapping


def collect_returns_data(output_path: str) -> dict:
    """Collect all data for returns audit.

    Fetches claims from both WB cabinets (ИП + ООО),
    deduplicates, maps to models, fetches orders from DB,
    builds summary.

    Period is fixed to last 14 days — WB Returns API does not support
    custom date ranges.
    """
    key_ip = os.getenv("WB_API_KEY_IP", "")
    key_ooo = os.getenv("WB_API_KEY_OOO", "")

    all_claims = []

    if key_ip:
        all_claims.extend(_fetch_claims_from_cabinet(key_ip, "ИП"))
    if key_ooo:
        all_claims.extend(_fetch_claims_from_cabinet(key_ooo, "ООО"))

    if not all_claims:
        logger.warning("No claims fetched from any cabinet")

    claims = _deduplicate_claims(all_claims)
    logger.info("After dedup: %d claims", len(claims))

    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=14)).strftime("%Y-%m-%d")

    nm_id_map = _build_nm_id_to_article(claims)
    claims = _map_claims_to_models(claims, nm_id_map)

    orders_by_model = _fetch_orders_for_period(date_from, date_to)

    summary = _build_summary(claims, orders_by_model)

    result = {
        "metadata": {
            "period": {"start": date_from, "end": date_to},
            "collected_at": datetime.now().isoformat(),
            "cabinets": ["ИП", "ООО"],
            "total_raw_claims": len(all_claims),
            "total_after_dedup": len(claims),
        },
        "claims": claims,
        "orders_by_model": orders_by_model,
        "summary": summary,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Data saved to %s", output_path)
    return result


def main():
    parser = argparse.ArgumentParser(description="Collect data for returns audit")
    parser.add_argument(
        "--output",
        default="/tmp/returns_audit_data.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_returns_data(output_path=args.output)


if __name__ == "__main__":
    main()
