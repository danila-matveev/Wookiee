---
phase: 02
slug: agent-setup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/agents/oleg/ -x -q` |
| **Full suite command** | `python -m pytest tests/agents/oleg/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/agents/oleg/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/agents/oleg/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | PLAY-01 | unit | `python -m pytest tests/agents/oleg/test_playbook_modules.py -k core` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | PLAY-02 | unit | `python -m pytest tests/agents/oleg/test_playbook_modules.py -k template` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | PLAY-03 | unit | `python -m pytest tests/agents/oleg/test_playbook_modules.py -k rules` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | VER-03 | integration | `python -m pytest tests/agents/oleg/test_playbook_loader.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agents/oleg/test_playbook_modules.py` — stubs for PLAY-01, PLAY-02, PLAY-03
- [ ] `tests/agents/oleg/test_playbook_loader.py` — stubs for VER-03
- [ ] `tests/agents/oleg/conftest.py` — shared fixtures for playbook paths

*Existing pytest infrastructure covers framework installation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Report quality matches template | PLAY-02 | Semantic content quality | Run test report, compare sections against template structure |
| Depth markers produce correct verbosity | PLAY-03 | Output quality judgment | Generate daily vs weekly report, verify depth difference |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
