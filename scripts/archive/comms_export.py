"""Export all WB + Ozon communications (feedbacks, questions, reviews).

Enriches data via Supabase SKU DB: nmId → article → model → model_osnova.
Outputs JSON (raw) + CSV (enriched) to data/comms_export/.

Usage:
    python scripts/comms_export.py [--dry-run] [--wb-only] [--ozon-only]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.sheets_sync.config import CABINET_IP, CABINET_OOO
from shared.clients.ozon_client import OzonClient
from shared.clients.wb_client import WBClient
from shared.data_layer import (
    get_artikul_to_submodel_mapping,
    get_model_statuses,
    get_nm_to_article_mapping,
)
from shared.model_mapping import map_to_osnova, map_to_submodel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUT_DIR = ROOT / "data" / "comms_export"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Supabase enrichment mappings (loaded once)
# ---------------------------------------------------------------------------

def load_enrichment() -> dict:
    """Load all SKU mappings from Supabase."""
    logger.info("Loading SKU mappings from Supabase...")
    nm_map = get_nm_to_article_mapping()  # {nm_id_int: "vuki/black"}
    sub_map = get_artikul_to_submodel_mapping()  # {"vuki/black": {"model_kod": "VukiN", "osnova_kod": "Vuki"}}
    statuses = get_model_statuses()  # {"vuki": "Продается"}
    logger.info(
        "Loaded: %d nm→article, %d article→submodel, %d model statuses",
        len(nm_map), len(sub_map), len(statuses),
    )
    return {"nm_map": nm_map, "sub_map": sub_map, "statuses": statuses}


def enrich_wb_item(item: dict, enrichment: dict, item_type: str) -> dict:
    """Enrich a WB feedback/question with product model data."""
    nm_id = item.get("nmId") or item.get("productDetails", {}).get("nmId")
    article = enrichment["nm_map"].get(nm_id, "") if nm_id else ""
    sub_info = enrichment["sub_map"].get(article, {})
    model_kod = sub_info.get("model_kod", "")
    osnova_kod = sub_info.get("osnova_kod", "")

    # Fallback: extract model from supplierArticle
    supplier_article = (
        item.get("productDetails", {}).get("supplierArticle", "")
        or item.get("supplierArticle", "")
    )
    if not osnova_kod and supplier_article:
        raw_model = supplier_article.split("/")[0] if "/" in supplier_article else supplier_article
        osnova_kod = map_to_osnova(raw_model)
        model_kod = map_to_submodel(raw_model)

    status = enrichment["statuses"].get(osnova_kod.lower(), "Unknown")

    # Common fields
    result = {
        "marketplace": "WB",
        "type": item_type,
        "id": item.get("id", ""),
        "nm_id": nm_id,
        "article": article,
        "supplier_article": supplier_article,
        "product_name": item.get("productDetails", {}).get("productName", ""),
        "model_kod": model_kod,
        "model_osnova": osnova_kod,
        "model_status": status,
        "created_at": item.get("createdDate", ""),
        "is_answered": item.get("answer") is not None and item.get("answer", {}).get("text", "") != "",
    }

    if item_type == "feedback":
        result.update({
            "rating": item.get("productValuation", 0),
            "pros": item.get("pros", ""),
            "cons": item.get("cons", ""),
            "comment": item.get("text", ""),
            "answer_text": item.get("answer", {}).get("text", "") if item.get("answer") else "",
            "photos_count": len(item.get("photoLinks") or []),
        })
    elif item_type == "question":
        result.update({
            "rating": None,
            "pros": "",
            "cons": "",
            "comment": item.get("text", ""),
            "answer_text": item.get("answer", {}).get("text", "") if item.get("answer") else "",
            "photos_count": 0,
        })

    return result


def enrich_ozon_item(item: dict, enrichment: dict) -> dict:
    """Enrich an Ozon review with product model data."""
    # Ozon review structure: sku, product_id, text, rating, etc.
    product_id = item.get("product_id") or item.get("sku")

    # Try to find article via nm mapping (Ozon doesn't use nm_id, but we can try product_id)
    # Ozon matching is done via supplier article if available
    article = ""
    offer_id = item.get("offer_id", "")
    if offer_id:
        article = offer_id.lower()

    sub_info = enrichment["sub_map"].get(article, {})
    model_kod = sub_info.get("model_kod", "")
    osnova_kod = sub_info.get("osnova_kod", "")

    if not osnova_kod and offer_id:
        raw_model = offer_id.split("/")[0] if "/" in offer_id else offer_id
        osnova_kod = map_to_osnova(raw_model)
        model_kod = map_to_submodel(raw_model)

    status = enrichment["statuses"].get(osnova_kod.lower(), "Unknown")

    # Extract text from Ozon review structure
    comment_text = item.get("text", {})
    if isinstance(comment_text, dict):
        positive = comment_text.get("positive", "")
        negative = comment_text.get("negative", "")
        comment = comment_text.get("comment", "")
    else:
        positive = ""
        negative = ""
        comment = str(comment_text) if comment_text else ""

    # Check for seller's response
    comments = item.get("comments", [])
    answer_text = ""
    if comments:
        seller_comments = [c for c in comments if c.get("author_type") == "seller"]
        if seller_comments:
            answer_text = seller_comments[-1].get("text", "")

    return {
        "marketplace": "Ozon",
        "type": "review",
        "id": item.get("id", "") or item.get("review_id", ""),
        "nm_id": product_id,
        "article": article,
        "supplier_article": offer_id,
        "product_name": item.get("product_name", ""),
        "model_kod": model_kod,
        "model_osnova": osnova_kod,
        "model_status": status,
        "created_at": item.get("published_at", "") or item.get("created_at", ""),
        "is_answered": bool(answer_text),
        "rating": item.get("rating", 0),
        "pros": positive,
        "cons": negative,
        "comment": comment,
        "answer_text": answer_text,
        "photos_count": len(item.get("photos") or []),
    }


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "marketplace", "type", "id", "nm_id", "article", "supplier_article",
    "product_name", "model_kod", "model_osnova", "model_status",
    "created_at", "is_answered", "rating", "pros", "cons", "comment",
    "answer_text", "photos_count",
]


def save_json(data: list[dict], filename: str):
    path = OUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved %d items → %s", len(data), path.name)


def save_csv(enriched: list[dict], filename: str):
    path = OUT_DIR / filename
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)
    logger.info("Saved %d rows → %s", len(enriched), path.name)


def export_wb(cabinet, enrichment: dict, dry_run: bool = False) -> list[dict]:
    """Export WB feedbacks + questions for one cabinet."""
    name = cabinet.name
    logger.info("=== WB %s: starting export ===", name)

    client = WBClient(api_key=cabinet.wb_api_key, cabinet_name=name)
    all_enriched = []

    try:
        # Feedbacks
        if dry_run:
            logger.info("[%s] DRY RUN: would fetch WB feedbacks", name)
            raw_feedbacks = []
        else:
            raw_feedbacks = client.get_all_feedbacks()
            save_json(raw_feedbacks, f"wb_feedbacks_{name}.json")

        for fb in raw_feedbacks:
            all_enriched.append(enrich_wb_item(fb, enrichment, "feedback"))

        # Questions
        if dry_run:
            logger.info("[%s] DRY RUN: would fetch WB questions", name)
            raw_questions = []
        else:
            raw_questions = client.get_all_questions()
            save_json(raw_questions, f"wb_questions_{name}.json")

        for q in raw_questions:
            all_enriched.append(enrich_wb_item(q, enrichment, "question"))

        logger.info(
            "[%s] WB total: %d feedbacks + %d questions = %d enriched",
            name, len(raw_feedbacks), len(raw_questions), len(all_enriched),
        )
    finally:
        client.close()

    return all_enriched


def export_ozon(cabinet, enrichment: dict, dry_run: bool = False) -> list[dict]:
    """Export Ozon reviews for one cabinet."""
    name = cabinet.name
    logger.info("=== Ozon %s: starting export ===", name)

    if not cabinet.ozon_client_id or not cabinet.ozon_api_key:
        logger.warning("[%s] Ozon credentials missing, skipping", name)
        return []

    client = OzonClient(
        client_id=cabinet.ozon_client_id,
        api_key=cabinet.ozon_api_key,
        cabinet_name=name,
    )
    all_enriched = []

    try:
        if dry_run:
            logger.info("[%s] DRY RUN: would fetch Ozon reviews", name)
            raw_reviews = []
        else:
            raw_reviews = client.get_all_reviews()
            save_json(raw_reviews, f"ozon_reviews_{name}.json")

        for r in raw_reviews:
            all_enriched.append(enrich_ozon_item(r, enrichment))

        logger.info("[%s] Ozon total: %d reviews", name, len(all_enriched))
    finally:
        client.close()

    return all_enriched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export WB + Ozon communications")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, test enrichment only")
    parser.add_argument("--wb-only", action="store_true", help="Export only WB data")
    parser.add_argument("--ozon-only", action="store_true", help="Export only Ozon data")
    args = parser.parse_args()

    enrichment = load_enrichment()
    all_enriched = []
    timestamp = datetime.now().strftime("%Y-%m-%d")

    cabinets = [CABINET_IP, CABINET_OOO]

    if not args.ozon_only:
        for cab in cabinets:
            all_enriched.extend(export_wb(cab, enrichment, dry_run=args.dry_run))

    if not args.wb_only:
        for cab in cabinets:
            all_enriched.extend(export_ozon(cab, enrichment, dry_run=args.dry_run))

    # Save combined enriched CSV
    if all_enriched:
        save_csv(all_enriched, f"all_comms_{timestamp}.csv")

        # Summary stats
        by_mp = {}
        by_model = {}
        by_type = {}
        for item in all_enriched:
            mp = item["marketplace"]
            model = item["model_osnova"] or "Unknown"
            typ = item["type"]
            by_mp[mp] = by_mp.get(mp, 0) + 1
            by_model[model] = by_model.get(model, 0) + 1
            by_type[typ] = by_type.get(typ, 0) + 1

        logger.info("=" * 60)
        logger.info("EXPORT COMPLETE: %d total items", len(all_enriched))
        logger.info("By marketplace: %s", by_mp)
        logger.info("By type: %s", by_type)
        logger.info("By model (top 10): %s", dict(sorted(by_model.items(), key=lambda x: -x[1])[:10]))
        logger.info("Output: %s", OUT_DIR)
    else:
        logger.warning("No data exported!")


if __name__ == "__main__":
    main()
