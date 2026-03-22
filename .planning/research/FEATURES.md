# Feature Research

**Domain:** Notion-like PIM editor for multi-channel fashion brand (4-level hierarchy, 90+ fields)
**Researched:** 2026-03-22
**Confidence:** HIGH — based on direct codebase inspection, existing design specs, and known patterns from Notion/Airtable/Akeneo PIM systems

---

## Context: What Already Exists vs. What's Needed

**Already built (DO NOT rebuild):**
- DataTable component with expand/collapse, checkboxes, inline cell editing
- DetailPanel shell (slide-in, open/close, ExternalLink to full page)
- MatrixSidebar (entity navigation, 9 entity types)
- MatrixTopbar with global search trigger and "Manage Fields" button
- MassEditBar with bulk status updates
- GlobalSearch (Cmd+K) with cross-entity results
- ViewTabs infrastructure (spec/stock/finance/rating)
- Zustand matrix store (entity selection, row selection, detail panel state)
- Full backend CRUD for all 9 entity types
- Bulk operations endpoint
- Field definitions system (JSONB custom_fields)
- Saved views backend (hub.saved_views)
- Archive / soft-delete with challenge dialog
- External data endpoints (stock + finance) with caching
- Entity detail page with tabs (Info, Stock, Finance, Rating, Tasks)

**The UX redesign gap:** The shell exists but the internals are incomplete or incorrect:
- DetailPanel shows only ~5 fields out of 20+ for ModelOsnova
- DetailPanel has no editing capability (read-only display)
- Table shows technical field names, reference fields show "—"
- No "+ Create" button anywhere
- No filter/sort controls wired up
- ViewTabs exist but stock/finance columns contain placeholder `_underscore` keys with no real data
- Missing ~70% of fields from the Google Sheets spec across all entity types
- Sidebar navigates entity types but no contextual hierarchy drill-down (ModelOsnova → its Models)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that make this usable as a daily work tool. Missing any = "not ready to replace Google Sheets."

| Feature | Why Expected | Complexity | Backend Dependency | Notes |
|---------|--------------|------------|-------------------|-------|
| Display names for all fields | Users see "Категория" not "kategoriya_id" | S | None — field names already defined in view-columns.ts and detail-panel.tsx | Purely a frontend mapping issue; ~20 display-name mappings needed |
| Reference field resolution in table | "Vuki" not "—" for category/collection/factory | S | Backend already returns `kategoriya_name`, `fabrika_name` etc. — it's a column config bug | In view-columns.ts, reference columns use wrong key or type="readonly" incorrectly |
| All fields from spec in DetailPanel | Users need to view/edit all 20+ fields of ModelOsnova | M | Backend returns full records; `ModelOsnovaCreate` has all 22 fields | DetailPanel currently hardcodes 5 fields; needs section-based layout for all fields |
| Editable DetailPanel | Side panel must allow editing, not just viewing | M | PATCH endpoints exist for all entities | Requires field-type-aware inputs (text, number, select with lookup options) |
| Create new record button ("+") | No way to add new models/articles/products | S | POST endpoints exist for all entities | Add "+ New" row at bottom of table OR button in topbar; needs a creation form/modal |
| Filter by field (basic) | Users filter by status, category, collection | M | Backend supports `filter[field]=value` query params — needs wiring | At minimum: status filter (active/archive), category filter for models |
| Sort by column | Click column header to sort | S | Backend supports `sort=field:asc\|desc` | Column headers need onClick handlers; sort state in matrix-store |
| Status badge display | Status "Активный"/"Архив" as colored badge not raw text | S | `status_name` already in response | Replace plain text with Badge component in table cells |
| Pagination or "load more" | Currently loads 200 rows hardcoded | S | Backend has full pagination (page/per_page/total) | Add pagination controls or increase limit to practical maximum |
| Hierarchy context: articles under model | Viewing articles filtered to a specific model | M | `GET /api/matrix/articles?filter[model_id]=X` works | Clicking a model in ModelOsnova detail → shows its articles in filtered view |
| Read-only protection for system fields | Barcodes, marketplace IDs must not be editable | S | Backend has no write-protect, frontend must enforce | Mark `barkod`, `nomenklatura_wb`, `ozon_product_id` as type="readonly" |
| Working stock tab columns | Stock view shows real data not placeholder keys | M | `GET /api/matrix/{entity}/{id}/stock` exists with real data | Table-level stock requires batch fetching for all visible rows — either column data from list endpoint or separate batch call |
| Working finance tab columns | Finance view shows real data | M | Finance endpoint exists per-entity | Same batch challenge as stock; consider showing finance data only in detail panel, not table |
| Lookup dropdowns for reference fields | Selecting category/collection/factory/status in edit | M | `GET /api/matrix/lookups/kategorii` (and similar) endpoints exist | Need to load lookup options once and cache in store; select fields in DetailPanel need populated options |

