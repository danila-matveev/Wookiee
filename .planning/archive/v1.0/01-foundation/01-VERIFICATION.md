---
phase: 01-foundation
verified: 2026-03-28T19:45:00Z
status: gaps_found
score: 5/7 must-haves verified
re_verification: false
gaps:
  - truth: "Opening detail panel for an Artikul or Tovar row fetches from the correct endpoint (not /api/matrix/models/)"
    status: partial
    reason: "articles and products are routed correctly. But fetchEntity in detail-panel.tsx returns Promise.resolve(null) for colors, factories, importers, cards-wb, cards-ozon, certs (line 25). Six entity types show a blank panel on open."
    artifacts:
      - path: "wookiee-hub/src/components/matrix/detail-panel.tsx"
        issue: "fetchEntity only handles 'models', 'articles', 'products' — falls through to return null for remaining 6 entity types"
    missing:
      - "fetchEntity cases for colors, factories, importers, cards-wb, cards-ozon, certs using matrixApi.getEntity or a generic fetch"
  - truth: "After saving a field change in the detail panel, the table row shows the updated value without full page reload"
    status: partial
    reason: "handleSave in detail-panel.tsx throws 'Unknown entity type' for the 6 secondary entities (colors, factories, importers, cards-wb, cards-ozon, certs). notifyEntityUpdated is never called for those, so table refetch never fires."
    artifacts:
      - path: "wookiee-hub/src/components/matrix/detail-panel.tsx"
        issue: "handleSave switch handles only models/articles/products, throws for remaining 6 types (line 180: throw new Error(`Unknown entity type`))"
    missing:
      - "Generic PATCH path in handleSave using getBackendType(detailPanelEntityType) for the 6 secondary entity types"
      - "matrixApi.updateEntity or equivalent generic update method, OR individual update methods for colors/factories/importers/cards-wb/cards-ozon/certs"
human_verification:
  - test: "Open a Colors row in the matrix table, verify the detail panel loads data (not blank)"
    expected: "Detail panel shows color fields (name, etc.)"
    why_human: "fetchEntity returns null for colors — panel may show loading spinner indefinitely or an empty state"
  - test: "Edit a field in the detail panel for a Factories row and save"
    expected: "Save succeeds and the factories table row updates without reload"
    why_human: "handleSave throws for factories — need to observe the actual error behavior in UI"
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The codebase has a single, correct source of truth for entity routing; the detail panel dispatches to the right API endpoint for every entity type; and table rows automatically reflect panel saves
**Verified:** 2026-03-28T19:45:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All 4 entity maps replaced — changing one registry entry updates ManageFieldsDialog, MassEditBar, and panel/types consumers | VERIFIED | ENTITY_TYPE_MAP, ENTITY_TO_DB, ENTITY_BACKEND_MAP deleted from real source files; all 3 consumers import getBackendType from entity-registry.ts |
| 2 | getBackendType('articles') returns 'artikuly' for every slug in the union | VERIFIED | entity-registry.ts lines 23-26; 9/9 slugs covered with correct plural forms |
| 3 | Test suite validates all 9 entity slugs map correctly | VERIFIED | entity-registry.test.ts: 14 tests covering all 9 slugs, labels, and completeness check |
| 4 | Opening detail panel for an Artikul or Tovar row fetches from the correct endpoint | PARTIAL | articles and products routed correctly; fetchEntity returns null for colors, factories, importers, cards-wb, cards-ozon, certs (detail-panel.tsx line 25) |
| 5 | Opening detail panel from global search result dispatches to correct entity API | PARTIAL | global-search.tsx passes correct page (MatrixEntity slug) to openDetailPanel; but detail-panel.tsx fetchEntity ignores all but 3 entity types |
| 6 | After saving a field change in the detail panel, the table row shows the updated value without full page reload | PARTIAL | Works for models/articles/products only; handleSave throws Error("Unknown entity type") for the 6 secondary entities |
| 7 | entityUpdateStamp increments are scoped per entity — saving an article does not cause models table to refetch | VERIFIED | notifyEntityUpdated uses per-entity key in Partial<Record<MatrixEntity, number>>; tests confirm scoped increments |

