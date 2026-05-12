# Wookiee Hub · Design System v2

> Эта DS — единый визуальный язык всех модулей Hub.
> Light + Dark тема, полный набор компонентов и UX-паттернов.
> Эталонные артефакты: `wookiee_ds_v2_foundation.jsx` + `wookiee_ds_v2_patterns.jsx`.

---

## 1. Принципы

**Refined minimalism.** Стиль — Linear, Notion, Vercel, Stripe. Отказ от теней на статичных карточках, минимум декора, чистая типографика, осмысленный whitespace.

**Числа — главный контент.** В B2B-tooling (которым является Hub) 80% полезной информации — это цифры. Они получают `tabular-nums`, font-medium, иногда увеличенный кегль. Технические идентификаторы (SKU, баркоды, артикулы) — `font-mono text-xs`.

**Тон команды.** Серьёзный профессиональный, без эмоджи в UI. Юмор — допустим, но в копирайтинге, не в чипах.

**Один визуальный язык на весь Hub.** Каталог, маркетинг, аналитика, операции, контент — все в одной DS. Никаких отдельных стилей под отдельный модуль.

---

## 2. Цветовая палитра

### Базовая шкала — Tailwind `stone`

```
stone-50   #FAFAF9    Страница (light)
stone-100  #F5F5F4    Hover, лёгкие фоны
stone-200  #E7E5E4    Обводки (light)
stone-300  #D6D3D1    Усиленные обводки
stone-400  #A8A29E    Лейблы UPPERCASE, иконки муты
stone-500  #78716C    Подписи (light), muted
stone-600  #57534E    Дополнительный
stone-700  #44403C    Вторичный текст (light) / обводки strong (dark)
stone-800  #292524    Обводки (dark)
stone-900  #1C1917    Primary текст (light) / surface (dark)
stone-950  #0C0A09    Page bg (dark)
```

**Никаких** `gray`, `slate`, `zinc`, `neutral`. Только stone.

### Семантические цвета

```
Emerald  #059669    Success / "В продаже" / положительные тренды / маржа
Blue     #2563EB    Info / "Запуск" / основная аналитика
Amber    #D97706    Warning / "Выводим" / комиссии
Red/Rose #E11D48    Error / "Не выводится" / возвраты / срочное
Purple   #7C3AED    Brand accent (logo, активный nav, маркетинг)
Teal     #0D9488    Логистика, поставки
Indigo   #4F46E5    Доп. серия для multi-series
```

В тёмной теме все семантические цвета сдвигаются в более светлую сторону (`-300` оттенок) с pollным фоном `-950/40`.

---

## 3. Семантические токены (light + dark)

**В компонентах никогда не пиши `stone-900`/`stone-200` напрямую. Используй семантические классы.**

| Токен              | Light            | Dark            | Применение                        |
|--------------------|------------------|-----------------|-----------------------------------|
| `bg-page`          | stone-50/40      | stone-950       | Фон всей страницы                 |
| `bg-surface`       | white            | stone-900       | Карточки, модалки                 |
| `bg-surface-muted` | stone-50/60      | stone-900/40    | Sidebar, hover-зоны               |
| `bg-elevated`      | white            | stone-800       | Popover, dropdown                 |
| `text-primary`     | stone-900        | stone-50        | Основной текст                    |
| `text-secondary`   | stone-700        | stone-300       | Вторичный текст                   |
| `text-muted`       | stone-500        | stone-400       | Подписи под полями                |
| `text-label`       | stone-400        | stone-500       | UPPERCASE-лейблы                  |
| `border-default`   | stone-200        | stone-800       | Обводки карточек, дивайдеры       |
| `border-strong`    | stone-300        | stone-700       | Усиленные обводки                 |
| `hover-bg`         | stone-100        | stone-800       | Hover на кнопках/строках          |

**Реализация в Tailwind v4:** через `@theme` в CSS и кастомные утилиты — см. раздел «Подготовка к dark theme» внизу.

---

## 4. Типографика

**Шрифты:**
- **DM Sans** — UI (400, 500, 600). Body, labels, кнопки, числа.
- **Instrument Serif** — заголовки страниц и секций (italic для бренда `Wookiee`).

