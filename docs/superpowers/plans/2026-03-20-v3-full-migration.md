# Wookiee v3 Full Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the migration from v2 monolith (agents/oleg/) to v3 micro-agent architecture, preserving all 13 scheduled jobs and 6 report types. Each stage leaves the system in a working state.

**Architecture:** v3 uses LangGraph + MD-defined micro-agents + 4 MCP servers. v2 remains in production until v3 is validated. Migration is incremental — v2 keeps running while v3 is built alongside it.

**Tech Stack:** Python, LangGraph, APScheduler, aiogram 3.15, MCP SDK, Supabase (pgvector + PostgreSQL), OpenRouter LLM

**Spec:** `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md`

---

## Current State

**v2 (production):** 13 cron jobs, 6 report types, TG+Notion delivery, gate checks, retry, anomaly monitor, watchdog. Entry: `python -m agents.oleg`

**v3 (code written, not deployed):** 22 MD micro-agents, runner.py (LangGraph), orchestrator.py (daily/weekly), christina.py, 4 MCP servers (81+ tools), observability logging. Missing: delivery, scheduling, 4/6 report types, gates, retry, monitoring.

## Reports to Preserve

| # | Report | Schedule | v2 Agent | v3 Status |
|---|--------|----------|----------|-----------|
| 1 | Daily financial | 09:00 | Reporter→Researcher | orchestrator.run_daily_report() exists |
| 2 | Weekly financial | Mon 10:15 | Reporter→Researcher | orchestrator.run_weekly_report() exists |
| 3 | Monthly financial | 1st Mon 10:30 | Reporter→Researcher | NOT implemented |
| 4 | Marketing weekly | Mon 11:15 | Marketer | NOT implemented |
| 5 | Marketing monthly | 1st Mon 11:30 | Marketer | NOT implemented |
| 6 | Funnel weekly | Mon 11:15 | FunnelAgent | NOT implemented |
| 7 | Finolog weekly DDS | Fri 18:00 | FinologService | NOT implemented |
| 8 | Monthly price analysis | 1st 11:00 | PriceAnalysis | NOT implemented |
| 9 | Anomaly monitor | every 4h | AnomalyMonitor | NOT implemented |
| 10 | Watchdog heartbeat | every 6h | Watchdog | NOT implemented |
| 11 | Data ready check | hourly 06-12 | GateChecker | NOT implemented |
| 12 | Notion feedback | 08:00 | NotionService | NOT implemented |
| 13 | Promotion scan | every 12h | PromotionScanner | NOT implemented (optional) |

---

## File Structure

### Stage 1: Project Cleanup
```
.gitignore                          # Modify: add data exclusions
.env.example                        # Create: env template
scripts/archive/                    # Create: move one-off scripts here
```

### Stage 2: Delivery Layer
```
agents/v3/delivery/
├── __init__.py
├── telegram.py                     # TG delivery adapter (port from v2 formatter)
├── notion.py                       # Notion delivery adapter (port from v2 notion_service)
└── router.py                       # Unified deliver(report, destinations) dispatcher
```

### Stage 3: Gates + Scheduling
```
agents/v3/
├── gates.py                        # Gate checker (port from v2 gate_checker.py)
├── scheduler.py                    # APScheduler cron jobs
├── app.py                          # Entry point: python -m agents.v3
└── state.py                        # SQLite state persistence (idempotency, dedup, retries)
```

### Stage 4: All Report Types
```
agents/v3/orchestrator.py           # Modify: add run_marketing_report, run_funnel_report, etc.
agents/v3/config.py                 # Modify: add all schedule times, thresholds, playbook paths
```

### Stage 5: Monitoring & Hardening
```
agents/v3/monitor.py                # Anomaly monitor + watchdog
agents/v3/circuit_breaker.py        # LangGraph retry wrapper
```

