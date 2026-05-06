---
name: coo-report
description: Weekly COO report — parallel data collection from 5 sources (finance, models, logistics, ads, team), anomaly detection, Notion template rendering
triggers:
  - /coo-report
  - отчёт coo
  - отчёт директора
---

# /coo-report — Еженедельный отчёт COO

**Запуск:** `/coo-report`

## Что делает

Собирает данные из 5 независимых источников параллельно, проверяет на аномалии и создаёт заполненную страницу в Notion по шаблону Елизаветы Литвиновой (COO).

Автоматически заполняет разделы 1, 2, 3, 6, 7, 8, 9 (финансы, анализ, рекомендации, комплекты, реклама, логистика, сотрудники).
Разделы 4, 5, 10, 11, 12 остаются для ручного заполнения.

---

## Шаг 0: Уточнить период

**Перед запуском сборщиков обязательно спроси пользователя:**

> За какой период сделать отчёт?
> Текущая неделя (пн {дата_пн} — вс {дата_вс}) или другой период?

Если пользователь не указал дату явно — покажи, какую неделю ты собираешься брать (автоопределение: неделя, содержащая сегодняшний день), и жди подтверждения или корректировки.

Получив ответ, определи `REF_DATE` — любую дату внутри нужной недели в формате `YYYY-MM-DD`. Например, если нужна неделя 4–11 мая, `REF_DATE=2026-05-04`.

---

## Шаг 1: Запустить все сборщики параллельно

Запускай все 5 команд одновременно в отдельных Bash-вызовах. Это необходимо для параллельного выполнения, так как сборщики независимы.

Подставь `REF_DATE` из Шага 0 (формат `YYYY-MM-DD`). Если неделя текущая — аргумент можно опустить.

```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/finance.py REF_DATE
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/models.py REF_DATE
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/logistics.py REF_DATE
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/ads.py REF_DATE
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/team.py REF_DATE
```

Каждый сборщик создаёт JSON в `/tmp/`:
- `/tmp/coo_finance.json`
- `/tmp/coo_models.json`
- `/tmp/coo_logistics.json`
- `/tmp/coo_ads.json`
- `/tmp/coo_team.json`

---

## Шаг 2: Проверить аномалии в каждом JSON

**СТОП (не публиковать, сообщить пользователю):**

Если обнаружишь, ОСТАНОВИТЬ выполнение и сообщить пользователю что именно неправильно:

- `/tmp/coo_finance.json`: `combined.current.orders_count == 0` → данные WB+OZON не пришли
- `/tmp/coo_finance.json`: `combined.current.drr_total_pct > 100` → ДРР некорректна (>100%)
- `/tmp/coo_finance.json`: `combined.current.margin < -0.5 * combined.current.revenue_after_spp` → маржа < -50% от выручки (аномалия в данных)

**ПРЕДУПРЕЖДЕНИЕ (публиковать с флагом ⚠️):**

Помести ⚠️ в соответствующей ячейке:

- `/tmp/coo_models.json`: любая модель с `trend_pct > 300%` → экстремальный рост (аномалия данных?)
- `/tmp/coo_logistics.json`: `localization_warning == true` → проблемы с локализацией склада
- `/tmp/coo_logistics.json`: любая модель с `turnover_days > 180` → скоро товар устаревает
- `/tmp/coo_team.json`: `data_refreshed == false` → данные Битрикс не обновлялись >24 часов

**Важно: неполная текущая неделя.** Если `period.current_end` — это дата раньше воскресенья (отчёт формируется в середине недели), то `trend_pct` у ВСЕХ моделей будет -40% — -87%. Это математический артефакт, не бизнес-сигнал. В таком случае:
- НЕ помечай падение тренда как ⚠️
- В ячейках тренда пиши `* неполная нед.` вместо ↑/↓
- Добавь callout в начало раздела 6: "⚠️ Текущая неделя неполная (N из 7 дней). Тренды статистически нерелевантны."

---

## Шаг 3: Синтез — заполнить разделы отчёта

### Раздел 1 (Финансы)

Таблица P&L из `/tmp/coo_finance.json`, поле `combined`:

| Метрика | Неделя 1 (previous) | Неделя 2 (current) |
|---------|---------------------|-------------------|
| Заказы шт | `combined.previous.orders_count` | `combined.current.orders_count` |
| Выручка до СПП | `combined.previous.revenue_before_spp` | `combined.current.revenue_before_spp` |
| Выручка после СПП | `combined.previous.revenue_after_spp` | `combined.current.revenue_after_spp` |
| Себестоимость | `combined.previous.cost_of_goods` | `combined.current.cost_of_goods` |
| Логистика | `combined.previous.logistics` | `combined.current.logistics` |
| Комиссия МП | `combined.previous.commission` | `combined.current.commission` |
| ДРР всего % | `combined.previous.drr_total_pct` | `combined.current.drr_total_pct` |
| — внутренняя | `combined.previous.drr_internal_pct` | `combined.current.drr_internal_pct` |
| — внешняя | `combined.previous.drr_external_pct` | `combined.current.drr_external_pct` |
| Выкуп % | *(лаг 3-21 дн., заполнить вручную)* | *(лаг 3-21 дн., заполнить вручную)* |
| Маржа | `combined.previous.margin` | `combined.current.margin` |

**Примечание:** Выкуп % — лаговый показатель. Всегда добавляй пометку "(лаг 3-21 дн.)" — не использовать как причину изменения маржи.

Числа форматировать: выручка и маржа — `1 234 567 ₽`, проценты — `12.3%`.

### Раздел 6 (Комплекты)

Таблица по 16 официальным моделям из `/tmp/coo_models.json`.

**Структура JSON:**
```
models.json = {
  "current": { "wendy": {...}, "ruby": {...}, ... },  # текущая неделя
  "previous": { "wendy": {...}, "ruby": {...}, ... }, # предыдущая неделя
  "period": { "current_start": "...", "current_end": "..." }
}
```

Поля модели в `current`:
- `revenue` — выручка ₽ (orders_rub)
- `margin` — маржа ₽
- `margin_pct` — маржа %
- `drr_pct` — ДРР %
- `orders_count` — заказы шт
- `trend_pct` — изменение выручки vs предыдущей неделе %

Поля модели в `previous`: те же, кроме `trend_pct`.

**Фильтрация:** используй только 16 официальных моделей (wendy, ruby, vuki, charlotte, audrey, joy, moon, lana, eva, bella, valery, alice, set vuki, set ruby, set moon, set bella). Пропускай "корректировка рекламы", "other" и другие артефакты.

| Модель | Выручка | Маржа | ДРР | Тренд | Действие |
|--------|---------|-------|-----|-------|----------|
| Wendy | `current.wendy.revenue` | `current.wendy.margin_pct` | `current.wendy.drr_pct` | `_trend()` | `_action()` |

**Логика тренда** (только если неделя полная):
- `trend_pct > 10` → "↑ +N%"
- `trend_pct < -10` → "↓ -N%"
- иначе → "→ стабильно"

**Логика действия** (формулируй содержательно):
- ДРР > 5% → "снизить ставки / выключить неэффективные кампании"
- маржа < 0 → "разобрать юнит-экономику, возможно убрать модель из рекламы"
- маржа упала > 20% от previous → "проверить рост себестоимости или логистики"
- всё в норме → "—" или конкретная развивающая рекомендация

### Раздел 7 (Реклама)

Из `/tmp/coo_ads.json`.

**Структура JSON:**
```
ads.json = {
  "previous": {
    "bloggers": { "spend_rub": N, "drr_pct": N },
    "vk":       { "spend_rub": N, "drr_pct": N },
    "creators": { "spend_rub": N, "drr_pct": N },
    "internal_wb": { "spend_rub": N, "drr_pct": N },
    "orders_rub": N
  },
  "current": { ... },  # те же поля
  "manual_fill_required": ["yandex", "vk_seeds_contractor"],
  "period": { "current_start": "...", "current_end": "..." }
}
```

