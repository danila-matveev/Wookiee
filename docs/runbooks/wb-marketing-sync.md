# WB Marketing Sync — runbook

Два связанных еженедельных сервиса в контейнере `wookiee_cron` пишут аналитику WB (промокоды + поисковые запросы) одновременно в Google Sheets (для людей) и Supabase (для UI/истории/анализа).

| Сервис | Версия | Cron | Назначение |
|---|---|---|---|
| `wb-promocodes-sync` | 2.1.0 | Пн 12:00 МСК | Аналитика промокодов: метрики недели + поартикульная история покупок |
| `wb-search-queries-sync` | 2.0.0 | Пн 10:00 МСК | Аналитика поисковых запросов: частота + переходы/корзина/заказы + ассоциированные конверсии по артикулам |

Общий Google Sheets: `1I4UFVYkUELm5phk8MDv518kF6z5sQJFmRdaLYg_-CPY` («Wookiee — Аналитика поисковых запросов»). Supabase project: `gjvwcdtfglupewcwzfhw`.

---

## 1. Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                  wookiee_cron (Docker)                              │
│                                                                     │
│  Mon 10:00 ─→ python scripts/run_search_queries_sync.py             │
│  Mon 12:00 ─→ python scripts/run_wb_promocodes_sync.py              │
│                       │                                             │
│                       ▼                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  WB Statistics API + WB Seller Analytics API                 │  │
│  │  ИП Медведева (oid 105757)  +  ООО Вуки (oid 947388)         │  │
│  └────────────────────┬─────────────────────────────────────────┘  │
│                       │                                             │
│           ┌───────────┴───────────┐                                 │
│           ▼                       ▼                                 │
│   Google Sheets             Supabase Postgres                       │
│   (people-readable)         (UI, history, analysis)                 │
└─────────────────────────────────────────────────────────────────────┘
```

Каждый сервис идемпотентен: повторный запуск на ту же неделю не плодит дубли (UPSERT по составным ключам).

---

## 2. WB Promocodes Sync 2.1.0

**Скрипт:** [`scripts/run_wb_promocodes_sync.py`](../../scripts/run_wb_promocodes_sync.py) → [`services/sheets_sync/sync/sync_promocodes.py`](../../services/sheets_sync/sync/sync_promocodes.py)

### Источник данных

WB Statistics API `reportDetailByPeriod` по двум кабинетам. Каждая строка отчёта содержит `uuid_promocode` (если продажа по промо) + `srid` (уникальный ID продажи) + `nm_id` + суммы.

### Куда пишет

**Google Sheets** — таб `Промокоды_аналитика (копия)`:

| Колонка | Заполняет | Назначение |
|---|---|---|
| A | человек | Название промокода |
| B | скрипт (при первом появлении) | UUID |
| C | скрипт | Канал (ИП/ООО) |
| D | человек | Скидка % |
| E | **скрипт ставит «требует review» для новых, человек переводит в «активный» / «неактивный»** | Статус |
| F+ | скрипт | Недельные метрики (6 кол × N недель) |

Справочника как отдельного таба нет — single source of truth прямо в основном листе.

**Supabase** (3 таблицы):

```
crm.promo_codes (справочник, 1 строка на промокод)
       │ id = promo_code_id
       ├─→ marketing.promo_stats_weekly       (агрегат по неделе)
       └─→ marketing.promo_product_breakdown  (детализация неделя × артикул)
                       │ artikul_id
                       └─→ public.artikuly (sku) → public.modeli (модель)
```

**`crm.promo_codes`** — `id`, `code`, `external_uuid` (UUID из WB), `status`. Новые UUID из выручки автоматически вставляются placeholder'ом `code='WB:<UUID>'`. Переименовываются вручную через UPDATE.

**`marketing.promo_stats_weekly`** — UNIQUE `(promo_code_id, week_start)`. Колонки: `sales_rub`, `payout_rub`, `orders_count`, `returns_count`, `avg_discount_pct`, `avg_check`.

**`marketing.promo_product_breakdown`** — UNIQUE `(promo_code_id, week_start, artikul_id)`. Колонки: `qty`, `amount_rub`, `model_code`, `sku_label`. Дедуп `srid` происходит после фильтра по uuid (commit `8c0e2ce`) — иначе non-promo строки забирают srid и реальные продажи теряются.

### CLI

```bash
# Дефолт — последняя закрытая неделя (Mon-Sun)
python scripts/run_wb_promocodes_sync.py

# Конкретная неделя
python scripts/run_wb_promocodes_sync.py --mode specific --from 2026-04-27 --to 2026-05-03

# Бекфил N недель назад
python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12

