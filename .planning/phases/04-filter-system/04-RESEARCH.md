# Phase 4: Filter System - Research

**Researched:** 2026-03-27
**Domain:** React state management, FastAPI query parameter filtering, Zustand persist, shadcn Popover/Select, SQLAlchemy IN-clause filtering
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Filter Bar UX:**
- Filters live in the existing `MatrixTopbar` component
- Layout: `[Создать] [+Фильтр] [chip][chip][chip]...  [Поля]`
- `[+Фильтр]` button opens a popover: field list → select field → select value(s) → chip appears
- Filter chips inline in the same toolbar row, format: `[Категория: Бельё ×]`
- Wrap behavior: `flex-wrap` when many chips
- No separate filter bar line, no sliding panel

**Hierarchy Navigation (Drill-down):**
- Auto-switch entity tab with preset filter
- Flow: Click model row → switch to "Артикулы" tab → auto-apply filter chip `[Модель: KOD-123 ×]`
- Return: Remove chip to see all articles, or click "Модели" tab
- No breadcrumb — filter chips provide context
- Existing expand-in-place (chevron → children rows) stays as-is
- Need `onDrillDown(entityType, filterField, filterValue)` handler that:
  1. Sets `activeEntity` to target tab
  2. Adds filter to active filters state

**Filter Builder Complexity:**
- Only `=` (equals) operator
- Lookup fields (kategoriya_id, fabrika_id, kollekciya_id): select from dropdown
- Text fields: `contains` semantics under the hood
- No range operators, no >, <, no is_empty
- Multi-select within one filter (OR logic): combobox with checkboxes for lookup fields
- Chip display: `[Категория: Бельё, Полотенца ×]`
- Backend: `kategoriya_id IN (1, 5)` query
- Filter logic between different fields = AND

**Status & Saved Views:**
- Add `status_id INT REFERENCES statusy(id)` to `modeli_osnova` via migration
- Each entity level has its OWN independent status — no inheritance
- Saved views: save everything — filters + sort + hidden columns
- Storage: localStorage via Zustand `persist`
- Reuse existing `views-store.ts` with `{ columns, filters, sort }` config
- No backend API needed for views storage (FILT-05 conflicts with REQUIREMENTS.md — see Open Questions)

### Claude's Discretion

- Which shadcn component to use for filter value picker (Popover + Command vs Select)
- Exact state shape for active filters in Zustand
- Whether `useTableState` hook is extended or a new `useMatrixFilters` hook is created
- Multi-step popover UX: whether field selection and value selection are in the same popover step or two separate steps

### Deferred Ideas (OUT OF SCOPE)
- Range operators (>, <, between) for numeric fields
- Backend-stored views with team sharing
- Cross-entity filter propagation (filter models → auto-filter articles)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FILT-01 | Фильтр по статусу (активные/архивные) в виде dropdown над таблицей | Status dropdown in MatrixTopbar; backend already accepts `status_id` on articles/products; modeli_osnova needs migration to add `status_id` |
| FILT-02 | Фильтр по категории для моделей | `kategoriya_id` already accepted by `list_models_osnova`; frontend needs chip UI wired to that param |
| FILT-03 | Hierarchy drill-down — клик по модели → показ её артикулов в отфильтрованном виде | `onDrillDown` handler sets `activeEntity + adds filter`; articles route already accepts `model_id` param |
| FILT-04 | Multi-field filter builder с поддержкой нескольких фильтров одновременно | New `FilterPopover` component + `activeFilters` state; CrudService `_build_filters` needs IN-clause support for multi-select |
| FILT-05 | Saved views UI — сохранение и загрузка конфигурации колонок и фильтров через backend hub.saved_views | Backend `hub.saved_views` table + `/api/matrix/views` CRUD already fully implemented; `views-store.ts` already calls the API; need to wire filters+sort into `SavedViewDialog` and add "load view" action |
</phase_requirements>

---

## Summary

