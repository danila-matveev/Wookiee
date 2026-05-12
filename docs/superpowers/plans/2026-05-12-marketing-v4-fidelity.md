# Marketing v4 Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `/marketing/{promo-codes,search-queries}` to pixel-perfect match with `wookiee_marketing_v4.jsx` prototype, with full CRUD on real Supabase data, configurable grouping, and closed UI↔DB↔Sheets↔WB sync loop.

**Architecture:** Phase 2A (frontend visual + CRUD on existing data via local UI components and CSS-variable scoped palette) + Phase 2B (additive view/RPC update + sync bridge in existing Python scripts + sync trigger endpoint in `analytics_api`).

**Tech Stack:** TypeScript + React 19 + Vite + TanStack Query 5 (frontend); Vitest + Testing Library (tests); Supabase JS Client; Python 3.11 + FastAPI + gspread + httpx (backend); PostgreSQL 17 (Supabase); pytest (backend tests).

**Source of truth:** `docs/superpowers/specs/2026-05-12-marketing-v4-fidelity-design.md` (commits `d7d25c4`, `23af98a`).

---

## Pre-flight

### Task P.1: Create feature branch

**Files:** none

- [ ] **Step 1: Verify clean working tree**

Run: `git status --short`
Expected: only untracked files in `.claude/worktrees/` and `docs/superpowers/plans/2026-05-12-marketing-v4-fidelity.md`. No modifications to tracked files.

- [ ] **Step 2: Create and switch to feature branch**

Run:
```bash
git checkout -b feature/marketing-v4-fidelity
git status
```
Expected: `On branch feature/marketing-v4-fidelity, nothing to commit, working tree clean` (plan file is untracked and ignored for now).

- [ ] **Step 3: Verify base is up-to-date with main**

Run: `git log --oneline -5`
Expected: top commit is `23af98a docs(marketing): self-review fixes to v4 fidelity design`.

---

## Phase 2A — Frontend Fidelity

### Wave A.0 — Foundation

### Task A.0: MarketingLayout

**Files:**
- Create: `wookiee-hub/src/components/layout/marketing-layout.tsx`
- Modify: `wookiee-hub/src/router.tsx` (around line 143-149 — replace two flat marketing routes with MarketingLayout wrapper)
- Test: `wookiee-hub/src/components/layout/__tests__/marketing-layout.test.tsx`

- [ ] **Step 1: Write failing test**

Create `wookiee-hub/src/components/layout/__tests__/marketing-layout.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import { MarketingLayout } from '../marketing-layout'

describe('MarketingLayout', () => {
  it('renders sub-sidebar with МАРКЕТИНГ heading and 2 nav items', () => {
    render(
      <MemoryRouter initialEntries={['/marketing/search-queries']}>
        <Routes>
          <Route path="/marketing" element={<MarketingLayout />}>
            <Route path="search-queries" element={<div>Search Page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('МАРКЕТИНГ')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Промокоды/i })).toHaveAttribute('href', '/marketing/promo-codes')
    expect(screen.getByRole('link', { name: /Поисковые запросы/i })).toHaveAttribute('href', '/marketing/search-queries')
    expect(screen.getByText('Search Page')).toBeInTheDocument()
  })

  it('sets data-section="marketing" on root element', () => {
    const { container } = render(
      <MemoryRouter><MarketingLayout /></MemoryRouter>
    )
    expect(container.querySelector('[data-section="marketing"]')).not.toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd wookiee-hub && npx vitest run src/components/layout/__tests__/marketing-layout.test.tsx`
Expected: FAIL with `Cannot find module '../marketing-layout'`

- [ ] **Step 3: Create MarketingLayout**

Create `wookiee-hub/src/components/layout/marketing-layout.tsx`:
```tsx
import { NavLink, Outlet } from "react-router-dom"
import { Percent, Hash } from "lucide-react"

const SUB_NAV = [
  { to: "/marketing/promo-codes", icon: Percent, label: "Промокоды" },
  { to: "/marketing/search-queries", icon: Hash, label: "Поисковые запросы" },
] as const

export function MarketingLayout() {
  return (
    <div data-section="marketing" className="flex h-screen overflow-hidden" style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <aside className="w-44 shrink-0 flex flex-col border-r border-stone-200 bg-white">
        <div className="px-3 py-3 border-b border-stone-100">
          <div className="text-[11px] uppercase tracking-wider text-stone-400 font-medium px-1">
            МАРКЕТИНГ
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {SUB_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${
                  isActive
                    ? "bg-stone-100 text-stone-900 font-medium"
                    : "text-stone-500 hover:bg-stone-50"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className={`w-3.5 h-3.5 ${isActive ? "text-stone-700" : "text-stone-400"}`} />
                  <span className="truncate text-left">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Register layout in router**

Open `wookiee-hub/src/router.tsx`. Find the block around line 143-149 where marketing routes are registered (look for `featureFlags.marketing` conditional). Replace the two separate marketing route entries with a single layout-wrapped block:

```tsx
import { MarketingLayout } from "@/components/layout/marketing-layout"

// inside the routes array, in the marketing feature flag block:
...(featureFlags.marketing
  ? [
      {
        path: "/marketing",
        element: <MarketingLayout />,
        children: [
          { path: "promo-codes", lazy: () => import("./pages/marketing/promo-codes") },
          { path: "search-queries", lazy: () => import("./pages/marketing/search-queries") },
        ],
      },
    ]
  : []),
```

- [ ] **Step 5: Run test to verify pass**

Run: `cd wookiee-hub && npx vitest run src/components/layout/__tests__/marketing-layout.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Smoke-test in browser**

Run: `cd wookiee-hub && npm run dev`
Open `http://localhost:5173/marketing/search-queries` — should show «МАРКЕТИНГ» sidebar with both nav items, current page highlighted.

- [ ] **Step 7: Commit**

```bash
git add wookiee-hub/src/components/layout/marketing-layout.tsx \
        wookiee-hub/src/components/layout/__tests__/marketing-layout.test.tsx \
        wookiee-hub/src/router.tsx
git commit -m "feat(marketing): add MarketingLayout with sub-sidebar + data-section attribute"
```

---

### Wave A.1 — Visual & Typography

### Task A.1.1: Stone palette CSS-variable override

**Files:**
- Modify: `wookiee-hub/src/index.css` (append at end)

- [ ] **Step 1: Identify existing OKLCH variables**

Run: `head -80 wookiee-hub/src/index.css`
Note the current `:root` block with `--background`, `--foreground`, `--card`, `--muted`, `--border` etc.

- [ ] **Step 2: Append stone override scope to index.css**

Append at end of `wookiee-hub/src/index.css`:
```css
/* Marketing section — stone palette override per design 2026-05-12 */
[data-section="marketing"] {
  --background: oklch(0.985 0 0);   /* near-white */
  --foreground: oklch(0.146 0.005 60); /* stone-900 */
  --card: oklch(1 0 0);             /* white */
  --card-foreground: oklch(0.146 0.005 60);
  --muted: oklch(0.97 0.005 60);    /* stone-50 */
  --muted-foreground: oklch(0.55 0.01 60); /* stone-400 */
  --border: oklch(0.91 0.005 60);   /* stone-200 */
  --input: oklch(0.91 0.005 60);
  --primary: oklch(0.146 0.005 60); /* stone-900 */
  --primary-foreground: oklch(1 0 0);
}
```

- [ ] **Step 3: Smoke-test in browser**

Run `npm run dev` if not running, open `/marketing/search-queries`. Compared with `/catalog/matrix` — backgrounds visually match (slight warm tint), borders are stone-tinted, no jarring contrast.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/index.css
git commit -m "feat(marketing): inject stone palette via [data-section=\"marketing\"] CSS-variable override"
```

### Task A.1.2: Local Badge / Button / Input components

**Files:**
- Create: `wookiee-hub/src/components/marketing/Badge.tsx`
- Create: `wookiee-hub/src/components/marketing/Button.tsx`
- Create: `wookiee-hub/src/components/marketing/Input.tsx`
- Test: `wookiee-hub/src/components/marketing/__tests__/Badge.test.tsx`

- [ ] **Step 1: Write failing Badge test**

Create `wookiee-hub/src/components/marketing/__tests__/Badge.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Badge } from '../Badge'

