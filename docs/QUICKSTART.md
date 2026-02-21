# Quickstart

## 1. Clone and Env

```bash
git clone <repo-url>
cd Wookiee
cp .env.example .env
```

Заполните `.env` минимумом:
- PostgreSQL: `DB_*`, `MARKETPLACE_DB_*`
- WB/OZON API: `WB_*`, `OZON_*`
- Telegram/OpenRouter для Олега: `TELEGRAM_BOT_TOKEN`, `BOT_PASSWORD_HASH`, `OPENROUTER_API_KEY`
- Google Sheets: `GOOGLE_SERVICE_ACCOUNT_FILE`, `SPREADSHEET_ID`

## 2. Install Dependencies

```bash
pip install -r agents/oleg/requirements.txt
pip install -r services/sheets_sync/requirements.txt
pip install -r services/vasily_api/requirements.txt
```

## 3. Verify Project

```bash
python3 -m compileall -q agents services shared scripts
python3 -m pytest -q
python3 -m pytest -q services/marketplace_etl/tests
```

## 4. Main Entrypoints

```bash
# Oleg bot (default mode)
python3 -m agents.oleg

# Oleg agent loop
python3 -m agents.oleg agent

# WB localization service dry-run
python3 -m services.wb_localization.run_localization --dry-run

# Sheets sync
python3 -m services.sheets_sync

# Marketplace ETL daily sync
python3 -m services.marketplace_etl.scripts.run_daily_sync
```

## 5. Docker Deploy (optional)

```bash
docker compose -f deploy/docker-compose.yml up -d
```
