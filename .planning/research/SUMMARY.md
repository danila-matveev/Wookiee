# Project Research Summary

**Project:** Wookiee Product Matrix — Notion-like PIM Table Editor
**Domain:** PIM (Product Information Management) editor — Notion/Airtable-style table UI over a 4-level product hierarchy (ModelOsnova → Artikul → Tovar → barcodes), 9 entity types, 90+ fields
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

This milestone replaces Google Sheets as the daily working tool for managing a fashion brand's product catalog (1450+ SKUs across 9 entity types). The shell already exists — layout, sidebar, topbar, table, detail panel, bulk operations, and all backend CRUD are built — but approximately 70% of the intended functionality is missing or broken: the detail panel is hardcoded to `models`, shows only 5 of 22 fields, has no editing capability, reference fields display "—" instead of names, and filter/sort controls are not wired. The job is completing and hardening what was started, not building from scratch.

The recommended approach is a layered build in strict dependency order. Phase 1 must address structural rot first — entity type mapping fragmentation (4 out-of-sync maps), detail panel entity dispatch hardcoded to `models`, and missing Zustand state for filters/sort/column widths. Only after this foundation is correct can field rendering (edit forms, lookup caching, validation, field visibility) and then table UX improvements (sort, filter bar, column resize) be safely added. The technology stack is already optimal: TanStack Table v8 + TanStack Virtual v3 integrate with the existing `@dnd-kit` and `zustand` setup, and `shadcn Sheet` covers the detail panel with zero new layout libraries.

The critical risk is data corruption from the hardcoded `models` endpoint in `DetailPanel`. If edit functionality is shipped before this is fixed, PATCHes for articles and products will silently hit `/api/matrix/models/{id}` with wrong field names, writing corrupt data. The second risk is scope creep into anti-features (inline editing for all 90+ fields, real-time collaboration, undo/redo, CSV import) that the project's own design spec explicitly rejects. The path to "replaces Google Sheets" is well-defined and has no fundamental unknowns.

## Key Findings

### Recommended Stack

The project is already correctly set up (React 19, Vite, Tailwind v4, shadcn/ui, zustand, @dnd-kit). New additions are minimal: `@tanstack/react-table@8.21.3` (headless table engine, ~15KB gzip) and `@tanstack/react-virtual@3.13.23` (~6KB) for virtualization, plus `react-hook-form@7.72.0` + `zod@3.25.x` + `@hookform/resolvers@5.2.2` (~30KB combined) for detail panel forms. shadcn components to add via CLI: `sheet`, `form`, `select`, `separator`, `badge`, `tooltip`, `checkbox`.

