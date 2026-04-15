# Database Audit Remediation — Design Spec

**Дата:** 2026-04-06
**Автор:** Claude Code (brainstorming session)
**Статус:** Draft → Pending Approval

## Контекст

Проведён полный аудит Supabase-базы Wookiee (`gjvwcdtfglupewcwzfhw`, PG 17.6). Выявлены критические проблемы безопасности (RLS с ролью `{public}`), отсутствие статистики (ANALYZE никогда не запускался), дублирующие индексы, FK без покрытия, и мёртвые таблицы от архивированных подсистем.

## Решения, принятые в ходе brainstorming

1. **Подход:** Волнами по приоритету (3 волны: критическое → оптимизация → cleanup)
2. **Инструмент:** Supabase MCP (`apply_migration` для DDL, `execute_sql` для DML)
3. **hub.* схема:** RLS не нужен — Product Matrix API подключается через SQLAlchemy как `postgres` (service_role), не через Supabase SDK
4. **assistant.* схема:** Удалить — 0 ссылок в коде, таблицы пустые
5. **lyudmila_* таблицы:** Удалить — бот в архиве (`docs/archive/retired_agents/lyudmila/`), все таблицы пустые
6. **vector в public:** Отложить — требует пересоздания HNSW-индекса и функций, средний риск

---

## Wave 1 — Критическое (безопасность + статистика)

### 1.1 ANALYZE на всю базу

- **Тип:** DML (execute_sql)
- **Команда:** `ANALYZE;`
- **Риск:** Нулевой — read-only операция, обновляет только pg_statistic
- **Зачем:** Планировщик запросов работает вслепую. 90% таблиц никогда не получали ANALYZE. pg_stat показывает 0 строк даже если данные есть.

### 1.2 Фикс RLS — заменить `{public}` на `{postgres}`

- **Тип:** DDL (apply_migration)
- **Таблицы:** agent_registry, agent_runs, orchestrator_runs
- **Проблема:** Политики `service_role_all_*` с ролью `{public}` дают полный доступ (SELECT/INSERT/UPDATE/DELETE) **любому неаутентифицированному пользователю** через Supabase API
- **Действие:** DROP старые политики → CREATE новые с ролью `{postgres}`
- **Риск:** Низкий — таблицы служебные, доступ только с сервера

```sql
-- agent_registry
DROP POLICY IF EXISTS service_role_all_agent_registry ON agent_registry;
CREATE POLICY service_role_all_agent_registry ON agent_registry
  FOR ALL TO postgres USING (true) WITH CHECK (true);

-- agent_runs
DROP POLICY IF EXISTS service_role_all_agent_runs ON agent_runs;
CREATE POLICY service_role_all_agent_runs ON agent_runs
  FOR ALL TO postgres USING (true) WITH CHECK (true);

-- orchestrator_runs
DROP POLICY IF EXISTS service_role_all_orchestrator_runs ON orchestrator_runs;
CREATE POLICY service_role_all_orchestrator_runs ON orchestrator_runs
  FOR ALL TO postgres USING (true) WITH CHECK (true);
```

### 1.3 Добавить RLS-политики на таблицы без политик

- **Тип:** DDL (apply_migration)
- **Таблицы:** archive_records, field_definitions, sertifikaty, modeli_osnova_sertifikaty
- **Проблема:** RLS включён, но 0 политик = никто кроме superuser не может обратиться
- **Шаблон:** Стандартный (как на остальных таблицах каталога):

```sql
-- Для каждой таблицы:
CREATE POLICY service_role_full_access_{table} ON {table}
  FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY authenticated_select_{table} ON {table}
  FOR SELECT TO authenticated USING (true);
```

### 1.4 Зафиксировать search_path на функциях

- **Тип:** DDL (apply_migration)
- **Функции:** search_content, search_kb (2 overloads)
- **Проблема:** Без фиксированного search_path возможна подмена объектов
- **Действие:** `ALTER FUNCTION ... SET search_path = public;`

---

## Wave 2 — Оптимизация (индексы)

### 2.1 Удалить дублирующие индексы

- **Тип:** DDL (apply_migration)
- **Дубли:**

| Таблица | UNIQUE constraint (оставляем) | Ручной индекс (удаляем) |
|---------|-------------------------------|------------------------|
| lyudmila_employees | lyudmila_employees_bitrix_id_key | idx_lyudmila_employees_bitrix_id |
| lyudmila_tasks | lyudmila_tasks_bitrix_task_id_key | idx_lyudmila_tasks_bitrix_id |

- **Риск:** Нулевой — UNIQUE constraint уже обеспечивает тот же индекс

> **Примечание:** Эти таблицы будут удалены в Wave 3. Если волны выполняются подряд в одной сессии, этот шаг можно пропустить (DROP TABLE удалит индексы автоматически).

### 2.2 Добавить индексы на FK-колонки без покрытия

- **Тип:** DDL (apply_migration)
- **Зачем:** При DELETE/UPDATE на родительской таблице Postgres делает seq scan по дочерней для проверки FK. На больших таблицах — тормозит.

