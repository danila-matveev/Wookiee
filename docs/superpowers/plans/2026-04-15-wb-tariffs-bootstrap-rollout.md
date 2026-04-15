# WB Tariffs Bootstrap Rollout Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fully finish the WB tariffs bootstrap by applying the real Supabase schema, importing history, backfilling the API gap, and installing the daily cron on `timeweb`.

**Architecture:** Code changes are already in place locally. This rollout plan is operational: first verify access and environment, then run the live bootstrap against Supabase, then prove idempotency and data completeness, and only after that install the host-level cron on the app server with a manual smoke run.

**Tech Stack:** Python 3, psycopg2, openpyxl, WB API, Supabase pooler, Ubuntu cron on Timeweb

---

### Task 1: Preflight And Access Checks

**Files:**
- Inspect: `.env`
- Inspect: `services/logistics_audit/etl/setup_wb_tariffs.py`
- Inspect: `services/logistics_audit/etl/cron_tariff_collector.sh`

- [ ] **Step 1: Re-run the local verification suite before touching external systems**

Run:

```bash
python3 -m pytest -q tests/services/logistics_audit/test_api_parsing.py tests/services/logistics_audit/test_overpayment.py tests/services/logistics_audit/test_tariff_calibrator.py tests/services/logistics_audit/test_tariff_etl.py
```

Expected: `20 passed`

- [ ] **Step 2: Confirm required env vars exist in the root `.env`**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(Path(".env"))
required = [
    "SUPABASE_HOST",
    "SUPABASE_PORT",
    "SUPABASE_DB",
    "SUPABASE_USER",
    "SUPABASE_PASSWORD",
    "WB_API_KEY_OOO",
]
missing = [key for key in required if not env.get(key)]
print({"missing": missing, "ok": not missing})
PY
```

Expected: `{"missing": [], "ok": True}`

- [ ] **Step 3: Confirm the historical workbook is present**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
path = Path("services/logistics_audit/Тарифы на логискику.xlsx")
print({"exists": path.exists(), "size_mb": round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else None})
PY
```

Expected: `exists=True`

- [ ] **Step 4: Validate server access before planning cron install**

Run:

```bash
ssh timeweb "pwd && test -d /home/danila/projects/wookiee && echo WOOKEE_OK"
```

Expected: prints the remote home path and `WOOKEE_OK`

### Task 2: Apply The Live Supabase Bootstrap

**Files:**
- Execute: `sku_database/scripts/migrations/007_create_wb_tariffs.py`
- Execute: `services/logistics_audit/etl/import_historical_tariffs.py`
- Execute: `services/logistics_audit/etl/setup_wb_tariffs.py`

- [ ] **Step 1: Run the bootstrap flow against the real Supabase database**

Run:

```bash
python3 -m services.logistics_audit.etl.setup_wb_tariffs
```

Expected:
- migration logs from `007_create_wb_tariffs.py`
- historical import progress logs
- one-time WB API backfill logs
- final verification log with `row_count`, `min_dt`, `max_dt`

- [ ] **Step 2: Verify the schema includes `storage_coef`**

Run:

```bash
python3 - <<'PY'
from shared.data_layer._connection import _get_supabase_connection

conn = _get_supabase_connection()
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'wb_tariffs'
    ORDER BY ordinal_position
""")
print(cur.fetchall())
cur.close()
conn.close()
PY
```

Expected: includes `('storage_coef', 'integer')`

- [ ] **Step 3: Verify the imported historical range is present**

Run:

```bash
python3 - <<'PY'
from shared.data_layer._connection import _get_supabase_connection

conn = _get_supabase_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*), MIN(dt), MAX(dt) FROM public.wb_tariffs")
print(cur.fetchone())
cur.close()
conn.close()
PY
```

Expected:
- `MIN(dt) = 2024-02-21`
- `COUNT(*) >= 38879`
- `MAX(dt)` reaches the latest successfully backfilled day

### Task 3: Prove Data Completeness And Idempotency

**Files:**
- Execute: `services/logistics_audit/etl/setup_wb_tariffs.py`
- Execute: `services/logistics_audit/etl/tariff_collector.py`

- [ ] **Step 1: Spot-check that both coefficients are stored**

Run:

```bash
python3 - <<'PY'
from shared.data_layer._connection import _get_supabase_connection

conn = _get_supabase_connection()
cur = conn.cursor()
cur.execute("""
    SELECT dt, warehouse_name, delivery_coef, storage_coef
    FROM public.wb_tariffs
    WHERE dt BETWEEN DATE '2024-02-21' AND DATE '2024-02-23'
    ORDER BY dt, warehouse_name
    LIMIT 10
""")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()
PY
```

Expected: sample rows show non-null `delivery_coef` and `storage_coef`

- [ ] **Step 2: Re-run bootstrap once to confirm it is safe**

Run:

```bash
python3 -m services.logistics_audit.etl.setup_wb_tariffs
```

Expected: completes without duplicate-key failure; final verification remains stable or only increases if new WB API dates became available

- [ ] **Step 3: Re-run daily collector for one existing date to confirm upsert idempotency**

Run:

```bash
python3 -m services.logistics_audit.etl.tariff_collector --date 2026-04-15 --cabinet OOO
```

Expected: completes successfully with upsert log and no uniqueness error

- [ ] **Step 4: Confirm the date gap is closed**

Run:

```bash
python3 - <<'PY'
from shared.data_layer._connection import _get_supabase_connection

conn = _get_supabase_connection()
cur = conn.cursor()
cur.execute("""
    SELECT generate_series(DATE '2026-03-30', CURRENT_DATE, INTERVAL '1 day')::date
    EXCEPT
    SELECT DISTINCT dt
    FROM public.wb_tariffs
    WHERE dt BETWEEN DATE '2026-03-30' AND CURRENT_DATE
    ORDER BY 1
""")
missing = cur.fetchall()
print({"missing_gap_dates": missing})
cur.close()
conn.close()
PY
```

Expected: `{"missing_gap_dates": []}` or only dates where WB returned no data and the collector logged a skip

### Task 4: Install And Smoke-Test The Daily Cron

**Files:**
- Execute: `services/logistics_audit/etl/cron_tariff_collector.sh`
- Update manually on server: user crontab for `timeweb`

- [ ] **Step 1: Copy latest code to the server if needed**

Run:

```bash
ssh timeweb "cd /home/danila/projects/wookiee && git status --short && git rev-parse --short HEAD"
```

Expected: repo is on the intended commit before cron install

- [ ] **Step 2: Install the cron entry manually**

Open:

```bash
ssh timeweb
crontab -e
```

Insert exactly:

```cron
PATH=/usr/local/bin:/usr/bin:/bin
CRON_TZ=Europe/Moscow
0 8 * * * /home/danila/projects/wookiee/services/logistics_audit/etl/cron_tariff_collector.sh
```

Expected: `crontab -l` shows the same three lines

- [ ] **Step 3: Validate the wrapper syntax on the server**

Run:

```bash
ssh timeweb "bash -n /home/danila/projects/wookiee/services/logistics_audit/etl/cron_tariff_collector.sh"
```

Expected: no output, exit code `0`

- [ ] **Step 4: Run the wrapper once manually for a smoke test**

Run:

```bash
ssh timeweb "/home/danila/projects/wookiee/services/logistics_audit/etl/cron_tariff_collector.sh && tail -n 50 /home/danila/projects/wookiee/logs/wb_tariffs/\$(date +%F).log"
```

Expected:
- wrapper exits `0`
- today’s log file exists
- log contains start line, collector output, and finish line

- [ ] **Step 5: Confirm cron persistence**

Run:

```bash
ssh timeweb "crontab -l"
```

Expected: includes the `CRON_TZ=Europe/Moscow` line and the `0 8 * * *` WB tariffs entry

### Task 5: Final Operational Close-Out

**Files:**
- Review: `services/logistics_audit/README.md`
- Review: `README.md`

- [ ] **Step 1: Record the bootstrap result for handoff**

Capture:
- final `COUNT/MIN/MAX` from `public.wb_tariffs`
- whether any gap dates were skipped due to empty WB API responses
- the exact server user and `crontab -l` output fragment

Expected: one short rollout summary that proves database state and scheduler state

- [ ] **Step 2: Run the final local verification one more time after rollout**

Run:

```bash
python3 -m pytest -q tests/services/logistics_audit/test_api_parsing.py tests/services/logistics_audit/test_overpayment.py tests/services/logistics_audit/test_tariff_calibrator.py tests/services/logistics_audit/test_tariff_etl.py
```

Expected: `20 passed`
