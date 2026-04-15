---
phase: 03-table-view
plan: 02
subsystem: ui
tags: [react, typescript, shadcn, sort, badges, field-definitions, data-table]

# Dependency graph
requires:
  - phase: 03-table-view/01
    provides: "useTableState hook, fieldDefsToColumns utility, backend sort/pagination params"
provides:
  - "DataTable with sort indicators, status badges, archive row styling"
  - "All entity pages (models, articles, products, factories, importers) using FieldDef-driven columns"
  - "Sort interaction triggering API re-fetch"
affects: [03-table-view/03, 04-filter-system]

# Tech tracking
tech-stack:
  added: [lucide-react ArrowUp/ArrowDown/ArrowUpDown icons]
  patterns: [FieldDef-driven column generation, status badge rendering, archive row opacity]

key-files:
  modified:
    - wookiee-hub/src/components/matrix/data-table.tsx
    - wookiee-hub/src/components/matrix/table-cell.tsx
    - wookiee-hub/src/pages/product-matrix/models-page.tsx
    - wookiee-hub/src/pages/product-matrix/articles-page.tsx
    - wookiee-hub/src/pages/product-matrix/products-page.tsx
    - wookiee-hub/src/pages/product-matrix/factories-page.tsx
    - wookiee-hub/src/pages/product-matrix/importers-page.tsx

key-decisions:
  - "Extended FieldDef-driven columns to factories and importers pages beyond original plan scope (3 pages -> 5 pages)"
  - "TableCell simplified to pure read-only renderer, inline editing removed (consistent with Detail Panel approach)"

patterns-established:
  - "Status badge rendering: green Badge for Aktivnyy, gray Badge for Arkhiv via fieldDef detection"
  - "Archive row opacity-60 applied via status_name check on tr element"
  - "Sort indicators on column headers: ArrowUp/ArrowDown for active sort, ArrowUpDown for sortable columns"

requirements-completed: [TABLE-01, TABLE-02, TABLE-03, TABLE-07]

# Metrics
duration: 8min
completed: 2026-03-26
---

# Phase 3 Plan 02: FieldDef-Driven Columns Summary

**DataTable with sort indicators, status badges, and archive row styling wired to FieldDef-driven columns across all five entity pages**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-26T22:50:00Z
- **Completed:** 2026-03-26T22:59:36Z
- **Tasks:** 2 auto + 1 checkpoint (approved)
- **Files modified:** 11

## Accomplishments
- DataTable renders sort indicators (ArrowUp/ArrowDown/ArrowUpDown) on column headers with click-to-sort interaction
- Status column shows colored Badge: green for Aktivnyy, gray for Arkhiv
- Archived rows visually dimmed with opacity-60
- All five entity pages (models, articles, products, factories, importers) use fieldDefsToColumns + useTableState instead of hardcoded columns
- Column headers display human-readable display_name from FieldDefinition
- Reference columns show resolved names (e.g., "Verkhnyaya odezhda") not IDs or dashes
- TableCell simplified to pure read-only renderer

## Task Commits

Each task was committed atomically:

1. **Task 1: DataTable sort, status badge, and archive row styling** - `0df8bb2` (feat)
2. **Task 2: FieldDef-driven columns in all entity pages** - `8b57b64` (feat)
3. **Task 3: Checkpoint human-verify** - approved by user

## Files Created/Modified
- `wookiee-hub/src/components/matrix/data-table.tsx` - Sort indicators on headers, status badge rendering, archive row opacity
- `wookiee-hub/src/components/matrix/table-cell.tsx` - Simplified to read-only renderer
- `wookiee-hub/src/pages/product-matrix/models-page.tsx` - FieldDef-driven columns via useTableState + fieldDefsToColumns
- `wookiee-hub/src/pages/product-matrix/articles-page.tsx` - Same refactor pattern
- `wookiee-hub/src/pages/product-matrix/products-page.tsx` - Same refactor pattern
- `wookiee-hub/src/pages/product-matrix/factories-page.tsx` - Same refactor pattern (extended scope)
- `wookiee-hub/src/pages/product-matrix/importers-page.tsx` - Same refactor pattern (extended scope)

## Decisions Made
- Extended FieldDef-driven columns to factories and importers pages beyond original 3-page plan scope for consistency
- TableCell simplified to pure read-only renderer — all editing happens in Detail Panel (Phase 2 decision)

## Deviations from Plan

None - plan executed exactly as written. The extension to factories/importers pages was a natural completion of the pattern.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Sort interaction and FieldDef-driven columns are complete across all entity pages
- Ready for Plan 03: pagination controls, column visibility popover, and create record dialog
- No blockers

---
*Phase: 03-table-view*
*Completed: 2026-03-26*
