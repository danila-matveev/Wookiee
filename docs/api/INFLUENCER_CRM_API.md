# Influencer CRM API

Base URL (local): `http://127.0.0.1:8082`
Auth: `X-API-Key: <INFLUENCER_CRM_API_KEY>` on every endpoint except `/health`.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| GET | `/bloggers?limit&cursor&status&marketer_id&q` | — | `Page[BloggerOut]` |
| GET | `/bloggers/{id}` | — | `BloggerDetailOut` |
| POST | `/bloggers` | `BloggerCreate` | `BloggerOut` (201) |
| PATCH | `/bloggers/{id}` | `BloggerUpdate` | `BloggerOut` |
| GET | `/integrations?limit&cursor&stage_in&marketplace&marketer_id&blogger_id&date_from&date_to` | — | `Page[IntegrationOut]` |
| GET | `/integrations/{id}` | — | `IntegrationDetailOut` |
| POST | `/integrations` | `IntegrationCreate` | `IntegrationOut` (201) |
| PATCH | `/integrations/{id}` | `IntegrationUpdate` | `IntegrationOut` |
| POST | `/integrations/{id}/stage` | `StageTransitionIn` | `IntegrationOut` |
| GET | `/products` | — | `Page[ProductSliceOut]` |
| GET | `/products/{model_osnova_id}` | — | `ProductDetailOut` |
| GET | `/tags` | — | `list[TagOut]` |
| POST | `/tags` | `{"name": "..."}` | `TagOut` (find-or-create, 201) |
| GET | `/substitute-articles?status` | — | `Page[SubstituteArticleOut]` |
| GET | `/promo-codes?status` | — | `Page[PromoCodeOut]` |
| POST | `/briefs` | `BriefCreate` | `BriefOut` (201) |
| POST | `/briefs/{id}/versions` | `BriefVersionCreate` | `BriefVersionOut` (201) |
| GET | `/briefs/{id}/versions` | — | `list[BriefVersionOut]` |
| POST | `/metrics-snapshots/{integration_id}` | `MetricsSnapshotIn` | `MetricsSnapshotOut` (201) |
| GET | `/search?q&limit` | — | `{"bloggers": [...], "integrations": [...]}` |

## Auth contract

Send `X-API-Key: <secret>` on every request except `/health`. Wrong/missing key → 403.

## Pagination

All list endpoints return `Page[T]`:

```json
{ "items": [...], "next_cursor": "base64..." | null }
```

To page forward: send `?cursor=<value>`. When `next_cursor` is `null`, you've reached the end.

## ETag

GET endpoints set `ETag`. Honor `If-None-Match` to get `304` on unchanged data.

## Errors

- `403` — missing/wrong API key
- `404` — resource not found
- `409` — unique constraint violation (e.g. duplicate erid)
- `422` — pydantic validation
- `500` — unexpected (we log; do not retry blindly)

## Schema deviations from spec (current dev DB)

A few fields differ from the original schema spec; the API surface is preserved but the DB layer adapts:

- `crm.brief_versions` stores markdown inside JSONB column `content` as `{"md": "..."}`. The API serializes/deserializes `content_md` as a regular string field.
- `crm.briefs.current_version_id` in the API actually maps to the latest version's row id (DB has `current_version` integer storing the version number, not an FK).
- `crm.briefs` requires `status` (default `'draft'`) — set automatically on create.
- `crm.integration_metrics_snapshots` has no free-text `note` column. The API accepts `note` in the request body for future use, but currently the response returns the value of the DB's `source` column (default `'manual'`). Free-text notes are silently dropped — pending a future migration to add a real text field.
- `crm.integration_metrics_snapshots` exposes `fact_ctr` and `fact_cpm` columns alongside the spec'd fact_views/clicks/carts/orders/revenue. The API surface includes these.
- `crm.integration_stage_history.comment` (not `note`). The `POST /integrations/{id}/stage` body field `note` is written to the `comment` column.
- `crm.promo_codes.discount_pct` (not `discount_percent`). The API field stays `discount_percent`; SQL aliases `discount_pct AS discount_percent`.
- `public.modeli.model_osnova_id` (not `osnova_id`); `public.modeli_osnova.nazvanie_etiketka` (not `nazvanie`). Used in the `/products` slices view.

These are documented for future migrations: when a clean schema rewrite happens, align these column names so the DB layer can drop the workarounds.
