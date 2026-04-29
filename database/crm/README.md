# database/crm/ — Influencer CRM

Supabase schema `crm`: 22 таблицы для управления отношениями с блогерами и performance-маркетингом.

## Статус
- ✅ Phase 1 + Phase 2 completed (2026-04-27)
- 22 таблицы (15 core CRM + 7 supporting)
- Поверх существующей товарной матрицы (`database/sku` / `public.artikuly`, `public.modeli`, `public.modeli_osnova`, `public.cveta`)

## Содержимое

- [`schema.sql`](schema.sql) — полный DDL (849 строк), идемпотентный, оборачивается в transaction
- `migrations/` — будущие миграции (формат `001_short_description.sql`)

## Как применить

Локально к Supabase (один раз — миграция уже применена в проде):
```bash
psql $SUPABASE_URL -f database/crm/schema.sql
```

Или через Python-обёртку (если будет создана):
```bash
python scripts/migrations/008_create_influencer_crm.py
```

## Что внутри схемы

### Core CRM (15 таблиц)
- `marketers` — справочник маркетологов
- `bloggers` — основная таблица блогеров (handle, имя, контакты, теги)
- `blogger_channels` — каналы блогера (Telegram/Instagram/YouTube/etc)
- `blogger_audience_snapshots` — слепки аудитории по каналу с датой
- `creatives` — креативы (видео, посты, статьи)
- `creative_versions` — версии креатива (A/B/...)
- `campaigns` — кампании (бриф, бюджет, период)
- `campaign_blogger_links` — связь кампания × блогер × креатив
- `campaign_performance` — метрики performance (показы, клики, заказы, выкупы, ₽)
- `tasks` — задачи маркетологам по кампаниям
- `briefs` — брифы кампаний
- `payments` — выплаты блогерам
- `contracts` — договоры
- `notes` — заметки маркетологов
- `attachments` — файлы (упоминание ссылок на YaDisk)

### Supporting (7 таблиц)
- `tags` — глобальные теги (для блогеров и креативов)
- `tag_links` — связь тегов с любой entity (polymorphic)
- `audit_log` — лог изменений по всем таблицам
- `etl_runs` — журнал запусков ETL из Google Sheets
- `etl_row_errors` — конкретные строки которые упали при импорте
- `external_ids` — внешние ID (Google Sheet rows, Bitrix24 ID и т.д.)
- `notifications_outbox` — очередь нотификаций (для будущей интеграции)

## Соглашения

- **PK**: `BIGSERIAL` везде
- **Soft-delete**: через `archived_at TIMESTAMPTZ` (где применимо)
- **Foreign keys**: `ON DELETE RESTRICT`
- **RLS**: включён, `service_role` full / `authenticated` read-only / `anon` revoked
- **Enum-подобные поля**: `text + CHECK (col IN (...))`
- **ETL idempotency**: `sheet_row_id` — content-stable hash `MD5(handle || publish_date || channel)`, не позиционный A1-notation. ON CONFLICT DO UPDATE только по безопасным полям.

## Связанные модули

- ETL из Google Sheets: `services/sheets_etl/run.py` (план — на момент миграции существует, апдейтит CRM из Sheets)
- Reports: `/marketing-report` потребляет `campaign_performance` и `blogger_audience_snapshots`

## Owner
danila-matveev