Phase 4 adds filtering, hierarchy drill-down, and saved views to the Product Matrix table. The good news: the backend is already 80% ready. `list_models_osnova` accepts `kategoriya_id` and `kollekciya_id`. `list_articles` accepts `model_id`, `cvet_id`, and `status_id`. The `CrudService._build_filters` already converts a `{field: value}` dict into SQLAlchemy WHERE conditions. The `hub.saved_views` table and its full CRUD API (`/api/matrix/views`) are already implemented. The `views-store.ts` on the frontend already calls `matrixApi.createView` / `listViews`.

The work in this phase is primarily frontend: building the `FilterPopover` component (Notion/Linear-style), extending `MatrixTopbar` to show filter chips, adding `activeFilters` state to `useMatrixStore` or extending `useTableState`, wiring active filters into API call params, implementing the drill-down handler, and updating `SaveViewDialog` to capture filters + sort (not just columns). On the backend, two targeted changes are needed: add `status_id` to `modeli_osnova` via a migration, and extend `CrudService._build_filters` to handle list values (`IN` clauses) for multi-select.

**Primary recommendation:** Extend `useTableState` to include `activeFilters: FilterEntry[]` + `addFilter/removeFilter/clearFilters` actions, add a `useMatrixFilters` hook that converts active filters to API params, and build a single reusable `FilterPopover` component that drives all entity filter pickers.

---

## Standard Stack

### Core (already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| zustand | ^5.0.0 | Active filter state + persist for saved views | Already used for all matrix state |
| @radix-ui/react-popover | ^1.0.0 | Filter builder popover trigger/content | Already used for `ColumnVisibilityPopover` |
| @radix-ui/react-select | ^2.0.0 | Status/category simple dropdowns | Already in project |
| lucide-react | ^0.400.0 | Icons (Filter, X, ChevronDown) | Already used throughout |
| tailwindcss | ^4.0.0 | Styling filter chips + popover content | Already used |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cmdk | ^1.0.0 | Command palette for searchable field list in FilterPopover | Already in project; use for the field selection step inside the popover |

### Already-in-place backend

| Component | Location | Status |
|-----------|----------|--------|
| `CrudService.get_list(filters=dict)` | `services/product_matrix_api/services/crud.py` | EXISTS — equality filters only, needs IN-clause extension |
| `list_models_osnova` route | `routes/models.py` | EXISTS — accepts `kategoriya_id`, `kollekciya_id` |
| `list_articles` route | `routes/articles.py` | EXISTS — accepts `model_id`, `cvet_id`, `status_id` |
| `hub.saved_views` table + CRUD | `routes/views.py`, `models/database.py` | FULLY EXISTS |
| `statusy` lookup table | `sku_database/database/models.py` | EXISTS — 7 statuses |

### Installation

No new packages needed. Everything required is already in `wookiee-hub/package.json`.

---

## Architecture Patterns

### Recommended Project Structure Changes

```
wookiee-hub/src/
├── components/matrix/
│   ├── filter-popover.tsx        # NEW: [+Фильтр] button + field/value picker
│   ├── filter-chip.tsx           # NEW: removable chip [Категория: Бельё ×]
│   ├── matrix-topbar.tsx         # EXTEND: accept activeFilters + filter actions
│   ├── save-view-dialog.tsx      # EXTEND: pass filters + sort into saved config
│   └── view-tabs.tsx             # EXTEND: "load saved view" applies filters
├── hooks/
│   └── use-table-state.ts        # EXTEND: add activeFilters state + helpers
├── stores/
│   ├── matrix-store.ts           # ADD: activeFilters + drillDown action
│   └── views-store.ts            # ALREADY EXISTS — addView already accepts config
services/product_matrix_api/
├── services/crud.py              # EXTEND: _build_filters handles list → IN clause
├── models/schemas.py             # EXTEND: ModelOsnovaRead + ModelOsnovaCreate add status_id
└── routes/models.py              # EXTEND: list_models_osnova accepts status_id, fabrika_id
sku_database/database/migrations/
└── 004_add_status_id_modeli_osnova.py  # NEW: ALTER TABLE modeli_osnova ADD COLUMN status_id
```

