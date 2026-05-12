# Wookiee Hub · UI Audit v0.2

> Аудит текущего UI Hub перед миграцией на **Design System v2**.
> Читать вместе с `docs/handoff/2026-05-design-system/{BRIEF_hub_redesign,DESIGN_SYSTEM,HANDOFF}.md`.
> Версия выровнена с DS v2 (май 2026): dark theme — first-class, фонты DM Sans + Instrument Serif, стек Vite + RR7 + Tailwind v4.

---

## Резюме

Hub сейчас содержит **три параллельных визуальных слоя**, расходящихся по палитре, шрифтам и плотности:

| Слой              | Зона                                                    | Стиль                                              | Действие в DS v2          |
|-------------------|---------------------------------------------------------|----------------------------------------------------|---------------------------|
| **Hub purple/dark**   | `/login`, `/operations/*`, `/community/*`, `/analytics/rnp` | Inter, primary `#7B2CE5`, dark default, shadcn-токены | **Мигрировать** на DS v2  |
| **Catalog stone**     | `/catalog/*` (через `.catalog-scope`)                  | DM Sans + Instrument Serif, stone, light only      | **Достроить** до 100% DS v2 (≈80–90% соответствия уже сейчас) |
| **CRM kit**           | `/influence/*`                                          | Локальный CRM-набор (`components/crm/ui/*`)        | **Мигрировать** на DS v2, после — удалить `components/crm/` |

Цель — единый стек примитивов (`app/components/ui/`) с CSS-vars (`bg-surface`, `text-primary`, …), переключаемый light/dark через `data-theme` на `<html>`.

---

## Карта модулей

Ниже — все маршруты из [src/router.tsx](../src/router.tsx) сгруппированы по разделам.
Колонки:

- **Layout** — какой shell оборачивает (CatalogLayout / AppShell / standalone).
- **Слой** — текущая визуальная привязка.
- **Состояние** — субъективная оценка соответствия целевой DS v2 (0–100%).
- **Сложность** — миграционная сложность (S — атомы и тексты, M — формы/таблицы, L — сложные виджеты/DnD/charts).
- **Бизнес-критичность** — насколько часто/важно используется (low/med/high).
- **Зависимости** — что блокирует миграцию модуля.
- **Волна** — DS v2 wave (1–5).

### Auth

| Маршрут   | Layout    | Слой                | Состояние | Сложность | Крит. | Зависимости                                | Волна |
|-----------|-----------|---------------------|-----------|-----------|-------|--------------------------------------------|-------|
| `/login`  | standalone| Hub purple/dark     | 0%        | S         | high  | atoms (Button, Field), Logo `Wookiee` italic | 1     |

### Operations (`/operations/*`)

| Маршрут                  | Layout   | Слой              | Состояние | Сложность | Крит. | Зависимости                                            | Волна |
|--------------------------|----------|-------------------|-----------|-----------|-------|--------------------------------------------------------|-------|
| `/operations/tools`      | AppShell | Hub purple/dark   | 10%       | M         | high  | DataTable, FilterChips, Toast, command palette         | 4     |
| `/operations/activity`   | AppShell | Hub purple/dark   | 10%       | M         | high  | DataTable (expand-row), Filters, BulkActionsBar        | 4     |
| `/operations/health`     | AppShell | Hub purple/dark   | 10%       | M         | med   | StatusBadge, KPI/StatCard, sparklines                   | 4     |

### Community (`/community/*`)

| Маршрут                  | Layout   | Слой              | Состояние | Сложность | Крит. | Зависимости                                | Волна |
|--------------------------|----------|-------------------|-----------|-----------|-------|--------------------------------------------|-------|
| `/community/reviews`     | AppShell | Hub purple/dark   | 10%       | M         | med   | DataTable, Drawer, Tabs (underline), Tag   | 4     |
| `/community/questions`   | AppShell | Hub purple/dark   | 10%       | M         | med   | DataTable, Drawer                          | 4     |
| `/community/answers`     | AppShell | Hub purple/dark   | 10%       | M         | med   | DataTable, RichTextEditor (light)          | 4     |
| `/community/analytics`   | AppShell | Hub purple/dark   | 10%       | L         | med   | Donut, BarChart, MultiSeriesLine, Funnel    | 3     |

### Influence (`/influence/*`)

