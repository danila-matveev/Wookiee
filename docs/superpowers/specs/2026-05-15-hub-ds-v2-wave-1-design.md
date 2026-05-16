# Wookiee Hub · Design System v2 — Wave 1 Foundation

**Дата:** 2026-05-15
**Автор:** Claude (CTO-mode) + Данила (одобрение)
**Статус:** Spec v2 — после второй верификации, готов к review
**Скоуп:** Wave 1 из 5 (Foundation). Wave 2-5 описаны как roadmap (high-level).

---

## 0. Что изменилось в v2

Вторая верификация кодовой базы (router, layout, stores, страницы) вскрыла **13 пробелов** в spec v1. v2 их закрывает:

| # | Пробел v1 | Фикс v2 |
|---|---|---|
| G1 | Spec упоминал `/agents/*` миграцию, но в `router.tsx` нет таких routes (страницы есть, в router не подключены) | `/agents/*` → out of scope Wave 1 |
| G2 | Default theme в `stores/theme.ts` — `dark`. DS v2 требует light default | Меняем default на `light`, существующая persisted-сессия не трогается |
| G3 | `/login` лежит вне `AppShell` — там useEffect для синхронизации `html.dark` не работает. На login FOWT гарантирован | Theme sync (читает store + ставит `html.dark`) переносим в `main.tsx` — выполняется до render любой страницы |
| G4 | `<Toaster />` в `main.tsx` без `theme` prop — в light выглядит как в dark | Добавляем `theme={theme}` через подписку на store |
| G5 | Hub использует extended токены `bg-bg-soft`, `text-text-dim`, `bg-icon-bar`, `bg-bg-hover`, `wk-green/red/yellow/blue/pink` — v1 их не упомянул | Явная карта Wookiee-extended → DS v2 значений; пересчитать в обеих темах |
| G6 | В `components/crm/layout/PageHeader.tsx` уже существует CRM-вариант, используется в `/influence/*` | Не трогаем CRM PageHeader. Создаём отдельный `components/layout/page-header.tsx` для Hub-страниц |
| G7 | `/login` использует чистый inline HTML form (без shadcn primitives) | Phase 6 включает миграцию login на `<Input>`, `<Button>` |
| G8 | `/community/*` страницы состоят из собственных компонентов (`ReviewsHeader`, `ReviewListItem`, `ReviewDetail`, и т.д.) — миграция должна рекурсивно зайти в эти под-компоненты | Group B расширена: миграция включает `src/components/community/*` |
| G9 | FOWT prevention отсутствует — переключение `html.dark` через React useEffect происходит **после** первого paint | Inline `<script>` в `index.html` ставит `html.dark` ДО монтирования React |
| G10 | В `package.json` нет `tsc` script. Acceptance "TS errors = 0" непроверяемо | Используем `npx tsc --noEmit` как acceptance команду; добавляем `typecheck` script |
| G11 | Acceptance "Build clean" не специфицирует bundle size — миграция может раздуть бандл | Добавляем acceptance: bundle размер `dist/` не растёт > +250 KB gzipped |
| G12 | `top-bar.tsx` использует inline `<kbd>` element — после ввода Kbd primitive он должен замениться | Phase 5 (layout-shell-agent) явно включает замену inline `<kbd>` → `<Kbd>` в `top-bar.tsx` |
| G13 | QA через Playwright MCP требует dev-server background | Phase 7 явно: `npm run dev` в background перед прохождением routes |

---

## 1. Контекст

`hub.os.wookiee.shop` — внутренний инструмент команды (18 человек, бренд женского белья, ~400M ₽/год). Сейчас в нём **три разных визуальных диалекта** одновременно:

1. **Hub default** — oklch + пурпурный primary, dark-first, Inter. Используется в `/operations`, `/community`, `/influence`, `/analytics`, `/login`.
2. **`.catalog-scope`** — stone-палитра в RGB tuples, DM Sans + Instrument Serif. 22 страницы `/catalog/*` (изолированный scope).
3. **`[data-section="marketing"]`** — stone overrides + DM Sans inline. 2 страницы `/marketing/*`.
4. **CRM Kit** — отдельный набор из 13 компонентов в `src/components/crm/ui/*` + `components/crm/layout/PageHeader.tsx`, используется только в `/influence/*` (52 импорта).

