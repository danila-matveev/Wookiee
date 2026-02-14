# Analytics Engine Agent

## Бизнес-описание

**Назначение:** Автоматическая генерация аналитических отчётов по финансовым и маркетинговым данным бренда Wookiee с маркетплейсов Wildberries и OZON.

**Статус:** Активен (production)

**Какие задачи решает:**
- Ежедневный мониторинг — сравнение дня с предыдущим и 7-дневным трендом
- Периодическая аналитика — отчёт за произвольный период с 4-уровневой иерархией
- Месячные итоги — сравнение с бизнес-ориентирами и понедельная динамика
- Синхронизация отчётов с Notion

**Кто использует:** Telegram-бот (вызывает через subprocess), ручной запуск из CLI

---

## Технические детали

### Архитектура

```
CLI / Telegram Bot
    ↓ (subprocess)
scripts/
    ├── config.py           → конфигурация (читает .env)
    ├── data_layer.py       → ВСЕ DB-запросы и утилиты
    │
    ├── daily_analytics.py  → ежедневная аналитика
    ├── period_analytics.py → аналитика за период
    ├── monthly_analytics.py → месячный отчёт
    │
    └── notion_sync.py      → Markdown → Notion
    ↓
reports/*.md                → Markdown-отчёты
    ↓
Notion "Фин аналитика"     → база отчётов
```

### Принципы

1. **Единый слой данных** — все SQL-запросы живут в `data_layer.py`. Никогда не дублировать в других скриптах.
2. **Единая конфигурация** — все настройки в `config.py`, читает из корневого `.env`.
3. **Верифицированные формулы** — маржа WB/OZON проверена против PowerBI, расхождение <1%.
4. **Качество данных** — GROUP BY всегда с `LOWER()`, проценты только средневзвешенные.

### Data Layer (`data_layer.py`)

Центральный модуль доступа к данным. Содержит:

**Утилиты:**
- `to_float()` — Decimal → float
- `format_num()` — форматирование чисел с пробелами
- `format_pct()` — форматирование процентов
- `get_arrow()` — индикаторы тренда (↑↓→)
- `calc_change()` — процентное изменение
- `calc_change_pp()` — изменение в процентных пунктах

**DB-функции:**

| Функция | Источник | Описание |
|---------|----------|----------|
| `get_wb_finance(start, end)` | WB | Финансы бренда (маржа, выручка, логистика, реклама) |
| `get_wb_by_model(start, end)` | WB | Разбивка по моделям |
| `get_wb_traffic(start, end)` | WB | Трафик и конверсии |
| `get_wb_traffic_by_model(start, end)` | WB | Трафик по моделям |
| `get_ozon_finance(start, end)` | OZON | Финансы бренда |
| `get_ozon_by_model(start, end)` | OZON | Разбивка по моделям |
| `get_ozon_traffic(start, end)` | OZON | Трафик и конверсии |
| `get_wb_daily_series(date, lookback)` | WB | Временные ряды за N дней |
| `get_ozon_daily_series(date, lookback)` | OZON | Временные ряды за N дней |
| `get_wb_weekly_breakdown(start, end)` | WB | Понедельная разбивка |
| `get_ozon_weekly_breakdown(start, end)` | OZON | Понедельная разбивка |
| `get_artikuly_statuses()` | Supabase | Статусы товаров из матрицы |

### Типы отчётов

#### Daily Analytics (`daily_analytics.py`)

Сравнение дня с предыдущим днём и 7-дневным трендом.

**Механизмы:**

- **Confidence Scoring** — каждая гипотеза получает оценку 0.0-1.0:
  ```
  confidence = 0.4 × direction_agreement + 0.35 × magnitude + 0.25 × stability
  ```

- **Триангуляция** — вывод надёжен если подтверждён 3+ независимыми источниками

- **Red Team** — автоматические контраргументы:

  | Контраргумент | Триггер | Штраф |
  |---------------|---------|-------|
  | День недели | Метрика в пределах нормы для дня | -0.15 |
  | Неполные данные | Заказов < 50% от среднего | -0.15 |
  | Низкая база | OZON revenue < 10% total | -0.15 |
  | Изменение СПП | СПП сдвиг > 2 п.п. | -0.15 |
  | Лаг выкупов | 1-дневное сравнение = шум | -0.10 |

