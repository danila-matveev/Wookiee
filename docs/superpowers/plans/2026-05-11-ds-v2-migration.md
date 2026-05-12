# DS v2 Migration — Master Spec (v0.2 final)

> **График:** 2-3 дня (вариант B принят).
> Day 1 = Wave 1 (Foundation) + Wave 2 (Catalog).
> Day 2 = Wave 3 (Marketing + Operations + Community + Analytics).
> Day 3 = Wave 4 (Influence) + Финал.
> **Метод:** параллельные субагенты по волнам.
> **Источник правды:** `docs/handoff/2026-05-design-system/{BRIEF_hub_redesign,DESIGN_SYSTEM,HANDOFF}.md` + два `.jsx` эталона.

---

## 1. Цель и non-goals

### Цель
Перевести `wookiee-hub` (27 экранов + login) на **единый визуальный язык** Design System v2 — stone-палитра, DM Sans + Instrument Serif, семантические токены, light/dark через `data-theme` атрибут.

### Non-goals (запрещено)
- ❌ **Новый функционал.** Канбан / Календарь / Marketing / Activity уже есть в коде — только переоформляем.
- ❌ **Calendar event DnD.** В текущем коде нет — это была бы новая фича. Не делаем.
- ❌ **Realtime через Supabase channels.**
- ❌ **SQL миграции.**
- ❌ **Mobile-адаптации** сверх того что уже есть.
- ❌ **Rich-text editor** в `/community/answers` — оставляем textarea.
- ❌ **Onboarding / welcome-туры.**
- ❌ **Откат изменений** в `/operations/activity` — только лог, без revert UI.

---

## 2. Бизнес-правила (locked-in)

| # | Правило |
|---|---------|
| BR-1 | **Включая marketing** — раздел `/marketing/{promo-codes,search-queries}` уже в коде (commit `4968d53`), редизайним наравне с остальным. |
| BR-2 | **Пользователи — без ролей.** Все могут всё. |
| BR-3 | **Permissions pattern (на будущее):** кнопки без прав НЕ скрываем, мьютим (`disabled` + `cursor-not-allowed` + tooltip «Нет прав, обратитесь к руководителю»). Реализуется через единый `<PermissionGate>` компонент в Wave 1. Сейчас не используется в JSX, но в DS лежит. |
| BR-4 | **Голый текст в ответах.** `/community/answers` — `textarea`, никакого rich-text. |
| BR-5 | **Лог изменений сохраняем** (`/operations/activity` уже есть, редизайним). Откат — НЕ делаем. |
| BR-6 | **Главная цель — дизайн.** Все рабочие процессы трогаем только в части UI. |
| BR-7 | **Срок 2-3 дня.** Параллельные субагенты по волнам. |

---

## 3. Технические решения (финал после ревью архитектора)

### TR-1. CSS-токены и темизация
- **`.dark` class → `[data-theme='dark']`** на `<html>`. Семантические переменные `--surface`, `--text-primary`, `--border-default`, etc.
- **`tokens.css`** — отдельный файл `src/styles/tokens.css`, импортируется первой строкой в `index.css` после `@import "tailwindcss"`.
- **`@theme` блок** — содержит `--color-*` mappings, доступные как `bg-surface`, `text-primary` etc через Tailwind v4 `@theme inline`.
- **CRM compat aliases в `index.css:247-261`** — НЕ удаляем сейчас, нужны пока живёт `components/crm/ui/*` (используется и Marketing, и Influence). Удаляем в Финале после Wave 4.

### TR-2. ThemeStore (Wave 0)
- **Default тема:** меняем `theme: "dark"` → `"light"` в `src/stores/theme.ts:13` (одна строка).
- **AppShell** (`src/components/layout/app-shell.tsx:22-24`): `classList.toggle("dark", ...)` → `document.documentElement.setAttribute("data-theme", theme)`.
- **Anti-FOUC inline-script** в `index.html` до `<script type="module">`:
  ```html
  <script>
    try {
      var raw = localStorage.getItem('wookiee-theme');
      var theme = raw ? (JSON.parse(raw).state || {}).theme : null;
      document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : 'light');
    } catch (e) {
      document.documentElement.setAttribute('data-theme', 'light');
    }
  </script>
  ```
