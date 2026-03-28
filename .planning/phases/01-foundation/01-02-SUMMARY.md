---
phase: 01-foundation
plan: 02
subsystem: ui
tags: [react, typescript, zustand, detail-panel, entity-routing, cache-invalidation]

# Dependency graph
requires:
  - "01-01: entity-registry.ts with getBackendType, MatrixEntity type, entityUpdateStamp + notifyEntityUpdated in matrix-store"
provides:
  - "All 9 entity pages pass entityType to openDetailPanel — panel routes to correct API endpoint"
  - "Global search passes entityType on result selection — panel works from search"
  - "detail-panel.tsx calls notifyEntityUpdated after save — table rows auto-refetch"
  - "All 9 entity pages include entityUpdateStamp in useApiQuery deps — scoped refetch on save"
affects:
  - 02-detail-panel
  - panel-body
  - future entity pages

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Entity page onRowClick pattern: onRowClick={(id) => openDetailPanel(id, 'entity-slug')} — never pass openDetailPanel directly"
    - "Entity-scoped cache invalidation: useMatrixStore((s) => s.entityUpdateStamp['slug'] ?? 0) in useApiQuery deps"
    - "Panel save propagation: notifyEntityUpdated(detailPanelEntityType) after successful PATCH"

key-files:
  created: []
  modified:
    - wookiee-hub/src/pages/product-matrix/articles-page.tsx
    - wookiee-hub/src/pages/product-matrix/products-page.tsx
    - wookiee-hub/src/pages/product-matrix/models-page.tsx
    - wookiee-hub/src/pages/product-matrix/colors-page.tsx
    - wookiee-hub/src/pages/product-matrix/factories-page.tsx
    - wookiee-hub/src/pages/product-matrix/importers-page.tsx
    - wookiee-hub/src/pages/product-matrix/cards-wb-page.tsx
    - wookiee-hub/src/pages/product-matrix/cards-ozon-page.tsx
    - wookiee-hub/src/pages/product-matrix/certs-page.tsx
    - wookiee-hub/src/components/matrix/global-search.tsx
    - wookiee-hub/src/components/matrix/detail-panel.tsx
    - wookiee-hub/src/stores/matrix-store.ts

key-decisions:
  - "notifyEntityUpdated called inside handleSave try block (after setLocalData, before setIsEditing) — ensures stamp increments only on successful save"
  - "Secondary entity pages (colors, factories, etc.) use [entityUpdateStamp] as sole useApiQuery dep since they have no pagination/sort/filter state"

patterns-established:
  - "Every openDetailPanel call site must pass entityType as second argument — grep for bare onRowClick={openDetailPanel} to detect regressions"
  - "New entity pages must include entityUpdateStamp selector and add it to useApiQuery deps array"

requirements-completed: [FOUND-02, FOUND-03]

# Metrics
duration: 3min
completed: 2026-03-28
---

# Phase 1 Plan 02: Detail Panel Routing + Cache Invalidation Summary

**All 9 entity pages wire entityType to openDetailPanel, detail-panel triggers notifyEntityUpdated on save, and entityUpdateStamp in useApiQuery deps auto-refetches table rows**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-28T19:07:19Z
- **Completed:** 2026-03-28T19:10:23Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Fixed detail panel routing for all 9 entity types — panel no longer shows "Not found" for non-model entities (FOUND-02)
- Added entity-scoped cache invalidation — table rows auto-refetch after panel save without page reload (FOUND-03)
- Global search now passes entityType when opening detail panel from search results
- 28 unit tests passing across all test files (registry, routing, stamp, filters)

## Task Commits

1. **Task 1: entityUpdateStamp + notifyEntityUpdated + routing tests** - `5d863b9` (feat — committed in prior session as part of Plan 01 wave)
2. **Task 2: Wire entityType at all call sites + entityUpdateStamp deps** - `4e82abc` (feat)

## Files Created/Modified

- `wookiee-hub/src/stores/matrix-store.ts` — entityUpdateStamp state + notifyEntityUpdated action (committed in 5d863b9)
- `wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts` — 4 tests for openDetailPanel routing correctness
- `wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts` — 4 tests for stamp increment behavior
- `wookiee-hub/src/components/matrix/detail-panel.tsx` — notifyEntityUpdated selector + call after save (committed in 5d863b9)
- `wookiee-hub/src/components/matrix/global-search.tsx` — openDetailPanel(result.id, page) (committed in 5d863b9)
- `wookiee-hub/src/pages/product-matrix/articles-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/products-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/models-page.tsx` — entityUpdateStamp dep + onRowClick wrapper + handleCreated fix
- `wookiee-hub/src/pages/product-matrix/colors-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/factories-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/importers-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/cards-wb-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/cards-ozon-page.tsx` — entityUpdateStamp dep + onRowClick wrapper
- `wookiee-hub/src/pages/product-matrix/certs-page.tsx` — entityUpdateStamp dep + onRowClick wrapper

## Decisions Made

- notifyEntityUpdated is called inside the try block after setLocalData — ensures the stamp only increments on successful saves, not on errors
- Secondary entity pages (colors, factories, importers, cards-wb, cards-ozon, certs) use `[entityUpdateStamp]` as the sole useApiQuery dependency since they lack pagination/sort/filter state

## Deviations from Plan

None — plan executed exactly as written. Task 1 store and test changes were partially pre-committed in a prior session (commit 5d863b9), so this execution focused on verifying those were correct and committing the remaining Task 2 entity page wiring.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 1 Foundation is complete (FOUND-01, FOUND-02, FOUND-03 all resolved)
- Detail panel correctly routes API calls for all entity types
- Table auto-refreshes after panel saves via entity-scoped stamps
- Ready for Phase 2 (Detail Panel) work

## Self-Check: PASSED

All 14 key files verified present. Both commits (5d863b9, 4e82abc) confirmed in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-28*
