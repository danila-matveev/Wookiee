---
phase: 1
slug: cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash / grep / filesystem checks |
| **Config file** | none — validation is filesystem-based |
| **Quick run command** | `test ! -d agents/v3 && echo PASS` |
| **Full suite command** | `bash -c 'test ! -d agents/v3 && ! grep -r "from agents.v3" agents/ shared/ --include="*.py" -q && ! grep -E "langchain|langgraph" requirements*.txt -q && echo ALL_PASS'` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `test ! -d agents/v3 && echo PASS`
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | CLEAN-01 | filesystem | `test ! -d agents/v3` | N/A | ⬜ pending |
| 01-01-02 | 01 | 1 | CLEAN-01 | filesystem | `test ! -d tests/v3 && test ! -d tests/agents/v3` | N/A | ⬜ pending |
| 01-01-03 | 01 | 1 | CLEAN-02 | grep | `! grep -rE "langchain\|langgraph" requirements*.txt -q` | N/A | ⬜ pending |
| 01-01-04 | 01 | 1 | CLEAN-03 | grep | `! ls docs/superpowers/specs/*v3* docs/superpowers/plans/*v3* 2>/dev/null` | N/A | ⬜ pending |
| 01-01-05 | 01 | 1 | CLEAN-04 | grep | `! grep -E "agents.v3\|agents/v3" deploy/docker-compose.yml -q` | N/A | ⬜ pending |
| 01-01-06 | 01 | 1 | CLEAN-01 | grep | `! grep -r "from agents.v3\|import agents.v3" agents/ shared/ --include="*.py" -q` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Validation is filesystem/grep-based — no test framework needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| finolog-cron doesn't crash | CLEAN-04 | Container kept intentionally broken | Verify container is disabled/stopped on server after deploy |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
