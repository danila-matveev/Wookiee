# BRIEF: Маркетинг — Промокоды + Поисковые запросы

## Что это
Новый раздел Hub: **Маркетинг** — два подраздела:
1. **Промокоды** — управление промокодами, статистика продаж
2. **Поисковые запросы** — отслеживание брендовых запросов, артикулов и подменных WW-кодов

## UX-эталон
Файл `wookiee_marketing_v4.jsx` — работающий прототип со всеми экранами.
**Дизайн должен быть повторён точь-в-точь: компоненты, отступы, палитра, шрифты.**
Mock-данные заменяются на Supabase-запросы.

---

## Страница 1: Поисковые запросы

### Сущности

#### `marketing.tracked_queries` — главная таблица
| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| group | enum | `brand`, `external`, `cr_general`, `cr_personal` |
| query | text | Что ищут на WB. Бренд: `wooki`. Артикул: `163151603`. Креатор: `WW121790` |
| article | text | Человекочитаемое название товара: `Wendy/white_S` |
| nomenclature | text | WB номенклатура |
| ww_code | text | Подменный артикул (WW-код) |
| channel | text | Канал: `бренд`, `Яндекс`, `Таргет ВК`, `Adblogger`, `креаторы`, `SMM` |
| campaign | text | Название кампании или блогер: `WENDY_креаторы`, `креатор_Донцов` |
| status | enum | `active`, `free`, `archive` |
| model | text | Привязка к модели: `Wendy`, `Audrey`, etc. |
| sku_id | uuid | FK → product_matrix.skus (опционально) |
| created_at | timestamptz | |
| updated_at | timestamptz | |

#### `marketing.query_stats_weekly` — понедельная статистика
| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| query_id | uuid | FK → tracked_queries |
| week_start | date | Понедельник недели |
| frequency | int | Частота поискового запроса |
| transitions | int | Переходы |
| cart_adds | int | Добавления в корзину |
| orders | int | Заказы |

Конверсии вычисляются на лету:
- CR→корз = cart_adds / transitions
- CR→зак = orders / cart_adds
- CRV = orders / transitions (итоговая)

#### `marketing.channels` — справочник каналов (теги)
| Поле | Тип |
|------|-----|
| id | uuid |
| name | text |
| created_at | timestamptz |

### Группировка (4 секции с collapsible headers)
1. **🔤 Брендированные** — group = `brand`
2. **📦 Артикулы (внешний лид)** — group = `external`
3. **👥 Креаторы общие** — group = `cr_general`
4. **👤 Креаторы личные** — group = `cr_personal`

### Фильтры
- **Модель** — pills в header (Все / Wendy / Audrey / ...)
- **Канал** — pills в header (Все / бренд / Яндекс / креаторы / ...)
- **Поиск** — по query, article, nomenclature, ww_code, campaign, model
- **Период** — date range picker (от / до), агрегация weekly stats

### Колонки таблицы (полная воронка)
Запрос | Артикул | Канал | Кампания | Частота | Перех. | CR→корз | Корз. | CR→зак | Заказы | CRV

### Итоговая строка (sticky bottom)
Суммы по всем отфильтрованным записям: Частота | Перех. | CR→корз | Корз. | CR→зак | Заказы | CRV

### Detail panel (правая панель при клике)
- Заголовок: query + StatusEditor + channel badge + campaign
- Привязка к товару: номенклатура, WW-код, артикул, модель
- Воронка за выбранный период (каскад с промежуточными CR)
- Понедельная таблица (scrollable, переключение «За период / Все»)

### StatusEditor
Custom dropdown (не нативный select): клик по badge → меню с вариантами → галочка у текущего.
Статусы: Используется (green), Свободен (blue), Архив (gray).

### Форма добавления WW-кода
Каскадная форма:
1. Модель (SelectMenu) → 2. Цвет → 3. Размер → авто-привязка SKU
4. WW-код (input, font-mono)
5. Канал (SelectMenu с `allowAdd`)
6. Кампания/блогер (SelectMenu с `allowAdd`)

### SelectMenu — кастомный dropdown
- Стилизованный триггер с chevron
- Список опций с поиском (если > 5 шт)
- Галочка у выбранного
- Кнопка «+ Добавить новый» — inline input для нового значения

