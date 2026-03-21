# Полная карта проекта Wookiee

> Справочник по архитектуре, агентам, ботам и инструментам.
> Создан для понимания текущей структуры перед пересборкой.

---

## 1. Общая архитектура

```
╔══════════════════════════════════════════════════════════════════════╗
║                        WOOKIEE SYSTEM                               ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  ПОЛЬЗОВАТЕЛИ                                                       ║
║  ┌──────────┐    ┌──────────────┐    ┌───────────────┐              ║
║  │ Telegram  │    │ CLI-скрипты  │    │ HTTP (Vasily) │              ║
║  │ (человек) │    │ (разработчик)│    │ (Google Sheets)│             ║
║  └─────┬─────┘   └──────┬───────┘    └───────┬───────┘             ║
║        │                 │                     │                     ║
║  ══════╪═════════════════╪═════════════════════╪═════════ ВХОДЫ ═══ ║
║        │                 │                     │                     ║
║  ┌─────▼──────────────────▼─────┐    ┌────────▼────────┐           ║
║  │      OLEG (agents/oleg)      │    │  VASILY API     │           ║
║  │  ┌─────────────────────────┐ │    │  (FastAPI)      │           ║
║  │  │  Telegram Bot (aiogram) │ │    │  POST /run      │           ║
║  │  │  - /report_daily        │ │    │  GET /status    │           ║
║  │  │  - /report_weekly       │ │    │  GET /health    │           ║
║  │  │  - /marketing_daily     │ │    └────────┬────────┘           ║
║  │  │  - /feedback            │ │             │                     ║
║  │  │  - /health              │ │    ┌────────▼────────┐           ║
║  │  │  - свободный текст      │ │    │ WB Localization │           ║
║  │  └────────────┬────────────┘ │    │ → Google Sheets │           ║
║  │               │              │    └─────────────────┘           ║
║  │  ┌────────────▼────────────┐ │                                   ║
║  │  │    ORCHESTRATOR         │ │    ┌─────────────────┐           ║
║  │  │  (цепочка агентов)      │ │    │  SHEETS SYNC    │           ║
║  │  │                         │ │    │  (ежедневная    │           ║
║  │  │  ┌───────┐ ┌─────────┐ │ │    │   синхронизация │           ║
║  │  │  │Report-│ │Research-│ │ │    │   в G.Sheets)   │           ║
║  │  │  │  er   │ │  er     │ │ │    └─────────────────┘           ║
║  │  │  │(30 SQL│ │(10 инст-│ │ │                                   ║
║  │  │  │ инстр)│ │рументов)│ │ │    ┌─────────────────┐           ║
║  │  │  └───────┘ └─────────┘ │ │    │   IBRAHIM        │           ║
║  │  │  ┌───────┐ ┌─────────┐ │ │    │  (Data Engineer) │           ║
║  │  │  │Quali- │ │Market-  │ │ │    │  ETL: WB/OZON   │           ║
║  │  │  │  ty   │ │  er     │ │ │    │  → PostgreSQL   │           ║
║  │  │  │(5 инс)│ │(маркет.)│ │ │    │  05:00 ежедн.   │           ║
║  │  │  └───────┘ └─────────┘ │ │    └─────────────────┘           ║
║  │  └─────────────────────────┘ │                                   ║
║  │                              │                                   ║
║  │  ┌─────────────────────────┐ │                                   ║
║  │  │   APScheduler (cron)    │ │                                   ║
║  │  │  09:00 — daily report   │ │                                   ║
║  │  │  10:15 пн — weekly      │ │                                   ║
║  │  │  03:00 1-й пн — monthly │ │                                   ║
║  │  │  */6ч — watchdog        │ │                                   ║
║  │  │  */Nч — anomaly monitor │ │                                   ║
║  │  └─────────────────────────┘ │                                   ║
║  │                              │                                   ║
║  │  ┌─────────────────────────┐ │                                   ║
║  │  │   Watchdog (здоровье)   │ │                                   ║
║  │  │  - диагностика          │ │                                   ║
║  │  │  - алерты в Telegram    │ │                                   ║
║  │  └─────────────────────────┘ │                                   ║
║  └──────────────────────────────┘                                   ║
║                                                                      ║
║  ══════════════════════════════════════════════════ ДАННЫЕ ═════════ ║
║                                                                      ║
║  ┌──────────────────────────────────────────────┐                   ║
║  │           shared/ (инфраструктура)           │                   ║
║  │  config.py ← .env (единый источник)          │                   ║
║  │  data_layer.py (127KB, все SQL-запросы)       │                   ║
║  │  model_mapping.py (нормализация моделей)      │                   ║
║  │  clients/ (WB, OZON, Sheets, MoySklad, LLM) │                   ║
║  └──────────────┬───────────────────────────────┘                   ║
║                 │                                                    ║
║  ┌──────────────▼───────────────────────────────┐                   ║
║  │              БАЗЫ ДАННЫХ                      │                   ║
║  │  PostgreSQL:                                  │                   ║
║  │    pbi_wb_wookiee (WB legacy)                │                   ║
║  │    pbi_ozon_wookiee (OZON legacy)            │                   ║
║  │    wookiee_marketplace (managed, Ibrahim)     │                   ║
║  │  Supabase: sku_database (матрица товаров)     │                   ║
║  │  SQLite: state_store (локальное состояние)    │                   ║
║  └──────────────────────────────────────────────┘                   ║
║                                                                      ║
║  ══════════════════════════════════════════════════ ВЫХОДЫ ═════════ ║
║                                                                      ║
║  ┌────────┐  ┌────────┐  ┌─────────────┐  ┌──────┐                ║
║  │Telegram│  │ Notion │  │Google Sheets │  │Логи  │                ║
║  │(отчёты)│  │(отчёты)│  │(дашборды)    │  │/logs │                ║
║  └────────┘  └────────┘  └─────────────┘  └──────┘                ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 2. Docker-контейнеры (Production)

```
docker-compose.yml (deploy/)
│
├── wookiee-oleg        → python -m agents.oleg
│   ├── 1 CPU, 1GB RAM
│   ├── Telegram bot (polling)
│   ├── APScheduler (cron-задачи)
│   ├── Watchdog (мониторинг)
│   └── 4 AI-агента (Reporter, Researcher, Quality, Marketer)
│
├── sheets-sync         → python -m services.sheets_sync.control_panel
│   ├── 0.5 CPU, 512MB RAM
│   └── Ежедневная синхронизация в Google Sheets
│
└── vasily-api          → uvicorn services.vasily_api.app:app
    ├── 0.5 CPU, 512MB RAM
    ├── POST /run — запуск расчёта WB-локализации
    ├── GET /status — статус расчёта
    └── GET /health — healthcheck
