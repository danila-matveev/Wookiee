# WB Promocodes Sync — runbook

**Purpose:** weekly Google Sheets sync of WB promocode metrics for ООО + ИП.

## Workflow (dictionary-driven)

1. **Manual step (любая команда):** заполняем справочник `Промокоды_справочник`.
   Колонки: `UUID | Название | Канал | Скидка % | ИП | ООО | Старт | Окончание | Примечание`.
   `ИП` и `ООО` — чекбоксы; ставим галочку в кабинете(ах), где промокод реально работает.
2. **Скрипт каждую неделю** читает справочник, создаёт строки на листе аналитики
   (по одной на каждую пару `(UUID, кабинет с галочкой)`), фетчит метрики из WB API
   и обновляет ячейки. Промокоды, которых нет в справочнике, **в аналитику не попадают** —
   их UUID пишутся в лог как warning.
3. **Cron** запускает CLI каждый понедельник в 12:00 МСК (см. ниже).

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

Server runs in Europe/Moscow TZ — schedule fires at **Monday 12:00 МСК**, when
the previous full ISO week (Mon-Sun) is already closed.

```cron
0 12 * * 1  curl -sS -X POST http://localhost:8092/promocodes/run \
            -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" \
            -H "Content-Type: application/json" \
            -d '{"mode":"last_week"}' \
            >> /var/log/wb-promocodes-cron.log 2>&1
```

Install:

```bash
ssh timeweb
crontab -l | grep -v promocodes > /tmp/cron.txt   # drop any old entry
cat >> /tmp/cron.txt <<'EOF'
0 12 * * 1  curl -sS -X POST http://localhost:8092/promocodes/run -H "X-API-Key: $(grep PROMOCODES_API_KEY /app/.env | cut -d= -f2)" -H "Content-Type: application/json" -d '{"mode":"last_week"}' >> /var/log/wb-promocodes-cron.log 2>&1
EOF
crontab /tmp/cron.txt
crontab -l | grep promocodes        # verify
```

## GAS button

See `apps_script/promocodes_button.gs` for installation and behavior.

## Manual run inside container

```bash
docker exec wb-logistics-api python scripts/run_wb_promocodes_sync.py
```
