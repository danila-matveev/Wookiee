# Phase 4 — Filter System: Context Decisions

## 1. Filter Bar UX

### Placement
- **Decision:** Filters live in the existing `MatrixTopbar` component
- **Layout:** `[Создать] [+Фильтр] [chip][chip][chip]...  [Поля]`
- **Rationale:** Reuses existing toolbar, no extra horizontal line, compact

### Adding Filters
- **Decision:** `[+Фильтр]` button opens a popover with field list → select field → select value(s) → chip appears
- **Pattern:** Similar to Notion/Linear filter builder
- **Scalable:** Works for any number of filterable fields

### Active Filters Display
- **Decision:** Filter chips inline in the same toolbar row
- **Format:** `[Категория: Бельё ×]` — removable chips with × button
- **Wrap behavior:** Toolbar wraps naturally with `flex-wrap` when many chips

### No separate filter bar line, no sliding panel.

---

## 2. Hierarchy Navigation (Drill-down)

### Mechanism
- **Decision:** Auto-switch entity tab with preset filter
- **Flow:** Click model row → switch to "Артикулы" tab → auto-apply filter chip `[Модель: KOD-123 ×]`
- **Return:** Remove chip to see all articles, or click "Модели" tab

### Breadcrumb
- **Decision:** No breadcrumb. Filter chips provide the same context
- **Existing expand-in-place** (chevron → children rows) stays as-is for quick preview

### Implementation note
- Need `onDrillDown(entityType, filterField, filterValue)` handler that:
  1. Sets `activeEntity` to target tab
  2. Adds filter to active filters state

---

## 3. Filter Builder Complexity

### Operators
- **Decision:** Only `=` (equals) operator
- **Lookup fields** (kategoriya_id, fabrika_id, kollekciya_id): select from dropdown
- **Text fields**: `contains` semantics under the hood
- **No range operators**, no >, <, no is_empty — keep it simple

### Multi-select
- **Decision:** Yes, multi-select within one filter (OR logic)
- **UI:** Combobox with checkboxes for lookup fields
- **Chip display:** `[Категория: Бельё, Полотенца ×]`
- **Backend:** `kategoriya_id IN (1, 5)` query

### Filter logic between different fields = AND
- Example: `kategoriya_id IN (1,5) AND fabrika_id = 3`

---

## 4. Status & Saved Views

### Status field for modeli_osnova
- **Decision:** Add `status_id INT REFERENCES statusy(id)` to `modeli_osnova` via migration
- **Key principle:** Each entity level has its OWN independent status:
  - `modeli_osnova.status_id` — status of the base model
  - `cveta.status_id` — status of the color variation (already exists)
  - `artikuly.status_id` — status of the article (already exists)
  - `tovary.status_id` — status of the product (already exists)
- **No inheritance:** A color can be "Архив" while the model is "Продается"
- **Statuses from `statusy` table:** Продается, Выводим, Архив, Подготовка, План, Новый, Запуск
- **Migration scope:** ALTER TABLE + update ORM model + add to frontend columns + make filterable

### Saved Views
- **Decision:** Save everything — filters + sort + hidden columns
- **Storage:** localStorage via Zustand `persist` (like existing `filters.ts`)
- **Structure:** Reuse existing `views-store.ts` with `{ columns, filters, sort }` config
- **No backend API** needed for views storage

---

## 5. Code Context (Existing Assets)

### Frontend
- `MatrixTopbar` — target for filter controls (currently has Создать + Поля)
- `views-store.ts` — already has `SavedView` type with `{ columns, filters, sort }`
- `model-columns.ts` — static column defs with field metadata (type, section)
- `LOOKUP_TABLE_MAP` — maps field names to lookup tables for value resolution

### Backend
- `list_models_osnova` already accepts `kategoriya_id`, `kollekciya_id` as query params
- `CrudService.get_list(filters=dict)` supports arbitrary WHERE clauses
- `statusy` lookup table exists with 7 statuses
- Need to extend backend to accept `status_id`, `fabrika_id`, and arbitrary filter params

### Deferred Ideas
- Range operators (>, <, between) for numeric fields — future phase
- Backend-stored views with team sharing — future phase
- Cross-entity filter propagation (filter models → auto-filter articles) — future phase