```

**Сеть:** `n8n-docker-caddy_default` (общая с N8N и Caddy)
**Restart policy:** `unless-stopped`

---

## 3. Агент OLEG — подробная карта

### Точка входа

```
python -m agents.oleg
  → agents/oleg/__main__.py
    → OlegApp().run()    (agents/oleg/app.py, 53KB)
```

### Процесс запуска

```
OlegApp.run()
│
├── 1. setup()
│   ├── Инициализация LLM-клиента (OpenRouter)
│   ├── Создание Reporter, Researcher, Quality, Marketer агентов
│   ├── Создание Orchestrator (координирует агентов)
│   ├── Создание Pipeline (генерация отчётов)
│   ├── Создание Watchdog (мониторинг здоровья)
│   └── Инициализация State Store (SQLite)
│
├── 2. _check_telegram_conflict()
│   ├── POST /close — закрыть чужую сессию
│   ├── wait 3 секунды
│   ├── GET /getUpdates (timeout=15с) — long-poll
│   └── Если 409 Conflict → другой экземпляр жив → skip polling
│
├── 3. _setup_scheduler()
│   └── Регистрация всех cron-задач (см. таблицу ниже)
│
├── 4. Запуск Telegram polling (aiogram Dispatcher)
│   └── Или: только scheduler (если обнаружен конфликт)
│
└── 5. Watchdog heartbeat (каждые 6ч)
```

### Telegram-команды

| Команда | Действие |
|---------|----------|
| `/start` | Приветствие |
| `/help` | Список команд |
| `/report_daily` | Дневной P&L отчёт |
| `/report_weekly` | Недельный отчёт |
| `/report_monthly` | Месячный отчёт |
| `/marketing_daily` | Маркетинговый дневной |
| `/marketing_weekly` | Маркетинговый недельный |
| `/marketing_monthly` | Маркетинговый месячный |
| `/feedback` | Обратная связь по отчётам |
| `/health` | Диагностика системы |
| *свободный текст* | → Orchestrator → агенты (произвольный запрос) |

### 4 суб-агента

```
Orchestrator (agents/oleg/orchestrator/)
│
├── Reporter (agents/oleg/agents/reporter/)
│   ├── 30 SQL-инструментов (финансы, цены, трафик)
│   ├── ReAct-цикл: reason → tool call → reasoning
│   ├── Timeout: 30с на инструмент, 120с общий
│   └── Запускается: при КАЖДОМ отчёте
│
├── Researcher (agents/oleg/agents/researcher/)
│   ├── 10 инструментов (WB API, корреляции, МойСклад)
│   ├── Гипотезо-ориентированный поиск причин
│   └── Запускается: при аномалиях (margin delta >10%, DRR delta >30%)
│
├── Quality (agents/oleg/agents/quality/)
│   ├── 5 инструментов (playbook CRUD, верификация)
│   ├── Проверяет обратную связь, обновляет правила
│   └── Запускается: при /feedback
│
└── Marketer (agents/oleg/agents/marketer/)
    ├── Анализ маркетинговой воронки
    ├── Impressions → Clicks → Cart → Orders → Buyouts
    └── Запускается: при маркетинг-отчётах
