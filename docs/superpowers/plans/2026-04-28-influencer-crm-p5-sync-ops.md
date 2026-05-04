# Influencer CRM Phase 5 — Sync & Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production-grade ops layer on top of the P1-P4 stack: scheduled MV refresh, weekly retention, scheduled Sheets→CRM sync (6h), tool_telemetry integration, and a lightweight ops dashboard. After P5 the system runs unattended; the human only watches the dashboard.

**Architecture:**
- **DB-side scheduling:** `pg_cron` extension on Supabase. Two new migrations (`010`, `011`) — one schedules `REFRESH MATERIALIZED VIEW CONCURRENTLY crm.v_blogger_totals` every 5 min, the other schedules weekly retention DELETEs.
- **App-side scheduling:** Add a cron line to the existing `wookiee-cron` container (`deploy/docker-compose.yml`) that runs `python -m services.sheets_etl.run --incremental` every 6h.
- **Telemetry:** Wrap the ETL run in `services.tool_telemetry.logger` `log_orchestrator_run` so each invocation appears in `agent_runs` (success/failure, duration, row counts).
- **Ops dashboard:** New `/ops` route on the BFF that returns a single JSON blob (last sync time + status, MV freshness, retention backlog counts, recent errors) — rendered by a tiny HTML page in the React app.
- **Cutover doc:** Markdown playbook in `docs/runbooks/` describing the Sheets→CRM swap (no auto-Notion post).

**Tech Stack:**
- Postgres 15 + `pg_cron` extension (Supabase managed)
- Python 3.11, psycopg, existing `services/sheets_etl/`, existing `services/tool_telemetry/`
- Docker (existing `wookiee-cron` container)
- FastAPI (existing `services/influencer_crm/`)

---

## File Structure

**Created:**
- `services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql` — schedule MV refresh
- `services/influencer_crm/migrations/011_retention_jobs.sql` — schedule retention DELETEs
- `services/sheets_etl/incremental.py` — hash-diff logic (only-changed-rows)
- `services/influencer_crm/routers/ops.py` — `/ops/health` endpoint
- `services/influencer_crm/schemas/ops.py` — `OpsHealth` pydantic model
- `services/influencer_crm/scripts/etl_runner.py` — CLI wrapper that logs to tool_telemetry
- `services/influencer_crm_ui/src/routes/ops/OpsPage.tsx` — minimal ops dashboard view
- `docs/runbooks/influencer-crm-cutover.md` — Sheets→CRM cutover playbook
- `tests/services/influencer_crm/test_ops_router.py`
- `tests/services/sheets_etl/test_incremental.py`

**Modified:**
- `services/sheets_etl/run.py` — add `--incremental` flag, route to `incremental.py`
- `services/influencer_crm/app.py` — register `ops` router
- `services/influencer_crm/deps.py` — expose db-pool dep for ops queries
- `deploy/docker-compose.yml` — add cron line to `wookiee-cron` for CRM ETL (every 6h)
- `services/influencer_crm_ui/src/routes/AppRoutes.tsx` — register `/ops` route + sidebar entry
- `services/influencer_crm_ui/src/api/ops.ts` — typed wrapper for `/ops/health`
- `services/influencer_crm_ui/src/hooks/use-ops.ts` — TanStack Query hook (refetch every 30s)

---

## Skill Map

- **Implementation:** `superpowers:subagent-driven-development`, `superpowers:test-driven-development`
- **DB:** `supabase:supabase-postgres-best-practices` for pg_cron syntax
- **Verification:** `superpowers:verification-before-completion`, `codex-quality-gate`
- **Telemetry registration:** `tool-register` (P5 wraps ETL as a tool)
- **Post-deploy:** `tool-status` (QA2 canary in T9)

---

## Task Decomposition

### Task 1: Migration 010 — pg_cron MV refresh

**Files:**
- Create: `services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql`

**Why concurrent:** the BFF reads `v_blogger_totals` constantly — a non-concurrent refresh would block reads. CONCURRENTLY requires the MV to have a unique index (it does — `blogger_id` is PK).

**SQL content:**

```sql
-- 010_pg_cron_mv_refresh.sql
-- Schedule v_blogger_totals refresh every 5 minutes via pg_cron.
-- Idempotent: drops the prior schedule if it exists, then inserts.

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Remove any previously-scheduled job with this name (re-run safety)
SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname = 'crm_v_blogger_totals_refresh';

SELECT cron.schedule(
    'crm_v_blogger_totals_refresh',
    '*/5 * * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY crm.v_blogger_totals$$
);

-- Verification query (run manually): SELECT * FROM cron.job WHERE jobname = 'crm_v_blogger_totals_refresh';
```

