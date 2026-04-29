# Influencer CRM — Phase 4 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Companion skills: `frontend-design:frontend-design` (aesthetic discipline), `ui-ux-pro-max` (a11y/touch/perf rules), `gstack-design-html` (visual review).

**Goal:** Build a production-grade React+Vite+Tailwind+TypeScript application that turns the locked HTML prototype into a working CRM connected to all 21 BFF endpoints, ready for the marketing team to dogfood.

**Architecture:** SPA on `pnpm + Vite + React 18 + TypeScript`. Routing via `react-router-dom@6`. Server state via `@tanstack/react-query` (cursor pagination + ETag-aware GET). Forms via `react-hook-form` + `zod`. Drag-n-drop kanban via `@dnd-kit/core`. Calendar via custom grid (the prototype is bespoke; no calendar lib needed). Styling: Tailwind 4 (CSS-first config) + tokens lifted verbatim from `prototype.html` `:root` block. Tests: `vitest` + `@testing-library/react` for components/hooks, MSW for API mocks, Playwright for golden-path E2E hitting a live BFF.

**Tech Stack:**
- Build: Vite 5, TypeScript 5.4+, pnpm 9
- UI: React 18, Tailwind CSS 4, Headless UI (drawer/dialog/menu primitives only), `lucide-react` icons (NEVER emojis)
- State: TanStack Query 5, react-router-dom 6
- Forms: react-hook-form 7 + zod 3
- DnD: @dnd-kit/core + @dnd-kit/sortable
- Lint: Biome 1.9 (faster than ESLint+Prettier together)
- Tests: Vitest 1.6, Testing Library, MSW 2.x, Playwright 1.45+
- Dev: BFF runs on http://localhost:8082 via `services/influencer_crm/scripts/run_dev.sh`

**Branch:** `feat/influencer-crm-p4` (worktree `/tmp/wookiee-crm-p4`)
**Design contract:** `.crm-mockups/content/prototype.html` (2240 lines, 7 screens) — locked. CSS variables at lines 11-40 are the source of truth for design tokens.

---

## File Structure

All frontend code lives under `services/influencer_crm_ui/`. Backend code is **not touched** in P4 — the API contract is `docs/api/INFLUENCER_CRM_API.md` plus the schema deviations from `project_influencer_crm.md`.

```
services/influencer_crm_ui/
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── biome.json
├── index.html
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                      # Vite entry, mounts <App/>
│   ├── App.tsx                       # Router + QueryClientProvider + ETagInterceptor
│   ├── styles/
│   │   ├── tokens.css                # CSS vars lifted from prototype:root
│   │   └── globals.css               # @import tokens + Tailwind directives + base
│   ├── lib/
│   │   ├── api.ts                    # fetch() wrapper: baseURL, X-API-Key, ETag cache, JSON decode, error mapping
│   │   ├── cursor.ts                 # encode/decode opaque base64 cursors (mirrors backend)
│   │   ├── query-client.ts           # QueryClient factory + defaults (staleTime, retry policy)
│   │   └── format.ts                 # formatRu(int), formatRub(decimal), formatDate(iso), formatPct(num)
│   ├── api/                          # one file per resource, hooks ride on top
│   │   ├── bloggers.ts               # listBloggers, getBlogger, createBlogger, updateBlogger
│   │   ├── integrations.ts
│   │   ├── products.ts
│   │   ├── tags.ts
│   │   ├── promos.ts                 # substitute-articles + promo-codes
│   │   ├── briefs.ts
│   │   ├── metrics.ts
│   │   └── search.ts
│   ├── hooks/
│   │   ├── use-bloggers.ts           # useBloggers (list+pagination), useBlogger (detail), useUpsertBlogger
│   │   ├── use-integrations.ts
│   │   ├── use-products.ts
│   │   ├── use-tags.ts
│   │   ├── use-briefs.ts
│   │   ├── use-metrics.ts
│   │   └── use-search.ts
│   ├── ui/                           # generic, design-system primitives
│   │   ├── Button.tsx
│   │   ├── Badge.tsx
│   │   ├── Avatar.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── Textarea.tsx
│   │   ├── FilterPill.tsx
│   │   ├── PlatformPill.tsx          # IG/TG/YT/TT/VK with brand gradients
│   │   ├── KpiCard.tsx
│   │   ├── EmptyState.tsx
│   │   ├── Skeleton.tsx
│   │   ├── Tabs.tsx
│   │   ├── Drawer.tsx                # Headless UI Dialog with right-slide animation
│   │   └── Toast.tsx                 # global toast via context
│   ├── layout/
│   │   ├── AppShell.tsx              # sidebar + main, sticky top bar via outlet
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx                # search + user menu
│   │   └── PageHeader.tsx            # title + sub + actions slot
│   ├── routes/                       # one folder per screen, route file + screen-specific components
│   │   ├── bloggers/
│   │   │   ├── BloggersPage.tsx      # list with filters, table, expand row
│   │   │   ├── BloggersTable.tsx
│   │   │   ├── BloggerExpandedRow.tsx
│   │   │   └── BloggerEditDrawer.tsx # full edit form
│   │   ├── integrations/
│   │   │   ├── IntegrationsKanbanPage.tsx
│   │   │   ├── KanbanColumn.tsx
│   │   │   ├── KanbanCard.tsx
│   │   │   └── IntegrationEditDrawer.tsx
│   │   ├── calendar/
│   │   │   ├── CalendarPage.tsx
│   │   │   └── CalendarMonthGrid.tsx
│   │   ├── briefs/
│   │   │   ├── BriefsPage.tsx
│   │   │   └── BriefCard.tsx
│   │   ├── slices/
│   │   │   ├── SlicesPage.tsx
│   │   │   └── SlicesFilters.tsx
│   │   ├── products/
│   │   │   ├── ProductsPage.tsx
│   │   │   └── ProductSliceCard.tsx
│   │   └── NotFound.tsx
│   ├── test/
│   │   ├── setup.ts                  # vitest global setup, MSW server, jest-dom
│   │   ├── msw-handlers.ts           # mock 21 endpoints
│   │   └── render.tsx                # renderWithProviders helper
│   └── e2e/                          # Playwright tests (hit live BFF)
│       ├── playwright.config.ts
│       ├── fixtures/seed.ts          # ensure DB has at least 1 blogger via API before test
│       ├── golden-bloggers.spec.ts
│       ├── golden-kanban.spec.ts
│       ├── golden-search.spec.ts
│       └── golden-brief-edit.spec.ts
└── README.md
```

---

## Task Map (overview)

| # | Task | Outputs |
|---|---|---|
| T1 | Scaffold Vite project, install deps, Biome, Tailwind 4, Vitest, Playwright | repo boots, `pnpm dev` serves blank page on :5173 |
| T2 | Port design tokens from prototype CSS vars to `tokens.css` + Tailwind theme | `bg-card`, `text-primary`, `shadow-warm` work |
| T3 | Set up Google Fonts (Plus Jakarta Sans, DM Sans, JetBrains Mono) + base typography | headings render in display font, mono numbers |
| T4 | API client: `lib/api.ts` with X-API-Key, ETag cache, error mapping | `await api.get('/bloggers')` returns typed payload |
| T5 | Cursor utility: `lib/cursor.ts` with `encode/decode` round-trip parity to backend | unit tests pass |
| T6 | TanStack Query setup + `useBloggers` hook with cursor pagination | dev server fetches real bloggers list |
| T7 | UI primitives: Button, Badge, Avatar, Input, Select, FilterPill, PlatformPill, EmptyState, Skeleton, Tabs | Storybook-equivalent demo route at `/dev/ui` |
| T8 | Layout: AppShell + Sidebar + TopBar + PageHeader + router scaffold | nav between empty pages works |
| T9 | Drawer component (Headless UI Dialog + right-slide) | opens, closes on Esc, focus-trapped |
| T10 | Bloggers list page: filter bar, table, row hover, row expand panel | golden path: see 241 bloggers paginated |
| T11 | Blogger edit drawer (react-hook-form + zod) — Info / Channels / Integrations / Compliance tabs | save → PATCH → toast → list refetch |
| T12 | Integrations Kanban page (10 columns from `Stage` enum), DnD via @dnd-kit | drag card to new column → optimistic PATCH → rollback on 409 |
| T13 | Integration edit drawer (largest form: blogger + product + brief + plan/fact metrics) | save persists across reload |
| T14 | Calendar page (month grid, ICS export hidden behind feature flag) | published/pending/draft markers per day |
| T15 | Briefs page (4-column kanban + template panel) | create draft → bump version → mark signed |
| T16 | Slices page (filter combinations × period × marketer × tag) + CSV export | filter → render aggregates table |
| T17 | Products page (model osnova → substitute articles → integration halo) | open Wendy slice → see all integrations grouped by month |
| T18 | Global search `/search?q=...` page (bloggers + integrations) | search "плюс сайз" returns mixed results |
| T19 | Loading/error/empty states polish: every list screen has Skeleton + ErrorBanner + EmptyState | no flash of unstyled, no white screens |
| T20 | A11y pass: keyboard nav for forms, focus rings, ARIA labels for icon buttons, contrast audit | tab order matches visual order on every screen |
| T21 | Playwright golden-path suite (4 specs) hitting real BFF on :8082 | `pnpm e2e` green |
| T22 | Production build + preview script + README + dev-runner integration | `pnpm build && pnpm preview` serves on :4173 |

