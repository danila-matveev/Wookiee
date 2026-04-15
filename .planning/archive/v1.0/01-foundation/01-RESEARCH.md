# Phase 1: Foundation - Research

**Researched:** 2026-03-28
**Domain:** React/TypeScript frontend — Zustand state management, entity routing, optimistic UI updates
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | Entity registry — single source of truth for entity key mapping (consolidate 4 parallel entity maps) | 4 entity maps identified in codebase, all can read from one `entity-registry.ts` |
| FOUND-02 | DetailPanel correctly routes requests for all entity types (not just models) | Bug confirmed: `openDetailPanel(id)` called without entityType on articles-page and products-page; global-search also omits entityType |
| FOUND-03 | Entity cache with update propagation — after PATCH in panel the table row reflects the update automatically without full page reload | Current state: panel uses `localData` override (panel shows updated), but table query is NOT refetched after save |
</phase_requirements>

---

## Summary

Phase 1 addresses three interconnected problems in the existing Product Matrix frontend. The codebase has 4 separate places that independently define the mapping from frontend entity slugs (e.g., `"articles"`) to backend entity type strings (e.g., `"artikuly"`) — each with slightly different keys. These need to be consolidated into a single `entity-registry.ts` module. Second, the detail panel is broken for Artikul and Tovar rows: `openDetailPanel(id)` is called without the `entityType` argument on `ArticlesPage`, `ProductsPage`, and `GlobalSearch`, so `detailPanelEntityType` stays `null` and `fetchEntity()` falls through to `Promise.resolve(null)` — panel renders "Не найдено". Third, after saving in the panel, the `localData` override shows the correct value inside the panel but the table row still shows the pre-save value because the table's `useApiQuery` is never triggered to refetch.

All three fixes are pure frontend TypeScript/Zustand changes — no backend work required. The fixes are independent tasks that can be sequenced: registry first (establishes the types), routing fix second (uses registry types), cache propagation third (uses Zustand store pattern already in place).

**Primary recommendation:** Create `entity-registry.ts`, fix `openDetailPanel` call sites to always pass entityType, then add a `notifyEntityUpdated` action to `matrix-store` that bumps a `refreshKey` consumers listen to.

---

## Bug Analysis

### FOUND-02 — The Entity Routing Bug (Confirmed)

**Root cause:** `openDetailPanel` signature is `(id: number, entityType?: MatrixEntity)`. The `entityType` parameter is optional. Pages that call it without `entityType` leave `detailPanelEntityType` unchanged in the store.

**Affected call sites (confirmed by code inspection):**

1. `articles-page.tsx:73` — `onRowClick={openDetailPanel}` — passes only `id`, no entityType
2. `articles-page.tsx:51` — `openDetailPanel(newId)` after create — no entityType
3. `products-page.tsx:72` — `onRowClick={openDetailPanel}` — same problem
4. `products-page.tsx:50` — `openDetailPanel(newId)` after create — same problem
5. `global-search.tsx:85` — `openDetailPanel(result.id)` — no entityType even though `ENTITY_TO_PAGE[result.entity]` is already computed

**What happens:** `fetchEntity()` in `detail-panel.tsx` has no `entityType` branch for `null`, returns `null`, panel renders "Не найдено".

**Fix pattern:** All `onRowClick` usages must pass a wrapper: `(id) => openDetailPanel(id, "articles")`. The `DataTable.onRowClick` prop is `(id: number) => void` — a single-argument callback. Pages must wrap it.

```typescript
// articles-page.tsx — correct pattern
onRowClick={(id) => openDetailPanel(id, "articles")}
```

For global-search, pass the page value as entityType:
```typescript
openDetailPanel(result.id, page)  // page is already MatrixEntity
```

### FOUND-03 — Cache Propagation Gap (Confirmed)

**Current state in detail-panel.tsx:**
- After save: `setLocalData(updated)` — panel shows new value immediately (good)
- Table `useApiQuery` deps: `[tableState.page, tableState.sort.field, tableState.sort.order, refreshKey, activeFilters]`
- `refreshKey` is a `useState` in the page component, incremented only on create
- After panel save: `refreshKey` is never bumped → table stays stale

**Options for propagation:**

Option A — Bump `refreshKey` from panel (requires prop/callback drilling).
Option B — Add `entityUpdateStamp` to Zustand matrix-store (a `Record<MatrixEntity, number>` counter). Panel calls `store.notifyEntityUpdated("articles")` after save. Table page reads `entityUpdateStamp["articles"]` in its `useApiQuery` deps.
Option C — Add a global `lastUpdated` counter (simpler, but causes all entity pages to refetch).

