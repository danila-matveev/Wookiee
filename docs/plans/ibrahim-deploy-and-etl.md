# План: Деплой Ибрагима + автономный сбор данных

> Дата: 2026-02-20
> Статус: ACTIVE
> Сервер: Timeweb Cloud Amsterdam (77.233.212.61), 2 vCPU / 2 GB / 40 GB NVMe

## Контекст

**Задача:** Построить автономного ИИ-агента (Ибрагим), который:
1. Анализирует исходную read-only БД (pbi_wb/ozon от подрядчика)
2. Самостоятельно собирает все те же данные через API WB и Ozon
3. Ежедневно сверяет свою базу с эталоном (reconciliation < 1%)
4. Подтверждает корректность данных и алертит при расхождениях

**Что уже построено (Ибрагим ~95% готов):**
- ETL: WB (6 API-эндпоинтов → 7 таблиц), Ozon (7 API → 7 таблиц)
- Reconciliation (managed vs source по revenue, margin, orders)
- Data quality (freshness, completeness, consistency)
- LLM-анализ API и схем (analyze-api, analyze-schema)
- Scheduler (daily 05:00 MSK, weekly Sun 03:00 MSK)
- CLI: sync, reconcile, status, health, analyze-api, analyze-schema, run-scheduler

---

## Часть 1: Архитектура

### Целевая схема (один сервер)

```
Timeweb Cloud (77.233.212.61)                VPS Россия (89.23.119.253)
┌────────────────────────────────┐           ┌─────────────────────────┐
│  Существующие контейнеры:      │  прямое   │  PostgreSQL (read-only) │
│  ├── wookiee_analytics_agent   │  TCP      │  :6433 pbi_wb_wookiee  │
│  ├── wookiee_analytics_bot     │◄────────► │  :6433 pbi_ozon_wookiee│
│  ├── wookiee_sheets_sync       │           │  (эталонная БД)        │
│  ├── vasily-api                │           └─────────────────────────┘
│  ├── n8n + caddy               │
│  │                             │
│  │  НОВОЕ:                     │
│  ├── ibrahim-db (PG 16-alpine) │ ── Docker network ──┐
│  └── wookiee_ibrahim (agent)   │ ─────────────────────┘
│                                │
│  Внешние API:                  │
│  ├── WB API (6 эндпоинтов)    │
│  ├── Ozon API (7 эндпоинтов)  │
│  └── OpenRouter (Kimi K2.5)   │
└────────────────────────────────┘
```

Нет WireGuard — Oleg уже подключается к российской БД напрямую. Ibrahim делает то же самое.

### Ресурсы после добавления

| Сервис | RAM limit | RAM reserve | CPU limit |
|--------|-----------|-------------|-----------|
| wookiee-agent (Oleg) | 512M | 256M | 1.0 |
| wookiee-bot | 256M | 128M | 0.5 |
| sheets-sync | 512M | 128M | 0.5 |
| vasily-api | 512M | 256M | 0.5 |
| **ibrahim-db** | **256M** | **128M** | **0.3** |
| **wookiee_ibrahim** | **384M** | **128M** | **0.5** |
| **ИТОГО** | **2.4 GB** | **1.0 GB** | **3.3** |

Limits > 2 GB, но пиковая нагрузка не одновременная: Ibrahim работает 05:00 MSK, Oleg — днём.
Reservations 1.0 GB — безопасно.

> Рекомендация: апгрейд до 4 GB RAM при возможности (~1140 ₽/мес вместо 810).

---

## Часть 2: Анализ SQL-документации (abc_date)

Из `docs/Копия Документация SQL.xlsx` (1342 строки):

### WB abc_date — 60+ метрик

**Основные (из reportdetailbyperiod API):**
revenue, full_counts, returns, revenue_return, comis, logist, penalty, surcharges, retention, acquiring_fee, rebill_logistic_cost, revenue_spp, revenue_return_spp, comis_spp, spp, price_rozn, retail_price, average_check, nds, advert, deduction, reclama_fin, loan, proverka, count_cancell, logis_cancell_rub

**Расход/доход (из reportdetailbyperiod):**
revenue_dop_defect, rashod_dop_defect, revenue_dop_loss, rashod_dop_loss, additional_payment, rashod_additional_payment

**Реклама (из wb_adv + content_analysis):**
reclama

**Еженедельные (из accrual_report_wb):**
storage, over_logist, dop_penalty, inspection

**Приёмка (из paid_acceptance, с 28.10.24):**
inspection (новая формула по nmid)

**Из Журнала операций:**
no_vozvratny_fulfil, prod_fulfil, no_vozvratny_vhesh_logist, prod_vnehs_logist, vozvratny_upakov, prod_upakov, vozvratny_zerkalo, prod_zercalo, fulfilment_sam, vnesh_logist_sam, upakovka_sam, zercalo_sam, fulfilment_returns, vnesh_logist_returns, upakovka_returns, zercalo_returns, marketing, buyouts, counts_sam

