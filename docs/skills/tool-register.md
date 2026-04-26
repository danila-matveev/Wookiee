# /tool-register — Регистрация нового инструмента

**Запуск:** `/tool-register`

## Что делает

Регистрирует новый инструмент (скилл) в каталоге: добавляет запись в таблицу `tools` в Supabase и обновляет `docs/TOOLS_CATALOG.md`. Источник истины — Supabase, Markdown генерируется автоматически.

## Параметры

- `name` — имя инструмента (обязательный, формат: `kebab-case`)
- `category` — категория: `analytics`, `finance`, `logistics`, `content`, `publishing`
- `description` — краткое описание (1-2 предложения)
- `version` — версия (по умолчанию: `1.0`)

## Результат

Запись добавляется в Supabase `tools`. `docs/TOOLS_CATALOG.md` обновляется через `scripts/generate_tools_catalog.py`.

## Зависимости

- Supabase (`tools` таблица)
- `services/tool_telemetry/version_tracker.py`
- `scripts/generate_tools_catalog.py`
