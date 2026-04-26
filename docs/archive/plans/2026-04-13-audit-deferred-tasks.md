# Audit Deferred Tasks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete 5 remaining tasks from the 2026-04-11 database audit: delete 28 legacy models, add sync cron, add retention cron, fix artikuly idempotent bug, decide on observability tables.

**Architecture:** 5 independent tasks. Task A = DB cleanup. Task B = add sync to existing docker cron. Task C = add retention SQL to same cron. Task D = fix INSERT → UPSERT in sync_artikuly. Task E = remove dead writes from logger.

**Key context:**
- Supabase connection: env vars from `.env` (SUPABASE_HOST, SUPABASE_PORT, SUPABASE_DB, SUPABASE_USER, SUPABASE_PASSWORD)
- Sync script: `scripts/sync_sheets_to_supabase.py`
- Docker cron: `deploy/docker-compose.yml` (wookiee-oleg service, crontab in command)
- Logger: `services/observability/logger.py`
- Server: Timeweb (77.233.212.61), `ssh timeweb`, deploy via `docker-compose up -d`

---

## Task A: Delete 28 legacy models with Russian names

**Purpose:** 28 models created by the old col-C bug still exist. All have 0 artikuly, 0 tovary. 25 of 28 have correct short-code counterparts already (e.g., "Nancy кружевные слипы" id=62 → "Nancy" id=63).

**Files:**
- Create: `scripts/audit_remediation/delete_legacy_models.py`

- [ ] **Step 1: Write cleanup script**

```python
"""Delete 28 legacy models with Russian descriptive names (0 artikuly each).

These were created by the old sync bug (col C instead of col A).
Most have correct short-code counterparts already created by the fixed sync.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

LEGACY_IDS = [
    57, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88,
    90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 112, 113,
]


def get_conn():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    deleted = 0
    skipped = 0
    for mid in LEGACY_IDS:
        # Safety: verify 0 artikuly
        cur.execute("SELECT COUNT(*) FROM artikuly WHERE model_id = %s", (mid,))
        art_count = cur.fetchone()[0]
        if art_count > 0:
            cur.execute("SELECT kod FROM modeli WHERE id = %s", (mid,))
            row = cur.fetchone()
            kod = row[0] if row else "?"
            print(f"  SKIP id={mid} ({kod}) — {art_count} artikuly!")
            skipped += 1
            continue

        cur.execute("DELETE FROM modeli WHERE id = %s RETURNING kod", (mid,))
        row = cur.fetchone()
        if row:
            print(f"  ✓ Deleted id={mid} ({row[0]})")
            deleted += 1
        else:
            print(f"  - id={mid} not found (already deleted?)")

    conn.commit()
    conn.close()
    print(f"\nDeleted {deleted}, skipped {skipped} (of {len(LEGACY_IDS)} targeted)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run script**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/audit_remediation/delete_legacy_models.py
```

Expected: "Deleted 28, skipped 0"

- [ ] **Step 3: Verify**

```bash
python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host=os.getenv('SUPABASE_HOST'),port=int(os.getenv('SUPABASE_PORT','5432')),database=os.getenv('SUPABASE_DB','postgres'),user=os.getenv('SUPABASE_USER'),password=os.getenv('SUPABASE_PASSWORD'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM modeli')
print('Total modeli:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM modeli WHERE model_osnova_id IS NULL')
print('NULL osnova:', cur.fetchone()[0])
conn.close()
"
```

Expected: Total ~75, NULL osnova = 0

- [ ] **Step 4: Commit**

```bash
git add scripts/audit_remediation/delete_legacy_models.py
git commit -m "fix(pim): delete 28 legacy models with Russian names (0 artikuly, col-C bug remnants)"
```

---

## Task B: Add sync cron to docker-compose

**Purpose:** Sync Sheet → Supabase currently runs only manually. Add a daily cron at 06:00 MSK so new models/products sync automatically.

**Files:**
- Modify: `deploy/docker-compose.yml:11-12` (crontab command in wookiee-oleg service)

- [ ] **Step 1: Read current crontab line**

