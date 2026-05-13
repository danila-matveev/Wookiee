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

Ожидание для текущих данных:
- `nomenclature` и `ww_code` — `with_orders` > 0 (исторические подмен-артикулы метчатся напрямую по `query_text == search_word`).
- `brand` — **может быть нулевым** даже после успешного sync. Это известная проблема, см. ниже.

UI: открыть `https://hub.os.wookiee.shop/marketing/search-queries`. В колонках «Частота / Переходы / Корзина / Заказы» цифры > 0 хотя бы у `nomenclature` и `ww_code`. В UpdateBar — «Готово», свежий timestamp.

---

## 5. Известная проблема — brand-метрики остаются нулевыми

Зафиксировано в задаче B.0.2 этой ветки.

### Симптом

После всех шагов раздела 3 RPC `search_query_stats_aggregated` для unified_id с `entity_type = 'brand'` возвращает нули по `frequency / transitions / additions / orders`, хотя `marketing.search_queries_weekly` содержит 1396 строк.

### Причина

RPC v2 джоинит `marketing.search_queries_unified` к `marketing.search_queries_weekly` по точному равенству:

```sql
ON w.search_word = u.query_text
```

В `crm.branded_queries` слова заведены в формате, который НЕ совпадает с тем, что WB API возвращает для bootstrap-периода в `marketing.search_queries_weekly.search_word`. На текущих данных пересечения нет.

Проверить руками:

```sql
SELECT q.query AS branded_query
FROM crm.branded_queries q
INTERSECT
SELECT DISTINCT search_word
FROM marketing.search_queries_weekly;
```

Если результат — 0 строк, симптом подтверждён.

### Временный workaround

Заполнить `crm.branded_queries` теми поисковыми словами, что реально есть в `marketing.search_queries_weekly`. Полуавтоматически:

```sql
SELECT DISTINCT w.search_word
FROM marketing.search_queries_weekly w
LEFT JOIN crm.branded_queries q ON q.query = w.search_word
WHERE q.id IS NULL
  AND (
    w.search_word ILIKE '%вуки%'
    OR w.search_word ILIKE '%wookie%'
    OR w.search_word ILIKE '%wendy%'
    OR w.search_word ILIKE '%audrey%'
    OR w.search_word ILIKE '%charlotte%'
  )
ORDER BY 1;
```

Глазами отфильтровать релевантные → INSERT в `crm.branded_queries` с правильным `canonical_brand` и `model_osnova_id`. После этого view + RPC начнут возвращать ненулевые метрики для бренда.

### Долгосрочное решение

Адресуется в Phase 2B-rework / Phase 3: либо нормализация `query_text` (lower + trim + диакритика), либо ввод поля `match_pattern` (LIKE/regex) в `crm.branded_queries`, либо отдельная таблица brand-aliases. Пока что — workaround выше.

---

## 6. Откат

Если v2 view/RPC сломали что-то в проде и нужно срочно откатиться к v1.

```bash
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-09-search-queries-unified.DOWN.sql
psql "$SUPABASE_DB_URL" -f database/marketing/views/2026-05-09-search-queries-unified.sql
psql "$SUPABASE_DB_URL" -f database/marketing/rpcs/2026-05-09-search-query-stats-aggregated.sql
```

DOWN-скрипт дропнет v2 view и v2 RPC; файлы 2026-05-09 пересоздадут v1-версии (без `entity_type`, без JOIN на weekly — RPC возвращает нули, как было до этой ветки). Сид `marketing.channels` откатывать не обязательно — лишняя строка ничего не ломает. UI продолжит работать на v1-схеме: фронт ветки использует только колонки, которые есть и в v1, новые поля опциональны.

---

## 7. Связанные документы

- `docs/runbooks/wb-marketing-sync.md` — общая архитектура двух cron-сервисов (источник истины по Sheets + Supabase).
- `docs/scripts/search-queries-sync.md` — детальный CLI-справочник.
- `docs/scripts/wb-promocodes-sync.md` — то же для промокодов.
- План: `docs/superpowers/plans/2026-05-12-marketing-v4-fidelity.md` — секция Phase 2B + задачи B.0.x / B.1.x / B.2.x.