```

### Расписание (APScheduler, MSK)

| Задача | Время | Частота | Retry |
|--------|-------|---------|-------|
| Daily report | 09:00 | Ежедневно | 3 попытки, 30 мин интервал |
| Weekly report | 10:15 пн | Еженедельно | — |
| Monthly report | 03:00 1-й пн | Ежемесячно | — |
| Marketing weekly | из config | Еженедельно | — |
| Marketing monthly | из config | Ежемесячно | — |
| Watchdog heartbeat | */6ч | Каждые 6 часов | — |
| Anomaly monitor | */Nч в :30 | Каждые N часов | — |
| Weekly price review | из config, пн | Еженедельно | — |
| Monthly price review | из config, 1-й пн | Ежемесячно | — |
| Regression refresh | 03:00 1-е число | Ежемесячно | — |
| Promotion scan | */12ч в :15 | Каждые 12 часов | — |
| Data ready check | 06:00–{daily+3ч} | Ежечасно | — |

### Механизмы дедупликации

| Механизм | Где | Окно |
|----------|-----|------|
| State store (SQLite) | `storage/state_store.py` | По дате отчёта |
| Message hash dedup | `app.py:_sent_msg_hashes` | 5 минут |
| Alert hash dedup | `watchdog/alerter.py:_sent_hashes` | 12 часов |
| Anomaly dedup | `anomaly/anomaly_monitor.py` | 12 часов |
| Telegram conflict | `app.py:_check_telegram_conflict()` | При старте |

---

## 4. Агент IBRAHIM — подробная карта

### Точка входа

```
python -m agents.ibrahim <command>
  → agents/ibrahim/__main__.py