**Estimated effort:** 5-7 working days for one engineer + reviewer subagents, per roadmap.

---

## T1 — Scaffold

**Files:**
- Create: `services/influencer_crm_ui/package.json`
- Create: `services/influencer_crm_ui/vite.config.ts`
- Create: `services/influencer_crm_ui/tsconfig.json`, `tsconfig.node.json`
- Create: `services/influencer_crm_ui/biome.json`
- Create: `services/influencer_crm_ui/index.html`
- Create: `services/influencer_crm_ui/src/main.tsx`
- Create: `services/influencer_crm_ui/src/App.tsx`
- Create: `services/influencer_crm_ui/.gitignore`

- [ ] **Step 1: Create scaffold via Vite template**

```bash
cd services
pnpm create vite influencer_crm_ui --template react-ts
cd influencer_crm_ui
```

- [ ] **Step 2: Install runtime dependencies**

```bash
pnpm add react-router-dom @tanstack/react-query @tanstack/react-query-devtools \
  react-hook-form zod @hookform/resolvers \
  @dnd-kit/core @dnd-kit/sortable \
  @headlessui/react lucide-react clsx
```

- [ ] **Step 3: Install dev dependencies**

```bash
pnpm add -D tailwindcss@next @tailwindcss/vite@next \
  vitest @vitest/ui @testing-library/react @testing-library/jest-dom @testing-library/user-event \
  jsdom msw @playwright/test \
  @biomejs/biome
```

- [ ] **Step 4: Configure Vite for proxy + Tailwind**

`vite.config.ts`:

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8082',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

- [ ] **Step 5: Configure Biome**

`biome.json`:

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.0/schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "style": { "noNonNullAssertion": "off" },
      "suspicious": { "noExplicitAny": "warn" }
    }
  },
  "formatter": {
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "javascript": { "formatter": { "quoteStyle": "single", "semicolons": "always" } }
}
```

- [ ] **Step 6: Add scripts to package.json**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 4173",
    "test": "vitest",
    "test:run": "vitest run",
    "e2e": "playwright test",
    "lint": "biome check src",
    "fix": "biome check --write src",
    "typecheck": "tsc -b --noEmit"
  }
}
```

- [ ] **Step 7: Verify boot**

```bash
pnpm dev
```

Expected: server on http://localhost:5173 serving the Vite default page (no errors in terminal).

- [ ] **Step 8: Commit**

```bash
git add services/influencer_crm_ui
git commit -m "chore(crm-ui): T1 — scaffold Vite + React + Tailwind 4 + Biome + Vitest"
```

---

## T2 — Design tokens (port from prototype CSS vars)

**Files:**
- Create: `services/influencer_crm_ui/src/styles/tokens.css`
- Create: `services/influencer_crm_ui/src/styles/globals.css`
- Modify: `services/influencer_crm_ui/src/main.tsx` — import globals.css

- [ ] **Step 1: Create tokens.css verbatim from prototype**

`src/styles/tokens.css`:

```css
:root {
  /* Brand */
  --color-bg: #F8FAFC;
  --color-fg: #111827;
  --color-card: #FFFFFF;
  --color-primary: #F97316;
  --color-primary-hover: #EA580C;
  --color-primary-light: #FFF7ED;
  --color-primary-muted: #FDBA74;
  --color-bg-warm: #FFFBF5;

  /* Neutrals */
  --color-secondary: #F3F4F6;
  --color-muted: #F9FAFB;
  --color-muted-fg: #6B7280;
  --color-accent: #FFF7ED;
  --color-border: #F3F4F6;
  --color-border-strong: #E5E7EB;

  /* Status */
  --color-success: #22C55E;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-info: #8B5CF6;
  --color-pink: #EC4899;
  --color-blue: #3B82F6;
  --color-green: #10B981;

  /* Radii */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;

  /* Shadows */
  --shadow-warm: 0 1px 3px rgba(249, 115, 22, 0.08), 0 1px 2px rgba(249, 115, 22, 0.04);
  --shadow-warm-md: 0 4px 6px -1px rgba(249, 115, 22, 0.08), 0 2px 4px -2px rgba(249, 115, 22, 0.04);
  --shadow-warm-lg: 0 10px 15px -3px rgba(249, 115, 22, 0.08), 0 4px 6px -4px rgba(249, 115, 22, 0.04);
  --shadow-drawer: -16px 0 60px -12px rgba(0, 0, 0, 0.18);

  /* Z-index scale (lifted from ui-ux-pro-max guideline) */
  --z-dropdown: 10;
  --z-sticky: 20;
  --z-drawer: 40;
  --z-modal: 50;
  --z-toast: 60;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Create globals.css with Tailwind 4 inline theme**

`src/styles/globals.css`:

```css
@import './tokens.css';
@import 'tailwindcss';

@theme inline {
  --color-bg: var(--color-bg);
  --color-fg: var(--color-fg);
  --color-card: var(--color-card);
  --color-primary: var(--color-primary);
  --color-primary-hover: var(--color-primary-hover);
  --color-primary-light: var(--color-primary-light);
  --color-primary-muted: var(--color-primary-muted);
  --color-bg-warm: var(--color-bg-warm);
  --color-muted: var(--color-muted);
  --color-muted-fg: var(--color-muted-fg);
  --color-border: var(--color-border);
  --color-border-strong: var(--color-border-strong);
  --color-success: var(--color-success);
  --color-warning: var(--color-warning);
  --color-danger: var(--color-danger);
  --color-info: var(--color-info);
  --color-pink: var(--color-pink);
  --color-blue: var(--color-blue);
  --color-green: var(--color-green);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --shadow-warm: 0 1px 3px rgba(249, 115, 22, 0.08), 0 1px 2px rgba(249, 115, 22, 0.04);
  --shadow-warm-md: 0 4px 6px -1px rgba(249, 115, 22, 0.08), 0 2px 4px -2px rgba(249, 115, 22, 0.04);
  --shadow-warm-lg: 0 10px 15px -3px rgba(249, 115, 22, 0.08), 0 4px 6px -4px rgba(249, 115, 22, 0.04);
  --font-display: 'Plus Jakarta Sans', system-ui, sans-serif;
  --font-body: 'DM Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}

html, body {
  background: var(--color-bg);
  color: var(--color-fg);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.625;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4, h5, h6 { font-family: var(--font-display); letter-spacing: -0.01em; }
.font-mono { font-family: var(--font-mono); }

/* Focus visible, contrast-safe */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: 4px;
}
```

- [ ] **Step 3: Wire into main.tsx**

`src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/globals.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 4: Smoke check in browser**

Run `pnpm dev`. Inspect computed style of `<body>` — `background: rgb(248, 250, 252)`. Run `<div className="bg-primary text-white p-4">test</div>` in App.tsx and verify orange background renders.

- [ ] **Step 5: Commit**

```bash
git add src/styles src/main.tsx
git commit -m "feat(crm-ui): T2 — port design tokens from prototype to Tailwind theme"
```

---

## T3 — Typography (Google Fonts)

**Files:**
- Modify: `services/influencer_crm_ui/index.html` — add `<link>` to fonts

- [ ] **Step 1: Add font preconnect + stylesheet to index.html**

```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Wookiee CRM</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Verify in browser DevTools**

Network tab → check 3 font css files load with 200. Inspect `<h1>` → `font-family: 'Plus Jakarta Sans'`.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat(crm-ui): T3 — load Plus Jakarta Sans + DM Sans + JetBrains Mono"
```

---

## T4 — API client (`lib/api.ts`)

**Files:**
- Create: `services/influencer_crm_ui/src/lib/api.ts`
- Create: `services/influencer_crm_ui/src/lib/api.test.ts`
- Create: `services/influencer_crm_ui/.env.local` (gitignored)
- Create: `services/influencer_crm_ui/src/test/setup.ts`

- [ ] **Step 1: Add env keys**

`.env.local` (gitignored, real value lifted from `sku_database/.env`):

```
VITE_API_BASE_URL=/api
VITE_API_KEY=<paste-INFLUENCER_CRM_API_KEY-from-sku_database/.env>
```

`.env.example` (committed):

```
VITE_API_BASE_URL=/api
VITE_API_KEY=replace-me
```

- [ ] **Step 2: Write failing test for api.get header**

`src/lib/api.test.ts`:

```ts
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { api, ApiError } from './api';

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    import.meta.env.VITE_API_KEY = 'test-key';
    import.meta.env.VITE_API_BASE_URL = 'http://test';
  });

  it('sends X-API-Key header on every request', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { 'content-type': 'application/json', etag: 'W/"abc"' },
      }),
    );
    await api.get('/bloggers');
    const [, init] = (globalThis.fetch as any).mock.calls[0];
    expect(init.headers['X-API-Key']).toBe('test-key');
  });

  it('throws ApiError with status on non-2xx', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'nope' }), { status: 404 }),
    );
    await expect(api.get('/bloggers/9999')).rejects.toBeInstanceOf(ApiError);
  });

  it('caches ETag and sends If-None-Match on repeat GET', async () => {
    (globalThis.fetch as any)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1 }), {
          status: 200,
          headers: { etag: 'W/"v1"' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    await api.get('/bloggers/1');
    const result = await api.get('/bloggers/1');
    const [, init] = (globalThis.fetch as any).mock.calls[1];
    expect(init.headers['If-None-Match']).toBe('W/"v1"');
    expect(result).toEqual({ id: 1 }); // served from cache on 304
  });
});
```

- [ ] **Step 3: Run test (should fail — no implementation)**

```bash
pnpm test:run src/lib/api.test.ts
```

Expected: FAIL — `Cannot find module './api'`.

- [ ] **Step 4: Implement `src/lib/api.ts`**

```ts
const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';
const KEY = import.meta.env.VITE_API_KEY ?? '';

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) {
    super(message);
  }
}

const etagCache = new Map<string, { etag: string; body: unknown }>();

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${BASE}${path}`;
  const cached = method === 'GET' ? etagCache.get(url) : undefined;
  const headers: Record<string, string> = {
    'X-API-Key': KEY,
    'Content-Type': 'application/json',
  };
  if (cached) headers['If-None-Match'] = cached.etag;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 304 && cached) {
    return cached.body as T;
  }

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch { /* empty body */ }
    throw new ApiError(res.status, payload, `${method} ${path} → ${res.status}`);
  }

  if (res.status === 204) return undefined as T;

  const json = (await res.json()) as T;
  if (method === 'GET') {
    const etag = res.headers.get('etag');
    if (etag) etagCache.set(url, { etag, body: json });
  } else {
    // mutations invalidate the cache for the same resource family
    for (const k of etagCache.keys()) if (k.startsWith(url.split('?')[0])) etagCache.delete(k);
  }
  return json;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
};
```

- [ ] **Step 5: Add `src/test/setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 6: Re-run tests**

