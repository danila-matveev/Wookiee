# Marketing v4 — bootstrap данных после Phase 2B

Короткий ранбук на случай, когда после деплоя Phase 2B (новый view `marketing.search_queries_unified` v2 + RPC `search_query_stats_aggregated` v2 + bridge crm→Sheets в обоих sync-скриптах) надо «прокачать» данные с нуля или после длительного простоя кронов.

Цель — собрать в одном месте порядок шагов, sanity-проверки и одно известное ограничение текущей реализации (см. раздел 5).

---

## 1. Назначение и когда запускать

- Только что применили миграции из этой ветки (B.0.1, B.0.2, B.0.3) на prod-Supabase и хотите убедиться, что UI на `/marketing/search-queries` показывает реальные цифры, а не нули.
- Восстанавливаете окружение после паузы в кронах (`wookiee_cron` стоял > 1 недели), и в `marketing.search_queries_weekly` отсутствуют свежие данные.
- В CRM (`crm.branded_queries` / `crm.substitute_articles`) добавили слова через UI и хотите, чтобы они попали в Sheets без ожидания понедельничного cron.

Не запускать «на всякий случай»: UPSERT-идемпотентен, но WB API имеет rate-limit 3 req/min, полный прогон длится десятки минут.

---

## 2. Предусловия

- Миграции применены. Три файла:
  - `database/marketing/views/2026-05-13-search-queries-unified-v2.sql` — view v2.
  - `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql` — RPC v2.
  - `database/marketing/migrations/2026-05-13-add-ooo-channel.sql` — seed `ooo`-канала.
- `.env` содержит: `WB_API_KEY_IP`, `WB_API_KEY_OOO`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GOOGLE_SHEETS_CREDENTIALS_JSON`.
- Если планируете дёргать через UI — `analytics-api` поднят на `https://hub.os.wookiee.shop/api/marketing/sync/...`.

---

## 3. Порядок шагов

### Шаг 3.1. Применить миграции

Через Supabase MCP `apply_migration` или напрямую `psql`:

```bash
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-13-search-queries-unified-v2.sql
psql "$SUPABASE_DB_URL" -f database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v2.sql
psql "$SUPABASE_DB_URL" -f database/marketing/migrations/2026-05-13-add-ooo-channel.sql
```

Все три — `CREATE OR REPLACE` или `INSERT ... ON CONFLICT DO NOTHING`, повторное применение безопасно.

### Шаг 3.2. Проверить, что view+RPC отвечают

```sql
SELECT entity_type, COUNT(*)
FROM marketing.search_queries_unified
GROUP BY entity_type
ORDER BY 1;
```

Ожидание: строки для `brand`, `nomenclature`, `ww_code`, `other` (последние два могут быть пустыми, если в `crm.substitute_articles` нет соответствующих кодов).

```sql
SELECT slug, label FROM marketing.channels ORDER BY slug;
```

Ожидание: среди slug есть `brand`, `creators`, `external`, `ooo`.

### Шаг 3.3. Search-queries sync (последняя закрытая неделя)

Через UI: на `/marketing/search-queries` нажать «Обновить» в `UpdateBar` → `POST /api/marketing/sync/search_queries`, фронт показывает прогресс через polling `marketing.sync_log`.

Через CLI:

```bash
python scripts/run_search_queries_sync.py --mode last_week
```

Ожидаемые лог-строки: `Bridge: inserted N new words into Sheets` (bridge сначала дописывает слова из `crm.branded_queries` и `crm.substitute_articles` в col A основного таба, потом WB-pull), `WB: pulled N rows for IP/OOO cabinet`, `Supabase: upserted N rows into marketing.search_queries_weekly`.

### Шаг 3.4. Promocodes sync (последняя закрытая неделя)

Через UI: кнопка на `/marketing/promo-codes` (UpdateBar, endpoint `/api/marketing/sync/promocodes`). Через CLI: `python scripts/run_wb_promocodes_sync.py --mode last_week`. Ожидаемая лог-строка bridge: `Promo bridge: inserted N UUIDs into Sheets dictionary`.

