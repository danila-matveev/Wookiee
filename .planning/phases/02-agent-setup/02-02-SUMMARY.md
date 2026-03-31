---
phase: "02"
plan: "02"
subsystem: agents/oleg/playbooks
tags: [playbook, loader, tdd, tests, modular-loading]
dependency_graph:
  requires: [02-01]
  provides: [PlaybookLoader, test_loader, test_module_coverage, test_depth_markers, test_toggle_headings]
  affects: [agents/oleg/agents/reporter/agent.py, agents/oleg/agents/reporter/prompts.py, agents/oleg/agents/marketer/agent.py, agents/oleg/agents/marketer/prompts.py, scripts/run_oleg_v2_single.py, scripts/run_oleg_v2_reports.py]
tech_stack:
  added: []
  patterns: [PlaybookLoader, assembled_playbook parameter, per-chain agent instantiation]
key_files:
  created:
    - agents/oleg/playbooks/__init__.py
    - agents/oleg/playbooks/loader.py
    - tests/agents/oleg/playbooks/__init__.py
    - tests/agents/oleg/playbooks/test_loader.py
    - tests/agents/oleg/playbooks/test_module_coverage.py
    - tests/agents/oleg/playbooks/test_depth_markers.py
    - tests/agents/oleg/playbooks/test_toggle_headings.py
  modified:
    - agents/oleg/agents/reporter/prompts.py
    - agents/oleg/agents/reporter/agent.py
    - agents/oleg/agents/marketer/prompts.py
    - agents/oleg/agents/marketer/agent.py
    - scripts/run_oleg_v2_single.py
    - scripts/run_oleg_v2_reports.py
    - README.md
decisions:
  - "PlaybookLoader.load(task_type) returns core.md + template/{type}.md + rules.md assembled into single prompt string"
  - "Reporter and Marketer accept assembled_playbook= parameter for backward-compatible prompt injection"
  - "run_oleg_v2_reports.py creates reporter/marketer agents per chain (not globally) to pass correct task_type"
  - "FunnelAgent unchanged — no playbook_path, no task_type, uses minimal FUNNEL_PREAMBLE only"
metrics:
  duration: "~5 minutes"
  completed: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 7
---

# Phase 02 Plan 02: PlaybookLoader and Agent Wiring Summary

Wired modular playbook loading into agent code: created `PlaybookLoader` with 9-entry `TEMPLATE_MAP`, updated Reporter and Marketer agents to assemble per-task-type prompts via `load(task_type)`, and added 76 automated tests covering all 4 requirements (PLAY-01, PLAY-02, PLAY-03, VER-03).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create PlaybookLoader and update agent prompt functions | 0cbcbc0 | loader.py, __init__.py, reporter/prompts.py, reporter/agent.py, marketer/prompts.py, marketer/agent.py, run scripts, README.md |
| 2 | Create automated tests for all playbook requirements | ed44281 | test_loader.py, test_module_coverage.py, test_depth_markers.py, test_toggle_headings.py |

## What Was Built

### PlaybookLoader (`agents/oleg/playbooks/loader.py`)

`TEMPLATE_MAP` with 9 entries (8 task types + `custom` fallback to weekly):
```
daily, weekly, monthly, marketing_weekly, marketing_monthly,
funnel_weekly, dds, localization, custom (→ weekly.md)
```

`load(task_type) -> str` assembles: `core.md + --- + template/{type}.md + --- + rules.md`

Unknown task types fall back to `weekly.md` via `TEMPLATE_MAP.get(task_type, "weekly.md")`.

### Agent Updates

**Reporter and Marketer agents** — both now accept `task_type: str = None` in `__init__`. When set, `get_system_prompt()` calls `load_playbook(task_type)` and passes the result as `assembled_playbook=` to the prompt function. When not set, falls back to legacy `playbook_path` behavior (full backward compatibility preserved).

