# GitHub Actions Workflows

This folder holds all scheduled and event-driven CI workflows for the Wookiee
monorepo. The most important grouping is the **Nighttime DevOps Agent** — five
serialised workflows that scan the repo every night, fix what they safely can,
and surface the rest to the owner in plain Russian.

---

## Always-on workflows

| File | Trigger | What it does |
|---|---|---|
| `ci.yml` | every PR + push to `main` | ruff + compileall + pytest across `agents/`, `services/`, `shared/`, `scripts/`. Known pre-existing failures are documented inline. |
| `deploy.yml` | push to `main` (specific paths) | Triggers app-server autopull for services that opted in. |
| `hygiene-daily.yml` | cron `0 3 * * *` (03:00 UTC) | Original daily hygiene flow (Telegram-only, no PR). Preserved as-is. **Independent** of the night DevOps agent below. |
| `hygiene-followup-daily.yml` | cron | Hygiene follow-up resolver. Not part of the night agent pipeline. |

---

## Nighttime DevOps Agent (Wave B5)

Single source of truth: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md`.

Five workflows run sequentially every night, all sharing `concurrency.group: night-devops` so they queue strictly in order even if a predecessor overruns. Each has `timeout-minutes: 20`. Failure of any step triggers a Telegram alert to `@wookiee_alerts_bot` (chat id `HYGIENE_TELEGRAM_CHAT_ID`).

| File | Cron (UTC) | Skill it invokes | What it produces |
|---|---|---|---|
| `hygiene-scan.yml` | `0 3 * * *` (03:00) | `python -m scripts.nightly.hygiene_scan` | `.hygiene/reports/hygiene-YYYY-MM-DD.{json,md}` (workflow artifact, 30-day retention) + optional Cloudflare Pages publish. Does **not** open a PR. |
| `code-quality-scan.yml` | `30 3 * * *` (03:30) | `/code-quality-scan --json-output` | `.hygiene/reports/code-quality-YYYY-MM-DD.json` + `.hygiene/codex_logs/`. Does **not** open a PR. |
| `night-coordinator.yml` | `0 4 * * *` (04:00) | `/night-coordinator` | **The only workflow that opens a PR.** Merges all SAFE findings into a single branch `night-devops/YYYY-MM-DD`, runs `gh pr create` + `gh pr merge --auto`. NEEDS_HUMAN items go to `.hygiene/queue.yaml` + a Telegram digest in plain Russian. |
| `test-coverage-check.yml` | `30 4 * * *` (04:30) | `/test-coverage-check --json-output` | Coverage gate — fails the job (and labels the night PR `do-not-merge`) if coverage drops below `.hygiene/config.yaml: coverage_min_pct`. |
| `heartbeat.yml` | `0 5 * * *` (05:00) | `/heartbeat` | One short Telegram summary. Quiet if zero activity (`heartbeat_quiet_if_zero: true`). |

### Rollback verification

`rollback-test.yml` runs **weekly** (cron `0 6 * * 0`, Sundays 06:00 UTC). It picks the 3 most recent rows from the Supabase `fix_log` table (migration `database/migrations/031_fix_log.sql`), simulates `git revert` in a throwaway branch, runs CI against the reverted tree, and alerts via Telegram if any rollback fails. This is the contract behind "every night-agent fix is one command away from being undone".

### Concurrency model

```
03:00 hygiene-scan ─┐
03:30 code-quality ─┤
04:00 coordinator  ─┤  group: night-devops, cancel-in-progress: false
04:30 coverage     ─┤  → strict FIFO, no overlap
05:00 heartbeat    ─┘
06:00 Sun rollback ─→  (same group, still queues behind any unfinished night run)
```

If the 03:00 scan overruns past 03:30, the 03:30 job waits. Nothing is cancelled — we'd rather see the full report 30 minutes late than half a report on time.

### Read-only mode (first week of life)

`.hygiene/config.yaml: read_only: true` (default after first deploy). In this mode `night-coordinator` builds the PR plan and renders the Telegram digest but does **not** call `gh pr create`. It only commits the JSON reports to a `night-devops/reports-only-YYYY-MM-DD` branch. The owner flips `read_only: false` manually after seven nights of calibration.

### Kill switches

| Severity | Action |
|---|---|
| Soft stop | `.hygiene/config.yaml: read_only: true` — PRs paused, JSON still produced |
| Per-workflow stop | GitHub UI → workflow → "Disable workflow" |
| Hard stop | Remove the `schedule:` block from the affected `.yml` (PR through the normal flow, Workflow Guard applies) |
| Full removal | Revert this PR |

### Required GitHub Secrets

The five workflows + rollback-test require these secrets to be configured at the repo level:

| Secret | Used by | Purpose |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | all 5 night workflows | Subscription auth for `anthropics/claude-code-action@v1` (see `feedback_subscription_over_api.md`) |
| `GITHUB_TOKEN` | all 6 (provided automatically) | Checkout + `gh pr create/merge` in coordinator |
| `TELEGRAM_ALERTS_BOT_TOKEN` | all 6 | `@wookiee_alerts_bot` bot token for digests and alerts |
| `HYGIENE_TELEGRAM_CHAT_ID` | all 6 | Destination chat id |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | hygiene, code-quality, coordinator, coverage, heartbeat, rollback-test | Supabase access for `fix_log` writes/reads and analytics queries |
| `CLOUDFLARE_API_TOKEN`, `CF_ACCOUNT_ID` | hygiene-scan, hygiene-daily | Wrangler / cloudflare-pub for the public hygiene report. The JSON artifact is still uploaded if Cloudflare credentials are missing. |
| `CODEX_AUTH_JSON` | code-quality-scan (Phase 2) | Contents of `~/.codex/auth.json` — Codex CLI OAuth, written into the runner before `codex exec` calls. Optional until Wave D is built. |

### Workflow Guard interaction

The ruleset (`12853246`) still applies: PR required, quality CI required, linear history required. The night coordinator works **with** the ruleset, not around it — it uses `gh pr create` and `gh pr merge --auto`, never `--admin`, never force-push, never `--no-verify`. See `project_workflow_guard.md`.

**Known concern:** if the ruleset blocks pushes from `GITHUB_TOKEN`-authenticated bot identities (some configurations of "Restrict who can push to matching branches" cover bots), the coordinator will fail at the push step. Mitigation: the coordinator pushes only to `night-devops/*` branches, never to `main`. If the ruleset's branch-protection allow-list excludes bot pushes to feature branches, the owner needs to add `github-actions[bot]` (or a dedicated bot account) to the ruleset bypass list, OR switch the coordinator to use a PAT with `repo` scope via a new secret `NIGHT_DEVOPS_PAT`.

---

## Adding a new workflow

1. Pick a clear filename matching the dominant verb (`*-scan.yml`, `*-check.yml`, `*-deploy.yml`).
2. Set `timeout-minutes` realistically — never unlimited.
3. If the workflow can collide with the night agent (e.g. anything that pushes), set `concurrency.group: night-devops`. Otherwise pick a workflow-specific group.
4. Add a Telegram-alert step gated on `if: failure()`. Silent failures are forbidden.
5. Document the workflow in the table above.