**Задача:** привести Hub к единому визуальному языку **Design System v2** (stone + DM Sans + Instrument Serif + light/dark) на основе эталонных артефактов `wookiee_ds_v2_foundation.jsx` и `wookiee_ds_v2_patterns.jsx`.

**Эталонные документы (источники правды):**
- `DESIGN_SYSTEM.md` — спецификация v2 (палитра, токены, типографика, компоненты, паттерны, антипаттерны, чек-лист)
- `HANDOFF.md` — инструкции для Claude Code
- `BRIEF_hub_redesign.md` — план миграции по 5 волнам
- `wookiee_ds_v2_foundation.jsx` — UX-эталон Atoms/Forms/Data/Charts/Layout/Overlays/Feedback
- `wookiee_ds_v2_patterns.jsx` — UX-эталон Kanban+DnD/Calendar+DnD/Comments/Notifications/Activity/Inbox

---

## 2. Стек проекта (подтверждён двумя верификациями)

- **Build:** Vite 7 + React 19 + React Router 7
- **Styling:** Tailwind CSS v4 (через `@tailwindcss/vite`) с `@theme inline`
- **UI primitives:** shadcn/ui (12 компонентов: Button, Calendar, Checkbox, Command, Dialog, DropdownMenu, InputGroup, Input, Popover, Separator, Tabs, Textarea) + Radix
- **DnD:** `@dnd-kit/core` + `@dnd-kit/sortable` + `@dnd-kit/utilities` (уже стоит)
- **Charts:** `recharts` (уже стоит, используется в `/analytics/rnp`)
- **State:** Zustand 5 (theme, navigation, integrations, community, operations) с persist в localStorage `wookiee-theme`. Default `theme = "dark"` — **меняем на "light" в Wave 1** (см. G2)
- **Auth/DB:** Supabase (OTP login)
- **Toast:** Sonner (привязан в `main.tsx`, **без theme prop — G4**)
- **Forms:** react-hook-form + zod
- **Fonts:** Inter Variable (`@fontsource-variable/inter`) — заменяем на DM Sans Variable
- **Tests:** Vitest 9 файлов (нет Playwright npm — используем MCP)
- **TypeScript:** strict, paths `@/*` → `./src/*` (config в `tsconfig.temp.json` — историческая особенность, не трогаем)
- **Deploy:** rsync на `/home/danila/projects/wookiee/wookiee-hub/dist/` (через autopull)

### 2.1. Wookiee-extended tokens (G5)

Кроме shadcn-токенов, в `index.css` объявлены extended Wookiee-токены под `@theme inline`. Они используются в `top-bar.tsx`, `icon-bar.tsx`, `app-shell.tsx`, и десятках страниц:

| Token | Используется в | DS v2 значение (light) | DS v2 значение (dark) |
|---|---|---|---|
| `--bg-soft` (`bg-bg-soft`) | top-bar overlay, hover-zones | stone-100 | stone-900 |
| `--text-dim` (`text-text-dim`) | вторичный текст, hints | stone-500 | stone-400 |
| `--icon-bar-bg` (`bg-icon-bar`) | IconBar фон | stone-50 | stone-950 |
| `--bg-hover` (`bg-bg-hover`) | hover states | stone-100 | stone-800 |
| `--wk-green` | success, status badges | emerald-500 | emerald-400 |
| `--wk-red` | danger, alerts | red-500 | red-400 |
| `--wk-yellow` | warning, pending | amber-500 | amber-400 |
| `--wk-blue` | info, links | blue-500 | blue-400 |
| `--wk-pink` | brand accent (logo, primary CTA) | pink-500 | pink-400 |

tokens-agent **обязан** пересчитать все extended-токены в обеих темах вместе с shadcn-токенами.

### 2.2. Routes — фактический список (G1)

Из `router.tsx` (verified):
- **Под `/login`** (без layout): `/login` — 1 page
- **Под `CatalogLayout`** (22 routes): `/catalog/{matrix,colors,artikuly,tovary,skleyki,semeystva-cvetov,upakovki,kanaly-prodazh,sertifikaty,import,__demo__}` + `/catalog/references/{kategorii,kollekcii,tipy-kollekciy,brendy,fabriki,importery,razmery,statusy,atributy}` + 2 redirects (`/catalog` → matrix, `/catalog/references` → kategorii)
- **Под `AppShell`** (~12 routes): `/`, `/operations/{tools,activity,health}`, `/community/{reviews,questions,answers,analytics}`, `/influence/{bloggers,integrations,calendar}`, `/analytics/rnp`, опционально `/marketing/{promo-codes,search-queries}` (за feature flag `featureFlags.marketing`)
- **`/agents/*`** — страницы существуют в `src/pages/agents/*`, **в router НЕ подключены** → out of scope Wave 1

