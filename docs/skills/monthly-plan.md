# /monthly-plan — Ежемесячный план продаж

**Запуск:** `/monthly-plan`

## Что делает

Формирует ежемесячный план продаж: таргеты по выручке, марже и рекламным расходам на основе исторических данных и плановых показателей из таблицы `plan_article` в БД. Строит 13-недельный прогноз.

## Параметры

- `month` — месяц планирования (формат `YYYY-MM`, по умолчанию: следующий месяц)
- `scenario` — сценарий: `base`, `optimistic`, `pessimistic` (по умолчанию: `base`)

## Результат

План экспортируется в Google Sheets (`WB_LOCALIZATION_SPREADSHEET_ID`) и выводится в stdout.

## Зависимости

- PostgreSQL (DB Server, read-only)
- Google Sheets API (`GOOGLE_SERVICE_ACCOUNT_FILE`)
- `shared/data_layer.py`
