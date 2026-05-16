# Wookiee Hub · Design System v2 — Wave 1 Foundation

**Дата:** 2026-05-15
**Автор:** Claude (CTO-mode) + Данила (одобрение)
**Статус:** Spec в работе, ожидает review
**Скоуп:** Wave 1 из 5 (Foundation). Wave 2-5 описаны как roadmap (high-level).

---

## 1. Контекст

`hub.os.wookiee.shop` — внутренний инструмент команды (18 человек, бренд женского белья, ~400M ₽/год). Сейчас в нём **три разных визуальных диалекта** одновременно:

1. **Hub default** — oklch + пурпурный primary, dark-first, Inter. Используется в `/operations`, `/community`, `/influence`, `/analytics`, `/agents`, `/login`.
2. **`.catalog-scope`** — stone-палитра в RGB tuples, DM Sans + Instrument Serif. 22 страницы `/catalog/*` (изолированный scope).
3. **`[data-section="marketing"]`** — stone overrides + DM Sans inline. 2 страницы `/marketing/*`.
4. **CRM Kit** — отдельный набор из 13 компонентов в `src/components/crm/ui/*`, используется только в `/influence/*` (52 импорта).

**Задача:** привести Hub к единому визуальному языку **Design System v2** (stone + DM Sans + Instrument Serif + light/dark) на основе эталонных артефактов `wookiee_ds_v2_foundation.jsx` и `wookiee_ds_v2_patterns.jsx`.

**Эталонные документы (источники правды):**
- `DESIGN_SYSTEM.md` — спецификация v2 (палитра, токены, типографика, компоненты, паттерны, антипаттерны, чек-лист)
- `HANDOFF.md` — инструкции для Claude Code
- `BRIEF_hub_redesign.md` — план миграции по 5 волнам
- `wookiee_ds_v2_foundation.jsx` — UX-эталон Atoms/Forms/Data/Charts/Layout/Overlays/Feedback
- `wookiee_ds_v2_patterns.jsx` — UX-эталон Kanban+DnD/Calendar+DnD/Comments/Notifications/Activity/Inbox

---

## 2. Стек проекта (подтверждён аудитом)

- **Build:** Vite 7 + React 19 + React Router 7
- **Styling:** Tailwind CSS v4 (через `@tailwindcss/vite`) с `@theme inline`
- **UI primitives:** shadcn/ui (12 компонентов: Button, Calendar, Checkbox, Command, Dialog, DropdownMenu, InputGroup, Input, Popover, Separator, Tabs, Textarea) + Radix
- **DnD:** `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` (уже стоит)
- **Charts:** `recharts` (уже стоит, используется в `/analytics/rnp-tabs`)
- **State:** Zustand 5 (theme, navigation, integrations, community, operations, agents) с persist в localStorage `wookiee-theme`
- **Auth/DB:** Supabase (OTP login)
- **Toast:** Sonner (уже привязан в `main.tsx`)
- **Forms:** react-hook-form + zod
- **Fonts:** Inter Variable (`@fontsource-variable/inter`)
- **Tests:** Vitest 9 файлов (нет Playwright npm — используем MCP)
- **TypeScript:** strict, paths `@/*` → `./src/*` (config в `tsconfig.temp.json` — историческая особенность, не трогаем)
- **Deploy:** rsync на `/home/danila/projects/wookiee/wookiee-hub/dist/` (через autopull)

---

## 3. Архитектурные решения (CTO-mode, обоснованные)

### 3.1. Token strategy: repaint values, keep names

**Что:** Имена shadcn-переменных (`--background`, `--foreground`, `--card`, `--primary`, `--border`, `--ring`, `--muted-foreground`...) сохраняются. Меняются только **значения** — с oklch-purple на stone-палитру DS v2.

**Почему:** Имена shadcn закрывают ~80% семантики DS v2:
- `bg-card` ≈ DS v2 `bg-surface`
- `bg-background` ≈ DS v2 `bg-page`
- `text-foreground` ≈ DS v2 `text-primary`
- `text-muted-foreground` ≈ DS v2 `text-muted`
- `border-border` ≈ DS v2 `border-default`