Итого активных routes для Playwright: 1 (login) + 22 (catalog) + 12 (hub-shell) + 2 (marketing если flag) + 1 (design-system-preview новый) = **38 routes** при включённом marketing flag, 36 без.

---

## 3. Архитектурные решения (CTO-mode, обоснованные)

### 3.1. Token strategy: repaint values, keep names

**Что:** Имена shadcn-переменных (`--background`, `--foreground`, `--card`, `--primary`, `--border`, `--ring`, `--muted-foreground`...) сохраняются. Меняются только **значения** — с oklch-purple на stone-палитру DS v2. То же для extended Wookiee-токенов (см. 2.1).

**Почему:** Имена shadcn закрывают ~80% семантики DS v2:
- `bg-card` ≈ DS v2 `bg-surface`
- `bg-background` ≈ DS v2 `bg-page`
- `text-foreground` ≈ DS v2 `text-primary`
- `text-muted-foreground` ≈ DS v2 `text-muted`
- `border-border` ≈ DS v2 `border-default`

Десятки shadcn-компонентов получают новый вид **автоматически** через CSS-cascade без правки кода. Будущие обновления shadcn остаются совместимыми. Минимальный ripple.

**Что добавляется новыми утилитами через `@utility`:** `text-label`, `border-strong` — этих shadcn не покрывает.

**Конфликт имён в эталоне:** в DS v2 `text-primary` = основной текст. В shadcn `text-primary` = on-primary-button color. **Не вводим дублирующее имя.** При переписывании primitives с эталона переводим:
- эталон `text-primary` → shadcn `text-foreground`
- эталон `bg-surface` → shadcn `bg-card`
- эталон `bg-page` → shadcn `bg-background`
- эталон `text-secondary` → `text-stone-700 dark:text-stone-300` (или alias через @utility)
- эталон `text-muted` → shadcn `text-muted-foreground`
- эталон `border-default` → `border` (shadcn default)
- эталон `border-strong` → новая утилита

### 3.2. Default theme: light (G2)

`stores/theme.ts` меняет default с `"dark"` на `"light"`. Persist-middleware означает: пользователи с уже сохранённым `dark` остаются в dark. **Принудительно не мигрируем** — это раздражает, и DS v2 явно поддерживает обе темы equal.

### 3.3. FOWT prevention (G9)

В `index.html` перед `<script type="module" src="/src/main.tsx">` добавляем inline-скрипт:

```html
<script>
  (function() {
    try {
      var stored = localStorage.getItem('wookiee-theme');
      var theme = stored ? JSON.parse(stored).state.theme : 'light';
      if (theme === 'dark') document.documentElement.classList.add('dark');
    } catch (e) {}
  })();
</script>
```

Это устраняет FOWT (Flash of Wrong Theme) на cold load — особенно на `/login`, который вне AppShell. Скрипт inline + sync = выполняется до first paint.

### 3.4. Theme sync — в main.tsx (G3)

Текущая логика в `app-shell.tsx`:
```tsx
useEffect(() => {
  document.documentElement.classList.toggle("dark", theme === "dark")
}, [theme])
```

**Проблема:** AppShell монтируется только для protected routes. На `/login` AppShell не рендерится → `html.dark` никогда не синхронизируется → theme switch на login делает ничего.

**Решение:** Переносим subscribe-логику в `main.tsx` через `useThemeStore.subscribe`:

```tsx
useThemeStore.subscribe((s) => {
  document.documentElement.classList.toggle('dark', s.theme === 'dark')
})
// + initial sync
document.documentElement.classList.toggle(
  'dark', useThemeStore.getState().theme === 'dark'
)
```

Работает универсально, до монтирования любого route. useEffect в app-shell.tsx — удаляем.

### 3.5. Toaster theme prop (G4)

В `main.tsx`:

```tsx
function App() {
  const theme = useThemeStore((s) => s.theme)
  return (
    <>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" closeButton theme={theme} />
    </>
  )
}
```

Sonner сам адаптирует toast styling под light/dark.

### 3.6. Catalog scope: сохраняем в Wave 1

