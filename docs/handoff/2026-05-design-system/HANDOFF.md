# HANDOFF: Wookiee Hub Design System v2 → Claude Code

> Этот документ — единственный источник правды для миграции Hub на DS v2.
> Прочитай его целиком перед тем как трогать код. Все ответы должны быть ниже.

---

## Контекст

**Wookiee Hub** — внутренний инструмент команды бренда женского белья Wookiee
(домен `hub.os.wookiee.shop`). Стек: **Vite + React 19 + React Router 7 + Tailwind v4 + Supabase + Zustand**.

**Сейчас** в Hub три разных UI-слоя (выявлено в `UI_AUDIT.md`):
1. Hub purple/dark — `/login`, `/operations`, `/community`, `/analytics`. Inter, primary `#7B2CE5`.
2. Catalog stone — `/catalog/*`. DM Sans + Instrument Serif. **Целевая DS на 80-90%.**
3. CRM kit — `/influence/*`. Нужно мигрировать.

**Задача:** привести весь Hub к единой Design System v2 (stone + DM Sans + Instrument Serif + dark theme).

---

## Что в пакете

| Файл                              | Назначение                                                       |
|-----------------------------------|------------------------------------------------------------------|
| `DESIGN_SYSTEM.md`                | **Главный источник правды.** Принципы, токены, компоненты, паттерны, антипаттерны, чеклист |
| `wookiee_ds_v2_foundation.jsx`    | UX-эталон: Foundation, Atoms, Forms, Data display, Charts, Layout, Overlays, Feedback. Light+Dark theme работают |
| `wookiee_ds_v2_patterns.jsx`      | UX-эталон: Kanban (DnD + detail drawer), Calendar (DnD событий), Comments thread, Notifications, Activity feed, Inbox, Theme demo |
| `BRIEF_hub_redesign.md`           | План миграции по волнам (Wave 1-5) и работа со существующим кодом |
| `HANDOFF.md`                      | Этот файл                                                        |

---

## Что НУЖНО сделать (acceptance criteria)

### A) Token system

Создать в `app/styles/tokens.css` (или эквиваленте) семантические CSS-переменные с двумя темами через `[data-theme='dark']`. Точное содержимое см. в **DESIGN_SYSTEM.md → раздел 12 «Подготовка к dark theme»**.

Создать `@utility` обёртки:
- `bg-surface`, `bg-surface-muted`, `bg-elevated`, `bg-page`
- `text-primary`, `text-secondary`, `text-muted`, `text-label`
- `border-default`, `border-strong`

### B) Перевод компонентов из артефакта в реальные

В артефактах `dark:` префиксы используются напрямую (`bg-white dark:bg-stone-900`). **В проде** — заменить на семантические утилиты:

```diff
- className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800"
+ className="bg-surface border border-default"

- className="text-stone-900 dark:text-stone-50"
+ className="text-primary"

- className="text-stone-500 dark:text-stone-400"
+ className="text-muted"
```

**Это обязательно для всех новых компонентов.** Не копируй артефакт «как есть» — переписывай через семантические токены.

### C) ThemeProvider

Создать `ThemeProvider` через React Context + Zustand store + persist в localStorage. Тема добавляет атрибут `data-theme` на `<html>`. Содержимое — см. DESIGN_SYSTEM.md раздел 12.

Default тема — **light**, не dark (как сейчас).

### D) Компоненты ядра — структура

Создать в `app/components/ui/`:

```
ui/
├── primitives/        # atoms: Button, Input, Checkbox, Radio, Toggle, Slider, Badge, StatusBadge, LevelBadge, Chip, Avatar, AvatarGroup, ColorSwatch, ProgressBar, Ring, Tooltip, Skeleton, Kbd, Tag
├── forms/             # FieldWrap, TextField, NumberField, SelectField, MultiSelectField, TextareaField, DatePicker, TimePicker, Combobox, FileUpload, ColorPicker
├── data/              # StatCard, DataTable, GroupedTable, Pagination, BulkActionsBar, TreeView
├── charts/            # Multi-series Line, Stacked Bar, Combo, Donut, Gauge, Funnel, Calendar Heatmap, Sparkline + chartTokens, makeRichTooltip helper
├── layout/            # Tabs, Breadcrumbs, Stepper, PageHeader, Sidebar
├── overlays/          # Modal, Drawer, Popover, DropdownMenu, ContextMenu, CommandPalette
├── feedback/          # Toast, Alert, EmptyState
└── patterns/          # Kanban (с @dnd-kit), Calendar (с @dnd-kit), Comments thread, Notifications panel, Activity feed, Inbox
```

Каждый компонент — отдельный файл с TypeScript типами (если проект на TS). Экспортировать через `index.ts`.

### E) DnD на @dnd-kit

В артефактах Kanban и Calendar используют **нативный HTML5 drag-and-drop** (для совместимости с artifact mode). **В проде заменить на `@dnd-kit/core` + `@dnd-kit/sortable`.**

Причины:
- Touch support (планшеты)
- Accessibility (клавиатурный DnD)
- Ghost preview через React portal
- Auto-scroll при drag за пределы видимой области

**Поведение должно остаться ровно как в артефакте:**
- При drag: opacity 30% + rotate 1° + scale 95%
- При hover-over target: ring-2 + translate-y -0.5
- Drop zone подсвечивается ring + bg
- WIP-лимит overflow → красный badge

### F) Графики