### Stage 6-7: Switchover & Decom
```
deploy/docker-compose.yml           # Modify: switch wookiee-oleg to v3
docs/archive/oleg-v2/               # Archive v2 code
services/etl/                       # Modify: real ETL logic (from Ibrahim)
```

---

## Task 1: Project Cleanup

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Create: `scripts/archive/` (move one-off scripts)

- [ ] **Step 1: Update .gitignore with data exclusions**

Add to `.gitignore`:
```
# Generated data (stored in Supabase, not git)
data/
agents/oleg/data/
reports/
test-results/

# Large reference files (ingested into KB)
Знания по Wildberries/
Вуки бренд/
```

- [ ] **Step 2: Create .env.example**

Create `.env.example` with all required variables (placeholder values):
```env
# === OpenRouter (LLM) ===
OPENROUTER_API_KEY=sk-or-...

# === Supabase ===
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres

# === External DB (read-only, marketplace data) ===
DB_HOST=89.23.119.253
DB_PORT=6433
DB_USER=...
DB_PASSWORD=...
DB_NAME_WB=pbi_wb_wookiee
DB_NAME_OZON=pbi_ozon_wookiee

# === Telegram ===
TELEGRAM_BOT_TOKEN=...
ADMIN_CHAT_ID=...

# === Notion ===
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=...

# === Wildberries ===
WB_API_KEY_IP=...
WB_API_KEY_OOO=...

# === OZON ===
OZON_CLIENT_ID=...
OZON_API_KEY=...

# === Finolog ===
FINOLOG_API_KEY=...
FINOLOG_BIZ_ID=48556

# === Google ===
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service_account.json

# === Knowledge Base ===
KB_API_URL=http://localhost:8002
GEMINI_API_KEY=...
```

- [ ] **Step 3: Move one-off scripts to archive**

```bash
mkdir -p scripts/archive
mv scripts/bitrix_chat_export.py scripts/archive/
mv scripts/bitrix_oauth_setup.py scripts/archive/
mv scripts/comms_analysis.py scripts/archive/
mv scripts/comms_export.py scripts/archive/
mv scripts/finolog_full_analysis.py scripts/archive/
mv scripts/wb_vuki_ratings.py scripts/archive/
```

Keep in `scripts/`: `manual_report.py`, `run_report.py`, `run_price_analysis.py`, `notion_sync.py`, `abc_analysis.py`, `abc_analysis_unified.py`, `abc_helpers.py`, `rebuild_reports.py`, `config.py` (shim), `data_layer.py` (shim).

