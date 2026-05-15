# code-quality-scan

Wave B3 of the Nighttime DevOps Agent.

Reads the repo, runs four static-analysis tools, writes a single JSON report
that the night-coordinator picks up at 04:00 UTC.

## Files

```
.claude/skills/code-quality-scan/
├── SKILL.md         # invocation contract + flow (used by Claude Code)
├── runner.py        # CLI entrypoint (also callable from GH Actions workflow)
└── README.md        # this file
```

## Local invocation

```bash
# Install dev deps once (mypy / vulture / pipdeptree)
pip install -r services/influencer_crm/requirements-dev.txt

# Run from repo root
python .claude/skills/code-quality-scan/runner.py

# Or with explicit flags
python .claude/skills/code-quality-scan/runner.py \
    --repo /Users/danilamatveev/Projects/Wookiee \
    --out .hygiene/reports/code-quality-$(date -u +%Y%m%d).json \
    --paths agents services shared scripts

# Preview without writing
python .claude/skills/code-quality-scan/runner.py --dry-run | head -80

# Skip Codex sidecar (useful for fast local iteration)
python .claude/skills/code-quality-scan/runner.py --no-codex --dry-run
```

## CI invocation

The 03:30 UTC cron workflow `.github/workflows/code-quality-daily.yml` (Wave D1,
not in this PR) will install dependencies and call:

```bash
python .claude/skills/code-quality-scan/runner.py --no-codex || true
```

`--no-codex` is the default in CI because the GH Actions runner has no
`~/.codex/auth.json`. The sidecar detects this and fails safe to
`confidence=0, used=true`, so all vulture candidates land in the
"needs human review" bucket — which is what we want anyway.

## Report schema

Plan §3.2. Each finding looks like:

```json
{
  "id": "vulture-unused-function-services-old-aggregator-py-88",
  "tool": "vulture",
  "severity": "warning",
  "rule_id": "unused-function",
  "file": "services/old_aggregator.py",
  "line": 88,
  "column": null,
  "message": "unused function 'compute' (75% confidence)",
  "auto_fixable": false,
  "confidence": 75
}
```

Top-level fields:

- `tools.<name>.{version, exit_code, errors}` — one entry per wrapped tool
- `findings` — array (above)
- `summary.{total, auto_fixable, needs_human, by_tool}` — aggregates

## Coupling

Skill is fully self-contained. Reads nothing; writes one JSON file.
`night-coordinator` (Wave A3) reads it at 04:00 UTC and merges with hygiene.

## Codex sidecar

For vulture candidates and mypy `unreachable` warnings, the runner asks
`shared.codex_sidecar.analyze_finding()` to verify whether the symbol is
referenced anywhere — including dynamic dispatch (getattr, importlib, entry
points). Codex's verdict either bumps the finding's confidence (if Codex agrees
it's unused) or drops it below the queue threshold (if Codex finds a reference).

In CI the sidecar fails safe: no auth.json → no Codex call → confidence stays
at 0 → coordinator queues for `/hygiene-resolve` rather than auto-deleting.

## Token budget

Per plan §9: 250k tokens hard cap for this skill, dominated by Codex calls
(~5k tokens × ~20 ambiguous findings/night). Enforced via `--config
model_context_window=5000` per call.
