# WAVE1 — Design System v2 миграция: инвентаризация `wookiee-hub/`

Read-only аудит перед стартом Wave 1 (миграция Hub-shell + operations/community/influence/analytics на DS v2: stone + DM Sans + Instrument Serif).

- Working directory: `/Users/danilamatveev/Projects/Wookiee/`
- Branch: `feat/ds-v2-wave-1-spec`
- Дата: 2026-05-15

---

## 0. Bundle baseline (pre-Wave 1)

Замер `npm run build` (Vite 7, production mode) до начала миграции.

- **Total `dist/`**: 2932 KB
- **Total CSS gzipped**: 19,995 bytes (~19.5 KB)

### Top 10 JS assets (raw size, KB)

| Файл | Raw KB | Gzip KB (из build output) |
|---|---|---|
| `assets/index-BmQQTPLD.js` | 1624 | 481.96 |
| `assets/supabase-DL5HCojG.js` | 192 | 51.68 |
| `assets/react-BrR0aEqA.js` | 100 | 33.95 |
| `assets/search-queries-ZYZKx21Z.js` | 64 | 17.32 |
| `assets/matrix-C7r7cnmr.js` | 56 | 13.82 |
| `assets/tovary-DgXJyyQV.js` | 52 | 14.07 |
| `assets/artikuly-AxOPD-5L.js` | 48 | 12.39 |
| `assets/query-ClBGlpKM.js` | 40 | 11.06 |
| `assets/colors-ZmgLqVS3.js` | 32 | 7.72 |
| `assets/promo-codes-DoGLrHy8.js` | 24 | 6.92 |

CSS bundle (single):
- `assets/index-DqUCRA4M.css` — 120 KB raw / ~19.5 KB gzipped

**G11 acceptance threshold:** после Wave 1 `du -sk dist/` не должен расти > +250 KB (общий, без учёта gzip).

Build time: 4.76s. Build exit code: 0.

Warning: `index-BmQQTPLD.js` > 700 KB warning threshold (Vite default). Это существующая проблема, не вводится Wave 1 — не блокер.

### Bundle final (post-Wave 1)

После всех 33 commits на ветке `feat/ds-v2-wave-1-spec`:

- **Total `dist/`**: 2784 KB
- **Delta vs baseline (2932 KB)**: **−148 KB** (bundle стал меньше)
- **G11 status**: ✅ PASS (delta < +250 KB threshold; реально negative)

Причина уменьшения: замена `@fontsource-variable/inter` → `@fontsource-variable/dm-sans` (Phase 3) экономит ~160 KB; primitives + preview добавили ~12 KB.

Build time post-Wave 1: 3.90s. Typecheck post-Wave 1: ✓ exit 0. Unit tests: 126/126 pass (31 files).

---

## 1. Hardcoded `stone-*` classes

Итого **74 файла** содержат хардкод `(text|bg|border)-stone-{50..950}`. Всего **1464 вхождения**.

### Топ-50 файлов по числу вхождений

