---
phase: 03-reliability
plan: 01
subsystem: agents/oleg/pipeline
tags: [reliability, gates, pre-flight, report-types, notion]
dependency_graph:
  requires: []
  provides: [agents/oleg/pipeline/gate_checker.py, agents/oleg/pipeline/report_types.py]
  affects: [agents/oleg/watchdog/diagnostic.py, shared/notion_client.py]
tech_stack:
  added: []
  patterns: [_db_cursor context manager, dataclass GateResult/CheckAllResult, ReportType enum]
key_files:
  created:
    - agents/oleg/pipeline/__init__.py
    - agents/oleg/pipeline/gate_checker.py
    - agents/oleg/pipeline/report_types.py
    - tests/oleg/pipeline/__init__.py
    - tests/oleg/pipeline/test_gate_checker.py
  modified:
    - shared/notion_client.py
decisions:
  - GateChecker uses _db_cursor context manager from shared.data_layer._connection per AGENTS.md — no direct psycopg2
  - Hard gates (3) block run; soft gates (3) warn only — separates blocking freshness checks from informational anomalies
  - datetime normalization via .date() with AttributeError fallback handles both datetime and date DB return types
  - format_preflight_message handles both can_run=True (success) and can_run=False (failure) cases per D-05/D-16
  - report_types.py excludes hardcoded required_sections — Phase 3 Plan 02 parses them dynamically from template files
  - funnel_weekly Notion label changed from Latin "funnel_weekly" to Russian "Воронка продаж" per REL-06
metrics:
  duration: ~15 minutes
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_changed: 6
---

# Phase 03 Plan 01: GateChecker and ReportTypes Summary

**One-liner:** Data quality gate checker (3 hard + 3 soft gates via _db_cursor) + ReportType enum (8 types) + funnel_weekly Notion label fix.

## What Was Built

### agents/oleg/pipeline/gate_checker.py

Core pre-flight gate checker for the reliability pipeline:

- `GateResult` dataclass: `name`, `passed`, `detail`, `is_hard`
- `CheckAllResult` dataclass: `gates`, `target_date`, `summary_metrics`, with properties `hard_failed`, `soft_warnings`, `can_run`
- `GateChecker.check_all(marketplace, target_date)` — runs all 6 gates and returns aggregated result compatible with DiagnosticRunner interface
- 3 hard gates: `wb_orders_freshness` (WB abc_date), `ozon_orders_freshness` (OZON abc_date), `fin_data_freshness` (fin_data)
- 3 soft gates: `advertising_data`, `margin_fill_rate`, `logistics_data`
- `format_preflight_message(result, report_names)` — formats D-05 pre-flight Telegram message in Russian

### agents/oleg/pipeline/report_types.py

Centralized registry of all 8 v2.0 report types:

- `ReportType` enum: DAILY, WEEKLY, MONTHLY, MARKETING_WEEKLY, MARKETING_MONTHLY, FUNNEL_WEEKLY, FINOLOG_WEEKLY, LOCALIZATION_WEEKLY
- `ReportConfig` dataclass: `report_type`, `display_name_ru`, `period`, `marketplaces`, `hard_gates`, `template_path`
- `REPORT_CONFIGS` dict — all 8 types mapped to their configs

### shared/notion_client.py (fix)

Changed `funnel_weekly` Notion label from `"funnel_weekly"` (Latin) to `"Воронка продаж"` (Russian) per REL-06.

## Tests

14 unit tests in `tests/oleg/pipeline/test_gate_checker.py`:
- GateResult attribute presence
- CheckAllResult.hard_failed and soft_warnings filtering
- can_run blocks on hard failure, allows with soft-only failures
- check_all with fresh data (all hard pass) → can_run=True
- check_all with stale WB dateupdate → can_run=False, wb_orders_freshness in hard_failed
- check_all with stale OZON dateupdate → can_run=False, ozon_orders_freshness in hard_failed
- soft gate failure → can_run still True, soft_warnings non-empty
- datetime normalization (datetime object compares correctly vs target date)
- DiagnosticRunner compatibility (gates[].passed/.name/.detail accessible)
- format_preflight_message for success and failure cases

All 33 tests in tests/oleg/ pass.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all gate SQL queries are real and wired to _db_cursor. format_preflight_message uses summary_metrics dict which defaults to empty dict (metrics shown as "?" when not provided). This is intentional: summary_metrics are populated by the pipeline caller (Plan 02) that has context about actual orders/revenue numbers.

## Self-Check: PASSED

Files created/modified:
- agents/oleg/pipeline/__init__.py: FOUND
- agents/oleg/pipeline/gate_checker.py: FOUND
- agents/oleg/pipeline/report_types.py: FOUND
- tests/oleg/pipeline/__init__.py: FOUND
- tests/oleg/pipeline/test_gate_checker.py: FOUND
- shared/notion_client.py (modified): FOUND

Commits:
- 2790235: feat(03-01): create pipeline package with GateChecker and ReportType registry — FOUND
- 3195b89: fix(03-01): change funnel_weekly Notion label from Latin to Russian (REL-06) — FOUND
