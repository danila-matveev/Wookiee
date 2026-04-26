# /marketing-report — Маркетинговый отчёт

**Запуск:** `/marketing-report`

## Что делает

Формирует маркетинговый отчёт: ДРР (внутренняя и внешняя реклама раздельно), воронка P&L, топ-модели по маржинальной прибыли. Экспортирует таблицы в Google Sheets.

## Параметры

- `period` — период (по умолчанию: текущий месяц)
- `channel` — канал: `wb`, `ozon`, `all` (по умолчанию: `all`)

## Результат

Данные экспортируются в Google Sheets (`MARKETING_SPREADSHEET_ID`). Сводка выводится в stdout.

## Зависимости

- PostgreSQL (DB Server, read-only)
- Google Sheets API (`GOOGLE_SERVICE_ACCOUNT_FILE`, `MARKETING_SPREADSHEET_ID`)
- `shared/data_layer.py`