describe('Badge', () => {
  it('renders label with green color classes', () => {
    render(<Badge color="green" label="Используется" />)
    const el = screen.getByText('Используется')
    expect(el.className).toContain('bg-emerald-50')
    expect(el.className).toContain('text-emerald-700')
  })

  it('shows dot when not compact', () => {
    const { container } = render(<Badge color="blue" label="Свободен" />)
    expect(container.querySelector('.bg-blue-500')).not.toBeNull()
  })

  it('hides dot in compact mode', () => {
    const { container } = render(<Badge color="amber" label="Не идентиф." compact />)
    expect(container.querySelector('.bg-amber-500')).toBeNull()
  })

  it('falls back to gray for unknown color', () => {
    render(<Badge color={'unknown' as any} label="X" />)
    expect(screen.getByText('X').className).toContain('bg-stone-100')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd wookiee-hub && npx vitest run src/components/marketing/__tests__/Badge.test.tsx`
Expected: FAIL with `Cannot find module '../Badge'`

- [ ] **Step 3: Create Badge.tsx**

Create `wookiee-hub/src/components/marketing/Badge.tsx` (replica of JSX:199-203):
```tsx
type BadgeColor = "green" | "blue" | "amber" | "gray"

interface BadgeProps {
  color: BadgeColor
  label: string
  compact?: boolean
}

const BG: Record<BadgeColor, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue: "bg-blue-50 text-blue-700 ring-blue-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  gray: "bg-stone-100 text-stone-600 ring-stone-500/20",
}

const DOT: Record<BadgeColor, string> = {
  green: "bg-emerald-500",
  blue: "bg-blue-500",
  amber: "bg-amber-500",
  gray: "bg-stone-400",
}

export function Badge({ color, label, compact }: BadgeProps) {
  const bg = BG[color] ?? BG.gray
  const dot = DOT[color] ?? DOT.gray
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium ring-1 ring-inset ${bg}`}
    >
      {!compact && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
      {label}
    </span>
  )
}
```

- [ ] **Step 4: Create Input.tsx (minimal)**

Create `wookiee-hub/src/components/marketing/Input.tsx`:
```tsx
import { forwardRef, InputHTMLAttributes } from "react"

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => (
    <input
      ref={ref}
      className={`w-full border border-stone-200 rounded-md px-2.5 py-1.5 text-sm text-stone-900 focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 bg-white ${className}`}
      {...props}
    />
  )
)
Input.displayName = "Input"
```

- [ ] **Step 5: Create Button.tsx (minimal)**

Create `wookiee-hub/src/components/marketing/Button.tsx`:
```tsx
import { ButtonHTMLAttributes, forwardRef } from "react"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary"
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", className = "", ...props }, ref) => {
    const base = "py-1.5 rounded-md text-sm font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    const variants = {
      primary: "bg-stone-900 text-white hover:bg-stone-800 px-3",
      secondary: "border border-stone-200 text-stone-700 hover:bg-stone-50 px-3",
    }
    return <button ref={ref} className={`${base} ${variants[variant]} ${className}`} {...props} />
  }
)
Button.displayName = "Button"
```

- [ ] **Step 6: Run Badge test to verify pass**

Run: `cd wookiee-hub && npx vitest run src/components/marketing/__tests__/Badge.test.tsx`
Expected: PASS, 4 tests.

- [ ] **Step 7: Commit**

```bash
git add wookiee-hub/src/components/marketing/{Badge,Button,Input}.tsx \
        wookiee-hub/src/components/marketing/__tests__/Badge.test.tsx
git commit -m "feat(marketing): add local Badge/Button/Input components (decoupled from CRM)"
```

### Task A.1.3: Load Instrument Serif font

**Files:**
- Modify: `wookiee-hub/src/index.css` (append `@import` near top)

- [ ] **Step 1: Inspect current font imports**

Run: `head -10 wookiee-hub/src/index.css`
Note any existing `@import` lines.

- [ ] **Step 2: Add Instrument Serif to Google Fonts import**

If `index.css` already imports DM Sans — extend that line. Otherwise add at line 1:
```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');
```

- [ ] **Step 3: Verify font loads in browser**

Reload `localhost:5173`. Open DevTools → Network → filter "font" — should see `Instrument_Serif` and `DM_Sans` woff2 fetches with 200 status.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/index.css
git commit -m "feat(marketing): load Instrument Serif font via Google Fonts"
```

### Task A.1.4: Apply v4 typography to page headers

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx`

- [ ] **Step 1: Update SearchQueriesPage header**

Open `wookiee-hub/src/pages/marketing/search-queries.tsx`. Find the `<h1>` element (around line 63-64). Replace its declaration with:
```tsx
<h1
  className="text-stone-900"
  style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: "italic" }}
>
  Поисковые запросы
</h1>
<p className="text-sm text-stone-500 mt-0.5">Брендовые, артикулы и подменные WW-коды</p>
```

- [ ] **Step 2: Update PromoCodesPage header**

Open `wookiee-hub/src/pages/marketing/promo-codes.tsx`. Find the `<h1>` element (around line 15-16). Replace with:
```tsx
<h1
  className="text-stone-900"
  style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: "italic" }}
>
  Промокоды
</h1>
<p className="text-sm text-stone-500 mt-0.5">Статистика по кодам скидок</p>
```

- [ ] **Step 3: Visual smoke-test**

Open both `/marketing/promo-codes` and `/marketing/search-queries`. Headers should render in italic serif, ~24px size.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries.tsx wookiee-hub/src/pages/marketing/promo-codes.tsx
git commit -m "feat(marketing): apply v4 typography to page headers (Instrument Serif italic 24px)"
```

---

### Wave A.2 — Status & Labels

### Task A.2.1: Bidirectional UI↔DB status mapping

**Files:**
- Modify: `wookiee-hub/src/types/marketing.ts` (add status maps)
- Modify: `wookiee-hub/src/components/marketing/StatusEditor.tsx`
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` (status update converter)
- Test: `wookiee-hub/src/types/__tests__/marketing-status.test.ts`

- [ ] **Step 1: Write failing status-map test**

Create `wookiee-hub/src/types/__tests__/marketing-status.test.ts`:
```ts
import { describe, it, expect } from 'vitest'
import { STATUS_UI_TO_DB, STATUS_DB_TO_UI, STATUS_LABELS, STATUS_COLORS } from '../marketing'

describe('Status mappings', () => {
  it('round-trips UI→DB→UI', () => {
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.active]).toBe('active')
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.free]).toBe('free')
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.archive]).toBe('archive')
  })

  it('maps free→paused, archive→archived', () => {
    expect(STATUS_UI_TO_DB.free).toBe('paused')
    expect(STATUS_UI_TO_DB.archive).toBe('archived')
    expect(STATUS_UI_TO_DB.active).toBe('active')
  })

  it('exposes Russian labels per v4', () => {
    expect(STATUS_LABELS.active).toBe('Используется')
    expect(STATUS_LABELS.free).toBe('Свободен')
    expect(STATUS_LABELS.archive).toBe('Архив')
  })

  it('exposes badge colors per v4', () => {
    expect(STATUS_COLORS.active).toBe('green')
    expect(STATUS_COLORS.free).toBe('blue')
    expect(STATUS_COLORS.archive).toBe('gray')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd wookiee-hub && npx vitest run src/types/__tests__/marketing-status.test.ts`
Expected: FAIL — symbols not exported.

- [ ] **Step 3: Append mappings to types/marketing.ts**

Open `wookiee-hub/src/types/marketing.ts`. Append at end:
```ts
// v4 fidelity status mapping (design 2026-05-12)
// DB stores active|paused|archived; UI shows active|free|archive
export type StatusUI = 'active' | 'free' | 'archive'
export type StatusDB = 'active' | 'paused' | 'archived'

export const STATUS_UI_TO_DB: Record<StatusUI, StatusDB> = {
  active: 'active',
  free: 'paused',
  archive: 'archived',
}

export const STATUS_DB_TO_UI: Record<StatusDB, StatusUI> = {
  active: 'active',
  paused: 'free',
  archived: 'archive',
}

export const STATUS_LABELS: Record<StatusUI, string> = {
  active: 'Используется',
  free: 'Свободен',
  archive: 'Архив',
}

export const STATUS_COLORS: Record<StatusUI, 'green' | 'blue' | 'gray'> = {
  active: 'green',
  free: 'blue',
  archive: 'gray',
}
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd wookiee-hub && npx vitest run src/types/__tests__/marketing-status.test.ts`
Expected: PASS, 4 tests.

- [ ] **Step 5: Update StatusEditor to use UI values + labels**

Open `wookiee-hub/src/components/marketing/StatusEditor.tsx`. Replace its content:
```tsx
import { useState, useRef, useEffect } from "react"
import { Check, ChevronDown } from "lucide-react"
import { Badge } from "./Badge"
import { STATUS_LABELS, STATUS_COLORS, type StatusUI } from "@/types/marketing"

interface StatusEditorProps {
  status: StatusUI
  onChange: (next: StatusUI) => void
}

export function StatusEditor({ status, onChange }: StatusEditorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  const keys: StatusUI[] = ["active", "free", "archive"]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent hover:border-stone-200 transition-colors"
      >
        <Badge color={STATUS_COLORS[status]} label={STATUS_LABELS[status]} />
        <ChevronDown className="w-3 h-3 text-stone-300 group-hover:text-stone-500" />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-30 bg-white border border-stone-200 rounded-lg shadow-sm py-1 min-w-[150px]">
          {keys.map((k) => (
            <button
              key={k}
              onClick={() => {
                onChange(k)
                setOpen(false)
              }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-stone-50 transition-colors ${
                k === status ? "bg-stone-50" : ""
              }`}
            >
              <Badge color={STATUS_COLORS[k]} label={STATUS_LABELS[k]} compact />
              {k === status && <Check className="w-3 h-3 text-emerald-600 ml-auto" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Update search-queries API mutation to convert UI→DB**

Open `wookiee-hub/src/api/marketing/search-queries.ts`. Find the status-update function (around line 77-82). Replace with:
```ts
import { STATUS_UI_TO_DB, type StatusUI } from "@/types/marketing"

export async function updateSearchQueryStatus(
  source: 'branded_queries' | 'substitute_articles',
  id: number,
  statusUI: StatusUI
) {
  const statusDB = STATUS_UI_TO_DB[statusUI]
  const { error } = await supabase
    .schema('crm').from(source)
    .update({ status: statusDB, updated_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw new Error(error.message)
}
```

Update the hook in `wookiee-hub/src/hooks/marketing/use-search-queries.ts` to pass `StatusUI` and convert DB→UI when reading (consumers should read `STATUS_DB_TO_UI[row.status]`).

- [ ] **Step 7: Run all status-related tests**

Run: `cd wookiee-hub && npx vitest run src/types/__tests__/marketing-status.test.ts`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add wookiee-hub/src/types/marketing.ts \
        wookiee-hub/src/types/__tests__/marketing-status.test.ts \
        wookiee-hub/src/components/marketing/StatusEditor.tsx \
        wookiee-hub/src/api/marketing/search-queries.ts \
        wookiee-hub/src/hooks/marketing/use-search-queries.ts
git commit -m "feat(marketing): bidirectional UI<->DB status mapping (free<->paused, archive<->archived)"
```

### Task A.2.2: Use channel_label from useChannels lookup

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`

**Note:** Phase 2A reads `channel_label` via `useChannels()` lookup on the frontend, joining `purpose` → `channels.slug` → `channels.label`. After B.0.1 view migration lands, the view will return `channel_label` directly and this lookup can be simplified.

- [ ] **Step 1: Add channel resolution helper**

Open `wookiee-hub/src/hooks/marketing/use-channels.ts`. Append:
```ts
import { useMemo } from "react"

export function useChannelLabelLookup() {
  const { data: channels = [] } = useChannels()
  return useMemo(() => {
    const map = new Map<string, string>()
    for (const ch of channels) {
      map.set(ch.slug, ch.label)
    }
    return (slug: string | null | undefined): string => {
      if (!slug) return '—'
      return map.get(slug) ?? slug
    }
  }, [channels])
}
```

- [ ] **Step 2: Apply in SearchQueriesTable channel pills + cells**

Open `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`. Find channel filter pills + channel cells in rows. Wrap channel display with the lookup:
```tsx
const channelLabel = useChannelLabelLookup()
// ...
<span>{channelLabel(item.channel)}</span>
```

For unique channels in pills, derive distinct labels:
```tsx
const uniqueChannels = useMemo(() =>
  [...new Set(items.map(i => channelLabel(i.channel)).filter(Boolean))].sort(),
  [items, channelLabel]
)
```

- [ ] **Step 3: Apply in PromoCodesTable**

Open `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`. Replace channel cell rendering analogously.

- [ ] **Step 4: Smoke-test in browser**

Open `/marketing/search-queries`. Channel pills should show «Бренд», «Яндекс», «Adblogger», «Креаторы» etc. (labels), not `brand`/`yandex`/`adblogger`/`creators` (slugs).

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/hooks/marketing/use-channels.ts \
        wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx \
        wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx
git commit -m "feat(marketing): use channel_label via useChannels lookup in pills + table cells"
```

---

### Wave A.3 — Layout & Components Refactor

### Task A.3.1: Replace Drawer with split-pane (responsive lg: fallback)

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx`

- [ ] **Step 1: Update search-queries layout for split-pane**

Open `wookiee-hub/src/pages/marketing/search-queries.tsx`. Find the existing `<Drawer>` usage wrapping detail panel. Replace with:
```tsx
import { SearchQueryDetailPanel } from './search-queries/SearchQueryDetailPanel'
import { AddWWPanel } from './search-queries/AddWWPanel'
import { AddBrandQueryPanel } from './search-queries/AddBrandQueryPanel'
import { Drawer } from '@/components/crm/ui/Drawer' // kept for < lg fallback only
import { useMediaQuery } from '@/hooks/use-media-query' // create if missing

export default function SearchQueriesPage() {
  const [panel, setPanel] = useState<'closed' | 'detail' | 'add-ww' | 'add-brand'>('closed')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const isWide = useMediaQuery('(min-width: 1024px)')

  const panelContent = (() => {
    if (panel === 'add-ww') return <AddWWPanel onClose={() => setPanel('closed')} />
    if (panel === 'add-brand') return <AddBrandQueryPanel onClose={() => setPanel('closed')} />
    if (panel === 'detail' && selectedId) return (
      <SearchQueryDetailPanel id={selectedId} onClose={() => { setPanel('closed'); setSelectedId(null) }} />
    )
    return null
  })()

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* ... existing header + filters + table ... */}
        <SearchQueriesTable
          onRowClick={(id) => { setSelectedId(id); setPanel('detail') }}
          onAddWW={() => setPanel('add-ww')}
          onAddBrand={() => setPanel('add-brand')}
        />
      </div>

      {/* Split-pane on lg+, drawer fallback on smaller */}
      {isWide && panel !== 'closed' && (
        <aside className="w-[420px] shrink-0 border-l border-stone-200 bg-white flex flex-col h-full overflow-hidden">
          {panelContent}
        </aside>
      )}
      {!isWide && (
        <Drawer open={panel !== 'closed'} onClose={() => setPanel('closed')}>
          {panelContent}
        </Drawer>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create useMediaQuery hook if missing**

Check: `ls wookiee-hub/src/hooks/use-media-query.ts`. If missing, create:
```ts
import { useEffect, useState } from "react"

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false
  )

  useEffect(() => {
    if (typeof window === "undefined") return
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [query])

  return matches
}
```

- [ ] **Step 3: Apply same pattern to promo-codes.tsx**

Open `wookiee-hub/src/pages/marketing/promo-codes.tsx`. Replace `Drawer` wrapper with the `isWide ? <aside w-[400px]> : <Drawer>` pattern, panel state with `'closed' | 'detail' | 'add'`.

- [ ] **Step 4: Smoke-test split-pane**

In browser:
1. Open `/marketing/search-queries` in full-width window (≥1024px), click a row → panel appears as right column inline.
2. Resize window narrower than 1024px → existing data shouldn't disappear; click another row → drawer slides in.

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries.tsx \
        wookiee-hub/src/pages/marketing/promo-codes.tsx \
        wookiee-hub/src/hooks/use-media-query.ts
git commit -m "refactor(marketing): replace Drawer with split-pane (responsive lg: fallback)"
```

### Task A.3.2: Align SectionHeader with v4 (icon + count + chevron)

**Files:**
- Modify: `wookiee-hub/src/components/marketing/SectionHeader.tsx`

- [ ] **Step 1: Read current SectionHeader**

Run: `cat wookiee-hub/src/components/marketing/SectionHeader.tsx`

- [ ] **Step 2: Replace with v4-aligned implementation**

Replace the file content:
```tsx
import { ChevronDown, ChevronRight } from "lucide-react"

interface SectionHeaderProps {
  icon: string
  label: string
  count: number
  collapsed: boolean
  onToggle: () => void
  colSpan?: number
}

export function SectionHeader({ icon, label, count, collapsed, onToggle, colSpan = 12 }: SectionHeaderProps) {
  return (
    <tr
      className="bg-stone-50/80 border-y border-stone-200 cursor-pointer select-none hover:bg-stone-100/60 transition-colors"
      onClick={onToggle}
    >
      <td colSpan={colSpan} className="px-3 py-2">
        <div className="flex items-center gap-2">
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5 text-stone-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-stone-400" />
          )}
          <span className="text-[12px] font-medium text-stone-700">
            {icon} {label}
          </span>
          <span className="text-[11px] tabular-nums text-stone-400">{count}</span>
        </div>
      </td>
    </tr>
  )
}
```

- [ ] **Step 3: Update existing test**

Open `wookiee-hub/src/components/marketing/__tests__/SectionHeader.test.tsx`. Update test imports and props as needed to match new signature:
```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { SectionHeader } from '../SectionHeader'

describe('SectionHeader', () => {
  it('renders icon, label, count', () => {
    const onToggle = vi.fn()
    render(
      <table><tbody>
        <SectionHeader icon="🔤" label="Брендированные запросы" count={15} collapsed={false} onToggle={onToggle} />
      </tbody></table>
    )
    expect(screen.getByText(/🔤 Брендированные запросы/)).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('calls onToggle on click', () => {
    const onToggle = vi.fn()
    render(
      <table><tbody>
        <SectionHeader icon="📦" label="X" count={1} collapsed={false} onToggle={onToggle} />
      </tbody></table>
    )
    fireEvent.click(screen.getByText(/📦 X/))
    expect(onToggle).toHaveBeenCalled()
  })
})
```

- [ ] **Step 4: Run tests**

Run: `cd wookiee-hub && npx vitest run src/components/marketing/__tests__/SectionHeader.test.tsx`
Expected: PASS.

- [ ] **Step 5: Update group config in SearchQueriesTable**

Open `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`. Find the GROUPS const, update icons:
```tsx
const GROUPS = [
  { id: 'brand',       label: 'Брендированные запросы', icon: '🔤' },
  { id: 'external',    label: 'Артикулы (внешний лид)', icon: '📦' },
  { id: 'cr_general',  label: 'Креаторы общие',         icon: '👥' },
  { id: 'cr_personal', label: 'Креаторы личные',        icon: '👤' },
] as const
```

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/components/marketing/SectionHeader.tsx \
        wookiee-hub/src/components/marketing/__tests__/SectionHeader.test.tsx \
        wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx
git commit -m "refactor(marketing): align SectionHeader with v4 (🔤/📦/👥/👤 + count + chevron)"
```

### Task A.3.3: Align AddWWPanel cascade with v4

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx`

- [ ] **Step 1: Read current implementation**

Run: `cat wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx | head -100`

- [ ] **Step 2: Rewrite to match JSX:465-494**

Replace contents:
```tsx
import { useState } from "react"
import { X } from "lucide-react"
import { SelectMenu } from "@/components/marketing/SelectMenu"
import { Input } from "@/components/marketing/Input"
import { Button } from "@/components/marketing/Button"
import { useCreateSubstituteArticle } from "@/hooks/marketing/use-search-queries"
import { useModeli, useArtikulyForModel } from "@/hooks/marketing/use-artikuly"
import { useChannels } from "@/hooks/marketing/use-channels"

const SIZES = ["XS", "S", "M", "L", "XL"] as const
const CAMPAIGN_SUGGESTIONS = [
  "WENDY_креаторы", "AUDREY_креатор", "VUKI_креаторы",
  "MOON_креаторы", "RUBY_креаторы", "Яндекс промост",
]

interface Props { onClose: () => void }

export function AddWWPanel({ onClose }: Props) {
  const { data: modeli = [] } = useModeli()
  const { data: channels = [] } = useChannels()
  const createMut = useCreateSubstituteArticle()

  const [modelId, setModelId] = useState<number | null>(null)
  const [color, setColor] = useState("")
  const [size, setSize] = useState("")
  const [ww, setWw] = useState("")
  const [channel, setChannel] = useState("")
  const [campaign, setCampaign] = useState("")

  const { data: artikuly = [] } = useArtikulyForModel(modelId)

  // Available colors derived from artikuly list (distinct color codes)
  const availableColors = [...new Set(artikuly.map((a) => a.color).filter(Boolean))]

  const matchedArtikul = artikuly.find(
    (a) => a.color === color && a.size === size
  )

  const canSubmit = matchedArtikul && ww.trim() && channel.trim()

  const handleSubmit = async () => {
    if (!matchedArtikul) return
    await createMut.mutateAsync({
      code: ww.trim().toUpperCase(),
      artikul_id: matchedArtikul.id,
      purpose: channel,
      campaign_name: campaign || null,
      nomenklatura_wb: matchedArtikul.nm_id?.toString() ?? null,
    })
    onClose()
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
        <div className="text-sm font-medium text-stone-900">Новый WW-код</div>
        <button onClick={onClose} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="px-5 py-4 space-y-3 overflow-y-auto">
        <SelectMenu
          label="Модель"
          value={modelId?.toString() ?? ""}
          placeholder="Выбрать модель…"
          options={modeli.map((m) => ({ value: m.id.toString(), label: m.kod }))}
          onChange={(v) => {
            setModelId(v ? Number(v) : null)
            setColor("")
            setSize("")
          }}
        />
        {modelId && (
          <SelectMenu
            label="Цвет"
            value={color}
            placeholder="Выбрать цвет…"
            options={availableColors.map((c) => ({ value: c, label: c }))}
            onChange={(v) => { setColor(v); setSize("") }}
          />
        )}
        {color && (
          <SelectMenu
            label="Размер"
            value={size}
            placeholder="Выбрать размер…"
            options={SIZES.map((s) => ({ value: s, label: s }))}
            onChange={setSize}
          />
        )}
        {matchedArtikul && (
          <div className="bg-stone-50 rounded-md border border-stone-100 px-3 py-2">
            <div className="text-[10px] uppercase text-stone-400">Привязан</div>
            <div className="text-sm text-stone-900 mt-0.5">{matchedArtikul.artikul}</div>
            {matchedArtikul.nm_id && (
              <div className="text-[11px] font-mono text-stone-500">NM: {matchedArtikul.nm_id}</div>
            )}
          </div>
        )}
        {!matchedArtikul && modelId && color && size && (
          <div className="bg-amber-50 rounded-md border border-amber-200 px-3 py-2 text-[11px] text-amber-700">
            SKU не найден
          </div>
        )}
        <div>
          <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">WW-код</label>
          <Input
            className="font-mono uppercase"
            value={ww}
            placeholder="WW..."
            onChange={(e) => setWw(e.target.value)}
          />
        </div>
        <SelectMenu
          label="Канал"
          value={channel}
          placeholder="Выбрать канал…"
          options={channels.map((c) => ({ value: c.slug, label: c.label }))}
          onChange={setChannel}
          allowAdd
        />
        <SelectMenu
          label="Кампания / блогер"
          value={campaign}
          placeholder="Опционально…"
          options={CAMPAIGN_SUGGESTIONS}
          onChange={setCampaign}
          allowAdd
        />
        <Button disabled={!canSubmit || createMut.isPending} onClick={handleSubmit} className="w-full">
          {createMut.isPending ? "Создаю…" : "Добавить"}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify hooks support color/size lookups**

Open `wookiee-hub/src/hooks/marketing/use-artikuly.ts`. Confirm `useArtikulyForModel(modelId)` returns artikuly with `color`, `size`, `nm_id`, `artikul` fields. If not — extend the SELECT query.

- [ ] **Step 4: Smoke-test cascade**

Open `/marketing/search-queries`, click «+ Добавить WW-код». Step through: select model → color dropdown appears → select color → size dropdown appears → select size → SKU card with "Привязан" shows. Submit creates record visible in table.

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx
git commit -m "feat(marketing): align AddWWPanel cascade with v4 (Модель→Цвет→Размер→auto-SKU)"
```

---

### Wave A.4 — Configurable Grouping

### Task A.4.1: Extract ui-preferences helpers

**Files:**
- Create: `wookiee-hub/src/lib/ui-preferences.ts`
- Modify: `wookiee-hub/src/lib/catalog/service.ts` (re-export)
- Test: `wookiee-hub/src/lib/__tests__/ui-preferences.test.ts`

- [ ] **Step 1: Write failing test**

Create `wookiee-hub/src/lib/__tests__/ui-preferences.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock supabase before imports
vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: vi.fn(),
  },
}))

import { supabase } from '@/lib/supabase'
import { getUiPref, setUiPref } from '../ui-preferences'

describe('ui-preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getUiPref returns null when no record', async () => {
    ;(supabase.from as any).mockReturnValue({
      select: () => ({
        eq: () => ({
          eq: () => ({
            maybeSingle: () => Promise.resolve({ data: null, error: null }),
          }),
        }),
      }),
    })
    const v = await getUiPref<string>('test', 'k1')
    expect(v).toBe(null)
  })

  it('setUiPref upserts with onConflict', async () => {
    const upsertMock = vi.fn().mockResolvedValue({ error: null })
    ;(supabase.from as any).mockReturnValue({ upsert: upsertMock })
    await setUiPref('test', 'k1', 'value1')
    expect(upsertMock).toHaveBeenCalledWith(
      expect.objectContaining({ scope: 'test', key: 'k1', value: 'value1' }),
      { onConflict: 'scope,key' }
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd wookiee-hub && npx vitest run src/lib/__tests__/ui-preferences.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Create lib/ui-preferences.ts**

Create `wookiee-hub/src/lib/ui-preferences.ts`:
```ts
import { supabase } from "@/lib/supabase"

export async function getUiPref<T>(scope: string, key: string): Promise<T | null> {
  const { data, error } = await supabase
    .from("ui_preferences")
    .select("value")
    .eq("scope", scope)
    .eq("key", key)
    .maybeSingle()
  if (error) throw new Error(error.message)
  if (!data) return null
  return (data as { value: T | null }).value
}

export async function setUiPref(scope: string, key: string, value: unknown): Promise<void> {
  const { error } = await supabase
    .from("ui_preferences")
    .upsert(
      { scope, key, value, updated_at: new Date().toISOString() },
      { onConflict: "scope,key" }
    )
  if (error) throw new Error(error.message)
}
```

- [ ] **Step 4: Update catalog/service.ts to re-export from new location**

Open `wookiee-hub/src/lib/catalog/service.ts`. Find existing `getUiPref` (line ~2452) and `setUiPref` (line ~2465). Delete those two functions and add at the top of the file:
```ts
export { getUiPref, setUiPref } from "@/lib/ui-preferences"
```
This keeps backward compatibility — existing imports `from '@/lib/catalog/service'` continue to work.

- [ ] **Step 5: Run all tests to confirm no regressions**

Run: `cd wookiee-hub && npx vitest run src/lib/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/lib/ui-preferences.ts \
        wookiee-hub/src/lib/__tests__/ui-preferences.test.ts \
        wookiee-hub/src/lib/catalog/service.ts
git commit -m "refactor(catalog): extract getUiPref/setUiPref to lib/ui-preferences.ts"
```

### Task A.4.2: GroupBySelector for search-queries (3 presets)

**Files:**
- Create: `wookiee-hub/src/components/marketing/GroupBySelector.tsx`
- Create: `wookiee-hub/src/hooks/marketing/use-group-by-pref.ts`
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`
- Test: `wookiee-hub/src/components/marketing/__tests__/GroupBySelector.test.tsx`

- [ ] **Step 1: Write failing test for hook**

Create `wookiee-hub/src/hooks/marketing/__tests__/use-group-by-pref.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('@/lib/ui-preferences', () => ({
  getUiPref: vi.fn(),
  setUiPref: vi.fn().mockResolvedValue(undefined),
}))

import { getUiPref, setUiPref } from '@/lib/ui-preferences'
import { useGroupByPref } from '../use-group-by-pref'

describe('useGroupByPref', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('loads preference on mount and sets state', async () => {
    ;(getUiPref as any).mockResolvedValue('entity_type')
    const { result } = renderHook(() => useGroupByPref('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('entity_type'))
  })

  it('falls back to default when no pref', async () => {
    ;(getUiPref as any).mockResolvedValue(null)
    const { result } = renderHook(() => useGroupByPref('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('direction'))
  })

  it('persists on change', async () => {
    ;(getUiPref as any).mockResolvedValue('direction')
    const { result } = renderHook(() => useGroupByPref('marketing.search-queries', 'direction'))
    await waitFor(() => expect(result.current.value).toBe('direction'))
    result.current.setValue('none')
    await waitFor(() =>
      expect(setUiPref).toHaveBeenCalledWith('marketing.search-queries', 'groupBy', 'none')
    )
  })
})
```

- [ ] **Step 2: Run test (FAIL)**

Run: `cd wookiee-hub && npx vitest run src/hooks/marketing/__tests__/use-group-by-pref.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Create use-group-by-pref hook**

Create `wookiee-hub/src/hooks/marketing/use-group-by-pref.ts`:
```ts
import { useEffect, useRef, useState } from "react"
import { getUiPref, setUiPref } from "@/lib/ui-preferences"

export function useGroupByPref<T extends string>(scope: string, defaultValue: T) {
  const [value, setValueState] = useState<T>(defaultValue)
  const loadedRef = useRef(false)

  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    getUiPref<T>(scope, "groupBy")
      .then((v) => { if (v) setValueState(v) })
      .catch(() => { /* ignore — fallback to default */ })
  }, [scope])

  const setValue = (next: T) => {
    setValueState(next)
    setUiPref(scope, "groupBy", next).catch(() => { /* non-fatal */ })
  }

  return { value, setValue }
}
```

- [ ] **Step 4: Run hook test (PASS)**

Run: `cd wookiee-hub && npx vitest run src/hooks/marketing/__tests__/use-group-by-pref.test.tsx`
Expected: PASS, 3 tests.

- [ ] **Step 5: Create GroupBySelector component**

Create `wookiee-hub/src/components/marketing/GroupBySelector.tsx`:
```tsx
import { SelectMenu } from "./SelectMenu"

interface GroupByOption<T extends string> {
  value: T
  label: string
}

interface GroupBySelectorProps<T extends string> {
  value: T
  options: readonly GroupByOption<T>[]
  onChange: (v: T) => void
  label?: string
}

export function GroupBySelector<T extends string>({
  value,
  options,
  onChange,
  label = "Группировка",
}: GroupBySelectorProps<T>) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-stone-500">{label}:</span>
      <div className="w-[180px]">
        <SelectMenu
          value={value}
          options={options as { value: string; label: string }[]}
          onChange={(v) => onChange(v as T)}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Define GroupBy types and integrate into SearchQueriesTable**

Open `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`. Add at top:
```tsx
import { useMemo } from "react"
import { GroupBySelector } from "@/components/marketing/GroupBySelector"
import { useGroupByPref } from "@/hooks/marketing/use-group-by-pref"

type SqGroupBy = "direction" | "entity_type" | "none"

const SQ_GROUP_BY_OPTIONS = [
  { value: "direction" as const,   label: "По направлению" },
  { value: "entity_type" as const, label: "По типу сущности" },
  { value: "none" as const,        label: "Без группировки" },
] as const

const GROUP_LABELS_DIRECTION = {
  brand:       { icon: "🔤", label: "Брендированные запросы" },
  external:    { icon: "📦", label: "Артикулы (внешний лид)" },
  cr_general:  { icon: "👥", label: "Креаторы общие" },
  cr_personal: { icon: "👤", label: "Креаторы личные" },
} as const

const GROUP_LABELS_ENTITY = {
  brand:        { icon: "🔤", label: "Брендированные запросы" },
  nomenclature: { icon: "🏷️", label: "Номенклатуры" },
  ww_code:      { icon: "🔗", label: "Подменные артикулы" },
  other:        { icon: "❔", label: "Прочее" },
} as const
```

In the table component body, add grouping logic:
```tsx
const { value: groupBy, setValue: setGroupBy } = useGroupByPref<SqGroupBy>('marketing.search-queries', 'direction')

function getGroupKey(row: SearchQueryRow, mode: SqGroupBy): string {
  if (mode === "direction") return row.group_kind ?? "external"
  if (mode === "entity_type") return row.entity_type ?? "other"
  return "_all"
}

const grouped = useMemo(() => {
  if (groupBy === 'none') return [{ key: '_all', icon: '', label: '', items: filteredRows }]
  const map = new Map<string, SearchQueryRow[]>()
  for (const r of filteredRows) {
    const k = getGroupKey(r, groupBy)
    if (!map.has(k)) map.set(k, [])
    map.get(k)!.push(r)
  }
  const labelMap = groupBy === 'direction' ? GROUP_LABELS_DIRECTION : GROUP_LABELS_ENTITY
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b, 'ru'))
    .map(([key, items]) => {
      const meta = (labelMap as any)[key] ?? { icon: '', label: key }
      return { key, icon: meta.icon, label: meta.label, items }
    })
}, [filteredRows, groupBy])
```

Render in toolbar:
```tsx
<GroupBySelector value={groupBy} options={SQ_GROUP_BY_OPTIONS} onChange={setGroupBy} />
```

Update table body to render `grouped` with `SectionHeader` (passing `icon` and `label`).

- [ ] **Step 7: Smoke-test in browser**

Open `/marketing/search-queries`. Group dropdown shows 3 options. Default "По направлению" with 4 sections (icons 🔤/📦/👥/👤). Switch to "По типу сущности" — sections regroup into 3-4 entity buckets. Reload page — selection persists.

- [ ] **Step 8: Commit**

```bash
git add wookiee-hub/src/components/marketing/GroupBySelector.tsx \
        wookiee-hub/src/hooks/marketing/use-group-by-pref.ts \
        wookiee-hub/src/hooks/marketing/__tests__/use-group-by-pref.test.tsx \
        wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx
git commit -m "feat(marketing): GroupBySelector + 3 presets for search-queries (direction default)"
```

### Task A.4.3: GroupBySelector for promo-codes

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`

- [ ] **Step 1: Integrate GroupBySelector**

Open `PromoCodesTable.tsx`. Add at top:
```tsx
import { GroupBySelector } from "@/components/marketing/GroupBySelector"
import { useGroupByPref } from "@/hooks/marketing/use-group-by-pref"

type PromoGroupBy = "channel" | "status" | "none"

const PROMO_GROUP_BY_OPTIONS = [
  { value: "channel" as const, label: "По каналу" },
  { value: "status" as const,  label: "По статусу" },
  { value: "none" as const,    label: "Без группировки" },
] as const
```

In component body:
```tsx
const { value: groupBy, setValue: setGroupBy } = useGroupByPref<PromoGroupBy>('marketing.promo-codes', 'channel')

function getPromoGroupKey(p: PromoCodeRow, mode: PromoGroupBy): string {
  if (mode === 'channel') return p.channel ?? 'Без канала'
  if (mode === 'status') {
    if (p.status === 'unidentified') return 'Не идентифицирован'
    if (p.qty === 0) return 'Нет данных'
    return 'Активен'
  }
  return '_all'
}

const groupedPromos = useMemo(() => {
  if (groupBy === 'none') return [{ key: '_all', label: '', items: filteredPromos }]
  const map = new Map<string, PromoCodeRow[]>()
  for (const p of filteredPromos) {
    const k = getPromoGroupKey(p, groupBy)
    if (!map.has(k)) map.set(k, [])
    map.get(k)!.push(p)
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b, 'ru'))
    .map(([key, items]) => ({ key, label: key, items }))
}, [filteredPromos, groupBy])
```

In toolbar:
```tsx
<GroupBySelector value={groupBy} options={PROMO_GROUP_BY_OPTIONS} onChange={setGroupBy} />
```

Render table rows from `groupedPromos`. For each group, render `SectionHeader` (without icon prop — pass empty string).

- [ ] **Step 2: Smoke-test**

Open `/marketing/promo-codes`. Group dropdown shows 3 options. Default "По каналу" — sections by channel. Switch to "По статусу" — 3 sections (Активен / Нет данных / Не идентифицирован).

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx
git commit -m "feat(marketing): GroupBySelector for promo-codes (channel default)"
```

