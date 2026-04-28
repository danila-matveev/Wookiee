# Influencer CRM — Frontend

## Что это

React + Vite + TypeScript SPA поверх Tailwind 4, потребляющая 21 endpoint BFF
сервиса `services/influencer_crm`. Phase 4 проекта Influencer CRM (см.
`docs/superpowers/plans/2026-04-28-influencer-crm-p4-frontend.md`).

Stack: React 18, TanStack Query, react-router 7, react-hook-form + Zod,
@dnd-kit (kanban), Headless UI (drawers/menus), Lucide иконки. Стили — Tailwind 4
с `@theme` поверх `tokens.css` (lift-as-is из прототипа).

## Экраны

1. **Блогеры** (`/bloggers`) — таблица с курсорной пагинацией, фильтры по тегам/каналу/marketplace, drawer редактирования, отдельный экран профиля `/bloggers/:id` с тайм-лайном интеграций.
2. **Интеграции** (`/integrations`) — kanban по `IntegrationStage` (planned → completed) с drag-and-drop через @dnd-kit, optimistic stage updates.
3. **Календарь** (`/calendar`) — месячная сетка с публикациями, фильтр по маркетплейсу.
4. **Брифы** (`/briefs`) — список брифов с draft/published статусом, drawer редактирования сценария.
5. **Срезы** (`/slices`) — отчёты по тегам/каналам/маркетингу с агрегатами CPM/ROI.
6. **Продукты** (`/products`) — список SKU, halo-strip склеек, profile с историей упоминаний.
7. **Поиск** (`/search`) — глобальный поиск по блогерам и интеграциям, debounced ввод.

## Локальный dev

Нужны два терминала.

**Бэкенд (порт 8082):**

```bash
bash services/influencer_crm/scripts/run_dev.sh
```

**Фронт (порт 5173):**

```bash
bash services/influencer_crm_ui/scripts/run_dev.sh
# или вручную:
cd services/influencer_crm_ui
pnpm install --frozen-lockfile
pnpm dev
```

Скрипт `run_dev.sh` создаёт `.env.local` из шаблона при первом запуске.
В `.env.local` нужно положить `VITE_API_KEY` — то же значение, что
`INFLUENCER_CRM_API_KEY` в `sku_database/.env`.

`VITE_API_BASE_URL=/api` — Vite dev-server проксирует `/api` на `http://127.0.0.1:8082`.

## Тесты

```bash
pnpm test         # vitest watch mode
pnpm test:run     # vitest run, 19 unit-тестов
pnpm e2e          # Playwright, 4 golden paths против mocked-API
pnpm lint         # biome check
pnpm typecheck    # tsc -b
```

- **Unit (vitest + MSW)** — purity-функции (cursor, tag-format), хуки TanStack
  Query с замоканной сетью через MSW, ETag/304-кеш.
- **E2E (Playwright)** — 4 спеки (bloggers list, integrations kanban DnD,
  briefs CRUD, search). Поднимают приложение в режиме `?mock=1`, BFF не нужен.

## Сборка

```bash
pnpm build      # tsc + vite build → dist/
pnpm preview    # local preview на :4173
```

`dist/index.html` ~0.75 KB, `dist/assets/*.js` ~528 KB (gzip 164 KB),
`dist/assets/*.css` ~35 KB (gzip 7 KB).

## Архитектура

```
src/
├── lib/        api client (X-API-Key + ETag), cursor utility
├── api/        typed endpoint wrappers (one file per resource)
├── hooks/      TanStack Query hooks (one file per resource)
├── ui/         design-system primitives (Button, Drawer, KpiCard, ...)
├── layout/     AppShell, Sidebar, TopBar, PageHeader
├── routes/     7 экранов, по папке на route
└── styles/     tokens.css (verbatim from prototype) + globals.css (Tailwind 4 @theme)
```

## Дизайн-контракт

Источник истины — `prototype.html` в
`.superpowers/brainstorm/4161-1777122150/content/`. Все CSS-vars в
`src/styles/tokens.css` лифтнуты оттуда as-is. При визуальных изменениях —
сначала правится прототип, потом подтягиваются токены, никак не наоборот.

## Известные ограничения / отложено

Backend-расширения нужны:

- `BloggerOut` (list) не содержит `channels_count`/`integrations_count` →
  таблица показывает `—`. Нужен агрегат через `v_blogger_totals` MV.
- `IntegrationOut` (list) не содержит `blogger_handle` → kanban-карточки
  показывают `Блогер #N`. Нужна денормализация handle на list endpoint
  или bulk-blogger lookup.
- Роутер `briefs` неполон: нет `GET /briefs` (list), `GET /briefs/:id`
  (detail с status), `PATCH /briefs/:id`. UI работает через MSW; на проде
  потребует расширения роутера.
- `/products/:id` не возвращает `substitute_articles[]` → halo-strip
  отрисован как placeholder.
- `/integrations` не принимает `tag_id` фильтр (только `marketer_id` /
  `marketplace` / `stage_in` / `date_from` / `date_to`).

UI follow-ups:

- Канал `rutube` отсутствует в `PlatformPill` (визуал-only).
- Toast-уведомления отложены — drawers показывают inline-ошибки.
- Combobox для `blogger_id` в IntegrationEditDrawer — пока numeric input.
  В follow-up можно добавить downshift/cmdk.

Все пункты будут собраны в `docs/superpowers/plans/2026-04-28-influencer-crm-p3-followups.md`.

## QA1 (mandatory per roadmap)

После T22 запускается QA1 пакет:

- `gstack-qa` — exploratory + bug-fix loop
- `gstack-design-review` — дизайнерский визуальный аудит
- `dogfood` — систематическое прохождение пользовательских флоу
- Playwright по 7 golden paths из roadmap (по одному на экран)

Без зелёного QA1 фронт не считается готовым к продовому подключению.
