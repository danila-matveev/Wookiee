# Phase 2: Detail Panel - Research

**Researched:** 2026-03-25
**Domain:** React / shadcn-nova / Base UI — Detail Panel overlay with form editing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Layout:** Notion-style flat vertical list (1 column: label → value, stacked)
- **Sections:** Collapsible sections (Основные, Размеры, Логистика, Контент) — expanded by default, collapse on click; use Base UI Collapsible
- **Panel container:** Sheet overlay (поверх таблицы, не сжимает её) — shadcn Sheet side="right" with custom resize handle; min 400px, max 800px
- **Header title:** Context-dependent — ModelOsnova → `kod`, Artikul → `artikul`, Tovar → `artikul_ozon`
- **Header badges:** Счётчики связанных сущностей под заголовком ("Артикулы: 4", "Товары: 12")
- **Edit mode:** Toggle button "Редактировать" in header → ALL editable fields become inputs simultaneously (NOT per-field Notion-style click-to-edit)
- **Save/Cancel placement:** Claude's discretion — sticky bottom bar recommended
- **Inherited fields:** Show on child levels, displayed as read-only, click → popover preview of parent, second click → navigate to parent in panel
- **Immutable fields:** barkod (once saved), ozon_product_id, nomenklatura_wb — stay as text in edit mode, cannot be changed
- **Sensitive fields:** Visual warning highlight in edit mode (no auth system yet — placeholder only)
- **Related entities:** Badge counters in header (clickable, navigate to filtered table) + collapsible list at bottom showing first 5 children with "показать все"
- **Field input types:** text→Input, number→Input[type=number], select→Select from getLookup(), textarea→Textarea, url→Input+icon, checkbox→Checkbox, date→DatePicker

### Claude's Discretion
- Save/Cancel button placement (recommend: sticky bottom bar in edit mode)
- Loading skeleton design for panel open
- Error state handling (failed save, network errors)
- Exact spacing, typography, colors within shadcn theme
- Which relations to show at each entity level
- Field input validation rules

