# Phase 2: Detail Panel - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

All fields visible in read mode for every entity type (ModelOsnova, Artikul, Tovar), edit mode with correct input types, save/cancel, lookup options cached. Panel replaces current hardcoded model-only sidebar with a full entity-aware sheet overlay.

Requirements: PANEL-01 through PANEL-08.

</domain>

<decisions>
## Implementation Decisions

### Layout & Sections
- Notion-style flat vertical list (1 column: label → value, stacked)
- Collapsible sections (Основные, Размеры, Логистика, Контент) — expanded by default, collapse on click
- shadcn Collapsible or Accordion for section toggle

### Panel Container
- Sheet overlay (поверх таблицы, не сжимает её) — like Notion record view
- Resizable width: min 400px, max 800px (drag edge to resize)
- shadcn Sheet component (side="right") with custom resize handle

### Panel Header
- Context-dependent title by entity level:
  - ModelOsnova → `kod` (название модели, e.g. "ML-3254")
  - Artikul → `artikul` (артикул, e.g. "ML-3254-BLK")
  - Tovar → `artikul_ozon` (уникален по цвету + размеру)
- Badge счётчики связанных сущностей под заголовком (e.g. "Артикулы: 4", "Товары: 12")

### Edit Mode Activation
- Toggle button "Редактировать" in header → switches ALL editable fields to inputs simultaneously (form mode)
- NOT per-field click-to-edit (Notion-style rejected — too easy to accidentally modify data)
- Save/Cancel buttons appear when in edit mode (Claude's discretion on placement — recommend sticky bottom bar)

### Inherited Fields
- Show inherited fields (e.g. категория on Артикул comes from ModelOsnova)
- Inherited fields are NOT editable at child level — displayed as read-only
- Click on inherited field → popover/tooltip preview of parent entity
- Second click from popover → navigate to parent in panel (two-step navigation)

### Read-Only / Sensitive Fields
- Three categories of field editability:
  1. **Editable** — standard fields, become inputs in edit mode
  2. **Immutable after creation** — barkod (once saved, cannot change; can only create new), ozon_product_id, nomenklatura_wb — these are pulled from marketplace and locked forever
  3. **Sensitive but editable** — fields like barkod during initial creation; visual warning highlight ("будьте внимательны")
- In read mode: all fields look similar (Claude's discretion on subtle differentiation)
- In edit mode: immutable fields stay as text (not input); sensitive fields get warning styling
- Admin-only access control for sensitive fields — architecture placeholder (no auth system yet, will be future milestone)

### Related Entities
- Combination approach: badge counters in header + expandable list at bottom of panel
- Badge in header: "Артикулы: 4" — clickable, navigates to filtered table view of children
- Section at bottom: collapsible list showing first 5 children with "показать все" link
- Click on specific child in list → opens that child in the panel (replaces current entity)
- Which relations to show: Claude's discretion (recommend: direct children + parent link)

### Field Input Types (driven by FieldDefinition.field_type)
- `text` → Input
- `number` → Input type=number
- `select` → Select populated from matrixApi.getLookup() (kategorii, kollekcii, fabriki, statusy, razmery, importery)
- `textarea` → Textarea (for opisanie_sayt, sostav_syrya, etc.)
- `url` → Input with link icon
- `checkbox` → Checkbox
- `date` → DatePicker

### Claude's Discretion
- Save/Cancel button placement (recommend: sticky bottom bar in edit mode)
- Loading skeleton design for panel open
- Error state handling (failed save, network errors)
- Exact spacing, typography, colors within shadcn theme
- Which relations to show at each entity level
- Field input validation rules

</decisions>

<specifics>
## Specific Ideas

- "Как в Notion — панель поверх таблицы, можно растягивать от 400 до 800px"
- "Редактирование каждого поля в формате Notion не самая лучшая идея, так как это легко изменяет всю базу данных. Точно должна быть кнопка Сохранить и Отменить"
- "Наследуемые данные с уровня модели на уровень цвета, с уровня цвета на уровень размера — некоторые данные не могут меняться, так как должны задаваться на уровне модели"
- "Как в Notion существуют поля взаимосвязанных таблиц через Rollup и Relation"
- "Баркод уже создан и окончательно сохранен — его уже не отредактировать. Можно создать только новый"
- "Ozon ID вообще нельзя поменять, номенклатуру нельзя поменять — они только подтягиваются"
- "При клике на наследуемое поле — показывается карточка/плашка с моделью, и уже по второму клику можно перейти"
- "При проектировании дизайна использовать плагин frontend-design"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `InfoTab` (info-tab.tsx): Already uses FieldDefinition system with section grouping — good pattern to follow for panel body
- `RelatedList` component in InfoTab: Shows linked child entities with clickable links
- `Section` / `Field` components in detail-panel.tsx: Simple read-only display, will be replaced
- `matrixApi.getLookup(table)`: Returns `{id, nazvanie}[]` for all FK tables — ready for select dropdowns
- `matrixApi.updateModel/updateArticle/updateProduct`: All PATCH endpoints ready, use `exclude_none=True`
- `matrixApi.listFields(entityType)`: Returns FieldDefinition[] with field_type, section, sort_order, is_system
- `StockTab`, `FinanceTab`: Mature tab components with channel cards, KPI cards — not modified in this phase

### Established Patterns
- Zustand store (`matrix-store.ts`): Has `activeEntity` and `detailPanelId` — needs `detailPanelEntityType` added (Phase 1 deliverable)
- `FIELD_DEF_ENTITY_MAP` in InfoTab: Maps frontend entity slugs to backend entity type strings
- Backend `FieldDefinition` model: `entity_type`, `field_name`, `display_name`, `field_type`, `config`, `section`, `sort_order`, `is_system`, `is_visible`
- `verbatimModuleSyntax: true` in tsconfig — all type imports must use `import type`

### Integration Points
- Phase 1 delivers entity-aware panel routing — Phase 2 builds on that foundation
- `ModelOsnovaRead` schema missing ~20 fields (sku_china, upakovka, ves_kg, etc.) — backend schema expansion needed
- Lookup tables: kategorii, kollekcii, statusy, razmery, importery, fabriki — all have GET endpoints
- `LOOKUP_MAP` in lookups.py: Maps table name to SQLAlchemy model
- `field_definitions` table may need seeding with all fields for all entity types (currently unknown population state)

</code_context>

<deferred>
## Deferred Ideas

- Admin-only access control for sensitive fields — future milestone (no auth system exists)
- Barcode immutability logic (created barcodes become read-only) — needs business rule implementation, consider for Phase 3 or separate phase
- Keyboard navigation (Tab/Enter/Escape) in edit mode — v2 requirement ADV-02
- Quick-edit hover on table cell — v2 requirement ADV-03

</deferred>

---

*Phase: 02-detail-panel*
*Context gathered: 2026-03-25*
