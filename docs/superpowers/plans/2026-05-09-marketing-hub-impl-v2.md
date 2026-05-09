# Marketing Hub Implementation Plan v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan task-by-task. After every task: BOTH spec-compliance review AND code-quality review (mandatory). After Phase 4 — full re-verification in browser. After Phase 5 — feature flag flip + 24h monitor before declaring complete.
>
> **Supersedes:** `2026-05-08-marketing-hub-impl.md` (v1). v1 was reviewed by CTO/designer/frontend/backend reviewers; all 4 returned `FIX BEFORE PROCEED`. v2 closes all 11 blockers and 20+ important findings.

**Goal:** Внедрить раздел «Маркетинг» в Wookiee Hub (страницы Промокоды и Поисковые запросы) с просмотром, аналитикой воронки и CRUD, повторяя UX из прототипа `wookiee_marketing_v4.jsx` 1:1 в семантической палитре Hub. Источник истины — `crm.*`, чтение через VIEW `marketing.*`, запись через `crm.*`. Релиз скрыт за feature flag до прохождения QA.

**Architecture:**
- **Read path**: VIEW `marketing.search_queries_unified` (UNION ALL `crm.branded_queries` + `crm.substitute_articles` с вычислением `group_kind`, **возвращает уже `source_table` + `source_id`** — клиент не парсит композитный id) + RPC `search_query_stats_aggregated` (включает branded-ветку с нулями) + физическая `marketing.promo_stats_weekly`.
- **Write path**: прямой Supabase JS client → `crm.branded_queries`, `crm.substitute_articles`, `crm.promo_codes`. `creator_ref` заполняется автоматически BEFORE INSERT/UPDATE триггером (решает drift c sheets-sync ETL без правок Python). Каналы валидируются в API-слое (soft-validation против `marketing.channels.slug`).
- **UI path**: `src/pages/marketing/{promo-codes,search-queries}.tsx` (lazy-loaded), reuse `@/components/crm/ui/{Drawer,Badge,EmptyState,Button,QueryStatusBoundary}` + `PageHeader`. Filter state в URL (`useSearchParams`). Только 2 новых примитива: `SelectMenu` (cmdk-popover с allowAdd) и `SectionHeader` (table-row group header).
- **Темизация**: палитра JSX `stone-*` маппится на семантические токены Hub по **явной таблице ниже**. Структура/spacing/типографика — 1:1.
- **Feature flag**: `VITE_FEATURE_MARKETING` env-флаг — роуты `/marketing/*` рендерятся как `<Navigate to="/" />` если флаг false. Навигационная группа фильтруется по флагу. Прод-флаг на main = false до Phase 5.

**Tech Stack:** Vite + React 19 + TypeScript strict + Tailwind v4 + shadcn/ui + react-router-dom v7 + TanStack Query v5 + Supabase JS v2 + Vitest.

**Источники истины:**
- Дизайн-эталон: `wookiee_marketing_v4.jsx` (приложен пользователем; pre-flight копирует в `docs/superpowers/specs/`)
- Data model: `BRIEF_marketing.md` (приложен; pre-flight копирует)
- Исходный контекст: `docs/superpowers/specs/2026-05-06-marketing-hub-mockup-context.md`

---

## Decisions Made (orchestrator, per user delegation)

| # | Вопрос | Решение | Обоснование |
|---|--------|---------|-------------|
| 1 | Деплой | env-flag `VITE_FEATURE_MARKETING` гейтит роуты + навигацию. Включается ручкой в `.env.production` после Phase 4 QA. | Autopull деплоит main каждые 5 мин — без флага сырой UI попадёт на prod после первого же merge |
| 2 | FK channels.slug → substitute_articles.purpose | **Soft-validation в API-слое**, без жёсткого FK | Жёсткий FK потребует миграцию исторических значений + ломает sheets-sync ETL который пишет text. Soft = `createSubstituteArticle()` отвергает unknown slug, ETL не трогаем |
| 3 | Brand seed | `AddBrandQueryPanel` форма (Phase 2 Task 2.5) — заполняет команда вручную | Пользователь подтвердил «заполняем мы, поле ввода» |
| 4 | promo_product_breakdown backfill | Таблица в Phase 2 (Empty в UI), backfill — отдельный backlog (требует доступ к WB API historical orders) | Декомпозиция по SKU не выводится из текущего ETL; backfill = новый ETL компонент, вне scope этого плана |
| 5 | Drawer | Reuse `@/components/crm/ui/Drawer` (паттерн `BloggerEditDrawer`, `IntegrationEditDrawer`) | Не плодить параллельную design-систему; focus management уже реализован |

---

## Pre-flight (выполняется субагентом перед Task 1.1)

- [ ] **PF1: Создать ветку `feature/marketing-hub` от main**

```bash
git checkout main && git pull
git checkout -b feature/marketing-hub
```

- [ ] **PF2: Сохранить дизайн-артефакты в репо**

Скопировать в `docs/superpowers/specs/`:
- `wookiee_marketing_v4.jsx` (~700 строк, React-прототип)
- `2026-05-08-marketing-hub-brief.md` (BRIEF из приложения пользователя)

- [ ] **PF3: Baseline build green**

```bash
cd wookiee-hub && npm install && npm run build && npm test
# Ожидаем: 0 errors, all tests pass.
```

- [ ] **PF4: Установить shadcn `command` примитив**

```bash
cd wookiee-hub && npx shadcn@latest add command
# Создаёт src/components/ui/command.tsx — нужен для SelectMenu (Task 1.4)
git add wookiee-hub/src/components/ui/command.tsx wookiee-hub/package.json wookiee-hub/components.json
git commit -m "chore(hub): install shadcn command primitive (cmdk wrapper)"
```

- [ ] **PF5: Подтвердить точное имя SKU-таблицы для cascade lookup**

```bash
# Через mcp__plugin_supabase_supabase__list_tables schemas=["catalog"] verbose=false:
# Найти таблицу со списком SKU (model + color + size + nm). Кандидаты: catalog.skus, catalog.tovary, catalog.artikuly
# Зафиксировать имя в комментарии в верху Task 2.6 перед стартом Phase 2.
```

- [ ] **PF6: Smoke-проверить что существующие CRM primitives есть на ожидаемых путях**

```bash
# Должны существовать:
ls wookiee-hub/src/components/crm/ui/Button.tsx
ls wookiee-hub/src/components/crm/ui/Badge.tsx
ls wookiee-hub/src/components/crm/ui/Drawer.tsx
ls wookiee-hub/src/components/crm/ui/QueryStatusBoundary.tsx
ls wookiee-hub/src/components/crm/ui/EmptyState.tsx
ls wookiee-hub/src/components/crm/layout/PageHeader.tsx
# Если какой-то отсутствует — STOP, зафиксировать в плане альтернативу (использовать shadcn Button и т.д.)
```

- [ ] **PF7: Добавить env-флаг в pipeline**

```bash
# wookiee-hub/.env.example — добавить:
echo 'VITE_FEATURE_MARKETING=false' >> wookiee-hub/.env.example
# wookiee-hub/.env.local (локально) — добавить true для разработки:
echo 'VITE_FEATURE_MARKETING=true' >> wookiee-hub/.env.local

git add wookiee-hub/.env.example
git commit -m "chore(hub): add VITE_FEATURE_MARKETING env flag (off by default)"
```

---

## stone-* → Semantic Token Mapping Table (canonical reference)

Это единственная таблица истины для портирования палитры из JSX-прототипа. Любое отклонение в Phase 1 — ошибка реализации.

| JSX класс | Hub-токен | Контекст |
|-----------|-----------|----------|
| `bg-stone-50` | `bg-muted` | приглушённый фон секций, hover row |
| `bg-stone-50/40` (or 80, 60) | `bg-muted/50` | полупрозрачные оверлеи |
| `bg-stone-100` | `bg-muted` | hover, badge bg |
| `bg-stone-100/95` | `bg-muted/95 backdrop-blur-sm` | sticky tfoot фон |
| `bg-white` | `bg-card` | карточка KPI, drawer body, table cell |
| `bg-stone-900` | `bg-primary` | primary button, active icon |
| `text-stone-300` | `text-muted-foreground/50` | очень приглушённый (icon Empty) |
| `text-stone-400` | `text-muted-foreground` | label uppercase, placeholder, secondary |
| `text-stone-500` | `text-muted-foreground` | regular muted text |
| `text-stone-600` | `text-foreground/80` | строка таблицы regular |
| `text-stone-700` | `text-foreground` | заголовок секции, sticky tfoot |
| `text-stone-900` | `text-foreground` | основной текст, h1, value |
| `text-white` | `text-primary-foreground` | текст на primary button |
| `border-stone-100` | `border-border/50` | подделители строк таблицы |
| `border-stone-200` | `border-border` | основные бордеры карточек, inputs |
| `border-stone-300` | `border-border` | hover bordered button |
| `ring-stone-500/20` | `ring-border` | inset ring на badge |
| `ring-stone-900` | `ring-ring` | focus ring |
| `bg-emerald-50 text-emerald-700 ring-emerald-600/20` | использовать существующий CRM `<Badge tone="success">` (НЕ создавать дубль) | success |
| `bg-blue-50 text-blue-700 ring-blue-600/20` | `<Badge tone="info">` | info |
| `bg-amber-50 text-amber-700 ring-amber-600/20` | `<Badge tone="warning">` | warning |
| `text-emerald-500` / `text-emerald-600` | `text-[color:var(--wk-green)]` | spinner ok, check icon |
| `text-amber-700` | `text-[color:var(--wk-yellow)]` | unidentified status |
| `text-stone-900` для primary action | `text-foreground` | |

**Шрифты:**
- DM Sans → default body (`font-sans` через Tailwind)
- Instrument Serif italic → page titles. Применять explicit override: `style={{fontFamily:"'Instrument Serif', serif", fontStyle:'italic'}}` на `<h1>` в `PageHeader` или специальной обёртке `<MarketingTitle>`.

**Числа:** `tabular-nums` всегда. **Коды/артикулы:** `font-mono text-xs`.

---

## Phase 1 — Foundation + Read-only UI (12 задач)

### Task 1.0: Feature flag scaffolding

**Files:**
- Create: `wookiee-hub/src/lib/feature-flags.ts`
- Modify: `wookiee-hub/src/router.tsx`
- Modify: `wookiee-hub/src/config/navigation.ts`

**Why:** Без флага первый же commit на main выкатит сырой UI на prod через autopull (5 мин cron). Флаг = безопасный rollout.

- [ ] **Step 1: Утилита**

```ts
// wookiee-hub/src/lib/feature-flags.ts
export const featureFlags = {
  marketing: import.meta.env.VITE_FEATURE_MARKETING === 'true',
} as const

export type FeatureFlag = keyof typeof featureFlags
export const isEnabled = (flag: FeatureFlag) => featureFlags[flag]
```

- [ ] **Step 2: Гейт в router.tsx**

(Реализовано полностью в Task 1.2 — здесь только подготавливаем утилиту. Test: `import { featureFlags } from '@/lib/feature-flags'` компилируется.)

- [ ] **Step 3: Тест утилиты**

```ts
// wookiee-hub/src/lib/__tests__/feature-flags.test.ts
import { isEnabled } from '../feature-flags'

it('returns false when env not set', () => {
  expect(typeof isEnabled('marketing')).toBe('boolean')
})
```

```bash
cd wookiee-hub && npm test -- feature-flags
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/lib/feature-flags.ts wookiee-hub/src/lib/__tests__/feature-flags.test.ts
git commit -m "feat(hub): feature flag utility for gated rollouts"
```

---

### Task 1.1: VIEW + RPC миграции (фиксы блокеров #1, #2, #11)

**Files:**
- Create: `database/marketing/views/2026-05-09-search-queries-unified.sql`
- Create: `database/marketing/rpcs/2026-05-09-search-query-stats-aggregated.sql`
- Apply через MCP `apply_migration`

**Why:** Замена v1 Task 1.1 с фиксами:
- **Блокер #1 (search_path)**: `SET search_path = pg_catalog, crm` (не public; CVE-2018-1058)
- **Блокер #2 (UNION inconsistency)**: RPC возвращает рядки и для `branded_queries` (с нулями) — клиент-side join по unified_id не теряет данные при заполнении brand
- **Блокер #11 (case-sensitivity)**: regex `~* '^креатор[_ ]'`
- **Frontend Important #3 (parsing fragility)**: VIEW отдаёт `source_table` + `source_id` напрямую (не парсим композитный id)
- **Backend Minor (concurrent index)**: индексы на views не создаём (нерелевантно)

- [ ] **Step 1: VIEW**