**Core technologies:**
- `@tanstack/react-table`: Headless table engine — sorting, filtering, column resize, column reorder — integrates with existing `@dnd-kit` and `zustand`; no styling conflicts with Tailwind
- `@tanstack/react-virtual`: Row virtualization for 1000+ rows — same ecosystem, composable with TanStack Table column virtualization for the 86-column Tovar view
- `react-hook-form` + `zod@3.25.x`: Form state and per-field validation for 40+ field detail panel; shadcn Form component is built on this; pin zod to 3.25.x (known zodResolver bug with zod 4.x and @hookform/resolvers 5.2.x)
- `shadcn Sheet (side="right")`: Detail panel overlay — Notion/Linear pattern; no persistent split pane needed for v1; add `react-resizable-panels` only if power-user toggle is requested
- Do NOT enable React Compiler — breaks TanStack Table re-renders (GitHub issue #5567)

### Expected Features

**Must have (v1 — "replaces Google Sheets"):**
- All field display names correct — zero technical names shown to user (S, pure frontend mapping)
- Reference fields show resolved values in table — `kategoriya_name` not "—" (S, backend already provides `_name` fields, column key mapping bug)
- All fields visible in DetailPanel in read mode — section-grouped, all 22 ModelOsnova fields, all Artikul and Tovar fields (M)
- DetailPanel edit mode — field-type-aware inputs (text, number, select with loaded lookup options) with explicit Save/Cancel (M)
- Lookup options pre-fetched at entity page mount and cached — kategorii, kollekcii, fabriki, statusy, razmery, cveta (S-M)
- Create new record — "+ New" in topbar opens creation panel reusing DetailPanel edit form components (M, depends on edit panel)
- Status filter — active vs archived, critical for daily use (S)
- Sort by column header click (S)
- Status badge display — colored badge not plain text (S)
- Read-only protection for system IDs — barkod, nomenklatura_wb, ozon_product_id (S)

**Should have (v1.x — "better than Google Sheets"):**
- Hierarchy drill-down in sidebar — click ModelOsnova to see its Artikuly (M, implemented as a special case of the filter system)
- Related counts as clickable links in DetailPanel — navigate to filtered child list (S)
- Column visibility toggle — show/hide columns, persists to localStorage (S)
- Saved views wired in UI — backend exists, wire filter+sort+columns into ViewConfig (M)
- Working stock tab columns in table — batch fetch pattern (M, solves first; finance follows same pattern)
- Working finance tab columns in table (M, after stock pattern proven)
- Keyboard navigation in DetailPanel — Tab/Enter/Escape (S)

**Defer (v2+):**
- Inherited field display (parent context in child detail panel)
- Status-based row coloring
- Per-entity full-text search bar
- Export to CSV
- Certificates entity integration

**Anti-features (do not build):**
- Inline editing for all 90+ fields — data validation nightmare, unclear save states
- Real-time collaborative editing — design spec non-goal
- Undo/redo in table — high cost, low value; archive/restore covers the "oops" case
- Drag-and-drop row reordering — no natural user-defined sort order for 1450 rows
- Bulk import from Excel/CSV — one-time migration, not a recurring UX feature
- Gallery/Kanban view, formula fields, notifications/activity feed

### Architecture Approach

The architecture is an entity-page-as-thin-adapter pattern: each `*-page.tsx` reads from `matrix-store`, builds list params via `filter-utils.ts`, and passes data + columns to `DataTable`. Business logic lives in stores and utilities, not in page components. The critical new additions are `fields-store.ts` (Zustand store caching `FieldDefinition[]` per entity with TTL), `use-entity-detail.ts` (hook centralizing all entity-type dispatch), and a single `entity-registry.ts` (replacing 4 out-of-sync entity key maps). State management stays Zustand — do not introduce TanStack Query for this milestone.

**Major components and their modifications:**
1. `entity-registry.ts` (NEW) — single authoritative mapping of `MatrixEntity` to apiPath / schemaType / dbKey; all 4 current parallel maps derived from this
2. `fields-store.ts` (NEW) — Zustand store with `FieldDefinition[]` per entity, deduplicating fetches across ManageFieldsDialog, column headers, DetailPanel, and FilterBuilder
3. `use-entity-detail.ts` (NEW) — hook encapsulating entity-type dispatch; `DetailPanel` uses this instead of hardcoded `matrixApi.getModel()`
4. `filter-utils.ts` (NEW) — pure utility: `buildListParams(filters, sort) → Record<string, ...>`; `FilterRule` and `SortConfig` types defined here
5. `filter_service.py` (NEW, backend) — maps FilterRule[] encoded as query params to SQLAlchemy WHERE clauses
6. `DetailPanel` (MODIFY) — entity-type-aware via `useEntityDetail` hook; all fields section-grouped; edit mode with react-hook-form; explicit Save/Cancel
7. `matrix-store.ts` (MODIFY) — add `activeFilters: FilterRule[]`, `sortConfig: SortConfig[]`, `columnWidths: Record<string, number>`
8. `DataTable` + `column-header.tsx` (MODIFY/NEW) — sort indicators, column resize via TanStack Table built-in `getResizeHandler()`, TanStack Virtual for large datasets

### Critical Pitfalls

1. **DetailPanel hardcoded to `models` entity** — change `MatrixState.detailPanelId` from `number | null` to `{ id: number; entity: MatrixEntity } | null` before writing any edit logic; add generic `updateEntity(entity, id, data)` dispatcher to matrixApi. Address in Phase 1 before any other work.

2. **Entity key mapping fragmentation (4 out-of-sync maps)** — create `src/config/entity-registry.ts` as the single source of truth; replace `ENTITY_TYPE_MAP` in ManageFieldsDialog, `ENTITY_TO_DB` in MassEditBar, `FIELD_DEF_ENTITY_MAP` in InfoTab, and the map in views-store with imports from entity-registry. Address in Phase 1.

3. **Stale table rows after panel edit** — no shared server-state cache means panel saves are not reflected in the table. Add `entityCache: Map<string, Record<string, unknown>>` slice to matrix-store keyed by `"{entity}:{id}"`; panel `onSave` updates cache; table reads from cache. Address in Phase 1 before edit UI ships.

4. **N+1 lookup fetches on panel open** — pre-fetch and cache all lookup tables for the active entity when the entity page mounts (not when the panel opens); cache in `lookupsCache` Zustand slice with 5-min TTL. Address in Phase 2 before any FK-editable field is added.

5. **Virtual scroll breaks on expand/collapse** — TanStack Virtual does not auto-remeasure parent rows when children expand. Model as a flat item array (one item per row, parent + children flattened); recalculate full array when `expandedRows` changes. Set `overscan: 5` to smooth stutter from GitHub issue #659. Address in Phase 3.

6. **No validation before PATCH** — inline cell edit fires PATCH immediately on blur with no validation; structured fields (TNVED 10-digit codes, barcodes, INN) will silently save bad data. Add `validate(fieldType, value)` per FieldDefinition type on frontend; add Pydantic `field_validator` constraints on backend for known formats. Address in Phase 2.

## Implications for Roadmap

Based on combined research, the natural phase structure is:

### Phase 1: Foundation and Structural Fixes
**Rationale:** Architecture research identifies 4 active time bombs that corrupt data or produce silent bugs if not fixed before any editing logic is added. Feature research confirms these are blocking dependencies. Nothing else can be safely built until these are resolved.
**Delivers:** A structurally sound codebase where adding any feature touches exactly the right file; entity registry is the single source of truth; panel routing is correct; filter/sort/cache state is defined.
**Addresses:** Entity key map fragmentation (Pitfall 10), DetailPanel entity hardcoding (Pitfall 1), stale table data after edit (Pitfall 2), concurrent inline+panel edit conflict (Pitfall 3).
**Creates:**
- `entity-registry.ts` — single entity map, all 4 existing maps replaced
- `fields-store.ts` — Zustand store for FieldDefinition[] per entity
- `use-entity-detail.ts` — centralizes entity dispatch
- `filter-utils.ts` — FilterRule, SortConfig types + buildListParams utility
- `matrix-store.ts` extended — activeFilters, sortConfig, columnWidths, entityCache
- `detailPanelId` type changed to `{ id, entity } | null`

### Phase 2: Field Rendering and DetailPanel Edit Mode
**Rationale:** Features research shows the most user-blocking gap is the non-functional detail panel. FEATURES.md marks these as P1 must-haves. Pitfalls 4, 7, 8, 9 all target field rendering — they must be addressed here before anything ships.
**Delivers:** A usable detail panel: all fields visible, section-grouped, editable with correct input types, validated before save, with computed vs editable fields visually distinct. Lookup options pre-cached. Create new record flow.
**Addresses:** All fields visible in DetailPanel, DetailPanel edit mode, lookup caching (Pitfall 4), field permission visibility (Pitfall 7), mixed editability UX (Pitfall 8), validation before PATCH (Pitfall 9).
**Uses:** react-hook-form + zod@3.25.x + @hookform/resolvers, shadcn Sheet/Form/Select/Badge, fields-store, use-entity-detail hook.

### Phase 3: Table View Completeness
**Rationale:** With the detail panel functional, table-level display bugs become the next bottleneck. These are largely independent of each other and fast to ship (mostly S-complexity fixes). Sort and filter are inter-dependent (same URL param wiring pattern) so they ship together.
**Delivers:** Table shows correct display names, resolved reference fields, colored status badges, working sort, status filter. "+ New" button wired to creation form.
**Addresses:** Display names, reference field resolution, status badge, sort by column, status filter, read-only system field protection.
**Uses:** TanStack Table `getSortedRowModel()`, `getFilteredRowModel()`; shadcn Badge/Checkbox/Tooltip; filter-utils.ts, matrix-store filter slice.

### Phase 4: Filter System (Full)
**Rationale:** Status filter from Phase 3 uses the same infrastructure. Full filter system (filter bar with chips, filter builder popover, backend filter_service.py, saved view persistence) ships here once the pattern is proven. Hierarchy drill-down in the sidebar is implemented as a special case of filters.
**Delivers:** Multi-field filter bar, active filter chips, filter builder UI, backend filter support for models/articles/products, saved views serialize filter+sort state, hierarchy drill-down in sidebar.
**Uses:** filter-bar.tsx (NEW), filter-builder.tsx (NEW), filter_service.py (NEW), views-store extended.
**Avoids:** URL search params for filter state — keep in Zustand only; URL sync is a future milestone.

### Phase 5: Performance and External Data
**Rationale:** These features are correctness-optional for v1 but become blocking once catalog grows. Virtual scroll and pagination address the `per_page: 200` cliff. Stock/finance tab columns require the same unsolved batch fetch pattern — solve once for stock, then finance follows.
**Delivers:** TanStack Virtual with flat-array expand/collapse model, server-side pagination, working stock columns in table, working finance columns in table.
**Addresses:** Pitfall 5 (virtual scroll + expand/collapse), Pitfall 6 (per_page: 200 at scale).
**Note:** Stock and finance batch fetch are explicitly flagged in FEATURES.md as "do not attempt simultaneously" — build stock first, finance second.

### Phase Ordering Rationale

- Phase 1 must precede all others because 4 architectural issues produce data corruption or silent bugs the moment any edit feature is added.
- Phase 2 (DetailPanel edit) enables Phase 3 (Create new record), which reuses the same form components — this dependency is explicit in FEATURES.md.
- Phase 3 (basic sort + status filter) proves the URL param wiring pattern before Phase 4 scales it to a full filter system.
- Phase 5 (performance) is explicitly deferred because `per_page: 200` works for current catalog size; virtual scroll adds complexity that should not block the v1 launch.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (Virtual scroll + external data):** TanStack Virtual with expand/collapse has documented open issues (GitHub #659, #832). Flat-array model is the correct approach but needs careful specification of how expanded children integrate with pagination. External data batch fetch pattern for stock/finance needs API design before implementation.
- **Phase 4 (Backend filter_service.py):** SQLAlchemy dynamic WHERE clause construction for the full filter operator set (eq/neq/contains/gt/lt/is_empty/is_not_empty) across 9 entity types should be specified before implementation to avoid partial rewrites.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Pure refactoring with known targets — no unknowns.
- **Phase 2:** react-hook-form + zod + shadcn Sheet/Form is a well-documented pattern; shadcn official examples cover it completely.
- **Phase 3:** Table display fixes and basic sort/filter are straightforward TanStack Table patterns with official examples.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from npm registry; official TanStack + shadcn integration patterns verified; zod pinning decision backed by specific GitHub issues |
| Features | HIGH | Based on direct codebase inspection + existing design specs + known gaps identified by diff against spec |
| Architecture | HIGH | Direct codebase analysis; all component files read; existing patterns confirmed; no speculation |
| Pitfalls | HIGH | 7 of 10 pitfalls identified from direct source code reading; 3 verified against external sources (TanStack Virtual GitHub issues, FastAPI PATCH patterns, accessibility research) |

**Overall confidence:** HIGH

### Gaps to Address

- **Zod 4 / @hookform/resolvers compatibility:** Pin to zod@3.25.x for this milestone. Re-evaluate when @hookform/resolvers >= 5.3 ships confirmed fix for issues #12816 and #13047. This is tracked but not blocking.
- **Stock/finance batch fetch API design:** Neither the list endpoints nor a dedicated batch endpoint currently returns external data for multiple rows. A design decision (add fields to list endpoint vs new batch endpoint) must be made before Phase 5 begins. Recommend: add dedicated `GET /api/matrix/{entity}/stock-batch?ids=...` endpoint to avoid polluting list response schema.
- **`is_editable` field on FieldDefinition:** Pitfall 8 requires a backend schema change (add `is_editable: bool` to `FieldDefinition`) to distinguish computed `_name` fields from user-editable fields. This is a Phase 2 prerequisite — confirm backend change is in scope.
- **Panel layout on 13" laptops:** Overlay Sheet reduces visible table columns to zero when open. If user testing reveals this is disorienting, `react-resizable-panels` (already flagged as optional in STACK.md) should be added as a persistent side panel toggle. Defer decision to after first user session.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `wookiee-hub/src/components/matrix/`, `wookiee-hub/src/stores/`, `wookiee-hub/src/lib/`, `services/product_matrix_api/` — architecture, pitfalls
- `docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md` — feature completeness assessment
- `docs/superpowers/specs/2026-03-21-product-matrix-phase6-design.md` — external data integration spec
- npm registry verified 2026-03-22: @tanstack/react-table@8.21.3, @tanstack/react-virtual@3.13.23, react-hook-form@7.72.0, zod@4.3.6 (pinning to 3.25.x), @hookform/resolvers@5.2.2
- TanStack Table v8 official docs: `tanstack.com/table/v8/docs/`
- TanStack Virtual v3 official docs: `tanstack.com/virtual/latest`
- shadcn/ui official docs: `ui.shadcn.com/docs/`

### Secondary (MEDIUM confidence)
- TanStack Virtual GitHub issues #659, #832, #376 — dynamic height stutter with expand/collapse
- GitHub react-hook-form #12816, #13047 + colinhacks/zod #4989 — zod 4 + zodResolver compatibility
- Notion database UI / Airtable grid view / Akeneo PIM — feature comparison patterns

### Tertiary (LOW confidence)
- `simple-table.com/blog/tanstack-table-vs-ag-grid-comparison` — AG Grid vs TanStack comparison (independent blog, no official affiliation)

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