**Шкала:**

```
text-4xl + Instrument Serif italic    — Page title (h1)
text-3xl + Instrument Serif italic    — Page section title
text-2xl + Instrument Serif italic    — Card section title
text-base font-medium                 — Subsection title
text-sm                               — Body, default
text-xs                               — Метаданные, hint
text-[11px] uppercase tracking-wider  — UPPERCASE label
text-[10px] font-mono                 — Tech identifiers (SKU, barcode)
text-2xl tabular-nums font-medium     — KPI value
```

**Числовые правила:**
- Все числа — `tabular-nums` (моноширинные цифры)
- Технические значения — `font-mono text-xs`
- Денежные значения — `2 890 ₽` или `₽ 2 890` (но не `$2,890`)
- Большие — `4.82M ₽`, `2.3к шт`
- Процент после числа — без пробела: `12.4%`

---

## 5. Spacing scale

База — **4px**. Основные значения в Tailwind:

```
gap-1.5 / 6px    — Внутри bunches иконок и текста
gap-2   / 8px    — Внутри form fields
gap-3   / 12px   — Между элементами в строке
gap-4   / 16px   — Между карточками в гриде
gap-6   / 24px   — Между секциями страницы
gap-8   / 32px   — Между крупными блоками
```

Высота интерактивных элементов:
- Input / Select / Button (md): **32px** (`py-1.5 + text-sm`)
- Button (sm): **28px**
- Кнопка только-иконка: **28×28px** (`p-1.5`)
- Чекбокс / радио: **14×14px**
- Toggle: **20×36px**

---

## 6. Компоненты

### Atoms

| Компонент       | Варианты / props                                         |
|-----------------|----------------------------------------------------------|
| `Button`        | primary, secondary, ghost, danger, danger-ghost, success / xs, sm, md, lg / icon |
| `IconButton`    | active, danger, title                                    |
| `Input`         | icon, prefix, suffix, error                              |
| `Checkbox`      | indeterminate, label                                     |
| `Radio`         | label                                                    |
| `Toggle`        | on, disabled, label                                      |
| `Slider`        | min, max, suffix                                         |
| `Badge`         | emerald, blue, amber, red, purple, teal, gray / dot, icon, compact |
| `StatusBadge`   | statusId (через STATUS_MAP)                              |
| `LevelBadge`    | model (M, blue), variation (V, purple), artikul (A, orange), sku (S, emerald) |
| `Chip`          | onRemove                                                 |
| `Avatar`        | initials, color (stone/emerald/blue/amber/purple/rose/teal), size (xs/sm/md/lg), status (online/busy/offline) |
| `AvatarGroup`   | users, max                                               |
| `ColorSwatch`   | hex, size, label                                         |
| `ProgressBar`   | value, color (stone/emerald/blue/amber/red), label, compact |
| `Ring`          | value (0-1), size                                        |
| `Tooltip`       | text, position (top/bottom)                              |
| `Skeleton`      | className                                                |
| `Kbd`           | children                                                 |
| `Tag`           | color, icon, onClick                                     |

### Forms

| Компонент           | Особенности                                             |
|---------------------|---------------------------------------------------------|
| `FieldWrap`         | label uppercase + level (LevelBadge) + hint + error     |
| `TextField`         | mono для технических значений                           |
| `NumberField`       | suffix (₽, %, шт)                                       |
| `SelectField`       | options [{ id, nazvanie }]                              |
| `MultiSelectField`  | chips-toggles, не dropdown                              |
| `TextareaField`     | rows, no resize                                         |
| `DatePicker`        | single или range. Свой grid-календарь, без либ          |
| `TimePicker`        | dropdown 30-мин шаг                                     |
| `Combobox`          | input + filtered list                                   |
| `FileUpload`        | drag-n-drop zone + список файлов                        |
| `ColorPicker`       | палитра цветов + hex input                              |

### Data display