**Score:** 5/7 truths verified (2 partial, blocking goal)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `wookiee-hub/src/lib/entity-registry.ts` | Single entity registry with ENTITY_REGISTRY, getBackendType, getEntityLabel, EntityRegistryEntry | VERIFIED | 79 lines; exports all 4 symbols; 9/9 entity slugs with backendType, label, titleField |
| `wookiee-hub/src/lib/__tests__/entity-registry.test.ts` | Unit tests for entity registry mappings (min 20 lines) | VERIFIED | 69 lines; 14 tests; all 9 slugs tested; completeness test included |
| `wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts` | Routing tests (min 25 lines) | VERIFIED | 46 lines; 4 real tests (not stubs); covers entityType set, preserved, reset, overwrite |
| `wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts` | Stamp increment tests (min 25 lines) | VERIFIED | 38 lines; 4 tests; covers init, increment, monotonic, scoped isolation |
| `wookiee-hub/src/stores/matrix-store.ts` | entityUpdateStamp state + notifyEntityUpdated action | VERIFIED | Lines 33, 51, 65, 114-118; correct Partial<Record<MatrixEntity, number>> pattern |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| manage-fields-dialog.tsx | entity-registry.ts | import { getBackendType } | WIRED | Line 20: import; line 51: getBackendType(entity as MatrixEntity) |
| mass-edit-bar.tsx | entity-registry.ts | import { getBackendType } | WIRED | Line 5: import; line 15: getBackendType(activeEntity) |
| panel/types.ts | entity-registry.ts | export { getBackendType } | WIRED | Line 54: re-export; panel-body.tsx consumes via types |
| articles-page.tsx | matrix-store.ts | openDetailPanel(id, 'articles') | WIRED | Line 74: onRowClick wrapper; line 52: handleCreated |
| products-page.tsx | matrix-store.ts | openDetailPanel(id, 'products') | WIRED | Line 73: onRowClick wrapper; line 51: handleCreated |
| models-page.tsx | matrix-store.ts | openDetailPanel(id, 'models') | WIRED | Line 232: onRowClick wrapper; line 173: handleCreated |
| colors-page.tsx | matrix-store.ts | openDetailPanel(id, 'colors') | WIRED | Line 38: onRowClick wrapper |
| factories-page.tsx | matrix-store.ts | openDetailPanel(id, 'factories') | WIRED | Line 35: onRowClick wrapper |
| importers-page.tsx | matrix-store.ts | openDetailPanel(id, 'importers') | WIRED | Line 37: onRowClick wrapper |
| cards-wb-page.tsx | matrix-store.ts | openDetailPanel(id, 'cards-wb') | WIRED | Line 35: onRowClick wrapper |
| cards-ozon-page.tsx | matrix-store.ts | openDetailPanel(id, 'cards-ozon') | WIRED | Line 35: onRowClick wrapper |
| certs-page.tsx | matrix-store.ts | openDetailPanel(id, 'certs') | WIRED | Line 39: onRowClick wrapper |
| global-search.tsx | matrix-store.ts | openDetailPanel(result.id, page) | WIRED | Line 85: passes MatrixEntity slug via ENTITY_TO_PAGE lookup |
| detail-panel.tsx | matrix-store.ts | notifyEntityUpdated after save | PARTIAL | Line 71: selector wired; line 185: called — but only reachable for models/articles/products; lines 173-181 throw for 6 others |
| articles-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 24: selector; line 46: in dep array |
| products-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 23: selector; line 45: in dep array |
| models-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 52: selector; line 155: in dep array |
| colors-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 21: selector; line 25: in dep array |
| factories-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 18: selector; line 22: in dep array |
| importers-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 20: selector; line 24: in dep array |
| cards-wb-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 18: selector; line 22: in dep array |
| cards-ozon-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 18: selector; line 22: in dep array |
| certs-page.tsx | matrix-store.ts | entityUpdateStamp in useApiQuery deps | WIRED | Line 22: selector; line 26: in dep array |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FOUND-01 | 01-01-PLAN.md | Entity registry — единый источник истины для маппинга entity keys (консолидация 4 параллельных entity maps) | SATISFIED | entity-registry.ts created; ENTITY_TYPE_MAP, ENTITY_TO_DB, ENTITY_BACKEND_MAP deleted from real source files; all 3 consumers wired via getBackendType |
| FOUND-02 | 01-02-PLAN.md | DetailPanel корректно роутит запросы для всех типов сущностей (не только models) | BLOCKED | Call sites pass entityType correctly (all 9 pages); but detail-panel.tsx fetchEntity returns null for 6/9 entity types. "Not found" bug partially fixed (models/articles/products work), 6 secondary types still blank. |
| FOUND-03 | 01-02-PLAN.md | Entity cache с update propagation — после PATCH в panel таблица автоматически обновляется | BLOCKED | entityUpdateStamp wired in all 9 pages; notifyEntityUpdated wired in detail-panel; but handleSave throws before reaching notifyEntityUpdated for 6/9 entity types. Works for models/articles/products only. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| detail-panel.tsx | 22-25 | fetchEntity falls through to `return Promise.resolve(null)` for 6 entity types | Blocker | Panel shows blank/loading for colors, factories, importers, cards-wb, cards-ozon, certs |
| detail-panel.tsx | 173-181 | handleSave if/else chain throws `Unknown entity type` for 6 entity types | Blocker | Save fails silently (error shown in saveError state) for 6/9 entity types; notifyEntityUpdated never called |
| entity-detail-page.tsx | 19-30 | Contains local ENTITY_LABELS map with different keys (models_osnova, cards_wb with underscore) | Info | Separate routing path for full-page entity detail (not the slide-over panel); not a duplicate of entity-registry concern but worth tracking |