### Differentiators (Competitive Advantage)

Features that make this better than the Google Sheets it replaces, worth building in this milestone.

| Feature | Value Proposition | Complexity | Backend Dependency | Notes |
|---------|-------------------|------------|-------------------|-------|
| Hierarchy drill-down in sidebar | Click ModelOsnova → see its Models; click Model → see its Articles | M | GET /api/matrix/articles?filter[model_id]= exists | MatrixSidebar can show a "breadcrumb" context panel; current design treats all entities as peer-level flat lists |
| Section-grouped fields in DetailPanel | Fields organized into "Основные / Размеры и упаковка / Логистика / Контент" | S | `section` field already in FieldDefinitionRead schema | Group ~22 ModelOsnova fields into 4-5 sections matching Google Sheets structure; collapses visual overwhelm |
| Inherited field display in child records | Artikul detail shows parent Model fields as read-only context | M | GET /api/matrix/articles/{id} → navigate to parent via model_id | Prevents "why is category missing?" confusion — show parent context clearly labeled "Унаследовано от модели" |
| Quick-edit hover on table cell | Single click on editable cell in table opens inline editor | S | PATCH endpoint exists | Currently clicking a cell does nothing for relation/readonly types; editable cells should activate on click |
| Related counts as clickable links | "4 артикула" in detail panel is a clickable link to filtered articles view | S | No new backend needed | Turns passive counts into navigation; key for hierarchy traversal workflow |
| Column visibility toggle | User can show/hide columns without saving a view | S | No backend needed, pure frontend state | Add a columns picker dropdown in topbar; persists in localStorage |
| "Jump to entity" from reference field | Clicking "Vuki" in factory column opens factory detail panel | S | GET /api/matrix/factories/{id} exists | Reference fields in table/detail panel become clickable navigation |
| Status-based row coloring | Archived rows visually dimmed, draft rows slightly highlighted | S | `status_name` in all responses | CSS class based on status_id; no backend change |
| Keyboard navigation | Tab through fields in DetailPanel, Enter to confirm, Escape to cancel | S | None | Standard UX expectation for power users managing 1450+ SKUs daily |
| Empty state guidance | "No articles yet — add the first one" with action button | S | None | Prevents confusion when filtered view returns zero rows |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Inline table editing for all fields | "Excel-like, feels fast" | Already identified in PROJECT.md as the WRONG approach. For 90+ fields, inline editing creates data validation nightmares, unclear save states, accidental edits, and impossible UX for select/relation fields. | DetailPanel with explicit edit mode per field. Table cells editable only for simple text/number fields where instant-save is safe. |
| Real-time collaborative editing | "Multiple users editing simultaneously" | Design spec explicitly non-goal. Adds websocket complexity, conflict resolution, presence indicators — none of which has value for a single-brand tool. | Optimistic locking (last-write-wins) is sufficient; audit log shows who changed what |
| Undo/redo in table | "Excel has it" | Requires client-side change buffering, diverges from saved state, conflicts with optimistic updates. High implementation cost, low unique value. | Archive/restore (30-day soft delete already built) serves the "oops" case. Audit log shows change history. |
| Drag-and-drop row reordering | "Sort products by hand" | Products have no natural user-defined sort order; business logic dictates order (status, date, barcode). Manual ordering breaks for 1450 rows and creates false precision. | Sort by meaningful fields (status, category, date) via column header click |
| Bulk import from Excel/CSV | "Migrate from Google Sheets" | One-time migration tool, not a recurring UX feature. High edge-case surface area (encoding, column matching, validation errors). Blocks roadmap unnecessarily. | Manual data entry for new records; data migration as a separate one-time script if needed |
| Gallery/Kanban view | "Visual product management" | Kanban requires status-as-column metaphor which doesn't map to product status lifecycle. Gallery requires product photos which aren't in scope. Adds significant complexity for no clear workflow benefit. | Table view with status-based row coloring achieves visual scan. Detail panel for image viewing when photos added later. |
| Formula fields with custom expressions | "Calculate margin in the table" | Formula engine (like Notion's) is a separate product feature requiring parser, dependency graph, error handling. Finance data already comes from external data service — duplicating it in formula fields creates divergence. | Finance tab in detail page shows all calculated metrics from the real data source |
| Notifications and activity feed | "See what changed" | No user identity system yet (auth is future milestone). Notifications without identity context are useless. | Audit log in admin panel serves change tracking. Add notifications when auth exists. |

---

## Feature Dependencies

```
[Reference field resolution in table]
    └──requires──> [Correct column key mapping in view-columns.ts]

[Editable DetailPanel]
    └──requires──> [Lookup dropdowns for reference fields]
                       └──requires──> [Lookups loaded from /api/matrix/lookups/*]

[Create new record button]
    └──requires──> [Editable DetailPanel] (same form components reused in creation modal)

[Filter by field]
    └──requires──> [Sort by column] (same URL query param wiring pattern)

[Hierarchy drill-down in sidebar]
    └──requires──> [Filter by field] (drill-down IS a filter)
                └──enhances──> [Related counts as clickable links]

[Working stock tab columns]
    └──requires──> [Batch stock data loading] (new: list endpoint needs stock data OR separate batch call)
    └──conflicts──> [Finance tab columns in table] (both require batch external data — implement one pattern first)

[Inherited field display in child records]
    └──requires──> [Editable DetailPanel] (context layout is part of the same panel)

[Section-grouped fields in DetailPanel]
    └──enhances──> [All fields from spec in DetailPanel]
    └──enhances──> [Inherited field display in child records]
```

### Dependency Notes

- **Editable DetailPanel requires Lookup dropdowns:** Without populated select options, editing category/collection/factory/status/color is impossible. The lookups API exists; the missing piece is loading and caching them in the store.
- **Hierarchy drill-down IS a filter:** MatrixSidebar drill-down and FilterBar are the same mechanism. Building filter URL param wiring first enables drill-down as a special case (filter[model_id]=X).
- **Working stock table columns conflict with finance table columns:** Both require the same unsolved problem — fetching external data for a full list of rows. Solve the stock batch pattern once, then finance follows. Do not attempt both simultaneously.
- **Create requires DetailPanel:** The same field-type-aware form components (text, number, select-with-lookup) used in the edit panel are reused in the creation dialog. Build edit first, extract components, then wire creation.

---

## MVP Definition

### Launch With (v1 — "Replaces Google Sheets for daily use")

These features together make the tool usable for the actual workflow: browsing the product catalog, editing records, and creating new ones.

- [ ] **All field display names correct** — zero technical names shown to user. S complexity. No backend work.
- [ ] **Reference fields show values in table** — category/factory/collection not "—". S. Fix column key mapping.
- [ ] **All fields visible in DetailPanel (read mode)** — section-grouped, all 22 ModelOsnova fields, all Artikul fields, all Tovar fields. M.
- [ ] **DetailPanel edit mode** — click field → edit, with correct input type per field. Select fields use loaded lookup options. M.
- [ ] **Lookup options loaded at startup** — kategorii, kollekcii, fabriki, statusy, razmery, cveta loaded once into store. S-M.
- [ ] **Create new record** — "+ New" button in topbar opens creation panel with required fields. M. Reuses DetailPanel edit components.
- [ ] **Status filter** — filter active vs archived records. S. Critical for daily use (most users only want active records).
- [ ] **Sort by column** — click column header to sort asc/desc. S.
- [ ] **Status badge display** — colored badge not plain text. S.
- [ ] **Read-only protection for system IDs** — barkod, nomenklatura_wb, ozon IDs cannot be edited. S.

### Add After Validation (v1.x — "Better than Google Sheets")

- [ ] **Hierarchy drill-down in sidebar** — trigger: users frequently ask "show me all articles for Vuki". M.
- [ ] **Related counts as clickable links in DetailPanel** — trigger: navigation from detail to children is a common workflow. S.
- [ ] **Column visibility toggle** — trigger: users want different column sets without saving a view. S.
- [ ] **Saved views wired in UI** — backend exists, wire the "+ Create View" tab to actually save/load column configs. M.
- [ ] **Stock tab with real data** — working stock columns in table using batch fetch. M. Trigger: finance/ops team needs quick stock scan.
- [ ] **Finance tab with real data in table** — working finance columns. M. After stock pattern proven.
- [ ] **Keyboard navigation in DetailPanel** — Tab/Enter/Escape. S. Trigger: power user feedback.

### Future Consideration (v2+)

- [ ] **Inherited field display (parent context in child detail)** — shows ModelOsnova fields in Artikul detail panel. M. Defer: adds layout complexity; explicit navigation to parent record is sufficient for v1.
- [ ] **Status-based row coloring** — M because requires consistent status_id semantics across entities. Defer: table is readable without it.
- [ ] **Full-text search within entity list** — search bar above table filtering current entity rows. S-M. Backend supports it. Defer: GlobalSearch (Cmd+K) covers cross-entity search; per-table filter is nice-to-have.
- [ ] **Export to CSV** — S backend + M frontend. Defer: Google Sheets remains for exports until sync is built.
- [ ] **Certificates linking to ModelOsnova** — certificate detail with linked models list. M. Defer: certificates are viewed rarely compared to models/articles/products.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Field display names | HIGH | LOW | P1 |
| Reference fields show values | HIGH | LOW | P1 |
| All fields in DetailPanel (read) | HIGH | MEDIUM | P1 |
| DetailPanel edit mode | HIGH | MEDIUM | P1 |
| Lookup options loading | HIGH | MEDIUM | P1 |
| Create new record | HIGH | MEDIUM | P1 |
| Status filter | HIGH | LOW | P1 |
| Sort by column | MEDIUM | LOW | P1 |
| Status badge display | MEDIUM | LOW | P1 |
| Read-only field protection | HIGH | LOW | P1 |
| Hierarchy drill-down | HIGH | MEDIUM | P2 |
| Related counts as links | MEDIUM | LOW | P2 |
| Column visibility toggle | MEDIUM | LOW | P2 |
| Saved views wired in UI | MEDIUM | MEDIUM | P2 |
| Working stock table columns | MEDIUM | HIGH | P2 |
| Working finance table columns | MEDIUM | HIGH | P2 |
| Keyboard navigation | MEDIUM | LOW | P2 |
| Inherited field display | LOW | MEDIUM | P3 |
| Status-based row coloring | LOW | LOW | P3 |
| Per-entity full-text filter | LOW | MEDIUM | P3 |
| Export to CSV | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1 launch (replaces Google Sheets)
- P2: Should have, add in v1.x after core works
- P3: Nice to have, v2+

---

## Feature Categories: Complexity Reference

Organized by the downstream consumer's requested categories:

### Navigation

| Feature | Size | Notes |
|---------|------|-------|
| Sidebar entity switching (existing) | — | Already works |
| Hierarchy drill-down sidebar context | M | Requires filter wiring; shows filtered child entity list |
| Breadcrumb trail in topbar | S | Shows "Модели > Vuki > Артикулы" context; pure UI |
| "Jump to entity" from reference field | S | Clickable reference values open detail panel for referenced entity |

### Table View

| Feature | Size | Notes |
|---------|------|-------|
| Correct column display names (fix existing) | S | Mapping fix in view-columns.ts |
| Reference field values (fix existing) | S | Column key fix; backend already returns `_name` variants |
| Sort by column header click | S | Add onClick to `<th>`, update URL params or local state |
| Status badge in status column | S | Replace plain text cell with Badge component |
| Column visibility toggle | S | Popover with checkbox list; persists to localStorage |
| Status-based row background | S | CSS class from status_id |
| Pagination controls | S | Connect to backend page/per_page; or increase limit to 500 |
| "+ New" row at table bottom | M | Inline creation row OR triggers panel |
| Stock data in stock tab columns | H | Requires batch fetch of external data for all visible rows |
| Finance data in finance tab columns | H | Same batch fetch pattern; build after stock |

### Detail Panel

| Feature | Size | Notes |
|---------|------|-------|
| All ModelOsnova fields (22 fields, read) | M | Section-grouped layout; all fields from `ModelOsnovaCreate` schema |
| All Artikul fields (6 fields, read) | S | Simpler than ModelOsnova |
| All Tovar fields (12 fields, read) | S | Several read-only marketplace IDs |
| Edit mode with field-type inputs | M | text/number/select/textarea; select needs lookup options loaded |
| Select field options from lookups API | M | Load kategorii/kollekcii/fabriki/statusy/razmery/cveta at app startup |
| Save/cancel edit buttons | S | Optimistic update + PATCH; revert on error |
| Related entity counts as clickable links | S | Count badges → navigate to filtered list |
| Parent context section (inherited fields) | M | Show read-only parent fields in child detail; deferred to v1.x |
| Expand to full page button (existing) | — | Already exists in DetailPanel header |

### Field Management

| Feature | Size | Notes |
|---------|------|-------|
| ManageFieldsDialog (existing custom fields) | — | Already built for JSONB custom fields |
| System field visibility toggle | S | Show/hide built-in fields in the manage fields dialog |
| Field section assignment | M | Assign fields to sections (Основные / Размеры / etc.) |
| Column width persistence | S | Store widths in localStorage or hub.ui_preferences (backend exists) |

### Filtering and Sorting

| Feature | Size | Notes |
|---------|------|-------|
| Status filter (active/archived) | S | Dropdown above table; appends filter[status_id]= to API call |
| Sort by field (single column) | S | Column header click; stored in local state; appends sort= param |
| Category filter | S | Same pattern as status filter |
| Multi-field filter bar | M | Filter builder UI; backend supports multiple filter[] params |
| Saved view filter persistence | M | Serialize filters to hub.saved_views; backend already exists |

### CRUD Operations

| Feature | Size | Notes |
|---------|------|-------|
| Create ModelOsnova | M | Form with required fields (kod) + optional; POST /api/matrix/modeli_osnova |
| Create Artikul | M | Requires model_id and cvet_id selectors; POST /api/matrix/artikuly |
| Create Tovar | M | Requires artikul_id and razmer_id; barkod as required field |
| Create reference entities (color/factory/etc.) | M | Same pattern; simpler field sets |
| Archive (soft delete, existing UI) | — | DeleteConfirmDialog + DeleteChallengeDialog already built |
| Restore from archive (admin) | — | Already built in admin panel |

### Data Display

| Feature | Size | Notes |
|---------|------|-------|
| Display name mapping (all entities) | S | Define `FIELD_DISPLAY_NAMES` mapping in frontend lib |
| Reference field name resolution | S | Backend already provides `_name` fields; fix column key references |
| Stock KPI cards in detail panel (existing) | — | stock-tab.tsx built with real StockResponse data |
| Finance KPI + expense table in detail panel (existing) | — | finance-tab.tsx built with real FinanceResponse data |
| Number formatting (₽, шт, %) | S | Shared formatter util; apply to table cells and detail panel |
| Date formatting | S | Created/updated timestamps in human-readable format |
| Empty value display "—" (partially existing) | S | Standardize across all field renderers |

### Bulk Operations

| Feature | Size | Notes |
|---------|------|-------|
| Bulk status update (existing MassEditBar) | — | Already built for status_id 1 and 3 |
| Bulk arbitrary field update | M | Add field picker to MassEditBar; POST bulk endpoint supports generic changes dict |
| Select all visible rows | S | "Select all" checkbox in table header; `selectAllRows` action exists in store |
| Bulk archive | S | Extend MassEditBar with "Архивировать выбранные" button |

---

## Competitor Feature Analysis

| Feature | Notion Database | Airtable | Our Approach |
|---------|-----------------|----------|--------------|
| Field types | 20+ types including formula, rollup | 20+ types including lookup | Use existing 8 types (text/number/select/etc); formula and rollup deferred to v2 |
| Row detail panel | Full-page record view | Expand row to side panel | Side panel (existing shell) + full-page route (existing); focus on making it functional first |
| Filtering | Filter builder, saved filters | Inline filter builder | Status filter for v1; full filter builder for v1.x using existing backend support |
| Multiple views | Gallery, Kanban, Calendar, Grid | Grid, Calendar, Kanban, Gallery | Grid only; tabs for data mode (spec/stock/finance) not layout mode |
| Relations between tables | Relation field type | Link to another record | Relations shown as read-only display + clickable navigation; no bi-directional editing in v1 |
| Hierarchy | Page nesting | Group by field | Expand/collapse rows in table (existing) + drill-down filter context |
| Collaboration | Real-time, presence | Real-time, comments | Single user + audit log; no real-time (non-goal by design) |

---

## Sources

- `/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.planning/PROJECT.md` — project goals and known problems
- `/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md` — full system design spec
- `/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/docs/superpowers/specs/2026-03-21-product-matrix-phase6-design.md` — external data integration spec
- Codebase inspection: `wookiee-hub/src/components/matrix/`, `services/product_matrix_api/models/schemas.py`, `wookiee-hub/src/lib/view-columns.ts`, `wookiee-hub/src/stores/matrix-store.ts`
- Pattern references: Notion database UI, Airtable grid view, Akeneo PIM field management patterns (prior knowledge, MEDIUM confidence)

---

*Feature research for: Notion-like PIM Editor — Wookiee Product Matrix*
*Researched: 2026-03-22*