---

### Wave A.5 — Edit Flows

### Task A.5.1: useUpdatePromoCode mutation hook

**Files:**
- Modify: `wookiee-hub/src/api/marketing/promo-codes.ts` (add update function)
- Modify: `wookiee-hub/src/hooks/marketing/use-promo-codes.ts` (add mutation hook)

- [ ] **Step 1: Add updatePromoCode in API layer**

Open `wookiee-hub/src/api/marketing/promo-codes.ts`. Append:
```ts
export interface UpdatePromoCodeInput {
  id: number
  code?: string
  channel?: string
  discount_pct?: number | null
  valid_from?: string | null
  valid_until?: string | null
}

export async function updatePromoCode(input: UpdatePromoCodeInput) {
  const { id, ...rest } = input
  const patch: Record<string, unknown> = { updated_at: new Date().toISOString() }
  if (rest.code !== undefined)         patch.code = rest.code
  if (rest.channel !== undefined)      patch.channel = rest.channel
  if (rest.discount_pct !== undefined) patch.discount_pct = rest.discount_pct
  if (rest.valid_from !== undefined)   patch.valid_from = rest.valid_from
  if (rest.valid_until !== undefined)  patch.valid_until = rest.valid_until

  const { error } = await supabase.schema('crm').from('promo_codes').update(patch).eq('id', id)
  if (error) throw new Error(error.message)
}
```

