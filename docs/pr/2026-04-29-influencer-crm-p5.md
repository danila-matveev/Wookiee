# Phase 5 — Sync & Ops для Influencer CRM

## Summary

Production-ready ops layer для CRM:
- pg_cron MV refresh каждые 5 минут (`crm_v_blogger_totals_refresh`) — applied to Supabase
- Weekly retention для `audit_log` (>90 дн) и `integration_metrics_snapshots` (>365 дн)
- Sheets ETL `--incremental` режим + cron каждые 6 часов в `wookiee-cron`
- Telemetry pipeline: `crm.etl_runs` table (P0 fix — `tool_telemetry.log_agent_run` no-op since 2026-04-13)
- `/ops/health` endpoint + `/ops` страница с KpiCards, cron table, retention queue
- Cutover runbook (Sheets → CRM swap playbook, 118 строк)

Также включает Phase 4 frontend baseline (T1–T22) — UI на React+Vite+Tailwind 4, 7 экранов, 19 unit + 4 e2e тестов. Branch ответвлена от `feat/influencer-crm-p3` и содержит merge-commit с `feat/influencer-crm-p4` (см. Rebase note).

## Что применено к Supabase (через MCP)

| Migration | Состояние | Объекты |
|---|---|---|
| `010_pg_cron_mv_refresh` | applied | `pg_cron` extension + job `crm_v_blogger_totals_refresh` (`*/5`) |
| `011_retention_jobs` | applied | jobs `crm_audit_log_retention` (вс 03:00) + `crm_metrics_snapshots_retention` (вс 03:15) |
| `012_etl_runs` | applied | table `crm.etl_runs` + index + retention job (вс 03:30) |

Verified: `cron.job` 4 jobs active, `cron.job_run_details` runid=1 succeeded (MV refresh, 82ms).

## Modified files

### Migrations (3 files, +84)
- `services/influencer_crm/migrations/010_pg_cron_mv_refresh.sql` (+18) — pg_cron extension + MV refresh job
- `services/influencer_crm/migrations/011_retention_jobs.sql` (+35) — audit_log + metrics_snapshots retention
- `services/influencer_crm/migrations/012_etl_runs.sql` (+31) — crm.etl_runs table + index + retention

### Sheets ETL (3 files, +85)
- `services/sheets_etl/incremental.py` (+29) — фильтр по sheet_row_id
- `services/sheets_etl/run.py` (+33/-) — `--incremental` flag wired
- `tests/services/sheets_etl/test_incremental.py` (+23) — 3/3 passed

### Influencer CRM BFF (5 files, +362)
- `services/influencer_crm/app.py` (+3/-1) — register ops router
- `services/influencer_crm/routers/ops.py` (+171) — `/ops/health` endpoint
- `services/influencer_crm/schemas/ops.py` (+37) — pydantic schemas
- `services/influencer_crm/scripts/_telemetry.py` (+62) — direct write to `crm.etl_runs` (P0 fix)
- `services/influencer_crm/scripts/etl_runner.py` (+69) — cron entrypoint
- `services/influencer_crm/scripts/run_dev.sh` (+1)
- `tests/services/influencer_crm/test_ops_router.py` (+24) — 2/2 passed

### Influencer CRM UI (P4 baseline + /ops dashboard, ~85 files, +9.6K)
- `services/influencer_crm_ui/src/routes/ops/OpsPage.tsx` (+138) — ETL status + cron table + retention queue
- `services/influencer_crm_ui/src/api/ops.ts` (+38), `src/hooks/use-ops.ts` (+12)
- Ранее в P4: AppShell, Sidebar, TopBar, 7 страниц (bloggers, integrations kanban, briefs, calendar, slices, products, search), UI primitives, MSW + Playwright infra (e2e/golden-*.spec.ts), TanStack Query hooks, RHF+zod drawers.

### Infra (1 file, +4/-2)
- `deploy/docker-compose.yml` — schedule CRM ETL every 6h в wookiee-cron

### Docs (4 files, +3459)
- `docs/runbooks/influencer-crm-cutover.md` (+118) — Sheets → CRM swap playbook
- `docs/superpowers/plans/2026-04-28-influencer-crm-p4-frontend.md` (+2352) — Phase 4 plan
- `docs/superpowers/plans/2026-04-28-influencer-crm-p5-sync-ops.md` (+903) — Phase 5 plan
- `docs/superpowers/plans/2026-04-28-influencer-crm-p5-verification.md` (+86) — verification report
- `docs/superpowers/plans/2026-04-26-influencer-crm-roadmap.md` (+1) — roadmap link

## Test plan

- [x] `pytest tests/services/sheets_etl/test_incremental.py` — 3/3
- [x] `pytest tests/services/influencer_crm/test_ops_router.py` — 2/2
- [x] Полный pytest suite (P3 BFF + P5 ETL) — 76 passed, 1 skipped, 0 failed
- [x] `pnpm typecheck` (UI) — 0 errors
- [x] `pnpm build` (UI) — clean, 532 KB / 165 KB gzip
- [ ] Playwright golden paths (вкл. /ops smoke) — см. QA1 report
- [ ] Codex quality gate — см. quality gate report
- [ ] Реальный ETL `--full` против Supabase — после merge (требует deploy)
- [ ] QA2 canary 24h — post-deploy

## Deferred follow-ups

