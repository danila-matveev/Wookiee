---
status: resolved
trigger: "Скрипт создания еженедельного отчёта по логистике не был запущен/выполнен за текущую неделю (25-30 марта 2026)"
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T10:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — the report is manually-only with no active automation running; the v3 agent was not running on Monday March 24 when the cron job would have fired
test: Checked v3_state.db conductor_log, kv_store, running processes, scheduler code
expecting: No record of localization_weekly in any state store
next_action: Document root cause and provide manual run command

## Symptoms

expected: Каждую неделю генерируется отчёт "Анализ логистических расходов" и публикуется в Notion (database "Аналитические отчеты", collection://30158a2b-d587-8091-bfc3-000b83c6b747)
actual: Отчёт за 25-30 марта 2026 не создан. Последний — за 18-24 марта (создан 2026-03-25).
errors: Неизвестно — нужно найти скрипт и проверить логи/крон/историю запуска
reproduction: Попытаться запустить скрипт для текущей недели
started: Последний успешный отчёт создан 2026-03-25 (за неделю 18-24 марта)

## Eliminated

- hypothesis: The report is fully automated and something broke the automation
  evidence: v3 conductor_log has no localization_weekly entries ever; kv_store is empty (0 rows); the report was run manually last time (Notion shows "Источник: Reporter (manual)")
  timestamp: 2026-03-30T10:00:00Z

- hypothesis: The v3 agent ran but the localization job failed silently
  evidence: conductor_log only has daily+notification entries (Mar 27-28); v3_state.db last modified Mar 28 09:04; kv_store has 0 entries — no mark_delivered ever called for localization_weekly
  timestamp: 2026-03-30T10:00:00Z

- hypothesis: The report was moved to a new pipeline
  evidence: No alternative pipeline exists for logistics reports; only v3 and manual script
  timestamp: 2026-03-30T10:00:00Z

## Evidence

- timestamp: 2026-03-30T10:00:00Z
  checked: agents/v3/data/v3_state.db — kv_store table
  found: 0 rows — no mark_delivered() ever called for localization_weekly
  implication: Job never successfully completed in automated mode

- timestamp: 2026-03-30T10:00:00Z
  checked: agents/v3/data/v3_state.db — conductor_log table
  found: Only 8 rows, all daily/notification, dates Mar 27-28 only. No localization_weekly entries.
  implication: v3 agent was not running on Monday Mar 24 when the job should have fired

- timestamp: 2026-03-30T10:00:00Z
  checked: ps aux for v3/wookiee/agent processes
  found: No v3 agent process running. Only node/vite (wookiee-hub) is running.
  implication: The scheduler is not currently active; no automation running

- timestamp: 2026-03-30T10:00:00Z
  checked: agents/v3/scheduler.py — _job_localization_weekly, _setup_conductor_scheduler
  found: Job is registered (line 880-891) in both legacy and conductor schedulers, fires Monday 13:00 MSK. But USE_CONDUCTOR=true uses conductor mode which does NOT include localization_weekly in ConductorSchedule enum (agents/v3/conductor/schedule.py has no localization entry).
  implication: Even when v3 runs, conductor mode may not trigger the localization job (it's added as a separate cron in _setup_conductor_scheduler, so it should fire — but the v3 agent was simply not running on March 24)

- timestamp: 2026-03-30T10:00:00Z
  checked: scripts/run_localization_report.py
  found: Manual runner exists; uses agents/v3/delivery/router.py deliver() with notion_source="Reporter (manual)"; last Notion report confirms this was run manually on 2026-03-25
  implication: The report requires manual execution or a running v3 agent process

- timestamp: 2026-03-30T10:00:00Z
  checked: agents/v3/data/test_reports/ file timestamps
  found: All files dated Mar 25 — daily_2026-03-23, daily_2026-03-24, marketing_weekly, price_analysis, weekly. Nothing after Mar 25.
  implication: The v3 agent/system was last actively used on Mar 25, then stopped or went offline

## Resolution

root_cause: The weekly localization/logistics report was not generated for 25-30 March because:
  1. PRIMARY: The v3 agent process is not currently running (no Python agent process found). The APScheduler cron job (Monday 13:00 MSK) could not fire on March 24 because the process was down.
  2. SECONDARY: The previous report (18-24 March) was run manually on March 25 via `scripts/run_localization_report.py`, not by the automation. This means the automation was already not reliably running.
  3. The report pipeline itself is intact and functional — the manual runner script works.

fix: Run the report manually for the current week:
  python scripts/run_localization_report.py --date-from 2026-03-25 --date-to 2026-03-30
  (or with --no-telegram if bot token is not configured)

verification:
files_changed: []
