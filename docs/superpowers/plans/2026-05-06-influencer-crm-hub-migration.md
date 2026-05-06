# Influencer CRM → Wookiee Hub Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перенести страницы Influencer CRM (блогеры, интеграции, календарь) из `services/influencer_crm_ui/` в Hub (`wookiee-hub/`), чтобы они открывались по `/influence/*` на `hub.os.wookiee.shop`, а FastAPI BFF (`crm.matveevdanila.com`) работал только как API.

**Architecture:**
Hub вызывает BFF через отдельный CRM API-клиент с `X-API-Key` заголовком. CRM UI-компоненты переносятся в `wookiee-hub/src/components/crm/` с минимальными правками (только пути импортов). CSS-токены CRM (`fg`, `muted-fg`, `primary-light`, `success`, `danger` и др.) добавляются в `wookiee-hub/src/index.css` как алиасы существующих Hub-токенов, чтобы CRM-компоненты работали без массовых переписываний классов.

**Tech Stack:** React 19, React Router 7, TanStack Query v5, @dnd-kit/core, react-hook-form, zod, Radix UI Dialog (для Drawer), shadcn/ui, Tailwind 4, FastAPI + CORS middleware, Caddy

---

## Files Map

### Создать в wookiee-hub/src

```
lib/
  crm-api.ts               API-клиент для BFF (X-API-Key, ETag кэш)
api/crm/
  bloggers.ts              Типы + API-функции для блогеров
  integrations.ts          Типы + API-функции для интеграций
hooks/crm/
  use-bloggers.ts          React Query хуки для блогеров
  use-integrations.ts      React Query хуки для интеграций
components/crm/
  ui/
    Avatar.tsx             Аватар с инициалами
    Badge.tsx              Бейдж с tone-вариантами (success/warning/danger/info/pink/secondary)
    Button.tsx             Кнопка с loading-состоянием
    Drawer.tsx             Slide-over (Radix Dialog, НЕ Headless UI)
    EmptyState.tsx         Пустое состояние
    FilterPill.tsx         Фильтр-пилюля
    Input.tsx              Инпут
    PlatformPill.tsx       Значок платформы (IG/TG/TT/YT/VK)
    QueryStatusBoundary.tsx Loading/error/empty обёртка
    Select.tsx             Native <select>
    Skeleton.tsx           Skeleton-плейсхолдер
    Tabs.tsx               Таб-панель
    Textarea.tsx           Textarea
  layout/
    PageHeader.tsx         Заголовок страницы (title + sub + actions)
pages/influence/
  bloggers/
    BloggersPage.tsx
    BloggersTable.tsx
    BloggersFilters.tsx
    BloggerEditDrawer.tsx
    BloggerExpandedRow.tsx
  integrations/
    IntegrationsKanbanPage.tsx
    KanbanColumn.tsx
    KanbanCard.tsx
    IntegrationEditDrawer.tsx
  calendar/
    CalendarPage.tsx
    CalendarMonthGrid.tsx
```

### Изменить

| Файл | Что меняется |
|---|---|
| `wookiee-hub/package.json` | Добавить 6 зависимостей |
| `wookiee-hub/src/main.tsx` | Обернуть в QueryClientProvider |
| `wookiee-hub/src/index.css` | Добавить CRM compat-токены в @theme inline + :root + .dark |
| `wookiee-hub/src/config/navigation.ts` | Добавить группу "Influence CRM" |
| `wookiee-hub/src/router.tsx` | Добавить маршруты /influence/* |
| `services/influencer_crm/app.py` | Добавить CORSMiddleware для hub.os.wookiee.shop |
| `deploy/Dockerfile.influencer_crm_api` | Удалить SPA build stage (Phase 3) |

---

## Phase 1: Hub Foundation

### Task 1: Установить зависимости и добавить QueryClientProvider

**Files:**
- Modify: `wookiee-hub/package.json`
- Modify: `wookiee-hub/src/main.tsx`

- [ ] **Step 1.1: Добавить зависимости в package.json**

Открыть `wookiee-hub/package.json`. В секцию `"dependencies"` добавить:
```json
"@tanstack/react-query": "^5.0.0",
"@dnd-kit/core": "^6.0.0",
"@dnd-kit/utilities": "^3.2.0",
"react-hook-form": "^7.0.0",
"@hookform/resolvers": "^3.0.0",
"zod": "^3.0.0"
```

- [ ] **Step 1.2: Установить зависимости**

```bash
cd wookiee-hub
npm install
```
Expected: package-lock.json обновится, `node_modules/@tanstack/react-query/` появится.

- [ ] **Step 1.3: Обернуть приложение в QueryClientProvider**

Текущий `wookiee-hub/src/main.tsx`:
```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router-dom"
import { router } from "./router"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
)
```

Заменить на:
```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { router } from "./router"
import "./index.css"

const queryClient = new QueryClient()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>
)
```

- [ ] **Step 1.4: Проверить TypeScript**

```bash
cd wookiee-hub
npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 1.5: Commit**

```bash
git add wookiee-hub/package.json wookiee-hub/package-lock.json wookiee-hub/src/main.tsx
git commit -m "feat(hub): add react-query, dnd-kit, react-hook-form, zod deps"
```

---

### Task 2: Добавить CRM CSS compat-токены в Hub

**Files:**
- Modify: `wookiee-hub/src/index.css`

Контекст: CRM-компоненты используют Tailwind-классы типа `text-fg`, `text-muted-fg`, `bg-primary-light`, `bg-success`, `text-danger` и т.д. В Hub эти классы не существуют (Hub использует `text-foreground`, `text-muted-foreground` и т.д.). Нужно добавить CSS-переменные и `@theme inline` алиасы.

- [ ] **Step 2.1: Добавить CSS-переменные в :root (light mode)**

В `wookiee-hub/src/index.css` найти блок `:root {` и добавить перед закрывающей `}` строки:
```css
    /* CRM compat — required by ported Influencer CRM components */
    --crm-primary-light: oklch(0.490 0.250 292 / 0.12);
    --crm-primary-hover: oklch(0.420 0.240 292);
    --crm-primary-muted: oklch(0.760 0.120 292);
    --crm-border-strong: oklch(0.870 0.006 285);
    --crm-bg-warm: oklch(0.985 0.002 285);
    --crm-surface: oklch(1 0 0);
```

- [ ] **Step 2.2: Добавить CSS-переменные в .dark**

В `wookiee-hub/src/index.css` найти блок `.dark {` и добавить перед закрывающей `}` строки:
```css
    /* CRM compat — dark mode */
    --crm-primary-light: oklch(0.541 0.232 292 / 0.15);
    --crm-primary-hover: oklch(0.620 0.240 292);
    --crm-primary-muted: oklch(0.400 0.150 292);
    --crm-border-strong: oklch(0.250 0.012 275);
    --crm-bg-warm: oklch(0.094 0.005 285);
    --crm-surface: oklch(0.150 0.008 285);
```

- [ ] **Step 2.3: Добавить @theme inline алиасы**

В `wookiee-hub/src/index.css` найти существующий блок `@theme inline {` и добавить перед закрывающей `}`:
```css
    /* CRM compat aliases */
    --color-fg: var(--foreground);
    --color-muted-fg: var(--muted-foreground);
    --color-primary-light: var(--crm-primary-light);
    --color-primary-hover: var(--crm-primary-hover);
    --color-primary-muted: var(--crm-primary-muted);
    --color-border-strong: var(--crm-border-strong);
    --color-bg-warm: var(--crm-bg-warm);
    --color-surface: var(--crm-surface);
    --color-success: var(--wk-green);
    --color-warning: var(--wk-yellow);
    --color-danger: var(--wk-red);
    --color-info: var(--wk-blue);
    --color-pink: var(--wk-pink);
    --shadow-warm: var(--shadow-xs);
