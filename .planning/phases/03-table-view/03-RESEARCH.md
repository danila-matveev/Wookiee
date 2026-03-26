# Phase 3: Table View - Research

**Researched:** 2026-03-26
**Domain:** React table refactor (FieldDef-driven columns, server sort, pagination, column toggle, create dialog) + FastAPI backend sort/pagination wiring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Columns auto-generated from backend FieldDefinitions (`is_visible=true`); `display_name` becomes header (TABLE-01)
- No more hardcoded `Column[]` arrays per entity page — single unified approach
- Reference field resolution via Zustand lookup cache (already built in Phase 2)
- `_id` fields resolved to names via `LOOKUP_TABLE_MAP` — no backend `_name` join dependency
- Lookup cache prefetched on entity switch (reuse Phase 2 prefetch pattern)
- Status badges: green "Активный", gray "Архив" (TABLE-03)
- Server-side sorting via `?sort=field&order=asc|desc` query params (TABLE-04)
- Classic pagination with page controls at bottom: « 1 2 3 ... N » (TABLE-05)
- Column visibility popover (Notion-style, checkboxes), triggered from "Настроить поля" button (TABLE-06)
- Replace current `ManageFieldsDialog` with lightweight popover
- Column list driven by FieldDefinitions
- `+ Создать` button in topbar → modal Dialog form (CRUD-01, CRUD-02)
- Create form: required/essential fields only, lookup selects for reference fields
- After creation: close dialog, refresh table, open new record in Detail Panel
- Entity-aware: form fields adapt to current entity type via FieldDefinitions
- Use `frontend-design:frontend-design` skill (ui-ux-pro-max) for all UI component design

### Claude's Discretion
- Inline table editing: remove or keep for simple fields (recommendation: remove, use Detail Panel)
- Archive row styling approach (opacity vs muted background)
- Column visibility persistence (localStorage vs Zustand-only)
- Reference cell interactivity (plain text vs subtle link)
- Pagination page size default (25 vs 50)
- Sort indicator visual design

### Deferred Ideas (OUT OF SCOPE)
- Virtual scrolling for 1000+ rows — v2 (PERF-01)
- Stock/finance data in table columns — v2 (PERF-02)
- Quick-edit hover on table cell — v2 (ADV-03)
- Breadcrumb trail in topbar — v2 (ADV-04)
- Column reorder via drag-and-drop — future enhancement
- Bulk operations (BULK-01, BULK-02)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TABLE-01 | All columns show human-readable field names (not technical) | FieldDefinition.display_name → Column.label; covered by FieldDef-driven column generation |
| TABLE-02 | Reference fields show resolved values (not "—") | Lookup cache in Zustand; `LOOKUP_TABLE_MAP` maps `_id` field → lookup table; resolved at render time |
| TABLE-03 | Status displayed as colored badge (Активный/Архив) | shadcn `Badge` component; `status_name` field from backend; green/gray variant mapping |
| TABLE-04 | Sorting via column header click (asc/desc) | Backend CrudService already handles `sort=field:desc`; frontend sends `sort` param; DataTable needs `onSort` prop |
| TABLE-05 | Pagination or "load more" (not fixed 200 rows) | `PaginatedResponse` already has `total`, `page`, `pages`; `CommonQueryParams` already has `page`/`per_page`; just wire them up |
| TABLE-06 | Column visibility toggle (show/hide without losing data) | shadcn Popover + Checkbox; visibility state in Zustand or localStorage; column list from FieldDefinitions |
| TABLE-07 | Archived rows visually dimmed (status-based row styling) | Row classname conditional on `status_name === "Архив"`; opacity-50 or muted background |
| CRUD-01 | "+ Создать" button in topbar for current entity type | shadcn Dialog triggered from MatrixTopbar button |
| CRUD-02 | Create form with required fields and lookup selects | FieldDefinitions provide field_type; `LOOKUP_TABLE_MAP` provides select options; reuse lookupCache |
</phase_requirements>

---

## Summary