- [ ] **Step 1: Write the SQL migration file with the content above.**
- [ ] **Step 2: Apply via Supabase MCP** (`mcp__plugin_supabase_supabase__apply_migration`, name `010_pg_cron_mv_refresh`). If MCP not authenticated, document apply command in commit message and skip; the user runs `apply_migration` after auth.
- [ ] **Step 3: Verify schedule exists.** Run `SELECT jobname, schedule, command FROM cron.job WHERE jobname = 'crm_v_blogger_totals_refresh';` via MCP `execute_sql`. Expected: 1 row, schedule `*/5 * * * *`.
- [ ] **Step 4: Commit.**

```bash
git add services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql
git commit -m "feat(crm-ops): pg_cron schedule v_blogger_totals refresh every 5 min"
```

---

### Task 2: Migration 011 — Retention jobs

**Files:**
- Create: `services/influencer_crm/migrations/011_retention_jobs.sql`

**Retention rules (locked):**
- `crm.audit_log` — DELETE rows older than 90 days, weekly (Sun 03:00 UTC)
- `crm.integration_metrics_snapshots` — DELETE rows older than 365 days, weekly (Sun 03:15 UTC) — these are point-in-time snapshots, the MV holds current values

**Why these tables:** audit_log grows linearly (every PATCH writes a row); metrics snapshots are written by future poller. No retention on `bloggers`/`integrations` themselves — those are SoT.

**SQL content:**

```sql
-- 011_retention_jobs.sql
-- Weekly retention: delete stale audit + snapshot rows.

SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname IN ('crm_audit_log_retention', 'crm_metrics_snapshots_retention');

SELECT cron.schedule(
    'crm_audit_log_retention',
    '0 3 * * 0',
    $$DELETE FROM crm.audit_log WHERE created_at < now() - INTERVAL '90 days'$$
);

SELECT cron.schedule(
    'crm_metrics_snapshots_retention',
    '15 3 * * 0',
    $$DELETE FROM crm.integration_metrics_snapshots WHERE captured_at < now() - INTERVAL '365 days'$$
);
```

- [ ] **Step 1: Write the SQL file.**
- [ ] **Step 2: Verify the column names exist before applying.** Run `SELECT column_name FROM information_schema.columns WHERE table_schema='crm' AND table_name IN ('audit_log','integration_metrics_snapshots');`. If `created_at`/`captured_at` differ — adapt the SQL and document the actual column.
- [ ] **Step 3: Apply via Supabase MCP** (`apply_migration`, name `011_retention_jobs`).
- [ ] **Step 4: Verify both schedules registered** (`SELECT jobname, schedule FROM cron.job WHERE jobname LIKE 'crm_%retention';`). Expected: 2 rows.
- [ ] **Step 5: Commit.**

```bash
git add services/influencer_crm/migrations/011_retention_jobs.sql
git commit -m "feat(crm-ops): pg_cron weekly retention (audit_log 90d, snapshots 365d)"
```

---

### Task 3: Sheets ETL incremental mode

**Files:**
- Create: `services/sheets_etl/incremental.py`
- Create: `tests/services/sheets_etl/test_incremental.py`
- Modify: `services/sheets_etl/run.py` — add `--incremental` arg

**Goal:** Skip re-loading rows whose `sheet_row_id` (MD5 of source-row content) is already present in DB AND whose row content didn't change. Reduces 6h cron from full-import to delta-import. Existing `loader.upsert` is already idempotent at the row level — the win here is fewer `INSERT` round-trips, not correctness.

**Approach:** before each sheet, fetch the set of `sheet_row_id`s already in the target table, build the new transform rows, filter to only those whose `sheet_row_id` is missing OR whose content hash changed. Existing `hash.sheet_row_id()` is the content fingerprint.

**Code:**