```

- [ ] **Step 2.4: Проверить сборку**

```bash
cd wookiee-hub
npm run build 2>&1 | tail -20
```
Expected: Build succeeded без ошибок.

- [ ] **Step 2.5: Commit**

```bash
git add wookiee-hub/src/index.css
git commit -m "feat(hub): add CRM compat CSS tokens for component migration"
```

---

### Task 3: Добавить navigation group + skeleton routes

**Files:**
- Modify: `wookiee-hub/src/config/navigation.ts`
- Modify: `wookiee-hub/src/router.tsx`
- Create: `wookiee-hub/src/pages/influence/bloggers/BloggersPage.tsx` (skeleton)
- Create: `wookiee-hub/src/pages/influence/integrations/IntegrationsKanbanPage.tsx` (skeleton)
- Create: `wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx` (skeleton)

- [ ] **Step 3.1: Добавить influence группу в navigation.ts**

Текущий `wookiee-hub/src/config/navigation.ts`:
```ts
import {
  MessageSquare,
  LayoutGrid,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  Activity,
  Clock,
} from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "operations",
    ...
  },
  {
    id: "community",
    ...
  },
]
```

Заменить на (добавить импорт `Users2, Kanban, CalendarDays` и группу):
```ts
import {
  MessageSquare,
  LayoutGrid,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  Activity,
  Clock,
  Users2,
  Kanban,
  CalendarDays,
} from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "operations",
    icon: LayoutGrid,
    label: "Операции",
    items: [
      { id: "tools",    label: "Каталог инструментов", icon: LayoutGrid, path: "/operations/tools" },
      { id: "activity", label: "История запусков",      icon: Activity,  path: "/operations/activity", badge: "Фаза 2" },
      { id: "health",   label: "Состояние системы",     icon: Clock,     path: "/operations/health",   badge: "Фаза 2" },
    ],
  },
  {
    id: "community",
    icon: MessageSquare,
    label: "Коммуникации",
    items: [
      { id: "reviews",   label: "Отзывы",    icon: Star,         path: "/community/reviews" },
      { id: "questions", label: "Вопросы",   icon: HelpCircle,   path: "/community/questions" },
      { id: "answers",   label: "Ответы",    icon: CheckCircle2, path: "/community/answers" },
      { id: "analytics", label: "Аналитика", icon: BarChart3,    path: "/community/analytics" },
    ],
  },
  {
    id: "influence",
    icon: Users2,
    label: "Influence CRM",
    items: [
      { id: "bloggers",      label: "Блогеры",    icon: Users2,       path: "/influence/bloggers" },
      { id: "integrations",  label: "Интеграции", icon: Kanban,       path: "/influence/integrations" },
      { id: "calendar",      label: "Календарь",  icon: CalendarDays, path: "/influence/calendar" },
    ],
  },
]
```

- [ ] **Step 3.2: Создать skeleton-страницу BloggersPage**

Создать файл `wookiee-hub/src/pages/influence/bloggers/BloggersPage.tsx`:
```tsx
export function BloggersPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-foreground">Блогеры</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Загрузка...</p>
      </div>
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  )
}
```

- [ ] **Step 3.3: Создать skeleton IntegrationsKanbanPage**

Создать `wookiee-hub/src/pages/influence/integrations/IntegrationsKanbanPage.tsx`:
```tsx
export function IntegrationsKanbanPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-foreground">Интеграции</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Загрузка...</p>
      </div>
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  )
}
```

- [ ] **Step 3.4: Создать skeleton CalendarPage**

Создать `wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx`:
```tsx
export function CalendarPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-foreground">Календарь публикаций</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Загрузка...</p>
      </div>
      <div className="h-96 rounded-xl bg-muted animate-pulse" />
    </div>
  )
}
```

- [ ] **Step 3.5: Добавить маршруты в router.tsx**

Текущий `wookiee-hub/src/router.tsx` (верхняя часть с импортами, строки 1-11):
```tsx
import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { LoginPage } from "@/pages/auth/login"
import { ToolsPage } from "@/pages/operations/tools"
import { ActivityPage } from "@/pages/operations/activity"
import { ReviewsPage } from "@/pages/community/reviews"
import { QuestionsPage } from "@/pages/community/questions"
import { AnswersPage } from "@/pages/community/answers"
import { AnalyticsPage } from "@/pages/community/analytics"
```

Добавить после последнего импорта:
```tsx
import { BloggersPage } from "@/pages/influence/bloggers/BloggersPage"
import { IntegrationsKanbanPage } from "@/pages/influence/integrations/IntegrationsKanbanPage"
import { CalendarPage } from "@/pages/influence/calendar/CalendarPage"
```

В массиве `children` после последнего маршрута (`/community/analytics`) добавить:
```tsx
      { path: "/influence",             element: <Navigate to="/influence/bloggers" replace /> },
      { path: "/influence/bloggers",    element: <BloggersPage /> },
      { path: "/influence/integrations",element: <IntegrationsKanbanPage /> },
      { path: "/influence/calendar",    element: <CalendarPage /> },
```

- [ ] **Step 3.6: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 3.7: Запустить dev-сервер и проверить навигацию**

```bash
cd wookiee-hub && npm run dev
```
Открыть http://localhost:5173. В иконбаре должна появиться новая кнопка Influence CRM (Users2-иконка). Клик → subsidebar с 3 пунктами. Навигация по /influence/bloggers → skeleton.

- [ ] **Step 3.8: Commit**

```bash
git add wookiee-hub/src/config/navigation.ts wookiee-hub/src/router.tsx \
  wookiee-hub/src/pages/influence/
git commit -m "feat(hub): add Influence CRM navigation group and skeleton routes"
```

---

### Task 4: Деплой Phase 1 на сервер

- [ ] **Step 4.1: Собрать Hub**

```bash
cd wookiee-hub && npm run build
```
Expected: `dist/` папка создана, 0 ошибок.

- [ ] **Step 4.2: Задеплоить**

```bash
ssh timeweb "cd /home/danila/projects/wookiee && git pull && cd wookiee-hub && npm ci && npm run build && cp -r dist/* /srv/hub/"
```

- [ ] **Step 4.3: Проверить через Playwright**

```bash
cd wookiee-hub && npx playwright open https://hub.os.wookiee.shop/influence/bloggers
```
Expected: страница загружается, skeleton виден, иконбар показывает группу Influence CRM.

---

### Task 4b: Убрать Продукты и Поиск из старого CRM sidebar

**Files:**
- Modify: `services/influencer_crm_ui/src/layout/Sidebar.tsx`

Контекст: Продукты и Поиск — устаревшие страницы, которые не переносятся в Hub. Убираем из навигации CRM-сайта, чтобы не путать пользователей. Сам CRM-сайт исчезнет в Phase 3 (SPAStaticFiles удалим), но до тех пор навигация должна быть чистой.

- [ ] **Step 4b.1: Убрать products и search из items**

В `services/influencer_crm_ui/src/layout/Sidebar.tsx` заменить массив `items`:
```ts
const items: NavItem[] = [
  { to: '/bloggers',     icon: Users,    label: 'Блогеры' },
  { to: '/integrations', icon: Layers,   label: 'Интеграции' },
  { to: '/calendar',     icon: Calendar, label: 'Календарь' },
  { to: '/briefs',       icon: FileText, label: 'Брифы' },
  { to: '/ops',          icon: Activity, label: 'Ops' },
]
```

Также удалить неиспользуемые импорты `Package` и `Search` из lucide-react.

- [ ] **Step 4b.2: Commit**

```bash
git add services/influencer_crm_ui/src/layout/Sidebar.tsx
git commit -m "feat(crm-ui): remove Products and Search from sidebar nav"
```

Примечание: Редеплой старого CRM (docker compose build + up) потребуется если нужно сразу убрать из прода. Можно отложить до деплоя Phase 2 (Task 14), чтобы не делать лишнюю пересборку.

---

## Phase 2: Data Layer

### Task 5: Создать CRM API-клиент

**Files:**
- Create: `wookiee-hub/src/lib/crm-api.ts`

Контекст: Hub уже имеет `api-client.ts` (без X-API-Key). Нужен отдельный клиент для BFF с X-API-Key и ETag-кэшем (аналог `services/influencer_crm_ui/src/lib/api.ts`). Базовый URL и ключ берутся из `VITE_CRM_API_URL` и `VITE_CRM_API_KEY`.

- [ ] **Step 5.1: Создать crm-api.ts**

Создать `wookiee-hub/src/lib/crm-api.ts`:
```ts
const getBase = (): string => import.meta.env.VITE_CRM_API_URL ?? 'https://crm.matveevdanila.com/api'
const getKey = (): string => import.meta.env.VITE_CRM_API_KEY ?? ''

