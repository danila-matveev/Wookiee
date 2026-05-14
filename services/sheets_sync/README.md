# services/sheets_sync/

Синхронизация данных из WB, OZON, МойСклад → Google Sheets. Заменяет 11 Google Apps Script.

Запускается как cron-задача в `wookiee-cron` контейнере (`scripts/run_search_queries_sync.py`).

Для ручного запуска финансового листа:

```bash
python -m services.sheets_sync.runner fin_data_new --prod --start 14.03.2026 --end 13.05.2026
```

→ Подробная документация: [DOCUMENTATION.md](DOCUMENTATION.md)