Phase 3 is primarily a frontend refactoring phase with a small backend wiring task. The core backend infrastructure (paginated list endpoints, CrudService with sort support, FieldDefinition schema, lookup endpoints, create endpoints) is already complete and working. What is missing is the frontend wiring that connects this infrastructure to the table UI.

The three largest frontend changes are: (1) replacing hardcoded `Column[]` arrays in each `*-page.tsx` with FieldDef-driven column generation, (2) adding sort state and `onSort` callback to `DataTable`, and (3) replacing the `per_page: 200` fixed fetch with a paginated fetch that reads from `[page, sortField, sortOrder]` state. The create dialog (CRUD-01/02) is a new component but follows the same Dialog + Select + lookupCache pattern already established in Phase 2.

The main risk is the backend's `sort` param format. The current `CrudService.get_list` expects `sort=field:desc` (colon-separated), but the CONTEXT decisions describe `?sort=field&order=asc|desc` (two separate params). These are incompatible. One of these needs to be the canonical format — research confirms the existing backend uses colon-format, so either `CommonQueryParams` needs an `order` field added, or the frontend must encode `sort=field:asc`. The simplest path is adding an `order` param to `CommonQueryParams` and combining them in `CrudService`, keeping frontend params readable.

**Primary recommendation:** Build a `useTableState` hook that owns `[page, sortField, sortOrder, hiddenColumns]` and passes them to the list API call. All three `*-page.tsx` files become thin consumers of this hook — eliminating duplication.

---

## Standard Stack

### Core (already installed, confirmed from node_modules)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Project baseline |
| Zustand | 5.0.12 | Client state (sort, page, hidden cols) | Already used for all matrix state |
| lucide-react | 0.575.0 | Icons (sort arrows, chevrons) | Already used throughout |
| tailwindcss | 4.2.2 | Utility CSS | Project baseline |
| class-variance-authority | 0.7.1 | Variant styling for badges | Already used in shadcn components |

### shadcn Components (already present in `src/components/ui/`)

| Component | File | Use in Phase 3 |
|-----------|------|----------------|
| `Dialog` | dialog.tsx | Create record modal |
| `Popover` | popover.tsx | Column visibility toggle |
| `Checkbox` | checkbox.tsx | Column visibility checkboxes |
| `Badge` | badge.tsx | Status badge (Активный/Архив) |
| `Select` | select.tsx | Lookup selects in create form |
| `Button` | button.tsx | Sort headers, pagination controls, "+ Создать" |
| `Input` | input.tsx | Text/number fields in create form |

**No new package installs required.** All components are already present.

### Backend (FastAPI + SQLAlchemy — already built)

| Component | File | Status |
|-----------|------|--------|
| `CrudService.get_list` | services/crud.py | Ready — has sort (`field:dir` format) and pagination |
| `CommonQueryParams` | dependencies.py | Has `page`, `per_page`, `sort` — needs `order` param added |
| `PaginatedResponse` | models/schemas.py | Returns `total`, `page`, `per_page`, `pages` |
| Create endpoints | routes/models.py, articles.py, products.py | Ready — POST /api/matrix/{entity} |
| Lookup endpoints | routes/lookups.py (assumed) | Ready — GET /api/matrix/lookups/{table} |

---

## Architecture Patterns

### Recommended Project Structure Changes

```
wookiee-hub/src/
├── components/matrix/
│   ├── data-table.tsx              # Add: onSort prop, sort indicators, row status styling
│   ├── table-cell.tsx              # Simplify: remove inline edit logic (Claude's discretion)
│   ├── matrix-topbar.tsx           # Add: "+ Создать" button
│   ├── manage-fields-dialog.tsx    # Replace with column-visibility-popover.tsx
│   ├── column-visibility-popover.tsx   # NEW: Popover with checkboxes for column toggle
│   └── create-record-dialog.tsx    # NEW: Entity-aware create form
├── hooks/
│   ├── use-api-query.ts            # Existing — no changes
│   └── use-table-state.ts          # NEW: Owns page, sort, hiddenColumns state
├── lib/
│   ├── field-def-columns.ts        # NEW: FieldDefinition[] → Column[] conversion
│   └── view-columns.ts             # Existing — keep for stock/finance/rating views
├── pages/product-matrix/
│   ├── models-page.tsx             # Refactor: use FieldDef-driven columns + useTableState
│   ├── articles-page.tsx           # Refactor: same
│   └── products-page.tsx           # Refactor: same
└── stores/
    └── matrix-store.ts             # Add: hiddenColumns per entity (or keep in useTableState)
```