- [ ] **Step 4: Verify nothing broke**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from agents.oleg import config; print('v2 config OK')"
python -c "from agents.v3 import config; print('v3 config OK')"
python -c "from shared.data_layer import get_brand_finance; print('data_layer OK')"
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example scripts/archive/
git commit -m "chore: project cleanup — gitignore data dirs, add .env.example, archive one-off scripts"
```

---

## Task 2: Telegram Delivery Adapter

**Files:**
- Create: `agents/v3/delivery/__init__.py`
- Create: `agents/v3/delivery/telegram.py`

**Context:** v2's Telegram delivery is in `agents/oleg/bot/formatter.py` (formatting, split, BBCode→HTML) and `agents/oleg/bot/handlers/reports.py` (send to users). We port the formatting logic and create a clean adapter.

- [ ] **Step 1: Create delivery directory**

```bash
mkdir -p agents/v3/delivery
touch agents/v3/delivery/__init__.py
```

- [ ] **Step 2: Read v2 formatter for reference**

Read `agents/oleg/bot/formatter.py` — understand `format_cost_footer()`, `add_caveats_header()`, message splitting logic (4000 char limit, split at paragraph/line/sentence/word boundaries).

- [ ] **Step 3: Write Telegram delivery adapter**

Create `agents/v3/delivery/telegram.py`:
- Function `format_telegram_message(report: dict, page_url: str = None, caveats: list = None) -> str` — assembles HTML message
- Function `split_message(text: str, max_len: int = 4000) -> list[str]` — splits long messages
- Function `send_report(bot_token: str, chat_ids: list[int], report: dict, page_url: str = None) -> None` — sends to all recipients
- Uses `aiogram.Bot` for sending (same as v2)
- Format: Notion link → caveats → telegram_summary → cost footer

- [ ] **Step 4: Test formatter produces valid output**

```bash
python -c "
from agents.v3.delivery.telegram import format_telegram_message, split_message
msg = format_telegram_message({
    'telegram_summary': 'Test summary',
    'cost_usd': 0.05, 'agents_called': 3, 'duration_ms': 15000,
})
print(f'Message length: {len(msg)}')
parts = split_message(msg)
print(f'Parts: {len(parts)}')
print(msg[:200])
"
```

- [ ] **Step 5: Commit**

```bash
git add agents/v3/delivery/
git commit -m "feat(v3): add Telegram delivery adapter"
```

---

## Task 3: Notion Delivery Adapter

**Files:**
- Create: `agents/v3/delivery/notion.py`

**Context:** v2's Notion delivery is in `agents/oleg/services/notion_service.py` — upserts pages by (date_start, date_end, report_type), converts Markdown→Notion blocks, sets properties (Период начала/конца, Статус, Источник, Тип анализа). We port this as a clean adapter.

- [ ] **Step 1: Read v2 notion_service.py for reference**

Read `agents/oleg/services/notion_service.py` — understand `sync_report()`, Markdown→blocks conversion, property mapping.

- [ ] **Step 2: Write Notion delivery adapter**

Create `agents/v3/delivery/notion.py`:
- Class `NotionDelivery(token, database_id)`
- Method `sync_report(start_date, end_date, report_md, report_type, chain_steps) -> str | None` — returns page URL
- Reuses the Markdown→Notion blocks conversion logic from v2
- Properties: Name (title), Период начала/конца (dates), Статус ("Актуальный"), Источник ("Oleg v3 (auto)"), Тип анализа

- [ ] **Step 3: Test Notion adapter imports**

```bash
python -c "from agents.v3.delivery.notion import NotionDelivery; print('Notion adapter OK')"
```

- [ ] **Step 4: Commit**

```bash
git add agents/v3/delivery/notion.py
git commit -m "feat(v3): add Notion delivery adapter"
```

---

## Task 4: Delivery Router

**Files:**
- Create: `agents/v3/delivery/router.py`

- [ ] **Step 1: Write delivery router**

Create `agents/v3/delivery/router.py`:
- Function `deliver(report: dict, destinations: list[str], config: dict) -> dict`
- Dispatches to telegram and/or notion adapters
- Returns `{"telegram": {"sent": True, "chat_ids": [...]}, "notion": {"page_url": "..."}}`
- Catches adapter errors independently (TG failure doesn't block Notion)

- [ ] **Step 2: Test router**

```bash
python -c "from agents.v3.delivery.router import deliver; print('Router OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/delivery/router.py
git commit -m "feat(v3): add delivery router (telegram + notion)"
```

---

## Task 5: Gate Checker

**Files:**
- Create: `agents/v3/gates.py`

**Context:** v2's gate_checker.py has hard gates (ETL ran today, source data ≥30% of avg, logistics >0) and soft gates (orders/revenue vs avg ≥70%, margin fill ≥50%). Hard gate failure blocks report, soft gate failure adds caveats.

- [ ] **Step 1: Read v2 gate_checker.py**

Read `agents/oleg/pipeline/gate_checker.py` — understand all gates, thresholds, column mappings (WB: dateupdate/logist/revenue/marga; OZON: date_update/logist_end/price_end).

- [ ] **Step 2: Write v3 gate checker**

Create `agents/v3/gates.py`:
- Class `GateChecker` with methods:
  - `check_hard_gates(date) -> GateResult` — ETL, source, logistics
  - `check_soft_gates(date) -> GateResult` — volume, revenue, margin fill
  - `check_all(date) -> GateResult` — both hard + soft
- `GateResult(passed: bool, hard_ok: bool, soft_ok: bool, caveats: list[str], details: dict)`
- Uses `shared/data_layer.py` for DB queries (same as v2)

- [ ] **Step 3: Test gates**

```bash
python -c "
from agents.v3.gates import GateChecker
gc = GateChecker()
# Will test against real DB
import asyncio
result = asyncio.run(gc.check_all('2026-03-19'))
print(f'Passed: {result.passed}, Hard: {result.hard_ok}, Soft: {result.soft_ok}')
print(f'Caveats: {result.caveats}')
"
```

- [ ] **Step 4: Commit**

```bash
git add agents/v3/gates.py
git commit -m "feat(v3): add gate checker (hard + soft gates)"
```

---

## Task 6: State Persistence

**Files:**
- Create: `agents/v3/state.py`

**Context:** v2 uses SQLite state_store for: report_delivered dedup, daily_retries tracking, data_ready notifications, notion_feedback cache. v3 needs the same for production reliability.

- [ ] **Step 1: Write state store**

Create `agents/v3/state.py`:
- Class `StateStore(db_path)` with SQLite backend
- Methods: `get(key) -> str`, `set(key, value, ttl_hours=None)`, `exists(key) -> bool`, `delete(key)`
- Helper methods: `mark_delivered(report_type, date)`, `is_delivered(report_type, date)`, `increment_retries(report_type, date)`, `get_retries(report_type, date)`
- Auto-creates table on first use

- [ ] **Step 2: Test state store**

```bash
python -c "
from agents.v3.state import StateStore
store = StateStore('/tmp/test_state.db')
store.set('test_key', 'test_value')
print(store.get('test_key'))
store.mark_delivered('daily', '2026-03-20')
print(f'Delivered: {store.is_delivered(\"daily\", \"2026-03-20\")}')
"
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/state.py
git commit -m "feat(v3): add SQLite state persistence"
```

---

## Task 7: All Report Types in Orchestrator

**Files:**
- Modify: `agents/v3/orchestrator.py`
- Modify: `agents/v3/config.py`

**Context:** Currently orchestrator.py only has `run_daily_report()` and `run_weekly_report()`. We need: monthly financial, marketing weekly/monthly, funnel weekly, finolog weekly, price analysis.

- [ ] **Step 1: Update config.py with all settings**

Add to `agents/v3/config.py`:
- All schedule times (from v2 config)
- All thresholds (anomaly margin 10%, DRR 30%, etc.)
- Playbook paths
- Pricing dict
- All report-related settings
- Telegram/Notion settings

- [ ] **Step 2: Add run_monthly_report() to orchestrator.py**

Same pipeline as weekly but with monthly period and `task_type="monthly_report"`.

- [ ] **Step 3: Add run_marketing_report() to orchestrator.py**

New pipeline:
1. Run campaign-optimizer, organic-vs-paid, ad-efficiency in parallel
2. Pass to report-compiler with marketing-specific prompt
3. Returns same structure (detailed_report, brief_report, telegram_summary)

- [ ] **Step 4: Add run_funnel_report() to orchestrator.py**

New pipeline:
1. Run funnel-digitizer (+ keyword-analyst if tools available)
2. Pass to report-compiler with funnel-specific prompt

- [ ] **Step 5: Add run_finolog_report() to orchestrator.py**

Uses FinologService from v2 (`agents/oleg/services/finolog_service.py`):
1. Call `FinologService.build_weekly_summary()`
2. Pass to report-compiler

- [ ] **Step 6: Add run_price_analysis() to orchestrator.py**

Pipeline:
1. Run price-strategist, hypothesis-tester in parallel
2. Pass to report-compiler with price-specific prompt

- [ ] **Step 7: Test each report type with --dry-run**

```bash
python -c "
import asyncio
from agents.v3.orchestrator import run_daily_report
result = asyncio.run(run_daily_report('2026-03-19', '2026-03-19', '2026-03-18', '2026-03-18', trigger='test'))
print(f'Status: {result[\"status\"]}, Agents: {result[\"agents_succeeded\"]}/{result[\"agents_called\"]}')
"
```

- [ ] **Step 8: Commit**

```bash
git add agents/v3/orchestrator.py agents/v3/config.py
git commit -m "feat(v3): add all report types — marketing, funnel, finolog, price, monthly"
```

---

## Task 8: Scheduler + App Entry Point

**Files:**
- Create: `agents/v3/scheduler.py`
- Create: `agents/v3/app.py`
- Create: `agents/v3/__main__.py`

**Context:** v2 uses APScheduler with AsyncIOScheduler. We create the same for v3, wiring all report types to their cron schedules.

- [ ] **Step 1: Write scheduler**

Create `agents/v3/scheduler.py`:
- Uses APScheduler `AsyncIOScheduler` with `CronTrigger`
- All 13 cron jobs from v2:
  - Daily financial (09:00), Weekly (Mon 10:15), Monthly (1st Mon 10:30)
  - Marketing weekly (Mon 11:15), Marketing monthly (1st Mon 11:30)
  - Funnel weekly (Mon 11:15, parallel with marketing)
  - Finolog weekly DDS (Fri 18:00)
  - Price analysis (1st 11:00)
  - Data ready check (hourly 06-12)
  - Notion feedback (08:00)
  - Anomaly monitor (every 4h) — placeholder, implemented in Task 9
  - Watchdog (every 6h) — placeholder, implemented in Task 9
- Each job: gate check → generate → deliver
- Retry logic: 3 attempts, 30 min intervals
- Idempotency via state store

- [ ] **Step 2: Write app entry point**

Create `agents/v3/app.py`:
- Initializes: config, scheduler, telegram bot (aiogram)
- Starts scheduler + bot polling in asyncio loop
- Handles graceful shutdown (SIGINT, SIGTERM)
- Logging setup

Create `agents/v3/__main__.py`:
```python
from agents.v3.app import main
main()
```

- [ ] **Step 3: Test scheduler starts without errors**

```bash
python -c "
from agents.v3.scheduler import create_scheduler
s = create_scheduler()
jobs = s.get_jobs()
print(f'Scheduled jobs: {len(jobs)}')
for j in jobs:
    print(f'  {j.id}: next_run={j.next_run_time}')
