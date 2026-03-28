# Roadmap: Product Matrix UX Redesign (v1.0)

## Overview

This milestone replaces Google Sheets as the daily working tool for managing a fashion brand's product catalog. The shell already exists — the job is completing and hardening what was started. Work proceeds in strict dependency order: structural rot fixed first (entity registry, panel routing, cache), then the detail panel made fully usable, then the table view polished, then the full filter system wired. Every phase delivers a coherent, independently verifiable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Entity registry, panel routing fix, and entity cache — structural prerequisites for all editing work (completed 2026-03-28)
- [ ] **Phase 2: Detail Panel** - All fields visible in read mode, edit mode with correct input types, save/cancel, lookup options cached
- [ ] **Phase 3: Table View** - Human-readable display names, resolved reference fields, status badges, sort, column toggle, create new record
- [x] **Phase 4: Filter System** - Status filter, category filter, multi-field filter builder, hierarchy drill-down, saved views (completed 2026-03-28)

## Phase Details

### Phase 1: Foundation
**Goal**: The codebase has a single, correct source of truth for entity routing; the detail panel dispatches to the right API endpoint for every entity type; and table rows automatically reflect panel saves
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03
**Success Criteria** (what must be TRUE):
  1. Opening the detail panel for an Artikul or Tovar row fetches from the correct endpoint (not /api/matrix/models/)
  2. All 4 existing entity maps (ManageFieldsDialog, MassEditBar, InfoTab, views-store) read from a single entity-registry.ts — changing one entry updates all consumers
  3. After saving a field change in the detail panel, the corresponding table row reflects the updated value without a full page reload
**Plans:** 2/2 plans complete

Plans:
- [ ] 01-01-PLAN.md — Entity registry module + consolidate 3 inline entity maps + Wave 0 test stubs
- [ ] 01-02-PLAN.md — Fix detail panel routing at all call sites + entityUpdateStamp cache propagation

### Phase 2: Detail Panel
**Goal**: Users can read all fields for any entity type in a section-grouped panel, edit any editable field with the correct input type, and save or cancel changes safely
**Depends on**: Phase 1
**Requirements**: PANEL-01, PANEL-02, PANEL-03, PANEL-04, PANEL-05, PANEL-06, PANEL-07, PANEL-08
**Success Criteria** (what must be TRUE):
  1. All ~22 ModelOsnova fields appear in read mode, grouped under sections (Основные, Размеры, Логистика, Контент); same for Artikul and Tovar fields
  2. Clicking a text/number field opens an inline text or number input; clicking a reference field (категория, фабрика, коллекция, статус) opens a select populated with lookup options
  3. System IDs (barkod, nomenklatura_wb, ozon_product_id, gs1, gs2) are displayed but cannot be edited — no input appears on click
  4. Save button persists changes via PATCH and closes edit mode; Cancel discards all changes; form does not submit with invalid data
  5. Related entity counts ("4 артикула") are clickable and navigate to a filtered list showing only those children
**Plans**: TBD

### Phase 3: Table View
**Goal**: The table displays correct human-readable data for all column types, supports sorting by any column, lets users show/hide columns, and allows creating new records of the current entity type
**Depends on**: Phase 2
**Requirements**: TABLE-01, TABLE-02, TABLE-03, TABLE-04, TABLE-05, TABLE-06, TABLE-07, CRUD-01, CRUD-02
**Success Criteria** (what must be TRUE):
  1. Every column header shows a human-readable label (e.g., "Категория" not "kategoriya_id"); reference fields show resolved names (e.g., "Верхняя одежда" not "—")
  2. Status column shows a colored badge (green for Активный, gray for Архив); archived rows are visually dimmed
  3. Clicking any column header sorts the table ascending; clicking again reverses to descending; a sort indicator is visible on the active column
  4. A column visibility toggle lets the user show or hide any column without losing current data or filters
  5. Clicking "+ Создать" in the topbar opens a creation form with required fields and lookup selects for reference fields; submitting creates the record and it appears in the table
  6. Table shows more than 200 rows (pagination or load-more control is present and functional)
**Plans:** 3/3 plans executed (COMPLETE)

Plans:
- [ ] 03-01-PLAN.md — Backend sort/pagination params + useTableState hook + fieldDefsToColumns utility
- [ ] 03-02-PLAN.md — FieldDef-driven columns, sort indicators, status badges, archive row styling
- [ ] 03-03-PLAN.md — Pagination controls, column visibility popover, create record dialog

### Phase 4: Filter System
**Goal**: Users can filter the table by status, category, or any combination of fields simultaneously, navigate from a parent model to its child articles via a sidebar click, and save and reload their preferred filter+sort configuration
**Depends on**: Phase 3
**Requirements**: FILT-01, FILT-02, FILT-03, FILT-04, FILT-05
**Success Criteria** (what must be TRUE):
  1. A status dropdown above the table shows Активные / Архивные / Все — selecting a value filters the table immediately
  2. A category dropdown above the table filters models to only the selected category
  3. Clicking a model in the sidebar (or a related-entities link in the detail panel) switches the table to Artikuly view showing only that model's articles
  4. A filter builder allows adding multiple simultaneous filters (field + operator + value) with active filter chips displayed and individually removable
  5. A "Сохранить вид" action saves the current filter + sort + column configuration; loading a saved view restores that exact state
**Plans:** 3/3 plans complete

Plans:
- [ ] 04-01-PLAN.md — Backend: migration status_id for modeli_osnova, IN-clause filters, route params, drill-down subquery
- [ ] 04-02-PLAN.md — Frontend: FilterEntry state, FilterPopover two-step builder, FilterChip, MatrixTopbar integration
- [ ] 04-03-PLAN.md — Frontend: Hierarchy drill-down action, saved views with filters+sort round-trip

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete   | 2026-03-28 |
| 2. Detail Panel | 0/TBD | Not started | - |
| 3. Table View | 3/3 | Complete | 2026-03-26 |
| 4. Filter System | 3/3 | Complete   | 2026-03-28 |
