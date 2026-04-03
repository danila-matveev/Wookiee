---
phase: 01-cleanup
plan: 01
subsystem: agents
tags: [cleanup, v3-removal, price-tools, refactor]
dependency_graph:
  requires: []
  provides: [clean-codebase-no-v3]
  affects: [agents/oleg/services/price_tools.py, shared/notion_client.py]
tech_stack:
  added: []
  patterns: [local-helper-functions, inline-client-factory]
key_files:
  created: []
  modified:
    - agents/oleg/services/price_tools.py
    - shared/notion_client.py
  deleted:
    - agents/v3/ (entire directory, ~50 tracked files)
    - tests/v3/ (V3 test suite)
    - tests/agents/v3/ (additional V3 tests)
    - scripts/run_report.py
    - scripts/run_price_analysis.py
    - scripts/test_v2_bridge.py
decisions:
  - "Copied get_wb_clients/get_ozon_clients locally into price_tools.py as private helpers (minimal footprint — single caller)"
  - "scripts/rerun_weekly_reports.py and scripts/run_localization_report.py were untracked in git (not committed), so they required only filesystem deletion — no git staging needed"
  - "scripts/run_finolog_weekly.py preserved with known-broken V3 import (deferred to Phase 3/4)"
metrics:
  duration: ~10 minutes
  completed: "2026-03-30T21:32:00Z"
  tasks: 2
  files_changed: 68
---

# Phase 01 Plan 01: V3 Code Removal Summary

**One-liner:** Deleted entire agents/v3/ LangGraph system (~50 files) and patched price_tools.py with local WB/Ozon client helpers to remove the last V3 import dependency.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Patch price_tools.py to remove V3 import | 19e2b1b | agents/oleg/services/price_tools.py, shared/notion_client.py |
| 2 | Delete agents/v3/, V3 test dirs, V3-only scripts | 59df52e | 66 files deleted |

## What Was Done

### Task 1: Patch price_tools.py
- Added `_get_wb_clients()` and `_get_ozon_clients()` as private module-level helpers in `agents/oleg/services/price_tools.py`
- Removed `from agents.v3 import config` inline import in `_handle_analyze_promotion()`
- Replaced `config.get_wb_clients()` / `config.get_ozon_clients()` calls with `_get_wb_clients()` / `_get_ozon_clients()`
- Cleaned `shared/notion_client.py` docstring to remove references to `agents/v3/delivery/notion.py (V3)`

### Task 2: Delete V3 Code
- Deleted `agents/v3/` entire directory (50 tracked files: conductor, delivery, 24 micro-agent MDs, config, scheduler, runner, state)
- Deleted `tests/v3/` (12 test files across conductor and root)
- Deleted `tests/agents/v3/` (1 test file)
- Deleted `scripts/run_report.py`, `scripts/run_price_analysis.py`, `scripts/test_v2_bridge.py` (3 tracked V3 wrapper scripts)
- Note: `scripts/rerun_weekly_reports.py` and `scripts/run_localization_report.py` were never committed to git (untracked), so filesystem deletion was sufficient

## Verification Results

- `agents/v3/` does not exist: PASS
- `tests/v3/` does not exist: PASS
- `tests/agents/v3/` does not exist: PASS
- `grep -r "agents.v3" agents/ services/ shared/` returns no results: PASS
- `grep -r "langchain" --include="*.txt" agents/ services/` returns no results: PASS
- `price_tools.py` contains `def _get_wb_clients()`: PASS
- `price_tools.py` contains `def _get_ozon_clients()`: PASS
- `price_tools.py` does NOT contain `agents.v3`: PASS
- `scripts/run_finolog_weekly.py` still exists (deferred): PASS
- Only `scripts/run_finolog_weekly.py` retains agents.v3 import (expected): PASS

## Deviations from Plan

None — plan executed exactly as written.

Note: `scripts/rerun_weekly_reports.py` was listed in the plan as a file to delete, but it was untracked in git. Filesystem deletion was performed as required; no git staging was needed for this file.

## Known Stubs

None. This plan performs deletion/cleanup only — no new features or UI introduced.

## Self-Check: PASSED

- `agents/oleg/services/price_tools.py` exists and contains `_get_wb_clients`: FOUND
- `shared/notion_client.py` cleaned: FOUND
- Commit 19e2b1b exists: FOUND
- Commit 59df52e exists: FOUND
- `agents/v3/` absent from filesystem: CONFIRMED
