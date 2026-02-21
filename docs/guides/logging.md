# Logging Conventions

## Oleg Runtime

- Логи: `agents/oleg/logs/`
- Уровень: `LOG_LEVEL` в `.env`
- Формат: standard Python logging

## WB Localization

- Runtime-логи: stdout/stderr
- История расчётов: `services/wb_localization/data/vasily.db`

## ETL and Sheets Sync

- ETL и sync сервисы логируют в stdout контейнера
- Для production диагностики использовать `docker logs`

## General Rules

- Не логировать секреты и токены
- `DEBUG` только для локальной отладки
- `INFO`/`WARNING` для production
