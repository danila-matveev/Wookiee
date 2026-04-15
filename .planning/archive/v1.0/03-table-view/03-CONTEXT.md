# Phase 3: Table View - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The table displays correct human-readable data for all column types, supports sorting by any column, lets users show/hide columns, shows status badges and archive row styling, includes pagination, and allows creating new records. Requirements: TABLE-01..07, CRUD-01, CRUD-02.

</domain>

<decisions>
## Implementation Decisions

### Column display & FieldDefinition-driven columns
- Columns auto-generated from backend FieldDefinitions (where `is_visible=true`)
- `display_name` from FieldDefinition becomes column header (TABLE-01)
- No more hardcoded Column[] arrays per entity page — single unified approach
- Consistent with Phase 2 panel (same metadata source)
- Adding a field in admin → it appears in both table and panel automatically

### Reference field resolution
- Frontend lookup resolution using Zustand lookup cache (already built in Phase 2)
- `_id` fields resolved to human names via cached lookup tables (kategorii, kollekcii, fabriki, statusy, razmery, importery)
- No dependency on backend `_name` join fields — frontend resolves independently
- Lookup cache prefetched on entity switch (reuse Phase 2 prefetch pattern)

### Inline table editing
- Claude's discretion — recommend removing inline editing for consistency with Phase 2 decision (all editing in Detail Panel)

### Status badges
- Colored badge in status column: green "Активный", gray "Архив"
- Archive row styling: Claude's discretion (recommend subtle opacity or muted background)

### Sorting
- Server-side sorting via `?sort=field&order=asc|desc` query params
- Click column header → ascending; click again → descending; sort indicator on active column
- Requires backend endpoint changes to accept sort params

### Pagination
- Classic pagination with page controls at bottom: « 1 2 3 ... N »
- Backend already has `page`/`per_page` params — wire them up
- Show total count and current page info
- Replace current `per_page: 200` fixed fetch

### Column visibility toggle
- Popover with checkboxes (Notion-style) — triggered from "Настроить поля" button in topbar
- Replace current ManageFieldsDialog with lightweight popover
- Column list driven by FieldDefinitions
- Persistence: Claude's discretion (recommend localStorage per entity or Zustand-only for now, saved views in Phase 4)

### Create new record
- Button "+ Создать" in topbar → modal Dialog with form
- Show only required/essential fields (kod, kategoriya_id, status_id for models)
- Lookup select fields for reference fields (reuse lookup cache)
- After successful creation: close dialog, refresh table, open new record in Detail Panel for further editing
- Entity-aware: form fields adapt to current entity type via FieldDefinitions

### Design approach
- Use `frontend-design:frontend-design` skill for all UI component design
- Use `frontend-design` skill for table redesign, badge styling, pagination controls, column toggle popover, and create form dialog

### Claude's Discretion
- Inline table editing: remove or keep for simple fields
- Archive row styling approach (opacity vs muted background)
- Column visibility persistence (localStorage vs Zustand-only)
- Reference cell interactivity (plain text vs subtle link)
- Pagination page size default (25 vs 50)
- Sort indicator visual design

</decisions>

<specifics>
## Specific Ideas

- "Использовать frontend-design:frontend-design скилл для создания дизайна компонентов"
- Columns should feel like Notion's table — clean headers, readable data, no clutter
- Status badge should be immediately scannable — green/gray color coding
- Pagination should show total count so user knows how many records exist

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DataTable` (data-table.tsx): Custom `<table>` with expand/select/children — needs refactoring for FieldDef-driven columns and server sort
- `TableCell` (table-cell.tsx): Has inline edit logic — may be simplified to read-only cell renderer
- `ManageFieldsDialog` (manage-fields-dialog.tsx): Full dialog for field management — replace with lightweight column visibility popover
- `ViewTabs` (view-tabs.tsx): Built-in and saved view tabs — already wired up
- `matrixApi.listModels/listArticles/listProducts`: List endpoints with `per_page` param — need `page`, `sort`, `order` params added
- Zustand `lookupCache`: Already populated from Phase 2 — reuse for reference resolution
- `ENTITY_BACKEND_MAP` in panel/types.ts: Maps frontend slugs to backend entity types

### Established Patterns
- FieldDefinition system: `entity_type`, `field_name`, `display_name`, `field_type`, `section`, `sort_order`, `is_system`, `is_visible`
- Zustand store for all matrix state (activeEntity, selectedRows, expandedRows, detailPanelId)
- `useApiQuery` hook for data fetching with dependency array
- shadcn components (Button, Dialog, Popover, Badge, Checkbox, Select)
- `verbatimModuleSyntax: true` — `import type` required

### Integration Points
- `models-page.tsx`, `articles-page.tsx`, `products-page.tsx`: Each will switch to FieldDef-driven columns
- `matrix-topbar.tsx`: Add "+ Создать" button, replace ManageFieldsDialog with popover
- Backend list endpoints: Need `sort`, `order`, `page` params wired through to SQLAlchemy ORDER BY
- `LOOKUP_TABLE_MAP` in panel/types.ts: Maps field_name → lookup table for resolution

</code_context>

<deferred>
## Deferred Ideas

- Virtual scrolling for 1000+ rows — v2 (PERF-01)
- Stock/finance data in table columns — v2 (PERF-02)
- Quick-edit hover on table cell — v2 (ADV-03)
- Breadcrumb trail in topbar — v2 (ADV-04)
- Column reorder via drag-and-drop — future enhancement
- Bulk operations (mass edit, bulk archive) — v2 (BULK-01, BULK-02)

</deferred>

---

*Phase: 03-table-view*
*Context gathered: 2026-03-26*
