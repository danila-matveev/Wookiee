# Marketing Database — Design Spec
**Дата:** 2026-05-05  
**Статус:** Approved for implementation  
**Фаза этого спека:** Phase 1 (Database). Phases 2 (ETL) и 3 (Hub UI) — отдельные спеки.

---

## Контекст и цель

Создать единую маркетинговую базу данных (`marketing` schema в Supabase) для хранения аналитики по промокодам и поисковым запросам. Сейчас эти данные разбросаны: часть в схеме `crm`, часть только в Google Sheets. Цель — один источник истины, доступный из разных модулей (инфлюенс-маркетинг, SMM, таргет, Wookiee Hub).

---

## Декомпозиция на фазы

| Фаза | Содержание | Сессия |
|------|-----------|--------|
| **1 (этот спек)** | Схема `marketing`: views + новая таблица метрик, RLS | Текущая |
| **2** | ETL-скрипты: запись метрик промокодов из WB API, выгрузка в Sheets | Следующая |
| **3** | Wookiee Hub UI: `/marketing/promo-codes`, `/marketing/search-queries` | Отдельная |

---

## Ключевое архитектурное решение

В процессе self-review обнаружено: `crm.substitute_articles` и `crm.promo_codes` имеют входящие FK из CRM-таблиц:

```
crm.integration_substitute_articles.substitute_article_id → crm.substitute_articles(id)
crm.integration_promo_codes.promo_code_id                 → crm.promo_codes(id)
crm.substitute_article_metrics_weekly.substitute_article_id → crm.substitute_articles(id)
```

PostgreSQL FK не может ссылаться на VIEW — только на физическую таблицу. Следовательно, физически переместить эти таблицы в `marketing` невозможно без каскадного обновления FK в CRM-таблицах. Это существенно увеличило бы риски и scope.

**Принятое решение:** `marketing` — это аналитический **read-layer** поверх `crm`. Физические данные остаются в `crm`, `marketing` предоставляет чистый именованный API через Views. Единственная физическая таблица в `marketing` — новая `promo_stats_weekly` (нет входящих FK).

---

## Архитектура схемы

### Физические таблицы (остаются в `crm`, не трогаем)

| Таблица | Строк | Роль |
|---------|-------|------|
| `crm.promo_codes` | 3 | Справочник промокодов |
| `crm.substitute_articles` | 85 | Справочник поисковых запросов |
| `crm.substitute_article_metrics_weekly` | 2 565 | Статистика запросов по неделям |

Эти таблицы не изменяются. ETL продолжает писать в них.

### Новая физическая таблица в `marketing`

**`marketing.promo_stats_weekly`** — статистика промокодов по неделям  
Источник: WB API через `sync_promocodes.py`. Данных нет — создаётся с нуля.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | BIGSERIAL PK | |
| `promo_code_id` | BIGINT NOT NULL | Cross-schema FK → `crm.promo_codes(id)` ON DELETE RESTRICT |
| `week_start` | DATE NOT NULL | Понедельник ISO-недели |
| `sales_rub` | NUMERIC(14,2) | Продажи, руб. |
| `payout_rub` | NUMERIC(14,2) | К перечислению, руб. |
| `orders_count` | INTEGER | Заказов, шт. |
| `returns_count` | INTEGER | Возвратов, шт. |
| `avg_check` | NUMERIC(12,2) | Средний чек, руб. |
| `captured_at` | TIMESTAMPTZ DEFAULT now() | Когда записано |

Constraints: `UNIQUE(promo_code_id, week_start)`, все числовые поля `>= 0`.  
Запись: через UUID→ID lookup: `SELECT id FROM crm.promo_codes WHERE external_uuid = %s`. Если UUID не найден — лог + skip, не падаем.

### Views в `marketing` (read-only API)

```sql
-- Промокоды — человеческое имя поверх crm
CREATE VIEW marketing.promo_codes AS
SELECT
    id, code, name, external_uuid, channel,
    discount_pct, valid_from, valid_until,
    status, notes, created_at, updated_at
FROM crm.promo_codes;

-- Поисковые запросы — переименование substitute_articles
CREATE VIEW marketing.search_queries AS
SELECT
    id, code, artikul_id,
    purpose      AS channel,   -- унификация naming: purpose→channel
    nomenklatura_wb,
    campaign_name,
    status, notes, external_uuid, created_at, updated_at
FROM crm.substitute_articles;

-- Статистика поисковых запросов по неделям
CREATE VIEW marketing.search_query_stats_weekly AS
SELECT
    id,
    substitute_article_id AS search_query_id,
    week_start,
    frequency, transitions, additions, orders,
    captured_at
FROM crm.substitute_article_metrics_weekly;
```

Views доступны только для чтения. Запись в `crm.*` — через ETL.

---

## Поле `name` в `crm.promo_codes`

Из скриншота WB Partners: у каждого промокода есть внутреннее название (`Audrey/dark_beige`) отдельно от кода покупателя (`AUDREY3`). В текущей схеме `crm.promo_codes` поля `name` нет.