```python
# services/sheets_etl/incremental.py
"""Incremental ETL helpers — filter transformed rows to only those needing upsert.

The full ETL (`run.py` without flags) processes all sheet rows every time.
For 6h-cadence cron we want to skip rows already present and unchanged.
We compare `sheet_row_id` (MD5 of source content) — same id = same content.
"""
from __future__ import annotations

from typing import Iterable


def existing_sheet_row_ids(conn, table: str) -> set[str]:
    """Return the set of sheet_row_id values currently in `table`.

    Caller passes a fully-qualified table name like 'crm.bloggers'.
    Returns empty set if table missing or empty.
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT sheet_row_id FROM {table} WHERE sheet_row_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def filter_new_rows(rows: Iterable[dict], existing: set[str]) -> list[dict]:
    """Return only rows whose `sheet_row_id` is NOT in `existing`.

    Rows without `sheet_row_id` (e.g., synthesized link rows) pass through
    unchanged — let the upsert dedup them on the natural conflict target.
    """
    return [r for r in rows if r.get("sheet_row_id") not in existing or "sheet_row_id" not in r]
```

**Test:**

```python
# tests/services/sheets_etl/test_incremental.py
from services.sheets_etl.incremental import filter_new_rows


def test_filter_new_rows_skips_existing():
    rows = [
        {"sheet_row_id": "a", "name": "x"},
        {"sheet_row_id": "b", "name": "y"},
        {"sheet_row_id": "c", "name": "z"},
    ]
    existing = {"a", "c"}
    out = filter_new_rows(rows, existing)
    assert out == [{"sheet_row_id": "b", "name": "y"}]


def test_filter_new_rows_passthrough_when_no_id():
    rows = [{"name": "no-id-row"}]
    existing = {"a"}
    assert filter_new_rows(rows, existing) == rows


def test_filter_new_rows_empty_existing():
    rows = [{"sheet_row_id": "a"}, {"sheet_row_id": "b"}]
    assert filter_new_rows(rows, set()) == rows
```

**run.py modification:**

```python
# Add to argparse:
parser.add_argument(
    "--incremental",
    action="store_true",
    help="Skip rows whose sheet_row_id is already present in the target table",
)

# In each run_X function (bloggers, integrations, etc.) — wrap the rows:
# Before:
#   rows = t_bloggers.transform(read_range(...))
#   n = upsert(conn, "crm.bloggers", rows)
# After:
#   rows = t_bloggers.transform(read_range(...))
#   if incremental:
#       existing = existing_sheet_row_ids(conn, "crm.bloggers")
#       rows = filter_new_rows(rows, existing)
#   n = upsert(conn, "crm.bloggers", rows)
```

- [ ] **Step 1: Write the failing test** (`tests/services/sheets_etl/test_incremental.py`).
- [ ] **Step 2: Run `pytest tests/services/sheets_etl/test_incremental.py -v` — expect 3 failures (module missing).**
- [ ] **Step 3: Implement `services/sheets_etl/incremental.py`.**
- [ ] **Step 4: Run pytest again — expect 3/3 pass.**
- [ ] **Step 5: Modify `run.py`** — add the flag, thread `incremental: bool` through each `run_X` function, wrap rows with `filter_new_rows` when set.
- [ ] **Step 6: Manual smoke** — run `python -m services.sheets_etl.run --incremental --sheet bloggers` against the test DB; verify second run logs "0 new rows" (or low count if anyone edited the sheet).
- [ ] **Step 7: Commit.**

```bash
git add services/sheets_etl/incremental.py services/sheets_etl/run.py tests/services/sheets_etl/test_incremental.py
git commit -m "feat(crm-etl): --incremental flag skips unchanged rows by sheet_row_id"
```

---

### Task 4: tool_telemetry-wrapped ETL runner

**Files:**
- Create: `services/influencer_crm/scripts/etl_runner.py`

**Goal:** A thin CLI wrapper that calls `services.sheets_etl.run.main(["--incremental"])` and reports the run to `tool_telemetry.agent_runs` (success/failure, duration, error message). The cron container invokes THIS wrapper, not raw `services.sheets_etl.run` directly.

**Why agent_runs (not a new table):** existing `tool_telemetry` already has the right schema — `agent_name`, `status`, `started_at`, `finished_at`, `duration_ms`, `error_message`. Treating "crm-sheets-etl" as a tool fits the registry model and reuses existing dashboards.

**Code:**