---

## Страница 2: Промокоды

### Сущности

#### `marketing.promo_codes`
| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| code | text | CHARLOTTE10, OOOCORP25, etc. |
| channel | text | Соцсети, Блогер, Корп, ЯПС, ООО |
| discount_pct | int | Скидка % |
| valid_from | date | |
| valid_until | date | |
| status | enum | `active`, `unidentified` |
| created_at | timestamptz | |

#### `marketing.promo_stats_weekly`
| Поле | Тип |
|------|-----|
| id | uuid |
| promo_id | uuid | FK → promo_codes |
| week_start | date |
| orders_qty | int |
| sales_amount | int |
| returns_qty | int |

#### `marketing.promo_product_breakdown`
| Поле | Тип |
|------|-----|
| id | uuid |
| promo_id | uuid |
| sku_label | text |
| model | text |
| qty | int |
| amount | int |

### KPI карточки (header)
Активных | Продажи, шт | Продажи, ₽ | Ср. чек, ₽

### Колонки таблицы
Код | Канал | Скидка | Статус | Продажи, шт | Продажи, ₽ | Ср. чек, ₽

### Итоговая строка (sticky bottom)
Суммы: кол-во кодов | шт | ₽ | ср. чек

### Detail panel
- Заголовок: code + badge + channel
- Форма: код, канал (SelectMenu с allowAdd), скидка %, даты — edit/view toggle
- Продажи: шт + ₽ + ср. чек
- Товарная разбивка (таблица)
- Понедельная статистика (таблица)

---

## Общие компоненты (обе страницы)

### UpdateBar
- Дата/время последнего обновления (из sync_log)
- Статус полноты: «✓ 1 нед (20.04–26.04), пропусков нет»
- Кнопка «Обновить» → запускает Edge Function / скрипт синхронизации
- Анимация спиннера при синхронизации

### DateRange
- Два `<input type="date">` с иконкой календаря
- min/max ограничения
- Влияет на агрегацию ВСЕХ данных на странице

### Layout
- Icon sidebar (48px) → Sub-sidebar (176px, «Маркетинг») → Content area
- Паттерн из matrix_v4: sidebar + tabs + content + detail panel

---

## Acceptance Criteria

### Поисковые запросы
- [ ] Таблица с 4 collapsible секциями, данные из Supabase
- [ ] Фильтры: модель pills + канал pills + текстовый поиск + date range
- [ ] Все конверсии вычисляются на лету (не хранятся)
- [ ] Итоговая строка с суммами по видимым записям
- [ ] Detail panel с воронкой за выбранный период
- [ ] Создание нового WW-кода через каскадную форму
- [ ] Редактирование статуса через custom dropdown
- [ ] SelectMenu с возможностью добавить новый канал/кампанию

### Промокоды
- [ ] Таблица с данными из Supabase
- [ ] KPI карточки (суммы)
- [ ] Date range picker
- [ ] Итоговая строка с суммами
- [ ] Detail panel: edit/view, товарная разбивка, понедельная статистика
- [ ] Создание нового промокода

### Обновление данных
- [ ] UpdateBar с timestamp + статус полноты
- [ ] Кнопка «Обновить» запускает синхронизацию (Edge Function)
- [ ] Таблица sync_log хранит историю обновлений

### Дизайн (HARD)
- [ ] Палитра: ТОЛЬКО stone (никаких gray/slate/zinc)
- [ ] Шрифты: DM Sans (UI) + Instrument Serif (page titles, italic)
- [ ] Числа: tabular-nums. Моноширинный: font-mono text-xs для кодов/артикулов
- [ ] Нативные select заменены на SelectMenu
- [ ] Нет теней на карточках, только border-stone-200

---

## Слепые зоны (обсудить при реализации)
1. **Sync Edge Function** — откуда берутся данные? WB API? CSV-импорт? Нужен отдельный скрипт.
2. **Permissions** — кто может создавать/редактировать WW-коды? Все или только маркетинг?
3. **RLS** — нужны ли Row Level Security policies?
4. **Справочник каналов** — хранить в отдельной таблице или enum?
5. **Привязка к товарной матрице** — sku_id → как связать с существующей таблицей SKU?
6. **Пагинация** — при >500 записей нужна серверная пагинация