```sql
-- database/marketing/views/2026-05-09-search-queries-unified.sql
CREATE OR REPLACE VIEW marketing.search_queries_unified
WITH (security_invoker = true)
AS
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
  NULL::text                           AS creator_ref,
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
    WHEN sa.purpose = 'creators' AND sa.campaign_name ~* '^креатор[_ ]'   THEN 'cr_personal'
    WHEN sa.purpose = 'creators'                                          THEN 'cr_general'
    ELSE                                                                       'external'
  END                                  AS group_kind,
  sa.code                              AS query_text,
  sa.artikul_id                        AS artikul_id,
  sa.nomenklatura_wb                   AS nomenklatura_wb,
  CASE WHEN sa.code LIKE 'WW%' THEN sa.code ELSE NULL END AS ww_code,
  sa.campaign_name                     AS campaign_name,
  sa.purpose                           AS purpose,
  NULL::text                           AS model_hint,
  sa.creator_ref                       AS creator_ref,           -- колонка появится в Task 2.2; до этого NULL не сломает (alter добавит nullable)
  sa.status                            AS status,
  sa.created_at                        AS created_at,
  sa.updated_at                        AS updated_at
FROM crm.substitute_articles sa;

GRANT SELECT ON marketing.search_queries_unified TO authenticated, service_role;

COMMENT ON VIEW marketing.search_queries_unified IS
  'Unified read-layer for marketing search queries. UNION of brand_queries + substitute_articles. group_kind computed: brand|cr_personal|cr_general|external. Returns source_table + source_id directly (no client-side parse).';
```

**Важно:** `creator_ref` упомянут в SELECT для substitute_articles ветки. Это поле будет добавлено в Task 2.2. Чтобы Phase 1 не падала, в Task 2.2 нужно сначала ALTER TABLE, потом CREATE OR REPLACE VIEW. Альтернатива — на Phase 1 не включать `creator_ref` в SELECT, а в Task 2.2 пересоздавать VIEW. **Выбираем альтернативу**: Phase 1 SELECT возвращает `NULL::text AS creator_ref`, Task 2.2 CREATE OR REPLACE VIEW заменяет на `sa.creator_ref`.

Финальная версия Phase 1 SELECT для `crm.substitute_articles` ветки — `NULL::text AS creator_ref`. (Заменим в Task 2.2.)

- [ ] **Step 2: RPC (с branded-веткой)**

```sql
-- database/marketing/rpcs/2026-05-09-search-query-stats-aggregated.sql
CREATE OR REPLACE FUNCTION marketing.search_query_stats_aggregated(
  p_from date,
  p_to   date
) RETURNS TABLE (
  unified_id  text,
  frequency   bigint,
  transitions bigint,
  cart_adds   bigint,
  orders      bigint
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, crm
AS $$
  -- substitute_articles aggregations
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
  GROUP BY sa.id

  UNION ALL

  -- branded_queries — нет stats, заполняем нулями для consistent join
  SELECT
    ('B' || bq.id::text) AS unified_id,
    0::bigint AS frequency,
    0::bigint AS transitions,
    0::bigint AS cart_adds,
    0::bigint AS orders
  FROM crm.branded_queries bq;
$$;

GRANT EXECUTE ON FUNCTION marketing.search_query_stats_aggregated(date, date) TO authenticated, service_role;

COMMENT ON FUNCTION marketing.search_query_stats_aggregated IS
  'Aggregated weekly stats per unified search query for [p_from, p_to]. Branded queries return zero rows (no stats source). SECURITY INVOKER — relies on caller RLS on crm.* tables.';
```

- [ ] **Step 3: Применить миграции через MCP**

Использовать `mcp__plugin_supabase_supabase__apply_migration`:

```
name: "marketing_search_queries_unified_view_v2"
query: <содержимое Step 1>
```

```
name: "marketing_search_query_stats_aggregated_rpc_v2"
query: <содержимое Step 2>
```

- [ ] **Step 4: Smoke verification**

```sql
-- Проверка VIEW
SELECT group_kind, COUNT(*) FROM marketing.search_queries_unified GROUP BY group_kind ORDER BY 1;
-- Ожидаем: brand=0, cr_general=N, cr_personal=M, external=K. N+M+K=87.

SELECT source_table, COUNT(*) FROM marketing.search_queries_unified GROUP BY source_table;
-- Ожидаем: branded_queries=0, substitute_articles=87

SELECT unified_id, source_table, source_id, group_kind FROM marketing.search_queries_unified ORDER BY group_kind, query_text LIMIT 10;
-- Spot-check: для каждой строки source_id числовой, source_table совпадает с префиксом unified_id

-- Проверка RPC
SELECT * FROM marketing.search_query_stats_aggregated('2026-03-30', '2026-04-27') ORDER BY orders DESC LIMIT 5;
-- Ожидаем: 87 строк всего (substitute_articles), топ-5 с orders > 0
SELECT COUNT(*) FROM marketing.search_query_stats_aggregated('2026-03-30', '2026-04-27');
-- Ожидаем: 87 (87 substitute + 0 branded = 87 пока branded пуст)
```

- [ ] **Step 5: Rollback SQL (на случай отката)**

```sql
-- database/marketing/views/2026-05-09-search-queries-unified.DOWN.sql
DROP FUNCTION IF EXISTS marketing.search_query_stats_aggregated(date, date);
DROP VIEW IF EXISTS marketing.search_queries_unified;
```

- [ ] **Step 6: Commit**

```bash
git add database/marketing/
git commit -m "feat(marketing): unified search_queries VIEW + stats RPC (v2: fix search_path, include branded zeros)"
```

---

### Task 1.2: Routing + navigation (lazy + feature-flag gated)

**Files:**
- Modify: `wookiee-hub/src/router.tsx`
- Modify: `wookiee-hub/src/config/navigation.ts`
- Create: `wookiee-hub/src/pages/marketing/promo-codes.tsx` (skeleton)
- Create: `wookiee-hub/src/pages/marketing/search-queries.tsx` (skeleton)

**Why:** Lazy-load (как catalog) — Frontend Important #5. Feature flag — CTO Important #7.

- [ ] **Step 1: Skeleton pages**

```tsx
// wookiee-hub/src/pages/marketing/promo-codes.tsx
export function PromoCodesPage() {
  return <div className="p-6 text-sm text-muted-foreground">Промокоды — скоро</div>
}
```

```tsx
// wookiee-hub/src/pages/marketing/search-queries.tsx
export function SearchQueriesPage() {
  return <div className="p-6 text-sm text-muted-foreground">Поисковые запросы — скоро</div>
}
```

- [ ] **Step 2: Lazy + flag gating в router.tsx**

В блоке lazy-imports (после `RnpPage` или рядом с lazy-блоком catalog):

```tsx
const PromoCodesPage = lazy(() =>
  import("@/pages/marketing/promo-codes").then((m) => ({ default: m.PromoCodesPage })),
)
const SearchQueriesPage = lazy(() =>
  import("@/pages/marketing/search-queries").then((m) => ({ default: m.SearchQueriesPage })),
)
```

В роутах (после analytics):

```tsx
import { featureFlags } from "@/lib/feature-flags"
// ...
...(featureFlags.marketing
  ? [
      { path: "/marketing",                element: <Navigate to="/marketing/promo-codes" replace /> },
      { path: "/marketing/promo-codes",    element: withFallback(<PromoCodesPage />) },
      { path: "/marketing/search-queries", element: withFallback(<SearchQueriesPage />) },
    ]
  : []),
```

- [ ] **Step 3: Navigation gating**

```ts
// wookiee-hub/src/config/navigation.ts
import { Megaphone, Percent, Hash } from "lucide-react"
import { featureFlags } from "@/lib/feature-flags"

const marketingGroup: NavGroup = {
  id: "marketing",
  icon: Megaphone,
  label: "Маркетинг",
  items: [
    { id: "promo-codes",    label: "Промокоды",         icon: Percent, path: "/marketing/promo-codes"    },
    { id: "search-queries", label: "Поисковые запросы", icon: Hash,    path: "/marketing/search-queries" },
  ],
}

export const navigationGroups: NavGroup[] = [
  // ... existing groups in order: catalog, operations, community, influence, analytics
  ...(featureFlags.marketing ? [marketingGroup] : []),
]
```

- [ ] **Step 4: Smoke с локальным флагом**

```bash
# .env.local: VITE_FEATURE_MARKETING=true
cd wookiee-hub && npm run dev
# Открыть localhost:5173 → вижу иконку Megaphone в icon-bar.
# Кликнуть → sub-sidebar с двумя пунктами. Skeleton-страницы рендерятся.
# Suspense fallback виден (на slow 3G в DevTools).

# Тогл флага:
# .env.local: VITE_FEATURE_MARKETING=false → перезапустить dev → иконки/роутов нет.
```

- [ ] **Step 5: Build с флагом ВЫКЛ — проверить что нет регрессии**

```bash
unset VITE_FEATURE_MARKETING && npm run build
# Ожидаем: green. Bundle не содержит marketing chunks (lazy + flag — tree-shake?).
# На самом деле lazy-чанки попадут в build, но не загрузятся без route hit. Это OK.
```

- [ ] **Step 6: Commit**

```bash
git add wookiee-hub/src/{router.tsx,config/navigation.ts,pages/marketing/}
git commit -m "feat(marketing): scaffold routes + navigation (lazy-loaded, feature-flag gated)"
```

---

### Task 1.3: Reuse audit + 2 новых примитива

**Files:**
- Read-only audit: подтвердить наличие `@/components/crm/ui/{Badge,Drawer,EmptyState,Button,QueryStatusBoundary}`
- Create: `wookiee-hub/src/components/marketing/SectionHeader.tsx`
- Create: `wookiee-hub/src/components/marketing/__tests__/SectionHeader.test.tsx`

**Why:** Designer Important #6 + Frontend findings: НЕ плодить параллельную design-систему. Только 2 новых компонента не имеют CRM-аналога: `SelectMenu` (Task 1.4) и `SectionHeader` (этот таск, table-row group header).

`Badge`, `Empty`, `KPI` маппятся:
- `Badge` (JSX) → `@/components/crm/ui/Badge` с `tone` API
- `Empty` (JSX) → `@/components/crm/ui/EmptyState` (если API совпадает) или inline `<div>...</div>` с `lucide-react Clock` если EmptyState слишком тяжёлый
- `KPI` (JSX) → проверить `@/components/crm/ui/`. Если нет — создать `KpiCard.tsx` в `marketing/` (легковесный, 12 строк).

- [ ] **Step 1: Audit existing primitives, документировать в комментарии плана**

```bash
# Читаем заголовки/props каждого:
head -50 wookiee-hub/src/components/crm/ui/Badge.tsx
head -50 wookiee-hub/src/components/crm/ui/EmptyState.tsx
head -50 wookiee-hub/src/components/crm/ui/QueryStatusBoundary.tsx
head -50 wookiee-hub/src/components/crm/ui/Drawer.tsx
head -50 wookiee-hub/src/components/crm/ui/Button.tsx

# Зафиксировать в файле audit (для последующих задач):
# - Badge tone values: 'success' | 'warning' | 'info' | 'secondary' | ?
# - EmptyState props: title, description, icon?
# - Drawer props: open, onOpenChange, side, title?
# - Button variants: 'primary' | 'secondary' | 'ghost' | ?
# - QueryStatusBoundary children API
```

Создать `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-audit.md` с этими data points для всех последующих задач.

- [ ] **Step 2: SectionHeader (новый)**

```tsx
// wookiee-hub/src/components/marketing/SectionHeader.tsx
import { ChevronDown, ChevronRight } from "lucide-react"

export interface SectionHeaderProps {
  icon: string                  // emoji like '🎯', '📦', '🎥', '👤'
  label: string
  count: number
  collapsed: boolean
  onToggle: () => void
  colSpan?: number               // default 12
}

export function SectionHeader({ icon, label, count, collapsed, onToggle, colSpan = 12 }: SectionHeaderProps) {
  return (
    <tr
      className="bg-muted/50 border-y border-border cursor-pointer select-none hover:bg-muted/80 transition-colors"
      onClick={onToggle}
    >
      <td colSpan={colSpan} className="px-3 py-2">
        <div className="flex items-center gap-2">
          {collapsed
            ? <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" aria-hidden />
            : <ChevronDown  className="w-3.5 h-3.5 text-muted-foreground" aria-hidden />}
          <span className="text-[12px] font-medium text-foreground">{icon} {label}</span>
          <span className="text-[11px] tabular-nums text-muted-foreground">{count}</span>
        </div>
      </td>
    </tr>
  )
}
```

- [ ] **Step 3: Test**