```python
# services/influencer_crm/scripts/etl_runner.py
"""Cron entrypoint for CRM Sheets→DB sync. Logs every run to tool_telemetry.

Usage:
    python -m services.influencer_crm.scripts.etl_runner [--full]

Default = --incremental. Pass --full to force full-import.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
from datetime import UTC, datetime

from services.sheets_etl import run as etl_run
from services.tool_telemetry.logger import log_agent_run, new_run_id


AGENT_NAME = "crm-sheets-etl"
AGENT_VERSION = "1.0.0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CRM Sheets ETL cron entrypoint")
    parser.add_argument("--full", action="store_true", help="Full re-import (default: incremental)")
    args = parser.parse_args(argv)

    run_id = new_run_id()
    started = datetime.now(UTC)
    t0 = time.monotonic()
    etl_argv = [] if args.full else ["--incremental"]

    status = "running"
    error = None
    exit_code = 0

    try:
        exit_code = etl_run.main(etl_argv)
        status = "success" if exit_code == 0 else "failed"
        if exit_code != 0:
            error = f"ETL exited non-zero: {exit_code}"
    except Exception as exc:  # noqa: BLE001 - top-level cron entrypoint
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
        exit_code = 1

    duration_ms = int((time.monotonic() - t0) * 1000)
    finished = datetime.now(UTC)

    asyncio.run(
        log_agent_run(
            run_id=run_id,
            agent_name=AGENT_NAME,
            agent_type="micro-agent",
            agent_version=AGENT_VERSION,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_ms=duration_ms,
            error_message=error,
        )
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1: Verify `log_agent_run` signature** — read `services/tool_telemetry/logger.py:275`. If signature differs from what's used above, adapt the call.
- [ ] **Step 2: Write the file.**
- [ ] **Step 3: Run smoke test** — `python -m services.influencer_crm.scripts.etl_runner --full` against test DB. Expect: ETL runs, exit 0, then check `SELECT * FROM agent_runs WHERE agent_name='crm-sheets-etl' ORDER BY started_at DESC LIMIT 1;` shows the run.
- [ ] **Step 4: Test failure path** — temporarily break the SUPABASE_HOST env var, re-run, expect: status='failed' with error_message in DB.
- [ ] **Step 5: Commit.**

```bash
git add services/influencer_crm/scripts/etl_runner.py
git commit -m "feat(crm-ops): tool_telemetry-wrapped ETL runner (agent_name=crm-sheets-etl)"
```

---

### Task 5: Cron container — add CRM ETL line

**Files:**
- Modify: `deploy/docker-compose.yml` — add the cron line

**Goal:** Hook `etl_runner` into the existing `wookiee-cron` container at every 6h (00:00, 06:00, 12:00, 18:00 Moscow time = `0 */6 * * *`).

**Change:**

```yaml
# In services.wookiee-cron.command — append a 4th cron line
command:
  - |
    (echo "PATH=/usr/local/bin:/usr/bin:/bin"; \
     echo "PYTHONPATH=/app"; \
     echo "0 10 * * 1 cd /app && python scripts/run_search_queries_sync.py >> /proc/1/fd/1 2>&1"; \
     echo "0 6 * * * cd /app && python scripts/sync_sheets_to_supabase.py --level all >> /proc/1/fd/1 2>&1"; \
     echo "0 */6 * * * cd /app && python -m services.influencer_crm.scripts.etl_runner >> /proc/1/fd/1 2>&1") | crontab -
    echo "Wookiee cron installed: search queries Mon 10:00 + sheets sync 06:00 + CRM ETL every 6h"
    cron -f
```

- [ ] **Step 1: Read the current `deploy/docker-compose.yml`** to confirm the exact format.
- [ ] **Step 2: Apply the modification — add the new cron line + update the echo banner.**
- [ ] **Step 3: Validate YAML** — `python -c "import yaml; yaml.safe_load(open('deploy/docker-compose.yml'))"`. Expect: no error.
- [ ] **Step 4: Document the deploy step** (commit message): "after deploy, the new cron line takes effect on next container restart — `docker compose up -d wookiee-cron` on the app server".
- [ ] **Step 5: Commit.**

```bash
git add deploy/docker-compose.yml
git commit -m "feat(crm-ops): schedule CRM Sheets ETL every 6h in wookiee-cron"
```

---

### Task 6: Ops health endpoint

**Files:**
- Create: `services/influencer_crm/schemas/ops.py`
- Create: `services/influencer_crm/routers/ops.py`
- Create: `tests/services/influencer_crm/test_ops_router.py`
- Modify: `services/influencer_crm/app.py` — register router

**Endpoint:** `GET /ops/health` → returns:

```json
{
  "etl_last_run": {
    "started_at": "2026-04-28T12:00:00Z",
    "status": "success",
    "duration_ms": 18743,
    "error_message": null
  },
  "etl_last_24h": { "success": 4, "failed": 0 },
  "mv_age_seconds": 142,
  "retention": {
    "audit_log_eligible_for_delete": 1234,
    "snapshots_eligible_for_delete": 0
  },
  "cron_jobs": [
    { "jobname": "crm_v_blogger_totals_refresh", "schedule": "*/5 * * * *", "active": true },
    { "jobname": "crm_audit_log_retention", "schedule": "0 3 * * 0", "active": true },
    { "jobname": "crm_metrics_snapshots_retention", "schedule": "15 3 * * 0", "active": true }
  ]
}
```

**Why these fields:** the human watches 4 things — "did ETL run recently?", "is the MV fresh?", "is retention scheduled?", "any failures in last day?". Anything more is noise.

**Schema:**

```python
# services/influencer_crm/schemas/ops.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EtlLastRun(BaseModel):
    started_at: Optional[datetime] = None
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None


