---
phase: 3
slug: table-view
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-26
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend); no frontend test framework — UI verified manually via Chrome DevTools MCP |
| **Config file** | none — pytest auto-discovers `tests/` directory |
| **Quick run command** | `pytest tests/product_matrix_api/test_routes_models.py -x -q` |
| **Full suite command** | `pytest tests/product_matrix_api/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/product_matrix_api/test_routes_models.py -x -q`
- **After every plan wave:** Run `pytest tests/product_matrix_api/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + manual UI smoke test
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | TABLE-04 | unit | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k sort` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | TABLE-05 | unit | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k page` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | CRUD-02 | integration | `pytest tests/product_matrix_api/test_routes_models.py -x -q -k create` | ✅ partial | ⬜ pending |
| 3-02-01 | 02 | 1 | TABLE-01 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |
| 3-02-02 | 02 | 1 | TABLE-02 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |
| 3-02-03 | 02 | 1 | TABLE-03 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |
| 3-02-04 | 02 | 1 | TABLE-07 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |
| 3-02-05 | 02 | 1 | TABLE-06 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |
| 3-02-06 | 02 | 1 | CRUD-01 | manual (UI) | Chrome DevTools snapshot | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/product_matrix_api/test_routes_models.py` — add `test_list_models_sort_asc` and `test_list_models_sort_desc` covering TABLE-04
- [ ] `tests/product_matrix_api/test_routes_models.py` — add `test_list_models_pagination` covering TABLE-05
- [ ] `tests/product_matrix_api/test_routes_articles.py` — add sort + pagination tests for articles endpoint
- [ ] Verify FieldDefinitions seeded for `artikuly` and `tovary` — check `GET /api/matrix/schema/artikuly`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FieldDef display_name → column header | TABLE-01 | Frontend-only React rendering | Open /product/matrix, verify column headers match FieldDefinition display_names |
| Reference fields show real values | TABLE-02 | Requires lookup cache + DOM rendering | Check КАТЕГОРИЯ, КОЛЛЕКЦИЯ, ФАБРИКА columns show names not "—" |
| Status badge green/gray | TABLE-03 | CSS/component visual check | Verify "Активный" green badge, "Архив" gray badge in status column |
| Sort via column header click | TABLE-04 | End-to-end UI interaction | Click КОД header → ascending sort, click again → descending |
| Pagination controls | TABLE-05 | UI interaction + data verification | Navigate pages, verify different data per page, total count shown |
| Column visibility toggle | TABLE-06 | Popover interaction check | Click "Настроить поля", toggle column checkbox → column hides/shows |
| Archive rows dimmed | TABLE-07 | CSS visual check | Verify archived rows have muted/opacity styling |
| "+ Создать" opens dialog | CRUD-01 | UI interaction | Click button, verify modal form appears |
| Create form submits | CRUD-02 | End-to-end create flow | Fill form, submit, verify record in table + Detail Panel opens |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
