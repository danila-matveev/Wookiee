---
name: hygiene-autofix
description: "Daily companion to /hygiene. Reads the freshly-opened hygiene PR, verifies each ask_user finding with project context (grep, refactor-audit notes, filesystem checks), applies SAFE fixes by pushing commits to the same PR branch, leaves UNSAFE/AMBIGUOUS findings for human review with a comment. Triggers: /hygiene-autofix."
triggers:
  - /hygiene-autofix
metadata:
  category: infra
  version: 1.0.0
  owner: danila
---

# Hygiene Autofix Skill

Companion to `/hygiene`. Where /hygiene is the **detector**, this skill is the **fixer with project context**.

## Why this exists

`/hygiene` parks judgment-heavy findings in the `ask_user` bucket — they go into the PR description as "FOLLOW-UP NEEDED". Each finding requires LLM verification (grep refs, read refactor-audit notes, check filesystem) before it's safe to fix. This skill does that verification daily, applies the safe ones, and leaves the rest with a human-readable comment.

**Hard separation of concerns:**

- `/hygiene` finds, classifies, opens PR with auto-fixes + ask findings → DOES NOT touch ask findings
- `/hygiene-autofix` (this skill) reads ask findings → verifies → applies SAFE fixes to same PR
- Future `/hygiene-merge` (Phase 1 from autopilot plan) → tier-classify + auto-merge tier:1 PRs

Three skills, three responsibilities. Don't merge them.

## Quick start

```
/hygiene-autofix              # full run on today's hygiene PR
/hygiene-autofix --dry-run    # report what would be fixed, don't push
/hygiene-autofix --pr <N>     # target specific PR (overrides discovery)
```

## Pre-conditions (skill aborts if missing)

- Required env vars in shell or `.env`: `TELEGRAM_ALERTS_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`, `GH_TOKEN`.
- `gh` CLI authenticated.
- Working tree clean (no uncommitted changes that would block branch checkout).

Use the same precondition pattern as `/hygiene` (see its SKILL.md). Do NOT add format/placeholder validation of tokens.

## 6-Phase Flow

```
1. DISCOVER     → find today's hygiene PR (open, label "hygiene", branch chore/hygiene-*)
2. PARSE        → extract ask_user findings from PR description
3. VERIFY       → for each finding, classify SAFE | UNSAFE | NEEDS_HUMAN per prompts/verify.md
4. ACT          → checkout PR branch, apply SAFE fixes, group commits per check
5. REPORT       → push to same branch, comment on PR with summary
6. NOTIFY+LOG   → Telegram alert if N>0 fixes applied; log to tool_runs
```

## Phase 1 — DISCOVER

Find the hygiene PR opened in the last 24 hours.

```bash
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)

# Find candidate PRs: branch starts with chore/hygiene-, opened today, state OPEN.
PR_NUMBER=$(gh pr list --state open --json number,headRefName,createdAt \
  --jq '[.[] | select(.headRefName | startswith("chore/hygiene-"))] | sort_by(.createdAt) | last | .number')

if [ -z "$PR_NUMBER" ] || [ "$PR_NUMBER" = "null" ]; then
  echo "No open hygiene PR found — nothing to fix today."
  # This is OK, not an error. Hygiene may have produced a clean run.
  # Log status=success with details.skipped="no_open_hygiene_pr" and exit.
  exit 0
fi
```

If `--pr <N>` flag passed, use that instead of discovery.

## Phase 2 — PARSE

Read PR description, extract ask findings from the `## FOLLOW-UP NEEDED` section.

```bash
gh pr view "$PR_NUMBER" --json body --jq '.body' > /tmp/hygiene-autofix-body-$RUN_ID.md
```

Parse the body. Each finding looks like:

```markdown
### <check>: <short label>
- Paths: <list>
- Reason: <reason>
- Suggested action: <suggested_action>
- Evidence: <evidence>
```

Build an array of finding objects:
```json
{"check": "...", "label": "...", "paths": [...], "reason": "...", "suggested_action": "...", "evidence": "..."}
```

If no `## FOLLOW-UP NEEDED` section found → exit 0 (PR has only auto-fixes).

## Phase 3 — VERIFY

For each finding, apply rules from `prompts/verify.md` to classify:
- `SAFE` — verified safe to fix automatically. Action is well-defined and reversible.
- `UNSAFE` — verification revealed risk (e.g., file IS used dynamically). Skip and comment.
- `NEEDS_HUMAN` — judgment call beyond autofix scope (e.g., new README content). Skip and comment.

**Limit:** ≤10 findings classified as SAFE per run. Process the rest as NEEDS_HUMAN with reason `"daily_quota_exceeded"` to avoid runaway sessions. Tomorrow's run will pick up where this one left off.

