---
name: hygiene
description: "Daily repo hygiene — push ready work, delete garbage, sync skills cross-platform, security tripwire. Reuse @matveevos_head_bot for Telegram alerts (only on ask-user/security). Cloudflare report every run. Designed for GitHub Actions cron at 00:00 São Paulo. Triggers: /hygiene, проверь репо, hygiene check."
triggers:
  - /hygiene
  - проверь репо
  - hygiene check
metadata:
  category: infra
  version: 1.0.0
  owner: danila
---

# Hygiene Skill

Single-pass repo maintenance routine. Spec: `docs/superpowers/specs/2026-04-27-hygiene-skill-design.md`.

## Quick start

```
/hygiene                    # full run (default)
/hygiene --dry-run          # scan only, classify, output report — no commits, no PR, no notifications
/hygiene --check <name>     # run only one check (e.g. --check security-scan)
```

## Pre-conditions (skill aborts if missing)

- Repo working directory clean OR all uncommitted changes are inside whitelisted `unpushed_paths` (see config).
- `.env` contains `TELEGRAM_MANAGER_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`, `CLOUDFLARE_API_TOKEN`, `POSTGRES_*` (Supabase).
- Branch `main` is reachable (`git fetch origin main` works).

If preconditions fail, the skill emits a single error message + Telegram alert (treated as `security_count=0, ask_count=0, error=1`), and exits.

## 7-Phase Flow

```
1. SCAN        → read prompts/detect.md, run all check commands, build findings JSON
2. CLASSIFY    → read prompts/classify.md, apply config defaults to each finding
3. ACT         → 3 parallel buckets:
   ├─ auto-fix     → git checkout -b chore/hygiene-YYYY-MM-DD, commit per group
   ├─ ask-user     → accumulate findings + rationale into PR description
   └─ security     → IMMEDIATELY send Telegram alert (don't wait for full run)
4. PR          → /pullrequest (auto-merge default; "wait" mode if --interactive)
5. PUBLISH     → /cloudflare-pub: render prompts/publish.md → Cloudflare Pages article
6. NOTIFY      → if ask_count > 0 OR security_count > 0: send Telegram message
7. LOG         → write tool_runs row via shared/tool_logger
```

## Phase 1 — SCAN

Open `prompts/detect.md`. For every check listed there:
1. Run the listed Bash commands.
2. Build a finding object: `{check, severity, paths[], reason, suggested_action, evidence}`.
3. Append to `/tmp/hygiene-findings-<run_id>.json` (one JSON per line, `jsonl` style).

Use a single `RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)` for all artefacts in this run.

**Hard limit:** if any single command runs longer than 60 s, kill it and record `severity=skipped, reason="timeout"`. Do not let one slow check block the routine.

## Phase 2 — CLASSIFY

Read `.claude/hygiene-config.yaml` once (parse YAML).

For each finding from Phase 1:
- Look up `checks.<name>.default` in config → `auto_fix | auto_delete | auto_commit_push | auto_untrack | auto_ignore | auto_sync | mixed | ask_user | flag_immediate | skip`.
- Apply the rules in `prompts/classify.md` (config defaults can be overridden by classify rules for edge cases).
- Tag the finding `bucket = auto | ask | security | skip`.

If `bucket=security` for ANY finding → fork an immediate Telegram task **before** continuing to Phase 3 (do not wait for the full run).

## Phase 3 — ACT

### 3a. auto bucket
```bash
RUN_DATE=$(date -u +%Y-%m-%d)
git checkout -b "chore/hygiene-$RUN_DATE" 2>/dev/null || git checkout "chore/hygiene-$RUN_DATE"
```

For each finding in `auto`:
- Apply the suggested action (delete file, `git rm`, `git add` to gitignore, etc.).
- Group by check name.
- One commit per group: `chore(hygiene): <check> — <count> items`.

If `auto` bucket is empty AND `ask` bucket is empty AND `security` bucket is empty → skip Phase 3-4-6 (clean run); still do Phase 5 + 7.

### 3b. ask bucket
Build a markdown section that will land in the PR description:

```
## FOLLOW-UP NEEDED — review before merge

<for each ask finding>
### <check>: <short label>
- Paths: <list>
- Reason: <reason>
- Suggested action: <suggested_action>
- Evidence: <evidence>
</for each>
```

Save to `/tmp/hygiene-followup-<run_id>.md` for Phase 4.

### 3c. security bucket — IMMEDIATE
For each security finding, send Telegram alert NOW:

```bash
SECURITY_MSG="🚨 Wookiee Hygiene SECURITY [$RUN_DATE]
Check: $check
Path: $path
Reason: $reason
Action required: review immediately."
curl -sf -X POST "https://api.telegram.org/bot$TELEGRAM_MANAGER_BOT_TOKEN/sendMessage" \
  -d "chat_id=$HYGIENE_TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$SECURITY_MSG"
```

Do NOT include the leaked secret value in the message — only the path and reason.

After security alerts, continue to Phase 4 (PR still opens for non-security findings).

## Phase 4 — PR

If both `auto` and `ask` buckets are empty: skip this phase entirely.

Otherwise:
1. Push the branch: `git push -u origin "chore/hygiene-$RUN_DATE"`.
2. Build PR body from `/tmp/hygiene-followup-<run_id>.md` + summary of auto-fixed groups.
3. Invoke the `pullrequest` skill (project version) — auto-merge if no findings need user review; `wait` mode if `ask_count > 0`.

PR title: `chore(hygiene): {auto_count} auto-fixed, {ask_count} need review — {YYYY-MM-DD}`.

## Phase 5 — PUBLISH (always)

Render `prompts/publish.md` with run data → markdown.
Invoke `cloudflare-pub` skill:

```bash
python3 ~/.claude/skills/cloudflare-pub/scripts/publish.py \
  /tmp/hygiene-report-$RUN_ID.md \
  --name "wookiee-hygiene-$RUN_DATE" \
  --title "Wookiee Hygiene Run $RUN_DATE"
```

Capture the Permanent URL from output → save as `CLOUDFLARE_URL` for Phase 6 + 7.

## Phase 6 — NOTIFY

Skip if `ask_count = 0 AND security_count = 0`. (Security already sent in 3c.)

Otherwise:
```bash
MSG="🧹 Wookiee Hygiene $RUN_DATE
Auto-fixed: $auto_count
Needs review: $ask_count
Security flags: $security_count

Full report: $CLOUDFLARE_URL
PR: $PR_URL"

curl -sf -X POST "https://api.telegram.org/bot$TELEGRAM_MANAGER_BOT_TOKEN/sendMessage" \
  -d "chat_id=$HYGIENE_TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$MSG"
```

## Phase 7 — LOG

```python
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
import os, json
log = ToolLogger('hygiene')
run_id = log.start(trigger=os.getenv('HYGIENE_TRIGGER', 'manual'), version='1.0.0', environment=os.getenv('HYGIENE_ENV', 'local'))
log.finish(run_id, status='${STATUS}', result_url='${CLOUDFLARE_URL}', details=json.dumps({
  'auto_count': ${AUTO_COUNT},
  'ask_count': ${ASK_COUNT},
  'security_count': ${SECURITY_COUNT},
  'pr_url': '${PR_URL}',
  'duration_seconds': ${DURATION},
}))
"
```

Set `STATUS=success` if all phases completed, `partial` if any check timed out or 1-2 phases failed, `failed` if hygiene aborted before Phase 5.

## Hard rules — DO NOT VIOLATE

These come from the spec and the project's `AGENTS.md`. Violating them = abort, no PR, Telegram alert.

- NEVER write to: `shared/**`, `sku_database/**`, `.env*`, `services/*/data/**`, `.github/workflows/**`.
- NEVER use: `git push --force`, `git reset --hard`, `gh pr close <other-PR>`, `rm -rf <tracked-file>` without explicit whitelist.
- NEVER include secret values in any output (Cloudflare, Telegram, PR description, logs).
- NEVER auto-fix items in `bucket=ask` — only the user merges those after review.
- NEVER modify branch protection / GitHub repo settings.

## Cost guardrails

From `hygiene-config.yaml.cost_caps`:
- Soft cap (default 50k tokens): log a warning into the Cloudflare report, continue.
- Hard cap (default 150k tokens): abort, partial PR with what's been done, Telegram alert: "hygiene aborted, hard cap hit".

The runner (GitHub Actions) enforces a 30-minute wall-clock job timeout regardless.

## See also

- `prompts/detect.md` — exact scan commands per check.
- `prompts/classify.md` — full classification rules.
- `prompts/publish.md` — Cloudflare + Telegram templates.
- `.claude/hygiene-config.yaml` — config (cron, whitelist, per-check defaults).
- `.github/workflows/hygiene-daily.yml` — production runner.
- `docs/superpowers/specs/2026-04-27-hygiene-skill-design.md` — full design rationale.