# Только в Sheets, без БД
python scripts/run_wb_promocodes_sync.py --skip-db
```

### Пример query: что покупали по промокоду X

```sql
SELECT pb.week_start, m.kod AS model, pb.sku_label, pb.qty, pb.amount_rub
FROM marketing.promo_product_breakdown pb
JOIN crm.promo_codes pc ON pc.id = pb.promo_code_id
LEFT JOIN public.artikuly a ON a.id = pb.artikul_id
LEFT JOIN public.modeli m ON m.id = a.model_id
WHERE pc.code = 'CHARLOTTE10'
ORDER BY pb.week_start, pb.amount_rub DESC;
```

---

## 3. WB Search Queries Sync 2.0.0

**Скрипт:** [`scripts/run_search_queries_sync.py`](../../scripts/run_search_queries_sync.py) → [`services/sheets_sync/sync/sync_search_queries.py`](../../services/sheets_sync/sync/sync_search_queries.py)

### Источник данных

WB Seller Analytics API `/api/v2/search-report/product/search-texts`. Запрашивается по двум кабинетам, батчами по 50 nm_id, пауза 21s между запросами (rate-limit 3 req/min). На 429 → пауза 60s. Лимит слов в ответе: ИП 30, ООО 100.

Список отслеживаемых слов — колонка A основного таба Sheets. Подмен-маппинг (слово → nm_id) — col B.

### Куда пишет

**Google Sheets** — таб `Аналитика по запросам`. Каждый прогон добавляет новые 4 колонки справа: `Частота / Переходы / Добавления / Заказы` за прошедшую неделю.

Старый таб `Аналитика по запросам (поартикульно)` больше **не пишется** — поартикульная история теперь в Supabase с накоплением по всем неделям.

**Supabase** (2 таблицы):

```
marketing.search_queries_weekly                 marketing.search_query_product_breakdown
─────────────────────────────────────           ─────────────────────────────────────────
UNIQUE: (week_start, search_word)               UNIQUE: (week_start, search_word, nm_id)

  frequency       (keyword-level на WB)           artikul_id  (FK → public.artikuly.id)
  open_card                                       sku_label   (Wendy/dark_beige)
  add_to_cart                                     model_code  (wendy)
  orders                                          open_card, add_to_cart, orders
```

### Критическая деталь — фильтр маппинга и breakdown

В `_analyze_cabinet` функция `_should_count_transitions(word, nm_id, podmen_mapping)` применяется **только к keyword-aggregate** (4 числа в Sheets). К `product_breakdown` фильтр НЕ применяется (commit `d14a1f7`).

Причина: подменные артикул-коды (`WW121790` и т.п.) ведут трафик не только на mapped target, но и на соседние SKU/модели — это **ассоциированные конверсии** (естественный effect бренд-продвижения). Если фильтровать breakdown по маппингу, теряется ~64% реальной картины.

Aggregate в Sheets = «успешность» подменки на свою цель. Breakdown в БД = «куда реально уходит трафик» — для аналитики ассоциированных конверсий.

### CLI

```bash
# Последняя закрытая неделя
python scripts/run_search_queries_sync.py

# Конкретная неделя
python scripts/run_search_queries_sync.py --mode specific --from 2026-04-27 --to 2026-05-03

# Бекфил
python scripts/run_search_queries_sync.py --mode bootstrap --weeks-back 12

# Sheets only
python scripts/run_search_queries_sync.py --skip-db
```

### Пример query: куда уходит трафик от поискового слова

```sql
SELECT pb.sku_label, m.kod AS model,
       SUM(pb.open_card)   AS opens,
       SUM(pb.add_to_cart) AS carts,
       SUM(pb.orders)      AS orders,
       COUNT(DISTINCT pb.week_start) AS weeks_active
FROM marketing.search_query_product_breakdown pb
LEFT JOIN public.artikuly a ON a.id = pb.artikul_id
LEFT JOIN public.modeli m   ON m.id = a.model_id
WHERE pb.search_word = 'WW121790'
GROUP BY pb.sku_label, m.kod
ORDER BY SUM(pb.orders) DESC NULLS LAST;
```

### Пример query: эффективность подменки (mapped share)

```sql
WITH agg AS (
  SELECT pb.search_word, pb.sku_label, SUM(pb.orders) AS orders
  FROM marketing.search_query_product_breakdown pb
  WHERE pb.search_word = 'WW121790'
  GROUP BY pb.search_word, pb.sku_label
)
SELECT
  SUM(orders) FILTER (WHERE sku_label = 'Wendy/dark_beige') AS mapped_orders,
  SUM(orders) AS total_orders,
  ROUND(100.0 * SUM(orders) FILTER (WHERE sku_label = 'Wendy/dark_beige') / SUM(orders), 1) AS mapped_share_pct
