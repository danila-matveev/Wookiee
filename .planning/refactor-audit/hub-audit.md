# Hub Audit — wookiee-hub trim to 2 modules (Комьюнити + Агенты)

**Date:** 2026-04-24
**Author:** audit-hub (read-only)
**Base spec:** `docs/superpowers/specs/2026-04-24-refactor-v3-design.md` §3, §4.1
**Scope:** `wookiee-hub/src/**`, `wookiee-hub/package.json`, `wookiee-hub/vite.config.ts`, `wookiee-hub/tsconfig*.json`, `wookiee-hub/index.html`, `wookiee-hub/public/`

Target after trim:
- **Комьюнити** (меню): подразделы Отзывы, Вопросы, Ответы, Аналитика.
- **Агенты** (меню): подразделы Табло скиллов, История запусков.

---

## 1. Dependency graph summary

### 1.1 Page → transitive closure (only pages relevant to 2 target modules)

| Page | Direct deps | Transitive (recursive) |
|---|---|---|
| `pages/comms-reviews.tsx` | `components/comms/reviews-header`, `reviews-status-tabs`, `review-list-item`, `review-detail`; `stores/comms`; `types/comms`; lucide | → reviews-header: `lib/utils`, `components/ui/input`, `stores/comms`, `stores/integrations`, `config/service-registry`, `components/comms/reviews-filter-popover`, `reviews-sort-popover`, `types/comms`<br>→ review-detail: `lib/utils`, `components/ui/{button,textarea}`, `config/service-registry`, `stores/{comms,comms-settings}`, `lib/comms-service`, `types/comms`<br>→ reviews-filter-popover: `components/ui/{popover,checkbox,button}`, `components/shared/date-range-picker`, `stores/{comms,integrations}`, `config/service-registry`<br>→ date-range-picker: `components/ui/{popover,calendar}`, `lib/utils`<br>→ lib/comms-service: `lib/api-client`, `types/{comms,comms-settings}` |
| `pages/comms-analytics.tsx` | `components/comms/analytics-header`, `analytics-metrics`, `analytics-response-chart`, `analytics-rating-chart`, `analytics-stores-table` | → analytics-header: `lib/utils`, `stores/integrations`, `config/service-registry`<br>→ analytics-metrics: `motion/react`, `components/shared/metric-card`, `lib/motion`, `lib/utils`, `data/comms-mock`<br>→ analytics-response-chart + analytics-rating-chart: `recharts`, `lib/utils`, `data/comms-mock`<br>→ analytics-stores-table: `lib/utils`, `config/service-registry`, `data/comms-mock`, `lib/format`<br>→ metric-card: `lib/utils`, `components/shared/{change-indicator,progress-bar}`, `types/dashboard` |

**No page exists yet for Агенты.** `pages/stubs/agents.tsx` is just a `ModuleStub` placeholder referenced via `/system/agents`.

### 1.2 Cross-shared dependencies (used by 2 kept pages)

- `stores/comms.ts` (reviews) — uses `lib/comms-service`, `types/comms`
- `stores/comms-settings.ts` (reviews detail) — uses `data/comms-settings-mock`, `types/comms-settings`
- `stores/integrations.ts` (both) — uses `data/integrations-mock`, `types/integrations`
- `stores/theme.ts` (layout) — self
- `stores/navigation.ts` (layout) — self
- `config/navigation.ts` (layout) — uses `types/navigation`
- `config/service-registry.ts` (both) — uses `types/integrations`

### 1.3 Layout shell (always kept)

`components/layout/{app-shell,icon-bar,icon-bar-button,logo,sub-sidebar,sub-sidebar-item,top-bar,theme-toggle,user-menu,mobile-menu,mobile-nav}.tsx`
`components/shared/command-palette.tsx` (global ⌘K)
`main.tsx`, `router.tsx`, `App.tsx` (but App.tsx is currently broken — imports non-existent `ComponentExample`; router is wired via `main.tsx` directly, so App.tsx is effectively unused).

---

## 2. KEEP list

### 2.1 Entry & build