| Файл | Вхождения |
|---|---|
| `pages/catalog/model-card.tsx` | 271 |
| `pages/catalog/matrix.tsx` | 110 |
| `pages/catalog/tovary.tsx` | 83 |
| `pages/catalog/skleyka-card.tsx` | 79 |
| `pages/catalog/artikuly.tsx` | 73 |
| `pages/marketing/search-queries/SearchQueryDetailPanel.tsx` | 55 |
| `pages/catalog/color-card.tsx` | 53 |
| `pages/catalog/import.tsx` | 52 |
| `pages/catalog/reference-card.tsx` | 51 |
| `pages/catalog/artikul-card.tsx` | 42 |
| `pages/marketing/promo-codes/PromoDetailPanel.tsx` | 41 |
| `pages/catalog/sku-card.tsx` | 34 |
| `pages/catalog/sertifikaty.tsx` | 29 |
| `pages/catalog/colors.tsx` | 28 |
| `pages/catalog/references/atributy.tsx` | 27 |
| `pages/catalog/skleyki.tsx` | 25 |
| `pages/catalog/references/_shared.tsx` | 24 |
| `components/catalog/ui/columns-manager.tsx` | 22 |
| `components/catalog/ui/fields.tsx` | 21 |
| `components/catalog/ui/attribute-control.tsx` | 18 |
| `pages/catalog/colors-edit.tsx` | 17 |
| `components/catalog/ui/ref-modal.tsx` | 16 |
| `components/catalog/ui/new-model-modal.tsx` | 16 |
| `components/catalog/ui/filter-bar.tsx` | 16 |
| `components/catalog/ui/command-palette.tsx` | 15 |
| `components/catalog/layout/catalog-sidebar.tsx` | 15 |
| `components/catalog/ui/color-picker.tsx` | 12 |
| `components/catalog/ui/__demo__.tsx` | 12 |
| `components/catalog/ui/bulk-actions-bar.tsx` | 11 |
| `components/catalog/ui/asset-uploader.tsx` | 11 |
| `pages/catalog/upakovki.tsx` | 10 |
| `pages/catalog/references/importery.tsx` | 10 |
| `pages/catalog/references/fabriki.tsx` | 10 |
| `components/catalog/ui/tags-combobox.tsx` | 9 |
| `components/catalog/ui/inline-color-cell.tsx` | 9 |
| `pages/catalog/kanaly-prodazh.tsx` | 8 |
| `components/catalog/ui/inline-select-cell.tsx` | 8 |
| `components/catalog/ui/inline-text-cell.tsx` | 7 |
| `components/catalog/layout/section.tsx` | 7 |
| `pages/catalog/references/razmery.tsx` | 6 |
| `pages/catalog/references/brendy.tsx` | 6 |
| `components/catalog/ui/pagination.tsx` | 6 |
| `components/catalog/layout/catalog-topbar.tsx` | 6 |
| `components/catalog/layout/catalog-table.tsx` | 6 |
| `pages/marketing/search-queries/AddWWPanel.tsx` | 5 |
| `pages/marketing/search-queries/AddNomenclaturePanel.tsx` | 5 |
| `pages/catalog/semeystva-cvetov.tsx` | 5 |
| `pages/catalog/references/kollekcii.tsx` | 5 |
| `pages/catalog/_stub.tsx` | 5 |
| `components/marketing/StatusEditor.tsx` | 5 |

### Группировка по директориям

| Группа | Файлов | Вхождений |
|---|---|---|
| `pages/catalog/*` (без references) | 19 | 976 |
| `components/catalog/ui/*` | 22 | 223 |
| `pages/catalog/references/*` | 10 | 93 |
| `pages/marketing/search-queries/*` | 5 | 71 |
| `pages/marketing/promo-codes/*` | 2 | 43 |
| `components/catalog/layout/*` | 4 | 34 |
| `components/marketing/*` | 8 | 18 |
| `lib/*` (`catalog/color-utils.ts`) | 1 | 3 |
| `hooks/*` (`use-resizable-columns.tsx`) | 1 | 1 |
| `components/crm/ui/*` (`Drawer.tsx`) | 1 | 1 |
| `router.tsx` | 1 | 1 |

### Wave 1 целевые директории — `stone-*` НЕ найдено

Следующие группы из Wave 1 scope **не содержат `stone-*` хардкода**:

- `pages/operations/*` (tools, activity, health) — 0 файлов
- `pages/community/*` (analytics, answers, questions, reviews) — 0 файлов
- `pages/influence/*` (bloggers, calendar, integrations) — 0 файлов
- `pages/analytics/*` (rnp) — 0 файлов
- `components/community/*` — 0 файлов
- `components/layout/*` — 0 файлов
- `components/agents/*` — 0 файлов
- `components/analytics/*` — 0 файлов
- `components/shared/*` — 0 файлов
- `components/ui/*` — 0 файлов
- `components/crm/layout/*` (PageHeader) — 0 файлов