| Маршрут                       | Layout   | Слой         | Состояние | Сложность | Крит. | Зависимости                                                                        | Волна |
|-------------------------------|----------|--------------|-----------|-----------|-------|------------------------------------------------------------------------------------|-------|
| `/influence/bloggers`         | AppShell | CRM kit      | 5%        | L         | high  | DataTable, Drawer (560px), Tabs, FieldWrap, MultiSelectField, Avatar, Tag           | 5     |
| `/influence/integrations`     | AppShell | CRM kit      | 5%        | L         | high  | **Kanban (@dnd-kit)** + DetailDrawer, CommentsThread, ActivityFeed                  | 5     |
| `/influence/calendar`         | AppShell | CRM kit      | 5%        | L         | high  | **Calendar (@dnd-kit)** month+week, EventDetailPopover                              | 5     |

### Analytics (`/analytics/*`)

| Маршрут            | Layout   | Слой              | Состояние | Сложность | Крит. | Зависимости                                                                          | Волна |
|--------------------|----------|-------------------|-----------|-----------|-------|--------------------------------------------------------------------------------------|-------|
| `/analytics/rnp`   | AppShell | Hub purple/dark   | 20%       | L         | high  | `chartTokens` hook, `makeRichTooltip`, MultiSeriesLine, StackedBar, ComboChart, Donut, Funnel, sparklines | 3     |

### Catalog (`/catalog/*`) — все маршруты под `CatalogLayout` + `.catalog-scope`

| Маршрут                                  | Слой           | Состояние | Сложность | Крит. | Зависимости                                                | Волна |
|------------------------------------------|----------------|-----------|-----------|-------|------------------------------------------------------------|-------|
| `/catalog/matrix`                        | Catalog stone  | 85%       | L         | high  | ModelCardModal (overlay), Tabs, FieldWrap, Drawer, BulkActionsBar | 2     |
| `/catalog/colors`                        | Catalog stone  | 85%       | M         | high  | DataTable, ColorChip, MultiSelectField                      | 2     |
| `/catalog/artikuly`                      | Catalog stone  | 85%       | M         | high  | DataTable, FilterChips, BulkActionsBar                      | 2     |
| `/catalog/tovary`                        | Catalog stone  | 85%       | M         | high  | DataTable, ImagePreview                                     | 2     |
| `/catalog/skleyki`                       | Catalog stone  | 80%       | M         | med   | GroupedTable (light)                                        | 2     |
| `/catalog/semeystva-cvetov`              | Catalog stone  | 85%       | M         | med   | DataTable, ColorFamilyChip                                  | 2     |
| `/catalog/upakovki`                      | Catalog stone  | 85%       | S         | low   | DataTable, FieldWrap                                        | 2     |
| `/catalog/kanaly-prodazh`                | Catalog stone  | 85%       | S         | low   | DataTable                                                   | 2     |
| `/catalog/sertifikaty`                   | Catalog stone  | 85%       | M         | low   | DataTable, FileUpload                                       | 2     |
| `/catalog/references/kategorii`          | Catalog stone  | 85%       | S         | med   | DataTable                                                   | 2     |
| `/catalog/references/kollekcii`          | Catalog stone  | 85%       | S         | med   | DataTable                                                   | 2     |
| `/catalog/references/fabriki`            | Catalog stone  | 85%       | S         | low   | DataTable                                                   | 2     |
| `/catalog/references/importery`          | Catalog stone  | 85%       | S         | low   | DataTable                                                   | 2     |
| `/catalog/references/razmery`            | Catalog stone  | 85%       | S         | low   | DataTable                                                   | 2     |
| `/catalog/references/statusy`            | Catalog stone  | 85%       | S         | low   | DataTable, StatusBadge                                      | 2     |
| `/catalog/__demo__`                      | Catalog stone  | 90%       | S         | low   | (демо-страница, можно удалить после Wave 2)                 | 2     |

> Цифра «85%» по каталогу — экспертная оценка по итогам редизайна 2026-04..05. Точную дельту замерим на стадии Wave 2 при прогоне чеклиста DS v2 §10.

---

## Разделы вне карты (нужно решить отдельно)

