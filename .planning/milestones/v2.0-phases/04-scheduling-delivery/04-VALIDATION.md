---
phase: 4
slug: scheduling-delivery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/ directory (existing) |
| **Quick run command** | `python -m pytest tests/services/reporting/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/services/reporting/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | SCHED-01 | unit | `python -m pytest tests/services/reporting/test_runner.py -x -q` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | SCHED-01 | unit | `python scripts/run_report.py --type daily --dry-run` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | SCHED-02 | integration | `grep -c 'run_report.py' docker/crontab` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | SCHED-03 | manual | Verify Telegram notification after Notion publish | N/A | ⬜ pending |
| 04-02-03 | 02 | 2 | SCHED-04 | unit | `grep -c 'display_name_ru' scripts/run_report.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/services/reporting/test_runner.py` — stubs for SCHED-01 (runner script logic)
- [ ] `tests/services/reporting/test_scheduling.py` — stubs for SCHED-02 (cron scheduling)

*Existing infrastructure covers Notion/Telegram delivery (SCHED-03, SCHED-04) via report_pipeline tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram notification arrives after Notion publish | SCHED-03 | Requires live Telegram bot | Run `python scripts/run_report.py --type daily`, check Telegram channel |
| Notion page has correct properties | SCHED-02 | Requires live Notion API | Run report, verify properties in Notion UI |
| Cron fires at correct times | SCHED-01 | Requires running Docker container | Deploy, wait for scheduled time, check logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
