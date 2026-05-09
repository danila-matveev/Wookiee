# Marketing Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. After every task implementer subagent completes, run BOTH spec-compliance review AND code-quality review (mandatory). After Phase 4 (QA) — full re-verification in browser before announcing complete.

**Goal:** Внедрить раздел «Маркетинг» в Wookiee Hub (страницы Промокоды и Поисковые запросы) с просмотром, аналитикой воронки и CRUD, повторяя UX из прототипа `wookiee_marketing_v4.jsx` 1:1 в семантической палитре Hub. Источник истины — `crm.*`, чтение через VIEW `marketing.*`, запись через `crm.*`.

**Architecture:**
- **Read path**: VIEW `marketing.search_queries_unified` (UNION ALL `crm.branded_queries` + `crm.substitute_articles` с вычислением `group_kind`) + существующие views `marketing.search_query_stats_weekly`, `marketing.promo_codes`, и физическая `marketing.promo_stats_weekly`. Aggregations недельных stats делаются в БД (RPC) для быстрого client-side responses.
- **Write path**: прямые INSERT/UPDATE в `crm.branded_queries`, `crm.substitute_articles`, `crm.promo_codes` через Supabase JS client. Новые поля (creator_ref, channel_id) добавляются миграциями без слома sheets-sync ETL.
- **UI path**: pages `src/pages/marketing/{promo-codes,search-queries}.tsx` поверх patterns из `src/pages/influence/bloggers/` (PageHeader + filters + table + edit drawer + URL state via useSearchParams). Sub-sidebar навигация в `src/config/navigation.ts`.
- **Темизация**: палитра JSX (`stone-*`) маппится на semantic tokens Hub (`bg-muted`, `text-foreground`, `border-border`, `bg-primary`). Структура/spacing/типографика — 1:1 из JSX. Шрифты DM Sans + Instrument Serif уже импортированы в `index.css`.

**Tech Stack:** Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui + react-router-dom v7 + TanStack Query + Supabase JS v2 + Zustand (если нужно).

**Источники истины:**
- Дизайн-эталон: `wookiee_marketing_v4.jsx` (приложен к задаче, **сохранить копию** в `docs/superpowers/specs/wookiee_marketing_v4.jsx` перед стартом)
- Data model: `BRIEF_marketing.md` (приложен, **сохранить** в `docs/superpowers/specs/2026-05-08-marketing-hub-brief.md`)
- Контекст: `docs/superpowers/specs/2026-05-06-marketing-hub-mockup-context.md`

**Phase summary:**
- **Phase 1 (Foundation + Read-only)** — миграции views + примитивы + 2 страницы read-only с воронкой. 10 задач.
- **Phase 2 (CRUD + новые поля)** — `marketing.channels`, `creator_ref`, формы создания, редактирование статусов. 7 задач.
- **Phase 3 (Sync infra)** — `marketing.sync_log`, кнопка «Обновить», UpdateBar. 3 задачи.
- **Phase 4 (QA pass)** — выделенный browser smoke-test всех экранов. 1 задача.

**Pre-flight (выполнить до Task 1.1):**
- [ ] Скопировать `wookiee_marketing_v4.jsx` в `docs/superpowers/specs/wookiee_marketing_v4.jsx`
- [ ] Скопировать `BRIEF_marketing.md` в `docs/superpowers/specs/2026-05-08-marketing-hub-brief.md`
- [ ] Создать ветку `feature/marketing-hub` (ОБЯЗАТЕЛЬНО, не работать на main)
- [ ] Прогнать `npm run build` в `wookiee-hub/` чтобы baseline зеленый

---

## Phase 1 — Foundation + Read-only UI

### Task 1.1: VIEW `marketing.search_queries_unified` + RPCs

**Files:**
- Create: `database/marketing/views/2026-05-08-search-queries-unified.sql`
- Create: `database/marketing/rpcs/2026-05-08-search-query-stats-aggregated.sql`
- Apply via: `mcp__plugin_supabase_supabase__apply_migration`

**Why:** UI ожидает единую таблицу с полем `group_kind ∈ {brand, external, cr_general, cr_personal}`. Реальные данные лежат в двух таблицах; объединяем через VIEW. Aggregated stats per (query_id, date_range) — через RPC, чтобы не тащить 2565 строк на клиент.

- [ ] **Step 1: Написать VIEW**

```sql
-- database/marketing/views/2026-05-08-search-queries-unified.sql
CREATE OR REPLACE VIEW marketing.search_queries_unified AS
SELECT
  ('B' || bq.id::text)::text          AS unified_id,
  bq.id                                AS source_id,
  'branded_queries'::text              AS source_table,
  'brand'::text                        AS group_kind,
  bq.query                             AS query_text,
  NULL::int                            AS artikul_id,
  NULL::text                           AS nomenklatura_wb,
  NULL::text                           AS ww_code,
  NULL::text                           AS campaign_name,
  NULL::text                           AS purpose,
  bq.canonical_brand                   AS model_hint,
  bq.status                            AS status,
  bq.created_at                        AS created_at,
  NULL::timestamptz                    AS updated_at
FROM crm.branded_queries bq
UNION ALL
SELECT
  ('S' || sa.id::text)::text           AS unified_id,
  sa.id                                AS source_id,
  'substitute_articles'::text          AS source_table,
  CASE
    WHEN sa.purpose = 'creators' AND sa.campaign_name LIKE 'креатор\_%' ESCAPE '\' THEN 'cr_personal'
    WHEN sa.purpose = 'creators'                                                 THEN 'cr_general'
    ELSE                                                                              'external'
  END                                  AS group_kind,
  sa.code                              AS query_text,
  sa.artikul_id                        AS artikul_id,
  sa.nomenklatura_wb                   AS nomenklatura_wb,
  CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END AS ww_code,
  sa.campaign_name                     AS campaign_name,
  sa.purpose                           AS purpose,
  NULL::text                           AS model_hint,
  sa.status                            AS status,
  sa.created_at                        AS created_at,
  sa.updated_at                        AS updated_at
FROM crm.substitute_articles sa;

GRANT SELECT ON marketing.search_queries_unified TO authenticated, service_role;
```

- [ ] **Step 2: Написать RPC для агрегированных stats**

```sql
-- database/marketing/rpcs/2026-05-08-search-query-stats-aggregated.sql
CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(
  p_from date,
  p_to   date
) RETURNS TABLE (
  unified_id text,
  frequency  bigint,
  transitions bigint,
  cart_adds  bigint,
  orders     bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    ('S' || sa.id::text) AS unified_id,
    COALESCE(SUM(m.frequency),  0) AS frequency,
    COALESCE(SUM(m.transitions),0) AS transitions,
    COALESCE(SUM(m.additions),  0) AS cart_adds,
    COALESCE(SUM(m.orders),     0) AS orders
  FROM crm.substitute_articles sa
  LEFT JOIN crm.substitute_article_metrics_weekly m
         ON m.substitute_article_id = sa.id
        AND m.week_start BETWEEN p_from AND p_to
  GROUP BY sa.id;
  -- branded_queries не имеет stats — выводятся с нулями на клиенте
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(date, date) TO authenticated, service_role;
```

- [ ] **Step 3: Применить миграции**

```bash
# Через mcp__plugin_supabase_supabase__apply_migration:
# name: "marketing_search_queries_unified_view"
# query: <содержимое файла Step 1>
#
# name: "marketing_search_query_stats_aggregated_rpc"
# query: <содержимое файла Step 2>
```

- [ ] **Step 4: Smoke-проверить через execute_sql**

```sql
SELECT group_kind, COUNT(*) FROM marketing.search_queries_unified GROUP BY group_kind ORDER BY 1;
-- Ожидаем: brand=0 (пока пусто), cr_general=N, cr_personal=M, external=K. Сумма N+M+K = 87.

SELECT * FROM marketing.search_query_stats_aggregated('2026-03-30','2026-04-27') LIMIT 5;
-- Ожидаем: 5 строк с числами > 0 для топовых артикулов.
```