### Pattern 1: FieldDef-Driven Column Generation

**What:** Convert `FieldDefinition[]` from backend into `Column<T>[]` for `DataTable`, replacing hardcoded arrays.

**When to use:** In all three `*-page.tsx` files for the "spec" view. Stock/finance/rating views still use `view-columns.ts`.

**Key insight:** `FieldDefinition.field_name` ending in `_id` maps to a reference cell; `field_name` of `status_id` gets badge rendering; all others get text rendering.

```typescript
// src/lib/field-def-columns.ts
import type { FieldDefinition } from "@/lib/matrix-api"
import type { Column } from "@/components/matrix/data-table"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"

export function fieldDefsToColumns<T>(
  defs: FieldDefinition[],
  lookupCache: Record<string, { id: number; nazvanie: string }[]>,
  hiddenFields: Set<string>,
): Column<T>[] {
  return defs
    .filter((d) => d.is_visible && !hiddenFields.has(d.field_name))
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((def) => {
      const isRefField = def.field_name.endsWith("_id")
      const lookupTable = isRefField ? LOOKUP_TABLE_MAP[def.field_name] : undefined
      const lookupItems = lookupTable ? (lookupCache[lookupTable] ?? []) : []

      return {
        key: isRefField
          ? def.field_name.replace(/_id$/, "_name")  // resolve to _name key
          : def.field_name,
        label: def.display_name,
        fieldDef: def,           // carry original def for sort/badge logic
        lookupItems,
      } satisfies Column<T>
    })
}
```

**IMPORTANT:** The current `ModelOsnova` type already has `_name` join fields (`kategoriya_name`, `fabrika_name`, etc.) returned by the backend. The column key must reference these `_name` fields, NOT the `_id` fields, so the lookup resolution is reading pre-joined values from the backend response. The Zustand lookup cache is needed only for the **create form** dropdowns and for any cases where the `_name` field is missing — the table rows themselves already carry `kategoriya_name` etc. This is a critical distinction.

### Pattern 2: useTableState Hook

**What:** Centralizes `page`, `sortField`, `sortOrder`, `hiddenColumns` state. Each `*-page.tsx` uses this hook instead of duplicating state.

**When to use:** In models-page, articles-page, products-page.

```typescript
// src/hooks/use-table-state.ts
import { useState, useCallback } from "react"
import type { MatrixEntity } from "@/stores/matrix-store"

export interface TableSortState {
  field: string | null
  order: "asc" | "desc"
}

export interface TableState {
  page: number
  perPage: number
  sort: TableSortState
  hiddenFields: Set<string>
  setPage: (page: number) => void
  toggleSort: (field: string) => void
  toggleFieldVisibility: (fieldName: string) => void
  apiParams: Record<string, string | number | undefined>
}

export function useTableState(entity: MatrixEntity, defaultPerPage = 50): TableState {
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<TableSortState>({ field: null, order: "asc" })
  const [hiddenFields, setHiddenFields] = useState<Set<string>>(new Set())

  const toggleSort = useCallback((field: string) => {
    setSort((prev) =>
      prev.field === field
        ? { field, order: prev.order === "asc" ? "desc" : "asc" }
        : { field, order: "asc" },
    )
    setPage(1) // reset to page 1 on sort change
  }, [])

  const toggleFieldVisibility = useCallback((fieldName: string) => {
    setHiddenFields((prev) => {
      const next = new Set(prev)
      next.has(fieldName) ? next.delete(fieldName) : next.add(fieldName)
      return next
    })
  }, [])

  const apiParams: Record<string, string | number | undefined> = {
    page,
    per_page: defaultPerPage,
    ...(sort.field ? { sort: sort.field, order: sort.order } : {}),
  }

  return { page, perPage: defaultPerPage, sort, hiddenFields, setPage, toggleSort, toggleFieldVisibility, apiParams }
}
```

