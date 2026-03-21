# Comms Live API Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock comms data with real WB/Ozon reviews via API and real AI responses via OpenRouter LLM, with cost tracking.

**Architecture:** FastAPI backend routes fetch reviews from WB + Ozon APIs, normalize to frontend Review type, and cache for 60s. AI generation proxies through OpenRouter (gemini-2.0-flash). Frontend replaces mocks with API calls and adds loading states + cost counter.

**Tech Stack:** FastAPI, httpx, cachetools, OpenRouter (openai SDK), React 19, Zustand 5, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-18-comms-live-api-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `services/dashboard_api/routes/comms.py` | Backend: reviews fetch + normalize + generate + publish stub |
| Edit | `services/dashboard_api/app.py` | Register comms router |
| Edit | `services/dashboard_api/requirements.txt` | Add openai dependency |
| Edit | `wookiee-hub/src/lib/api-client.ts` | Add post() method |
| Edit | `wookiee-hub/src/types/comms.ts` | Add AiGenerationResult type |
| Edit | `wookiee-hub/src/lib/comms-service.ts` | Replace mocks with real API calls |
| Edit | `wookiee-hub/src/stores/comms.ts` | Add loading/error/fetch/cost state |
| Edit | `wookiee-hub/src/components/comms/review-detail.tsx` | Cost badge, read-only publish toast |
| Edit | `wookiee-hub/src/pages/comms-reviews.tsx` | Loading spinner, error banner, cost pill |

---

## Chunk 1: Backend

### Task 1: Create comms backend route

**Files:**
- Create: `services/dashboard_api/routes/comms.py`
- Modify: `services/dashboard_api/app.py:14,41`
- Modify: `services/dashboard_api/requirements.txt`

- [ ] **Step 1: Add openai to requirements.txt**

Append `openai>=1.30.0` to `services/dashboard_api/requirements.txt`.

- [ ] **Step 2: Install dependency**

Run: `pip install openai>=1.30.0`

- [ ] **Step 3: Create `services/dashboard_api/routes/comms.py`**

```python
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


def _fetch_reviews(connection: str) -> list[dict]:
    """Fetch and normalize reviews from WB and/or Ozon."""
    cache_key = f"reviews_{connection}"
    if cache_key in _reviews_cache:
        return _reviews_cache[cache_key]

    all_reviews: list[dict] = []

    if connection in ("wb", "all"):
        wb = _get_wb_client()
        if wb:
            try:
                feedbacks = wb.get_all_feedbacks()
                all_reviews.extend(_normalize_wb_feedback(fb) for fb in feedbacks)
                questions = wb.get_all_questions()
                all_reviews.extend(_normalize_wb_question(q) for q in questions)
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
```

- [ ] **Step 4: Register router in `services/dashboard_api/app.py`**

Add import and include_router:
```python
# After existing imports (line ~14):
from services.dashboard_api.routes.comms import router as comms_router

# After existing routers (line ~46):
app.include_router(comms_router)
```

- [ ] **Step 5: Test backend manually**

Run:
```bash
cd /path/to/Wookiee
python -m services.dashboard_api
```

Then in another terminal:
```bash
curl -s http://localhost:8001/api/comms/reviews?connection=wb | python -m json.tool | head -30
curl -s http://localhost:8001/api/comms/reviews?connection=ozon | python -m json.tool | head -30
```

Expected: JSON with `reviews` array containing real normalized reviews.

- [ ] **Step 6: Test generate endpoint**

```bash
curl -s -X POST http://localhost:8001/api/comms/generate \
  -H 'Content-Type: application/json' \
  -d '{"comment":"Очень удобный, ношу каждый день","rating":5,"product_name":"Vuki","source":"review","system_prompt":"Ты — голос бренда WOOKIEE. Общаешься как близкая подруга. Всегда на ты."}' \
  | python -m json.tool
```

Expected: JSON with `text`, `usage.cost_usd`, `model`.

- [ ] **Step 7: Commit backend**

```bash
git add services/dashboard_api/routes/comms.py services/dashboard_api/app.py services/dashboard_api/requirements.txt
git commit -m "feat(comms): add backend routes for live reviews + AI generation"
```

---

## Chunk 2: Frontend — API client + types + service

### Task 2: Add post() to api-client.ts

**Files:**
- Modify: `wookiee-hub/src/lib/api-client.ts:21-44`

- [ ] **Step 1: Add post method**

