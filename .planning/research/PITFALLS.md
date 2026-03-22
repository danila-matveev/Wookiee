# Pitfalls Research

**Domain:** Notion-like PIM UI — adding detail-panel editing, 90+ fields, virtual scroll, reference resolution, and column config to an existing Product Matrix (React 19 + Vite + Zustand + FastAPI)
**Researched:** 2026-03-22
**Confidence:** HIGH (project code read directly; web-verified for virtual scroll, concurrent edits, accessibility patterns)

---

## Critical Pitfalls

### Pitfall 1: Detail panel hardcoded to `models` entity — edit writes to wrong row

**What goes wrong:**
The current `DetailPanel` component calls `matrixApi.getModel(detailPanelId)` unconditionally, regardless of which entity tab is active. When the redesign adds editing inside the panel, a user editing a product's detail panel will write a PATCH to `/api/matrix/models/{id}` instead of `/api/matrix/products/{id}`. The wrong field names will be sent, silently corrupting data or returning 422 errors.

**Why it happens:**
The panel was built only for `models` as a quick prototype. `detailPanelId` in Zustand carries only an integer — no entity context. When editing support is added, the panel needs to know both `id` and `entity` to route the PATCH correctly, but that context isn't there.

**How to avoid:**
Change `MatrixState.detailPanelId` from `number | null` to `{ id: number; entity: MatrixEntity } | null` before writing a single edit field in the panel. Every consumer of `detailPanelId` needs to be updated at the same time. Extend `matrixApi` with a generic `updateEntity(entity, id, data)` dispatcher that routes to the correct endpoint.

**Warning signs:**
- `DetailPanel` does not read `activeEntity` from the store
- `openDetailPanel` only accepts a bare number
- Any PATCH call inside the panel that uses a hardcoded endpoint

**Phase to address:** Phase 1 (Panel Architecture) — this must be the very first structural change before any editing logic is written.

---

### Pitfall 2: Zustand store holds stale table rows after panel edit

**What goes wrong:**
The table fetches its data once (`useApiQuery` with empty deps) and stores it in local component state. After the detail panel saves a field edit via PATCH, the saved value is visible only in the panel. The table row still shows the old value. If the user closes the panel and looks at the table, they see inconsistency — which erodes trust in the editing feature entirely.

**Why it happens:**
There is no shared server-state cache (no React Query / SWR). Each page component owns its own `data` state. The panel edits do not reach that state. Optimistic updates on the panel side only affect the panel's local copy.

**How to avoid:**
Either (a) introduce a lightweight server-state cache (TanStack Query) so all components sharing the same cache key auto-refresh on mutation, or (b) add an `entityCache` slice to the Zustand store that holds the canonical record and is updated on every PATCH success. Option (a) is cleaner for a subsequent milestone. For this milestone, option (b) (a simple `Map<string, Record<string, unknown>>` keyed by `"{entity}:{id}"`) prevents the immediate bug without a large refactor.

**Warning signs:**
- Table data is fetched directly inside page components without a cache key
- `onCellEdit` in `data-table.tsx` fires a PATCH but does not update local state
- Panel saves with no callback to the table

**Phase to address:** Phase 1 (Panel Architecture) — define the update propagation contract before writing any edit UI.

---

### Pitfall 3: Inline cell edit and panel edit fight over the same record

**What goes wrong:**
The table currently allows direct inline editing (`TableCell` with `type: "text"`). The panel will also allow editing the same fields. If a user double-clicks a cell to edit inline while the panel is open for the same row, there are two concurrent drafts of the same field. Whichever `onBlur` fires last wins, silently overwriting the other edit. No conflict is shown to the user.

**Why it happens:**
There is no "edit lock" concept: the store has no notion of which component currently owns a record's edit session.

