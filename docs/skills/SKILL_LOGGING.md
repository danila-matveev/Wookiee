# Логирование скиллов в Wookiee Hub

Каждый скилл обязан записать факт запуска в `tool_runs`. Это нужно чтобы Hub показывал статистику, последний статус и историю.

## Как это работает

В конце SKILL.md добавляется секция `## Логирование`. Она выполняется **всегда** — независимо от успеха или ошибки.

Claude вставляет данные через Supabase MCP (`execute_sql`). Пользователь читается из `USER_EMAIL` в `.env`.

---

## Шаблон: скилл с результатом в Notion

Вставить в конец SKILL.md (заменить `{TOOL_SLUG}` на slug из таблицы `tools`):

```
## Логирование (выполнить всегда в конце)

Определи переменные для логирования:
- `_log_status` = `success` или `error`
- `_log_url` = URL страницы в Notion (или пустая строка)
- `_log_items` = количество обработанных элементов (или 0)
- `_log_notes` = краткое описание результата или ошибки
- `_log_user` = значение USER_EMAIL из .env (или "unknown")

Выполни через Supabase MCP:

```sql
WITH ins AS (
  INSERT INTO tool_runs (
    id, tool_slug, status, trigger_type, triggered_by,
    result_url, items_processed, notes,
    started_at, finished_at, duration_sec
  ) VALUES (
    gen_random_uuid(),
    '{TOOL_SLUG}',
    '_log_status',       -- заменить на реальное значение
    'manual',
    'user:_log_user',    -- заменить на реальное значение
    '_log_url',          -- заменить на реальное значение (NULL если нет)
    _log_items,          -- заменить на реальное значение
    '_log_notes',        -- заменить на реальное значение
    now() - interval 'N seconds',  -- заменить N на реальную длительность
    now(),
    N                    -- заменить N на реальную длительность в секундах
  )
  RETURNING tool_slug, status
)
UPDATE tools SET
  total_runs = total_runs + 1,
  last_run_at = now(),
  last_status = '_log_status',  -- заменить
  updated_at = now()
WHERE slug = '{TOOL_SLUG}';
```

---

## Шаблон: скилл-коллектор (без Notion URL)

Тот же шаблон, только `result_url = NULL` и `_log_items` = количество строк/записей собранных данных.

---

## Шаблон: логирование ошибки

Если скилл завершился ошибкой:

```sql
WITH ins AS (
  INSERT INTO tool_runs (
    id, tool_slug, status, trigger_type, triggered_by,
    error_stage, error_message,
    started_at, finished_at, duration_sec
  ) VALUES (
    gen_random_uuid(),
    '{TOOL_SLUG}',
    'error',
    'manual',
    'user:_log_user',
    '_log_error_stage',   -- этап где произошла ошибка (например: "data_collection")
    '_log_error_message', -- текст ошибки (первые 500 символов)
    now() - interval 'N seconds',
    now(),
    N
  )
  RETURNING tool_slug
)
UPDATE tools SET
  total_runs = total_runs + 1,
  last_run_at = now(),
  last_status = 'error',
  updated_at = now()
WHERE slug = '{TOOL_SLUG}';
```

---

## Как определить USER_EMAIL в скилле

В начале скилла (или в секции "Подготовка") добавить:

```
Прочитай значение USER_EMAIL из файла `.env` в корне проекта.
Если переменная не найдена — использовать "unknown".
```

---

## Какие скиллы уже логируют

| Скилл | Slug | Логирование |
|-------|------|-------------|
| finance-report | `finance-report` | ✅ через SKILL.md блок |
| daily-brief | `daily-brief` | ✅ через Python ToolLogger |
| analytics-report | `analytics-report` | ✅ через Python ToolLogger |
| market-review | `market-review` | ✅ через Python ToolLogger |
| finolog-dds-report | `finolog-dds-report` | ✅ через Python ToolLogger |
| logistics-report | `logistics-report` | ✅ через Python ToolLogger |
| abc-audit | `abc-audit` | ⏳ pending |
| marketing-report | `marketing-report` | ⏳ pending |
| funnel-report | `funnel-report` | ⏳ pending |

---

## Настройка для коллег

Каждый член команды добавляет в свой `.env`:

```
USER_EMAIL=имя@wookiee.shop
```

Тогда в Hub будет видно кто запускал инструмент.
