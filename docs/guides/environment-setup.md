# Environment Setup

## Requirements

- Python 3.11+
- Docker + docker compose (for deploy)
- Access to PostgreSQL (legacy + managed), WB/OZON API, Google Sheets service account

## Local Setup

```bash
git clone <repo-url>
cd Wookiee
cp .env.example .env
```

Install core dependencies:

```bash
pip install -r agents/oleg/requirements.txt
pip install -r services/sheets_sync/requirements.txt
pip install -r services/vasily_api/requirements.txt
```

## Environment Variables

Minimum required groups in `.env`:

- Oleg runtime: `TELEGRAM_BOT_TOKEN`, `BOT_PASSWORD_HASH`, `OPENROUTER_API_KEY`
- Data access: `DB_*`, `MARKETPLACE_DB_*`, `SUPABASE_*`
- Marketplace APIs: `WB_*`, `OZON_*`
- Sheets/WB localization: `GOOGLE_SERVICE_ACCOUNT_FILE`, `SPREADSHEET_ID`, `VASILY_SPREADSHEET_ID`

## Validation

```bash
python3 -m compileall -q agents services shared scripts
python3 -m pytest -q
python3 -m pytest -q services/marketplace_etl/tests
python3 -m services.wb_localization.run_localization --dry-run
```

## Production Server (Timeweb)

- Host: `77.233.212.61`
- Deploy workflow: `.github/workflows/deploy.yml`
- Deploy is sequenced after successful CI (`.github/workflows/ci.yml`)