- **5-рычажная декомпозиция маржи:** Цена до СПП → СПП% → ДРР → Логистика → Выкуп

**CLI:**
```bash
python scripts/daily_analytics.py --date 2026-02-08 --save --notion
python scripts/daily_analytics.py --date 2026-02-08 --lookback 14
```

#### Period Analytics (`period_analytics.py`)

Отчёт за произвольный период с 4-уровневой иерархией:
1. Бренд (ИТОГО WB + OZON)
2. Канал (WB vs OZON)
3. Модель (разбивка по товарным моделям)
4. Статус товара (из Supabase: "В продаже", "Выводим", "Новинки")

**CLI:**
```bash
python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-07
python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-07 --compare-days 7 --save --notion
```

#### Monthly Analytics (`monthly_analytics.py`)

Месячный отчёт с понедельной динамикой и сравнением с бизнес-ориентирами.

**Бизнес-ориентиры:**
- Маржа: 5 000 000 - 6 500 000 руб/месяц
- Маржинальность: 20-25%
- ДРР: <10%

**CLI:**
```bash
python scripts/monthly_analytics.py --month 2026-01 --save --notion
python scripts/monthly_analytics.py --month 2026-01 --compare 2025-11
```

### Notion-синхронизация (`notion_sync.py`)

Конвертирует Markdown-отчёты в Notion-блоки и синхронизирует с базой "Фин аналитика".

**Логика:**
- Существует страница с таким периодом → перезаписать контент
- Не существует → создать новую

**Поддерживает:** заголовки, таблицы, списки, жирный текст, код, разделители.

```bash
python scripts/notion_sync.py --file reports/2026-02-01_2026-02-07_analytics.md
```

### Формулы маржи (верифицированные)

**WB (<1% расхождение с PowerBI):**
```sql
SUM(revenue_spp) - SUM(comis_spp) - SUM(logist) - SUM(sebes)
- SUM(reclama) - SUM(reclama_vn) - SUM(storage) - SUM(nds)
- SUM(penalty) - SUM(retention) - SUM(deduction)
```

**OZON (точное совпадение с PowerBI):**
```sql
SUM(marga) - SUM(nds)
```

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `scripts/config.py` | Конфигурация (DB connections, Notion token) |
| `scripts/data_layer.py` | ВСЕ DB-запросы и утилиты |
| `scripts/daily_analytics.py` | Ежедневная аналитика + confidence scores |
| `scripts/period_analytics.py` | Аналитика за произвольный период |
| `scripts/monthly_analytics.py` | Месячный отчёт с бизнес-ориентирами |
| `scripts/notion_sync.py` | Синхронизация с Notion |

---

## Запуск и использование

### Prerequisites

```bash
pip install psycopg2-binary python-dotenv notion-client
```

### Генерация отчётов

```bash
# Все скрипты запускаются из корня проекта
python scripts/daily_analytics.py --date 2026-02-08 --save --notion
python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-07
python scripts/monthly_analytics.py --month 2026-01 --save --notion
```

### Флаги

| Флаг | Описание |
|------|----------|
| `--save` | Сохранить отчёт в `reports/` |
| `--notion` | Синхронизировать с Notion |
| `--lookback N` | Глубина тренда (по умолчанию 7 дней) |
| `--compare-days N` | Период сравнения |

---

## Зависимости

- **Внутренние:** `sku_database/` (статусы артикулов через Supabase)
- **Внешние:** PostgreSQL (WB/OZON), Supabase, Notion API

---

## Ссылки

- Исходный код: [`scripts/`](../scripts/)
- Справочник БД: [`docs/database/DATABASE_REFERENCE.md`](../database/DATABASE_REFERENCE.md)
- Качество данных: [`docs/database/DATA_QUALITY_NOTES.md`](../database/DATA_QUALITY_NOTES.md)
- Telegram Bot (потребитель): [`agents/telegram-bot.md`](telegram-bot.md)