### Pattern 3: Server-Side Sort — Backend Wiring

**What:** The frontend sends `?sort=field&order=asc|desc`. The backend `CommonQueryParams` currently has `sort: Optional[str]` using `field:dir` colon format. Must add an `order` param.

**Current backend CrudService sort format** (from `services/crud.py` line 60-63):
```python
field, _, direction = sort.partition(":")
col = getattr(model, field, None)
if col is not None:
    query = query.order_by(col.desc() if direction == "desc" else col.asc())
```

**Required change to `dependencies.py`:**
```python
@dataclass
class CommonQueryParams:
    page: int = 1
    per_page: int = 50
    sort: Optional[str] = None
    order: Optional[str] = None   # ADD THIS
    search: Optional[str] = None

def common_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: Optional[str] = Query(None),
    order: Optional[str] = Query(None, pattern="^(asc|desc)$"),   # ADD THIS
    search: Optional[str] = Query(None),
) -> CommonQueryParams:
    return CommonQueryParams(page=page, per_page=per_page, sort=sort, order=order, search=search)
```

**Required change to route handlers** — combine `sort` and `order` into the `field:dir` format that `CrudService` expects:
```python
sort_param = f"{params.sort}:{params.order or 'asc'}" if params.sort else None
items, total = CrudService.get_list(db, ModelOsnova, ..., sort=sort_param)
```

**Alternatively**: Update `CrudService.get_list` to accept `sort: str | None` and `order: str | None` directly. Either way works, but combining in the route is less invasive.

### Pattern 4: Status Badge + Archive Row Styling

**What:** Status column renders a colored badge; rows with `status_name === "Архив"` get visual dimming.

**Recommendation for archive row styling:** `opacity-60` on the row `<tr>` — simpler than muted background, immediately scannable, consistent with how GitHub shows closed issues.

```typescript
// In data-table.tsx — row className
<tr
  className={cn(
    "group border-b border-border transition-colors hover:bg-accent/20",
    selectedRows.has(row.id) && "bg-accent/10",
    isArchivedRow(row) && "opacity-60",   // TABLE-07
  )}
>

// Status badge render function (column.render override)
function renderStatusCell(value: string | null) {
  if (!value) return <span className="text-muted-foreground">—</span>
  const isActive = value === "Активный"
  return (
    <Badge
      variant={isActive ? "default" : "secondary"}
      className={cn(
        "text-xs font-medium",
        isActive ? "bg-green-100 text-green-800 border-green-200" : "bg-gray-100 text-gray-600 border-gray-200",
      )}
    >
      {value}
    </Badge>
  )
}
```

**`isArchivedRow` helper:** check `(row as Record<string, unknown>)["status_name"] === "Архив"` — works for all entity types since they all have `status_name`.

### Pattern 5: Pagination Controls

**What:** A pagination bar below the table reading from `PaginatedResponse.total`, `page`, `pages`.

**Design:** « Prev | 1 2 3 ... N | Next » with "Showing X–Y of Z records" label.

**Key implementation detail:** `useApiQuery` re-runs when its `deps` array changes. Pagination works by including `[page, sortField, sortOrder]` in the deps array:

```typescript
const { data, loading } = useApiQuery(
  () => matrixApi.listModels(tableState.apiParams),
  [tableState.page, tableState.sort.field, tableState.sort.order],
)
```

**Page size default recommendation:** 50 (matches `CommonQueryParams` backend default; shows enough rows without overwhelming the browser).

### Pattern 6: Column Visibility Popover

**What:** Replaces `ManageFieldsDialog`. A `Popover` with a checklist of all FieldDef column names; toggling shows/hides that column in the table.

**Persistence recommendation:** Zustand-only for Phase 3 (localStorage deferred to Phase 4 saved views). Store `hiddenFields: Set<string>` inside `useTableState` — it lives as component state scoped to the page mount, so switching entities resets visibility (correct behavior before saved views).

