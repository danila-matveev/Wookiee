# Wookiee — Система аналитических отчётов

> Единая точка входа для понимания архитектуры, компонентов и эксплуатации.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│  Cron (каждые 30 мин, 07:00–18:00 MSK)                     │
│  python scripts/run_report.py --schedule                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Report Runner (scripts/run_report.py)                      │
│  • Определяет типы отчётов по дню недели (D-10)             │
│  • Lock-file дедупликация (D-06)                            │
│  • Stub-уведомления в Telegram (D-07)                       │
│  • Final alert в 18:00 если ничего не опубликовано (D-08)   │
└────────────────────────┬────────────────────────────────────┘
                         │ для каждого report_type
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Report Pipeline (agents/oleg/pipeline/report_pipeline.py)  │
│  7 шагов:                                                   │
│  1. Gate Check — hard/soft gates по свежести данных          │
│  2. Pre-flight Telegram — "Запущена генерация..."            │
│  3. LLM Chain + Retry (до 2 попыток)                        │
│  4. Section Validation + Graceful Degradation                │
│  5. Substantiality Check (≥200 символов + заголовки)         │
│  6. Notion Publish (upsert по дате+типу)                    │
│  7. Telegram Notification (secondary, failure = warning)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator (agents/oleg/orchestrator/)                    │
│  • Решает цепочку агентов: Reporter → Advisor → Validator   │
│  • Детектирует аномалии (маржа >10%, ДРР >30%)              │
│  • Синтезирует финальный отчёт                              │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         Reporter    Marketer    Funnel
         Advisor     Validator
         (agents/oleg/agents/)
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  ReAct Loop (agents/oleg/executor/react_loop.py)            │
│  • До 10 итераций, 30 инструментов (Reporter)               │
│  • Circuit breaker, context compression после 5 итерации    │
│  • Timeout: 30s/tool, 120s total                            │
└─────────────────────────────────────────────────────────────┘
```

## 8 типов отчётов

| Тип | Название | Период | Расписание | Маркетплейсы |
|-----|----------|--------|------------|--------------|
| `daily` | Финансовый анализ | день | каждый день | WB + OZON |
| `weekly` | Финансовый анализ | неделя | понедельник | WB + OZON |
| `monthly` | Финансовый анализ | месяц | пн 1–7 числа | WB + OZON |
| `marketing_weekly` | Маркетинговый анализ | неделя | понедельник | WB + OZON |
| `marketing_monthly` | Маркетинговый анализ | месяц | пн 1–7 числа | WB + OZON |
| `funnel_weekly` | Воронка продаж | неделя | понедельник | WB |
| `finolog_weekly` | Сводка ДДС | неделя | понедельник | WB + OZON |
| `localization_weekly` | Логистические расходы | неделя | понедельник | WB |

**Порядок генерации** (D-09): daily → weekly → monthly → marketing_weekly → marketing_monthly → funnel_weekly → localization_weekly → finolog_weekly (всегда последний).

**Глубина анализа**: daily = компактный (ключевые метрики), weekly = глубокий (тренды, модели, гипотезы), monthly = максимальный (P&L, юнит-экономика, стратегия).

**Реестр типов**: `agents/oleg/pipeline/report_types.py`

## Playbook система

Модульная система промптов в `agents/oleg/playbooks/`:

```
PlaybookLoader.load(task_type)
  → core.md (35 KB — бизнес-контекст, формулы, глоссарий)
  + templates/{type}.md (структура конкретного отчёта)
  + rules.md (26 KB — валидация, антипаттерны, диагностика)