After the existing `get<T>()` function (line 44), add:

```typescript
/**
 * Generic POST helper.
 * Sends JSON body and parses the JSON response.
 */
export async function post<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, BASE_URL || window.location.origin)

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }

  return res.json() as Promise<T>
}
```

### Task 3: Add AiGenerationResult type

**Files:**
- Modify: `wookiee-hub/src/types/comms.ts`

- [ ] **Step 1: Add type at end of file**

```typescript
export interface AiGenerationResult {
  text: string
  usage: { input_tokens: number; output_tokens: number; cost_usd: number }
  model: string
}
```

### Task 4: Replace mocks in comms-service.ts

**Files:**
- Modify: `wookiee-hub/src/lib/comms-service.ts` (full rewrite)

- [ ] **Step 1: Rewrite comms-service.ts**

Replace entire file with:

```typescript
import { get, post } from "@/lib/api-client"
import type { Review, AiGenerationResult } from "@/types/comms"
import type { StoreResponseConfig } from "@/types/comms-settings"

function buildSystemPrompt(config: StoreResponseConfig): string {
  const parts: string[] = []

  // Tone instruction
  const toneMap: Record<string, string> = {
    formal: "Отвечайте в официальном, деловом тоне.",
    friendly: "Отвечайте дружелюбно и тепло.",
    neutral: "Отвечайте в нейтральном, сбалансированном тоне.",
    playful: "Отвечайте в лёгком, игривом тоне.",
    wookiee:
      "Ты — голос бренда WOOKIEE. Общаешься как близкая подруга. Всегда на «ты». Тон: тёплый, живой, экспертный, честный. Без канцеляризмов. Эмодзи — скупо (💛, ✨).",
  }
  const tone =
    config.toneOfVoice.preset === "custom"
      ? config.toneOfVoice.custom
      : toneMap[config.toneOfVoice.preset] ?? ""
  if (tone) parts.push(tone)

  // Review prompt from settings
  if (config.reviewPrompt) parts.push(config.reviewPrompt)

  // Signature
  if (config.signatureEnabled && config.signatureTemplate) {
    parts.push(`Подпись: ${config.signatureTemplate}`)
  }

  // Stop words
  if (config.stopWords.length > 0) {
    parts.push(`Никогда не используй слова: ${config.stopWords.join(", ")}`)
  }

  // Negative handling
  if (config.negativeHandling.enabled && config.negativeHandling.prompt) {
    parts.push(`При негативном отзыве: ${config.negativeHandling.prompt}`)
    if (config.negativeHandling.ctaTemplate) {
      parts.push(`CTA для негатива: ${config.negativeHandling.ctaTemplate}`)
    }
  }

  return parts.join("\n\n")
}

export const commsService = {
  /** Fetch real reviews from WB/Ozon via backend */
  async fetchReviews(connection: string = "all"): Promise<Review[]> {
    const data = await get<{ reviews: Review[]; total: number }>(
      "/api/comms/reviews",
      { connection }
    )
    return data.reviews
  },

  /** Generate AI response via OpenRouter LLM */
  async generateAiResponse(
    review: Review,
    config: StoreResponseConfig
  ): Promise<AiGenerationResult> {
    const systemPrompt = buildSystemPrompt(config)

    return post<AiGenerationResult>("/api/comms/generate", {
      comment: review.comment,
      rating: review.rating,
      product_name: review.productName,
      source: review.source,
      system_prompt: systemPrompt,
      pros: review.pros || undefined,
      cons: review.cons || undefined,
    })
  },

  /** Publish response (read-only stub) */
  async publishResponse(
    _connectionId: string,
    _reviewId: string,
    _text: string
  ): Promise<{ success: boolean; reason?: string; message?: string }> {
    return post("/api/comms/publish", {})
  },
}
```

- [ ] **Step 2: Commit frontend service layer**

```bash
git add wookiee-hub/src/lib/api-client.ts wookiee-hub/src/types/comms.ts wookiee-hub/src/lib/comms-service.ts
git commit -m "feat(comms): replace mock service with real API calls"
```

---

## Chunk 3: Frontend — store + UI updates

### Task 5: Update comms store with loading/error/fetch/cost

**Files:**
- Modify: `wookiee-hub/src/stores/comms.ts` (full rewrite)

- [ ] **Step 1: Rewrite comms store**

Replace entire file with:

```typescript
import { create } from "zustand"
import type { Review, ReviewFilters, ReviewStatus } from "@/types/comms"
import { commsService } from "@/lib/comms-service"

interface CommsState {
  reviews: Review[]
  selectedReviewId: string | null
  filters: ReviewFilters
  loading: boolean
  error: string | null
  sessionCost: number
  setSelectedReview: (id: string | null) => void
  setFilters: (filters: Partial<ReviewFilters>) => void
  updateReviewStatus: (id: string, status: ReviewStatus) => void
  setAiDraft: (id: string, draft: string) => void
  publishResponse: (id: string, response: string) => void
  fetchReviews: (connection?: string) => Promise<void>
  addCost: (amount: number) => void
}

export const useCommsStore = create<CommsState>((set, get) => ({
  reviews: [],
  selectedReviewId: null,
  filters: {
    sources: [],
    statuses: [],
    ratings: [],
    connectionIds: [],
    search: "",
    tab: "new",
    processedSubTab: "pending",
    sortBy: "newest",
  },
  loading: false,
  error: null,
  sessionCost: 0,
  setSelectedReview: (id) => set({ selectedReviewId: id }),
  setFilters: (partial) =>
    set((s) => ({ filters: { ...s.filters, ...partial } })),
  updateReviewStatus: (id, status) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id ? { ...r, status } : r
      ),
    })),
  setAiDraft: (id, draft) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id ? { ...r, aiDraft: draft, status: "ai_generated" as const } : r
      ),
    })),
  publishResponse: (id, response) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id
          ? {
              ...r,
              publishedResponse: response,
              status: "published" as const,
              respondedAt: new Date().toISOString(),
            }
          : r
      ),
    })),
  fetchReviews: async (connection = "all") => {
    set({ loading: true, error: null })
    try {
      const reviews = await commsService.fetchReviews(connection)
      set({ reviews, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Ошибка загрузки отзывов",
        loading: false,
      })
    }
  },
  addCost: (amount) =>
    set((s) => ({ sessionCost: s.sessionCost + amount })),
}))
```

### Task 6: Update review-detail.tsx — cost badge + read-only publish

**Files:**
- Modify: `wookiee-hub/src/components/comms/review-detail.tsx`

- [ ] **Step 1: Update imports (line 1-10)**

Add `toast` import (or inline alert) and `useCommsStore` cost:
```typescript
import { useState, useEffect } from "react"
import { Star, Archive, Sparkles, RefreshCw, Send, Loader2, DollarSign } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { getServiceDef } from "@/config/service-registry"
import { useCommsStore } from "@/stores/comms"
import { useCommsSettingsStore } from "@/stores/comms-settings"
import { commsService } from "@/lib/comms-service"
import type { Review } from "@/types/comms"
```

- [ ] **Step 2: Add cost state and update handleGenerate (lines 17-52)**

Inside the component, add state for last generation cost and update handleGenerate:
```typescript
export function ReviewDetail({ review, className }: ReviewDetailProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [draftText, setDraftText] = useState("")
  const [lastCost, setLastCost] = useState<number | null>(null)
  const { setAiDraft, publishResponse, updateReviewStatus, addCost } = useCommsStore()
  const getOrCreateConfig = useCommsSettingsStore((s) => s.getOrCreateConfig)
```

Update handleGenerate:
```typescript
  const handleGenerate = async () => {
    setIsGenerating(true)
    try {
      const config = getOrCreateConfig(review.connectionId)
      const result = await commsService.generateAiResponse(review, config)
      setAiDraft(review.id, result.text)
      setDraftText(result.text)
      setLastCost(result.usage.cost_usd)
      addCost(result.usage.cost_usd)
    } finally {
      setIsGenerating(false)
    }
  }
```

- [ ] **Step 3: Update handlePublish for read-only (lines 54-64)**

```typescript
  const handlePublish = async () => {
    const text = draftText || review.aiDraft || ""
    if (!text) return
    setIsPublishing(true)
    try {
      const result = await commsService.publishResponse(review.connectionId, review.id, text)
      if (!result.success) {
        alert(result.message || "Отправка отключена")
        return
      }
      publishResponse(review.id, text)
    } finally {
      setIsPublishing(false)
    }
  }
```

- [ ] **Step 4: Add cost badge after the draft textarea (after line 180)**