### Шаг 3.5. Статус через `marketing.sync_log`

```sql
SELECT job_id, status, started_at, finished_at, error_message
FROM marketing.sync_log
ORDER BY started_at DESC
LIMIT 5;
```

Ожидание: верхние записи — `status = 'completed'`, `error_message IS NULL`. Если `failed` — читать `error_message`.

---

## 4. Sanity-проверки

Свежесть данных:

```sql
SELECT MAX(week_start) AS last_week
FROM marketing.search_queries_weekly;
```

Ожидание: `last_week` = последний полный понедельник.

Покрытие RPC:

```sql
SELECT u.entity_type,
       COUNT(*)                                  AS total,
       COUNT(*) FILTER (WHERE a.orders > 0)      AS with_orders,
       COUNT(*) FILTER (WHERE a.frequency > 0)   AS with_frequency
FROM marketing.search_queries_unified u
LEFT JOIN LATERAL marketing.search_query_stats_aggregated('2026-02-01', '2026-04-27') a
  ON a.unified_id = u.unified_id
GROUP BY u.entity_type
ORDER BY 1;
```

> Имя RPC одно и то же — `marketing.search_query_stats_aggregated`; v2 и v3 — это альтернативные тела под одним идентификатором. Актуальная — v3 (см. `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v3.sql`, применена в R.1.1). v3 добавляет JOIN через `core.nomenklatura_wb`, чтобы метчить `substitute_articles` с цифровым `search_word` (nm_id) к `query_text == article`.

Ожидание для текущих данных (после R.1.1 фикс):
- `substitute_articles` (entity_type `nomenclature` / `ww_code`) — `with_orders` > 0; на bootstrap-периоде матчатся ~10 строк через nm_id-путь (`crm.substitute_articles.search_word == core.nomenklatura_wb.nm_id`, далее `wb.article` склеивается с `query_text`).
- `brand` — **остаётся нулевым** до тех пор, пока `crm.branded_queries` не будет заполнена (см. раздел 5). Это data-issue, не код.

UI: открыть `https://hub.os.wookiee.shop/marketing/search-queries`. В колонках «Частота / Переходы / Корзина / Заказы» цифры > 0 у `nomenclature` / `ww_code` строк, у `brand`-строк пока 0 (ожидаемо).

---

## 5. Известная проблема — brand-метрики остаются нулевыми

История этого ограничения растянулась на B.0.2 (v2 RPC) → R.1.1 (v3 RPC) → Phase 3 (data ops). Ниже — текущее состояние.

### История

- **HISTORICAL (B.0.2, v2 RPC).** Первая итерация джоинила `marketing.search_queries_unified` к `marketing.search_queries_weekly` ТОЛЬКО по `w.search_word = u.query_text`. На bootstrap-данных это давало 0 пересечений по всем сущностям — ни бренды, ни подмен-артикулы не получали метрик, потому что `crm.substitute_articles.search_word` хранит nm_id (например `163151603`), а `u.query_text` — артикул (`Wendy/white`). Полный пробой JOIN.
- **FIXED (R.1.1, v3 RPC).** Текущая активная версия — `database/marketing/rpcs/2026-05-13-search-query-stats-aggregated-v3.sql`. Тело расширено двумя путями JOIN:
  - прямой: `w.search_word = u.query_text` (как было) — закрывает `brand`-сущности и текстовые подмен-артикулы;
  - через `core.nomenklatura_wb`: `w.search_word = nwb.nm_id::text AND nwb.article = u.query_text` — закрывает substitute_articles, у которых `search_word` числовой nm_id.

  Эффект на bootstrap-периоде: ~10 строк `substitute_articles` (entity_type `nomenclature` / `ww_code`) с непустым `nomenklatura_wb` получают ненулевые `frequency / transitions / additions / orders`.