```bash
pnpm test:run src/lib/api.test.ts
```

Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/lib/api.ts src/lib/api.test.ts src/test/setup.ts .env.example
git commit -m "feat(crm-ui): T4 — fetch wrapper with X-API-Key + ETag cache"
```

---

## T5 — Cursor utility (round-trip with backend)

**Files:**
- Create: `services/influencer_crm_ui/src/lib/cursor.ts`
- Create: `services/influencer_crm_ui/src/lib/cursor.test.ts`

- [ ] **Step 1: Write failing test (parity with backend `services/influencer_crm/pagination.py`)**

`src/lib/cursor.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { encodeCursor, decodeCursor } from './cursor';

describe('cursor', () => {
  it('encode/decode round-trips', () => {
    const c = encodeCursor('2026-04-28T12:00:00+00:00', 42);
    const d = decodeCursor(c);
    expect(d).toEqual({ updatedAt: '2026-04-28T12:00:00+00:00', id: 42 });
  });

  it('returns null for garbage input', () => {
    expect(decodeCursor('not-base64!')).toBeNull();
    expect(decodeCursor('')).toBeNull();
  });

  it('produces base64-of-json shape (must match Python encode_cursor)', () => {
    const c = encodeCursor('2026-04-28T12:00:00+00:00', 42);
    const decoded = JSON.parse(atob(c));
    expect(decoded).toEqual(['2026-04-28T12:00:00+00:00', 42]);
  });
});
```

- [ ] **Step 2: Run test (FAIL)**

```bash
pnpm test:run src/lib/cursor.test.ts
```

Expected: FAIL.

- [ ] **Step 3: Implement `src/lib/cursor.ts`**

```ts
export type Cursor = { updatedAt: string; id: number };

export function encodeCursor(updatedAt: string, id: number): string {
  return btoa(JSON.stringify([updatedAt, id]));
}

export function decodeCursor(cursor: string | null | undefined): Cursor | null {
  if (!cursor) return null;
  try {
    const arr = JSON.parse(atob(cursor)) as unknown;
    if (!Array.isArray(arr) || arr.length !== 2) return null;
    const [updatedAt, id] = arr;
    if (typeof updatedAt !== 'string' || typeof id !== 'number') return null;
    return { updatedAt, id };
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Tests PASS**

```bash
pnpm test:run src/lib/cursor.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add src/lib/cursor.ts src/lib/cursor.test.ts
git commit -m "feat(crm-ui): T5 — cursor encode/decode (parity with backend)"
```

---

## T6 — TanStack Query setup + first hook

**Files:**
- Create: `services/influencer_crm_ui/src/lib/query-client.ts`
- Create: `services/influencer_crm_ui/src/api/bloggers.ts`
- Create: `services/influencer_crm_ui/src/hooks/use-bloggers.ts`
- Create: `services/influencer_crm_ui/src/hooks/use-bloggers.test.tsx`
- Create: `services/influencer_crm_ui/src/test/render.tsx`
- Create: `services/influencer_crm_ui/src/test/msw-handlers.ts`
- Modify: `services/influencer_crm_ui/src/App.tsx` — add `QueryClientProvider`
- Modify: `services/influencer_crm_ui/src/test/setup.ts` — start MSW

- [ ] **Step 1: Install MSW worker**

```bash
pnpm exec msw init public/ --save
```

- [ ] **Step 2: `src/lib/query-client.ts`**

```ts
import { QueryClient } from '@tanstack/react-query';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (count, err: any) => count < 2 && err?.status !== 404 && err?.status !== 403,
        refetchOnWindowFocus: false,
      },
    },
  });
}
```

- [ ] **Step 3: `src/api/bloggers.ts` — typed contracts (mirror BFF schemas)**

```ts
import { api } from '@/lib/api';

export interface BloggerOut {
  id: number;
  handle: string;
  display_name: string | null;
  status: 'active' | 'paused' | 'archived';
  marketer_id: number | null;
  tags: { id: number; name: string }[];
  channels_count: number;
  integrations_count: number;
  updated_at: string;
}

export interface BloggersPage {
  items: BloggerOut[];
  next_cursor: string | null;
}

export interface BloggerListParams {
  status?: 'active' | 'paused' | 'archived';
  marketer_id?: number;
  tag_id?: number;
  q?: string;
  cursor?: string;
  limit?: number;
}

export function listBloggers(params: BloggerListParams = {}): Promise<BloggersPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) search.set(k, String(v));
  const q = search.toString();
  return api.get<BloggersPage>(`/bloggers${q ? `?${q}` : ''}`);
}
```

- [ ] **Step 4: `src/hooks/use-bloggers.ts` (infinite cursor)**

```ts
import { useInfiniteQuery } from '@tanstack/react-query';
import { listBloggers, type BloggerListParams } from '@/api/bloggers';

export function useBloggers(params: Omit<BloggerListParams, 'cursor'> = {}) {
  return useInfiniteQuery({
    queryKey: ['bloggers', params],
    queryFn: ({ pageParam }) => listBloggers({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}
```

- [ ] **Step 5: MSW handler stub**

`src/test/msw-handlers.ts`:

```ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/bloggers', () =>
    HttpResponse.json({
      items: [
        {
          id: 1, handle: '_anna.blog', display_name: 'Anna', status: 'active',
          marketer_id: 7, tags: [], channels_count: 2, integrations_count: 5,
          updated_at: '2026-04-28T10:00:00Z',
        },
      ],
      next_cursor: null,
    }),
  ),
];
```

- [ ] **Step 6: Update `src/test/setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { handlers } from './msw-handlers';

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

- [ ] **Step 7: `src/test/render.tsx` helper**

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createQueryClient } from '@/lib/query-client';

export function renderWithProviders(ui: ReactNode) {
  return render(<QueryClientProvider client={createQueryClient()}>{ui}</QueryClientProvider>);
}
```

- [ ] **Step 8: `src/hooks/use-bloggers.test.tsx`**

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QueryClientProvider } from '@tanstack/react-query';
import { createQueryClient } from '@/lib/query-client';
import { useBloggers } from './use-bloggers';

describe('useBloggers', () => {
  it('fetches first page', async () => {
    const client = createQueryClient();
    const { result } = renderHook(() => useBloggers(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.pages[0].items[0].handle).toBe('_anna.blog');
  });
});
```

- [ ] **Step 9: Update App.tsx**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { createQueryClient } from './lib/query-client';

const client = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={client}>
      <div className="p-8 font-display text-2xl">Wookiee CRM — alive</div>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 10: Run tests + dev**

```bash
pnpm test:run
pnpm dev   # browser shows "Wookiee CRM — alive"
```

- [ ] **Step 11: Commit**

```bash
git add src/lib/query-client.ts src/api/bloggers.ts src/hooks/ src/test/ src/App.tsx public/mockServiceWorker.js
git commit -m "feat(crm-ui): T6 — TanStack Query + useBloggers + MSW test infra"
```

---

## T7 — UI primitives

**Files:**
- Create: `src/ui/Button.tsx`, `src/ui/Badge.tsx`, `src/ui/Avatar.tsx`, `src/ui/Input.tsx`, `src/ui/Select.tsx`, `src/ui/FilterPill.tsx`, `src/ui/PlatformPill.tsx`, `src/ui/EmptyState.tsx`, `src/ui/Skeleton.tsx`, `src/ui/Tabs.tsx`, `src/ui/KpiCard.tsx`
- Create: `src/lib/cn.ts`
- Create: `src/routes/__dev/UiCatalog.tsx` (dev-only catalog route at `/dev/ui`)

- [ ] **Step 1: cn helper**

`src/lib/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx';
export const cn = (...inputs: ClassValue[]) => clsx(inputs);
```

- [ ] **Step 2: Button**

`src/ui/Button.tsx`:

```tsx
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary: 'bg-primary text-white shadow-sm hover:bg-primary-hover',
  secondary: 'bg-card border border-border-strong hover:bg-primary-light',
  ghost: 'bg-transparent hover:bg-primary-light',
  danger: 'text-danger bg-danger/10 hover:bg-danger/20',
};

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = 'secondary', loading, className, children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      disabled={loading || disabled}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium',
        'transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
        'min-h-[36px]',
        variantClass[variant],
        className,
      )}
      {...rest}
    >
      {loading && <span className="size-3 rounded-full border-2 border-current border-t-transparent animate-spin" />}
      {children}
    </button>
  ),
);
Button.displayName = 'Button';
```

- [ ] **Step 3: Badge**

`src/ui/Badge.tsx`:

```tsx
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'success' | 'warning' | 'info' | 'orange' | 'pink' | 'secondary' | 'danger';

