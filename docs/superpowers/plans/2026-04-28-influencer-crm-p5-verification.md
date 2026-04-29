# P5 Verification Report (2026-04-28)

**Branch:** feat/influencer-crm-p5
**Verifier:** P5 T9 subagent
**Plan:** 2026-04-28-influencer-crm-p5-sync-ops.md

## Summary
- ✅ Passed: 7
- ⚠️ Deferred: 2 (Supabase migrations 010 + 011 — MCP not authenticated)
- ❌ Failed: 0

(Counts по чекам: чеки 1 и 2 учитывают grep-валидацию как PASS, а *применение* миграций — как DEFERRED. Поэтому 7 чеков полностью PASS, 2 чека PASS с отложенным применением.)

## Check details

### Check 1: Migration 010 — pg_cron MV refresh
**Result:** ✅ PASS
**Evidence:** grep по `services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql` нашёл `CREATE EXTENSION IF NOT EXISTS pg_cron;`, `SELECT cron.schedule(`, расписание `'*/5 * * * *'` и тело `$$REFRESH MATERIALIZED VIEW CONCURRENTLY crm.v_blogger_totals$$`.
**Apply status:** ⚠️ DEFERRED — Supabase MCP не аутентифицирован, миграция не применена. Применяется юзером через `apply_migration` после авторизации.

### Check 2: Migration 011 — retention jobs
**Result:** ✅ PASS
**Evidence:** grep по `services/influencer_crm/migrations/011_retention_jobs.sql` нашёл `cron.schedule('crm_audit_log_retention'`, имя джобы `crm_metrics_snapshots_retention`, окна удаления `INTERVAL '90 days'` (audit_log) и `INTERVAL '365 days'` (integration_metrics_snapshots).
**Apply status:** ⚠️ DEFERRED — Supabase MCP не аутентифицирован. Применяется юзером после авторизации.

### Check 3: Incremental ETL unit tests
**Result:** ✅ PASS
**Evidence:** `pytest tests/services/sheets_etl/test_incremental.py -v` → 3/3 passed (test_filter_new_rows_skips_existing, test_filter_new_rows_passthrough_when_no_id, test_filter_new_rows_empty_existing) за 0.01s. Использован `.venv/bin/python` (Python 3.12.13).

### Check 4: `--incremental` flag wired
**Result:** ✅ PASS
**Evidence:** `python -m services.sheets_etl.run --help` показывает опцию `--incremental` с описанием "Skip rows whose sheet_row_id is already present in the target table".

### Check 5: etl_runner CLI shape
**Result:** ✅ PASS
**Evidence:** `python -m services.influencer_crm.scripts.etl_runner --help` показывает usage `etl_runner.py [-h] [--full]` с описанием "CRM Sheets ETL cron entrypoint" и опцией `--full` ("Full re-import (default: incremental)"). Импорт `from services.influencer_crm.scripts.etl_runner import main` → `ok`.

### Check 6: Ops endpoint tests
**Result:** ✅ PASS
**Evidence:** `pytest tests/services/influencer_crm/test_ops_router.py -v` → 2/2 passed (test_ops_health_shape, test_ops_health_requires_api_key) за 9.35s. `.env` симлинк (`/tmp/wookiee-crm-p5/.env → /Users/danilamatveev/Projects/Wookiee/.env`) на месте, fixture chain отработала чисто.

### Check 7: docker-compose YAML
**Result:** ✅ PASS
**Evidence:** `yaml.safe_load(...)` парсит `deploy/docker-compose.yml`; `services.wookiee-cron.command[0]` содержит `etl_runner` (фрагмент: `... && python scripts/...` → строки crontab включают вызов etl_runner). Assert `'etl_runner' in cmd` прошёл, выведено `OK`.

### Check 8: Frontend build
**Result:** ✅ PASS
**Evidence:** `pnpm build` (tsc -b && vite build) — `✓ 2130 modules transformed`, `✓ built in 205ms`. Артефакты: `dist/index.html` (0.75 kB), `dist/assets/index-D5QGp5kY.css` (34.92 kB), `dist/assets/index-D1i1ve92.js` (532.14 kB). Vite warning о chunk > 500 kB — не блокер.

### Check 9: Cutover runbook
**Result:** ✅ PASS
**Evidence:** `docs/runbooks/influencer-crm-cutover.md` существует, 118 строк (≥60). Все 6 обязательных секций присутствуют:
- `## Когда применять` (line 8)
- `## Pre-cutover чек-лист` (line 16)
- `## Cutover sequence` (line 32, c шагами 1–5)
- `## Rollback plan` (line 91)
- `## Day-1 monitoring` (line 103)
- `## Контакты эскалации` (line 116)

## Deferred items (action required by user)
1. Apply migration `010_pg_cron_mv_refresh.sql` через Supabase MCP после `mcp__plugin_supabase_supabase__authenticate`.
2. Apply migration `011_retention_jobs.sql` через Supabase MCP после авторизации (там же).
3. После применения миграций — проверить, что job-ы появились в `cron.job` (имена: pg_cron MV-refresh job, `crm_audit_log_retention`, `crm_metrics_snapshots_retention`).
4. Если после первого `*/5 * * * *` запуска MV не обновится — посмотреть `cron.job_run_details` для диагностики.

## Update — 2026-04-29 (post-application)

P0 fix coммичен (`6947d09`): `tool_telemetry.log_agent_run` no-op заменён на прямую запись в `crm.etl_runs` через `services/influencer_crm/scripts/_telemetry.py`. Routers/ops.py обновлён — SQL запросы переведены с `agent_runs` на `crm.etl_runs`.

Все 3 миграции применены к `gjvwcdtfglupewcwzfhw` (Wookiee Supabase) через MCP:
- ✅ `010_pg_cron_mv_refresh` — `pg_cron` extension установлен, job `crm_v_blogger_totals_refresh` зарегистрирован (`*/5 * * * *`).
- ✅ `011_retention_jobs` — два job'а: `crm_audit_log_retention` (вс 03:00, >90д) + `crm_metrics_snapshots_retention` (вс 03:15, >365д). Колонки `created_at`/`captured_at` верифицированы через information_schema перед apply.
- ✅ `012_etl_runs` — таблица `crm.etl_runs` (10 колонок), индекс `idx_etl_runs_agent_started`, retention job `crm_etl_runs_retention` (вс 03:30, >180д).

**Cron-проверка (2026-04-29 00:35 UTC):** все 4 джобы `active=true`. MV refresh уже отработал один раз: `cron.job_run_details` runid=1, status=succeeded, 82ms.

**Что осталось (требует явного разрешения юзера):**
- Первый реальный ETL: `python -m services.influencer_crm.scripts.etl_runner --full` — write на shared production, ждёт авторизации.
- QA1 mandatory gate.
- Push P5 ветки + PR (после landing P4 в main + rebase).
- Deploy на app server (`docker compose up -d wookiee-cron`).
- QA2 canary 24h post-deploy.

## Conclusion
P5 infra-side: COMPLETE (миграции применены, cron работает).
P5 deploy-side: PENDING (требует явных destructive действий: ETL/push/deploy).