export class CrmApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message: string,
  ) {
    super(message)
  }
}

const etagCache = new Map<string, { etag: string; body: unknown }>()

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${getBase()}${path}`
  const cached = method === 'GET' ? etagCache.get(url) : undefined
  const headers: Record<string, string> = {
    'X-API-Key': getKey(),
    'Content-Type': 'application/json',
  }
  if (cached) headers['If-None-Match'] = cached.etag

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 304 && cached) {
    return cached.body as T
  }

  if (!res.ok) {
    let payload: unknown = null
    try { payload = await res.json() } catch { /* empty */ }
    throw new CrmApiError(res.status, payload, `${method} ${path} → ${res.status}`)
  }

  if (res.status === 204) return undefined as T

  const json = (await res.json()) as T
  if (method === 'GET') {
    const etag = res.headers.get('etag')
    if (etag) etagCache.set(url, { etag, body: json })
  } else {
    const family = url.replace(/\/\d+$/, '').split('?')[0]
    for (const k of etagCache.keys()) {
      if (k.startsWith(family)) etagCache.delete(k)
    }
  }
  return json
}

export const crmApi = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
}
```

- [ ] **Step 5.2: Добавить env vars в .env.example**

В `.env.example` в корне проекта добавить (если файл существует):
```
VITE_CRM_API_URL=https://crm.matveevdanila.com/api
VITE_CRM_API_KEY=
```

- [ ] **Step 5.3: Добавить env vars в wookiee-hub/.env.local**

Создать или обновить `wookiee-hub/.env.local` (gitignored):
```
VITE_CRM_API_URL=https://crm.matveevdanila.com/api
VITE_CRM_API_KEY=<значение INFLUENCER_CRM_API_KEY из .env>
```

Ключ найти в `/home/danila/projects/wookiee/.env` на сервере или в локальном `.env`.

- [ ] **Step 5.4: Commit**

```bash
git add wookiee-hub/src/lib/crm-api.ts
git commit -m "feat(hub): add CRM API client (X-API-Key + ETag)"
```

---

### Task 6: Перенести типы API

**Files:**
- Create: `wookiee-hub/src/api/crm/bloggers.ts`
- Create: `wookiee-hub/src/api/crm/integrations.ts`

Контекст: Это точные копии из `services/influencer_crm_ui/src/api/bloggers.ts` и `integrations.ts`, с одним изменением: `import { api }` → `import { crmApi }` и все вызовы `api.get/post/patch` → `crmApi.get/post/patch`.

- [ ] **Step 6.1: Создать wookiee-hub/src/api/crm/bloggers.ts**

```ts
import { crmApi } from '@/lib/crm-api'

export type BloggerStatus = 'active' | 'in_progress' | 'new' | 'paused'

export interface BloggerOut {
  id: number
  display_handle: string
  real_name: string | null
  status: BloggerStatus
  default_marketer_id: number | null
  price_story_default: string | null
  price_reels_default: string | null
  created_at: string | null
  updated_at: string | null
}

export interface BloggerChannelOut {
  id: number
  channel: string
  handle: string
  url: string | null
}

export interface BloggerDetailOut extends BloggerOut {
  channels: BloggerChannelOut[]
  integrations_count: number
  integrations_done: number
  last_integration_at: string | null
  total_spent: string
  avg_cpm_fact: string | null
  contact_tg: string | null
  contact_email: string | null
  contact_phone: string | null
  notes: string | null
  geo_country: string[] | null
}

export interface BloggersPage {
  items: BloggerOut[]
  next_cursor: string | null
}

export interface BloggerListParams {
  status?: BloggerStatus
  marketer_id?: number
  tag_id?: number
  q?: string
  cursor?: string
  limit?: number
}

export function listBloggers(params: BloggerListParams = {}): Promise<BloggersPage> {
  const search = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v))
  }
  const q = search.toString()
  return crmApi.get<BloggersPage>(`/bloggers${q ? `?${q}` : ''}`)
}

export function getBlogger(id: number): Promise<BloggerDetailOut> {
  return crmApi.get<BloggerDetailOut>(`/bloggers/${id}`)
}

export interface BloggerInput {
  display_handle: string
  real_name?: string | null
  status?: BloggerStatus
  default_marketer_id?: number | null
  price_story_default?: string | null
  price_reels_default?: string | null
  contact_tg?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  notes?: string | null
}

export function createBlogger(body: BloggerInput): Promise<BloggerOut> {
  return crmApi.post<BloggerOut>('/bloggers', body)
}

export function updateBlogger(id: number, body: Partial<BloggerInput>): Promise<BloggerOut> {
  return crmApi.patch<BloggerOut>(`/bloggers/${id}`, body)
}
```

- [ ] **Step 6.2: Создать wookiee-hub/src/api/crm/integrations.ts**

Скопировать `services/influencer_crm_ui/src/api/integrations.ts` в `wookiee-hub/src/api/crm/integrations.ts` и заменить:
- Строку `import { api } from '@/lib/api'` → `import { crmApi } from '@/lib/crm-api'`
- Все вхождения `api.get<` → `crmApi.get<`
- Все вхождения `api.post<` → `crmApi.post<`
- Все вхождения `api.patch<` → `crmApi.patch<`

Примечание: `STAGES`, все интерфейсы (`IntegrationOut`, `IntegrationDetailOut`, `IntegrationUpdate`, `IntegrationInput`, `IntegrationsPage`, `IntegrationListParams`), `STAGE_LABELS`, и функции `listIntegrations`, `getIntegration`, `createIntegration`, `updateIntegration` — всё остаётся идентичным.

- [ ] **Step 6.3: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 6.4: Commit**

```bash
git add wookiee-hub/src/api/crm/
git commit -m "feat(hub): add CRM API types (bloggers + integrations)"
```

---

### Task 7: Перенести React Query хуки

**Files:**
- Create: `wookiee-hub/src/hooks/crm/use-bloggers.ts`
- Create: `wookiee-hub/src/hooks/crm/use-integrations.ts`

- [ ] **Step 7.1: Создать use-bloggers.ts**

Скопировать `services/influencer_crm_ui/src/hooks/use-bloggers.ts` в `wookiee-hub/src/hooks/crm/use-bloggers.ts` и заменить импорт:
```ts
// Было:
import { ... } from '@/api/bloggers'
// Стало:
import { ... } from '@/api/crm/bloggers'
```

Весь остальной код — идентично оригиналу (функции `useBloggers`, `useBlogger`, `useUpsertBlogger`).

- [ ] **Step 7.2: Создать use-integrations.ts**

Скопировать `services/influencer_crm_ui/src/hooks/use-integrations.ts` в `wookiee-hub/src/hooks/crm/use-integrations.ts` и заменить импорт:
```ts
// Было:
import { ... } from '@/api/integrations'
// Стало:
import { ... } from '@/api/crm/integrations'
```

Весь остальной код — идентично (функции `useIntegrations`, `useIntegration`, `useUpsertIntegration`, `useUpdateIntegrationStage`).

