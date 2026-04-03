---
phase: 03-reliability
plan: 02
subsystem: agents/oleg/pipeline
tags: [reliability, pipeline, retry, graceful-degradation, notion, telegram]
dependency_graph:
  requires: [agents/oleg/pipeline/gate_checker.py, agents/oleg/pipeline/report_types.py]
  provides: [agents/oleg/pipeline/report_pipeline.py]
  affects: [agents/oleg/watchdog/alerter.py, shared/notion_client.py]
tech_stack:
  added: []
  patterns:
    - ReportPipelineResult dataclass (success/skipped/failed/reason/notion_url/warnings)
    - _run_chain_with_retry with max_retries=2 (3 total attempts)
    - validate_and_degrade with DEGRADATION_PLACEHOLDER (Russian human-readable)
    - has_substantial_content with section-by-section check + length fallback
    - unittest.mock.patch for _load_required_sections isolation in integration tests
key_files:
  created:
    - agents/oleg/pipeline/report_pipeline.py
    - tests/oleg/pipeline/test_report_pipeline.py
  modified: []
decisions:
  - _is_substantial checks len>=200 AND "##" heading presence — short reports without structure are not considered real
  - max_retries=2 = 3 total attempts as specified in REL-02
  - DEGRADATION_PLACEHOLDER uses Russian human-readable text, no technical error language
  - has_substantial_content falls back to len>500 when no template sections are available
  - Integration tests patch _load_required_sections to [] to isolate from real template files
  - Telegram failure after Notion success recorded as warning (D-13) — Notion is primary artifact
metrics:
  duration: ~6 minutes
  completed_date: "2026-03-31"
  tasks_completed: 1
  files_changed: 2
---

# Phase 03 Plan 02: Report Pipeline Summary

**One-liner:** Full reliability pipeline (gate check -> LLM retry x2 -> section validation with Russian degradation -> Notion publish -> Telegram notify) with 28 unit tests covering all REL requirements.

## What Was Built

### agents/oleg/pipeline/report_pipeline.py

Central reliability pipeline for Oleg v2.0 report generation:

- `ReportPipelineResult` dataclass: `success`, `skipped`, `failed`, `reason`, `notion_url`, `warnings`
- `_is_substantial(result: ChainResult) -> bool`: checks `len(detailed) >= 200` AND `"##" in detailed`
- `_run_chain_with_retry(orchestrator, task, task_type, context, max_retries=2)`: 3 total attempts, returns None after all fail
- `DEGRADATION_PLACEHOLDER`: Russian human-readable text — "Данные для этой секции временно недоступны..."
- `_load_required_sections(report_type)`: parses `## ` headings from template file, returns `[]` on FileNotFoundError
- `validate_and_degrade(report_md, report_type, required_sections=None)`: adds DEGRADATION_PLACEHOLDER for each missing required section
- `has_substantial_content(report_md, report_type, required_sections=None)`: at least one section with non-placeholder content; falls back to `len > 500` if no required sections
- `run_report(...)`: 7-step sequential pipeline — gate check, pre-flight Telegram, LLM chain with retry, validate+degrade, empty check, Notion publish, Telegram notify

Pipeline steps enforce REL requirements in order:
1. Pre-flight gate check (hard failures → `skipped=True`, Telegram alert sent)
2. Pre-flight success Telegram notification (D-05)
3. LLM chain with retry (`max_retries=2`, 3 total attempts) (REL-02)
4. Section validation + graceful degradation (Russian placeholders) (REL-04, REL-05)
5. Empty report guard — all-placeholder reports NOT published (REL-03)
6. Notion publish via `sync_report` (REL-06)
7. Telegram notification ONLY after Notion success; failure recorded as warning (D-13, REL-07)

### tests/oleg/pipeline/test_report_pipeline.py

28 unit tests across 6 test classes:

- `TestIsSubstantial` (6 tests): short result, no headings, None detailed, boundary cases
- `TestRunChainWithRetry` (4 tests): good first try, retry on empty, 3 empties → None, default max_retries
- `TestValidateAndDegrade` (4 tests): missing section gets Russian placeholder, no technical errors, all sections present after degrade
- `TestHasSubstantialContent` (4 tests): real content → True, all placeholders → False, mixed → True, length fallback
- `TestPublishNotifyOrder` (4 tests): notion before telegram call order, notion fails → telegram not called, telegram fails → still success, telegram message contains Notion URL
- `TestRunReportGateCheck` (4 tests): hard gate failure skips, LLM empty after retries fails, empty report not published, partial content published
- `TestReportPipelineResult` (2 tests): default state, success state

## Tests

42 total tests in `tests/oleg/pipeline/` (14 from Plan 01 + 28 new):
- All 42 pass
- All 61 tests in `tests/oleg/` pass (no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test isolation from real template files**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Integration tests for `run_report` called `_load_required_sections` which loaded real DAILY template (containing 16 `## ▶` headed sections), causing `has_substantial_content` to return False for test content that didn't match template headings
- **Fix:** Added `patch("agents.oleg.pipeline.report_pipeline._load_required_sections", return_value=[])` in integration tests; for section-specific tests (empty/partial content), patched to return exactly the sections used in test data
- **Files modified:** `tests/oleg/pipeline/test_report_pipeline.py`
- **Commit:** `c78a8aa`

**2. [Rule 1 - Bug] _good_chain_result() content too short for length fallback**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test helper `_good_chain_result()` produced 307 chars of content — below the 500-char fallback threshold used when no template sections are loaded
- **Fix:** Extended test helper with more substantive content (715 chars) to pass the `len > 500` fallback
- **Files modified:** `tests/oleg/pipeline/test_report_pipeline.py`
- **Commit:** `c78a8aa`

**3. [Rule 1 - Bug] Test assertion used "retry" but reason contained "retries"**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test asserted `"retry" in result.reason.lower()` but actual reason string was "LLM empty after 2 retries for daily"
- **Fix:** Extended assertion to also check "retries" and "empty"
- **Files modified:** `tests/oleg/pipeline/test_report_pipeline.py`
- **Commit:** `c78a8aa`

## Known Stubs

None — all pipeline steps are real. Template loading uses actual template files (which exist for DAILY, WEEKLY, etc. from Phase 2). `_load_required_sections` returns `[]` gracefully when template not found, falling back to length-based check.

## Self-Check: PASSED

Files created:
- agents/oleg/pipeline/report_pipeline.py: FOUND
- tests/oleg/pipeline/test_report_pipeline.py: FOUND

Commits:
- `bcabc34`: test(03-02): add failing tests for report_pipeline (RED) — FOUND
- `c78a8aa`: feat(03-02): implement report_pipeline with full reliability flow (GREEN) — FOUND

Verification commands passed:
- `python3 -m pytest tests/oleg/pipeline/ -x -q` → 42 passed
- `python3 -m pytest tests/oleg/ -x -q` → 61 passed
- `python3 -c "from agents.oleg.pipeline.report_pipeline import run_report, ReportPipelineResult; print('pipeline imports OK')"` → imports OK