### Pattern 1: Active Filters State Shape

**What:** A typed `FilterEntry` represents one active filter. Multiple entries are AND-ed; multiple values within one entry are OR-ed (IN clause).
**When to use:** Any component that reads or writes active filters.

```typescript
// In stores/matrix-store.ts (or use-table-state.ts extension)
export interface FilterEntry {
  field: string          // e.g. "kategoriya_id"
  label: string          // e.g. "Категория"
  values: number[]       // IDs for lookup fields; OR semantics within field
  valueLabels: string[]  // e.g. ["Бельё", "Полотенца"] for chip display
}

// In MatrixState, add:
activeFilters: FilterEntry[]
addFilter: (entry: FilterEntry) => void
removeFilter: (field: string) => void
clearFilters: () => void
drillDown: (entity: MatrixEntity, field: string, value: number, valueLabel: string) => void
```

### Pattern 2: Filter → API Params Conversion

**What:** Convert `FilterEntry[]` to flat query params that the backend accepts.
**When to use:** In `useTableState.apiParams` computation.

```typescript
// In use-table-state.ts (or a useMatrixFilters hook)
function filtersToParams(filters: FilterEntry[]): Record<string, string | number> {
  const params: Record<string, string | number> = {}
  for (const f of filters) {
    if (f.values.length === 1) {
      params[f.field] = f.values[0]
    } else if (f.values.length > 1) {
      // Backend must accept repeated params or comma-joined list
      // Recommended: comma-joined → backend splits on comma
      params[f.field] = f.values.join(",")
    }
  }
  return params
}
```

**Note:** The current backend uses `field == value` equality only. Multi-select requires the backend `_build_filters` to handle list values. See Backend Changes below.

### Pattern 3: FilterPopover — Two-Step Flow

**What:** Single popover with two states — field picker, then value picker.
**When to use:** When user clicks `[+Фильтр]`.

```
Step 1: Show field list (use cmdk Command for searchable list)
        → User selects "Категория"
Step 2: Show value picker for that field
        - Lookup fields: multi-select checkboxes (like ColumnVisibilityPopover)
        - Text fields: text input with "содержит" label
        → User selects values → chip appears → popover closes
```

Implementation: Use a single `Popover` with internal `step: "field" | "value"` state. Reset to "field" after chip is added.

### Pattern 4: Drill-Down Handler

**What:** Clicking a model row's "drill-down" action switches entity tab and pre-applies a filter.
**When to use:** Model row chevron → Артикулы; or DetailPanel related-entities link.

```typescript
// In matrix-store.ts
drillDown: (entity: MatrixEntity, field: string, value: number, valueLabel: string) => {
  set((s) => ({
    activeEntity: entity,
    activeFilters: [
      {
        field,
        label: LOOKUP_LABEL_MAP[field] ?? field,
        values: [value],
        valueLabels: [valueLabel],
      },
    ],
  }))
}

// Usage from ModelsPage row click / detail panel:
drillDown("articles", "model_id", row.id, row.kod)
```

### Pattern 5: Saved View with Filters

**What:** Extend `addView` to save filters + sort, not just columns.
**When to use:** When user clicks "Сохранить вид".

The existing `ViewConfig` type in `matrix-api.ts` already has the right shape:
```typescript
export interface ViewConfig {
  columns: string[]
  filters: Array<{ field: string; op: string; value: unknown }>
  sort: Array<{ field: string; dir: string }>
}
```
Map `FilterEntry[]` → `ViewConfig.filters` on save. Map `ViewConfig.filters` → `FilterEntry[]` on load.

The `views-store.ts` `addView` signature currently only passes `columns`. It must be extended:
```typescript
addView: async (entity, name, columns, filters, sort) => { ... }
```