```tsx
// __tests__/SectionHeader.test.tsx
import { render, fireEvent, screen } from '@testing-library/react'
import { SectionHeader } from '../SectionHeader'

it('renders label, icon, count', () => {
  render(<table><tbody><SectionHeader icon="📦" label="Артикулы" count={42} collapsed={false} onToggle={() => {}} /></tbody></table>)
  expect(screen.getByText(/Артикулы/)).toBeInTheDocument()
  expect(screen.getByText('42')).toBeInTheDocument()
})

it('calls onToggle on click', () => {
  const handle = vi.fn()
  render(<table><tbody><SectionHeader icon="📦" label="X" count={1} collapsed={true} onToggle={handle} /></tbody></table>)
  fireEvent.click(screen.getByRole('row'))
  expect(handle).toHaveBeenCalled()
})
```

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/marketing/ docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-audit.md
git commit -m "feat(marketing): SectionHeader primitive + CRM-reuse audit"
```

---

### Task 1.4: SelectMenu (cmdk-popover c allowAdd, accessibility)

**Files:**
- Create: `wookiee-hub/src/components/marketing/SelectMenu.tsx`
- Create: `wookiee-hub/src/components/marketing/__tests__/SelectMenu.test.tsx`

**Why:** Самый сложный новый компонент. Frontend Blocker #1 фиксится в pre-flight (`shadcn add command`). Designer Important #4 — keyboard nav, aria.

- [ ] **Step 1: Реализация (cmdk-base)**

```tsx
// wookiee-hub/src/components/marketing/SelectMenu.tsx
import * as React from "react"
import * as Popover from "@radix-ui/react-popover"
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command"
import { Check, ChevronDown, Plus, X } from "lucide-react"
import { cn } from "@/lib/utils"

type Option = { value: string; label: string } | string

export interface SelectMenuProps {
  label?: string
  value: string
  options: Option[]
  onChange: (v: string) => void
  allowAdd?: boolean
  placeholder?: string
  disabled?: boolean
  emptyHint?: string                          // text shown when filter has 0 matches
  newValueLabel?: string                      // label for «+ Добавить новый»
}

