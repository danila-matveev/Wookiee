# Influencer CRM Implementation Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first CRM for blogger relationships management on top of existing Supabase project. Replace 1821-row Google Sheets workbook with relational schema, FastAPI backend, and React frontend that matches v3a/v3b mockups (Trello-board + per-blogger drawer + slices view).

**Architecture:** 22-table Postgres schema in Supabase `public` (already designed as v4.1, applied via migration 008). Python BFF (FastAPI) with service_role connects directly via psycopg connection pooler — no Supabase Auth on local. ETL pulls from Sheets every 6h until cutover. React+Vite+TypeScript frontend renders Trello board + blogger drawer + product slices using mockups as design contract.

**Tech Stack:**
- DB: Postgres 15 (Supabase), psycopg 3, SQLAlchemy 2.x typed
- ETL: gws CLI (Google Sheets) → pandas → psycopg COPY
- API: FastAPI + pydantic v2, uvicorn local
- Frontend: React 18 + Vite + TypeScript + TailwindCSS 4 + shadcn/ui
- State: TanStack Query for server cache
- Lint/Type: ruff + mypy + tsc + biome

---

## Skill Map (locked per phase)

Each phase has explicit skill assignments — no improvisation. Skills are invoked via the `Skill` tool inside the executing subagent.

| Phase | Implementation skills | Verification skills |
|---|---|---|
| **P1 Database** | `superpowers:subagent-driven-development` `superpowers:test-driven-development` | `superpowers:verification-before-completion` `supabase:supabase-postgres-best-practices` |
| **P2 Sheets ETL** | `superpowers:subagent-driven-development` `superpowers:test-driven-development` `gws-sheets` `gws-drive` | `superpowers:verification-before-completion` `superpowers:requesting-code-review` `codex-arch-review` |
| **P3 API BFF** | `superpowers:subagent-driven-development` `superpowers:test-driven-development` `claude-api` (if AI features) `supabase:supabase` | `superpowers:verification-before-completion` `codex-quality-gate` `gstack-review` |
| **P4 Frontend** | `frontend-design:frontend-design` `ui-ux-pro-max` `gstack-design-html` `superpowers:subagent-driven-development` | **MANDATORY QA gates — see § QA Gates below** |
| **P5 Sync & ops** | `superpowers:subagent-driven-development` `tool-register` (register sync as tool) | `tool-status` `superpowers:verification-before-completion` |

**Cross-cutting (any phase):**
- `superpowers:systematic-debugging` — when bugs appear
- `superpowers:dispatching-parallel-agents` — when 2+ independent tasks
- `codex:rescue` — when stuck or want second-opinion implementation

---

## Phase Overview

| # | Phase | Detailed plan | Status | Estimated effort |
|---|---|---|---|---|
| 1 | **Database** — apply migration 008 v4.1 to Supabase, write Python wrapper, verify | [p1-database.md](./2026-04-26-influencer-crm-p1-database.md) | DRAFTED | 1 day |
| 2 | **Sheets ETL** — pull-only import from 5 critical sheets, validation gate, idempotent re-run | TBD (write after P1) | PENDING | 3-4 days |
| 3 | **API BFF** — FastAPI with endpoints powering all 7 UX scenarios from mockups | TBD (write after P2) | PENDING | 2-3 days |
| 4 | **Frontend** — React app implementing v3a (drawer edit) + v3b (slices/products) + Kanban | TBD (write after P3) | PENDING | 5-7 days |
| **QA1** | **Functional QA + visual QA + dogfood** — autonomous test loop after P4 | TBD | MANDATORY | 1-2 days |
| 5 | **Sync & monitoring** — cron Sheets pull, MV refresh, retention jobs, observability | TBD (write after QA1) | PENDING | 1-2 days |
| **QA2** | **Post-deploy canary** — autonomous monitoring after P5 | TBD | MANDATORY | 0.5 day |

Total: ~14-19 working days including QA gates.

---

## QA Gates (mandatory, autonomous)