| Таблица | FK-колонка | Индекс |
|---------|-----------|--------|
| cveta | status_id | idx_cveta_status_id |
| modeli_osnova | fabrika_id | idx_modeli_osnova_fabrika_id |
| modeli_osnova | status_id | idx_modeli_osnova_status_id |
| skleyki_wb | importer_id | idx_skleyki_wb_importer_id |
| skleyki_ozon | importer_id | idx_skleyki_ozon_importer_id |
| tovary | status_ozon_id | idx_tovary_status_ozon_id |
| tovary | status_sayt_id | idx_tovary_status_sayt_id |
| tovary | status_lamoda_id | idx_tovary_status_lamoda_id |
| tovary_skleyki_wb | skleyka_id | idx_tovary_skleyki_wb_skleyka_id |
| tovary_skleyki_ozon | skleyka_id | idx_tovary_skleyki_ozon_skleyka_id |

- **Не включаем:** modeli_osnova_sertifikaty.sertifikat_id (таблица имеет composite PK, малый объём), hub.audit_log.user_id и hub.saved_views.user_id (hub не в scope)
- **Риск:** Низкий

---

## Wave 3 — Cleanup (мёртвые таблицы и схемы)

### 3.1 Бэкап DDL удаляемых объектов

- **Тип:** Файл в репо
- **Путь:** `docs/database/dropped-tables-backup.sql`
- **Содержимое:** CREATE TABLE + CREATE INDEX + RLS policies для всех удаляемых таблиц
- **Зачем:** Если понадобится восстановить структуру (данных нет — все таблицы пустые)

### 3.2 Удалить схему `assistant`

- **Тип:** DDL (apply_migration)
- **Таблицы (6):** users, auth_codes, tasks_cache, events_cache, sync_state, notification_outbox
- **Обоснование:** 0 ссылок в коде, 0 строк данных, ни один индекс не использовался
- **Команда:** `DROP SCHEMA assistant CASCADE;`

### 3.3 Удалить таблицы `lyudmila_*`

- **Тип:** DDL (apply_migration)
- **Таблицы (5):** lyudmila_employees, lyudmila_tasks, lyudmila_task_comments, lyudmila_suggestions, lyudmila_user_preferences
- **Обоснование:** Бот Людмила в архиве, весь код в `docs/archive/retired_agents/lyudmila/`, 0 строк, все 17 индексов — 0 сканов
- **Порядок:** Сначала зависимые (comments, suggestions, preferences), потом tasks, потом employees

### 3.4 Удалить неиспользуемые индексы на живых таблицах

- **Только после подтверждения ANALYZE (Wave 1)** что таблицы действительно имеют данные
- **Кандидаты (agent_runs, 5 индексов):**

| Индекс | Размер | Сканов |
|--------|--------|--------|
| idx_agent_runs_run_id | 48 KB | 0 |
| idx_agent_runs_agent | 56 KB | 0 |
| idx_agent_runs_version | 16 KB | 0 |
| idx_agent_runs_status | 48 KB | 0 |
| idx_agent_runs_date | 40 KB | 0 |

- **Решение:** Удаляем только если после ANALYZE подтвердится, что таблица активно используется но индексы нет. Если таблица тоже не используется — оставить как есть (объём минимальный).

---

## Правила выполнения

### Перед каждой волной
- Снимок состояния: `list_tables` + `get_advisors`

### Внутри волны
- Каждая DDL-операция — отдельный `apply_migration` с осмысленным именем
- DML-операции (ANALYZE) — через `execute_sql`
- Порядок: сначала добавление (CREATE), потом удаление (DROP)

### После каждой волны
- `list_tables` — сверка что нужные объекты появились/исчезли
- `get_advisors(security)` + `get_advisors(performance)` — warnings должны уменьшиться
- Smoke-тест: `SELECT count(*) FROM <affected_table>` для каждой затронутой таблицы

### Rollback
- **Wave 1:** Пересоздать старые политики (DDL сохранён в миграции)
- **Wave 2:** DROP INDEX / CREATE INDEX обратно
- **Wave 3:** Восстановить из `dropped-tables-backup.sql` (данных нет — потери невозможны)

---

## Ожидаемый результат

| Метрика | До | После |
|---------|-----|-------|
| Security warnings | 11 | 3 |
| Performance warnings | 47 | ~15 |
| Таблиц в public | 27 | 22 |
| Схема assistant | 6 таблиц | удалена |
| Дублирующих индексов | 2 пары | 0 |
| FK без индексов (public) | 11 | 1 (modeli_osnova_sertifikaty) |
| Таблиц с RLS без политик | 4 | 0 |
| Таблиц с {public} ALL | 3 | 0 |

## Вне scope (отложено)

| Задача | Причина |
|--------|---------|
| Перенос vector из public в extensions | Средний риск, требует пересоздания HNSW-индекса (55 MB) и 3 функций |
| RLS на hub.* | Не нужен пока API через SQLAlchemy/postgres |
| RLS на assistant.* | Схема удаляется |
| Cleanup unused индексов на живых таблицах (кроме agent_runs) | Подождать 2 недели после ANALYZE |