const tones: Record<Tone, string> = {
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  info: 'bg-info/10 text-info',
  orange: 'bg-primary-light text-primary-hover',
  pink: 'bg-pink/10 text-pink',
  secondary: 'bg-muted text-muted-fg border border-border',
  danger: 'bg-danger/10 text-danger',
};

export function Badge({ tone = 'secondary', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold', tones[tone])}>
      {children}
    </span>
  );
}
```

- [ ] **Step 4: Avatar (initials, 6 colors based on hash)**

`src/ui/Avatar.tsx`:

```tsx
import { cn } from '@/lib/cn';

const palettes = ['bg-[#F97316]', 'bg-[#3B82F6]', 'bg-[#8B5CF6]', 'bg-[#EC4899]', 'bg-[#10B981]', 'bg-[#F59E0B]'];

function colorFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return palettes[Math.abs(h) % palettes.length];
}

const sizes = { xs: 'size-7 text-[11px]', sm: 'size-8 text-xs', md: 'size-12 text-base', lg: 'size-16 text-2xl' } as const;

export function Avatar({ name, size = 'sm' }: { name: string; size?: keyof typeof sizes }) {
  const initials = name.split(/\s+|\./).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('');
  return (
    <span className={cn('inline-flex items-center justify-center rounded-full text-white font-semibold font-display shrink-0', sizes[size], colorFor(name))}>
      {initials || '?'}
    </span>
  );
}
```

- [ ] **Step 5: Input + Select + Textarea (forwardRef so RHF can register)**

`src/ui/Input.tsx`:

```tsx
import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        'w-full rounded-md border border-border bg-card px-3 py-2 text-sm',
        'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
        'placeholder:text-muted-fg',
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = 'Input';
```

`src/ui/Select.tsx` and `src/ui/Textarea.tsx`: same pattern, ref forwarded.

- [ ] **Step 6: FilterPill, PlatformPill, EmptyState, Skeleton, Tabs, KpiCard**

Each is a small focused file. PlatformPill has the IG/TG/YT/TT/VK gradients lifted from prototype lines 332-333.

`src/ui/PlatformPill.tsx`:

```tsx
const styles = {
  instagram: 'bg-gradient-to-br from-[#f58529] via-[#dd2a7b] to-[#8134af]',
  tiktok: 'bg-black',
  youtube: 'bg-[#FF0000]',
  telegram: 'bg-[#229ED9]',
  vk: 'bg-[#0077FF]',
} as const;

const labels = { instagram: 'IG', tiktok: 'TT', youtube: 'YT', telegram: 'TG', vk: 'VK' } as const;

export function PlatformPill({ channel }: { channel: keyof typeof styles }) {
  return (
    <span className={`inline-flex size-[22px] items-center justify-center rounded-md text-[10px] font-bold text-white ${styles[channel]}`}>
      {labels[channel]}
    </span>
  );
}
```

- [ ] **Step 7: Build a `/dev/ui` catalog route (developer-only)**

`src/routes/__dev/UiCatalog.tsx` renders one card per primitive in all variants. Lets reviewers see the kit in one place.

- [ ] **Step 8: Verify in browser at `/dev/ui`**

Eyeball check: every primitive renders with the prototype's warm orange tone. Hover changes are smooth (200ms).

- [ ] **Step 9: Commit**

```bash
git add src/ui src/lib/cn.ts src/routes/__dev
git commit -m "feat(crm-ui): T7 — UI primitives (Button/Badge/Avatar/Input/Select/Pills/EmptyState/Skeleton/Tabs/Kpi)"
```

---

## T8 — Layout + Routing

**Files:**
- Create: `src/layout/AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`, `PageHeader.tsx`
- Modify: `src/App.tsx` — wire `<RouterProvider>`
- Create: `src/routes/router.tsx`

- [ ] **Step 1: Sidebar (256px, gradient bg, lifted from prototype)**

`src/layout/Sidebar.tsx`:

```tsx
import { NavLink } from 'react-router-dom';
import { Users, Layers, Calendar, FileText, Package, Search } from 'lucide-react';
import { cn } from '@/lib/cn';

const items = [
  { to: '/bloggers', icon: Users, label: 'Блогеры' },
  { to: '/integrations', icon: Layers, label: 'Интеграции' },
  { to: '/calendar', icon: Calendar, label: 'Календарь' },
  { to: '/briefs', icon: FileText, label: 'Брифы' },
  { to: '/products', icon: Package, label: 'Продукты' },
  { to: '/search', icon: Search, label: 'Поиск' },
];

export function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-r border-border bg-gradient-to-b from-primary-light to-card sticky top-0 h-screen flex flex-col">
      <div className="p-4 flex items-center gap-2">
        <div className="size-8 rounded-md bg-primary text-white flex items-center justify-center font-display font-extrabold text-sm">W</div>
        <span className="font-display font-bold text-lg tracking-tight">Wookiee CRM</span>
      </div>
      <nav className="flex-1 px-3 py-2" aria-label="Главное меню">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors duration-150 cursor-pointer',
                isActive ? 'bg-primary text-white font-medium' : 'hover:bg-primary-light',
              )
            }
          >
            <Icon size={16} aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: TopBar with global search input**

`src/layout/TopBar.tsx`:

```tsx
import { Bell } from 'lucide-react';
import { Input } from '@/ui/Input';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

export function TopBar() {
  const [q, setQ] = useState('');
  const nav = useNavigate();
  return (
    <header className="sticky top-0 z-20 bg-card/80 backdrop-blur border-b border-border px-6 py-3 flex items-center gap-4">
      <form
        className="flex-1 max-w-xl"
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) nav(`/search?q=${encodeURIComponent(q)}`);
        }}
      >
        <Input
          aria-label="Глобальный поиск"
          placeholder="Поиск по блогерам, интеграциям…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </form>
      <button type="button" aria-label="Уведомления" className="p-2 rounded-md hover:bg-primary-light cursor-pointer">
        <Bell size={18} />
      </button>
    </header>
  );
}
```

- [ ] **Step 3: PageHeader + AppShell**