Current crontab in `deploy/docker-compose.yml` line 12:
```
(echo "PATH=/usr/local/bin:/usr/bin:/bin"; echo "PYTHONPATH=/app"; echo "*/30 7-18 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1"; echo "0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1") | crontab -
```

- [ ] **Step 2: Add sync cron line**

Add after the search_queries line:
```
echo "0 6 * * * cd /app && python scripts/sync_sheets_to_supabase.py --level all >> /proc/1/fd/1 2>&1"
```

The full command block becomes:
```bash
(echo "PATH=/usr/local/bin:/usr/bin:/bin"; echo "PYTHONPATH=/app"; echo "*/30 7-18 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1"; echo "0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1"; echo "0 6 * * * cd /app && python scripts/sync_sheets_to_supabase.py --level all >> /proc/1/fd/1 2>&1") | crontab -
```

Update the echo message too:
```
echo "Wookiee cron installed: reports every 30 min 07-18, search queries Mon 10:00, sheet sync daily 06:00"
```

- [ ] **Step 3: Verify syntax**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "
# Validate crontab syntax
lines = [
    '*/30 7-18 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1',
    '0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1',
    '0 6 * * * cd /app && python scripts/sync_sheets_to_supabase.py --level all >> /proc/1/fd/1 2>&1',
]
for l in lines:
    parts = l.split()
    print(f'{parts[0]:>5} {parts[1]:>5} {parts[2]:>3} {parts[3]:>3} {parts[4]:>3} | {\" \".join(parts[5:8])}...')
print('All 3 cron lines valid')
"
```

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "feat(infra): add daily Sheet→Supabase sync cron at 06:00 MSK"
```

- [ ] **Step 5: Deploy (requires ssh timeweb)**

```bash
ssh timeweb "cd /opt/wookiee && git pull && docker-compose -f deploy/docker-compose.yml up -d wookiee-oleg"
```

---

## Task C: Add retention cron for istoriya_izmeneniy

**Purpose:** Audit log table grows indefinitely (4304 rows in 2 months). Add a weekly cleanup that deletes records older than 180 days.

**Files:**
- Modify: `deploy/docker-compose.yml:11-12` (add one more crontab line)

- [ ] **Step 1: Create retention script**

Create `scripts/retention_cleanup.py`:

```python
"""Delete old records from istoriya_izmeneniy (180-day retention)."""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = psycopg2.connect(
        host=os.getenv("SUPABASE_HOST"),
        port=int(os.getenv("SUPABASE_PORT", "5432")),
        database=os.getenv("SUPABASE_DB", "postgres"),
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
    )
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM istoriya_izmeneniy
        WHERE data_izmeneniya < now() - interval '180 days'
    """)
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    print(f"Retention cleanup: deleted {deleted} records older than 180 days")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add to docker crontab**

Add to the crontab block in `deploy/docker-compose.yml`:
```
echo "0 5 * * 0 cd /app && python scripts/retention_cleanup.py >> /proc/1/fd/1 2>&1"
```

This runs every Sunday at 05:00 MSK (before the 06:00 sync).

- [ ] **Step 3: Commit**

```bash
git add scripts/retention_cleanup.py deploy/docker-compose.yml
git commit -m "feat(infra): add 180-day retention cron for istoriya_izmeneniy (weekly Sun 05:00)"
```

---

## Task D: Fix artikuly idempotent re-run bug

**Purpose:** `sync_artikuly()` uses bare INSERT for new records, causing unique constraint errors on re-run. Fix by adding ON CONFLICT handling.

**Files:**
- Modify: `scripts/sync_sheets_to_supabase.py:727-734`

- [ ] **Step 1: Read the current INSERT block**

Current code at lines 727-734:
```python
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO artikuly (artikul, model_id, cvet_id, status_id, nomenklatura_wb, artikul_ozon)
                           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                        (data["artikul_raw"], model_id, cvet_id, status_id,
                         data["nomenklatura_wb"], data["artikul_ozon"]),
                    )
                    art_map[key] = cur.fetchone()[0]
                conn.commit()