| Найдено                                          | Где                                                                                          | Что с этим             |
|--------------------------------------------------|----------------------------------------------------------------------------------------------|------------------------|
| `src/pages/agents/`                              | каталог страниц без записи в роутере                                                          | удалить (orphan)       |
| `src/components/agents/*` (`runs-table`, `tools-table`, `run-status-badge`) | примитивы старого «agents-кита»                                                | удалить (orphan)       |
| `src/components/shared/change-indicator.tsx`     | неиспользуется в текущих страницах                                                            | проверить и удалить    |
| `src/components/shared/progress-bar.tsx`         | неиспользуется                                                                                | проверить и удалить    |
| `src/components/marketing/*`                     | страницы `/marketing/*` отсутствуют в роутере, но компоненты лежат                            | подтвердить со стейкхолдером, либо удалить, либо запланировать на отдельную волну |
| `src/components/crm/{layout,ui}/*`               | используется только `/influence/*`                                                            | удалить после Wave 5   |
| shadcn-примитивы `src/components/ui/*` (`button`, `dialog`, `popover`, `command`, …) | `/influence` + `/operations`                                                                  | заменить на `app/components/ui/primitives/*` (DS v2), удалить shadcn-обёртки   |
| `src/index.css` (Inter, `:root` + `.dark` + `.catalog-scope` + CRM-aliases) | глобальные стили                                                                              | переписать на `app/styles/tokens.css` с `@theme` блоком (DS v2 §12) |

---

## Волны миграции (DS v2)

Ниже — то же самое, что в `BRIEF_hub_redesign.md`, но с привязкой к найденным модулям.

### Wave 1 · Foundation (1–2 нед)
- Tailwind v4 `@theme` + CSS-vars (light/dark), семантические `@utility` обёртки
- ThemeProvider (Zustand persist) + `data-theme` на `<html>` (заменить `dark`-class в [components/layout/app-shell.tsx](../src/components/layout/app-shell.tsx))
- Шрифты: DM Sans (UI), Instrument Serif (заголовки/«Wookiee» italic), убрать Inter Variable
- `app/components/ui/primitives/` — Button, IconButton, Badge, Tag, StatusBadge, Avatar, Card, Field, Input, Select, …
- `app/components/ui/layout/` — Sidebar, TopBar, PageHeader, Tabs (3 варианта), Breadcrumbs, Stepper
- Тестовая страница `/design-system-preview` с переключателем темы
- `/login` мигрирует здесь же как первая end-to-end проверка

**Acceptance:** Button рендерится одинаково в light/dark, переключение `data-theme='dark'` на `<html>` мгновенно перекрашивает всё дерево.

### Wave 2 · Catalog (2–3 нед)
- Все 16 экранов `/catalog/*` доводятся до 100% DS v2
- Удалить `.catalog-scope` (после Wave 1 stone-токены — это и есть default light)
- Заменить локальные карточки моделей на DS-карточки + ModelCardModal-overlay
- Перейти на `FieldWrap` + `*Field` для атрибутов, `DataTable` для SKU
- Внедрить `BulkActionsBar`, `CommandPalette` (⌘K), `Toast`
- Прогнать каждый экран по чеклисту `DESIGN_SYSTEM.md §10`

**Acceptance:** клик `/catalog → модель → атрибуты → SKU` работает в обеих темах без артефактов.

### Wave 3 · Аналитика и графики (2 нед)
- `app/components/ui/charts/` + `chartTokens` хук + `makeRichTooltip`
- Перенос `/analytics/rnp` со всеми графиками (`wookiee_rnp_dashboard_v3.jsx` — эталон)
- `/community/analytics` — Donut, Funnel, BarChart, MultiSeriesLine
- Sparklines (h-10 w-20), Donut с центром, Gauge, CalendarHeatmap

**Acceptance:** все графики реагируют на смену темы без перезагрузки, палитра единая на всех дашбордах.

### Wave 4 · Operations + Community (2 нед)
- `/operations/{tools,activity,health}` на DS v2: DataTable + Filter chips + Drawer + Toast + StatusBadge
- `/community/{reviews,questions,answers}` на DS v2: DataTable + Drawer + Tabs + RichTextEditor (light)
- Заменить shadcn-примитивы (`button`, `dialog`, `popover`, `command`, …) на DS-аналоги, удалить `components/ui/*` shadcn
- Перенести `GroupedTable` (если потребуется) в `app/components/ui/data/`

**Acceptance:** ни одна страница не использует Inter, shadcn-`button`, `:root` purple-токены или `.catalog-scope`.