- [ ] **Step 2: Add useUpdatePromoCode hook**

Open `wookiee-hub/src/hooks/marketing/use-promo-codes.ts`. Append:
```ts
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { updatePromoCode, type UpdatePromoCodeInput } from "@/api/marketing/promo-codes"

export function useUpdatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdatePromoCodeInput) => updatePromoCode(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['promo-codes'] })
    },
  })
}
```

- [ ] **Step 3: Verify compilation**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: no errors related to new code.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/api/marketing/promo-codes.ts \
        wookiee-hub/src/hooks/marketing/use-promo-codes.ts
git commit -m "feat(marketing): useUpdatePromoCode mutation hook"
```

### Task A.5.2: Edit-mode in PromoDetailPanel

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx`

- [ ] **Step 1: Replace contents with edit-mode-aware implementation**

Open `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx`. Replace with:
```tsx
import { useState, useMemo } from "react"
import { X, Edit3 } from "lucide-react"
import { Badge } from "@/components/marketing/Badge"
import { Input } from "@/components/marketing/Input"
import { Button } from "@/components/marketing/Button"
import { SelectMenu } from "@/components/marketing/SelectMenu"
import { useUpdatePromoCode } from "@/hooks/marketing/use-promo-codes"
import { useChannels } from "@/hooks/marketing/use-channels"
import type { PromoCodeRow } from "@/types/marketing"

interface Props {
  promo: PromoCodeRow
  onClose: () => void
}

const fmt = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("ru-RU")
const fmtR = (n: number | null | undefined) =>
  n == null ? "—" : `${n.toLocaleString("ru-RU")} ₽`

function computeStatusBadge(p: PromoCodeRow) {
  if (p.status === "unidentified") return { label: "Не идентиф.", color: "amber" as const }
  if ((p.qty ?? 0) === 0)          return { label: "Нет данных", color: "gray" as const }
  return { label: "Активен", color: "green" as const }
}

export function PromoDetailPanel({ promo, onClose }: Props) {
  const [isEdit, setIsEdit] = useState(false)
  const [form, setForm] = useState({
    code: promo.code,
    channel: promo.channel ?? "",
    discount_pct: promo.discount_pct?.toString() ?? "",
    valid_from: promo.valid_from ?? "",
    valid_until: promo.valid_until ?? "",
  })

  const { data: channels = [] } = useChannels()
  const updateMut = useUpdatePromoCode()
  const statusBadge = useMemo(() => computeStatusBadge(promo), [promo])
  const avg = promo.qty && promo.qty > 0 ? Math.round((promo.sales ?? 0) / promo.qty) : 0

  const handleSave = async () => {
    await updateMut.mutateAsync({
      id: promo.id,
      code: form.code,
      channel: form.channel || null,
      discount_pct: form.discount_pct ? Number(form.discount_pct) : null,
      valid_from: form.valid_from || null,
      valid_until: form.valid_until || null,
    })
    setIsEdit(false)
  }

  const handleCancel = () => {
    setForm({
      code: promo.code,
      channel: promo.channel ?? "",
      discount_pct: promo.discount_pct?.toString() ?? "",
      valid_from: promo.valid_from ?? "",
      valid_until: promo.valid_until ?? "",
    })
    setIsEdit(false)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start justify-between px-5 py-4 border-b border-stone-200">
        <div className="flex-1 min-w-0 mr-3">
          <div className="font-mono text-xs text-stone-400 mb-1 break-all">{promo.code}</div>
          <div className="flex items-center gap-1.5">
            <Badge color={statusBadge.color} label={statusBadge.label} />
            {promo.channel && (
              <span className="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 text-[11px] font-medium ring-1 ring-inset ring-stone-500/20">
                {promo.channel}
              </span>
            )}
          </div>
          {promo.external_uuid && (
            <div className="text-[10px] text-stone-400 mt-1 font-mono break-all">
              UUID: {promo.external_uuid}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {!isEdit && (
            <button
              onClick={() => setIsEdit(true)}
              className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100"
              aria-label="Edit"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          )}
          <button onClick={onClose} className="p-1.5 rounded-md text-stone-400 hover:bg-stone-100">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Edit/View fields */}
        <div className="px-5 py-4 border-b border-stone-200 space-y-3">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">Код</label>
            {isEdit ? (
              <Input
                className="font-mono uppercase"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              />
            ) : (
              <div className="font-mono text-xs text-stone-900 break-all">{form.code}</div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              {isEdit ? (
                <SelectMenu
                  label="Канал"
                  value={form.channel}
                  placeholder="Выбрать…"
                  options={channels.map((c) => ({ value: c.slug, label: c.label }))}
                  onChange={(v) => setForm((f) => ({ ...f, channel: v }))}
                  allowAdd
                />
              ) : (
                <div>
                  <div className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">Канал</div>
                  <div className="text-sm text-stone-900">{form.channel || "—"}</div>
                </div>
              )}
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">Скидка %</label>
              {isEdit ? (
                <Input
                  type="number"
                  value={form.discount_pct}
                  onChange={(e) => setForm((f) => ({ ...f, discount_pct: e.target.value }))}
                />
              ) : (
                <div className="text-sm tabular-nums text-stone-900">
                  {form.discount_pct ? `${form.discount_pct}%` : "—"}
                </div>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">Начало</label>
              {isEdit ? (
                <Input
                  type="date"
                  value={form.valid_from}
                  onChange={(e) => setForm((f) => ({ ...f, valid_from: e.target.value }))}
                />
              ) : (
                <div className="text-sm tabular-nums text-stone-900">{form.valid_from || "—"}</div>
              )}
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-stone-400 font-medium mb-1">Окончание</label>
              {isEdit ? (
                <Input
                  type="date"
                  value={form.valid_until}
                  onChange={(e) => setForm((f) => ({ ...f, valid_until: e.target.value }))}
                />
              ) : (
                <div className="text-sm tabular-nums text-stone-900">{form.valid_until || "—"}</div>
              )}
            </div>
          </div>
          {isEdit && (
            <div className="flex gap-2 pt-1">
              <Button onClick={handleSave} disabled={updateMut.isPending} className="flex-1">
                {updateMut.isPending ? "Сохраняю…" : "Сохранить"}
              </Button>
              <Button variant="secondary" onClick={handleCancel}>
                Отмена
              </Button>
            </div>
          )}
        </div>

        {/* KPI block */}
        <div className="px-5 py-4 border-b border-stone-200">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, шт</div>
              <div className="text-lg font-medium text-stone-900 tabular-nums">{fmt(promo.qty)}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Продажи, ₽</div>
              <div className="text-lg font-medium text-stone-900 tabular-nums">{fmtR(promo.sales)}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">Ср. чек, ₽</div>
              <div className="text-lg font-medium text-stone-900 tabular-nums">{avg > 0 ? fmtR(avg) : "—"}</div>
            </div>
          </div>
        </div>

        {/* Product breakdown — Task A.5.3 will fill this */}
        {/* Weekly stats — preserved from current implementation */}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify types**

Open `wookiee-hub/src/types/marketing.ts`. Ensure `PromoCodeRow` has `external_uuid` field. If not, add:
```ts
export interface PromoCodeRow {
  id: number
  code: string
  external_uuid: string | null
  channel: string | null
  discount_pct: number | null
  valid_from: string | null
  valid_until: string | null
  status: 'active' | 'unidentified'
  qty: number | null
  sales: number | null
  // ... preserve existing fields
}
```

- [ ] **Step 3: Smoke-test edit-flow**

Open `/marketing/promo-codes`. Click a promo. Click Edit3 (pencil) icon. Modify Discount %. Click Сохранить. Reload page — value persists.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx \
        wookiee-hub/src/types/marketing.ts
git commit -m "feat(marketing): edit-mode in PromoDetailPanel (Edit3 toggle + Save/Cancel)"
```

### Task A.5.3: Connect product-breakdown to PromoDetailPanel

**Files:**
- Modify: `wookiee-hub/src/api/marketing/promo-codes.ts` (add fetchProductBreakdown)
- Modify: `wookiee-hub/src/hooks/marketing/use-promo-codes.ts` (add hook)
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx`

- [ ] **Step 1: Add API function**

Open `wookiee-hub/src/api/marketing/promo-codes.ts`. Append:
```ts
export interface PromoProductBreakdownRow {
  id: number
  promo_code_id: number
  week_start: string
  artikul_id: number
  sku_label: string
  model_code: string | null
  qty: number
  amount_rub: number
}

export async function fetchPromoProductBreakdown(promoCodeId: number): Promise<PromoProductBreakdownRow[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('promo_product_breakdown')
    .select('*')
    .eq('promo_code_id', promoCodeId)
    .order('amount_rub', { ascending: false })
  if (error) throw new Error(error.message)
  return data as PromoProductBreakdownRow[]
}
```

- [ ] **Step 2: Add hook**

Open `wookiee-hub/src/hooks/marketing/use-promo-codes.ts`. Append:
```ts
import { useQuery } from "@tanstack/react-query"
import { fetchPromoProductBreakdown } from "@/api/marketing/promo-codes"

export function usePromoProductBreakdown(promoCodeId: number | null) {
  return useQuery({
    queryKey: ['promo-product-breakdown', promoCodeId],
    queryFn: () => fetchPromoProductBreakdown(promoCodeId!),
    enabled: promoCodeId != null,
  })
}
```

- [ ] **Step 3: Render breakdown in PromoDetailPanel**

Open `PromoDetailPanel.tsx`. Above the "Product breakdown — Task A.5.3 will fill this" comment, insert:
```tsx
import { usePromoProductBreakdown } from "@/hooks/marketing/use-promo-codes"

// Inside component:
const { data: breakdown = [], isLoading } = usePromoProductBreakdown(promo.id)

