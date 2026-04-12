---
phase: 02-detail-panel
plan: 03
subsystem: ui
tags: [react, typescript, shadcn, zustand, react-day-picker, date-fns]

requires:
  - phase: 02-detail-panel/02-02
    provides: PanelFieldRow read mode, PanelBody, PanelHeader, PanelSection, lookupCache in Zustand

provides:
  - PanelFieldRow edit mode with correct input per field_type (text, number, select, textarea, checkbox, date via Calendar+Popover)
  - PanelSaveBar component with Save/Cancel and loading/disabled states
  - detail-panel.tsx full edit state management: isEditing, editState, saving, saveError
  - Lookup prefetch via Promise.allSettled across all 7 tables on panel open
  - PATCH save with field-level diff (only changed fields sent), server response merge as localData
  - PanelBody threaded with editState, onChange, lookupCache
  - PanelHeader hides "Редактировать" while editing, shows "Редактирование..." indicator

affects: [02-detail-panel/02-04, 02-detail-panel/02-05]

tech-stack:
  added: []
  patterns:
    - "Calendar+Popover date picker pattern: no native date input, use react-day-picker Calendar inside shadcn Popover"
    - "Field-level diff on save: iterate editState, skip id and _name fields, compare against original data"
    - "localData override pattern: successful PATCH response stored in localData state, overrides fetchedData from useApiQuery"
    - "Lookup prefetch via Promise.allSettled: fetch all missing tables in parallel, skip cached, setLookupCache each result independently"

key-files:
  created:
    - wookiee-hub/src/components/matrix/panel/panel-save-bar.tsx
  modified:
    - wookiee-hub/src/components/matrix/panel/panel-field-row.tsx
    - wookiee-hub/src/components/matrix/detail-panel.tsx
    - wookiee-hub/src/components/matrix/panel/panel-body.tsx
    - wookiee-hub/src/components/matrix/panel/panel-header.tsx

key-decisions:
  - "useApiQuery has no refetch; after save, merge server response as localData state override instead of re-fetching"
  - "sonner not installed; show error inline below panel body instead of toast notification"
  - "PanelHeader hides edit button while editing (save bar in bottom handles cancel); shows Редактирование... indicator text"
  - "Sensitive fields (kod, artikul, barkod_perehod, tnved) get subtle amber tint in edit mode — no hard block, visual warning only"
  - "lookupCacheRef pattern used to avoid stale closure in prefetchLookups without adding lookupCache to useEffect deps"

requirements-completed: [PANEL-04, PANEL-05, PANEL-06]

duration: 18min
completed: 2026-03-25
---

# Phase 2 Plan 03: Edit Mode — Form Editing with Inputs, Lookups, Save/Cancel Summary

**Toggle-mode edit form for the detail panel: per-field input types (text/number/select/textarea/checkbox/Calendar-date), lookup-populated selects from Zustand cache, PATCH-on-save with field diff, and sticky PanelSaveBar**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-25T19:40:00Z
- **Completed:** 2026-03-25T19:58:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- PanelFieldRow renders the correct input type per field_type when isEditing=true; date fields use Calendar component in Popover (react-day-picker), never native `<input type="date">`
- PanelSaveBar is a sticky bottom component with disabled Save when no changes and Loader2 spinner during PATCH
- detail-panel.tsx manages full edit lifecycle: clone data into editState on enter, diff on save, merge response as localData, reset on cancel/close
- Lookup prefetch runs in parallel via Promise.allSettled on panel open; cached tables are skipped; each table stored independently so partial failures don't block others
- PanelHeader hides the "Редактировать" button during edit mode and shows "Редактирование..." indicator; close button always visible

## Task Commits

1. **Task 1: Add edit inputs to PanelFieldRow and create PanelSaveBar** - `52eab73` (feat)
2. **Task 2: Wire edit state, lookup prefetch, and save/cancel flow** - `2f00084` (feat)