class EtlCounts(BaseModel):
    success: int = 0
    failed: int = 0


class CronJobInfo(BaseModel):
    jobname: str
    schedule: str
    active: bool


class RetentionCounts(BaseModel):
    audit_log_eligible_for_delete: int = 0
    snapshots_eligible_for_delete: int = 0


class OpsHealth(BaseModel):
    etl_last_run: EtlLastRun
    etl_last_24h: EtlCounts
    mv_age_seconds: Optional[int] = None
    retention: RetentionCounts
    cron_jobs: list[CronJobInfo]
```

**Router:**

```python
# services/influencer_crm/routers/ops.py
"""Ops health endpoint — single source of truth for the dashboard.

Read-only. Reads from agent_runs, cron.job, and crm.* retention sources.
No auth beyond the X-API-Key gate the rest of the BFF uses.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from services.influencer_crm.deps import get_db
from services.influencer_crm.schemas.ops import (
    CronJobInfo,
    EtlCounts,
    EtlLastRun,
    OpsHealth,
    RetentionCounts,
)


router = APIRouter(prefix="/ops", tags=["ops"])

ETL_AGENT_NAME = "crm-sheets-etl"


@router.get("/health", response_model=OpsHealth)
def get_health(db = Depends(get_db)) -> OpsHealth:
    last_run_row = db.execute(
        text(
            """
            SELECT started_at, status, duration_ms, error_message
            FROM agent_runs
            WHERE agent_name = :name
            ORDER BY started_at DESC
            LIMIT 1
            """
        ),
        {"name": ETL_AGENT_NAME},
    ).first()
    last_run = (
        EtlLastRun(
            started_at=last_run_row.started_at,
            status=last_run_row.status,
            duration_ms=last_run_row.duration_ms,
            error_message=last_run_row.error_message,
        )
        if last_run_row
        else EtlLastRun()
    )

    counts_row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE status='success') AS ok,
                COUNT(*) FILTER (WHERE status='failed') AS failed
            FROM agent_runs
            WHERE agent_name = :name AND started_at > now() - INTERVAL '24 hours'
            """
        ),
        {"name": ETL_AGENT_NAME},
    ).first()
    counts = EtlCounts(success=counts_row.ok or 0, failed=counts_row.failed or 0)

    mv_age_row = db.execute(
        text(
            """
            SELECT EXTRACT(EPOCH FROM (now() - GREATEST(MAX(refreshed_at), now() - INTERVAL '1 day')))::int AS age
            FROM pg_stat_user_tables
            WHERE schemaname='crm' AND relname='v_blogger_totals'
            """
        )
    ).first()
    mv_age = int(mv_age_row.age) if mv_age_row and mv_age_row.age is not None else None

    retention_row = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM crm.audit_log
                  WHERE created_at < now() - INTERVAL '90 days') AS audit_count,
                (SELECT COUNT(*) FROM crm.integration_metrics_snapshots
                  WHERE captured_at < now() - INTERVAL '365 days') AS snap_count
            """
        )
    ).first()
    retention = RetentionCounts(
        audit_log_eligible_for_delete=retention_row.audit_count or 0,
        snapshots_eligible_for_delete=retention_row.snap_count or 0,
    )

    cron_rows = db.execute(
        text(
            """
            SELECT jobname, schedule, active
            FROM cron.job
            WHERE jobname LIKE 'crm_%'
            ORDER BY jobname
            """
        )
    ).all()
    cron_jobs = [
        CronJobInfo(jobname=r.jobname, schedule=r.schedule, active=r.active)
        for r in cron_rows
    ]

    return OpsHealth(
        etl_last_run=last_run,
        etl_last_24h=counts,
        mv_age_seconds=mv_age,
        retention=retention,
        cron_jobs=cron_jobs,
    )
```

**Note on `mv_age`:** the simple proxy above (pg_stat_user_tables) is good enough as a freshness signal — exact "last refresh" needs another approach (e.g. an `updated_at` row written by the cron job). If the proxy is too imprecise during testing, fall back to `(SELECT now()::int)` and document a follow-up.

**Test (httpx mock-style):**

```python
# tests/services/influencer_crm/test_ops_router.py
from fastapi.testclient import TestClient

from services.influencer_crm.app import app


def test_ops_health_shape(client: TestClient, api_key_header):
    r = client.get("/ops/health", headers=api_key_header)
    assert r.status_code == 200
    body = r.json()
    assert "etl_last_run" in body
    assert "etl_last_24h" in body
    assert "retention" in body
    assert "cron_jobs" in body
    assert isinstance(body["cron_jobs"], list)


def test_ops_health_requires_api_key(client: TestClient):
    r = client.get("/ops/health")
    assert r.status_code == 403
```

- [ ] **Step 1: Write `schemas/ops.py`.**
- [ ] **Step 2: Read `deps.py:get_db`** — confirm it exists and the type-hint pattern. If db is async, switch the router to `async def` + `await`.
- [ ] **Step 3: Write `routers/ops.py`.**
- [ ] **Step 4: Register the router** in `app.py` (`app.include_router(ops.router)`).
- [ ] **Step 5: Write the test file using existing test fixtures** (look at `tests/services/influencer_crm/conftest.py` for `client` + `api_key_header`).
- [ ] **Step 6: Run `pytest tests/services/influencer_crm/test_ops_router.py -v` — expect both tests pass against live Supabase.**
- [ ] **Step 7: Hit `curl -H "X-API-Key: $CRM_API_KEY" http://localhost:8000/ops/health | jq` — sanity-check the JSON shape.**
- [ ] **Step 8: Commit.**

```bash
git add services/influencer_crm/schemas/ops.py services/influencer_crm/routers/ops.py services/influencer_crm/app.py tests/services/influencer_crm/test_ops_router.py
git commit -m "feat(crm-ops): /ops/health endpoint (etl status + cron + retention queue)"
```

---

### Task 7: Ops dashboard page (frontend)

**Files:**
- Create: `services/influencer_crm_ui/src/api/ops.ts`
- Create: `services/influencer_crm_ui/src/hooks/use-ops.ts`
- Create: `services/influencer_crm_ui/src/routes/ops/OpsPage.tsx`
- Modify: `services/influencer_crm_ui/src/routes/AppRoutes.tsx` — register `/ops`
- Modify: `services/influencer_crm_ui/src/layout/Sidebar.tsx` — add nav entry

**Layout (single screen, no over-design):**
- Top: 3 KpiCards — "ETL: last run", "MV freshness", "Failures (24h)"
- Middle: cron job table (4 cols: jobname, schedule, active, status indicator dot)
- Bottom: retention queue (2 numbers, plain text)
- Auto-refresh every 30s via TanStack Query.

**API wrapper:**

```typescript
// src/api/ops.ts
import { apiGet } from '@/lib/api';

export interface OpsHealth {
  etl_last_run: {
    started_at: string | null;
    status: string | null;
    duration_ms: number | null;
    error_message: string | null;
  };
  etl_last_24h: { success: number; failed: number };
  mv_age_seconds: number | null;
  retention: {
    audit_log_eligible_for_delete: number;
    snapshots_eligible_for_delete: number;
  };
  cron_jobs: Array<{ jobname: string; schedule: string; active: boolean }>;
}

export const fetchOpsHealth = () => apiGet<OpsHealth>('/ops/health');
```

**Hook:**

```typescript
// src/hooks/use-ops.ts
import { useQuery } from '@tanstack/react-query';
import { fetchOpsHealth } from '@/api/ops';

export function useOpsHealth() {
  return useQuery({
    queryKey: ['ops', 'health'],
    queryFn: fetchOpsHealth,
    refetchInterval: 30_000,
  });
}
```

**Page (concise — no inline screenshots, just shadcn-style primitives):**

```tsx
// src/routes/ops/OpsPage.tsx
import { useOpsHealth } from '@/hooks/use-ops';
import { PageHeader } from '@/layout/PageHeader';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { KpiCard } from '@/ui/KpiCard';
import { Badge } from '@/ui/Badge';
import { formatDate } from '@/lib/format';

function formatAge(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds} с`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} мин`;
  return `${Math.round(seconds / 3600)} ч`;
}

export function OpsPage() {
  const { data, isLoading, error } = useOpsHealth();

  return (
    <>
      <PageHeader
        title="Ops"
        sub="Состояние синхронизаций и расписаний CRM."
      />
      <QueryStatusBoundary isLoading={isLoading} error={error} isEmpty={!data}>
        {data && (
          <div className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <KpiCard
                label="ETL — последний запуск"
                value={
                  data.etl_last_run.started_at
                    ? formatDate(data.etl_last_run.started_at)
                    : '—'
                }
                hint={data.etl_last_run.status ?? 'нет данных'}
              />
              <KpiCard
                label="Свежесть MV"
                value={formatAge(data.mv_age_seconds)}
                hint="v_blogger_totals"
              />
              <KpiCard
                label="Сбои за 24ч"
                value={`${data.etl_last_24h.failed}`}
                hint={`успешно: ${data.etl_last_24h.success}`}
              />
            </div>

            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-semibold mb-3">Cron-задачи</h2>
              <table className="w-full text-sm">
                <thead className="text-xs text-muted-fg uppercase">
                  <tr>
                    <th className="text-left py-1">Задача</th>
                    <th className="text-left py-1">Расписание</th>
                    <th className="text-left py-1">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cron_jobs.map((j) => (
                    <tr key={j.jobname} className="border-t border-border-strong">
                      <td className="py-2 font-mono">{j.jobname}</td>
                      <td className="py-2 font-mono">{j.schedule}</td>
                      <td className="py-2">
                        <Badge tone={j.active ? 'success' : 'muted'}>
                          {j.active ? 'активна' : 'выключена'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-semibold mb-2">Очередь retention</h2>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-muted-fg text-xs">audit_log &gt; 90 дн.</dt>
                  <dd className="font-mono text-base">
                    {data.retention.audit_log_eligible_for_delete}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-fg text-xs">snapshots &gt; 365 дн.</dt>
                  <dd className="font-mono text-base">
                    {data.retention.snapshots_eligible_for_delete}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        )}
      </QueryStatusBoundary>
    </>
  );
}

export default OpsPage;
```

**AppRoutes.tsx + Sidebar:**

```tsx
// AppRoutes.tsx — add inside <Routes>:
<Route path="/ops" element={<OpsPage />} />

// Sidebar.tsx — add to nav array:
{ to: '/ops', label: 'Ops', icon: ActivityIcon }
```

(Use `ActivityIcon` or `GaugeIcon` from `lucide-react` — pick whichever the existing `Sidebar` already imports a sibling of.)

- [ ] **Step 1: Write `api/ops.ts`** + matching test in `src/api/ops.test.ts` if the existing API wrappers have tests.
- [ ] **Step 2: Write the hook.**
- [ ] **Step 3: Write `OpsPage.tsx`.**
- [ ] **Step 4: Register the route + sidebar nav entry.**
- [ ] **Step 5: Run `pnpm dev` and visit `/ops`** with the BFF running locally — confirm the page renders, all 3 KpiCards filled, cron table populated.
- [ ] **Step 6: Run `pnpm test` and `pnpm build`** — expect all green.
- [ ] **Step 7: Commit.**

```bash
git add services/influencer_crm_ui/src/api/ops.ts services/influencer_crm_ui/src/hooks/use-ops.ts services/influencer_crm_ui/src/routes/ops/OpsPage.tsx services/influencer_crm_ui/src/routes/AppRoutes.tsx services/influencer_crm_ui/src/layout/Sidebar.tsx
git commit -m "feat(crm-ui): /ops dashboard (ETL status + cron table + retention queue)"
```

---

### Task 8: Cutover runbook

**Files:**
- Create: `docs/runbooks/influencer-crm-cutover.md`

**Goal:** A short, follow-along playbook describing the steps to swap the team off Sheets and onto the CRM. No automation — human reads, executes, marks. Sections:

1. Pre-cutover checks (8 items — green dashboards, ETL incremental clean, no failed runs in 48h)
2. Cutover sequence (1) Freeze Sheets writes (announce in chat); 2) Run final ETL `--full`; 3) Diff Sheets vs DB counts; 4) Flip the team to UI; 5) Mark Sheets header "READ-ONLY")
3. Rollback plan (re-enable Sheets writes, freeze CRM writes, no data loss because Sheets is unchanged until step 5)
4. Day-1 monitoring (what to watch in `/ops`, what's "normal")

**This task = pure markdown. No code, no tests.**

- [ ] **Step 1: Write the runbook (~120-200 lines).**
- [ ] **Step 2: Cross-link from `docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md`** § Phase 5 line 286 ("Lightweight ops dashboard") to point to this runbook.
- [ ] **Step 3: Commit.**

```bash
git add docs/runbooks/influencer-crm-cutover.md docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md
git commit -m "docs(crm-ops): cutover runbook (Sheets → CRM swap playbook)"
```

---

### Task 9: P5 verification — green-light gate

**Files:**
- Read: all P5 artifacts above
- Create: `docs/superpowers/plans/2026-04-28-influencer-crm-p5-verification.md`

**Goal:** Self-verification report that confirms each P5 deliverable lands. Not a test suite — a checklist with concrete evidence.

**Checks:**

1. `cron.job` query shows 3 active CRM cron rows (`crm_v_blogger_totals_refresh`, `crm_audit_log_retention`, `crm_metrics_snapshots_retention`).
2. Manual `python -m services.influencer_crm.scripts.etl_runner --full` returns exit 0 + writes a row in `agent_runs` with `agent_name='crm-sheets-etl'`, status='success'.
3. Manual `python -m services.influencer_crm.scripts.etl_runner` (default = incremental) on a quiet DB shows "0 new rows" per sheet (or near-zero) — proves incremental works.
4. `curl /ops/health` returns valid `OpsHealth` JSON with all 4 sections.
5. `pytest tests/services/sheets_etl/test_incremental.py tests/services/influencer_crm/test_ops_router.py -v` → all green.
6. `services/influencer_crm_ui/` `pnpm build` clean; `/ops` page renders with the BFF running.
7. `deploy/docker-compose.yml` validates as YAML (`python -c "import yaml; yaml.safe_load(open('deploy/docker-compose.yml'))"`).
8. Cutover runbook exists at `docs/runbooks/influencer-crm-cutover.md`.

- [ ] **Step 1: Run each check above and record the result in the verification doc.**
- [ ] **Step 2: For any FAILED check — open a follow-up entry in `docs/superpowers/plans/2026-04-28-influencer-crm-p5-followups.md` rather than blocking the merge.** Record root cause + planned fix date.
- [ ] **Step 3: Commit.**

```bash
git add docs/superpowers/plans/2026-04-28-influencer-crm-p5-verification.md
git commit -m "docs(crm-ops): P5 verification report (checklist + evidence)"
```

---

## Self-Review

**Spec coverage:**
- pg_cron MV refresh ↔ T1 ✅
- pg_cron retention ↔ T2 ✅
- sheets cron 6h ↔ T5 ✅
- `--incremental` ↔ T3 ✅
- tool_telemetry integration ↔ T4 ✅
- Lightweight ops dashboard ↔ T6+T7 ✅
- Notion entry on cutover ↔ T8 (markdown runbook, no auto-post) ✅
- Verification gate ↔ T9 ✅

**Placeholder scan:** none.

**Type consistency:** `OpsHealth` shape lines up across `schemas/ops.py`, `api/ops.ts`, and `OpsPage.tsx`.

**Out of scope (deferred):**
- QA2 canary (24h post-deploy monitoring) — runs after the deploy, not as part of this plan.
- Promoting the dashboard to a real-time websocket feed — overkill for current load.
- Notion auto-post of the runbook — needs the Notion writeback agent we don't have.
- Per-sheet incremental tracking with separate `etl_state` table — current `sheet_row_id` filter is enough for the 6h cadence.

---

## Execution Notes

- All 9 tasks are independent enough that subagents can execute T1→T9 sequentially without conflicts (T6 needs T4 done; T7 needs T6 done; T9 needs all prior).
- Apply migrations 010/011 via Supabase MCP (`apply_migration`). If the agent's MCP isn't authenticated, write the SQL file and skip apply — leave a TODO in commit msg for the user to apply manually.
- The cron container reload is a deploy-time action — out of scope for the plan, just commit the YAML.