**Себестоимость (из Справочника/ЖО/МойСклад):**
sebes, sebes_return, sebes_sam, sebes_kompens, nalog

**Производные:**
marga, marga_union, logist_union, logist_union_prod, comis_union, penalty_union, storage_union, inspection_union, retention_union, over_logist_union, logist_union_return, logis_return_rub, comis_sam, logist_sam, conversion, count_orders

### Источники данных в эталонной БД

| Источник | Таблица в source DB | Ibrahim покрывает? |
|----------|--------------------|--------------------|
| WB reportDetailByPeriod API | abc_date (основа ~80% метрик) | ✅ Есть |
| WB sales API | sales | ✅ Есть |
| WB orders API | orders | ✅ Есть |
| WB stocks API | stocks | ✅ Есть |
| WB content/cards API | nomenclature | ✅ Есть |
| WB fullstats API | wb_adv | ✅ Есть |
| WB nm-report API | content_analysis | ✅ Есть |
| **WB accrual report** | **accrual_report_wb** | **❌ НЕТ** |
| **WB paid_acceptance** | **paid_acceptance** | **❌ НЕТ** |
| **Журнал операций** (Google Sheets) | **journal** | **❌ НЕТ** |
| **Справочник** (Google Sheets) | **sebest** | **❌ НЕТ** |
| **МойСклад API** | **ms_stocks** | **❌ НЕТ** |
| **Сопоставление МС** | **sopostavlenie_ms** | **❌ НЕТ** |
| Ozon finance/transaction API | ozon.abc_date | ✅ Есть |
| Ozon fbo/fbs posting APIs | ozon.orders | ✅ Есть |
| Ozon returns | ozon.returns | ✅ Есть |
| Ozon stocks | ozon.stocks | ✅ Есть |
| Ozon product/list | ozon.nomenclature | ✅ Есть |
| Ozon performance/statistics | ozon.adv_stats_daily | ✅ Есть |
| **Ozon SKU-level advertising** | **ozon.ozon_adv_api** | **⚠️ Схема есть, API нет** |
| **Ozon kompens** | **kompens** | **❌ НЕТ** |
| **Ozon utilization/categore** | **utilization, categore** | **❌ НЕТ** |

### Вывод: стратегия в 2 этапа

**Этап 1 (MVP — запуск):** Ibrahim собирает сырые данные из API (14 таблиц, уже реализовано). Reconciliation сверяет ключевые агрегаты (revenue, margin). Расхождения по sebes/fulfillment/marketing ожидаемы — эти поля зависят от Google Sheets и МойСклад.

**Этап 2 (полная репликация):** Добавить недостающие источники:
- `accrual_report_wb` — WB API ещё один эндпоинт
- `paid_acceptance` — WB API
- Google Sheets → sebes, journal (через existing sheets_sync инфраструктуру)
- МойСклад API → ms_stocks, sopostavlenie_ms
- Формулы расчёта abc_date метрик (views/materialized views в PostgreSQL)

---

## Часть 3: Файлы для создания

```
deploy/
├── Dockerfile.ibrahim           # образ для Ibrahim
├── healthcheck_ibrahim.py       # проверка: процесс + DBs
├── docker-compose.yml           # + 2 сервиса (ibrahim-db, ibrahim)

agents/ibrahim/
├── alerting.py                  # Telegram-алерты (НОВЫЙ)
├── __main__.py                  # + PID lock (МОДИФИКАЦИЯ)

services/marketplace_etl/config/
├── accounts.json                # API-ключи WB/Ozon (СОЗДАТЬ на сервере)
```

### Шаг 1: Dockerfile.ibrahim

По шаблону `deploy/Dockerfile`:
- `python:3.11-slim` + gcc + postgresql-client
- Копирует: `shared/`, `agents/ibrahim/`, `services/marketplace_etl/`, `scripts/`
- CMD: `python -m agents.ibrahim run-scheduler`

### Шаг 2: docker-compose.yml (+ 2 сервиса)

**ibrahim-db:**
- `postgres:16-alpine`, volume `ibrahim_pgdata`
- Init: `schema.sql` + `indexes.sql`
- Healthcheck: `pg_isready`
- Limits: 256M RAM, 0.3 CPU

**wookiee_ibrahim:**
- `MARKETPLACE_DB_HOST=ibrahim-db` (Docker DNS)
- `DB_HOST` из .env (source DB в России)
- Volumes: data, logs, accounts.json (ro)
- Depends on: ibrahim-db (service_healthy)
- Limits: 384M RAM, 0.5 CPU

### Шаг 3: healthcheck_ibrahim.py

- Проверка процесса `pgrep -f agents.ibrahim`
- Marketplace DB (ibrahim-db:5432)
- Source WB DB (DB_HOST:6433)
- Source OZON DB (DB_HOST:6433)

