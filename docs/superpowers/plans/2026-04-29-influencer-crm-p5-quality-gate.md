# P5 Quality Gate Report (2026-04-29)

## Diff scope
- Branch: `feat/influencer-crm-p5` vs `feat/influencer-crm-p3`
- Commits: 49 (включая auto-fix `14ed371` и пред-merge коммиты P4)
- Files changed: 124 (+14640 / −9 lines, доминирует P4 frontend, который влит через `9947c67`)
- P5-specific surface (новое в P5):
  - `services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql`
  - `services/influencer_crm/migrations/011_retention_jobs.sql`
  - `services/influencer_crm/migrations/012_etl_runs.sql`
  - `services/influencer_crm/routers/ops.py` + `schemas/ops.py`
  - `services/influencer_crm/scripts/_telemetry.py` + `etl_runner.py`
  - `services/sheets_etl/incremental.py` + `--incremental` flag в `run.py`
  - `services/influencer_crm_ui/src/api/ops.ts` + `routes/ops/OpsPage.tsx` + `hooks/use-ops.ts`
  - `deploy/docker-compose.yml` (cron-строка для CRM ETL)
  - `docs/runbooks/influencer-crm-cutover.md`
  - тесты: `tests/services/influencer_crm/test_ops_router.py`, `tests/services/sheets_etl/test_incremental.py`, `services/influencer_crm_ui/e2e/golden-ops.spec.ts`

## Verdict
- HIGH: 0
- MEDIUM: 2
- LOW: 3

## HIGH priority findings
Нет.

## MEDIUM priority findings

### M1. `_fetch_mv_age` использует неправильный источник свежести
- File: `services/influencer_crm/routers/ops.py:91-113`
- Description: запрос читает `pg_stat_user_tables.last_analyze` / `last_autoanalyze` для оценки "свежести" `crm.v_blogger_totals`. Эти счётчики не обновляются при `REFRESH MATERIALIZED VIEW CONCURRENTLY` — они меняются только при `ANALYZE`/autovacuum-аналайзе. На практике метрика `mv_age_seconds` будет либо upper-bounded на ~24 часа (через защитный COALESCE с `now() - INTERVAL '1 day'`), либо отражать момент последнего autoanalyze (типично через несколько часов после первого REFRESH). Это вводит дашборд `/ops` в заблуждение: "MV age = 5 минут" не значит "REFRESH прошёл 5 минут назад".
- Right fix: читать `MAX(end_time)` из `cron.job_run_details` для `jobname = 'crm_v_blogger_totals_refresh'` (или хранить ts последнего REFRESH в отдельной таблице, но `cron.job_run_details` достаточно):
  ```sql
  SELECT EXTRACT(EPOCH FROM (now() - MAX(d.end_time)))::int AS age
  FROM cron.job_run_details d
  JOIN cron.job j ON j.jobid = d.jobid
  WHERE j.jobname = 'crm_v_blogger_totals_refresh' AND d.status = 'succeeded'
  ```
- Why not auto-fixed: запрос требует прав на `cron.job_run_details` (доступно postgres-owner-у; SQL уже подключается тем же ролью что и миграции, но требует валидации на live DB), и нужно минимум один тест-фикс. Перед PR — рекомендуется fix отдельной коммитой с проверкой на Supabase.
- Severity: MEDIUM, не блокер для PR — текущая метрика не врёт катастрофически (`audit_log_eligible_for_delete` и `cron_jobs.active` — основные сигналы здоровья), но ввод в заблуждение в day-1 monitoring (`mv_age_seconds < 600`) — реален.

### M2. `_fetch_etl_counts` не различает `running`-запуски
- File: `services/influencer_crm/routers/ops.py:67-88`
- Description: счётчики "успешно за 24ч" и "сбоев за 24ч" фильтруют по `status IN ('success','failed')`. Запуск, который завис в `status='running'` (например, ETL получил SIGKILL до записи финального статуса), не попадает ни туда, ни туда — дашборд покажет `failed = 0`, а реальная ситуация — мёртвый ETL. `EtlCounts` не отражает stuck-runs.
- Right fix: добавить третье поле `stuck` (или `running` если `started_at < now() - INTERVAL '1 hour'`), или хотя бы пометить последний run в `EtlLastRun` как "stale" если `status='running' AND started_at < now() - 1h`.
- Why not auto-fixed: расширение схемы (новое поле в Pydantic + TypeScript + UI карточка). Может быть отдельным P5.1 PR.
- Severity: MEDIUM — снижает signal-to-noise day-1 dashboard, но не блокирует PR.

## LOW / Notes

### L1. `incremental.py:filter_new_rows` — избыточная trailing-предикат — fixed
- File: `services/sheets_etl/incremental.py:23-29`
- Description: Старый код:
  ```python
  return [r for r in rows if r.get("sheet_row_id") not in existing or "sheet_row_id" not in r]
  ```
  Trailing `or "sheet_row_id" not in r` дублировал условие "passthrough при отсутствии ключа", потому что `r.get("sheet_row_id") → None`, а `None not in <set[str]>` всегда True (None никогда не в set строк). Поведение корректное, но читается плохо.
