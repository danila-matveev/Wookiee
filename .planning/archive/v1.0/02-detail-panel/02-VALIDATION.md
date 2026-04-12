---
phase: 2
slug: detail-panel
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (`@playwright/test` 1.52.0) |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `npx playwright test --grep "detail-panel"` |
| **Full suite command** | `npx playwright test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npx playwright test --grep "detail-panel"`
- **After every plan wave:** Run `npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | PANEL-01 | e2e | `npx playwright test --grep "PANEL-01"` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | PANEL-02 | e2e | `npx playwright test --grep "PANEL-02"` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | PANEL-03 | e2e | `npx playwright test --grep "PANEL-03"` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | PANEL-04 | e2e | `npx playwright test --grep "PANEL-04"` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | PANEL-05 | e2e | `npx playwright test --grep "PANEL-05"` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | PANEL-06 | e2e | `npx playwright test --grep "PANEL-06"` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 2 | PANEL-07 | e2e | `npx playwright test --grep "PANEL-07"` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | PANEL-08 | e2e | `npx playwright test --grep "PANEL-08"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `wookiee-hub/playwright.config.ts` — Playwright config targeting localhost:25000
- [ ] `wookiee-hub/tests/detail-panel.spec.ts` — test stubs for PANEL-01 through PANEL-08
- [ ] `wookiee-hub/tests/fixtures.ts` — shared page fixtures and test helpers

*Playwright is installed but no config file detected — Wave 0 must create it.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Panel resize 400-800px drag | PANEL-04 (UX) | Drag interaction hard to test reliably | Open panel → drag left edge → verify width stays in 400-800px range |
| Inherited field popover preview | PANEL-07 (UX) | Hover/click interaction chain | Click inherited field → verify popover shows parent → click again → verify navigation |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