```

The issue: if the artikul already exists in DB but wasn't loaded into `existing_by_key` (e.g., race condition or data mismatch), the INSERT fails with `duplicate key value violates unique constraint "artikuly_artikul_key"`.

- [ ] **Step 2: Fix — use INSERT ... ON CONFLICT**

Replace lines 727-734 with:
```python
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO artikuly (artikul, model_id, cvet_id, status_id, nomenklatura_wb, artikul_ozon)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (artikul) DO UPDATE SET
                               model_id = COALESCE(EXCLUDED.model_id, artikuly.model_id),
                               cvet_id = COALESCE(EXCLUDED.cvet_id, artikuly.cvet_id),
                               status_id = COALESCE(EXCLUDED.status_id, artikuly.status_id),
                               nomenklatura_wb = COALESCE(EXCLUDED.nomenklatura_wb, artikuly.nomenklatura_wb),
                               artikul_ozon = COALESCE(EXCLUDED.artikul_ozon, artikuly.artikul_ozon),
                               updated_at = NOW()
                           RETURNING id""",
                        (data["artikul_raw"], model_id, cvet_id, status_id,
                         data["nomenklatura_wb"], data["artikul_ozon"]),
                    )
                    art_map[key] = cur.fetchone()[0]
                conn.commit()
```

- [ ] **Step 3: Test idempotent run**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/sync_sheets_to_supabase.py --level artikuly --dry-run
```

Then run twice (without dry-run) to verify no errors:
```bash
python scripts/sync_sheets_to_supabase.py --level artikuly
python scripts/sync_sheets_to_supabase.py --level artikuly
```

Expected: both runs succeed, second run shows 0 inserts.

- [ ] **Step 4: Commit**

```bash
git add scripts/sync_sheets_to_supabase.py
git commit -m "fix(sync): use ON CONFLICT for artikuly INSERT — enables safe re-runs"
```

---

## Task E: Remove dead observability writes

**Purpose:** `agent_runs` and `orchestrator_runs` are written to by `logger.py` but never read. Stop writing to save DB resources and simplify code. Tables remain in `infra` schema (data preserved).

**Files:**
- Modify: `services/observability/logger.py:300-350` (comment out or remove fire-and-forget inserts)

- [ ] **Step 1: Read logger.py to identify the write functions**

Two functions:
- `log_agent_run()` (line ~300) — fire-and-forget insert to agent_runs
- `log_orchestrator_run()` (line ~350) — fire-and-forget insert to orchestrator_runs

Both are async, called with `asyncio.create_task()` from various agents.

- [ ] **Step 2: Make the functions no-op**

Replace the body of both functions with early return + deprecation log:

For `log_agent_run()` (~line 300):
```python
async def log_agent_run(...) -> None:
    """Deprecated: agent_runs table is no longer actively used.
    
    Writes were disabled 2026-04-13 (audit remediation).
    Table preserved in infra schema for historical data.
    """
    return
```

For `log_orchestrator_run()` (~line 350):
```python
async def log_orchestrator_run(...) -> None:
    """Deprecated: orchestrator_runs table is no longer actively used.
    
    Writes were disabled 2026-04-13 (audit remediation).
    Table preserved in infra schema for historical data.
    """
    return
```

Keep the function signatures intact so callers don't break. Just return immediately.

- [ ] **Step 3: Verify no import errors**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from services.observability.logger import log_agent_run, log_orchestrator_run; print('Import OK')"
```

Expected: "Import OK"

- [ ] **Step 4: Commit**

```bash
git add services/observability/logger.py
git commit -m "chore(observability): disable writes to agent_runs/orchestrator_runs (never read)

Tables preserved in infra schema for historical data.
Functions kept as no-ops to avoid breaking callers."
```

---

## Execution Order

```
Independent — can run in any order or parallel:

  Task A: Delete 28 legacy models (5 min)
  Task D: Fix artikuly idempotent bug (15 min)
  Task E: Disable dead observability writes (10 min)

Sequential — B before C:

  Task B: Add sync cron to docker (15 min)
  Task C: Add retention cron (10 min) — same file, depends on B
```

**Total: ~55 min across 5 tasks.**

**Deploy note:** Tasks B+C require `ssh timeweb` + `docker-compose up -d` to activate crons on the server. Tasks A, D, E take effect immediately (DB + code changes).
