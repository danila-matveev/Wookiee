---
phase: 03
slug: reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with asyncio_mode=auto |
| **Config file** | `pyproject.toml` (testpaths = ["tests"]) |
| **Quick run command** | `python3 -m pytest tests/oleg/pipeline/ -x -q` |
| **Full suite command** | `python3 -m pytest tests/oleg/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/oleg/pipeline/ -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/oleg/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | REL-01 | unit | `python3 -m pytest tests/oleg/pipeline/test_gate_checker.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | REL-01 | unit | `python3 -m pytest tests/oleg/pipeline/test_gate_checker.py -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | REL-02 | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_retry -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | REL-02 | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_retry_max -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | REL-03 | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_empty_report -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | REL-04 | unit | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_graceful -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 1 | REL-05 | unit | (covered by REL-03 + REL-04 tests) | ❌ W0 | ⬜ pending |
| 03-02-06 | 02 | 1 | REL-06 | unit (mock) | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_upsert -x` | ❌ W0 | ⬜ pending |
| 03-02-07 | 02 | 1 | REL-07 | unit (call order) | `python3 -m pytest tests/oleg/pipeline/test_report_pipeline.py::test_order -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/oleg/pipeline/__init__.py` — empty init for test module
- [ ] `tests/oleg/pipeline/test_gate_checker.py` — unit tests for gate logic (mock DB)
- [ ] `tests/oleg/pipeline/test_report_pipeline.py` — unit tests for pipeline flow (mock orchestrator, notion, alerter)
- [ ] `agents/oleg/pipeline/__init__.py` — empty init for new module

*Existing tests in `tests/oleg/` (test_orchestrator.py, test_circuit_breaker.py) are not affected — Phase 3 does not modify orchestrator.py.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pre-flight Telegram message format | REL-01 | Requires real Telegram bot token | Send test gate check, verify message format in Telegram |
| Notion upsert deduplication | REL-06 | Requires real Notion API | Run sync_report twice for same period+type, verify single page |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
