# Wookiee — Онбординг

## О проекте

Wookiee — система AI-агентов и аналитических инструментов для управления бизнесом бренда Wookiee. Данные: WB, OZON, CRM, Google Sheets, МойСклад.

## Быстрый старт

1. Скопируй `.env.example` → `.env`, заполни токены
2. `pip install -r services/sheets_sync/requirements.txt` (или нужного сервиса)
3. Запусти нужный скрипт: `python scripts/<script>.py`

## Структура проекта

```
shared/          — общая библиотека (data_layer, config, clients)
services/        — активные сервисы
scripts/         — CLI-скрипты аналитики (запускаются напрямую)
wookiee-hub/     — веб-интерфейс (React + Vite)
docs/            — документация
database/sku/    — товарная матрица (Supabase)
```

## Активные скиллы (CLI)

Все скиллы описаны в `docs/skills/`. Запуск через Claude Code:
`/finance-report`, `/marketing-report`, `/daily-brief`, `/logistics-report`, `/abc-audit`, и др.

## Активные сервисы

| Сервис | Назначение |
|---|---|
| `services/logistics_audit/` | Расчёт переплат WB за логистику |
| `services/wb_localization/` | Расчёт ИЛ/ИРП + экспорт в Sheets |
| `services/wb_logistics_api/` | HTTP-эндпоинт для wb_localization |
| `services/sheets_sync/` | Google Sheets ↔ Supabase |
| `services/content_kb/` | Векторный поиск по фото (pgvector) |
| `services/creative_kb/` | KB для контент-задач |
| `services/tool_telemetry/` | Логирование запусков инструментов |

## Инфраструктура

- App server: `ssh timeweb` (77.233.212.61)
- DB server: PostgreSQL на 89.23.119.253:6433 (только чтение)
- Supabase: товарная матрица + телеметрия инструментов
- Docker: `bash deploy/deploy.sh`

## Правила разработки

→ `AGENTS.md` (единый источник правил)
→ `docs/index.md` (навигация по документации)
→ `docs/guides/dod.md` (Definition of Done)
