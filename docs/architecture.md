# Wookiee — Architecture

## Current Production Contour

`Oleg + Ibrahim + marketplace_etl + sheets_sync + wb_localization + deploy`

## Infrastructure

```
┌─────────────────────────────────┐          ┌──────────────────────────┐
│  APP SERVER (Timeweb Cloud)     │          │  DB SERVER (VPS Россия)  │
│  77.233.212.61 — Amsterdam      │  TCP     │  89.23.119.253           │
│                                 │ ◄──────► │                          │
│  Docker-контейнеры:             │  :6433   │  PostgreSQL (read-only)  │
│  ├── wookiee_oleg               │          │  ├── pbi_wb_wookiee      │
│  ├── wookiee_sheets_sync        │          │  └── pbi_ozon_wookiee    │
│  ├── vasily-api                 │          │                          │
│  ├── oleg_mcp                   │          │  Управляется сторонним   │
│  ├── n8n + caddy                │          │  разработчиком БД.       │
│  └── ...                        │          └──────────────────────────┘
│                                 │
│  Деплой: GitHub Actions / SSH   │
│  Домен: matveevdanila.com       │
└─────────────────────────────────┘
```

| Сервер | IP | Роль | Доступ |
|---|---|---|---|
| **App Server** | `77.233.212.61` | Docker runtime, CI/CD, reverse proxy | SSH `timeweb`, полный контроль |
| **DB Server** | `89.23.119.253` | PostgreSQL с данными WB/OZON | TCP :6433, **read-only** |

> Весь деплой — только на App Server. DB Server — чужой, мы подключаемся к нему из `.env` (`DB_HOST`).

Подробности: [infrastructure.md](infrastructure.md)

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

### MCP Servers

| Сервер | Конфиг | Назначение |
|---|---|---|
| `wildberries-ip` | `.mcp.json` | Wildberries API — кабинет ИП. Товары, цены, остатки, заказы FBS, аналитика |
| `wildberries-ooo` | `.mcp.json` | Wildberries API — кабинет ООО. Те же инструменты, другой кабинет |

Оба экземпляра запускают `node ./wildberries-mcp-server/dist/index.js` (stdio transport). Токены берутся из `.env` (`WB_API_KEY_IP`, `WB_API_KEY_OOO`). Репо: `https://github.com/danila-matveev/wildberries-mcp-server`.

**~160 инструментов** в 11 категориях: products, prices, orders (FBS/DBS/DBW), analytics, marketing, feedback, reports, supplies, tariffs, documents. Полное покрытие Wildberries Seller API.

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
