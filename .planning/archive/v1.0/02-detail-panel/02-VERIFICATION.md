---
phase: 02-detail-panel
verified: 2026-03-30T16:30:00Z
status: gaps_found
score: 7/8 requirements satisfied
re_verification:
  previous_status: human_needed
  previous_score: 9/9 must-haves verified (pre-UAT)
  gaps_closed:
    - "GAP-01: FieldDefinition field_names now match ModelOsnovaUpdate Pydantic schema (migration 005 created)"
    - "GAP-02: children_count column_property added to ModelOsnova ORM model"
  gaps_remaining:
    - "Migration 005 must be applied to Supabase — until then GAP-01 and GAP-02 fixes are code-only"
    - "GAP-03: Inherited field popover never triggers — child entity schemas missing parent-level fields"
  regressions: []
gaps:
  - truth: "PANEL-08: Related entity counts appear in header as clickable badges"
    status: partial
    reason: "Frontend badge code is correct. Backend column_property for children_count exists in ORM and schema. However migration 005 has NOT been applied to Supabase yet — the column_property correlated subquery only returns a value after migration runs and DB reflects the new column_property. Until migration 005 is applied, badges will not appear."
    artifacts:
      - path: "services/product_matrix_api/migrations/005_fix_field_definitions.sql"
        issue: "Migration created but not yet applied to Supabase production DB"
      - path: "sku_database/database/models.py"
        issue: "children_count column_property code is present and correct — awaits DB migration"
    missing:
      - "Run migration 005 on Supabase to activate children_count and corrected field_names"
  - truth: "PANEL-03/PANEL-04/PANEL-05/PANEL-06: Inherited field popover is wired for Artikul and Tovar entities"
    status: failed
    reason: "GAP-03 was explicitly deferred. The frontend popover code in panel-field-row.tsx is complete, but the backend /api/matrix/schema/artikuly does not return inherited parent-level fields (kategoriya_id, kollekciya_id, etc.). The INHERITED_FIELDS map in panel-body.tsx lists these field names, but since they are absent from the FieldDefinition rows returned for child entities, the popover is never rendered. This is classified as a deferred architectural gap, not a blocker for core PANEL requirements."
    artifacts:
      - path: "wookiee-hub/src/components/matrix/panel/panel-body.tsx"
        issue: "INHERITED_FIELDS map references fields that are absent from child entity FieldDefinition DB rows"
    missing:
      - "Backend: include parent-level fields (with is_inherited flag) in child entity schema responses, OR add those field_definition rows to artikuly/tovary entities in DB"
human_verification:
  - test: "Apply migration 005 and open a model detail panel — verify field names match and edits persist"
    expected: "After migration 005 runs on Supabase: (1) field_names in detail panel match ModelOsnovaUpdate fields (ves_kg not ves_g, dlina_cm not dlina_sm, etc.); (2) editing a field and saving sends correct field name; value persists on reload"
    why_human: "Migration must be applied to live DB before runtime behavior can be confirmed"
  - test: "Open a model with child articles — verify badge counter appears in panel header"
    expected: "Panel header shows badge 'Артикулы N' where N > 0 when the model has child articles. Clicking the badge switches the active tab to Articles."
    why_human: "children_count is populated by correlated subquery at query time — requires live DB with migration 005 applied"
  - test: "Open an Artikul panel — confirm inherited field popover behavior (or absence)"
    expected: "Currently: no popover trigger since inherited fields are absent from artikuly FieldDefinition rows. After GAP-03 is resolved: clicking kategoriya on an Artikul shows parent model preview with 'Перейти к модели' button."
    why_human: "Requires DB state for inherited field definitions; currently deferred per architectural decision"
  - test: "Enter edit mode on a model — verify correct input types per field type"
    expected: "Text fields show Input; number fields (ves_kg, dlina_cm, etc.) show Input[type=number]; select fields show Select dropdown populated from lookups; date fields show Calendar in Popover; system fields show lock icon"
    why_human: "Requires live FieldDefinition data from DB post-migration; select options require lookup API responses"
  - test: "Panel drag-resize from left edge"
    expected: "Panel resizes between 400px and 800px when dragging left edge; table behind is not squeezed"
    why_human: "CSS resize interaction requires manual drag; noted in 02-VALIDATION.md as manual-only"
