# Wookiee Analytics — Data Hub

Централизованный хаб по работе с данными бренда нижнего белья **Wookiee**. Объединяет финансовую аналитику маркетплейсов, товарную матрицу, оптимизацию логистики и CRM — в единую экосистему с AI-агентами.

---

## Визия

**Проблема:** Данные бренда разбросаны по маркетплейсам (Wildberries, OZON), CRM (Bitrix24), Google Sheets, Notion. Каждый источник требует ручной работы для извлечения инсайтов.

**Решение:** Wookiee Analytics — единая точка доступа ко всем данным компании. Каждый модуль проекта — это автономный **агент**, который решает конкретную бизнес-задачу: от ежедневных финансовых отчётов до оптимизации распределения товаров по складам.

**Будущее:** Полная автоматизация рутинных аналитических задач через AI-агентов. Один Telegram-бот как интерфейс ко всем данным и процессам компании.

---

## Архитектура

### Поток данных

```mermaid
graph LR
    WB[Wildberries API] --> ETL[Data Pipeline]
    OZ[OZON API] --> ETL
    ETL --> PG[(PostgreSQL)]
    PG --> AE[Analytics Engine]
    PG --> BOT[Telegram Bot]
    AE --> MD[Markdown Reports]
    MD --> NOT[Notion]
    BOT --> TG[Telegram Users]
    BOT --> NOT
    GS[Google Sheets] --> SB[(Supabase)]
    SB --> AE
    SB --> BOT
    SB --> VAS[Vasily Agent]
    B24[Bitrix24] --> LYU[Lyudmila Agent]
```

### Агенты проекта

```mermaid
graph TB
    HUB[Wookiee Analytics Hub]
    HUB --> ACTIVE[Активные]
    HUB --> DEV[В разработке]

    ACTIVE --> A1[Олег — Telegram Bot Agent]
    ACTIVE --> A2[Analytics Engine]
    ACTIVE --> A3[SKU Database]

    DEV --> D1[Василий — MP Localization Agent]
    DEV --> D2[Людмила — CRM Agent]
```

Подробное описание каждого агента: [`docs/agents/`](docs/agents/)

---

## Компоненты проекта

| Папка | Назначение | Статус | Описание |
|-------|-----------|--------|----------|
| [`agents/oleg/`](agents/oleg/) | Олег, Telegram-бот (ReAct AI-agent) | Активен | Финансовый ассистент: отчёты, NL-запросы, мониторинг |
| [`agents/lyudmila/`](agents/lyudmila/) | Людмила, CRM-ассистент | В разработке | Bitrix24, управление задачами |
| [`agents/vasily/`](agents/vasily/) | Василий, оптимизация логистики WB | В разработке | Индекс локализации, перемещения между складами |
| [`scripts/`](scripts/) | Аналитический движок | Активен | Daily/period/monthly отчёты, Notion-синхронизация |
| [`sku_database/`](sku_database/) | Товарная матрица (Supabase) | Активен | 22 модели, 478 артикулов, 1450 SKU |
| [`shared/`](shared/) | Общая библиотека | Активен | config, data_layer, API-клиенты, утилиты |
| [`services/sheets_sync/`](services/sheets_sync/) | Синхронизация Google Sheets | Активен | Google Sheets <-> МП |
| [`docs/`](docs/) | Вся документация | Справочник | Архитектура, ADR, руководства, шаблоны, БД |
| [`docs/database/`](docs/database/) | Документация по БД | Справочник | Схемы, формулы, качество данных |
| [`deploy/`](deploy/) | Docker конфигурация | Инфраструктура | Dockerfile, docker-compose.yml |
| [`reports/`](reports/) | Сгенерированные отчёты | git-ignored | Markdown-файлы аналитики |

---

## Структура проекта

