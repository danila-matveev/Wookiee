"""ABC analysis routes — per-article financial data with Pareto classification."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from services.dashboard_api.cache import cached
from services.dashboard_api.dependencies import CommonParams
from services.dashboard_api.schemas import AbcArticle, AbcResponse
from shared.data_layer import (
    get_artikuly_full_info,
    get_ozon_by_article,
    get_wb_by_article,
)

logger = logging.getLogger("dashboard_api.abc")

router = APIRouter(prefix="/api/abc", tags=["abc"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _classify_abc(articles: list[dict]) -> list[dict]:
    """Assign ABC category based on margin-based Pareto (80/95/100).

    - Sort by margin descending
    - Cumulative share: A = top 80%, B = 80-95%, C = rest
    - Articles with margin <= 0 are always "C"
    """
    total_margin = sum(max(a["margin"], 0) for a in articles)

    if total_margin <= 0:
        for a in articles:
            a["abc_category"] = "C"
            a["margin_share_pct"] = 0
            a["cumulative_share_pct"] = 0
        return articles

    # Sort by margin descending
    articles.sort(key=lambda a: a["margin"], reverse=True)

    cumulative = 0.0
    for a in articles:
        if a["margin"] <= 0:
            a["abc_category"] = "C"
            a["margin_share_pct"] = 0
            a["cumulative_share_pct"] = 100.0
        else:
            share = a["margin"] / total_margin * 100
            cumulative += share
            a["margin_share_pct"] = round(share, 4)
            a["cumulative_share_pct"] = round(cumulative, 4)

            if cumulative <= 80:
                a["abc_category"] = "A"
            elif cumulative <= 95:
                a["abc_category"] = "B"
            else:
                a["abc_category"] = "C"

    return articles


@cached
def _fetch_metadata() -> dict:
    return get_artikuly_full_info()


def _enrich_with_metadata(articles: list[dict], metadata: dict) -> list[dict]:
    """Add Supabase metadata (status, color, collection) to each article."""
    for a in articles:
        key = a["article"].lower()
        meta = metadata.get(key, {})
        a["status"] = meta.get("status")
        a["model_kod"] = meta.get("model_kod")
        a["model_osnova"] = meta.get("model_osnova")
        a["color_code"] = meta.get("color_code")
        a["color"] = meta.get("color")
        a["tip_kollekcii"] = meta.get("tip_kollekcii")
    return articles


def _mark_new_articles(
    current_articles: list[dict],
    prev_articles: list[dict],
) -> list[dict]:
    """Mark articles that were absent in the previous period as 'New'."""
    prev_keys = {a["article"] for a in prev_articles}
    for a in current_articles:
        if a["article"] not in prev_keys:
            a["abc_category"] = "New"
    return current_articles


# ── Route ────────────────────────────────────────────────────────────────────

@cached
def _fetch_abc(start: str, end: str, prev_start: str, mp: str) -> AbcResponse:
    """Fetch, classify, and enrich ABC data. Cached 5 min."""
    all_articles: list[dict] = []

    if mp in ("wb", "all"):
        wb_current = get_wb_by_article(start, end)
        for a in wb_current:
            a["mp"] = "wb"
        all_articles.extend(wb_current)

    if mp in ("ozon", "all"):
        ozon_current = get_ozon_by_article(start, end)
        for a in ozon_current:
            a["mp"] = "ozon"
        all_articles.extend(ozon_current)

    prev_articles: list[dict] = []

    if mp in ("wb", "all"):
        prev_articles.extend(get_wb_by_article(prev_start, start))

    if mp in ("ozon", "all"):
        prev_articles.extend(get_ozon_by_article(prev_start, start))

    all_articles = _classify_abc(all_articles)
    all_articles = _mark_new_articles(all_articles, prev_articles)

    metadata = _fetch_metadata()
    all_articles = _enrich_with_metadata(all_articles, metadata)

    total_margin = sum(a["margin"] for a in all_articles)

    return AbcResponse(
        articles=[AbcArticle(**a) for a in all_articles],
        total_margin=round(total_margin, 2),
        article_count=len(all_articles),
    )


@router.get("/by-article", response_model=AbcResponse)
def abc_by_article(params: CommonParams = Depends()):
    """Per-article ABC analysis with classification and metadata."""
    return _fetch_abc(params.start_date, params.end_date, params.prev_start, params.mp)