```typescript
// column-visibility-popover.tsx
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { Settings2 } from "lucide-react"
import type { FieldDefinition } from "@/lib/matrix-api"

interface ColumnVisibilityPopoverProps {
  fields: FieldDefinition[]
  hiddenFields: Set<string>
  onToggle: (fieldName: string) => void
}

export function ColumnVisibilityPopover({ fields, hiddenFields, onToggle }: ColumnVisibilityPopoverProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
          <Settings2 className="h-4 w-4" />
          <span className="text-xs">Настроить поля</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-56 p-2">
        <p className="mb-2 px-1 text-xs font-medium text-muted-foreground">Видимость колонок</p>
        <div className="space-y-1">
          {fields.map((f) => (
            <label key={f.field_name} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 hover:bg-accent/30">
              <Checkbox
                checked={!hiddenFields.has(f.field_name)}
                onCheckedChange={() => onToggle(f.field_name)}
              />
              <span className="text-sm">{f.display_name}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
```

### Pattern 7: Create Record Dialog

**What:** A Dialog with a form rendered from FieldDefinitions for the current entity. Only includes "essential" fields (not `is_system`, not computed `_name` fields, not read-only marketplace IDs).

**Entity-aware form fields:**
- `models`: `kod` (required text), `kategoriya_id` (select), `kollekciya_id` (select), `fabrika_id` (select)
- `articles`: `artikul` (required text), `model_id` (requires lookup), `cvet_id` (select), `status_id` (select)
- `products`: `barkod` (required text), `artikul_id` (requires lookup), `razmer_id` (select), `status_id` (select)

**Key wiring:** After `matrixApi.createModel(data)` succeeds:
1. Call `setPage(1)` to reset pagination (so the new record appears)
2. Trigger a re-fetch by incrementing a `refreshKey` counter in the `useApiQuery` deps
3. Call `openDetailPanel(newRecord.id)` to open the record for further editing

**`refreshKey` pattern:**
```typescript
const [refreshKey, setRefreshKey] = useState(0)
const { data, loading } = useApiQuery(
  () => matrixApi.listModels(tableState.apiParams),
  [tableState.page, tableState.sort.field, tableState.sort.order, refreshKey],
)
// After create:
setRefreshKey((k) => k + 1)
```

### Anti-Patterns to Avoid

