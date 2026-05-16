# Wookiee

Система AI-скиллов и аналитических инструментов для управления бизнесом бренда Wookiee.
Данные: WB, OZON, CRM, Google Sheets, МойСклад.

Подробный онбординг: [ONBOARDING.md](ONBOARDING.md)

---

## Активные сервисы

| Сервис | Назначение |
|---|---|
| `services/logistics_audit/` | Расчёт переплат WB за логистику + ETL тарифов |
| `services/wb_localization/` | Расчёт ИЛ/ИРП + экспорт в Google Sheets |
| `services/wb_logistics_api/` | HTTP-эндпоинт для wb_localization |
| `services/sheets_sync/` | Синхронизация Google Sheets ↔ Supabase |
| `services/content_kb/` | Векторный поиск по фото (pgvector) |
| `services/creative_kb/` | KB для контент-задач |
| `services/tool_telemetry/` | Логирование запусков инструментов |

---

## Активные скиллы (Claude Code)

Все скиллы описаны в [`docs/skills/`](docs/skills/).

`/finance-report` `/marketing-report` `/daily-brief` `/logistics-report` `/abc-audit`
`/market-review` `/analytics-report` `/reviews-audit` `/funnel-report` `/monthly-plan`
`/finolog-dds-report` `/content-search` `/tool-status` `/tool-register`

---

## Shared Library

- `shared/config.py` — единая конфигурация (читает из `.env`)
- `shared/data_layer.py` — все DB-запросы (единственный источник)
- `shared/clients/` — API-клиенты (WB, OZON, МойСклад, Sheets, Finolog)

---

## Entrypoints

```bash
# WB localization dry-run
python -m services.wb_localization.run_localization --dry-run

# WB Logistics API
uvicorn services.wb_logistics_api.app:app --host 0.0.0.0 --port 8000

# Sheets sync
python -m services.sheets_sync.runner --list
python -m services.sheets_sync.runner fin_data_new --prod --start 14.03.2026 --end 13.05.2026

# WB tariffs daily collector
python -m services.logistics_audit.etl.tariff_collector --cabinet OOO

# Night DevOps hygiene scan (JSON + Markdown report only; no PR)
python -m scripts.nightly.hygiene_scan --print-summary
```

---

## Quick Setup

```bash
cp .env.example .env
# заполни токены в .env
pip install -r services/sheets_sync/requirements.txt
```

---

## Quality Gates

```bash
make test   # pytest -q
make lint   # ruff check
```

CI: `.github/workflows/ci.yml` — compileall + тесты (Python 3.11)

---

## Документация

- [AGENTS.md](AGENTS.md) — правила разработки (единый источник)
- [ONBOARDING.md](ONBOARDING.md) — онбординг
- [docs/index.md](docs/index.md) — навигация по документации
- [docs/architecture.md](docs/architecture.md) — текущая архитектура

---

## Инфраструктура

- App server: `ssh timeweb` (77.233.212.61, Timeweb Cloud)
- DB server: PostgreSQL 89.23.119.253:6433 (read-only, сторонний)
- Supabase: товарная матрица + телеметрия инструментов
- Docker: `bash deploy/deploy.sh`