Миграция 015 добавляет:
```sql
ALTER TABLE crm.promo_codes ADD COLUMN name TEXT;
```

Трансформер `transformers/promo_codes.py` обновляется: берёт "Название" из Sheets (колонка 0 или отдельная — уточнить по реальному листу в Phase 2).

---

## Стратегия применения (миграция 015)

**Один SQL-файл. Нулевой риск данных — ничего не перемещается.**

```
services/influencer_crm/migrations/015_marketing_schema.sql
```

Содержит последовательно:
1. `CREATE SCHEMA IF NOT EXISTS marketing`
2. `ALTER TABLE crm.promo_codes ADD COLUMN IF NOT EXISTS name TEXT` — новое поле
3. `CREATE TABLE marketing.promo_stats_weekly (...)` + индексы + RLS
4. `CREATE VIEW marketing.promo_codes AS ...`
5. `CREATE VIEW marketing.search_queries AS ...`
6. `CREATE VIEW marketing.search_query_stats_weekly AS ...`
7. `GRANT SELECT ON ALL TABLES IN SCHEMA marketing TO authenticated`
8. `GRANT ALL ON marketing.promo_stats_weekly TO service_role`
9. `GRANT SELECT ON ALL TABLES IN SCHEMA marketing TO service_role`

**Откат:** `DROP SCHEMA marketing CASCADE; ALTER TABLE crm.promo_codes DROP COLUMN name;` — оригинальные `crm.*` таблицы и данные нетронуты.

---

## RLS

`marketing.promo_stats_weekly` (единственная физическая таблица в `marketing`):
- RLS включён
- `anon` — нет доступа
- `service_role` — полный доступ (SELECT / INSERT / UPDATE)
- `authenticated` — только SELECT

Views RLS не требуют собственных политик — они наследуют политики base-таблиц из `crm`.

---

## Изменения в коде (минимальные)

Основные изменения — в Phase 2 спеке. Единственное изменение Phase 1:

| Файл | Изменение |
|------|-----------|
| `services/sheets_etl/transformers/promo_codes.py` | Добавить поле `name` (после уточнения колонки в Sheets) |

ETL `run.py` — без изменений, `crm.promo_codes` остаётся целевой таблицей.

---

## ETL — контур (детали в Phase 2 спеке)

### Промокоды (справочник)
- Источник: Google Sheets "Промокоды_справочник"
- Cron: пн 06:00, `sheets_etl --sheet promo_codes` → `crm.promo_codes`
- Конфликт-ключ: `code`

### Метрики промокодов (новое)
- Источник: WB API (два кабинета: ИП + ООО)
- Cron: пн 12:00, `sync_promocodes.py` → `marketing.promo_stats_weekly`
- Связка: UUID → `crm.promo_codes.id` → FK в `promo_stats_weekly`
- Идемпотентность: `ON CONFLICT (promo_code_id, week_start) DO UPDATE SET ...`

### Поисковые запросы (без изменений)
- Cron: пн 06:00, `sheets_etl --sheet substitute_articles` → `crm.substitute_articles` + `crm.substitute_article_metrics_weekly`
- Никаких изменений в логике и именах таблиц

---

## Wookiee Hub UI — контур (детали в Phase 3 спеке)

Оба раздела читают из `marketing.*` (views + физическая таблица):

### `/marketing/promo-codes`
- Таблица с фильтром по `channel` и `status`
- Sparkline последних 8 недель из `marketing.promo_stats_weekly`
- Форма добавления: `name`, `code`, `external_uuid`, `channel`, `discount_pct`, `valid_from`, `valid_until`
- Запись через Supabase JS client → вставка в `crm.promo_codes` (service_role)

### `/marketing/search-queries`
- Таблица с фильтром по `channel` (purpose) и `status`
- Форма добавления: модель из дропдауна → автозаполнение `nomenklatura_wb` → артикул → `purpose` → `status`
- Запись → `crm.substitute_articles` (service_role)
- Дропдаун моделей: из `public.artikuly`

---

## Зависимости между фазами

```
Phase 1 (миграция 015 в Supabase)
  └─→ Phase 2 (ETL: promo_stats_weekly начинает наполняться)
        └─→ Phase 3 (Hub UI: данные есть, можно показывать)
```

Phase 3 не начинать до стабильного ETL (минимум 2 недели данных в `promo_stats_weekly`).

---

## Критерии готовности Phase 1

- [ ] Миграция 015 применена в Supabase (prod)
- [ ] `marketing.promo_stats_weekly` существует, RLS включён
- [ ] Три views в `marketing` возвращают данные: `SELECT count(*) FROM marketing.search_queries` = 85, `marketing.search_query_stats_weekly` = 2565, `marketing.promo_codes` = 3
- [ ] `crm.*` таблицы работают без изменений (ETL прогон без ошибок)
- [ ] `ALTER TABLE crm.promo_codes ADD COLUMN name` применён