### Шаг 4: alerting.py

- `send_alert(message)` через Telegram Bot API
- Env: `IBRAHIM_ALERT_BOT_TOKEN`, `IBRAHIM_ALERT_CHAT_ID`
- Вызов после daily/weekly routine

### Шаг 5: PID lock в __main__.py

- PID-файл `agents/ibrahim/logs/ibrahim.pid`
- Проверка дубля при старте

### Шаг 6: accounts.json

```json
{
  "wb": [
    {"lk": "WB ИП", "api_key": "..."},
    {"lk": "WB ООО", "api_key": "..."}
  ],
  "ozon": [
    {"lk": "Ozon ИП", "client_id": "...", "api_key": "..."},
    {"lk": "Ozon ООО", "client_id": "...", "api_key": "..."}
  ]
}
```

---

## Часть 4: Чеклист релиза

### Фаза 0: Подготовка (локально)
- [ ] Удалить папку `Wookiee Marketplace/` (устаревшая)
- [ ] Создать `deploy/Dockerfile.ibrahim`
- [ ] Создать `deploy/healthcheck_ibrahim.py`
- [ ] Добавить ibrahim-db + ibrahim в `deploy/docker-compose.yml`
- [ ] Создать `agents/ibrahim/alerting.py`
- [ ] Добавить PID lock в `agents/ibrahim/__main__.py`
- [ ] Обновить `deploy/deploy.sh`
- [ ] Обновить `.github/workflows/deploy.yml`
- [ ] Тест: `docker compose -f deploy/docker-compose.yml config`
- [ ] PR в main

### Фаза 1: Подготовка сервера
- [ ] SSH: `ssh timeweb`
- [ ] Создать `accounts.json` из .env переменных
- [ ] Добавить в .env: `MARKETPLACE_DB_PASSWORD`, `IBRAHIM_ALERT_BOT_TOKEN`, `IBRAHIM_ALERT_CHAT_ID`
- [ ] `mkdir -p agents/ibrahim/{data,logs}`

### Фаза 2: Деплой
- [ ] Push в main → GitHub Actions автодеплой
- [ ] `docker ps` — все контейнеры running
- [ ] `docker logs wookiee_ibrahim --tail 20`
- [ ] `docker exec wookiee_ibrahim python -m agents.ibrahim health`

### Фаза 3: Инициализация данных
- [ ] `docker exec wookiee_ibrahim python -m agents.ibrahim sync --from 2024-01-01 --to 2026-02-20`
- [ ] `docker exec wookiee_ibrahim python -m agents.ibrahim reconcile --days 30`
- [ ] `docker exec wookiee_ibrahim python -m agents.ibrahim health`

### Фаза 4: Валидация (7 дней)
- [ ] ETL проходит в 05:00 MSK ежедневно
- [ ] Reconciliation < 1% по revenue + margin
- [ ] Telegram-алерты работают
- [ ] `docker stats` — сервер стабилен
- [ ] После успеха: `DATA_SOURCE=managed`

---

## Часть 5: Этап 2 (после стабилизации MVP)

Добавить недостающие источники для полной репликации abc_date:

| Приоритет | Источник | Что даёт | Сложность |
|-----------|----------|----------|-----------|
| 🔴 HIGH | WB accrual_report API | storage, over_logist, dop_penalty, inspection | Средняя — новый API-клиент |
| 🔴 HIGH | WB paid_acceptance API | inspection (с 28.10.24) | Средняя |
| 🟠 MED | МойСклад API | ms_stocks → sebes (для Dizori и др.) | Средняя — новый API-клиент |
| 🟠 MED | Google Sheets → sebes | Себестоимость из Справочника/ЖО | Низкая — sheets_sync уже есть |
| 🟠 MED | Google Sheets → journal | Фулфилмент, логистика, маркетинг, самовыкупы | Низкая |
| 🟡 LOW | Ozon SKU-level ads API | ozon_adv_api | Средняя |
| 🟡 LOW | Ozon kompens/utilization | sebes_kompens, sebes_util | Низкая |
| 🟡 LOW | Materialized views для abc_date | Расчётные метрики (marga, unit-метрики) | Высокая — бизнес-логика |

---

## Верификация

1. `docker compose -f deploy/docker-compose.yml config` — валидный compose
2. `docker compose up --build` — все 6+ сервисов стартуют
3. `docker exec wookiee_ibrahim python -m agents.ibrahim health` — PASS
4. `docker exec wookiee_ibrahim python -m agents.ibrahim sync` — данные в marketplace DB
5. `docker exec wookiee_ibrahim python -m agents.ibrahim reconcile --days 1` — < 1%
6. Через сутки: автозапуск ETL в 05:00, Telegram-алерт
7. `docker stats --no-stream` — RAM < 2 GB суммарно