- [ ] **Step 5: Commit**

```bash
git add database/marketing/views/ database/marketing/rpcs/
git commit -m "feat(marketing): add search_queries_unified VIEW + stats RPC for Hub UI"
```

---

### Task 1.2: Marketing routing + navigation

**Files:**
- Modify: `wookiee-hub/src/config/navigation.ts` — добавить группу `marketing`
- Modify: `wookiee-hub/src/router.tsx` — добавить роуты `/marketing/promo-codes`, `/marketing/search-queries`
- Create: `wookiee-hub/src/pages/marketing/promo-codes.tsx` (skeleton: `<div>TODO</div>`)
- Create: `wookiee-hub/src/pages/marketing/search-queries.tsx` (skeleton)

**Why:** Сначала пустые страницы и навигация, чтобы можно было визуально проверить что меню рендерится корректно до начала наполнения.

- [ ] **Step 1: Skeleton-страницы**

```tsx
// wookiee-hub/src/pages/marketing/promo-codes.tsx
export function PromoCodesPage() {
  return <div className="p-6 text-sm text-muted-foreground">Промокоды — TODO</div>
}
```

```tsx
// wookiee-hub/src/pages/marketing/search-queries.tsx
export function SearchQueriesPage() {
  return <div className="p-6 text-sm text-muted-foreground">Поисковые запросы — TODO</div>
}
```

- [ ] **Step 2: Регистрация в router**

```tsx
// wookiee-hub/src/router.tsx — добавить импорты:
import { PromoCodesPage } from "@/pages/marketing/promo-codes"
import { SearchQueriesPage } from "@/pages/marketing/search-queries"

// В блоке children of AppShell, после analytics-блока:
{ path: "/marketing",                element: <Navigate to="/marketing/promo-codes" replace /> },
{ path: "/marketing/promo-codes",    element: <PromoCodesPage /> },
{ path: "/marketing/search-queries", element: <SearchQueriesPage /> },
```

- [ ] **Step 3: Регистрация в navigation**

```ts
// wookiee-hub/src/config/navigation.ts — после "analytics":
import { Megaphone, Percent, Hash } from "lucide-react"
// ... existing groups ...
{
  id: "marketing",
  icon: Megaphone,
  label: "Маркетинг",
  items: [
    { id: "promo-codes",    label: "Промокоды",        icon: Percent, path: "/marketing/promo-codes"    },
    { id: "search-queries", label: "Поисковые запросы", icon: Hash,    path: "/marketing/search-queries" },
  ],
},
```

- [ ] **Step 4: Запустить dev и визуально проверить**

```bash
cd wookiee-hub && npm run dev
# Открыть http://localhost:5173, авторизоваться, кликнуть на иконку Megaphone в icon-bar.
# Ожидаем: sub-sidebar с двумя пунктами, обе страницы открываются и показывают TODO.
```

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/router.tsx wookiee-hub/src/config/navigation.ts wookiee-hub/src/pages/marketing/
git commit -m "feat(hub): scaffold Marketing section routes + sub-sidebar navigation"
```

---

### Task 1.3: Shared primitives — Badge, KPI, Empty, SectionHeader

**Files:**
- Create: `wookiee-hub/src/components/marketing/Badge.tsx`
- Create: `wookiee-hub/src/components/marketing/KPI.tsx`
- Create: `wookiee-hub/src/components/marketing/Empty.tsx`
- Create: `wookiee-hub/src/components/marketing/SectionHeader.tsx`

**Why:** Лёгкие визуальные атомы, переиспользуются на обеих страницах. Берём дизайн из `wookiee_marketing_v4.jsx` (функции `Badge`, `KPI`, `Empty`, `SectionHeader`), адаптируем `stone-*` на семантические токены.

- [ ] **Step 1: Badge**

Открыть `wookiee_marketing_v4.jsx`, найти функцию `Badge` (~строки 305–310). Перенести с заменой:
- `bg-emerald-50 text-emerald-700` → оставить (semantic accent для status — допустимо)
- `bg-stone-100 text-stone-600` → `bg-muted text-muted-foreground`
- `ring-stone-500/20` → `ring-border`
- `bg-stone-400` → `bg-muted-foreground`

Типизировать: `color: 'green' | 'blue' | 'amber' | 'gray'`, `compact?: boolean`. Экспорт named.

- [ ] **Step 2: KPI**

JSX: функция `KPI` (~строка 311). Замены:
- `bg-white` → `bg-card`
- `border-stone-200` → `border-border`
- `text-stone-400` → `text-muted-foreground`
- `text-stone-900` → `text-foreground`

Props: `label: string`, `value: ReactNode`, `sub?: string`. Класс `tabular-nums` сохранить.

- [ ] **Step 3: Empty**

JSX: функция `Empty` (~строка 312). Замены: `text-stone-300` → `text-muted-foreground/50`, `text-stone-400` → `text-muted-foreground`. Иконка `Clock` из `lucide-react`.

- [ ] **Step 4: SectionHeader**

JSX: функция `SectionHeader` (~строки 380–395). Это `<tr>` с `colSpan={12}`. Замены: `bg-stone-50/80` → `bg-muted/50`, `border-stone-200` → `border-border`, `text-stone-400` → `text-muted-foreground`, `text-stone-700` → `text-foreground`.

Props: `group: { id: string; label: string; icon: string }`, `count: number`, `collapsed: boolean`, `onToggle: () => void`, `colSpan?: number` (default 12).

- [ ] **Step 5: Smoke-test через temp story**

Создать `wookiee-hub/src/pages/marketing/__playground__.tsx` со всеми 4 компонентами в выводе. Открыть в браузере на `/marketing/__playground__` (зарегистрировать роут временно). Визуально сверить с JSX-прототипом — те же отступы, тот же размер шрифта, та же типографика.

- [ ] **Step 6: Удалить playground, commit**

```bash
git add wookiee-hub/src/components/marketing/
git commit -m "feat(marketing): Badge, KPI, Empty, SectionHeader primitives"
```

---

### Task 1.4: SelectMenu (custom dropdown с поиском и «+ Добавить»)

**Files:**
- Create: `wookiee-hub/src/components/marketing/SelectMenu.tsx`
- Create: `wookiee-hub/src/components/marketing/__tests__/SelectMenu.test.tsx`

**Why:** Ядерный компонент — используется для канала, кампании, модели в обеих формах. JSX-вариант (~строки 320–375) ручной dropdown. У Hub есть `@radix-ui/react-popover` + `cmdk` — можно построить надёжнее на них, но **визуально точно как в JSX**.

- [ ] **Step 1: Перенести JSX 1:1 (использовать Radix Popover + Command под капотом)**

```tsx
// wookiee-hub/src/components/marketing/SelectMenu.tsx
import * as React from "react"
import * as Popover from "@radix-ui/react-popover"
import { Command, CommandInput, CommandList, CommandItem, CommandEmpty } from "@/components/ui/command"
import { ChevronDown, Check, Plus, X } from "lucide-react"

type Option = { value: string; label: string } | string

export interface SelectMenuProps {
  label?: string
  value: string
  options: Option[]
  onChange: (v: string) => void
  allowAdd?: boolean
  placeholder?: string
}

