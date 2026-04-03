---
phase: 04-scheduling-delivery
plan: 02
subsystem: infra
tags: [docker, cron, cleanup, dockerfile, docker-compose]

# Dependency graph
requires:
  - phase: 04-01
    provides: "scripts/run_report.py — unified runner with --schedule mode"
provides:
  - "deploy/Dockerfile — no v3 refs, cron pre-installed, neutral CMD"
  - "deploy/docker-compose.yml — wookiee-oleg runs cron every 30 min 07:00-18:00 MSK, no finolog-cron"
affects: [cron-deployment, docker-infrastructure]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cron inside container: cron pre-installed in Dockerfile, configured via crontab in entrypoint"
    - "Docker logs routing: cron output >> /proc/1/fd/1 2>&1 routes to docker logs"
    - "TZ=Europe/Moscow already set in environment — cron window 7-18 matches MSK 07:00-18:00"

key-files:
  created: []
  modified:
    - deploy/Dockerfile
    - deploy/docker-compose.yml
  deleted:
    - scripts/run_oleg_v2_reports.py
    - scripts/run_oleg_v2_single.py
    - scripts/run_finolog_weekly.py

key-decisions:
  - "CMD in Dockerfile is python --version (neutral fallback) — each service overrides via compose command/entrypoint"
  - "cron installed in Dockerfile (not entrypoint) — no apt-get at container start, clean startup"
  - "finolog-cron service removed entirely (not just disabled) — V3 dependency gone, FINOLOG_WEEKLY now runs via wookiee-oleg cron"
  - "Cron window 7-18 per D-05: last trigger at 18:00 enables is_final_window (hour>=17, minute>=55)"

# Metrics
duration: 1min
completed: 2026-04-01
---

# Phase 4 Plan 02: Docker Infrastructure Update Summary

**Dockerfile with cron pre-installed, wookiee-oleg entrypoint runs run_report.py --schedule every 30 min 07:00-18:00 MSK, finolog-cron service removed, 3 dead scripts deleted**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-01T13:21:21Z
- **Completed:** 2026-04-01T13:22:39Z
- **Tasks:** 2
- **Files modified:** 2
- **Files deleted:** 3

## Accomplishments

- Updated `deploy/Dockerfile`: removed all `agents/v3` references, added `cron` to apt-get system dependencies, changed CMD from `agents.v3` to neutral `python --version`
- Updated `deploy/docker-compose.yml`: replaced wookiee-oleg `command: ["python", "-m", "agents.oleg"]` with cron-based entrypoint executing `run_report.py --schedule` every 30 minutes in the 07:00-18:00 MSK window (7-18), output redirected to Docker logs via `/proc/1/fd/1`
- Removed entire `finolog-cron` service block from docker-compose.yml (was disabled with profiles, now fully gone)
- Deleted 3 stale runner scripts: `run_oleg_v2_reports.py`, `run_oleg_v2_single.py`, `run_finolog_weekly.py`
- Verified 24 runner unit tests still pass after cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Update Dockerfile** - `ed517fa` (chore)
2. **Task 2: Update docker-compose.yml + delete old scripts** - `0d741ef` (chore)

## Files Modified/Deleted

- `deploy/Dockerfile` — removed v3 COPY/pip/mkdir refs, added cron to apt-get, neutral CMD
- `deploy/docker-compose.yml` — wookiee-oleg cron entrypoint, finolog-cron service removed
- `scripts/run_oleg_v2_reports.py` — DELETED (replaced by scripts/run_report.py)
- `scripts/run_oleg_v2_single.py` — DELETED (replaced by scripts/run_report.py --type)
- `scripts/run_finolog_weekly.py` — DELETED (broken V3 import; FINOLOG_WEEKLY now runs via wookiee-oleg cron)

## Decisions Made

- **Neutral CMD**: `CMD ["python", "--version"]` as Dockerfile default — each service in docker-compose sets its own command/entrypoint. Avoids misleading default that references deleted module.
- **cron in Dockerfile**: Pre-installing cron in the image (not in entrypoint apt-get) keeps container startup clean and fast. The finolog-cron pattern of installing cron at runtime is eliminated.
- **finolog-cron fully removed**: The service was already `profiles: ["disabled"]`. With FINOLOG_WEEKLY now handled by `scripts/run_report.py --schedule` inside wookiee-oleg, the separate container has no purpose.
- **Cron window 7-18**: Per D-05, the 18:00 cron run triggers `is_final_window` (hour>=17 AND minute>=55) which sends the daily delivery notification per D-08.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

To deploy:
```bash
docker-compose -f deploy/docker-compose.yml build wookiee-oleg
docker-compose -f deploy/docker-compose.yml up -d wookiee-oleg
```

Verify cron is running:
```bash
docker exec wookiee_oleg crontab -l
# Expected: */30 7-18 * * * cd /app && python scripts/run_report.py --schedule >> /proc/1/fd/1 2>&1
```

## Known Stubs

None.

## Self-Check: PASSED

All files verified:
- deploy/Dockerfile: FOUND — no agents/v3 refs, cron in apt-get, python --version CMD
- deploy/docker-compose.yml: FOUND — run_report.py --schedule, 7-18 cron window, no finolog-cron
- scripts/run_oleg_v2_reports.py: DELETED (confirmed)
- scripts/run_oleg_v2_single.py: DELETED (confirmed)
- scripts/run_finolog_weekly.py: DELETED (confirmed)
- Commit ed517fa (Dockerfile): FOUND
- Commit 0d741ef (docker-compose + scripts deleted): FOUND

---
*Phase: 04-scheduling-delivery*
*Completed: 2026-04-01*