### Anti-Patterns to Avoid

- **Storing filter state in URL params:** CONTEXT.md decision — filter state lives in Zustand only, no URL sync.
- **Per-page component filter state:** Filters must live in `matrix-store` or a shared hook so the drill-down action from ModelDetail can set article filters without prop drilling.
- **Calling lookup tables on every FilterPopover open:** Cache is already in `lookupCache` in `matrix-store`. Use that, don't re-fetch.
- **Rebuilding filter params in each page component:** Centralize in `useTableState` or a `useMatrixFilters` hook.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Searchable dropdown for field list | Custom input+list | `cmdk` Command component | Already in project; handles keyboard nav, fuzzy search |
| Multi-select combobox with checkboxes | Custom | Radix Popover + internal checkbox list (same pattern as `ColumnVisibilityPopover`) | Already proven in project |
| localStorage persistence | Custom storage | Zustand `persist` middleware | Already used in `filters.ts` — handles serialization |
| Filter chip removal | Custom event bus | Direct Zustand `removeFilter(field)` call | Store is accessible everywhere |

**Key insight:** The `ColumnVisibilityPopover` is the template for the value picker step in FilterPopover — it already does multi-select checkboxes with sections in a Radix Popover.

---

## Common Pitfalls

### Pitfall 1: modeli_osnova has no status_id yet

**What goes wrong:** FILT-01 requires filtering models by status. The `modeli_osnova` table does NOT have a `status_id` column yet (confirmed by reading the ORM model and schema). The `ModelOsnovaRead` schema in `schemas.py` also has no `status_id` field.

**Why it happens:** `modeli` (child variations) has `status_id`, but `modeli_osnova` (base models) was never given one.

**How to avoid:**
1. Write migration: `ALTER TABLE modeli_osnova ADD COLUMN status_id INTEGER REFERENCES statusy(id);`
2. Add `status_id: Optional[int] = None` to `ModelOsnovaCreate`, `ModelOsnovaUpdate`, `ModelOsnovaRead`
3. Add `status_id` to `list_models_osnova` route query params
4. Add `status_name: Optional[str] = None` to `ModelOsnovaRead` (resolve in route via join or subquery)

**Warning signs:** If `status_id` filter on models returns empty results or 422, check whether the column exists and whether the route accepts the param.

### Pitfall 2: CrudService._build_filters only handles scalar equality

**What goes wrong:** Multi-select filter sends `kategoriya_id = [1, 5]`. The current `_build_filters` does `model.field == value` which fails for lists.

**Why it happens:** `_build_filters` was written for simple equality filters. The multi-select requirement in CONTEXT.md needs `IN` semantics.

**How to avoid:** Extend `_build_filters` to detect list values and use SQLAlchemy `in_()`:
```python
if isinstance(value, list):
    conditions.append(getattr(model, field).in_(value))
else:
    conditions.append(getattr(model, field) == value)
```

**Warning signs:** Empty table when multiple values selected; no error thrown because list silently coerces.

### Pitfall 3: activeFilters must reset on entity tab switch (except for drill-down)

**What goes wrong:** User applies `kategoriya_id = 3` on Models tab, then clicks "Артикулы". Category filter persists but makes no sense for articles — resulting in no data or wrong data.

**Why it happens:** Zustand store persists across entity tab switches.

**How to avoid:** In `setActiveEntity`, clear `activeFilters` unless the switch came from a `drillDown` action. Simplest: add a `drillDownPending` flag that `drillDown()` sets, and `setActiveEntity` reads before clearing.

**Warning signs:** Articles page loads with a filter chip that says "Категория" but articles have no category field.

### Pitfall 4: FILT-05 storage conflict — localStorage vs backend API

**What goes wrong:** REQUIREMENTS.md says FILT-05 uses "backend hub.saved_views". CONTEXT.md says "No backend API needed for views storage / localStorage via Zustand persist". The backend API already exists and `views-store.ts` already calls it.

