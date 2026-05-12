# Wookiee Hub · Redesign Brief v2

> Контекст и план миграции Hub на Design System v2.
> Этот документ читают вместе с `DESIGN_SYSTEM.md` и `HANDOFF.md`.

---

## Контекст

**Wookiee Hub** — внутренний инструмент команды бренда женского белья
~400M ₽ оборот / год · 18 человек · полностью удалённо
домен `hub.os.wookiee.shop`

**Задача:** заменить разнородный UI на единый визуальный язык, работающий
в светлой и тёмной теме, поддерживающий все процессы команды
(каталог → производство → маркетплейсы → маркетинг → контент → аналитика).

**Что заменяется:** Google Sheets, Notion, частично Bitrix24.

---

## Стек

```
Frontend:   Vite + React 19 + React Router 7
Styling:    Tailwind CSS v4 (с @theme tokens)
Icons:      lucide-react
Charts:     recharts
DnD:        @dnd-kit/core + @dnd-kit/sortable
State:      Zustand (с persist для theme и user prefs)
Backend:    Supabase (Auth + Postgres + Realtime + Storage)
i18n:       Не нужно — только русский
```

---

## UI-аудит (исходное состояние)

В Hub сейчас **три разных визуальных слоя** (выявлено в `UI_AUDIT.md`):

| Слой       | Где                                            | Стиль                              | Действие             |
|------------|------------------------------------------------|------------------------------------|----------------------|
| Hub purple/dark | `/login`, `/operations`, `/community`, `/analytics` | Inter, primary `#7B2CE5`, dark default | **Мигрировать** на DS v2 |
| Catalog stone | `/catalog/*`                                  | DM Sans + Instrument Serif, stone, light | **Дотянуть** до 100% (сейчас ~80-90%) |
| CRM kit    | `/influence/*`                                 | Свой стиль                         | **Мигрировать** на DS v2 |

---

## План миграции по волнам

### Wave 1 · Foundation (1-2 недели)

**Цель:** заложить инфраструктуру DS v2.

- [ ] Установить зависимости: `@dnd-kit/core`, `@dnd-kit/sortable`, `recharts` (если нет)
- [ ] Создать `app/styles/tokens.css` с CSS-переменными light/dark + `@theme` блоком (см. DESIGN_SYSTEM.md раздел 12)
- [ ] Создать семантические `@utility` обёртки (`bg-surface`, `text-primary`, etc)
- [ ] Создать `ThemeProvider` через Zustand store + persist в localStorage
- [ ] Перенести шрифты (DM Sans + Instrument Serif) через локальные `@font-face` или Google Fonts CDN
- [ ] Создать `app/components/ui/primitives/` — все atoms из артефакта `wookiee_ds_v2_foundation.jsx`, переписанные на семантические токены
- [ ] Создать `app/components/ui/layout/` — Sidebar, TopBar, PageHeader, Tabs (3 варианта), Breadcrumbs, Stepper
- [ ] Тестовая страница `/design-system-preview` с переключателем темы — для проверки

**Acceptance:** компонент `Button` (со всеми вариантами и размерами) рендерится одинаково в light и dark, `data-theme='dark'` на html переключает всё дерево.

### Wave 2 · Каталог (2-3 недели)

**Цель:** довести каталог до 100% соответствия DS v2.

- [ ] Заменить локальные карточки моделей на новый `Card` + `PageHeader` + `Tabs (underline)`
- [ ] Перенести формы атрибутов на `FieldWrap` + `TextField` / `SelectField` / `MultiSelectField` / etc
- [ ] Заменить таблицу SKU на новый `DataTable`
- [ ] Внедрить `BulkActionsBar` для массовых действий
- [ ] Добавить `CommandPalette` (⌘K) для глобального поиска по моделям/цветам
- [ ] Внедрить `Toast` через context-провайдер
- [ ] **Каждый экран** прогнать через чеклист из DESIGN_SYSTEM.md раздел 10

**Acceptance:** клик от `/catalog` → модель → атрибуты → SKU работает в обоих темах без визуальных артефактов.

### Wave 3 · Аналитика и графики (2 недели)

**Цель:** все дашборды на новой палитре.

- [ ] Создать `app/components/ui/charts/` — `chartTokens` хук, `makeRichTooltip` helper
- [ ] Перенести существующие компоненты графиков из `wookiee_rnp_dashboard_v3.jsx` на новые токены
- [ ] Внедрить `MultiSeriesLine` (P&L разрез — 5 серий разными цветами)
- [ ] Внедрить `StackedBar` (бюджет маркетинга по 6 каналам)
- [ ] Внедрить `ComboChart` (Bar выручки + Line маржинальности)
- [ ] Заменить sparklines на компактный формат (h-10 w-20)
- [ ] Внедрить `Donut` с центральным значением, `Gauge`, `Funnel`, `CalendarHeatmap`

