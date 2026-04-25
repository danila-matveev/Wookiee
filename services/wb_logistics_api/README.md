# WB Logistics API

## Назначение
FastAPI HTTP-сервис, оборачивающий пайплайн `services/wb_localization/` (расчёт перестановок и оптимизация индекса локализации WB). Запускается из кнопки в Google Sheets через Apps Script: пользователь жмёт кнопку → GAS дёргает `/run` с API-ключом → сервис фоновым потоком прогоняет расчёт по всем кабинетам и обновляет Sheets.

## Точка входа / как запускать
Деплой в Docker через `deploy/docker-compose.yml` (сервис `wb-logistics-api`, образ собирается из `deploy/Dockerfile.wb_logistics_api`).

Эндпоинты:
- `POST /run` — запуск расчёта в фоне (header `x-api-key`)
- `GET /status` — текущий статус (`idle | running | done | error`)
- `GET /health` — healthcheck для Docker

Локально:
```bash
uvicorn services.wb_logistics_api.app:app --host 0.0.0.0 --port 8000
```

## Зависимости
- Data: WB API (`warehouse_remains`, `supplier/orders`), МойСклад API, Google Sheets (`WB_LOGISTICS_SPREADSHEET_ID` / legacy `VASILY_SPREADSHEET_ID`)
- External: FastAPI, uvicorn, gspread (через `shared/clients/sheets_client.py`)
- Internal: `services/wb_localization/` (вся бизнес-логика расчёта)

## Связанные скиллы
- `/logistics-report` — еженедельный/ежемесячный аналитический отчёт по логистике, потребляет результаты расчёта локализации

## Owner
danila-matveev