**Вывод по секции 1:** весь `stone-*` хардкод сосредоточен в уже мигрированных разделах `/catalog/*` и `/marketing/*` (Wave 1 их не трогает). Wave 1 целевые разделы (`hub-shell + operations + community + influence + analytics`) — чистые от `stone-*`. Это значит, что миграция этих разделов на палитру stone не сломает существующий каталог/маркетинг.

---

## 2. `dark:` префиксы (топ-30 файлов)

Итого **12 файлов**, **21 вхождение**.

| Файл | Вхождения |
|---|---|
| `components/ui/button.tsx` | 4 |
| `components/ui/input-group.tsx` | 3 |
| `components/agents/run-status-badge.tsx` | 3 |
| `components/community/review-detail.tsx` | 2 |
| `components/agents/tools-table.tsx` | 2 |
| `components/ui/textarea.tsx` | 1 |
| `components/ui/input.tsx` | 1 |
| `components/ui/dropdown-menu.tsx` | 1 |
| `components/ui/checkbox.tsx` | 1 |
| `components/ui/calendar.tsx` | 1 |
| `components/community/review-list-item.tsx` | 1 |
| `components/agents/runs-table.tsx` | 1 |

**Вывод:** `dark:` встречается только в shadcn-style primitives и таблицах. Все эти файлы — внутри Wave 1 scope, нужно вычистить (DS v2 — light-only stone).

---

## 3. Inline styles + font-family

### `style={{ ... }}` — 38 файлов, **74 вхождения**

Группы:
- `components/analytics/rnp-tabs/*` — 3 файла (tab-funnel, tab-margin, tab-orders)
- `components/catalog/ui/*` — 6 файлов (`__demo__`, color-picker, color-swatch, empty-state, new-model-modal, ref-modal)
- `components/community/*` — 4 файла (analytics-rating-chart, analytics-stores-table, review-detail, review-list-item)
- `components/crm/ui/Drawer.tsx`
- `components/layout/*` — 2 файла (catalog-layout, marketing-layout)
- `components/shared/progress-bar.tsx`
- `hooks/use-resizable-columns.tsx`
- `index.css` (одно вхождение — это технически не файл .tsx; учитывается отдельно)
- `pages/catalog/*` — 13 файлов
- `pages/influence/bloggers/*` — 1 файл (BloggersTableView)
- `pages/influence/integrations/*` — 2 файла (IntegrationsTableView, KanbanCard)
- `pages/marketing/*` — 3 файла

### `font-family`

Только в `wookiee-hub/src/index.css`:

- Строка 306: `font-family: 'DM Sans', system-ui, sans-serif;`
- Строка 314: `font-family: 'Instrument Serif', ui-serif, Georgia, serif;`

Никаких `font-family: 'Inter'` или иных шрифтовых хардкодов в `.tsx/.ts` не найдено. DS v2 шрифты (DM Sans + Instrument Serif) уже декларированы в `index.css`.

---

## 4. CRM Kit импорты

Подтверждаю числа:

- **52 import-statement** из `@/components/crm/...` (всего строк)
- **21 уникальный файл** импортирует из `@/components/crm/...`
- **21 файл** импортирует из `@/components/crm/ui/...`
- **3 файла** импортируют из `@/components/crm/layout/...` (PageHeader)

Структура `components/crm/`:

```
crm/
├── layout/
│   └── PageHeader.tsx
└── ui/
    ├── Avatar.tsx
    ├── Badge.tsx
    ├── Button.tsx
    ├── Drawer.tsx
    ├── EmptyState.tsx
    ├── FilterPill.tsx
    ├── Input.tsx
    ├── PlatformPill.tsx
    ├── QueryStatusBoundary.tsx
    ├── Select.tsx
    ├── Skeleton.tsx
    ├── Tabs.tsx
    └── Textarea.tsx
```

### Основные потребители (consumer-files)

`pages/influence/bloggers/*`:
- `BloggerEditDrawer.tsx` (7) — Button, Drawer, EmptyState, Input, Select, Tabs, Textarea
- `BloggersPage.tsx` (3) — PageHeader, Button, QueryStatusBoundary
- `BloggersFilters.tsx` (2) — FilterPill, Input
- `BloggersTable.tsx` (2) — Avatar, Badge
- `BloggerExpandedRow.tsx` (4) — Avatar, Badge, Button, Skeleton

