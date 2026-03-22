# Architecture Research

**Domain:** Notion-like table editor integrated into existing React + FastAPI product management app
**Researched:** 2026-03-22
**Confidence:** HIGH (based on direct codebase analysis)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ProductMatrixLayout (index.tsx)                      │
├──────────┬──────────────────────────────────────────────┬───────────────────┤
│          │                                              │                   │
│ Matrix   │         Main Content Area                   │   Detail Panel    │
│ Sidebar  │  ┌──────────────────────────────────────┐   │  (side panel,     │
│          │  │ MatrixTopbar                         │   │   384px wide)     │
│ Entity   │  │  [Title] [Filter] [Fields] [Search]  │   │                   │
│ type     │  └──────────────────────────────────────┘   │  ┌─────────────┐  │
│ selector │  ┌──────────────────────────────────────┐   │  │ Entity data │  │
│          │  │ ViewTabs                             │   │  │ sections    │  │
│          │  │  [Spec][Stock][Finance][Rating][+]   │   │  │ (read only  │  │
│          │  └──────────────────────────────────────┘   │  │  snapshot)  │  │
│          │  ┌──────────────────────────────────────┐   │  └─────────────┘  │
│          │  │ DataTable                            │   │                   │
│          │  │  [expand][select][col...][col...][…] │   │                   │
│          │  │  → inline cell editing               │   │                   │
│          │  │  → expandable child rows             │   │                   │
│          │  └──────────────────────────────────────┘   │                   │
│          │  MassEditBar (sticky bottom, when rows sel.) │                   │
├──────────┴──────────────────────────────────────────────┴───────────────────┤
│                      Zustand Stores (matrix-store, views-store)              │
├─────────────────────────────────────────────────────────────────────────────┤
│                   matrixApi → FastAPI /api/matrix/* endpoints                │
├─────────────────────────────────────────────────────────────────────────────┤
│                   PostgreSQL (hub schema: saved_views, field_definitions)    │
│                   + existing tables (modeli_osnova, artikuly, tovary, etc.)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `ProductMatrixLayout` | `pages/product-matrix/index.tsx` | Shell: sidebar + topbar + main + detail panel assembly |
| `MatrixSidebar` | `components/matrix/matrix-sidebar.tsx` | Entity type navigation (9 entity types) |
| `MatrixTopbar` | `components/matrix/matrix-topbar.tsx` | Title, search trigger, "Manage fields" button |
| `ViewTabs` | `components/matrix/view-tabs.tsx` | Built-in tabs (spec/stock/finance/rating) + saved views CRUD |
| `DataTable` | `components/matrix/data-table.tsx` | Generic table with expand, select, inline edit, child rows |
| `TableCell` | `components/matrix/table-cell.tsx` | Inline editor per cell (text/number/select/readonly) |
| `DetailPanel` | `components/matrix/detail-panel.tsx` | Right slide-over showing entity fields (currently models-only) |
| `MassEditBar` | `components/matrix/mass-edit-bar.tsx` | Sticky bottom bar for bulk actions on selected rows |
| `ManageFieldsDialog` | `components/matrix/manage-fields-dialog.tsx` | Create/delete custom field definitions |
| `GlobalSearch` | `components/matrix/global-search.tsx` | ⌘K modal global search across entities |
| `*Page` | `pages/product-matrix/*-page.tsx` | Per-entity data fetch + column config + DataTable wiring |
| `EntityDetailPage` | `pages/product-matrix/entity-detail-page.tsx` | Full-page entity detail with tabs (info/stock/finance/rating/tasks) |

---

## Recommended Project Structure (after milestone)

```
wookiee-hub/src/
├── components/matrix/
│   ├── data-table.tsx              MODIFY — add column resize, sticky cols, sort indicators
│   ├── table-cell.tsx              MODIFY — add date/url/checkbox/multi-select cell types
│   ├── detail-panel.tsx            MODIFY — make entity-type-aware (not models-only)
│   ├── matrix-topbar.tsx           MODIFY — add filter button, filter count badge
│   ├── manage-fields-dialog.tsx    MODIFY — add drag-to-reorder (dnd-kit already installed)
│   ├── mass-edit-bar.tsx           MODIFY — expose field-agnostic bulk-set (not hardcoded status)
│   ├── view-tabs.tsx               MINIMAL CHANGE — already handles saved views
│   ├── matrix-sidebar.tsx          NO CHANGE
│   ├── global-search.tsx           NO CHANGE
│   │
│   ├── filter-bar.tsx              NEW — active filter chips strip below topbar
│   ├── filter-builder.tsx          NEW — popover/sheet for adding/editing filter rules
│   ├── column-header.tsx           NEW — sortable, resizable column header with filter indicator
│   ├── field-type-icon.tsx         NEW — icon per field type (text/number/date/select/…)
│   │
│   └── tabs/                       NO CHANGE (info/stock/finance/rating/tasks tabs)
│
├── stores/
│   ├── matrix-store.ts             MODIFY — add filter rules array, sort config, column widths
│   ├── views-store.ts              MODIFY — persist filter+sort+column config in SavedView.config
│   └── fields-store.ts             NEW — cache FieldDefinition[] per entity, avoid re-fetching
│
├── lib/
│   ├── matrix-api.ts               MODIFY — add filter params to list* calls, add field value CRUD
│   ├── view-columns.ts             MODIFY — merge system columns + dynamic FieldDefinitions
│   └── filter-utils.ts             NEW — build query params from FilterRule[], type predicates
│
└── pages/product-matrix/
    ├── index.tsx                   MODIFY — add FilterBar between topbar and ViewTabs
    ├── models-page.tsx             MINIMAL — pass filter params to matrixApi.listModels
    ├── articles-page.tsx           MINIMAL — same pattern
    ├── products-page.tsx           MINIMAL — same pattern
    └── entity-detail-page.tsx      MODIFY — detail panel content generalised (reuse DetailPanel logic)
```

```
services/product_matrix_api/
├── routes/
│   ├── schema.py                   NO CHANGE (field CRUD complete)
│   ├── views.py                    NO CHANGE (saved views CRUD complete)
│   ├── models.py                   MODIFY — accept filter query params
│   ├── articles.py                 MODIFY — accept filter query params
│   └── products.py                 MODIFY — accept filter query params
├── models/
│   └── schemas.py                  MODIFY — add FilterParam schema, add field_values endpoint schemas
└── services/
    └── filter_service.py           NEW — parse FilterRule list → SQLAlchemy WHERE clauses
```

### Structure Rationale

- **`fields-store.ts` (new):** `FieldDefinition[]` is fetched in `ManageFieldsDialog` today with local `useState`. Multiple components (topbar, detail panel, data-table header) will need this data. A Zustand store with per-entity TTL prevents redundant API calls and keeps the definition list consistent across components.
- **`filter-utils.ts` (new):** Filter logic (building URL params, validating rule completeness) is pure utility with no React dependency. Keeping it separate from components and stores makes it testable and reusable.
- **`filter-bar.tsx` + `filter-builder.tsx` (new):** Filter UI is complex enough to warrant two components — the chip strip (always visible when filters active) and the builder popover (opened on demand). Combining them into one file creates a 400+ line component.
- **Minimal changes to `*-page.tsx` files:** Each entity page follows the same pattern (fetch with `useApiQuery`, pass to `DataTable`). Filter params should be threaded in as a single `params` object derived from `matrix-store`. No structural redesign needed.

---

## Architectural Patterns

### Pattern 1: Entity-Page-as-Thin-Adapter

**What:** Each `*-page.tsx` is a thin adapter that reads from `matrix-store`, calls `matrixApi.list*()`, and passes `data` + `columns` to `DataTable`. No business logic lives in page components.

**When to use:** For the filter feature. Do not put filter state or filter-param-building logic inside individual page files. Read filter state from `matrix-store`, build params in `filter-utils.ts`, pass to `matrixApi.list*()`.

**Trade-offs:** Pages stay small and uniform. Adding a new entity type is copy-paste of ~30 lines. Risk: over-abstraction if entity types diverge significantly in their data needs.

**Example (filter integration):**
```typescript
// Inside models-page.tsx — minimal change to support filters
const filters = useMatrixStore((s) => s.activeFilters)
const sort = useMatrixStore((s) => s.sortConfig)
const params = buildListParams(filters, sort)   // from filter-utils.ts

const { data, loading } = useApiQuery(
  () => matrixApi.listModels({ per_page: 200, ...params }),
  [params],   // re-fetch when filters/sort change
)
```

### Pattern 2: SavedView.config as Filter+Sort+Columns Envelope

**What:** `HubSavedView.config` is already a `JSON` column with shape `{ columns: string[], filters: [], sort: [] }`. The `filters` and `sort` arrays are already declared in the schema but never populated. Use them.

**When to use:** When saving a view via the "+" button in `ViewTabs`. Serialize active filter rules + sort config + visible column list into `config` on save. Restore on view selection.

**Trade-offs:** No backend schema changes needed. Filter config lives fully in JSON, so it is flexible but not queryable server-side. Acceptable for saved views (UI state only). Risky if filter rules ever need server-side validation (mitigate with frontend schema validation in `filter-utils.ts`).

**Example (ViewConfig type extension):**
```typescript
// lib/matrix-api.ts — extend ViewConfig
export interface FilterRule {
  field: string         // field_name from FieldDefinition or system column key
  operator: "eq" | "neq" | "contains" | "gt" | "lt" | "is_empty" | "is_not_empty"
  value: string | number | null
}

export interface SortConfig {
  field: string
  direction: "asc" | "desc"
}

export interface ViewConfig {
  columns: string[]
  filters: FilterRule[]
  sort: SortConfig[]
}
```

### Pattern 3: DetailPanel as Entity-Type-Aware Slot

**What:** The current `DetailPanel` is hardcoded to `matrixApi.getModel()` and renders `ModelOsnova` fields. The `EntityDetailPage` already has the generic fetch-by-entity logic. Extract the fetch dispatch into a `useEntityDetail(entityType, id)` hook and make `DetailPanel` use it.

**When to use:** When the detail panel needs to show fields for articles, products, colors, etc.

**Trade-offs:** Hook encapsulates the `switch(entity)` dispatch, keeping `DetailPanel` declarative. Downside: the hook needs to know the full list of entity types and their API calls — this is already duplicated between `entity-detail-page.tsx` and `detail-panel.tsx`. Unify it.

**Example:**
```typescript
// hooks/use-entity-detail.ts
export function useEntityDetail(entityType: MatrixEntity | null, id: number | null) {
  return useApiQuery(
    () => {
      if (!entityType || !id) return Promise.resolve(null)
      switch (entityType) {
        case "models":    return matrixApi.getModel(id)
        case "articles":  return matrixApi.getArticle(id)
        case "products":  return matrixApi.getProduct(id)
        default:          return get(`/api/matrix/${entityType}/${id}`)
      }
    },
    [entityType, id],
  )
}
```

### Pattern 4: Column Visibility via FieldDefinition Merge

**What:** `view-columns.ts` currently defines static `Column[]` arrays per entity+view. Custom `FieldDefinition` records from the backend are not shown in the table (only in `ManageFieldsDialog`). Merge them.

**When to use:** When rendering column headers. Fetch `FieldDefinition[]` from `fields-store`, filter by `is_visible: true`, map to `Column<T>` objects, append after system columns.

**Trade-offs:** Table columns become dynamic — column count changes when user adds/removes fields. `DataTable` already accepts `Column<T>[]` as props, so no changes to the table rendering logic itself. Risk: custom fields that don't exist as properties on the TypeScript type require `(row as Record<string, unknown>)[col.key]` access — this pattern is already used in `DataTable` internally.

**Hierarchy-aware visibility:** Custom fields defined for `modeli_osnova` should NOT appear in the child rows of expanded models (which are `ModelVariation` type). Use the `section` column on `FieldDefinition` to tag fields as parent-only vs child-visible. The `DataTable` already distinguishes parent vs child rows.

---

## Data Flow

### Filter Application Flow

```
User sets filter rule
    ↓
matrix-store.setFilter(rule: FilterRule)
    ↓
*-page.tsx re-renders (useMatrixStore subscription)
    ↓
buildListParams(filters, sort) → { status_id: 1, q: "...", ... }
    ↓
matrixApi.listModels({ per_page: 200, ...params })
    ↓
GET /api/matrix/models?status_id=1&...
    ↓
filter_service.py builds WHERE clause
    ↓
PaginatedResponse<ModelOsnova> returned
    ↓
DataTable re-renders with filtered rows
```

### Field Definition Flow

```
User opens ManageFieldsDialog  OR  DataTable mounts for entity
    ↓
fields-store.fetchFields(entityType)   [if TTL expired or not loaded]
    ↓
GET /api/matrix/schema/{entity_type}
    ↓
FieldDefinition[] cached in fields-store
    ↓
view-columns.ts getViewColumns() merges system cols + custom FieldDefinitions
    ↓
Column<T>[] passed to DataTable
```

### Detail Panel Flow

```
User clicks table row
    ↓
matrix-store.openDetailPanel(id)     [detailPanelId set]
    ↓
DetailPanel renders (conditional on detailPanelId !== null)
    ↓
useEntityDetail(activeEntity, detailPanelId)
    ↓
GET /api/matrix/{entity}/{id}
    ↓
Sections rendered using FieldDefinition[] from fields-store
  (system fields as static sections, custom fields as "Custom" section)
```

### Saved View Persistence Flow

```
User clicks "+" in ViewTabs → enters name
    ↓
views-store.addView(entity, name, columns)
    ↓
POST /api/matrix/views  { config: { columns, filters, sort } }
    ↓
HubSavedView persisted in hub.saved_views
    ↓
SavedView returned, added to savedViews[]
    ↓
User clicks saved view tab
    ↓
views-store loads config.filters → matrix-store.setFilters(config.filters)
views-store loads config.sort   → matrix-store.setSort(config.sort)
views-store loads config.columns → visible columns applied
```

### State Management Decision

Use **Zustand** for UI state (already in use via `matrix-store` and `views-store`). Do NOT introduce React Query or TanStack Query for this milestone — the existing `useApiQuery` hook is sufficient and consistent with the rest of the codebase.

New state to add to `matrix-store`:
```typescript
activeFilters: FilterRule[]      // current filter rules (not persisted)
sortConfig: SortConfig[]         // current sort (not persisted)
columnWidths: Record<string, number>  // user-resized column widths

setFilters: (rules: FilterRule[]) => void
addFilter: (rule: FilterRule) => void
removeFilter: (index: number) => void
setSortConfig: (sort: SortConfig[]) => void
setColumnWidth: (key: string, width: number) => void
```

Add `fields-store.ts` (new Zustand store):
```typescript
fieldsByEntity: Record<string, FieldDefinition[]>
loadingEntities: Set<string>

fetchFields: (entityType: string) => Promise<void>
getFields: (entityType: string) => FieldDefinition[]
invalidate: (entityType: string) => void
```

---

## Integration Points

### New vs Modified Components (explicit)

| Component | Status | Changes Required |
|-----------|--------|-----------------|
| `DataTable` | MODIFY | Add `sortConfig` prop, emit `onSort`, add resize handle on `column-header.tsx` |
| `TableCell` | MODIFY | Add `date`, `url`, `checkbox`, `multi_select` cell rendering branches |
| `DetailPanel` | MODIFY | Use `useEntityDetail` hook; render custom fields from `fields-store`; support all entity types |
| `MatrixTopbar` | MODIFY | Add filter button + active filter count badge; trigger `FilterBar` visibility |
| `ManageFieldsDialog` | MODIFY | Add dnd-kit drag handles for sort_order reordering (library already installed) |
| `MassEditBar` | MODIFY | Replace hardcoded status buttons with field-agnostic "Set field" dropdown |
| `index.tsx` (layout) | MODIFY | Insert `<FilterBar />` between `<MatrixTopbar />` and `<main>` |
| `matrix-store.ts` | MODIFY | Add `activeFilters`, `sortConfig`, `columnWidths` slices + actions |
| `views-store.ts` | MODIFY | On view selection, hydrate `matrix-store` filters+sort from `config` |
| `matrix-api.ts` | MODIFY | Add `filter` params to `listModels/listArticles/listProducts`; add `updateFieldValue` call |
| `view-columns.ts` | MODIFY | `getViewColumns` accepts `customFields: FieldDefinition[]`, merges them |
| `filter-bar.tsx` | NEW | Chip row showing active filter rules; remove/clear buttons |
| `filter-builder.tsx` | NEW | Popover with field selector + operator + value inputs |
| `column-header.tsx` | NEW | `<th>` content: label + sort indicator + resize handle + filter shortcut icon |
| `field-type-icon.tsx` | NEW | Small icon component mapping `FieldDefinition.field_type` to a lucide icon |
| `fields-store.ts` | NEW | Zustand store caching `FieldDefinition[]` per entity |
| `filter-utils.ts` | NEW | `buildListParams(filters, sort) → Record<string, ...>` |
| `use-entity-detail.ts` | NEW | Hook encapsulating entity-type-dispatch for detail fetch |
| `filter_service.py` (backend) | NEW | Parses filter query params → SQLAlchemy filters |
| `models.py` route | MODIFY | Accept and forward filter params to `filter_service` |
| `articles.py` route | MODIFY | Same as models |
| `products.py` route | MODIFY | Same as models |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `fields-store` ↔ `ManageFieldsDialog` | Store fetch + local mutation optimism | Dialog invalidates store on create/delete |
| `fields-store` ↔ `view-columns.ts` | Store getter called in page render | Fields must be loaded before `getViewColumns` runs |
| `matrix-store` filters ↔ `*-page.tsx` | Zustand subscription | Pages subscribe to filters slice, re-fetch on change |
| `views-store` ↔ `matrix-store` | Zustand cross-store action | On view select, `views-store` calls `matrix-store.setFilters()` |
| `DetailPanel` ↔ `matrix-store` | Reads `detailPanelId` + `activeEntity` | Panel is entity-type-aware via `activeEntity` |
| `FilterBar` ↔ `matrix-store` | Reads `activeFilters`; calls `removeFilter` | Pure display + remove, no internal state |
| `FilterBuilder` ↔ `fields-store` | Reads `getFields(activeEntity)` | Populates field selector in filter form |

---

## Suggested Build Order

Build order respects dependencies — later phases depend on earlier ones being complete.

### Phase 1: Foundation (no visible UX change)
1. **`fields-store.ts`** — Cache `FieldDefinition[]` per entity. Replace local state in `ManageFieldsDialog`.
2. **`use-entity-detail.ts`** — Extract entity-dispatch logic from `entity-detail-page.tsx`.
3. **`filter-utils.ts`** — Pure utility, zero React deps. Define `FilterRule`, `SortConfig` types here.
4. **Extend `matrix-store.ts`** — Add `activeFilters`, `sortConfig`, `columnWidths` slices.

_Why first:_ Everything else depends on these stores and types being defined. No UI changes means no risk of breaking the existing product.

### Phase 2: Backend Filter Support
5. **`filter_service.py`** — Map `FilterRule[]` encoded as query params to SQLAlchemy WHERE clauses for models/articles/products.
6. **Modify `models.py`, `articles.py`, `products.py` routes** — Accept filter query params, delegate to `filter_service`.
7. **Extend `matrix-api.ts`** — Update `listModels/listArticles/listProducts` to pass filter params.

_Why second:_ Frontend filter UI is useless without backend support. Better to build and test the backend in isolation before wiring to UI.

### Phase 3: Filter UI
8. **`filter-bar.tsx`** — Chip strip reading from `matrix-store.activeFilters`.
9. **`filter-builder.tsx`** — Popover using `fields-store` for field selector. Dispatches to `matrix-store`.
10. **Modify `matrix-topbar.tsx`** — Add filter button with badge count.
11. **Modify `index.tsx`** — Insert `<FilterBar />` between topbar and main content.
12. **Wire pages** — Each `*-page.tsx` reads filters from store, calls `buildListParams`, passes to `matrixApi`.

### Phase 4: Table UX Improvements
13. **`column-header.tsx`** — Sortable, resizable column header.
14. **Modify `DataTable`** — Accept `sortConfig` prop, emit `onSort`, use `column-header.tsx`.
15. **Modify `TableCell`** — Add `date`, `url`, `checkbox`, `multi_select` cell types.
16. **`field-type-icon.tsx`** — Icon mapping utility used by column headers and field dialogs.
17. **Modify `view-columns.ts`** — Merge custom fields into column definitions.

_Why fourth:_ Table UX improvements are independent of filter logic but depend on `fields-store` (Phase 1) being in place.

### Phase 5: Detail Panel Upgrade
18. **Modify `DetailPanel`** — Use `useEntityDetail` hook; read `fields-store` for custom field rendering; support all entity types.
19. **Modify `manage-fields-dialog.tsx`** — Add dnd-kit drag reordering for `sort_order`.
20. **Modify `MassEditBar`** — Replace hardcoded status actions with field-agnostic setter.

### Phase 6: Saved View Persistence
21. **Modify `views-store.ts`** — Serialize filters+sort into `config` on save; restore on view select.
22. **`save-view-dialog.tsx`** — Already exists; minimal change to include filter/sort preview text.

---

## Anti-Patterns

### Anti-Pattern 1: Duplicating EntityType Dispatch

**What people do:** Add another `switch(entityType)` block in `DetailPanel`, then in `FilterBuilder`, then in a new component. The dispatch already exists in `entity-detail-page.tsx`.

**Why it's wrong:** Four places need updating when a new entity type is added. Bugs appear when one is missed.

**Do this instead:** `use-entity-detail.ts` hook owns all entity-type dispatch. Every component that needs entity data calls this hook.

### Anti-Pattern 2: Entity-Type Strings Scattered Across Files

**What people do:** Use `"model_osnova"` in one file, `"modeli_osnova"` in another, `"models"` in a third (all three currently exist in the codebase — `manage-fields-dialog.tsx` uses `"model_osnova"`, `views-store.ts` uses `"modeli_osnova"`, `matrix-store.ts` uses `"models"`).

**Why it's wrong:** `ENTITY_TYPE_MAP` is duplicated with slightly different values in `manage-fields-dialog.tsx` vs `views-store.ts`. One of them is wrong (the schema backend rejects `"model_osnova"` if `VALID_ENTITY_TYPES` expects `"modeli_osnova"`).

**Do this instead:** `ENTITY_TYPE_MAP` from `views-store.ts` is authoritative. All components import from there, not define their own. The one in `manage-fields-dialog.tsx` should be removed and replaced with an import.

### Anti-Pattern 3: Inline Fetch in Dialog

**What people do:** `ManageFieldsDialog` uses local `useState + useEffect` to fetch `FieldDefinition[]`. If the dialog is opened twice, the list is fetched twice.

**Why it's wrong:** With the new `fields-store`, the same data is needed in the column headers, filter builder, and detail panel. Multiple fetches = inconsistency lag.

**Do this instead:** Replace `ManageFieldsDialog`'s local fetch with `fields-store.fetchFields(entityType)`. The store deduplicates requests.

### Anti-Pattern 4: Filter State in URL Search Params Instead of Zustand

**What people do:** Mirror filter state into URL query params for shareability, creating a two-source-of-truth situation.

**Why it's wrong:** The app currently uses no URL-based state for the matrix. Retrofitting URL sync requires careful `useSearchParams` wiring in every page, and the React Router v7 setup uses `ProductMatrixLayout` as a single nested route — all entity pages are rendered via Zustand state, not URL params.

**Do this instead:** Keep filter state in `matrix-store` (Zustand). If URL shareability is needed later, add a single sync effect at the layout level in a future milestone. Don't do it now.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (~200 rows per entity) | `per_page: 200` fetch-all works fine; no virtual scrolling needed |
| 1k+ rows per entity | Add server-side pagination with page controls; DataTable needs `onPageChange` prop |
| Complex filters (5+ rules) | Add `AND/OR` logic to `FilterRule`; backend `filter_service` needs recursive WHERE builder |
| Multiple concurrent users with saved views | `user_id` column already on `HubSavedView`; add user-scoped view visibility when auth is added |

### Scaling Priorities

1. **First bottleneck:** `per_page: 200` hardcoded in each entity page. When table grows beyond ~500 rows, perceived scroll performance degrades. Fix: add pagination or virtual scrolling to `DataTable`, controlled by `matrix-store.pagination`.
2. **Second bottleneck:** `fields-store` has no cache invalidation across browser tabs. If two users edit field definitions simultaneously, one sees stale columns. Fix: add a short TTL (e.g., 60s) or a `visibilitychange` listener to re-fetch.

---

## Sources

- Direct analysis of `wookiee-hub/src/` — HIGH confidence
- Direct analysis of `services/product_matrix_api/` — HIGH confidence
- `@dnd-kit/core` and `@dnd-kit/sortable` confirmed installed in `package.json` — HIGH confidence
- `zustand` v5.0.11 confirmed installed — HIGH confidence
- React 19 + React Router v7 confirmed — HIGH confidence

---

*Architecture research for: Notion-like table editor UX on top of existing Product Matrix*
*Researched: 2026-03-22*