**Acceptance:** все графики реагируют на смену темы без перезагрузки. Палитра одинаковая на всех дашбордах.

### Wave 4 · Производство и операции (2 недели)

**Цель:** Планирование поставок + операционные таблицы.

- [ ] Перенести универсальный `GroupedTable` из артефакта в `ui/data/`
- [ ] Заменить таблицу в `wookiee_supply_planning_v1.jsx` на новый `GroupedTable`
- [ ] Цветные индикаторы cover days (red <30 / amber <60 / emerald норма / blue >365)
- [ ] Edit-cells для quantity (`bg-blue-50/30 focus:bg-white`)
- [ ] `OrderHeaderCard` — карточка заказа с TargetDaysSlider
- [ ] Перенести модули `/operations` на новую DS

**Acceptance:** «Планирование поставок» работает идентично текущей версии, но в DS v2 + dark theme.

### Wave 5 · Контент-завод (Kanban + Calendar) (2-3 недели)

**Цель:** Workflow для команды контента.

- [ ] Создать `app/components/ui/patterns/Kanban.tsx` на @dnd-kit
- [ ] Колонки с WIP-лимитами, accent-цветами, action-buttons
- [ ] Карточки с обложкой, тегом, priority, assignee, прогрессом подзадач, метаданными
- [ ] Detail Drawer при клике (560px справа) — header, properties, description, subtasks, attachments, comments, activity
- [ ] Создать `app/components/ui/patterns/Calendar.tsx` на @dnd-kit для DnD событий
- [ ] Month view (6×7 grid, события inline до 3 + «ещё N»)
- [ ] Week view (часовая сетка 8:00–21:00, события abs-positioned)
- [ ] Drag в month — изменяет дату; drag в week — изменяет дату+время
- [ ] Event Detail Popover при клике
- [ ] Создать `app/components/ui/patterns/CommentsThread.tsx`
- [ ] Создать `app/components/ui/patterns/NotificationsPanel.tsx` (slide-out right)
- [ ] Создать `app/components/ui/patterns/ActivityFeed.tsx`
- [ ] Создать `app/components/ui/patterns/Inbox.tsx`

**Acceptance:** Команда контента может вести задачи в Kanban от Идеи до Опубликовано, планировать съёмки в Calendar и видеть @-mentions в Inbox.

---

## Real-time (отдельный этап после Wave 5)

После завершения UI-миграции — добавить Supabase realtime channels:

- Comments — push новых комментов через WebSocket
- Activity feed — auto-update при изменениях
- Notifications — bell badge с unread count
- Kanban — multi-user коллаборация (показ кто на доске сейчас + соседский DnD)

Это **отдельный архитектурный этап**, не влезает в DS v2 миграцию.

---

## Что НЕ делается в этом раунде

- ❌ Mobile-адаптация (артефакты под desktop)
- ❌ Touch-DnD на планшетах (нативно через @dnd-kit когда настроим)
- ❌ Print-стили
- ❌ Email-уведомления, Telegram-бот
- ❌ Tours / onboarding для новых пользователей
- ❌ Версионирование с откатами
- ❌ SQL-миграции (отдельный раунд после UI)

---

## Файлы-эталоны

| Файл                                  | Что внутри                                              |
|---------------------------------------|---------------------------------------------------------|
| `DESIGN_SYSTEM.md`                    | Главный source of truth                                 |
| `HANDOFF.md`                          | Промт для Claude Code: как принимать пакет             |
| `wookiee_ds_v2_foundation.jsx`        | Foundation, Atoms, Forms, Data, Charts, Layout, Overlays, Feedback |
| `wookiee_ds_v2_patterns.jsx`          | Kanban с DnD + detail, Calendar с DnD, Comments, Notifications, Activity, Inbox |
| `wookiee_matrix_mvp_v4.jsx`           | Эталон сложного модуля каталога                         |
| `wookiee_supply_planning_v1.jsx`      | Эталон GroupedTable                                     |
| `wookiee_rnp_dashboard_v3.jsx`        | Эталон сложного дашборда с графиками                    |
| `UI_AUDIT.md`                         | Аудит текущего состояния Hub                            |

---

*Версия: 2.0 · Май 2026*
