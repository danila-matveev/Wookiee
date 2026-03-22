# Stack Research

**Domain:** Notion-like PIM table editor (React, existing shadcn/ui project)
**Researched:** 2026-03-22
**Confidence:** HIGH — all versions verified from npm registry; all integration patterns verified via official docs and official examples

---

## Context: What Already Exists (Do Not Re-add)

| Already Installed | Version | Notes |
|---|---|---|
| React | ^19.2.0 | Do NOT use React Compiler — breaks TanStack Table re-render (known issue) |
| Vite + TypeScript | ^7 / ~5.9.3 | Stable |
| Tailwind CSS v4 | ^4.1.17 | Already configured |
| shadcn/ui | ^3.8.5 | Component source model — all new UI components add via `npx shadcn@latest add` |
| @dnd-kit/core | ^6.3.1 | Already present — used for column reorder, no additional DnD library needed |
| @dnd-kit/sortable | ^10.0.0 | Already present |
| zustand | ^5.0.11 | State management for table UI state (column visibility, panel open/close) |

---

## Recommended Stack Additions

### Core Libraries

| Technology | Version (npm latest) | Purpose | Why Recommended |
|---|---|---|---|
| @tanstack/react-table | 8.21.3 | Headless table engine — sorting, filtering, column ordering, column resize, row selection | Official TanStack/shadcn integration; headless = zero style conflict with Tailwind; ~15 KB gzipped; column resize is built-in (`getResizeHandler()`), no extra library needed; `@dnd-kit` (already installed) covers column drag-reorder per official TanStack column DnD example |
| @tanstack/react-virtual | 3.13.23 | Virtual scrolling for 1000+ rows | Same ecosystem as TanStack Table; composable with it; renders only visible rows at 60fps; integrates with column virtualization for wide tables (86-column Tovar view) |
| react-hook-form | 7.72.0 | Form state and validation for detail panel edit forms | shadcn/ui `<Form>` component is built on react-hook-form; the existing project likely already expects this pattern; minimal re-render on field change |
| zod | 4.3.6 | Schema validation | Use **`zod` v3 API style via `zod/v4` subpath** — Zod 4 is stable, but `@hookform/resolvers` v5.2.x has known edge-case type errors with zod 4; pin to `zod@3.25.x` until `@hookform/resolvers` >= 5.3 ships a confirmed fix. See note below. |
| @hookform/resolvers | 5.2.2 | Bridge between react-hook-form and zod schemas | Required for `zodResolver`; supports Zod 3 and Zod 4; ship v5.2.2 with Zod 3.x to stay clear of the known type-error issues |

> **Zod version decision:** npm latest is `zod@4.3.6`, but GitHub issues #12816 and #13047 on react-hook-form confirm that zodResolver does not fully capture ZodError under some Zod 4 scenarios as of March 2026. Use `zod@3.25.x` with `@hookform/resolvers@5.2.2` until this is resolved upstream. Re-evaluate at next milestone.

### shadcn/ui Components to Add

These are added via the shadcn CLI (`npx shadcn@latest add <name>`), not npm installs. They copy source into the project and integrate with existing Tailwind config.

| Component | shadcn add name | Purpose |
|---|---|---|
| Sheet | `sheet` | Right-side detail panel — slides from right, built on Radix Dialog, full accessibility. Prefer over `drawer` for desktop-primary PIM workflow. |
| Form | `form` | Wraps react-hook-form + shadcn inputs with accessible labels and error messages |
| Select | `select` | Reference field dropdowns (Kategoriya, Cvet, Fabrika, Status, etc.) |
| Command | `command` | Already installed (`cmdk@^1.1.1`) — use for searchable select within reference fields |
| Separator | `separator` | Panel section dividers |
| Badge | `badge` | Status chips in table rows |
| Tooltip | `tooltip` | Column header info icons |
| Checkbox | `checkbox` | Row selection |

> Sheet's `side="right"` prop positions it as a Notion-style detail panel. The `<SheetContent>` width can be set via className (e.g., `w-[600px]`). No additional panel library is needed.