`pages/influence/integrations/*`:
- `IntegrationEditDrawer.tsx` (6) — Button, Drawer, EmptyState, Input, Select, Textarea
- `IntegrationsKanbanPage.tsx` (3) — PageHeader, Button, QueryStatusBoundary
- `KanbanCard.tsx` (2) — Badge, PlatformPill
- `KanbanColumn.tsx` (1) — Badge

`pages/influence/calendar/*`:
- `CalendarPage.tsx` (5) — PageHeader, Button, FilterPill, QueryStatusBoundary, Skeleton
- `CalendarMonthGrid.tsx` (1) — PlatformPill

`pages/marketing/promo-codes/*`:
- `AddPromoPanel.tsx` (3) — Drawer, Button, Input
- `PromoDetailPanel.tsx` (2) — Drawer, EmptyState
- `PromoCodesTable.tsx` (1) — QueryStatusBoundary
- `promo-codes.tsx` (1) — Button

`pages/marketing/search-queries/*`:
- `AddBrandQueryPanel.tsx` (3) — Drawer, Button, Input
- `AddNomenclaturePanel.tsx` (1) — Drawer
- `AddWWPanel.tsx` (1) — Drawer
- `SearchQueryDetailPanel.tsx` (2) — Drawer, EmptyState
- `SearchQueriesTable.tsx` (1) — QueryStatusBoundary
- `search-queries.tsx` (1) — Button

### Сигнатуры CRM Kit (фиксируем для миграции)

| Компонент | Экспорт + ключевые props |
|---|---|
| `Avatar` | `function Avatar({ name, size='sm', className })` |
| `Badge` | `function Badge({ tone='secondary', children, className })` + `type BadgeProps` |
| `Button` | `forwardRef<HTMLButton, ButtonProps>` — extends `ButtonHTMLAttributes` |
| `Drawer` | `function Drawer({ ... })` (полный drawer с overlay) |
| `EmptyState` | `function EmptyState({ title, description, icon, action, className })` |
| `FilterPill` | `forwardRef<HTMLButton, FilterPillProps>` — extends `ButtonHTMLAttributes` |
| `Input` | `forwardRef<HTMLInput, InputProps>` |
| `PlatformPill` | `function PlatformPill({ channel: PlatformChannel, className })` |
| `QueryStatusBoundary` | `function QueryStatusBoundary(...)` + default export |
| `Select` | `forwardRef<HTMLSelect, SelectProps>` |
| `Skeleton` | `function Skeleton({ className, ...rest })` |
| `Tabs` | `function Tabs({ tabs: TabItem[], defaultIndex=0, className })` |
| `Textarea` | `forwardRef<HTMLTextarea, TextareaProps>` |
| `PageHeader` | `function PageHeader({ title, sub, actions, className })` |

---

## 5. Routes inventory

Полный список из `wookiee-hub/src/router.tsx`. **Active routes: 36** + 2 redirect-cluster заглушки (`/operations`, `/community`, `/influence`, `/analytics`, `/catalog`, `/catalog/references`, `/marketing` index) — всего **38 entry в router**.

> Замечание: `design-system-preview-NEW` route не найден в коде. В роутере его нет.

### Login (1)

| Path | Component |
|---|---|
| `/login` | `LoginPage` |

### Catalog cluster (22 — внутри `CatalogLayout`)