User requirement: after each implementation phase that produces a user-facing artifact, **autonomous QA must run before declaring phase done**. The dev does not say "ready" — the QA loop says it.

### After P1 (Database) — Schema smoke gate
**Skill:** `superpowers:verification-before-completion` + `supabase:supabase-postgres-best-practices`
**What runs:**
- 22 tables exist
- All indexes/triggers/MV created
- RLS enabled on all 22
- Marketers seed = 5 rows
- `chk_int_erid` blocks insert with NULL erid in `published` stage (manual SQL test)
- `total_cost` GENERATED column handles NULL costs → 0.0
**Pass criterion:** all assertions in `test_influencer_crm_schema.py` GREEN.

### After P2 (Sheets ETL) — Data quality gate
**Skill:** `superpowers:verification-before-completion` + `codex-arch-review` for diff between Sheets pivots vs DB queries
**What runs:**
- 0 rows lost (Sheets count = DB count by source sheet)
- ≥95% blogger handles resolved
- sum(cost) per month ±1% match between Sheets pivot and DB SUM
- Idempotent re-run produces zero changes (run twice, diff)
- Each anomaly category logged to CSV
**Pass criterion:** validation script returns exit 0 + report.

### After P3 (API BFF) — Contract gate
**Skill:** `superpowers:verification-before-completion` + `codex-quality-gate` (cross-model review of API code) + `gstack-review` (SQL safety + structural)
**What runs:**
- pytest + httpx async — all endpoint contract tests green
- OpenAPI spec at `/docs` covers every endpoint
- Pagination/cursor consistency verified
- N+1 detection: each list-endpoint must execute ≤3 queries (assert via SQLAlchemy event listener)
- Auth: anon attempts blocked
**Pass criterion:** test suite green + Codex finds 0 critical, ≤3 warnings.

### **QA1 — After P4 (Frontend) — MANDATORY autonomous Playwright loop**
**Skills (run in sequence):**
1. **`gstack-qa`** — Systematically QA the running web app, Playwright under the hood. Iteratively fixes bugs and commits.
2. **`gstack-design-review`** — Designer's-eye review (spacing, hierarchy, AI-slop patterns, slow interactions). Iteratively fixes visual issues in source code.
3. **`dogfood`** — Exploratory testing (find UX issues, edge cases, broken flows that scripted tests miss).
4. **Direct Playwright MCP** (`mcp__plugin_playwright_playwright__*`) — for specific flow scenarios that need manual scripting:
   - Create blogger → drag integration through 10 stages → see in Kanban dwell-time
   - Search "плюс сайз" in bloggers → see filtered list
   - Open product (Wendy) slice → see all integrations halo
   - Edit brief from inside integration drawer → see audit_log entry

**What runs (golden paths):**
- **GP-1 Kanban**: open `/integrations` → see 10 stage columns → drag card from `agreed` to `awaiting_content` → API PATCH succeeds → optimistic update + rollback on failure → audit_log row created
- **GP-2 Blogger drawer**: search blogger → open drawer → switch tabs (Info / Channels / Integrations / Compliance) → edit a field → save → see toast + refetch
- **GP-3 Integration drawer (multi-model)**: open existing integration with 2 substitute_articles → see both displayed with display_order → edit → save → posts tab shows integration_posts
- **GP-4 Product slice**: navigate to Products → click "Wendy" → see all integrations grouped by month + halo of related models
- **GP-5 Slices filter combo**: marketplace=wb × period=Q1 × marketer=Лиля × tag=lifestyle → table updates → CSV export works
- **GP-6 Promo code attribution**: filter integrations with promo "CHARLOTTE10" → see attribution
- **GP-7 Search**: full-text "плюс сайз" → see bloggers + integrations filtered

**What gets checked across breakpoints:**
- 1440px (desktop default), 1920px (large), 1024px (laptop), 768px (tablet), 375px (mobile fallback — even if not core target)