FROM agg;
```

---

## 4. Cron

Контейнер `wookiee_cron` (entrypoint в [`deploy/docker-compose.yml`](../../deploy/docker-compose.yml)). Все crontab-строки прописаны в `command:` контейнера и устанавливаются при старте:

```cron
PATH=/usr/local/bin:/usr/bin:/bin
PYTHONPATH=/app
0 10 * * 1   cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1
0 6  * * *   cd /app && python scripts/sync_sheets_to_supabase.py --level all >> /proc/1/fd/1 2>&1
0 12 * * 1   cd /app && python scripts/run_wb_promocodes_sync.py >> /proc/1/fd/1 2>&1
0 */6 * * *  cd /app && python -m services.influencer_crm.scripts.etl_runner >> /proc/1/fd/1 2>&1
```

Логи cron'а пишутся в `stdout` контейнера → `docker logs wookiee_cron`.

### Важная деталь — `.env` для cron

Cron-демон скрабит окружение для спавнящихся job'ов, `env_file` из docker-compose недоступен в crontab-контексте. Поэтому контейнер монтирует `.env` файл как volume и `dotenv.load_dotenv()` в каждом скрипте читает его при старте:

```yaml
volumes:
  - ../.env:/app/.env:ro
```

Без этого фикса (`2b629a6`) WB API ключи в cron-вызовах окажутся пустые → 401 → сервисы молча no-op'ят.

### Проверка состояния

```bash
# Crontab в живом контейнере
ssh timeweb "docker exec wookiee_cron crontab -l"

# Последние логи
ssh timeweb "docker logs --tail 100 wookiee_cron"

# Ручной запуск (для отладки)
ssh timeweb "docker exec wookiee_cron python /app/scripts/run_search_queries_sync.py --mode last_week"
```

---

## 5. Backfill / переразвёртывание

UPSERT-идемпотентность означает, что любой ручной прогон на уже посчитанную неделю просто перезаписывает строки в обеих таблицах. Поэтому:

- **Изменили логику агрегации** → запускайте `--mode bootstrap --weeks-back N` для нужной глубины, новые расчёты заменят старые.
- **Хотите данные только за одну неделю** → `--mode specific --from YYYY-MM-DD --to YYYY-MM-DD`.
- **Хотите проверить без БД** → `--skip-db` (Sheets обновятся, Supabase нет).

### Когда требуется ребилд контейнера

`/app/services/` baked в Docker image. Если меняли код в `services/sheets_sync/sync/`, нужно:

```bash
ssh timeweb "cd /home/danila/projects/wookiee/deploy && docker compose build wookiee-cron && docker compose up -d wookiee-cron"
```

`/app/scripts/` смонтирован volume'ом — для изменений только в `scripts/` ребилд не нужен.

---

## 6. Текущее покрытие БД (2026-05-12)

| Таблица | Строк | Период |
|---|---|---|
| `crm.promo_codes` | 6 | — |
| `marketing.promo_stats_weekly` | 6 | 2026-03-02 → 2026-05-04 |
| `marketing.promo_product_breakdown` | 9 | 2026-03-02 → 2026-05-04 |
| `marketing.search_queries_weekly` | 1 396 | 2026-02-16 → 2026-05-04 |
| `marketing.search_query_product_breakdown` | 18 750 | 2026-02-16 → 2026-05-04 |

Search queries — 222 distinct слова × 201 distinct nm_id. Promo — 6 промокодов (`CHARLOTTE10`, `LANA5`, `MYBELLA5`, `OOOCORP25`, `UFL6BFH9_AUDREY_TG10`, плюс один placeholder).

Бекфил на год запланирован отдельным шагом.

---

## 7. Ключевые коммиты

| Commit | Что |
|---|---|
| `f301f41` | feat(promo): v2.0.0 — single-source-of-truth refactor |
| `8c0e2ce` | fix(promo): dedup srid only after promo filter |
| `2b629a6` | fix(deploy): mount .env into wookiee_cron container |
| `33585e5` | docs(catalog): promo bump to 2.1.0 |
| `39e4146` | feat(search-queries): v2.0.0 — Supabase history + per-article breakdown |
| `d14a1f7` | fix(search-queries): breakdown captures all articles, not only mapped |
| `91935e2` | docs(search-queries): terminology — associated conversions, not leaks |

## 8. Реестр инструментов

Оба сервиса зарегистрированы в Supabase `tools` и попадают в [`docs/TOOLS_CATALOG.md`](../TOOLS_CATALOG.md) (автогенерация). Обновление: `python scripts/generate_tools_catalog.py`.