Создать `chartTokens` хук, возвращающий объект с цветами в зависимости от текущей темы. Точное содержимое токенов — см. артефакт `wookiee_ds_v2_foundation.jsx` (`chartTokens` const в начале файла).

Создать helper `makeRichTooltip(tk, opts)` — он же из артефакта. Поддерживает `showTotal` и `showPercent`.

Использовать **контекстные миксы** (`pnl`, `channels`) везде где смысловая связь подразумевается. Не подбирать цвета каждый раз.

Sparklines — **только** компактный формат `h-10 w-20` рядом с числом, не на всю ширину.

### G) GroupedTable

Перенести компонент из артефакта в `ui/data/GroupedTable.tsx`. Сделать его generic'ом:

```tsx
type GroupedTableProps<TItem, TGroup> = {
  groups: Group<TItem, TGroup>[];
  columns: ColumnDef<TItem>[];
  groupColumns?: ColumnDef<TGroup>[]; // верхний row header
  onItemUpdate?: (itemId, patch) => void;
  // ...
};
```

Применить в первую очередь в **«Планирование поставок»** — оно уже использует похожий паттерн в `wookiee_supply_planning_v1.jsx`. Заменить на универсальный компонент.

### H) Миграция

Не переписывай весь Hub разом. Иди по волнам из `BRIEF_hub_redesign.md`:

1. **Wave 1** — Foundation (tokens, theme provider, layout shell, sidebar, topbar)
2. **Wave 2** — Каталог (там DS уже на 80-90%, нужно дотянуть до 100%)
3. **Wave 3** — Влияние (CRM kit) и Аналитика
4. **Wave 4** — Операции
5. **Wave 5** — Контент (Kanban + Calendar)

В каждой волне:
- Сначала создаёшь компоненты которые понадобятся
- Потом мигрируешь страницы
- В конце волны — выбрасываешь старые стили из удалённых страниц

### I) Acceptance — до коммита

- [ ] Все компоненты используют семантические токены, никакого `dark:bg-stone-900` напрямую в JSX
- [ ] ThemeProvider работает, переключение мгновенное
- [ ] Все графики — мульти-цветная палитра, контекстные миксы где применимо, rich tooltips
- [ ] Sparklines — компактные (h-10 w-20)
- [ ] Kanban DnD на @dnd-kit, поведение совпадает с артефактом
- [ ] Calendar DnD событий работает в month и week
- [ ] Нет хардкода цветов вне `tokens.css` и `chartTokens.ts`
- [ ] Чеклист из DESIGN_SYSTEM.md раздел 10 пройден на каждом экране

---

## Что НЕ делать

❌ **Не делай UI-стили в Tailwind напрямую через `stone-*`/`white`/`black`.** Только через семантические утилиты или CSS-переменные.

❌ **Не используй HTML5 нативный DnD в проде.** Только @dnd-kit.

❌ **Не вводи новые цвета вне палитры.** Если кажется что нужен новый — обсуди с Даней до того как добавить.

❌ **Не переписывай каталог под предлогом «DS v2».** Каталог уже работает на 80-90%. Дотягивай точечно.

❌ **Не делай отдельные стили для отдельных модулей.** Hub — единый.

❌ **Не подключай дополнительные UI-библиотеки** (Radix, Headless UI, Mantine, MUI). Всё уже в DS.

❌ **Не делай SQL миграции в этом раунде.** Это отдельный этап. Сначала UI.

❌ **Не запускай прод-деплой пока Wave 1 не закрыта целиком.** Темно-светлая тема должна работать на каждой странице.

---

## Что делать когда непонятно

**Уточняй у Дани, не угадывай по:**

- Бизнес-логике процессов (статусы моделей, права на действие, флоу заказа)
- Permissions / ролям пользователей (CEO / COO / product / marketplace / finance / warehouse / designer)
- Внешним интеграциям (МойСклад, WB API, Ozon API)
- Структуре БД (имена таблиц, поля, foreign keys)
- Приоритетам в плане миграции (если волны не закрываются за разумное время)

---

## Слепые зоны DS v2 (что я НЕ покрыл — обсуди до начала)

1. **Mobile / responsive** — артефакты под desktop. Мобильные адаптации (sidebar → hamburger, таблицы → cards, kanban → горизонтальный скролл) **не спроектированы**. Решение: проектировать по факту, по каждому модулю отдельно.

2. **Real-time** — Comments, Activity, Notifications в артефактах работают на mock-данных. Реалтайм через Supabase realtime channels — отдельный архитектурный этап.

3. **Permissions UI** — нет отдельного паттерна для «у тебя нет прав». Сейчас просто скрываются кнопки. Нужен ли явный hint? Обсудить.

4. **Onboarding / empty states первого захода** — есть EmptyState компонент, но не продумано «впервые в Hub» (туры, hints, welcome-карточки).

5. **Bulk-операции** — есть BulkActionsBar для таблиц. Нет паттерна для bulk DnD в Kanban (выбрать несколько → перенести в колонку). Обсудить если понадобится.

6. **Версионирование изменений** — Activity показывает changes, но нет UI для отката изменений. Нужен ли?

7. **Print / экспорт страниц** — нет проектирования print-стилей. Если нужен печатный отчёт — отдельный этап.

8. **Уведомления вне Hub** — email, Telegram, push. UI panel есть, integration — отдельная задача.

---

## Контакт

Если что-то непонятно или появляются вопросы по архитектуре — пиши Дане в чат проекта.
**Не делай предположений по бизнес-логике без подтверждения.**

---

*Wookiee Hub DS v2 · Май 2026*
