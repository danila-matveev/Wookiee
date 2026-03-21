"""Comms routes — real reviews from WB/Ozon + AI generation via OpenRouter."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from cachetools import TTLCache
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.wb_client import WBClient
from shared.clients.ozon_client import OzonClient
from shared.clients.openrouter_client import OpenRouterClient

logger = logging.getLogger("dashboard_api.comms")

router = APIRouter(prefix="/api/comms", tags=["comms"])

# ── Cache ────────────────────────────────────────────────────────────────────
_reviews_cache: TTLCache = TTLCache(maxsize=4, ttl=60)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_wb_client() -> WBClient | None:
    key = os.getenv("WB_API_KEY_IP") or os.getenv("WB_API_KEY_OOO")
    if not key:
        logger.warning("No WB API key found in env")
        return None
    name = "ИП" if os.getenv("WB_API_KEY_IP") else "ООО"
    return WBClient(api_key=key, cabinet_name=f"WB {name}")


def _get_ozon_client() -> OzonClient | None:
    client_id = os.getenv("OZON_CLIENT_ID")
    api_key = os.getenv("OZON_API_KEY")
    if not client_id or not api_key:
        logger.warning("No Ozon credentials found in env")
        return None
    return OzonClient(client_id=client_id, api_key=api_key, cabinet_name="Ozon")


def _get_openrouter() -> OpenRouterClient | None:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        logger.warning("No OPENROUTER_API_KEY found in env")
        return None
    return OpenRouterClient(
        api_key=key,
        model="google/gemini-2.0-flash-001",
        site_name="Wookiee Comms",
    )


def _normalize_wb_feedback(fb: dict) -> dict:
    """Convert WB feedback API response to frontend Review format."""
    answer = fb.get("answer")
    has_answer = answer and answer.get("text")
    product = fb.get("productDetails") or {}

    return {
        "id": f"wb-fb-{fb.get('id', '')}",
        "connectionId": "conn-wb-01",
        "serviceType": "wildberries",
        "source": "review",
        "productName": product.get("productName", ""),
        "productArticle": str(product.get("nmId", "")),
        "productImg": "",
        "authorName": fb.get("userName", "Покупатель"),
        "rating": fb.get("productValuation", 0),
        "status": "published" if has_answer else "new",
        "purchaseStatus": "verified",
        "comment": fb.get("text", ""),
        "pros": fb.get("pros", ""),
        "cons": fb.get("cons", ""),
        "createdAt": fb.get("createdDate", ""),
        "publishedResponse": answer.get("text") if has_answer else None,
        "respondedAt": answer.get("edtDt") if has_answer else None,
        "hasPhoto": bool(fb.get("photoLinks")),
    }


def _normalize_wb_question(q: dict) -> dict:
    """Convert WB question API response to frontend Review format."""
    answer = q.get("answer")
    has_answer = answer and answer.get("text")
    product = q.get("productDetails") or {}

    return {
        "id": f"wb-q-{q.get('id', '')}",
        "connectionId": "conn-wb-01",
        "serviceType": "wildberries",
        "source": "question",
        "productName": product.get("productName", ""),
        "productArticle": str(product.get("nmId", "")),
        "productImg": "",
        "authorName": q.get("userName", "Покупатель"),
        "rating": 0,
        "status": "published" if has_answer else "new",
        "purchaseStatus": "not_verified",
        "comment": q.get("text", ""),
        "createdAt": q.get("createdDate", ""),
        "publishedResponse": answer.get("text") if has_answer else None,
        "respondedAt": answer.get("edtDt") if has_answer else None,
    }


def _normalize_ozon_review(rv: dict) -> dict:
    """Convert Ozon review API response to frontend Review format."""
    company_comment = rv.get("company_comment") or ""
    product = rv.get("product") or {}

    return {
        "id": f"oz-rv-{rv.get('id', '')}",
        "connectionId": "conn-ozon-01",
        "serviceType": "ozon",
        "source": "review",
        "productName": product.get("name", ""),
        "productArticle": str(product.get("offer_id", "")),
        "productImg": "",
        "authorName": rv.get("author_name", "Покупатель"),
        "rating": rv.get("rating", 0),
        "status": "published" if company_comment else "new",
        "purchaseStatus": "verified",
        "comment": rv.get("text", ""),
        "pros": rv.get("pros", ""),
        "cons": rv.get("cons", ""),
        "createdAt": rv.get("created_at", ""),
        "publishedResponse": company_comment or None,
        "respondedAt": rv.get("company_comment_date") if company_comment else None,
        "hasPhoto": bool(rv.get("photos")),
    }


def _fetch_wb_feedbacks_page(wb: "WBClient", is_answered: bool, take: int = 500) -> list[dict]:
    """Fetch a single page of WB feedbacks (newest first)."""
    url = (
        f"{wb.FEEDBACKS_BASE}/api/v1/feedbacks"
        f"?isAnswered={'true' if is_answered else 'false'}"
        f"&take={take}&skip=0"
    )
    resp = wb._request("GET", url)
    if not resp or not resp.get("data", {}).get("feedbacks"):
        return []
    return resp["data"]["feedbacks"]


def _fetch_wb_questions_page(wb: "WBClient", is_answered: bool, take: int = 500) -> list[dict]:
    """Fetch a single page of WB questions (newest first)."""
    url = (
        f"{wb.FEEDBACKS_BASE}/api/v1/questions"
        f"?isAnswered={'true' if is_answered else 'false'}"
        f"&take={take}&skip=0"
    )
    resp = wb._request("GET", url)
    if not resp or not resp.get("data", {}).get("questions"):
        return []
    return resp["data"]["questions"]


def _fetch_reviews(connection: str) -> list[dict]:
    """Fetch and normalize reviews from WB and/or Ozon (limited to recent)."""
    cache_key = f"reviews_{connection}"
    if cache_key in _reviews_cache:
        return _reviews_cache[cache_key]

    all_reviews: list[dict] = []

    if connection in ("wb", "all"):
        wb = _get_wb_client()
        if wb:
            try:
                # Fetch only first page (500 newest) to avoid long pagination
                for answered in (True, False):
                    fbs = _fetch_wb_feedbacks_page(wb, is_answered=answered)
                    all_reviews.extend(_normalize_wb_feedback(fb) for fb in fbs)
                    qs = _fetch_wb_questions_page(wb, is_answered=answered)
                    all_reviews.extend(_normalize_wb_question(q) for q in qs)
            except Exception as e:
                logger.error("WB fetch error: %s", e)
            finally:
                wb.close()

    if connection in ("ozon", "all"):
        ozon = _get_ozon_client()
        if ozon:
            try:
                reviews = ozon.get_all_reviews()
                all_reviews.extend(_normalize_ozon_review(rv) for rv in reviews)
            except Exception as e:
                logger.error("Ozon fetch error: %s", e)
            finally:
                ozon.close()

    # Sort by date descending
    all_reviews.sort(key=lambda r: r.get("createdAt", ""), reverse=True)

    _reviews_cache[cache_key] = all_reviews
    return all_reviews


# ── Request/Response models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    comment: str
    rating: int = 0
    product_name: str = ""
    source: str = "review"
    system_prompt: str
    pros: Optional[str] = None
    cons: Optional[str] = None


class GenerateResponse(BaseModel):
    text: str
    usage: dict
    model: str


class PublishResponse(BaseModel):
    success: bool
    reason: str
    message: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/reviews")
def get_reviews(connection: str = "all", limit: int = 500):
    """Fetch normalized reviews from WB and/or Ozon."""
    if connection not in ("wb", "ozon", "all"):
        raise HTTPException(400, f"Invalid connection: {connection}")

    reviews = _fetch_reviews(connection)
    total = len(reviews)
    limited = reviews[:limit]

    return {
        "reviews": limited,
        "total": total,
        "cached": f"reviews_{connection}" in _reviews_cache,
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate_response(req: GenerateRequest):
    """Generate AI response for a review via OpenRouter LLM."""
    client = _get_openrouter()
    if not client:
        raise HTTPException(500, "OpenRouter not configured (missing OPENROUTER_API_KEY)")

    # Build user message
    parts = [f'Отзыв на "{req.product_name}" (рейтинг: {req.rating}/5):']
    if req.comment:
        parts.append(req.comment)
    if req.pros:
        parts.append(f"Достоинства: {req.pros}")
    if req.cons:
        parts.append(f"Недостатки: {req.cons}")
    parts.append("\nНапиши ответ на этот отзыв.")

    messages = [
        {"role": "system", "content": req.system_prompt},
        {"role": "user", "content": "\n".join(parts)},
    ]

    result = await client.complete(
        messages=messages,
        temperature=0.6,
        max_tokens=500,
    )

    if result.get("error"):
        raise HTTPException(502, f"LLM error: {result['error']}")

    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    # gemini-2.0-flash: $0.10/1M input, $0.40/1M output
    cost_usd = input_tokens * 0.10 / 1_000_000 + output_tokens * 0.40 / 1_000_000

    return GenerateResponse(
        text=result.get("content", ""),
        usage={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6),
        },
        model=result.get("model", "google/gemini-2.0-flash-001"),
    )


@router.post("/publish", response_model=PublishResponse)
def publish_response():
    """Stub — publishing is disabled (read-only API keys)."""
    return PublishResponse(
        success=False,
        reason="read_only",
        message="Отправка отключена (режим чтения)",
    )