`.catalog-scope` сейчас хардкодит stone-палитру через `--cat-*` CSS-vars (RGB tuples) **без зависимости от Hub-токенов**. Перекраска Hub-токенов **не влияет** на catalog visually. В Wave 1 — не трогаем, только Playwright-QA подтверждает что 22 страницы работают.

В Wave 2 — снимаем `.catalog-scope`, унифицируем токены.

### 3.7. CRM Kit + CRM PageHeader: оставляем изолированным в Wave 1 (G6)

`src/components/crm/ui/*` (13 компонентов) + `src/components/crm/layout/PageHeader.tsx` — отдельная мини-DS. После repaint Hub-токенов CRM Kit автоматически перекрашивается (он использует те же CSS-переменные shadcn внутри). Унификация — **Wave 5**.

Для Hub-страниц (operations, community, analytics, login) создаём **новый** `src/components/layout/page-header.tsx` со структурой эталона: kicker + Instrument Serif title + breadcrumbs + actions + status. CRM-страницы продолжают использовать свой `crm/layout/PageHeader.tsx` до Wave 5.

### 3.8. Шрифты

- **Основной (`--font-sans`):** меняем с `Inter Variable` на `DM Sans Variable` (`@fontsource-variable/dm-sans`)
- **Заголовки страниц:** Instrument Serif italic (Google Fonts с preload — уже подключено в `index.css`)
- Inter удаляем после миграции (`npm uninstall @fontsource-variable/inter`)

### 3.9. DnD: `@dnd-kit` (уже стоит)

Не меняем. Эталонные patterns пишутся под `@dnd-kit/core` + `@dnd-kit/sortable`.

### 3.10. QA: через Playwright MCP (G13)

Local `playwright` npm не ставим. Используем `mcp__plugin_playwright_playwright__*`. Phase 7 явно:

1. `npm run dev` в background (через Bash `run_in_background: true`)
2. Ждём `localhost:5173` доступным (через `browser_navigate` с retry)
3. Логин через OTP скипаем — используем pre-existing Supabase session token (см. `reference_hub_qa_user.md`)
4. Проход всех routes × 2 темы → 76 screenshots (38 × 2)
5. `browser_console_messages` после каждой страницы — errors count

### 3.11. CI workflow: не в Wave 1

Сейчас `.github/workflows/` для monorepo есть, но он Python-only. Для wookiee-hub CI отсутствует. **Не добавляем в Wave 1** (out of scope).

### 3.12. TypeScript acceptance (G10)

В `package.json` нет `tsc` script. Добавляем:

```json
"typecheck": "tsc -p tsconfig.temp.json --noEmit"
```

Acceptance: `npm run typecheck` exit code 0.

### 3.13. Bundle size acceptance (G11)

До миграции: `npm run build` + `du -sk dist/` = baseline. После Wave 1: bundle gzipped не должен расти > +250 KB. DM Sans Variable (~70KB gzipped) + 11 primitives (~30KB) — запас. Если выходим за лимит → tree-shake check.

### 3.14. tsconfig.temp.json

Не переименовываем — это сознательная особенность проекта. Build через Vite работает.

---

## 4. Архитектура оркестрации

**Главный оркестратор** = chat-сессия Claude. Координирует под-агентов через `Agent` tool (subagent_type=general-purpose), делает атомарные коммиты, передаёт следующему агенту через context summary.

**Под-агенты (8):**

