# Database Audit Remediation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить критические проблемы безопасности, оптимизировать индексы, удалить мёртвые таблицы в Supabase-базе Wookiee.

**Architecture:** 3 волны через Supabase MCP — `execute_sql` для DML, `apply_migration` для DDL. Каждая волна завершается верификацией через `get_advisors` + smoke-тесты.

**Tech Stack:** Supabase MCP (project `gjvwcdtfglupewcwzfhw`), PostgreSQL 17.6

**Spec:** `docs/superpowers/specs/2026-04-06-db-audit-remediation-design.md`

---

## Wave 1 — Критическое (безопасность + статистика)

### Task 1: Снимок состояния "до" и ANALYZE

**Tools:** Supabase MCP `execute_sql`, `get_advisors`, `list_tables`

- [ ] **Step 1: Снять baseline — security advisors**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="security")
```

Записать количество warnings. Ожидаемо: 11.

- [ ] **Step 2: Снять baseline — performance advisors**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="performance")
```

Записать количество warnings. Ожидаемо: 47.

- [ ] **Step 3: Запустить ANALYZE на всю базу**

```sql
-- execute_sql
ANALYZE;
```

Ожидаемо: успешное выполнение, без ошибок.

- [ ] **Step 4: Проверить что ANALYZE обновил статистику**

```sql
-- execute_sql
SELECT relname, n_live_tup, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC
LIMIT 10;
```

Ожидаемо: `last_analyze` заполнен для всех таблиц, `n_live_tup` отражает реальное кол-во строк.

---

### Task 2: Фикс RLS — заменить `{public}` на `{postgres}`

**Tools:** Supabase MCP `apply_migration`

- [ ] **Step 1: Применить миграцию fix_rls_public_role**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="fix_rls_public_role",
  query=<SQL ниже>
)
```

```sql
-- agent_registry: заменить {public} → {postgres}
DROP POLICY IF EXISTS service_role_all_agent_registry ON agent_registry;
CREATE POLICY service_role_all_agent_registry ON agent_registry
  FOR ALL TO postgres USING (true) WITH CHECK (true);

-- agent_runs: заменить {public} → {postgres}
DROP POLICY IF EXISTS service_role_all_agent_runs ON agent_runs;
CREATE POLICY service_role_all_agent_runs ON agent_runs
  FOR ALL TO postgres USING (true) WITH CHECK (true);

-- orchestrator_runs: заменить {public} → {postgres}
DROP POLICY IF EXISTS service_role_all_orchestrator_runs ON orchestrator_runs;
CREATE POLICY service_role_all_orchestrator_runs ON orchestrator_runs
  FOR ALL TO postgres USING (true) WITH CHECK (true);
```

- [ ] **Step 2: Проверить что политики обновились**

```sql
-- execute_sql
SELECT tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('agent_registry', 'agent_runs', 'orchestrator_runs')
ORDER BY tablename;
```

Ожидаемо: все 3 политики с ролью `{postgres}`, не `{public}`.

---

### Task 3: Добавить RLS-политики на таблицы без политик

**Tools:** Supabase MCP `apply_migration`

- [ ] **Step 1: Применить миграцию add_missing_rls_policies**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="add_missing_rls_policies",
  query=<SQL ниже>
)
```

```sql
-- archive_records
CREATE POLICY service_role_full_access_archive_records ON archive_records
  FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY authenticated_select_archive_records ON archive_records
  FOR SELECT TO authenticated USING (true);

-- field_definitions
CREATE POLICY service_role_full_access_field_definitions ON field_definitions
  FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY authenticated_select_field_definitions ON field_definitions
  FOR SELECT TO authenticated USING (true);

-- sertifikaty
CREATE POLICY service_role_full_access_sertifikaty ON sertifikaty
  FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY authenticated_select_sertifikaty ON sertifikaty
  FOR SELECT TO authenticated USING (true);

-- modeli_osnova_sertifikaty
CREATE POLICY service_role_full_access_modeli_osnova_sertifikaty ON modeli_osnova_sertifikaty
  FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY authenticated_select_modeli_osnova_sertifikaty ON modeli_osnova_sertifikaty
  FOR SELECT TO authenticated USING (true);
```

- [ ] **Step 2: Проверить что политики созданы**