- **Sending `sort=field:asc` from frontend**: The CONTEXT decision is `?sort=field&order=asc` — use two separate params for readability and to match REST convention.
- **Resolving reference fields in FieldDef column keys as `_id`**: The table row data already has `kategoriya_name` etc. — map column `key` to the `_name` field, not the `_id` field, so no extra resolution step is needed at render time.
- **Using TanStack Table**: The project uses a custom `DataTable` component — do not introduce TanStack Table. The existing custom table is good enough for Phase 3 needs (no virtual scroll, no complex selection logic beyond what's already there).
- **Fetching FieldDefinitions inside each page component**: Fetch FieldDefs once at the entity level (index.tsx or a shared hook), cache in Zustand or pass as prop — avoid N concurrent fetches when 3 pages mount.
- **Column visibility in global Zustand store**: Keep it in `useTableState` (local component state). Global store is for shared state (detailPanelId, activeEntity). Per-page UI state belongs locally.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Status badge variants | Custom CSS class map | shadcn `Badge` + `cn()` | Already installed; variant prop handles styling |
| Popover for column toggle | Custom dropdown div | shadcn `Popover` + Radix primitives | Already in `src/components/ui/popover.tsx` — focus trap, a11y, portal, escape dismiss all handled |
| Create form modal | Custom modal div | shadcn `Dialog` | Already in `src/components/ui/dialog.tsx` |
| Sort indicator icon | SVG inline | lucide-react `ArrowUp` / `ArrowUpDown` / `ArrowDown` | Already installed |
| Pagination UI | Custom page number logic | Build thin component using `PaginatedResponse.pages` data from backend | Simple enough — but DO use the `pages` count from the API response, not client-calculated |
| Form validation in create dialog | Custom validation | Simple `required` HTML attribute + early return | No react-hook-form installed; keep it simple |

**Key insight:** No new packages are needed. Everything required is already in the project.

---

## Common Pitfalls

### Pitfall 1: `useApiQuery` deps array not including sort/page state
**What goes wrong:** Table doesn't re-fetch when user clicks sort or changes page — data appears stale.
**Why it happens:** `useApiQuery` only re-runs when `deps` changes. If `[page, sortField, sortOrder]` are not in deps, the fetcher is never re-triggered.
**How to avoid:** Always spread the pagination/sort state into the `useApiQuery` deps: `[tableState.page, tableState.sort.field, tableState.sort.order, refreshKey]`.
**Warning signs:** Sorting column header has no effect on displayed data; paginating goes to "page 2" but same rows show.

### Pitfall 2: FieldDef column key mismatch for reference fields
**What goes wrong:** Reference columns show "—" because column key is `kategoriya_id` (a number) instead of `kategoriya_name` (a string).
**Why it happens:** FieldDef `field_name` is the raw DB column name (`kategoriya_id`), but `ModelOsnova` has `kategoriya_name` as the join field to display.
**How to avoid:** In `fieldDefsToColumns`, when `field_name.endsWith("_id")`, set `column.key = field_name.replace(/_id$/, "_name")`.
**Warning signs:** Reference cells show numeric IDs or "—" even though backend returns `_name` fields.

### Pitfall 3: Backend sort param format conflict
**What goes wrong:** Frontend sends `?sort=kod&order=asc` but `CrudService` expects `sort=kod:asc` — all sort requests silently ignored (no error, just unsorted results).
**Why it happens:** The existing `CrudService` was built before the `?sort=field&order=dir` API design was decided. The colon format `field:dir` is what it uses internally.
**How to avoid:** Add `order: Optional[str]` to `CommonQueryParams` and combine in route handlers before passing to `CrudService`: `sort_param = f"{params.sort}:{params.order or 'asc'}" if params.sort else None`.
**Warning signs:** Clicking sort header visually changes the sort indicator but rows don't reorder.

### Pitfall 4: Create form shows raw FieldDef `field_type` values for lookups
**What goes wrong:** Reference fields (`kategoriya_id`) render as text inputs because the create form doesn't know to show a `<Select>`.
**Why it happens:** `FieldDefinition.field_type` in the DB is probably `"select"` or `"number"` — but the form needs to know the lookup table name, not just the type.
**How to avoid:** In the create form renderer, check `LOOKUP_TABLE_MAP[def.field_name]` — if a lookup table exists for that field, render a Select with options from `lookupCache[lookupTable]`.

### Pitfall 5: `zod` version conflict with form validation
**What goes wrong:** If react-hook-form is introduced with `@hookform/resolvers`, it will clash with `zod@4.3.6` (the project has zod 4.x, but the known pin in STATE.md says "pin zod to 3.25.x").
**Why it happens:** STATE.md decision from Pre-Phase 1: "Pin zod to 3.25.x — known zodResolver bug with zod 4.x". However, the installed version is actually **4.3.6**. This means react-hook-form is NOT currently used, and should NOT be introduced in Phase 3.
**How to avoid:** For the create form, use simple controlled React state + manual validation. No react-hook-form. No zod schema validation in the form.
**Warning signs:** `@hookform/resolvers` is not installed (confirmed — not in node_modules).

### Pitfall 6: `verbatimModuleSyntax: true` — missing `import type`
**What goes wrong:** TypeScript build fails with "This import is never used as a value" errors.
**Why it happens:** Project has `verbatimModuleSyntax: true` in tsconfig (noted in CONTEXT.md). Type-only imports must use `import type`.
**How to avoid:** Use `import type { FieldDefinition }` wherever only the type is used, not the runtime value.

---

## Code Examples

### Sort Indicator in Column Header
```typescript
// In data-table.tsx — thead
import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react"

<th
  key={col.key}
  onClick={() => col.sortable ? onSort?.(col.key) : undefined}
  className={cn(
    "border-b border-border px-2 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground",
    col.sortable && "cursor-pointer select-none hover:text-foreground",
  )}
>
  <span className="flex items-center gap-1">
    {col.label}
    {col.sortable && (
      sortField === col.key
        ? sortOrder === "asc"
          ? <ArrowUp className="h-3 w-3" />
          : <ArrowDown className="h-3 w-3" />
        : <ArrowUpDown className="h-3 w-3 opacity-40" />
    )}
  </span>
</th>
```

### Pagination Controls Component
```typescript
// src/components/matrix/table-pagination.tsx
interface TablePaginationProps {
  page: number
  pages: number
  total: number
  perPage: number
  onPageChange: (page: number) => void
}

export function TablePagination({ page, pages, total, perPage, onPageChange }: TablePaginationProps) {
  const from = (page - 1) * perPage + 1
  const to = Math.min(page * perPage, total)

  return (
    <div className="flex items-center justify-between px-2 py-2 text-sm text-muted-foreground">
      <span>{from}–{to} из {total}</span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          ‹
        </Button>
        {/* page number buttons — show first, last, and window around current */}
        <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          ›
        </Button>
      </div>
    </div>
  )
}
```

### DataTable Props Extension for Sort
```typescript
// In data-table.tsx — props interface
interface DataTableProps<T extends { id: number }> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  // ... existing props ...
  sortField?: string | null       // ADD
  sortOrder?: "asc" | "desc"      // ADD
  onSort?: (field: string) => void  // ADD
}
```

### Column type extension
```typescript
// In data-table.tsx — Column interface
export interface Column<T> {
  key: string
  label: string
  width?: number
  type?: CellType
  sortable?: boolean              // ADD — controls whether header is clickable
  options?: { id: number; label: string }[]
  render?: (row: T) => React.ReactNode
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `per_page: 200` fixed fetch | Paginated fetch with `page` + `per_page` params | Supports >200 rows; TABLE-05 |
| Hardcoded `Column[]` per entity page | FieldDef-driven columns from `/api/matrix/schema/{entity}` | Auto-updates when admin adds a field |
| `ManageFieldsDialog` (full Dialog for field admin) | `ColumnVisibilityPopover` (lightweight Popover) | Shows/hides columns without changing backend schema |
| No sort support (UI) | `onSort` callback + `sortField`/`sortOrder` props | TABLE-04 |
| No create button in topbar | `+ Создать` → Dialog form | CRUD-01, CRUD-02 |

---

## Open Questions

1. **FieldDefinition `field_type` for reference fields**
   - What we know: `LOOKUP_TABLE_MAP` maps `kategoriya_id → kategorii` etc. But what is the `field_type` stored in the DB for these fields — is it `"select"`, `"relation"`, or something else?
   - What's unclear: The create form renderer needs to know when to show a Select vs text input. If `field_type` is already `"select"` for reference fields, that's sufficient. If it's `"number"` (because the DB column is an integer FK), we need `LOOKUP_TABLE_MAP` as the signal.
   - Recommendation: Use `LOOKUP_TABLE_MAP[def.field_name] !== undefined` as the signal to render a Select in the create form. This is authoritative regardless of what `field_type` says.

2. **FieldDefinitions for `articles` and `products` entity types in `/api/matrix/schema/`**
   - What we know: `manage-fields-dialog.tsx` maps `articles → artikuly`, `products → tovary` via `ENTITY_TYPE_MAP`. But `ENTITY_BACKEND_MAP` in `panel/types.ts` maps `articles → artikuly`, `products → tovary`.
   - What's unclear: Are FieldDefinitions seeded/populated for `artikuly` and `tovary` in the database, or only for `modeli_osnova`?
   - Recommendation: Verify by calling `/api/matrix/schema/artikuly` and `/api/matrix/schema/tovary` during Wave 0 (setup task). If empty, seed them as part of Phase 3 Wave 0.

3. **`status_name` availability in all entity types**
   - What we know: `ModelVariation`, `Artikul`, `Tovar`, `Cvet` all have `status_name: string | null` in the TypeScript types.
   - What's unclear: Whether `status_name` is always populated (not null) so archive row detection works reliably.
   - Recommendation: Check for `status_name === "Архив"` with null guard — if null, treat as active (no dimming).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (backend) — no frontend test framework detected |
| Config file | none — pytest auto-discovers `tests/` directory |
| Quick run command | `pytest tests/product_matrix_api/ -x -q` |
| Full suite command | `pytest tests/ -x -q --ignore=tests/integration` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TABLE-01 | FieldDef display_name → column header | manual (UI) | N/A — frontend-only | N/A |
| TABLE-02 | Reference field values resolved | manual (UI) | N/A — frontend-only | N/A |
| TABLE-03 | Status badge green/gray | manual (UI) | N/A — frontend-only | N/A |
| TABLE-04 | Sort via column header | unit (backend sort) | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k sort` | Wave 0 gap |
| TABLE-05 | Pagination works | unit (backend pagination) | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k page` | Wave 0 gap |
| TABLE-06 | Column visibility toggle | manual (UI) | N/A — frontend-only | N/A |
| TABLE-07 | Archive rows dimmed | manual (UI) | N/A — frontend-only | N/A |
| CRUD-01 | "+ Создать" opens dialog | manual (UI) | N/A — frontend-only | N/A |
| CRUD-02 | Create form creates record | integration | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k create` | Partial ✅ |

### Sampling Rate

- **Per task commit:** `pytest tests/product_matrix_api/test_routes_models.py -x -q`
- **Per wave merge:** `pytest tests/product_matrix_api/ -x -q`
- **Phase gate:** Manual UI smoke test of all 6 success criteria before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/product_matrix_api/test_routes_models.py` — add `test_list_models_sort_asc` and `test_list_models_sort_desc` covering TABLE-04
- [ ] `tests/product_matrix_api/test_routes_models.py` — add `test_list_models_pagination` covering TABLE-05 (page=2 returns different items)
- [ ] `tests/product_matrix_api/test_routes_articles.py` — same sort + pagination coverage for articles
- [ ] Verify FieldDefinitions are seeded for `artikuly` and `tovary` — check `GET /api/matrix/schema/artikuly` response

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `wookiee-hub/src/components/matrix/data-table.tsx` — existing Column interface, DataTable component
- Direct code inspection: `wookiee-hub/src/components/matrix/manage-fields-dialog.tsx` — current ManageFieldsDialog to replace
- Direct code inspection: `wookiee-hub/src/components/matrix/matrix-topbar.tsx` — topbar layout for "+ Создать" insertion
- Direct code inspection: `wookiee-hub/src/components/matrix/panel/types.ts` — LOOKUP_TABLE_MAP, ENTITY_BACKEND_MAP authoritative definitions
- Direct code inspection: `wookiee-hub/src/stores/matrix-store.ts` — Zustand store shape, lookupCache
- Direct code inspection: `services/product_matrix_api/services/crud.py` — `CrudService.get_list` sort format (`field:dir`)
- Direct code inspection: `services/product_matrix_api/dependencies.py` — `CommonQueryParams` current shape
- Direct code inspection: `wookiee-hub/node_modules/.package-lock.json` — confirmed installed package versions
- Direct code inspection: `wookiee-hub/src/components/ui/` — confirmed available shadcn components (Dialog, Popover, Checkbox, Badge, Select)
- Direct code inspection: `.planning/STATE.md` — Pre-Phase 1 decisions (no React Compiler, zod pin note, filter state in Zustand)

### Secondary (MEDIUM confidence)
- `.planning/phases/03-table-view/03-CONTEXT.md` — locked design decisions (sort params, pagination style, create form flow)
- `.planning/REQUIREMENTS.md` — TABLE-01..07, CRUD-01, CRUD-02 requirement text

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified from node_modules
- Architecture: HIGH — all patterns derived from existing code; no speculative libraries
- Backend sort wiring: HIGH — CrudService source code read directly
- Pitfalls: HIGH — derived from code inspection (field key mismatch, sort format conflict confirmed by reading source)
- FieldDef seeding for articles/products: LOW — not verified by code, flagged as Wave 0 check

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable project; no external package updates expected to affect this)