After the Textarea and before the button row, insert a cost indicator:
```tsx
                {lastCost !== null && (
                  <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                    <DollarSign size={10} />
                    <span>${lastCost.toFixed(4)}</span>
                  </div>
                )}
```

Insert this between the `</Textarea>` (line 180) and the button `<div className="flex gap-2 flex-wrap">` (line 181).

### Task 7: Update comms-reviews.tsx — loading spinner + error + cost pill

**Files:**
- Modify: `wookiee-hub/src/pages/comms-reviews.tsx`

- [ ] **Step 1: Add loading/error/fetch/cost to destructuring (line 66)**

Change:
```typescript
const { reviews, selectedReviewId, setSelectedReview, filters, setFilters } = useCommsStore()
```
To:
```typescript
const { reviews, selectedReviewId, setSelectedReview, filters, setFilters, loading, error, fetchReviews, sessionCost } = useCommsStore()
```

- [ ] **Step 2: Add useEffect to fetch on mount (after line 66)**

```typescript
  useEffect(() => {
    fetchReviews("all")
  }, [fetchReviews])
```

- [ ] **Step 3: Add Loader2, AlertCircle imports (line 1-2)**

Update imports:
```typescript
import { useState, useMemo, useEffect } from "react"
import { Loader2, AlertCircle } from "lucide-react"
```

- [ ] **Step 4: Add cost pill in header area**

After `<ReviewsHeader>` (line 138), add session cost pill:
```tsx
      {sessionCost > 0 && (
        <div className="flex justify-end -mt-1">
          <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            AI сессия: ${sessionCost.toFixed(4)}
          </span>
        </div>
      )}
```

- [ ] **Step 5: Add loading/error states in the review list panel**

Replace the reviews list content (lines 153-168) with:
```tsx
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {loading ? (
              <div className="flex items-center justify-center h-32 gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-[13px]">Загрузка отзывов...</span>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-32 gap-2 text-destructive">
                <AlertCircle size={16} />
                <span className="text-[13px] text-center px-4">{error}</span>
                <button
                  onClick={() => fetchReviews("all")}
                  className="text-[12px] text-primary hover:underline"
                >
                  Повторить
                </button>
              </div>
            ) : displayedReviews.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-[13px] text-muted-foreground">
                Нет отзывов
              </div>
            ) : (
              displayedReviews.map((review) => (
                <ReviewListItem
                  key={review.id}
                  review={review}
                  isSelected={selectedReviewId === review.id}
                  onClick={() => setSelectedReview(review.id)}
                />
              ))
            )}
          </div>
```

- [ ] **Step 6: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 7: Vite build**

Run: `cd wookiee-hub && npx vite build`
Expected: Build succeeds.

- [ ] **Step 8: Commit frontend UI updates**

```bash
git add wookiee-hub/src/stores/comms.ts wookiee-hub/src/components/comms/review-detail.tsx wookiee-hub/src/pages/comms-reviews.tsx
git commit -m "feat(comms): live reviews, AI generation with cost tracking, read-only publish"
```

---

## Chunk 4: Integration testing

### Task 8: End-to-end verification

- [ ] **Step 1: Start backend**

```bash
cd /path/to/Wookiee && python -m services.dashboard_api
```

- [ ] **Step 2: Start frontend**

```bash
cd wookiee-hub && npm run dev
```

- [ ] **Step 3: Open Hub, verify real reviews load**

Open `http://localhost:25000/comms/reviews`
- Should see real WB + Ozon reviews (not mock data)
- Reviews answered from WB cabinet should show as "published" with the response text
- Loading spinner visible during fetch

- [ ] **Step 4: Click a review, generate AI response**

- Click an unanswered review
- Click "Сгенерировать ответ"
- Should see real LLM response (not template)
- Cost badge appears (~$0.0003)
- Session cost pill appears in header

- [ ] **Step 5: Try publish — should show read-only alert**

- Click "Опубликовать"
- Should see alert: "Отправка отключена (режим чтения)"

- [ ] **Step 6: Verify with Playwright screenshots (optional)**

```javascript
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  await page.goto('http://localhost:25000/comms/reviews');
  await page.waitForTimeout(8000); // wait for API
  await page.screenshot({ path: '/tmp/pw-live-reviews.png' });
  // Click first review
  const firstReview = await page.$('.space-y-1\\.5 > div:first-child');
  if (firstReview) await firstReview.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/pw-live-detail.png' });
  await browser.close();
})();
```