export function SelectMenu({ label, value, options, onChange, allowAdd, placeholder = "Выбрать…" }: SelectMenuProps) {
  // Реализация — повторяет визуал JSX функции SelectMenu (триггер с chevron, popover-список с поиском при >5 опций, отметка checkmark, опция «— Empty —», блок «+ Добавить новый»).
  // Для уменьшения объёма плана — детали из JSX, но c заменой stone-* → semantic tokens.
}
```

Полная реализация — построчно перенести из JSX функции `SelectMenu`, заменив:
- `border-stone-200` → `border-border`
- `bg-white` → `bg-card`
- `text-stone-900` → `text-foreground`
- `text-stone-400/500/600/700` → `text-muted-foreground` (для приглушённых) или `text-foreground` (для активных)
- `hover:bg-stone-50` → `hover:bg-muted`
- `text-emerald-600` → `text-[var(--wk-green)]`
- `bg-stone-50/0` (фон поиска) → `bg-muted`

- [ ] **Step 2: Тест базовой механики**

```tsx
// __tests__/SelectMenu.test.tsx
import { render, screen, fireEvent } from "@testing-library/react"
import { SelectMenu } from "../SelectMenu"

it("opens, lists options, calls onChange", () => {
  const handle = vi.fn()
  render(<SelectMenu value="" options={["A","B","C"]} onChange={handle} />)
  fireEvent.click(screen.getByRole("button"))
  fireEvent.click(screen.getByText("B"))
  expect(handle).toHaveBeenCalledWith("B")
})

it("allowAdd inserts new value", () => {
  const handle = vi.fn()
  render(<SelectMenu value="" options={["A"]} onChange={handle} allowAdd />)
  fireEvent.click(screen.getByRole("button"))
  fireEvent.click(screen.getByText("Добавить новый"))
  fireEvent.change(screen.getByPlaceholderText(/Новое/), { target: { value: "Новый канал" } })
  fireEvent.click(screen.getByLabelText(/подтвердить/i))
  expect(handle).toHaveBeenCalledWith("Новый канал")
})
```

- [ ] **Step 3: Запустить тесты**

```bash
cd wookiee-hub && npm test -- SelectMenu
# Ожидаем: 2 passed
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/marketing/SelectMenu.tsx wookiee-hub/src/components/marketing/__tests__/
git commit -m "feat(marketing): SelectMenu (popover-based custom dropdown with allowAdd)"
```

---

### Task 1.5: StatusEditor + DateRange + UpdateBar

**Files:**
- Create: `wookiee-hub/src/components/marketing/StatusEditor.tsx`
- Create: `wookiee-hub/src/components/marketing/DateRange.tsx`
- Create: `wookiee-hub/src/components/marketing/UpdateBar.tsx`

**Why:** Три специализированных компонента. StatusEditor использует SelectMenu внутри. DateRange — два `<input type="date">` с min/max. UpdateBar пока заглушка (timestamp хардкод), на Phase 3 свяжется с `marketing.sync_log`.

- [ ] **Step 1: StatusEditor**

JSX функция `StatusEditor` (~строки 397–420). Props: `status: 'active'|'free'|'archive'`, `onChange: (s) => void`. Использовать SelectMenu или Radix DropdownMenu (как в JSX). Палитра badge через `Badge` компонент.

- [ ] **Step 2: DateRange**

JSX функция `DateRange` (~строки 377–388). Props: `from: string` (ISO), `to: string`, `onChange: (from, to) => void`, `min?: string`, `max?: string`. Заменить fixed `w-[120px]` на отзывчивое.

- [ ] **Step 3: UpdateBar (заглушка)**

JSX функция `UpdateBar` (~строки 390–406). На Phase 1 timestamp хардкод (текущая дата минус 1 день). Spinner работает локально (имитация). Phase 3 — заменим на реальный sync_log.

```tsx
export function UpdateBar({ lastUpdate, completeness, onSync }: { lastUpdate: string; completeness: string; onSync?: () => Promise<void> }) {
  // Реализация из JSX — replace stone-* → semantic tokens.
}
```

- [ ] **Step 4: Smoke-test в playground**

Зарегистрировать снова `__playground__` route, рендерить эти 3 компонента + Phase-1 примитивы. Проверить визуально.

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/components/marketing/{StatusEditor,DateRange,UpdateBar}.tsx
git commit -m "feat(marketing): StatusEditor, DateRange, UpdateBar primitives"
```

---

### Task 1.6: API + hooks layer (search queries + promo codes)

**Files:**
- Create: `wookiee-hub/src/api/marketing/search-queries.ts`
- Create: `wookiee-hub/src/api/marketing/promo-codes.ts`
- Create: `wookiee-hub/src/hooks/marketing/use-search-queries.ts`
- Create: `wookiee-hub/src/hooks/marketing/use-promo-codes.ts`
- Create: `wookiee-hub/src/types/marketing.ts`

**Why:** Слой данных отделен от UI — соответствует patterns из `src/api/crm/bloggers.ts`. TanStack Query для кэша + invalidation.

- [ ] **Step 1: Типы**

```ts
// wookiee-hub/src/types/marketing.ts
export type SearchQueryGroup = 'brand' | 'external' | 'cr_general' | 'cr_personal'
export type SearchQueryStatus = 'active' | 'free' | 'archive'

export interface SearchQueryRow {
  unified_id: string       // 'B1' | 'S42'
  source_id: number
  source_table: 'branded_queries' | 'substitute_articles'
  group_kind: SearchQueryGroup
  query_text: string
  artikul_id: number | null
  nomenklatura_wb: string | null
  ww_code: string | null
  campaign_name: string | null
  purpose: string | null
  model_hint: string | null
  status: SearchQueryStatus
  created_at: string
  updated_at: string | null
}

export interface SearchQueryStatsAgg {
  unified_id: string
  frequency: number
  transitions: number
  cart_adds: number
  orders: number
}

export interface SearchQueryWeeklyStat {
  search_query_id: number  // substitute_article_id
  week_start: string
  frequency: number
  transitions: number
  additions: number
  orders: number
}

export interface PromoCodeRow {
  id: number
  code: string
  name: string | null
  external_uuid: string | null
  channel: string | null
  discount_pct: number | null
  valid_from: string | null
  valid_until: string | null
  status: 'active' | 'unidentified' | 'archive'
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PromoStatWeekly {
  promo_code_id: number
  week_start: string
  sales_rub: number
  payout_rub: number
  orders_count: number
  returns_count: number
  avg_discount_pct: number
  avg_check: number
}
```

- [ ] **Step 2: API search-queries**

```ts
// wookiee-hub/src/api/marketing/search-queries.ts
import { supabase } from '@/lib/supabase'
import type { SearchQueryRow, SearchQueryStatsAgg, SearchQueryWeeklyStat } from '@/types/marketing'

export async function fetchSearchQueries(): Promise<SearchQueryRow[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('search_queries_unified')
    .select('*')
    .order('updated_at', { ascending: false, nullsFirst: false })
  if (error) throw error
  return (data ?? []) as SearchQueryRow[]
}

export async function fetchSearchQueryStats(from: string, to: string): Promise<SearchQueryStatsAgg[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .rpc('search_query_stats_aggregated', { p_from: from, p_to: to })
  if (error) throw error
  return (data ?? []) as SearchQueryStatsAgg[]
}

export async function fetchSearchQueryWeekly(substituteArticleId: number): Promise<SearchQueryWeeklyStat[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('search_query_stats_weekly')
    .select('*')
    .eq('search_query_id', substituteArticleId)
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as SearchQueryWeeklyStat[]
}
```

- [ ] **Step 3: API promo-codes**

```ts
// wookiee-hub/src/api/marketing/promo-codes.ts
import { supabase } from '@/lib/supabase'
import type { PromoCodeRow, PromoStatWeekly } from '@/types/marketing'

export async function fetchPromoCodes(): Promise<PromoCodeRow[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('promo_codes')
    .select('*')
    .order('updated_at', { ascending: false })
  if (error) throw error
  return (data ?? []) as PromoCodeRow[]
}

export async function fetchPromoStatsWeekly(): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('promo_stats_weekly')
    .select('*')
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as PromoStatWeekly[]
}

export async function fetchPromoStatsForCode(promoCodeId: number): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase
    .schema('marketing')
    .from('promo_stats_weekly')
    .select('*')
    .eq('promo_code_id', promoCodeId)
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as PromoStatWeekly[]
}
```

