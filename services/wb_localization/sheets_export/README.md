# wb_localization / sheets_export

Sub-пакет родительского модуля `services/wb_localization/`. Отвечает за запись результатов расчёта локализации в Google Sheets — по 5+ листов на кабинет плюс общие листы (Справочник, Сценарии, Roadmap, История). Публичный API сохранён в `__init__.py` (`export_to_sheets`, `export_dashboard`).

## Файлы
- `core_sheets.py` — основные листы кабинета: «Перемещения», «Допоставки», «Сводка», «Регионы», «Проблемные SKU» + общий дашборд «Обновление»
- `analysis_sheets.py` — листы анализа: «ИЛ Анализ», legacy «Экономика», append-only «История»
- `scenario_sheet.py` — лист «Сценарии» (новый, 30–90% градация локализации)
- `roadmap_sheet.py` — лист «Перестановки Roadmap» (понедельный прогноз эффекта)
- `reference_sheet.py` — лист «Справочник» (документация КТР/КРП и правил)
- `formatters.py` — общие хелперы стилизации (цвета, batchUpdate-операции)

## Зависимости
- `shared/clients/sheets_client.py` (gspread + Service Account)
- `services/wb_localization/config.py` (`GOOGLE_SA_FILE`, `VASILY_SPREADSHEET_ID`)

См. родительский [README](../README.md) для общей картины пайплайна.

## Owner
danila-matveev