```

### Команды

| Команда | Действие |
|---------|----------|
| `sync` | ETL: WB/OZON API → PostgreSQL (вчера или --from/--to) |
| `reconcile` | Сверка managed vs source DB (допуск <1%) |
| `status` | Статистика управляемой БД |
| `health` | Полная диагностика (свежесть, полнота, консистентность) |
| `analyze-api` | LLM-анализ API-документации WB/OZON |
| `analyze-schema` | Предложения по оптимизации схемы |
| `run-scheduler` | Фоновый планировщик (05:00 daily sync) |

### Ключевые файлы

```
agents/ibrahim/
├── __main__.py          ← CLI точка входа (argparse)
├── ibrahim_service.py   ← Основная логика
├── scheduler.py         ← APScheduler (05:00 sync, воскресенье API-анализ)
├── config.py            ← Конфигурация (API-ключи, логирование)
├── playbook.md          ← Правила и формулы
└── tasks/
    ├── etl_operator.py   ← Оркестрация ETL
    ├── reconciliation.py ← Сверка данных
    ├── schema_manager.py ← Управление схемой БД
    └── data_quality.py   ← Проверки качества
```

### Целевая БД

```
wookiee_marketplace (PostgreSQL)
├── wb schema
│   ├── abc_date, orders, sales, stocks
│   ├── nomenclature, content_analysis
│   └── wb_adv (реклама)
└── ozon schema
    ├── abc_date, orders, returns, stocks
    ├── nomenclature, adv_stats_daily
    └── ozon_adv_api
```

---

## 5. Сервисы

### Marketplace ETL (`services/marketplace_etl/`)

```
Используется Ibrahim'ом для ETL
├── config/database.py    ← подключения, аккаунты
├── etl/
│   ├── wb_etl.py         ← WB: extract → transform → load
│   ├── ozon_etl.py       ← OZON: extract → transform → load
│   ├── reconciliation.py ← сверка managed vs legacy
│   └── scheduler.py      ← APScheduler (ежедневный sync)
└── Стратегия: UPSERT с unique keys (идемпотентность)
```

### Sheets Sync (`services/sheets_sync/`)

```
Синхронизация данных → Google Sheets
├── runner.py              ← CLI (--list для списка задач)
├── control_panel.py       ← Основной контроллер (Docker CMD)
├── config.py              ← Google credentials, spreadsheet IDs
└── sync/
    ├── sync_wb_prices.py        ← WB цены
    ├── sync_wb_stocks.py        ← WB остатки
    ├── sync_wb_feedbacks.py     ← WB отзывы
    ├── sync_wb_bundles.py       ← WB бандлы
    ├── sync_ozon_stocks_prices.py ← OZON остатки+цены
    ├── sync_moysklad.py         ← МойСклад данные
    ├── sync_fin_data.py         ← Финансовые данные
    └── sync_search_analytics.py ← Поисковая аналитика