"
```

- [ ] **Step 4: Test app entry point**

```bash
timeout 5 python -m agents.v3 --dry-run 2>&1 || true
# Should start without errors, print scheduled jobs
```

- [ ] **Step 5: Commit**

```bash
git add agents/v3/scheduler.py agents/v3/app.py agents/v3/__main__.py
git commit -m "feat(v3): add scheduler + app entry point with all 13 cron jobs"
```

---

## Task 9: Monitoring & Hardening

**Files:**
- Create: `agents/v3/monitor.py`

- [ ] **Step 1: Write anomaly monitor**

Create anomaly monitor in `agents/v3/monitor.py`:
- `check_anomalies()` — uses anomaly-detector micro-agent
- Thresholds: revenue ±20%, margin ±10%, DRR >30% increase, orders >25% decrease
- Weekend multiplier 1.5x
- Sends TG alert if anomalies detected

- [ ] **Step 2: Write watchdog heartbeat**

Add to `agents/v3/monitor.py`:
- `heartbeat()` — checks LLM API, MCP servers, DB connectivity, last report status
- Escalation: info → warning → critical (Telegram alert)

- [ ] **Step 3: Add circuit breaker wrapper**

Add to `agents/v3/runner.py` or separate file:
- 3 consecutive failures → skip agent for 5 min
- Wraps `run_agent()` calls

- [ ] **Step 4: Commit**

```bash
git add agents/v3/monitor.py
git commit -m "feat(v3): add anomaly monitor, watchdog, circuit breaker"
```

---

## Task 10: Parallel Validation

**Files:**
- Modify: `agents/v3/app.py` (add --dry-run and --compare modes)

- [ ] **Step 1: Add dry-run mode**

`python -m agents.v3 --dry-run` — generates reports but doesn't deliver (prints to stdout).

- [ ] **Step 2: Run v3 alongside v2 for 3 days**

Manual: Run daily report via v3 with `--dry-run`, compare output with v2 Notion page.

Checklist:
- [ ] Day 1: Daily report matches v2 (same KPIs, same sections)
- [ ] Day 2: Daily report + marketing weekly
- [ ] Day 3: Full week (all report types)

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(v3): validation fixes from parallel run"
```

