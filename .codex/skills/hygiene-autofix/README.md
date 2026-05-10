# /hygiene-autofix

Daily companion to `/hygiene`. Verifies and fixes the safe `ask_user` findings that /hygiene parks in the daily PR description.

## How it fits with /hygiene

```
03:00 UTC  ┌──────────┐
           │ /hygiene │ ── creates PR with auto-fixes + ask_user findings in description
           └──────────┘
04:00 UTC  ┌──────────────────┐
           │ /hygiene-autofix │ ── reads PR, verifies each ask, fixes SAFE, comments on PR
           └──────────────────┘
later      ┌──────┐
           │ user │ ── reviews remaining findings, merges PR
           └──────┘
```

## What this skill DOES

- Discovers today's hygiene PR (open, branch starts with `chore/hygiene-`)
- Parses `## FOLLOW-UP NEEDED` section of PR body to extract ask findings
- For each finding, applies a per-check verification rule from `prompts/verify.md`
- Classifies each as `SAFE | UNSAFE | NEEDS_HUMAN`
- Applies SAFE fixes → 1 commit per check group → push to same PR branch
- Comments on PR with detailed summary of what was fixed/skipped
- Sends Telegram alert if N>0 fixes applied

## What this skill DOES NOT do

- Does NOT modify `/hygiene` config or detector logic
- Does NOT close, merge, or rebase PRs
- Does NOT touch protected zones (`shared/`, `database/sku/`, `.env*`, `services/*/data/`, `.github/workflows/`, hygiene/hygiene-autofix skill dirs, `.claude/hygiene-config.yaml`)
- Does NOT process more than 10 SAFE findings per run
- Does NOT auto-fix any check that's not explicitly whitelisted in `prompts/verify.md`

## Whitelisted checks (v1)

Only these check types can be SAFE-classified:

| Check | SAFE condition | Action |
|---|---|---|
| `orphan-imports` | 0 grep references, no `__main__` block, not in archive | `git rm` |
| `broken-doc-links` | Target exists at relative path | Comment (false positive ack) |
| `structure-conventions` | Has `package.json`/`tsconfig.json`, no `.py` files | Comment (recommend whitelist add) |
| `skill-registry-drift` | Skill exists in `.cursor/skills/` or `.codex/skills/` | rsync from mirror to `.claude/skills/` |
| `cross-platform-skill-prep` | Source exists in `.claude/skills/`, mirror missing | rsync to mirror |
| `orphan-docs` | Refactor-audit notes mark as ARCHIVE | `git mv` to `docs/archive/` |

Everything else → `NEEDS_HUMAN`. See `prompts/verify.md` for full rules.

## Manual trigger

```bash
# Run on latest open hygiene PR:
gh workflow run hygiene-autofix.yml

# Run on specific PR:
gh workflow run hygiene-autofix.yml -f pr_number=123

# Dry run — report what would be fixed without committing:
gh workflow run hygiene-autofix.yml -f dry_run=true

# Watch progress:
gh run watch
```

## Expanding the SAFE whitelist

This is an explicit human-only PR. The directory `.claude/skills/hygiene-autofix/` is in `protected_zones.never_modify`, so neither /hygiene nor /hygiene-autofix can self-modify. To add a new check:

1. Run /hygiene-autofix in observation for ≥2 weeks
2. Manually review N occurrences of `<check>` finding to confirm action is mechanical
3. Open PR adding rule to `prompts/verify.md`
4. Get human review + merge
5. Next run picks up the new whitelist automatically

## Files

- `SKILL.md` — full 6-phase flow, hard rules, cost guardrails
- `prompts/system.md` — operating principles, decision tree, communication style
- `prompts/verify.md` — per-check verification rules and SAFE actions (the whitelist)
- `../../../.github/workflows/hygiene-autofix.yml` — production runner

## Related

- `.claude/skills/hygiene/` — companion detector
- `.claude/skills/hygiene-followup/` — separate auto-resolver (closes resolved issues)
- `docs/superpowers/plans/2026-05-09-hygiene-autopilot.md` — full 3-phase plan
