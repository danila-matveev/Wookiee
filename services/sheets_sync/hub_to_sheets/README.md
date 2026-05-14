# services/sheets_sync/hub_to_sheets

Hub → Google Sheets mirror sync. Reads Supabase export views (see
[`database/migrations/030_catalog_export_views.sql`](../../../database/migrations/030_catalog_export_views.sql))
and updates the mirror spreadsheet `CATALOG_MIRROR_SHEET_ID` row-by-row.

## Принципы

- **Mirror-first** — пишем только в зеркало, основная «Спецификация» не трогается.
- **Delta-update** — точечные `values.batchUpdate`, формат и заметки сохраняются.
- **Hub-empty не затирает** — пустое значение из БД не перезаписывает ячейку (правило #2 PLAN.md).
- **Anchor-based identification** — каждый лист имеет якорную колонку (см. `config.SHEET_SPECS`).
- **Idempotent** — повторный запуск без изменений в БД ≡ 0 операций.
- **Удаления** — для не-склеек: проставить `Статус = Архив`; для склеек: физическое удаление строки.

## Конфиг (`config.py`)

| Лист (Sheets tab)     | View                              | Anchor                                | Status col      |
|-----------------------|-----------------------------------|---------------------------------------|-----------------|
| Все модели            | `public.vw_export_modeli`         | `Модель`                              | `Статус`        |
| Все артикулы          | `public.vw_export_artikuly`       | `Артикул`                             | `Статус`        |
| Все товары            | `public.vw_export_tovary`         | `БАРКОД`                              | `Статус товара` |
| Аналитики цветов      | `public.vw_export_cveta`          | `Color code`                          | `Статус`        |
| Склейки WB            | `public.vw_export_skleyki_wb`     | (`Название склейки`, `БАРКОД`)        | — (delete)      |
| Склейки Озон          | `public.vw_export_skleyki_ozon`   | (`Название склейки`, `БАРКОД`)        | — (delete)      |

## CLI

```bash
# Read-only smoke (нужен только сервис-аккаунт + spreadsheet ID).
python -m services.sheets_sync.hub_to_sheets.runner --smoke

# Все 6 листов.
python -m services.sheets_sync.hub_to_sheets.runner --all

# Один лист.
python -m services.sheets_sync.hub_to_sheets.runner --sheet "Все модели"

# Подсчитать diff без записи.
python -m services.sheets_sync.hub_to_sheets.runner --sheet "Все товары" --dry-run
```

## Переменные окружения

| Variable                       | Назначение                                    |
|--------------------------------|-----------------------------------------------|
| `CATALOG_MIRROR_SHEET_ID`      | ID зеркальной таблицы                         |
| `GOOGLE_SERVICE_ACCOUNT_FILE`  | Путь к JSON service-account                   |
| `SUPABASE_HOST/PORT/DB/USER/PASSWORD` | DSN для psycopg2                       |

Сервис-аккаунт (`wookiee-dashboard@n8n-matveev.iam.gserviceaccount.com`)
должен иметь Editor access к зеркалу.

## Тесты

```bash
pytest tests/services/sheets_sync/
```

Покрытие — `diff.py` (правила overwrite, новая строка, архив, удаление склеек)
и `anchor.py` (composite-keys, дубликаты, регистр).
