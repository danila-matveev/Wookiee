# WB Promocodes Sync — runbook

**Purpose:** weekly Google Sheets sync of WB promocode metrics for ООО + ИП.

## Components
- Core: `services/sheets_sync/sync/sync_promocodes.py`
- HTTP: `services/wb_logistics_api/app.py` → `POST /promocodes/run`, `GET /promocodes/status`
- CLI: `scripts/run_wb_promocodes_sync.py`
- GAS: `apps_script/promocodes_button.gs`

## Env vars (`.env`)

```
PROMOCODES_API_KEY=<32-char hex>
PROMOCODES_SPREADSHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
PROMOCODES_DICT_SHEET=Промокоды_справочник
PROMOCODES_DATA_SHEET=Промокоды_аналитика
WB_API_KEY_IP=...
WB_API_KEY_OOO=...
```

## CLI

```bash
# Last closed ISO week
python scripts/run_wb_promocodes_sync.py

# Specific date range
python scripts/run_wb_promocodes_sync.py --mode specific \
    --from 2026-04-13 --to 2026-04-19

# Historical bootstrap (12 weeks back)
python scripts/run_wb_promocodes_sync.py --mode bootstrap --weeks-back 12
```

## Deploy

```bash
ssh timeweb
cd /app && git pull
docker restart wb-logistics-api
```

## Cron (host crontab on Timeweb)

```cron
0 9 * * 2  curl -sS -X POST http://localhost:8092/promocodes/run \
           -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" \
           -H "Content-Type: application/json" \
           -d '{"mode":"last_week"}' \
           >> /var/log/wb-promocodes-cron.log 2>&1
```

## GAS button

See `apps_script/promocodes_button.gs` for installation and behavior.

## Manual run inside container

```bash
docker exec wb-logistics-api python scripts/run_wb_promocodes_sync.py
```