**How to avoid:**
During the panel-editing milestone, designate one primary editing surface: the detail panel is the canonical editor; the table shows read-only values for rows that have their panel open. Implement a simple rule: when `detailPanelId` is set, the corresponding table row's cells become non-interactive (the `type` for all columns defaults to `"readonly"` for that row ID). This is a one-line guard in `TableCell` — check `detailPanelId === row.id`.

**Warning signs:**
- `onCellEdit` and panel PATCH can both fire for the same `(entity, id, field)` within the same render cycle
- No check in `TableCell` for whether the row is "owned" by an open panel

**Phase to address:** Phase 1 (Panel Architecture).

---

### Pitfall 4: Reference field resolution causes N+1 lookups in the panel

**What goes wrong:**
When the panel opens for a `models` record, it already has `kategoriya_name`, `kollekciya_name`, `fabrika_name` resolved server-side. But for editable reference fields (FK dropdowns), the frontend needs the full lookup list to populate a `<select>`. If each reference field triggers its own `matrixApi.getLookup(table)` call on mount, opening a panel for a record with 5 FK references fires 5 serial requests. With 90+ fields across all entity types, some panels will fire 10–15 lookup requests at open time, adding 500–1500ms to perceived open latency.

**Why it happens:**
`getLookup(table)` is a per-table API call. Without caching or batching, each editable FK field fetches independently.

**How to avoid:**
Pre-fetch and cache all lookup tables for the active entity when the user lands on that entity page — not when the panel opens. Cache lookup results in a module-level `Map<string, LookupItem[]>` (or Zustand `lookupsCache` slice) with a TTL of 5 minutes. The panel then reads from cache synchronously, with zero added latency. This is a small addition to `useMatrixStore` and a `useLookups(entityType)` hook.

**Warning signs:**
- `getLookup` is called inside panel component `useEffect` or render
- Network tab shows multiple `GET /api/matrix/lookups/` requests firing simultaneously when a panel opens
- Lookup responses are not shared between panel and ManageFieldsDialog

**Phase to address:** Phase 2 (Field Rendering) — implement lookup cache before adding any FK-editable field to the panel.

---

### Pitfall 5: Virtual scroll breaks with dynamic row heights when child rows are expanded

**What goes wrong:**
The current `DataTable` uses a plain `<table>` with a CSS `overflow-auto` container. When virtual scrolling is added (TanStack Virtual is the appropriate library for this stack), the virtualizer assumes a stable estimated row height. When a parent row is expanded to show children (as `ModelsPage` does), the effective height of that "row group" changes from ~32px to 32px + (N * 32px). If TanStack Virtual is not told to re-measure after expansion, the scroll position jumps and rows appear at wrong offsets.

**Why it happens:**
TanStack Virtual's `measureElement` callback is tied to individual DOM elements. Expand/collapse changes the DOM structure but doesn't automatically trigger re-measurement for the parent row. Developers add virtualization for performance, test with collapsed rows, and ship — only discovering the jump on expand/collapse during QA.

**Warning signs:**
- Virtualizer `estimateSize` is a fixed constant rather than a function of `isExpanded`
- Expand toggle does not call `virtualizer.measure()` or `scrollToIndex` to resync position
- Scroll position visibly jumps after toggling a row
- Children rows are rendered as separate virtualized items rather than part of the parent item's measured height

**How to avoid:**
Model each expanded parent + all its children as a single "virtual row group" with a dynamically measured height, using TanStack Virtual's `measureElement` ref callback on the outermost group `<tbody>` element. Alternatively, use fixed-height rows only (32px guaranteed) and render children as separate items in the virtualizer's flat item array, recalculating the full array when `expandedRows` changes. The flat-array approach is simpler and avoids ResizeObserver cost.