```
Wookiee/
├── AGENTS.md                    — правила для AI-агентов
├── CLAUDE.md                    — Claude Code настройки
├── README.md                    — этот файл
├── .env.example                 — шаблон переменных окружения
│
├── shared/                      — общая библиотека
│   ├── config.py               — конфигурация (единый источник)
│   ├── data_layer.py           — слой данных (ВСЕ DB-запросы)
│   ├── db_config.py            — совместимость
│   ├── clients/                — API-клиенты (WB, OZON, МойСклад, Sheets, Bitrix, z.ai)
│   └── utils/                  — утилиты
│
├── agents/                      — AI-агенты
│   ├── oleg/                   — Олег: ReAct-агент, финансовая аналитика
│   ├── lyudmila/               — Людмила: CRM-ассистент, Bitrix24
│   └── vasily/                 — Василий: оптимизация логистики WB
│
├── scripts/                     — CLI-скрипты аналитики
│   ├── abc_analysis.py         — ABC-анализ
│   ├── notion_sync.py          — синхронизация с Notion
│   └── ...
│
├── services/                    — доменные сервисы
│   ├── sheets_sync/            — синхронизация Google Sheets ↔ МП
│   └── ozon_delivery/          — оптимизация доставки OZON
│
├── sku_database/                — товарная матрица (Supabase)
│
├── docs/                        — вся документация
│   ├── index.md                — карта навигации
│   ├── agents/                 — описания агентов
│   ├── database/               — справочник БД
│   ├── guides/                 — руководства (DoD, env, logging)
│   └── templates/              — шаблоны документов
│
├── deploy/                      — Docker конфигурация
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── reports/                     — сгенерированные отчёты (git-ignored)
```

---

## Быстрый старт

### Prerequisites

- Python 3.11+
- PostgreSQL (доступ на чтение к базам WB/OZON — предоставляется подрядчиком)
- Docker (опционально, для бота)

### 1. Настроить переменные окружения

```bash
cp .env.example .env
# Заполнить реальные значения в .env
```

### 2. Зависимости для скриптов

```bash
pip install psycopg2-binary python-dotenv
```

### 3. Запустить аналитику

```bash
# Ежедневный отчёт
python scripts/daily_analytics.py --date 2026-02-08 --save --notion

# Отчёт за период
python scripts/period_analytics.py --start 2026-02-01 --end 2026-02-07

# Месячный отчёт
python scripts/monthly_analytics.py --month 2026-01 --save --notion
```

### 4. Запустить Telegram-бот

```bash
cd agents/oleg
pip install -r requirements.txt
cp .env.example .env
nano .env  # заполнить токены

# Запуск
python -m agents.oleg

# Или через Docker (рекомендуется)
docker compose -f deploy/docker-compose.yml up -d
```

Подробнее: [`docs/agents/telegram-bot.md`](docs/agents/telegram-bot.md)

---

## Telegram-бот

AI-ассистент финансового менеджера с доступом ко всем данным бренда.

**Возможности:**
- Шаблонные отчёты (daily, period, ABC) с интерактивным выбором периодов
- Кастомные запросы на естественном языке через AI
- Автоматическая ежедневная рассылка после 10:05 МСК
- Уведомления о готовности данных (проверка каждые 5 мин, 06:00-12:00 МСК)
- История отчётов с full-text search
- Синхронизация с Notion

**AI-маршрутизация:**
- z.ai (95% запросов, ~$0.002/запрос) — быстрые и простые вопросы
- Claude (5% запросов, ~$0.02/запрос) — сложные аналитические запросы

**Использование:**
1. Найти бота в Telegram
2. `/start` → ввести пароль
3. `/menu` → выбрать тип отчёта или задать вопрос

Полное описание: [`docs/agents/telegram-bot.md`](docs/agents/telegram-bot.md)

---

## Аналитический движок

Ядро системы — скрипты генерации отчётов с верифицированными формулами маржи (<1% расхождение с PowerBI).

### Типы отчётов

| Скрипт | Назначение | Пример |
|--------|-----------|--------|
| `daily_analytics.py` | День vs день + 7-дневный тренд | `--date 2026-02-08 --save --notion` |
| `period_analytics.py` | Произвольный период, 4-уровневая иерархия | `--start 2026-02-01 --end 2026-02-07` |
| `monthly_analytics.py` | Месяц с понедельной динамикой | `--month 2026-01 --save --notion` |

### Ключевые механизмы

**Confidence Scoring** — каждая гипотеза оценивается по формуле:
```
confidence = 0.4 × direction_agreement + 0.35 × magnitude + 0.25 × stability
```

| Диапазон | Интерпретация |
|----------|---------------|
| 0.8-1.0 | Сильный вывод |
| 0.6-0.8 | Вывод с оговоркой |
| 0.3-0.6 | Требует ручной проверки |
| 0.0-0.3 | Спекулятивно |

**Red Team** — алгоритмические контраргументы к каждой гипотезе (день недели, неполные данные, низкая база, изменение СПП, лаг выкупов).

**5-рычажная декомпозиция маржи:** Цена до СПП → СПП% → ДРР → Логистика → Выкуп

**4-уровневая иерархия:** Бренд → Канал (WB/OZON) → Модель → Статус товара

### Архитектурные правила

- **Все DB-запросы** — только в `scripts/data_layer.py`
- **Конфигурация** — только в `scripts/config.py` (читает `.env`)
- **Notion-синхронизация** — через `scripts/notion_sync.py`

