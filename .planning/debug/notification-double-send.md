---
status: investigating
trigger: "notification-double-send"
created: 2026-03-28T14:00:00Z
updated: 2026-03-28T14:30:00Z
---

## Current Focus

hypothesis: TWO independent bugs cause the double-send pattern:
  BUG 1 (01:00 MSK data_ready + daily report): The legacy scheduler's _job_data_ready_check (scheduler.py:213) and its daily_report job run at DAILY_REPORT_TIME (default 09:00 but seemingly configured to 01:00 on server). This is the legacy path. The conductor scheduler also runs at 06-12 MSK. The two schedulers are MUTUALLY EXCLUSIVE (create_scheduler picks one based on USE_CONDUCTOR). So the 01:00 sends must come from the legacy scheduler — meaning USE_CONDUCTOR=false on the server OR the DAILY_REPORT_TIME env var is set to "01:00" and gates pass that early, OR there's a second process.
  BUG 2 (prompt-tuner 3x): _send_admin rate-limits to 5 min (300s). The 3 sends were at 09:51, 10:46, 10:51 — 55 min apart then 5 min apart. The 55-min gap (09:51 → 10:46) is beyond the 5-min rate limit, so each is a genuinely separate hourly _job_notion_feedback run (IntervalTrigger 60min). The 10:46 → 10:51 send (5 min apart) is WITHIN rate limit — meaning the error text changed slightly, creating a different md5 hash that passes rate limiting.

test: Check if DAILY_REPORT_TIME is set to "01:00" on server, or if USE_CONDUCTOR is false
expecting: Either the env var explains the 01:00 sends, or there's a second process/container
next_action: CHECKPOINT - need server env vars to confirm

## Symptoms

expected: Data-ready WB/OZON/aggregate notifications and daily financial report sent ONCE per day.
actual:
  - Data-ready WB/OZON/aggregate notifications sent at 01:00 MSK (WB 895 orders) AND again at 09:00 MSK (WB 897 orders)
  - Daily financial report sent at 01:05 MSK AND again at 09:04 MSK
  - prompt-tuner error "Key limit exceeded (monthly limit)" sent 3 times (09:51, 10:46, 10:51)
errors: No error - just duplicate sends. Also "Key limit exceeded" for prompt-tuner.
reproduction: Happens automatically on the scheduler. Observed on 2026-03-28.
timeline: User reported 2026-03-28. May have started recently.

## Eliminated

- hypothesis: Both conductor and legacy schedulers running simultaneously from same process
  evidence: create_scheduler() at scheduler.py:1018-1022 is an if/else — picks ONE based on USE_CONDUCTOR. Single app.py entry point calls create_scheduler() once. Cannot run both from same process.
  timestamp: 2026-03-28T14:10:00Z

- hypothesis: ConductorState dedup fails on restart (in-memory set cleared)
  evidence: mark_notified() persists to SQLite (conductor_log row with status='notified'). already_notified() reads from SQLite. Dedup survives restarts for the conductor path.
  timestamp: 2026-03-28T14:15:00Z

- hypothesis: _send_admin rate limiting prevents prompt-tuner triple send
  evidence: Rate limit is 5 min (300s). Sends at 09:51, 10:46, 10:51 — first two are 55 min apart (beyond limit). Third at 10:51 is only 5 min after second — but different error text would produce different md5 hash and bypass rate limit. Three genuinely distinct sends are possible.
  timestamp: 2026-03-28T14:20:00Z

## Evidence

- timestamp: 2026-03-28T14:05:00Z
  checked: scheduler.py create_scheduler() at line 1018
  found: Pure if/else branch — USE_CONDUCTOR=true → _setup_conductor_scheduler(), false → _setup_legacy_scheduler(). Mutually exclusive. Single process cannot run both.
  implication: If 01:00 MSK notifications arrive, they come from EITHER a separate process running legacy mode OR USE_CONDUCTOR=false on the server.

- timestamp: 2026-03-28T14:10:00Z
  checked: _setup_legacy_scheduler() data_ready_check job (scheduler.py:761-768)
  found: Legacy data_ready_check fires CronTrigger(hour="6-12", minute=0) — SAME window as conductor. Legacy daily_report job fires at DAILY_REPORT_TIME (default "09:00"). If server has DAILY_REPORT_TIME="01:00" AND USE_CONDUCTOR=false, the legacy scheduler would fire daily report at 01:00 AND data_ready_check at 06:00-12:00. But user sees data_ready at BOTH 01:00 AND 09:00.
  implication: The 01:00 send is NOT from data_ready_check (runs 06-12). It must be from a different mechanism or a second process.