- [ ] **Step 4: Hooks**

```ts
// wookiee-hub/src/hooks/marketing/use-search-queries.ts
import { useQuery } from '@tanstack/react-query'
import { fetchSearchQueries, fetchSearchQueryStats, fetchSearchQueryWeekly } from '@/api/marketing/search-queries'

export const searchQueriesKeys = {
  all: ['marketing', 'search-queries'] as const,
  list: () => [...searchQueriesKeys.all, 'list'] as const,
  stats: (from: string, to: string) => [...searchQueriesKeys.all, 'stats', from, to] as const,
  weekly: (id: number) => [...searchQueriesKeys.all, 'weekly', id] as const,
}

export function useSearchQueries() {
  return useQuery({ queryKey: searchQueriesKeys.list(), queryFn: fetchSearchQueries, staleTime: 5 * 60_000 })
}

export function useSearchQueryStats(from: string, to: string) {
  return useQuery({ queryKey: searchQueriesKeys.stats(from, to), queryFn: () => fetchSearchQueryStats(from, to), staleTime: 60_000 })
}

export function useSearchQueryWeekly(substituteArticleId: number | null) {
  return useQuery({
    queryKey: searchQueriesKeys.weekly(substituteArticleId ?? -1),
    queryFn: () => fetchSearchQueryWeekly(substituteArticleId!),
    enabled: substituteArticleId != null,
  })
}
```

```ts
// wookiee-hub/src/hooks/marketing/use-promo-codes.ts
// Аналогично — useQuery поверх api/marketing/promo-codes.ts
```

- [ ] **Step 5: Smoke-test через React Query Devtools**

```bash
# В компоненте PromoCodesPage временно:
const { data } = usePromoCodes()
console.log('promo', data)
# Открыть страницу, проверить в консоли: должно быть 6 промокодов.
```

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/api/marketing/ wookiee-hub/src/hooks/marketing/ wookiee-hub/src/types/marketing.ts
git commit -m "feat(marketing): API + TanStack Query hooks for search queries and promo codes"
```

---

### Task 1.7: Промокоды — таблица + KPI + фильтры (read-only)

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx` (полная замена skeleton)
- Create: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`

**Why:** Главный экран промокодов. JSX функция `PromoPage` (~строки 545–620) даёт полный референс. Перенос с заменой mocks → real hooks.

- [ ] **Step 1: PromoCodesTable**

Перенести JSX `PromoPage` table структуру (KPI grid + UpdateBar + search input + DateRange + table + sticky tfoot). Mock `PROMOS` заменить на `usePromoCodes()`. Колонки 1:1 как в JSX: Код | Канал | Скидка | Статус | Продажи, шт | Продажи, ₽ | Ср. чек, ₽.

Aggregate из недельной статистики: orders_count, sales_rub. На клиенте в `useMemo`.

```tsx
const { data: promos = [] } = usePromoCodes()
const { data: weeklyStats = [] } = usePromoStatsWeekly()

const enriched = useMemo(() => {
  const byId = new Map<number, { qty: number; sales: number }>()
  for (const w of weeklyStats) {
    if (!w.promo_code_id) continue
    const cur = byId.get(w.promo_code_id) ?? { qty: 0, sales: 0 }
    cur.qty   += w.orders_count ?? 0
    cur.sales += Number(w.sales_rub ?? 0)
    byId.set(w.promo_code_id, cur)
  }
  return promos.map(p => ({ ...p, qty: byId.get(p.id)?.qty ?? 0, sales: byId.get(p.id)?.sales ?? 0 }))
}, [promos, weeklyStats])
```

DateRange пока чисто визуальный (фильтрация stats придёт в Phase 2 с разбивкой по дате).

- [ ] **Step 2: Page-обёртка с PageHeader**

```tsx
// promo-codes.tsx — новый файл
import { PageHeader } from "@/components/crm/layout/PageHeader"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"

export function PromoCodesPage() {
  return (
    <>
      <PageHeader
        title="Промокоды"
        sub="Статистика по кодам скидок"
        actions={null /* Add будет в Phase 2 */}
      />
      <PromoCodesTable />
    </>
  )
}
```

- [ ] **Step 3: Запустить, визуально сверить**

```bash
cd wookiee-hub && npm run dev
# Открыть /marketing/promo-codes. Должны видеть:
# - 4 KPI наверху (Активных X из 6 / Продажи шт / Продажи ₽ / Ср. чек ₽)
# - UpdateBar (заглушка timestamp)
# - Search input + DateRange
# - Таблица 6 строк, отсортирована по продажам ₽ desc
# - Sticky tfoot с итогами
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes*
git commit -m "feat(marketing): Promo Codes page table + KPIs (read-only)"
```

---

### Task 1.8: Промокоды — detail panel (товарная разбивка пока заглушка + weekly)

**Files:**
- Create: `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx` (открытие панели)

**Why:** JSX `PromoPanel` (~строки 510–540). На Phase 1 — read-only view (без edit toggle). Товарная разбивка `marketing.promo_product_breakdown` ещё не существует — рендерим Empty заглушку.

- [ ] **Step 1: Skeleton panel**

```tsx
// PromoDetailPanel.tsx
export function PromoDetailPanel({ promoId, onClose }: { promoId: number; onClose: () => void }) {
  const { data: promos = [] } = usePromoCodes()
  const { data: weekly = [] } = useQuery({ queryKey: ['promo-weekly', promoId], queryFn: () => fetchPromoStatsForCode(promoId) })
  const promo = promos.find(p => p.id === promoId)
  if (!promo) return null
  // 1. Header (code, badge, channel)
  // 2. Read-only форма (код / канал / скидка / даты)
  // 3. KPI блок: Продажи шт / Продажи ₽ / Ср. чек
  // 4. Empty заглушка для «Товарная разбивка» (Phase 2 заполнит)
  // 5. Таблица "По неделям" из weekly
}
```

Структура и стили — 1:1 из JSX `PromoPanel`, но без `edit` toggle (всегда view).

- [ ] **Step 2: Открытие из таблицы через URL state**

```tsx
// PromoCodesTable.tsx
const [searchParams, setSearchParams] = useSearchParams()
const openId = searchParams.get('open')
const selectedId = openId ? Number(openId) : null

const openPanel = (id: number) => setSearchParams(p => { p.set('open', String(id)); return p })
const closePanel = () => setSearchParams(p => { p.delete('open'); return p })

// onClick={() => openPanel(promo.id)} на каждой строке
// {selectedId && <PromoDetailPanel promoId={selectedId} onClose={closePanel} />}
```

- [ ] **Step 3: Layout — основная таблица + панель сбоку**

Контейнер `<div className="flex">` — таблица занимает flex-1, панель `w-[400px] border-l` справа. Идентично JSX layout.

- [ ] **Step 4: Smoke-test**

Открыть `/marketing/promo-codes`, кликнуть по CHARLOTTE10 → панель открывается справа, видна агрегированная статистика 7+1=8 заказов, 12433₽, и две недельные строки (02 мар + 09 мар). Закрытие крестиком.

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes/
git commit -m "feat(marketing): Promo Codes — detail panel (read-only with weekly stats)"
```

---

### Task 1.9: Поисковые запросы — page (все секции + воронка)

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries.tsx`
- Create: `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`
- Create: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`

**Why:** Самый сложный экран. JSX функция `SearchPage` (~строки 422–535). Включает: pills модель + pills канал, search input, DateRange, collapsible секции (4), полная воронка (Частота → Переходы → CR→корз → Корз → CR→зак → Заказы → CRV), sticky totals.