```

### Vasily API (`services/vasily_api/`)

```
HTTP API для расчёта WB-локализации (FastAPI + uvicorn)
├── app.py         ← FastAPI приложение
├── POST /run      ← Запуск расчёта (фоновая задача)
├── GET /status    ← Статус (idle/running/done/error)
├── GET /health    ← Healthcheck
└── Аутентификация: X-API-Key header
```

### WB Localization (`services/wb_localization/`)

```
Расчёт оптимальной WB-локализации (минимизация picking time)
└── Результаты экспортируются в Google Sheets через Vasily API
```

### OZON Delivery (`services/ozon_delivery/`)

```
Утилиты для оптимизации доставки OZON FBO
└── CLI-инструмент (не Docker-контейнер)
```

---

## 6. CLI-скрипты (`scripts/`)

| Скрипт | Назначение | Как запускать |
|--------|------------|---------------|
| `run_report.py` | Все отчёты (daily/weekly/period/marketing) | `python scripts/run_report.py daily [YYYY-MM-DD]` |
| | | `python scripts/run_report.py weekly [YYYY-MM-DD]` |
| | | `python scripts/run_report.py period FROM TO` |
| | | `python scripts/run_report.py marketing [FROM [TO]]` |
| `run_price_analysis.py` | Ценовой анализ | `python scripts/run_price_analysis.py` |
| `abc_analysis.py` | ABC-анализ (базовый, по каналам) | `python scripts/abc_analysis.py` |
| `abc_analysis_unified.py` | ABC-анализ (расширенный, объединённый) | `python scripts/abc_analysis_unified.py` |
| `abc_helpers.py` | Общие ABC-функции (не CLI) | импорт из abc_analysis/abc_analysis_unified |
| `notion_sync.py` | Sync отчётов → Notion | `python scripts/notion_sync.py` |
| `wb_vuki_ratings.py` | Рейтинги WB Vuki | `python scripts/wb_vuki_ratings.py` |

**Общий паттерн:** `run_report.py` создаёт `OlegApp()`, вызывает `pipeline.generate_report()`.

**Шим обратной совместимости:**
- `scripts/data_layer.py` → переадресация в `shared/data_layer.py`

---

## 7. Инфраструктура (`shared/`)

```
shared/
├── config.py                 ← ЕДИНЫЙ источник конфигурации (← .env)
│   ├── DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
│   ├── DB_WB (pbi_wb_wookiee), DB_OZON (pbi_ozon_wookiee)
│   ├── MARKETPLACE_DB_CONFIG (wookiee_marketplace)
│   ├── MODEL_LIGHT (GLM 4.7 Flash), MODEL_MAIN, MODEL_HEAVY
│   ├── NOTION_TOKEN, NOTION_DATABASE_ID
│   └── TIMEZONE (Europe/Moscow)
│
├── data_layer.py             ← ВСЕ SQL-запросы (127KB)
│   ├── get_wb_finance()      — WB финансы
│   ├── get_wb_by_model()     — WB по моделям (LOWER!)
│   ├── get_wb_traffic()      — WB воронка
│   ├── get_ozon_finance()    — OZON финансы
│   ├── get_ozon_by_model()   — OZON по моделям
│   ├── get_ozon_traffic()    — OZON воронка
│   ├── to_float(), format_num(), format_pct() — форматирование
│   └── map_to_osnova(), get_osnova_sql() — нормализация моделей
│
├── model_mapping.py          ← Маппинг названий товаров
│   ├── MODEL_OSNOVA_MAPPING (vuki → Vuki, moon → Moon)
│   ├── SUBMODEL_MAPPING (варианты: Vuki-N, Vuki-W)
│   └── KNOWN_PHASING_OUT (устаревшие: Olivia, Roxy, Mia)
│
├── notion_blocks.py          ← Markdown→Notion конвертер (общий)
│   ├── parse_inline() — bold, BBCode
│   ├── md_to_notion_blocks() — таблицы, заголовки, списки
│   └── remove_empty_sections() — очистка пустых секций
│
├── clients/
│   ├── openrouter_client.py  ← LLM (OpenRouter, AsyncOpenAI)
│   ├── wb_client.py          ← Wildberries API (async reports)
│   ├── ozon_client.py        ← OZON Seller API
│   ├── sheets_client.py      ← Google Sheets API
│   └── moysklad_client.py    ← МойСклад CRM
│
└── utils/
    └── json_utils.py