**Why it happens:** CONTEXT.md was written with a simplification in mind, but the backend is already built.

**How to avoid:** Use the backend API (`views-store.ts` + `/api/matrix/views`) — it already works. The CONTEXT.md "localStorage" note likely referred to not needing a NEW backend API (since it already existed). The `SaveViewDialog` already calls `addView` which calls `matrixApi.createView`. The gap is wiring filters + sort into the config payload, and adding a "load view" UI that restores those values.

**Warning signs:** Views saved but only columns restored on load; filters and sort silently ignored.

### Pitfall 5: Filter popover z-index under sticky header

**What goes wrong:** The filter popover content renders behind the sticky table header.

**Why it happens:** Radix Popover portals to `document.body` by default but CSS stacking context can interfere.

**How to avoid:** Ensure the popover `ContentProps` uses default portal behavior (Radix handles this); don't nest the popover inside a CSS `transform` parent. Verify with a real browser test.

### Pitfall 6: drill-down from ModelsPage — model_id vs model_osnova_id

**What goes wrong:** Drilling down from a `modeli_osnova` row needs to filter articles by the model hierarchy. Articles (`artikuly`) link to `modeli` (child variations) via `model_id`, not to `modeli_osnova` directly.

**Why it happens:** The entity hierarchy is: `modeli_osnova` → `modeli` (variations) → `artikuly`.

**How to avoid:**
- Option A: Filter articles by `model_id IN (ids of all modeli for this osnova)` — requires a pre-fetch.
- Option B: Drill-down from a `modeli` row (child variation), not from `modeli_osnova`.
- Option C: Add a `model_osnova_id` filter to the articles backend route that does the join server-side.

**Recommendation:** Option C is cleanest. Add `model_osnova_id: Optional[int] = Query(None)` to `list_articles` that filters via JOIN: `Artikul.model_id IN (SELECT id FROM modeli WHERE model_osnova_id = :id)`.

---

## Code Examples

### Backend: Extend _build_filters for IN clauses

```python
# services/product_matrix_api/services/crud.py
@staticmethod
def _build_filters(model: Type[T], filters: dict[str, Any]) -> list:
    conditions = []
    mapper = inspect(model) if hasattr(model, "__mapper__") else None
    if not mapper:
        return conditions
    col_names = {c.key for c in mapper.column_attrs}
    for field, value in filters.items():
        if field in col_names and value is not None:
            if isinstance(value, list):
                if value:  # non-empty list
                    conditions.append(getattr(model, field).in_(value))
            else:
                conditions.append(getattr(model, field) == value)
    return conditions
```

### Backend: Migration for modeli_osnova.status_id

```python
# sku_database/database/migrations/004_add_status_id_modeli_osnova.py
"""Add status_id to modeli_osnova table."""

def upgrade(conn):
    conn.execute("""
        ALTER TABLE modeli_osnova
        ADD COLUMN IF NOT EXISTS status_id INTEGER REFERENCES statusy(id);
    """)

def downgrade(conn):
    conn.execute("""
        ALTER TABLE modeli_osnova
        DROP COLUMN IF EXISTS status_id;
    """)
```

### Backend: Extend list_models_osnova route

```python
# routes/models.py — add status_id + fabrika_id params
@router.get("", response_model=PaginatedResponse)
def list_models_osnova(
    params: CommonQueryParams = Depends(common_params),
    kategoriya_id: Optional[int] = Query(None),
    kollekciya_id: Optional[int] = Query(None),
    fabrika_id: Optional[int] = Query(None),         # NEW
    status_id: Optional[int] = Query(None),           # NEW
    db: Session = Depends(get_db),
):
    filters = {}
    if kategoriya_id: filters["kategoriya_id"] = kategoriya_id
    if kollekciya_id: filters["kollekciya_id"] = kollekciya_id
    if fabrika_id: filters["fabrika_id"] = fabrika_id   # NEW
    if status_id: filters["status_id"] = status_id       # NEW
    ...
```