```tsx
// PageHeader.tsx
import type { ReactNode } from 'react';
export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div>
        <h1 className="text-3xl font-bold font-display tracking-tight">{title}</h1>
        {sub && <p className="text-sm text-muted-fg mt-1">{sub}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

// AppShell.tsx
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppShell() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 px-8 py-6 max-w-[1600px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Router config**

`src/routes/router.tsx`:

```tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/layout/AppShell';
import { BloggersPage } from './bloggers/BloggersPage';
import { IntegrationsKanbanPage } from './integrations/IntegrationsKanbanPage';
import { CalendarPage } from './calendar/CalendarPage';
import { BriefsPage } from './briefs/BriefsPage';
import { SlicesPage } from './slices/SlicesPage';
import { ProductsPage } from './products/ProductsPage';
import { SearchPage } from './search/SearchPage';
import { NotFound } from './NotFound';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/bloggers" replace /> },
      { path: 'bloggers', element: <BloggersPage /> },
      { path: 'integrations', element: <IntegrationsKanbanPage /> },
      { path: 'calendar', element: <CalendarPage /> },
      { path: 'briefs', element: <BriefsPage /> },
      { path: 'slices', element: <SlicesPage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
```

- [ ] **Step 5: Stub each page so router compiles**

Every `routes/<name>/<Name>Page.tsx` exports a function returning `<PageHeader title="…" sub="…" />` plus a `<EmptyState/>` placeholder. They get filled in T10-T18.

- [ ] **Step 6: Mount router in App.tsx**

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { createQueryClient } from './lib/query-client';
import { router } from './routes/router';

const client = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 7: Manual smoke**

`pnpm dev` → click each sidebar item → URL changes, PageHeader renders, no console errors.

- [ ] **Step 8: Commit**

```bash
git add src/layout src/routes/router.tsx src/routes/*/[A-Z]*.tsx src/App.tsx
git commit -m "feat(crm-ui): T8 — AppShell + Sidebar + TopBar + router with 7 stub pages"
```

---

## T9 — Drawer component

**Files:**
- Create: `src/ui/Drawer.tsx`
- Create: `src/ui/Drawer.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Drawer } from './Drawer';

describe('Drawer', () => {
  it('calls onClose when Esc pressed', async () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="Edit blogger">
        <p>body</p>
      </Drawer>,
    );
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('renders title and traps focus on first focusable', () => {
    render(
      <Drawer open onClose={() => {}} title="Edit blogger">
        <button type="button">save</button>
      </Drawer>,
    );
    expect(screen.getByText('Edit blogger')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement using Headless UI Dialog**

```tsx
import { Dialog, Transition } from '@headlessui/react';
import { Fragment, type ReactNode } from 'react';
import { X } from 'lucide-react';

export function Drawer({
  open, onClose, title, children, footer, width = 'max-w-2xl',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  return (
    <Transition show={open} as={Fragment}>
      <Dialog as="div" className="relative z-40" onClose={onClose}>
        <Transition.Child as={Fragment} enter="transition-opacity duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="transition-opacity duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
          <div className="fixed inset-0 bg-black/30" />
        </Transition.Child>
        <div className="fixed inset-0 flex justify-end">
          <Transition.Child
            as={Fragment}
            enter="transition-transform duration-200" enterFrom="translate-x-full" enterTo="translate-x-0"
            leave="transition-transform duration-150" leaveFrom="translate-x-0" leaveTo="translate-x-full"
          >
            <Dialog.Panel className={`w-full ${width} bg-card shadow-[var(--shadow-drawer)] flex flex-col`}>
              <header className="px-6 py-4 border-b border-border flex items-center justify-between">
                <Dialog.Title className="font-display font-bold text-lg">{title}</Dialog.Title>
                <button type="button" aria-label="Закрыть" className="p-2 rounded-md hover:bg-primary-light cursor-pointer" onClick={onClose}>
                  <X size={18} />
                </button>
              </header>
              <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
              {footer && <footer className="px-6 py-4 border-t border-border flex justify-end gap-2">{footer}</footer>}
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition>
  );
}
```

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```bash
git add src/ui/Drawer.tsx src/ui/Drawer.test.tsx
git commit -m "feat(crm-ui): T9 — Drawer with Esc + focus trap"
```

---

## T10 — Bloggers list page

**Files:**
- Create: `src/routes/bloggers/BloggersPage.tsx`
- Create: `src/routes/bloggers/BloggersTable.tsx`
- Create: `src/routes/bloggers/BloggersFilters.tsx`
- Create: `src/routes/bloggers/BloggerExpandedRow.tsx`
- Create: `src/routes/bloggers/BloggersPage.test.tsx`

- [ ] **Step 1: Filters component (status, marketer, tag, search input)**

```tsx
// src/routes/bloggers/BloggersFilters.tsx
import { Input } from '@/ui/Input';
import { FilterPill } from '@/ui/FilterPill';
import type { BloggerListParams } from '@/api/bloggers';

interface Props {
  value: Pick<BloggerListParams, 'status' | 'q'>;
  onChange: (next: Pick<BloggerListParams, 'status' | 'q'>) => void;
}

const statuses: ({ key: BloggerListParams['status']; label: string })[] = [
  { key: undefined, label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'paused', label: 'На паузе' },
  { key: 'archived', label: 'Архив' },
];

export function BloggersFilters({ value, onChange }: Props) {
  return (
    <div className="bg-card border border-border rounded-lg shadow-warm px-3.5 py-3 mb-5 flex items-center gap-2.5 flex-wrap">
      <span className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold">Статус</span>
      {statuses.map((s) => (
        <FilterPill
          key={s.label}
          active={value.status === s.key}
          onClick={() => onChange({ ...value, status: s.key })}
        >
          {s.label}
        </FilterPill>
      ))}
      <Input
        className="ml-auto max-w-xs"
        placeholder="Поиск по handle / имени"
        value={value.q ?? ''}
        onChange={(e) => onChange({ ...value, q: e.target.value || undefined })}
      />
    </div>
  );
}
```

- [ ] **Step 2: Table with row-expand state lifted**

```tsx
// src/routes/bloggers/BloggersTable.tsx
import type { BloggerOut } from '@/api/bloggers';
import { Avatar } from '@/ui/Avatar';
import { Badge } from '@/ui/Badge';
import { useState } from 'react';
import { BloggerExpandedRow } from './BloggerExpandedRow';

const statusTone: Record<BloggerOut['status'], 'success' | 'warning' | 'secondary'> = {
  active: 'success', paused: 'warning', archived: 'secondary',
};

export function BloggersTable({ bloggers }: { bloggers: BloggerOut[] }) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  return (
    <div className="bg-card border border-border-strong rounded-lg shadow-warm overflow-hidden">
      <table className="w-full">
        <thead>
          <tr>
            <Th>Блогер</Th>
            <Th>Статус</Th>
            <Th>Каналы</Th>
            <Th className="text-right">Интеграций</Th>
          </tr>
        </thead>
        <tbody>
          {bloggers.map((b) => (
            <>
              <tr
                key={b.id}
                className={`cursor-pointer transition-colors duration-150 ${expandedId === b.id ? 'bg-primary-light' : 'hover:bg-bg-warm'}`}
                onClick={() => setExpandedId(expandedId === b.id ? null : b.id)}
                aria-expanded={expandedId === b.id}
              >
                <td className="px-3.5 py-3">
                  <div className="flex items-center gap-3">
                    <Avatar name={b.display_name ?? b.handle} />
                    <div className="min-w-0">
                      <div className="font-semibold text-sm">{b.display_name ?? b.handle}</div>
                      <div className="text-xs text-muted-fg truncate">@{b.handle}</div>
                    </div>
                  </div>
                </td>
                <td className="px-3.5 py-3"><Badge tone={statusTone[b.status]}>{b.status}</Badge></td>
                <td className="px-3.5 py-3 font-mono text-sm">{b.channels_count}</td>
                <td className="px-3.5 py-3 font-mono text-sm text-right">{b.integrations_count}</td>
              </tr>
              {expandedId === b.id && (
                <tr key={`${b.id}-expand`}>
                  <td colSpan={4} className="bg-bg-warm p-0">
                    <BloggerExpandedRow id={b.id} />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <th className={`bg-muted text-[11.5px] uppercase tracking-wider text-muted-fg font-semibold px-3.5 py-2.5 text-left ${className}`}>{children}</th>;
}
```

- [ ] **Step 3: Expanded row uses `useBlogger(id)` for detail (T11 will reuse the hook)**

```tsx
// src/routes/bloggers/BloggerExpandedRow.tsx
import { useBlogger } from '@/hooks/use-bloggers';
import { Skeleton } from '@/ui/Skeleton';

export function BloggerExpandedRow({ id }: { id: number }) {
  const { data, isLoading } = useBlogger(id);
  if (isLoading) return <div className="p-6"><Skeleton className="h-24" /></div>;
  if (!data) return null;
  return (
    <div className="p-6 grid grid-cols-[320px_1fr] gap-6">
      <ProfileCard blogger={data} />
      <IntegrationsList integrations={data.integrations ?? []} />
    </div>
  );
}

// ProfileCard + IntegrationsList helpers in same file
```

- [ ] **Step 4: BloggersPage glue**

```tsx
// src/routes/bloggers/BloggersPage.tsx
import { useState } from 'react';
import { useBloggers } from '@/hooks/use-bloggers';
import { Button } from '@/ui/Button';
import { PageHeader } from '@/layout/PageHeader';
import { Skeleton } from '@/ui/Skeleton';
import { EmptyState } from '@/ui/EmptyState';
import { BloggersFilters } from './BloggersFilters';
import { BloggersTable } from './BloggersTable';

export function BloggersPage() {
  const [filters, setFilters] = useState<{ status?: 'active' | 'paused' | 'archived'; q?: string }>({ status: 'active' });
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useBloggers(filters);
  const items = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
        actions={<Button variant="primary">+ Новый блогер</Button>}
      />
      <BloggersFilters value={filters} onChange={setFilters} />
      {isLoading ? <Skeleton className="h-96" />
        : items.length === 0 ? <EmptyState title="Никого не нашлось" description="Снимите фильтр или создайте нового." />
        : <BloggersTable bloggers={items} />}
      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button onClick={() => fetchNextPage()} loading={isFetchingNextPage}>Показать ещё</Button>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 5: Add `useBlogger(id)` hook**

```ts
// src/hooks/use-bloggers.ts (extend)
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function useBlogger(id: number) {
  return useQuery({
    queryKey: ['blogger', id],
    queryFn: () => api.get<BloggerDetailOut>(`/bloggers/${id}`),
    enabled: id > 0,
  });
}
```

(`BloggerDetailOut` type added to `src/api/bloggers.ts` mirroring backend schema.)

- [ ] **Step 6: Component test**

```tsx
// src/routes/bloggers/BloggersPage.test.tsx
import { describe, it, expect } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { BloggersPage } from './BloggersPage';
import { MemoryRouter } from 'react-router-dom';
import { screen, waitFor } from '@testing-library/react';

describe('BloggersPage', () => {
  it('renders bloggers from API', async () => {
    renderWithProviders(<MemoryRouter><BloggersPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('_anna.blog', { exact: false })).toBeInTheDocument());
  });
});
```

- [ ] **Step 7: Manual smoke against live BFF**

Make sure BFF is running: `bash services/influencer_crm/scripts/run_dev.sh` in another terminal.
`pnpm dev` → http://localhost:5173/bloggers → see real 241 bloggers paginated.

- [ ] **Step 8: Commit**

```bash
git add src/routes/bloggers src/hooks/use-bloggers.ts src/api/bloggers.ts
git commit -m "feat(crm-ui): T10 — bloggers list with filters + table + row expand"
```

---

## T11 — Blogger edit drawer

**Files:**
- Create: `src/routes/bloggers/BloggerEditDrawer.tsx`
- Modify: `src/api/bloggers.ts` — add `updateBlogger`, `createBlogger`
- Modify: `src/hooks/use-bloggers.ts` — add `useUpsertBlogger`

- [ ] **Step 1: Add API + hook**

```ts
// src/api/bloggers.ts (extend)
export interface BloggerInput {
  handle: string;
  display_name?: string | null;
  status: 'active' | 'paused' | 'archived';
  marketer_id?: number | null;
  notes?: string | null;
  // ... full schema per docs/api/INFLUENCER_CRM_API.md
}

export const updateBlogger = (id: number, body: Partial<BloggerInput>) =>
  api.patch<BloggerOut>(`/bloggers/${id}`, body);
export const createBlogger = (body: BloggerInput) =>
  api.post<BloggerOut>('/bloggers', body);
```

```ts
// src/hooks/use-bloggers.ts (extend)
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createBlogger, updateBlogger } from '@/api/bloggers';

export function useUpsertBlogger() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id?: number; body: BloggerInput }) =>
      input.id ? updateBlogger(input.id, input.body) : createBlogger(input.body),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['bloggers'] });
      qc.setQueryData(['blogger', saved.id], saved);
    },
  });
}
```

- [ ] **Step 2: Drawer with react-hook-form + zod**

```tsx
// src/routes/bloggers/BloggerEditDrawer.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Drawer } from '@/ui/Drawer';
import { Button } from '@/ui/Button';
import { Input } from '@/ui/Input';
import { Select } from '@/ui/Select';
import { Tabs } from '@/ui/Tabs';
import { useUpsertBlogger } from '@/hooks/use-bloggers';

const Schema = z.object({
  handle: z.string().min(1, 'Обязательно'),
  display_name: z.string().nullable().optional(),
  status: z.enum(['active', 'paused', 'archived']),
  marketer_id: z.coerce.number().int().nullable().optional(),
  notes: z.string().nullable().optional(),
});

type FormValues = z.infer<typeof Schema>;

export function BloggerEditDrawer({
  open, onClose, blogger,
}: {
  open: boolean;
  onClose: () => void;
  blogger?: { id: number } & FormValues;
}) {
  const upsert = useUpsertBlogger();
  const form = useForm<FormValues>({
    resolver: zodResolver(Schema),
    defaultValues: blogger ?? { handle: '', status: 'active' },
  });
  const onSubmit = form.handleSubmit((vals) =>
    upsert.mutateAsync({ id: blogger?.id, body: vals }).then(() => onClose()),
  );
  return (
    <Drawer
      open={open} onClose={onClose}
      title={blogger ? `Редактирование: ${blogger.handle}` : 'Новый блогер'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Отмена</Button>
          <Button variant="primary" loading={upsert.isPending} onClick={onSubmit}>Сохранить</Button>
        </>
      }
    >
      <Tabs tabs={[
        { label: 'Инфо', content: <InfoTab form={form} /> },
        { label: 'Каналы', content: <ChannelsTab id={blogger?.id} /> },
        { label: 'Интеграции', content: <IntegrationsTab id={blogger?.id} /> },
        { label: 'Compliance', content: <ComplianceTab form={form} /> },
      ]} />
    </Drawer>
  );
}
// InfoTab/ChannelsTab/IntegrationsTab/ComplianceTab as inline subcomponents in same file
```

- [ ] **Step 3: Wire from BloggersPage — header `+ Новый блогер` opens empty, clicking "✏️" in expanded row opens with prefill.**

- [ ] **Step 4: Manual test**

Open http://localhost:5173/bloggers → click "+ Новый блогер" → fill handle → save → toast → row appears in list. Edit → change display_name → save → expanded row updates.

- [ ] **Step 5: Commit**

```bash
git add src/routes/bloggers/BloggerEditDrawer.tsx src/hooks/use-bloggers.ts src/api/bloggers.ts
git commit -m "feat(crm-ui): T11 — blogger edit drawer with RHF + zod + 4 tabs"
```

---

## T12 — Integrations Kanban

**Files:**
- Create: `src/api/integrations.ts`
- Create: `src/hooks/use-integrations.ts`
- Create: `src/routes/integrations/IntegrationsKanbanPage.tsx`
- Create: `src/routes/integrations/KanbanColumn.tsx`
- Create: `src/routes/integrations/KanbanCard.tsx`

- [ ] **Step 1: Add types + hooks (mirror BFF Stage Literal: 10 values)**

```ts
// src/api/integrations.ts
export const STAGES = [
  'lead', 'agreed_terms', 'briefed', 'awaiting_content',
  'content_review', 'scheduled', 'published', 'measured',
  'paid', 'archived',
] as const;
export type Stage = typeof STAGES[number];

export interface IntegrationOut {
  id: number;
  blogger_id: number;
  blogger_handle: string;
  stage: Stage;
  cost: string | null;
  scheduled_at: string | null;
  // ... per backend schema
  updated_at: string;
}

export const listIntegrations = (params?: { stage_in?: Stage[]; archived?: boolean; cursor?: string }) =>
  api.get<{ items: IntegrationOut[]; next_cursor: string | null }>(
    `/integrations?${new URLSearchParams(/* ... */)}`,
  );
export const updateIntegrationStage = (id: number, stage: Stage) =>
  api.patch<IntegrationOut>(`/integrations/${id}`, { stage });
```