- Реальный ETL run после deploy (заполнит `crm.etl_runs` первой строкой)
- QA1 live-BFF portion (gstack-qa, gstack-design-review, dogfood) — best after staging deploy
- QA2 canary post-deploy
- (опц.) Удалить deprecation `tool_telemetry.log_agent_run` если она нигде больше не нужна — отдельный PR

## Rebase note

Эта ветка ответвлена от `feat/influencer-crm-p3` и содержит merge-commit `9947c67` с `feat/influencer-crm-p4` (нужен был UI baseline для T7). После landing P4 в main — rebase на main дропнет merge-commit:

```bash
git checkout main && git pull
git rebase --onto main feat/influencer-crm-p4 feat/influencer-crm-p5
git push --force-with-lease origin feat/influencer-crm-p5
```

## Commits

```
8ca3aaa docs(crm-ops): P5 verification update — 3 migrations applied, MV refresh fired
6947d09 fix(crm-ops): switch telemetry to crm.etl_runs (tool_telemetry is no-op)
260a69e docs(crm-ops): P5 verification report (8 checks: passed/deferred breakdown)
7329cef docs(crm-ops): cutover runbook (Sheets → CRM swap playbook)
2a4cd29 feat(crm-ui): /ops dashboard (ETL status + cron table + retention queue)
9947c67 Merge branch 'feat/influencer-crm-p4' into feat/influencer-crm-p5
af5011c feat(crm-ops): /ops/health endpoint (etl status + cron + retention queue)
fd874e8 feat(crm-ops): schedule CRM Sheets ETL every 6h in wookiee-cron
16baa0f feat(crm-ops): tool_telemetry-wrapped ETL runner (agent_name=crm-sheets-etl)
8aa0c1c feat(crm-etl): --incremental flag skips unchanged rows by sheet_row_id
ea96f22 feat(crm-ops): pg_cron weekly retention (audit_log 90d, snapshots 365d)
346e9c2 feat(crm-ops): pg_cron schedule v_blogger_totals refresh every 5 min
052c5b9 plan(crm-p5): sync & ops — pg_cron + sheets ETL cron + tool_telemetry + /ops dashboard
dae659b refactor(crm-ui): extract lib/format.ts (Gap 3)
945936e feat(crm-ui): optional live-BFF mode for Playwright (Gap 2)
b28f7e7 feat(crm-ui): axe-core a11y assertions in Playwright (Gap 1)
2192790 chore(crm-ui): Phase 4 done
79104ba feat(crm-ui): T22 — README + dev runner + production build verified
e18fcd5 feat(crm-ui): T21 — Playwright golden-path tests (4 specs vs mocked API)
03d040a feat(crm-ui): T20 — a11y pass (aria-labels, captions, axe-core in dev)
4bf4409 feat(crm-ui): T19 — unified QueryStatusBoundary across pages
0d2d337 feat(crm-ui): T18 — global search page (bloggers + integrations)
0b0d2b1 feat(crm-ui): T17 — products page with halo slice
2568d74 feat(crm-ui): T16 — slices page with multi-filter aggregation + CSV export
61d0446 feat(crm-ui): T15 — briefs kanban + markdown editor + version history
3bc0663 feat(crm-ui): T14 — calendar month grid with click-to-edit + click-to-create
e794a9b feat(crm-ui): T13 — integration edit drawer (basics + costs + compliance + fact, substitutes RO)
5b84cbb feat(crm-ui): T12 — integrations Kanban with @dnd-kit + optimistic stage updates
e469597 feat(crm-ui): T11 — blogger edit drawer with RHF + zod (Инфо tab live, others stubbed)
54083e3 feat(crm-ui): T10 — bloggers list with filters + table + row expand
17b52a2 feat(crm-ui): T9 — Drawer with Esc + focus trap
408e180 feat(crm-ui): T8 — AppShell + Sidebar + TopBar + router with 7 stub pages
8fea636 feat(crm-ui): T7 — UI primitives (Button/Badge/Avatar/Input/Select/Pills/EmptyState/Skeleton/Tabs/Kpi)
7ca3100 chore: ignore local .crm-mockups copy (design contract — see .superpowers/brainstorm/)
220a5e4 chore(crm-ui): migrate biome.json to installed Biome version
62622da chore(crm-ui): align tsconfig.node.json with composite project requirements
567e9c4 chore(crm-ui): use vitest/config import for Vite types
69f46ec feat(crm-ui): T6 — TanStack Query + useBloggers + MSW test infra
ab00019 feat(crm-ui): T5 — cursor encode/decode (parity with backend)
88d83fd feat(crm-ui): T4 — fetch wrapper with X-API-Key + ETag cache
995a096 feat(crm-ui): T3 — load Plus Jakarta Sans + DM Sans + JetBrains Mono
219ace2 feat(crm-ui): T2 — port design tokens from prototype to Tailwind theme
8fd4725 chore(crm-ui): T1 — scaffold Vite + React + Tailwind 4 + Biome + Vitest
8f38432 docs(crm-ui): Phase 4 frontend implementation plan (22 tasks)
```

## Roadmap link

См. полный план: [docs/superpowers/plans/2026-04-28-influencer-crm-p5-sync-ops.md](docs/superpowers/plans/2026-04-28-influencer-crm-p5-sync-ops.md)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