- **Существующие пользователи** с `wookiee-theme.state.theme === 'dark'` сохраняют dark — никакой отдельной миграции данных не нужно, Zustand persist уже хранит.

### TR-3. Шрифты — НЕ self-host
- **Оставляем Google Fonts** `@import` в `src/index.css:5` (уже работает): DM Sans 400/500/600 + italic + Instrument Serif regular+italic.
- **Удаляем `Inter Variable`:** `import "@fontsource-variable/inter"` из `index.css:4` + пакет `@fontsource-variable/inter` из `package.json`.
- **`--font-sans`** в `@theme` меняется на DM Sans.
- Self-host — отдельный пост-релизный тикет «privacy/perf».

### TR-4. Структура DS v2
- **Путь:** `wookiee-hub/src/components/ui-v2/{primitives,forms,data,charts,layout,overlays,feedback,patterns}/`.
- **Параллельное сосуществование** со старым `src/components/ui/*` до Финала. В Финале — `ui/` удаляется, `ui-v2/` → `ui/`.
- **API compatibility:** новые primitives имеют такие же сигнатуры как `components/catalog/ui/*`, чтобы Wave 2 был массовым find&replace.

### TR-5. `.catalog-scope` — удаляем в конце Wave 2
- В Wave 1 НЕ трогаем. stone-50 из DS v2 совпадает по цвету со scope — мирно сосуществуют.
- Удаляется единым коммитом после миграции 16 catalog-экранов (внутри Wave 2).

### TR-6. DnD
- **`@dnd-kit/core` + `@dnd-kit/sortable`** уже в `package.json`, **Kanban в `/influence/integrations` уже на @dnd-kit** — только реcкин карточек/колонок.
- **Calendar event DnD — НЕ делаем** (нет в текущем коде, это новая фича).

### TR-7. Charts
- **Recharts остаётся.**
- **`chartTokens(theme)` хук** возвращает палитру под current theme.
- **`makeRichTooltip(tk, opts)` helper** — портируем из `wookiee_ds_v2_foundation.jsx`.
- **`key={theme}` на чартах** — иначе Recharts кеширует цвета и не перерисует при смене темы. Acceptance HANDOFF: «графики реагируют на смену темы без перезагрузки».

### TR-8. Branch model
- **Одна long-lived ветка** `feat/ds-v2-migration` от main.
- **Атомарные коммиты** на каждый wave-task. Финальный PR в main.

### TR-9. Verification gate
- После каждой волны — `gsd-verifier` с goal-backward analysis.
- Финальный smoke в браузере через Playwright (`/login → /catalog/matrix → /marketing/promo-codes → /influence/integrations → /analytics/rnp` в обеих темах).

### TR-10. Запреты для субагентов
- **`router.tsx` НИКТО кроме оркестратора (меня) не трогает.** Если субагент добавляет роут — пишет в общий контракт, я добавляю.
- **`tokens.css` / `index.css`** в Wave 2+ — read-only. Если нужна семантика — пишет ТЗ оркестратору.
- **`ui-v2/`** в Wave 2+ — read-only. Если нужен новый примитив — пишет ТЗ.
- **Запреты на хардкод:** никаких `dark:bg-*`, `bg-stone-*`, `text-purple-*`, `bg-card`, `bg-background`, `text-foreground` в новых компонентах. Только семантические утилиты.

### TR-11. PermissionGate (BR-3)
Один компонент в `ui-v2/primitives/`:
```tsx
<PermissionGate allowed={canEdit} reason="Нет прав, обратитесь к руководителю">
  <Button>Сохранить</Button>
</PermissionGate>
```
Клонирует child, добавляет `disabled`, `aria-disabled`, `cursor-not-allowed`, оборачивает в Tooltip.

---

## 4. Структура папок (target)