Save classified findings to `/tmp/hygiene-autofix-classified-$RUN_ID.jsonl`.

## Phase 4 — ACT

```bash
PR_BRANCH=$(gh pr view "$PR_NUMBER" --json headRefName --jq '.headRefName')
git fetch origin "$PR_BRANCH"
git checkout "$PR_BRANCH"
```

**Defensive guard — MUST run before every commit:** verify each path is allowed.

```bash
guard_path() {
  local path="$1"
  for proto in shared/ database/sku/ .env services/*/data/ .github/workflows/ .claude/skills/hygiene/ .claude/skills/hygiene-autofix/ .claude/hygiene-config.yaml; do
    case "$path" in $proto*) echo "BLOCKED: $path matches protected_zone $proto" >&2; return 1;; esac
  done
  return 0
}
```

For each SAFE finding, group by check name, run the action defined in `prompts/verify.md`, one commit per group:

```bash
git commit -m "chore(hygiene-autofix): <check> — <count> items"
```

If `guard_path` fails for any path in the action → demote that finding to UNSAFE, drop from this run's commit set.

**Never** force-push, `--no-verify`, `git rebase`, `git reset --hard`, or any history rewrite. Only `git commit` + `git push`.

## Phase 5 — REPORT

```bash
git push origin "$PR_BRANCH"
```

Comment on PR with structured summary:

```markdown
## 🔧 Hygiene Autofix run — <YYYY-MM-DD HH:MM UTC>

**Applied (<N> commits):**
- ✅ <check>: <short description> — <count> items
- ✅ ...

**Skipped — needs human review (<M>):**
- ⏸️ <check>: <short label> — reason: <unsafe/needs_human/quota>

**Verification details:** see commit messages.
```

If 0 SAFE findings → comment with `## ℹ️ Autofix scanned X findings — all need human review` listing skipped items.

## Phase 6 — NOTIFY + LOG

If `applied_count > 0`:

```bash
MSG="🔧 Hygiene Autofix — $RUN_DATE
Починил: $applied_count пунктов из $total_count
Оставил человеку: $skipped_count
PR: https://github.com/danila-matveev/Wookiee/pull/$PR_NUMBER"

curl -sf -X POST "https://api.telegram.org/bot$TELEGRAM_ALERTS_BOT_TOKEN/sendMessage" \
  -d "chat_id=$HYGIENE_TELEGRAM_CHAT_ID" \
  --data-urlencode "text=$MSG"
```

If `applied_count == 0` and `skipped_count > 0` → no Telegram (avoid noise; comment on PR is enough).

Log to `tool_runs`:

```python
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
import os, json
log = ToolLogger('hygiene-autofix')
run_id = log.start(trigger=os.getenv('HYGIENE_TRIGGER', 'cron'), version='1.0.0', environment=os.getenv('HYGIENE_ENV', 'production'))
log.finish(run_id, status='${STATUS}', result_url='https://github.com/danila-matveev/Wookiee/pull/${PR_NUMBER}', details=json.dumps({
  'pr_number': ${PR_NUMBER},
  'total_findings': ${TOTAL_COUNT},
  'applied_count': ${APPLIED_COUNT},
  'skipped_count': ${SKIPPED_COUNT},
  'duration_seconds': ${DURATION},
}))
"
```

## Hard rules — DO NOT VIOLATE

1. **NEVER write to:** `shared/**`, `database/sku/**`, `.env*`, `services/*/data/**`, `.github/workflows/**`, `.claude/skills/hygiene/**`, `.claude/skills/hygiene-autofix/**`, `.claude/hygiene-config.yaml`.
2. **NEVER use:** `git push --force`, `--no-verify`, `git reset --hard`, `gh pr merge`, `gh pr close`.
3. **NEVER apply a fix on a finding the verifier classified as UNSAFE or NEEDS_HUMAN** — even if it looks tempting. Human reviews those.
4. **NEVER include secrets in comments, commits, Telegram, or logs.**
5. **NEVER process more than 10 SAFE findings per run.** Hard stop. Tomorrow's run will continue.
6. **NEVER expand the SAFE classification rules.** Editing `prompts/verify.md` requires human PR (this directory is in protected_zones).

## Cost guardrails

- Soft cap: 50K tokens — log warning, continue.
- Hard cap: 100K tokens — abort with partial results, Telegram alert "autofix aborted, hard cap hit".
- Wall clock: 20 min via GH Actions job timeout.

## See also

- `prompts/system.md` — operating principles + decision tree.
- `prompts/verify.md` — per-check verification rules and SAFE actions.
- `.github/workflows/hygiene-autofix.yml` — production runner.
- `docs/superpowers/plans/2026-05-09-hygiene-autopilot.md` — full autopilot vision (Phases 1+2+3).
- `.claude/skills/hygiene/SKILL.md` — companion detector skill.