---

## Task 11: Production Switchover

**Files:**
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: Update docker-compose to use v3**

Change `wookiee-oleg` service:
```yaml
wookiee-oleg:
  command: python -m agents.v3  # was: python -m agents.oleg
```

- [ ] **Step 2: Deploy to server**

```bash
ssh timeweb "cd /opt/wookiee && git pull && docker compose up -d wookiee-oleg"
```

- [ ] **Step 3: Verify first report generates**

Monitor Telegram for next scheduled report (or trigger manually).

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml
git commit -m "feat: switch production to v3 multi-agent system"
```

---

## Task 12: Decommission v2 + Migrate Ibrahim/Finolog

**Files:**
- Move: `agents/oleg/` → `docs/archive/oleg-v2/`
- Modify: `services/etl/` (real ETL from Ibrahim)
- Modify: Various import references

- [ ] **Step 1: Archive v2 code**

```bash
mkdir -p docs/archive
mv agents/oleg docs/archive/oleg-v2
```

- [ ] **Step 2: Migrate Ibrahim ETL to services/etl/**

Move real ETL logic from `agents/ibrahim/tasks/` to `services/etl/`:
- `services/etl/marketplace_sync.py` — real WB/OZON ETL (not stub)
- `services/etl/data_quality.py` — real data quality checks
- `services/etl/reconciliation.py` — real reconciliation
- Add cron jobs to v3 scheduler

- [ ] **Step 3: Migrate Finolog Categorizer**

Options:
a) Keep as standalone cron job in `services/etl/finolog_categorizer.py`
b) Integrate into v3 scheduler

- [ ] **Step 4: Fix any broken imports**

Update imports that referenced `agents.oleg.*` to use v3 equivalents or archived paths.

- [ ] **Step 5: Update documentation**

- Update `docs/architecture.md`
- Update `docs/index.md`
- Update `README.md`

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete v2→v3 migration — archive v2, migrate Ibrahim/Finolog"
```

---

## Summary

| Task | What | Est. Complexity |
|------|------|-----------------|
| 1 | Project cleanup (.gitignore, .env.example, archive scripts) | Easy |
| 2 | Telegram delivery adapter | Medium |
| 3 | Notion delivery adapter | Medium |
| 4 | Delivery router | Easy |
| 5 | Gate checker | Medium |
| 6 | State persistence (SQLite) | Easy |
| 7 | All report types in orchestrator | Hard |
| 8 | Scheduler + app entry point | Hard |
| 9 | Monitoring & hardening | Medium |
| 10 | Parallel validation (3 days) | Manual |
| 11 | Production switchover | Easy |
| 12 | Decommission v2 + migrate Ibrahim/Finolog | Medium |

**Acceptance Criteria:**
- [ ] All 6 report types generate correctly (daily, weekly, monthly, marketing, funnel, finolog)
- [ ] Reports delivered to Telegram and Notion
- [ ] Scheduler runs all 13 cron jobs
- [ ] Gate checks prevent broken reports
- [ ] Anomaly monitor detects and alerts
- [ ] System recovers from individual agent failures (graceful degradation)
- [ ] `python -m agents.v3` starts cleanly and runs autonomously