```
wookiee-hub/
├── index.html                       # + anti-FOUC inline-script
├── src/
│   ├── styles/
│   │   └── tokens.css               # @theme + :root + [data-theme=dark]
│   ├── index.css                    # @import "tailwindcss" + @import "./styles/tokens.css" + @layer base; убран Inter
│   ├── stores/theme.ts              # default=light, data-theme attribute
│   ├── components/
│   │   ├── ui-v2/                   # DS v2 (new)
│   │   │   ├── primitives/          # +PermissionGate
│   │   │   ├── forms/
│   │   │   ├── data/                # DataTable, GroupedTable, BulkActionsBar, FilterChips, Pagination
│   │   │   ├── charts/              # chartTokens, makeRichTooltip, MultiSeriesLine, StackedBar, Donut, Funnel, Sparkline
│   │   │   ├── layout/
│   │   │   ├── overlays/
│   │   │   ├── feedback/
│   │   │   └── patterns/            # (Wave 4 only)
│   │   ├── ui/                      # → удалить в Финале
│   │   ├── crm/                     # → удалить в Финале
│   │   └── layout/                  # обновляется в Wave 0/1
│   └── pages/
│       └── design-system-preview/   # (Wave 1.T6)
```

---

## 5. План волн

### Wave 0 — Theme migration + orphan cleanup (~45 мин, **делаю сам**)
1. Создать ветку `feat/ds-v2-migration` от main.
2. Удалить orphan-код:
   - `src/pages/agents/`
   - `src/components/agents/*`
   - `src/components/shared/{change-indicator,progress-bar}.tsx` (grep на использование).
3. `src/stores/theme.ts:13` → `theme: "light"`.
4. `src/components/layout/app-shell.tsx:22-24` → `setAttribute("data-theme", ...)`.
5. `index.html` → anti-FOUC inline-script.
6. Smoke: `npm run dev`, проверить что Hub стартует в light, переключение работает.

**Acceptance Wave 0:**
- [ ] Ветка `feat/ds-v2-migration` живёт.
- [ ] Hub стартует в light для нового юзера; пользователь с `wookiee-theme.state.theme=dark` остаётся в dark.
- [ ] Нет FOUC при reload.
- [ ] Orphan-код удалён, `npm run build` без ошибок.

### Wave 1 — Foundation (~8-10 ч, Day 1)

**Sequential первый шаг (делаю сам, ~30 мин):**

- **W1.T1** — `src/styles/tokens.css`: семантические переменные + `@theme inline` маппинг + `@utility`-обёртки. Импорт из `index.css`. Удаление Inter из `index.css`. Обновление `--font-sans` на DM Sans.

**Параллельные субагенты (4 одновременно, после W1.T1):**

| W1.T | Субагент | Файлы | Запрещено |
|------|----------|-------|-----------|
| W1.T2 | **Primitives** | `src/components/ui-v2/primitives/*` (Button, IconButton, Badge, Tag, StatusBadge, LevelBadge, Chip, Avatar, AvatarGroup, ColorSwatch, ProgressBar, Ring, Tooltip, Skeleton, Kbd) + `index.ts` + **PermissionGate** | трогать `ui/*`, `tokens.css`, `router.tsx`, другие папки `ui-v2/*` |
| W1.T3 | **Forms** | `src/components/ui-v2/forms/*` (FieldWrap, TextField, NumberField, SelectField, MultiSelectField, TextareaField, DatePicker, Combobox, FileUpload) + `index.ts` | то же |
| W1.T4 | **Layout** | `src/components/ui-v2/layout/*` (Sidebar, TopBar, PageHeader, Tabs x3, Breadcrumbs, Stepper) + `index.ts` | то же |
| W1.T5 | **Overlays + Feedback** | `src/components/ui-v2/overlays/*` (Modal, Drawer, Popover, DropdownMenu, ContextMenu, CommandPalette) + `src/components/ui-v2/feedback/*` (Toast, Alert, EmptyState) + `index.ts`-ы | то же |

**Sequential после параллельных (делаю сам, ~1-1.5 ч):**

- **W1.T6** — `/login` reskin на DS v2 + `/design-system-preview` стенд: показывает все примитивы/формы/layout/overlays/feedback в обеих темах. Канарейка.

