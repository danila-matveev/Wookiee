# Wookiee — Architecture

## Current Production Contour

`sheets_sync (cron) + wb_localization + wb_logistics_api + logistics_audit + content_kb + creative_kb + tool_telemetry + wookiee-hub`

## Infrastructure

```
┌─────────────────────────────────┐          ┌──────────────────────────┐
│  APP SERVER (Timeweb Cloud)     │          │  DB SERVER (VPS Россия)  │
│  77.233.212.61 — Amsterdam      │  TCP     │  89.23.119.253           │
│                                 │ ◄──────► │                          │
│  Docker-контейнеры:             │  :6433   │  PostgreSQL (read-only)  │
│  ├── wookiee-cron               │          │  ├── pbi_wb_wookiee      │
│  ├── wb-logistics-api           │          │  └── pbi_ozon_wookiee    │
│  ├── n8n + caddy                │          │                          │
│  └── ...                        │          │  Управляется сторонним   │
│                                 │          │  разработчиком БД.       │
│  Деплой: GitHub Actions / SSH   │          └──────────────────────────┘
│  Домен: matveevdanila.com       │
└─────────────────────────────────┘
```

| Сервер | IP | Роль | Доступ |
|---|---|---|---|
| **App Server** | `77.233.212.61` | Docker runtime, CI/CD, reverse proxy | SSH `timeweb`, полный контроль |
| **DB Server** | `89.23.119.253` | PostgreSQL с данными WB/OZON | TCP :6433, **read-only** |

> Весь деплой — только на App Server. DB Server — чужой, мы подключаемся к нему из `.env` (`DB_HOST`).

Подробности: [infrastructure.md](infrastructure.md)

## Active Services (`services/`)

| Сервис | Путь | Назначение |
|---|---|---|
| Sheets Sync (cron) | `services/sheets_sync/` | Синхронизация Google Sheets ↔ Supabase |
| WB Localization | `services/wb_localization/` | Расчёт локализации WB + экспорт в Google Sheets |
| WB Logistics API | `services/wb_logistics_api/` | HTTP-эндпоинт для wb_localization |
| Logistics Audit | `services/logistics_audit/` | Аудит логистики WB + ETL тарифов складов → Supabase |
| Content KB | `services/content_kb/` | Векторный поиск по фото (pgvector + Gemini embeddings) |
| Creative KB | `services/creative_kb/` | KB для контент-задач |
| Tool Telemetry | `services/tool_telemetry/` | Логирование запусков инструментов в Supabase |

## Frontend (`wookiee-hub/`)

| Модуль | Путь | Назначение |
|---|---|---|
| Комьюнити | `wookiee-hub/src/modules/community/` | Страница отзывов и общения с покупателями |
| Агенты | `wookiee-hub/src/modules/agents/` | Управление AI-агентами и инструментами |

Stack: React + Vite + TypeScript + Supabase JS

## MCP Servers

| Сервер | Конфиг | Назначение |
|---|---|---|
| `wildberries-ip` | `.mcp.json` | Wildberries API — кабинет ИП |
| `wildberries-ooo` | `.mcp.json` | Wildberries API — кабинет ООО |

Оба запускают `node ./wildberries-mcp-server/dist/index.js` (stdio transport). ~160 инструментов в 11 категориях.

## Shared Layer

- `shared/config.py` — единая конфигурация
- `shared/data_layer.py` — единый слой SQL/данных
- `shared/clients/*` — API клиенты (WB/OZON/Sheets/MoySklad/Finolog)

## Runtime Entrypoints

- `python -m services.sheets_sync.runner`
- `python -m services.wb_localization.run_localization`
- `uvicorn services.wb_logistics_api.app:app --host 0.0.0.0 --port 8000`
- `python -m services.logistics_audit.etl.tariff_collector --cabinet OOO`

## Deprecated / Archived

- `agents/oleg` — финансовый AI-агент выведен из эксплуатации (2026-04), архив: `docs/archive/oleg-v2-architecture.md`
- `agents/ibrahim` — data-engineering модуль выведен (2026-04)
- `agents/lyudmila` — CRM AI-агент удалён из активного runtime, архив: `docs/archive/retired_agents/`
- `agents/vasily` — логистический AI-агент удалён, сервис переехал в `services/wb_localization/`
- `services/marketplace_etl` — ETL-пайплайн удалён (2026-04)