- [ ] **Step 1: SearchQueriesTable**

```tsx
// SearchQueriesTable.tsx
const { data: items = [] } = useSearchQueries()
const { data: aggStats = [] } = useSearchQueryStats(dateFrom, dateTo)

const statsById = useMemo(() => new Map(aggStats.map(s => [s.unified_id, s])), [aggStats])

const filtered = useMemo(() => {
  let list = items
  if (modelFilter !== 'all')   list = list.filter(i => /* по model_hint или campaign_name */)
  if (channelFilter !== 'all') list = list.filter(i => i.purpose === channelFilter)
  if (search)                   list = list.filter(i => searchText(i).includes(search.toLowerCase()))
  return list
}, [items, modelFilter, channelFilter, search])

const grouped = useMemo(() => {
  const buckets: Record<SearchQueryGroup, SearchQueryRow[]> = { brand: [], external: [], cr_general: [], cr_personal: [] }
  for (const item of filtered) buckets[item.group_kind].push(item)
  // Сортировка внутри секции по orders desc
  for (const k of Object.keys(buckets) as SearchQueryGroup[]) {
    buckets[k].sort((a, b) => (statsById.get(b.unified_id)?.orders ?? 0) - (statsById.get(a.unified_id)?.orders ?? 0))
  }
  return buckets
}, [filtered, statsById])
```

Колонки таблицы 1:1 из JSX (Запрос | Артикул | Канал | Кампания | Частота | Перех. | CR→корз | Корз. | CR→зак | Заказы | CRV).

CR-проценты вычисляются на клиенте: `pct(a, b)` = `b > 0 ? ((a/b)*100).toFixed(1) + '%' : '—'`.

Sticky totals — суммы по `filtered`, как в JSX функции `SearchPage`.

- [ ] **Step 2: Pills filters в header**

`uniqueModels` — из `items.map(i => i.model_hint).filter(Boolean)`. `uniqueChannels` — из `items.map(i => i.purpose).filter(Boolean)`. Pills как в JSX (строки 444–462).

- [ ] **Step 3: SearchQueryDetailPanel**

JSX функция `SQPanel` (~строки 465–530). Содержит:
- Header: query + StatusEditor (на Phase 1 — read-only badge, без edit) + channel
- Привязка к товару (nm/ww/art/model)
- Воронка за выбранный период (каскад с CR между шагами)
- Таблица по неделям (toggle "На период" / "Все недели") — данные из `useSearchQueryWeekly(item.source_id)` если `source_table === 'substitute_articles'`. Для brand нет stats — Empty.

- [ ] **Step 4: Page-обёртка**

```tsx
export function SearchQueriesPage() {
  return (
    <>
      <PageHeader title="Поисковые запросы" sub="Брендовые, артикулы и подменные WW-коды" />
      <SearchQueriesTable />
    </>
  )
}
```

- [ ] **Step 5: Smoke-test**