### Frontend: FilterEntry type and activeFilters in matrix-store

```typescript
// stores/matrix-store.ts additions
export interface FilterEntry {
  field: string
  label: string
  values: number[]       // for lookup fields
  valueLabels: string[]  // human-readable labels for chip
}

// Add to MatrixState:
activeFilters: FilterEntry[]
addFilter: (entry: FilterEntry) => void
removeFilter: (field: string) => void
clearFilters: () => void
drillDown: (entity: MatrixEntity, field: string, value: number, valueLabel: string) => void
```

### Frontend: FilterChip component

```tsx
// components/matrix/filter-chip.tsx
interface FilterChipProps {
  label: string
  values: string[]
  onRemove: () => void
}

export function FilterChip({ label, values, onRemove }: FilterChipProps) {
  const display = values.length <= 2
    ? values.join(", ")
    : `${values[0]}, +${values.length - 1}`

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs text-primary">
      <span className="font-medium">{label}:</span>
      <span>{display}</span>
      <button onClick={onRemove} className="ml-0.5 hover:text-destructive">
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}
```

### Frontend: MatrixTopbar extended signature

```tsx
// components/matrix/matrix-topbar.tsx — new props
interface MatrixTopbarProps {
  // existing props...
  fieldDefs?: Array<...>
  hiddenFields?: Set<string>
  onToggleField?: (fieldName: string) => void
  onCreateClick?: () => void
  // NEW filter props:
  filterableDefs?: FilterableDef[]    // which fields are filterable
  activeFilters?: FilterEntry[]
  onAddFilter?: (entry: FilterEntry) => void
  onRemoveFilter?: (field: string) => void
  onSaveView?: () => void
}
```

### Frontend: Convert FilterEntry[] to API params

```typescript
// In use-table-state.ts or useMatrixFilters hook
function filtersToApiParams(filters: FilterEntry[]): Record<string, string | number> {
  const result: Record<string, string | number> = {}
  for (const f of filters) {
    if (f.values.length === 1) {
      result[f.field] = f.values[0]
    } else if (f.values.length > 1) {
      result[f.field] = f.values.join(",")
      // Backend must parse comma-joined string back to list
      // Alternative: send as repeated params if API client supports it
    }
  }
  return result
}
```

**Note on multi-value params:** The `get()` client function in `api-client.ts` needs to be verified for how it handles repeated keys or comma-joined strings. If it only supports scalar values per key, use comma-joined strings and parse on the backend.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hardcoded `kategoriya_id` param in route | Extend `_build_filters` with list support | Single backend change enables all multi-select filters |
| `SaveViewDialog` saves only `columns` | Extend to save `filters + sort + columns` | Saved views fully round-trip |
| No `activeFilters` in store | Add to `useMatrixStore` | Drill-down can set filters from any component |

---

## Open Questions

1. **FILT-05: localStorage vs backend API for saved views**
   - What we know: CONTEXT.md says "localStorage via Zustand persist". REQUIREMENTS.md says "через backend hub.saved_views". The backend API is already fully implemented.
   - What's unclear: Whether CONTEXT.md intended to replace the existing backend or simplify implementation.
   - Recommendation: Use the existing backend API — `views-store.ts` already calls it. The localStorage statement in CONTEXT.md likely meant "no NEW backend work needed". The planner should use the existing `matrixApi.createView` flow.

2. **Multi-value params encoding**
   - What we know: `api-client.ts`'s `get()` helper accepts `Record<string, string | number | undefined>` — no native array support.
   - What's unclear: Whether comma-joining works end-to-end.
   - Recommendation: Use comma-joined string (`"1,5"`) on the frontend, parse with `value.split(",").map(int)` in the route function. This is simpler than changing the API client signature.

