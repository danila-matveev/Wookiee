---
phase: 4
slug: filter-system
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-28
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (frontend), pytest (backend migration) |
| **Config file** | wookiee-hub/vitest.config.ts |
| **Quick run command** | `cd wookiee-hub && npx vitest run --reporter=verbose` |
| **Full suite command** | `cd wookiee-hub && npx vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd wookiee-hub && npx vitest run`
- **After every plan wave:** Run full suite + manual browser check
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | FILT-01 | unit | `python -c "from sku_database.database.models import ModelOsnova; assert hasattr(ModelOsnova, 'status_id')"` | N/A | pending |
| 4-01-02 | 01 | 1 | FILT-01..04 | integration | `python -m pytest tests/product_matrix_api/test_crud_filters.py tests/product_matrix_api/test_models_filter.py tests/product_matrix_api/test_articles_filter.py -x -q` | W0 | pending |
| 4-02-00 | 02 | 2 | infra | setup | `cd wookiee-hub && npx vitest run 2>&1 \| tail -5` | W0 | pending |
| 4-02-01 | 02 | 2 | FILT-01..04 | behavioral | `cd wookiee-hub && npx vitest run src/stores/__tests__/matrix-store-filters.test.ts` | W0 | pending |
| 4-02-02 | 02 | 2 | FILT-02,04 | tsc + checkpoint | `cd wookiee-hub && npx tsc --noEmit` + Task 3 manual verify | N/A | pending |
| 4-03-01 | 03 | 3 | FILT-03 | tsc + checkpoint | `cd wookiee-hub && npx tsc --noEmit` + Task 3 manual verify | N/A | pending |
| 4-03-02 | 03 | 3 | FILT-05 | tsc + checkpoint | `cd wookiee-hub && npx tsc --noEmit` + Task 3 step 3 (persistence) | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] Plan 02 Task 0 installs vitest + creates vitest.config.ts (addresses vitest not in devDependencies)
- [ ] Verify migration tooling works for sku_database

*Vitest install is now an explicit Task 0 in Plan 02, not a pre-condition.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Filter chips appear/remove on click | FILT-04 | UI interaction | Open page, add filter via +Фильтр, verify chip appears, click x to remove |
| Drill-down switches tab with filter | FILT-03 | Cross-component navigation | Click model row, verify tab switches to Артикулы with filter chip |
| Saved view restores full state | FILT-05 | Full state persistence | Save view, refresh page, load view, verify filters+sort+columns match |
| Status filter works | FILT-01 | Depends on real data in DB | Select status from dropdown, verify table filters |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (vitest install = Plan 02 Task 0)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
