# Wookiee

Система AI-модулей для управления бизнесом бренда Wookiee.

Текущий production-контур:
- `agents/oleg`
- `agents/ibrahim`
- `services/marketplace_etl`
- `services/sheets_sync`
- `services/wb_localization`
- `deploy`

## Active Components

### Agents

- `agents/oleg/` — финансовый AI-агент (Telegram runtime + price analytics)
- `agents/ibrahim/` — data-engineering модуль (ETL/reconciliation/DB)

### Services

- `services/marketplace_etl/` — WB/OZON API -> PostgreSQL
- `services/sheets_sync/` — синхронизация Google Sheets
- `services/wb_localization/` — расчёт локализации WB + экспорт в Sheets
- `services/vasily_api/` — HTTP trigger для запуска WB localization
- `services/ozon_delivery/` — утилиты по доставке OZON

### Shared

- `shared/config.py` — единая конфигурация
- `shared/data_layer.py` — единый слой SQL/данных
- `shared/clients/*` — API-клиенты

## Entrypoints

```bash
# Oleg bot (default)
python -m agents.oleg

# Oleg agent loop
python -m agents.oleg agent

# Sheets sync
python -m services.sheets_sync

# Marketplace ETL daily sync
python -m services.marketplace_etl.scripts.run_daily_sync

# WB localization dry-run
python -m services.wb_localization.run_localization --dry-run

# Vasily API
uvicorn services.vasily_api.app:app --host 0.0.0.0 --port 8000
```

## CLI Scripts (`scripts/`)

Актуальные публичные скрипты:
- `scripts/abc_analysis.py`
- `scripts/abc_analysis_unified.py`
- `scripts/notion_sync.py`
- `scripts/wb_vuki_ratings.py`

Совместимость-шимы:
- `scripts/config.py`
- `scripts/data_layer.py`

## Quick Setup

```bash
cp .env.example .env
pip install -r agents/oleg/requirements.txt
pip install -r services/sheets_sync/requirements.txt
pip install -r services/vasily_api/requirements.txt
```

## Quality Gates

Локальная проверка:

```bash
python -m compileall -q agents services shared scripts
python -m pytest -q
python -m pytest -q services/marketplace_etl/tests
```

CI:
- `.github/workflows/ci.yml` — compileall + тесты (Python 3.11)
- `.github/workflows/deploy.yml` — deploy после успешного CI на `main`

## Docs

- `docs/index.md` — карта документации
- `docs/architecture.md` — текущая архитектура
- `docs/adr.md` — архитектурные решения
- `docs/development-history.md` — история изменений

## Archive / Retired

- `docs/archive/retired_agents/lyudmila/`
- `docs/archive/retired_agents/vasily_agent_runtime/`
- `docs/archive/agents/lyudmila-bot.md`