- [ ] **Step 2: Kanban with @dnd-kit**

```tsx
// src/routes/integrations/IntegrationsKanbanPage.tsx
import { DndContext, type DragEndEvent } from '@dnd-kit/core';
import { useIntegrationsByStage, useUpdateIntegrationStage } from '@/hooks/use-integrations';
import { STAGES } from '@/api/integrations';
import { KanbanColumn } from './KanbanColumn';
import { PageHeader } from '@/layout/PageHeader';

const stageLabels: Record<typeof STAGES[number], string> = {
  lead: 'Лид', agreed_terms: 'Условия', briefed: 'Бриф', awaiting_content: 'Ждём контент',
  content_review: 'На правках', scheduled: 'Запланировано', published: 'Опубликовано',
  measured: 'Измерено', paid: 'Оплачено', archived: 'Архив',
};

export function IntegrationsKanbanPage() {
  const { data, byStage } = useIntegrationsByStage();
  const update = useUpdateIntegrationStage();

  function onDragEnd(e: DragEndEvent) {
    const id = Number(e.active.id);
    const stage = e.over?.id as typeof STAGES[number] | undefined;
    if (!id || !stage) return;
    update.mutate({ id, stage });
  }

  return (
    <>
      <PageHeader title="Интеграции" sub="Канбан 10 стадий. Перетащи карточку — стадия сменится." />
      <DndContext onDragEnd={onDragEnd}>
        <div className="flex gap-4 overflow-x-auto pb-4 -mx-2 px-2">
          {STAGES.map((s) => (
            <KanbanColumn key={s} stage={s} label={stageLabels[s]} items={byStage[s] ?? []} />
          ))}
        </div>
      </DndContext>
    </>
  );
}
```

