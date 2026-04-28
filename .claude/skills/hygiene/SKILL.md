---
name: hygiene
description: "Daily repo hygiene — push ready work, delete garbage, sync skills cross-platform, security tripwire. Сообщения в общий @wookiee_alerts_bot (TELEGRAM_ALERTS_BOT_TOKEN), только при ask-user/security. Cloudflare report every run. GitHub Actions cron 00:00 São Paulo. Triggers: /hygiene, проверь репо, hygiene check."
triggers:
  - /hygiene
  - проверь репо
  - hygiene check
metadata:
  category: infra
  version: 1.1.0
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
- Required env vars present **either in shell environment OR in `.env`**: `TELEGRAM_ALERTS_BOT_TOKEN` (общий бот системных уведомлений), `HYGIENE_TELEGRAM_CHAT_ID`, `CLOUDFLARE_API_TOKEN`, `POSTGRES_*` (Supabase). On GitHub Actions runner only shell env is set (no `.env` file) — that's expected, do **not** abort if `.env` is missing as long as the variables are exported.
- Branch `main` is reachable (`git fetch origin main` works).

**Concrete check (use this exact logic, do not invent your own):**
```bash
for var in TELEGRAM_ALERTS_BOT_TOKEN HYGIENE_TELEGRAM_CHAT_ID CLOUDFLARE_API_TOKEN; do
  if [ -z "${!var}" ]; then
    # not in shell env — try .env (local dev path)
    if [ -f .env ] && grep -q "^${var}=" .env; then
      export "${var}=$(grep "^${var}=" .env | head -1 | cut -d= -f2-)"
    else
      echo "ABORT: $var not in shell env and not in .env" >&2
      exit 1
    fi
  fi
done
```

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
# Use $RUN_ID for branch name to avoid collisions across same-day runs.
git checkout -b "chore/hygiene-$RUN_ID"
```

**Defensive guard — MUST run before every commit:** verify each path is allowed.

```bash
# Build a regex from config: protected_zones (deny) + per-check whitelist (allow).
# A path passes only if it does NOT match any protected_zone glob AND
# (for unpushed-work specifically) DOES match whitelist.unpushed_paths.
guard_path() {
  local path="$1" check="$2"
  for proto in shared/ sku_database/ .env services/*/data/ .github/workflows/ .claude/skills/hygiene/ .claude/hygiene-config.yaml; do
    case "$path" in $proto*) echo "BLOCKED: $path matches protected_zone $proto" >&2; return 1;; esac
  done
  if [ "$check" = "unpushed-work" ]; then
    case "$path" in
      docs/superpowers/plans/*|docs/superpowers/specs/*|docs/skills/*|docs/database/*) ;;
      *) echo "BLOCKED: $path not in whitelist.unpushed_paths" >&2; return 1;;
    esac
  fi
  return 0
}
```

For each finding in `auto`:
- Run `guard_path <each-path> <check>` — if any fails, drop that finding from auto, move to ask bucket with reason `protected_zone_or_not_whitelisted`.
- Apply the suggested action (delete file, `git rm`, `git add` to gitignore, etc.) ONLY for paths that passed the guard.
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
For each security finding, send Telegram alert NOW. Сообщение — на простом русском, по шаблону из `prompts/publish.md → Алерт о подозрительном файле`. Никогда не включать само значение секрета — только путь и человекочитаемую причину.

```bash
SECURITY_MSG="🚨 Hygiene нашёл подозрительный файл в репозитории Wookiee.

Файл: $path
Что не так: $reason_human

Глянь и убери, если это реальный секрет. Само содержимое не присылаю — оно может быть опасным."
curl -sf -X POST "https://api.telegram.org/bot$TELEGRAM_ALERTS_BOT_TOKEN/sendMessage" \
  -d "chat_id=$HYGIENE_TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$SECURITY_MSG"
```

`$reason_human` — это `reason` из finding, переписанный по-человечески (например, `"похоже на API-ключ"`, `"в трекинге .env"`, `"в .env.example лежит реальное значение"`).

After security alerts, continue to Phase 4 (PR still opens for non-security findings).

## Phase 4 — PR / Issue

Three sub-cases based on bucket sizes:

### 4a. Both auto and ask buckets empty
Skip entirely. Continue to Phase 5.

### 4b. Auto bucket has commits (regardless of ask bucket)
Auto-fixes were committed on `chore/hygiene-$RUN_ID` in Phase 3a. Now:
1. Push the branch: `git push -u origin "chore/hygiene-$RUN_ID"`.
2. Build PR body from `/tmp/hygiene-followup-<run_id>.md` + summary of auto-fixed groups.
3. Invoke the `pullrequest` skill (project version):
   - **Use `wait` mode if `ask_count > 0`** — user must merge manually.
   - **Default (auto-merge) only if `ask_count = 0` AND CI checks pass.** Before merging, poll `gh pr checks <pr_number>` until all required checks report `success`. If any check is `failure` / `cancelled` / `pending` >10min → switch to `wait` mode and notify user.
   - Never auto-merge if hygiene PR touched anything outside the auto bucket's expected blast radius (sanity check: `git diff main..HEAD --name-only` should match files referenced in `auto` findings only).

PR title: `chore(hygiene): {auto_count} auto-fixed, {ask_count} need review — {YYYY-MM-DD}`.

### 4c. Auto bucket empty BUT ask bucket has findings
Branch has no commits, so a PR cannot be opened. Open a GitHub issue instead — that way ask findings stay discoverable on the project board:

```bash
gh issue create \
  --title "hygiene followups — $(date -u +%Y-%m-%d)" \
  --label "hygiene,followup" \
  --body-file /tmp/hygiene-followup-$RUN_ID.md
```

Capture the issue URL → save as `PR_URL` for Phase 6/7 logging (the field name stays `pr_url` for schema stability; downstream consumers should treat it as "discussion URL"). Mention in NOTIFY message that this is an issue, not a PR.

If `gh issue create` fails or `gh` not available → fall back to listing followups in the Cloudflare report only (Phase 5 already covers this).

## Phase 5 — PUBLISH (always)

Render `prompts/publish.md` with run data → markdown.

Use the **project-level** `cloudflare-pub` skill (`.claude/skills/cloudflare-pub/`) so this works on GitHub Actions runners (where `~/.claude/skills/` is empty):

```bash
PUBLISH_SCRIPT=".claude/skills/cloudflare-pub/scripts/publish.py"
# Local-dev fallback if run from outside repo root:
[ ! -f "$PUBLISH_SCRIPT" ] && PUBLISH_SCRIPT="$HOME/.claude/skills/cloudflare-pub/scripts/publish.py"

python3 "$PUBLISH_SCRIPT" \
  /tmp/hygiene-report-$RUN_ID.md \
  --name "wookiee-hygiene-$RUN_DATE" \
  --title "Wookiee Hygiene Run $RUN_DATE"
```

Capture the Permanent URL from output → save as `CLOUDFLARE_URL` for Phase 6 + 7.

## Phase 6 — NOTIFY

Skip if `ask_count = 0 AND security_count = 0`. (Security already sent in 3c.)

Otherwise — собрать сообщение по шаблону «Сводка по итогам уборки» из `prompts/publish.md`. Числа выводить словами для согласованности (один файл / два файла / пять файлов / одну ветку / две ветки).

Псевдокод:

```bash
# Соберите $MSG_BODY из шаблона «Сводка» в prompts/publish.md.
# Строки выводите только если соответствующий счётчик > 0.

MSG="🧹 Hygiene убрался в репозитории Wookiee.

${LINE_AUTO}${LINE_ASK}${LINE_SECURITY}
Полный отчёт: ${CLOUDFLARE_URL}${LINE_PR}"

curl -sf -X POST "https://api.telegram.org/bot$TELEGRAM_ALERTS_BOT_TOKEN/sendMessage" \
  -d "chat_id=$HYGIENE_TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$MSG"
```

Никаких английских лейблов (`Auto-fixed:`, `Needs review:`), никаких таблиц, никаких `RUN_ID` — Telegram это не рендерит, читателю выглядит как мусор.

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

Set `STATUS=success` if all phases completed (record warnings in `details.warnings`).
Set `STATUS=timeout` if hygiene hit the 30-min wall-clock or 1-2 checks exceeded their 60s budget.
Set `STATUS=error` if hygiene aborted before Phase 5 (precondition fail, hard-cap hit, unrecoverable error).

Allowed `tool_runs.status` values (DB CHECK constraint): `running | success | error | timeout | data_not_ready`. Do NOT use `partial` or `failed` — they will fail the constraint.

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