### Human Verification Required

#### 1. Detail Panel Opens for Secondary Entity

**Test:** Click any row in the Colors, Factories, or Importers table
**Expected:** Detail panel opens and shows entity fields
**Why human:** fetchEntity returns `Promise.resolve(null)` for these types — need to observe whether this renders an empty panel, a loading spinner, or an error state

#### 2. Save Works for Secondary Entity

**Test:** Open a Colors row in detail panel, enter edit mode, change a field, click Save
**Expected:** Save succeeds; table row updates
**Why human:** handleSave throws `Error("Unknown entity type")` at line 180 — the saveError state will render an error message; need to confirm error UX

### Gaps Summary

FOUND-01 is fully achieved: entity-registry.ts is the single source of truth, all inline maps deleted, all consumers wired. Tests green.

FOUND-02 and FOUND-03 are **structurally wired but incomplete at the implementation layer**. The call-site half of both requirements is done — all 9 entity pages pass `entityType` to `openDetailPanel`, and all 9 pages subscribe to `entityUpdateStamp`. The store half is also done — `notifyEntityUpdated` exists and increments correctly.

The gap is inside `detail-panel.tsx` itself:

1. `fetchEntity` (lines 17-26) only dispatches API calls for `models`, `articles`, `products`. The other 6 types hit `return Promise.resolve(null)`, producing a blank panel — the routing bug is NOT fixed for those 6.

2. `handleSave` (lines 147-195) only handles the same 3 types. Any save attempt on a secondary entity throws, which means `notifyEntityUpdated` is never called and the table never refetches.

Both gaps share a single root cause: `detail-panel.tsx` was only extended to cover 3 of 9 entity types. A generic fetch path (`get('/api/matrix/${getBackendType(entityType)}/${id}')`) and a generic PATCH path would close both gaps for the 6 secondary entities.

---

_Verified: 2026-03-28T19:45:00Z_
_Verifier: Claude (gsd-verifier)_
