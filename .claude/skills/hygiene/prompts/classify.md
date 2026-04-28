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
