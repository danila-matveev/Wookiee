# shared/

Общая библиотека, которую используют все скрипты, скиллы и сервисы Wookiee. Импортируется через `from shared.<module> import …` (или через шим `scripts/<module>.py` для legacy кода).

## Что должно сюда попадать

- API-клиенты к внешним системам (WB, OZON, MPStats, Notion, Finolog, Sheets, OpenRouter и т.д.) — один клиент = один модуль в `clients/`
- Доступ к БД (PostgreSQL и Supabase) — все запросы только через `data_layer/`
- Утилиты, которые реально шарятся между ≥2 потребителями
- Конфиг (`config.py`) — единая точка чтения `.env`

## Что НЕ должно сюда попадать

- Бизнес-логика отчётов / агентов / скиллов → в `scripts/`, `services/` или `agents/`
- Узкоспециализированные helper'ы одного скилла → в его модуле
- Промпты LLM → рядом со своим агентом / скиллом

## Содержимое

| Модуль | Назначение |
|---|---|
| `config.py` | Чтение `.env`, единая точка конфигурации (см. также `scripts/config.py` — шим) |
| `clients/` | API-клиенты внешних систем (WB, OZON, MPStats, Sheets, Notion, Moysklad, OpenRouter) |
| `data_layer/` | Все SQL-запросы и DB-утилиты. ВСЕГДА используй это вместо raw psycopg2. См. `.claude/rules/data-quality.md` |
| `services/` | Сервисные обёртки над несколькими клиентами (сейчас: `finolog_service.py`) |
| `utils/` | Stateless утилиты (json, форматирование) |
| `model_mapping.py` | Маппинг артикулов в модели (используется отчётами) |
| `notion_blocks.py`, `notion_client.py` | Публикация отчётов в Notion DB |
| `tool_logger.py` | Унифицированный логгер для трекинга запусков скиллов в Supabase (`tool_telemetry`) |

## Правила импорта

- Внутри `shared/` — относительные импорты (`from .clients import ...`)
- Снаружи — абсолютные (`from shared.data_layer.finance import ...`)
- Никогда не импортируй из `services/` или `scripts/` внутри `shared/` — это создаст циклы

## Owner
danila-matveev
