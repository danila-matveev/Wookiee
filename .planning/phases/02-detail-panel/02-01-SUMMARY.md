---
phase: 02-detail-panel
plan: 01
subsystem: matrix-panel-foundation
tags: [ui-primitives, zustand, pydantic, typescript, base-ui]
dependency_graph:
  requires: [02-00]
  provides: [sheet-ui, panel-types, store-extensions, schema-expansion]
  affects: [02-02, 02-03, 02-04]
tech_stack:
  added: ["@base-ui/react/drawer (Sheet wrapper)"]
  patterns: ["Base UI Drawer as non-modal Sheet overlay", "CSS rtl trick for left-edge resize", "Zustand lookup cache", "Pydantic Read schema field parity"]
key_files:
  created:
    - wookiee-hub/src/components/ui/sheet.tsx
    - wookiee-hub/src/components/matrix/panel/types.ts
  modified:
    - wookiee-hub/src/stores/matrix-store.ts
    - wookiee-hub/src/lib/matrix-api.ts
    - services/product_matrix_api/models/schemas.py
decisions:
  - "Sheet built on @base-ui/react/drawer with modal=false — non-modal overlay that does not trap focus or block table interaction"
  - "CSS direction:rtl on outer wrapper + direction:ltr on inner wrapper enables left-edge drag resize without JS"
  - "openDetailPanel extended with optional entityType to avoid breaking existing callers"
  - "All 16 missing fields added to ModelOsnovaRead matching exact types from ModelOsnovaCreate"
metrics:
  duration: "5 minutes"
  completed: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 2 Plan 1: Panel Foundation — Sheet, Types, Store, Schema Summary

Sheet UI primitive on Base UI Drawer with panel type contracts, extended Zustand store (entity tracking + lookup cache), and ModelOsnovaRead expanded to full 22-field parity with ModelOsnovaCreate.

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Sheet UI primitive and panel type contracts | df75a08 (hub) | sheet.tsx, panel/types.ts |
| 2 | Expand Zustand store, backend schema, frontend types | 73742da (hub), 94d9f9f (main) | matrix-store.ts, matrix-api.ts, schemas.py |

## What Was Built

### Sheet UI Component (`sheet.tsx`)
- Built on `@base-ui/react/drawer` with `modal={false}` — the panel floats over the table without squeezing it or blocking interaction
- `SheetContent`: fixed right-side overlay, `w-[480px]` default, `min-w-[400px]` / `max-w-[800px]`
- Slide-in/out animation via `data-open:slide-in-from-right` / `data-closed:slide-out-to-right`
- Horizontal resize from left edge: outer wrapper uses `direction: rtl` + CSS `resize: horizontal`, inner `div` restores `direction: ltr`
- Named exports: `Sheet`, `SheetContent`, `SheetOverlay`, `SheetPortal`, `SheetClose`, `SheetTitle`, `SheetTrigger`
- `data-slot` attributes and `cn()` className merging — consistent with dialog.tsx pattern

### Panel Type Contracts (`panel/types.ts`)
- `IMMUTABLE_FIELDS` Set — 7 marketplace-pulled fields that are locked forever (barkod, nomenklatura_wb, ozon_product_id, etc.)
- `COMPUTED_FIELD_PATTERN` — `/_name$/` regex to exclude join-computed fields from edit mode
- `ENTITY_TITLE_FIELD` — maps entity slug to its header title field (models→kod, articles→artikul, products→artikul_ozon)
- `LOOKUP_TABLE_MAP` — maps FK field names to lookup table names for select dropdowns
- `ENTITY_BACKEND_MAP` — maps frontend slugs to backend entity_type strings (mirrors FIELD_DEF_ENTITY_MAP)
- `PanelFieldRowProps` interface — contract for field row components (def, value, editValue, isEditing, lookupOptions, onChange)
- `PanelSectionData` interface — named group of FieldDefinitions for collapsible sections

### Zustand Store Extensions (`matrix-store.ts`)
- `detailPanelEntityType: MatrixEntity | null` — tracks which entity type is currently shown in panel
- `lookupCache: Record<string, LookupItem[]>` — keyed by lookup table name; avoids refetching same lookup data
- `setLookupCache(table, items)` — action to populate cache after getLookup() API calls
- `openDetailPanel(id, entityType?)` — optional second argument; existing callers unaffected (backward compatible)
- `closeDetailPanel()` — now also clears `detailPanelEntityType`
- `import type { LookupItem }` — correct verbatimModuleSyntax usage

### Backend Schema (`schemas.py`) + Frontend Types (`matrix-api.ts`)
Added 16 fields to `ModelOsnovaRead` (and matching `ModelOsnova` interface):

| Field | Type | Category |
|-------|------|----------|
| sku_china | str / null | Internal SKU |
| upakovka | str / null | Packaging |
| ves_kg | float / null | Logistics |
| dlina_cm | float / null | Logistics |
| shirina_cm | float / null | Logistics |
| vysota_cm | float / null | Logistics |
| kratnost_koroba | int / null | Logistics |
| srok_proizvodstva | str / null | Production |
| komplektaciya | str / null | Content |
| composition | str / null | Content |
| tegi | str / null | Content |
| notion_link | str / null | Content |
| gruppa_sertifikata | str / null | Compliance |
| nazvanie_etiketka | str / null | Label |
| opisanie_sayt | str / null | Website |
| (nazvanie_sayt was already present) | — | — |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Created
- [x] `wookiee-hub/src/components/ui/sheet.tsx` — exists
- [x] `wookiee-hub/src/components/matrix/panel/types.ts` — exists

### Files Modified
- [x] `wookiee-hub/src/stores/matrix-store.ts` — detailPanelEntityType present
- [x] `wookiee-hub/src/lib/matrix-api.ts` — ves_kg present
- [x] `services/product_matrix_api/models/schemas.py` — ves_kg present in ModelOsnovaRead

### Commits
- [x] df75a08 — Task 1 (wookiee-hub)
- [x] 73742da — Task 2 (wookiee-hub)
- [x] 94d9f9f — Task 2 (main repo backend schema)

### TypeScript
- [x] `npx tsc --noEmit` passes with zero errors

## Self-Check: PASSED