// Aggregate per artikul/sku
const aggregated = useMemo(() => {
  const map = new Map<number, { sku_label: string; model_code: string | null; qty: number; amount: number }>()
  for (const row of breakdown) {
    const cur = map.get(row.artikul_id)
    if (cur) {
      cur.qty += row.qty
      cur.amount += row.amount_rub
    } else {
      map.set(row.artikul_id, {
        sku_label: row.sku_label,
        model_code: row.model_code,
        qty: row.qty,
        amount: row.amount_rub,
      })
    }
  }
  return Array.from(map.values()).sort((a, b) => b.amount - a.amount)
}, [breakdown])
```

Replace the placeholder comment with:
```tsx
{aggregated.length > 0 && (
  <div className="px-5 py-4 border-b border-stone-200">
    <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">Товарная разбивка</div>
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-stone-100">
          <th className="text-left py-1 text-[10px] uppercase text-stone-400">Товар</th>
          <th className="text-right py-1 text-[10px] uppercase text-stone-400">Шт</th>
          <th className="text-right py-1 text-[10px] uppercase text-stone-400">Сумма</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-stone-50">
        {aggregated.map((p, i) => (
          <tr key={i}>
            <td className="py-1.5">
              <div className="text-stone-900">{p.sku_label}</div>
              <div className="text-[10px] text-stone-400">{p.model_code ?? "—"}</div>
            </td>
            <td className="py-1.5 text-right tabular-nums text-stone-700">{p.qty}</td>
            <td className="py-1.5 text-right tabular-nums text-stone-900 font-medium">{fmtR(p.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
{aggregated.length === 0 && !isLoading && (
  <div className="px-5 py-4 border-b border-stone-200">
    <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-2">Товарная разбивка</div>
    <p className="text-xs text-stone-400 italic">Данные собираются</p>
  </div>
)}
```

- [ ] **Step 4: Smoke-test**

Open `/marketing/promo-codes`. Click a promo with `qty > 0`. Detail panel shows "Товарная разбивка" with rows of SKU + qty + sum.

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/api/marketing/promo-codes.ts \
        wookiee-hub/src/hooks/marketing/use-promo-codes.ts \
        wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx
git commit -m "feat(marketing): connect product-breakdown to PromoDetailPanel"
```

### Task A.5.4: Wire StatusEditor mutation in SearchQueryDetailPanel

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`

- [ ] **Step 1: Wire mutation to StatusEditor**

Open `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`. Find the existing StatusEditor render. Update to use the existing mutation hook + status mapping:
```tsx
import { useUpdateSearchQueryStatus } from "@/hooks/marketing/use-search-queries"
import { STATUS_DB_TO_UI, type StatusUI } from "@/types/marketing"

// Inside component:
const statusMut = useUpdateSearchQueryStatus()

const handleStatusChange = (next: StatusUI) => {
  statusMut.mutate({
    source: item.source_table,
    id: item.source_id,
    statusUI: next,
  })
}

// In JSX:
<StatusEditor
  status={STATUS_DB_TO_UI[item.status]}
  onChange={handleStatusChange}
/>
```

Make sure `useUpdateSearchQueryStatus` in `use-search-queries.ts` accepts `statusUI` (the bidirectional mapping should already be in place from Task A.2.1).

- [ ] **Step 2: Add optimistic update + invalidation**

Open `wookiee-hub/src/hooks/marketing/use-search-queries.ts`. Find `useUpdateSearchQueryStatus`. Confirm/update it as:
```ts
export function useUpdateSearchQueryStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ source, id, statusUI }: { source: 'branded_queries' | 'substitute_articles'; id: number; statusUI: StatusUI }) =>
      updateSearchQueryStatus(source, id, statusUI),
    onMutate: async ({ source, id, statusUI }) => {
      await qc.cancelQueries({ queryKey: ['search-queries'] })
      const prev = qc.getQueryData<SearchQueryRow[]>(['search-queries'])
      qc.setQueryData<SearchQueryRow[]>(['search-queries'], (old) =>
        old?.map((r) =>
          r.source_table === source && r.source_id === id
            ? { ...r, status: STATUS_UI_TO_DB[statusUI] }
            : r
        )
      )
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(['search-queries'], ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['search-queries'] })
    },
  })
}
```

- [ ] **Step 3: Smoke-test**

Open `/marketing/search-queries`. Click a WW-code. In detail panel, click status badge → dropdown opens → select "Архив" → badge changes immediately. F5 — change persists.

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx \
        wookiee-hub/src/hooks/marketing/use-search-queries.ts
git commit -m "feat(marketing): wire StatusEditor mutation in SearchQueryDetailPanel (optimistic)"
```

---

### Wave A.6 — Detail Funnel Completeness

### Task A.6.1: Full funnel rendering in SearchQueryDetailPanel

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`

- [ ] **Step 1: Add funnel block**

In `SearchQueryDetailPanel.tsx`, locate where funnel/stats are rendered. Replace with v4-aligned 7-row funnel:
```tsx
const fmt = (n: number | null | undefined) => n == null ? '—' : n.toLocaleString('ru-RU')
const pct = (a: number, b: number) => b > 0 ? `${((a / b) * 100).toFixed(1)}%` : '—'

// Inside component, where the funnel section renders:
<div className="px-5 py-4 border-b border-stone-200">
  <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-3">За выбранный период</div>
  <div className="space-y-2">
    <div className="flex items-center justify-between">
      <span className="text-xs text-stone-500">Частота</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(stats.frequency)}</span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-stone-500">Переходы</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(stats.transitions)}</span>
    </div>
    <div className="flex items-center justify-between pl-4 -mt-0.5">
      <span className="text-[11px] text-stone-400">CR перех → корзина</span>
      <span className="text-[11px] text-stone-500 tabular-nums">{pct(stats.additions, stats.transitions)}</span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-stone-500">Корзина</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(stats.additions)}</span>
    </div>
    <div className="flex items-center justify-between pl-4 -mt-0.5">
      <span className="text-[11px] text-stone-400">CR корзина → заказ</span>
      <span className="text-[11px] text-stone-500 tabular-nums">{pct(stats.orders, stats.additions)}</span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-xs text-stone-500">Заказы</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{fmt(stats.orders)}</span>
    </div>
    <div className="pt-1 mt-1 border-t border-stone-100 flex items-center justify-between">
      <span className="text-xs font-medium text-stone-700">CR перех → заказ</span>
      <span className="text-sm font-medium text-stone-900 tabular-nums">{pct(stats.orders, stats.transitions)}</span>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Smoke-test**

Open `/marketing/search-queries`, click a row with stats > 0. Detail panel funnel shows 7 lines: Частота / Переходы / CR перех→корзина / Корзина / CR корзина→заказ / Заказы / итоговый CR перех→заказ (separated by border).

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx
git commit -m "feat(marketing): full funnel rendering in SearchQueryDetailPanel (7 rows + final CR)"
```

### Task A.6.2: Weekly stats toggle (period vs all) with empty state

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` (add fetchWeeklyForQuery)
- Modify: `wookiee-hub/src/hooks/marketing/use-search-queries.ts`

- [ ] **Step 1: Add API function**

Open `wookiee-hub/src/api/marketing/search-queries.ts`. Append:
```ts
export interface WeeklyStatsRow {
  week_start: string
  frequency: number
  open_card: number
  add_to_cart: number
  orders: number
}

export async function fetchWeeklyForQuery(searchWord: string): Promise<WeeklyStatsRow[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('search_queries_weekly')
    .select('week_start,frequency,open_card,add_to_cart,orders')
    .eq('search_word', searchWord)
    .order('week_start', { ascending: true })
  if (error) throw new Error(error.message)
  return data as WeeklyStatsRow[]
}
```

- [ ] **Step 2: Add hook**

Open `use-search-queries.ts`. Append:
```ts
export function useWeeklyStatsForQuery(searchWord: string | null) {
  return useQuery({
    queryKey: ['weekly-stats', searchWord],
    queryFn: () => fetchWeeklyForQuery(searchWord!),
    enabled: !!searchWord,
  })
}
```

- [ ] **Step 3: Render weekly table with toggle**

In `SearchQueryDetailPanel.tsx`, add below the funnel block:
```tsx
import { useState } from "react"
import { useWeeklyStatsForQuery } from "@/hooks/marketing/use-search-queries"

// Inside component:
const [showAll, setShowAll] = useState(false)
const { data: weekly = [] } = useWeeklyStatsForQuery(item.query_text)

const rangeWeeks = useMemo(
  () => weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo),
  [weekly, dateFrom, dateTo]
)
const slicedWeeks = showAll ? weekly : rangeWeeks

// JSX:
<div className="px-5 py-4">
  <div className="flex items-center justify-between mb-2">
    <div className="text-[11px] uppercase tracking-wider text-stone-400">
      {showAll ? 'Все недели' : 'За период'}
    </div>
    <button
      onClick={() => setShowAll((v) => !v)}
      className="text-[11px] text-stone-500 hover:text-stone-700 underline"
    >
      {showAll ? `За период (${rangeWeeks.length})` : `Все ${weekly.length}`}
    </button>
  </div>
  {slicedWeeks.length > 0 ? (
    <div className="overflow-y-auto max-h-[280px]">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-stone-50/90 backdrop-blur-sm">
          <tr className="border-b border-stone-200">
            <th className="px-1 py-1 text-left text-[10px] uppercase text-stone-400">Нед</th>
            <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Част.</th>
            <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Перех.</th>
            <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Корз.</th>
            <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">Зак.</th>
            <th className="px-1 py-1 text-right text-[10px] uppercase text-stone-400">CRV</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-50">
          {slicedWeeks.map((w, i) => (
            <tr key={i} className="hover:bg-stone-50/60">
              <td className="px-1 py-1 tabular-nums text-stone-500">
                {new Date(w.week_start).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}
              </td>
              <td className="px-1 py-1 text-right tabular-nums text-stone-600">{fmt(w.frequency)}</td>
              <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.open_card)}</td>
              <td className="px-1 py-1 text-right tabular-nums text-stone-500">{fmt(w.add_to_cart)}</td>
              <td className="px-1 py-1 text-right tabular-nums text-stone-900 font-medium">{fmt(w.orders)}</td>
              <td className="px-1 py-1 text-right tabular-nums text-stone-400">{pct(w.orders, w.open_card)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <div className="py-6 flex flex-col items-center gap-2">
      <p className="text-xs text-stone-400 italic">
        {item.entity_type === 'brand'
          ? 'Метрики появятся после Phase 2B'
          : 'Нет данных за этот период'}
      </p>
    </div>
  )}
</div>
```

- [ ] **Step 4: Smoke-test**

Open `/marketing/search-queries`. Click `Wendy/brown_S` WW-code (has many weeks). Detail panel shows weekly table with toggle. Click "Все N" — switches to full history. For a brand `wooki` (which currently has no metrics from `search_queries_weekly`, until B.0.2 RPC update), empty state shows "Метрики появятся после Phase 2B".

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx \
        wookiee-hub/src/api/marketing/search-queries.ts \
        wookiee-hub/src/hooks/marketing/use-search-queries.ts
git commit -m "feat(marketing): weekly stats toggle (period vs all) with empty state for brands"
```

---

### Wave A.7 — Tests Cleanup

### Task A.7: Update test suite after refactor

**Files:**
- Modify: `wookiee-hub/src/components/marketing/__tests__/SelectMenu.test.tsx` (if breaks)
- Modify: `wookiee-hub/src/components/marketing/__tests__/SectionHeader.test.tsx` (already done in A.3.2)

- [ ] **Step 1: Run full marketing test suite**

Run: `cd wookiee-hub && npx vitest run src/components/marketing src/types/__tests__ src/hooks/marketing src/lib/__tests__`
Expected: all PASS or failures with clear messages.

- [ ] **Step 2: Fix any breakages**

For each failing test:
- Read the failure message.
- Update test setup to match new component signatures (e.g., SectionHeader now takes `icon` instead of `group` object).
- Re-run.

- [ ] **Step 3: Run full app test suite**

Run: `cd wookiee-hub && npm test`
Expected: PASS overall (any pre-existing failures noted in writeup).

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/marketing/__tests__/
git commit -m "test(marketing): update SectionHeader + SelectMenu tests after refactor"
```

---

## Phase 2A Pull Request

### Task A.PR: Create Pull Request for Phase 2A

- [ ] **Step 1: Push branch**

```bash
git push -u origin feature/marketing-v4-fidelity
```

- [ ] **Step 2: Create PR via gh CLI**

Run:
```bash
gh pr create --base main --title "feat(marketing): Phase 2A — v4 fidelity frontend (visual + CRUD)" --body "$(cat <<'EOF'
## Summary

Phase 2A of marketing v4 fidelity refactor. Brings `/marketing/{promo-codes,search-queries}` to pixel-perfect match with `wookiee_marketing_v4.jsx` prototype.

Implemented from design: `docs/superpowers/specs/2026-05-12-marketing-v4-fidelity-design.md`

## Changes

- New `MarketingLayout` with sub-sidebar and `data-section="marketing"` scope
- Stone palette via CSS-variable override (no global change)
- Local Badge/Button/Input components (decoupled from CRM)
- Instrument Serif italic 24px page headers
- Bidirectional UI↔DB status mapping (no enum migration)
- Split-pane detail panel with responsive `lg:` fallback to drawer
- Configurable grouping (3 presets) via `ui_preferences`
- PromoDetailPanel edit-mode with `external_uuid` read-only
- Connected `marketing.promo_product_breakdown` to UI
- Full 7-row funnel in SearchQueryDetailPanel
- Weekly stats toggle with empty state for brands

## Test plan

- [ ] Visual smoke check `/marketing/search-queries` — sub-sidebar, italic header, 4 groups with 🔤/📦/👥/👤 icons
- [ ] Switch grouping dropdown — sections regroup, F5 persists choice
- [ ] Click WW-code → detail panel shows funnel + status dropdown works
- [ ] Add WW-code via cascade form
- [ ] `/marketing/promo-codes` — edit mode toggles, save persists
- [ ] Товарная разбивка renders for promo with sales
- [ ] Resize browser to < 1024px — drawer fallback works
- [ ] `/catalog` and `/influence` visually unchanged
- [ ] `npm test` passes
EOF
)"
```

- [ ] **Step 3: Wait for review and merge**

After review/approval, merge via squash or merge commit per project convention.

---

## Phase 2B — Backend & Sync Bridge

### Wave B.0 — SQL Migrations

### Task B.0.1: View v2 — additive update with entity_type / channel_label / sku_label

**Files:**
- Create: `database/marketing/views/2026-05-13-search-queries-unified-v2.sql`

- [ ] **Step 1: Create migration file**

