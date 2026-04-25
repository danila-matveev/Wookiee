# WB Localization

## Назначение
Пайплайн оптимизации индекса локализации (ИЛ) WB: скачивает остатки и заказы по кабинетам, рассчитывает локальные/нелокальные продажи по 6 ФО, строит перестановки между складами WB и допоставки со своего склада МойСклад, симулирует понедельный прогноз ИЛ на 13 недель и сценарии экономики при 30–90% локализации. Результат публикуется в Google Sheets (один файл, листы по кабинетам).

## Точка входа / как запускать
```bash
# CLI (один кабинет)
python -m services.wb_localization.run_localization --cabinet ooo --days 14
python -m services.wb_localization.run_localization --cabinet ip --dry-run

# Через HTTP (все кабинеты, фоном)
curl -X POST -H "x-api-key: $WB_LOGISTICS_API_KEY" http://server:8000/run
```

## Зависимости
- Data: WB API (`warehouse_remains`, `supplier/orders`), МойСклад API, Google Sheets (`WB_LOGISTICS_SPREADSHEET_ID`)
- External: pandas, httpx, gspread (через `shared/clients/sheets_client.py`)
- Internal: `shared/clients/wb_client.py`, `shared/clients/moysklad_client.py`, `services/sheets_sync/config.py`

## Структура
- `run_localization.py` — обёртка с CLI и интеграцией калькуляторов
- `generate_localization_report_v3.py` — основная логика расчёта перестановок (v3)
- `calculators/` — sub-package с pure-Python калькуляторами (ИЛ/ИРП анализ, сценарии 30–90%, прогноз roadmap, справочник)
- `sheets_export/` — sub-package для записи всех листов в Google Sheets
- `irp_coefficients.py` — таблица КТР/КРП и лимиты перераспределения
- `wb_localization_mappings.py` — маппинг складов WB → ФО
- `history.py` — append-only история запусков
- `config.py` — конфигурация (кабинеты, период, spreadsheet ID)

## Связанные скиллы
- `/logistics-report` — еженедельный/ежемесячный отчёт по логистике, использует артефакты этого пайплайна
- HTTP-обёртка живёт в `services/wb_logistics_api/` (запуск из кнопки в Google Sheets)

## Owner
danila-matveev