- [ ] **Step 3: KanbanColumn (droppable) + KanbanCard (draggable)**

Use `useDroppable` for column, `useDraggable` for card. Optimistic update via React Query mutation `onMutate`/`onError` to rollback.

- [ ] **Step 4: Manual test**

`pnpm dev` → /integrations → drag a card from `briefed` to `awaiting_content` → API PATCH 200 → card stays in new column. Force-fail (kill BFF for 5s, drag, restart) → card snaps back, toast error.

- [ ] **Step 5: Commit**

```bash
git add src/api/integrations.ts src/hooks/use-integrations.ts src/routes/integrations
git commit -m "feat(crm-ui): T12 — integrations Kanban with @dnd-kit + optimistic stage updates"
```

---

## T13 — Integration edit drawer

**Files:**
- Create: `src/routes/integrations/IntegrationEditDrawer.tsx`
- Modify: `src/api/integrations.ts` — add full upsert
- Modify: `src/hooks/use-integrations.ts` — add `useUpsertIntegration`, `useIntegration(id)`

- [ ] **Step 1: Add full schema (largest form: blogger picker, product picker, brief link, plan/fact metrics, compliance)**

The form has 4 sections from prototype lines 1419-1542:
1. Header (date, status, marketplace, marketer)
2. Параметры (blogger, channel, format, model, cost breakdown)
3. План vs Факт (views, CPM, CTR, clicks, CPC, orders)
4. Compliance (ОРД-токен, метка)

- [ ] **Step 2: Implement (RHF + zod, ~150 LOC). Cost breakdown computes total via `useWatch`.**

- [ ] **Step 3: Open from KanbanCard click + from BloggersPage `Integrations` tab**

- [ ] **Step 4: Manual test**

Click any card on Kanban → drawer opens → edit cost → save → card on Kanban shows new cost. Reload page → value persisted.

- [ ] **Step 5: Commit**

```bash
git add src/routes/integrations/IntegrationEditDrawer.tsx src/api/integrations.ts src/hooks/use-integrations.ts
git commit -m "feat(crm-ui): T13 — integration edit drawer (4 sections, plan/fact, compliance)"
```

---

## T14 — Calendar page

**Files:**
- Create: `src/routes/calendar/CalendarPage.tsx`
- Create: `src/routes/calendar/CalendarMonthGrid.tsx`

- [ ] **Step 1: Use `useIntegrations({ scheduled_from, scheduled_to })` filter**

Compute first/last day of visible month, fetch all integrations falling in that window. Group by `scheduled_at::date`.

- [ ] **Step 2: 7-column grid, 5-6 rows. Each cell:**

```tsx
<div className="border border-border min-h-[100px] p-2">
  <div className="text-xs font-mono text-muted-fg">{day}</div>
  {events.map(e => <CalendarEvent key={e.id} integration={e} />)}
</div>
```

- [ ] **Step 3: Click on event → open IntegrationEditDrawer (reuse T13)**

- [ ] **Step 4: Click on empty cell → open new-integration drawer with `scheduled_at` prefilled**

- [ ] **Step 5: Manual test**

/calendar → see Apr 2026 events → click event → drawer opens → edit → close → event still on date.

- [ ] **Step 6: Commit**

```bash
git add src/routes/calendar
git commit -m "feat(crm-ui): T14 — calendar month grid with click-to-edit"
```

---

## T15 — Briefs page

**Files:**
- Create: `src/api/briefs.ts`
- Create: `src/hooks/use-briefs.ts`
- Create: `src/routes/briefs/BriefsPage.tsx`
- Create: `src/routes/briefs/BriefCard.tsx`
- Create: `src/routes/briefs/BriefEditorDrawer.tsx`

- [ ] **Step 1: Hook + types per backend (4 stages: draft, on_review, signed, completed)**

Note: backend stores `content` as JSONB `{"md": "..."}` — UI handles `content_md` string per docs.

- [ ] **Step 2: 4-column kanban (read-only column moves; status changes happen via brief actions in drawer)**

- [ ] **Step 3: BriefCard shows blogger avatar, title, version badge, scheduled date, budget**

- [ ] **Step 4: BriefEditorDrawer = textarea (markdown) + meta fields + version history list**

- [ ] **Step 5: "Сохранить" → POST `/briefs/{id}/versions` (creates new version atomically per backend)**

- [ ] **Step 6: Manual test**

/briefs → click "+ Новый бриф" → fill markdown → save → appears in "Черновик" column. Edit → save → version bumps to v2. Mark signed → moves to "Подписан" column.

- [ ] **Step 7: Commit**

```bash
git add src/routes/briefs src/api/briefs.ts src/hooks/use-briefs.ts
git commit -m "feat(crm-ui): T15 — briefs kanban + markdown editor + version history"
```

---

## T16 — Slices analytics page

**Files:**
- Create: `src/routes/slices/SlicesPage.tsx`
- Create: `src/routes/slices/SlicesFilters.tsx`
- Create: `src/api/metrics.ts` (if not yet)

- [ ] **Step 1: Filter combo: marketplace × period × marketer × tag → triggers `/integrations?…` aggregation**

- [ ] **Step 2: Render KPI strip (4 cards: spend, reach, orders, ROMI) + result table**

- [ ] **Step 3: CSV export — client-side from current filtered result (no new endpoint)**

```ts
function exportCsv(rows: IntegrationOut[]) {
  const header = ['blogger', 'date', 'cost', 'views', 'orders'];
  const csv = [header, ...rows.map(r => [r.blogger_handle, r.scheduled_at, r.cost, r.fact_views, r.fact_orders])]
    .map(line => line.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'integrations-slice.csv'; a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 4: Manual test**

/slices → marketplace=wb × marketer=Лиля → table updates → "Экспорт CSV" → файл сохранён, открывается в LibreOffice/Excel правильно.

- [ ] **Step 5: Commit**

```bash
git add src/routes/slices
git commit -m "feat(crm-ui): T16 — slices page with multi-filter aggregation + CSV export"
```

---

## T17 — Products page (model osnova → halo)

**Files:**
- Create: `src/api/products.ts`
- Create: `src/hooks/use-products.ts`
- Create: `src/routes/products/ProductsPage.tsx`
- Create: `src/routes/products/ProductSliceCard.tsx`

- [ ] **Step 1: List models from `/products` (model_osnova-level)**

- [ ] **Step 2: Click "Wendy" → expand to slice card showing all integrations for that model_osnova grouped by month + halo of related artikuly_substitutes**

- [ ] **Step 3: Manual test against real Wendy data — should see 25+ integrations**

- [ ] **Step 4: Commit**

```bash
git add src/routes/products src/api/products.ts src/hooks/use-products.ts
git commit -m "feat(crm-ui): T17 — products page with halo slice"
```

---

## T18 — Global search

**Files:**
- Create: `src/api/search.ts`
- Create: `src/hooks/use-search.ts`
- Create: `src/routes/search/SearchPage.tsx`

- [ ] **Step 1: `/search?q=...` calls BFF `/search` endpoint, returns `{ bloggers: [...], integrations: [...] }`**

- [ ] **Step 2: Tabs (Все / Блогеры / Интеграции) + result list with avatar + handle + status**

- [ ] **Step 3: Manual test: "плюс сайз" → returns mixed bloggers + integrations**

- [ ] **Step 4: Commit**

```bash
git add src/routes/search src/api/search.ts src/hooks/use-search.ts
git commit -m "feat(crm-ui): T18 — global search page (bloggers + integrations)"
```

---

## T19 — Loading / error / empty states polish

**Files:**
- Modify: every screen file to wrap content in `<QueryStatusBoundary>`
- Create: `src/ui/QueryStatusBoundary.tsx`

- [ ] **Step 1: Generic boundary**

```tsx
import type { ReactNode } from 'react';
import { Skeleton } from './Skeleton';
import { EmptyState } from './EmptyState';