- [ ] **Step 7.3: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```

- [ ] **Step 7.4: Commit**

```bash
git add wookiee-hub/src/hooks/crm/
git commit -m "feat(hub): add CRM React Query hooks"
```

---

## Phase 2: CRM UI Components

### Task 8: Перенести простые UI-компоненты

**Files:** все в `wookiee-hub/src/components/crm/ui/`

Правило замены для каждого файла: `import { cn } from '@/lib/cn'` → `import { cn } from '@/lib/utils'`
Все остальные импорты — внутри директории `@/components/crm/ui/`.

- [ ] **Step 8.1: Создать Avatar.tsx**

```tsx
import { cn } from '@/lib/utils'

const palettes = [
  'bg-[#F97316]', 'bg-[#3B82F6]', 'bg-[#8B5CF6]',
  'bg-[#EC4899]', 'bg-[#10B981]', 'bg-[#F59E0B]',
]

function colorFor(seed: string): string {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0
  return palettes[Math.abs(h) % palettes.length]
}

const sizes = {
  xs: 'size-7 text-[11px]',
  sm: 'size-8 text-xs',
  md: 'size-12 text-base',
  lg: 'size-16 text-2xl',
} as const

interface AvatarProps {
  name: string
  size?: keyof typeof sizes
  className?: string
}

export function Avatar({ name, size = 'sm', className }: AvatarProps) {
  const initials = name.split(/\s+|\./).filter(Boolean).slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '').join('')
  return (
    <span
      role="img"
      aria-label={name || 'avatar'}
      className={cn(
        'inline-flex items-center justify-center rounded-full text-white font-semibold shrink-0',
        sizes[size], colorFor(name), className,
      )}
    >
      {initials || '?'}
    </span>
  )
}

export type { AvatarProps }
```

- [ ] **Step 8.2: Создать Badge.tsx**

```tsx
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type Tone = 'success' | 'warning' | 'info' | 'orange' | 'pink' | 'secondary' | 'danger'

const tones: Record<Tone, string> = {
  success:   'bg-success/10 text-success',
  warning:   'bg-warning/10 text-warning',
  info:      'bg-info/10 text-info',
  orange:    'bg-primary-light text-primary-hover',
  pink:      'bg-pink/10 text-pink',
  secondary: 'bg-muted text-muted-fg border border-border',
  danger:    'bg-danger/10 text-danger',
}

interface BadgeProps {
  tone?: Tone
  children: ReactNode
  className?: string
}

export function Badge({ tone = 'secondary', children, className }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
      tones[tone], className,
    )}>
      {children}
    </span>
  )
}

export type { BadgeProps }
```

- [ ] **Step 8.3: Создать Button.tsx**

```tsx
import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
}

const variantClass: Record<Variant, string> = {
  primary:   'bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover',
  secondary: 'bg-card border border-border-strong hover:bg-primary-light',
  ghost:     'bg-transparent hover:bg-primary-light',
  danger:    'text-danger bg-danger/10 hover:bg-danger/20',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', loading, className, children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      type={rest.type ?? 'button'}
      disabled={loading || disabled}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium',
        'transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
        'min-h-[36px]',
        variantClass[variant], className,
      )}
      {...rest}
    >
      {loading && (
        <span aria-hidden="true"
          className="size-3 rounded-full border-2 border-current border-t-transparent animate-spin"
        />
      )}
      {children}
    </button>
  ),
)
Button.displayName = 'Button'

export type { ButtonProps }
```

- [ ] **Step 8.4: Создать FilterPill.tsx**

```tsx
import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface FilterPillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
  solid?: boolean
}

export const FilterPill = forwardRef<HTMLButtonElement, FilterPillProps>(
  ({ active, solid, className, children, ...rest }, ref) => (
    <button
      ref={ref}
      type={rest.type ?? 'button'}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium',
        'transition-colors duration-200 cursor-pointer',
        solid
          ? 'bg-primary text-primary-foreground border-primary hover:bg-primary-hover'
          : active
            ? 'bg-primary-light border-primary-muted text-primary-hover'
            : 'bg-muted border-border text-fg hover:bg-primary-light',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
)
FilterPill.displayName = 'FilterPill'

export type { FilterPillProps }
```

- [ ] **Step 8.5: Создать Input.tsx**

```tsx
import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type InputProps = InputHTMLAttributes<HTMLInputElement>

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...rest }, ref) => (
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
))
Input.displayName = 'Input'
```

- [ ] **Step 8.6: Создать Select.tsx**

```tsx
import { ChevronDown } from 'lucide-react'
import { forwardRef, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...rest }, ref) => (
    <span className="relative inline-block w-full">
      <select
        ref={ref}
        className={cn(
          'w-full appearance-none rounded-md border border-border bg-card px-3 py-2 pr-9 text-sm',
          'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
          'disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-fg"
      />
    </span>
  ),
)
Select.displayName = 'Select'
```

- [ ] **Step 8.7: Создать Skeleton.tsx**

```tsx
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type SkeletonProps = HTMLAttributes<HTMLDivElement>

export function Skeleton({ className, ...rest }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...rest}
    />
  )
}
```

- [ ] **Step 8.8: Создать Textarea.tsx**

```tsx
import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, rows = 3, ...rest }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        'w-full rounded-md border border-border bg-card px-3 py-2 text-sm',
        'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
        'placeholder:text-muted-fg resize-y',
        className,
      )}
      {...rest}
    />
  ),
)
Textarea.displayName = 'Textarea'
```

- [ ] **Step 8.9: Создать PlatformPill.tsx**

```tsx
import { cn } from '@/lib/utils'

const styles = {
  instagram: 'bg-gradient-to-br from-[#f58529] via-[#dd2a7b] to-[#8134af]',
  tiktok:    'bg-black',
  youtube:   'bg-[#FF0000]',
  telegram:  'bg-[#229ED9]',
  vk:        'bg-[#0077FF]',
} as const

const labels = {
  instagram: 'IG', tiktok: 'TT', youtube: 'YT', telegram: 'TG', vk: 'VK',
} as const

export type PlatformChannel = keyof typeof styles

interface PlatformPillProps {
  channel: PlatformChannel
  className?: string
}