Полное описание: [`docs/agents/analytics-engine.md`](docs/agents/analytics-engine.md)

---

## Notion-интеграция

Отчёты автоматически синхронизируются с базой **"Фин аналитика"** в Notion.

```bash
# Автоматически при генерации отчёта
python scripts/daily_analytics.py --date 2026-02-08 --save --notion

# Ручная синхронизация
python scripts/notion_sync.py --file reports/2026-02-01_2026-02-07_analytics.md
```

- Если страница с таким периодом существует — контент перезаписывается
- Если нет — создаётся новая страница
- Отчёты из бота помечаются "Telegram Bot", из скриптов — "Скрипт"

---

## Источники данных

| Источник | БД | Что хранит | Обновление |
|----------|-------|------------|------------|
| Wildberries | `pbi_wb_wookiee` (PostgreSQL) | Финансы, трафик, заказы, реклама (853K+ строк) | Ежедневно ~06:18 МСК |
| OZON | `pbi_ozon_wookiee` (PostgreSQL) | Финансы, трафик, заказы, реклама (156K+ строк) | Ежедневно ~07:03 МСК |
| Товарная матрица | Supabase | Модели, артикулы, SKU, статусы, цвета | По запросу |
| Notion | API | Хранение отчётов | При генерации |

Базы WB/OZON предоставляются подрядчиком (доступ только на чтение). Данные обновляются автоматически.

Полный справочник схем, формул и маппинга: [`docs/database/DATABASE_REFERENCE.md`](docs/database/DATABASE_REFERENCE.md)

Известные проблемы качества данных: [`docs/database/DATA_QUALITY_NOTES.md`](docs/database/DATA_QUALITY_NOTES.md)

---

## Бизнес-правила

Аналитика опирается на правила Wookiee как на **гибкие ориентиры**, а не жёсткие ограничения:

- Декомпозиция маржи по 5 рычагам: Цена до СПП → СПП% → ДРР → Логистика → Выкуп
- Целевая рентабельность: от 15% по чистой прибыли
- ABC-классификация: A (~70% маржи), B (~20%), C (~10%)
- Рекомендации описывают цепочки причин и следствий с расчётом эффекта в рублях

---

## Технологический стек

| Категория | Технологии |
|-----------|-----------|
| Язык | Python 3.11+ |
| Базы данных | PostgreSQL (финансы WB/OZON), Supabase (товарная матрица), SQLite FTS5 (история отчётов) |
| Бот | aiogram 3.15, APScheduler 3.10.4 |
| AI | z.ai API (GLM-4.5-flash), Claude API (Sonnet 4.5) |
| Интеграции | Notion API, Bitrix24 API (планируется) |
| Инфраструктура | Docker, docker-compose |
| Безопасность | bcrypt (пароли), .env (секреты), .cursorignore (защита от AI) |

---

## Roadmap

### Активные компоненты
- Telegram Bot Agent — ежедневные отчёты, AI-запросы, мониторинг данных
- Analytics Engine — daily/period/monthly аналитика с confidence scoring
- SKU Database — товарная матрица на Supabase (22 модели, 1450 SKU)

### В разработке
- Василий (MP Localization Agent) — автоматизация перемещений между складами (WB/OZON)
- Людмила (CRM Agent) — постановка задач, анализ процессов, работа с Bitrix24
- Расширение AI-возможностей бота (более глубокий анализ, прогнозирование)

### Планируемые
- AB-тестирование и ценовые эксперименты
- Единый дашборд с real-time данными

---

## Для AI-агентов

Все правила проекта: [`AGENTS.md`](AGENTS.md) (единственный источник истины).

Навигация по документации: [`docs/index.md`](docs/index.md).

**Обязательные правила:**
- DB-запросы: только `scripts/data_layer.py`
- GROUP BY по модели: ВСЕГДА с `LOWER()`
- Процентные метрики: ТОЛЬКО средневзвешенные
- Проблемы качества данных: фиксировать в `docs/database/DATA_QUALITY_NOTES.md`

---

## Для разработчиков

- **Git-конвенции:** коммиты на английском, ветки `feature/`, `fix/`, `docs/`, `refactor/`
- **DoD чеклист:** [`docs/guides/dod.md`](docs/guides/dod.md)
- **Настройка окружения:** [`docs/guides/environment-setup.md`](docs/guides/environment-setup.md)
- **Архитектурные решения:** [`docs/adr.md`](docs/adr.md)
- **Логирование:** [`docs/guides/logging.md`](docs/guides/logging.md)