```

---

## 8. Базы данных

```
┌───────────────────────────────────────────────────────────┐
│                     PostgreSQL (Timeweb)                   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  pbi_wb_wookiee (legacy, read-only source)               │
│  ├── abc_date    — финансы по дням/артикулам              │
│  ├── orders      — заказы                                 │
│  ├── sales       — продажи                                │
│  ├── stocks      — остатки на складах                     │
│  ├── nomenclature — карточки товаров                      │
│  ├── wb_adv      — рекламные расходы                      │
│  └── content_analysis — органическая воронка              │
│                                                           │
│  pbi_ozon_wookiee (legacy, read-only source)             │
│  ├── abc_date, orders, returns, stocks                   │
│  ├── nomenclature, adv_stats_daily                       │
│  └── ozon_adv_api                                        │
│                                                           │
│  wookiee_marketplace (managed by Ibrahim ETL)            │
│  ├── wb.*    — копия WB с ETL-трансформацией             │
│  └── ozon.*  — копия OZON с ETL-трансформацией           │
│                                                           │
├───────────────────────────────────────────────────────────┤
│  Переключение: DATA_SOURCE = "legacy" | "managed"        │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│  Supabase (cloud)                                         │
│  sku_database — матрица товаров (SKU, цвета, модели)     │
│  RLS включён, CLI: python sku_database/db.py             │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│  SQLite (локально в контейнере)                           │
│  state_store — состояние Oleg (даты отчётов, retry)      │
└───────────────────────────────────────────────────────────┘
```

---

## 9. Внешние интеграции

```
ВХОДЯЩИЕ ДАННЫЕ:
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ Wildberries │     │    OZON      │     │  МойСклад    │
│    API      │     │    API       │     │    API       │
└──────┬──────┘     └──────┬───────┘     └──────┬───────┘
       │                   │                     │
       └───────────┬───────┴─────────────────────┘
                   │
          ┌────────▼────────┐
          │  shared/clients/ │
          └────────┬────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐   ┌─────▼─────┐  ┌────▼─────┐
│ Oleg  │   │  Ibrahim  │  │  Sheets  │
│(анализ)│  │   (ETL)   │  │  Sync    │
└───┬───┘   └───────────┘  └────┬─────┘
    │                            │
    ▼                            ▼
ИСХОДЯЩИЕ ДАННЫЕ:
┌────────┐  ┌────────┐    ┌──────────┐    ┌──────┐
│Telegram│  │ Notion │    │G. Sheets │    │ Логи │
│(отчёты │  │(детальн│    │(дашборды │    │/logs │
│ алерты)│  │ отчёты)│    │ таблицы) │    │      │
└────────┘  └────────┘    └──────────┘    └──────┘

LLM (AI-мозги):
┌────────────────────────────────────────┐
│  OpenRouter API (единый провайдер)     │
│  ├── LIGHT: GLM 4.7 Flash ($0.07/1M)  │
│  ├── MAIN:  GLM 4.7 ($0.06/1M)        │
│  ├── HEAVY: Gemini 3 Flash ($0.50/1M) │
│  └── FREE:  Last-resort fallback      │
└────────────────────────────────────────┘
```

---

## 10. Потоки данных

### Отчёт по запросу (Telegram)

```
Пользователь → /report_daily
    → telegram_bot.py → handler
        → orchestrator.run_chain()
            → Reporter Agent (ReAct loop)
                → data_layer.get_wb_finance()  → PostgreSQL
                → data_layer.get_ozon_finance() → PostgreSQL
                → LLM (OpenRouter) → анализ + текст
            → [если аномалия] Researcher Agent
                → wb_client → WB API
                → moysklad_client → МойСклад
                → calculate_correlation() → scipy
        → format response + cost footer
        → split into Telegram chunks (4096 char limit)
    → Telegram API → пользователь
    → notion_service.py → Notion (сохранение)
```

### Автоматический отчёт (Scheduler)

```
APScheduler (09:00 MSK)
    → _scheduled_daily_report()
        → state_store: уже запускался сегодня?
            → да: skip
            → нет: mark started
        → pipeline.generate_report()
            → gate_checker: данные готовы?
                → нет: schedule retry (30 мин)
                → да: proceed
            → orchestrator.run_chain()
                → [те же агенты]
        → send to Telegram (all admins)
        → save to Notion
        → state_store: mark completed
```

### ETL (Ibrahim)

```
Ibrahim scheduler (05:00 MSK)
    → ETL Operator
        → WB ETL:
            → wb_client.py → WB API (reports)
            → transform (normalize, LOWER, dedup)
            → UPSERT → wookiee_marketplace.wb.*
        → OZON ETL:
            → ozon_client.py → OZON API (reports)
            → transform
            → UPSERT → wookiee_marketplace.ozon.*
    → Reconciliation
        → compare managed vs legacy (variance < 1%)
        → log results