---

# Phase 2: Detail Panel Verification Report (Re-Verification)

**Phase Goal:** Users can read all fields for any entity type in a section-grouped panel, edit any editable field with the correct input type, and save or cancel changes safely
**Verified:** 2026-03-30T16:30:00Z
**Status:** gaps_found — 2 gaps blocking full goal achievement; 1 is a pending migration, 1 is a deferred architectural gap
**Re-verification:** Yes — after UAT (02-UAT.md) revealed GAP-01 and GAP-02; Plan 05 addressed both at code level

---

## Re-Verification Context

The initial VERIFICATION.md (2026-03-25) reported `human_needed` after automated checks passed for all 9 must-haves. Human UAT (02-UAT.md) was subsequently performed and found:

- **GAP-01** (high): 19/24 FieldDefinition field_names for modeli_osnova did not match ModelOsnovaUpdate Pydantic schema — edits silently failed
- **GAP-02** (medium): children_count returned null for all models — header badges never appeared
- **GAP-03** (low, deferred): Inherited fields absent from child entity schemas — popover code unused

Plan 05 (02-05-SUMMARY.md) addressed GAP-01 and GAP-02 by:
1. Creating migration 005 that renames 9, deletes 9, and inserts 12 field_definition rows for modeli_osnova
2. Adding `children_count = column_property(...)` correlated subquery to ModelOsnova ORM class
3. Deferring GAP-03 per architectural decision (inherited fields require schema redesign)

**This re-verification confirms** the code fixes are correct and complete. The remaining gap is operational: migration 005 must be applied to Supabase before the fixes become live.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All ~22 ModelOsnova fields appear in read mode, grouped under sections | VERIFIED | `panel-body.tsx`: `groupFieldsBySection()` with SECTION_ORDER; `schemas.py` ModelOsnovaRead has 22+ fields; migration 005 adds/corrects 12 more field_definitions |
| 2 | Artikul fields appear in read mode | VERIFIED | `ENTITY_BACKEND_MAP["articles"] = "artikuly"`; `panel-body.tsx` fetches FieldDefinition for artikuly; renders all visible fields |
| 3 | Tovar fields appear in read mode with read-only markers for marketplace IDs | VERIFIED | `IMMUTABLE_FIELDS` set in `panel/types.ts` includes ozon_product_id, barkod, nomenklatura_wb, barkod_gs1, barkod_gs2; lock icon in `panel-field-row.tsx` line 118 |
| 4 | Edit mode shows correct input type per field_type; system fields remain locked | VERIFIED | `panel-field-row.tsx` switch at line 127: text/url/number/select/textarea/checkbox/date (Calendar+Popover); `isImmutable \|\| isSystemField` guard at line 112 |
| 5 | Select fields populated with lookup options from API | VERIFIED | `detail-panel.tsx` prefetchLookups via `Promise.allSettled`; `panel-body.tsx` passes `lookupOptions` to PanelFieldRow; Select renders from `lookupOptions` |
| 6 | Save PATCHes only changed fields; Cancel discards; Save bar visible only in edit mode | VERIFIED | `detail-panel.tsx` diff loop lines 154-165; `handleCancel` resets state; `PanelSaveBar` rendered conditionally at line 300 |
| 7 | System fields cannot be edited — no input appears | VERIFIED | `panel-field-row.tsx` line 112: `if (isImmutable \|\| isSystemField)` returns read-only span + lock icon; no input rendered |
| 8 | FieldDefinition field_names match ModelOsnovaUpdate schema (post-migration) | PARTIAL | Migration 005 SQL is correct and complete. Code-level fix exists. **Requires migration 005 applied to Supabase.** Until applied, 19/24 fields still mismatch in production DB |
| 9 | Related entity badge counters appear when children exist | PARTIAL | `children_count` column_property on ModelOsnova ORM is correct. `ModelOsnovaRead` has `children_count: Optional[int]`. Frontend badge logic is correct. **Requires migration 005 applied** (column_property becomes available after DB reflects schema); also requires Supabase DB restart |