Known TanStack Virtual issue: scrolling up with dynamic heights stutters when height-corrected items push other items out of the estimated position (GitHub issue #659). Mitigate by over-scanning 5+ rows (`overscan: 5`) to smooth the correction.

**Phase to address:** Phase 3 (Performance / Virtual Scroll) — do not mix virtualization with expand/collapse unless the row model is fully specified first.

---

### Pitfall 6: `per_page: 200` hardcoded — memory and DOM pressure at scale

**What goes wrong:**
Every entity page fetches `per_page: 200` and renders all rows at once into a real DOM table. `Tovar` (SKU/barcode level) is the largest entity: a brand with 500 models × 3 colors × 8 sizes = 12,000+ rows. Fetching 200 at a time works for now, but as the catalog grows, the initial page load will spike memory and Time-to-Interactive. Pagination was intentionally not shipped to keep the UI simple, but this creates a known cliff.

**Why it happens:**
The `PaginatedResponse<T>` type exists in the API but the UI ignores `pages` and always fetches page 1 with a high per_page. No virtual scroll yet means each row is a real DOM node.

**How to avoid:**
Implement virtual scroll (see Pitfall 5) and server-side cursor pagination together. The virtualizer requests the next page when the user scrolls within 2 screens of the bottom. This is the "infinite scroll with virtualization" pattern. The key requirement is that `totalCount` from `PaginatedResponse` feeds the virtualizer's `count` prop so the scroll thumb reflects actual data size.

**Warning signs:**
- `per_page: 200` appears as a literal in all entity pages
- `data?.items ?? []` is passed directly to the table without any windowing

**Phase to address:** Phase 3 (Performance / Virtual Scroll).

---

### Pitfall 7: Column config `SavedView` not validated against actual field permissions

**What goes wrong:**
`SavedView.config.columns` is a plain `string[]` of field names. When a user saves a view that includes a column they can currently see, then their role changes and that field becomes restricted, the saved view still includes the restricted column key. The column renders silently — either as an empty cell or, worse, with real data that should be hidden.

**Why it happens:**
There is no intersection step between `ViewConfig.columns` and the set of `FieldDefinition` where `is_visible: true` for the current user's role. The current code in `getViewColumns` applies column lists statically, with no runtime permission gate.

**How to avoid:**
On panel open and on table render, compute the effective visible column set as: `savedView.columns.filter(col => permittedFields.has(col))`. The `permittedFields` set should come from the backend's `GET /api/matrix/schema/{entityType}` response, which already carries `is_visible` per field. This filter should be applied in `getViewColumns` or a new `usePermittedColumns(entityType, savedView)` hook.

**Warning signs:**
- `getViewColumns` does not check `is_visible` from `FieldDefinition`
- Column visibility is controlled entirely on the frontend without server confirmation
- No test that verifies restricted fields are hidden when role changes

**Phase to address:** Phase 2 (Field Rendering) — field-level permissions must be enforced before saved views are introduced.

---

### Pitfall 8: Read-only `_name` fields visually indistinguishable from editable fields in the panel

**What goes wrong:**
In `matrix-api.ts`, denormalized display fields (`kategoriya_name`, `fabrika_name`, `status_name`, etc.) are `readonly` at the DB level — they are computed server-side. In the detail panel, if these render using the same visual style as editable text fields, users will click them expecting to edit, discover they cannot, and either give up or file bugs. This cognitive friction is severe when there are 90+ fields with mixed editability.

**Why it happens:**
The current `info-tab.tsx` renders all fields as plain `<span>` text — no editing at all. When editing is added, developers typically style all fields uniformly and add a `disabled` or `readOnly` attribute. Research shows gray-disabled styling adds cognitive load because users cannot distinguish "this field is read-only because it's computed" from "this field is disabled for me specifically".

**How to avoid:**
Use three distinct visual states, not two:
1. **Editable** — white background, hover highlight, pencil icon on hover
2. **Computed/derived** — subtle tinted background (e.g., `bg-muted/30`), no hover effect, "calculated" badge or tooltip explaining the source
3. **Permission-restricted** — same as computed but with a lock icon and tooltip "Edit requires admin role"

Map field types from `FieldDefinition.field_type` + a new `is_editable` boolean (add to `FieldDefinition`) to determine which state to use. Do not rely purely on frontend inference.

**Warning signs:**
- `FieldDefinition` has no `is_editable` or `is_readonly` flag
- Panel renders editable and readonly fields with identical markup
- "Computed" fields (ending in `_name` or `_count`) are not flagged as derived in the schema

**Phase to address:** Phase 2 (Field Rendering).

---

### Pitfall 9: Panel edit saves fire without validation, leaving partial state

**What goes wrong:**
`onCellEdit` in `data-table.tsx` fires a PATCH immediately on `onBlur` / Enter. There is no validation before the API call. For the panel, if a user is editing a `tnved` code (which must be exactly 10 digits) and navigates away mid-edit, the PATCH fires with an invalid partial value. FastAPI's Pydantic model may accept it (if the field is `str | None`), silently saving bad data. The audit log will record the bad value with no error.

**Why it happens:**
The current cell-edit model is "optimistic immediate save" — no pending/dirty state, no validation schema. This works for simple string fields but is dangerous for fields with business rules (codes, identifiers, foreign keys).

**How to avoid:**
Introduce a per-field validation layer in the panel before PATCH dispatch:
- Define a `validate(fieldType, value)` function per `FieldDefinition.field_type`
- Block the PATCH if validation fails; show inline error under the field
- For the table's inline edits, add the same validation before calling `onSave`
- On the FastAPI side, add Pydantic `@validator` or `field_validator` constraints for fields with known formats (TNVED = `\d{10}`, barcodes, INN, etc.)

**Warning signs:**
- No Pydantic validators on structured string fields in `schemas.py`
- `onCellEdit` calls `matrixApi.updateModel(id, { [field]: value })` without any client-side check
- Error responses from FastAPI are not surfaced to the user (caught with `catch { // TODO: toast error }`)

**Phase to address:** Phase 2 (Field Rendering) — validation must be in place before editable panel fields go to production.

---

### Pitfall 10: Entity type mapping inconsistency between frontend keys and backend endpoint names

**What goes wrong:**
There are at least three parallel entity key systems in the codebase:
- Zustand `MatrixEntity`: `"models"`, `"cards-wb"`, `"cards-ozon"`, `"articles"`, `"products"`, ...
- `ENTITY_TYPE_MAP` in `ManageFieldsDialog`: `models → "model_osnova"`, `"cards-wb" → "sleyka_wb"`, ...
- `FIELD_DEF_ENTITY_MAP` in `InfoTab`: `models_osnova → "modeli_osnova"`, `cards_wb → "skleyki_wb"`, ...
- API URL prefixes: `/api/matrix/models`, `/api/matrix/cards-wb`, `/api/matrix/articles`, ...
- `ENTITY_TO_DB` in `MassEditBar`: `models → "modeli_osnova"`, `"cards-wb" → "skleyki_wb"`, ...

These four maps are out of sync. Adding a new entity to one map and forgetting another causes routing failures that surface only at runtime with a specific interaction.

**Why it happens:**
The mappings were added incrementally across components without a canonical source of truth. Each developer who added a new entity added a local map rather than extending a shared one.

**How to avoid:**
Create a single `ENTITY_REGISTRY` module (e.g., `src/config/entity-registry.ts`) that defines all four names per entity as a typed record, and derive all local maps from it. Any new entity is added in one place only.

```typescript
// src/config/entity-registry.ts
export const ENTITY_REGISTRY = {
  models:      { apiPath: "models",    schemaType: "model_osnova",  dbKey: "modeli_osnova" },
  articles:    { apiPath: "articles",  schemaType: "artikul",       dbKey: "artikuly" },
  products:    { apiPath: "products",  schemaType: "tovar",         dbKey: "tovary" },
  "cards-wb":  { apiPath: "cards-wb",  schemaType: "sleyka_wb",     dbKey: "skleyki_wb" },
  // ...
} as const satisfies Record<MatrixEntity, EntityRegistryEntry>
```

**Warning signs:**
- More than one `Record<MatrixEntity, string>` map exists in the codebase (currently: at least 4)
- A new entity page requires touching 5+ files to register it
- Tests pass but the detail panel shows wrong data for `cards-wb` or `cards-ozon`

**Phase to address:** Phase 1 (Panel Architecture) — fix before adding any new entity-dependent logic.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `per_page: 200` hardcoded | Simple, works today | Memory spike + slow load at 1000+ rows | Only until Phase 3 (virtual scroll + pagination) |
| Parallel entity key maps (ENTITY_TYPE_MAP, ENTITY_TO_DB, etc.) | Fast per-component bootstrap | Silent bugs when adding entities; 4 places to update | Never — consolidate in Phase 1 |
| No validation before PATCH | Instant save, simple code | Bad data in DB for structured fields (codes, IDs) | Never for fields with business rules |
| Panel reads stale table data | Simple implementation | Users see inconsistent state after editing | Never once panel editing is live |
| `DetailPanel` always calls `getModel` | Works for models entity | Wrong API call for all other entities | Never beyond current prototype |
| Lookup fetched per-field in panel | Simple, self-contained | N+1 requests on panel open | Only in dev; must cache before any FK field is editable |
| No `is_editable` on `FieldDefinition` | Schema stays small | Cannot distinguish computed from editable fields in UI | Never once 90+ fields are displayed |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI PATCH + Pydantic | Sending `null` for unset optional fields erases existing data | Send only changed fields (sparse PATCH); Pydantic models should use `model_update` with `exclude_unset=True` |
| TanStack Virtual + `<table>` | `<tr>` elements inside a virtualized container require `display: block` on `<tbody>` which breaks table layout | Use `<div>`-based rows instead of native `<table>`, or use TanStack Table's virtualizer example that wraps `<tr>` in a `relative` positioned `<tbody>` |
| Zustand + React 19 Strict Mode | Double-invocation of state setters in dev mode can cause duplicate PATCH calls if mutation is triggered in state initializer | Separate API calls from Zustand actions; call API in event handlers, not inside `set()` callbacks |
| `SavedView` config + `FieldDefinition` schema | View config column list can reference fields deleted from the schema, causing silent blank columns | On view load, filter columns through current `listFields` response; tombstone missing field keys visually |
| `matrixApi.getLookup` + RLS (Supabase) | Lookup tables may have row-level policies that restrict which options a user can see; bypassing via service key on a public endpoint exposes all options | Ensure lookup endpoints respect the same auth context as entity endpoints |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| All rows in real DOM (no virtualization) | Scroll lag, high memory, long TTI | TanStack Virtual with flat item array | > ~500 rows in `products` or `articles` views |
| N+1 lookup fetches on panel open | Network waterfall of 5–15 sequential requests | Pre-fetch all lookups for active entity on mount, cache with 5-min TTL | First time a panel is opened for any entity with FK fields |
| `useEffect` with `expandedRows` dependency fires a new children fetch for every newly visible row during scroll | Hundreds of API calls during fast scroll through expanded rows | Gate fetch on `!childrenMap.has(id)` (already partially done) + debounce the effect | When > 20 rows are expanded simultaneously |
| Column config recomputed on every render | Jank during scroll as columns are recalculated | Memoize column config with `useMemo` keyed on `[entityType, activeView, savedViewConfig]` | On any re-render of the page component (e.g., panel open/close) |
| `InfoTab` calls `listFields` on every panel open | Redundant schema fetch, visible latency | Cache `listFields` response per `entityType` for session lifetime | After user opens 20+ panels during one session |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Field-level `is_visible: false` enforced only on frontend | Backend returns hidden field values in JSON; user can read them via DevTools | Backend must omit hidden fields from serialized responses, not just filter on the client |
| Bulk PATCH action (`/api/matrix/bulk/{entityType}`) does not validate individual field permissions | A user with read-only access to a field can include it in a bulk update payload | Bulk route must apply same per-field permission checks as single PATCH |
| Saved view `is_default` can be set by any user for any entity | One user's default view overrides another's | `is_default` should be scoped per `user_id`; the backend already has `user_id` on `SavedView` — enforce it |
| Archive restore does not re-validate business rules | A record archived when a FK target existed may be restored after the FK target was deleted, creating orphaned references | Restore endpoint should re-run integrity checks before confirming restore |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| 90+ fields shown flat in panel with no grouping | Users cannot find fields; panel feels like a database dump | Group by `FieldDefinition.section` (already implemented in `InfoTab`) + add collapsible sections per group |
| Panel opens to the right and pushes table left, suddenly reducing visible columns | Disorienting layout shift, columns may disappear | Reserve panel space from the start using CSS Grid with a fixed panel column that collapses to zero width with CSS transition |
| No "unsaved changes" guard when closing panel mid-edit | User loses edit silently | Track `isDirty` in panel local state; show confirmation dialog on close if dirty |
| Edit confirmation is "press Enter or click away" (onBlur = save) | Accidental saves when tabbing through fields | Use explicit Save button for panel edits; reserve onBlur-save for table cell inline edits only |
| Disabled and computed fields render in same gray style | Users cannot distinguish "no permission" from "system calculated" | Three visual states: editable / computed / permission-restricted (see Pitfall 8) |
| Filter bar disappears when panel is open | User cannot filter while reviewing a record | Filter and column config toolbar should remain accessible above the table even when panel is open |
| Column reordering via drag-and-drop is not keyboard accessible | Blocks users who navigate with keyboard | Provide an alternative: arrow buttons in the column config dialog to move fields up/down |

---

## "Looks Done But Isn't" Checklist

- [ ] **Detail Panel editing:** Panel shows editable fields — verify PATCH goes to the correct entity endpoint, not always `models`
- [ ] **Panel saves reflected in table:** After closing the panel, verify the table row shows updated values without a manual page refresh
- [ ] **Read-only fields blocked on write:** Verify that `_name` (computed) fields cannot be written to via the panel edit form (no input rendered, no PATCH sent for those keys)
- [ ] **Lookup cache:** Verify that opening 10 panels in a row for the same entity fires `getLookup` only once per lookup table per session
- [ ] **Saved view column filter:** Verify that a field marked `is_visible: false` in `listFields` does not appear in the table even if it exists in a saved view config
- [ ] **Virtual scroll expand/collapse:** Verify that expanding a row with 50 children and then scrolling down does not cause position jumps
- [ ] **Entity registry consistency:** Verify that adding a new entity requires changes in exactly one file (`entity-registry.ts`), not five
- [ ] **Validation before PATCH:** Verify that saving an invalid TNVED code (fewer than 10 digits) shows an inline error and does not call the API
- [ ] **Concurrent inline + panel edit:** Verify that while a detail panel is open for row ID 42, the corresponding row in the table shows readonly cells
- [ ] **Bulk edit with mixed permissions:** Verify that bulk status update does not allow setting fields the current user cannot write

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong entity endpoint in panel (Pitfall 1) | HIGH — data corruption in DB | Roll back corrupted records from `archive` table if available; add entity context to store, rewrite panel to route correctly |
| Zustand stale state after panel edit (Pitfall 2) | LOW | Add `entityCache` slice to store; panel `onSave` updates cache; table reads from cache |
| N+1 lookup requests (Pitfall 4) | LOW | Add module-level lookup cache map; replace `useEffect` fetches with cache read |
| Virtual scroll jump on expand (Pitfall 5) | MEDIUM | Rebuild row model as flat array with one item per row (parent + children flattened); re-measure after expand |
| Parallel entity key maps out of sync (Pitfall 10) | MEDIUM | Create `entity-registry.ts`; grep for all `Record<MatrixEntity` usages; replace with derived maps |
| Field without validation saves bad data (Pitfall 9) | HIGH — data quality | Add Pydantic validators on backend for all structured fields; run backfill query to identify and flag malformed existing values |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Panel hardcoded to `models` entity (1) | Phase 1 — Panel Architecture | Open panel for `articles` entity, save a field, verify PATCH goes to `/api/matrix/articles/{id}` |
| Stale table after panel edit (2) | Phase 1 — Panel Architecture | Edit a field in panel, close panel, table row shows new value without refresh |
| Concurrent inline + panel edit conflict (3) | Phase 1 — Panel Architecture | Open panel for row 1, attempt to click row 1 inline cell, verify cell is non-interactive |
| N+1 lookup fetches (4) | Phase 2 — Field Rendering | Open panel with 5 FK fields, Network tab shows 0 lookup requests (served from cache) |
| Virtual scroll + expand/collapse (5) | Phase 3 — Performance | Expand 3 rows, scroll to bottom, scroll back — no position jumps |
| Hardcoded `per_page: 200` (6) | Phase 3 — Performance | `products` entity with 1000+ rows loads in < 1s, scroll is smooth |
| Saved view vs. field permissions (7) | Phase 2 — Field Rendering | Restricted field in saved view renders as blank/absent, not as visible data |
| Mixed editability visual confusion (8) | Phase 2 — Field Rendering | Computed fields have distinct tinted background; permission-restricted fields show lock icon |
| No validation before PATCH (9) | Phase 2 — Field Rendering | Saving invalid TNVED shows inline error, no API call made |
| Entity key map fragmentation (10) | Phase 1 — Panel Architecture | Adding a test entity requires editing exactly one file; all mappings auto-derived |

---

## Sources

- Project source code: `wookiee-hub/src/stores/matrix-store.ts`, `wookiee-hub/src/components/matrix/detail-panel.tsx`, `wookiee-hub/src/components/matrix/data-table.tsx`, `wookiee-hub/src/lib/matrix-api.ts`, `wookiee-hub/src/components/matrix/tabs/info-tab.tsx`, `wookiee-hub/src/components/matrix/mass-edit-bar.tsx`
- TanStack Virtual — dynamic height issues: [GitHub #659 (scroll stutter)](https://github.com/TanStack/virtual/issues/659), [GitHub #832 (lag)](https://github.com/TanStack/virtual/issues/832), [GitHub #376 (no update after height change)](https://github.com/TanStack/virtual/issues/376)
- FastAPI concurrent edits: [SQLAlchemy Database Locks with FastAPI](https://medium.com/@mojimich2015/sqlalchemy-database-locks-using-fastapi-a-simple-guide-3e7dcd552d87), [REST Best Practices: Concurrent Updates](https://blog.4psa.com/rest-best-practices-managing-concurrent-updates/)
- Read-only field UX: [Avoid Read-only Controls — Adrian Roselli](https://adrianroselli.com/2024/11/avoid-read-only-controls.html), [Cloudscape: Disabled and Read-only States](https://cloudscape.design/patterns/general/disabled-and-read-only-states/)
- Focus trap in side panels: [Accessibility Quick Wins in ReactJS 2025](https://medium.com/@sureshdotariya/accessibility-quick-wins-in-reactjs-2025-skip-links-focus-traps-aria-live-regions-c926b9e44593)
- Virtual scroll high-row-count patterns: [Virtual Scrolling for Billions of Rows — HighTable](https://rednegra.net/blog/20260212-virtual-scroll/)

---
*Pitfalls research for: Notion-like PIM Editor — Product Matrix UX Redesign*
*Researched: 2026-03-22*