3. **Drill-down from modeli_osnova to artikuly**
   - What we know: `artikuly.model_id` references `modeli`, not `modeli_osnova`.
   - What's unclear: Whether the MVP drill-down should target `modeli` (child variations) instead of `modeli_osnova`.
   - Recommendation: Add `model_osnova_id` filter support to `list_articles` route (subquery: `model_id IN SELECT id FROM modeli WHERE model_osnova_id = X`). This is the cleanest UX.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python), no frontend test framework detected |
| Config file | `tests/conftest.py` exists |
| Quick run command | `pytest tests/product_matrix_api/ -x -q` |
| Full suite command | `pytest tests/ -x -q --ignore=tests/integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILT-01 | `list_models_osnova` filters by `status_id` | unit | `pytest tests/product_matrix_api/test_models_filter.py -x` | Wave 0 |
| FILT-02 | `list_models_osnova` filters by `kategoriya_id` (existing) | unit | `pytest tests/product_matrix_api/test_models_filter.py::test_filter_by_kategoria -x` | Wave 0 |
| FILT-03 | Drill-down `model_osnova_id` filter on articles | unit | `pytest tests/product_matrix_api/test_articles_filter.py -x` | Wave 0 |
| FILT-04 | `_build_filters` handles list values → IN clause | unit | `pytest tests/product_matrix_api/test_crud.py::test_build_filters_in_clause -x` | Wave 0 |
| FILT-05 | SavedView config round-trip (columns + filters + sort) | unit | `pytest tests/product_matrix_api/test_views.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/product_matrix_api/ -x -q`
- **Per wave merge:** `pytest tests/product_matrix_api/ tests/product_matrix_api/test_crud.py -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/product_matrix_api/test_models_filter.py` — covers FILT-01, FILT-02
- [ ] `tests/product_matrix_api/test_articles_filter.py` — covers FILT-03
- [ ] `tests/product_matrix_api/test_views.py` — covers FILT-05 config round-trip
- [ ] `tests/product_matrix_api/test_crud.py` — extend with `test_build_filters_in_clause` for FILT-04

Frontend (React) tests are not applicable — no test framework (vitest, jest) is configured in `wookiee-hub/package.json`. Frontend behavior must be verified manually.

---

## Sources

### Primary (HIGH confidence)

- Source code audit — `services/product_matrix_api/services/crud.py` — confirmed scalar-only `_build_filters`
- Source code audit — `services/product_matrix_api/routes/models.py` — confirmed existing `kategoriya_id`, `kollekciya_id` params; missing `status_id`, `fabrika_id`
- Source code audit — `services/product_matrix_api/routes/articles.py` — confirmed existing `model_id`, `cvet_id`, `status_id` params
- Source code audit — `services/product_matrix_api/routes/views.py` — confirmed full CRUD API exists
- Source code audit — `sku_database/database/models.py` (line 175–247) — confirmed `modeli_osnova` has NO `status_id` column
- Source code audit — `wookiee-hub/src/stores/views-store.ts` — confirmed `addView` only passes `columns`, not filters/sort
- Source code audit — `wookiee-hub/src/stores/matrix-store.ts` — confirmed no `activeFilters` state exists yet
- Source code audit — `wookiee-hub/src/hooks/use-table-state.ts` — confirmed no filter state in hook
- Source code audit — `wookiee-hub/src/lib/matrix-api.ts` — confirmed `ViewConfig` type has `filters + sort + columns`

### Secondary (MEDIUM confidence)

- Zustand v5 docs — `persist` middleware supports custom storage objects (same pattern as `filters.ts` in project)
- Radix UI Popover — supports internal state management; portal behavior handles z-index

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already in the project, no new installs
- Architecture: HIGH — based on direct source code reading, not assumptions
- Pitfalls: HIGH — confirmed by reading actual ORM models and route implementations
- Backend gaps: HIGH — `modeli_osnova` confirmed missing `status_id`; `_build_filters` confirmed scalar-only

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable codebase; schema changes would invalidate)