Create `database/marketing/views/2026-05-13-search-queries-unified-v2.sql`:
```sql
-- search_queries_unified v2 — additive update of v1 (2026-05-09)
-- New columns: entity_type, channel_label, sku_label
-- Improved: model_hint via modeli_osnova JOIN
-- Preserved: source_id, source_table, group_kind, query_text, artikul_id,
--   nomenklatura_wb, ww_code, campaign_name, purpose, creator_ref, status,
--   created_at, updated_at, security_invoker, GRANTs

CREATE OR REPLACE VIEW marketing.search_queries_unified
WITH (security_invoker = true)
AS
SELECT
  ('B' || bq.id::text)::text                AS unified_id,
  bq.id                                     AS source_id,
  'branded_queries'::text                   AS source_table,
  'brand'::text                             AS entity_type,
  'brand'::text                             AS group_kind,
  bq.query                                  AS query_text,
  NULL::int                                 AS artikul_id,
  NULL::text                                AS nomenklatura_wb,
  NULL::text                                AS ww_code,
  NULL::text                                AS campaign_name,
  NULL::text                                AS purpose,
  COALESCE(
    (SELECT m.kod FROM public.modeli_osnova m WHERE m.id = bq.model_osnova_id),
    bq.canonical_brand
  )                                         AS model_hint,
  NULL::text                                AS sku_label,
  NULL::text                                AS creator_ref,
  (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = 'brand') AS channel_label,
  bq.status                                 AS status,
  bq.created_at                             AS created_at,
  NULL::timestamptz                         AS updated_at
FROM crm.branded_queries bq
UNION ALL
SELECT
  ('S' || sa.id::text)::text                AS unified_id,
  sa.id                                     AS source_id,
  'substitute_articles'::text               AS source_table,
  CASE
    WHEN sa.code LIKE 'WW%'      THEN 'ww_code'
    WHEN sa.code ~ '^[0-9]+$'    THEN 'nomenclature'
    ELSE                              'other'
  END                                       AS entity_type,
  CASE
    WHEN sa.purpose = 'creators' AND sa.campaign_name ~* '^креатор[_ ]' THEN 'cr_personal'
    WHEN sa.purpose = 'creators'                                        THEN 'cr_general'
    ELSE                                                                     'external'
  END                                       AS group_kind,
  sa.code                                   AS query_text,
  sa.artikul_id                             AS artikul_id,
  sa.nomenklatura_wb                        AS nomenklatura_wb,
  CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END AS ww_code,
  sa.campaign_name                          AS campaign_name,
  sa.purpose                                AS purpose,
  (SELECT m.kod FROM public.modeli_osnova m WHERE m.id =
    (SELECT a.model_osnova_id FROM public.artikuly a WHERE a.id = sa.artikul_id)) AS model_hint,
  (SELECT a.artikul FROM public.artikuly a WHERE a.id = sa.artikul_id) AS sku_label,
  sa.creator_ref                            AS creator_ref,
  (SELECT ch.label FROM marketing.channels ch WHERE ch.slug = sa.purpose) AS channel_label,
  sa.status                                 AS status,
  sa.created_at                             AS created_at,
  sa.updated_at                             AS updated_at
FROM crm.substitute_articles sa;

GRANT SELECT ON marketing.search_queries_unified TO authenticated, service_role;

COMMENT ON VIEW marketing.search_queries_unified IS
  'v2 (2026-05-13): adds entity_type/channel_label/sku_label, improves model_hint via modeli_osnova JOIN. Backward-compatible additive update of v1.';
```

- [ ] **Step 2: Apply migration to Supabase**

Run:
```bash
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-13-search-queries-unified-v2.sql
```
Expected: `CREATE VIEW` + `GRANT` + `COMMENT` confirmations.

- [ ] **Step 3: Verify new columns work**

Run:
```bash
psql "$SUPABASE_DB_URL" -c "SELECT unified_id, entity_type, channel_label, sku_label, model_hint FROM marketing.search_queries_unified LIMIT 10;"
```
Expected: rows with `entity_type` ∈ {brand, nomenclature, ww_code, other}, `channel_label` showing labels like «Бренд» / «Яндекс» / «Креаторы», `sku_label` populated for substitute_articles rows, `model_hint` showing kod from modeli_osnova.

- [ ] **Step 4: Confirm existing fields preserved**

Run:
```bash
psql "$SUPABASE_DB_URL" -c "SELECT source_id, source_table, group_kind, status FROM marketing.search_queries_unified LIMIT 5;"
```
Expected: existing fields work — frontend reading the view continues to function.

- [ ] **Step 5: Commit**

```bash
git add database/marketing/views/2026-05-13-search-queries-unified-v2.sql
git commit -m "feat(marketing-db): update search_queries_unified view with entity_type + channel_label + sku_label (additive)"
```

### Task B.0.2: RPC v2 — JOIN marketing.search_queries_weekly

**Files:**
- Create: `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql`

- [ ] **Step 1: Create migration file**

Create `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql`:
```sql
-- search_query_stats_aggregated v2 — JOIN on marketing.search_queries_weekly by search_word
-- Closes the "brands with zeros" bug: brands now get real metrics from the unified
-- weekly table (1396 rows after bootstrap 2026-05-12).

CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(p_from DATE, p_to DATE)
RETURNS TABLE (
  unified_id   TEXT,
  frequency    BIGINT,
  transitions  BIGINT,
  additions    BIGINT,
  orders       BIGINT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    u.unified_id,
    COALESCE(SUM(w.frequency),   0)::bigint AS frequency,
    COALESCE(SUM(w.open_card),   0)::bigint AS transitions,
    COALESCE(SUM(w.add_to_cart), 0)::bigint AS additions,
    COALESCE(SUM(w.orders),      0)::bigint AS orders
  FROM marketing.search_queries_unified u
  LEFT JOIN marketing.search_queries_weekly w
    ON  w.search_word = u.query_text
    AND w.week_start BETWEEN p_from AND p_to
  GROUP BY u.unified_id;
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) TO authenticated, service_role;

COMMENT ON FUNCTION marketing.search_query_stats_aggregated(DATE, DATE) IS
  'v2 (2026-05-13): JOIN on marketing.search_queries_weekly by search_word. Returns metrics for ALL entity types including brands.';
```

- [ ] **Step 2: Apply migration**

```bash
psql "$SUPABASE_DB_URL" -f database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql
```

- [ ] **Step 3: Verify brands now have non-zero metrics**

Run:
```bash
psql "$SUPABASE_DB_URL" -c "
WITH agg AS (
  SELECT * FROM marketing.search_query_stats_aggregated('2026-02-01'::date, '2026-04-27'::date)
)
SELECT u.unified_id, u.entity_type, u.query_text, a.frequency, a.transitions, a.orders
FROM marketing.search_queries_unified u
LEFT JOIN agg a ON a.unified_id = u.unified_id
WHERE u.entity_type = 'brand'
ORDER BY a.orders DESC NULLS LAST
LIMIT 10;"
```
Expected: brand rows (e.g. `wooki`, `Wendy`, `Audrey`) show non-zero frequency/transitions/orders.

- [ ] **Step 4: Commit**

```bash
git add database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql
git commit -m "feat(marketing-db): rewrite search_query_stats_aggregated RPC to JOIN marketing.search_queries_weekly"
```

### Task B.0.3: Seed 'ooo' channel

**Files:**
- Create: `database/marketing/migrations/2026-05-13-add-ooo-channel.sql`

- [ ] **Step 1: Create seed migration**

Create `database/marketing/migrations/2026-05-13-add-ooo-channel.sql`:
```sql
-- Add 'ooo' channel for promo codes per v4 PROMO_CH list (was missing from initial seed)
INSERT INTO marketing.channels (slug, label) VALUES ('ooo', 'ООО') ON CONFLICT (slug) DO NOTHING;
```

- [ ] **Step 2: Apply migration**

```bash
psql "$SUPABASE_DB_URL" -f database/marketing/migrations/2026-05-13-add-ooo-channel.sql
psql "$SUPABASE_DB_URL" -c "SELECT slug, label FROM marketing.channels WHERE slug='ooo';"
```
Expected: 1 row with `ooo | ООО`.

- [ ] **Step 3: Commit**

```bash
git add database/marketing/migrations/2026-05-13-add-ooo-channel.sql
git commit -m "feat(marketing-db): seed marketing.channels with 'ooo' label"
```

---

### Wave B.1 — Sync Bridge

### Task B.1.1: search-queries sync bridge (DB → Sheets col A)

**Files:**
- Modify: `services/sheets_sync/sync/sync_search_queries.py`
- Create: `services/sheets_sync/sync/search_queries/bridge.py`
- Test: `tests/services/sheets_sync/test_search_queries_bridge.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/sheets_sync/__init__.py` (empty file) if not exists.

Create `tests/services/sheets_sync/test_search_queries_bridge.py`:
```python
"""Tests for DB→Sheets bridge in search-queries sync."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from services.sheets_sync.sync.search_queries.bridge import (
    parse_section_dividers, plan_inserts
)


def test_parse_section_dividers_finds_known_markers():
    col_a = [
        "Аналитика по запросам",  # row 1
        "",                       # row 2 (dates)
        "wooki",                  # row 3
        "Вуки",                   # row 4
        "Артикулы внешний лид",   # row 29 marker
        "163151603",              # row 30
        "Креаторы общие:",        # row 54 marker
        "WW121749",               # row 55
        "Креаторы личные:",       # row 74 marker
        "WW113490",               # row 75
        "Соцсети:",               # row 97 marker
        "WW140475",               # row 98
    ]
    sections = parse_section_dividers(col_a)
    assert sections['brand_end'] == 5     # last branded row at idx 4 → row 5 (1-indexed +1)
    assert sections['external_end'] == 7
    assert sections['cr_general_end'] == 9
    assert sections['cr_personal_end'] == 11
    assert sections['social_end'] == 13


def test_plan_inserts_skips_existing():
    sheet_words = {"wooki", "163151603", "WW121749"}
    db_words = [
        ("wooki", "brand"),          # exists — skip
        ("Audrey", "brand"),         # new
        ("WW999999", "creators"),    # new
        ("163151603", "yandex"),     # exists — skip
    ]
    sections = {
        'brand_end': 5,
        'external_end': 7,
        'cr_general_end': 9,
        'cr_personal_end': 11,
        'social_end': 13,
    }
    inserts = plan_inserts(db_words, sheet_words, sections)
    # Two inserts; campaign_name not given so creators → cr_general section
    assert len(inserts) == 2
    assert ("Audrey", 5) in inserts          # at end of brand section
    assert ("WW999999", 9) in inserts        # at end of cr_general section


def test_plan_inserts_routes_personal_creator_by_campaign():
    sheet_words = set()
    db_words = [
        ("WW113490", "creators", "креатор_Шматов"),
    ]
    sections = {'brand_end': 3, 'external_end': 5, 'cr_general_end': 7, 'cr_personal_end': 9, 'social_end': 11}
    inserts = plan_inserts(db_words, sheet_words, sections)
    assert inserts == [("WW113490", 9)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Projects/Wookiee && python -m pytest tests/services/sheets_sync/test_search_queries_bridge.py -v`
Expected: FAIL — module `bridge` does not exist.

- [ ] **Step 3: Create bridge module**

Create `services/sheets_sync/sync/search_queries/bridge.py`:
```python
"""DB→Sheets bridge for search-queries sync.

Before pulling metrics from WB API, ensure all words from `crm.branded_queries`
and `crm.substitute_articles` are present in Sheets col A in the correct section.

Section dividers in Sheets:
- "Артикулы внешний лид"  → external section (purpose != 'creators', numeric code)
- "Креаторы общие:"       → cr_general (purpose='creators', campaign_name NOT 'креатор_*')
- "Креаторы личные:"      → cr_personal (purpose='creators', campaign_name LIKE 'креатор_*')
- "Соцсети:"              → social (purpose='social')
- (implicit top section)  → brand (from branded_queries; no divider)
"""
from __future__ import annotations
import logging
import re
from typing import Iterable

logger = logging.getLogger(__name__)

SECTION_MARKERS = {
    "Артикулы внешний лид": "external_end",
    "Креаторы общие:":      "cr_general_end",
    "Креаторы личные:":     "cr_personal_end",
    "Соцсети:":             "social_end",
}

CREATOR_PERSONAL_RE = re.compile(r'^креатор[_ ]', re.IGNORECASE)


def parse_section_dividers(col_a: list[str]) -> dict[str, int]:
    """Return {section_end_key: insert_row (1-indexed)} for each section.

    The insert row is one past the last data row of that section, i.e. where
    the next new word for that section should land.

    Defaults assume all 4 markers present. If a marker is missing, that section's
    insert row defaults to len(col_a)+1 (append to bottom).
    """
    result: dict[str, int] = {}
    # 1-indexed Sheets rows (col_a[0] = row 1)
    markers_found: dict[str, int] = {}
    for idx, val in enumerate(col_a):
        text = (val or "").strip()
        if text in SECTION_MARKERS:
            markers_found[SECTION_MARKERS[text]] = idx + 1  # row of marker itself

    fallback = len(col_a) + 1

    # brand section: 0..external_marker_row-1; insert before external_end marker
    if "external_end" in markers_found:
        result["brand_end"] = markers_found["external_end"]
    else:
        result["brand_end"] = fallback

    # external: rows between external marker and cr_general marker
    if "external_end" in markers_found and "cr_general_end" in markers_found:
        result["external_end"] = markers_found["cr_general_end"]
    else:
        result["external_end"] = fallback

    if "cr_general_end" in markers_found and "cr_personal_end" in markers_found:
        result["cr_general_end"] = markers_found["cr_personal_end"]
    else:
        result["cr_general_end"] = fallback

    if "cr_personal_end" in markers_found and "social_end" in markers_found:
        result["cr_personal_end"] = markers_found["social_end"]
    else:
        result["cr_personal_end"] = fallback

    result["social_end"] = fallback  # social = bottom

    return result


def _route_word(word: str, purpose: str, campaign_name: str | None, sections: dict[str, int]) -> int:
    """Decide which row to insert a DB word at, based on its purpose+campaign.

    Returns 1-indexed Sheets row.
    """
    if not purpose:
        # No purpose → likely brand (from branded_queries)
        return sections["brand_end"]

    p = purpose.lower()
    if p == "brand":
        return sections["brand_end"]
    if p == "creators":
        if campaign_name and CREATOR_PERSONAL_RE.match(campaign_name):
            return sections["cr_personal_end"]
        return sections["cr_general_end"]
    if p == "social":
        return sections["social_end"]
    # yandex, vk_target, adblogger, other → external
    return sections["external_end"]


def plan_inserts(
    db_words: Iterable[tuple],
    sheet_words: set[str],
    sections: dict[str, int],
) -> list[tuple[str, int]]:
    """Build list of (word, target_row) tuples to insert.

    Each db_words entry: (word, purpose) or (word, purpose, campaign_name).
    Words already in sheet_words are skipped.
    """
    inserts: list[tuple[str, int]] = []
    for entry in db_words:
        if len(entry) == 2:
            word, purpose = entry
            campaign = None
        else:
            word, purpose, campaign = entry[:3]
        if word in sheet_words:
            continue
        row = _route_word(word, purpose or "", campaign, sections)
        inserts.append((word, row))
    return inserts


def fetch_db_words(supabase) -> list[tuple]:
    """SELECT all words from crm.branded_queries + crm.substitute_articles.

    Returns list of (word, purpose, campaign_name) tuples.
    """
    rows: list[tuple] = []
    # Branded queries — purpose hardcoded as 'brand'
    bq = (
        supabase.schema("crm").table("branded_queries")
        .select("query")
        .execute()
    )
    for r in bq.data or []:
        rows.append((r["query"], "brand", None))

    sa = (
        supabase.schema("crm").table("substitute_articles")
        .select("code, purpose, campaign_name")
        .execute()
    )
    for r in sa.data or []:
        rows.append((r["code"], r["purpose"], r.get("campaign_name")))
    return rows


def ensure_db_words_in_sheets(ws, supabase) -> int:
    """Main entrypoint. Reads DB + Sheets, inserts missing words in correct sections.

    Returns count of inserted rows.
    """
    col_a = ws.col_values(1)
    sheet_words = set((c or "").strip() for c in col_a[2:] if c)  # skip header rows 1-2
    sections = parse_section_dividers(col_a)
    db_words = fetch_db_words(supabase)
    inserts = plan_inserts(db_words, sheet_words, sections)

    if not inserts:
        logger.info("Bridge: no new words to insert")
        return 0

    # Insert rows in descending order to preserve row numbers as we go
    inserts_sorted = sorted(inserts, key=lambda x: -x[1])
    for word, target_row in inserts_sorted:
        ws.insert_row([word], target_row)

    logger.info("Bridge: inserted %d new words into Sheets", len(inserts))
    return len(inserts)
```