**Score:** 7/9 truths fully verified (2 partial — pending migration 005 on Supabase)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `wookiee-hub/src/components/ui/sheet.tsx` | Sheet primitive on Base UI Drawer | VERIFIED | 101 lines; modal=false; slide animation; CSS rtl resize |
| `wookiee-hub/src/components/matrix/panel/types.ts` | Type contracts: IMMUTABLE_FIELDS, COMPUTED_FIELD_PATTERN, LOOKUP_TABLE_MAP | VERIFIED | 83 lines; all 7 exports present |
| `wookiee-hub/src/stores/matrix-store.ts` | Extended with detailPanelEntityType, lookupCache, setLookupCache | VERIFIED | detailPanelEntityType, lookupCache, setLookupCache all present |
| `services/product_matrix_api/models/schemas.py` | ModelOsnovaRead with 22+ fields; children_count | VERIFIED | ves_kg, dlina_cm, shirina_cm, vysota_cm, upakovka, sku_china + children_count: Optional[int] at line 104 |
| `sku_database/database/models.py` | children_count column_property on ModelOsnova | VERIFIED | Lines 293-300: `ModelOsnova.children_count = column_property(select(func.count(Model.id)).where(...).scalar_subquery())` |
| `services/product_matrix_api/migrations/005_fix_field_definitions.sql` | Migration: rename 9, delete 9, insert 12 field_definitions | VERIFIED | File exists; 61 lines; uses natural keys (field_name+entity_type) not hardcoded IDs; COMMIT included |
| `wookiee-hub/src/components/matrix/detail-panel.tsx` | Sheet-based panel with edit state and save/cancel | VERIFIED | 315 lines; handleSave, handleCancel, isEditing, localData override, prefetchLookups, PanelRelated wired |
| `wookiee-hub/src/components/matrix/panel/panel-header.tsx` | Header with title, edit toggle, related entity badges | VERIFIED | Badge rendering from relatedCounts prop; edit toggle wired |
| `wookiee-hub/src/components/matrix/panel/panel-body.tsx` | Section-grouped field display driven by FieldDefinition | VERIFIED | 179 lines; groupFieldsBySection, INHERITED_FIELDS, resolveDisplayValue, lookupOptions from cache |
| `wookiee-hub/src/components/matrix/panel/panel-section.tsx` | Collapsible section using Base UI Collapsible | VERIFIED | Collapsible.Root/Trigger/Panel; defaultOpen=true |
| `wookiee-hub/src/components/matrix/panel/panel-field-row.tsx` | Read/edit field row with correct input types and lock | VERIFIED | 327 lines; switch on field_type; IMMUTABLE_FIELDS guard; Calendar date picker; inherited popover |
| `wookiee-hub/src/components/matrix/panel/panel-save-bar.tsx` | Sticky save/cancel bar with disabled/loading states | VERIFIED | 49 lines; Save disabled when !hasChanges or saving; Loader2 spinner |
| `wookiee-hub/src/components/matrix/panel/panel-related.tsx` | Related children list with navigation | VERIFIED | 251 lines; ArticlesChildren/ProductsChildren sub-components; openDetailPanel onClick |
| `wookiee-hub/tests/detail-panel.spec.ts` | E2E test stubs for all 8 PANEL requirements | VERIFIED | 10 test.fixme stubs covering PANEL-01 through PANEL-08 |
| `wookiee-hub/tests/fixtures.ts` | Shared Playwright fixtures | VERIFIED | openDetailPanel, switchEntityType, enterEditMode, getFieldRow exports |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `detail-panel.tsx` | `matrixApi.getModel/getArticle/getProduct` | `fetchEntity()` | WIRED | Lines 22-25: entity type dispatch |
| `detail-panel.tsx` | `matrixApi.updateModel/updateArticle/updateProduct` | `handleSave()` | WIRED | Lines 173-177: PATCH dispatch per entity type |
| `detail-panel.tsx` | `matrixApi.getLookup` | `prefetchLookups()` | WIRED | Lines 117-125: Promise.allSettled over ALL_LOOKUP_TABLES |
| `detail-panel.tsx` | `matrix-store.ts` | `useMatrixStore` selectors | WIRED | Lines 68-73: detailPanelId, detailPanelEntityType, closeDetailPanel, notifyEntityUpdated, lookupCache, setLookupCache |
| `panel-body.tsx` | `matrixApi.listFields` | `useApiQuery` | WIRED | Line 113: `matrixApi.listFields(backendEntityType)` |
| `panel-body.tsx` | `panel-field-row.tsx` | props: def, value, editValue, isEditing, lookupOptions, onChange | WIRED | Lines 158-171: full prop threading |
| `panel-field-row.tsx` | `panel/types.ts` | `IMMUTABLE_FIELDS.has(def.field_name)` | WIRED | Line 87: guard against immutable fields |
| `panel-field-row.tsx` | `matrix-store.ts` | `openDetailPanel` in inherited popover | WIRED | Line 313: `openDetailPanel(parentEntityId, parentEntityType)` |
| `panel-related.tsx` | `matrixApi.listArticles/listProducts` | `useApiQuery` | WIRED | Lines 71, 129: child entity fetches |
| `panel-related.tsx` | `matrix-store.ts` | `openDetailPanel`, `setActiveEntity`, `closeDetailPanel` | WIRED | Lines 66-68, 102, 110-111 |
| `migration 005` | `field_definitions` table | Natural-key WHERE clauses | WIRED (code) | SQL uses `entity_type + field_name` conditions; correct and safe. Awaits execution on Supabase. |
| `ModelOsnova.children_count` | `Model` table | `column_property` correlated subquery | WIRED (code) | Lines 295-300 of models.py; triggers additional query on attribute access via `db.get()` |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PANEL-01 | 02-00, 02-01, 02-02, 02-05 | Все поля ModelOsnova (~22) в read mode, сгруппированы по секциям | SATISFIED | ModelOsnovaRead 22+ fields; panel-body groupFieldsBySection; PanelSection collapsible; migration 005 ensures field_definitions align |
| PANEL-02 | 02-00, 02-01, 02-02 | Все поля Artikul в read mode | SATISFIED | ENTITY_BACKEND_MAP["articles"]="artikuly"; panel-body fetches FieldDefinition for artikuly; renders all visible fields |
| PANEL-03 | 02-00, 02-01, 02-02 | Все поля Tovar в read mode с read-only маркировкой для marketplace IDs | SATISFIED | IMMUTABLE_FIELDS: ozon_product_id, barkod, nomenklatura_wb, barkod_gs1, barkod_gs2; lock icon rendered |
| PANEL-04 | 02-00, 02-03 | Edit mode с правильным типом input per field_type | SATISFIED | panel-field-row switch covers text/url/number/select/textarea/checkbox/date; correct input types confirmed in UAT |
| PANEL-05 | 02-00, 02-01, 02-03 | Select-поля используют lookup options из /api/matrix/lookups/* | SATISFIED | prefetchLookups in detail-panel; panel-body threads lookupOptions; Select renders from cache |
| PANEL-06 | 02-00, 02-03 | Save/Cancel с валидацией и оптимистичным обновлением | SATISFIED | handleSave diffs only changed fields; setLocalData on success; handleCancel resets; UAT confirmed flow works |
| PANEL-07 | 02-00, 02-02, 02-03 | Read-only защита для системных полей | SATISFIED | IMMUTABLE_FIELDS + is_system guard; lock icon; no input in edit mode; UAT confirmed |
| PANEL-08 | 02-00, 02-04 | Связанные сущности как кликабельные ссылки с количеством | PARTIAL | PanelRelated children list works (UAT pass). Badge counters: code complete but children_count returns null until migration 005 applied to Supabase. |

**Requirements fully satisfied: 7/8**
**Requirements partially satisfied: 1/8 (PANEL-08 — badge counters pending migration)**
**No orphaned requirements.** All 8 PANEL-XX IDs from plans 02-00 through 02-04 are accounted for.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `wookiee-hub/tests/detail-panel.spec.ts` | 1-end | All tests marked `test.fixme` | INFO | By design — Wave 0 scaffolding; stubs await activation after live UAT |
| `02-VALIDATION.md` | frontmatter | `nyquist_compliant: false`, all tasks pending | INFO | Validation doc never updated post-execution; not a code issue |
| `panel-body.tsx` INHERITED_FIELDS | 15-25 | Lists inherited field names that are absent from child entity FieldDefinitions | WARNING | Inherited field popover code exists but never triggers. Silent non-event — no errors, just unused code path |

No blocker anti-patterns in implementation files. The migration-pending state is an operational concern, not a code defect.

---

### Gaps Summary

**Gap 1: Migration 005 not applied to Supabase (operational, high priority)**

Migration `services/product_matrix_api/migrations/005_fix_field_definitions.sql` corrects two UAT failures:
- GAP-01: renames 9 field_names in field_definitions to match ModelOsnovaUpdate Pydantic schema (e.g., `ves_g` → `ves_kg`, `dlina_sm` → `dlina_cm`)
- GAP-02: the `children_count` column_property is code-complete; the field also requires migration to be applied for the Supabase schema to include it

Until migration 005 runs: edits to dimension/content fields will silently fail (Pydantic extra="ignore" drops unknown fields), and badge counters will show null.

**Action required:** Run migration 005 on Supabase.

**Gap 2: GAP-03 deferred — inherited field popover never triggers (architectural, low priority)**

The frontend popover implementation in `panel-field-row.tsx` is complete. `panel-body.tsx` INHERITED_FIELDS lists the relevant fields for articles and products. However, those fields are absent from the FieldDefinition rows returned by `/api/matrix/schema/artikuly` and `/api/matrix/schema/tovary` — so `groupFieldsBySection()` never includes them, and no PanelFieldRow with `inherited=true` is ever rendered.

Resolution requires a backend architectural decision: either add inherited field rows to child entity field_definitions (with an `is_inherited` flag), or modify the schema endpoint to merge parent-level fields.

This is explicitly deferred per Plan 05 decision log.

---

### Human Verification Required

#### 1. Apply Migration 005 — Confirm Field Names and Save Behavior

**Test:** Apply migration 005 to Supabase. Open a model detail panel, enter edit mode, change `ves_kg` (weight field). Click Сохранить.
**Expected:** PATCH request contains `{ "ves_kg": <new_value> }` — field name matches Pydantic schema. Value persists after panel is closed and reopened.
**Why human:** Migration must be applied to live DB; PATCH body confirmation requires network inspection.

#### 2. Badge Counters After Migration

**Test:** After migration 005 + backend restart: open a model known to have child articles. Inspect panel header.
**Expected:** Badge showing "Артикулы N" (N > 0) appears below the model title. Clicking the badge switches the active tab to Articles.
**Why human:** `children_count` is populated at query time by correlated subquery — requires live DB and backend running with updated models.py.

#### 3. Edit Mode Input Types (Post-Migration)

**Test:** Open any model in edit mode. Observe each field.
**Expected:** Number fields (ves_kg, dlina_cm, etc.) show `<input type="number">`; select fields (kategoriya, fabrika, kollekciya) show dropdown with options; date fields show Calendar in Popover. System fields show lock + no input.
**Why human:** Requires live FieldDefinition data from DB with migration 005 applied.

#### 4. Panel Drag-Resize

**Test:** Open any panel. Try dragging from its left edge.
**Expected:** Panel resizes horizontally between 400px and 800px. Table behind is not squeezed.
**Why human:** CSS `resize: horizontal` with `direction: rtl` trick requires manual drag interaction.

---

_Verified: 2026-03-30T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — post-UAT + Plan 05 backend fixes_
