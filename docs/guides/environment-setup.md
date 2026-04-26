# Environment Setup

## Requirements

- Python 3.11+
- Docker + docker compose (for deploy)
- Access to PostgreSQL (read-only DB server), WB/OZON API, Google Sheets service account

## Local Setup

```bash
git clone <repo-url>
cd Wookiee
cp .env.example .env
# заполни токены в .env
```

Install dependencies for the service you need:

```bash
pip install -r services/sheets_sync/requirements.txt
pip install -r services/wb_logistics_api/requirements.txt
pip install -r services/logistics_audit/requirements.txt
```

## Environment Variables

Minimum required groups in `.env`:

- Data access: `DB_*`, `SUPABASE_*`, `SUPABASE_URL`, `SUPABASE_KEY`
- Marketplace APIs: `WB_*`, `OZON_*`
- Sheets/WB localization: `GOOGLE_SERVICE_ACCOUNT_FILE`, `SPREADSHEET_ID`
- Notion: `NOTION_TOKEN` (for skills that publish to Notion)
- AI/LLM: `OPENROUTER_API_KEY`

## Validation

```bash
python3 -m compileall -q services shared scripts
python3 -m pytest -q
python3 -m services.wb_localization.run_localization --dry-run
```

## Production Server (Timeweb)

- Host: `77.233.212.61`
- Deploy workflow: `.github/workflows/deploy.yml`
- Deploy is sequenced after successful CI (`.github/workflows/ci.yml`)
