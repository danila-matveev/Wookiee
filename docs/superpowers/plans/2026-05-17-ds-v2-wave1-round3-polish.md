# Wave 1 — Round 3 polish (DS v2 hub)

**Date:** 2026-05-17
**Branch:** `feat/ds-v2-wave-1-polish-round3`
**Base:** `main` (Wave 1 уже влит через PR #149)
**Repo subdir:** `wookiee-hub/`

---

## GOAL

Закрыть 7 UX/верстальных недочётов Wave 1 DS v2 в hub-ui, найденных пользователем при ручной проверке проде/деве, **не задевая** `/catalog/*` (изолированный Wave 4) и **не редизайня** `/influence/bloggers` (пользователь сделает сам). Результат — компактные страницы без тавтологии в заголовках, рабочий sticky thead/tfoot, нормальная клавиатура навигации (логотип → главная, back-arrow из каталога), без визуального двойного паддинга на маркетинге. PR создан, CI зелёный, локальный smoke прошёл на 5 контрольных страницах.

**Definition of Done:**
1. Все 5 атомарных коммитов из секции «Execution» в ветке `feat/ds-v2-wave-1-polish-round3`.
2. `npm run build` зелёный.
3. `npm run lint` зелёный (или без новых ворнингов сверх baseline).
4. `npm run test -- --run` зелёный.
5. Playwright smoke (см. секцию «Verification») сделал 5 скринов и все они подтверждают фиксы.
6. PR создан и пушнут (через `/ship`) с описанием по шаблону из секции «PR description».

---

## NON-GOALS / Гардрейлы

- **НЕ ТРОГАТЬ** `/catalog/*` ни в pages, ни в `components/catalog/*` (Wave 4, изолированный `.catalog-scope`).
- **НЕ РЕДИЗАЙНИТЬ** `/influence/bloggers` (`pages/influence/bloggers/`) — пользователь делает сам отдельным PR. PageHeader в `BloggersPage.tsx` тоже **не** трогаем (он войдёт в редизайн юзера).
- **НЕ МЕНЯТЬ** дизайн-токены `src/index.css`, шрифты, цвета, темы. Wave 1 их зафиксировал.
- **НЕ ПУШИТЬ В MAIN напрямую** — только через PR, ruleset 12853246 это всё равно заблокирует.
- **НЕ СКИПАТЬ ХУКИ** (`--no-verify`, `--no-gpg-sign`).
- **НЕ УДАЛЯТЬ** `kicker` из catalog `_shared.tsx` PageHeader — это отдельный компонент (он не от `layout/page-header.tsx`).

---

## CONTEXT (что важно для исполнителя)

- AppShell-страницы рендерятся внутри `src/components/layout/app-shell.tsx:56-57`:
  ```tsx
  <div className="flex-1 overflow-y-auto p-4 sm:p-6 pb-16 sm:pb-6">
    <div className="max-w-screen-2xl mx-auto">
      <Outlet />
    </div>
  </div>
  ```
  Это даёт scroll + padding + центрирование. Страницы НЕ должны добавлять ещё один scroll-контейнер или ещё один `px-6` — это и есть источник «двойного паддинга» и «срезанного края».

- TopBar (`src/components/layout/top-bar.tsx:45-66`) **уже** рендерит хлебные крошки «Группа › Раздел» на основе `navigationGroups`. PageHeader дублирует это своими `breadcrumbs` + `kicker` — отсюда тавтология.

- Sticky thead/tfoot работают только если scroll-контейнер имеет фиксированную высоту. Сейчас вложенный `<div className="flex-1 overflow-auto">` без явной высоты — scroll реально на AppShell, sticky сломан.

---

## EXECUTION — 5 атомарных коммитов

### Commit 1: `feat(hub): logo → main, add back-to-hub from catalog`

**Файлы:**
- `wookiee-hub/src/components/layout/logo.tsx`
- `wookiee-hub/src/components/catalog/layout/catalog-topbar.tsx`

**Изменения:**

1. В `logo.tsx:6` — `to="/community/reviews"` → `to="/"`. Это редиректнет на `/operations/tools` через `router.tsx:146`.

2. В `catalog-topbar.tsx` — добавить в левую часть topbar'а **до** существующего контента кнопку-ссылку:
   ```tsx
   import { ArrowLeft } from "lucide-react"
   import { Link } from "react-router-dom"
   // ...
   <Link
     to="/"
     aria-label="Назад в Hub"
     className="flex items-center gap-1.5 px-2 py-1 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
   >
     <ArrowLeft size={14} aria-hidden />
     <span className="hidden sm:inline">В Hub</span>
   </Link>
   ```
   Если в catalog-topbar логотип каталога есть — тоже сделать кликабельным на `/` (как в основном AppShell).

**Verify:**
- Открыть `/community/reviews`, кликнуть лого → URL становится `/operations/tools`.
- Открыть `/catalog/references/brendy`, кликнуть «← В Hub» → URL `/operations/tools`.

---

### Commit 2: `fix(marketing): remove redundant wrapper that clips table edges`

**Файлы:**
- `wookiee-hub/src/pages/marketing/promo-codes.tsx`
- `wookiee-hub/src/pages/marketing/search-queries.tsx`

**Изменения:**

В обоих файлах удалить внешние обёртки. Было (promo-codes.tsx:37-58):
```tsx
return (
  <div className="flex flex-1 overflow-hidden">
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
      <div className="px-6 pt-6 pb-0">
        <PageHeader ... />
      </div>
      <PromoCodesTable />
    </div>
    {renderPanel()}
  </div>
)
```

Станет:
```tsx
return (
  <>
    <PageHeader ... />
    <PromoCodesTable />
    {renderPanel()}
  </>
)
```

То же самое для `search-queries.tsx:100-121`.

**Verify:**
- `/marketing/promo-codes` — нет белого «среза» слева, таблица занимает всю доступную ширину до правого края `max-w-screen-2xl`.
- `/marketing/search-queries` — то же.

---

### Commit 3: `fix(marketing): make sticky thead+tfoot work via bounded scroll`

**Файлы:**
- `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx`
- `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`
- `wookiee-hub/src/pages/marketing/search-queries/SearchQueryDetailPanel.tsx`

**Изменения:**

1. **PromoCodesTable.tsx:131** — `<div className="flex-1 overflow-auto">` → `<div className="overflow-auto max-h-[calc(100dvh-280px)]">`. Параметр 280px рассчитан: TopBar 48 + AppShell padding 24+24 + PageHeader высота ~136 + KPI cards ~64 + UpdateBar ~32 + фильтры ~48 ≈ 280px. Если визуально низ упирается криво, подстроить (тестировать на высоте viewport 900px).

2. **SearchQueriesTable.tsx:215** — то же изменение: `<div className="flex-1 overflow-auto">` → `<div className="overflow-auto max-h-[calc(100dvh-260px)]">`. Тут нет KPI cards, поэтому 260.

3. **SearchQueriesTable.tsx:155** — заменить `<div className="flex flex-col h-full">` на `<div className="flex flex-col">` (нет нужды в h-full, scroll теперь у внутреннего div).

4. **PromoCodesTable.tsx** — аналогично, если есть `h-full` на корневом `<div>`, убрать.

5. **SearchQueryDetailPanel.tsx:263** — добавить `sticky bottom-0 bg-card` к `<tfoot>`:
   ```tsx
   <tfoot className="sticky bottom-0 bg-card">
     <tr className="border-t border-border">
       ...
     </tr>
   </tfoot>
   ```
   Родитель `max-h-[320px] overflow-y-auto` уже есть, sticky сработает.

**Verify:**
- `/marketing/search-queries`: при скролле длинного списка шапка остаётся вверху, «Итого · N запросов» — внизу.
- `/marketing/promo-codes`: то же.
- Открыть drawer любого запроса → блок «По товарам (за выбранный период)»: при scroll'е таблицы внутри блока «Итого по N товарам» прилипает к низу.

---

### Commit 4: `feat(marketing): status dropdown + compact filter row`

**Файлы:**
- `wookiee-hub/src/pages/marketing/search-queries/SearchQueriesTable.tsx`

**Изменения:**

1. Удалить строку 183-195 (пилюль-кнопки статуса).

2. В строке фильтров (`<div className="px-6 pt-3 pb-2 ...">` line 158) добавить третий `SelectMenu` для статуса прямо рядом с «Модель» и «Назначение»:
   ```tsx
   <div className="flex items-center gap-2">
     <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Статус:</span>
     <div className="w-[140px]">
       <SelectMenu
         value={statusF === 'all' ? '' : statusF}
         options={[
           { value: 'active', label: STATUS_LABELS.active },
           { value: 'free', label: STATUS_LABELS.free },
           { value: 'archive', label: STATUS_LABELS.archive },
         ]}
         onChange={(v) => setQ('status', v || null)}
         placeholder="Все"
       />
     </div>
   </div>
   ```

3. **Не трогать** строки поиска/периода/группировки (строка 198+) — они и так в одном ряду.

**Verify:**
- `/marketing/search-queries`: одна строка с тремя dropdown'ами (Модель / Назначение / Статус) вместо двух строк. Выбор «Активный» в Статусе фильтрует таблицу.

---

### Commit 5: `refactor(layout): drop tautological kicker+breadcrumbs from PageHeader callers`

**Файлы (11 штук, BloggersPage НЕ трогаем):**
- `wookiee-hub/src/pages/operations/tools.tsx`
- `wookiee-hub/src/pages/operations/activity.tsx`
- `wookiee-hub/src/pages/operations/health.tsx`
- `wookiee-hub/src/pages/community/reviews.tsx`
- `wookiee-hub/src/pages/community/questions.tsx`
- `wookiee-hub/src/pages/community/answers.tsx`
- `wookiee-hub/src/pages/community/analytics.tsx`
- `wookiee-hub/src/pages/influence/integrations/IntegrationsKanbanPage.tsx`
- `wookiee-hub/src/pages/influence/calendar/CalendarPage.tsx`
- `wookiee-hub/src/pages/analytics/rnp.tsx`
- `wookiee-hub/src/pages/marketing/promo-codes.tsx`
- `wookiee-hub/src/pages/marketing/search-queries.tsx`

**Изменения:**

В каждом файле в вызове `<PageHeader ...>`:
- Удалить пропс `kicker={...}`.
- Удалить пропс `breadcrumbs={[...]}`.
- Оставить `title`, `description`, `actions`, `status` как есть.

Для `community/reviews.tsx`:
- Также удалить из интерфейса `ReviewsPageProps` (lines 75-88) поля `pageBreadcrumbs?: Crumb[]`.
- Удалить дефолтный параметр `pageBreadcrumbs = [...]` из сигнатуры функции `ReviewsPage`.
- Удалить импорт `type Crumb` если становится unused.
- Соответственно в `questions.tsx`/`answers.tsx` — убрать передачу `pageBreadcrumbs` если она есть.

После рефакторинга в page-header.tsx **оставить** props `kicker` и `breadcrumbs` опциональными — их использует catalog через `_shared.tsx` независимо, но даже если не использует — props всё равно остаются опциональными, ничего удалять не надо.

**Опционально (если успевается):** убрать внешние `<div className="space-y-N">` обёртки вокруг PageHeader в перечисленных файлах, если они есть. PageHeader сам даёт `mb-6 border-b pb-6`.

**Verify:**
- `/operations/tools`, `/community/reviews`, `/community/analytics`, `/influence/integrations`, `/analytics/rnp`, `/marketing/promo-codes`, `/marketing/search-queries` — на каждой странице видна **одна** хлебная крошка (в TopBar), затем сразу `<h1>` с italic-заголовком. Без uppercase «kicker». Без второй крошки выше заголовка.

---

## VERIFICATION (выполняется после каждого коммита + финально)

### После каждого коммита:
```bash
cd wookiee-hub
npm run build
npm run lint
npm run test -- --run
```
Если что-то красное — фиксить в ТОТ ЖЕ коммит (`git commit --amend`), не создавать новый.

### Финальный Playwright smoke (после Commit 5):
Создать временный скрипт `wookiee-hub/scripts/round3-smoke.mjs` (по образу `wave1-qa.mjs`), который:
1. Стартует `npm run dev` в фоне (порт 5173 или 5174).
2. Логинится через `HUB_QA_USER_PASSWORD` из `.env` (см. memory `reference_hub_qa_user`).
3. Делает скрины 5 страниц в `scripts/screenshots/round3/`:
   - `/operations/tools` — проверить: нет kicker'а, одна хлебная крошка
   - `/community/reviews` — то же
   - `/analytics/rnp` — то же
   - `/marketing/promo-codes` — проверить: нет белого среза, sticky thead+tfoot
   - `/marketing/search-queries` — то же + одна строка фильтров со статус-dropdown
4. Также кликает по логотипу со страницы `/community/reviews` и проверяет, что URL стал `/operations/tools`.
5. Грохает dev-сервер.

Скрипт можно удалить перед PR (он одноразовый) или закоммитить в `scripts/` если orchestrator сочтёт полезным.

### Финальный визуальный чек-лист:
- [ ] Лого → `/operations/tools`
- [ ] Каталог → есть «← В Hub», ведёт в `/operations/tools`
- [ ] `/marketing/promo-codes` — нет среза, sticky работает
- [ ] `/marketing/search-queries` — нет среза, sticky работает, статус-dropdown
- [ ] 11 страниц AppShell — нет дублирования крошек, нет uppercase kicker'а

---

## DEVIATION HANDLING

Если на любом шаге orchestrator натыкается на:

- **`max-h-[calc(100dvh-Npx)]` визуально не сходится** — подобрать N экспериментально, перезапустить smoke, не блокировать.
- **lint/test падает на не относящихся к этой задаче файлах** — НЕ фиксить чужие баги. Зафиксировать в PR description в секции «Known issues», продолжить.
- **catalog-topbar.tsx требует более глубокой переработки** — добавить только back-link, без переработки. Если совсем нет места — сделать back-link плавающим (`fixed top-2 left-2`) на catalog-страницах.
- **`status` фильтр в URL уже занят валидацией** — оставить логику валидации, заменить только UI.

Если что-то блокирует серьёзно — остановиться, написать в PR description «Stopped at commit N because: [причина]», создать PR на то, что успел.

---

## PR DESCRIPTION (шаблон для финального `/ship`)

```markdown
## Round-3 polish for DS v2 Wave 1

После ручного review пользователя обнаружены 7 UX/верстальных багов. Закрыты 5 атомарными коммитами.

### Что починено
- **Навигация**: логотип ведёт в главную (`/operations/tools`), в каталог-topbar добавлена кнопка «← В Hub».
- **Marketing layout**: убран лишний `flex flex-1 overflow-hidden` + `px-6` wrapper — таблицы больше не обрезаются сбоку.
- **Sticky thead/tfoot**: scroll-контейнер таблицы получил `max-h-[calc(100dvh-Npx)]` — шапка и «Итого» липнут корректно. Тот же фикс применён к блоку «По товарам» в drawer'е.
- **Status filter**: пилюль-кнопки → SelectMenu в одну строку с другими фильтрами.
- **Тавтология заголовков**: на 11 страницах под AppShell удалены `kicker` и `breadcrumbs` из PageHeader — TopBar уже даёт хлебные крошки.

### Out of scope
- `/influence/bloggers` — пользователь редизайнит сам отдельным PR.
- `/catalog/*` — Wave 4.

### Verification
- `npm run build` ✅
- `npm run lint` ✅
- `npm run test -- --run` ✅
- Playwright smoke по 5 страницам ✅ (см. screenshots в `scripts/screenshots/round3/`)
```

---

## NOTES для orchestrator'а

- Работаешь в worktree `.worktrees/feat-ds-v2-wave-1-polish-round3/` (создаётся автоматически superpowers:using-git-worktrees). Если запущен в основном репо (не в worktree) — это тоже ок, ветка уже создана.
- Все команды — из `wookiee-hub/` или корня репозитория.
- Commit message format: `<type>(<scope>): <subject>` без emoji. Trailer:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- Перед финальным `/ship` — убедись, что все 5 коммитов на месте через `git log --oneline main..HEAD`.
- В `/ship` использовать `gh pr create` с base = main, head = `feat/ds-v2-wave-1-polish-round3`.

Удачи. Спрашивать у юзера разрешения по ходу не нужно — он уже его дал.