```

**Шаблоны** (`agents/oleg/playbooks/templates/`):
- `daily.md`, `weekly.md`, `monthly.md` — финансовые
- `marketing_weekly.md`, `marketing_monthly.md` — маркетинговые
- `funnel_weekly.md` — воронка продаж
- `dds.md` — ДДС (data-driven, без LLM depth markers)
- `localization.md` — логистика (data-driven)

**Загрузчик**: `agents/oleg/playbooks/loader.py`

## Агенты

| Агент | Роль | Инструменты |
|-------|------|-------------|
| Reporter | Сбор финансовых данных, структурированный отчёт | 30 tools (12 финансовых + 18 ценовых) |
| Marketer | Маркетинг и реклама | Marketing tools |
| Funnel | Воронка продаж, SEO | Funnel tools |
| Advisor | Детекция аномалий, рекомендации | Аналитические tools |
| Validator | Проверка качества отчёта | 4 скрипта: coverage, direction, numbers, kb_rules |

**Базовый класс**: `agents/oleg/agents/base_agent.py`

**Цепочки оркестратора**:
- Daily (норма): Reporter → синтез
- Daily (аномалия): Reporter → Advisor → Reporter verify → синтез
- Weekly: Reporter → Advisor (опционально) → синтез
- Marketing: Marketer → синтез (или + Advisor)

## Gate Checker (pre-flight)

`agents/oleg/pipeline/gate_checker.py`

**Hard gates** (блокируют запуск — `can_run=False`):

| Gate | Что проверяется | Порог | При провале |
|------|----------------|-------|-------------|
| `wb_orders_freshness` | `MAX(dateupdate)` в `abc_date` (WB) | `dateupdate >= target_date` | Pipeline не запускается, в логе причина |
| `ozon_orders_freshness` | `MAX(date_update)` в `abc_date` (OZON) | `date_update >= target_date` | Pipeline не запускается, в логе причина |
| `fin_data_freshness` | `MAX(dateupdate)` в `abc_date` (WB, финансы) | `dateupdate >= target_date` | Pipeline не запускается, в логе причина |

**Soft gates** (предупреждение, не блокируют — добавляют `soft_warnings`):

| Gate | Что проверяется | Порог | При провале |
|------|----------------|-------|-------------|
| `advertising_data` | `SUM(reclama)` в `abc_date` за target_date | `> 0` | Warning: "Рекламных расходов: 0" |
| `margin_fill_rate` | Доля артикулов с `marga > 0` за последние 30 дней | `≥ 50%` | Warning: "Маржа рассчитана только для N%" |
| `logistics_data` | `SUM(logist)` в `abc_date` за target_date | `> 0` | Warning: "Логистических расходов: 0" |

## Доставка в Notion

**Database ID**: берётся из `NOTION_DATABASE_ID` в `.env`.

**Properties при публикации**:

| Property | Тип | Описание |
|----------|-----|----------|
| Name | title | `"{Тип анализа} за {период}"` (русский, авто-формат) |
| Период начала | date | Начало периода отчёта |
| Период конца | date | Конец периода отчёта |
| Тип анализа | select | Русское название из `_REPORT_TYPE_MAP` (22 маппинга) |
| Статус | select | `"Актуальный"` |
| Источник | select | `"Oleg v3 (auto)"` |

**Upsert логика** (`shared/notion_client.py` → `sync_report()`):
1. `_find_existing_page()` ищет страницу по `Период начала` + `Период конца` + `Тип анализа`
2. Если найдена — удаляет все блоки, обновляет properties и добавляет новый контент
3. Если не найдена — создаёт новую страницу (без children inline, потом append)
4. Per-report-type `asyncio.Lock` предотвращает гонку при параллельных запусках

**Markdown → Notion blocks** (`shared/notion_blocks.py`):
- `md_to_notion_blocks()` конвертирует markdown в Notion blocks
- Toggle-заголовки (`## ▸ Заголовок`) → toggle heading blocks с children
- Таблицы отправляются inline с `table_row` children (не strip)
- Остальные children strip'ятся и append'ятся отдельными PATCH-запросами (обходит баг Notion API с nested children)

## Инфраструктура

### Сервер (77.233.212.61 — Timeweb Cloud)

**Подключение**: `ssh timeweb`

**Docker-контейнеры** (`deploy/docker-compose.yml`):

| Контейнер | Сервис | Назначение |
|-----------|--------|------------|
| `wookiee_oleg` | Oleg V2 | Оркестратор отчётов (cron каждые 30 мин) |
| `wookiee_sheets_sync` | Sheets Sync | Синхронизация данных в Google Sheets |
| `vasily-api` | Vasily API | HTTP для расчёта перестановок |
| `wb_mcp_ip` | WB MCP (ИП) | Wildberries Seller API для ИП |
| `wb_mcp_ooo` | WB MCP (ООО) | Wildberries Seller API для ООО |
| `bitrix24_mcp` | Bitrix24 MCP | Задачи, CRM, пользователи |
| n8n | n8n | Workflow automation (управляется отдельным compose) |
| Caddy | Caddy | Reverse proxy + HTTPS (управляется отдельным compose) |

**Опциональные сервисы** (определены в `docker-compose.yml`, но не деплоятся на прод):

| Контейнер | Сервис | Назначение | Почему не на проде |
|-----------|--------|------------|--------------------|
| `wookiee_dashboard_api` | Dashboard API | HTTP-эндпоинт для дашборда | Дашборд не используется |
| `wookiee_knowledge_base` | Knowledge Base | Векторный поиск по базе знаний | Не используется в pipeline |

Для запуска опциональных: `docker compose --profile optional up -d`

**Все контейнеры** в сети `n8n-docker-caddy_default` (общая с n8n + Caddy reverse proxy).

### База данных (89.23.119.253:6433)

**ТОЛЬКО ЧТЕНИЕ**. Сторонний сервер подрядчика. Две базы: WB и OZON.

Все запросы через `shared/data_layer/` (14 модулей, ~200 KB):
- `finance.py`, `advertising.py`, `pricing.py`, `inventory.py`, `funnel_seo.py`, `article.py`, `sku_mapping.py`, `time_series.py`, `traffic.py`, `quality.py`, `planning.py`, `pricing_article.py`

