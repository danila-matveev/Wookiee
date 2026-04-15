---
phase: 02-detail-panel
plan: 04
subsystem: ui
tags: [react, zustand, typescript, base-ui, collapsible, badge]

# Dependency graph
requires:
  - phase: 02-detail-panel/02-02
    provides: PanelHeader, PanelBody, PanelSection collapsible pattern
  - phase: 02-detail-panel/02-03
    provides: edit state management, detail-panel.tsx structure

provides:
  - PanelRelated component: collapsible children list at panel bottom with parent link
  - PanelHeader badge counters for related entity counts (Артикулы, Товары)
  - Navigation: badge click switches entity tab; child row click opens child in panel

affects: [phase-03-filters, phase-04-filter-by-parent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RelatedCount[] prop pattern for passing navigation targets to header badges"
    - "Nested useApiQuery per entity relationship level (ArticlesChildren, ProductsChildren sub-components)"
    - "setActiveEntity + closeDetailPanel combo for tab-switch navigation from panel"

key-files:
  created:
    - wookiee-hub/src/components/matrix/panel/panel-related.tsx
  modified:
    - wookiee-hub/src/components/matrix/panel/panel-header.tsx
    - wookiee-hub/src/components/matrix/detail-panel.tsx
    - wookiee-hub/src/components/matrix/panel/panel-body.tsx

key-decisions:
  - "PanelRelated uses sub-components (ArticlesChildren, ProductsChildren) with their own useApiQuery — keeps each fetch self-contained"
  - "PanelBody overflow-y-auto removed; outer wrapper in detail-panel.tsx handles scroll for PanelBody+PanelRelated together"
  - "Badge click defers parent-ID filtering to Phase 4 — only switches entity type tab for now"

patterns-established:
  - "Related nav: setActiveEntity(childEntityType) + closeDetailPanel() for tab-switch from panel badge"
  - "openDetailPanel(id, entityType) for panel-to-panel navigation within child rows"

requirements-completed: [PANEL-08]

# Metrics
duration: 5min
completed: 2026-03-25
---

# Phase 2 Plan 04: Related Entities Summary

**Badge counters in detail panel header plus collapsible children list at bottom, enabling Model->Articles->Products navigation without leaving the panel**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-25T19:44:58Z
- **Completed:** 2026-03-25T19:49:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created PanelRelated component: collapsible children section (first 5 rows) with parent entity link and "Показать все (N)" button
- Added relatedCounts badge rendering to PanelHeader — each badge click switches the entity type tab
- Wired PanelRelated into detail-panel.tsx inside shared scrollable wrapper with PanelBody
- Fixed scroll architecture: removed PanelBody's own overflow-y-auto so both PanelBody and PanelRelated scroll together

## Task Commits

1. **Task 1: Create PanelRelated component** - `ca9ae26` (feat)
2. **Task 2: Add badge counters and wire PanelRelated** - `0e483a1` (feat)

## Files Created/Modified

- `wookiee-hub/src/components/matrix/panel/panel-related.tsx` - New component: parent link, collapsible children list, "Показать все" navigation
- `wookiee-hub/src/components/matrix/panel/panel-header.tsx` - Added RelatedCount[] prop and Badge rendering below title
- `wookiee-hub/src/components/matrix/detail-panel.tsx` - Computes relatedCounts, passes to PanelHeader, renders PanelRelated
- `wookiee-hub/src/components/matrix/panel/panel-body.tsx` - Removed own overflow-y-auto (outer wrapper handles scroll now)

## Decisions Made

- PanelRelated uses dedicated sub-components (ArticlesChildren, ProductsChildren) rather than one unified component with conditional logic — keeps each fetch isolated and readable
- Removed PanelBody's `overflow-y-auto flex-1` to allow PanelRelated to appear in the same scrollable flow; outer wrapper in detail-panel.tsx now owns scrolling
- Badge + "Показать все" clicks only switch entity tab (no parent ID filtering) — filtering by parent ID is deferred to Phase 4 per plan spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed PanelBody's conflicting overflow-y-auto**
- **Found during:** Task 2 (wiring PanelRelated into detail-panel)
- **Issue:** PanelBody had `overflow-y-auto flex-1` which would absorb all vertical space, pushing PanelRelated outside the visible scroll area
- **Fix:** Changed PanelBody's root div to `flex-1` only; outer wrapper in detail-panel.tsx owns `overflow-y-auto flex-1`
- **Files modified:** wookiee-hub/src/components/matrix/panel/panel-body.tsx
- **Verification:** TypeScript clean; PanelRelated now renders in same scrollable container as field sections
- **Committed in:** `0e483a1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (scroll architecture correction)
**Impact on plan:** Essential for correct rendering of PanelRelated below PanelBody fields. No scope creep.

## Issues Encountered

- wookiee-hub is a nested git repo (has its own .git) — commits go inside wookiee-hub/, not the root repo. Both repos now committed correctly.

## Next Phase Readiness

- Related entity navigation fully wired: Model->Articles->Products navigation possible via panel badges and child rows
- Phase 4 (filter by parent): when user clicks "Показать все" or badge, they land on the child entity tab; Phase 4 can add URL-based or Zustand filter-by-parent logic on top

---
*Phase: 02-detail-panel*
*Completed: 2026-03-25*
