---
name: code-quality-scan
description: "Nightly code-quality scan — runs ruff/mypy/vulture/pip-deptree and emits one JSON report to .hygiene/reports/code-quality-YYYYMMDD.json. Calls Codex sidecar for ambiguous dead-code candidates. GitHub Actions cron 03:30 UTC. Triggers: /code-quality-scan, прогон код-качества."
triggers:
  - /code-quality-scan
  - прогон код-качества
  - code quality scan
metadata:
  category: infra
  version: 0.1.0
  owner: danila
---

# Code-quality-scan Skill

Wave B3 of the Nighttime DevOps Agent. Single-pass code-quality probe across the
Wookiee repo. **No PR creation, no commits** — emits a single JSON report at
`.hygiene/reports/code-quality-YYYYMMDD.json` which `night-coordinator` reads at 04:00 UTC.

Plan: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md` (§3.2, §12).

## Quick start

```
/code-quality-scan                       # full run, writes JSON to .hygiene/reports/
/code-quality-scan --dry-run             # print summary to stdout, do not write file
/code-quality-scan --no-codex            # skip Codex sidecar for ambiguous findings
/code-quality-scan --out <path>          # override report path
```

Direct CLI invocation:

```bash
python .claude/skills/code-quality-scan/runner.py \
    --repo /Users/danilamatveev/Projects/Wookiee \
    --out .hygiene/reports/code-quality-$(date -u +%Y%m%d).json
```

## What it runs

| Tool          | Detects                                                  | Auto-fixable  |
| ------------- | -------------------------------------------------------- | ------------- |
| `ruff check`  | lint errors (imports, style, simple bugs)                | yes           |
| `mypy`        | type errors                                              | partial       |
| `vulture`     | dead code (functions/classes never referenced)           | no (judgment) |
| `pip-deptree` | unused requirements (import-graph vs requirements*.txt)  | no (judgment) |

`ruff` and the test deps are already pinned in CI (`.github/workflows/ci.yml`).
`mypy`, `vulture`, and `pipdeptree` are listed in `services/influencer_crm/requirements-dev.txt`
so the runner picks them up locally; on the GH Actions runner the workflow that
invokes this skill installs them inline (`pip install mypy vulture pipdeptree`).

## Codex sidecar

For each `vulture` candidate (and any `mypy` `unreachable` warning that lacks
clear context), the runner calls `shared.codex_sidecar.analyze_finding()`. Codex
is asked a single yes/no question: "is this symbol actually used anywhere,
including dynamic dispatch?" The verdict (confidence 0–100) lands on the
finding as `confidence` so `night-coordinator` can bucket it:

- `>= 90` → safe to auto-fix
- `60..90` → queue for `/hygiene-resolve`
- `< 60` → discarded (logged, not surfaced)

In CI (no `~/.codex/auth.json`) the sidecar fails safe: every ambiguous finding
gets `confidence=0, used=true` so we never delete code based on a missing arbiter.

## JSON report schema

See plan §3.2 for the canonical schema. Each finding contains:

```json
{
  "id": "vulture-dead-fn-services-old-aggregator-compute",
  "tool": "vulture",
  "severity": "warning",
  "rule_id": "unused-function",
  "file": "services/old_aggregator.py",
  "line": 88,
  "column": null,
  "message": "unused function 'compute'",
  "auto_fixable": false,
  "confidence": 72
}
```

The top-level report has `tools.<name>.{version, exit_code, errors}` plus an
aggregate `summary`.

## Pre-conditions

- Python 3.11
- `ruff`, `mypy`, `vulture`, `pipdeptree` available on PATH (locally via
  `pip install -r services/influencer_crm/requirements-dev.txt`, in CI installed inline)
- Repo root mounted at `--repo` argument (defaults to `git rev-parse --show-toplevel`)

## Failure modes

| Failure                              | Behaviour                                     |
| ------------------------------------ | --------------------------------------------- |
| Any wrapped tool missing             | Skip that tool, emit `exit_code=-1`, continue |
| Codex sidecar timeout / unavailable  | Mark finding with `confidence=0`, keep as-is  |
| Repo path doesn't exist              | Exit 2, no file written                       |
| Output directory unwritable          | Exit 3, no file written                       |

## Coupling with night-coordinator

- Cron `03:30 UTC` runs this skill (defined in `.github/workflows/code-quality-daily.yml`
  — not in this Wave B3 scope, lands in Wave D1/E).
- `04:00 UTC` night-coordinator reads the JSON and merges with the hygiene report.

## Not in scope for this skill

- Opening PRs (done by night-coordinator only)
- Auto-applying fixes (done by hygiene-autofix only)
- Test coverage gating (separate skill `test-coverage-check`)
- Refactoring (Phase 4, not implemented)