```bash
npm run dev
# /marketing/search-queries → должен показывать 87 запросов в 3 непустых группах (cr_general, cr_personal, external) + пустой brand.
# Pills фильтры работают.
# Sticky totals меняются при фильтрации.
# Клик по строке → панель справа, воронка с реальными числами для substitute_articles.
```

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries*
git commit -m "feat(marketing): Search Queries page — pills, sections, funnel, detail panel"
```

---

### Task 1.10: Phase 1 verification + manual smoke

**Files:** none

- [ ] **Step 1: Build prod**

```bash
cd wookiee-hub && npm run build
# Ожидаем: green build, 0 errors.
```

- [ ] **Step 2: Запустить dev и пройти E2E (manual)**

Открыть https://localhost:5173:
1. Login → главная
2. Megaphone в icon-bar → sub-sidebar «Маркетинг»
3. Промокоды:
   - 4 KPI карточки заполнены
   - 6 промокодов в таблице (CHARLOTTE10 первый по продажам)
   - Sticky totals корректны
   - Клик CHARLOTTE10 → панель справа, weekly stats 02 мар (10845₽, 7) + 09 мар (1588₽, 1)
   - URL содержит `?open=1`, refresh → панель остаётся
   - Закрытие крестиком убирает `?open` из URL
4. Поисковые запросы:
   - 87 строк в 3 секциях (brand=0)
   - Pills модель: при выборе Wendy — фильтр работает, totals пересчитываются
   - Pills канал: creators / yandex / adblogger / vk_target / other
   - DateRange сужает период → числа в таблице меняются
   - Клик по `WW121790` (Wendy/dark_beige_S) → воронка с числами, weekly таблица
   - Brand-секция пуста (т.к. `crm.branded_queries` пуста) — это OK
5. Все остальные разделы Hub (catalog, operations, community, influence, analytics) **не сломаны**.

- [ ] **Step 3: Документировать в Phase 1 Done**

Создать `docs/superpowers/plans/2026-05-08-marketing-hub-impl-phase1-done.md` с скриншотами/findings.

- [ ] **Step 4: Tag commit**

```bash
git tag marketing-phase-1-complete
git push --tags
```

---

## Phase 2 — CRUD + новые поля

### Task 2.1: Migration `marketing.channels` registry

**Files:**
- Create: `database/marketing/tables/2026-05-08-channels.sql`

**Why:** UI требует справочник каналов с возможностью добавлять новые. Сейчас канал — это `crm.substitute_articles.purpose` (text). Переходим на FK к `marketing.channels`. Миграция данных + обновление VIEW.

- [ ] **Step 1: Таблица + seed**

```sql
CREATE TABLE marketing.channels (
  id          bigserial PRIMARY KEY,
  slug        text NOT NULL UNIQUE,        -- 'yandex', 'creators', и т.д.
  label       text NOT NULL,                -- 'Яндекс', 'Креаторы', и т.д.
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE marketing.channels ENABLE ROW LEVEL SECURITY;
CREATE POLICY channels_read ON marketing.channels FOR SELECT TO authenticated USING (true);
CREATE POLICY channels_write_authd ON marketing.channels FOR INSERT TO authenticated WITH CHECK (true);
GRANT SELECT, INSERT ON marketing.channels TO authenticated;
GRANT USAGE ON SEQUENCE marketing.channels_id_seq TO authenticated;

INSERT INTO marketing.channels (slug, label) VALUES
  ('brand',     'Бренд'),
  ('yandex',    'Яндекс'),
  ('vk_target', 'Таргет ВК'),
  ('adblogger', 'Adblogger'),
  ('creators',  'Креаторы'),
  ('smm',       'SMM'),
  ('other',     'Прочее'),
  ('social',    'Соцсети'),
  ('blogger',   'Блогер'),
  ('corp',      'Корп'),
  ('yps',       'ЯПС'),
  ('mvp',       'МВП');
```

- [ ] **Step 2: Применить через apply_migration, smoke-проверить**

```sql
SELECT * FROM marketing.channels ORDER BY id;
-- Ожидаем 12 строк.
```

- [ ] **Step 3: Commit**

```bash
git add database/marketing/tables/
git commit -m "feat(marketing): channels registry table + seed 12 base channels"
```

---

### Task 2.2: Migration `crm.substitute_articles.creator_ref` + group_kind helper

**Files:**
- Create: `database/marketing/migrations/2026-05-08-add-creator-ref.sql`
- Modify: `database/marketing/views/2026-05-08-search-queries-unified.sql` (включить creator_ref в output)

**Why:** Добавляем поле `creator_ref text` для personal creators. Сейчас имя креатора зашито в `campaign_name` (`креатор_Шматок`). Извлекаем при миграции, очищаем `campaign_name`.

- [ ] **Step 1: Миграция**

```sql
ALTER TABLE crm.substitute_articles ADD COLUMN creator_ref text;

UPDATE crm.substitute_articles
SET creator_ref = regexp_replace(campaign_name, '^креатор_', '')
WHERE campaign_name LIKE 'креатор_%';

CREATE INDEX idx_substitute_articles_creator_ref ON crm.substitute_articles(creator_ref);
```

- [ ] **Step 2: Обновить VIEW**

```sql
CREATE OR REPLACE VIEW marketing.search_queries_unified AS
-- ... как Task 1.1, но добавить колонку sa.creator_ref в SELECT для substitute_articles ветки
```

- [ ] **Step 3: Применить, проверить**

```sql
SELECT creator_ref, COUNT(*) FROM crm.substitute_articles WHERE creator_ref IS NOT NULL GROUP BY creator_ref ORDER BY 1;
-- Ожидаем: Донцова, Малашкина, Токмачева, Чиркина, Шматок, Юдина, ... (≥6 имён)
```

- [ ] **Step 4: Обновить TypeScript тип**

```ts
// types/marketing.ts
export interface SearchQueryRow {
  // ... existing fields
  creator_ref: string | null
}
```

- [ ] **Step 5: Commit**

```bash
git add database/marketing/ wookiee-hub/src/types/marketing.ts
git commit -m "feat(marketing): creator_ref field on substitute_articles + extract from campaign_name"
```

---

### Task 2.3: Migration `marketing.promo_product_breakdown`

**Files:**
- Create: `database/marketing/tables/2026-05-08-promo-product-breakdown.sql`

**Why:** UI показывает товарную разбивку для каждого промокода. Сейчас этих данных нет. Создаём таблицу + ETL её заполнит. Phase 1 — заглушка-Empty; Phase 2 — реальные данные.

- [ ] **Step 1: Таблица**

```sql
CREATE TABLE marketing.promo_product_breakdown (
  id              bigserial PRIMARY KEY,
  promo_code_id   bigint NOT NULL REFERENCES crm.promo_codes(id) ON DELETE CASCADE,
  week_start      date NOT NULL,
  artikul_id      integer,
  sku_label       text NOT NULL,
  model_code      text,
  qty             integer NOT NULL DEFAULT 0,
  amount_rub      numeric NOT NULL DEFAULT 0,
  captured_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (promo_code_id, week_start, sku_label)
);

CREATE INDEX idx_ppb_promo_code ON marketing.promo_product_breakdown(promo_code_id);
ALTER TABLE marketing.promo_product_breakdown ENABLE ROW LEVEL SECURITY;
CREATE POLICY ppb_read  ON marketing.promo_product_breakdown FOR SELECT TO authenticated USING (true);
CREATE POLICY ppb_write ON marketing.promo_product_breakdown FOR ALL    TO service_role  USING (true);
GRANT SELECT ON marketing.promo_product_breakdown TO authenticated;
GRANT ALL    ON marketing.promo_product_breakdown TO service_role;
```

- [ ] **Step 2: Бэкфилл из существующего ETL — отдельная задача, вне scope этого плана**

Phase 2 не требует backfill — пустая таблица OK. UI рисует Empty заглушку.

- [ ] **Step 3: Commit**

```bash
git add database/marketing/tables/2026-05-08-promo-product-breakdown.sql
git commit -m "feat(marketing): promo_product_breakdown table (per-week per-sku promo decomposition)"
```

---

### Task 2.4: AddPromoPanel — drawer-форма создания промокода

**Files:**
- Create: `wookiee-hub/src/pages/marketing/promo-codes/AddPromoPanel.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx` — кнопка «+ Добавить» в PageHeader actions
- Modify: `wookiee-hub/src/api/marketing/promo-codes.ts` — `createPromoCode()`

**Why:** JSX функция `PromoPanel` режим `mode='add'` (~строки 510–540). Форма: код / канал (SelectMenu allowAdd) / скидка / даты. INSERT в `crm.promo_codes`.

- [ ] **Step 1: API mutation**

```ts
export interface PromoCreate {
  code: string
  name?: string
  external_uuid?: string
  channel?: string
  discount_pct?: number
  valid_from?: string
  valid_until?: string
}

export async function createPromoCode(input: PromoCreate): Promise<PromoCodeRow> {
  const { data, error } = await supabase
    .schema('crm')
    .from('promo_codes')
    .insert({
      code: input.code.toUpperCase(),
      name: input.name ?? null,
      external_uuid: input.external_uuid ?? null,
      channel: input.channel ?? null,
      discount_pct: input.discount_pct ?? null,
      valid_from: input.valid_from ?? null,
      valid_until: input.valid_until ?? null,
      status: 'active',
    })
    .select('*')
    .single()
  if (error) throw error
  return data as PromoCodeRow
}
```

```ts
// hooks/marketing/use-promo-codes.ts
export function useCreatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createPromoCode,
    onSuccess: () => qc.invalidateQueries({ queryKey: promoCodesKeys.all }),
  })
}
```

- [ ] **Step 2: AddPromoPanel компонент**

JSX `PromoPanel` (mode=add) — input для кода, SelectMenu для канала с allowAdd, number для скидки, date inputs, кнопка «Создать». На submit → `createPromo.mutateAsync({...form})`, при успехе — `onClose()` и toast.

Каналы для SelectMenu — fetch из `marketing.channels`:

```ts
// api/marketing/channels.ts
export async function fetchChannels(): Promise<Channel[]> {
  const { data, error } = await supabase.schema('marketing').from('channels').select('*').eq('is_active', true).order('label')
  if (error) throw error
  return data ?? []
}

export async function createChannel(slug: string, label: string): Promise<Channel> {
  const { data, error } = await supabase.schema('marketing').from('channels').insert({ slug, label }).select('*').single()
  if (error) throw error
  return data
}
```

- [ ] **Step 3: Кнопка «+ Добавить» в PageHeader**

```tsx
<PageHeader
  title="Промокоды"
  actions={<Button onClick={() => setSearchParams(p => { p.set('add', '1'); return p })}>+ Добавить</Button>}
/>

{searchParams.get('add') && <AddPromoPanel onClose={() => setSearchParams(p => { p.delete('add'); return p })} />}
```

- [ ] **Step 4: E2E проверка**

```bash
npm run dev
# /marketing/promo-codes → клик «+ Добавить» → drawer открыт
# Заполнить: код TEST10, канал «Соцсети» (или новый "Тест" через allowAdd), скидка 10
# Создать → drawer закрывается, в таблице 7 строк, TEST10 виден
# /api проверка: SELECT * FROM crm.promo_codes WHERE code='TEST10'; → 1 row
# Cleanup: DELETE FROM crm.promo_codes WHERE code='TEST10';
```

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes/AddPromoPanel.tsx wookiee-hub/src/api/marketing/ wookiee-hub/src/hooks/marketing/
git commit -m "feat(marketing): AddPromoPanel drawer — create promo codes through UI"
```

---

### Task 2.5: AddWWPanel — каскадная форма WW-кода

**Files:**
- Create: `wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx`
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` — `createSubstituteArticle()`
- Modify: `wookiee-hub/src/pages/marketing/search-queries.tsx` — кнопка в PageHeader

**Why:** JSX функция `AddWWPanel` (~строки 480–510). Каскад: модель → цвет → размер → авто-привязка SKU (artikul_id). Затем WW-код, канал, кампания, тип (общий/личный). INSERT в `crm.substitute_articles`.

- [ ] **Step 1: API**

```ts
export interface SubstituteArticleCreate {
  code: string
  artikul_id: number
  purpose: string                 // canonicalized to channel slug
  nomenklatura_wb?: string
  campaign_name?: string
  creator_ref?: string             // for cr_personal
}