**Pass criteria (all must hold):**
- 0 console errors in QA browser session
- All 7 golden paths complete without manual intervention
- `gstack-design-review` verdict: ≥8/10 on hierarchy + spacing + clarity
- `gstack-qa` returns "no fixable bugs remaining" after auto-fix loop
- Performance: each page render <1s on local, <200ms API responses (p95)
- Accessibility: tab navigation works for all forms (Tab + Enter completes flow)

**On fail:** loop iterates — `gstack-qa` fixes the bug, commits, re-tests. Manual escalation only if 3 iterations fail on same issue.

### After P5 (Sync & ops) — Canary gate
**Skill:** `gstack-canary` — post-deploy monitoring (console errors, performance regressions) + `tool-status`
**What runs:**
- Cron job triggered → Sheets pulled → DB updated within 6h SLA
- MV refresh ran → query latency on landing screen <200ms
- Retention DELETE didn't lose live rows
**Pass criterion:** dashboard green for 24h after enable.

---

## Phase Decomposition Principle

Each phase produces working, testable software:
- **P1**: schema applied, smoke-tests pass
- **P2**: data loaded, validation script reports ≥95% match
- **P3**: API endpoints respond with correct payloads (pytest + Codex review)
- **P4**: frontend renders Kanban + drawer + slices on real data
- **QA1**: golden paths pass autonomous Playwright loop
- **P5**: cron jobs running, dashboards show live state
- **QA2**: 24h canary green

Don't write Phase N+1 plan until Phase N is in execution. Requirements often change after touching real data.

---

## Cross-Cutting Decisions (apply to all phases)

These decisions, locked from v4.1 schema design + Codex review, propagate through every phase:

1. **PKs are BIGSERIAL** (not UUID). Sheets idempotency via `sheet_row_id` content-hash.
2. **No Supabase Auth on local** — FastAPI uses service_role pooler connection directly.
3. **DB queries only via `shared/data_layer/influencer_crm/`** (new module, follows project rule).
4. **Money is `numeric(12,2)` in DB, `Decimal` in Python**. Never float.
5. **GROUP BY by model uses `LOWER(SPLIT_PART(article,'/',1))`** (already in schema where relevant).
6. **Weighted averages for percentages** (CPM, CTR, ROMI). Materialised view `v_blogger_totals` does this at DB level.
7. **Sheets is source-of-truth until cutover.** Pull-only direction in P1-P3. P5 adds optional push-back.
8. **Atomic, frequent commits.** Each step that compiles + passes test = commit.
9. **TDD for non-trivial logic.** ETL transforms, API endpoints, frontend hooks have tests. Schema migrations don't (verified via apply).
10. **Errors don't go silent.** ETL row failures get logged to `audit_log` with row identity; user-facing errors surface in UI.
11. **No claim of "done" without QA gate passing.** This is enforced by `superpowers:verification-before-completion` invocation at end of each phase.

---

## Phase 1: Database Setup

**Goal:** Migration 008 applied to Supabase dev project. Smoke tests confirm 22 tables exist, all indexes/triggers/RLS work, materialized view refreshable.

**Deliverables:**
- `sku_database/scripts/migrations/008_create_influencer_crm.py` — Python wrapper (`--dry-run`, `--force`)
- Migration applied to remote Supabase
- Smoke-test suite `sku_database/scripts/test_influencer_crm_schema.py` (5 pytest tests)
- SQLAlchemy typed models for 7 core tables
- Updated `sku_database/README.md` + new `docs/database/INFLUENCER_CRM.md`
- Memory entry `project_influencer_crm.md`

**Detailed plan:** [`2026-04-26-influencer-crm-p1-database.md`](./2026-04-26-influencer-crm-p1-database.md)

---

## Phase 2: Sheets ETL Outline

**Goal:** Migrate all data from "Маркетинг Wookiee" workbook into the CRM tables. Idempotent re-run produces same state.

**Sub-tasks (TDD):**
1. **Sheets reader module** (`shared/data_layer/influencer_crm/sheets_reader.py`)
   - Generic `read_sheet(sheet_name, range_a1) → pd.DataFrame`
   - Cache layer (skip re-fetch if `last_pulled_at < N min ago`)
   - Pytest with mock CSV fixtures
