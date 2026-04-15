---
phase: 02-detail-panel
plan: 02
subsystem: matrix-panel-read-mode
tags: [ui-components, base-ui, zustand, typescript, panel, popover, collapsible]
dependency_graph:
  requires: [02-01]
  provides: [detail-panel-sheet, panel-body-read, panel-section-collapsible, panel-field-row-popover]
  affects: [02-03, 02-04]
tech_stack:
  added: ["@base-ui/react/collapsible (PanelSection)", "@base-ui/react/popover (inherited field popover)"]
  patterns:
    - "Sheet overlay replaces embedded aside for detail panel"
    - "FieldDefinition-driven section grouping with sort_order"
    - "Inherited field popover: two-step parent navigation via openDetailPanel"
    - "Select field value resolved from _name counterpart in entity data"
    - "COMPUTED_FIELD_PATTERN exclusion at render level"
key_files:
  created:
    - wookiee-hub/src/components/matrix/panel/panel-header.tsx
    - wookiee-hub/src/components/matrix/panel/panel-body.tsx
    - wookiee-hub/src/components/matrix/panel/panel-section.tsx
    - wookiee-hub/src/components/matrix/panel/panel-field-row.tsx
  modified:
    - wookiee-hub/src/components/matrix/detail-panel.tsx
decisions:
  - "PanelFieldRow returns null for COMPUTED_FIELD_PATTERN fields rather than filtering in PanelBody — simpler co-location of logic"
  - "Parent entity secondary fetch keyed on data!=null dep so it refetches only after main entity arrives"
  - "PopoverTrigger uses render prop with a div to wrap non-button content for inherited field"
  - "Section ordering uses SECTION_ORDER lookup with fallback to alphabetical for unknown sections"
metrics:
  duration: "4 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 2 Plan 2: Read-Mode Detail Panel — Sheet, Sections, Inherited Field Popovers Summary

Sheet-based detail panel with entity-aware data fetching, FieldDefinition-driven collapsible section grouping, system field lock indicators, and inherited field popovers with two-step parent navigation.

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Rewrite detail-panel.tsx as Sheet overlay with entity-aware fetching | 75e3aaf | detail-panel.tsx, panel-header.tsx |
| 2 | Build section-grouped read-mode body with collapsible sections, field rows, inherited popovers | 1904c9b | panel-body.tsx, panel-section.tsx, panel-field-row.tsx |

## What Was Built

### detail-panel.tsx (complete rewrite)
- Replaced hardcoded `<aside>` with `<Sheet>` controlled by `detailPanelId` Zustand state
- Entity-aware fetching: `detailPanelEntityType` dispatches `getModel`/`getArticle`/`getProduct`
- Secondary parent entity fetch: articles fetch parent model, products fetch parent article
- Helper functions: `fetchEntity`, `fetchParentEntity`, `getParentEntityType`, `getParentEntityId`
- Loading skeleton (4 rows), error state, "not found" fallback
- `isEditing` local state hardcoded to false in this plan; edit toggle is wired (Plan 03 implements full edit mode)
- Passes `parentData`, `parentEntityType`, `parentEntityId` to `PanelBody`

### panel-header.tsx
- Props: `title`, `onClose`, `isEditing`, `onToggleEdit`
- Title truncates with `truncate` class, large semibold text
- "Редактировать" / "Отменить" ghost button with Pencil icon
- Close (X) button with aria-label

### panel-section.tsx
- Built on `@base-ui/react/collapsible`: `Collapsible.Root`, `Collapsible.Trigger`, `Collapsible.Panel`
- `defaultOpen={true}` — sections start expanded
- Trigger: uppercase xs semibold muted-foreground label + rotating ChevronDown
- `border-b` separator between sections, `last:border-b-0` to avoid bottom border on last section

### panel-field-row.tsx
- **Computed fields**: returns `null` if `COMPUTED_FIELD_PATTERN.test(def.field_name)` — _name fields excluded
- **Lock icon**: shown for `IMMUTABLE_FIELDS` members and `is_system` fields (subtle, non-intrusive)
- **Null values**: display as "—" em-dash via `formatValue()`
- **Inherited field visual**: subtle `bg-muted/30` tint + `ArrowUpRight` inline icon on label
- **Inherited field popover**: wraps content in Base UI Popover with `PopoverTrigger render` prop
  - Shows parent title + 3-4 key preview fields in a compact card
  - "Перейти к модели/артикулу" button calls `openDetailPanel(parentEntityId, parentEntityType)`
  - Parent entity type labels: models → "модели", articles → "артикулу"

### panel-body.tsx
- Fetches `FieldDefinition[]` via `matrixApi.listFields(ENTITY_BACKEND_MAP[entityType])`
- Groups fields by `section`, sorted: Основные(0) → Размеры(1) → Логистика(2) → Контент(3) → alphabetical → Другое
- Skips `is_visible === false` fields and `COMPUTED_FIELD_PATTERN` fields
- `resolveDisplayValue`: for `field_type === "select"`, reads `_name` counterpart from entity data
- `INHERITED_FIELDS` map defines which fields are inherited per entity type:
  - `articles`: kategoriya_id, kollekciya_id, fabrika_id, material, sostav_syrya
  - `products`: same + artikul
- Passes inherited metadata to `PanelFieldRow` for popover rendering
- Skeleton (5 rows) while FieldDefinition loads

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Created
- [x] `wookiee-hub/src/components/matrix/panel/panel-header.tsx` — exists
- [x] `wookiee-hub/src/components/matrix/panel/panel-body.tsx` — exists
- [x] `wookiee-hub/src/components/matrix/panel/panel-section.tsx` — exists
- [x] `wookiee-hub/src/components/matrix/panel/panel-field-row.tsx` — exists

### Files Modified
- [x] `wookiee-hub/src/components/matrix/detail-panel.tsx` — Sheet wrapper present

### Commits
- [x] 75e3aaf — Task 1 (detail-panel.tsx + panel-header.tsx)
- [x] 1904c9b — Task 2 (panel-body.tsx + panel-section.tsx + panel-field-row.tsx)

### Verification Checks
- [x] `npx tsc --noEmit` passes with zero errors
- [x] `grep -r "Collapsible" panel/` confirms Base UI usage in panel-section.tsx
- [x] `grep "IMMUTABLE_FIELDS" panel-field-row.tsx` confirms read-only protection
- [x] `grep "Popover" panel-field-row.tsx` confirms inherited field popover
- [x] `grep "openDetailPanel" panel-field-row.tsx` confirms parent navigation from popover

## Self-Check: PASSED