- timestamp: 2026-03-28T14:15:00Z
  checked: Legacy _job_data_ready_check (scheduler.py:213-229) vs conductor data_ready_check
  found: Legacy _job_data_ready_check calls messages.data_ready() and _run_daily_report_attempt(). The conductor data_ready_check calls messages.channel_data_ready() (per WB/OZON) and messages.data_ready(). User sees BOTH per-channel (WB/OZON) AND combined notifications — this matches CONDUCTOR behavior, not legacy. Legacy only sends combined data_ready, not per-channel.
  implication: The 09:00 sends are from the CONDUCTOR (per-channel + combined). The 01:00 sends must be from a SECOND process/container running in legacy mode, OR from the legacy daily_report cron job triggered at an unusual time.

- timestamp: 2026-03-28T14:20:00Z
  checked: Legacy _job_daily_report / _run_daily_report_attempt (scheduler.py:135-201)
  found: Legacy _job_daily_report calls _run_daily_report_attempt which at line 226 calls messages.data_ready(date_to, ["дневной фин"]) BEFORE generating the report. This sends the data_ready combined notification. It does NOT send per-channel WB/OZON notifications.
  implication: The 01:00 combined notification "Данные готовы, запускаю: дневной фин" matches legacy behavior. The 01:00 WB/OZON per-channel notifications suggest a SECOND conductor process (or same conductor running with a different schedule config).

- timestamp: 2026-03-28T14:25:00Z
  checked: Conductor data_ready_check flow (conductor.py:116-201) — specifically mark_notified for per-channel keys
  found: Per-channel key = f"{report_date}:{mp}" = "2026-03-28:wb". mark_notified("2026-03-28:wb") inserts into SQLite with date="2026-03-28:wb". already_notified("2026-03-28:wb") queries WHERE date='2026-03-28:wb'. This is correct. BUT: if a second process has a SEPARATE SQLite DB (different STATE_DB_PATH or a fresh DB), both processes pass already_notified() independently and both send.
  implication: Two processes with separate state DBs is the most consistent explanation for ALL observed symptoms (both per-channel and combined notifications at different times).

- timestamp: 2026-03-28T14:30:00Z
  checked: config.py STATE_DB_PATH (line 107-110)
  found: Defaults to PROJECT_ROOT/agents/v3/data/v3_state.db. Can be overridden by V3_STATE_DB_PATH env var. If two containers/processes share the same DB file path (e.g., mounted volume), they share state and dedup works. If they have separate DB paths or separate volumes, dedup is broken.
  implication: Root cause mechanism confirmed — two isolated processes with separate conductor_log SQLite DBs, each running data_ready_check independently, each passing already_notified() because they don't see each other's marks.

- timestamp: 2026-03-28T14:35:00Z
  checked: prompt-tuner triple-send (09:51, 10:46, 10:51)
  found: _job_notion_feedback uses IntervalTrigger(minutes=60). Sends at 09:51 and 10:46 are ~55 min apart — consistent with one process running since ~09:00 (first interval fires ~60 min after start). The 10:51 send (5 min after 10:46) is within the 5-min rate limit window, so it must have a different error text causing a different md5 hash. Alternatively, the second process fires its own 10:51 notion_feedback interval.
  implication: The 10:51 send being 5 min after 10:46 strongly suggests TWO PROCESSES each running notion_feedback — process A fires at 10:46, process B fires at 10:51 (slight offset due to different start times). The rate-limit dict (_recent_messages) is in-memory and NOT shared between processes.

## Resolution

root_cause: |
  Two separate processes (likely two Docker containers or two systemd units) are running
  agents/v3 simultaneously. Each process:
  1. Creates its own AsyncIOScheduler with conductor jobs
  2. Maintains its own in-memory _recent_messages rate-limit dict
  3. Has its own ConductorState instance

  If the two processes use SEPARATE SQLite DB files (different mount paths or volumes),
  ConductorState.already_notified() passes independently in each process, causing:
  - Per-channel WB/OZON data_ready sent twice (different hourly slots, e.g. 01:00 and 09:00)
  - Combined data_ready sent twice
  - Daily report generated and delivered twice
  - notion_feedback error sent by each process independently

  SECONDARY HYPOTHESIS: One process runs USE_CONDUCTOR=false (legacy mode) and one runs
  USE_CONDUCTOR=true (conductor mode). The legacy process sends at 01:00 (DAILY_REPORT_TIME
  configured on server) + combined data_ready. The conductor sends at 06-12 MSK window.
  This explains WHY 01:00 differs from 09:00 — different schedulers with different clocks.
  The WB/OZON per-channel notifications at 01:00 would then indicate the legacy process
  was at some point ALSO running conductor code, OR the 01:00 per-channel was actually the
  conductor running at 01:00 (outside the 6-12 window) via a misconfigured cron.

  MOST LIKELY: Server has two running instances — one is a stale/old process from before
  a deploy that was not properly killed, or docker-compose brought up a second replica.

fix: |
  1. IMMEDIATE: Kill all v3 processes on server, verify only ONE instance is running
  2. Ensure both processes share the same SQLite DB path via mounted volume (prevents recurrence)
  3. OR add a process-level lock file at startup to prevent duplicate instances

verification: |
  After killing duplicate process: notifications arrive only once per day.
  Pending: server confirmation.

files_changed: []