2. **Stage 1: marketers + tags seed** (already in DDL `INSERT`)
3. **Stage 2: substitute_articles + weekly metrics**
   - Parser for 223-col layout: 8 meta + 52 weeks × 4 metrics
   - Match `model + nomenklatura → artikuly.id` via dictionary
   - Tests with synthetic 5-week × 3-code fixtures
4. **Stage 3: promo_codes** — 7 cols + UUID preservation
5. **Stage 4: bloggers + blogger_channels**
   - "БД БЛОГЕРЫ": 1 row → 1 blogger + N channels
   - URL → channel detection (`instagram.com` → instagram, etc.)
   - "inst на проверку" → blogger_candidates
6. **Stage 5: integrations** (largest)
   - Lookup blogger_id by handle (with URL fallback)
   - Multi-model parsing (cols 33+36)
   - Stage Russian → English mapping
   - Compliance booleans: empty → NULL
7. **Stage 6: validation gate**
   - 0 rows lost, ≥95% resolved, sum(cost) ±1%
   - Anomaly CSV report
8. **Stage 7: idempotent dry-run** — re-run produces zero changes

**Files (sketched):**
- `shared/data_layer/influencer_crm/__init__.py`
- `shared/data_layer/influencer_crm/sheets_reader.py`
- `shared/data_layer/influencer_crm/etl/{marketers,substitute_articles,promo_codes,bloggers,integrations}.py`
- `scripts/sheets_to_crm.py` — orchestrator CLI
- `scripts/validate_crm_migration.py` — gate
- `tests/data_layer/influencer_crm/`

---

## Phase 3: API BFF Outline

**Goal:** FastAPI app exposing endpoints sufficient to render all 7 UX scenarios from mockups.

**Endpoint families:**
- `GET /bloggers?status&marketer&tag&q` — list with filters + cursor pagination
- `GET /bloggers/{id}` — drawer payload (channels, integrations history, last 10)
- `POST /bloggers` / `PATCH /bloggers/{id}` — create/update
- `GET /integrations` (Kanban-aware: `?stage_in=...`, `?date_from`, `?archived=false`)
- `GET /integrations/{id}` — drawer with brief, posts, substitutes, promos, metrics history
- `POST /integrations` / `PATCH /integrations/{id}` — including stage transitions (audit + history via trigger)
- `GET /products` (model-osnova-level) — slices view with integration count
- `GET /products/{model_osnova_id}` — slice card
- `GET /tags` / `POST /tags`
- `GET /substitute-articles` / `GET /promo-codes`
- `POST /briefs` / brief versioning
- `POST /metrics-snapshots/{integration_id}` — manual fact entry

**Architecture:**
- `shared/data_layer/influencer_crm/repository/` — query logic per aggregate
- `services/influencer_crm/` — FastAPI app, pydantic models, routes
- TanStack Query-friendly: cursor pagination, ETag on list endpoints, no N+1
- Read paths use materialised views (`v_blogger_totals`, future `v_integration_models`)
- Write paths use SQLAlchemy session per request

**Tests:** pytest + httpx async client, fixtures for seed data.

---

## Phase 4: Frontend Outline

**Goal:** React app implementing mockups v3a/v3b at production quality. Use `frontend-design:frontend-design` skill for component generation, `ui-ux-pro-max` for design system.

**Mockup contracts (locked):**
- v3a `mvp-mockup-v3a-edit-drawers.html` — drawer interaction patterns
- v3b `mvp-mockup-v3b-slices-products.html` — slices and product views
- prototype `prototype.html` — overall navigation

**Screens:**
- **Sidebar nav**: Bloggers · Integrations (Kanban) · Products · Briefs · Tags · Candidates
- **Kanban**: 10-stage columns, drag-drop transitions, dwell-time chip
- **Blogger drawer (v3a)**: tabs — Info, Channels, Integrations, Compliance, Notes
- **Integration drawer (v3a)**: tabs — Info, Brief, Substitutes, Promos, Posts, Metrics, Compliance
- **Product slice (v3b)**: filterable table per model
- **Slices view (v3b)**: parallel selectors marketplace × period × marketer × tag
- **Search**: GIN-tsvector backed full-text