## Files Created/Modified

- `wookiee-hub/src/components/matrix/panel/panel-field-row.tsx` — Extended with renderEditInput() switch on field_type; immutable/system fields stay read-only with lock icon; inherited fields keep popover; sensitive fields get amber tint
- `wookiee-hub/src/components/matrix/panel/panel-save-bar.tsx` — New sticky bottom bar with "Отменить" / "Сохранить" buttons, disabled + loading states
- `wookiee-hub/src/components/matrix/detail-panel.tsx` — Full edit state management (isEditing, editState, saving, saveError, localData); prefetchLookups via Promise.allSettled; handleSave with PATCH dispatch; handleCancel
- `wookiee-hub/src/components/matrix/panel/panel-body.tsx` — Accepts editState, onChange, lookupCache; resolves editValue and lookupOptions per field; passes them to PanelFieldRow
- `wookiee-hub/src/components/matrix/panel/panel-header.tsx` — Hides "Редактировать" button in edit mode; shows "Редактирование..." indicator

## Decisions Made

- `useApiQuery` does not expose a `refetch` function — after a successful PATCH, the server response is stored in `localData` state as an override. This gives immediate UI update without triggering a full refetch cycle.
- `sonner` is not installed in the project — save errors are shown inline below the panel body with a `text-destructive` class rather than a toast.
- PanelHeader hides the "Редактировать" button while editing because Save/Cancel in PanelSaveBar serve as the exit controls. The X close button always remains visible.
- `lookupCacheRef` pattern (a ref tracking the latest `lookupCache`) is used inside `prefetchLookups` to avoid a stale closure, while keeping the `useEffect` dependency minimal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] useApiQuery lacks refetch — localData override pattern instead**
- **Found during:** Task 2 (detail-panel.tsx save flow)
- **Issue:** Plan specified `refetch()` after successful save, but `useApiQuery` only returns `data/loading/error` with no `refetch` method
- **Fix:** Store successful PATCH response as `localData` state; component renders `localData ?? fetchedData` so the panel immediately shows updated values
- **Files modified:** wookiee-hub/src/components/matrix/detail-panel.tsx
- **Verification:** TypeScript compiles without errors; `localData` is reset on panel close/entity change
- **Committed in:** 2f00084 (Task 2 commit)

**2. [Rule 1 - Bug] toast/sonner not available — inline error display**
- **Found during:** Task 2 (error handling in handleSave)
- **Issue:** Plan mentioned "show error toast or inline error"; sonner is not in package.json
- **Fix:** Show inline `text-destructive` error text above PanelSaveBar; no toast dependency needed
- **Files modified:** wookiee-hub/src/components/matrix/detail-panel.tsx
- **Verification:** TypeScript compiles; no import errors
- **Committed in:** 2f00084 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug/missing capability in existing hooks)
**Impact on plan:** Both fixes are pragmatic adaptations to the existing hook API. Behavior is equivalent: data updates immediately after save, errors are visible to the user.

## Issues Encountered

- `wookiee-hub/` is a separate git repository (not a subdirectory tracked by the parent repo), so all commits are made with `cd wookiee-hub && git ...`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Edit mode fully functional: toggle, per-field inputs, lookup selects, Calendar date picker, save/cancel with PATCH diff
- Ready for Phase 02-04 (validation layer — required fields, format constraints, form submit guard)
- Lookup cache is populated on first panel open; subsequent opens are instant

---
*Phase: 02-detail-panel*
*Completed: 2026-03-25*

## Self-Check: PASSED

- FOUND: panel-field-row.tsx
- FOUND: panel-save-bar.tsx
- FOUND: detail-panel.tsx
- FOUND: panel-body.tsx
- FOUND: panel-header.tsx
- FOUND: 02-03-SUMMARY.md
- FOUND: commit 52eab73 (Task 1)
- FOUND: commit 2f00084 (Task 2)