- **REMAINING (Phase 3 data ops).** Brand-метрики продолжают быть нулевыми — это уже не баг кода, а пустая таблица `crm.branded_queries` (0 rows). Пока туда не зальют хотя бы 5-10 brand-aliases, отражающих то, как WB реально пишет бренд в `search_queries_weekly.search_word`, RPC честно вернёт 0 по всем `entity_type = 'brand'` строкам unified.

### Симптом сейчас (после R.1.1)

`brand`-строки в UI и в покрытии-запросе из §4 — все нули. `nomenclature` / `ww_code` — частично заполнены.

### Проверить, какие brand-слова реально приходят от WB

```sql
SELECT DISTINCT search_word
  FROM marketing.search_queries_weekly
 WHERE search_word !~ '^[0-9]+$'  -- отсечь числовые nm_id из bridge
 ORDER BY 1
 LIMIT 100;
```

Глазами выделить те, что выглядят как бренд/модель/коллекция (`wookiee`, `wendy`, `audrey` и т.п.), и засеять `crm.branded_queries`.

### Шаблон для seed-а brand-aliases

> Это **черновик**, требует ревью оператора (Phase 3 data-ops тикет). Не запускать вслепую — `canonical_brand = 'Wookiee'` подойдёт не всем строкам; для модель-специфичных запросов нужен правильный `canonical_brand` (например `Wendy` для `wendy black`).

```sql
-- Seed brands from observed search_word values that look like brand names
-- (Example, requires operator review):
INSERT INTO crm.branded_queries (query, canonical_brand, status, created_at)
SELECT DISTINCT search_word, 'Wookiee', 'active', NOW()
  FROM marketing.search_queries_weekly
 WHERE search_word ~ '^[a-zа-я]+'  -- non-numeric, alphabetic
   AND search_word NOT IN (SELECT query FROM crm.branded_queries)
LIMIT 10;
```

После INSERT-а view `marketing.search_queries_unified` сразу подхватит новые `brand`-строки (это view, без материализации), а v3 RPC через прямой JOIN (`w.search_word = u.query_text`) вернёт по ним ненулевые метрики.

### Долгосрочное решение

Phase 3 data-ops тикет (не код, а данные + процесс):
1. Собрать первичный seed brand-aliases вручную (5-15 строк, с правильными `canonical_brand` / `model_osnova_id`).
2. Решить, нужен ли в `crm.branded_queries` дополнительный столбец `match_pattern` (LIKE/regex), чтобы один запис ловил множество вариаций (`wendy*` → все «wendy black», «wendy 30», и т.д.) — альтернатива поштучному вводу.
3. Зафиксировать оператора, ответственного за поддержание этой таблицы (CRM-вкладка `branded_queries` уже есть в Hub).

---

## 6. Откат

Если v2/v3 view+RPC сломали что-то в проде и нужно срочно откатиться к v1.

```bash
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-09-search-queries-unified.DOWN.sql
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-09-search-queries-unified.sql
psql "$SUPABASE_DB_URL" -f database/marketing/rpcs/2026-05-09-search-query-stats-aggregated.sql
```

DOWN-скрипт дропнет v2 view и текущее тело RPC (v3 шарит идентификатор с v2 — DROP по имени снесёт обе ревизии); файлы 2026-05-09 пересоздадут v1-версии (без `entity_type`, без JOIN на weekly — RPC возвращает нули, как было до этой ветки). Сид `marketing.channels` откатывать не обязательно — лишняя строка ничего не ломает. UI продолжит работать на v1-схеме: фронт ветки использует только колонки, которые есть и в v1, новые поля опциональны.

---

## 7. Связанные документы

- `docs/runbooks/wb-marketing-sync.md` — общая архитектура двух cron-сервисов (источник истины по Sheets + Supabase).
- `docs/scripts/search-queries-sync.md` — детальный CLI-справочник.
- `docs/scripts/wb-promocodes-sync.md` — то же для промокодов.
- План: `docs/superpowers/plans/2026-05-12-marketing-v4-fidelity.md` — секция Phase 2B + задачи B.0.x / B.1.x / B.2.x.