**Recommendation:** Option B. It's Zustand-native, zero prop drilling, and pages already read from the store. Pattern is consistent with how `refreshKey` is currently used locally, just lifted into shared state.

---

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| zustand | ^5.0.0 | State management | Already in use; `create` + `set` pattern established |
| react | ^19.0.0 | UI framework | No changes needed |
| typescript | ^5.0.0 | Type safety | Entity registry benefits from typed exports |
| vitest | ^4.1.2 | Testing | Already configured, jsdom environment |
| @testing-library/react | ^16.3.2 | Component testing | Available for smoke tests |

No new packages required for Phase 1.

---

## The 4 Entity Maps to Consolidate (FOUND-01)

Current state — 4 independent maps with overlapping but inconsistent coverage:

**Map 1: `manage-fields-dialog.tsx:21`**
```typescript
const ENTITY_TYPE_MAP: Record<string, string> = {
  models: "model_osnova",
  articles: "artikul",
  products: "tovar",
  colors: "cvet",
  factories: "fabrika",
  importers: "importer",
  "cards-wb": "sleyka_wb",
  "cards-ozon": "sleyka_ozon",
  certs: "sertifikat",
}
```
Note: Uses singular backend names (`model_osnova`, not `modeli_osnova`).

**Map 2: `mass-edit-bar.tsx:6`**
```typescript
const ENTITY_TO_DB: Record<MatrixEntity, string> = {
  models: "modeli_osnova",
  articles: "artikuly",
  products: "tovary",
  colors: "cveta",
  factories: "fabriki",
  importers: "importery",
  "cards-wb": "skleyki_wb",
  "cards-ozon": "skleyki_ozon",
  certs: "sertifikaty",
}
```
Note: Uses plural backend names for bulk API.

**Map 3: `panel/types.ts:56` — `ENTITY_BACKEND_MAP`**
```typescript
export const ENTITY_BACKEND_MAP: Record<string, string> = {
  models: "modeli_osnova",
  articles: "artikuly",
  products: "tovary",
}
```
Note: Only 3 entities (the main trio). Used for `listFields()` schema lookup.

**Map 4: `tabs/info-tab.tsx:12` — `FIELD_DEF_ENTITY_MAP`**
```typescript
const FIELD_DEF_ENTITY_MAP: Record<string, string> = {
  models_osnova: "modeli_osnova",
  models: "modeli",
  articles: "artikuly",
  products: "tovary",
  colors: "cveta",
  factories: "fabriki",
  importers: "importery",
  cards_wb: "skleyki_wb",
  cards_ozon: "skleyki_ozon",
  certs: "sertifikaty",
}
```
Note: Uses different key format (`cards_wb` not `cards-wb`), and `models_osnova`/`models` distinction.

**Analysis:** Maps 2 and 3 are consistent (use `modeli_osnova`, `artikuly`, `tovary`). Map 1 is inconsistent (singular forms). Map 4 has a different key schema. The registry must preserve both mappings:
- `slug → backendType` (for `listFields` and `bulkAction`)
- `slug → schemaType` (for `manage-fields-dialog` which uses singular forms — but this appears to be a legacy mismatch that should be corrected to match the API)

**Registry design:**

```typescript
// src/lib/entity-registry.ts

export type EntitySlug =
  | "models" | "articles" | "products"
  | "colors" | "factories" | "importers"
  | "cards-wb" | "cards-ozon" | "certs"

export interface EntityRegistryEntry {
  /** Backend plural table name — used for listFields, bulk actions */
  backendType: string
  /** Display label (Russian) */
  label: string
  /** Title field name for panel header */
  titleField: string
}

export const ENTITY_REGISTRY: Record<EntitySlug, EntityRegistryEntry> = {
  models:     { backendType: "modeli_osnova", label: "Модели",      titleField: "kod" },
  articles:   { backendType: "artikuly",      label: "Артикулы",    titleField: "artikul" },
  products:   { backendType: "tovary",        label: "Товары",      titleField: "barkod" },
  colors:     { backendType: "cveta",         label: "Цвета",       titleField: "color_code" },
  factories:  { backendType: "fabriki",       label: "Фабрики",     titleField: "nazvanie" },
  importers:  { backendType: "importery",     label: "Импортёры",   titleField: "nazvanie" },
  "cards-wb": { backendType: "skleyki_wb",    label: "Склейки WB",  titleField: "nazvanie" },
  "cards-ozon": { backendType: "skleyki_ozon", label: "Склейки Ozon", titleField: "nazvanie" },
  certs:      { backendType: "sertifikaty",   label: "Сертификаты", titleField: "nazvanie" },
}

export function getBackendType(slug: EntitySlug): string {
  return ENTITY_REGISTRY[slug].backendType
}
```