### Wave 5 · Influence + паттерны (Kanban / Calendar / Inbox) (2–3 нед)
- `app/components/ui/patterns/Kanban.tsx` на @dnd-kit (колонки с WIP-лимитами, accent-цветами; карточки с обложкой/тегом/priority/assignee/прогрессом)
- `Detail Drawer` (560px справа) — header, properties, description, subtasks, attachments, comments, activity
- `app/components/ui/patterns/Calendar.tsx` — month view (6×7 + «ещё N»), week view (8:00–21:00, abs-positioned), DnD меняет дату/время
- `CommentsThread`, `NotificationsPanel`, `ActivityFeed`, `Inbox`
- Миграция `/influence/{bloggers,integrations,calendar}` на новые паттерны
- После — удалить `src/components/crm/`

**Acceptance:** команда контента ведёт задачи Kanban от «Идея» до «Опубликовано», планирует съёмки в Calendar, видит @-mentions в Inbox.

> Real-time через Supabase channels — отдельный архитектурный этап **после** Wave 5 (см. `BRIEF_hub_redesign.md` раздел Real-time).

---

## Найденные риски / точки внимания

1. **Hub default = dark.** В [components/layout/app-shell.tsx](../src/components/layout/app-shell.tsx) сейчас принудительно ставится `dark` class. На Wave 1 нужно перейти на `data-theme` атрибут (DS v2 §12) и ThemeProvider, иначе CatalogLayout продолжит подставлять `data-theme='light'` через `.catalog-scope`, а AppShell — `dark` через class — конфликт классов и переменных гарантирован.
2. **Catalog уже близко к DS v2.** Wave 2 — это в основном замена локальных компонентов на общие, а не редизайн. Большие просадки ждать только в `matrix` (ModelCardModal) и `skleyki` (GroupedTable).
3. **Influence держит свой UI-кит** (`components/crm/ui/*`). Миграцию делать атомарно по экрану — иначе появится 4-й параллельный слой.
4. **Charts ↔ palette.** `/analytics/rnp` написан до DS v2. Перенос на `chartTokens` потребует пересмотреть hard-coded цвета серий — ожидаются мелкие расхождения с эталонным дашбордом.
5. **Marketing pages.** Компоненты в `components/marketing/*` есть, маршрутов в роутере нет. До волн нужен ответ: они в плане или их удаляем.
6. **shadcn-примитивы.** `components/ui/{button,dialog,popover,command,…}` используются точечно (`/operations`, `/influence`). Удалять только после полной миграции зависимых страниц (Wave 4 для operations, Wave 5 для influence).

---

## Открытые вопросы

> Q1 (dark theme), Q2 (фонты), Q3 (стек) из v0.1 закрыты в DS v2. Оставшиеся:

- **Q4. Marketing-страницы:** запланировать отдельную волну или удалить компоненты `components/marketing/*`?
- **Q5. Удаление `.catalog-scope`:** оставить scope-обёртку до конца Wave 2 как safety net, или сразу выпилить с Wave 1?
- **Q6. shadcn-примитивы:** удалять `components/ui/*` параллельно с миграцией страницы или одной зачисткой в конце Wave 5?
- **Q7. ThemeProvider:** хранить тему per-user в Supabase (как usability prefs) или ограничиться localStorage через Zustand persist?
- **Q8. CommandPalette (⌘K):** глобальный (Wave 1) или после Wave 2 (когда наполнится поиск по моделям)?

---

## Источники

- [src/router.tsx](../src/router.tsx) — карта маршрутов
- [src/index.css](../src/index.css) — текущие глобальные токены (Inter + shadcn + `.catalog-scope`)
- [src/components/layout/app-shell.tsx](../src/components/layout/app-shell.tsx) — текущий ThemeStore (`dark` class)
- [docs/handoff/2026-05-design-system/BRIEF_hub_redesign.md](../../docs/handoff/2026-05-design-system/BRIEF_hub_redesign.md)
- [docs/handoff/2026-05-design-system/DESIGN_SYSTEM.md](../../docs/handoff/2026-05-design-system/DESIGN_SYSTEM.md)
- [docs/handoff/2026-05-design-system/HANDOFF.md](../../docs/handoff/2026-05-design-system/HANDOFF.md)

---

*Версия: v0.2 · 2026-05-09 · выровнено с DS v2*