export async function createSubstituteArticle(input: SubstituteArticleCreate): Promise<void> {
  const { error } = await supabase
    .schema('crm')
    .from('substitute_articles')
    .insert({ ...input, status: 'active' })
  if (error) throw error
}
```

- [ ] **Step 2: Cascade SKU lookup**

Использовать существующую `crm.skus` (или `catalog.tovary`) для автозаполнения artikul_id. API hook:

```ts
// api/catalog/skus.ts (если ещё нет)
export async function lookupSku(model: string, color: string, size: string): Promise<{ id: number; nomenklatura_wb: string } | null> {
  const { data } = await supabase.schema('catalog').from('skus')
    .select('id, nomenklatura_wb')
    .eq('model_code', model).eq('color_slug', color).eq('size_slug', size)
    .maybeSingle()
  return data
}
```

(Если таблица называется иначе — проверить через `mcp__plugin_supabase_supabase__list_tables` schema=catalog. Скорее всего `catalog.skus` или `catalog.tovary`.)

- [ ] **Step 3: AddWWPanel компонент**

JSX `AddWWPanel` 1:1, но с реальными данными:
- Список моделей: `useQuery(['models'], () => fetchModels())` из `catalog.modeli` (или захардкодить временно — список known models)
- Цвета по модели: `useQuery(['colors', model], ...)`
- Размеры: ['XS','S','M','L','XL']
- При (model, color, size) → `lookupSku()` → показать привязанный SKU
- Tabs / radio для типа: «общий креатор / личный креатор / номенклатура (yandex/adblogger/vk)»
- Channel SelectMenu allowAdd
- Campaign SelectMenu allowAdd
- При submit → `createSubstituteArticle()`

- [ ] **Step 4: E2E проверка**

```bash
npm run dev
# /marketing/search-queries → «+ Добавить WW-код»
# Wendy → white → S → SKU привязан 163151603
# WW-код WW999000, канал creators, кампания "Тест"
# Создать → строка появляется в секции «Креаторы общие»
# Cleanup: DELETE FROM crm.substitute_articles WHERE code='WW999000';
```

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx wookiee-hub/src/api/marketing/search-queries.ts
git commit -m "feat(marketing): AddWWPanel — cascade form for WW-codes with SKU autobinding"
```

---

### Task 2.6: Status edit — StatusEditor connected

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx` — wire StatusEditor
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` — `updateSearchQueryStatus()`

**Why:** На Phase 1 StatusEditor был read-only. Теперь — реальный UPDATE в БД.

- [ ] **Step 1: API**

```ts
export async function updateSearchQueryStatus(unifiedId: string, status: SearchQueryStatus): Promise<void> {
  const sourceTable = unifiedId.startsWith('B') ? 'branded_queries' : 'substitute_articles'
  const sourceId = Number(unifiedId.slice(1))
  const { error } = await supabase
    .schema('crm')
    .from(sourceTable)
    .update({ status, updated_at: new Date().toISOString() })
    .eq('id', sourceId)
  if (error) throw error
}
```

- [ ] **Step 2: Hook**

```ts
export function useUpdateSearchQueryStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ unifiedId, status }: { unifiedId: string; status: SearchQueryStatus }) => updateSearchQueryStatus(unifiedId, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}
```

- [ ] **Step 3: Wire в SearchQueryDetailPanel**

```tsx
const updateStatus = useUpdateSearchQueryStatus()
<StatusEditor status={item.status} onChange={(s) => updateStatus.mutate({ unifiedId: item.unified_id, status: s })} />
```

- [ ] **Step 4: E2E**

Открыть один из WW-кодов → StatusEditor → переключить на «Свободен» → проверить в БД:

```sql
SELECT status FROM crm.substitute_articles WHERE code='WW121790';
-- Ожидаем 'free'
-- Restore: UPDATE crm.substitute_articles SET status='active' WHERE code='WW121790';
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(marketing): wire StatusEditor to update search query status"
```

---

### Task 2.7: Phase 2 verification

- [ ] **Step 1: Build prod + manual E2E**

Все CRUD-flow:
1. Создать промокод TEST_PROMO → виден в таблице → удалить через SQL
2. Создать WW-код TEST_WW → виден в секции → удалить
3. Изменить статус существующего → проверить персистентность через refresh
4. Добавить новый канал через SelectMenu (allowAdd) → проверить что попал в `marketing.channels`

- [ ] **Step 2: Tag**

```bash
git tag marketing-phase-2-complete
```

---

## Phase 3 — Sync infrastructure

### Task 3.1: Migration `marketing.sync_log`

**Files:**
- Create: `database/marketing/tables/2026-05-08-sync-log.sql`

- [ ] **Step 1: Таблица**

```sql
CREATE TABLE marketing.sync_log (
  id              bigserial PRIMARY KEY,
  job_name        text NOT NULL,                 -- 'promo_codes_sync' | 'search_queries_sync'
  status          text NOT NULL CHECK (status IN ('running','success','failed')),
  started_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz,
  rows_processed  integer,
  rows_written    integer,
  weeks_covered   text,                          -- '2026-04-20 .. 2026-04-26' для UpdateBar
  error_message   text,
  triggered_by    text                            -- 'cron' | 'manual:user_id'
);

CREATE INDEX idx_sync_log_job_finished ON marketing.sync_log(job_name, finished_at DESC);
ALTER TABLE marketing.sync_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY sl_read ON marketing.sync_log FOR SELECT TO authenticated USING (true);
CREATE POLICY sl_write ON marketing.sync_log FOR ALL TO service_role USING (true);
GRANT SELECT ON marketing.sync_log TO authenticated;
```

- [ ] **Step 2: Подключить существующий ETL**

В `services/sheets_sync/sync/sync_promocodes.py` и `scripts/search_queries_sync.py` добавить INSERT в `marketing.sync_log` в начале и UPDATE в конце. Это отдельная мини-задача, можно сделать через Edit tool. Проверить что текущий cron (Mon 10:00 + Mon 12:00) пишет туда.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(marketing): sync_log table + ETL hooks"
```

---

### Task 3.2: API + UpdateBar wiring

**Files:**
- Create: `wookiee-hub/src/api/marketing/sync-log.ts`
- Modify: `wookiee-hub/src/components/marketing/UpdateBar.tsx`

- [ ] **Step 1: Fetch последнего лога**

```ts
export async function fetchLastSync(jobName: string): Promise<SyncLogEntry | null> {
  const { data } = await supabase.schema('marketing').from('sync_log')
    .select('*').eq('job_name', jobName).eq('status', 'success')
    .order('finished_at', { ascending: false }).limit(1).maybeSingle()
  return data
}
```

- [ ] **Step 2: UpdateBar реальные данные**

```tsx
const { data: last } = useQuery({ queryKey: ['sync-log', jobName], queryFn: () => fetchLastSync(jobName), refetchInterval: 60_000 })
return (
  <div>
    <span>{last ? formatDateTime(last.finished_at) : '—'}</span>
    <span>{last?.weeks_covered ?? 'данных нет'}</span>
    <button onClick={onSync}>Обновить</button>
  </div>
)
```

- [ ] **Step 3: Manual sync trigger**

Вариант (Phase 3.5, отдельной задачей если нужно): Edge Function `marketing-sync-trigger` которая запускает `services/sheets_sync/sync/sync_promocodes.py` через docker-команду. На MVP — кнопка показывает «Запросите ручной запуск у админа» / отправляет TG-уведомление в `@wookiee_alerts_bot`.

Решение: на Phase 3 кнопка-заглушка, реальный manual trigger — backlog.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(marketing): wire UpdateBar to real marketing.sync_log"
```

---

### Task 3.3: Phase 3 verification + Phase 3 tag

- [ ] **Step 1: Запустить ETL вручную, проверить UpdateBar**