---

## Architecture Patterns

### Recommended Project Structure (additions)

```
wookiee-hub/src/lib/
├── entity-registry.ts    # NEW — single entity map (FOUND-01)
├── matrix-api.ts         # existing
└── ...

wookiee-hub/src/stores/
├── matrix-store.ts       # add entityUpdateStamp (FOUND-03)
└── ...

wookiee-hub/src/stores/__tests__/
├── matrix-store-filters.test.ts    # existing
└── entity-registry.test.ts         # NEW — Wave 0 gap
```

### Pattern 1: Registry-first entity resolution

All consumers replace their local map with a registry import:

```typescript
// Before (mass-edit-bar.tsx)
const ENTITY_TO_DB: Record<MatrixEntity, string> = { models: "modeli_osnova", ... }
const entityType = ENTITY_TO_DB[activeEntity]

// After
import { getBackendType } from "@/lib/entity-registry"
const entityType = getBackendType(activeEntity)
```

```typescript
// Before (manage-fields-dialog.tsx)
const ENTITY_TYPE_MAP: Record<string, string> = { models: "model_osnova", ... }
const entityType = ENTITY_TYPE_MAP[entity] ?? entity

// After
import { getBackendType } from "@/lib/entity-registry"
const entityType = getBackendType(entity as EntitySlug)
```

Note on manage-fields-dialog: The current map uses singular forms (`model_osnova`). The `/api/matrix/schema/:entityType` endpoint must accept the plural form (`modeli_osnova`). If the API accepts either, use plural. If only singular, the registry needs a `schemaType` field too — this needs to be confirmed during implementation but is LOW risk since `listFields` API is already working for articles/products via `ENTITY_BACKEND_MAP`.

### Pattern 2: Zustand entityUpdateStamp for table refresh (FOUND-03)

```typescript
// matrix-store.ts additions
interface MatrixState {
  // ... existing fields ...
  entityUpdateStamp: Partial<Record<MatrixEntity, number>>
  notifyEntityUpdated: (entity: MatrixEntity) => void
}

// In create():
entityUpdateStamp: {},
notifyEntityUpdated: (entity) =>
  set((s) => ({
    entityUpdateStamp: {
      ...s.entityUpdateStamp,
      [entity]: (s.entityUpdateStamp[entity] ?? 0) + 1,
    },
  })),
```

```typescript
// detail-panel.tsx — after successful save
setLocalData(updated)
notifyEntityUpdated(detailPanelEntityType)  // trigger table refetch
setIsEditing(false)
```

```typescript
// articles-page.tsx — add stamp to useApiQuery deps
const entityUpdateStamp = useMatrixStore((s) => s.entityUpdateStamp["articles"] ?? 0)

const { data, loading } = useApiQuery(
  () => matrixApi.listArticles(tableState.apiParams),
  [tableState.page, tableState.sort.field, tableState.sort.order, refreshKey, activeFilters, entityUpdateStamp],
)
```

### Pattern 3: Entity-typed openDetailPanel wrapper

Pages already know their entity type. Wrap the callback at the call site:

```typescript
// articles-page.tsx
<DataTable
  onRowClick={(id) => openDetailPanel(id, "articles")}
  ...
/>
```

`DataTable.onRowClick` prop type is `(id: number) => void` — no type changes needed.

### Anti-Patterns to Avoid

- **Don't change the `openDetailPanel` signature to required entityType** — would break `models-page.tsx` which passes just `id` and relies on `activeEntity` inference elsewhere. Fix at call sites only.
- **Don't use React context for entity registry** — it's static data, a plain module export is correct.
- **Don't add `notifyEntityUpdated` to DetailPanel via prop** — use Zustand selector to keep DetailPanel self-contained.
- **Don't replace all 4 maps simultaneously in one commit** — consolidate first, then update consumers one by one.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reactive table refresh | Manual event system / pub-sub | Zustand `entityUpdateStamp` counter in deps array | useApiQuery already reacts to dep changes — just add the stamp |
| Entity label lookups | Yet another per-component map | `ENTITY_REGISTRY[slug].label` | Single update point |
| TypeScript entity validation | Runtime checks | TypeScript `EntitySlug` union type | Compile-time safety, zero runtime cost |

---

## Common Pitfalls

### Pitfall 1: openDetailPanel called on DataTable onRowClick without entityType