| # | Агент | Цель | Зависит от | Параллелит с |
|---|---|---|---|---|
| 1 | **audit-agent** | Полная инвентаризация: хардкод stone-* по файлам, dark: префиксы, неиспользуемые tokens, использование shadcn vs custom, inline-styles. Output: `WAVE1_AUDIT.md`. | — | — |
| 2 | **tokens-agent** | Repaint `src/index.css`: значения OKLCH → stone-палитра + extended Wookiee-токены (G5) в обеих темах. Добавляет утилиты `text-label`, `border-strong`. FOWT script в `index.html` (G9). | 1 | 3 |
| 3 | **fonts-agent** | `npm install @fontsource-variable/dm-sans` + import в index.css + меняет `--font-sans`. Подключает Instrument Serif preload. `npm uninstall @fontsource-variable/inter`. | 1 | 2 |
| 4 | **primitives-agent** | Расширяет shadcn-набор до эталона: `Badge`, `StatusBadge`, `LevelBadge`, `Tag`, `Chip`, `Avatar` (+`AvatarGroup`), `ColorSwatch`, `Ring`, `Tooltip`, `Skeleton`, `Kbd`, `EmptyState`. Расширяет `Button` вариантами `success`, `danger-ghost`. | 2, 3 | 5 |
| 5 | **preview-route-agent** | Создаёт `/design-system-preview` (testbed страница, скрыта из nav). Все primitives + форм-поля + layout-секции в light+dark. | 2, 3 | 4 |
| 6 | **layout-shell-agent** | Repaint `AppShell`, `IconBar`, `SubSidebar`, `TopBar`, `Logo`, `MobileNav`, `MobileMenu`. Замена inline `<kbd>` → `<Kbd>` (G12). Создаёт **новый** `src/components/layout/page-header.tsx` (G6). Theme-sync в `main.tsx` (G3, G4). FOWT skip в app-shell.tsx. | 4 | — |
| 7 | **pages-migration-agent ×3** | Параллельно: **Group A:** `/operations/*` + `/login` (включая login deep refactor на shadcn primitives — G7). **Group B:** `/community/*` + `src/components/community/*` под-компоненты (G8). **Group C:** `/influence/*` (НЕ-CRM-Kit части) + `/analytics/rnp`. Точечная замена хардкода stone-* → shadcn utility names. | 6 | — |
| 8 | **qa-playwright-agent** | `npm run dev` background (G13). Через Playwright MCP проходит ВСЕ 38 routes × 2 темы = 76 скриншотов, console errors check, visual diff vs эталона. Output: `WAVE1_QA_REPORT.md`. | 5, 6, 7 | — |

---

## 5. Фазы Wave 1 (последовательно, атомарные коммиты)

### Phase 1 · Audit & branch setup
- Ветка `feat/ds-v2-wave-1` создана от `main` (✅ создана 2026-05-15)
- Spec этот файл — первый коммит на ветке (v1 ✅, v2 коммит после написания)
- audit-agent → `WAVE1_AUDIT.md` (хардкод stone-*, dark: префиксы, inline-styles, использование shadcn-vs-custom)
- Baseline bundle: `npm run build && du -sk dist/` → запись в `WAVE1_AUDIT.md` (для G11 сравнения)
- Commit: `docs(ds-v2): wave 1 codebase audit + bundle baseline`

### Phase 2 · Tokens & fonts
- tokens-agent:
  - `src/index.css` — все значения OKLCH в `:root` и `.dark` пересчитаны под stone-палитру
  - extended Wookiee-tokens (G5) пересчитаны в обеих темах
  - Добавлены `@utility text-label`, `@utility border-strong`
  - `index.html` — inline FOWT script (G9)
- fonts-agent:
  - `npm install @fontsource-variable/dm-sans`
  - import в `index.css`, `--font-sans: 'DM Sans Variable'`
  - `npm uninstall @fontsource-variable/inter`
  - удалить старый Inter import из `index.css`
- Build check: `npm run build` локально (size delta vs baseline записан)
- Commit: `feat(ds-v2): repaint tokens to stone + DM Sans + FOWT script`

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
  - `kbd.tsx` (G12 будет использовать)
  - `empty-state.tsx`
- Расширяется `button.tsx` вариантами `success`, `danger-ghost`
- Существующий `shared/progress-bar.tsx` обновляется под эталон (с label, compact, color variants)
- Commit: `feat(ds-v2): primitives package`

### Phase 4 · Design System preview
- preview-route-agent создаёт `src/pages/design-system-preview/index.tsx`
- Route в `router.tsx` (под AppShell, не в navigation menu — скрыт от обычных пользователей, нужен для QA)
- Все primitives + форм-поля + layout-секции, переключатель темы прямо на странице
- Commit: `feat(ds-v2): /design-system-preview route`

### Phase 5 · Layout shell repaint + theme orchestration
- layout-shell-agent:
  - Repaint `AppShell`, `IconBar`, `IconBarButton`, `SubSidebar`, `SubSidebarItem`, `TopBar`, `Logo`, `MobileNav`, `MobileMenu`, `UserMenu`, `ThemeToggle` через shadcn utility names
  - В `top-bar.tsx` заменить inline `<kbd>...</kbd>` на `<Kbd>` (G12)
  - Создать **новый** `src/components/layout/page-header.tsx` (G6) с структурой:
    ```tsx
    type PageHeaderProps = {
      kicker?: string;
      title: string;           // Instrument Serif italic
      breadcrumbs?: Crumb[];
      status?: ReactNode;
      actions?: ReactNode;
      description?: string;
    }
    ```
  - **CRM `components/crm/layout/PageHeader.tsx` не трогаем** — он остаётся для `/influence/*`
  - Theme sync орchestration (G3): subscribe в `main.tsx`, useEffect удалить из `app-shell.tsx`
  - Toaster theme prop (G4): `theme={theme}` через subscribe
  - Default theme (G2): `stores/theme.ts` default → `"light"`