```sql
-- execute_sql
SELECT tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('archive_records', 'field_definitions', 'sertifikaty', 'modeli_osnova_sertifikaty')
ORDER BY tablename, policyname;
```

Ожидаемо: по 2 политики на каждую таблицу (service_role + authenticated).

---

### Task 4: Зафиксировать search_path на функциях

**Tools:** Supabase MCP `apply_migration`

- [ ] **Step 1: Применить миграцию fix_function_search_path**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="fix_function_search_path",
  query=<SQL ниже>
)
```

```sql
-- search_content (1 overload)
ALTER FUNCTION public.search_content(
  vector, integer, character varying, character varying, character varying, character varying, double precision
) SET search_path = public;

-- search_kb overload 1 (5 params)
ALTER FUNCTION public.search_kb(
  vector, integer, character varying, character varying, double precision
) SET search_path = public;

-- search_kb overload 2 (6 params, with filter_source_tag)
ALTER FUNCTION public.search_kb(
  vector, integer, character varying, character varying, double precision, character varying
) SET search_path = public;
```

- [ ] **Step 2: Проверить что search_path зафиксирован**

```sql
-- execute_sql
SELECT proname, proconfig
FROM pg_proc
WHERE proname IN ('search_content', 'search_kb')
  AND pronamespace = 'public'::regnamespace;
```

Ожидаемо: `proconfig` содержит `{search_path=public}` для всех 3 функций.

---

### Task 5: Верификация Wave 1

**Tools:** Supabase MCP `get_advisors`

- [ ] **Step 1: Проверить security advisors**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="security")
```

Ожидаемо: warnings уменьшились с 11. Не должно быть:
- `rls_enabled_no_policy` для archive_records, field_definitions, sertifikaty, modeli_osnova_sertifikaty
- `rls_policy_always_true` с ролью `{public}`
- `function_search_path_mutable` для search_content, search_kb

- [ ] **Step 2: Smoke-тест — запросы к затронутым таблицам**

```sql
-- execute_sql
SELECT 'agent_registry' as t, count(*) as c FROM agent_registry
UNION ALL SELECT 'agent_runs', count(*) FROM agent_runs
UNION ALL SELECT 'orchestrator_runs', count(*) FROM orchestrator_runs
UNION ALL SELECT 'archive_records', count(*) FROM archive_records
UNION ALL SELECT 'field_definitions', count(*) FROM field_definitions
UNION ALL SELECT 'sertifikaty', count(*) FROM sertifikaty;
```

Ожидаемо: все запросы выполняются без ошибок, данные доступны.

---

## Wave 2 — Оптимизация (индексы)

### Task 6: Добавить индексы на FK-колонки

**Tools:** Supabase MCP `apply_migration`

> **Примечание:** Шаг "удалить дубли lyudmila" пропускаем — таблицы удалятся в Wave 3.

- [ ] **Step 1: Применить миграцию add_fk_indexes**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="add_fk_indexes",
  query=<SQL ниже>
)
```

```sql
-- cveta
CREATE INDEX IF NOT EXISTS idx_cveta_status_id ON cveta(status_id);

-- modeli_osnova
CREATE INDEX IF NOT EXISTS idx_modeli_osnova_fabrika_id ON modeli_osnova(fabrika_id);
CREATE INDEX IF NOT EXISTS idx_modeli_osnova_status_id ON modeli_osnova(status_id);

-- skleyki
CREATE INDEX IF NOT EXISTS idx_skleyki_wb_importer_id ON skleyki_wb(importer_id);
CREATE INDEX IF NOT EXISTS idx_skleyki_ozon_importer_id ON skleyki_ozon(importer_id);

-- tovary
CREATE INDEX IF NOT EXISTS idx_tovary_status_ozon_id ON tovary(status_ozon_id);
CREATE INDEX IF NOT EXISTS idx_tovary_status_sayt_id ON tovary(status_sayt_id);
CREATE INDEX IF NOT EXISTS idx_tovary_status_lamoda_id ON tovary(status_lamoda_id);