**What goes wrong:** `DataTable.onRowClick` is `(id: number) => void`. If you pass `openDetailPanel` directly and it needs `(id, entityType)`, the entityType is never set. The panel opens but `fetchEntity` returns null.

**Why it happens:** The `entityType?` parameter is optional in the current signature, so TypeScript doesn't complain.

**How to avoid:** Every call site that passes `openDetailPanel` to `onRowClick` MUST use an arrow function wrapper: `(id) => openDetailPanel(id, "articles")`. Grep for `openDetailPanel` before shipping.

**Warning signs:** Panel shows "Не найдено" for any entity other than "models". `detailPanelEntityType` is null in React DevTools.

### Pitfall 2: manage-fields-dialog uses singular backend type names

**What goes wrong:** The current `ENTITY_TYPE_MAP` in manage-fields-dialog uses `"model_osnova"` (singular) while the API backend uses `"modeli_osnova"` (plural table name). When the registry replaces this, changing to `"modeli_osnova"` may break if the `/api/matrix/schema/:entityType` endpoint expects singular.

**How to avoid:** Before replacing the map, verify what the schema endpoint expects by checking the backend route. If it expects singular, add `schemaType: string` to the registry entry.

**Warning signs:** ManageFieldsDialog stops loading fields after registry migration. 404 on `/api/matrix/schema/modeli_osnova`.

### Pitfall 3: entityUpdateStamp causing infinite refetch loops

**What goes wrong:** If `notifyEntityUpdated` is called inside a `useEffect` that also reads from the stamp, the update triggers a re-render that triggers the effect again.

**How to avoid:** Call `notifyEntityUpdated` only in response to user actions (save button click), never in effects. The stamp should be in `useApiQuery` deps (a read), not in the save handler's effect.

### Pitfall 4: info-tab.tsx FIELD_DEF_ENTITY_MAP uses `cards_wb` keys (underscore)

**What goes wrong:** `info-tab.tsx` uses `cards_wb` as key, not `cards-wb`. If the registry uses `cards-wb` (hyphen), info-tab will fall through to `entityType` as fallback.

**How to avoid:** Either add an adapter in info-tab that normalizes the key, or add underscore aliases to the registry. Given info-tab is not in this phase's scope (PANEL-* requirements are Phase 2), leave info-tab's local map unchanged for now and only migrate the 3 maps explicitly in FOUND-01 scope (ManageFieldsDialog, MassEditBar, panel/types ENTITY_BACKEND_MAP).

---

## Code Examples

### entity-registry.ts (complete file)

```typescript
// Source: codebase analysis — consolidation of 4 existing maps
import type { MatrixEntity } from "@/stores/matrix-store"

export type { MatrixEntity as EntitySlug }

export interface EntityRegistryEntry {
  /** Backend plural table name used for schema/fields API and bulk actions */
  backendType: string
  /** Human-readable Russian label */
  label: string
  /** Field name used as panel header title */
  titleField: string
}

export const ENTITY_REGISTRY: Record<MatrixEntity, EntityRegistryEntry> = {
  models:       { backendType: "modeli_osnova", label: "Модели",        titleField: "kod" },
  articles:     { backendType: "artikuly",      label: "Артикулы",      titleField: "artikul" },
  products:     { backendType: "tovary",        label: "Товары",        titleField: "barkod" },
  colors:       { backendType: "cveta",         label: "Цвета",         titleField: "color_code" },
  factories:    { backendType: "fabriki",       label: "Фабрики",       titleField: "nazvanie" },
  importers:    { backendType: "importery",     label: "Импортёры",     titleField: "nazvanie" },
  "cards-wb":   { backendType: "skleyki_wb",    label: "Склейки WB",    titleField: "nazvanie" },
  "cards-ozon": { backendType: "skleyki_ozon",  label: "Склейки Ozon",  titleField: "nazvanie" },
  certs:        { backendType: "sertifikaty",   label: "Сертификаты",   titleField: "nazvanie" },
}

/** Get backend entity type string for schema/fields/bulk API calls */
export function getBackendType(slug: MatrixEntity): string {
  return ENTITY_REGISTRY[slug].backendType
}

/** Get display label for entity */
export function getEntityLabel(slug: MatrixEntity): string {
  return ENTITY_REGISTRY[slug].label
}
```

### matrix-store.ts additions for FOUND-03