**Acceptance Wave 1:**
- [ ] `/login` рендерится корректно в light и dark.
- [ ] `/design-system-preview` показывает все 30+ компонентов в обеих темах.
- [ ] `npm run typecheck` + `npm run build` — без ошибок.
- [ ] Никаких `dark:bg-*` / `bg-stone-*` / `bg-card` в новых файлах `ui-v2/`.

### Wave 2 — Catalog reskin (~3-4 ч, Day 1 вечер)

**4 параллельных субагента:**

| W2.T | Субагент | Экраны |
|------|----------|--------|
| W2.T1 | **Catalog главные** | `/catalog/matrix`, `/catalog/colors`, `/catalog/artikuly`, `/catalog/tovary` |
| W2.T2 | **Catalog вторичные** | `/catalog/skleyki`, `/catalog/semeystva-cvetov`, `/catalog/upakovki`, `/catalog/kanaly-prodazh`, `/catalog/sertifikaty` |
| W2.T3 | **Catalog справочники A** | `/catalog/references/{kategorii,kollekcii,fabriki}` |
| W2.T4 | **Catalog справочники B + demo** | `/catalog/references/{importery,razmery,statusy}` + `/catalog/__demo__` |

**Sequential после параллельных (делаю сам, ~15 мин):**

- **W2.T5** — удалить `.catalog-scope` обёртку: `CatalogLayout` (убрать `className` + inline-style) + блок `index.css:285-316`.

**Acceptance Wave 2:**
- [ ] Все 16 catalog-экранов используют только семантические токены DS v2.
- [ ] `.catalog-scope` удалён.
- [ ] `/catalog/matrix → ModelCardModal → SKU` работает в обеих темах.

### Wave 3 — Marketing + Operations + Community + Analytics reskin (Day 2, ~6-7 ч)

**Wave 3a (sequential, делает 1 субагент или я, ~4 ч):**
Создаёт всё «горизонтальное», от чего зависят все pages:
- `ui-v2/data/{DataTable, FilterChips, BulkActionsBar, Pagination, GroupedTable}`
- `ui-v2/overlays/Toast` (если ещё не сделан в Wave 1)
- `ui-v2/charts/{chartTokens, makeRichTooltip, MultiSeriesLine, StackedBar, ComboChart, Donut, Funnel, Sparkline, CalendarHeatmap}`

**Wave 3b (4 параллельных субагента, ~3 ч):**

| W3.T | Субагент | Экраны | Файлы read-only |
|------|----------|--------|-----------------|
| W3b.T1 | **Marketing** | `/marketing/{promo-codes,search-queries}` | `ui-v2/*` |
| W3b.T2 | **Operations** | `/operations/{tools,activity,health}` (activity.tsx 608 строк — будет дольше) | `ui-v2/*` |
| W3b.T3 | **Community** | `/community/{reviews,questions,answers,analytics}` | `ui-v2/*` |
| W3b.T4 | **Analytics** | `/analytics/rnp` | `ui-v2/*` |

**Запреты во всех Wave 3 субагентах:** `tokens.css`, `ui-v2/*` write, `router.tsx`. Если нужен новый примитив — пишет ТЗ оркестратору.

### Wave 4 — Influence reskin (Day 3, ~5-6 ч)

**Wave 4a (sequential, 1 субагент, ~2 ч):**
- `ui-v2/patterns/{Kanban, CommentsThread, NotificationsPanel, ActivityFeed, Inbox}` (Calendar — позже, в Wave 4b сам)
- `IntegrationEditDrawer.tsx` (908 строк) — один субагент только на него.

**Wave 4b (3 параллельных + Calendar отдельно, ~3 ч):**

| W4.T | Субагент | Файлы |
|------|----------|-------|
| W4b.T1 | **Bloggers** | `src/pages/influence/bloggers/*` |
| W4b.T2 | **Integrations** (Kanban-страница, без IntegrationEditDrawer — он в W4a) | `src/pages/influence/integrations/*` кроме EditDrawer |
| W4b.T3 | **Calendar** (только реcкин month-view, без DnD) | `src/pages/influence/calendar/*` |