Десятки shadcn-компонентов получают новый вид **автоматически** через CSS-cascade без правки кода. Будущие обновления shadcn остаются совместимыми. Минимальный ripple.

**Что добавляется новыми утилитами через `@utility`:** `text-label`, `border-strong` — этих shadcn не покрывает. И только их.

**Конфликт имён в эталоне:** в DS v2 `text-primary` = основной текст. В shadcn `text-primary` = on-primary-button color. **Не ввожу дублирующее имя.** При переписывании primitives с эталона переводим:
- эталон `text-primary` → shadcn `text-foreground`
- эталон `bg-surface` → shadcn `bg-card`
- эталон `bg-page` → shadcn `bg-background`
- эталон `text-secondary` → `text-stone-700 dark:text-stone-300` (или alias через @utility)
- эталон `text-muted` → shadcn `text-muted-foreground`
- эталон `border-default` → `border` (shadcn default)
- эталон `border-strong` → новая утилита

### 3.2. Default theme: light, но respect user preference

DS v2 рекомендует light default. **Не насильно** переключаю существующих пользователей — для них в localStorage `wookiee-theme=dark` остаётся. Новые посетители получают `light` по умолчанию.

### 3.3. Catalog scope: сохраняем в Wave 1

`.catalog-scope` сейчас хардкодит stone-палитру через `--cat-*` CSS-vars (RGB tuples) **без зависимости от Hub-токенов**. Перекраска Hub-токенов **не влияет** на catalog visually. В Wave 1 — не трогаем, только Playwright-QA подтверждает что 22 страницы работают.

В Wave 2 — снимаем `.catalog-scope`, унифицируем токены.

### 3.4. CRM Kit: оставляем изолированным в Wave 1