### Ключевые shared-модули

| Модуль | Назначение |
|--------|------------|
| `shared/config.py` | Единая конфигурация (читает `.env`) |
| `shared/data_layer/` | Все SQL-запросы к БД |
| `shared/notion_client.py` | Клиент Notion API (upsert, комментарии) |
| `shared/notion_blocks.py` | Markdown → Notion blocks |
| `shared/clients/openrouter_client.py` | Единый LLM-клиент (OpenRouter) |

### LLM модели (OpenRouter)

| Тир | Модель | Стоимость (input/output per 1K tokens) |
|-----|--------|----------------------------------------|
| LIGHT | google/gemini-3-flash-preview | $0.0005 / $0.003 |
| MAIN | google/gemini-3-flash-preview | $0.0005 / $0.003 |
| HEAVY | anthropic/claude-sonnet-4-6 | $0.003 / $0.015 |
| FREE | openrouter/free | $0 |

**Стратегия**: MAIN → retry → HEAVY → FREE.

## Другие сервисы

| Сервис | Путь | Назначение |
|--------|------|------------|
| Sheets Sync | `services/sheets_sync/` | Google Sheets ↔ MP данные |
| Dashboard API | `services/dashboard_api/` | API для аналитического дашборда |
| Knowledge Base | `services/knowledge_base/` | Текстовый векторный поиск (768d) |
| Content KB | `services/content_kb/` | Фото-контент поиск (3072d, Gemini Embedding) |
| Vasily API | `services/wb_localization/` | Расчёт перестановок WB |
| Product Matrix | `services/product_matrix_api/` | API каталога товаров |
| Logistics Audit | `services/logistics_audit/` | Аудит логистических расходов |

## Мониторинг

**Watchdog** (`agents/oleg/watchdog/`):
- `watchdog.py` — мониторинг здоровья генерации
- `alerter.py` — Telegram-алерты с дедупликацией (окно 5 мин)
- `diagnostic.py` — диагностические отчёты при сбоях

**Уровни алертов**:
- 1 день без отчёта: "Отчёт не создан. Запустил диагностику..."
- 2 дня: "⚠ Отчёт не создан 2-й день подряд"
- 3+ дней: "🚨 КРИТИЧНО: N дней без отчётов"

## Troubleshooting

### Отчёт не генерируется

1. **Проверить gate checker**: данные могут быть несвежими
   ```bash
   ssh timeweb "docker logs wookiee_oleg --tail 100 | grep -i gate"
   ```

2. **Проверить lock-файлы**: возможно отчёт уже был сгенерирован
   ```bash
   ssh timeweb "docker exec wookiee_oleg ls /app/locks/"
   ```

3. **Ручной запуск**:
   ```bash
   ssh timeweb "docker exec wookiee_oleg python scripts/run_report.py --type daily"
   ```

### Отчёт пустой / неполный

1. Проверить логи LLM chain:
   ```bash
   ssh timeweb "docker logs wookiee_oleg --tail 200 | grep -i 'substantial\|retry\|degradation'"
   ```

2. Graceful degradation заменяет пустые секции плейсхолдерами — проверить template.

### Notion не обновляется

1. Проверить `NOTION_TOKEN` в `.env`
2. Проверить `NOTION_DATABASE_ID` — должен совпадать с базой "Аналитические отчёты"
3. Логи: `docker logs wookiee_oleg | grep -i notion`

### Telegram не приходит

- Telegram — secondary (failure = warning, не блокирует pipeline)
- Проверить `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`

## Ручное управление

```bash
# Запуск конкретного типа отчёта
python scripts/run_report.py --type daily [--date 2026-04-01]
python scripts/run_report.py --type weekly
python scripts/run_report.py --type marketing_monthly --date 2026-03-30

# Запуск по расписанию (определяет типы автоматически)
python scripts/run_report.py --schedule [--date 2026-04-01]

# Деплой
ssh timeweb
cd /root/Wookiee && git pull && docker compose -f deploy/docker-compose.yml up -d --build
```

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `scripts/run_report.py` | Entry point — runner с двумя режимами |
| `agents/oleg/pipeline/report_pipeline.py` | 7-step reliability pipeline |
| `agents/oleg/pipeline/report_types.py` | Реестр 8 типов отчётов |
| `agents/oleg/pipeline/gate_checker.py` | Pre-flight data quality gates |
| `agents/oleg/orchestrator/orchestrator.py` | Мастер-оркестратор цепочек |
| `agents/oleg/executor/react_loop.py` | ReAct loop с circuit breaker |
| `agents/oleg/playbooks/loader.py` | Загрузчик модульных плейбуков |
| `shared/data_layer/__init__.py` | Все SQL-запросы (~200 KB) |
| `shared/config.py` | Конфигурация (из `.env`) |
| `shared/notion_client.py` | Notion API клиент |
| `deploy/docker-compose.yml` | Docker Compose для всех сервисов |