### Финал — Cleanup + smoke (~1.5 ч)

| F.T | Задача |
|-----|--------|
| F.T1 | Удалить `src/components/crm/*` + CRM compat aliases из `tokens.css` |
| F.T2 | Удалить `src/components/ui/*` shadcn-обёртки (после grep на использование) |
| F.T3 | Переименовать `ui-v2/` → `ui/` (mass find&replace импортов) |
| F.T4 | Удалить `@fontsource-variable/inter` из `package.json` + `npm install` |
| F.T5 | `npm run typecheck` + `npm run build` + `npm test` |
| F.T6 | Playwright smoke: `/login → /catalog/matrix → /marketing/promo-codes → /operations/activity → /influence/integrations → /analytics/rnp` × light/dark |
| F.T7 | `gsd-verifier`: goal-backward analysis по acceptance этого спека |
| F.T8 | PR `feat/ds-v2-migration` → main |

---

## 6. Subagent dispatch protocol

### Каждому субагенту даём:
1. **Контекст**: ссылка на этот спек + ссылка на DS v2 хендоффы + ссылка на UI_AUDIT.
2. **Чёткий scope**: какие файлы создаёт, какие read-only, какие НЕ трогает.
3. **Acceptance**: проверочные пункты.
4. **API contract**: примерные сигнатуры компонентов, чтобы между ними была совместимость.

### Antifragility
- Если субагент возвращает «не удалось» — повторный запуск с более узким scope.
- Если verifier режектит — точечный fix-агент, не повторный полный wave.
- Если merge-конфликт между параллельными агентами — переписываю задачу с более узким file scope.

---

## 7. Risks + rollback

| Risk | Mitigation |
|------|-----------|
| FOUC при первом заходе | Anti-FOUC inline-script (Wave 0). |
| Существующие пользователи (default dark) видят light | localStorage уже хранит — никакой миграции данных, только default change. |
| 4 субагента Wave 3b изобретают свои DataTable | Wave 3a sequential делает все shared первым шагом. |
| Recharts не реагирует на смену темы | `key={theme}` на всех графиках. |
| `IntegrationEditDrawer.tsx` 908 строк ломается | Один опытный субагент только на него, smoke в браузере. |
| Удаление `Inter Variable` пакета ломает build | Удаление пакета — в Финале (F.T4), не в Wave 1. В Wave 1 только убираем `@import`. |
| `router.tsx` конфликты между субагентами | Никто не пишет в router. Только я, единым коммитом в конце волны. |
| `.catalog-scope` удаление раньше Wave 2 | Удаляется только после миграции последнего catalog-экрана. |

### Rollback
- Каждая волна — серия атомарных коммитов.
- Если Wave N ломает — `git revert` от последнего тэга волны.
- Перед merge в main — обязательный full smoke на staging build.

---

## 8. Quick wins (V1-V6 из ревью архитектора)

- ✅ **V1.** `VITE_FEATURE_MARKETING` — рассмотреть отключение marketing на Wave 3, если останется без времени. Дефолт: оставляем включённым.
- ✅ **V2.** API compatibility primitives ↔ `components/catalog/ui/*` — учтено в TR-4.
- ✅ **V3.** Orphan-код снести в Wave 0 — добавлено.
- ✅ **V4.** `/design-system-preview` — первой задачей после tokens.css в Wave 1.T6.
- ⏸️ **V5.** ESLint правило против старых токенов — отложить, ручной grep-check после Wave 1 достаточен.
- ✅ **V6.** `<PermissionGate>` обёртка — добавлен в primitives Wave 1.T2.

---

## 9. Ссылки

- Эталоны: `docs/handoff/2026-05-design-system/{BRIEF_hub_redesign,DESIGN_SYSTEM,HANDOFF}.md` + `wookiee_ds_v2_foundation.jsx` + `wookiee_ds_v2_patterns.jsx`
- Audit: `wookiee-hub/docs/UI_AUDIT.md`
- Память проекта: `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/MEMORY.md`

---

*Версия: v0.2 final · 2026-05-12 · после ревью архитектора*