-- junction tables
CREATE INDEX IF NOT EXISTS idx_tovary_skleyki_wb_skleyka_id ON tovary_skleyki_wb(skleyka_id);
CREATE INDEX IF NOT EXISTS idx_tovary_skleyki_ozon_skleyka_id ON tovary_skleyki_ozon(skleyka_id);
```

- [ ] **Step 2: Проверить что индексы созданы**

```sql
-- execute_sql
SELECT indexname, tablename
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_cveta_status_id',
    'idx_modeli_osnova_fabrika_id',
    'idx_modeli_osnova_status_id',
    'idx_skleyki_wb_importer_id',
    'idx_skleyki_ozon_importer_id',
    'idx_tovary_status_ozon_id',
    'idx_tovary_status_sayt_id',
    'idx_tovary_status_lamoda_id',
    'idx_tovary_skleyki_wb_skleyka_id',
    'idx_tovary_skleyki_ozon_skleyka_id'
  )
ORDER BY tablename;
```

Ожидаемо: 10 индексов.

---

### Task 7: Верификация Wave 2

**Tools:** Supabase MCP `get_advisors`

- [ ] **Step 1: Проверить performance advisors**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="performance")
```

Ожидаемо: `unindexed_foreign_keys` warnings уменьшились. Должны остаться только:
- hub.audit_log.user_id (hub не в scope)
- hub.saved_views.user_id (hub не в scope)
- modeli_osnova_sertifikaty.sertifikat_id (composite PK, малый объём)

---

## Wave 3 — Cleanup (мёртвые таблицы и схемы)

### Task 8: Создать бэкап DDL удаляемых таблиц

**Tools:** Write (файл в репо)

- [ ] **Step 1: Создать файл бэкапа**

Создать файл `docs/database/dropped-tables-backup.sql` с содержимым:

```sql
-- =============================================================
-- BACKUP DDL — dropped tables (2026-04-06)
-- Данные: все таблицы были пустыми (0 строк) на момент удаления
-- =============================================================

-- =====================
-- SCHEMA: assistant
-- =====================

CREATE SCHEMA IF NOT EXISTS assistant;

CREATE TABLE assistant.users (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  telegram_id bigint NOT NULL,
  telegram_chat_id bigint NOT NULL,
  bitrix_user_id bigint NOT NULL,
  email text NOT NULL,
  timezone text NOT NULL DEFAULT 'Europe/Moscow'::text,
  notifications_enabled boolean NOT NULL DEFAULT true,
  morning_time time without time zone NOT NULL DEFAULT '08:00:00'::time without time zone,
  evening_time time without time zone NOT NULL DEFAULT '18:00:00'::time without time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  UNIQUE (telegram_id),
  UNIQUE (email)
);

CREATE TABLE assistant.auth_codes (
  id bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY,
  telegram_id bigint NOT NULL,
  email text NOT NULL,
  code_hash text NOT NULL,
  expires_at timestamp with time zone NOT NULL,
  attempts smallint NOT NULL DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  PRIMARY KEY (id)
);

CREATE TABLE assistant.tasks_cache (
  id bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY,
  bitrix_task_id bigint NOT NULL UNIQUE,
  bitrix_user_id bigint NOT NULL,
  title text NOT NULL,
  status text NOT NULL,
  deadline timestamp with time zone,
  updated_at timestamp with time zone,
  raw_payload jsonb,
  PRIMARY KEY (id)
);

CREATE TABLE assistant.events_cache (
  id bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY,
  bitrix_event_id bigint NOT NULL UNIQUE,
  bitrix_user_id bigint NOT NULL,
  title text NOT NULL,
  start_at timestamp with time zone NOT NULL,
  end_at timestamp with time zone NOT NULL,
  updated_at timestamp with time zone,
  raw_payload jsonb,
  PRIMARY KEY (id)
);

CREATE TABLE assistant.sync_state (
  id bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY,
  bitrix_user_id bigint NOT NULL,
  entity_type text NOT NULL CHECK (entity_type = ANY (ARRAY['task', 'event', 'user'])),
  last_synced_at timestamp with time zone,
  PRIMARY KEY (id),
  UNIQUE (bitrix_user_id, entity_type)
);

CREATE TABLE assistant.notification_outbox (
  id bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY,
  dedupe_key text NOT NULL UNIQUE,
  telegram_chat_id bigint NOT NULL,
  payload jsonb NOT NULL,
  sent_at timestamp with time zone NOT NULL DEFAULT now(),
  PRIMARY KEY (id)
);

-- Indexes (assistant)
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON assistant.tasks_cache(deadline);
CREATE INDEX IF NOT EXISTS idx_events_start ON assistant.events_cache(start_at);
CREATE INDEX IF NOT EXISTS idx_sync_state_user ON assistant.sync_state(bitrix_user_id);

-- =====================
-- TABLES: lyudmila_*
-- =====================

CREATE TABLE public.lyudmila_employees (
  id serial PRIMARY KEY,
  bitrix_id integer NOT NULL UNIQUE,
  first_name text,
  last_name text,
  full_name text,
  email text,
  position text,
  department_ids integer[] DEFAULT '{}',
  is_internal boolean DEFAULT false,
  is_active boolean DEFAULT true,
  custom_role text,
  synced_at timestamp with time zone DEFAULT now()
);

CREATE TABLE public.lyudmila_tasks (
  id serial PRIMARY KEY,
  bitrix_task_id integer NOT NULL UNIQUE,
  title text,
  description text,
  status integer,
  priority integer,
  responsible_id integer,
  created_by integer,
  deadline timestamp with time zone,
  created_at timestamp with time zone,
  closed_at timestamp with time zone,
  auditors integer[] DEFAULT '{}',
  accomplices integer[] DEFAULT '{}',
  synced_at timestamp with time zone DEFAULT now()
);

CREATE TABLE public.lyudmila_task_comments (
  id serial PRIMARY KEY,
  bitrix_task_id integer NOT NULL,
  author_id integer,
  comment_text text,
  created_at timestamp with time zone,
  synced_at timestamp with time zone DEFAULT now()
);

CREATE TABLE public.lyudmila_suggestions (
  id serial PRIMARY KEY,
  telegram_id bigint NOT NULL,
  entity_type text NOT NULL,
  suggestion_text text NOT NULL,
  suggestion_type text,
  accepted boolean,
  created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE public.lyudmila_user_preferences (
  id serial PRIMARY KEY,
  telegram_id bigint NOT NULL,
  preference_key text NOT NULL,
  preference_value text NOT NULL,
  confidence real DEFAULT 0.5,
  updated_at timestamp with time zone DEFAULT now(),
  UNIQUE (telegram_id, preference_key)
);

-- Indexes (lyudmila)
CREATE INDEX IF NOT EXISTS idx_lyudmila_employees_bitrix_id ON public.lyudmila_employees(bitrix_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_employees_internal ON public.lyudmila_employees(is_internal);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_bitrix_id ON public.lyudmila_tasks(bitrix_task_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_responsible ON public.lyudmila_tasks(responsible_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_created_by ON public.lyudmila_tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_deadline ON public.lyudmila_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_lyudmila_tasks_status ON public.lyudmila_tasks(status);
CREATE INDEX IF NOT EXISTS idx_lyudmila_comments_task ON public.lyudmila_task_comments(bitrix_task_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_comments_author ON public.lyudmila_task_comments(author_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_suggestions_tg ON public.lyudmila_suggestions(telegram_id);
CREATE INDEX IF NOT EXISTS idx_lyudmila_prefs_tg ON public.lyudmila_user_preferences(telegram_id);

-- RLS policies (lyudmila)
-- All had: service_role_full_access (postgres, ALL) + authenticated_select (authenticated, SELECT)
```

---

### Task 9: Удалить схему `assistant`

**Tools:** Supabase MCP `apply_migration`

- [ ] **Step 1: Применить миграцию drop_assistant_schema**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="drop_assistant_schema",
  query=<SQL ниже>
)
```

```sql
DROP SCHEMA IF EXISTS assistant CASCADE;
```

- [ ] **Step 2: Проверить что схема удалена**

```sql
-- execute_sql
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'assistant';
```

Ожидаемо: 0 строк.

---

### Task 10: Удалить таблицы `lyudmila_*`

**Tools:** Supabase MCP `apply_migration`

- [ ] **Step 1: Применить миграцию drop_lyudmila_tables**

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="drop_lyudmila_tables",
  query=<SQL ниже>
)
```