`src/components/crm/ui/*` (13 компонентов: Button, Input, Drawer, Badge, Avatar, и др.) — отдельная мини-DS. После repaint Hub-токенов CRM Kit автоматически перекрашивается (он использует те же CSS-переменные shadcn внутри). Унификация с shadcn (замена crm/ui/* → shadcn эквиваленты, удаление дублей) — **Wave 5** как отдельный sub-project.

### 3.5. Шрифты

- **Основной (`--font-sans`):** меняем с `Inter Variable` на `DM Sans Variable` (`@fontsource-variable/dm-sans`)
- **Заголовки страниц:** Instrument Serif italic (Google Fonts с preload — уже подключено в `index.css`)
- Inter удаляем после миграции

### 3.6. DnD: `@dnd-kit` (уже стоит)

Не меняем. Эталонные patterns пишутся под `@dnd-kit/core` + `@dnd-kit/sortable`.

### 3.7. QA: через Playwright MCP

Local `playwright` npm не ставим (200MB chromium + сложности CI). Используем встроенный `mcp__plugin_playwright_playwright__*` для прохода routes, screenshots, console-error check.

### 3.8. CI workflow: не в Wave 1

Сейчас `.github/workflows/` для monorepo есть, но он Python-only. Для wookiee-hub CI отсутствует. **Не добавляем в Wave 1** (out of scope). Финальный QA-gate — локальный `npm run build` + tsc.

### 3.9. tsconfig.temp.json

Не переименовываем — это сознательная особенность проекта. Build через Vite работает.

---

## 4. Архитектура оркестрации

**Главный оркестратор** = chat-сессия Claude. Координирует под-агентов, делает атомарные коммиты, передаёт следующему агенту.

**Под-агенты (8):**

| # | Агент | Цель | Зависит от | Параллелит с |
|---|---|---|---|---|
| 1 | **audit-agent** | Полная инвентаризация: хардкод stone-* по файлам, dark: префиксы, неиспользуемые tokens, использование shadcn vs custom. Output: `WAVE1_AUDIT.md`. | — | — |
| 2 | **tokens-agent** | Repaint `src/index.css` (значения OKLCH → stone-палитра в обеих темах). Добавляет утилиты `text-label`, `border-strong`. | 1 | 3 |
| 3 | **fonts-agent** | `npm install @fontsource-variable/dm-sans` + import в index.css. Меняет `--font-sans`. Подключает Instrument Serif preload. | 1 | 2 |
| 4 | **primitives-agent** | Расширяет shadcn-набор до эталона: добавляет `Badge`, `StatusBadge`, `LevelBadge`, `Tag`, `Chip`, `Avatar` (+`AvatarGroup`), `ColorSwatch`, `Ring`, `Tooltip` (на radix), `Skeleton`, `Kbd`, `EmptyState`. Расширяет `Button` вариантами `success`, `danger-ghost`. | 2, 3 | 5 |
| 5 | **preview-route-agent** | Создаёт `/design-system-preview` (testbed страница, скрыта из nav). Все primitives, форм-поля, layout-секции в light+dark. | 2, 3 | 4 |
| 6 | **layout-shell-agent** | Repaint `AppShell`, `IconBar`, `SubSidebar`, `TopBar`, `Logo`, `MobileNav`, `MobileMenu`. Создаёт `PageHeader` компонент (kicker + Instrument Serif title + breadcrumbs + actions + status). | 4 | — |
| 7 | **pages-migration-agent ×3** | Параллельно: Group A: `/operations/*` + `/agents/*` + `/login`. Group B: `/community/*` (gradients check). Group C: `/influence/*` + `/analytics/rnp`. Точечная замена хардкода stone-* → shadcn utility names. | 6 | — |
| 8 | **qa-playwright-agent** | Через Playwright MCP: проходит ВСЕ routes (catalog 22 + marketing 2 + Hub-shell ~12 + design-system-preview = ~37), screenshots в light+dark, console errors check, visual diff vs эталона. Output: `WAVE1_QA_REPORT.md`. | 5, 6, 7 | — |

---

## 5. Фазы Wave 1 (последовательно, атомарные коммиты)

### Phase 1 · Audit & branch setup
- Ветка `feat/ds-v2-wave-1` создана от `main` (✅ создана 2026-05-15)
- Spec этот файл — первый коммит на ветке
- Запустить audit-agent → `WAVE1_AUDIT.md`
- Commit: `docs(ds-v2): wave 1 codebase audit`

### Phase 2 · Tokens & fonts
- tokens-agent: `src/index.css` — все значения OKLCH в `:root` и `.dark` пересчитаны под stone-палитру. Добавлены `@utility text-label`, `@utility border-strong`.
- fonts-agent: `npm install @fontsource-variable/dm-sans`, import в `index.css`, `--font-sans: 'DM Sans Variable'`.
- Build check: `npm run build` локально
- Commit: `feat(ds-v2): repaint tokens to stone + DM Sans`

### Phase 3 · Primitives package
- primitives-agent создаёт в `src/components/ui/`:
  - `badge.tsx` (variants: emerald/blue/amber/red/purple/teal/gray + dot/icon/compact)
  - `status-badge.tsx` (через STATUS_MAP)
  - `level-badge.tsx` (model/variation/artikul/sku)
  - `tag.tsx`, `chip.tsx`
  - `avatar.tsx` + `avatar-group.tsx`
  - `color-swatch.tsx`
  - `ring.tsx`
  - `tooltip.tsx` (на @radix-ui/react-tooltip — уже стоит)
  - `skeleton.tsx`
  - `kbd.tsx`
  - `empty-state.tsx`
- Расширяется `button.tsx` вариантами `success`, `danger-ghost`
- Существующий `shared/progress-bar.tsx` обновляется под эталон (с label, compact, color variants)
- Commit: `feat(ds-v2): primitives package`

### Phase 4 · Design System preview
- preview-route-agent создаёт `src/pages/design-system-preview/index.tsx`
- Route в `router.tsx` (под AppShell, не в navigation menu)
- Все primitives + форм-поля + layout-секции, переключатель темы
- Commit: `feat(ds-v2): /design-system-preview route`

### Phase 5 · Layout shell repaint
- layout-shell-agent: `AppShell`, `IconBar`, `IconBarButton`, `SubSidebar`, `SubSidebarItem`, `TopBar`, `Logo`, `MobileNav`, `MobileMenu`, `UserMenu`, `ThemeToggle` — repaint через shadcn utility names. CRM-специфичный `PageHeader` (в `components/crm/layout/`) не трогаем.
- Создаётся новый `src/components/layout/page-header.tsx` для Hub-страниц (kicker + Instrument Serif title + breadcrumbs + actions + status)
- Commit: `feat(ds-v2): repaint AppShell + add PageHeader`

### Phase 6 · Pages migration (3 параллельных под-агента)
- **Group A:** `/operations/{tools,activity,health}` + `/agents/{runs,skills}` + `/login` — точечная замена hardcoded `text-stone-*`/`bg-stone-*` → semantic shadcn utilities
- **Group B:** `/community/{reviews,questions,answers,analytics}` + связанные компоненты — gradients проверка/упрощение, dark: префиксы → utility classes
- **Group C:** `/influence/{bloggers,integrations,calendar}` + `/analytics/rnp` — CRM Kit не трогаем, только wrappers и not-CRM-Kit части страниц. Analytics charts получают новые `--chart-1..5` (Wave 3 переколесит формы)
- Каждая group → отдельный коммит:
  - `feat(ds-v2): migrate pages (operations+agents)`
  - `feat(ds-v2): migrate pages (community)`
  - `feat(ds-v2): migrate pages (influence+analytics)`

### Phase 7 · QA Playwright
- qa-playwright-agent: запуск `npm run dev`, проход routes через MCP, screenshots в light+dark, console errors, visual diff
- Routes (~37): catalog 22, marketing 2, operations 3, agents 2, community 4, influence 3, analytics 1, login 1, design-system-preview 1
- Output: `WAVE1_QA_REPORT.md` (что проверено, что найдено, скриншоты)
- **Blocker дефекты** (фикс в Wave 1 обязательно): console errors > 0 на любой странице, theme switch ломается, build break, primitive не рендерится в одной из тем, page header не отображается с Instrument Serif
- **Non-blocker дефекты** (отдельный issue в backlog Wave 2+): visual nit < 4px misalignment, gradient mismatch в community (если не критично), CRM Kit стиль не точно совпадает с эталоном (это ожидаемо до Wave 5)
- Commit: `chore(ds-v2): wave 1 QA report`

### Phase 8 · PR open
- Push ветка `feat/ds-v2-wave-1` на origin
- `gh pr create` с описанием:
  - Список изменений
  - Acceptance checklist
  - Скриншоты ключевых routes (light + dark)
  - Attached `WAVE1_AUDIT.md` + `WAVE1_QA_REPORT.md`
- **НЕ auto-merge** — Данила ревьюит и мерджит сам

---

## 6. Acceptance Wave 1

1. **Console errors = 0** на всех 37 routes в обеих темах (Playwright измерение через `page.on('console')`)
2. **Каталог открывается** — все 22 страницы `/catalog/*` рендерятся (DOM есть, no white screen of death)
3. **Маркетинг открывается** — `/marketing/promo-codes`, `/marketing/search-queries` рендерятся
4. **Шрифты** — `getComputedStyle(document.body).fontFamily` содержит `DM Sans`, на `<h1>` через `<PageHeader>` — содержит `Instrument Serif`
5. **Theme switch** — клик по toggle переключает `<html class>` между `""` и `"dark"`, localStorage `wookiee-theme` обновляется, CSS-переменные cascade
6. **Build clean** — `npm run build` exit code 0, нет TS errors в production tsc
7. **Preview route** — `/design-system-preview` открывается, все 11 новых primitives + расширенный Button присутствуют в DOM в light и dark
8. **Primitives API соответствует эталону** — каждый компонент в `src/components/ui/{badge,status-badge,level-badge,tag,chip,avatar,color-swatch,ring,tooltip,skeleton,kbd,empty-state}.tsx` принимает props идентичные эталонной сигнатуре в `wookiee_ds_v2_foundation.jsx`
9. **PR open** — `feat/ds-v2-wave-1` open без auto-merge, описание соответствует шаблону (changelog + screenshots + acceptance checklist + 2 attached reports)
10. **QA report attached** — `WAVE1_QA_REPORT.md` + `WAVE1_AUDIT.md` приложены к PR

---

## 7. Risk register

| # | Риск | Mitigation |
|---|---|---|
| R1 | Catalog/marketing хардкодят stone (~1347 классов) — могут зависеть от Hub-token cascade | Аудит подтвердил: они хардкодят stone-цвета напрямую, **не** через CSS vars Hub. Repaint Hub-токенов не затрагивает их. Playwright QA подтверждает |
| R2 | CRM Kit (crm/ui/*) после repaint визуально не дотягивает до эталона | Ожидаемо — унификация в Wave 5. В Wave 1 — только «не сломалось» |
| R3 | Конфликт shadcn `text-primary` vs DS v2 `text-primary` | Используем только shadcn-имена в новом коде. Эталонный `text-primary` → shadcn `text-foreground` при переписывании |
| R4 | Community gradients конфликтуют с новой палитрой | Group B handles это точечно — gradients либо упрощаются, либо переводятся на новые brand-токены |
| R5 | Build broken после migration | Atomic commits, локальный `npm run build` после каждого. Если break — rollback + investigate |
| R6 | Playwright MCP не справляется с 37 routes за один проход | Бьём QA на 3 партии: catalog (22), marketing+hub-shell (~13), preview + diff (2). Если падает дальше — split |
| R7 | Calendar в `/influence/*` плохо смотрится после repaint (только month, недоразвит) | Wave 5 расширит до Month+Week+DnD. В Wave 1 — отмечается в QA report, не блокер |
| R8 | Inter Variable удаление ломает существующие inline styles | grep + замена inline `font-family: 'Inter'` → use `var(--font-sans)` или удаление. Audit-agent ловит все места |

---

## 8. Out of scope для Wave 1

- Унификация CRM Kit с shadcn (Wave 5)
- Расширение Calendar до Month+Week+DnD (Wave 5)
- Charts patterns (chartTokens, makeRichTooltip, MultiSeriesLine и т.д.) (Wave 3)
- GroupedTable (Wave 4)
- Realtime через Supabase channels (Post Wave 5)
- CI workflow для wookiee-hub (отдельный sub-project)
- Local Playwright npm install (используем MCP)
- Переименование `tsconfig.temp.json`
- Mobile adaptations (не покрыто эталоном)

---

## 9. ROADMAP Wave 2-5 (high-level)

### Wave 2 — Catalog finishing (2-3 нед)
- Снять `.catalog-scope` cascade
- Унифицировать catalog токены с Hub
- Внедрить CommandPalette globally (cmdk + ⌘K)
- Toast context-provider поверх sonner
- 22 страницы catalog работают на shadcn-tокенах в обеих темах

### Wave 3 — Charts & Analytics (2 нед)
- Создать `src/lib/chart-tokens.ts` (light + dark sets)
- `makeRichTooltip(tk, opts)` helper
- Новые компоненты в `src/components/charts/`: MultiSeriesLine, StackedBar, ComboChart, Donut (с central value), Gauge, Funnel (custom div-based), CalendarHeatmap, Sparkline
- Миграция `/analytics/rnp/*` (6 tabs) под новые компоненты
- Context: P&L разрез, channels stacked bar, combo bar+line

### Wave 4 — Operations & Production (2 нед)
- GroupedTable (pivot-style) компонент в `src/components/ui/data/`
- Применить в новой странице «Планирование поставок»
- OrderHeaderCard + TargetDaysSlider
- Cover-days color indicators (red/amber/emerald/blue)

### Wave 5 — Content & Patterns (2-3 нед)
- CRM Kit unification: заменить crm/ui/* → shadcn эквиваленты, удалить дубли (52 импорта переписать)
- Расширить `/influence/calendar` до Month+Week+DnD событий
- Detail Drawer для Kanban карточки (560px полный layout: header + properties + description + subtasks + attachments + comments + activity)
- Новые pattern-компоненты: CommentsThread, NotificationsPanel (slide-out), ActivityFeed (Linear-style), Inbox

### Post Wave 5 — Realtime (отдельный sub-project)
- Supabase realtime channels для Comments, Activity, Notifications
- Multi-user collab в Kanban (presence + concurrent DnD)
- Bell badge с unread count

---

## 10. Open questions

Ни одного — все технические развилки приняты CTO-mode. Жду review этого spec; если возражений нет — переходим к writing-plans skill.

---

*Spec ver 1.0 · 2026-05-15 · Wookiee Hub DS v2 · Wave 1 Foundation*