export function SelectMenu({
  label, value, options, onChange,
  allowAdd, placeholder = "Выбрать…", disabled,
  emptyHint = "Ничего не найдено",
  newValueLabel = "Добавить новый",
}: SelectMenuProps) {
  const [open, setOpen] = React.useState(false)
  const [adding, setAdding] = React.useState(false)
  const [newVal, setNewVal] = React.useState("")
  const opts: { value: string; label: string }[] = (typeof options[0] === "string"
    ? (options as string[]).map((o) => ({ value: o, label: o }))
    : (options as { value: string; label: string }[]))
  const current = opts.find((o) => o.value === value)

  const submitNew = () => {
    const v = newVal.trim()
    if (!v) return
    onChange(v)
    setNewVal("")
    setAdding(false)
    setOpen(false)
  }

  return (
    <div>
      {label && (
        <div className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1">{label}</div>
      )}
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button
            type="button"
            disabled={disabled}
            aria-label={label ?? placeholder}
            aria-expanded={open}
            className={cn(
              "w-full flex items-center justify-between rounded-md border px-2.5 py-1.5 text-sm bg-card hover:border-foreground/20 transition-colors",
              "border-border focus:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            <span className={current ? "text-foreground" : "text-muted-foreground"}>
              {current ? current.label : placeholder}
            </span>
            <ChevronDown className={cn("w-3.5 h-3.5 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
          </button>
        </Popover.Trigger>
        <Popover.Content
          className="z-50 bg-popover border border-border rounded-lg shadow-md p-0 w-[var(--radix-popover-trigger-width)]"
          sideOffset={4}
          align="start"
        >
          {!adding ? (
            <Command>
              {opts.length > 5 && <CommandInput placeholder="Поиск…" />}
              <CommandList className="max-h-[240px]">
                <CommandEmpty>{emptyHint}</CommandEmpty>
                <CommandItem value="__empty__" onSelect={() => { onChange(""); setOpen(false) }}>
                  <span className="text-muted-foreground">—</span>
                </CommandItem>
                {opts.map((o) => (
                  <CommandItem key={o.value} value={o.label} onSelect={() => { onChange(o.value); setOpen(false) }}>
                    <span className="flex-1 truncate">{o.label}</span>
                    {o.value === value && <Check className="w-3 h-3 text-[color:var(--wk-green)]" aria-hidden />}
                  </CommandItem>
                ))}
                {allowAdd && (
                  <>
                    <CommandSeparator />
                    <CommandItem value="__add__" onSelect={() => setAdding(true)}>
                      <Plus className="w-3 h-3 mr-1.5" aria-hidden /> {newValueLabel}
                    </CommandItem>
                  </>
                )}
              </CommandList>
            </Command>
          ) : (
            <div className="flex items-center gap-1 p-2 border-t border-border">
              <input
                autoFocus
                value={newVal}
                onChange={(e) => setNewVal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitNew()
                  if (e.key === "Escape") { setAdding(false); setNewVal("") }
                }}
                placeholder="Новое значение…"
                className="flex-1 px-2 py-1 text-xs border border-border rounded bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label="Ввести новое значение"
              />
              <button
                type="button"
                onClick={submitNew}
                disabled={!newVal.trim()}
                aria-label="Подтвердить"
                className="p-1 rounded text-[color:var(--wk-green)] hover:bg-muted disabled:opacity-30"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => { setAdding(false); setNewVal("") }}
                aria-label="Отмена"
                className="p-1 rounded text-muted-foreground hover:bg-muted"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </Popover.Content>
      </Popover.Root>
    </div>
  )
}
```

- [ ] **Step 2: Тесты (a11y + behavior)**

```tsx
// __tests__/SelectMenu.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SelectMenu } from '../SelectMenu'

describe('SelectMenu', () => {
  it('opens, lists options, calls onChange', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A','B','C']} onChange={handle} />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.click(await screen.findByText('B'))
    expect(handle).toHaveBeenCalledWith('B')
  })

  it('keyboard nav: ArrowDown + Enter selects', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A','B','C']} onChange={handle} />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    // cmdk default behavior — first ArrowDown highlights first item
    expect(handle).toHaveBeenCalled()
  })

  it('Esc closes popover', async () => {
    render(<SelectMenu value="" options={['A']} onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button'))
    expect(await screen.findByText('A')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByText('A')).not.toBeInTheDocument())
  })

  it('allowAdd inserts new value via Enter', async () => {
    const handle = vi.fn()
    render(<SelectMenu value="" options={['A']} onChange={handle} allowAdd />)
    await userEvent.click(screen.getByRole('button'))
    await userEvent.click(await screen.findByText(/Добавить новый/))
    const input = await screen.findByPlaceholderText(/Новое значение/)
    await userEvent.type(input, 'Новый канал{Enter}')
    expect(handle).toHaveBeenCalledWith('Новый канал')
  })

  it('aria-expanded toggles', async () => {
    render(<SelectMenu value="" options={['A']} onChange={() => {}} />)
    const trigger = screen.getByRole('button')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })
})
```

```bash
cd wookiee-hub && npm test -- SelectMenu
# Ожидаем: 5 passed
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/components/marketing/SelectMenu.tsx wookiee-hub/src/components/marketing/__tests__/SelectMenu.test.tsx
git commit -m "feat(marketing): SelectMenu (cmdk popover with allowAdd, full a11y)"
```

---

### Task 1.5: DateRange + UpdateBar + StatusEditor (reuse Drawer/Badge)

**Files:**
- Create: `wookiee-hub/src/components/marketing/DateRange.tsx`
- Create: `wookiee-hub/src/components/marketing/UpdateBar.tsx`
- Create: `wookiee-hub/src/components/marketing/StatusEditor.tsx`

**Why:** Designer Minor #12 — DateRange нельзя оставлять «чисто визуальным». Делаем рабочим сразу (client-side weekly-stats фильтр в Phase 1.7-1.10). Designer Important #5 — Drawer reuse в Phase 2 — здесь только готовим прим. компоненты.

- [ ] **Step 1: DateRange (working)**

```tsx
// wookiee-hub/src/components/marketing/DateRange.tsx
import { Calendar } from "lucide-react"

export interface DateRangeProps {
  from: string
  to: string
  onChange: (from: string, to: string) => void
  min?: string
  max?: string
}

export function DateRange({ from, to, onChange, min, max }: DateRangeProps) {
  // Auto-swap if from > to
  const handleFrom = (v: string) => onChange(v, v > to ? v : to)
  const handleTo   = (v: string) => onChange(v < from ? v : from, v)
  const inputCls = "border border-border rounded-md px-2 py-1 text-xs tabular-nums text-foreground/80 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring bg-card w-[120px]"

  return (
    <div className="flex items-center gap-1.5">
      <Calendar className="w-3.5 h-3.5 text-muted-foreground shrink-0" aria-hidden />
      <input
        type="date" value={from} min={min} max={to} onChange={(e) => handleFrom(e.target.value)}
        className={inputCls} aria-label="Дата начала"
      />
      <span className="text-muted-foreground/50 text-xs">→</span>
      <input
        type="date" value={to} min={from} max={max} onChange={(e) => handleTo(e.target.value)}
        className={inputCls} aria-label="Дата окончания"
      />
    </div>
  )
}
```

- [ ] **Step 2: UpdateBar (Phase 1 — заглушка с ручкой `onSync`)**

```tsx
// wookiee-hub/src/components/marketing/UpdateBar.tsx
import { CheckCircle, AlertCircle, RefreshCw } from "lucide-react"

export interface UpdateBarProps {
  lastUpdate?: string                   // formatted: '27 апр 2026, 23:24'
  weeksCovered?: string                  // '20.04–26.04, пропусков нет'
  status?: 'success' | 'failed' | 'unknown'
  onSync?: () => Promise<void> | void
  syncing?: boolean
}

export function UpdateBar({ lastUpdate, weeksCovered, status = 'unknown', onSync, syncing }: UpdateBarProps) {
  const Icon  = status === 'failed' ? AlertCircle : CheckCircle
  const color = status === 'failed' ? 'text-[color:var(--wk-red)]'
              : status === 'success' ? 'text-[color:var(--wk-green)]'
              : 'text-muted-foreground'

  return (
    <div className="flex items-center gap-3 px-6 py-1.5 bg-muted/30 border-b border-border text-[11px]">
      <Icon className={`w-3 h-3 ${color}`} aria-hidden />
      <span className="tabular-nums text-muted-foreground">{lastUpdate ?? '—'}</span>
      {weeksCovered && (
        <>
          <span className="text-muted-foreground/50">·</span>
          <span className={status === 'failed' ? 'text-[color:var(--wk-red)]' : 'text-[color:var(--wk-green)]'}>
            {weeksCovered}
          </span>
        </>
      )}
      {onSync && (
        <button
          type="button" onClick={() => onSync()} disabled={syncing}
          className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium transition-colors border-border text-muted-foreground hover:bg-muted hover:border-foreground/30 disabled:opacity-50"
          aria-label="Обновить данные"
        >
          <RefreshCw className={`w-3 h-3 ${syncing ? 'animate-spin' : ''}`} aria-hidden />
          {syncing ? 'Обновляю…' : 'Обновить'}
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 3: StatusEditor (использует существующий CRM Badge + DropdownMenu)**

```tsx
// wookiee-hub/src/components/marketing/StatusEditor.tsx
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { Check, ChevronDown } from "lucide-react"
import { Badge } from "@/components/crm/ui/Badge"

const STATUSES = {
  active:  { label: 'Используется', tone: 'success' as const },
  free:    { label: 'Свободен',     tone: 'info'    as const },
  archive: { label: 'Архив',        tone: 'secondary' as const },
}
type Status = keyof typeof STATUSES

export function StatusEditor({ status, onChange, disabled }: { status: Status; onChange: (s: Status) => void; disabled?: boolean }) {
  const cur = STATUSES[status]
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild disabled={disabled}>
        <button
          type="button"
          aria-label={`Текущий статус: ${cur.label}. Нажмите чтобы изменить.`}
          className="group flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent hover:border-border transition-colors disabled:opacity-50"
        >
          <Badge tone={cur.tone}>{cur.label}</Badge>
          <ChevronDown className="w-3 h-3 text-muted-foreground/50 group-hover:text-muted-foreground" aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content className="z-50 bg-popover border border-border rounded-lg shadow-md py-1 min-w-[150px]">
        {(Object.keys(STATUSES) as Status[]).map((k) => {
          const s = STATUSES[k]
          return (
            <DropdownMenu.Item key={k}
              onSelect={() => onChange(k)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
            >
              <Badge tone={s.tone}>{s.label}</Badge>
              {k === status && <Check className="w-3 h-3 text-[color:var(--wk-green)] ml-auto" aria-hidden />}
            </DropdownMenu.Item>
          )
        })}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  )
}
```

- [ ] **Step 4: Smoke в playground (временный route)**

Добавить временный route `/marketing/__playground` в локальный режим, рендерить все 4 примитива (DateRange + UpdateBar + StatusEditor + SelectMenu + SectionHeader). Проверить визуально в светлой и тёмной теме (toggle `<html class="dark">`).

- [ ] **Step 5: Commit + удалить playground**

```bash
git add wookiee-hub/src/components/marketing/{DateRange,UpdateBar,StatusEditor}.tsx
git commit -m "feat(marketing): DateRange (auto-swap), UpdateBar (status-aware), StatusEditor (reuse CRM Badge)"
```

---

### Task 1.6: Types + API + hooks (creator_ref forward-compat, parseUnifiedId, numeric coercion)

**Files:**
- Create: `wookiee-hub/src/types/marketing.ts`
- Create: `wookiee-hub/src/api/marketing/search-queries.ts`
- Create: `wookiee-hub/src/api/marketing/promo-codes.ts`
- Create: `wookiee-hub/src/api/marketing/channels.ts`
- Create: `wookiee-hub/src/hooks/marketing/use-search-queries.ts`
- Create: `wookiee-hub/src/hooks/marketing/use-promo-codes.ts`
- Create: `wookiee-hub/src/hooks/marketing/use-channels.ts`
- Create: `wookiee-hub/src/lib/marketing-helpers.ts` (parseUnifiedId, numeric coercion)
- Tests: `wookiee-hub/src/lib/__tests__/marketing-helpers.test.ts`

**Why:**
- Frontend Important #3 — `parseUnifiedId` helper, source_table+source_id из VIEW (фикс)
- Frontend Important #4 — `creator_ref` в типе уже в Phase 1
- Backend Important #8 — coerce numeric → number в API-слое

- [ ] **Step 1: Helpers**

```ts
// wookiee-hub/src/lib/marketing-helpers.ts
export type SearchQuerySource = 'branded_queries' | 'substitute_articles'

export function parseUnifiedId(unifiedId: string): { source: SearchQuerySource; id: number } {
  const prefix = unifiedId[0]
  const id = Number(unifiedId.slice(1))
  if (Number.isNaN(id)) throw new Error(`Invalid unified_id: ${unifiedId}`)
  if (prefix === 'B') return { source: 'branded_queries', id }
  if (prefix === 'S') return { source: 'substitute_articles', id }
  throw new Error(`Unknown unified_id prefix: ${prefix}`)
}

/** Supabase JS returns Postgres numeric as string. Coerce safely. */
export const numToNumber = (v: number | string | null | undefined): number => {
  if (v == null) return 0
  if (typeof v === 'number') return v
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}
```

- [ ] **Step 2: Tests for helpers**

```ts
// __tests__/marketing-helpers.test.ts
import { parseUnifiedId, numToNumber } from '../marketing-helpers'

describe('parseUnifiedId', () => {
  it('parses B-prefix', () => expect(parseUnifiedId('B42')).toEqual({ source: 'branded_queries', id: 42 }))
  it('parses S-prefix', () => expect(parseUnifiedId('S100')).toEqual({ source: 'substitute_articles', id: 100 }))
  it('throws on bad prefix', () => expect(() => parseUnifiedId('X1')).toThrow())
  it('throws on non-numeric', () => expect(() => parseUnifiedId('Sabc')).toThrow())
})

describe('numToNumber', () => {
  it('coerces string', () => expect(numToNumber('123.45')).toBe(123.45))
  it('handles null', () => expect(numToNumber(null)).toBe(0))
  it('handles undefined', () => expect(numToNumber(undefined)).toBe(0))
  it('passes number', () => expect(numToNumber(7)).toBe(7))
})
```

- [ ] **Step 3: Types**

```ts
// wookiee-hub/src/types/marketing.ts
export type SearchQueryGroup = 'brand' | 'external' | 'cr_general' | 'cr_personal'
export type SearchQueryStatus = 'active' | 'free' | 'archive'

export interface SearchQueryRow {
  unified_id: string                      // 'B1' | 'S42'
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
  creator_ref: string | null              // Phase 1: всегда null. Phase 2 заполнит.
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
  search_query_id: number
  week_start: string
  frequency: number
  transitions: number
  additions: number
  orders: number
}

export type PromoStatus = 'active' | 'unidentified' | 'archive'

export interface PromoCodeRow {
  id: number
  code: string
  name: string | null
  external_uuid: string | null
  channel: string | null
  discount_pct: number | null
  valid_from: string | null
  valid_until: string | null
  status: PromoStatus
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

export interface MarketingChannel {
  id: number
  slug: string
  label: string
  is_active: boolean
}

export interface SyncLogEntry {
  id: number
  job_name: string
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  rows_processed: number | null
  rows_written: number | null
  weeks_covered: string | null
  error_message: string | null
  triggered_by: string | null
}
```

- [ ] **Step 4: API search-queries**

```ts
// wookiee-hub/src/api/marketing/search-queries.ts
import { supabase } from '@/lib/supabase'
import type { SearchQueryRow, SearchQueryStatsAgg, SearchQueryWeeklyStat, SearchQueryStatus } from '@/types/marketing'
import { parseUnifiedId } from '@/lib/marketing-helpers'

export async function fetchSearchQueries(): Promise<SearchQueryRow[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_queries_unified')
    .select('*')
    .order('updated_at', { ascending: false, nullsFirst: false })
  if (error) throw error
  return (data ?? []) as SearchQueryRow[]
}

export async function fetchSearchQueryStats(from: string, to: string): Promise<SearchQueryStatsAgg[]> {
  const { data, error } = await supabase
    .schema('marketing').rpc('search_query_stats_aggregated', { p_from: from, p_to: to })
  if (error) throw error
  return (data ?? []) as SearchQueryStatsAgg[]
}

export async function fetchSearchQueryWeekly(substituteArticleId: number): Promise<SearchQueryWeeklyStat[]> {
  const { data, error } = await supabase
    .schema('marketing').from('search_query_stats_weekly')
    .select('*').eq('search_query_id', substituteArticleId)
    .order('week_start', { ascending: true })
  if (error) throw error
  return (data ?? []) as SearchQueryWeeklyStat[]
}

export async function updateSearchQueryStatus(unifiedId: string, status: SearchQueryStatus): Promise<void> {
  const { source, id } = parseUnifiedId(unifiedId)
  const { error } = await supabase
    .schema('crm').from(source)
    .update({ status, updated_at: new Date().toISOString() })
    .eq('id', id)
  if (error) throw error
}
```

- [ ] **Step 5: API promo-codes (с numeric coerce)**

```ts
// wookiee-hub/src/api/marketing/promo-codes.ts
import { supabase } from '@/lib/supabase'
import type { PromoCodeRow, PromoStatWeekly } from '@/types/marketing'
import { numToNumber } from '@/lib/marketing-helpers'

export async function fetchPromoCodes(): Promise<PromoCodeRow[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_codes').select('*').order('updated_at', { ascending: false })
  if (error) throw error
  return ((data ?? []) as PromoCodeRow[]).map((p) => ({
    ...p,
    discount_pct: p.discount_pct == null ? null : numToNumber(p.discount_pct),
  }))
}

export async function fetchPromoStatsWeekly(): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_stats_weekly').select('*').order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    promo_code_id: r.promo_code_id as number,
    week_start: r.week_start as string,
    sales_rub: numToNumber(r.sales_rub as never),
    payout_rub: numToNumber(r.payout_rub as never),
    orders_count: numToNumber(r.orders_count as never),
    returns_count: numToNumber(r.returns_count as never),
    avg_discount_pct: numToNumber(r.avg_discount_pct as never),
    avg_check: numToNumber(r.avg_check as never),
  }))
}
```

- [ ] **Step 6: API channels**

```ts
// wookiee-hub/src/api/marketing/channels.ts
import { supabase } from '@/lib/supabase'
import type { MarketingChannel } from '@/types/marketing'

export async function fetchChannels(): Promise<MarketingChannel[]> {
  const { data, error } = await supabase.schema('marketing').from('channels').select('*').eq('is_active', true).order('label')
  if (error) throw error
  return (data ?? []) as MarketingChannel[]
}
```

- [ ] **Step 7: Hooks**

```ts
// wookiee-hub/src/hooks/marketing/use-search-queries.ts
import { useQuery } from '@tanstack/react-query'
import { fetchSearchQueries, fetchSearchQueryStats, fetchSearchQueryWeekly } from '@/api/marketing/search-queries'

export const searchQueriesKeys = {
  all:    ['marketing', 'search-queries'] as const,
  list:   () => [...searchQueriesKeys.all, 'list'] as const,
  stats:  (from: string, to: string) => [...searchQueriesKeys.all, 'stats', from, to] as const,
  weekly: (id: number) => [...searchQueriesKeys.all, 'weekly', id] as const,
}

export function useSearchQueries() {
  return useQuery({ queryKey: searchQueriesKeys.list(), queryFn: fetchSearchQueries, staleTime: 5 * 60_000 })
}
export function useSearchQueryStats(from: string, to: string) {
  return useQuery({
    queryKey: searchQueriesKeys.stats(from, to),
    queryFn: () => fetchSearchQueryStats(from, to),
    staleTime: 60_000,
    enabled: Boolean(from && to),
  })
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
import { useQuery } from '@tanstack/react-query'
import { fetchPromoCodes, fetchPromoStatsWeekly } from '@/api/marketing/promo-codes'

export const promoCodesKeys = {
  all:    ['marketing', 'promo-codes'] as const,
  list:   () => [...promoCodesKeys.all, 'list'] as const,
  stats:  () => [...promoCodesKeys.all, 'stats'] as const,
}

export function usePromoCodes()       { return useQuery({ queryKey: promoCodesKeys.list(),  queryFn: fetchPromoCodes,       staleTime: 5 * 60_000 }) }
export function usePromoStatsWeekly() { return useQuery({ queryKey: promoCodesKeys.stats(), queryFn: fetchPromoStatsWeekly, staleTime: 60_000 }) }
```

```ts
// wookiee-hub/src/hooks/marketing/use-channels.ts
import { useQuery } from '@tanstack/react-query'
import { fetchChannels } from '@/api/marketing/channels'
export function useChannels() {
  return useQuery({ queryKey: ['marketing', 'channels'], queryFn: fetchChannels, staleTime: 10 * 60_000 })
}
```

- [ ] **Step 8: Запустить тесты**

```bash
cd wookiee-hub && npm test -- marketing
# Ожидаем: SelectMenu + SectionHeader + marketing-helpers tests passing
```

- [ ] **Step 9: Commit**

```bash
git add wookiee-hub/src/types/marketing.ts wookiee-hub/src/api/marketing/ wookiee-hub/src/hooks/marketing/ wookiee-hub/src/lib/marketing-helpers.ts wookiee-hub/src/lib/__tests__/marketing-helpers.test.ts
git commit -m "feat(marketing): types + API + TanStack Query hooks (creator_ref forward-compat, parseUnifiedId, numeric coerce)"
```

---

### Task 1.7: Промокоды — table + KPI + URL filter state

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx`
- Create: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`

**Why:** Главный экран. Frontend Important #6 — filter state в URL. Designer Minor #12 — DateRange working с первого дня. Designer Important #3 — QueryStatusBoundary loading states.

- [ ] **Step 1: PromoCodesTable**

```tsx
// wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx
import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { Search } from "lucide-react"
import { usePromoCodes, usePromoStatsWeekly } from "@/hooks/marketing/use-promo-codes"
import { QueryStatusBoundary } from "@/components/crm/ui/QueryStatusBoundary"
import { Badge } from "@/components/crm/ui/Badge"
import { DateRange } from "@/components/marketing/DateRange"
import { UpdateBar } from "@/components/marketing/UpdateBar"
import { numToNumber } from "@/lib/marketing-helpers"

const FIRST = '2025-07-28'
const LAST  = new Date().toISOString().slice(0, 10)

export function PromoCodesTable() {
  const [params, setParams] = useSearchParams()
  const search   = params.get('q') ?? ''
  const dateFrom = params.get('from') ?? '2026-03-30'
  const dateTo   = params.get('to')   ?? LAST

  const { data: promos = [], isLoading: lp, error: ep } = usePromoCodes()
  const { data: weekly = [], isLoading: lw, error: ew } = usePromoStatsWeekly()

  const enriched = useMemo(() => {
    const inRange = weekly.filter((w) => w.week_start >= dateFrom && w.week_start <= dateTo)
    const byId = new Map<number, { qty: number; sales: number }>()
    for (const w of inRange) {
      const cur = byId.get(w.promo_code_id) ?? { qty: 0, sales: 0 }
      cur.qty   += numToNumber(w.orders_count)
      cur.sales += numToNumber(w.sales_rub)
      byId.set(w.promo_code_id, cur)
    }
    return promos.map((p) => ({ ...p, qty: byId.get(p.id)?.qty ?? 0, sales: byId.get(p.id)?.sales ?? 0 }))
  }, [promos, weekly, dateFrom, dateTo])

  const filtered = useMemo(() => {
    let l = enriched
    if (search) {
      const q = search.toLowerCase()
      l = l.filter((p) => p.code.toLowerCase().includes(q) || p.channel?.toLowerCase().includes(q))
    }
    return l.sort((a, b) => b.sales - a.sales)
  }, [enriched, search])

  const totals = useMemo(() => ({
    qty:   filtered.reduce((s, p) => s + p.qty, 0),
    sales: filtered.reduce((s, p) => s + p.sales, 0),
  }), [filtered])

  const setQ = (k: string, v: string | null) => setParams((p) => { v ? p.set(k, v) : p.delete(k); return p })

  return (
    <QueryStatusBoundary isLoading={lp || lw} error={ep ?? ew}>
      <div className="grid grid-cols-4 gap-3 px-6 py-4 border-b border-border">
        <KpiCard label="Активных" value={String(promos.filter((p) => p.status === 'active').length)} sub={`из ${promos.length}`} />
        <KpiCard label="Продажи, шт" value={fmt(totals.qty)} />
        <KpiCard label="Продажи, ₽" value={fmtR(totals.sales)} />
        <KpiCard label="Ср. чек, ₽" value={totals.qty > 0 ? fmtR(Math.round(totals.sales / totals.qty)) : '—'} />
      </div>

      <UpdateBar />

      <div className="px-6 py-2 border-b border-border flex items-center gap-3 bg-card flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" aria-hidden />
          <input
            value={search} onChange={(e) => setQ('q', e.target.value || null)}
            placeholder="Код или канал…"
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-border rounded-md bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            aria-label="Поиск промокода"
          />
        </div>
        <DateRange from={dateFrom} to={dateTo} min={FIRST} max={LAST} onChange={(f, t) => setParams((p) => { p.set('from', f); p.set('to', t); return p })} />
        <span className="text-[10px] text-muted-foreground ml-auto tabular-nums">{filtered.length} кодов</span>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full table-fixed">
          <colgroup>
            <col className="w-[220px]" /><col className="w-[120px]" /><col className="w-[80px]" /><col className="w-[110px]" />
            <col /><col /><col />
          </colgroup>
          <thead className="sticky top-0 bg-muted/95 backdrop-blur-sm border-b border-border z-10">
            <tr>
              {['Код','Канал','Скидка','Статус'].map((h) => <th key={h} className={TH}>{h}</th>)}
              {['Продажи, шт','Продажи, ₽','Ср. чек, ₽'].map((h) => <th key={h} className={THR}>{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {filtered.map((p) => {
              const tone = p.status === 'unidentified' ? 'warning' : p.qty === 0 ? 'secondary' : 'success'
              const lab  = p.status === 'unidentified' ? 'Не идентиф.' : p.qty === 0 ? 'Нет данных' : 'Активен'
              const avg  = p.qty > 0 ? Math.round(p.sales / p.qty) : 0
              return (
                <tr key={p.id} onClick={() => setQ('open', String(p.id))}
                    className="cursor-pointer transition-colors hover:bg-muted/50">
                  <td className="px-2 py-2.5"><span className="font-mono text-xs text-foreground">{p.code.length > 24 ? p.code.slice(0, 24) + '…' : p.code}</span></td>
                  <td className="px-2 py-2.5"><Badge tone="secondary">{p.channel ?? '—'}</Badge></td>
                  <td className="px-2 py-2.5 text-sm tabular-nums text-foreground/80">{p.discount_pct != null ? `${p.discount_pct}%` : '—'}</td>
                  <td className="px-2 py-2.5"><Badge tone={tone}>{lab}</Badge></td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm font-medium text-foreground">{p.qty > 0 ? fmt(p.qty) : <span className="text-muted-foreground/50">—</span>}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm text-foreground/80">{p.sales > 0 ? fmtR(p.sales) : <span className="text-muted-foreground/50">—</span>}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-sm text-muted-foreground">{avg > 0 ? fmtR(avg) : <span className="text-muted-foreground/50">—</span>}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot className="sticky bottom-0 bg-muted/95 backdrop-blur-sm border-t-2 border-border z-10">
            <tr>
              <td className="px-2 py-2 text-xs font-medium text-foreground" colSpan={4}>Итого · {filtered.length} кодов</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmt(totals.qty)}</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-bold text-foreground">{fmtR(totals.sales)}</td>
              <td className="px-2 py-2 text-right tabular-nums text-sm font-medium text-foreground/80">{totals.qty > 0 ? fmtR(Math.round(totals.sales / totals.qty)) : '—'}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </QueryStatusBoundary>
  )
}

const TH  = "px-2 py-2 text-left  text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const THR = "px-2 py-2 text-right text-[10px] uppercase tracking-wider text-muted-foreground font-medium select-none whitespace-nowrap"
const fmt  = (n: number) => n.toLocaleString('ru-RU')
const fmtR = (n: number) => `${n.toLocaleString('ru-RU')} ₽`

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-card rounded-lg border border-border px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</div>
      <div className="text-xl font-medium text-foreground tabular-nums leading-tight mt-0.5">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}
```

- [ ] **Step 2: Page wrapper с Instrument Serif title**

```tsx
// wookiee-hub/src/pages/marketing/promo-codes.tsx
import { PageHeader } from "@/components/crm/layout/PageHeader"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"

export function PromoCodesPage() {
  return (
    <>
      <PageHeader
        title={<span style={{ fontFamily: "'Instrument Serif', serif", fontStyle: 'italic', fontSize: 24 }}>Промокоды</span>}
        sub="Статистика по кодам скидок"
        actions={null /* «+ Добавить» в Phase 2 */}
      />
      <PromoCodesTable />
    </>
  )
}
```

- [ ] **Step 3: Table-aggregation tests**

```tsx
// __tests__/PromoCodesTable.test.tsx
// Smoke: render с replyMockSupabase, проверить:
// - 4 KPI заполнены
// - 6 строк
// - Sticky tfoot Итого совпадает с суммой строк
// - URL ?q=CHARLOTTE фильтрует
// - URL ?from=2026-03-09 меняет qty/sales
// (Использовать MSW/setupTests.ts mocks как в существующих тестах Hub)
```

- [ ] **Step 4: Manual smoke**

```bash
npm run dev
# /marketing/promo-codes — 4 KPI, 6 строк, DateRange меняет числа.
# Поиск работает. URL содержит q + from + to.
# Темная тема — все цвета корректны.
```

- [ ] **Step 5: Commit**

```bash
git add wookiee-hub/src/pages/marketing/promo-codes*
git commit -m "feat(marketing): Promo Codes — table + KPI + DateRange + URL filter state"
```

---

### Task 1.8: Промокоды — detail panel (Drawer reuse)

**Files:**
- Create: `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx`
- Modify: `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx` — открытие drawer
- Modify: `wookiee-hub/src/api/marketing/promo-codes.ts` — `fetchPromoStatsForCode`

**Why:** Designer Important #5 — reuse `@/components/crm/ui/Drawer`. Read-only, edit и create — Phase 2.

- [ ] **Step 1: API endpoint per-code**

```ts
// api/marketing/promo-codes.ts (добавить):
export async function fetchPromoStatsForCode(promoCodeId: number): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_stats_weekly')
    .select('*').eq('promo_code_id', promoCodeId).order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map(/* same coerce as fetchPromoStatsWeekly */)
}
```

- [ ] **Step 2: PromoDetailPanel в Drawer**

```tsx
// PromoDetailPanel.tsx
import { Drawer } from "@/components/crm/ui/Drawer"
import { Badge } from "@/components/crm/ui/Badge"
import { useQuery } from "@tanstack/react-query"
import { fetchPromoStatsForCode } from "@/api/marketing/promo-codes"
import { usePromoCodes } from "@/hooks/marketing/use-promo-codes"
import { EmptyState } from "@/components/crm/ui/EmptyState"

export function PromoDetailPanel({ promoId, onClose }: { promoId: number; onClose: () => void }) {
  const { data: promos = [] } = usePromoCodes()
  const { data: weekly = [], isLoading } = useQuery({ queryKey: ['promo-weekly', promoId], queryFn: () => fetchPromoStatsForCode(promoId), enabled: promoId > 0 })
  const promo = promos.find((p) => p.id === promoId)

  return (
    <Drawer open onOpenChange={(o) => !o && onClose()} side="right" title={
      promo ? (
        <div className="flex flex-col gap-1">
          <span className="font-mono text-xs text-muted-foreground break-all">{promo.code}</span>
          <div className="flex items-center gap-1.5">
            <Badge tone={promo.status === 'unidentified' ? 'warning' : 'success'}>
              {promo.status === 'unidentified' ? 'Не идентиф.' : 'Активен'}
            </Badge>
            {promo.channel && <Badge tone="secondary">{promo.channel}</Badge>}
          </div>
        </div>
      ) : 'Промокод'
    }>
      {/* Read-only форма (код, канал, скидка, даты) */}
      {/* KPI блок: Продажи шт / ₽ / Ср. чек */}
      {/* «Товарная разбивка» — EmptyState placeholder (Phase 2 пока без backfill) */}
      {/* Weekly table */}
      {/* Подробная реализация повторяет JSX PromoPanel mode='view' с заменой stone-* по mapping table */}
    </Drawer>
  )
}
```

- [ ] **Step 3: Подключить из PromoCodesTable**

Открытие через `?open=N` (уже сделано в Task 1.7 setQ). В PromoCodesTable рендерим:

```tsx
const openId = params.get('open') ? Number(params.get('open')) : null
{openId && <PromoDetailPanel promoId={openId} onClose={() => setQ('open', null)} />}
```

- [ ] **Step 4: Smoke**

```bash
npm run dev
# /marketing/promo-codes — клик CHARLOTTE10 → drawer справа.
# URL ?open=1 — refresh открывает drawer.
# Esc / клик по фону / крестик — закрывает (Drawer focus management).
# Weekly stats: 02 мар (10845₽, 7) + 09 мар (1588₽, 1).
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(marketing): Promo detail panel (read-only, Drawer reuse, EmptyState placeholder for breakdown)"
```

---

### Task 1.9: Поисковые запросы — table + URL state + sticky overflow

**Files:**
- Modify: `wookiee-hub/src/pages/marketing/search-queries.tsx`
- Create: `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`

**Why:** Designer Important #8 — `overflow-x-auto` + `<colgroup>`. Frontend Important #6 — URL state. Designer Important #3 — loading states.

- [ ] **Step 1: SearchQueriesTable (URL filters, table-fixed colgroup, sticky tfoot, lazy panel)**

```tsx
// SearchQueriesTable.tsx
// Подробная имплементация — следует JSX функции SearchPage с заменами:
// - stone-* → semantic токены (см. mapping table)
// - filter state в URL: model, channel, q, from, to, open
// - QueryStatusBoundary вокруг основного контента
// - <table className="min-w-[1100px] table-fixed tabular-nums"> в <div className="overflow-x-auto">
// - <colgroup> с явными w-* для всех 11 колонок
// - sticky tfoot с теми же colgroup
// - SectionHeader для 4 групп (brand, external, cr_general, cr_personal) с counter
// - Empty state для секции с count=0 (но СЕКЦИЯ ВСЕГДА ВИДИМА)
// - Pills фильтры модель + канал в header
// - DateRange — wired к useSearchQueryStats(from, to)
// - Sorting внутри секции по orders desc
// - CR проценты client-side: pct(orders, transitions) etc
// - Стартовая брендовая секция БУДЕТ ВИДИМА с counter=0 + Empty body (per Frontend Minor #13)
```

Ключевое — `<colgroup>`:

```tsx
<colgroup>
  <col className="w-[140px]" />  {/* Запрос */}
  <col className="w-[140px]" />  {/* Артикул */}
  <col className="w-[100px]" />  {/* Канал */}
  <col className="w-[120px]" />  {/* Кампания */}
  <col className="w-[80px]"  />  {/* Частота */}
  <col className="w-[80px]"  />  {/* Перех. */}
  <col className="w-[70px]"  />  {/* CR→корз */}
  <col className="w-[80px]"  />  {/* Корз. */}
  <col className="w-[70px]"  />  {/* CR→зак */}
  <col className="w-[80px]"  />  {/* Заказы */}
  <col className="w-[60px]"  />  {/* CRV */}
</colgroup>
```

Полный код будет ~200 строк — следовать JSX `SearchPage` функция как референс.

- [ ] **Step 2: Aggregation tests**

```tsx
// __tests__/SearchQueriesTable.test.tsx
// Smoke + grouping logic:
// - Группа brand с count=0 показана с Empty
// - Группа external с N строк
// - Сортировка внутри секции по orders desc
// - CR проценты вычисляются на лету
// - Pills фильтр уменьшает count в SectionHeader
// - DateRange меняет stats per row (mock RPC)
```

- [ ] **Step 3: Page wrapper**

```tsx
// search-queries.tsx
export function SearchQueriesPage() {
  return (
    <>
      <PageHeader
        title={<span style={{ fontFamily: "'Instrument Serif', serif", fontStyle: 'italic', fontSize: 24 }}>Поисковые запросы</span>}
        sub="Брендовые, артикулы и подменные WW-коды"
        actions={null /* «+ Добавить» в Phase 2 */}
      />
      <SearchQueriesTable />
    </>
  )
}
```

- [ ] **Step 4: Manual smoke**

```bash
npm run dev
# /marketing/search-queries:
# - 4 секции, brand=0 (Empty), external/cr_general/cr_personal с реальными числами
# - Pills фильтр работает, totals пересчитываются
# - URL содержит ?model=Wendy&channel=creators&from=...&to=...
# - Сужение DateRange меняет числа
# - Клик по строке → ?open=S42 (panel в Task 1.10)
# - Horizontal overflow при detail panel открытом — корректно scrollable
# - Sticky tfoot align к колонкам
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(marketing): Search Queries — table + pills + DateRange + URL state + sticky overflow"
```

---

### Task 1.10: Поисковые запросы — detail panel + funnel cascade spec

**Files:**
- Create: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx` — открытие panel

**Why:** Designer Important #7 — funnel cascade explicit visual spec.

**Funnel visual spec (canonical):**

Вертикальный stack, 4 ступени + 3 промежуточных CR. Каждая ступень — flex row `[icon? label] ... [value tabular-nums]`. Между ступенями — отдельная строка `[indent-4 pl-4 [CR description]] ... [CR % small]` (опускается на 0.5 строки, серый текст). Финальная строка — `border-t mt-2 pt-2` с `[CR Перех → Зак]` жирно.

Пример layout для Phase 1:
```
┌─────────────────────────────────────────┐
│  За выбранный период                    │
│                                          │
│  Частота           ........  148,174    │
│  Переходы          ........    6,246    │
│      CR Перех→корз ........   27.1%     │
│  Корзина           ........    1,694    │
│      CR Корз→Зак   ........   11.0%     │
│  Заказы            ........      186    │
│  ─────────────────────────────────────  │
│  CR Перех→Зак      ........   2.98%     │
│                                          │
│  Всего за всё время: 5,820 заказов · 40 нед данных │
└─────────────────────────────────────────┘
```

CSS подход: каждая ступень `flex items-center justify-between`, промежуточные CR вложены `pl-4 -mt-0.5 text-[11px] text-muted-foreground`. Финальная итоговая `pt-1 mt-1 border-t border-border/50` с большим текстом.

- [ ] **Step 1: Реализация в Drawer**

Полный код ~150 строк — следовать JSX `SQPanel` функция (~ строки 465–530) с заменами:
- Drawer wrapper from `@/components/crm/ui/Drawer`
- StatusEditor (Task 1.5) wired в Phase 1 как **disabled** (mutation в Task 2.7)
- Funnel cascade per spec выше
- Weekly table с toggle «На период / Все недели»
- Empty state когда `weekly.length === 0` (для branded queries)

- [ ] **Step 2: Подключить из table**

```tsx
{openId && <SearchQueryDetailPanel
  unifiedId={openId}
  dateFrom={dateFrom}
  dateTo={dateTo}
  onClose={() => setQ('open', null)}
/>}
```

- [ ] **Step 3: Smoke**

```bash
npm run dev
# /marketing/search-queries — клик `WW121790` Wendy/dark_beige_S
# Drawer с воронкой:
# - Частота 148174, Переходы 6246, CR→корз 27.1%, Корз 1694, CR→Зак 11.0%, Заказы 186, CRV 2.98%
# - Weekly table с переключением «На период / Все 40»
# - StatusEditor disabled (Phase 2 enables)
# - Esc/клик-вне закрывают, focus возвращается на строку
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(marketing): Search query detail panel — funnel cascade + weekly toggle (Drawer reuse)"
```

---

### Task 1.11: Phase 1 verification + tag

**Files:** none (only verification)

- [ ] **Step 1: Build prod + tests**

```bash
cd wookiee-hub && npm run build && npm test
# Зелёный билд, все тесты проходят.
```

- [ ] **Step 2: Manual E2E через все Hub-разделы (regression check)**

Зайти в каждую существующую секцию (catalog, operations, community, influence, analytics) — убедиться что ничего не сломано.

- [ ] **Step 3: Manual matrix Phase 1**

15 пунктов — см. Phase 4 QA matrix items 1–15. Все должны пройти.

- [ ] **Step 4: Tag**

```bash
git tag marketing-phase-1-complete
```

---

## Phase 2 — CRUD + новые поля (8 задач)

### Task 2.1: Migration `marketing.channels` (с slug-trigger, restricted INSERT)

**Files:**
- Create: `database/marketing/tables/2026-05-09-channels.sql`

**Why:** Backend Blocker #3 — slug auto-generation server-side, INSERT только service_role и admin role; Phase 2 SelectMenu allowAdd идёт через защищённый API endpoint (Task 2.8) который пишет от service_role.

- [ ] **Step 1: Таблица + trigger**

```sql
CREATE TABLE marketing.channels (
  id          bigserial PRIMARY KEY,
  slug        text NOT NULL UNIQUE,
  label       text NOT NULL,
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Server-side slug generation (lower latin + digits + _, fallback)
CREATE OR REPLACE FUNCTION marketing.tg_channels_slug() RETURNS trigger AS $$
DECLARE
  base text;
  candidate text;
  n int := 0;
BEGIN
  IF NEW.slug IS NULL OR NEW.slug = '' THEN
    base := lower(regexp_replace(NEW.label, '[^a-zA-Z0-9]+', '_', 'g'));
    base := regexp_replace(base, '^_+|_+$', '', 'g');
    IF base = '' THEN base := 'channel'; END IF;
    candidate := base;
    WHILE EXISTS (SELECT 1 FROM marketing.channels WHERE slug = candidate) LOOP
      n := n + 1;
      candidate := base || '_' || n::text;
    END LOOP;
    NEW.slug := candidate;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER channels_slug_before_insert BEFORE INSERT ON marketing.channels
  FOR EACH ROW EXECUTE FUNCTION marketing.tg_channels_slug();

ALTER TABLE marketing.channels ENABLE ROW LEVEL SECURITY;

-- Read for authenticated
CREATE POLICY channels_read ON marketing.channels FOR SELECT TO authenticated USING (true);
-- Write only service_role (UI пойдёт через Edge Function / RPC если потребуется)
GRANT SELECT ON marketing.channels TO authenticated;
GRANT ALL ON marketing.channels TO service_role;
GRANT USAGE ON SEQUENCE marketing.channels_id_seq TO service_role;

-- Seed
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

- [ ] **Step 2: Apply, verify, commit**

```sql
SELECT * FROM marketing.channels ORDER BY id;
-- 12 строк
```

```bash
git add database/marketing/tables/2026-05-09-channels.sql
git commit -m "feat(marketing): channels registry (slug auto-trigger, service_role write)"
```

---

### Task 2.2: Migration `creator_ref` + BEFORE INSERT trigger (фикс ETL drift)

**Files:**
- Create: `database/marketing/migrations/2026-05-09-creator-ref-trigger.sql`
- Modify: `database/marketing/views/2026-05-09-search-queries-unified.sql` — заменить `NULL::text AS creator_ref` на `sa.creator_ref`

**Why:** CTO Blocker #2 + Backend Minor #12 — trigger решает drift без правки Python ETL. Backend Important #4 — case-insensitive regex.

- [ ] **Step 1: Миграция + триггер**

```sql
ALTER TABLE crm.substitute_articles ADD COLUMN IF NOT EXISTS creator_ref text;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_substitute_articles_creator_ref ON crm.substitute_articles(creator_ref);

-- Backfill existing rows
UPDATE crm.substitute_articles
SET creator_ref = trim(regexp_replace(campaign_name, '^креатор[_ ]', '', 'i'))
WHERE creator_ref IS NULL AND campaign_name ~* '^креатор[_ ]';

-- Trigger: keep creator_ref in sync with campaign_name on INSERT/UPDATE (handles ETL going forward)
CREATE OR REPLACE FUNCTION crm.tg_substitute_articles_creator_ref() RETURNS trigger AS $$
BEGIN
  IF NEW.campaign_name IS NOT NULL AND NEW.campaign_name ~* '^креатор[_ ]' THEN
    NEW.creator_ref := trim(regexp_replace(NEW.campaign_name, '^креатор[_ ]', '', 'i'));
  ELSIF NEW.campaign_name IS NULL OR NEW.campaign_name !~* '^креатор[_ ]' THEN
    NEW.creator_ref := NULL;  -- explicit clear when pattern not matching
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS substitute_articles_creator_ref ON crm.substitute_articles;
CREATE TRIGGER substitute_articles_creator_ref
  BEFORE INSERT OR UPDATE OF campaign_name ON crm.substitute_articles
  FOR EACH ROW EXECUTE FUNCTION crm.tg_substitute_articles_creator_ref();
```

- [ ] **Step 2: Update VIEW**

CREATE OR REPLACE VIEW marketing.search_queries_unified — заменить `NULL::text AS creator_ref` на `sa.creator_ref` для substitute_articles ветки. Полный SQL — см. Task 1.1 Step 1, replace ту строку.

- [ ] **Step 3: Verify**

```sql
SELECT creator_ref, COUNT(*) FROM crm.substitute_articles WHERE creator_ref IS NOT NULL GROUP BY creator_ref ORDER BY 1;
-- Ожидаем ≥6 имён: Донцова, Малашкина, Токмачева, Чиркина, Шматок, Юдина

-- Тест trigger
INSERT INTO crm.substitute_articles (code, artikul_id, purpose, campaign_name, status) VALUES ('TESTWW', 1, 'creators', 'креатор_ТестИмя', 'active');
SELECT creator_ref FROM crm.substitute_articles WHERE code='TESTWW';
-- Ожидаем 'ТестИмя'
DELETE FROM crm.substitute_articles WHERE code='TESTWW';

-- View
SELECT unified_id, creator_ref FROM marketing.search_queries_unified WHERE creator_ref IS NOT NULL LIMIT 5;
```

- [ ] **Step 4: Commit**

```bash
git add database/marketing/
git commit -m "feat(marketing): creator_ref column + auto-sync trigger from campaign_name (case-insensitive)"
```

---

### Task 2.3: Migration `marketing.promo_product_breakdown`

**Files:**
- Create: `database/marketing/tables/2026-05-09-promo-product-breakdown.sql`

**Why:** Backend Important #5 — `artikul_id NOT NULL FK` вместо text label.

- [ ] **Step 1: Таблица**

```sql
CREATE TABLE marketing.promo_product_breakdown (
  id              bigserial PRIMARY KEY,
  promo_code_id   bigint  NOT NULL REFERENCES crm.promo_codes(id)  ON DELETE CASCADE,
  week_start      date    NOT NULL,
  artikul_id      integer NOT NULL,                 -- FK добавим если catalog.artikuly экспортирует SELECT для authenticated
  sku_label       text    NOT NULL,                 -- denormalized cache
  model_code      text,
  qty             integer NOT NULL DEFAULT 0,
  amount_rub      numeric NOT NULL DEFAULT 0,
  captured_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (promo_code_id, week_start, artikul_id)
);

CREATE INDEX idx_ppb_promo_code ON marketing.promo_product_breakdown(promo_code_id);

ALTER TABLE marketing.promo_product_breakdown ENABLE ROW LEVEL SECURITY;
CREATE POLICY ppb_read  ON marketing.promo_product_breakdown FOR SELECT TO authenticated USING (true);
GRANT SELECT ON marketing.promo_product_breakdown TO authenticated;
GRANT ALL    ON marketing.promo_product_breakdown TO service_role;
GRANT USAGE ON SEQUENCE marketing.promo_product_breakdown_id_seq TO service_role;
```

(FK на `catalog.skus(id)` или `catalog.artikuly(id)` — добавить после Pre-flight PF5 подтверждения. Если такого первичного нет — оставляем `artikul_id NOT NULL` без FK.)

- [ ] **Step 2: Verify, commit**

---

### Task 2.4: AddPromoPanel (Drawer, optimistic mutation)

**Files:**
- Create: `wookiee-hub/src/pages/marketing/promo-codes/AddPromoPanel.tsx`
- Modify: `wookiee-hub/src/api/marketing/promo-codes.ts` — `createPromoCode`
- Modify: `wookiee-hub/src/hooks/marketing/use-promo-codes.ts` — `useCreatePromoCode` с optimistic
- Modify: `wookiee-hub/src/pages/marketing/promo-codes.tsx` — кнопка «+ Добавить»

**Why:** Designer Important #5 — Drawer reuse. Frontend Important #8 — optimistic update + rollback.

- [ ] **Step 1: API**

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
  const { data, error } = await supabase.schema('crm').from('promo_codes').insert({
    code: input.code.toUpperCase().trim(),
    name: input.name ?? null,
    external_uuid: input.external_uuid ?? null,
    channel: input.channel ?? null,
    discount_pct: input.discount_pct ?? null,
    valid_from: input.valid_from || null,
    valid_until: input.valid_until || null,
    status: 'active',
  }).select('*').single()
  if (error) throw error
  return data as PromoCodeRow
}
```

- [ ] **Step 2: Hook with optimistic update**

```ts
export function useCreatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createPromoCode,
    onMutate: async (input) => {
      await qc.cancelQueries({ queryKey: promoCodesKeys.list() })
      const prev = qc.getQueryData<PromoCodeRow[]>(promoCodesKeys.list()) ?? []
      const optimistic: PromoCodeRow = {
        id: -Date.now(), // negative id для optimistic, заменится после success
        code: input.code.toUpperCase().trim(),
        name: input.name ?? null,
        external_uuid: input.external_uuid ?? null,
        channel: input.channel ?? null,
        discount_pct: input.discount_pct ?? null,
        valid_from: input.valid_from ?? null,
        valid_until: input.valid_until ?? null,
        status: 'active',
        notes: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      qc.setQueryData<PromoCodeRow[]>(promoCodesKeys.list(), [optimistic, ...prev])
      return { prev }
    },
    onError: (_err, _input, ctx) => {
      if (ctx?.prev) qc.setQueryData(promoCodesKeys.list(), ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: promoCodesKeys.list() }),
  })
}
```

- [ ] **Step 3: AddPromoPanel в Drawer**

```tsx
// AddPromoPanel.tsx
import { Drawer } from "@/components/crm/ui/Drawer"
import { Button } from "@/components/crm/ui/Button"
import { SelectMenu } from "@/components/marketing/SelectMenu"
import { useChannels } from "@/hooks/marketing/use-channels"
import { useCreatePromoCode } from "@/hooks/marketing/use-promo-codes"
import { useState } from "react"

export function AddPromoPanel({ onClose }: { onClose: () => void }) {
  const { data: channels = [] } = useChannels()
  const create = useCreatePromoCode()
  const [form, setForm] = useState({ code: '', channel: '', discount_pct: '', valid_from: '', valid_until: '' })
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!form.code.trim()) { setError('Код обязателен'); return }
    setError(null)
    try {
      await create.mutateAsync({
        code: form.code,
        channel: form.channel || undefined,
        discount_pct: form.discount_pct ? Number(form.discount_pct) : undefined,
        valid_from: form.valid_from || undefined,
        valid_until: form.valid_until || undefined,
      })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось создать')
    }
  }

  return (
    <Drawer open onOpenChange={(o) => !o && onClose()} side="right" title="Новый промокод">
      {/* Form */}
      {/* code (text required) / channel (SelectMenu allowAdd) / discount_pct (number) / valid_from / valid_until */}
      {/* error inline */}
      {/* submit Button с loading state когда create.isPending */}
      {/* Drawer focus management — автоматически */}
    </Drawer>
  )
}
```

- [ ] **Step 4: Кнопка «+ Добавить» в PageHeader через URL state**

```tsx
// promo-codes.tsx
const [params, setParams] = useSearchParams()
const adding = params.get('add') === '1'
// PageHeader actions:
<Button variant="primary" onClick={() => setParams((p) => { p.set('add', '1'); return p })}>+ Добавить</Button>
{adding && <AddPromoPanel onClose={() => setParams((p) => { p.delete('add'); return p })} />}
```

- [ ] **Step 5: E2E + cleanup**

```bash
# /marketing/promo-codes → + Добавить → drawer → создать TEST10 / Соцсети / 10%
# Убедиться: optimistic появилась моментально, через ~300мс заменилась на server-id
# DELETE FROM crm.promo_codes WHERE code='TEST10';
```

- [ ] **Step 6: Commit**

---

### Task 2.5: AddBrandQueryPanel (NEW per user)

**Files:**
- Create: `wookiee-hub/src/pages/marketing/search-queries/AddBrandQueryPanel.tsx`
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` — `createBrandQuery`
- Modify: `wookiee-hub/src/hooks/marketing/use-search-queries.ts` — `useCreateBrandQuery`

**Why:** Пользователь подтвердил «брендовые запросы заполняем мы, поле ввода».

- [ ] **Step 1: API**

```ts
export interface BrandQueryCreate {
  query: string                          // что ищут на WB
  canonical_brand: string                 // например 'wookiee'
  model_osnova_id?: number | null         // опционально привязка к модели
  notes?: string
}

export async function createBrandQuery(input: BrandQueryCreate): Promise<void> {
  const { error } = await supabase.schema('crm').from('branded_queries').insert({
    query: input.query.trim(),
    canonical_brand: input.canonical_brand.trim().toLowerCase(),
    model_osnova_id: input.model_osnova_id ?? null,
    status: 'active',
    notes: input.notes ?? null,
  })
  if (error) throw error
}
```

- [ ] **Step 2: Hook + Drawer + UI** (детали ниже, аналогично AddPromoPanel)

- [ ] **Step 3: Кнопка в SearchQueriesPage** — из dropdown выбор «Что добавить?» → branded / WW-code (Task 2.6).

- [ ] **Step 4: E2E**

```bash
# /marketing/search-queries → + Добавить → branded → query "wookee" / canonical_brand "wookiee"
# Убедиться: появилась в секции «Брендированные» (раньше пустая)
```

- [ ] **Step 5: Commit**

---

### Task 2.6: AddWWPanel (Drawer, cascade SKU)

**Files:**
- Create: `wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx`
- Modify: `wookiee-hub/src/api/marketing/search-queries.ts` — `createSubstituteArticle` с soft-validation
- Create: `wookiee-hub/src/api/catalog/skus.ts` (если нет) — `lookupSku`

**Why:** v1 Task 2.5 + soft-validation channel slug (CTO Blocker #3 + decision).

- [ ] **Step 1: API + soft-validation**

```ts
export async function createSubstituteArticle(input: {
  code: string
  artikul_id: number
  purpose: string                       // должен быть валидный slug из marketing.channels
  nomenklatura_wb?: string
  campaign_name?: string                 // creator_ref извлечётся триггером
}): Promise<void> {
  // Soft-validate channel slug
  const { data: ch } = await supabase.schema('marketing').from('channels').select('slug').eq('slug', input.purpose).maybeSingle()
  if (!ch) throw new Error(`Неизвестный канал: ${input.purpose}. Добавьте через справочник каналов.`)

  const { error } = await supabase.schema('crm').from('substitute_articles').insert({
    code: input.code,
    artikul_id: input.artikul_id,
    purpose: input.purpose,
    nomenklatura_wb: input.nomenklatura_wb ?? null,
    campaign_name: input.campaign_name ?? null,
    status: 'active',
  })
  if (error) throw error
}
```

- [ ] **Step 2-5: Hook with optimistic, AddWWPanel Drawer with cascade SKU lookup, E2E, commit**

(Имплементация cascade — следовать v1 plan + добавить tabs/radio для типа: «общий креатор / личный креатор / артикул-номенклатура».)

---

### Task 2.7: Status edit mutation (optimistic)

**Files:**
- Modify: `wookiee-hub/src/hooks/marketing/use-search-queries.ts` — `useUpdateSearchQueryStatus` с optimistic
- Modify: `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx` — enable StatusEditor

**Why:** Frontend Important #8.

- [ ] **Step 1: Hook with optimistic**

```ts
export function useUpdateSearchQueryStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ unifiedId, status }: { unifiedId: string; status: SearchQueryStatus }) => updateSearchQueryStatus(unifiedId, status),
    onMutate: async ({ unifiedId, status }) => {
      await qc.cancelQueries({ queryKey: searchQueriesKeys.list() })
      const prev = qc.getQueryData<SearchQueryRow[]>(searchQueriesKeys.list()) ?? []
      const next = prev.map((r) => (r.unified_id === unifiedId ? { ...r, status } : r))
      qc.setQueryData(searchQueriesKeys.list(), next)
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(searchQueriesKeys.list(), ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: searchQueriesKeys.list() }),
  })
}
```

- [ ] **Step 2: Wire в panel** — `<StatusEditor status={item.status} onChange={(s) => updateStatus.mutate({ unifiedId: item.unified_id, status: s })} disabled={updateStatus.isPending} />`

- [ ] **Step 3: E2E + restore**

---

### Task 2.8: Phase 2 verification + tag

```bash
git tag marketing-phase-2-complete
```

QA: создание промокода / brand query / WW-кода работает; status edit персистится; rollback при offline / unauthorized; soft-validation отвергает unknown slug.

---

## Phase 3 — Sync infrastructure (3 задачи)

### Task 3.1: Migration `marketing.sync_log` + alerting hook

**Files:**
- Create: `database/marketing/tables/2026-05-09-sync-log.sql`
- Modify: `services/sheets_sync/sync/sync_promocodes.py` — sync_log + telegram alert
- Modify: `services/sheets_sync/sync/sync_search_queries.py` (correct path per Backend Important #6) — sync_log + telegram alert

**Why:** Backend Important #6 + CTO Important #6.

- [ ] **Step 1: Таблица**

```sql
CREATE TABLE marketing.sync_log (
  id              bigserial PRIMARY KEY,
  job_name        text NOT NULL,
  status          text NOT NULL CHECK (status IN ('running','success','failed')),
  started_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz,
  rows_processed  integer,
  rows_written    integer,
  weeks_covered   text,
  error_message   text,
  triggered_by    text
);

CREATE INDEX idx_sync_log_job_finished ON marketing.sync_log(job_name, finished_at DESC);

ALTER TABLE marketing.sync_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY sl_read ON marketing.sync_log FOR SELECT TO authenticated USING (true);
GRANT SELECT ON marketing.sync_log TO authenticated;
GRANT ALL ON marketing.sync_log TO service_role;
GRANT USAGE ON SEQUENCE marketing.sync_log_id_seq TO service_role;
```

- [ ] **Step 2: ETL hooks (Python)**

В `services/sheets_sync/sync/sync_promocodes.py` и `services/sheets_sync/sync/sync_search_queries.py` обернуть main():

```python
from shared.data_layer import get_supabase_admin
from shared.telegram_alerts import send_alert  # уже существует — алерт-бот pattern

def run_with_logging(job_name: str, run_fn):
    sb = get_supabase_admin()
    log = sb.schema('marketing').from_('sync_log').insert({
        'job_name': job_name, 'status': 'running', 'triggered_by': 'cron'
    }).execute()
    log_id = log.data[0]['id']
    try:
        result = run_fn()
        sb.schema('marketing').from_('sync_log').update({
            'status': 'success',
            'finished_at': 'now()',
            'rows_processed': result.get('rows_processed'),
            'rows_written':   result.get('rows_written'),
            'weeks_covered':  result.get('weeks_covered'),
        }).eq('id', log_id).execute()
    except Exception as e:
        sb.schema('marketing').from_('sync_log').update({
            'status': 'failed', 'finished_at': 'now()', 'error_message': str(e)[:500]
        }).eq('id', log_id).execute()
        # Fail-open — log INSERT failure не должен крашить ETL отдельно. Но ALERT всегда:
        try:
            send_alert(f'❌ Sync FAILED: {job_name}\n{str(e)[:300]}')
        except Exception:
            pass
        raise
```

- [ ] **Step 3: Stale-sync watcher (cron job)**

Добавить новый cron job в `services/sheets_sync/`:

```python
# scripts/check_stale_sync.py — runs daily 09:00 UTC
# Если последний success_finished_at < now() - 36h для любого job_name — alert.
```

- [ ] **Step 4: Verify, commit**

---

### Task 3.2: UpdateBar wiring (5min polling, status-aware)

**Files:**
- Create: `wookiee-hub/src/api/marketing/sync-log.ts`
- Modify: `wookiee-hub/src/components/marketing/UpdateBar.tsx` — реальные данные

**Why:** Frontend Important #10 — 5min polling, не 60s.

- [ ] **Step 1: API**

```ts
export async function fetchLastSync(jobName: string): Promise<SyncLogEntry | null> {
  const { data } = await supabase.schema('marketing').from('sync_log')
    .select('*').eq('job_name', jobName)
    .order('finished_at', { ascending: false }).limit(1).maybeSingle()
  return data
}
```

- [ ] **Step 2: Hook**

```ts
export function useLastSync(jobName: string) {
  return useQuery({
    queryKey: ['marketing', 'sync-log', jobName],
    queryFn: () => fetchLastSync(jobName),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
    refetchOnWindowFocus: true,
  })
}
```

- [ ] **Step 3: Wire в страницы**

В PromoCodesTable:
```tsx
const { data: last } = useLastSync('promo_codes_sync')
<UpdateBar lastUpdate={last?.finished_at ? formatDateTime(last.finished_at) : '—'} weeksCovered={last?.weeks_covered ?? undefined} status={last?.status === 'failed' ? 'failed' : last?.status === 'success' ? 'success' : 'unknown'} />
```

Аналогично в SearchQueriesTable с `'search_queries_sync'`.

- [ ] **Step 4: Manual trigger button — backlog**

«Обновить» button делаем placeholder (логирует «manual trigger requested»). Реальный trigger — Edge Function или authenticated RPC, отдельный backlog.

---

### Task 3.3: Phase 3 verification

```bash
# Запустить ETL вручную:
docker exec wookiee_cron python services/sheets_sync/sync/sync_promocodes.py --mode rolling
# UpdateBar в Hub обновляется через ≤5 мин.
git tag marketing-phase-3-complete
```

---

## Phase 4 — QA pass (расширенная матрица 40+ пунктов)

### Task 4.1: Полная QA-матрица

**Files:**
- Create: `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2-qa.md`

**Why:** CTO Important #8 — добавить RLS, ETL idempotency, load test, dark/light theme.

Матрица (минимум 40 пунктов):

**Феатур-флаг (3):**
1. С `VITE_FEATURE_MARKETING=false` — иконка Megaphone отсутствует в icon-bar
2. С false — прямой переход `/marketing/promo-codes` редиректит
3. С true — всё доступно

**Промокоды (12):**
4–15. Покрытие как в v1 + URL state restore + optimistic update + rollback на error

**Поисковые запросы (15):**
16–30. Покрытие v1 + 4 секции (включая brand с Empty) + URL filter persistence + horizontal overflow + sticky tfoot + StatusEditor optimistic + AddBrandQueryPanel + AddWWPanel cascade

**Безопасность / RLS (5):**
31. `anon` (без login) — нет доступа к `/marketing/*` (ProtectedRoute)
32. SQL: `SELECT ... FROM marketing.search_queries_unified` от анонима возвращает 0 строк (RLS)
33. SQL: `INSERT INTO marketing.channels` от authenticated НЕ работает (только service_role)
34. ETL idempotency: ручной TEST_PROMO + cron Mon — не дублируется
35. AddPromoPanel под нерасширенными правами (если есть роли) — корректное error message

**Темизация (3):**
36. Все экраны в dark — токены корректны, нет белых пятен
37. Все экраны в light — то же
38. Toggle темы в одном sitting — без визуальных glitches

**Performance / load (3):**
39. RPC `search_query_stats_aggregated` для 1-год периода — < 500мс
40. Page load `/marketing/search-queries` cold — < 2s
41. Filter change re-render — нет visual lag

**Регрессии (2):**
42. Все остальные секции Hub работают
43. `npm run build` + `npm test` — green

- [ ] **Step 1: Скрипт QA — отдельный subagent (НЕ тот что писал код), проходит каждый пункт, документирует findings + screenshots**

- [ ] **Step 2: Findings → fixes → re-run QA**

- [ ] **Step 3: Tag**

```bash
git tag marketing-phase-4-complete
```

---

## Phase 5 — Feature flag flip + 24h monitor

### Task 5.1: Production flip + observation

**Files:**
- Modify: `.env.production` (на сервере 77.233.212.61) — `VITE_FEATURE_MARKETING=true`
- Re-build prod через autopull → npm run build

**Why:** Защищённый rollout. Без monitor можно неделями не заметить regression.

- [ ] **Step 1: Merge `feature/marketing-hub` → main**

После Phase 4 done. Autopull деплоит main, но без env флага UI не доступен.

- [ ] **Step 2: Установить флаг на prod**

```bash
ssh timeweb 'cd /home/danila/projects/wookiee/wookiee-hub && echo VITE_FEATURE_MARKETING=true >> .env.production'
# Триггер re-build (через предусмотренный механизм Hub deploy):
# rsync `dist/` → `/home/danila/projects/wookiee/wookiee-hub/dist/` после `npm run build` локально с правильным env.
# Или: добавить env в `.env.production` репозитория и push — autopull подхватит.
```

(Точный механизм — за пользователем. Я предлагаю самый безопасный — env в `.env.production` репо, ребуилд через CI/локально.)

- [ ] **Step 3: 24h наблюдение**

Мониторить:
- `marketing.sync_log` — успешные ли cron-ы Mon 10:00 + Mon 12:00 (если попадают в 24h окно)
- Slack/Telegram alert-бот — нет ли ошибок
- Hub UI — open `/marketing/promo-codes` и `/marketing/search-queries` каждые 6 часов
- Browser console errors

- [ ] **Step 4: Tag GA + memory update**

```bash
git tag marketing-phase-5-ga
# Memory update: добавить запись о completed marketing module
```

---

## File Structure Reference (final)

```
database/marketing/
├── views/
│   └── 2026-05-09-search-queries-unified.sql
├── rpcs/
│   └── 2026-05-09-search-query-stats-aggregated.sql
├── tables/
│   ├── 2026-05-09-channels.sql
│   ├── 2026-05-09-promo-product-breakdown.sql
│   └── 2026-05-09-sync-log.sql
└── migrations/
    └── 2026-05-09-creator-ref-trigger.sql

services/sheets_sync/sync/
├── sync_promocodes.py        (modified — sync_log hook)
└── sync_search_queries.py    (modified — sync_log hook)

scripts/
└── check_stale_sync.py       (new — cron Mon-Sun 09:00 UTC)

wookiee-hub/src/
├── lib/
│   ├── feature-flags.ts
│   ├── marketing-helpers.ts (parseUnifiedId, numToNumber)
│   └── __tests__/{feature-flags,marketing-helpers}.test.ts
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
│   ├── SectionHeader.tsx        (new primitive)
│   ├── SelectMenu.tsx            (new primitive)
│   ├── DateRange.tsx
│   ├── UpdateBar.tsx
│   ├── StatusEditor.tsx
│   └── __tests__/
├── pages/marketing/
│   ├── promo-codes.tsx          (lazy)
│   ├── search-queries.tsx       (lazy)
│   ├── promo-codes/
│   │   ├── PromoCodesTable.tsx
│   │   ├── PromoDetailPanel.tsx     (Drawer reuse)
│   │   └── AddPromoPanel.tsx        (Drawer reuse, optimistic)
│   └── search-queries/
│       ├── SearchQueriesTable.tsx
│       ├── SearchQueryDetailPanel.tsx
│       ├── AddBrandQueryPanel.tsx   (NEW per user)
│       └── AddWWPanel.tsx
└── types/
    └── marketing.ts
```

---

## Self-Review Checklist (v2)

**Spec coverage:**
- [x] Брендированные / артикулы / WW-коды (Task 1.1)
- [x] cr_general / cr_personal (Task 1.1 + 2.2 trigger)
- [x] Каналы registry (Task 2.1, server-side slug)
- [x] Промокоды CRUD (1.7-1.8 + 2.4)
- [x] WW-коды CRUD (1.9-1.10 + 2.6)
- [x] Brand query CRUD (NEW Task 2.5 per user)
- [x] StatusEditor optimistic (1.5 + 2.7)
- [x] UpdateBar реальные данные + alerting (3.1-3.2)
- [x] Воронка с CR explicit visual spec (1.10)
- [x] Sticky tfoot + horizontal overflow (1.7, 1.9)
- [x] DateRange wired client-side с Phase 1 (1.7, 1.9)
- [x] Pills фильтры в URL (1.9)
- [x] SelectMenu allowAdd + a11y (1.4)
- [x] Темизация semantic tokens (mapping table)
- [x] QA фаза 40+ пунктов (4.1)
- [x] Feature flag rollout (1.0, 5.1)
- [x] Lazy-loading (1.2)
- [x] Loading states via QueryStatusBoundary
- [x] Optimistic mutations (2.4-2.7)
- [x] ETL alerting (3.1)

**Closed blockers from review:**
- [x] CTO B1 (DateRange functional) → Task 1.7/1.9 client-side filter
- [x] CTO B2 (creator_ref drift) → Task 2.2 BEFORE INSERT trigger
- [x] CTO B3 (channels FK missing) → Decision: soft-validation (Task 2.6 API)
- [x] Designer B1 (emerald hardcoded) → Reuse CRM Badge с tone API
- [x] Designer B2 (стон-mapping incomplete) → Mapping table в плане
- [x] Frontend B1 (command не существует) → PF4 shadcn add command
- [x] Frontend B2 (Button ambiguous) → Spec @/components/crm/ui/Button
- [x] Backend B1 (search_path public) → SET search_path = pg_catalog, crm
- [x] Backend B2 (RPC UNION inconsistency) → Branded ветка с нулями
- [x] Backend B3 (channels INSERT permissive) → service_role only + slug trigger
- [x] Backend B4/I4 (case-sensitive) → ~* regex

**Closed important:**
- [x] CTO I4 (rollback) → Step 5 в Task 1.1 + DOWN sql
- [x] CTO I5 (SECURITY DEFINER) → SECURITY INVOKER
- [x] CTO I6 (sync alerting) → Task 3.1 send_alert + stale watcher
- [x] CTO I7 (autopull) → Feature flag (Task 1.0, 5.1)
- [x] CTO I8 (QA matrix) → Расширена до 43 пунктов
- [x] Designer I3 (loading) → QueryStatusBoundary
- [x] Designer I4 (a11y SelectMenu) → 5 тестов keyboard + aria
- [x] Designer I5 (Drawer focus) → Reuse CRM Drawer
- [x] Designer I6 (parallel design system) → Только 2 новых примитива
- [x] Designer I7 (funnel spec) → Explicit ASCII-spec в Task 1.10
- [x] Designer I8 (sticky overflow) → table-fixed + colgroup + overflow-x-auto
- [x] Frontend I3 (parseUnifiedId) → Helper в marketing-helpers.ts
- [x] Frontend I4 (creator_ref forward-compat) → Type с Phase 1
- [x] Frontend I5 (lazy-load) → withFallback в Task 1.2
- [x] Frontend I6 (URL filter state) → useSearchParams везде
- [x] Frontend I7 (test coverage) → 4 test files (helpers, SelectMenu, SectionHeader, feature-flags)
- [x] Frontend I8 (optimistic) → Все 3 mutations с rollback
- [x] Frontend I10 (refetchInterval) → 5 min не 1 min
- [x] Backend I5 (FK) → artikul_id NOT NULL (FK pending PF5)
- [x] Backend I6 (sync_log paths) → sync_search_queries.py исправлен
- [x] Backend I7 (channel drift) → Soft-validation в createSubstituteArticle
- [x] Backend I8 (numeric coerce) → numToNumber helper

**Backlog (явно вне scope):**
- promo_product_breakdown backfill (требует WB API)
- Manual sync trigger через Edge Function
- crm.creators registry
- Pagination >500 запросов
- Тестов покрытие >50% (ставится отдельной задачей)

---

## Execution Handoff

**Plan v2 saved to** `docs/superpowers/plans/2026-05-09-marketing-hub-impl-v2.md`.

**Объём:** Pre-flight (7 шагов) + 5 phases × 1-12 tasks = 25 задач total. Estimated 3-5 дней работы для одного агента, ~1.5-2 дня при параллельном subagent execution с QA gate.

**Запуск:** Subagent-Driven Development. Старт с Pre-flight, потом Phase 1 Task 1.0 → 1.11, потом Phase 2 → 3 → 4 → 5.