| Канал | Расходы (пред.) | ДРР (пред.) | Расходы (тек.) | ДРР (тек.) |
|-------|-----------------|-------------|----------------|------------|
| Блогеры | `previous.bloggers.spend_rub` | `previous.bloggers.drr_pct`% | `current.bloggers.spend_rub` | `current.bloggers.drr_pct`% |
| ВК таргет + посевы | `previous.vk.spend_rub` | `previous.vk.drr_pct`% | `current.vk.spend_rub` | `current.vk.drr_pct`% |
| Создатели | `previous.creators.spend_rub` | — | `current.creators.spend_rub` | — |
| WB внутренняя | `previous.internal_wb.spend_rub` | `previous.internal_wb.drr_pct`% | `current.internal_wb.spend_rub` | `current.internal_wb.drr_pct`% |
| Яндекс | ⚠️ заполнить вручную | | ⚠️ заполнить вручную | |
| Посевы подрядчик | ⚠️ заполнить вручную | | ⚠️ заполнить вручную | |

**Примечание:** Яндекс и Посевы подрядчика — данных в DB нет, всегда ставь плейсхолдер. ВК и блогеры агрегированы в группы (разбивка на посевы / подрядчик / таргет недоступна из DB).

### Раздел 8 (Логистика)

Из `/tmp/coo_logistics.json`.

**Структура JSON:**
```
logistics.json = {
  "localization_index": N,       # индекс локализации WB %
  "localization_warning": bool,  # true если <65%
  "models": {
    "Wendy": {
      "turnover_days": N,         # оборачиваемость дн.
      "stock_fbo_units": N,       # остаток на FBO WB
      "stock_moysklad_units": N,  # остаток в МойСклад (компоненты!)
      "stock_transit_units": N,   # в транзите
      "daily_sales": N,           # продажи/день (7-дн. среднее)
      "gmroi_pct": N,             # GMROI %
      "low_sales": bool
    },
    ...
  }
}
```

**Важно по МойСклад:** `stock_moysklad_units` считается в компонентах, не в комплектах. Для комплектов (Set Vuki, Set Ruby и т.д.) реальное число комплектов = N/2.

Итоговая таблица логистики:

| Показатель | Значение | Статус |
|------------|----------|--------|
| Индекс локализации | `localization_index`% | ≥65% 🟢 / 50–65% 🟡 / <50% 🔴 |
| Средневзвешенная оборачиваемость | вычислить: `sum(t*s for t,s in models) / sum(s)` дн. | <60 🟢 / 60–90 🟡 / >90 🔴 |

Затем — подробная таблица по каждой модели:

| Модель | Оборачиваемость | FBO (шт) | МС (шт) | Транзит | Продажи/день | GMROI |
|--------|----------------|----------|---------|---------|--------------|-------|
| Wendy | N дн. | N | N | N | N | N% |

Статус оборачиваемости в ячейке: <60 дн. → 🟢, 60–90 → 🟡, >90 → 🔴 (жирный шрифт для >180).

### Раздел 9 (Сотрудники)

Из `/tmp/coo_team.json`.

**Структура JSON:**
```
team.json = {
  "staff": {
    "Имя": {
      "name": "Имя",
      "full_name": "Имя Фамилия",
      "role": "...",
      "done": N,
      "active": N,
      "overdue": N,
      "done_titles": ["задача 1", "задача 2", ...],
      "active_titles": [...],
      "overdue_titles": [...]
    },
    ...
  },
  "data_refreshed": bool,
  "bitrix_period": {...}
}
```

| Сотрудник | Что выполнено | Активные | Просрочено | Оценка |
|-----------|---------------|----------|-----------|--------|
| Имя | первые 2-3 из `done_titles` | `active` | `overdue` | 🟢/🟡/🔴 |

**Оценка:**
- `overdue == 0` → 🟢
- `overdue` 1–2 → 🟡
- `overdue` ≥ 3 → 🔴
- Если `data_refreshed == false` → добавь ⚠️ к оценке

**Важно про просрочки:** высокие `overdue` (20+) часто означают накопившиеся recurring-задачи (еженедельные отчёты и т.д.), а не реальное невыполнение. Смотри на `done_titles` — если задачи делаются, это нормально.

### Разделы 2, 3 (Анализ и решения)