| Компонент       | Применение                                              |
|-----------------|---------------------------------------------------------|
| `StatCard`      | KPI tile: label uppercase + value tabular + trend badge + sub |
| `DataTable`     | Базовая. Sticky header, selection, expandable rows      |
| `GroupedTable`  | **Pivot-style**. Multi-row header, группировка с агрегацией, edit-cells, цветные индикаторы. См. Patterns. |
| `Pagination`    | Простая, с эллипсисом                                   |
| `BulkActionsBar`| Появляется когда выбрано > 0                            |
| `TreeView`      | Рекурсивный, для категорий                              |

### Layout

| Компонент       | Применение                                              |
|-----------------|---------------------------------------------------------|
| `Tabs`          | Три варианта: `underline` (внутри карточки), `pill` (переключение вьюх), `segmented` (форматы отображения) |
| `Breadcrumbs`   | Навигационный путь                                      |
| `Stepper`       | Wizard'ы и многошаговые формы                           |
| `PageHeader`    | kicker + Instrument Serif title + breadcrumbs + status + actions |
| `Sidebar`       | Группы → пункты с иконкой → активный fill stone-900     |

### Overlays

| Компонент       | Применение                                              |
|-----------------|---------------------------------------------------------|
| `Modal`         | sm/md/lg/xl. Title + body + footer. Backdrop blur       |
| `Drawer`        | side='right' (фильтры, детальные карточки) или 'bottom' (bulk-edit) |
| `Popover`       | Инлайн-фильтры, контекстные меню                        |
| `DropdownMenu`  | items с icon + shortcut + divider + danger              |
| `ContextMenu`   | Right-click на сущности                                 |
| `CommandPalette`| ⌘K. Унифицированный поиск по Hub                        |

### Feedback

| Компонент       | Применение                                              |
|-----------------|---------------------------------------------------------|
| `Toast`         | success/error/info/warning/loading. Bottom-right        |
| `Alert`         | Inline в карточках                                      |
| `EmptyState`    | icon + title + description italic + action              |
| `Skeleton`      | Для loading state карточек                              |

---

## 7. Charts

### Палитра

```js
palette: {
  ink:    '#1C1917',  // основной (light) / stone-50 в dark
  blue:   '#2563EB',
  purple: '#7C3AED',
  teal:   '#0D9488',
  emerald:'#059669',
  amber:  '#D97706',
  rose:   '#E11D48',
  indigo: '#4F46E5',
}
```

### Контекстные миксы

Не подбирай цвета каждый раз — есть готовые mappings:

```js
// P&L разрез
pnl: {
  revenue: ink,       // выручка — основная метрика, тёмная
  margin: emerald,    // маржинальная прибыль
  logistics: teal,    // логистика
  commission: amber,  // комиссии МП
  marketing: purple,  // маркетинг
}

// Каналы рекламы
channels: {
  internal: ink,      // внутренняя WB
  yandex: blue,
  vk: purple,
  seedVk: teal,       // посевы ВК
  seedAg: amber,      // посевы агентство
  bloggers: rose,
}
```

### Tooltip pattern

Все графики — `makeRichTooltip(tk, opts)` с поддержкой:
- Multi-value display (все серии за выбранную точку X)
- Заголовок с разделителем
- Цветной dot + название серии + значение в `tabular-nums`
- Опционально: `showTotal: true` — добавляет ИТОГО внизу
- Опционально: `showPercent: true` — добавляет проценты

### Типы графиков