**Stack:** React 18 + Vite + TS + Tailwind v4 + shadcn/ui + lucide-react + dnd-kit + recharts.

**State:** TanStack Query v5, no global store. Each drawer is a query.

**Auth:** none on local. Future-ready: header `X-User-Id` (not enforced).

**Tests:** vitest + React Testing Library on hooks, then **MANDATORY** QA1 gate (Playwright via `gstack-qa`).

---

## Phase 5: Sync & Monitoring Outline

**Goal:** Production-grade ops: scheduled syncs, MV refresh, retention, basic dashboards.

**Tasks:**
- pg_cron: refresh `v_blogger_totals` every 5 min, retention DELETEs weekly
- systemd timer or cron on app server: `sheets_to_crm.py --incremental` every 6h
- `tool_telemetry` integration (`tool-register` skill registers ETL as tool, `tool-status` skill shows runs)
- Notion entry on completed cutover
- Lightweight ops dashboard
- Cutover playbook (Sheets → CRM): [`docs/runbooks/influencer-crm-cutover.md`](../../runbooks/influencer-crm-cutover.md)

---

## Open Questions / Decisions Locked

**Locked (from earlier conversation):**
- 1 WW = 1 артикул
- 1 blogger = 1 record, multi-channel via blogger_channels
- Brief 1:N, contracts not linked
- Reels+Stories = usually 1 integration; integration_posts for 1:N case
- Tags = open set
- Auth = service_role only locally
- BIGSERIAL not UUID
- Promo codes mirror substitutes
- TZ-templates per channel/format = `content_brief_templates`
- Sheets = SoT until cutover
- **Mandatory autonomous QA1 (Playwright) gate after P4** ← user requirement

**Open (will surface during P2 ETL):**
- Stage Russian wording → English mapping table
- "Магазин" Sheets values → wb/ozon/both mapping
- Handle/URL conflict resolution (one blogger, 3 spellings)
- Multi-model integrations cost allocation: equal? primary-takes-all? — defer until reports

These get answered as P2 starts pulling real rows.

---

## Self-Review Checklist

- **Spec coverage**: All 6 blockers + 12 majors from earlier critique → fixed in v4.1 schema (P1 verifies). All 5 critical from Codex → fixed in v4.1. UX scenarios (Kanban / drawer / slices / search / Trello-dwell) → P3 endpoints + P4 screens map 1:1 to mockups. QA1 covers all 7 golden paths. ✅
- **Placeholder scan**: No "TODO", "implement later", "fill in details" anywhere in this roadmap. Sub-task lists in P2-P5 are intentionally outline (not detailed) — those become detailed plans when written. ✅
- **Type consistency**: Function names mentioned in roadmap (`read_sheet`, `sheets_to_crm.py`, `v_blogger_totals`, `008_create_influencer_crm.py`) align with schema names and migration filenames. No drift. ✅
- **Skill assignment**: every phase has explicit implementation skill + verification skill. QA1 is mandatory and uses Playwright via `gstack-qa`. ✅

---

## How execution works

After P1 plan is approved:
1. Execute P1 task-by-task (subagent-driven recommended).
2. On P1 completion → write detailed P2 plan, get approval, execute.
3. Repeat for P3.
4. After P3 → write detailed P4 plan with `frontend-design` skill, execute.
5. After P4 ships → **autonomously run QA1 loop** (`gstack-qa` → `gstack-design-review` → `dogfood` → manual Playwright scripts) until all 7 golden paths green, ≥8/10 design score.
6. After QA1 passes → write P5, execute, run QA2 canary.

This avoids writing detailed P4 frontend tasks before we know what the API actually returns, and avoids declaring "done" without an autonomous browser proving it works.
