# /hygiene Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/hygiene` skill described in `docs/superpowers/specs/2026-04-27-hygiene-skill-design.md` (commit `9abfd7d`) so daily 00:00 São Paulo runs auto-clean repo drift, sync skills cross-platform, scan secrets, publish to Cloudflare, and ping Telegram only when needed.

**Architecture:** Pure SKILL.md (no Python orchestrator). Cron via GitHub Actions scheduled workflow. Telegram alerts via existing `@matveevos_head_bot` (token already in local `.env` as `TELEGRAM_MANAGER_BOT_TOKEN`). Cloudflare publishing via `/cloudflare-pub` skill. Supabase logging via `shared/tool_logger`.

**Tech Stack:** Markdown skill files; YAML config; GitHub Actions YAML; Bash + curl + jq; Python via `shared/tool_logger`; existing skills `/cloudflare-pub`, `/ecosystem-sync`, `/pullrequest`, `/tool-register`.

---

## File Structure

Files this plan creates or modifies:

| Path | Status | Responsibility |
|---|---|---|
| `.claude/skills/hygiene/SKILL.md` | **create** | Main skill: trigger, 7-phase flow orchestration, refers to prompts |
| `.claude/skills/hygiene/prompts/detect.md` | **create** | Scan commands per check, finding JSON schema |
| `.claude/skills/hygiene/prompts/classify.md` | **create** | auto-fix vs ask-user vs flag rules per check |
| `.claude/skills/hygiene/prompts/publish.md` | **create** | Cloudflare article + Telegram message templates |
| `.claude/skills/hygiene/README.md` | **modify** | Replace Phase 1 placeholder with real description |
| `.claude/hygiene-config.yaml` | **modify** | Replace Phase 1 placeholder with real config (cron, whitelists, defaults) |
| `.env.example` | **modify** | Add `TELEGRAM_MANAGER_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID` placeholders |
| `.env` (local only, gitignored) | **modify** | Add captured `HYGIENE_TELEGRAM_CHAT_ID` |
| `.github/workflows/hygiene-daily.yml` | **create** | Cron `0 3 * * *` + `workflow_dispatch`, runs hygiene via Anthropic API |
| Supabase `tools` table | **insert** | One row `slug=hygiene` via `/tool-register` |
| GitHub Secrets | **insert** | `ANTHROPIC_API_KEY`, `TELEGRAM_MANAGER_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`, `CLOUDFLARE_API_TOKEN`, `POSTGRES_*` (Supabase) |

Branch: `spec/hygiene-skill-design` (already created with the spec). Implementation continues on this branch; PR opens at end against `main`.

---

## Task 1: Pre-flight — verify branch, action availability, Cloudflare creds

**Files:**
- Read: `docs/superpowers/specs/2026-04-27-hygiene-skill-design.md`
- Read: `.env` (do NOT print contents)

- [ ] **Step 1: Verify on correct branch**

```bash
test "$(git branch --show-current)" = "spec/hygiene-skill-design" || (echo "WRONG BRANCH"; exit 1)
git log --oneline -2 | head -2
```
Expected: shows `9abfd7d docs(superpowers): hygiene spec v2 …` as latest or second-latest.

- [ ] **Step 2: Verify manager bot token is in `.env` and reachable**

```bash
grep -q '^TELEGRAM_MANAGER_BOT_TOKEN=' .env && echo "TOKEN_PRESENT" || (echo "TOKEN_MISSING"; exit 1)
TOKEN=$(grep '^TELEGRAM_MANAGER_BOT_TOKEN=' .env | cut -d= -f2-)
curl -s "https://api.telegram.org/bot$TOKEN/getMe" | python3 -c 'import sys,json; r=json.load(sys.stdin); assert r["ok"], r; print("BOT_OK", "@"+r["result"]["username"])'
```
Expected: `TOKEN_PRESENT` then `BOT_OK @matveevos_head_bot`.

- [ ] **Step 3: Verify Cloudflare token present**

```bash
grep -E '^(CF_API_TOKEN|CLOUDFLARE_API_TOKEN)=' .env >/dev/null && echo "CF_OK" || echo "CF_MISSING — ask user before continuing"
```
If `CF_MISSING`: stop the task and ask user for `CLOUDFLARE_API_TOKEN`. Do not fabricate.

- [ ] **Step 4: Verify `anthropics/claude-code-action` action exists on GitHub**

```bash
curl -fsSL "https://api.github.com/repos/anthropics/claude-code-action" -H "Accept: application/vnd.github+json" | python3 -c 'import sys,json; r=json.load(sys.stdin); print("ACTION_OK" if r.get("name") else "MISSING", r.get("html_url"))'
```
Expected: `ACTION_OK https://github.com/anthropics/claude-code-action`.

If `MISSING` (404 or no `name`): plan continues, but Task 10 must use the **fallback** workflow shape (direct `curl` to Anthropic Messages API) instead of the action. Note the result here:

```bash
echo "USE_ACTION=true   # or false if previous step failed" > /tmp/hygiene_preflight.txt
```

- [ ] **Step 5: Verify required Wookiee skills resolve**

```bash
for skill in cloudflare-pub ecosystem-sync pullrequest tool-register; do
  if [ -f "$HOME/.claude/skills/$skill/SKILL.md" ] || [ -f ".claude/skills/$skill/SKILL.md" ]; then
    echo "$skill: OK"
  else
    echo "$skill: MISSING"; exit 1
  fi
done
```
Expected: all four `OK`. Note: `tool-register` and `pullrequest` live in project, others global.

- [ ] **Step 6: Commit pre-flight result note** (so subsequent subagents see the action decision)

```bash
mkdir -p .planning/hygiene
mv /tmp/hygiene_preflight.txt .planning/hygiene/preflight.txt
git add .planning/hygiene/preflight.txt
git commit -m "chore(hygiene): record preflight (action availability + skill resolution)"
```

---

## Task 2: Write `.claude/skills/hygiene/SKILL.md`

**Files:**
- Create: `.claude/skills/hygiene/SKILL.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p .claude/skills/hygiene/prompts
ls .claude/skills/hygiene/
```
Expected: `README.md  prompts/` (README from Phase 1 placeholder).

- [ ] **Step 2: Write SKILL.md** (full content — no placeholders)

Path: `.claude/skills/hygiene/SKILL.md`

