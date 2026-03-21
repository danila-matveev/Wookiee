# Comms Live API Integration — Design Spec

## Goal

Replace mock data in Wookiee Hub comms module with real WB/Ozon reviews and AI-generated responses via OpenRouter LLM. Add cost tracking UI.

## Constraints

- Publish endpoint is read-only (API keys are read-only)
- Reviews answered from WB/Ozon cabinets must show as "published"
- Frontend settings (prompts, tone, product models) stay in localStorage (Zustand persist) — backend receives them per-request
- Cost counter is session-scoped (no persistence needed)

## Architecture

```
Browser (React)
  │
  ├─ GET /api/comms/reviews?connection=wb|ozon|all
  │     → dashboard_api → WBClient + OzonClient → normalize → cache 60s → JSON
  │
  ├─ POST /api/comms/generate
  │     body: { comment, rating, product_name, source, system_prompt }
  │     → dashboard_api → OpenRouterClient (gemini-2.0-flash-001) → { text, usage }
  │
  └─ POST /api/comms/publish
        → { success: false, reason: "read_only" }
```

## Backend: `services/dashboard_api/routes/comms.py`

### GET /api/comms/reviews

Query params:
- `connection`: `wb` | `ozon` | `all` (default: `all`)
- `limit`: int (default: 500)

Response: `{ reviews: Review[], total: int, cached: bool }`

WB feedback normalization:
```python
{
  "id": f"wb-fb-{feedback['id']}",
  "connectionId": "conn-wb-01",
  "serviceType": "wildberries",
  "source": "review",
  "productName": feedback.get("productDetails", {}).get("productName", ""),
  "productArticle": str(feedback.get("productDetails", {}).get("nmId", "")),
  "productImg": "",  # WB feedbacks API doesn't return images
  "authorName": feedback.get("userName", "Покупатель"),
  "rating": feedback.get("productValuation", 0),
  "status": "published" if feedback.get("answer") else "new",
  "purchaseStatus": "verified",
  "comment": feedback.get("text", ""),
  "pros": feedback.get("pros", ""),
  "cons": feedback.get("cons", ""),
  "createdAt": feedback.get("createdDate", ""),
  "publishedResponse": feedback.get("answer", {}).get("text") if feedback.get("answer") else None,
  "respondedAt": feedback.get("answer", {}).get("edtDt") if feedback.get("answer") else None,
}
```

WB question normalization:
```python
{
  "id": f"wb-q-{question['id']}",
  "source": "question",
  "rating": 0,
  "comment": question.get("text", ""),
  # answer field same pattern as feedbacks
}
```

Ozon review normalization:
```python
{
  "id": f"oz-rv-{review['id']}",
  "connectionId": "conn-ozon-01",
  "serviceType": "ozon",
  "source": "review",
  "productName": review.get("product", {}).get("name", ""),
  "rating": review.get("rating", 0),
  "comment": review.get("text", ""),
  "status": "published" if review.get("company_comment") else "new",
  "publishedResponse": review.get("company_comment") or None,
}
```

Cache: `cachetools.TTLCache(maxsize=4, ttl=60)` keyed by connection type.

### POST /api/comms/generate

Request body:
```json
{
  "comment": "string — review text",
  "rating": 5,
  "product_name": "Vuki",
  "source": "review | question",
  "system_prompt": "string — full system prompt from frontend settings",
  "pros": "optional",
  "cons": "optional"
}
```

Response:
```json
{
  "text": "Привет! Это Wookiee 💛 ...",
  "usage": {
    "input_tokens": 450,
    "output_tokens": 120,
    "cost_usd": 0.000093
  },
  "model": "google/gemini-2.0-flash-001"
}
```

LLM prompt construction (on backend):
```
System: {system_prompt from frontend}

User: Отзыв на "{product_name}" (рейтинг: {rating}/5):
{comment}
{pros ? "Достоинства: " + pros : ""}
{cons ? "Недостатки: " + cons : ""}

Напиши ответ на этот отзыв.
```

Model: `google/gemini-2.0-flash-001`
Temperature: 0.6
Max tokens: 500

Cost formula: `input_tokens * 0.10 / 1_000_000 + output_tokens * 0.40 / 1_000_000`

### POST /api/comms/publish

Always returns:
```json
{ "success": false, "reason": "read_only", "message": "Отправка отключена (режим чтения)" }
```

## Frontend Changes

### `src/lib/api-client.ts`
Add `post<T>(path, body, signal?)` method.

### `src/lib/comms-service.ts`
Replace mock implementations:
- `fetchReviews(connectionId)` → `GET /api/comms/reviews?connection=...`
- `generateAiResponse(review, config)` → `POST /api/comms/generate` with system_prompt assembled from config
- `publishResponse()` → `POST /api/comms/publish`

Return type of `generateAiResponse` changes from `string` to `{ text: string, usage: { input_tokens, output_tokens, cost_usd } }`.

### `src/stores/comms.ts`
- Add `loading: boolean`, `error: string | null`
- Add `fetchReviews(connection)` action that calls comms-service
- Add `sessionCost: number` — cumulative cost counter
- Add `addCost(amount)` action
- Replace `reviews: mockReviews` with `reviews: []` + fetch on mount

### `src/types/comms.ts`
Add:
```typescript
export interface AiGenerationResult {
  text: string
  usage: { input_tokens: number; output_tokens: number; cost_usd: number }
  model: string
}
```

### UI: Cost counter
- In `ReviewDetail` component: after AI generation, show "~$0.0003" badge next to the draft
- In reviews page header: small pill showing session total "AI: $0.02"

### UI: Loading state
- Spinner overlay on reviews list during initial fetch
- Error banner if API fails, with "Retry" button

### UI: Read-only publish
- "Отправить" button shows toast: "Отправка отключена (режим чтения)" instead of mock success

## Files Changed

| Action | File | Scope |
|--------|------|-------|
| Create | `services/dashboard_api/routes/comms.py` | Backend route + normalization |
| Edit | `services/dashboard_api/app.py` | Register comms router |
| Edit | `wookiee-hub/src/lib/api-client.ts` | Add post() |
| Edit | `wookiee-hub/src/lib/comms-service.ts` | Replace mocks with API calls |
| Edit | `wookiee-hub/src/stores/comms.ts` | Loading, error, fetch, cost |
| Edit | `wookiee-hub/src/types/comms.ts` | AiGenerationResult type |
| Edit | `wookiee-hub/src/components/comms/review-detail.tsx` | Cost badge, loading, read-only publish |
| Edit | `wookiee-hub/src/pages/comms-reviews.tsx` | Loading spinner, cost pill, error banner |

## Testing

1. Start dashboard_api: `cd services/dashboard_api && uvicorn app:app --port 8001`
2. Verify `curl localhost:8001/api/comms/reviews` returns real WB+Ozon reviews
3. Verify `curl -X POST localhost:8001/api/comms/generate -d '{"comment":"test","rating":5,"product_name":"Vuki","source":"review","system_prompt":"Ты голос бренда WOOKIEE"}' -H 'Content-Type: application/json'` returns LLM response
4. Open Hub → Reviews → see real reviews
5. Click review → Generate → see real AI response with cost
6. Click Publish → see read-only toast
7. TypeScript + Vite build pass