```sql
-- Порядок: сначала зависимые, потом основные
DROP TABLE IF EXISTS public.lyudmila_task_comments CASCADE;
DROP TABLE IF EXISTS public.lyudmila_suggestions CASCADE;
DROP TABLE IF EXISTS public.lyudmila_user_preferences CASCADE;
DROP TABLE IF EXISTS public.lyudmila_tasks CASCADE;
DROP TABLE IF EXISTS public.lyudmila_employees CASCADE;
```

- [ ] **Step 2: Проверить что таблицы удалены**

```sql
-- execute_sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'lyudmila_%';
```

Ожидаемо: 0 строк.

---

### Task 11: Оценка индексов agent_runs после ANALYZE

**Tools:** Supabase MCP `execute_sql`

- [ ] **Step 1: Проверить использование индексов после ANALYZE**

```sql
-- execute_sql
SELECT
  indexrelname as index_name,
  idx_scan as scans,
  pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND relname = 'agent_runs'
ORDER BY idx_scan;
```

- [ ] **Step 2: Принять решение**

Если все 5 индексов по-прежнему 0 сканов, а таблица содержит данные (650+ строк) — удалить:

```
apply_migration(
  project_id="gjvwcdtfglupewcwzfhw",
  name="drop_unused_agent_runs_indexes",
  query=<SQL ниже>
)
```

```sql
DROP INDEX IF EXISTS idx_agent_runs_run_id;
DROP INDEX IF EXISTS idx_agent_runs_agent;
DROP INDEX IF EXISTS idx_agent_runs_version;
DROP INDEX IF EXISTS idx_agent_runs_status;
DROP INDEX IF EXISTS idx_agent_runs_date;
```

Если какие-то индексы уже показывают сканы — оставить их, удалить только неиспользуемые.

---

### Task 12: Финальная верификация

**Tools:** Supabase MCP `get_advisors`, `list_tables`, `execute_sql`

- [ ] **Step 1: Security advisors — финальный срез**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="security")
```

Ожидаемо: значительно меньше warnings чем baseline (11).

- [ ] **Step 2: Performance advisors — финальный срез**

```
get_advisors(project_id="gjvwcdtfglupewcwzfhw", type="performance")
```

Ожидаемо: значительно меньше warnings чем baseline (47).

- [ ] **Step 3: Финальный снимок таблиц**

```
list_tables(project_id="gjvwcdtfglupewcwzfhw", schemas=["public"], verbose=false)
```

Ожидаемо: 22 таблицы (было 27), нет lyudmila_*.

- [ ] **Step 4: Полный smoke-тест**

```sql
-- execute_sql
SELECT 'content_assets' as t, count(*) FROM content_assets
UNION ALL SELECT 'kb_chunks', count(*) FROM kb_chunks
UNION ALL SELECT 'agent_runs', count(*) FROM agent_runs
UNION ALL SELECT 'orchestrator_runs', count(*) FROM orchestrator_runs
UNION ALL SELECT 'tovary', count(*) FROM tovary
UNION ALL SELECT 'modeli_osnova', count(*) FROM modeli_osnova
UNION ALL SELECT 'artikuly', count(*) FROM artikuly;
```

Ожидаемо: все запросы выполняются, данные доступны.

- [ ] **Step 5: Сравнить с baseline и зафиксировать результат**

Составить таблицу "было/стало" и записать в комментарий к коммиту бэкап-файла.

| Метрика | До | После |
|---------|-----|-------|
| Security warnings | 11 | ? |
| Performance warnings | 47 | ? |
| Таблиц в public | 27 | 22 |
| Схема assistant | 6 таблиц | удалена |

---

## Порядок выполнения (summary)

```
Wave 1 (критическое):
  Task 1  → ANALYZE + baseline
  Task 2  → Фикс RLS {public} → {postgres}
  Task 3  → Добавить RLS-политики на 4 таблицы
  Task 4  → Зафиксировать search_path
  Task 5  → Верификация Wave 1

Wave 2 (оптимизация):
  Task 6  → Добавить FK-индексы (10 шт)
  Task 7  → Верификация Wave 2

Wave 3 (cleanup):
  Task 8  → Бэкап DDL (файл в репо)
  Task 9  → DROP assistant schema
  Task 10 → DROP lyudmila_* tables
  Task 11 → Оценка + cleanup agent_runs indexes
  Task 12 → Финальная верификация
```
