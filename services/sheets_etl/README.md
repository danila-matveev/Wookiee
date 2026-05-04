# sheets_etl

ETL-сервис для синхронизации данных CRM из Google Sheets в Supabase.

## Запуск

```bash
python -m services.sheets_etl.run
python -m services.sheets_etl.run --sheet integrations
```

## Структура

- `run.py` — CLI-оркестратор: pull → transform → upsert в порядке зависимостей
- `fetch.py` — загрузка листов из Google Sheets
- `transformers/` — трансформация данных по типу листа
- `loader.py` — upsert в Supabase
- `config.py` — конфиг (spreadsheet IDs, mapping)

## Зависимости

Требует `google_sa.json` (service account) и переменных из `.env` (`POSTGRES_*`, `SHEETS_SPREADSHEET_ID`).