| File | Reason | Module |
|---|---|---|
| `wookiee-hub/package.json` | Keep (some deps to prune — see §7) | infra |
| `wookiee-hub/vite.config.ts` | Keep | infra |
| `wookiee-hub/vitest.config.ts` | Keep | infra |
| `wookiee-hub/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` | Keep (not in repo yet — actual file is `tsconfig.temp.json`; needs verification during PR #6) | infra |
| `wookiee-hub/index.html` | Keep | infra |
| `wookiee-hub/src/main.tsx` | Keep — entry | infra |
| `wookiee-hub/src/index.css` | Keep — Tailwind entry | infra |
| `wookiee-hub/src/router.tsx` | Keep (rewrite — see §6) | infra |

### 2.2 Pages (kept)

| File | Reason | Module |
|---|---|---|
| `src/pages/comms-reviews.tsx` | Source of "Отзывы" sub-section; also base for "Вопросы"/"Ответы" — the `source` filter already splits review/question/chat | Комьюнити |
| `src/pages/comms-analytics.tsx` | Source of "Аналитика" sub-section | Комьюнити |

### 2.3 Components (kept — transitive closure from 2 pages + layout)

**Comms components (from reviews + analytics):**
- `components/comms/reviews-header.tsx`
- `components/comms/reviews-status-tabs.tsx`
- `components/comms/review-list-item.tsx`
- `components/comms/review-detail.tsx`
- `components/comms/reviews-filter-popover.tsx`
- `components/comms/reviews-sort-popover.tsx`
- `components/comms/analytics-header.tsx`
- `components/comms/analytics-metrics.tsx`
- `components/comms/analytics-response-chart.tsx`
- `components/comms/analytics-rating-chart.tsx`
- `components/comms/analytics-stores-table.tsx`

**Layout (always):**
- `components/layout/app-shell.tsx`
- `components/layout/icon-bar.tsx`
- `components/layout/icon-bar-button.tsx`
- `components/layout/logo.tsx`
- `components/layout/sub-sidebar.tsx`
- `components/layout/sub-sidebar-item.tsx`
- `components/layout/top-bar.tsx`
- `components/layout/theme-toggle.tsx`
- `components/layout/user-menu.tsx`
- `components/layout/mobile-menu.tsx`
- `components/layout/mobile-nav.tsx`

**Shared components used by kept:**
- `components/shared/metric-card.tsx` (analytics-metrics → needs it)
- `components/shared/change-indicator.tsx` (metric-card)
- `components/shared/progress-bar.tsx` (metric-card)
- `components/shared/date-range-picker.tsx` (reviews-filter-popover)
- `components/shared/command-palette.tsx` (app-shell)

**UI primitives (used by the above — kept):**
- `components/ui/button.tsx`
- `components/ui/input.tsx`
- `components/ui/textarea.tsx`
- `components/ui/popover.tsx`
- `components/ui/checkbox.tsx`
- `components/ui/calendar.tsx`
- `components/ui/command.tsx`
- `components/ui/dialog.tsx` (Command uses `CommandDialog` which wraps Dialog)
- `components/ui/separator.tsx` (IconBar)
- `components/ui/dropdown-menu.tsx` (likely user-menu — verify)

### 2.4 Stores (kept)

- `stores/comms.ts`
- `stores/comms-settings.ts`
- `stores/integrations.ts`
- `stores/theme.ts`
- `stores/navigation.ts`

### 2.5 Lib (kept)

- `lib/utils.ts` (cn — used everywhere)
- `lib/api-client.ts` (comms-service + future agents-service)
- `lib/comms-service.ts` (reviews detail AI generate)
- `lib/motion.ts` (analytics-metrics staggerContainer/Item)
- `lib/format.ts` (analytics-stores-table formatPercent)

### 2.6 Data (mocks kept — temporary until real backend wired)

- `data/comms-mock.ts` (analytics charts, dashboard mock; reviews are fetched live but `commsStoreBreakdown` is read by the dashboard code that we're deleting — check §3)
- `data/comms-settings-mock.ts` (review-detail AI config)
- `data/integrations-mock.ts` (integrations store initial state)

> Note: if `comms-dashboard.tsx` is deleted, `commsTopProducts`, `commsChartData`, `commsDashboardMetrics`, `commsStoreBreakdown` remain in `comms-mock.ts` but are unused. The `reviews-filter-popover` and `analytics-*` still consume `commsResponseTimeData`, `commsRatingDistribution`, `commsAnalyticsMetrics`, `commsAnalyticsStores`. Recommendation: keep `comms-mock.ts` as-is for PR #6 and let hygiene pass prune unused exports later.

### 2.7 Types (kept)

- `types/comms.ts`
- `types/comms-settings.ts`
- `types/integrations.ts`
- `types/navigation.ts`
- `types/dashboard.ts` (MetricCard uses `DashboardMetric` interface)
- `types/api.ts` (used by api-client — verify; if not, move to DELETE)

### 2.8 Config (kept)

- `config/navigation.ts` (rewrite to only 2 groups — see §6)
- `config/service-registry.ts`

### 2.9 Hooks

- None of the hooks (`hooks/use-api-query.ts`, `hooks/use-table-state.ts`) are imported by kept pages. **DELETE** both (see §3).

### 2.10 Public / assets

- `wookiee-hub/src/assets/react.svg` — default Vite asset, used nowhere; **DELETE**.
- `wookiee-hub/public/` — directory not present in repo listing; no action.

---

## 3. DELETE list

### 3.1 Pages (orphaned after trim — not in closure)

| File | Reason |
|---|---|
| `src/pages/dashboard.tsx` | Module "Главная/Дашборд" removed |
| `src/pages/dashboard-placeholder.tsx` | Module removed |
| `src/pages/catalog.tsx` | Product/Catalog module removed |
| `src/pages/development.tsx` | Product/Development removed |
| `src/pages/production.tsx` | Product/Production removed |
| `src/pages/shipments.tsx` | Operations/Shipments removed |
| `src/pages/supply.tsx` | Operations/Supply removed |
| `src/pages/ideas.tsx` | Team/Ideas removed |
| `src/pages/analytics-overview.tsx` | Analytics module removed |
| `src/pages/analytics-abc.tsx` | Analytics module removed |
| `src/pages/analytics-promo.tsx` | Analytics module removed |
| `src/pages/analytics-unit.tsx` | Analytics module removed |
| `src/pages/comms-broadcasts.tsx` | Spec §3.1: "Блок Comms оставляем только про отзывы" |
| `src/pages/comms-dashboard.tsx` | Not in 2 target modules |
| `src/pages/comms-store-settings.tsx` | Spec §3.1 |
| `src/pages/product-matrix/**` (all 11 files) | Spec §3.1 |
| `src/pages/system/**` (all 6 files: api-explorer, archive-manager, audit-log, db-stats, matrix-admin-layout, schema-explorer) | Not in 2 target modules |
| `src/pages/stubs/**` (all ~22 files) | All stub modules removed; `agents.tsx` replaced by real Agents page |

### 3.2 Components (orphaned)

| Directory | Files | Reason |
|---|---|---|
| `components/analytics/` | abc-chart, abc-header, abc-table, analytics-chart, analytics-header, analytics-metrics | Analytics module removed |
| `components/catalog/` | catalog-grid, catalog-header, catalog-table | Catalog removed |
| `components/dashboard/` | 9 files (activity-feed, dashboard-header/metrics, expenses-table, global-filters, model-detail-drawer, model-table, orders-chart, quick-stats, upcoming-shipments) | Dashboard removed |
| `components/kanban/` | 13 files (all drawer-*, kanban-*, list-view, sortable-card, table-view) | Dashboards/ideas/shipments removed |
| `components/matrix/` | ~25 files (all) incl. `panel/`, `tabs/` | Product matrix removed |
| `components/promo/` | 6 files | Analytics/Promo removed |
| `components/supply/` | 6 files | Supply removed |
| `components/unit/` | unit-table | Unit economics removed |
| `components/comms/` (partial) | `broadcast-create-form`, `broadcast-list`, `comms-dashboard-chart`, `comms-dashboard-header`, `comms-dashboard-metrics`, `comms-dashboard-stores`, `comms-dashboard-tabs`, `comms-dashboard-top-products`, `settings-tab-ai-learning`, `settings-tab-chats`, `settings-tab-extended`, `settings-tab-questions`, `settings-tab-recommendations`, `settings-tab-reviews`, `settings-tab-signature` | Broadcasts/dashboard/store-settings pages deleted |
| `components/shared/` (partial) | `chart-skeleton`, `metric-card-skeleton`, `module-stub`, `multi-select-filter`, `priority-dot`, `status-pill`, `table-skeleton`, `view-switcher` | Used only by deleted modules |
| `components/component-example.tsx` | — | Referenced only by broken `App.tsx` |
| `components/example.tsx` | — | Demo artefact |
| `components/ui/` (verify) | `alert-dialog`, `badge`, `card`, `combobox`, `field`, `input-group`, `label`, `select`, `sheet`, `skeleton`, `tabs` | UI primitives only used by deleted components. Verify with final grep; `tabs.tsx` may be needed if Агенты page uses tabs (see §4 recommendation). |

### 3.3 Stores (orphaned)

| File | Reason |
|---|---|
| `stores/comms-broadcasts.ts` | broadcasts page deleted |
| `stores/filters.ts` | Analytics/dashboard only |
| `stores/kanban.ts` | Kanban removed |
| `stores/matrix-store.ts` | Product matrix removed |
| `stores/supply.ts` | Supply removed |
| `stores/views-store.ts` | Matrix views removed |
| `stores/__tests__/detail-panel-routing.test.ts` | Matrix store tests |
| `stores/__tests__/entity-update-stamp.test.ts` | Matrix store tests |
| `stores/__tests__/matrix-store-filters.test.ts` | Matrix store tests |

### 3.4 Lib (orphaned)

| File | Reason |
|---|---|
| `lib/api/abc.ts`, `finance.ts`, `promo.ts`, `series.ts`, `stocks.ts`, `supply.ts`, `traffic.ts` | All analytics/supply backend clients — modules removed |
| `lib/entity-registry.ts` | Matrix-admin |
| `lib/field-def-columns.ts` | Matrix |
| `lib/matrix-api.ts` | Matrix |
| `lib/model-columns.ts` | Matrix |
| `lib/supply-calc.ts` | Supply |
| `lib/view-columns.ts` | Matrix views |
| `lib/__tests__/entity-registry.test.ts` | Matrix tests |

### 3.5 Data (orphaned)

| File | Reason |
|---|---|
| `data/analytics-mock.ts` | Analytics removed |
| `data/catalog-mock.ts` | Catalog removed |
| `data/dashboard-mock.ts` | Dashboard removed |
| `data/kanban-mock.ts` | Kanban removed |
| `data/supply-mock.ts` | Supply removed |

### 3.6 Types (orphaned)

| File | Reason |
|---|---|
| `types/analytics.ts` | Analytics removed |
| `types/catalog.ts` | Catalog removed |
| `types/comms-broadcasts.ts` | Broadcasts removed |
| `types/kanban.ts` | Kanban removed |
| `types/supply.ts` | Supply removed |

### 3.7 Config (orphaned)

| File | Reason |
|---|---|
| `config/boards.ts` | Kanban boards config — deleted |

### 3.8 Hooks (orphaned)

| File | Reason |
|---|---|
| `hooks/use-api-query.ts` | Not used by kept pages (verify with grep during PR #6) |
| `hooks/use-table-state.ts` | Matrix/table views only |

### 3.9 Misc

| File | Reason |
|---|---|
| `src/App.tsx` | Imports `component-example` which is being deleted; not rendered by `main.tsx` → dead |
| `src/assets/react.svg` | Default Vite asset, unused |

**Total DELETE count (approximate):** ~145 files under `src/`.

---

## 4. CREATE list (new files for Агенты module)

Scaffold scope per spec §4.2.A — "только scaffold: роут + страница списка скиллов из `tools`, страница истории запусков из `tool_runs`, базовая таблица без украшательств".

| New file | Purpose |
|---|---|
| `src/pages/agents-skills.tsx` | "Табло скиллов" — lists rows from Supabase `tools` table (name, category, status, last_run_at, last_status) |
| `src/pages/agents-runs.tsx` | "История запусков" — lists rows from Supabase `tool_runs` table (tool, status, started_at, duration, cost_usd, trigger_source) |
| `src/types/agents.ts` | TS types: `Tool`, `ToolRun`, `ToolStatus`, `RunStatus` (mirrors Supabase schema of `tools`/`tool_runs`) |
| `src/stores/agents.ts` | Zustand store: `tools[]`, `runs[]`, `loading`, `error`, `fetchTools()`, `fetchRuns(toolId?)` |
| `src/lib/agents-service.ts` | Service wrapping Supabase client: `fetchTools()`, `fetchRuns(filter)` |
| `src/lib/supabase.ts` | Supabase client singleton (`createClient` with `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`). **New dep: `@supabase/supabase-js`**. |
| `src/components/agents/tools-table.tsx` | Compact table row component for skills list |
| `src/components/agents/runs-table.tsx` | Compact table row component for runs list |
| `src/components/agents/run-status-badge.tsx` | Tiny status pill (success/error/running) |
| `.env.example` additions in `wookiee-hub/` | `VITE_SUPABASE_URL=`, `VITE_SUPABASE_ANON_KEY=` |

**Optional (Фаза 1.5):**
- `src/components/agents/tool-detail-drawer.tsx` — click-through from skills → filtered runs
- Charts (runs per day, cost by tool) via `recharts` (already a dep)

---

## 5. RENAME recommendations

### 5.1 Page layout decision (tabs vs routes)

**RECOMMENDATION: Use routes, not tabs. Keep files flat in `pages/` with `community-*` / `agents-*` prefixes (or group under `pages/community/` and `pages/agents/` subdirs — see 5.2).**

Reasoning:
1. Bookmarkability — users can save `/community/reviews` vs `/community?tab=reviews`.
2. Deep-linkable filters — `comms-reviews.tsx` already has rich URL-worthy state (source tab, sort, filters). Tabs collapse that into one URL.
3. Code-split friendly — route-based lazy loading is easier later.
4. Existing code is already page-per-route; converting 4 separate pages into a tabs-container adds work without benefit.
5. The top-level "Комьюнити" / "Агенты" menu buttons remain as navigation *groups* (icon-bar items), and the sub-sidebar shows the 4+2 sub-items — this matches the existing `navigationGroups` pattern with zero refactor of the shell.

### 5.2 Suggested path layout

**Option A (recommended): group by subdir, rename files**

| Old path | New path | Route |
|---|---|---|
| `pages/comms-reviews.tsx` | `pages/community/reviews.tsx` | `/community/reviews` |
| — (new, same logic, different source filter) | `pages/community/questions.tsx` | `/community/questions` |
| — (new) | `pages/community/answers.tsx` | `/community/answers` |
| `pages/comms-analytics.tsx` | `pages/community/analytics.tsx` | `/community/analytics` |
| — (new) | `pages/agents/skills.tsx` | `/agents/skills` |
| — (new) | `pages/agents/runs.tsx` | `/agents/runs` |
| `components/comms/*` | `components/community/*` | — |
| `stores/comms.ts` | `stores/community.ts` | — |
| `stores/comms-settings.ts` | `stores/community-settings.ts` | — |
| `types/comms.ts` | `types/community.ts` | — |
| `types/comms-settings.ts` | `types/community-settings.ts` | — |
| `lib/comms-service.ts` | `lib/community-service.ts` | — |
| `data/comms-mock.ts` | `data/community-mock.ts` | — |
| `data/comms-settings-mock.ts` | `data/community-settings-mock.ts` | — |

Reasoning: the new top-level menu says "Комьюнити" — code naming should match product naming. Future contributors won't wonder "why is it called `comms` when the nav says `community`?".

**Option B (lighter): keep `comms-*` names, add two new pages only**

Keep `pages/comms-reviews.tsx` and `pages/comms-analytics.tsx` as-is. Add `pages/comms-questions.tsx` (thin wrapper forcing `source="question"`) and `pages/comms-answers.tsx`. Add `pages/agents-skills.tsx`, `pages/agents-runs.tsx`. Routes become `/comms/reviews`, `/comms/questions`, `/comms/answers`, `/comms/analytics`, `/agents/skills`, `/agents/runs`.

Reasoning: less churn, smaller diff — but leaves naming inconsistent between UI label ("Комьюнити") and code (`comms-*`).

### 5.3 Questions/Answers decomposition

Current `comms-reviews.tsx` has a `source` source filter with values `review | question | chat`. The product mapping is:
- **Отзывы** → `source === "review"`
- **Вопросы** → `source === "question"`
- **Ответы** → `status === "published"` (i.e., everything already answered, across sources)

So "Ответы" is NOT a new `source` — it's a `status`-based view. Implementation: `reviews.tsx` already handles the "Отвеченные" sub-tab inside the "Обработанные" tab. The Ответы page can be a thin wrapper around `CommsReviewsPage` with `initialTab="processed"` + `initialProcessedSubTab="answered"` passed as props (needs a tiny refactor to accept initial state).

**Recommendation:** "Вопросы" page = same component with default `activeSource = "question"` (prop). "Ответы" page = same component with default `filters.tab = "processed"` + `processedSubTab = "answered"` (prop). Minimal code, maximal reuse.

---

## 6. Router / App / menu changes

### 6.1 `src/router.tsx` — rewrite

Strip all imports except `AppShell` + the 6 kept pages. Final shape:

```tsx
import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ReviewsPage }    from "@/pages/community/reviews"
import { QuestionsPage }  from "@/pages/community/questions"
import { AnswersPage }    from "@/pages/community/answers"
import { AnalyticsPage }  from "@/pages/community/analytics"
import { SkillsPage }     from "@/pages/agents/skills"
import { RunsPage }       from "@/pages/agents/runs"

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Navigate to="/community/reviews" replace /> },
      { path: "/community", element: <Navigate to="/community/reviews" replace /> },
      { path: "/community/reviews",   element: <ReviewsPage /> },
      { path: "/community/questions", element: <QuestionsPage /> },
      { path: "/community/answers",   element: <AnswersPage /> },
      { path: "/community/analytics", element: <AnalyticsPage /> },
      { path: "/agents", element: <Navigate to="/agents/skills" replace /> },
      { path: "/agents/skills", element: <SkillsPage /> },
      { path: "/agents/runs",   element: <RunsPage /> },
    ],
  },
])
```

### 6.2 `src/App.tsx` — delete (or make a simple re-export)

Currently broken (imports `ComponentExample` that stays; if we delete `component-example.tsx`, App.tsx must be either deleted or re-written). `main.tsx` doesn't use `App`, so **delete `App.tsx`**.

### 6.3 `src/config/navigation.ts` — rewrite

```ts
import { MessageSquare, Bot, Star, HelpCircle, CheckCircle2, BarChart3, LayoutGrid, ScrollText } from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "community",
    icon: MessageSquare,
    label: "Комьюнити",
    items: [
      { id: "reviews",   label: "Отзывы",    icon: Star,         path: "/community/reviews" },
      { id: "questions", label: "Вопросы",   icon: HelpCircle,   path: "/community/questions" },
      { id: "answers",   label: "Ответы",    icon: CheckCircle2, path: "/community/answers" },
      { id: "analytics", label: "Аналитика", icon: BarChart3,    path: "/community/analytics" },
    ],
  },
  {
    id: "agents",
    icon: Bot,
    label: "Агенты",
    items: [
      { id: "skills", label: "Табло скиллов",   icon: LayoutGrid,  path: "/agents/skills" },
      { id: "runs",   label: "История запусков", icon: ScrollText, path: "/agents/runs" },
    ],
  },
]
```

### 6.4 `src/components/layout/mobile-nav.tsx` — rewrite

Replace the 4 hardcoded tabs (`home/product/operations/more`) with 2 real + 1 more:

```ts
const tabs = [
  { id: "community", label: "Комьюнити", icon: MessageSquare, path: "/community/reviews" },
  { id: "agents",    label: "Агенты",    icon: Bot,           path: "/agents/skills" },
  { id: "more",      label: "Ещё",       icon: MoreHorizontal, path: null },
]
```

### 6.5 `src/components/layout/app-shell.tsx` — tiny fix

Lines 31-32: the "home" branch doing `path.startsWith("/dashboard")` becomes stale. Replace with a `/community` check or just let the generic segment matcher handle it. Low-risk.

### 6.6 `src/components/layout/top-bar.tsx` — tiny fix

`buildBreadcrumbs` line 101 — drop the `/dashboard` shortcut, first crumb becomes "Комьюнити" / "Агенты" depending on segment 0.

### 6.7 Sidebar

`components/layout/sub-sidebar.tsx` and `sub-sidebar-item.tsx` need no changes — they read from `navigationGroups`, which we rewrote.

### 6.8 `src/components/shared/command-palette.tsx`

Needs no changes — reads `navigationGroups` automatically.

---

## 7. Missing pieces / Supabase integration

1. **`@supabase/supabase-js` client** — not currently a dep in `wookiee-hub/package.json`. Must add. Rough patch:
   ```json
   "@supabase/supabase-js": "^2.45.0"
   ```
2. **Env vars** — new entries in Hub `.env` (and `.env.example`):
   - `VITE_SUPABASE_URL` — Supabase project URL (`gjvwcdtfglupewcwzfhw.supabase.co`)
   - `VITE_SUPABASE_ANON_KEY` — anon key (RLS enforced)
3. **RLS policies for `tools` and `tool_runs`** — per `CLAUDE.md` and `sku_database/README.md`, new Supabase tables need RLS + policies. Verify:
   - `tools` table has a `SELECT` policy for `anon` or `authenticated` role (read-only from Hub)
   - `tool_runs` table has same
   If missing, Orchestrator should flag a DB-side task before PR #6.
4. **Auth**: Hub has no login UI today. Two options:
   - **Simple**: use anon key + row-level policy `USING (true)` on these 2 tables (read-only, no PII). Safe for internal dashboard.
   - **Proper**: add Supabase Auth screen + email/password → blocks PR #6 until auth module shipped. Recommend deferring to Фаза 1.5 unless blocking.
5. **`dashboard_api`** — spec §3.2 flags this service as undecided. Given we're switching to direct supabase-js from Hub, `dashboard_api` is **not needed** for the Агенты module. Orchestrator should greenlight its deletion unless another module needs it.
6. **Package-json cleanup candidates after trim** (hygiene — can defer):
   - `@dnd-kit/core`, `@dnd-kit/sortable` — used only by kanban components → remove.
   - Remaining Radix/cmdk/recharts/zustand/react-day-picker — still needed.
7. **Tests** — `vitest.config.ts` is present but most tests live under `stores/__tests__` and `lib/__tests__` which we're deleting. No blocking test on kept modules; add 1-2 smoke tests for new `agents-service` to pass `npm test` cleanly.

---

## 8. iCloud-duplicate files (for anti-garbage PR #1)

Inside `wookiee-hub/`:

| Path | Action |
|---|---|
| `wookiee-hub/index 2.html` | DELETE — iCloud duplicate of `index.html` |
| `wookiee-hub/package-lock 2.json` | DELETE — iCloud duplicate of `package-lock.json` |
| `wookiee-hub/tsconfig.temp 2.json` | DELETE — iCloud duplicate of `tsconfig.temp.json` |
| `wookiee-hub/e2e-analytics.png` | DELETE — old e2e screenshot artefact |
| `wookiee-hub/e2e-broadcasts.png` | DELETE — old e2e screenshot artefact (broadcasts being deleted) |
| `wookiee-hub/e2e-dashboard.png` | DELETE — old e2e screenshot (dashboard being deleted) |
| `wookiee-hub/e2e-reviews.png` | DELETE — old e2e screenshot (superseded) |
| `wookiee-hub/e2e-settings.png` | DELETE — old e2e screenshot (settings being deleted) |
| `wookiee-hub/mockups/` | Review — if obsolete, DELETE. Contains `agent-dashboard-v2-*.{png,html}` — probably outdated mockup references. Recommend moving to `docs/archive/mockups/` or deleting. |
| `wookiee-hub/планы/референсы-otveto/` | DELETE — per cleanup-v2 spec; russian-named ref dir with old references |
| `wookiee-hub/.claude/` | Keep if active project skills; otherwise evaluate with audit-infra |

Total iCloud/garbage in `wookiee-hub/` root: **8 files + 2 directories** to delete in PR #1.

---

## Appendix: file counts

- Total `src/` files today: ~180
- KEEP (incl. layout, kept components, stores, lib, types, data, config, pages): **~55**
- DELETE: **~145** (including all pages/stubs, all non-layout/non-comms components, 7 stores, 8 lib files, 5 data mocks, 5 types, 1 config, 2 hooks, 2 misc)
- CREATE: **9 new files** (2 pages + 3 components + 1 types + 1 store + 1 service + 1 supabase client) + `.env.example` entry + `@supabase/supabase-js` dep

Net delta: ~180 → ~55 + 9 = **~64 files** (≈ 65% reduction).