```

---

## 11. Решённые проблемы (март 2026)

Все ранее зафиксированные проблемы и дублирования устранены:

| # | Было | Решение |
|---|------|---------|
| 1 | Telegram 409 conflict detection ненадёжен | Исправлен `_check_telegram_conflict()`: HTTP 409 check + 2 попытки |
| 2 | Дублирование Markdown→Notion конвертера | Общие функции в `shared/notion_blocks.py`, оба клиента используют |
| 3 | Дублирование ABC-логики | Общие функции в `scripts/abc_helpers.py` |
| 4 | Шим `scripts/config.py` | Удалён, `notion_sync.py` импортирует из `shared/config.py` напрямую |
| 5 | 4 однотипных CLI-скрипта отчётов | Объединены в `scripts/run_report.py` (daily/weekly/period/marketing) |
| 6 | Мёртвый код (bitrix_oauth, zai_client, db_config) | Удалён |

---

## 12. Дерево файлов (ключевые)

```
Wookiee/
├── .env                             ← секреты (не в git)
├── AGENTS.md                        ← правила для ВСЕХ разработчиков
├── CLAUDE.md                        ← инструкции для Claude Code
├── Makefile                         ← make oleg, make test, make oleg-deploy
│
├── agents/
│   ├── oleg/                        ← ГЛАВНЫЙ АГЕНТ
│   │   ├── __main__.py              ← точка входа
│   │   ├── app.py                   ← 53KB, весь жизненный цикл
│   │   ├── config.py                ← настройки (расписание, пороги)
│   │   ├── playbook.md              ← бизнес-правила (115KB!)
│   │   ├── marketing_playbook.md    ← правила маркетинга
│   │   ├── bot/
│   │   │   └── telegram_bot.py      ← обработчики команд
│   │   ├── orchestrator/
│   │   │   └── orchestrator.py      ← координация цепочки агентов
│   │   ├── pipeline/
│   │   │   └── report_pipeline.py   ← генерация отчётов
│   │   ├── agents/
│   │   │   ├── reporter/            ← Reporter (30 SQL tools)
│   │   │   │   ├── agent.py
│   │   │   │   ├── tools.py
│   │   │   │   └── prompts.py
│   │   │   ├── researcher/          ← Researcher (10 tools)
│   │   │   ├── quality/             ← Quality (5 tools)
│   │   │   └── marketer/            ← Marketer
│   │   ├── services/
│   │   │   └── notion_service.py    ← Notion API (httpx, async)
│   │   ├── watchdog/
│   │   │   ├── watchdog.py          ← health monitoring
│   │   │   └── alerter.py           ← Telegram алерты
│   │   ├── anomaly/
│   │   │   └── anomaly_monitor.py   ← детекция аномалий
│   │   └── storage/
│   │       └── state_store.py       ← SQLite (состояние отчётов)
│   │
│   └── ibrahim/                     ← DATA ENGINEER
│       ├── __main__.py              ← CLI (sync, reconcile, status, health)
│       ├── ibrahim_service.py       ← основная логика
│       ├── scheduler.py             ← APScheduler (05:00 sync)
│       ├── config.py
│       ├── playbook.md
│       └── tasks/
│           ├── etl_operator.py      ← ETL оркестрация
│           ├── reconciliation.py    ← сверка данных
│           ├── schema_manager.py    ← управление схемой
│           └── data_quality.py      ← проверки качества
│
├── services/
│   ├── marketplace_etl/             ← ETL (используется Ibrahim)
│   │   ├── config/database.py
│   │   └── etl/
│   │       ├── wb_etl.py, ozon_etl.py
│   │       ├── reconciliation.py
│   │       └── scheduler.py
│   ├── sheets_sync/                 ← Google Sheets
│   │   ├── runner.py, control_panel.py
│   │   ├── config.py
│   │   └── sync/
│   │       ├── sync_wb_prices.py
│   │       ├── sync_wb_stocks.py
│   │       ├── sync_wb_feedbacks.py
│   │       ├── sync_ozon_stocks_prices.py
│   │       ├── sync_moysklad.py
│   │       ├── sync_fin_data.py
│   │       └── sync_search_analytics.py
│   ├── vasily_api/                  ← HTTP API (FastAPI)
│   │   └── app.py
│   ├── wb_localization/             ← WB-локализация
│   └── ozon_delivery/               ← OZON доставка
│
├── shared/                          ← ОБЩАЯ ИНФРАСТРУКТУРА
│   ├── config.py                    ← единый источник (.env)
│   ├── data_layer.py                ← все SQL-запросы (127KB)
│   ├── model_mapping.py             ← нормализация моделей
│   ├── notion_blocks.py             ← Markdown→Notion конвертер
│   └── clients/                     ← API-клиенты
│
├── scripts/                         ← CLI-утилиты
│   ├── run_report.py                ← единый CLI (daily/weekly/period/marketing)
│   ├── run_price_analysis.py
│   ├── abc_analysis.py
│   ├── abc_analysis_unified.py
│   ├── abc_helpers.py               ← общие ABC-функции
│   ├── notion_sync.py
│   ├── wb_vuki_ratings.py
│   └── data_layer.py                ← шим → shared/data_layer.py
│
├── sku_database/                    ← Supabase матрица товаров
│   ├── db.py                        ← CLI (status, colors, models, query)
│   ├── config/
│   ├── database/                    ← SQL-схемы
│   └── scripts/                     ← миграции
│
├── deploy/
│   ├── docker-compose.yml           ← 3 контейнера
│   ├── Dockerfile                   ← Oleg + Sheets Sync
│   ├── Dockerfile.vasily_api        ← Vasily API
│   ├── deploy.sh                    ← скрипт деплоя
│   ├── healthcheck.py               ← Docker healthcheck
│   └── healthcheck_agent.py         ← проверка агента
│
├── docs/
│   ├── index.md                     ← навигация
│   ├── architecture.md              ← архитектура
│   ├── infrastructure.md            ← инфраструктура (Timeweb, Docker)
│   ├── database/                    ← DB-документация
│   ├── guides/                      ← гайды разработки
│   ├── plans/                       ← активные планы
│   └── archive/                     ← архивные агенты (Lyudmila, Vasily)
│
├── tests/oleg/                      ← unit-тесты
├── logs/                            ← runtime логи
└── reports/                         ← сгенерированные отчёты
```

---

## 13. Конфигурация — иерархия

```
.env (root, не в git)
│
├── shared/config.py (ЕДИНЫЙ ИСТОЧНИК)
│   │
│   ├── agents/oleg/config.py (расширяет: Telegram, расписание, пороги)
│   ├── agents/ibrahim/config.py (расширяет: API-ключи маркетплейсов)
│   ├── services/sheets_sync/config.py (расширяет: Google credentials)
│   ├── services/marketplace_etl/config/database.py (расширяет: ETL DB)
│   │
│   └── Шим обратной совместимости:
│       └── scripts/data_layer.py → shared/data_layer.py
│
└── sku_database/.env (отдельный, Supabase credentials)
```

---

## 14. Makefile

```makefile
make oleg           # Запуск Oleg локально
make oleg-test      # Unit-тесты
make oleg-check     # Проверка scheduler
make oleg-deploy    # Деплой в Docker (deploy/deploy.sh)
make test           # Все тесты
```

---

## 15. Deployment

```
Сервер: Timeweb VPS
├── Docker + Docker Compose
├── Caddy (reverse proxy)
├── N8N (автоматизации, общая сеть)
└── deploy/deploy.sh:
    1. Остановить старый контейнер
    2. Проверить .env (TELEGRAM_BOT_TOKEN, DB_*)
    3. docker compose build
    4. docker compose up -d
    5. wait 10s + healthcheck
    6. Показать логи
```