- Build check + manual smoke test на `/operations/tools` + `/login` (theme switch работает на обеих)
- Commit: `feat(ds-v2): repaint AppShell + Hub PageHeader + theme orchestration`

### Phase 6 · Pages migration (3 параллельных под-агента)
- **Group A:** `/operations/{tools,activity,health}` + `/login`
  - Точечная замена hardcoded `text-stone-*`/`bg-stone-*` → semantic shadcn utilities
  - **Login deep refactor (G7):** inline HTML form → `<Input type="email">`, `<Button>` shadcn, `<PageHeader>` для логин-карточки
  - Commit: `feat(ds-v2): migrate pages (operations + login)`

- **Group B:** `/community/{reviews,questions,answers,analytics}` + `src/components/community/*` под-компоненты (G8)
  - Рекурсивный обход: `ReviewsHeader`, `ReviewsStatusTabs`, `ReviewListItem`, `ReviewDetail`, и аналогичные для questions/answers
  - gradients проверка/упрощение, dark: префиксы → utility classes
  - Commit: `feat(ds-v2): migrate pages (community)`

- **Group C:** `/influence/{bloggers,integrations,calendar}` + `/analytics/rnp`
  - CRM Kit и CRM PageHeader **не трогаем** — только wrappers и не-CRM-Kit части страниц
  - Analytics charts получают новые `--chart-1..5` (Wave 3 переколесит формы)
  - Commit: `feat(ds-v2): migrate pages (influence + analytics)`

### Phase 7 · QA Playwright
- `npm run dev` в background (G13)
- Подождать `localhost:5173` готовности
- Использовать pre-logged Supabase session (см. `reference_hub_qa_user.md`)
- qa-playwright-agent через Playwright MCP:
  - 38 routes × 2 темы = 76 скриншотов, сохраняются в `wave1-qa-screenshots/`
  - `browser_console_messages` после каждой страницы — errors count
  - Visual diff (eye-level) против эталонных JSX-страниц для key-routes
- Routes (~38):
  - login (1)
  - catalog (22): matrix, colors, artikuly, tovary, skleyki, semeystva-cvetov, upakovki, kanaly-prodazh, sertifikaty, import, __demo__, references/{kategorii, kollekcii, tipy-kollekciy, brendy, fabriki, importery, razmery, statusy, atributy}
  - hub-shell (12): /, /operations/{tools,activity,health}, /community/{reviews,questions,answers,analytics}, /influence/{bloggers,integrations,calendar}, /analytics/rnp
  - marketing (2, если flag): promo-codes, search-queries
  - design-system-preview (1)
- Output: `WAVE1_QA_REPORT.md` (per-route pass/fail table, console errors counts, screenshots paths, найденные дефекты с severity)
- **Blocker дефекты** (фикс в Wave 1 обязательно):
  - Console errors > 0 на любой странице
  - Theme switch ломается на любой странице (включая `/login`)
  - Build break
  - Primitive не рендерится в одной из тем
  - PageHeader не отображается с Instrument Serif italic
  - FOWT visible на cold reload (G9 не работает)
- **Non-blocker дефекты** (отдельный issue в backlog Wave 2+):
  - Visual nit < 4px misalignment
  - Gradient mismatch в community (если не критично)
  - CRM Kit стиль не точно совпадает с эталоном (ожидаемо до Wave 5)
- Commit: `chore(ds-v2): wave 1 QA report`

### Phase 8 · PR open
- Push ветка `feat/ds-v2-wave-1` на origin
- `gh pr create` с описанием:
  - Список изменений
  - Acceptance checklist (раздел 6)
  - Скриншоты ключевых routes (login, operations/tools, community/reviews, design-system-preview — light + dark)
  - Attached `WAVE1_AUDIT.md` + `WAVE1_QA_REPORT.md`
- **НЕ auto-merge** — Данила ревьюит и мерджит сам