- Status: FIXED в `14ed371` (auto-fix #1) — заменил на явный loop. 3/3 unit-теста проходят.

### L2. `/ops` маршрут отсутствовал в a11y ROUTES — fixed
- File: `services/influencer_crm_ui/e2e/golden-a11y.spec.ts:5-13`
- Description: новый дашборд `/ops` не был перечислен в массиве `ROUTES` для axe-core теста. Это пропустило бы wcag2a/wcag2aa нарушения на странице Ops.
- Status: FIXED в `14ed371` (auto-fix #1) — `/ops` добавлен в массив.

### L3. Migration `011` опирается на column-name `audit_log.created_at` без явной DDL-проверки в PR
- File: `services/influencer_crm/migrations/011_retention_jobs.sql:11-15`
- Description: комментарий миграции честно отмечает: "no live DDL or repo query references this column in the worktree. Verify column name on Supabase before applying." Verification report подтвердил, что после реального apply колонка существует, но в самом репо нет automated test, который сломается если переименуют. Если кто-то в будущем переименует `audit_log.created_at` — pg_cron job начнёт молча падать в `cron.job_run_details`, дашборд этого не покажет (мы смотрим `cron.job.active`, а не `last_run.status`).
- Followup: Day-1 monitoring должен проверять `MAX(status) FROM cron.job_run_details WHERE jobname LIKE 'crm_%_retention'`. Можно вынести в M1 fix (иначе M1 уже трогает `cron.job_run_details`).

## Notes on Wookiee-specific rule check
- **SQL safety**: все `text()` запросы в `routers/ops.py` параметризованы (`{"name": ETL_AGENT_NAME}`); user-controlled значений нет — все литералы хардкодятся в коде. PASS.
- **N+1 в /ops/health**: 5 коротких запросов на запрос — приемлемо. Каждый изолирован try/except + rollback. Coalescing в один `SELECT ... FROM (subquery1), (subquery2), ...` ухудшит читаемость и не даст заметного выигрыша (BFF на FastAPI, refetch 30s). PASS.
- **Connection leaks в `_telemetry.py`**: `try/finally conn.close()` корректно вложено в outer `try/except`. На исключении внутри `with conn.cursor()` — finally всё равно закрывает conn. PASS.
- **psycopg2 vs asyncio**: `etl_runner.py` синхронный (`def main`, не `async`); `services/sheets_etl/run.py` тоже sync. Никаких остаточных `await` / `import asyncio`. PASS.
- **Decimal rule**: P5 не вводит финансовых вычислений. PASS.
- **GROUP BY rule**: новые SQL не агрегируют по `article` / модели. PASS.
- **Telemetry no-op risk**: `log_agent_run` упоминается ТОЛЬКО как комментарий в `_telemetry.py` (объяснение, почему не вызывается). Нет ни одного импорта `tool_telemetry.logger` в P5-коде. PASS.
- **YAML safety**: `deploy/docker-compose.yml` парсится `yaml.safe_load`; cron-строка с `&&` корректно экранирована (вся команда — multiline literal под `command:`). PASS.
- **TypeScript типы**: `src/api/ops.ts` 1:1 mirror с `schemas/ops.py` (даже nullable matched: `T | None` ↔ `T | null`). PASS.
- **A11y `/ops`**: KpiCard имеет `aria-hidden` на dot-индикаторе, `<table>` имеет `<caption className="sr-only">`, `<th scope="col">`, sidebar `<nav aria-label="Главное меню">`. После M2-fix /ops покрыт axe-core. PASS (после fix).
- **Race conditions**: `REFRESH MATERIALIZED VIEW CONCURRENTLY` корректно (требует UNIQUE INDEX на MV, но это контракт MV из P1, не нового кода). ETL делает upsert по `sheet_row_id`, MV читает только финальные строки — гонка возможна (refresh запускается каждые 5 мин, ETL — каждые 6 ч, окно overlap минимально + CONCURRENTLY не блокирует читателей). PASS.
- **Migration ordering**: 010 → 011 → 012 не имеют явных FK-зависимостей друг от друга. 010 создаёт `pg_cron` extension (idempotent: `IF NOT EXISTS`). 011 предполагает `pg_cron` (через 010), но не требует 012. 012 создаёт `crm.etl_runs` и собственный retention-job. Применять в порядке номеров — рекомендация, но не строгое требование. Verification report подтвердил что все 3 применены успешно. PASS.

## Auto-fixes applied
- `14ed371` — `fix(crm-ops): a11y coverage for /ops + clarify filter_new_rows predicate`

## Codex CLI status
- Ran: NO (по факту — попытка была, exit-код 1)
- Reason: установленный `codex-cli 0.118.0` пытается использовать модель `gpt-5.5`, которая требует более новой версии CLI:
  > `ERROR: The 'gpt-5.5' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.`
- Дополнительно: при старте Codex выдал warning про неаутентифицированный Supabase MCP (`AuthRequired`), но это не блокер review-пайплайна.
- Action item: апгрейд `codex-cli` до версии, поддерживающей `gpt-5.5`, либо настройка fallback на `gpt-5.4`/`o3` через `~/.codex/config.toml` (`-c model="o3"`). Документировано как followup для quality-gate skill.
- Cross-model coverage в этом PR — Claude-only.

## Conclusion
- **PASS** (0 critical, 2 medium, 3 low — попадает в порог "≤3 warnings, 0 critical" если считать warnings как HIGH+MEDIUM = 2). 
- HIGH = 0 → не блокер.
- MEDIUM × 2 → recommended fix in follow-up PR (P5.1: ops dashboard accuracy):
  - M1: `_fetch_mv_age` через `cron.job_run_details`
  - M2: stuck-runs detection в `EtlCounts`
- LOW × 3 → 2 уже auto-fixed; L3 (audit_log column drift detector) — внести в day-1 monitoring runbook.

**Status: DONE_WITH_CONCERNS** — PR готов к открытию, но рекомендую коротко упомянуть M1+M2 в PR description как "known gaps, P5.1 follow-up".
