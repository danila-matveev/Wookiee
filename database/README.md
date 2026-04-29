# database/

Источники истины для всех баз данных и схем Wookiee. Один каталог = одна база/схема.

## Зачем эта папка существует

Единая точка для DDL/миграций/документации всех Supabase-схем Wookiee. Под одной крышей:
- `database/sku/` — товарная матрица (артикулы, модели, цвета, остатки)
- `database/crm/` — Influencer CRM (блогеры, креативы, кампании, performance)

Что было до этого: товарная матрица жила в `sku_database/` в корне репо, CRM-схема существовала только в `.superpowers/brainstorm/` (gitignore-папке) — canonical DDL в репо отсутствовал, хотя миграция в Supabase была применена. Теперь обе схемы в одном месте.

## Содержимое

| Папка | Supabase schema | Назначение | Статус |
|---|---|---|---|
| [crm/](crm/) | `crm` | Influencer CRM — блогеры, креативы, кампании, performance | ✅ Applied 2026-04-27 |
| [sku/](sku/) | `public` | Товарная матрица — артикулы, модели, цвета, остатки (ранее `sku_database/` в корне) | ✅ Production |
| `services/tool_telemetry/schema.sql` (legacy расположение, внутри сервиса) | `public.tool_telemetry` | Телеметрия запусков скиллов | ✅ Production |

> **Legacy расположение** — `tool_telemetry/schema.sql` пока лежит внутри сервиса-логгера: перенос затронул бы ссылки в коде сервиса. Новые БД сразу попадают в `database/`.

## Как добавлять новую базу

1. Создай папку `database/<schema_name>/` (snake_case, имя совпадает со схемой в Supabase)
2. Положи туда:
   - `schema.sql` — DDL (CREATE TABLE, индексы, триггеры, RLS-политики)
   - `README.md` — описание: что хранится, кто пишет, кто читает, связь с другими таблицами
   - `migrations/` — папка для последующих миграций (формат: `001_short_description.sql`)
3. Обнови таблицу выше в этом файле
4. Если нужен ETL — клади его в `services/<schema_name>_etl/` (пример: будущий `services/sheets_etl/` для CRM)

## Соглашения для DDL

- **PK**: `BIGSERIAL PRIMARY KEY` (не UUID — экономия места и быстрее JOIN'ы)
- **Timestamps**: `timestamptz DEFAULT now()` для всех `created_at`/`updated_at`
- **Soft-delete**: через `archived_at TIMESTAMPTZ` (NULL = активная запись), не через `is_deleted BOOLEAN`
- **Enums**: `text + CHECK (col IN (...))` вместо native enum (проще миграции)
- **Foreign keys**: `ON DELETE RESTRICT` (никаких silent data loss)
- **RLS**: ВКЛЮЧЕН на каждой таблице. Минимум: `service_role` full access, `authenticated` read-only, `anon` revoked.
  См. [.claude/rules/infrastructure.md](../.claude/rules/infrastructure.md) — это требование для всех новых таблиц.
- **Search path**: каждая миграция начинается с `SET search_path = <schema>;`

## Где находятся данные

Все базы — на одном Supabase-проекте `gjvwcdtfglupewcwzfhw`. Подключение через `shared/data_layer/_connection.py` (читает credentials из `.env`).

См. также:
- [docs/database/DATABASE_REFERENCE.md](../docs/database/DATABASE_REFERENCE.md) — полный справочник таблиц с примерами запросов
- [docs/database/DATA_QUALITY_NOTES.md](../docs/database/DATA_QUALITY_NOTES.md) — известные проблемы качества данных

## Owner
danila-matveev