**Funnel agent** — not modified. No playbook, bypasses LLM entirely.

**run_oleg_v2_single.py** — passes `task_type=` when creating `ReporterAgent` and `MarketerAgent`.

**run_oleg_v2_reports.py** — creates reporter/marketer agents inside the chain loop with the current `task_type=`. Shared agents (funnel, advisor, validator) created once outside the loop.

### Test Suite (76 tests, all passing)

| File | Tests | Requirement |
|------|-------|-------------|
| test_loader.py | 7 (+ 8 parametrized = 23 total) | PLAY-02 |
| test_module_coverage.py | 4 + 19 parametrized = 28 total | PLAY-01 |
| test_depth_markers.py | 12 tests | PLAY-03 |
| test_toggle_headings.py | 3 + 8 + 3 + 8 + 1 + 1 = 14 tests | VER-03 |

## Decisions Made

1. **Per-chain agent instantiation in run_oleg_v2_reports.py**: Creating reporter/marketer agents once globally doesn't work with `task_type=` since different chains need different task types. Fix: create task-type-specific agents inside the loop, reuse stateless shared agents (funnel, advisor, validator) outside.

2. **Backward compatibility preserved**: Both `get_reporter_system_prompt` and `get_marketer_system_prompt` retain their `playbook_path` parameter and fallback logic. `assembled_playbook` takes priority if provided, otherwise falls back to legacy file-loading behavior.

3. **TDD applied**: RED (loader module missing → import error), GREEN (loader implemented → test passes), REFACTOR not needed.

## Deviations from Plan

None — plan executed exactly as written. The per-chain agent instantiation pattern for `run_oleg_v2_reports.py` (D4 of Decisions Made) was explicitly called out in the plan's Task 1 action item #8.

## Known Stubs

None. PlaybookLoader is fully implemented and agents use it when `task_type=` is set. All 76 tests pass green.

## Self-Check: PASSED

Files exist:
- agents/oleg/playbooks/__init__.py: FOUND
- agents/oleg/playbooks/loader.py: FOUND (contains def load and TEMPLATE_MAP)
- tests/agents/oleg/playbooks/test_loader.py: FOUND (7+ test functions)
- tests/agents/oleg/playbooks/test_module_coverage.py: FOUND (19 parametrized phrases)
- tests/agents/oleg/playbooks/test_depth_markers.py: FOUND (brief/deep/max + no-depth-driven)
- tests/agents/oleg/playbooks/test_toggle_headings.py: FOUND (## ▶ checks)

Commits exist:
- 0cbcbc0: feat(02-02): create PlaybookLoader and wire modular playbook into agents — FOUND
- ed44281: test(02-02): add 76 automated tests covering PLAY-01, PLAY-02, PLAY-03, VER-03 — FOUND

Acceptance criteria:
- agents/oleg/playbooks/loader.py contains def load(task_type: str) -> str: PASSED
- TEMPLATE_MAP has 9 keys (daily, weekly, monthly, marketing_weekly, marketing_monthly, funnel_weekly, dds, localization, custom): PASSED
- reporter/prompts.py contains assembled_playbook: str = None: PASSED
- reporter/prompts.py still contains REPORTER_PREAMBLE: PASSED
- reporter/agent.py imports from agents.oleg.playbooks.loader: PASSED
- reporter/agent.py contains task_type parameter in __init__: PASSED
- marketer/prompts.py contains assembled_playbook: str = None: PASSED
- marketer/agent.py contains task_type parameter in __init__: PASSED
- funnel/agent.py has no "loader" reference: PASSED
- run_oleg_v2_single.py passes task_type= to ReporterAgent and MarketerAgent: PASSED
- README.md updated with playbooks/ docs: PASSED
- python3 -c "from agents.oleg.playbooks.loader import load; load('daily')" succeeds: PASSED
- python3 -m pytest tests/agents/oleg/playbooks/ -v returns 76 passed: PASSED