| Тип             | Когда использовать                                       |
|-----------------|----------------------------------------------------------|
| Line            | Динамика метрики во времени, multi-series для P&L разреза |
| Area            | Динамика с акцентом на объём; со сравнением периодов    |
| Bar             | Сравнение моделей/каналов в одной точке времени         |
| Stacked Bar     | Структура расходов/выручки по каналам, разложенная во времени |
| Stacked Area    | Динамика структуры (как меняются доли)                  |
| Combo (Bar+Line)| Абсолют + относительная метрика на двух осях           |
| Donut           | Доли в обороте. С центральным значением (Total)         |
| Gauge           | Прогресс к цели (% от плана)                            |
| Funnel          | Воронка покупки/конверсий (свой через div'ы)            |
| Calendar Heatmap| Активность по дням за период (контент, публикации)     |
| Sparkline       | Тренд внутри KPI карточки. **h-10 w-20**, не растянутый  |
| Inline sparkline| Тренд в строке таблицы. h-6 w-24, без точек             |

---

## 8. Patterns

### Kanban Board

**Применение:** контент-завод, hiring pipeline, любой workflow со статусами.

**Структура:**
- Колонки с accent-цветом, лимитом WIP, счётчиком, action-buttons
- Карточки с draggable, обложкой-полоской цвета модели, тегом канала, priority dot, assignee-аватаром, прогресс-баром подзадач, метаданными (due/comments/attachments)
- При drag: opacity 30% + rotate 1° + scale 95%
- При hover-over: ring-2 + translate-y -0.5
- WIP-лимит overflow → красный badge

**Карточка → Detail Drawer:**
Открывается справа (560px). Header с cover, статусом-Badge (изменяемым через select), tag, model-hash. Title в Instrument Serif. Properties block (автор, исполнитель, приоритет, дедлайн, тег, колонка). Description, Subtasks (чекбоксы + прогресс-бар), Attachments grid, Comments thread с composer, History timeline. Footer: Архивировать / Открыть полностью / Сохранить.

**Production:** в Hub переписать на `@dnd-kit/core` + `@dnd-kit/sortable` (touch-support, accessibility, ghost preview).

### Calendar

**Применение:** съёмки, релизы, промо, поставки, командные встречи.

**Два вида:**
- **Month** — 6×7 сетка. События inline до 3 + «ещё N». Цветные категории.
- **Week** — часовая сетка 8:00–21:00. События abs-positioned по времени. Now-line красная горизонтальная.

**DnD событий:**
- В month — drag между днями (изменяет `event.date`)
- В week — drag между slots (изменяет `event.date` + `event.time` с шагом часа)
- Drop-target подсвечивается ring + bg

**Цветовая схема событий:**
- `blue` — съёмки
- `purple` — Reels / контент
- `emerald` — релизы
- `amber` — промо / распродажи
- `teal` — поставки / логистика
- `gray` — встречи

**Click → Event Detail Popover:** centered modal с полной инфой о событии.

### Comments thread

**Применение:** под моделью, задачей, SKU, заказом — везде где нужно обсуждение.

**Структура:**
- Header: иконка + «Обсуждение» + счётчик + actions (Pin, BellOff, More)
- Основная ветка → reply-ветка с border-left
- Каждый комментарий: avatar + author + time + text
- @-mentions подсвечиваются `bg-blue-50 text-blue-700` badge
- `inline code` styled через `font-mono bg-stone-100`
- Attachments — pill-карточки с image-icon + filename mono + size
- Реакции — pill-buttons с emoji + count
- Footer-actions: добавить реакцию (Smile), Reply
- Composer внизу: textarea + toolbar (At, Hash, Paperclip, Smile) + Send

### Notifications

**Slide-out панель (right, w-420px).**

- Header: иконка Bell + title + красный badge с количеством непрочитанных + Settings + X
- Фильтр-чипы: Все / Непрочитанные / Упоминания + count badges
- Группировка по дате: Today / Yesterday / Earlier (sticky labels)
- Каждое уведомление: blue dot если непрочитанное + avatar/typeIcon + текст с подсветкой автора + target в pill + timestamp
- Типы с иконками: mention (@, blue), task (Check, emerald), comment (MessageSquare, purple), status (Refresh, amber), system (Info, stone)

### Activity feed

**Linear-style timeline.**

- Header: иконка Activity + «История изменений» + filter
- Каждое событие: avatar (vertical line connector до next) + автор + действие + entity kind + entity name + change badges (from→to с зачёркнутым старым) + timestamp + field-tag

### Inbox

**Объединённые задачи / упоминания / ревью / комментарии / system.**

- Header: title + counter + «Отметить все»
- Tabs: Все / Непрочитанные / Срочные с count badges
- Каждый item: priority dot (rose/amber/stone) + type icon (в quad-card) + author avatar + title + project chip + due (красным «сегодня») + actions

---

## 9. Сложные таблицы (GroupedTable / Pivot)

Когда обычной DataTable недостаточно — используй `GroupedTable`. Применение: планирование поставок, сводки по моделям/SKU, финансовые pivot'ы.

**Особенности:**
1. **Multi-row header** — две строки. Верхняя — групповые колонки (Товар / Аналитика продаж / Заказ №). Нижняя — атомарные колонки. Между группами — `border-l`.
2. **Группировка с агрегацией** — заголовок группы (`bg-stone-50/60`) показывает суммы/средние по items: сумма stock, средний cover, сумма orders/day. Кликаемый chevron → expand/collapse.
3. **Edit-cells** — quantity-поля для редактирования прямо в таблице. Стиль: `bg-blue-50/30 border-blue-200/40 focus:bg-white focus:border-blue-400`.
4. **Цветные индикаторы** — для cover days:
   - `< 30` дней → red (`bg-red-50 text-red-700`)
   - `30-60` → amber
   - `60-365` → emerald (норма)
   - `> 365` → blue (избыток)
5. **Footer** — ИТОГО строка с агрегированными значениями.
6. **Sticky header** в проде (для длинных таблиц).
7. **Минимальная ширина** — 1100px+, с `overflow-x-auto`. Мобильная версия — отдельный stack-вид.

---

## 10. Чеклист перед мёрджом любого экрана

- [ ] **Палитра** — только stone, никаких gray/slate/zinc
- [ ] **Шрифты** — Instrument Serif для page titles, DM Sans для UI
- [ ] **Числа** — `tabular-nums` везде
- [ ] **Технические значения** — `font-mono text-xs`
- [ ] **Statuses** — через STATUS_MAP, не хардкоженный stone-300
- [ ] **Уровни** — все формы используют LevelBadge через FieldWrap
- [ ] **Карточки** — `border` + `rounded-lg`, **никаких теней**
- [ ] **Иконки** — lucide-react, размер `w-3.5 h-3.5` (sm) или `w-4 h-4` (md), цвет `text-stone-500/400`
- [ ] **Hover** — единая логика: ghost кнопки `hover:bg-stone-100`, ряды таблиц `hover:bg-stone-50/60`
- [ ] **Focus** — обводка `border-stone-900 focus:ring-1 ring-stone-900` (не синяя)
- [ ] **Empty states** — иконка серая + title + description italic + action
- [ ] **Dark theme** — все цвета через семантические токены, никаких `text-stone-900` без `dark:text-stone-50`
- [ ] **Графики** — палитра из `chartTokens.palette` или контекстная (`pnl`, `channels`)
- [ ] **Tooltips на графиках** — `makeRichTooltip` с multi-value
- [ ] **Mobile** — sidebar превращается в hamburger, колонки таблицы скрываются по приоритетам

---

## 11. Антипаттерны (что НЕ делать)

❌ **Тени на статичных карточках** (`shadow-sm`, `shadow-md`). Только `border-stone-200`.
   *Исключение:* Kanban карточки — `shadow-sm` + `hover:shadow-md` для тактильной обратной связи.

❌ **Цветные кнопки primary** (синие, зелёные кнопки «Сохранить»). Primary = stone-900.
   *Исключение:* `danger` для деструктивных действий (Удалить → rose-600).

❌ **Эмоджи в UI**. В копирайтинге — ок, в чипах и кнопках — нет.

❌ **Заголовки только в DM Sans Bold**. Page titles — обязательно Instrument Serif italic для бренда.

❌ **3D-индикаторы**, дикий цвет, gradients вне brand. У нас холодный, спокойный визуал.

❌ **Хардкодить stone-* в компонентах**. Использовать семантические утилиты `bg-surface`, `text-primary`, `border-default`.

❌ **Иконки больше w-4 h-4 в инлайн-контексте**. Большие иконки — только в EmptyState (w-8) и Empty illustrations.

❌ **Цветной background на disabled state**. Только `opacity-50` + `cursor-not-allowed`.

❌ **Text decoration на hover ссылок**. Используй `hover:text-stone-900` или подсветку фоном — не underline.

❌ **Stone-монохром на multi-series графиках**. Каждая серия — свой цвет из палитры.

❌ **Растянутые sparklines на всю ширину карточки**. Они должны быть `h-10 w-20` рядом с числом.

---

## 12. Подготовка к dark theme — реализация в проде

В .jsx-артефактах используется Tailwind `dark:` prefix через wrapping `<div className="dark">`. **В проде Hub** нужно перейти на CSS-переменные для:
1. Чистоты JSX (без `dark:bg-stone-900` на каждом теге)
2. Возможности менять токены централизованно
3. Подготовки к доп. темам (системная, high-contrast)

### Tailwind v4 setup

В `app.css` (или `globals.css`):

```css
@import "tailwindcss";

@theme {
  --color-page: theme(colors.stone.50);        /* light default */
  --color-surface: theme(colors.white);
  --color-surface-muted: theme(colors.stone.50);
  --color-elevated: theme(colors.white);
  --color-text-primary: theme(colors.stone.900);
  --color-text-secondary: theme(colors.stone.700);
  --color-text-muted: theme(colors.stone.500);
  --color-text-label: theme(colors.stone.400);
  --color-border-default: theme(colors.stone.200);
  --color-border-strong: theme(colors.stone.300);
}

[data-theme='dark'] {
  --color-page: theme(colors.stone.950);
  --color-surface: theme(colors.stone.900);
  --color-surface-muted: theme(colors.stone.900 / 40%);
  --color-elevated: theme(colors.stone.800);
  --color-text-primary: theme(colors.stone.50);
  --color-text-secondary: theme(colors.stone.300);
  --color-text-muted: theme(colors.stone.400);
  --color-text-label: theme(colors.stone.500);
  --color-border-default: theme(colors.stone.800);
  --color-border-strong: theme(colors.stone.700);
}

/* Semantic utilities */
@utility bg-surface     { background-color: var(--color-surface); }
@utility bg-surface-muted { background-color: var(--color-surface-muted); }
@utility bg-elevated    { background-color: var(--color-elevated); }
@utility bg-page        { background-color: var(--color-page); }
@utility text-primary   { color: var(--color-text-primary); }
@utility text-secondary { color: var(--color-text-secondary); }
@utility text-muted     { color: var(--color-text-muted); }
@utility text-label     { color: var(--color-text-label); }
@utility border-default { border-color: var(--color-border-default); }
@utility border-strong  { border-color: var(--color-border-strong); }
```

В компонентах — вместо `bg-white dark:bg-stone-900` пиши `bg-surface`. Вместо `text-stone-900 dark:text-stone-50` → `text-primary`.

### ThemeProvider

```jsx
const ThemeContext = React.createContext({ theme: 'light', toggle: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() =>
    localStorage.getItem('hub-theme') || 'light'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('hub-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, toggle: () => setTheme(t => t === 'light' ? 'dark' : 'light') }}>
      {children}
    </ThemeContext.Provider>
  );
}
```

### Графики (recharts)

Recharts не поддерживает CSS-переменные напрямую. Решение — `useTheme()` hook + два набора `chartTokens` (light/dark) — как в DS-артефактах.

---

## 13. Файлы-референсы

| Файл                                  | Что внутри                               |
|---------------------------------------|------------------------------------------|
| `wookiee_ds_v2_foundation.jsx`        | Foundation, Atoms, Forms, Data, Charts, Layout, Overlays, Feedback. Все с light + dark |
| `wookiee_ds_v2_patterns.jsx`          | Kanban (с DnD + detail drawer), Calendar (с DnD событий), Comments, Notifications, Activity, Inbox, Theme demo |
| `wookiee_matrix_mvp_v4.jsx`           | Эталон сложного модуля: sidebar + tabs + detail card + columns + filters |
| `wookiee_supply_planning_v1.jsx`      | Эталон GroupedTable (pivot-style) |
| `wookiee_rnp_dashboard_v3.jsx`        | Эталон сложного дашборда: chart palette, story-headers, KPI |

---

## 14. Стек (для Claude Code)

- **Vite + React 19**
- **React Router 7**
- **Tailwind CSS v4** (с `@theme` для токенов)
- **Lucide React** для иконок
- **Recharts** для графиков
- **@dnd-kit/core** + **@dnd-kit/sortable** для production DnD (не нативный HTML5)
- **Supabase** для backend
- **Zustand** для глобального state (включая theme)

---

*Версия: 2.0 · Май 2026*