```bash
docker exec wookiee_cron python services/sheets_sync/sync/sync_promocodes.py --mode rolling
# Через 30 секунд — UpdateBar в /marketing/promo-codes должен показать новый timestamp.
```

- [ ] **Step 2: Tag**

```bash
git tag marketing-phase-3-complete
```

---

## Phase 4 — QA pass (обязательная сессия)

### Task 4.1: Comprehensive QA — browser walkthrough

**Files:** none (только тестирование)

**Why:** Пользователь явно потребовал «обязательной QA-сешеной перепроверкой полностью результата». Эту фазу выполняет ОТДЕЛЬНЫЙ subagent (не тот же который реализовывал) с инструкцией пройти каждый сценарий и зафиксировать findings.

- [ ] **Step 1: Создать `docs/superpowers/plans/2026-05-08-marketing-hub-impl-qa.md` с матрицей проверок**

Матрица (минимум 30 пунктов):

**Промокоды:**
1. Открыть страницу — KPI заполнены (Активных, Продажи шт/₽, Ср. чек)
2. Таблица 6 строк, отсортирована по продажам ₽ desc
3. UpdateBar показывает реальный timestamp последнего sync_log
4. Search input — фильтрует по коду и каналу
5. DateRange — на Phase 1/2 чисто визуальный (доб. фильтрацию stats — backlog)
6. Sticky tfoot корректные суммы
7. Клик по строке → панель справа открывается, URL содержит `?open=N`
8. Refresh с `?open=N` → панель остаётся открытой
9. Detail panel: header + read-only форма + KPI + товарная разбивка (Empty) + weekly stats
10. Закрытие крестиком убирает `?open` из URL
11. «+ Добавить» открывает AddPromoPanel
12. Создание нового промокода работает, инвалидирует кэш, новая строка появляется
13. Все статусы badge отображаются: Активен (green), Не идентиф. (amber), Нет данных (gray)

**Поисковые запросы:**
14. 87 строк в 3 секциях (brand=0)
15. Pills «Модель» — фильтрация работает, totals пересчитываются
16. Pills «Канал» — отображает counter рядом с названием
17. Search input — ищет по query, art, nm, ww, campaign, model
18. DateRange — числа в таблице меняются при сужении периода
19. Collapsible section headers — chevron корректно меняется
20. Sorting внутри секции по Заказам desc
21. CR проценты вычисляются на лету (не из БД)
22. Sticky totals по filtered records
23. Клик по строке (substitute_article) → панель с воронкой
24. Detail panel: query header + StatusEditor (рабочий!) + воронка с CR между шагами
25. Toggle «На период / Все недели» в panel
26. StatusEditor — изменение статуса персистится в БД
27. «+ Добавить WW-код» → каскад модель/цвет/размер → SKU привязка
28. Создание WW-кода → новая строка в правильной секции

**Регрессии:**
29. Все остальные разделы Hub работают (catalog, operations, community, influence, analytics)
30. `npm run build` — green
31. `npm test` — green
32. Тёмная тема — все экраны выглядят корректно (semantic tokens)
33. Светлая тема — все экраны выглядят корректно

- [ ] **Step 2: Subagent выполняет каждый пункт, скрин на каждый экран**

Использовать `mcp__plugin_playwright_playwright__*` для автоматизации, плюс ручной осмотр.

- [ ] **Step 3: Все findings → issues в плане**

Если что-то не работает — описать в `2026-05-08-marketing-hub-impl-qa-findings.md`, исправить (отдельный mini-task), повторить QA.

- [ ] **Step 4: Финальный commit + tag**

```bash
git tag marketing-phase-4-complete
git push --tags
```

---

## File Structure Reference

```
database/marketing/
├── views/
│   └── 2026-05-08-search-queries-unified.sql
├── rpcs/
│   └── 2026-05-08-search-query-stats-aggregated.sql
├── tables/
│   ├── 2026-05-08-channels.sql
│   ├── 2026-05-08-promo-product-breakdown.sql
│   └── 2026-05-08-sync-log.sql
└── migrations/
    └── 2026-05-08-add-creator-ref.sql

wookiee-hub/src/
├── api/marketing/
│   ├── search-queries.ts
│   ├── promo-codes.ts
│   ├── channels.ts
│   └── sync-log.ts
├── hooks/marketing/
│   ├── use-search-queries.ts
│   ├── use-promo-codes.ts
│   ├── use-channels.ts
│   └── use-sync-log.ts
├── components/marketing/
│   ├── Badge.tsx
│   ├── KPI.tsx
│   ├── Empty.tsx
│   ├── SectionHeader.tsx
│   ├── SelectMenu.tsx
│   ├── StatusEditor.tsx
│   ├── DateRange.tsx
│   ├── UpdateBar.tsx
│   └── __tests__/
├── pages/marketing/
│   ├── promo-codes.tsx
│   ├── search-queries.tsx
│   ├── promo-codes/
│   │   ├── PromoCodesTable.tsx
│   │   ├── PromoDetailPanel.tsx
│   │   └── AddPromoPanel.tsx
│   └── search-queries/
│       ├── SearchQueriesTable.tsx
│       ├── SearchQueryDetailPanel.tsx
│       └── AddWWPanel.tsx
└── types/
    └── marketing.ts
```

---

## Self-Review Checklist (выполнено перед сохранением)

**Spec coverage:**
- [x] Брендированные / артикулы / WW-коды — все 3 типа покрыты Task 1.1 (VIEW) + 1.9 (UI секции)
- [x] cr_general / cr_personal — Task 1.1 (CASE WHEN в VIEW) + 2.2 (creator_ref для personal)
- [x] Каналы как справочник — Task 2.1
- [x] Промокоды CRUD — Task 1.7-1.8 (read) + 2.4 (create)
- [x] WW-коды CRUD — Task 1.9 (read) + 2.5 (create)
- [x] StatusEditor работает — Task 2.6
- [x] UpdateBar реальные данные — Task 3.2
- [x] Воронка с CR — Task 1.9 Step 1
- [x] Sticky totals — Task 1.7, 1.9
- [x] Date range filter — Task 1.7, 1.9
- [x] Pills фильтры — Task 1.9
- [x] SelectMenu с allowAdd — Task 1.4
- [x] Темизация Hub — отмечено в Architecture
- [x] QA фаза — Task 4.1
- [x] **Не покрыто:** товарная разбивка промокодов (Empty заглушка) — backfill data вне scope, плановый backlog

**Placeholder scan:**
- [x] Нет «TBD», «TODO», «implement later» в шагах
- [x] SQL и TypeScript — конкретные, исполняемые
- [x] Команды git/npm/sql — точные

**Type consistency:**
- [x] `unified_id: string` (формат 'B|S' + id) везде
- [x] `SearchQueryGroup` enum совпадает в БД (CASE WHEN) и TS
- [x] `creator_ref` тип `text/string|null` всюду
- [x] Channel slug ('yandex','creators',...) — единый ключ через стек

**Открытые backlog-пункты (НЕ в этом плане):**
- Backfill `marketing.promo_product_breakdown` исторически (требует доступ к WB API заказам)
- Edge Function для manual sync trigger из UI (Phase 3.5)
- `crm.creators` registry (когда нужно — сейчас text-ref достаточно)
- Пагинация при >500 запросов (сейчас 87)
- Server-side фильтрация date range stats (сейчас client-side aggregate)

---

## Execution Handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-05-08-marketing-hub-impl.md`.

**Two execution options:**

**1. Subagent-Driven (рекомендовано пользователем)** — диспатчу свежего subagent на каждую задачу, между задачами spec + code review, после Phase 4 — выделенная QA-сессия.

**2. Inline Execution** — выполнить пакетно с чекпоинтами. Не подходит для этого объёма (21 задача).

**Решение пользователя:** Subagent-Driven Development — начинаем с Pre-flight + Task 1.1.
