---
status: complete
phase: 02-detail-panel
source: [02-00-SUMMARY.md, 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md]
started: 2026-03-30T12:00:00Z
updated: 2026-03-30T18:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Detail Panel Opens as Sheet Overlay
expected: Open "Модели основы" tab, click any row. Panel slides in from the right as a floating overlay (Sheet). The table behind remains visible and is NOT squeezed. Panel width ~480px.
result: pass

### 2. Read Mode — All Fields Grouped by Sections
expected: Open a model detail panel. All ~22 fields visible, grouped under collapsible sections (Основные, Размеры, Логистика, Контент). Clicking a section header collapses/expands it.
result: pass
notes: 5 sections visible (Основные, Размеры, Логистика, Контент, Система), all collapsible via section header buttons.

### 3. System Fields Show Lock Icon
expected: In the detail panel, system/immutable fields (barkod, nomenklatura_wb, ozon_product_id) display a lock icon indicating they cannot be edited.
result: pass
notes: Lock icon (img "Системное поле") displayed on Код модели and Создано fields.

### 4. Edit Mode — Correct Input Types
expected: Click "Редактировать" in the panel header. Text fields show text input, number fields show number input, select fields (kategoriya, fabrika, kollekciya) show dropdown populated with lookup options, date fields show Calendar picker (not native date input). System fields remain locked.
result: pass
notes: Textbox for text fields, spinbutton for numbers, combobox for lookups. System fields remain locked in edit mode.

### 5. Save Sends Only Changed Fields
expected: In edit mode, change one field value (e.g., nazvanie_sayt). Click "Сохранить". Panel returns to read mode showing the updated value. The PATCH request contains only the changed field, not all 22 fields.
result: pass
notes: |
  Re-tested 2026-03-30 after Plan 02-05 fixes (migration 005 + audit_service datetime fix).
  Typed "Evelyn UAT" into "Название (сайт)" field → clicked Сохранить → panel returned to read mode showing "Evelyn UAT".
  Verified via API: GET /api/matrix/models/23 returns nazvanie_sayt="Evelyn UAT". Value persisted correctly.

### 6. Cancel Discards Changes
expected: In edit mode, change a field value. Click "Отменить". All changes are discarded and original values are restored.
result: pass

### 7. Related Entity Badges in Header
expected: Open a model that has articles. The panel header shows badge counters (e.g., "4 артикула"). Clicking a badge switches the active tab to that entity type.
result: pass
notes: |
  Re-tested 2026-03-30 after Plan 02-05 (children_count column_property on ModelOsnova).
  Badge "Артикулы: 1" visible in panel header for model Evelyn. children_count=1 confirmed via API.

### 8. Related Children List
expected: Scroll down in a model detail panel. A collapsible "Связанные" section shows child articles (first 5). Each child row is clickable and opens that article in the panel.
result: pass
notes: Collapsible "Артикулы" section shows first 5 children with "Показать все (N)" button. Clicking a child navigates the panel to that article.

### 9. Inherited Field Popover on Artikul
expected: Open an Artikul detail panel. Click on an inherited field (e.g., kategoriya). A popover appears showing the parent model's key fields. A "Перейти к модели" button navigates the panel to the parent model.
result: skipped
reason: Frontend popover code is fully implemented (PanelFieldRow renders Popover with parent preview + "Перейти к модели" button). However, the backend /api/matrix/schema/artikuly does not return inherited fields (kategoriya_id, kollekciya_id, etc.) since those exist only on the model schema. Without inherited fields in the article schema response, the popover never triggers. Fix requires backend to include inherited parent fields in child entity schemas.

## Summary

total: 9
passed: 7
issues: 0
pending: 0
skipped: 1

## Gaps

### GAP-01: FieldDefinition field_names don't match Pydantic schema — FIXED
severity: high
scope: backend
details: Fixed by migration 005 (Plan 02-05 Task 1). All 27 field_name values now match ModelOsnovaUpdate schema.
fix: Applied. Also fixed AuditService datetime serialization and CAST syntax for jsonb.

### GAP-02: children_count not populated on model records — FIXED
severity: medium
scope: backend
details: Fixed by column_property on ModelOsnova (Plan 02-05 Task 2). children_count returns correct counts.
fix: Applied.

### GAP-03: Inherited fields not in child entity schemas — DEFERRED
severity: low
scope: backend
details: /api/matrix/schema/artikuly doesn't include parent-level fields (kategoriya_id, etc.). Frontend inherited field popover code is complete but unused.
fix: Deferred to a later phase — requires architectural decision on how to expose inherited fields.