```typescript
// Add to interface MatrixState:
entityUpdateStamp: Partial<Record<MatrixEntity, number>>
notifyEntityUpdated: (entity: MatrixEntity) => void

// Add to initial state:
entityUpdateStamp: {},

// Add to create():
notifyEntityUpdated: (entity) =>
  set((s) => ({
    entityUpdateStamp: {
      ...s.entityUpdateStamp,
      [entity]: (s.entityUpdateStamp[entity] ?? 0) + 1,
    },
  })),
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 4 independent entity maps | entity-registry.ts single source | Phase 1 (this phase) | One change point for all consumers |
| `openDetailPanel(id)` without entityType | `openDetailPanel(id, "articles")` at call sites | Phase 1 | Panel works for all entity types |
| localData override only in panel | Zustand entityUpdateStamp in table deps | Phase 1 | Table row reflects save without reload |

---

## Open Questions

1. **Does `/api/matrix/schema/:entityType` accept plural or singular form?**
   - What we know: `listFields` is called with `ENTITY_BACKEND_MAP.articles = "artikuly"` (plural) and is working for articles/products pages
   - What's unclear: whether `manage-fields-dialog` calling with `"model_osnova"` (singular) is actually working or silently failing
   - Recommendation: Check browser network tab for `/api/matrix/schema/model_osnova` call — if 404, registry migration will fix it (use plural). If 200, document that `schemaType` needs to be separate field.

2. **Does `openDetailPanel` on models-page need to remain single-argument?**
   - What we know: `models-page.tsx:231` passes `onRowClick={openDetailPanel}` without entityType — but `setActiveEntity` is called separately when navigating to models, so `detailPanelEntityType` is already "models" from the store initialization
   - What's unclear: whether the panel works correctly for models currently (likely yes, since "models" is the default `activeEntity`)
   - Recommendation: Wrap ALL `onRowClick` usages consistently for clarity, even models. No regression risk.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.2 + @testing-library/react 16.3.2 |
| Config file | `wookiee-hub/vitest.config.ts` (exists, jsdom environment) |
| Quick run command | `cd wookiee-hub && npm test -- --reporter=verbose src/stores/__tests__/ src/lib/__tests__/` |
| Full suite command | `cd wookiee-hub && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | `getBackendType("articles")` returns `"artikuly"` | unit | `npm test -- src/lib/__tests__/entity-registry.test.ts` | Wave 0 |
| FOUND-01 | All 9 entity slugs covered, no undefined | unit | same | Wave 0 |
| FOUND-02 | `openDetailPanel(id, "articles")` sets `detailPanelEntityType = "articles"` | unit (store) | `npm test -- src/stores/__tests__/detail-panel-routing.test.ts` | Wave 0 |
| FOUND-02 | `openDetailPanel(id)` without type: store entityType unchanged | unit (store) | same | Wave 0 |
| FOUND-03 | `notifyEntityUpdated("articles")` increments stamp | unit (store) | `npm test -- src/stores/__tests__/entity-update-stamp.test.ts` | Wave 0 |
| FOUND-03 | Stamp is scoped per entity (articles stamp doesn't affect products) | unit (store) | same | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd wookiee-hub && npm test -- src/stores/__tests__/ src/lib/__tests__/`
- **Per wave merge:** `cd wookiee-hub && npm test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `wookiee-hub/src/lib/__tests__/entity-registry.test.ts` — covers FOUND-01
- [ ] `wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts` — covers FOUND-02
- [ ] `wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts` — covers FOUND-03

*(Note: existing `matrix-store-filters.test.ts` serves as the pattern to follow for Zustand store unit tests)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all 4 entity maps read directly from source files
- `wookiee-hub/src/components/matrix/detail-panel.tsx` — routing logic confirmed
- `wookiee-hub/src/stores/matrix-store.ts` — Zustand store structure confirmed
- `wookiee-hub/src/pages/product-matrix/articles-page.tsx` — bug confirmed (line 73, 51)
- `wookiee-hub/src/pages/product-matrix/products-page.tsx` — bug confirmed (line 72, 50)
- `wookiee-hub/src/components/matrix/global-search.tsx` — bug confirmed (line 85)
- `wookiee-hub/vitest.config.ts` — test infrastructure confirmed
- `wookiee-hub/package.json` — dependency versions confirmed

### Secondary (MEDIUM confidence)
- None required — all findings from direct code inspection

### Tertiary (LOW confidence)
- Singular vs plural form for manage-fields-dialog schema API — not verified (network inspection needed)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — inspected package.json and existing code directly
- Architecture: HIGH — patterns derived from existing working code (matrix-store-filters.test.ts, existing useApiQuery deps pattern)
- Bug identification: HIGH — traced call chains directly in source
- Pitfalls: HIGH — derived from actual code structure, not speculation

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable frontend architecture)
