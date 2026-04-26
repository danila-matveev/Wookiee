# Logging Conventions

## Services Runtime

- Все сервисы логируют в stdout/stderr контейнера
- Для production диагностики: `docker logs <container> --tail 50`
- Уровень логирования задаётся через `LOG_LEVEL` в `.env` (default: `INFO`)

## WB Localization

- Runtime-логи: stdout/stderr
- История расчётов: `services/wb_localization/data/vasily.db`

## ETL and Sheets Sync

- ETL и sync сервисы логируют в stdout контейнера
- Для production диагностики использовать `docker logs`

## Tool Telemetry

- Каждый запуск скилла логируется в Supabase (`tool_runs` таблица) через `shared/tool_logger.py`
- Просмотр через скилл `/tool-status` или напрямую в Supabase

## General Rules

- Не логировать секреты и токены
- `DEBUG` только для локальной отладки
- `INFO`/`WARNING` для production
- Structured logging (JSON) для сервисов с высокой нагрузкой