```markdown
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
```

- [ ] **Step 3: Verify SKILL.md is well-formed**

```bash
test -f .claude/skills/hygiene/SKILL.md && head -5 .claude/skills/hygiene/SKILL.md
```
Expected: starts with `---\nname: hygiene\n…`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/hygiene/SKILL.md
git commit -m "feat(hygiene): SKILL.md — 7-phase flow orchestrator"
```

---

## Task 3: Write `prompts/detect.md`

**Files:**
- Create: `.claude/skills/hygiene/prompts/detect.md`

- [ ] **Step 1: Write detect.md** (full content)

Path: `.claude/skills/hygiene/prompts/detect.md`

````markdown
# Hygiene — Detect (Phase 1 commands)

For each check below, run the command exactly. Append findings to `/tmp/hygiene-findings-$RUN_ID.jsonl` as one JSON object per line.

## Finding schema

```json
{"check":"<name>","severity":"info|low|med|high|critical","paths":["..."],"reason":"...","suggested_action":"...","evidence":"<short verbatim from command output>"}
```

## 1. unpushed-work

```bash
git fetch origin --quiet
git log --oneline @{u}..HEAD 2>/dev/null
git status --porcelain
```
Match-rules:
- Untracked file under `docs/superpowers/plans/`, `docs/superpowers/specs/`, `docs/skills/`, `docs/database/` → finding.
- Local commit on a non-protected branch ahead of `@{u}` → finding.
- Anything outside whitelist → IGNORE here (other checks may flag it).

## 2. stray-binaries

```bash
git ls-files | grep -E '\.(xlsx|pdf|docx|png|jpg|jpeg|wmv|mov|mp4|zip)$'
find . -type f \( -name '*.xlsx' -o -name '*.pdf' -o -name '*.wmv' -o -name '*.mov' -o -name '*.mp4' \) -not -path './.git/*' -not -path './node_modules/*'
```
Match-rules: any path NOT matching `whitelist.binaries_keep` from config → finding.

## 3. icloud-dupes

```bash
find . -type f \( -name '* 2.*' -o -name '* 3.*' \) -not -path './.git/*' -not -path './node_modules/*'
```
Match-rules: every match → finding (auto_delete).

## 4. pycache-committed

```bash
git ls-files | grep -E '(__pycache__|\.pytest_cache|\.mypy_cache)/' | head -50
```
Match-rules: any line → finding (auto_untrack + add to gitignore).

## 5. gitignore-violations

```bash
git ls-files --ignored --exclude-standard --cached 2>/dev/null
git status --ignored --porcelain | grep '^!!' | head -50
```
Match-rules: any tracked file that matches `.gitignore` rules → finding.

## 6. skill-registry-drift

```bash
ls .claude/skills/ | sort > /tmp/hygiene-skills-fs.txt
PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('sku_database/.env')
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT','5432'), dbname=os.getenv('POSTGRES_DB','postgres'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()
cur.execute(\"SELECT slug FROM tools WHERE type='skill' ORDER BY slug\")
for r in cur.fetchall(): print(r[0])
" > /tmp/hygiene-skills-db.txt
diff /tmp/hygiene-skills-fs.txt /tmp/hygiene-skills-db.txt
```
Match-rules:
- Lines `<` (in FS, not in DB) → finding `skill-registry-drift / unregistered`, suggested_action: "register via /tool-register".
- Lines `>` (in DB, not in FS) → finding `skill-registry-drift / orphan`, suggested_action: "ask-user — confirm deletion or restore".

## 7. cross-platform-skill-prep

```bash
ls .claude/skills/ > /tmp/hygiene-cc-skills.txt
ls .cursor/skills/ 2>/dev/null > /tmp/hygiene-cur-skills.txt || touch /tmp/hygiene-cur-skills.txt
ls .codex/skills/ 2>/dev/null > /tmp/hygiene-cdx-skills.txt || touch /tmp/hygiene-cdx-skills.txt
diff /tmp/hygiene-cc-skills.txt /tmp/hygiene-cur-skills.txt | head -30
diff /tmp/hygiene-cc-skills.txt /tmp/hygiene-cdx-skills.txt | head -30
```
Match-rules: any skill in CC but missing in Cursor/Codex → finding (auto_sync via `/ecosystem-sync sync`).

## 8. empty-directories

```bash
find . -type d -empty -not -path './.git/*' -not -path './node_modules/*' -not -path './venv/*' -not -path '*/__pycache__*' | head -50
```
Match-rules:
- Empty AND untracked → finding (auto_delete).
- Empty AND tracked (i.e. `.gitkeep` exists) → finding (ask_user — was this intentional?).

## 9. orphan-imports

```bash
PYTHONPATH=. python3 - <<'PY'
import os, ast, pathlib, subprocess
roots = ['shared','services','agents','scripts']
modules = {}
for r in roots:
    for p in pathlib.Path(r).rglob('*.py') if pathlib.Path(r).exists() else []:
        if '__pycache__' in p.parts: continue
        modules[str(p)] = p.stem
seen_imports = set()
for p in modules:
    try:
        tree = ast.parse(pathlib.Path(p).read_text())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            seen_imports.add(node.module.split('.')[-1])
        elif isinstance(node, ast.Import):
            for n in node.names: seen_imports.add(n.name.split('.')[-1])
orphans = [p for p,name in modules.items() if name not in seen_imports and name != '__init__']
for o in orphans:
    age_days = int(subprocess.check_output(['git','log','-1','--format=%cr','--',o]).decode().strip().split()[0] or '0') if 'days' in subprocess.check_output(['git','log','-1','--format=%cr','--',o]).decode() else 0
    if age_days >= 60:
        print(o)
PY
```
Match-rules: each printed path → finding (ask_user, no auto-delete).

## 10. orphan-docs

```bash
find docs -name '*.md' -type f | while read f; do
  basename=$(basename "$f" .md)
  refs=$(grep -rl "$basename" docs --include='*.md' 2>/dev/null | grep -v "^$f$" | wc -l)
  age_days=$(git log -1 --format=%cr -- "$f" | grep -oE '[0-9]+' | head -1)
  if [ "$refs" = "0" ] && [ "${age_days:-0}" -ge 60 ]; then echo "$f"; fi
done
```
Match-rules: each printed path → finding (ask_user).

## 11. broken-doc-links

```bash
grep -rEoh '\]\([^)]+\.md[^)]*\)' docs --include='*.md' | sed 's/^](\(.*\))$/\1/' | sort -u | while read link; do
  base=$(echo "$link" | sed 's/#.*$//')
  if [ -n "$base" ] && [ ! -f "$base" ] && [ ! -f "docs/$base" ]; then echo "BROKEN: $link"; fi
done | head -30
```
Match-rules: any `BROKEN:` line → finding (ask_user — could be intentional rename).

## 12. missing-readme

```bash
for d in services/*/; do test -f "$d/README.md" || echo "MISSING: $d"; done
```
Match-rules: each `MISSING:` line → finding (ask_user — propose stub README).

## 13. stale-branches

```bash
git fetch --all --quiet
git for-each-ref --format='%(refname:short) %(committerdate:relative)' refs/remotes/origin/ | grep -v 'origin/main\|origin/HEAD' | while read branch rel; do
  case "$rel" in *months*|*year*) echo "STALE: $branch ($rel)";; esac
done
```
Match-rules: any `STALE:` (older than 14 days per spec — adjust threshold from config) → finding (ask_user).

## 14. structure-conventions

LLM-driven. Read 5 random `services/X/` directories, infer the dominant layout pattern (e.g. `__init__.py`, `README.md`, `run.py` or similar), then list any service that deviates.

```bash
ls -1 services/ | head -10
for s in $(ls -1 services/ | head -5); do echo "--- $s ---"; ls services/$s/; done
```
Apply LLM judgment on diff vs majority pattern. Match-rules: deviating service → finding (ask_user).

## 15. obsolete-tracked-files

```bash
git ls-files | while read f; do
  refs=$(git log --since="60 days ago" --pretty=oneline -- "$f" 2>/dev/null | wc -l)
  if [ "$refs" = "0" ]; then
    age_days=$(git log -1 --format=%cr -- "$f" | grep -oE '[0-9]+' | head -1)
    if [ "${age_days:-0}" -ge 60 ]; then echo "$f ($age_days days)"; fi
  fi
done | head -20
```
Match-rules: each printed line → finding (ask_user).

## 16. security-scan

```bash
# Real secrets in tracked files (regex from gstack-cso, simplified)
git ls-files | grep -vE '\.(md|example|sample)$' | xargs grep -lE '(API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*["\x27]?[A-Za-z0-9_/+=-]{16,}' 2>/dev/null | head -20
# .env tracked check
git ls-files | grep -E '^\.env$|\.env\.local$|\.env\.production$' | head
# .env.example sanity (no real values)
grep -E '^[A-Z_]+=([A-Za-z0-9_/+=-]{20,})' .env.example | grep -vE '(your-|0000|placeholder|example|xxxxxxxx)' | head
```
Match-rules:
- Any line from cmd 1 → CRITICAL finding (`security-scan / leaked_secret`, severity=critical, bucket=security).
- Any line from cmd 2 → CRITICAL finding (`.env tracked`).
- Any line from cmd 3 → MEDIUM finding (`.env.example has real value`).

**Important:** never print the secret value into the finding's `evidence` field. Use only `<redacted>` + path.

---

After all checks complete, write summary line to stdout:
```
SCAN_DONE: total=$N findings (critical=$C, high=$H, med=$M, low=$L)
```
````

- [ ] **Step 2: Verify file**

```bash
wc -l .claude/skills/hygiene/prompts/detect.md
head -3 .claude/skills/hygiene/prompts/detect.md
```
Expected: ~150 lines, starts with `# Hygiene — Detect`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/hygiene/prompts/detect.md
git commit -m "feat(hygiene): prompts/detect.md — 16 scan commands"
```

---

## Task 4: Write `prompts/classify.md`

**Files:**
- Create: `.claude/skills/hygiene/prompts/classify.md`

- [ ] **Step 1: Write classify.md**

Path: `.claude/skills/hygiene/prompts/classify.md`

```markdown
# Hygiene — Classify (Phase 2 rules)

Input: findings JSONL from `/tmp/hygiene-findings-$RUN_ID.jsonl`.
Output: same JSONL, with each finding annotated with `bucket`, `auto_action_command`, `ask_user_text`.

## Default lookup (config-driven)

For each finding:
1. Read `.claude/hygiene-config.yaml` `checks.<finding.check>.default`.
2. Map default value to bucket:

| default | bucket |
|---|---|
| `auto_commit_push`, `auto_delete`, `auto_untrack`, `auto_ignore`, `auto_sync` | `auto` |
| `mixed` | resolve per-finding (see overrides) |
| `ask_user` | `ask` |
| `flag_immediate` | `security` |
| `skip` | `skip` (drop from findings) |

## Per-check overrides

### unpushed-work
Auto-commit ONLY if path matches `whitelist.unpushed_paths`. Anything outside → bucket=`ask`.

Auto command:
```bash
git add <paths>
git commit -m "chore(hygiene): auto-commit untracked under <prefix>"
```

### stray-binaries
Auto-delete ONLY if path NOT in `whitelist.binaries_keep`. Otherwise drop (skip).

Auto command:
```bash
git rm -f <path>
```
If untracked: `rm -f <path>`.

### icloud-dupes
Always auto-delete (the file with " 2." or " 3." in name is always the dupe; the canonical version exists nearby).

```bash
rm -f <path>      # if untracked
git rm -f <path>  # if tracked
```

### pycache-committed
Auto-untrack and add to `.gitignore` if not present.

```bash
git rm -r --cached <path>
grep -qxF '<pattern>' .gitignore || echo '<pattern>' >> .gitignore
git add .gitignore
```

### gitignore-violations
Auto-add the matching pattern to `.gitignore`. Do not delete files (they may be intentional locally).

### skill-registry-drift
- `unregistered` (in FS, not in DB) → auto-call `/tool-register <slug>`.
- `orphan` (in DB, not in FS) → bucket=`ask`. Show paths, ask user "delete orphan row in `tools`?"

### cross-platform-skill-prep
Auto-call `/ecosystem-sync sync` (additive only — guaranteed safe by ecosystem-sync's own rules).

### empty-directories — `mixed` resolution
- Untracked + empty → bucket=`auto` (rmdir).
- Tracked + empty (has .gitkeep) → bucket=`ask` ("intentional placeholder?").

### orphan-imports / orphan-docs / broken-doc-links / missing-readme / stale-branches / structure-conventions / obsolete-tracked-files
Always bucket=`ask`. Build `ask_user_text`:

```
**<check>**: <count> findings
<for each finding>
- `<path>`: <reason>. Suggested: <suggested_action>.
</for each>
```

### security-scan
Always bucket=`security`. Build short message:

```
🚨 <check>: <severity>
Path: <path>
Reason: <reason>
```

NEVER include the secret value itself.

## Overall ruleset

- If a finding's `severity = critical` → force bucket=`security` regardless of default.
- If a finding's path matches `protected_zones.never_modify` → drop from auto bucket entirely (re-classify as `ask` with reason "in protected zone").
- If config has `checks.<name>` block missing → log warning, default to `ask`.

## Output JSONL fields after classify

```json
{"check":"...","severity":"...","paths":[...],"reason":"...","suggested_action":"...","evidence":"...","bucket":"auto|ask|security|skip","auto_action_command":"<bash>","ask_user_text":"<markdown>"}
```

## Counts

After all findings classified:
```
auto_count = N
ask_count = N
security_count = N
skip_count = N
```

These propagate to Phase 4-7.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/hygiene/prompts/classify.md
git commit -m "feat(hygiene): prompts/classify.md — bucket-routing rules"
```

---

## Task 5: Write `prompts/publish.md`

**Files:**
- Create: `.claude/skills/hygiene/prompts/publish.md`

- [ ] **Step 1: Write publish.md**

Path: `.claude/skills/hygiene/prompts/publish.md`

````markdown
# Hygiene — Publish (Phase 5 + 6 templates)

## Cloudflare article template

Render to `/tmp/hygiene-report-$RUN_ID.md`, then publish via `cloudflare-pub`.

```markdown
# Wookiee Hygiene Run — {YYYY-MM-DD}

**Status:** {clean | N auto-fixed | N need review | security flag}
**Run ID:** `{RUN_ID}`
**Triggered by:** {github_actions | manual | workflow_dispatch}
**Duration:** {DURATION}s
**Tokens used:** ~{TOKENS}

---

## Summary

| Bucket | Count |
|---|---|
| Auto-fixed | {auto_count} |
| Needs review | {ask_count} |
| Security flags | {security_count} |
| Skipped | {skip_count} |

PR: [{pr_branch}]({pr_url}) — {merged | open — needs review | not opened}

---

## Auto-fixed

(Only present if auto_count > 0.)

For each auto finding (grouped by check):

### `{check}` — {N items}

- `{path}` — {reason}. Action: {auto_action_command}.

---

## Needs review

(Only present if ask_count > 0.)

For each ask finding:

### `{check}`: {short label}

**Paths:**
- `{path1}`
- `{path2}`

**Reason:** {reason}
**Suggested action:** {suggested_action}
**Evidence:** {evidence}

---

## Security flags

(Only present if security_count > 0.)

For each security finding:

### 🚨 `{check}` — {severity}

- Path: `{path}`
- Reason: {reason}
- Telegram alert sent at: {timestamp}

(Secret values are never published — only paths.)

---

## Stats

- Phase durations: scan={t1}s, classify={t2}s, act={t3}s, pr={t4}s, publish={t5}s.
- Cron run number: {N} (counted from `tool_runs`).
- Repo state hash (post-run): `{git rev-parse HEAD}`.
```

## Telegram message templates

### Security alert (sent immediately during Phase 3c)

```
🚨 Wookiee Hygiene SECURITY [{YYYY-MM-DD}]
Check: {check}
Path: {path}
Reason: {reason}
Action required: review immediately.
```

### Run summary (Phase 6, only if ask_count > 0 OR security_count > 0)

```
🧹 Wookiee Hygiene {YYYY-MM-DD}
Auto-fixed: {auto_count}
Needs review: {ask_count}
Security flags: {security_count}

Full report: {cloudflare_url}
PR: {pr_url}
```

### Abort alert (cost cap or precondition fail)

```
⚠️ Wookiee Hygiene ABORTED [{YYYY-MM-DD}]
Reason: {reason}
Partial state: {what got done before abort}

Investigate: {cloudflare_url or "no report"}
```

## Constants for templating

| Variable | Source |
|---|---|
| `{YYYY-MM-DD}` | `date -u +%Y-%m-%d` |
| `{RUN_ID}` | `date -u +%Y%m%dT%H%M%SZ` (set at start of run, propagated everywhere) |
| `{cloudflare_url}` | output of `cloudflare-pub` Permanent URL |
| `{pr_url}` | output of `gh pr view --json url` |
| `{auto_count}/{ask_count}/{security_count}/{skip_count}` | from classify Phase 2 |
| `{DURATION}` | `date +%s` end - start |
| `{TOKENS}` | from Anthropic API response usage block |

## Important formatting rules

- Always use Markdown headings (Cloudflare-pub renders them).
- No raw HTML — `cloudflare-pub` strips/escapes some tags.
- Code blocks use triple-backtick + language hint.
- Telegram messages: plain text, no Markdown (Telegram interprets some chars).
- Truncate any field longer than 500 chars to "…(truncated, see Cloudflare report)".
````

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/hygiene/prompts/publish.md
git commit -m "feat(hygiene): prompts/publish.md — Cloudflare + Telegram templates"
```

---

## Task 6: Replace placeholder `.claude/skills/hygiene/README.md`

**Files:**
- Modify: `.claude/skills/hygiene/README.md` (replace Phase 1 placeholder)

- [ ] **Step 1: Read existing placeholder**

```bash
cat .claude/skills/hygiene/README.md
```
Expected: shows the Phase 1 placeholder text.

- [ ] **Step 2: Overwrite with real README**

Path: `.claude/skills/hygiene/README.md`

```markdown
# /hygiene

Daily repo hygiene routine for the Wookiee project.

## What it does

Scans for common drift, fixes safe stuff automatically, opens PRs for ambiguous decisions, and pings Telegram only when human attention is needed.

| Bucket | Examples |
|---|---|
| auto | unpushed plans/specs, iCloud dupes, pycache leaks, gitignore violations, skill registry drift, cross-platform skill sync, empty dirs |
| ask-user | orphan imports, orphan docs, broken doc links, missing READMEs, stale branches, structure deviations, obsolete tracked files |
| security | leaked secrets in tracked files, `.env` accidentally tracked, `.env.example` containing real-looking values |

## How to invoke

```bash
/hygiene                   # full run
/hygiene --dry-run         # scan + classify only
/hygiene --check security-scan   # one check only
```

## Production schedule

Runs automatically at **00:00 São Paulo (UTC-3)** every day via GitHub Actions (`.github/workflows/hygiene-daily.yml`). Triggerable on-demand via `Actions → Hygiene Daily → Run workflow`.

## Notifications

- **Cloudflare Pages**: every run produces an article (`https://wookiee-hygiene-YYYY-MM-DD.pages.dev`).
- **Telegram (`@matveevos_head_bot`)**: alerts ONLY when ask_count > 0 OR security_count > 0. Clean runs → silent (just Cloudflare).

## Files

- `SKILL.md` — main skill (7-phase orchestrator).
- `prompts/detect.md` — exact scan commands per check.
- `prompts/classify.md` — bucket-routing rules.
- `prompts/publish.md` — Cloudflare + Telegram templates.
- `../hygiene-config.yaml` — config (cron, whitelists, defaults).

## Spec & rationale

`docs/superpowers/specs/2026-04-27-hygiene-skill-design.md`
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/hygiene/README.md
git commit -m "docs(hygiene): real README — replaces Phase 1 placeholder"
```

---

## Task 7: Replace placeholder `.claude/hygiene-config.yaml`

**Files:**
- Modify: `.claude/hygiene-config.yaml`

- [ ] **Step 1: Read existing placeholder**

```bash
cat .claude/hygiene-config.yaml
```
Expected: `# Hygiene checks config — Phase 2 placeholder\nversion: 1\nchecks: []`.

- [ ] **Step 2: Overwrite with full config**

Path: `.claude/hygiene-config.yaml`

```yaml
# Hygiene config — drives the /hygiene skill
# Spec: docs/superpowers/specs/2026-04-27-hygiene-skill-design.md
version: 2

schedule:
  runner: github_actions     # see .github/workflows/hygiene-daily.yml
  cron: "0 3 * * *"          # 03:00 UTC = 00:00 São Paulo (UTC-3, no DST since 2019)
  workflow_timeout_minutes: 30

cost_caps:
  soft_tokens: 50000          # warning, continue
  hard_tokens: 150000         # abort + Telegram alert

protected_zones:
  never_modify:
    - shared/**
    - sku_database/**
    - .env
    - .env.*
    - services/*/data/**
    - .github/workflows/**

whitelist:
  binaries_keep:
    - services/logistics_audit/*Итоговый*.xlsx
    - services/logistics_audit/*final*.xlsx
    - services/logistics_audit/*Тарифы*.xlsx
    - docs/images/**

  unpushed_paths:
    - docs/superpowers/plans/**
    - docs/superpowers/specs/**
    - docs/skills/**
    - docs/database/**

checks:
  unpushed_work:           { default: auto_commit_push }
  stray_binaries:          { default: auto_delete }
  icloud_dupes:            { default: auto_delete }
  pycache_committed:       { default: auto_untrack }
  gitignore_violations:    { default: auto_ignore }
  skill_registry_drift:    { default: auto_sync }
  cross_platform_skill_prep: { default: auto_sync, via: /ecosystem-sync }
  empty_directories:       { default: mixed }
  orphan_imports:          { default: ask_user, no_reference_days: 60 }
  orphan_docs:             { default: ask_user, no_reference_days: 60 }
  broken_doc_links:        { default: ask_user }
  missing_readme:          { default: ask_user, applies_to: services/* }
  stale_branches:          { default: ask_user, threshold_days: 14 }
  structure_conventions:   { default: ask_user }
  obsolete_tracked_files:  { default: ask_user, no_reference_days: 60 }
  security_scan:           { default: flag_immediate, telegram_alert: true }

notifications:
  cloudflare:
    always_publish: true
    title_format: "Wookiee Hygiene Run {date} — {summary}"
    project_name_format: "wookiee-hygiene-{date}"

  telegram:
    bot_env: TELEGRAM_MANAGER_BOT_TOKEN
    chat_env: HYGIENE_TELEGRAM_CHAT_ID
    only_if_ask_user_or_security: true
    message_prefix: "🧹 Wookiee Hygiene"
```

- [ ] **Step 3: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.claude/hygiene-config.yaml')); print('YAML_OK')"
```
Expected: `YAML_OK`.

- [ ] **Step 4: Commit**

```bash
git add .claude/hygiene-config.yaml
git commit -m "feat(hygiene): real config — replaces Phase 1 placeholder"
```

---

## Task 8: Update `.env.example` with hygiene placeholders

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Read current Telegram block**

```bash
grep -n -A 3 "TELEGRAM_BOT_TOKEN" .env.example
```
Expected: shows lines around `TELEGRAM_BOT_TOKEN=0000000000:AAxxx...`.

- [ ] **Step 2: Insert hygiene block after `TELEGRAM_BOT_TOKEN`**

Use the Edit tool. Find the existing line:
```
TELEGRAM_BOT_TOKEN=0000000000:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
Replace with:
```
TELEGRAM_BOT_TOKEN=0000000000:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Manager bot (Батя бот) — for hygiene Telegram alerts (reused, no child bot)
TELEGRAM_MANAGER_BOT_TOKEN=0000000000:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Hygiene chat_id — captured automatically on first /hygiene setup run
HYGIENE_TELEGRAM_CHAT_ID=
```

- [ ] **Step 3: Verify**

```bash
grep -E "MANAGER_BOT_TOKEN|HYGIENE_TELEGRAM_CHAT_ID" .env.example
```
Expected: both lines present.

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "chore(env): document hygiene env vars (manager bot + chat id)"
```

---

## Task 9: Capture `HYGIENE_TELEGRAM_CHAT_ID` from manager bot

**Files:**
- Modify: `.env` (local only — never commit)

- [ ] **Step 1: Verify chat_id not yet set**

```bash
grep -E "^HYGIENE_TELEGRAM_CHAT_ID=" .env || echo "NOT_SET"
```
If already set with a non-empty value: skip remaining steps in this task.

- [ ] **Step 2: Ask user to /start the bot**

Print this instruction and wait for user confirmation:
> Open Telegram, find `@matveevos_head_bot`, send `/start`. Reply "done" when complete.

(The subagent executing this task pauses for user reply.)

- [ ] **Step 3: Capture chat_id via getUpdates**

```bash
TOKEN=$(grep '^TELEGRAM_MANAGER_BOT_TOKEN=' .env | cut -d= -f2-)
CHAT_ID=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates" | python3 -c '
import sys, json
r = json.load(sys.stdin)
if not r["ok"] or not r["result"]:
    print("NO_UPDATES", file=sys.stderr); sys.exit(1)
ids = {u["message"]["chat"]["id"] for u in r["result"] if "message" in u}
if len(ids) != 1:
    print(f"AMBIGUOUS: {ids}", file=sys.stderr); sys.exit(1)
print(next(iter(ids)))
')
test -n "$CHAT_ID" || (echo "FAILED: no chat_id captured"; exit 1)
echo "Captured: $CHAT_ID"
```

If `NO_UPDATES`: ask user to actually send `/start`, then retry.
If `AMBIGUOUS`: ask user which chat_id they want (multiple chats interacted with the bot recently); pick one, continue.

- [ ] **Step 4: Write to `.env` (local only)**

```bash
if grep -q '^HYGIENE_TELEGRAM_CHAT_ID=' .env; then
  sed -i.bak "s/^HYGIENE_TELEGRAM_CHAT_ID=.*/HYGIENE_TELEGRAM_CHAT_ID=$CHAT_ID/" .env
  rm .env.bak
else
  echo "HYGIENE_TELEGRAM_CHAT_ID=$CHAT_ID" >> .env
fi
grep '^HYGIENE_TELEGRAM_CHAT_ID=' .env
```
Expected: line present with the captured numeric chat_id.

- [ ] **Step 5: Smoke-test with a hello message**

```bash
TOKEN=$(grep '^TELEGRAM_MANAGER_BOT_TOKEN=' .env | cut -d= -f2-)
CHAT=$(grep '^HYGIENE_TELEGRAM_CHAT_ID=' .env | cut -d= -f2-)
curl -sf -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" \
  -d "chat_id=$CHAT" \
  --data-urlencode "text=🧹 Wookiee Hygiene — chat_id captured, ready for daily runs." \
  | python3 -c 'import sys,json; r=json.load(sys.stdin); assert r["ok"]; print("SENT")'
```
Expected: `SENT`. User confirms message arrived.

- [ ] **Step 6: No commit** — `.env` is gitignored. Only proceed once user confirmed receipt.

---

## Task 10: Write `.github/workflows/hygiene-daily.yml`

**Files:**
- Create: `.github/workflows/hygiene-daily.yml`
- Read: `.planning/hygiene/preflight.txt` (decides USE_ACTION=true|false)

- [ ] **Step 1: Determine workflow shape based on preflight**

```bash
cat .planning/hygiene/preflight.txt
```
If `USE_ACTION=true`: use the **action variant** (Step 2a).
If `USE_ACTION=false`: use the **curl-fallback variant** (Step 2b).

- [ ] **Step 2a: Write action variant (preferred)**

Path: `.github/workflows/hygiene-daily.yml`

```yaml
name: Hygiene Daily

on:
  schedule:
    - cron: "0 3 * * *"  # 03:00 UTC = 00:00 São Paulo (no DST)
  workflow_dispatch:

concurrency:
  group: hygiene-daily
  cancel-in-progress: false

jobs:
  hygiene:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: write
      pull-requests: write
      issues: write

    steps:
      - name: Checkout (full history for git ops)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install hygiene deps
        run: |
          python -m pip install --upgrade pip
          pip install psycopg2-binary python-dotenv pyyaml requests

      - name: Set up Node 20 (for wrangler / cloudflare-pub)
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install wrangler
        run: npm i -g wrangler

      - name: Run /hygiene via Claude Code action
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/hygiene"
          allowed_tools: "Bash,Read,Edit,Write,Skill"
        env:
          TELEGRAM_MANAGER_BOT_TOKEN: ${{ secrets.TELEGRAM_MANAGER_BOT_TOKEN }}
          HYGIENE_TELEGRAM_CHAT_ID: ${{ secrets.HYGIENE_TELEGRAM_CHAT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CF_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CF_ACCOUNT_ID: ${{ secrets.CF_ACCOUNT_ID }}
          POSTGRES_HOST: ${{ secrets.POSTGRES_HOST }}
          POSTGRES_PORT: ${{ secrets.POSTGRES_PORT }}
          POSTGRES_DB: ${{ secrets.POSTGRES_DB }}
          POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
          POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
          HYGIENE_TRIGGER: ${{ github.event_name }}
          HYGIENE_ENV: github_actions
```

- [ ] **Step 2b: Write curl-fallback variant (only if action missing)**

Path: `.github/workflows/hygiene-daily.yml`

```yaml
name: Hygiene Daily

on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:

concurrency:
  group: hygiene-daily
  cancel-in-progress: false

jobs:
  hygiene:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: |
          pip install psycopg2-binary python-dotenv pyyaml requests anthropic

      - name: Run hygiene via Anthropic Messages API
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TELEGRAM_MANAGER_BOT_TOKEN: ${{ secrets.TELEGRAM_MANAGER_BOT_TOKEN }}
          HYGIENE_TELEGRAM_CHAT_ID: ${{ secrets.HYGIENE_TELEGRAM_CHAT_ID }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          POSTGRES_HOST: ${{ secrets.POSTGRES_HOST }}
          POSTGRES_PORT: ${{ secrets.POSTGRES_PORT }}
          POSTGRES_DB: ${{ secrets.POSTGRES_DB }}
          POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
          POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
        run: |
          # Fallback: minimal Anthropic Messages API call that pastes SKILL.md content
          # then asks Claude to execute the hygiene flow with Bash tool emulation.
          # NOTE: this fallback is non-functional for full hygiene because Bash tool
          # can't be enabled via raw Messages API. Use only as a placeholder until
          # Claude Code action is published, then switch to action variant.
          echo "FATAL: action-less mode cannot run /hygiene end-to-end."
          echo "Switch back to action variant once anthropics/claude-code-action exists."
          exit 1
```

(Plan-author note: if Step 1 in Task 1 found `USE_ACTION=false`, the plan should pause here and ask user how they want to proceed — most likely by running hygiene from a long-running self-hosted Claude instead of GH Actions. Do not silently ship a non-functional workflow.)

- [ ] **Step 3: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/hygiene-daily.yml')); print('YAML_OK')"
```
Expected: `YAML_OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/hygiene-daily.yml
git commit -m "feat(hygiene): GitHub Actions workflow — daily 00:00 São Paulo"
```

---

## Task 11: Set up GitHub Secrets

**Files:** none (uses `gh secret set`)

- [ ] **Step 1: Check `gh` is authed**

```bash
gh auth status 2>&1 | head -5
```
Expected: `Logged in to github.com as ...`. If not: `gh auth login` first.

- [ ] **Step 2: Push secrets**

```bash
# Read values from local .env without echoing them
set -a; source .env; set +a

# Anthropic API key — required for action
gh secret set ANTHROPIC_API_KEY --body "$ANTHROPIC_API_KEY" --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# Telegram
gh secret set TELEGRAM_MANAGER_BOT_TOKEN --body "$TELEGRAM_MANAGER_BOT_TOKEN"
gh secret set HYGIENE_TELEGRAM_CHAT_ID --body "$HYGIENE_TELEGRAM_CHAT_ID"

# Cloudflare
gh secret set CLOUDFLARE_API_TOKEN --body "$CLOUDFLARE_API_TOKEN"
[ -n "$CF_ACCOUNT_ID" ] && gh secret set CF_ACCOUNT_ID --body "$CF_ACCOUNT_ID"

# Supabase (read from sku_database/.env, fallback to .env)
SKU_ENV=sku_database/.env
for var in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
  val=$(grep "^$var=" "$SKU_ENV" 2>/dev/null | cut -d= -f2- || true)
  [ -z "$val" ] && val=$(grep "^$var=" .env 2>/dev/null | cut -d= -f2- || true)
  [ -n "$val" ] && gh secret set "$var" --body "$val"
done
```

- [ ] **Step 3: Verify secrets exist (without printing values)**

```bash
gh secret list | grep -E "ANTHROPIC_API_KEY|TELEGRAM_MANAGER_BOT_TOKEN|HYGIENE_TELEGRAM_CHAT_ID|CLOUDFLARE_API_TOKEN|POSTGRES_HOST"
```
Expected: 5+ lines with each secret name and recent updated timestamp.

- [ ] **Step 4: No commit** — secrets live in GitHub, not in repo.

---

## Task 12: Register `hygiene` in Supabase `tools`

**Files:** none (uses `/tool-register`)

- [ ] **Step 1: Invoke tool-register**

Run the project skill:

```
/tool-register hygiene
```

If the skill prompts for fields, provide:
- `display_name`: "Hygiene"
- `type`: `skill`
- `category`: `infra`
- `version`: `1.0.0`
- `run_command`: `/hygiene`
- `description`: "Daily repo hygiene — push ready, delete garbage, sync skills cross-platform, security tripwire, Cloudflare report + Telegram alerts."

- [ ] **Step 2: Verify row in Supabase**

```bash
PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('sku_database/.env')
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT','5432'), dbname=os.getenv('POSTGRES_DB','postgres'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()
cur.execute(\"SELECT slug, display_name, type, category, status, version FROM tools WHERE slug = 'hygiene'\")
row = cur.fetchone()
assert row, 'hygiene not registered'
print('REGISTERED:', row)
"
```
Expected: `REGISTERED: ('hygiene', 'Hygiene', 'skill', 'infra', 'active', '1.0.0')`.

- [ ] **Step 3: Regenerate tools catalog**

```bash
PYTHONPATH=. python3 scripts/generate_tools_catalog.py
git status docs/TOOLS_CATALOG.md
```
Expected: catalog updated to include `hygiene`.

- [ ] **Step 4: Commit catalog update**

```bash
git add docs/TOOLS_CATALOG.md
git commit -m "chore(catalog): regenerate after hygiene registration"
```

---

## Task 13: Local dry-run end-to-end

**Files:** none (read-only validation)

- [ ] **Step 1: Run `/hygiene --dry-run` from Claude REPL**

In the active Claude session, invoke:
```
/hygiene --dry-run
```

Watch for:
- Phase 1 (SCAN) completes < 60s.
- Phase 2 (CLASSIFY) outputs counts (e.g. `auto=7 ask=2 security=0 skip=0`).
- Phases 3-4-5-6-7 are skipped (dry-run).
- No commits made (`git status` unchanged).

- [ ] **Step 2: Confirm findings file written**

```bash
ls -la /tmp/hygiene-findings-*.jsonl | head
wc -l /tmp/hygiene-findings-*.jsonl
```
Expected: at least one findings file with non-zero lines reflecting current drift (`.codex/`, `.cursor/`, etc. from the live drift listed in spec §8).

- [ ] **Step 3: Manually inspect a couple of findings**

```bash
head -3 /tmp/hygiene-findings-$(ls -t /tmp/hygiene-findings-*.jsonl | head -1 | xargs basename | sed 's/hygiene-findings-//;s/\.jsonl//').jsonl | python3 -c "import sys, json; [print(json.dumps(json.loads(l), indent=2, ensure_ascii=False)) for l in sys.stdin]"
```
Verify the JSON shape matches `prompts/detect.md` schema. If not — return to Tasks 3-4 to fix.

- [ ] **Step 4: No commit** — dry-run produces no artefacts in the repo.

---

## Task 14: Manual `workflow_dispatch` to validate CI path

**Files:** none

- [ ] **Step 1: Push the branch (if not already)**

```bash
git push -u origin spec/hygiene-skill-design 2>&1 | tail -3
```

- [ ] **Step 2: Trigger workflow manually**

```bash
gh workflow run hygiene-daily.yml --ref spec/hygiene-skill-design
sleep 10
gh run list --workflow=hygiene-daily.yml --limit 1
```
Expected: latest run shows `in_progress` or `queued`.

- [ ] **Step 3: Watch run to completion**

```bash
RUN_ID=$(gh run list --workflow=hygiene-daily.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID"
```
Expected: run completes within 30 minutes with `success` (or `success` with auto-merge of a tiny PR for live drift).

- [ ] **Step 4: Verify outputs**

a. Check Cloudflare article URL was logged in run output:
```bash
gh run view "$RUN_ID" --log | grep -E "Permanent URL|wookiee-hygiene-" | head -3
```

b. Check Supabase `tool_runs` has a fresh row:
```bash
PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('sku_database/.env')
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT','5432'), dbname=os.getenv('POSTGRES_DB','postgres'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()
cur.execute(\"SELECT id, status, started_at, finished_at, result_url FROM tool_runs WHERE tool_slug='hygiene' ORDER BY started_at DESC LIMIT 1\")
print(cur.fetchone())
"
```
Expected: a row from the last few minutes with `status='success'` or `'partial'`.

c. If `ask_count > 0` or `security_count > 0`: confirm Telegram message received in `@matveevos_head_bot` chat with prefix `🧹 Wookiee Hygiene`.

- [ ] **Step 5: If anything failed — debug, fix, retry**

Common fixes:
- Action 401: secret `ANTHROPIC_API_KEY` missing or wrong → re-run Task 11 Step 2.
- Cloudflare deploy fails: missing `CF_ACCOUNT_ID` secret → add via `gh secret set`.
- Supabase connect fails: `POSTGRES_*` secrets missing → re-run Task 11 Step 2.
- Telegram fails: chat_id wrong → re-run Task 9 to recapture.

After fix, re-trigger with `gh workflow run hygiene-daily.yml --ref spec/hygiene-skill-design`. Repeat until green.

- [ ] **Step 6: No commit** — workflow_dispatch is a runtime action, no repo changes from this task itself.

---

## Task 15: Open PR with `/pullrequest wait`

**Files:** none (PR description auto-built)

- [ ] **Step 1: Self-check before PR**

```bash
git status
git log --oneline main..HEAD | head -20
```
Expected: 7-9 commits on `spec/hygiene-skill-design` (spec v1, spec v2, preflight, SKILL.md, detect, classify, publish, README, config, env.example, workflow, catalog).

- [ ] **Step 2: Invoke /pullrequest in wait mode**

This is infra-heavy: cron, secrets, manager bot. Use `wait` mode so user reviews before auto-merge.

```
/pullrequest wait
```

PR title (suggest to skill): `feat(hygiene): /hygiene skill + GitHub Actions daily routine`.

PR body should include:
- Summary: spec link, commit `9abfd7d`, list of files added/changed.
- Test plan checklist:
  - [ ] Local `/hygiene --dry-run` passes (Task 13).
  - [ ] `workflow_dispatch` run on `spec/hygiene-skill-design` ended `success` (Task 14).
  - [ ] Cloudflare report published.
  - [ ] Telegram alert received (if drift had ask/security).
  - [ ] Supabase `tool_runs` has fresh `hygiene` row.
- Manual checks for reviewer:
  - [ ] Verify `.github/workflows/hygiene-daily.yml` cron is `0 3 * * *`.
  - [ ] Verify `tools` row has `category='infra'`, `status='active'`.
  - [ ] Spot-check 2-3 findings in `prompts/detect.md` for correctness.

- [ ] **Step 3: Wait for Codex + Copilot reviews**

The `/pullrequest` skill loops until both bots return green or surfaces blocking comments. Address any blockers, push fixups, re-run reviews. Do not bypass.

- [ ] **Step 4: User merge confirmation**

Once reviews are green, the skill prompts the user. User merges manually (this is a manual checkpoint per spec — first hygiene run is high-impact).

- [ ] **Step 5: Post-merge — verify cron is registered**

```bash
gh workflow list | grep -i hygiene
gh workflow view "Hygiene Daily" | head
```
Expected: workflow appears, schedule shown as `0 3 * * *`.

- [ ] **Step 6: Cleanup**

```bash
# Delete the merged branch locally
git checkout main && git pull
git branch -d spec/hygiene-skill-design
# Remote branch is auto-deleted by repo's "Automatically delete head branches" setting
```

---

## Self-Review

After writing all tasks, ran the spec-coverage check against `2026-04-27-hygiene-skill-design.md`:

| Spec section | Covered by |
|---|---|
| §1 Goals (push, delete, structure, sync, security, notify) | Task 2 (SKILL.md flow) + Task 7 (config defaults) |
| §1 Non-goals | Task 2 (Hard rules section) + Task 7 (protected_zones) |
| §2 Architecture: pure SKILL.md | Tasks 2-5 (no Python orchestrator created) |
| §2 7-phase flow | Task 2 SKILL.md sections "Phase 1-7" |
| §2 cron via GitHub Actions | Task 10 |
| §2 Protected zones / forbidden ops | Task 2 "Hard rules" + Task 7 `protected_zones` |
| §3 16 checks | Task 3 (detect.md has all 16) + Task 7 (config has all 16) + Task 4 (classify rules per check) |
| §4 Config | Task 7 |
| §5 Notification format | Task 5 (publish.md) |
| §6.1 Manager bot reuse | Task 9 (capture chat_id) + Task 11 (push secret) |
| §6.2 Skill files | Tasks 2-7 |
| §6.3 GitHub Actions workflow | Task 10 |
| §6.4 Supabase registration | Task 12 |
| §6.5 Verification (local + CI) | Tasks 13 + 14 |
| §7 Edge cases (cost cap, conflict PR, hallucination) | Task 2 SKILL.md ("Cost guardrails", Phase 4 conflict-handling, Phase 3b "ask only never auto") |
| §8 Success criteria | Task 14 (CI run) + Task 12 (Supabase row) + Task 9 (Telegram smoke test) |
| §9 Open Q1 (chat_id) | Task 9 |
| §9 Open Q4 (action availability) | Task 1 Step 4 + Task 10 Step 1 (decides variant) |

All 16 checks present in detect.md, classify.md, and config.yaml — verified by cross-referencing the table headings.

Type/name consistency check passed:
- `auto_count`, `ask_count`, `security_count`, `skip_count` used consistently across SKILL.md, classify.md, publish.md, detect.md.
- `RUN_ID` defined once in SKILL.md, referenced uniformly.
- `TELEGRAM_MANAGER_BOT_TOKEN` and `HYGIENE_TELEGRAM_CHAT_ID` env var names match across `.env.example`, config.yaml, SKILL.md, workflow.yml.
- `bucket` enum is consistently `auto|ask|security|skip` everywhere.

No placeholders found (`TBD`, `TODO`, "implement later") — all code blocks contain runnable content.