export function PlatformPill({ channel, className }: PlatformPillProps) {
  return (
    <span
      role="img"
      aria-label={channel}
      className={cn(
        'inline-flex size-[22px] items-center justify-center rounded-md text-[10px] font-bold text-white',
        styles[channel], className,
      )}
    >
      {labels[channel]}
    </span>
  )
}
```

- [ ] **Step 8.10: Создать EmptyState.tsx**

```tsx
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  title: string
  description?: ReactNode
  icon?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-10',
      className,
    )}>
      {icon && <div className="text-muted-fg">{icon}</div>}
      <div className="text-base font-semibold text-fg">{title}</div>
      {description && <p className="max-w-md text-sm text-muted-fg">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 8.11: Создать QueryStatusBoundary.tsx**

```tsx
import type { ReactNode } from 'react'
import { EmptyState } from './EmptyState'
import { Skeleton } from './Skeleton'

interface Props {
  isLoading: boolean
  error: unknown
  isEmpty?: boolean
  loadingFallback?: ReactNode
  emptyTitle?: string
  emptyDescription?: string
  children: ReactNode
}

export function QueryStatusBoundary({
  isLoading, error, isEmpty, loadingFallback,
  emptyTitle = 'Пусто',
  emptyDescription = 'Снимите фильтры или добавьте первую запись.',
  children,
}: Props) {
  if (isLoading) return <>{loadingFallback ?? <Skeleton className="h-96" />}</>
  if (error) {
    const msg = error instanceof Error ? error.message : 'Что-то пошло не так'
    return (
      <div role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-6">
        <h3 className="font-semibold text-danger">Ошибка загрузки</h3>
        <p className="text-sm text-muted-fg mt-1">{msg}</p>
      </div>
    )
  }
  if (isEmpty) return <EmptyState title={emptyTitle} description={emptyDescription} />
  return <>{children}</>
}
```

- [ ] **Step 8.12: Создать Tabs.tsx**

```tsx
import { type ReactNode, useId, useState } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem {
  label: string
  content: ReactNode
  count?: number
}

interface TabsProps {
  tabs: TabItem[]
  defaultIndex?: number
  className?: string
}

export function Tabs({ tabs, defaultIndex = 0, className }: TabsProps) {
  const [active, setActive] = useState(defaultIndex)
  const baseId = useId()

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div role="tablist" className="flex gap-1 border-b border-border px-1">
        {tabs.map((t, i) => {
          const isActive = i === active
          return (
            <button
              key={t.label}
              id={`${baseId}-tab-${t.label}`}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`${baseId}-panel-${t.label}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActive(i)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium -mb-px',
                'border-b-2 transition-colors duration-200 cursor-pointer',
                isActive
                  ? 'text-primary border-primary'
                  : 'text-muted-fg border-transparent hover:text-fg',
              )}
            >
              {t.label}
              {typeof t.count === 'number' && (
                <span className={cn(
                  'rounded-full px-1.5 py-px text-[11px] font-mono font-semibold',
                  isActive ? 'bg-primary-light text-primary-hover' : 'bg-muted text-muted-fg',
                )}>
                  {t.count}
                </span>
              )}
            </button>
          )
        })}
      </div>
      {tabs.map((t, i) => (
        <div
          key={t.label}
          id={`${baseId}-panel-${t.label}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${t.label}`}
          hidden={i !== active}
        >
          {i === active && t.content}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 8.13: Создать PageHeader.tsx в components/crm/layout/**

Создать `wookiee-hub/src/components/crm/layout/PageHeader.tsx`:
```tsx
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  sub?: string
  actions?: ReactNode
  className?: string
}

export function PageHeader({ title, sub, actions, className }: PageHeaderProps) {
  return (
    <header className={cn(
      'mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
      className,
    )}>
      <div>
        <h1 className="text-3xl font-bold text-fg">{title}</h1>
        {sub && <p className="mt-1 text-sm text-muted-fg">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
```

- [ ] **Step 8.14: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 8.15: Commit**

```bash
git add wookiee-hub/src/components/crm/
git commit -m "feat(hub): port CRM UI components (Avatar, Badge, Button, FilterPill, Input, Select, Skeleton, Textarea, Tabs, PlatformPill, EmptyState, QueryStatusBoundary, PageHeader)"
```

---

### Task 9: Создать Drawer (Radix Dialog-based)

**Files:**
- Create: `wookiee-hub/src/components/crm/ui/Drawer.tsx`

Контекст: CRM использует `@headlessui/react Dialog` для Drawer. Hub не имеет Headless UI, но имеет `@radix-ui/react-dialog`. Реализуем Drawer через Radix с теми же props.

- [ ] **Step 9.1: Создать Drawer.tsx**

```tsx
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  width?: string
}

export function Drawer({
  open, onClose, title, children, footer, width = 'max-w-2xl',
}: DrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 duration-200" />
        <Dialog.Content
          className={cn(
            'fixed inset-y-0 right-0 z-50 flex flex-col bg-card',
            'w-full', width,
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
            'duration-200',
          )}
          style={{ boxShadow: '-16px 0 60px -12px rgba(0,0,0,0.18)' }}
        >
          <header className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
            <Dialog.Title className="font-semibold text-lg text-fg">{title}</Dialog.Title>
            <button
              type="button"
              aria-label="Закрыть"
              className="p-2 rounded-md hover:bg-primary-light cursor-pointer"
              onClick={onClose}
            >
              <X size={18} />
            </button>
          </header>
          <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
          {footer && (
            <footer className="px-6 py-4 border-t border-border flex justify-end gap-2 shrink-0">
              {footer}
            </footer>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
```

- [ ] **Step 9.2: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```

- [ ] **Step 9.3: Commit**

```bash
git add wookiee-hub/src/components/crm/ui/Drawer.tsx
git commit -m "feat(hub): add CRM Drawer component (Radix Dialog slide-over)"
```

---

## Phase 2: Pages

### Task 10: Реализовать BloggersPage

**Files:**
- Modify: `wookiee-hub/src/pages/influence/bloggers/BloggersPage.tsx`
- Create: `wookiee-hub/src/pages/influence/bloggers/BloggersTable.tsx`
- Create: `wookiee-hub/src/pages/influence/bloggers/BloggersFilters.tsx`
- Create: `wookiee-hub/src/pages/influence/bloggers/BloggerExpandedRow.tsx`
- Create: `wookiee-hub/src/pages/influence/bloggers/BloggerEditDrawer.tsx`

Правило для всех файлов: импорты `@/ui/X` → `@/components/crm/ui/X`, `@/layout/X` → `@/components/crm/layout/X`, `@/hooks/use-X` → `@/hooks/crm/use-X`, `@/api/bloggers` → `@/api/crm/bloggers`, `@/api/integrations` → `@/api/crm/integrations`.

- [ ] **Step 10.1: Создать BloggersFilters.tsx**

```tsx
import { useId } from 'react'
import type { BloggerListParams, BloggerStatus } from '@/api/crm/bloggers'
import { FilterPill } from '@/components/crm/ui/FilterPill'
import { Input } from '@/components/crm/ui/Input'

export type BloggersFilterValue = Pick<BloggerListParams, 'status' | 'q' | 'marketer_id' | 'tag_id'>

interface Props {
  value: BloggersFilterValue
  onChange: (next: BloggersFilterValue) => void
}

const statuses: { key: BloggerStatus | undefined; label: string }[] = [
  { key: undefined, label: 'Все' },
  { key: 'active',  label: 'Активные' },
  { key: 'paused',  label: 'На паузе' },
  { key: 'new',     label: 'Новые' },
]

export function BloggersFilters({ value, onChange }: Props) {
  const searchId = useId()
  return (
    <div className="bg-card border border-border rounded-lg px-3.5 py-3 mb-5 flex items-center gap-2.5 flex-wrap">
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
      <label htmlFor={searchId} className="sr-only">Поиск блогеров</label>
      <Input
        id={searchId}
        className="ml-auto max-w-xs"
        placeholder="Поиск по handle / имени"
        value={value.q ?? ''}
        onChange={(e) => onChange({ ...value, q: e.target.value || undefined })}
      />
    </div>
  )
}
```

- [ ] **Step 10.2: Создать BloggersTable.tsx**

```tsx
import { Fragment, type ReactNode, useState } from 'react'
import type { BloggerOut, BloggerStatus } from '@/api/crm/bloggers'
import { Avatar } from '@/components/crm/ui/Avatar'
import { Badge, type BadgeProps } from '@/components/crm/ui/Badge'
import { BloggerExpandedRow } from './BloggerExpandedRow'

const statusTone: Record<BloggerStatus, NonNullable<BadgeProps['tone']>> = {
  active: 'success', paused: 'warning', in_progress: 'info', new: 'secondary',
}
const statusLabel: Record<BloggerStatus, string> = {
  active: 'Активный', paused: 'На паузе', in_progress: 'В работе', new: 'Новый',
}

interface Props {
  bloggers: BloggerOut[]
  onEdit?: (id: number) => void
}

export function BloggersTable({ bloggers, onEdit }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <table className="w-full">
        <caption className="sr-only">Список блогеров</caption>
        <thead>
          <tr>
            <Th>Блогер</Th>
            <Th>Статус</Th>
            <Th>Каналы</Th>
            <Th className="text-right">Интеграций</Th>
          </tr>
        </thead>
        <tbody>
          {bloggers.map((b) => {
            const isExpanded = expandedId === b.id
            const displayName = b.real_name ?? b.display_handle
            return (
              <Fragment key={b.id}>
                <tr
                  className={`cursor-pointer transition-colors duration-150 ${isExpanded ? 'bg-primary-light' : 'hover:bg-bg-warm'}`}
                  onClick={() => setExpandedId(isExpanded ? null : b.id)}
                >
                  <td className="px-3.5 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={displayName} />
                      <div className="min-w-0">
                        <div className="font-semibold text-sm">{displayName}</div>
                        <div className="text-xs text-muted-fg truncate">@{b.display_handle}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3.5 py-3">
                    <Badge tone={statusTone[b.status]}>{statusLabel[b.status]}</Badge>
                  </td>
                  <td className="px-3.5 py-3 font-mono text-sm text-muted-fg">—</td>
                  <td className="px-3.5 py-3 font-mono text-sm text-right text-muted-fg">—</td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={4} className="bg-bg-warm p-0">
                      <BloggerExpandedRow id={b.id} onEdit={onEdit} />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Th({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <th className={`bg-muted text-[11.5px] uppercase tracking-wider text-muted-fg font-semibold px-3.5 py-2.5 text-left ${className}`}>
      {children}
    </th>
  )
}
```

- [ ] **Step 10.3: Создать BloggerExpandedRow.tsx**

Скопировать `services/influencer_crm_ui/src/routes/bloggers/BloggerExpandedRow.tsx` в `wookiee-hub/src/pages/influence/bloggers/BloggerExpandedRow.tsx`. Заменить импорты:
- `'@/api/bloggers'` → `'@/api/crm/bloggers'`
- `'@/hooks/use-bloggers'` → `'@/hooks/crm/use-bloggers'`
- `'@/ui/Avatar'` → `'@/components/crm/ui/Avatar'`
- `'@/ui/Badge'` → `'@/components/crm/ui/Badge'`
- `'@/ui/Button'` → `'@/components/crm/ui/Button'`
- `'@/ui/Skeleton'` → `'@/components/crm/ui/Skeleton'`

Тело компонента — идентично оригиналу.

- [ ] **Step 10.4: Создать BloggerEditDrawer.tsx**

Скопировать `services/influencer_crm_ui/src/routes/bloggers/BloggerEditDrawer.tsx` в `wookiee-hub/src/pages/influence/bloggers/BloggerEditDrawer.tsx`. Заменить импорты:
- `'@/api/bloggers'` → `'@/api/crm/bloggers'`
- `'@/hooks/use-bloggers'` → `'@/hooks/crm/use-bloggers'`
- `'@/ui/Button'` → `'@/components/crm/ui/Button'`
- `'@/ui/Drawer'` → `'@/components/crm/ui/Drawer'`
- `'@/ui/EmptyState'` → `'@/components/crm/ui/EmptyState'`
- `'@/ui/Input'` → `'@/components/crm/ui/Input'`
- `'@/ui/Select'` → `'@/components/crm/ui/Select'`
- `'@/ui/Tabs'` → `'@/components/crm/ui/Tabs'`
- `'@/ui/Textarea'` → `'@/components/crm/ui/Textarea'`

Тело компонента — идентично оригиналу.

- [ ] **Step 10.5: Реализовать BloggersPage.tsx**

Заменить skeleton-заглушку в `wookiee-hub/src/pages/influence/bloggers/BloggersPage.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useBloggers } from '@/hooks/crm/use-bloggers'
import { PageHeader } from '@/components/crm/layout/PageHeader'
import { Button } from '@/components/crm/ui/Button'
import { QueryStatusBoundary } from '@/components/crm/ui/QueryStatusBoundary'
import { BloggerEditDrawer } from './BloggerEditDrawer'
import { BloggersFilters, type BloggersFilterValue } from './BloggersFilters'
import { BloggersTable } from './BloggersTable'

export function BloggersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [filters, setFilters] = useState<BloggersFilterValue>({ status: 'active' })
  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useBloggers(filters)
  const items = data?.pages.flatMap((p) => p.items) ?? []

  const openParam = searchParams.get('open')
  const [drawerOpen, setDrawerOpen] = useState(() => openParam !== null)
  const [drawerBloggerId, setDrawerBloggerId] = useState<number | undefined>(
    () => (openParam ? Number(openParam) : undefined),
  )

  useEffect(() => {
    if (openParam !== null) {
      setDrawerBloggerId(Number(openParam))
      setDrawerOpen(true)
    }
  }, [openParam])

  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
        actions={
          <Button variant="primary" onClick={() => { setDrawerBloggerId(undefined); setDrawerOpen(true) }}>
            + Новый блогер
          </Button>
        }
      />
      <BloggersFilters value={filters} onChange={setFilters} />
      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyTitle="Никого не нашлось"
        emptyDescription="Снимите фильтр или создайте нового."
      >
        <BloggersTable
          bloggers={items}
          onEdit={(id) => { setDrawerBloggerId(id); setDrawerOpen(true) }}
        />
      </QueryStatusBoundary>
      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
            Показать ещё
          </Button>
        </div>
      )}
      <BloggerEditDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          if (searchParams.has('open')) {
            setSearchParams((prev) => { prev.delete('open'); return prev })
          }
        }}
        bloggerId={drawerBloggerId}
      />
    </>
  )
}
```

- [ ] **Step 10.6: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 10.7: Commit**

```bash
git add wookiee-hub/src/pages/influence/bloggers/
git commit -m "feat(hub): implement BloggersPage (table + drawer + filters)"
```

---

### Task 11: Реализовать IntegrationsKanbanPage

**Files:**
- Modify: `wookiee-hub/src/pages/influence/integrations/IntegrationsKanbanPage.tsx`
- Create: `wookiee-hub/src/pages/influence/integrations/KanbanColumn.tsx`
- Create: `wookiee-hub/src/pages/influence/integrations/KanbanCard.tsx`
- Create: `wookiee-hub/src/pages/influence/integrations/IntegrationEditDrawer.tsx`

- [ ] **Step 11.1: Создать KanbanCard.tsx**

Скопировать `services/influencer_crm_ui/src/routes/integrations/KanbanCard.tsx` в `wookiee-hub/src/pages/influence/integrations/KanbanCard.tsx`. Заменить импорты:
- `'@/api/integrations'` → `'@/api/crm/integrations'`
- `'@/lib/cn'` → `'@/lib/utils'`
- `'@/ui/Avatar'` → `'@/components/crm/ui/Avatar'`
- `'@/ui/Badge'` → `'@/components/crm/ui/Badge'`
- `'@/ui/PlatformPill'` → `'@/components/crm/ui/PlatformPill'`

Тело — идентично.

- [ ] **Step 11.2: Создать KanbanColumn.tsx**

Скопировать `services/influencer_crm_ui/src/routes/integrations/KanbanColumn.tsx` в `wookiee-hub/src/pages/influence/integrations/KanbanColumn.tsx`. Заменить импорты:
- `'@/api/integrations'` → `'@/api/crm/integrations'`
- `'@/lib/cn'` → `'@/lib/utils'`
- `'@/ui/Badge'` → `'@/components/crm/ui/Badge'`
- `'./KanbanCard'` — оставить (локальный)

- [ ] **Step 11.3: Создать IntegrationEditDrawer.tsx**

Скопировать `services/influencer_crm_ui/src/routes/integrations/IntegrationEditDrawer.tsx` в `wookiee-hub/src/pages/influence/integrations/IntegrationEditDrawer.tsx`. Заменить импорты:
- `'@/api/integrations'` → `'@/api/crm/integrations'`
- `'@/hooks/use-integrations'` → `'@/hooks/crm/use-integrations'`
- `'@/ui/Button'` → `'@/components/crm/ui/Button'`
- `'@/ui/Drawer'` → `'@/components/crm/ui/Drawer'`
- `'@/ui/EmptyState'` → `'@/components/crm/ui/EmptyState'`
- `'@/ui/Input'` → `'@/components/crm/ui/Input'`
- `'@/ui/Select'` → `'@/components/crm/ui/Select'`
- `'@/ui/Textarea'` → `'@/components/crm/ui/Textarea'`

- [ ] **Step 11.4: Реализовать IntegrationsKanbanPage.tsx**

Заменить skeleton:
```tsx
import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { IntegrationOut, Stage } from '@/api/crm/integrations'
import { STAGES } from '@/api/crm/integrations'
import { useIntegrations, useUpdateIntegrationStage } from '@/hooks/crm/use-integrations'
import { PageHeader } from '@/components/crm/layout/PageHeader'
import { Button } from '@/components/crm/ui/Button'
import { QueryStatusBoundary } from '@/components/crm/ui/QueryStatusBoundary'
import { IntegrationEditDrawer } from './IntegrationEditDrawer'
import { KanbanColumn } from './KanbanColumn'

type StageGroups = Record<Stage, IntegrationOut[]>

function emptyGroups(): StageGroups {
  return STAGES.reduce<StageGroups>((acc, stage) => { acc[stage] = []; return acc }, {} as StageGroups)
}

export function IntegrationsKanbanPage() {
  const { data, isLoading, error } = useIntegrations({ limit: 200 })
  const updateStage = useUpdateIntegrationStage()
  const [activeId, setActiveId] = useState<number | undefined>(undefined)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))
  const items = data?.items ?? []

  const groups = useMemo(() => {
    const acc = emptyGroups()
    for (const it of items) {
      if (acc[it.stage]) acc[it.stage].push(it)
    }
    return acc
  }, [items])

  function onDragEnd(e: DragEndEvent) {
    const id = Number(e.active.id)
    const target = e.over?.id
    if (!Number.isFinite(id) || target == null) return
    const stage = target as Stage
    if (!STAGES.includes(stage)) return
    const current = items.find((i) => i.id === id)
    if (!current || current.stage === stage) return
    updateStage.mutate({ id, stage })
  }

  return (
    <>
      <PageHeader
        title="Интеграции"
        sub="8 стадий — перетащи карточку для смены стадии. Клик откроет детали."
        actions={
          <Button variant="primary" onClick={() => setActiveId(0)}>
            <Plus size={16} /> Новая интеграция
          </Button>
        }
      />
      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyTitle="Интеграций пока нет"
        emptyDescription="Создайте первую интеграцию из карточки блогера."
      >
        <DndContext sensors={sensors} onDragEnd={onDragEnd}>
          <div className="-mx-2 flex gap-4 overflow-x-auto px-2 pb-4">
            {STAGES.map((stage) => (
              <KanbanColumn
                key={stage}
                stage={stage}
                items={groups[stage]}
                onOpenCard={(id) => setActiveId(id)}
              />
            ))}
          </div>
        </DndContext>
      </QueryStatusBoundary>
      <IntegrationEditDrawer
        open={activeId !== undefined}
        id={activeId !== undefined && activeId > 0 ? activeId : undefined}
        onClose={() => setActiveId(undefined)}
      />
    </>
  )
}
```

- [ ] **Step 11.5: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```

- [ ] **Step 11.6: Commit**

```bash
git add wookiee-hub/src/pages/influence/integrations/
git commit -m "feat(hub): implement IntegrationsKanbanPage (dnd-kit kanban)"
```

---

### Task 12: Реализовать CalendarPage

**Files:**
- Modify: `wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx`
- Create: `wookiee-hub/src/pages/influence/calendar/CalendarMonthGrid.tsx`

- [ ] **Step 12.1: Создать CalendarMonthGrid.tsx**

Скопировать `services/influencer_crm_ui/src/routes/calendar/CalendarMonthGrid.tsx` в `wookiee-hub/src/pages/influence/calendar/CalendarMonthGrid.tsx`. Заменить импорты:
- `'@/api/integrations'` → `'@/api/crm/integrations'`
- `'@/lib/cn'` → `'@/lib/utils'`
- `'@/ui/PlatformPill'` → `'@/components/crm/ui/PlatformPill'`

Тело — идентично.

- [ ] **Step 12.2: Реализовать CalendarPage.tsx**

Скопировать `services/influencer_crm_ui/src/routes/calendar/CalendarPage.tsx` в `wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx`. Заменить импорты:
- `'@/hooks/use-integrations'` → `'@/hooks/crm/use-integrations'`
- `'@/routes/integrations/IntegrationEditDrawer'` → `'@/pages/influence/integrations/IntegrationEditDrawer'`
- `'@/layout/PageHeader'` → `'@/components/crm/layout/PageHeader'`
- `'@/ui/Button'` → `'@/components/crm/ui/Button'`
- `'@/ui/FilterPill'` → `'@/components/crm/ui/FilterPill'`
- `'@/ui/QueryStatusBoundary'` → `'@/components/crm/ui/QueryStatusBoundary'`
- `'@/ui/Skeleton'` → `'@/components/crm/ui/Skeleton'`
- `'./CalendarMonthGrid'` — оставить

- [ ] **Step 12.3: Проверить TypeScript**

```bash
cd wookiee-hub && npx tsc --noEmit
```
Expected: 0 ошибок.

- [ ] **Step 12.4: Commit**

```bash
git add wookiee-hub/src/pages/influence/calendar/
git commit -m "feat(hub): implement CalendarPage (month grid + integration drawer)"
```

---

### Task 13: Добавить CORS в BFF

**Files:**
- Modify: `services/influencer_crm/app.py`

Контекст: Hub (`hub.os.wookiee.shop`) будет делать cross-origin запросы к `crm.matveevdanila.com/api`. BFF сейчас не имеет CORS middleware → браузер заблокирует запросы.

- [ ] **Step 13.1: Добавить CORSMiddleware в app.py**

В `services/influencer_crm/app.py` добавить импорт после `from fastapi import FastAPI, HTTPException`:
```python
from fastapi.middleware.cors import CORSMiddleware
```

В функцию `create_app()` после `app.add_middleware(ETagMiddleware)` добавить:
```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://hub.os.wookiee.shop"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "If-None-Match"],
        expose_headers=["ETag"],
    )
```

Примечание: `CORSMiddleware` нужно добавлять ДО других middleware. Порядок важен.

- [ ] **Step 13.2: Проверить изменение**

```bash
grep -n "CORSMiddleware" services/influencer_crm/app.py
```
Expected: строки с импортом и `add_middleware`.

- [ ] **Step 13.3: Commit**

```bash
git add services/influencer_crm/app.py
git commit -m "feat(crm): add CORS for hub.os.wookiee.shop"
```

---

### Task 14: Deploy + Env + Smoke Test

- [ ] **Step 14.1: Добавить VITE_CRM_API_URL и VITE_CRM_API_KEY на сервер**

```bash
ssh timeweb "grep -q VITE_CRM_API_URL /home/danila/projects/wookiee/.env || echo 'VITE_CRM_API_URL=https://crm.matveevdanila.com/api' >> /home/danila/projects/wookiee/.env"
ssh timeweb "grep -q VITE_CRM_API_KEY /home/danila/projects/wookiee/.env || echo 'VITE_CRM_API_KEY=' >> /home/danila/projects/wookiee/.env"
```

Затем вручную задать значение ключа (равно `INFLUENCER_CRM_API_KEY`):
```bash
ssh timeweb
grep INFLUENCER_CRM_API_KEY /home/danila/projects/wookiee/.env
# скопировать значение и установить в VITE_CRM_API_KEY
```

- [ ] **Step 14.2: Деплой BFF (пересборка с CORS)**

```bash
ssh timeweb "cd /home/danila/projects/wookiee && git pull && docker compose -f deploy/docker-compose.yml up -d --build influencer-crm-api"
```

- [ ] **Step 14.3: Собрать и задеплоить Hub с env**

```bash
ssh timeweb "cd /home/danila/projects/wookiee/wookiee-hub && source /home/danila/projects/wookiee/.env && VITE_CRM_API_URL=$VITE_CRM_API_URL VITE_CRM_API_KEY=$VITE_CRM_API_KEY npm run build && cp -r dist/* /srv/hub/"
```

- [ ] **Step 14.4: Smoke test BloggersPage через Playwright**

```bash
cd wookiee-hub && npx playwright open https://hub.os.wookiee.shop/influence/bloggers
```
Expected: таблица блогеров загружается, статус-фильтры работают.

- [ ] **Step 14.5: Smoke test IntegrationsKanbanPage**

```bash
cd wookiee-hub && npx playwright open https://hub.os.wookiee.shop/influence/integrations
```
Expected: канбан с 8 колонками, карточки загружены.

- [ ] **Step 14.6: Smoke test CalendarPage**

```bash
cd wookiee-hub && npx playwright open https://hub.os.wookiee.shop/influence/calendar
```
Expected: месячный грид отображается, события видны.

---

## Phase 3: Cleanup

### Task 15: Убрать SPA из BFF

**Files:**
- Modify: `services/influencer_crm/app.py`
- Modify: `deploy/Dockerfile.influencer_crm_api`

⚠️ Выполнять ТОЛЬКО после того, как все страницы в Hub работают корректно (Task 14 completed).

- [ ] **Step 15.1: Удалить SPAStaticFiles из app.py**

В `services/influencer_crm/app.py` удалить весь класс `SPAStaticFiles` (строки 49-64) и блок монтирования SPA в конце `create_app()`:
```python
# Удалить эти строки из create_app():
    if UI_DIST_DIR.exists():
        app.mount("/", SPAStaticFiles(directory=str(UI_DIST_DIR), html=True), name="ui")
```

Также удалить импорт `StaticFiles` если он больше нигде не используется:
```python
# Удалить из импортов:
from fastapi.staticfiles import StaticFiles
```

И удалить константу:
```python
# Удалить:
UI_DIST_DIR = Path("/app/ui_dist")
```

Также удалить `from pathlib import Path` если больше не нужен.

Итоговый `app.py` должен содержать только: импорты, `create_app()` с middleware + routers + exception handler, `app = create_app()`.

- [ ] **Step 15.2: Обновить Dockerfile — удалить SPA build stage**

Текущий `deploy/Dockerfile.influencer_crm_api` имеет 2 этапа: `spa-builder` (Node.js) и Python. Оставить только Python этап.

Заменить весь файл на:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/influencer_crm/requirements.txt /app/services/influencer_crm/requirements.txt
RUN pip install --no-cache-dir -r services/influencer_crm/requirements.txt

COPY shared/ /app/shared/
COPY services/__init__.py /app/services/__init__.py
COPY services/influencer_crm/ /app/services/influencer_crm/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8082

CMD ["uvicorn", "services.influencer_crm.app:app", "--host", "0.0.0.0", "--port", "8082"]
```

- [ ] **Step 15.3: Убрать VITE_API_KEY build arg из docker-compose.yml**

В `deploy/docker-compose.yml` найти секцию `influencer-crm-api` и удалить блок `args`:
```yaml
# Удалить:
      args:
        VITE_API_KEY: ${INFLUENCER_CRM_API_KEY:-}
```

Оставить только `context` и `dockerfile` в секции `build`.

- [ ] **Step 15.4: Проверить Python код**

```bash
cd /Users/danilamatveev/Projects/Wookiee
python -m py_compile services/influencer_crm/app.py && echo "OK"
```

- [ ] **Step 15.5: Commit**

```bash
git add services/influencer_crm/app.py deploy/Dockerfile.influencer_crm_api deploy/docker-compose.yml
git commit -m "feat(crm): remove SPA bundle — BFF is now API-only"
```

---

### Task 16: Обновить Caddy — crm.matveevdanila.com → API only

- [ ] **Step 16.1: Открыть Caddyfile на сервере**

```bash
ssh timeweb "cat /home/danila/n8n-docker-caddy/caddy_config/Caddyfile | grep -A 10 'crm.matveevdanila'"
```
Expected: текущий блок для crm.matveevdanila.com.

- [ ] **Step 16.2: Обновить блок crm.matveevdanila.com**

Найти текущий блок (примерно):
```
crm.matveevdanila.com {
    reverse_proxy influencer_crm_api:8082
}
```

Заменить на (API проксируется, остальное редиректит на Hub):
```
crm.matveevdanila.com {
    # API запросы — проксировать к BFF
    handle /api/* {
        reverse_proxy influencer_crm_api:8082
    }
    # Всё остальное — 301 на Hub
    handle {
        redir https://hub.os.wookiee.shop/influence{uri} 301
    }
}
```

Применить изменения:
```bash
ssh timeweb "docker exec n8n-docker-caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile"
```

Или если контейнер называется иначе:
```bash
ssh timeweb "docker ps | grep caddy"
# и заменить имя контейнера
```

- [ ] **Step 16.3: Деплой обновлённого BFF**

```bash
ssh timeweb "cd /home/danila/projects/wookiee && git pull && docker compose -f deploy/docker-compose.yml up -d --build influencer-crm-api"
```

- [ ] **Step 16.4: Проверить API через Playwright**

```bash
cd wookiee-hub && npx playwright open https://hub.os.wookiee.shop/influence/bloggers
```
Expected: страница работает, данные грузятся через новый CORS-маршрут.

- [ ] **Step 16.5: Проверить редирект**

```bash
curl -I https://crm.matveevdanila.com/
```
Expected: `HTTP/2 301` с `Location: https://hub.os.wookiee.shop/influence`.

- [ ] **Step 16.6: Проверить API endpoint напрямую**

```bash
curl -s -o /dev/null -w "%{http_code}" https://crm.matveevdanila.com/api/health
```
Expected: `200`.

- [ ] **Step 16.7: Final smoke test — все три страницы**

Открыть через Playwright:
1. `https://hub.os.wookiee.shop/influence/bloggers` → таблица загружается
2. `https://hub.os.wookiee.shop/influence/integrations` → канбан
3. `https://hub.os.wookiee.shop/influence/calendar` → календарь

- [ ] **Step 16.8: Commit Caddyfile (если Caddyfile в git)**

```bash
git add /home/danila/n8n-docker-caddy/caddy_config/Caddyfile 2>/dev/null || true
git commit -m "feat(infra): crm.matveevdanila.com → API-only + redirect to Hub"
```

---

## Spec Coverage Checklist

| Требование | Задача |
|---|---|
| Убрать "Поиск" и "Продукты" из старого CRM sidebar | Task 4b |
| Группа "Influence CRM" в navigation.ts, иконка Users2 | Task 3 |
| 3 пункта: Блогеры / Интеграции / Календарь | Task 3 |
| Маршруты /influence/* в Hub router | Task 3 |
| CRM API-клиент с X-API-Key из env | Task 5 |
| Типы из api/bloggers.ts и api/integrations.ts | Task 6 |
| Хуки use-bloggers.ts и use-integrations.ts | Task 7 |
| Страница блогеров (shadcn-style Table + Drawer) | Task 10 |
| Страница интеграций (dnd-kit канбан) | Task 11 |
| Страница календаря | Task 12 |
| CORS на BFF для hub.os.wookiee.shop | Task 13 |
| VITE_CRM_API_URL и VITE_CRM_API_KEY в Hub env | Task 14 |
| Убрать SPAStaticFiles из BFF | Task 15 |
| Обновить Caddy: API-only для crm.matveevdanila.com | Task 16 |
| Убрать SPA build stage из Dockerfile | Task 15 |
| Деплой Hub после каждой фазы | Tasks 4, 14, 16 |
| Верификация через Playwright | Tasks 4, 14, 16 |
