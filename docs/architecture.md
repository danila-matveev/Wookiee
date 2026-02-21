# Wookiee — Architecture

## Current Production Contour

`Oleg + Ibrahim + marketplace_etl + sheets_sync + wb_localization + deploy`

## Components

### AI Agents (`agents/`)

| Компонент | Путь | Роль | Интерфейс |
|---|---|---|---|
| Олег | `agents/oleg/` | Финансовая аналитика, рекомендации, Telegram runtime | Telegram |
| Ибрагим | `agents/ibrahim/` | Data engineering, ETL/DB orchestration | CLI |

### Services (`services/`)

| Сервис | Путь | Назначение |
|---|---|---|
| Marketplace ETL | `services/marketplace_etl/` | Загрузка WB/OZON API данных в PostgreSQL |
| Sheets Sync | `services/sheets_sync/` | Синхронизация Google Sheets |
| WB Localization | `services/wb_localization/` | Расчёт локализации WB + экспорт в Google Sheets |
| Vasily API | `services/vasily_api/` | HTTP запуск WB localization расчётов |
| Ozon Delivery | `services/ozon_delivery/` | Утилиты оптимизации доставки OZON |

### Shared Layer

- `shared/config.py` — единая конфигурация
- `shared/data_layer.py` — единый слой SQL/данных
- `shared/clients/*` — API клиенты (WB/OZON/Sheets/Bitrix/MoySklad)

## Runtime Entrypoints

- `python -m agents.oleg`
- `python -m services.marketplace_etl.scripts.run_daily_sync`
- `python -m services.sheets_sync.runner`
- `python -m services.wb_localization.run_localization`
- `uvicorn services.vasily_api.app:app --host 0.0.0.0 --port 8000`

## Deprecated / Archived

- `agents/lyudmila` удалён из активного runtime (архив: `docs/archive/retired_agents/lyudmila/`)
- Агентный runtime Василия удалён (`agents/vasily` архивирован)
- Актуальный модуль локализации: `services/wb_localization`
