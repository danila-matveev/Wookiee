---
phase: 01-foundation
plan: 01
subsystem: ui
tags: [react, typescript, zustand, vitest, entity-registry]

# Dependency graph
requires: []
provides:
  - "entity-registry.ts — single source of truth for MatrixEntity slug → backend type mappings"
  - "getBackendType helper — all 9 entities covered, replaces 3 deleted inline maps"
  - "getEntityLabel helper — Russian display labels per entity"
  - "Wave 0 test stubs for FOUND-02 (detail-panel-routing) and FOUND-03 (entity-update-stamp)"
affects:
  - 01-02
  - 02-detail-panel
  - panel-body
  - manage-fields-dialog
  - mass-edit-bar

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Centralized entity registry pattern: single Record<MatrixEntity, EntityRegistryEntry> replaces scattered inline maps"
    - "Re-export pattern in panel/types.ts: getBackendType forwarded from entity-registry to preserve existing import paths for consumers"
    - "Wave 0 TDD stubs: it.todo() stubs committed before implementation to anchor future test-driven work"

key-files:
  created:
    - wookiee-hub/src/lib/entity-registry.ts
    - wookiee-hub/src/lib/__tests__/entity-registry.test.ts
    - wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts
    - wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts
  modified:
    - wookiee-hub/src/components/matrix/manage-fields-dialog.tsx
    - wookiee-hub/src/components/matrix/mass-edit-bar.tsx
    - wookiee-hub/src/components/matrix/panel/types.ts
    - wookiee-hub/src/components/matrix/panel/panel-body.tsx
    - wookiee-hub/src/pages/product-matrix/products-page.tsx
    - wookiee-hub/src/pages/product-matrix/articles-page.tsx

key-decisions:
  - "All backendType values use plural forms (modeli_osnova, artikuly, etc.) matching mass-edit-bar's existing convention — manage-fields-dialog previously used singular forms (model_osnova, artikul) which were inconsistent"
  - "panel/types.ts re-exports getBackendType from entity-registry rather than importing directly, preserving existing import paths for panel-body.tsx"
  - "products-page.tsx and articles-page.tsx fixed as Rule 3 blocking deviation — they imported ENTITY_BACKEND_MAP which was removed"

patterns-established:
  - "Entity slug consumers: always import getBackendType from @/lib/entity-registry (or via @/components/matrix/panel/types re-export)"
  - "New entity slugs: add to MatrixEntity type in matrix-store.ts AND ENTITY_REGISTRY in entity-registry.ts"

requirements-completed: [FOUND-01]

# Metrics
duration: 10min
completed: 2026-03-28
---

# Phase 1 Plan 01: Entity Registry Summary

**Single entity-registry.ts module replaces 3 divergent inline maps, covering all 9 MatrixEntity slugs with plural backend types, Russian labels, and title fields**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-28T18:40:00Z
- **Completed:** 2026-03-28T18:50:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created `entity-registry.ts` as single source of truth with `ENTITY_REGISTRY`, `getBackendType`, `getEntityLabel` exports
- Deleted `ENTITY_TYPE_MAP` (singular forms), `ENTITY_TO_DB`, and `ENTITY_BACKEND_MAP` from their respective files
- 14 unit tests passing (all 9 entity slug mappings verified)
- Wave 0 `it.todo()` test stubs created for FOUND-02 and FOUND-03

## Task Commits

1. **Task 1: Create entity-registry.ts and unit tests** - `d285947` (feat + test)
2. **Task 2: Replace 3 inline entity maps** - `d8c9986` (feat)

## Files Created/Modified

- `wookiee-hub/src/lib/entity-registry.ts` — EntityRegistryEntry interface, ENTITY_REGISTRY map, getBackendType, getEntityLabel, EntitySlug re-export
- `wookiee-hub/src/lib/__tests__/entity-registry.test.ts` — 14 unit tests for all 9 slugs
- `wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts` — Wave 0 stubs for FOUND-02
- `wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts` — Wave 0 stubs for FOUND-03
- `wookiee-hub/src/components/matrix/manage-fields-dialog.tsx` — deleted ENTITY_TYPE_MAP, import getBackendType
- `wookiee-hub/src/components/matrix/mass-edit-bar.tsx` — deleted ENTITY_TO_DB, import getBackendType
- `wookiee-hub/src/components/matrix/panel/types.ts` — deleted ENTITY_BACKEND_MAP, re-export getBackendType
- `wookiee-hub/src/components/matrix/panel/panel-body.tsx` — updated to use getBackendType (Rule 3 fix)
- `wookiee-hub/src/pages/product-matrix/products-page.tsx` — updated to use getBackendType (Rule 3 fix)
- `wookiee-hub/src/pages/product-matrix/articles-page.tsx` — updated to use getBackendType (Rule 3 fix)

## Decisions Made

- All backendType values use plural forms (modeli_osnova, artikuly, etc.) — `manage-fields-dialog` previously used inconsistent singular forms which are now normalized
- `panel/types.ts` re-exports `getBackendType` rather than deleting it, so `panel-body.tsx` keeps its existing import path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed 3 additional consumers of deleted ENTITY_BACKEND_MAP**
- **Found during:** Task 2 (Replace 3 inline entity maps)
- **Issue:** `panel-body.tsx`, `products-page.tsx`, and `articles-page.tsx` imported `ENTITY_BACKEND_MAP` from `panel/types.ts` — which was deleted as part of Task 2. TypeScript would fail at build.
- **Fix:** Updated all 3 files to use `getBackendType` directly from entity-registry (products/articles pages) or via types re-export (panel-body)
- **Files modified:** panel-body.tsx, products-page.tsx, articles-page.tsx
- **Verification:** `grep -rn "ENTITY_BACKEND_MAP"` returns zero matches in real source files; TypeScript shows no new errors
- **Committed in:** d8c9986 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking)
**Impact on plan:** Fix was necessary to maintain a compiling codebase after map deletion. No scope creep.

## Issues Encountered

- macOS " 2.ts" file duplicates in `node_modules` cause pre-existing TS2688 errors on `tsc --noEmit` — these are not related to this plan's changes and were present before execution.

## Next Phase Readiness

- `entity-registry.ts` ready for consumption by plan 01-02 (detail panel routing store fields)
- Wave 0 stubs in `stores/__tests__/` anchor TDD work for FOUND-02 and FOUND-03

## Self-Check: PASSED

All 7 files verified present. Both commits (d285947, d8c9986) confirmed in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-28*
