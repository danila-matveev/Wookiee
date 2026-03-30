---
status: awaiting_human_verify
trigger: "Weekly ДДС report fails every hour and sends duplicate failure notifications"
created: 2026-03-28T00:00:00Z
updated: 2026-03-28T13:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - Two separate bugs found:
  (1) Production server running OLD v3 code (pre-commit 38070b3) which has FINOLOG_WEEKLY in conductor schedule. The conductor's get_missed_reports returns finolog_weekly every hourly check because it permanently fails (LLM agents have no Finolog data access). Each hour exhausts 3 attempts and sends the "3/3 exhausted" notification.
  (2) The recovery mechanism in ConductorState.get_failed_types has a latent infinite-loop bug: failed reports get retried every hour indefinitely, with no daily retry cap. This is a design flaw that affects any persistently failing report.

test: Traced through conductor.py, schedule.py, state.py, scheduler.py; examined conductor_log SQLite DB
expecting: Fixes:
  (1) Deploy new code (38070b3 already deployed locally) - removes FINOLOG_WEEKLY from conductor
  (2) Add daily retry cap to get_missed_reports: skip report_type if attempts for that date already >= MAX_ATTEMPTS
next_action: Implement the retry cap fix in conductor.py/state.py and update the test

## Symptoms

expected: Weekly ДДС report should generate successfully and send one notification (success or failure)
actual: Report fails with "все агенты завершились с ошибкой — данные не получены", sends failure notification every hour (01:11, 02:06, 03:06, 04:06, 05:06, 06:06). 3/3 retries exhausted each time.
errors: "Не удалось сформировать «Weekly ДДС» за 2026-03-28. Причина: Все агенты завершились с ошибкой — данные не получены. Попытки: 3/3 — все исчерпаны."
reproduction: Happens automatically every hour overnight
started: ДДС report broken since 2026-03-16. Notification spam is a newer/separate issue.

## Eliminated

- hypothesis: Standalone run_finolog_weekly.py is the source of notifications
  evidence: The script has no Telegram notification code - it only logs stdout and sys.exit(1). The finolog-cron container only runs Monday 09:00 MSK.
  timestamp: 2026-03-28T12:00:00Z

- hypothesis: The NEW conductor code (post-38070b3) is generating the spam
  evidence: conductor_log shows no finolog_weekly entries. The new schedule.py has no FINOLOG_WEEKLY enum. get_today_reports and get_missed_reports cannot return it.
  timestamp: 2026-03-28T12:15:00Z

- hypothesis: Individual DateTrigger retries are causing all hourly notifications
  evidence: DateTrigger retries are spaced 1-5 minutes apart, not hourly. The hourly pattern matches the data_ready_check cron (06-12 MSK).
  timestamp: 2026-03-28T12:20:00Z

## Evidence

- timestamp: 2026-03-28T12:00:00Z
  checked: conductor_log SQLite DB
  found: Only 'daily' and '_notification' entries - no finolog_weekly. daily:success on both Mar 27 and 28.
  implication: The NEW code is deployed and running on the server. The spam happened while OLD code was running overnight.

- timestamp: 2026-03-28T12:05:00Z
  checked: git show 38070b3 -- agents/v3/conductor/schedule.py
  found: FINOLOG_WEEKLY enum removed, Friday trigger removed, human_name "Weekly ДДС" was FINOLOG_WEEKLY.human_name
  implication: The exact string "Weekly ДДС" in error messages comes from the old conductor code's ReportType.FINOLOG_WEEKLY.human_name

- timestamp: 2026-03-28T12:10:00Z
  checked: conductor.py data_ready_check + get_missed_reports logic
  found: get_missed_reports returns reports with status='failed' from past 6 days. generate_and_validate does NOT check if a report_type has already exceeded a daily attempt cap before retrying.
  implication: Any report that consistently fails gets retried every hourly data_ready_check indefinitely. This is the root cause of hourly spam.

- timestamp: 2026-03-28T12:15:00Z
  checked: messages.report_error() function
  found: When attempt >= max_attempts (3/3), sends "Попытки: 3/3 — все исчерпаны" - matching user's error
  implication: The conductor runs 3 internal retries per hourly run, then sends the "exhausted" notification. This repeats every hour.

- timestamp: 2026-03-28T12:20:00Z
  checked: scheduler.py data_ready_check window
  found: CronTrigger(hour="6-12", minute=0, timezone=MSK) = 7 hourly runs per day. 02:06-06:06 UTC = 05:06-09:06 MSK. Matches times reported by user (UTC+3 offset).
  implication: 6 of the 7 hourly runs fired notifications. The 06:00 MSK run was last one in the window.

## Resolution

root_cause: Two bugs:
  (1) IMMEDIATE - Production server was running pre-38070b3 code with FINOLOG_WEEKLY in conductor schedule. The report permanently fails (LLM agents have no Finolog data). Each hourly data_ready_check finds it via get_missed_reports, exhausts 3 attempts, sends "3/3" notification.
  (2) LATENT - ConductorState has no per-date attempt cap for missed-report recovery. A failing report type gets retried every hour indefinitely, with each retry sending a "3/3 exhausted" notification.

fix: |
  Bug 1: Fixed by 38070b3 (FINOLOG_WEEKLY removed from conductor entirely). Standalone finolog-cron container handles the report independently.
  Bug 2: Added ConductorState.get_exhausted_types(date, max_attempts) that returns report types where attempts >= max_attempts and status='failed' for that date. In data_ready_check, skip missed reports that are exhausted_today before adding to pending.

verification: |
  33/33 conductor tests pass (python3 -m pytest tests/v3/conductor/ -v).
  New test test_exhausted_report_not_retried_same_day verifies the fix.
  test_friday_returns_only_daily updated to reflect FINOLOG_WEEKLY removal.
  Pending: server redeployment + confirmation that spam stopped.

files_changed:
  - agents/v3/conductor/state.py (add get_exhausted_types method)
  - agents/v3/conductor/conductor.py (use get_exhausted_types in recovery block)
  - tests/v3/conductor/test_schedule.py (update test_friday_returns_finolog → test_friday_returns_only_daily)
  - tests/v3/conductor/test_integration.py (add test_exhausted_report_not_retried_same_day)