Also create empty `services/sheets_sync/sync/search_queries/__init__.py` if not exists.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest tests/services/sheets_sync/test_search_queries_bridge.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Wire bridge into sync_search_queries.py**

Open `services/sheets_sync/sync/sync_search_queries.py`. Add import at top:
```python
from .search_queries.bridge import ensure_db_words_in_sheets
from shared.data_layer import get_supabase_client  # or whatever the existing import is
```

Find the `sync()` function. Inside `_sync_search_words` or directly in `sync()`, before the existing `col_a = ws.col_values(1)` line, add:
```python
# Bridge: ensure DB-added words are present in Sheets before WB API pull
supabase = get_supabase_client()
inserted = ensure_db_words_in_sheets(ws, supabase)
if inserted:
    logger.info("Bridge added %d words to Sheets, refreshing col_a", inserted)
```

- [ ] **Step 6: Smoke-test against staging**

Run (with test data — add 1 row to `crm.substitute_articles` first, then):
```bash
python scripts/run_search_queries_sync.py --mode specific --from 2026-05-05 --to 2026-05-11
```
Expected log: `Bridge: inserted N new words into Sheets`. Manually open the Google Sheet — new row appears in correct section.

- [ ] **Step 7: Commit**

```bash
git add services/sheets_sync/sync/search_queries/bridge.py \
        services/sheets_sync/sync/search_queries/__init__.py \
        services/sheets_sync/sync/sync_search_queries.py \
        tests/services/sheets_sync/test_search_queries_bridge.py \
        tests/services/sheets_sync/__init__.py
git commit -m "feat(search-queries-sync): bridge crm tables → sheets col A before WB pull (section-aware)"
```

### Task B.1.2: promocodes sync bridge

**Files:**
- Modify: `services/sheets_sync/sync/sync_promocodes.py`
- Modify: `services/sheets_sync/sync/promocodes/dictionary.py` (or create bridge module)
- Test: `tests/services/sheets_sync/test_promocodes_bridge.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/sheets_sync/test_promocodes_bridge.py`:
```python
from __future__ import annotations
from services.sheets_sync.sync.promocodes.bridge import plan_promo_inserts


def test_plan_promo_inserts_skips_known_uuids():
    sheet_uuids = {"aaa-bbb-ccc", "ddd-eee-fff"}
    db_promos = [
        {"external_uuid": "aaa-bbb-ccc", "code": "CHARLOTTE10", "channel": "social", "discount_pct": 10},
        {"external_uuid": "zzz-yyy-xxx", "code": "NEW_PROMO",   "channel": "blogger", "discount_pct": 5},
        {"external_uuid": None,          "code": "NO_UUID",     "channel": "corp",    "discount_pct": 25},
    ]
    inserts = plan_promo_inserts(db_promos, sheet_uuids)
    # Only the 'zzz-yyy-xxx' row is new + has uuid
    assert len(inserts) == 1
    assert inserts[0]["external_uuid"] == "zzz-yyy-xxx"
    assert inserts[0]["code"] == "NEW_PROMO"
```

- [ ] **Step 2: Run test (FAIL)**

Run: `python -m pytest tests/services/sheets_sync/test_promocodes_bridge.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create bridge module**

Create `services/sheets_sync/sync/promocodes/bridge.py`:
```python
"""DB→Sheets bridge for wb-promocodes sync.

Before reading dictionary from Sheets and pulling WB API metrics, ensure all
promo codes from `crm.promo_codes` with non-null `external_uuid` are present
in the dictionary section of the main Sheets tab.
"""
from __future__ import annotations
import logging
from typing import Iterable

logger = logging.getLogger(__name__)


def plan_promo_inserts(
    db_promos: Iterable[dict],
    sheet_uuids: set[str],
) -> list[dict]:
    """Filter db_promos to only those with non-null external_uuid not yet in Sheets.

    Returns list of dicts ready for batch insert into dictionary section.
    """
    inserts: list[dict] = []
    for p in db_promos:
        uuid = p.get("external_uuid")
        if not uuid:
            continue  # no UUID → can't match to WB API row
        if uuid.lower() in {u.lower() for u in sheet_uuids}:
            continue
        inserts.append({
            "external_uuid": uuid,
            "code": p.get("code", ""),
            "channel": p.get("channel", ""),
            "discount_pct": p.get("discount_pct"),
        })
    return inserts


def ensure_db_promos_in_sheets(ws_dict, supabase) -> int:
    """Read DB promo_codes, add missing UUIDs to dictionary sheet section.

    Returns count of inserted rows.
    """
    # Find UUID column index in dictionary header
    rows = ws_dict.get_all_values()
    if not rows:
        logger.warning("Dictionary sheet empty, skipping bridge")
        return 0

    header = [(c or "").strip().lower() for c in rows[0]]
    try:
        uuid_idx = header.index("uuid")
    except ValueError:
        logger.warning("Dictionary header has no UUID column, skipping bridge")
        return 0

    sheet_uuids = set()
    for r in rows[1:]:
        if uuid_idx < len(r) and r[uuid_idx]:
            sheet_uuids.add(r[uuid_idx].strip())

    db_promos = (
        supabase.schema("crm").table("promo_codes")
        .select("external_uuid, code, channel, discount_pct")
        .execute()
    ).data or []

    inserts = plan_promo_inserts(db_promos, sheet_uuids)
    if not inserts:
        logger.info("Promo bridge: no new UUIDs to insert")
        return 0

    # Append at bottom of dictionary section
    for promo in inserts:
        # Build row matching header order — simplified: UUID, name, channel, discount%
        ws_dict.append_row([
            promo["external_uuid"],
            promo.get("code", ""),
            promo.get("channel", ""),
            promo.get("discount_pct") or "",
        ])

    logger.info("Promo bridge: inserted %d UUIDs into Sheets dictionary", len(inserts))
    return len(inserts)
```

Ensure `services/sheets_sync/sync/promocodes/__init__.py` exists (likely already does — confirm with `ls`).

- [ ] **Step 4: Run test (PASS)**

Run: `python -m pytest tests/services/sheets_sync/test_promocodes_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Wire into sync_promocodes.py**

Open `services/sheets_sync/sync/sync_promocodes.py`. Find where the dictionary sheet is read (around `read_dictionary_sheet` call near line 136). Before that call, add:
```python
from .promocodes.bridge import ensure_db_promos_in_sheets
from shared.data_layer import get_supabase_client

# Inside run():
ws_main = ...  # existing reference to the main pivot tab where dictionary lives
supabase = get_supabase_client()
inserted = ensure_db_promos_in_sheets(ws_main, supabase)
if inserted:
    logger.info("Promo bridge added %d codes; dictionary will be re-read", inserted)
```

- [ ] **Step 6: Smoke-test**

Insert a test row in `crm.promo_codes` with a fake external_uuid. Run:
```bash
python scripts/run_wb_promocodes_sync.py --mode specific --from 2026-05-05 --to 2026-05-11
```
Expected: log `Promo bridge: inserted 1 UUIDs`. Manually verify dictionary row in Sheets.

- [ ] **Step 7: Commit**

```bash
git add services/sheets_sync/sync/promocodes/bridge.py \
        services/sheets_sync/sync/sync_promocodes.py \
        tests/services/sheets_sync/test_promocodes_bridge.py
git commit -m "feat(promocodes-sync): bridge crm.promo_codes → dictionary sheet (UUID-based dedup)"
```

---

### Wave B.2 — Sync API + UI Wiring

### Task B.2.1: analytics_api sync endpoints

**Files:**
- Create: `services/analytics_api/marketing.py`
- Modify: `services/analytics_api/app.py` (register router + extend CORS methods)
- Test: `tests/services/analytics_api/test_marketing_sync.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/analytics_api/__init__.py` if missing.

Create `tests/services/analytics_api/test_marketing_sync.py`:
```python
"""Tests for /api/marketing/sync endpoints."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from services.analytics_api.app import app


client = TestClient(app)


def test_trigger_sync_unknown_job_returns_404():
    r = client.post("/api/marketing/sync/unknown-job", headers={"X-API-Key": "test"})
    assert r.status_code in (401, 404)  # 401 if auth fires first


def test_status_returns_404_for_unknown_job():
    r = client.get("/api/marketing/sync/unknown-job/status", headers={"X-API-Key": "test"})
    assert r.status_code in (401, 404)


@patch("services.analytics_api.marketing.create_sync_log_entry", return_value=42)
@patch("services.analytics_api.marketing.run_sync_subprocess")
@patch.dict("os.environ", {"ANALYTICS_API_KEY": "test"})
def test_trigger_sync_creates_log_and_returns_running(mock_run, mock_create):
    r = client.post(
        "/api/marketing/sync/search-queries",
        headers={"X-API-Key": "test"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["job_name"] == "search-queries"
    assert body["status"] == "running"
    assert body["sync_log_id"] == 42
```

- [ ] **Step 2: Run test (FAIL)**

Run: `python -m pytest tests/services/analytics_api/test_marketing_sync.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Create marketing.py router**

Create `services/analytics_api/marketing.py`:
```python
"""Marketing sync trigger endpoints.

POST /api/marketing/sync/{job_name}        — start sync subprocess in background
GET  /api/marketing/sync/{job_name}/status — read latest marketing.sync_log row
"""
from __future__ import annotations
import asyncio
import logging
import os
import subprocess
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from supabase import Client, create_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketing", tags=["marketing"])

JOB_SCRIPTS = {
    "search-queries": "scripts/run_search_queries_sync.py",
    "promocodes":     "scripts/run_wb_promocodes_sync.py",
}

ANALYTICS_API_KEY = os.getenv("ANALYTICS_API_KEY", "")


def _get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase env not configured")
    return create_client(url, key)


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if not ANALYTICS_API_KEY:
        raise HTTPException(500, "ANALYTICS_API_KEY not set")
    if x_api_key != ANALYTICS_API_KEY:
        raise HTTPException(401, "Invalid API key")


async def create_sync_log_entry(job_name: str) -> int:
    sb = _get_supabase()
    res = sb.schema("marketing").table("sync_log").insert({
        "job_name": job_name,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
    }).execute()
    if not res.data:
        raise RuntimeError("Failed to create sync_log row")
    return int(res.data[0]["id"])


def run_sync_subprocess(job_name: str, sync_log_id: int) -> None:
    """Run the sync script in a subprocess and update sync_log."""
    script = JOB_SCRIPTS[job_name]
    sb = _get_supabase()
    try:
        result = subprocess.run(
            ["python", script, "--mode", "last_week"],
            capture_output=True,
            text=True,
            timeout=900,  # 15 min cap
        )
        if result.returncode == 0:
            sb.schema("marketing").table("sync_log").update({
                "status": "success",
                "finished_at": datetime.utcnow().isoformat(),
            }).eq("id", sync_log_id).execute()
        else:
            sb.schema("marketing").table("sync_log").update({
                "status": "failed",
                "finished_at": datetime.utcnow().isoformat(),
                "error_message": result.stderr[:500],
            }).eq("id", sync_log_id).execute()
    except subprocess.TimeoutExpired:
        sb.schema("marketing").table("sync_log").update({
            "status": "failed",
            "finished_at": datetime.utcnow().isoformat(),
            "error_message": "Timeout after 15 min",
        }).eq("id", sync_log_id).execute()
    except Exception as e:
        logger.exception("Sync %s failed", job_name)
        sb.schema("marketing").table("sync_log").update({
            "status": "failed",
            "finished_at": datetime.utcnow().isoformat(),
            "error_message": str(e)[:500],
        }).eq("id", sync_log_id).execute()