---

## 6. Acceptance Wave 1

1. **Console errors = 0** на всех 38 routes в обеих темах (Playwright измерение через `browser_console_messages`)
2. **Catalog открывается** — все 22 страницы `/catalog/*` рендерятся (DOM есть, no white screen)
3. **Marketing открывается** — `/marketing/promo-codes`, `/marketing/search-queries` рендерятся (если flag вкл)
4. **Шрифты** — `getComputedStyle(document.body).fontFamily` содержит `DM Sans`, на `<h1>` через `<PageHeader>` — содержит `Instrument Serif`
5. **Theme switch** — клик по toggle переключает `<html class>` между `""` и `"dark"`, localStorage `wookiee-theme` обновляется, CSS-переменные cascade. **Работает на /login тоже** (G3)
6. **No FOWT** — cold reload на любой route не показывает flash противоположной темы (G9)
7. **Toaster theme** — тосты в light выглядят как light, в dark — как dark (G4)
8. **Default theme = light** для новых пользователей (clear localStorage + reload → light) (G2)
9. **Build clean** — `npm run build` exit code 0
10. **TypeScript clean** — `npm run typecheck` exit code 0 (G10)
11. **Bundle не раздут** — `du -sk dist/` после миграции не растёт > +250 KB gzipped vs baseline (G11)
12. **Preview route** — `/design-system-preview` открывается, все 11 новых primitives + расширенный Button присутствуют в DOM в light и dark
13. **Primitives API соответствует эталону** — каждый компонент в `src/components/ui/{badge,status-badge,level-badge,tag,chip,avatar,color-swatch,ring,tooltip,skeleton,kbd,empty-state}.tsx` принимает props идентичные эталонной сигнатуре в `wookiee_ds_v2_foundation.jsx`
14. **No inline `<kbd>`** в shell (top-bar) — заменено на `<Kbd>` (G12)
15. **Login на shadcn** — `/login` использует `<Input>`, `<Button>`, не inline HTML (G7)
16. **PR open** — `feat/ds-v2-wave-1` open без auto-merge, описание соответствует шаблону (changelog + screenshots + acceptance checklist + 2 attached reports)
17. **QA report attached** — `WAVE1_QA_REPORT.md` + `WAVE1_AUDIT.md` приложены к PR

---

## 7. Risk register