| Path | Component |
|---|---|
| `/catalog` | `Navigate → /catalog/matrix` |
| `/catalog/matrix` | `MatrixPage` |
| `/catalog/colors` | `ColorsPage` |
| `/catalog/artikuly` | `ArtikulyPage` |
| `/catalog/tovary` | `TovaryPage` |
| `/catalog/skleyki` | `SkleykiPage` |
| `/catalog/semeystva-cvetov` | `SemeystvaCvetovPage` |
| `/catalog/upakovki` | `UpakovkiPage` |
| `/catalog/kanaly-prodazh` | `KanalyProdazhPage` |
| `/catalog/sertifikaty` | `SertifikatyPage` |
| `/catalog/import` | `CatalogImportPage` |
| `/catalog/__demo__` | `DemoPage` |
| `/catalog/references` | `Navigate → /catalog/references/kategorii` |
| `/catalog/references/kategorii` | `KategoriiPage` |
| `/catalog/references/kollekcii` | `KollekciiPage` |
| `/catalog/references/tipy-kollekciy` | `TipyKollekciyPage` |
| `/catalog/references/brendy` | `BrendyPage` |
| `/catalog/references/fabriki` | `FabrikiPage` |
| `/catalog/references/importery` | `ImporteryPage` |
| `/catalog/references/razmery` | `RazmeryPage` |
| `/catalog/references/statusy` | `StatusyPage` |
| `/catalog/references/atributy` | `AtributyPage` |

### Hub-shell cluster (12 — внутри `AppShell`)

| Path | Component |
|---|---|
| `/` | `Navigate → /operations/tools` |
| `/operations` | `Navigate → /operations/tools` |
| `/operations/tools` | `ToolsPage` |
| `/operations/activity` | `ActivityPage` |
| `/operations/health` | `HealthPage` |
| `/community` | `Navigate → /community/reviews` |
| `/community/reviews` | `ReviewsPage` |
| `/community/questions` | `QuestionsPage` |
| `/community/answers` | `AnswersPage` |
| `/community/analytics` | `AnalyticsPage` |
| `/influence` | `Navigate → /influence/bloggers` |
| `/influence/bloggers` | `BloggersPage` |
| `/influence/integrations` | `IntegrationsKanbanPage` |
| `/influence/calendar` | `CalendarPage` |
| `/analytics` | `Navigate → /analytics/rnp` |
| `/analytics/rnp` | `RnpPage` |

