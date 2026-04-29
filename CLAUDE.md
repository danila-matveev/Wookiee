# Wookiee — правила для Claude Code

## Основные правила

Все правила определены в [AGENTS.md](AGENTS.md). Прочитай его ПЕРВЫМ перед любым действием.

## Claude-специфичные настройки

- Локальные разрешения: `.claude/settings.local.json`
- Команды: `.claude/commands/`
- Навигация по проекту: `docs/index.md`

## Quick Reference (из AGENTS.md)

- Онбординг: `ONBOARDING.md`
- Скиллы: `docs/skills/`
- DB-запросы: только `shared/data_layer.py` (шим: `scripts/data_layer.py`)
- Конфигурация: только `shared/config.py` (шим: `scripts/config.py`, читает из `.env`)
- GROUP BY по модели: ВСЕГДА с `LOWER()`
- Процентные метрики: ТОЛЬКО средневзвешенные
- Проблемы качества данных: фиксировать в `docs/database/DATA_QUALITY_NOTES.md`
- Supabase: RLS включён, новые таблицы — обязательно RLS + политики (см. `database/sku/README.md`)