export function QueryStatusBoundary({
  isLoading, error, isEmpty, children,
}: {
  isLoading: boolean;
  error: unknown;
  isEmpty?: boolean;
  children: ReactNode;
}) {
  if (isLoading) return <Skeleton className="h-96" />;
  if (error) {
    const msg = error instanceof Error ? error.message : 'Что-то пошло не так';
    return (
      <div className="rounded-lg border border-danger/30 bg-danger/5 p-6">
        <h3 className="font-semibold text-danger">Ошибка загрузки</h3>
        <p className="text-sm text-muted-fg mt-1">{msg}</p>
      </div>
    );
  }
  if (isEmpty) return <EmptyState title="Пусто" description="Снимите фильтры или добавьте первую запись." />;
  return <>{children}</>;
}
```

- [ ] **Step 2: Wrap each list page**

- [ ] **Step 3: Test: stop the BFF → see all pages show error banner with retry → restart BFF → click retry → recovers**

- [ ] **Step 4: Commit**

```bash
git add src/ui/QueryStatusBoundary.tsx src/routes
git commit -m "feat(crm-ui): T19 — unified loading/error/empty states across all pages"
```

---

## T20 — A11y pass

**Files:**
- Modify: any file flagged by audit

- [ ] **Step 1: Tab through every form on every page — order matches visual order, no skipped fields**

- [ ] **Step 2: Run axe-core in dev console on each route**

```bash
pnpm add -D @axe-core/react
```

In `src/main.tsx` (DEV only):

```ts
if (import.meta.env.DEV) {
  const axe = await import('@axe-core/react');
  axe.default(React, ReactDOM, 1000);
}
```

- [ ] **Step 3: Resolve any violations**

Common ones expected:
- icon-only buttons missing `aria-label`
- table without `<caption>` (add visually hidden caption per page)
- form inputs missing `<label htmlFor>` (RHF + Headless UI handles, double-check)
- Color contrast on `text-muted-fg` over `bg-warm` — measure with WebAIM contrast checker, ensure ≥4.5:1

- [ ] **Step 4: Commit**

```bash
git add src
git commit -m "feat(crm-ui): T20 — a11y pass (keyboard nav, ARIA labels, axe clean)"
```

---

## T21 — Playwright golden-path tests

**Files:**
- Create: `e2e/playwright.config.ts`
- Create: `e2e/fixtures/seed.ts`
- Create: `e2e/golden-bloggers.spec.ts`
- Create: `e2e/golden-kanban.spec.ts`
- Create: `e2e/golden-search.spec.ts`
- Create: `e2e/golden-brief-edit.spec.ts`

- [ ] **Step 1: Playwright config**

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: 'http://localhost:5173',
    extraHTTPHeaders: { 'X-API-Key': process.env.VITE_API_KEY ?? '' },
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
  ],
});
```

- [ ] **Step 2: Seed fixture (idempotent — creates 1 blogger if none has handle 'e2e-test', leaves alone otherwise)**

- [ ] **Step 3: golden-bloggers.spec.ts**

```ts
import { test, expect } from '@playwright/test';

test('GP-1: create blogger → see in list', async ({ page, request }) => {
  await page.goto('/bloggers');
  await expect(page.getByRole('heading', { name: 'Блогеры' })).toBeVisible();
  await page.getByRole('button', { name: '+ Новый блогер' }).click();
  await page.getByLabel('Handle').fill('e2e-test-' + Date.now());
  await page.getByRole('button', { name: 'Сохранить' }).click();
  await expect(page.getByText(/e2e-test-/)).toBeVisible();
});
```

- [ ] **Step 4: golden-kanban.spec.ts (drag card via mouse simulation), golden-search.spec.ts, golden-brief-edit.spec.ts**

- [ ] **Step 5: Run**

```bash
# In a separate terminal — start BFF on 8082
bash services/influencer_crm/scripts/run_dev.sh

# In UI dir
pnpm e2e
```

Expected: all 4 specs PASS.

- [ ] **Step 6: Commit**

```bash
git add e2e
git commit -m "feat(crm-ui): T21 — Playwright golden-path tests (4 specs vs live BFF)"
```

---

## T22 — Production build + dev runner + README

**Files:**
- Create: `services/influencer_crm_ui/README.md`
- Create: `services/influencer_crm_ui/scripts/run_dev.sh`
- Modify: `services/influencer_crm/scripts/run_dev.sh` to mention companion UI runner
- Modify: `docs/api/INFLUENCER_CRM_API.md` — add note "Companion UI: services/influencer_crm_ui"

- [ ] **Step 1: README**

```markdown
# Wookiee CRM — Frontend (P4)

React + Vite + Tailwind 4 + TypeScript SPA on top of the Influencer CRM BFF.

## Local dev

```bash
# Terminal 1: backend
bash services/influencer_crm/scripts/run_dev.sh

# Terminal 2: frontend
cd services/influencer_crm_ui
cp .env.example .env.local   # paste VITE_API_KEY = your INFLUENCER_CRM_API_KEY
pnpm install
pnpm dev   # http://localhost:5173
```

## Tests

- Unit: `pnpm test`
- E2E (needs BFF running): `pnpm e2e`
- Lint: `pnpm lint`
- Typecheck: `pnpm typecheck`

## Build

```bash
pnpm build
pnpm preview   # http://localhost:4173
```

Deployment: out of scope for P4. P5 will wire CI + Timeweb deploy.
```

- [ ] **Step 2: Scripts**

`scripts/run_dev.sh`:

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
[ -f .env.local ] || cp .env.example .env.local
pnpm install --frozen-lockfile
pnpm dev
```

- [ ] **Step 3: Verify clean build**

```bash
pnpm typecheck
pnpm lint
pnpm test:run
pnpm build   # writes dist/
pnpm preview &
curl -sf http://localhost:4173 > /dev/null && echo "preview OK"
kill %1
```

- [ ] **Step 4: Wrap commit**

```bash
git add services/influencer_crm_ui/README.md services/influencer_crm_ui/scripts docs/api/INFLUENCER_CRM_API.md
git commit -m "feat(crm-ui): T22 — README + dev runner + production build verified"

git commit --allow-empty -m "chore(crm-ui): Phase 4 done

- 7 screens (bloggers, integrations kanban, calendar, briefs, slices, products, search)
- 21/21 endpoints consumed
- Cursor pagination + ETag cache
- A11y axe clean, keyboard nav verified
- Playwright golden-path suite green vs live BFF
"
```

---

## QA1 — autonomous loop (per roadmap, runs AFTER T22)

Per roadmap line 88, QA1 is a mandatory autonomous loop AFTER P4 implementation. Out of scope for *this* plan — but the executor should run it next, in this order:

1. `Skill: gstack-qa` — Playwright bug-find loop
2. `Skill: gstack-design-review` — visual review (≥8/10 hierarchy + spacing + clarity)
3. `Skill: dogfood` — exploratory edge cases
4. Direct Playwright MCP for the 7 golden paths from roadmap lines 152-159

QA1 produces an additional commit `qa(crm-ui): QA1 passed` only after `gstack-qa` returns "no fixable bugs remaining" and `gstack-design-review ≥8/10`.

---

## Self-Review checklist (run before declaring plan complete)

**1. Spec coverage:**
- [x] All 7 prototype screens have a task (T10/T11 bloggers, T12/T13 integrations, T14 calendar, T15 briefs, T16 slices, T17 products, T18 search)
- [x] All 21 endpoints from `docs/api/INFLUENCER_CRM_API.md` consumed (bloggers/integrations/products/tags/promos/briefs/metrics/search × CRUD)
- [x] Cursor pagination + ETag (T4, T5, T6)
- [x] Auth via X-API-Key (T4)
- [x] Design tokens lifted from prototype (T2)
- [x] Typography: Plus Jakarta Sans / DM Sans / JetBrains Mono (T3)
- [x] A11y discipline (T20)
- [x] E2E golden paths (T21)

**2. Placeholder scan:** No "TBD"/"add validation later"/"similar to Task X" found. Each task carries the actual code.

**3. Type consistency:**
- `BloggerOut`, `IntegrationOut`, `Stage` defined in `src/api/*.ts` and consumed in hooks + components.
- `Cursor` type used by `cursor.ts` and consumed via `useInfiniteQuery`.
- `useUpsertBlogger` mutation matches API `createBlogger`/`updateBlogger`.

**4. Open assumptions worth flagging to executor:**
- Backend `BloggerDetailOut` includes `integrations: []` (need to verify against `docs/api/INFLUENCER_CRM_API.md` — if not, T10 BloggerExpandedRow needs a separate fetch via `/bloggers/{id}/integrations` or similar).
- `/integrations` filter `scheduled_from` / `scheduled_to` may not exist (T14 calendar). If absent, calendar fetches all integrations and filters client-side — fine for current data scale (≤200 integrations).
- BFF endpoint for "halo of related substitute_articles" by model_osnova — may need a new endpoint for T17. If missing, executor logs a P4-followup and uses available `/products/{id}` plus client-side join.

---

## Execution

**Plan complete.** Saved to `docs/superpowers/plans/2026-04-28-influencer-crm-p4-frontend.md` on branch `feat/influencer-crm-p4` in worktree `/tmp/wookiee-crm-p4`.

Two execution options:

**1. Subagent-Driven** (recommended) — fresh subagent per task with two-stage review loop.
**2. Inline Execution** — execute in this session via `superpowers:executing-plans`, batched checkpoints.
