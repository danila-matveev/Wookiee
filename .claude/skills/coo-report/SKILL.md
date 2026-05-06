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

Автоматически заполняет разделы 1, 6, 7, 8, 9 (финансы, комплекты, реклама, логистика, сотрудники).
Разделы 2-5, 10-12 остаются для ручного заполнения.

---

## Шаг 1: Запустить все сборщики параллельно

Запускай все 5 команд одновременно в отдельных Bash-вызовах. Это необходимо для параллельного выполнения, так как сборщики независимы:

```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/finance.py
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/models.py
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/logistics.py
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/ads.py
```
```bash
cd /Users/danilamatveev/Projects/Wookiee && python3 modules/coo_report/collectors/team.py
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

- `/tmp/coo_models.json`: любая модель с `trend_pct > 300%` или `trend_pct < -80%` → экстремальные скачки
- `/tmp/coo_logistics.json`: `localization_warning == true` → проблемы с локализацией склада
- `/tmp/coo_logistics.json`: любая модель с `turnover_days > 180` → скоро товар устаревает
- `/tmp/coo_team.json`: `data_refreshed == false` → данные Битрикс не обновлялись >24 часов

---

## Шаг 3: Синтез — заполнить разделы отчёта

Используя прочитанные JSON, дублируй шаблон в Notion и заполни разделы:

### Раздел 1 (Финансы)

Таблица P&L из `/tmp/coo_finance.json`:

| Метрика | Неделя 1 (previous) | Неделя 2 (current) |
|---------|---------------------|-------------------|
| Заказы шт | `previous.orders_count` | `current.orders_count` |
| Выручка до СПП | `previous.revenue_before_spp` | `current.revenue_before_spp` |
| Выручка после СПП | `previous.revenue_after_spp` | `current.revenue_after_spp` |
| Себестоимость | `previous.cost_of_goods` | `current.cost_of_goods` |
| Логистика | `previous.logistics` | `current.logistics` |
| Комиссия МП | `previous.commission` | `current.commission` |
| ДРР всего % | `previous.drr_total_pct` | `current.drr_total_pct` |
| — внутренняя | `previous.drr_internal_pct` | `current.drr_internal_pct` |
| — внешняя | `previous.drr_external_pct` | `current.drr_external_pct` |
| Выкуп % | `previous.buyout_pct` (лаг 3-21 дн.) | `current.buyout_pct` (лаг 3-21 дн.) |
| Маржа | `previous.margin` | `current.margin` |

**Примечание:** Выкуп % — лаговый показатель. Добавь пометку "(лаг 3-21 дн.)" в ячейке.

### Раздел 6 (Комплекты)

Таблица по 16 моделям из `/tmp/coo_models.json`:

| Модель | Выручка | Маржа | Тренд | Статус | Проблема | Действие |
|--------|---------|-------|-------|--------|----------|----------|
| wendy | `current.revenue` | `current.margin` | `_trend()` | `_status()` | `_problem()` | `_action()` |
| ... | | | | | | |

**Логика заполнения:**

- **Тренд:**
  - `trend_pct > 10` → "↑ рост"
  - `trend_pct < -10` → "↓ падение"
  - иначе → "→ стабильно"
  - Если `trend_pct > 300` или `< -80`: добавь префикс ⚠️

- **Статус продаж:**
  - выручка > 500K → "Активно"
  - 100K–500K → "Умеренно"
  - < 100K → "Слабо"

- **Проблема и Действие:** сформулируй сам на основе данных:
  - Если маржа упала > 20% от previous → проблема "Маржа ↓"
  - Если ДРР > 30% → проблема "ДРР высокий"
  - Если тренд падение + маржа падает → проблема "Падающая модель"
  - Действие = конкретное рекомендация (пересчитать цену, выключить рекламу, проверить costs и т.д.)

### Раздел 7 (Реклама)

Из `/tmp/coo_ads.json`:

| Канал | Расходы | ROI | Заказы |
|-------|---------|-----|--------|
| Блогеры | `bloggers.spend` | `bloggers.roi` | `bloggers.orders` |
| ВК | `vk.spend` | `vk.roi` | `vk.orders` |
| Создатели | `creators.spend` | `creators.roi` | `creators.orders` |
| Яндекс | ⚠️ заполнить вручную | | |
| Посевы подрядчик | ⚠️ заполнить вручную | | |

**Примечание:** Яндекс и Посевы подрядчика заполни плейсхолдерами "⚠️ заполнить вручную" — данных в API не получить.

### Раздел 8 (Логистика)

Из `/tmp/coo_logistics.json`:

| Метрика | Значение | Статус |
|---------|----------|--------|
| Индекс локализации | `localization_index`% | `_status()` |
| Средняя оборачиваемость | `avg_turnover_days` дн. | `_status()` |

**Статусы:**

- **Локализация:** ≥65% → 🟢, 50–65% → 🟡, <50% → 🔴 (+ предупреждение если warning)
- **Оборачиваемость:** <60 дн. → 🟢, 60–90 дн. → 🟡, >90 дн. → 🔴

### Раздел 9 (Сотрудники)

Из `/tmp/coo_team.json`:

| Сотрудник | Что выполнено | Активные | Просрочено | Оценка |
|-----------|---------------|----------|-----------|--------|
| Артём | `done_titles[0:2]` | `active_count` | `overdue_count` | `_grade()` |
| ... | | | | |

**Логика:**
- **Что выполнено:** первые 2–3 задачи из `done_titles`
- **Оценка:** 
  - нет просрочек → 🟢
  - 1–2 просрочки → 🟡
  - 3+ просрочки → 🔴
  - Если `data_refreshed == false` → добавь ⚠️

### Разделы 2, 3 (Проблемы и решения)

Сформулируй на основе всех данных:

**Раздел 2 — Основная проблема:**
- То, что сильнее всего отклонилось от нормы
- Примеры: "Маржа упала на 15% из-за роста себестоимости", "ДРР растёт, заказы нет", "Оборачиваемость 120+ дн. на 3 моделях"

**Раздел 3 — Рекомендуемое решение:**
- Конкретное действие с ответственным
- Примеры: "Артём: пересчитать себестоимость с поставщиком", "Светлана: выключить рекламу на убыточных каналах", "Валерия: перепроверить локализацию склада"

### Разделы 4, 5, 10, 11, 12

Оставь пустыми с текстом:
```
← заполнить вручную
```

---

## Шаг 4: Создать страницу в Notion

1. **Дублируй шаблон** через Notion MCP:
   - Template ID: `35658a2bd5878028ad75f1773a0f8593`
   - Parent folder ID: `35658a2bd587803b8ab5fc540e4318e7`

2. **Переименуй страницу:**
   ```
   Отчётность COO 04.05 — 11.05.2026
   ```
   (дата из `coo_finance.json["period"]["current_start"]`)

3. **Заполни разделы** согласно шагу 3

4. **Верни ссылку** на готовую страницу в Notion

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
```

---

## Диагностика

Если сборщик упал:

```bash
# Читай логи сборщика
tail -f /tmp/coo_*.json

# Проверь синтаксис Python
python3 -m py_compile modules/coo_report/collectors/finance.py

# Запусти один сборщик с трассировкой
python3 -u modules/coo_report/collectors/finance.py 2>&1 | tee /tmp/debug.log
```

---

## Время выполнения

- Запуск 5 сборщиков параллельно: ~10–30 секунд
- Проверка аномалий: ~1–2 минуты
- Синтез и заполнение Notion: ~5–10 минут
- **Итого:** ~20–40 минут (в зависимости от volume данных)