| # | Риск | Mitigation |
|---|---|---|
| R1 | Catalog/marketing хардкодят stone (~1347 классов) — могут зависеть от Hub-token cascade | Аудит подтвердил: они хардкодят stone-цвета напрямую, **не** через CSS vars Hub. Repaint Hub-токенов не затрагивает их. Playwright QA подтверждает |
| R2 | CRM Kit (crm/ui/*) после repaint визуально не дотягивает до эталона | Ожидаемо — унификация в Wave 5. В Wave 1 — только «не сломалось» |
| R3 | Конфликт shadcn `text-primary` vs DS v2 `text-primary` | Используем только shadcn-имена в новом коде. Эталонный `text-primary` → shadcn `text-foreground` при переписывании |
| R4 | Community gradients конфликтуют с новой палитрой | Group B handles это точечно — gradients либо упрощаются, либо переводятся на новые brand-токены |
| R5 | Build broken после migration | Atomic commits, локальный `npm run build` + `npm run typecheck` после каждого. Если break — rollback + investigate |
| R6 | Playwright MCP не справляется с 76 скриншотами за один проход | Бьём QA на 3 партии: catalog (22×2=44), hub-shell+marketing+login (14×2=28), preview+design-diff (1×2+visual=spot) |
| R7 | Calendar в `/influence/*` плохо смотрится после repaint (только month, недоразвит) | Wave 5 расширит до Month+Week+DnD. В Wave 1 — отмечается в QA report, не блокер |
| R8 | Inter Variable удаление ломает существующие inline styles | grep + замена inline `font-family: 'Inter'` → use `var(--font-sans)` или удаление. Audit-agent ловит все места |
| R9 | Community own-components структура глубже ожидаемого (sub-headers, list items, detail panels) | Group B расширена явно (G8), audit-agent inventory `src/components/community/*` файлов перед миграцией |
| R10 | DM Sans Variable + 11 primitives раздувают bundle > +250 KB | Baseline + после-замер в Phase 1+2, если raddvigaem > +250KB → tree-shake check, lazy preview route, либо drop static fonts в пользу Google Fonts CDN |
| R11 | FOWT script ломается на пустом / corrupted localStorage | Try/catch вокруг JSON.parse в FOWT script (G9 — уже в коде script) |
| R12 | Theme subscribe в main.tsx подтекает (memory leak) | Zustand subscribe возвращает unsubscribe, но main.tsx не unmount — leak теоретически невозможен. Подтверждается smoke-test |

---

## 8. Out of scope для Wave 1

- `/agents/*` миграция (страницы существуют, но не подключены в router — отдельный sub-project) (G1)
- Унификация CRM Kit с shadcn (`crm/ui/*` + `crm/layout/PageHeader.tsx`) (Wave 5)
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
- Новые компоненты в `src/components/charts/`: MultiSeriesLine, StackedBar, ComboChart, Donut (central value), Gauge, Funnel (custom div-based), CalendarHeatmap, Sparkline
- Миграция `/analytics/rnp/*` (6 tabs) под новые компоненты

### Wave 4 — Operations & Production (2 нед)
- GroupedTable (pivot-style) компонент в `src/components/ui/data/`
- Применить в новой странице «Планирование поставок»
- OrderHeaderCard + TargetDaysSlider
- Cover-days color indicators (red/amber/emerald/blue)

### Wave 5 — Content & Patterns + CRM unification (2-3 нед)
- **CRM Kit unification:** заменить `crm/ui/*` → shadcn эквиваленты, удалить дубли (52 импорта переписать), `crm/layout/PageHeader.tsx` → migrate to Hub `layout/page-header.tsx`
- Расширить `/influence/calendar` до Month+Week+DnD событий
- Detail Drawer для Kanban карточки (560px полный layout: header + properties + description + subtasks + attachments + comments + activity)
- Новые pattern-компоненты: CommentsThread, NotificationsPanel (slide-out), ActivityFeed (Linear-style), Inbox
- Подключить `/agents/*` в router (G1)

### Post Wave 5 — Realtime (отдельный sub-project)
- Supabase realtime channels для Comments, Activity, Notifications
- Multi-user collab в Kanban (presence + concurrent DnD)
- Bell badge с unread count

---

## 10. QA detailed plan (Phase 7 expansion)

### 10.1. Pre-flight
1. `npm run build && du -sk dist/` → baseline-after-wave1 (для G11 финального сравнения)
2. `npm run typecheck` → exit 0
3. `npm run dev` в background → ждём `localhost:5173`

### 10.2. Per-route test matrix (38 routes × 2 themes = 76 cells)

Для каждого route:
1. `browser_navigate(url)` → ждём 1s
2. `browser_take_screenshot(filename=<route>__<theme>.png)`
3. `browser_console_messages()` → assert errors count == 0
4. Visual diff (eye-level) vs эталона:
   - Шрифт body = DM Sans
   - PageHeader h1 = Instrument Serif italic
   - Палитра = stone (нет purple остаточных)
   - Theme corresponds (light ≠ dark)

### 10.3. Smoke tests (manual)

Эти проверки идут после auto-screenshot pass:
- Theme switch на `/login` → html.dark меняется
- Cold reload `/login` в dark → no FOWT (G9)
- Toaster на любой странице (dispatch `toast.success("test")`) → в light выглядит как light
- localStorage clear + reload → default light (G2)
- DnD на `/influence/integrations` (Kanban) — карточка перетаскивается
- Filter+sort на `/community/reviews`

### 10.4. Output format

```
# WAVE1_QA_REPORT.md

## Routes pass/fail

| Route | Light | Dark | Console errs | Notes |
|---|---|---|---|---|
| /login | ✅ | ✅ | 0 | — |
| /catalog/matrix | ✅ | ✅ | 0 | — |
| ... | | | | |

## Blocker defects
(пусто или список с reproducer)

## Non-blocker defects (backlog)
- ...

## Bundle size delta
baseline: 1234 KB
after wave 1: 1456 KB
delta: +222 KB (acceptable, < 250 KB threshold)

## Screenshots
`./wave1-qa-screenshots/*.png` (76 files)
```

---

## 11. Open questions

Ни одного — все технические развилки приняты CTO-mode. Жду review этого spec; если возражений нет — переходим к writing-plans skill для подробного implementation plan.

---

*Spec ver 2.0 · 2026-05-15 · Wookiee Hub DS v2 · Wave 1 Foundation · Re-verified gap-fills*