Формулируй на основе всех данных — это ценность отчёта, не оставляй пустыми.

**Раздел 2 — Основная проблема недели:**
- Самое значимое отклонение от нормы
- С цифрами: не "маржа упала", а "маржа упала на 15% (-200K₽) при росте логистики +30%"

**Раздел 3 — Рекомендуемое решение:**
- Конкретное действие + ответственный + срок
- Например: "Артём: пересчитать юнит-экономику Valery и Alice до пятницы — GMROI отрицательный"

### Разделы 4, 5, 10, 11, 12

Оставь с текстом:
```
← заполнить вручную
```

---

## Шаг 4: Создать страницу в Notion

1. **Дублируй шаблон** через Notion MCP (`notion-duplicate-page`):
   - Template ID: `35658a2bd5878028ad75f1773a0f8593`
   - Parent folder ID: `35658a2bd587803b8ab5fc540e4318e7`

2. **Переименуй страницу** по формату:
   ```
   Отчётность COO ДД.ММ — ДД.ММ.ГГГГ
   ```
   Даты берёшь из `coo_finance.json["period"]`: `current_start` и `current_end`.

3. **Заполни разделы** согласно шагу 3 через `notion-update-page`.

4. **Верни ссылку** на готовую страницу в Notion.

---

## Зависимости

Убедись что в `.env` установлены:

```
DB_HOST=...              # PostgreSQL
DB_PORT=...
DB_USER=...
DB_PASSWORD=...
DB_NAME=...

WB_API_KEY_OOO=...       # WildBerries API
WB_API_KEY_IP=...

MOYSKLAD_TOKEN=...       # МойСклад API

Bitrix_rest_api=...      # Bitrix24 REST API

NOTION_TOKEN=...         # Notion API
USER_EMAIL=...           # для логирования (например danila@wookiee.shop)
```

---

## Диагностика

Если сборщик упал:

```bash
# Проверь синтаксис Python
python3 -m py_compile modules/coo_report/collectors/finance.py

# Запусти один сборщик с трассировкой
python3 -u modules/coo_report/collectors/finance.py 2>&1 | tee /tmp/debug.log
```

Частые причины:
- `team.py` — Bitrix API возвращает camelCase (`responsibleId`), а не UPPERCASE. `_normalize_task()` в коде это исправляет.
- `logistics.py` — читает индекс локализации из листа `Сводка` самого свежего `.xlsx` в `services/wb_localization/Отчеты готовые/`. Если файлов нет — вернёт `None`.

---

## Время выполнения

- Запуск 5 сборщиков параллельно: ~10–30 секунд
- Проверка аномалий: ~1–2 минуты
- Синтез и заполнение Notion: ~5–10 минут
- **Итого:** ~20–40 минут (в зависимости от volume данных)

---

## Логирование (выполнить всегда в конце)

Определи переменные для логирования:
- `_log_status` = `success` или `error`
- `_log_url` = URL страницы в Notion (например `https://www.notion.so/PAGE_ID`)
- `_log_items` = количество моделей в отчёте (обычно 16)
- `_log_notes` = краткое описание результата (например "Отчёт 04.05–11.05.2026, 16 моделей, маржа 37.1%")
- `_log_user` = значение `USER_EMAIL` из `.env` (или "unknown")
- `N` = длительность выполнения в секундах

Выполни через Supabase MCP (`execute_sql`, project `gjvwcdtfglupewcwzfhw`):

```sql
WITH ins AS (
  INSERT INTO tool_runs (
    id, tool_slug, status, trigger_type, triggered_by,
    result_url, items_processed, notes,
    started_at, finished_at, duration_sec
  ) VALUES (
    gen_random_uuid(),
    '/coo-report',
    '_log_status',
    'manual',
    'user:_log_user',
    '_log_url',
    _log_items,
    '_log_notes',
    now() - interval 'N seconds',
    now(),
    N
  )
  RETURNING tool_slug, status
)
UPDATE tools SET
  total_runs = total_runs + 1,
  last_run_at = now(),
  last_status = '_log_status',
  updated_at = now()
WHERE slug = '/coo-report';
```
