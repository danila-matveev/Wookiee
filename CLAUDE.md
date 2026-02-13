# Wookiee Analytics — правила для Claude Code

## Основные правила

Все правила определены в [AGENTS.md](AGENTS.md). Прочитай его ПЕРВЫМ перед любым действием.

## Claude-специфичные настройки

- Локальные разрешения: `.claude/settings.local.json`
- Команды: `.claude/commands/`
- Навигация по проекту: `agent_docs/index.md`

## Quick Reference (из AGENTS.md)

- DB-запросы: только `scripts/data_layer.py`
- Конфигурация: только `scripts/config.py` (читает из `.env`)
- GROUP BY по модели: ВСЕГДА с `LOWER()`
- Процентные метрики: ТОЛЬКО средневзвешенные
- Проблемы качества данных: фиксировать в `database_docs/DATA_QUALITY_NOTES.md`
- Supabase: RLS включён, новые таблицы — обязательно RLS + политики (см. `wookiee_sku_database/README.md`)