### Supporting Infrastructure

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| react-resizable-panels | 4.7.5 | Resizable split-pane layout (table + detail panel side-by-side, not overlay) | Only if UX calls for persistent side panel (Notion-database style) rather than overlay sheet. Ships with shadcn `resizable` component. Add if product decides on non-overlay panel. |

---

## Installation

```bash
# Core table + virtual scrolling
npm install @tanstack/react-table@8.21.3 @tanstack/react-virtual@3.13.23

# Form validation (pin zod to v3 — see note above)
npm install react-hook-form@7.72.0 zod@3.25.4 @hookform/resolvers@5.2.2

# shadcn/ui component additions (copies source, no npm install needed for these)
npx shadcn@latest add sheet
npx shadcn@latest add form
npx shadcn@latest add select
npx shadcn@latest add separator
npx shadcn@latest add badge
npx shadcn@latest add tooltip
npx shadcn@latest add checkbox

# Optional: resizable split-pane (only if non-overlay panel chosen)
npx shadcn@latest add resizable
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|---|---|---|
| @tanstack/react-table | AG Grid React | AG Grid advanced features require paid enterprise license. Free tier lacks column reordering. ~200KB+ bundle vs 15KB TanStack. Overkill for a single editor view with 1000 rows. |
| @tanstack/react-table | Material React Table | Wraps TanStack but couples to MUI styling system; conflicts with existing Tailwind + shadcn setup. Would require MUI theme override fights. |
| @tanstack/react-table | react-data-grid (adazzle) | Opinionated DOM structure; harder to integrate with shadcn/ui primitive components; column definition API diverges from the headless pattern. |
| shadcn Sheet | react-resizable-panels (persistent split) | Persistent panel reduces table visible area significantly on 13" laptops. Overlay sheet is the Notion/Linear pattern for detail editing. Offer resizable split as a power-user toggle later. |
| @tanstack/react-virtual | react-window / react-virtuoso | react-window is largely unmaintained. react-virtuoso works but adds 25KB; @tanstack/react-virtual integrates tighter with TanStack Table column virtualization and shares the same ecosystem. |
| react-hook-form + zod | Formik + yup | Formik is significantly slower on field-change re-renders for a detail panel with 40+ fields. react-hook-form's uncontrolled model is better for large forms. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| AG Grid / Syncfusion Grid / DevExtreme Grid | Heavy PIM/grid frameworks that dictate markup, styling, and licensing. Bundle sizes 200KB–2MB. Conflict with Tailwind. Not composable with shadcn. | @tanstack/react-table (headless) + custom shadcn-styled cells |
| react-beautiful-dnd | Archived by Atlassian. No React 19 support. | @dnd-kit (already installed) |
| React Compiler (Babel plugin) | Known issue: TanStack Table does not re-render correctly when data changes under the React Compiler (GitHub issue #5567). | Do not enable React Compiler until TanStack Table ships a fix. |
| zod@4.x with @hookform/resolvers@5.2.x | Active bug: ZodError thrown instead of captured by zodResolver in some scenarios (issues #12816, #13047). | Pin zod@3.25.x until upstream fix confirmed. |
| Separate column resize library (react-resizable, re-resizable) | TanStack Table v8 has built-in column sizing with `getResizeHandler()`. Extra library = conflicting state. | Use `columnResizeMode: "onChange"` in TanStack Table options. |

---

## Stack Patterns by Feature

**Notion-like table view (sortable + filterable columns):**
- TanStack Table `useReactTable` with `getSortedRowModel()`, `getFilteredRowModel()`, `getFacetedUniqueValues()`
- Column header: `<th>` with `header.column.getToggleSortingHandler()` onClick
- Filter inputs rendered above table or in column header popover using shadcn `<Popover>` + `<Input>`

**Column resize:**
- TanStack Table built-in: `enableColumnResizing: true`, `columnResizeMode: "onChange"`
- Render `<div onMouseDown={header.getResizeHandler()} onTouchStart={header.getResizeHandler()}` on column edge
- No external library needed

**Column drag-reorder:**
- `@dnd-kit/core` + `@dnd-kit/sortable` (already installed) with `SortableContext`
- TanStack Table's `setColumnOrder()` in `onDragEnd` handler
- Official example: `tanstack.com/table/latest/docs/framework/react/examples/column-dnd`

**Virtual scrolling (1000+ rows):**
- `@tanstack/react-virtual` `useVirtualizer` with `estimateSize` and absolute positioning of rows
- For 86-column Tovar view: add `getVirtualColumns()` for horizontal virtualization

**Detail side panel:**
- shadcn `<Sheet side="right">` — open/close state in zustand store
- `<SheetContent className="w-[560px] overflow-y-auto">` for 40+ field forms
- react-hook-form `useForm<EntitySchema>()` with `zodResolver` + `reset(rowData)` on panel open

**Inline cell validation (for status/simple fields edited in-table):**
- Keep inline editing minimal — reserved for single-select Status fields only
- Use shadcn `<Select>` rendered directly in the cell, call mutation on `onValueChange`
- Do NOT use react-hook-form for single-cell inline edits; zustand local state + direct API call is sufficient

---

## Version Compatibility

| Package | Compatible With | Notes |
|---|---|---|
| @tanstack/react-table@8.21.3 | React 19, TypeScript 5.x | Works. Do NOT enable React Compiler. |
| @tanstack/react-virtual@3.13.23 | @tanstack/react-table@8.x | Same major ecosystem, composable. |
| @dnd-kit/sortable@10.0.0 | @tanstack/react-table@8.x | Integrate via `setColumnOrder`. Official TanStack column DnD example uses dnd-kit. |
| react-hook-form@7.72.0 | React 19, shadcn/ui@3.x | Stable. |
| zod@3.25.x | @hookform/resolvers@5.2.2 | Safe. Avoid zod@4.x until resolver bug fixed. |
| react-resizable-panels@4.7.5 | shadcn `resizable` component | shadcn ships this as a wrapper. Install via `npx shadcn@latest add resizable`. |

---

## Bundle Size Impact

| Addition | Size (gzip) | Impact |
|---|---|---|
| @tanstack/react-table | ~15 KB | Low |
| @tanstack/react-virtual | ~6 KB | Low |
| react-hook-form | ~13 KB | Low |
| zod@3.25 | ~14 KB | Low (already likely expected from shadcn form patterns) |
| @hookform/resolvers | ~3 KB | Negligible |
| shadcn Sheet | ~0 KB (copies source, already using Radix Dialog) | Negligible |
| **Total new additions** | ~51 KB gzip | Acceptable for a business internal tool |

---

## Sources

- TanStack Table v8 docs (installation, column sizing, column ordering, React adapter): `tanstack.com/table/v8/docs/`
- TanStack Table column DnD official example: `tanstack.com/table/latest/docs/framework/react/examples/column-dnd`
- TanStack Virtual v3 docs: `tanstack.com/virtual/latest`
- shadcn/ui Sheet component: `ui.shadcn.com/docs/components/radix/sheet`
- shadcn/ui Form + react-hook-form integration: `ui.shadcn.com/docs/forms/react-hook-form`
- shadcn/ui Resizable (react-resizable-panels): `ui.shadcn.com/docs/components/radix/resizable`
- Zod v4 / react-hook-form compatibility issues: GitHub react-hook-form #12816, #13047, colinhacks/zod #4989
- npm registry versions verified 2026-03-22: @tanstack/react-table@8.21.3, @tanstack/react-virtual@3.13.23, react-hook-form@7.72.0, zod@4.3.6 (pinning to 3.25.x), @hookform/resolvers@5.2.2, react-resizable-panels@4.7.5
- TanStack Table vs AG Grid comparison (confidence: MEDIUM): `simple-table.com/blog/tanstack-table-vs-ag-grid-comparison`

---

*Stack research for: Wookiee Product Matrix — Notion-like table UI milestone*
*Researched: 2026-03-22*
