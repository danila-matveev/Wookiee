---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.2 + @testing-library/react 16.3.2 |
| **Config file** | `wookiee-hub/vitest.config.ts` |
| **Quick run command** | `cd wookiee-hub && npm test -- --reporter=verbose src/stores/__tests__/ src/lib/__tests__/` |
| **Full suite command** | `cd wookiee-hub && npm test` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd wookiee-hub && npm test -- --reporter=verbose src/stores/__tests__/ src/lib/__tests__/`
- **After every plan wave:** Run `cd wookiee-hub && npm test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | FOUND-01 | unit | `npm test -- src/lib/__tests__/entity-registry.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | FOUND-02 | unit | `npm test -- src/stores/__tests__/detail-panel-routing.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | FOUND-03 | unit | `npm test -- src/stores/__tests__/entity-update-stamp.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | FOUND-01 | unit | `npm test -- src/lib/__tests__/entity-registry.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 2 | FOUND-02 | unit | `npm test -- src/stores/__tests__/detail-panel-routing.test.ts` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 3 | FOUND-03 | unit | `npm test -- src/stores/__tests__/entity-update-stamp.test.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `wookiee-hub/src/lib/__tests__/entity-registry.test.ts` — stubs for FOUND-01 (entity registry mapping)
- [ ] `wookiee-hub/src/stores/__tests__/detail-panel-routing.test.ts` — stubs for FOUND-02 (detail panel routing)
- [ ] `wookiee-hub/src/stores/__tests__/entity-update-stamp.test.ts` — stubs for FOUND-03 (cache invalidation)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Detail panel shows correct data for Artikul row | FOUND-02 | E2E visual check | Open articles page, click row, verify panel shows data (not "Не найдено") |
| Table row updates after panel save | FOUND-03 | E2E visual check | Edit field in panel, save, verify table row updates without page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
