---
phase: 03-table-view
plan: 01
subsystem: api, ui
tags: [fastapi, react, sort, pagination, hooks, typescript]

# Dependency graph
requires:
  - phase: 02-detail-panel
    provides: "LOOKUP_TABLE_MAP, FieldDefinition schema, Zustand lookupCache"
provides:
  - "Backend sort+order query params on models, articles, products list endpoints"
  - "useTableState hook for page/sort/hiddenFields management"
  - "fieldDefsToColumns utility for FieldDef-to-Column conversion"
affects: [03-02-PLAN, 03-03-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sort+order params combined into field:dir format at route layer"
    - "useTableState hook owns page/sort/visibility state, exposes apiParams"
    - "fieldDefsToColumns maps _id fields to _name columns for pre-joined data"

key-files:
  created:
    - wookiee-hub/src/hooks/use-table-state.ts
    - wookiee-hub/src/lib/field-def-columns.ts
  modified:
    - services/product_matrix_api/dependencies.py
    - services/product_matrix_api/routes/models.py
    - services/product_matrix_api/routes/articles.py
    - services/product_matrix_api/routes/products.py
    - tests/product_matrix_api/test_routes_models.py

key-decisions:
  - "Invalid order param falls back to None (treated as asc) rather than returning 422"
  - "Order validation done in common_params dependency, not in FastAPI Query regex"

patterns-established:
  - "Route layer combines sort+order into CrudService field:dir format"
  - "useTableState hook pattern for table state management across entities"
  - "FieldDefColumn extends Column with fieldDef for sort/type detection"

requirements-completed: [TABLE-04, TABLE-05]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 3 Plan 01: Backend Sort/Pagination and Frontend Table Hooks Summary

**Backend sort+order query params on all list endpoints, useTableState hook for page/sort/visibility management, fieldDefsToColumns for FieldDef-driven column generation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T22:11:33Z
- **Completed:** 2026-03-26T22:17:50Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Backend list endpoints (models, articles, products) now accept `?sort=field&order=asc|desc` params
- `CommonQueryParams` extended with `order` field, invalid values fall back gracefully
- `useTableState` hook manages page, sort, hiddenFields state with ready-to-use `apiParams`
- `fieldDefsToColumns` converts FieldDefinition[] to Column[] with automatic `_id` to `_name` key mapping
- 5 new backend tests verify sort ordering, pagination, and invalid order fallback

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend sort and pagination params** - `490dff5` (test) + `9b8e25f` (feat) - TDD red/green
2. **Task 2: useTableState hook and fieldDefsToColumns utility** - `fef5ead` (feat)

**Plan metadata:** TBD (docs: complete plan)

_Note: Task 1 used TDD with separate test and implementation commits_

## Files Created/Modified
- `services/product_matrix_api/dependencies.py` - Added `order` field to CommonQueryParams
- `services/product_matrix_api/routes/models.py` - Combine sort+order into field:dir format
- `services/product_matrix_api/routes/articles.py` - Combine sort+order into field:dir format
- `services/product_matrix_api/routes/products.py` - Combine sort+order into field:dir format
- `tests/product_matrix_api/test_routes_models.py` - 5 new sort/pagination tests with DB mock
- `wookiee-hub/src/hooks/use-table-state.ts` - Table state hook (page, sort, visibility, apiParams)
- `wookiee-hub/src/lib/field-def-columns.ts` - FieldDef-to-Column converter with _name key mapping

## Decisions Made
- Invalid `order` param falls back to `None` (treated as `asc` by CrudService) rather than returning 422 validation error -- more forgiving API behavior
- Order validation done in Python dependency function rather than FastAPI Query regex -- allows graceful fallback instead of hard rejection
- `fieldDefsToColumns` receives `lookupCache` parameter for future use but currently only uses `LOOKUP_TABLE_MAP` for reference field detection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `wookiee-hub` has no committed tsconfig.json (entire directory is git-untracked), so TypeScript verification used a temporary tsconfig -- files compile cleanly with path aliases

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Backend sort+pagination infrastructure ready for frontend wiring in Plan 02
- `useTableState` and `fieldDefsToColumns` ready for DataTable integration
- Plan 02 can now build FieldDef-driven DataTable columns and pagination controls

## Self-Check: PASSED

All 7 files verified present. All 3 commits (490dff5, 9b8e25f, fef5ead) verified in git log.

---
*Phase: 03-table-view*
*Completed: 2026-03-26*