(`16 entries` в hub-shell блоке если считать redirect cluster index'ы; чистых страниц — `tools, activity, health, reviews, questions, answers, analytics(community), bloggers, integrations, calendar, rnp` = 11.)

### Marketing cluster (2 — внутри `MarketingLayout`, под feature flag)

| Path | Component |
|---|---|
| `/marketing` | `Navigate → /marketing/promo-codes` |
| `/marketing/promo-codes` | `PromoCodesPage` |
| `/marketing/search-queries` | `SearchQueriesPage` |

### Design system preview

**НЕ НАЙДЕНО.** В `router.tsx` нет роута `design-system-preview` / `__demo__` (кроме каталоговского `/catalog/__demo__`). Если на Wave 1 нужна preview-страница — её необходимо добавить отдельно.

### Feature flag

- Декларация: `wookiee-hub/src/lib/feature-flags.ts`
  ```ts
  export const featureFlags = {
    marketing: import.meta.env.VITE_FEATURE_MARKETING === 'true',
  } as const
  ```
- Использование: `router.tsx:160` — `...(featureFlags.marketing ? [{ path: "/marketing", ... }] : [])`
- Env-переменная: `VITE_FEATURE_MARKETING=true`
- Сетевой импорт: `import { featureFlags } from "@/lib/feature-flags"` в `router.tsx:19`

### Подсчёт vs ожидание

- Ожидалось: **38** (1 login + 22 catalog + 12 hub-shell + 2 marketing + 1 design-system-preview)
- Фактически: **38 entries в router.tsx** (1 login + 22 catalog + 14 hub-shell включая redirects + 3 marketing включая redirect) — близко, но дизайн-preview-NEW отсутствует
- Чистых рабочих страниц (без redirect): **36** (1 + 21 + 11 + 3 marketing pages)

---

## 6. Primitives gap (DS v2 vs Hub)

Что есть в `wookiee-hub/src/components/ui/` сейчас:

```
button.tsx, calendar.tsx, checkbox.tsx, command.tsx, dialog.tsx,
dropdown-menu.tsx, input-group.tsx, input.tsx, popover.tsx,
separator.tsx, tabs.tsx, textarea.tsx
```

(всего 12 файлов, shadcn-style)

### Сравнение с целевыми 13 primitives DS v2

| Primitive | Status | Где живёт сейчас |
|---|---|---|
| **Badge** | partial | `components/catalog/ui/status-badge.tsx`, `components/marketing/Badge.tsx`, `components/crm/ui/Badge.tsx`. Нет единого `components/ui/badge.tsx`. |
| **StatusBadge** | partial | `components/catalog/ui/status-badge.tsx` (с другой сигнатурой), `components/agents/run-status-badge.tsx`. Нет канонического `components/ui/status-badge.tsx`. |
| **LevelBadge** | missing | Нигде нет. |
| **Tag** | missing | Нет (есть `tags-combobox.tsx`, но это input). |
| **Chip** | missing | Нет (ближайшее — `FilterPill` в CRM kit и `Badge`). |
| **Avatar** | partial | `components/crm/ui/Avatar.tsx` — `function Avatar({ name, size='sm', className })`. Нет в `components/ui/`. |
| **AvatarGroup** | missing | Нет. |
| **ColorSwatch** | partial | `components/catalog/ui/color-swatch.tsx` (есть, но только для каталога). Нет в `components/ui/`. |
| **Ring** | partial | `components/catalog/ui/completeness-ring.tsx` (узко-каталоговый). Нет общего `Ring`. |
| **Tooltip** | partial | `components/catalog/ui/tooltip.tsx` (каталоговский). Нет в `components/ui/`. |
| **Skeleton** | partial | `components/crm/ui/Skeleton.tsx`. Нет в `components/ui/`. |
| **Kbd** | missing | Используется inline в трёх местах (см. секцию 7). Нет компонента. |
| **EmptyState** | partial | `components/catalog/ui/empty-state.tsx`, `components/crm/ui/EmptyState.tsx`. Нет канонического `components/ui/empty-state.tsx`. |

### Сигнатуры существующих primitives (`components/ui/`)

| Файл | Экспорт |
|---|---|
| `button.tsx` | `Button`, `buttonVariants` (cva-based) |
| `calendar.tsx` | `Calendar`, `CalendarDayButton` |
| `checkbox.tsx` | `Checkbox` |
| `command.tsx` | `Command`, `CommandDialog`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandSeparator`, `CommandItem` |
| `dialog.tsx` | `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogClose`, `DialogOverlay`, `DialogContent`, `DialogHeader`, `DialogFooter` |
| `dropdown-menu.tsx` | `DropdownMenu`, `DropdownMenuPortal`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuGroup`, `DropdownMenuLabel`, `DropdownMenuItem`, `DropdownMenuSub` |
| `input-group.tsx` | `InputGroup`, `InputGroupAddon`, `InputGroupButton`, `InputGroupText`, `InputGroupInput` (cva-based) |
| `input.tsx` | `Input` |
| `popover.tsx` | `Popover`, `PopoverTrigger`, `PopoverContent`, `PopoverHeader`, `PopoverTitle`, `PopoverDescription` |
| `separator.tsx` | `Separator` |
| `tabs.tsx` | `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` (re-export base-ui Tabs as shadcn API) |
| `textarea.tsx` | `Textarea` |

### Gap summary

- **Missing (4):** LevelBadge, Tag, Chip, AvatarGroup, Kbd → **5 primitives** нужно создать с нуля.
- **Partial (8):** Badge, StatusBadge, Avatar, ColorSwatch, Ring, Tooltip, Skeleton, EmptyState → существуют в раздробленных местах, надо консолидировать в `components/ui/`.
- **Present** (в `components/ui/`): только Tabs (через shadcn-обёртку). Остальные 12 целевых primitives отсутствуют или раздроблены по `catalog/ui/`, `crm/ui/`, `marketing/`, `agents/`.

---

## 7. Inline `<kbd>` элементы

Найдено **3 вхождения**:

| Файл:строка | Контекст |
|---|---|
| `components/layout/top-bar.tsx:90` | `<kbd className="hidden sm:inline text-[10px] border border-border bg-background rounded px-1 py-0 ml-1 text-text-dim">` |
| `components/catalog/layout/catalog-topbar.tsx:62` | `<kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5 font-mono">` |
| `components/catalog/ui/command-palette.tsx:153` | `<kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5"` |

**Вывод:** три разных inline-стиля для одной и той же визуальной единицы (горячая клавиша). Идеальный кандидат для нового `<Kbd>` primitive в Wave 1.

---

## 8. Extended Wookiee tokens (G5 — где используются)

Поиск `bg-bg-soft|text-text-dim|bg-icon-bar|bg-bg-hover|wk-green|wk-red|wk-yellow|wk-blue|wk-pink`:

Найдено **24 файла**.

| Файл | Вхождения |
|---|---|
| `index.css` | 20 (декларация токенов в @theme/CSS variables) |
| `components/layout/top-bar.tsx` | 5 |
| `components/layout/mobile-menu.tsx` | 3 |
| `components/shared/progress-bar.tsx` | 2 |
| `components/shared/date-range-picker.tsx` | 2 |
| `components/shared/change-indicator.tsx` | 2 |
| `components/marketing/UpdateBar.tsx` | 2 |
| `components/marketing/SelectMenu.tsx` | 2 |
| `components/layout/sub-sidebar.tsx` | 2 |
| `components/layout/sub-sidebar-item.tsx` | 2 |
| `components/community/reviews-status-tabs.tsx` | 2 |
| `components/community/reviews-sort-popover.tsx` | 2 |
| `components/community/reviews-header.tsx` | 2 |
| `components/community/analytics-response-chart.tsx` | 2 |
| `components/catalog/sync-mirror-button.tsx` | 2 |
| `components/agents/tools-table.tsx` | 2 |
| `components/agents/runs-table.tsx` | 2 |
| `components/shared/metric-card.tsx` | 1 |
| `components/layout/theme-toggle.tsx` | 1 |
| `components/layout/mobile-nav.tsx` | 1 |
| `components/layout/icon-bar.tsx` | 1 |
| `components/layout/icon-bar-button.tsx` | 1 |
| `components/community/reviews-filter-popover.tsx` | 1 |
| `components/community/analytics-header.tsx` | 1 |

**Вывод по G5:** extended tokens (`bg-bg-soft`, `text-text-dim`, `bg-icon-bar`, `bg-bg-hover`, `wk-*`) активно используются в Hub-shell (layout/), community/, agents/, shared/, marketing/ — то есть именно в Wave 1 scope. При миграции на DS v2 stone эти токены нужно либо сохранить (если они уже маппятся на stone-палитру через CSS-variables в `index.css`), либо переписать на canonical stone-классы.

---

## Summary

- **Stone-* хардкод: 74 файла / 1464 вхождения**, но **весь** сосредоточен в уже-мигрированных `/catalog/*` и `/marketing/*` (вне Wave 1 scope). Это значит, что Wave 1 целевые разделы (`hub-shell + operations + community + influence + analytics`) — стартуют с чистой палитры.
- **dark: префиксы: 21 вхождение в 12 файлах**, все в Wave 1 scope (shadcn-primitives `components/ui/*`, `agents/`, `community/`). Их нужно вычистить.
- **Inline styles: 74 вхождения в 38 файлах** — почти всё в каталоге, но 8 файлов в Wave 1 scope (community, layout, shared, influence) — потенциальные мини-цели для рефакторинга.
- **CRM Kit: 52 импорта в 21 файле** (21 файл импортирует из `crm/ui/`, 3 файла — из `crm/layout/PageHeader`). Все 13 компонентов CRM kit — кандидаты на промоушн в `components/ui/` (Avatar, Badge, Button, Drawer, EmptyState, FilterPill, Input, PlatformPill, QueryStatusBoundary, Select, Skeleton, Tabs, Textarea + PageHeader в layout).
- **Routes: 38 entries в `router.tsx`** (1 login + 22 catalog + 14 hub-shell + 3 marketing). `design-system-preview-NEW` route — **отсутствует**. Feature flag `featureFlags.marketing` декларирован в `src/lib/feature-flags.ts`, читает `VITE_FEATURE_MARKETING`.
- **Primitives gap: 5 missing (LevelBadge, Tag, Chip, AvatarGroup, Kbd) + 8 partial** (Badge, StatusBadge, Avatar, ColorSwatch, Ring, Tooltip, Skeleton, EmptyState — раздроблены по `catalog/ui/`, `crm/ui/`, `marketing/`, `agents/`). Из 13 целевых ни один не лежит в каноническом `components/ui/` чистым.
- **Inline `<kbd>`: 3 вхождения** — в `top-bar.tsx`, `catalog-topbar.tsx`, `command-palette.tsx`. Чёткий кандидат на `<Kbd>` primitive.
- **Extended tokens (G5): 24 файла** используют `bg-bg-soft / text-text-dim / wk-*` — в основном в Hub-shell. `font-family` для DM Sans + Instrument Serif уже декларирован в `index.css`.

### Ключевые числа для оркестратора

| Метрика | Значение |
|---|---|
| Файлов с `stone-*` хардкодом | 74 (всего 1464 вхождения) |
| Файлов с `dark:` | 12 (21 вхождение) |
| Файлов с inline styles | 38 (74 вхождения) |
| CRM Kit импортов | 52 (21 файл) |
| Routes (entries в router) | 38 |
| Primitives missing | 5 (LevelBadge, Tag, Chip, AvatarGroup, Kbd) |
| Primitives partial | 8 (Badge, StatusBadge, Avatar, ColorSwatch, Ring, Tooltip, Skeleton, EmptyState) |
| Inline `<kbd>` | 3 |
| Файлов с extended tokens | 24 |
| `design-system-preview-NEW` route | отсутствует |
| `featureFlags.marketing` | объявлен в `src/lib/feature-flags.ts` (env: `VITE_FEATURE_MARKETING`) |

---

## Phase 4 — Primitives package: результаты (2026-05-15)

11 primitives созданы + Button расширен. Все в каноническом `src/components/ui/`:

- `badge.tsx` (Task 4.1) — 7 variants × 2 sizes + dot/icon slots
- `status-badge.tsx` (Task 4.2) — 10 статусов на русском (active/draft/review/archived/pending/approved/rejected/in_progress/completed/blocked)
- `level-badge.tsx` (Task 4.3) — 4 уровня (model/variation/artikul/sku), `font-mono`
- `tag.tsx` + `chip.tsx` (Task 4.4) — Tag декоративный, Chip с `onRemove` (lucide X)
- `avatar.tsx` + `avatar-group.tsx` (Task 4.5) — инициалы 2 буквы, `-space-x-2` overlap
- `color-swatch.tsx` + `ring.tsx` (Task 4.6) — SVG progress ring с `strokeDasharray/Offset`
- `tooltip.tsx` (Task 4.7) — на `@radix-ui/react-tooltip` (Provider/Root/Trigger/Content)
- `skeleton.tsx` + `kbd.tsx` + `empty-state.tsx` (Task 4.8) — Kbd поддерживает single + `keys[]` combo
- `button.tsx` extended (Task 4.9) — добавлены variants `success` (emerald-600/white) + `danger-ghost` (red-600 text)

### Unit-tests smoke pass (Task 4.10)

```
Test Files  9 passed (9)
     Tests  21 passed (21)
```

Запуск: `npx vitest run src/components/ui/__tests__/`.

### Bundle delta после Phase 4

| Метрика | Pre-Wave 1 | После Phase 4 | Delta |
|---|---|---|---|
| `du -sk dist/` | 2932 KB | 2772 KB | −160 KB |

Замечание: baseline 2932 KB в секции 0 был зафиксирован до серии оптимизаций в фазах 0-3 (chunking, prune, etc.). Реальный baseline на старте Phase 4 (после Phases 0-3) = 2768 KB. Сама Phase 4 добавила +4 KB к этому промежуточному значению. Бюджет G11 (+250 KB к 2932 KB) → far under threshold.

Build time после Phase 4: 4.67s. Build exit code: 0.
