---
phase: 02-detail-panel
plan: 00
subsystem: testing
tags: [playwright, e2e, typescript, detail-panel, fixtures]

# Dependency graph
requires: []
provides:
  - Playwright config targeting localhost:25000 with chromium + testMatch for e2e/ and tests/
  - Shared test fixtures: openDetailPanel, switchEntityType, enterEditMode, getFieldRow
  - Test stubs (fixme) for all 8 PANEL requirements (PANEL-01 through PANEL-08)
  - @playwright/test installed in wookiee-hub (was missing from node_modules)
affects:
  - 02-detail-panel (all subsequent plans depend on these stubs for verification)

# Tech tracking
tech-stack:
  added:
    - "@playwright/test@1.52.0 (installed in wookiee-hub)"
  patterns:
    - "Test stubs with test.fixme() for progressive implementation across plans"
    - "Shared fixtures file re-exporting extended test/expect"
    - "testMatch covering both e2e/ and tests/ directories in a single playwright config"

key-files:
  created:
    - wookiee-hub/tests/fixtures.ts
    - wookiee-hub/tests/detail-panel.spec.ts
  modified:
    - wookiee-hub/playwright.config.ts
    - wookiee-hub/package.json
    - wookiee-hub/package-lock.json

key-decisions:
  - "Updated playwright.config.ts to use testMatch instead of testDir so both e2e/ and tests/ directories are covered without breaking existing dashboard tests"
  - "Used test.fixme() (not test.skip) so stubs are discovered and marked in test reports as needing implementation"
  - "@playwright/test installed via npm install to fix missing package (only playwright 1.58.2 was present, which has Node 24 CLI incompatibility)"

patterns-established:
  - "Fixture pattern: shared helpers in tests/fixtures.ts exported alongside extended test/expect"
  - "Panel locator pattern: [data-slot='sheet-content'] as root selector for all panel assertions"
  - "Field locator pattern: [data-field='field_name'] or [data-testid='field-row-field_name'] with .first() fallback"

requirements-completed: [PANEL-01, PANEL-02, PANEL-03, PANEL-04, PANEL-05, PANEL-06, PANEL-07, PANEL-08]

# Metrics
duration: 9min
completed: 2026-03-25
---

# Phase 2 Plan 00: Detail Panel Test Infrastructure Summary

**Playwright config + shared fixtures + test stubs for all 8 PANEL requirements, with @playwright/test installed and 16 tests discoverable via CLI**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-25T19:18:18Z
- **Completed:** 2026-03-25T19:26:51Z
- **Tasks:** 2
- **Files modified:** 5 (playwright.config.ts, tests/fixtures.ts, tests/detail-panel.spec.ts, package.json, package-lock.json)

## Accomplishments
- Created `tests/fixtures.ts` with panel interaction helpers: openDetailPanel, switchEntityType, enterEditMode, getFieldRow
- Created `tests/detail-panel.spec.ts` with fixme stubs covering all 8 PANEL requirements (10 individual test cases)
- Updated `playwright.config.ts` to use `testMatch` covering both `e2e/` (existing) and `tests/` (new) directories
- Fixed missing `@playwright/test` dependency — only `playwright` 1.58.2 was present, which has CLI incompatibility with Node 24

## Task Commits

Each task was committed atomically (in wookiee-hub repo):

1. **Task 1: Create Playwright config and shared fixtures** - `c29ca71` (feat)
2. **Task 2: Create test stubs for PANEL-01 through PANEL-08** - `d2a0c9e` (feat)

## Files Created/Modified
- `wookiee-hub/playwright.config.ts` - Changed testDir to testMatch pattern covering e2e/ and tests/, set trace to on-first-retry
- `wookiee-hub/tests/fixtures.ts` - Shared helpers: openDetailPanel (waits for [data-slot="sheet-content"]), switchEntityType, enterEditMode, getFieldRow; re-exports test/expect
- `wookiee-hub/tests/detail-panel.spec.ts` - 10 test.fixme stubs across 8 describe blocks for PANEL-01 through PANEL-08
- `wookiee-hub/package.json` - Added @playwright/test@1.52.0 to devDependencies
- `wookiee-hub/package-lock.json` - Updated lock file

## Decisions Made
- Used `testMatch` pattern instead of changing `testDir` — preserves existing `e2e/` tests without configuration conflicts
- Used `test.fixme()` annotations so stubs appear in test listings and reports as "needs implementation" rather than silently skipping
- Panel root locator `[data-slot="sheet-content"]` — matches shadcn Sheet component's default data attribute

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing @playwright/test package**
- **Found during:** Task 2 (verifying test discovery with `npx playwright test --list`)
- **Issue:** `playwright` package 1.58.2 was present in node_modules but its `cli.js` calls `require('./lib/program')` which fails on Node.js v24 — `program` is undefined. `@playwright/test` (declared in package.json devDependencies) was not installed.
- **Fix:** Ran `npm install --save-dev @playwright/test@1.52.0` in wookiee-hub directory
- **Files modified:** wookiee-hub/package.json, wookiee-hub/package-lock.json
- **Verification:** `node node_modules/@playwright/test/cli.js test --list` discovered all 16 tests across 3 files
- **Committed in:** d2a0c9e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required fix for test discovery to work. No scope creep.

## Issues Encountered
- `playwright.config.ts` used `testDir: "./e2e"` which would have excluded the new `tests/` directory — changed to `testMatch` pattern to cover both directories without breaking existing e2e suite

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Test infrastructure ready for 02-01 through 02-04 to progressively remove `test.fixme()` as features are implemented
- All subsequent plans can use `grep "PANEL-0" tests/detail-panel.spec.ts` to confirm stubs exist
- Panel locator conventions established in fixtures.ts for consistent test authoring

## Self-Check: PASSED

All files exist. Both commits (c29ca71, d2a0c9e) verified in wookiee-hub repo.

---
*Phase: 02-detail-panel*
*Completed: 2026-03-25*