### Deferred Ideas (OUT OF SCOPE)
- Admin-only access control for sensitive fields
- Barcode immutability logic (created barcodes become read-only)
- Keyboard navigation (Tab/Enter/Escape) in edit mode — v2 ADV-02
- Quick-edit hover on table cell — v2 ADV-03
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PANEL-01 | All ModelOsnova (~22) fields visible in read mode, grouped by sections (Основные, Размеры, Логистика, Контент) | FieldDefinition system + InfoTab pattern; ModelOsnovaRead schema expansion needed |
| PANEL-02 | All Artikul fields visible in read mode | ArtikulRead already has all fields; schema seeding needed |
| PANEL-03 | All Tovar fields visible in read mode with read-only markers for marketplace IDs | TovarRead complete; IMMUTABLE_FIELDS set in frontend |
| PANEL-04 | Edit mode — correct input type per field_type (text, number, select, textarea) | field_type from FieldDefinition drives input component selection |
| PANEL-05 | Select fields use loaded lookup options from /api/matrix/lookups/* | getLookup() ready; 6 lookup tables available; caching in Zustand recommended |
| PANEL-06 | Save/Cancel with validation and optimistic update | PATCH endpoints ready; local form state via useState; Zustand cache invalidation |
| PANEL-07 | Read-only protection for system fields (barkod, nomenklatura_wb, ozon_product_id, gs1, gs2) | IMMUTABLE_FIELDS constant; FieldDefinition.is_system=true for these |
| PANEL-08 | Related entities as clickable links with count ("4 артикула" → filtered view) | Badge in header + RelatedSection at bottom; navigate() with filter params |
</phase_requirements>

---

## Summary

Phase 2 builds the entity-aware detail panel on top of the Phase 1 foundation. The codebase already has the core ingredients: `InfoTab` with section-grouped `FieldDefinition`-driven read display, all PATCH endpoints for the three main entity types, `getLookup()` for all reference tables, and `Skeleton` for loading states. What does not yet exist: the Sheet overlay container, the edit mode form state layer, a `Sheet` UI component (not in `/components/ui/` yet), and `is_editable` on `FieldDefinition`.

The project uses `@base-ui/react` (not Radix UI) as the primitive layer. A shadcn-nova Sheet component does not appear to be installed — the `dialog.tsx` uses `@base-ui/react/dialog` and a Sheet equivalent must be built on top of `@base-ui/react/drawer` (which IS available and already exported by `@base-ui/react`). The existing `model-detail-drawer.tsx` in the dashboard demonstrates the pattern. Alternatively, `Sheet` can be a styled `<div>` fixed to the right edge with an overlay — simpler and avoids drawer semantics (which implies swipe/snap which is not wanted here).

The critical blocker from STATE.md — `is_editable: bool` on `FieldDefinition` — must be resolved in this phase. The current `FieldDefinition` DB model only has `is_system: bool` and `is_visible: bool`. The `is_system` flag can be repurposed to mean "not editable by user" which covers immutable marketplace IDs. No new DB migration is strictly needed if `is_system=true` means "display only, never editable." This must be confirmed and any field seeding must ensure all system/immutable fields have `is_system=true`.

**Primary recommendation:** Build the Sheet as a fixed-right positioned `<div>` controlled by Zustand `detailPanelId` + `detailPanelEntityType` (Phase 1 addition). Use `InfoTab`'s existing `FieldDefinition` section grouping pattern for read mode. Add a `FormFieldRow` component that switches between read and edit based on `isEditing` state, using the `field_type` to select the correct input.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@base-ui/react/drawer` | 1.2.0 (installed) | Sheet overlay container | Already installed, used in kanban; avoids adding Radix dependency |
| `@base-ui/react/collapsible` | 1.2.0 (installed) | Collapsible sections | Matches project's existing primitive layer |
| `@base-ui/react/popover` | 1.2.0 (installed) | Inherited field parent preview | Already used in `popover.tsx` UI component |
| `zustand` | 5.0.11 (installed) | Panel state + lookup cache | Existing store; add `detailPanelEntityType` + `lookupCache` |
| `lucide-react` | 0.575.0 (installed) | Icons (ChevronDown, X, Edit, Save, ExternalLink) | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react-day-picker` + `date-fns` | 9.13.2 / 4.1.0 (installed) | DatePicker for date fields | Only when field_type === "date" |
| `Skeleton` (ui/skeleton.tsx) | — | Panel loading skeleton | On initial open before data arrives |
| `Badge` (ui/badge.tsx) | — | Related entity count badges in header | Header counter display |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Base UI Drawer as Sheet | Fixed-position `<div>` | Custom div is simpler, no swipe semantics; Drawer adds accessibility but complexity |
| `useState` for form | `react-hook-form` + `zod` | STATE.md pins zod to 3.25.x; RHF is overkill for a single-entity form; simple `useState<Record<string, unknown>>` is sufficient |
| Zustand lookup cache | Per-component `useApiQuery` | Zustand avoids re-fetching identical lookup lists on every panel open |

**Installation:** No new packages needed — all required primitives are installed.

---

## Architecture Patterns

### Recommended Project Structure
```
src/components/matrix/
├── detail-panel.tsx           # REPLACE — new Sheet wrapper (entity-aware)
├── panel/
│   ├── panel-header.tsx       # Title, badges, Edit/Close buttons
│   ├── panel-body.tsx         # Sections + field rows
│   ├── panel-section.tsx      # Collapsible section wrapper
│   ├── panel-field-row.tsx    # Read/edit switcher per field
│   ├── panel-related.tsx      # Collapsible children list at bottom
│   └── panel-save-bar.tsx     # Sticky bottom bar (Save/Cancel)
src/components/ui/
└── sheet.tsx                  # NEW — Sheet primitive built on Base UI Drawer

src/stores/
└── matrix-store.ts            # ADD: detailPanelEntityType, lookupCache, editingEntityId
```

### Pattern 1: Sheet built on Base UI Drawer (side panel, no swipe)

**What:** Use `@base-ui/react/drawer` with `modal=false` and a fixed-right positioned popup, disabling snap/swipe semantics. The Drawer gives accessibility (focus trap optional, portal, backdrop) without mobile drawer behavior.

**When to use:** When opening the detail panel from any table row click.

**Example:**
```typescript
// src/components/ui/sheet.tsx
import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer"
import { cn } from "@/lib/utils"

function Sheet({ ...props }: DrawerPrimitive.Root.Props) {
  return <DrawerPrimitive.Root data-slot="sheet" modal={false} {...props} />
}

function SheetContent({
  className,
  children,
  ...props
}: DrawerPrimitive.Popup.Props) {
  return (
    <DrawerPrimitive.Portal>
      <DrawerPrimitive.Popup
        data-slot="sheet-content"
        className={cn(
          "bg-background fixed right-0 top-0 bottom-0 z-50",
          "w-[480px] min-w-[400px] max-w-[800px]",
          "border-l border-border shadow-xl",
          "flex flex-col overflow-hidden",
          "data-open:animate-in data-closed:animate-out",
          "data-open:slide-in-from-right data-closed:slide-out-to-right",
          "duration-200",
          className
        )}
        {...props}
      >
        {children}
      </DrawerPrimitive.Popup>
    </DrawerPrimitive.Portal>
  )
}
```

**Resize handle:** Custom `<div>` on the left edge with `onMouseDown` + `document.addEventListener('mousemove')` + `useRef` for width state. Store width in local component state (not Zustand — no cross-panel persistence needed).

### Pattern 2: Collapsible Sections via Base UI

**What:** Each section (Основные, Размеры, etc.) uses `@base-ui/react/collapsible`. Default state is open (`defaultOpen={true}`).

**Example:**
```typescript
// src/components/matrix/panel/panel-section.tsx
import { Collapsible } from "@base-ui/react/collapsible"
import { ChevronDown } from "lucide-react"

export function PanelSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <Collapsible.Root defaultOpen={true} className="border-b border-border/50 last:border-0">
      <Collapsible.Trigger className="flex w-full items-center justify-between px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:bg-accent/20">
        {title}
        <ChevronDown className="h-3.5 w-3.5 transition-transform data-[panel-open]:rotate-180" />
      </Collapsible.Trigger>
      <Collapsible.Panel className="px-4 pb-3 space-y-1">
        {children}
      </Collapsible.Panel>
    </Collapsible.Root>
  )
}
```

### Pattern 3: FormFieldRow — Read/Edit Switcher

**What:** Single component that renders either a read display or the correct input type, based on `isEditing` and `field_type` from `FieldDefinition`.

**Example:**
```typescript
// src/components/matrix/panel/panel-field-row.tsx
import type { FieldDefinition } from "@/lib/matrix-api"

const IMMUTABLE_FIELDS = new Set([
  "barkod", "nomenklatura_wb", "ozon_product_id", "barkod_gs1", "barkod_gs2",
])

export function PanelFieldRow({
  def,
  value,
  editValue,
  isEditing,
  lookupOptions,
  onChange,
}: PanelFieldRowProps) {
  const isImmutable = def.is_system || IMMUTABLE_FIELDS.has(def.field_name)

  if (!isEditing || isImmutable) {
    return <ReadRow label={def.display_name} value={value} immutable={isImmutable && isEditing} />
  }

  // Edit mode: render input by field_type
  switch (def.field_type) {
    case "select":
      return <SelectRow label={def.display_name} value={editValue} options={lookupOptions} onChange={onChange} />
    case "number":
      return <NumberRow label={def.display_name} value={editValue} onChange={onChange} />
    case "textarea":
      return <TextareaRow label={def.display_name} value={editValue} onChange={onChange} />
    case "checkbox":
      return <CheckboxRow label={def.display_name} value={editValue} onChange={onChange} />
    case "date":
      return <DateRow label={def.display_name} value={editValue} onChange={onChange} />
    default: // "text", "url"
      return <TextRow label={def.display_name} value={editValue} onChange={onChange} />
  }
}
```

### Pattern 4: Zustand store additions for Phase 2

**What:** Add `detailPanelEntityType` (Phase 1 deliverable — confirmed needed here), `editingEntityId` flag, and `lookupCache` to avoid re-fetching.

```typescript
// matrix-store.ts additions
interface MatrixState {
  // ... existing fields
  detailPanelEntityType: MatrixEntity | null  // Phase 1 adds this
  lookupCache: Record<string, LookupItem[]>   // Phase 2 adds this

  setLookupCache: (table: string, items: LookupItem[]) => void
}
```

### Pattern 5: Save flow with optimistic update

**What:** On Save click — PATCH request, update Zustand cache entry immediately (optimistic), show error toast on failure, revert data.

```typescript
async function handleSave() {
  const updates = Object.fromEntries(
    Object.entries(editState).filter(([k, v]) => v !== originalData[k])
  )
  if (Object.keys(updates).length === 0) { setIsEditing(false); return }

  // Optimistic update in store
  updateEntityInCache(entityId, updates)

  try {
    const updated = await patchFn(entityId, updates)
    updateEntityInCache(entityId, updated)  // confirm with server response
    setIsEditing(false)
  } catch (err) {
    revertEntityInCache(entityId, originalData)  // rollback
    setError(err.message)
  }
}
```

### Anti-Patterns to Avoid
- **Per-field click-to-edit:** Explicitly rejected by user. All fields must toggle simultaneously via the "Редактировать" button.
- **Blocking the table:** Do NOT use `modal={true}` on Drawer/Sheet — panel overlays table, table remains interactive.
- **Re-fetching lookups on every open:** Cache all 6 lookup tables in Zustand on first fetch. They change infrequently.
- **Sending all fields on PATCH:** Only send changed fields (`exclude_none=True` on backend already handles this, but frontend should also diff to avoid spurious audits).
- **Using `react-hook-form`:** Overkill for this use case; introduces zod version complexity (STATE.md pins zod to 3.25.x).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Side panel overlay | Custom CSS positioned panel | Base UI Drawer (modal=false) | Accessibility, portal, focus management already solved |
| Collapsible sections | `useState` + height animation | Base UI Collapsible | Proper ARIA, keyboard, animation already in Base UI |
| Date picker | Native `<input type="date">` | `react-day-picker` + `Calendar` UI component | Locale formatting, consistent design system |
| Select dropdowns | Native `<select>` | Existing `Select` UI component (Base UI backed) | Matches design system; already handles portal, keyboard |
| Inherited field popover | Custom modal | Existing `Popover` UI component | Already built and styled |

**Key insight:** The project already has all primitive UI building blocks in `src/components/ui/`. No new primitives need to be installed.

---

## Common Pitfalls

### Pitfall 1: Sheet component does not exist in `/components/ui/`
**What goes wrong:** Planner assumes `shadcn Sheet` is available and tasks reference `import { Sheet } from "@/components/ui/sheet"` — but this file does not exist.
**Why it happens:** shadcn's default style includes Sheet, but this project uses `base-nova` style and only the components explicitly added are present.
**How to avoid:** Wave 0 task must create `src/components/ui/sheet.tsx` using `@base-ui/react/drawer`.
**Warning signs:** `Cannot find module '@/components/ui/sheet'` at build time.

### Pitfall 2: `is_editable` missing from FieldDefinition
**What goes wrong:** Frontend has no way to distinguish user-editable fields from computed `_name` fields (e.g. `kategoriya_name`, `fabrika_name`) — if both appear in `listFields()`, the edit form renders inputs for computed fields that cannot be PATCHed.
**Why it happens:** `FieldDefinition` DB model has `is_system` but not `is_editable`. The `_name` suffix fields are view-only join columns.
**How to avoid:** Either (a) add `is_editable: bool` to `FieldDefinition` DB schema + API + seed data, OR (b) filter out `_name` suffix fields in frontend by convention. Option (b) is faster — hardcode a `COMPUTED_FIELD_PATTERN = /_name$/` exclusion in the panel, and block PATCH for those fields.
**Warning signs:** PATCH returns 422 because `kategoriya_name` is not in `ModelOsnovaUpdate` schema.

### Pitfall 3: ModelOsnovaRead schema missing ~20 fields
**What goes wrong:** PANEL-01 requires all ~22 fields visible, but `ModelOsnovaRead` (backend Pydantic schema) only includes ~10 fields. The extra fields (`sku_china`, `upakovka`, `ves_kg`, `dlina_cm`, `shirina_cm`, `vysota_cm`, `kratnost_koroba`, `srok_proizvodstva`, `komplektaciya`, `composition`, `tegi`, `notion_link`, `gruppa_sertifikata`, `nazvanie_etiketka`, `opisanie_sayt`) exist in `ModelOsnovaCreate`/`Update` but not in `Read`.
**Why it happens:** `ModelOsnovaRead` was defined minimally; `ModelOsnovaCreate` has the full field set.
**How to avoid:** Expand `ModelOsnovaRead` to include all fields from `ModelOsnovaCreate`. This is a backend task — must be done in Wave 0 or Wave 1 before panel read mode can show all fields.
**Warning signs:** Field shows "—" in panel even though data exists in DB.

### Pitfall 4: `verbatimModuleSyntax` type import violation
**What goes wrong:** TypeScript build fails with "This import is never used as a value and must use 'import type'".
**Why it happens:** `tsconfig.app.json` has `"verbatimModuleSyntax": true`. All interface/type-only imports must use `import type`.
**How to avoid:** Always use `import type { FieldDefinition }` not `import { FieldDefinition }` when importing only types.

### Pitfall 5: Lookup cache miss causing empty selects
**What goes wrong:** User opens edit mode for a field with `field_type: "select"` — dropdown appears empty because lookups aren't fetched yet.
**Why it happens:** Lookups fetched lazily only when edit mode is entered.
**How to avoid:** Prefetch all 6 lookup tables when the panel first opens (not when edit mode is activated). Store in Zustand `lookupCache`. Check cache before fetching.

### Pitfall 6: Related entity navigation breaks if entity type routing is not in place
**What goes wrong:** Clicking "4 артикула" badge navigates to filtered articles view, but the URL/filter state only works after Phase 1's entity routing is complete.
**Why it happens:** Phase 2 depends on Phase 1's `detailPanelEntityType` and filter state shape.
**How to avoid:** Confirm Phase 1 delivers `detailPanelEntityType` in Zustand and URL navigation to `/product/matrix/articles?model_id=X` before implementing PANEL-08.

---

## Code Examples

Verified patterns from existing codebase:

### FieldDefinition-driven section grouping (from info-tab.tsx)
```typescript
// Pattern to reuse for read mode — already proven in InfoTab
const defMap = new Map<string, FieldDefinition>()
for (const fd of fieldDefs) {
  defMap.set(fd.field_name, fd)
}
// Group by section preserving sort_order
definedFields.sort((a, b) => a.sortOrder - b.sortOrder)
```

### getLookup call (from matrix-api.ts)
```typescript
// Available lookup tables: kategorii, kollekcii, statusy, razmery, importery, fabriki
matrixApi.getLookup("kategorii")  // returns LookupItem[] { id: number, nazvanie: string }
```

### PATCH endpoint usage (from matrix-api.ts)
```typescript
// All three entity types:
matrixApi.updateModel(id, data)    // PATCH /api/matrix/models/:id
matrixApi.updateArticle(id, data)  // PATCH /api/matrix/articles/:id
matrixApi.updateProduct(id, data)  // PATCH /api/matrix/products/:id
// Backend uses exclude_none=True — only send changed fields
```

### Base UI Collapsible (from installed package)
```typescript
import { Collapsible } from "@base-ui/react/collapsible"
// Exports: Collapsible.Root, Collapsible.Trigger, Collapsible.Panel
// Props: defaultOpen (uncontrolled), open/onOpenChange (controlled)
```

### Base UI Drawer (from installed package)
```typescript
import { Drawer } from "@base-ui/react/drawer"
// Exports: Drawer.Root, Drawer.Trigger, Drawer.Portal, Drawer.Popup,
//          Drawer.Content, Drawer.Backdrop, Drawer.Close, Drawer.Title
// Key prop on Root: modal={false} — non-modal, doesn't trap focus
```

### Select component (existing ui/select.tsx — uses Base UI Select)
```typescript
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select"
// Used for select-type fields in edit mode
// SelectPrimitive.Root accepts: value, onValueChange
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `detail-panel.tsx` hardcoded to ModelOsnova only | Entity-aware panel routing (Phase 1) | Phase 1 | Panel now handles any entity type |
| `InfoTab` 2-column grid layout | 1-column label→value stacked (Notion-style) | Phase 2 | Matches CONTEXT.md decision |
| `<aside>` embedded in page layout | Sheet overlay via Drawer portal | Phase 2 | Panel overlays table without squeezing it |
| No edit capability in panel | Toggle-mode form editing | Phase 2 | Full CRUD from panel |

**Deprecated/outdated:**
- `detail-panel.tsx` current implementation: Replace entirely — it's a model-only sidebar `<aside>`, not a Sheet overlay.
- `InfoTab`'s `Section` component (2-column grid): Replace with 1-column stacked layout inside the new panel body.

---

## Open Questions

1. **Should `is_editable` be a new DB column or derived from `is_system` + naming convention?**
   - What we know: `FieldDefinition` has `is_system: bool` but no `is_editable`; STATE.md flags this as a Phase 2 prereq
   - What's unclear: Whether adding a DB migration for `is_editable` is acceptable scope or whether using `is_system=true` + `_name` suffix heuristic is sufficient
   - Recommendation: Use `is_system=true` to mean "not editable" for now (avoids migration); add `_name` suffix filter in frontend as belt-and-suspenders. If Phase 3 needs finer control, add `is_editable` column then.

2. **Are `field_definitions` rows seeded for all three entity types?**
   - What we know: CONTEXT.md notes "currently unknown population state"; `listFields(entityType)` returns empty array if no rows exist, falling back to raw keys in `InfoTab`
   - What's unclear: Whether seed data exists for `modeli_osnova`, `artikuly`, `tovary`
   - Recommendation: Wave 0 task must query `/api/matrix/schema/modeli_osnova` and check. If empty, create a migration/seed script as part of Wave 0.

3. **Resize handle implementation — mouse vs CSS `resize`?**
   - What we know: Decision is min 400px, max 800px, drag edge; no library specified
   - What's unclear: CSS `resize: horizontal` vs JS mouse drag
   - Recommendation: CSS `resize: horizontal` on the panel container with `min-width`/`max-width` constraints is the simplest approach (2 lines of CSS). JS mouse drag adds complexity without benefit for this use case.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in config.json — treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright (installed: `@playwright/test` 1.52.0) |
| Config file | Not detected — see Wave 0 |
| Quick run command | `npx playwright test --grep "detail-panel"` |
| Full suite command | `npx playwright test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PANEL-01 | ModelOsnova fields appear in sections in read mode | e2e | `npx playwright test --grep "PANEL-01"` | Wave 0 |
| PANEL-02 | Artikul fields appear in read mode | e2e | `npx playwright test --grep "PANEL-02"` | Wave 0 |
| PANEL-03 | Tovar fields appear; marketplace IDs non-editable | e2e | `npx playwright test --grep "PANEL-03"` | Wave 0 |
| PANEL-04 | Edit mode shows correct input types | e2e | `npx playwright test --grep "PANEL-04"` | Wave 0 |
| PANEL-05 | Select fields populate from lookups | e2e | `npx playwright test --grep "PANEL-05"` | Wave 0 |
| PANEL-06 | Save persists changes; Cancel discards | e2e | `npx playwright test --grep "PANEL-06"` | Wave 0 |
| PANEL-07 | System fields remain text in edit mode | e2e | `npx playwright test --grep "PANEL-07"` | Wave 0 |
| PANEL-08 | Related badge click navigates to filtered view | e2e | `npx playwright test --grep "PANEL-08"` | Wave 0 |

### Sampling Rate
- **Per task commit:** `npx playwright test --grep "detail-panel" --headed=false`
- **Per wave merge:** `npx playwright test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/e2e/detail-panel.spec.ts` — covers PANEL-01 through PANEL-08
- [ ] `playwright.config.ts` — base URL, browser config
- [ ] `src/components/ui/sheet.tsx` — component must exist before tests can import it

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `wookiee-hub/src/components/matrix/detail-panel.tsx` — current state confirmed
- Direct codebase inspection: `wookiee-hub/src/components/matrix/tabs/info-tab.tsx` — FieldDefinition section grouping pattern
- Direct codebase inspection: `wookiee-hub/src/lib/matrix-api.ts` — all API types and methods
- Direct codebase inspection: `wookiee-hub/src/stores/matrix-store.ts` — Zustand state shape
- Direct codebase inspection: `services/product_matrix_api/models/schemas.py` — ModelOsnovaRead gap confirmed
- Direct codebase inspection: `services/product_matrix_api/models/database.py` — FieldDefinition columns confirmed
- Direct codebase inspection: `node_modules/@base-ui/react/` — Drawer and Collapsible confirmed available
- Direct codebase inspection: `wookiee-hub/src/components/ui/` — Sheet NOT present, Dialog/Select/Popover/Skeleton present

### Secondary (MEDIUM confidence)
- Base UI Drawer types: `node_modules/@base-ui/react/drawer/root/DrawerRoot.d.ts` — `modal` prop confirmed
- shadcn `components.json` — `base-nova` style confirmed, which affects which components are auto-included

### Tertiary (LOW confidence)
- CSS `resize: horizontal` pattern — standard CSS, works in all modern browsers, no source verification needed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified by direct inspection of node_modules and package.json
- Architecture: HIGH — patterns derived from existing codebase code, not assumptions
- Pitfalls: HIGH — ModelOsnovaRead gap and Sheet absence confirmed by direct file inspection; `is_editable` blocker from STATE.md
- Validation: MEDIUM — Playwright config not found; test file paths are recommendations

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable stack; Base UI 1.x API unlikely to change)