@router.post("/sync/{job_name}", dependencies=[Depends(_require_api_key)])
async def trigger_sync(job_name: str, bg: BackgroundTasks):
    if job_name not in JOB_SCRIPTS:
        raise HTTPException(404, f"Unknown job: {job_name}")
    sync_log_id = await create_sync_log_entry(job_name)
    bg.add_task(run_sync_subprocess, job_name, sync_log_id)
    return {
        "job_name": job_name,
        "status": "running",
        "sync_log_id": sync_log_id,
        "started_at": datetime.utcnow().isoformat(),
    }


@router.get("/sync/{job_name}/status", dependencies=[Depends(_require_api_key)])
async def sync_status(job_name: str):
    if job_name not in JOB_SCRIPTS:
        raise HTTPException(404, f"Unknown job: {job_name}")
    sb = _get_supabase()
    res = (
        sb.schema("marketing").table("sync_log")
        .select("id, status, started_at, finished_at, rows_processed, error_message")
        .eq("job_name", job_name)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"status": "never_run"}
    return res.data[0]
```

- [ ] **Step 4: Register router and extend CORS**

Open `services/analytics_api/app.py`. Find `app.add_middleware(CORSMiddleware, ...)`. Update `allow_methods` from `["GET"]` to `["GET", "POST"]`. After the middleware block, add:
```python
from .marketing import router as marketing_router
app.include_router(marketing_router)
```

- [ ] **Step 5: Run test (PASS)**

Run: `python -m pytest tests/services/analytics_api/test_marketing_sync.py -v`
Expected: PASS.

- [ ] **Step 6: Smoke-test endpoint locally**

Start API: `cd services/analytics_api && uvicorn app:app --reload --port 8001`

Trigger:
```bash
curl -X POST http://localhost:8001/api/marketing/sync/search-queries -H "X-API-Key: $ANALYTICS_API_KEY"
```
Expected: 200 with `{"job_name": "search-queries", "status": "running", "sync_log_id": N, ...}`. Background subprocess runs (check log).

Status:
```bash
curl http://localhost:8001/api/marketing/sync/search-queries/status -H "X-API-Key: $ANALYTICS_API_KEY"
```
Expected: latest sync_log row JSON.

- [ ] **Step 7: Commit**

```bash
git add services/analytics_api/marketing.py \
        services/analytics_api/app.py \
        tests/services/analytics_api/__init__.py \
        tests/services/analytics_api/test_marketing_sync.py
git commit -m "feat(analytics-api): /api/marketing/sync/{job} POST + status endpoints with background subprocess"
```

### Task B.2.2: Wire UpdateBar refresh to backend endpoint

**Files:**
- Modify: `wookiee-hub/src/components/marketing/UpdateBar.tsx`
- Modify: `wookiee-hub/src/api/marketing/sync-log.ts` (add triggerSync + getSyncStatus)
- Modify: `wookiee-hub/src/hooks/marketing/use-sync-log.ts` (add useTriggerSync + useSyncStatus)

- [ ] **Step 1: Add API functions**

Open `wookiee-hub/src/api/marketing/sync-log.ts`. Append:
```ts
const ANALYTICS_API_URL = import.meta.env.VITE_ANALYTICS_API_URL || ''
const ANALYTICS_API_KEY = import.meta.env.VITE_ANALYTICS_API_KEY || ''

export type SyncJobName = 'search-queries' | 'promocodes'

export interface SyncStatusResponse {
  status: 'never_run' | 'running' | 'success' | 'failed'
  started_at?: string
  finished_at?: string
  rows_processed?: number
  error_message?: string
}

export async function triggerSync(job: SyncJobName): Promise<{ sync_log_id: number }> {
  const r = await fetch(`${ANALYTICS_API_URL}/api/marketing/sync/${job}`, {
    method: 'POST',
    headers: { 'X-API-Key': ANALYTICS_API_KEY },
  })
  if (!r.ok) throw new Error(`Sync trigger failed: ${r.status}`)
  return r.json()
}

export async function fetchSyncStatus(job: SyncJobName): Promise<SyncStatusResponse> {
  const r = await fetch(`${ANALYTICS_API_URL}/api/marketing/sync/${job}/status`, {
    headers: { 'X-API-Key': ANALYTICS_API_KEY },
  })
  if (!r.ok) throw new Error(`Sync status failed: ${r.status}`)
  return r.json()
}
```

- [ ] **Step 2: Add hooks**

Open `wookiee-hub/src/hooks/marketing/use-sync-log.ts`. Append:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { triggerSync, fetchSyncStatus, type SyncJobName } from "@/api/marketing/sync-log"

export function useTriggerSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (job: SyncJobName) => triggerSync(job),
    onSuccess: (_data, job) => {
      qc.invalidateQueries({ queryKey: ['sync-status', job] })
    },
  })
}

export function useSyncStatus(job: SyncJobName, enabled: boolean = false) {
  return useQuery({
    queryKey: ['sync-status', job],
    queryFn: () => fetchSyncStatus(job),
    refetchInterval: (data) => (data?.state?.data?.status === 'running' ? 2000 : false),
    enabled,
  })
}
```

- [ ] **Step 3: Update UpdateBar to use trigger + status**

Open `wookiee-hub/src/components/marketing/UpdateBar.tsx`. Replace contents:
```tsx
import { CheckCircle, RefreshCw, AlertCircle } from "lucide-react"
import { useTriggerSync, useSyncStatus } from "@/hooks/marketing/use-sync-log"
import type { SyncJobName } from "@/api/marketing/sync-log"

interface Props {
  job: SyncJobName
}

export function UpdateBar({ job }: Props) {
  const triggerMut = useTriggerSync()
  const { data: status } = useSyncStatus(job, true)

  const isRunning = status?.status === 'running' || triggerMut.isPending
  const isFailed = status?.status === 'failed'

  const lastTime = status?.finished_at
    ? new Date(status.finished_at).toLocaleString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <div className="flex items-center gap-3 px-6 py-1.5 bg-stone-50 border-b border-stone-200 text-[11px]">
      <div className="flex items-center gap-1.5 text-stone-500">
        {isFailed ? (
          <AlertCircle className="w-3 h-3 text-amber-500" />
        ) : (
          <CheckCircle className="w-3 h-3 text-emerald-500" />
        )}
        <span className="tabular-nums">{lastTime}</span>
        {isRunning && status?.rows_processed != null && (
          <>
            <span className="text-stone-300">·</span>
            <span className="text-stone-500">Обновление: {status.rows_processed} строк</span>
          </>
        )}
        {isFailed && status?.error_message && (
          <>
            <span className="text-stone-300">·</span>
            <span className="text-amber-600 truncate max-w-[300px]" title={status.error_message}>
              {status.error_message}
            </span>
          </>
        )}
      </div>
      <button
        onClick={() => triggerMut.mutate(job)}
        disabled={isRunning}
        className={`ml-auto flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium transition-colors ${
          isRunning
            ? "border-stone-200 text-stone-400 bg-stone-100"
            : "border-stone-300 text-stone-600 hover:bg-stone-100 hover:border-stone-400"
        }`}
      >
        <RefreshCw className={`w-3 h-3 ${isRunning ? "animate-spin" : ""}`} />
        {isRunning ? "Обновляю…" : "Обновить"}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Pass job prop in pages**

In `wookiee-hub/src/pages/marketing/search-queries.tsx`: `<UpdateBar job="search-queries" />`
In `wookiee-hub/src/pages/marketing/promo-codes.tsx`: `<UpdateBar job="promocodes" />`

- [ ] **Step 5: Update .env.example**

Open `wookiee-hub/.env.example`. Add:
```
VITE_ANALYTICS_API_URL=http://localhost:8001
VITE_ANALYTICS_API_KEY=
```

- [ ] **Step 6: Smoke-test**

Open `/marketing/search-queries`. Click «Обновить». Spinner spins, button disabled. After completion — timestamp updates.

- [ ] **Step 7: Commit**

```bash
git add wookiee-hub/src/components/marketing/UpdateBar.tsx \
        wookiee-hub/src/api/marketing/sync-log.ts \
        wookiee-hub/src/hooks/marketing/use-sync-log.ts \
        wookiee-hub/src/pages/marketing/search-queries.tsx \
        wookiee-hub/src/pages/marketing/promo-codes.tsx \
        wookiee-hub/.env.example
git commit -m "feat(marketing-hub): wire UpdateBar refresh to /api/marketing/sync endpoint with live progress"
```

### Task B.2.3: Runbook for fresh data bootstrap

**Files:**
- Create: `docs/scripts/marketing-v4-bootstrap-runbook.md`

- [ ] **Step 1: Create runbook**

Create `docs/scripts/marketing-v4-bootstrap-runbook.md`:
```markdown
# Marketing v4 — Post-deploy Bootstrap Runbook

After Phase 2B is deployed (view v2 + RPC v2 + bridge), run a fresh sync to ensure all DB-added words are in Sheets and that view/RPC return non-zero metrics for brands.

## Step 1: Verify view + RPC migrations applied

```bash
psql "$SUPABASE_DB_URL" -c "
SELECT entity_type, COUNT(*) FROM marketing.search_queries_unified GROUP BY entity_type;"
```
Expected: rows for `brand`, `nomenclature`, `ww_code` (+ `other`).

```bash
psql "$SUPABASE_DB_URL" -c "
SELECT u.entity_type, COUNT(*) FILTER (WHERE a.orders > 0) AS with_orders
FROM marketing.search_queries_unified u
LEFT JOIN LATERAL marketing.search_query_stats_aggregated('2026-02-01', '2026-04-27') a
  ON a.unified_id = u.unified_id
GROUP BY u.entity_type;"
```
Expected: brand row shows non-zero `with_orders` (~10-15).

## Step 2: Run search-queries sync (last week)

```bash
python scripts/run_search_queries_sync.py --mode last_week
```
Expected log line: `Bridge: inserted N new words into Sheets` (N may be 0 if no UI-added words pending).

## Step 3: Run promocodes sync (last week)

```bash
python scripts/run_wb_promocodes_sync.py --mode last_week
```
Expected: `Promo bridge: inserted N UUIDs into Sheets dictionary`.

## Step 4: Verify in Hub UI

Open `https://hub.os.wookiee.shop/marketing/search-queries`. Brand group `wooki` / `Wendy` / `Audrey` should show non-zero metrics.

## Troubleshooting

If sync subprocess times out:
- Check `marketing.sync_log` for `error_message`
- WB API rate limits: ~21s between batches of 50 nm_id. Long-tail accounts may need >15min cap.
- Increase timeout in `services/analytics_api/marketing.py:run_sync_subprocess`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/scripts/marketing-v4-bootstrap-runbook.md
git commit -m "chore(marketing): runbook for fresh data bootstrap after view changes"
```

---

## Phase 2B Pull Request

### Task B.PR: Create Pull Request for Phase 2B

- [ ] **Step 1: Push**

```bash
git push
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --base main --title "feat(marketing): Phase 2B — backend SQL + sync bridge + endpoint" --body "$(cat <<'EOF'
## Summary

Phase 2B of marketing v4 fidelity. Closes the UI→DB→Sheets→WB→DB→UI loop and activates metrics for branded queries.

Implemented from design: `docs/superpowers/specs/2026-05-12-marketing-v4-fidelity-design.md`

## Changes

### Database
- View `marketing.search_queries_unified` v2: adds `entity_type`, `channel_label`, `sku_label`; improves `model_hint` via modeli_osnova JOIN. Additive — preserves all v1 columns.
- RPC `marketing.search_query_stats_aggregated` v2: JOINs `marketing.search_queries_weekly` by `search_word`. Closes "brands with zeros" bug.
- Seed channel `ooo` (was missing from initial 12-channel seed).

### ETL Bridges
- `sync_search_queries.py`: section-aware insert into Sheets col A for DB-added words before WB pull.
- `sync_promocodes.py`: UUID-based dedup insert into dictionary section.

### Backend API
- `services/analytics_api/marketing.py`: POST `/api/marketing/sync/{job}` + GET `/api/marketing/sync/{job}/status` with background subprocess + sync_log tracking.
- CORS extended to allow POST.

### Frontend
- `UpdateBar` wired to live endpoint. Shows progress + error states. 2s poll while running.

## Test plan

- [ ] Apply migrations: `psql -f` all 3 SQL files
- [ ] `psql` verify: brand rows have non-zero orders
- [ ] Add WW-code via UI on `/marketing/search-queries`
- [ ] Click «Обновить» → progress shows → completes → new WW-code has metrics
- [ ] `pytest tests/services/sheets_sync tests/services/analytics_api -v` passes
- [ ] Cron Mon 10:00/12:00 МСК continues without regression
EOF
)"
```

- [ ] **Step 3: Wait for review and merge.**

After merge — run **B.2.3 runbook** in prod.

---

## Self-Review Summary

The plan covers all 28 commits from the design document (`docs/superpowers/specs/2026-05-12-marketing-v4-fidelity-design.md`):

- **Phase 2A (20 commits across 7 waves A.0-A.7):** all visual + CRUD work on existing Phase 2 data
- **Phase 2B (8 commits across 3 waves B.0-B.2):** additive view/RPC migrations + sync bridges + endpoint

Each task includes:
- Exact file paths (Create/Modify/Test)
- Full code blocks (no `// ... existing ...` placeholders except where contextual location is clear)
- Verification commands with expected output
- Commit message ready to paste

**Dependencies respected:**
- A.0 (MarketingLayout) must precede all other A.x
- A.1.1 (palette scope) provides the visual canvas all later visual work relies on
- A.2.1 (status mapping) must precede A.5.4 (StatusEditor mutation wiring)
- A.4.1 (extract ui-preferences) must precede A.4.2 and A.4.3
- A.5.1 (useUpdatePromoCode) must precede A.5.2 (edit-mode)
- B.0.1 (view v2) must precede B.0.2 (RPC v2)
- B.0 must complete before B.2.2 frontend can read `channel_label` directly (Phase 2A uses `useChannels()` lookup as bridge)
- B.1 + B.2.1 independent; B.2.2 depends on B.2.1

**Risk mitigations from design:**
- A.2.2 documents the Phase 2A→2B handoff for `channel_label`
- B.0.1 keeps view additive to avoid breaking existing frontend
- B.2.1 has 15-min subprocess timeout matching design risk 3
- B.2.2 shows error state from `marketing.sync_log.error_message`
