---
name: codex-arch-review
description: "Adversarial architecture review via Codex — pressure-tests design decisions, finds failure modes, edge cases. Use before major changes, new services, data model changes. Triggers: arch review, adversarial review, архитектурный ревью, design review, codex-arch-review, second opinion."
---

# Codex Arch Review: context → adversarial review → categorize → report

## Overview

Запускает adversarial review от Codex (GPT-модель) для давления на архитектурные решения.
Claude собирает контекст, формирует фокусированный запрос, категоризирует и cross-validates находки.

## Arguments

```
/codex-arch-review "<what you're changing and why>"
```

Примеры:
- `/codex-arch-review "adding new MCP server for pricing analysis"`
- `/codex-arch-review "migrating from flat files to Supabase tables"`
- `/codex-arch-review "new ETL pipeline for Ozon returns data"`
- `/codex-arch-review` (без аргументов — review текущих uncommitted changes)

## Workflow

```
  ┌──────────────────────────┐
  │ 1. Gather context        │
  │    (diff, files, rules)  │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 2. Detect change type    │
  │    → select focus areas  │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 3. Run adversarial review│
  │    /codex:adversarial-   │
  │    review <focus>        │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 4. Categorize findings   │
  │    Critical/Warning/Info │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 5. Cross-validate with   │
  │    Wookiee project rules │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 6. Report + action items │
  └──────────────────────────┘
```

## Steps

### 1. Gather context

Collect information about what's being reviewed:

```bash
# Current changes
git diff --stat
git diff --name-only

# If reviewing a branch
git diff main...HEAD --stat
git log main...HEAD --oneline
```

Read the changed files to understand the scope.
Read CLAUDE.md and AGENTS.md for project rules.

### 2. Detect change type and select focus

Automatically determine the review focus based on what changed:

| Files changed match | Focus areas |
|-------------------|-------------|
| `shared/data_layer/` or `*.sql` | Data integrity, GROUP BY correctness, SQL injection, LOWER() usage, index impact |
| `mcp_servers/` or `*_mcp_server/` | API security, RLS policies, auth, rate limiting, input validation |
| `shared/config.py` or `deploy/` or `docker-compose` | Secrets exposure, env var handling, .env.example sync, port conflicts |
| `shared/clients/` | Breaking changes, error handling, retry logic, timeout handling |
| `.claude/skills/` or `agents/` | Prompt injection risks, cost estimation, model tier usage, token limits |
| `services/` | Resource management, error recovery, data consistency, idempotency |
| `wookiee-hub/` | XSS, CSRF, auth state, API surface, bundle size |
| General / mixed | Architecture coherence, dependency direction, separation of concerns |

### 3. Run adversarial review

Build a targeted prompt and run:

```bash
/codex:adversarial-review --base main <focus_text>
```

**Without `--base`** (review working changes):
```bash
/codex:adversarial-review <focus_text>
```

**Focus text template:**
```
Review architecture decision: <what's changing>.
Context: <why it's being done>.
Focus on: <selected focus areas from step 2>.
Challenge: design tradeoffs, failure modes, edge cases, security implications, simpler alternatives.
```

### 4. Categorize findings

Parse Codex response and categorize each finding:

| Category | Criteria | Action |
|----------|----------|--------|
| **CRITICAL** | Security vulnerability, data loss risk, breaking change | Must fix before proceeding |
| **WARNING** | Performance concern, missing edge case, suboptimal design | Should address, discuss with user |
| **INFO** | Style suggestion, alternative approach, nice-to-have | Note for future, no action needed |

### 5. Cross-validate with Wookiee rules

Check each finding against project-specific rules that Codex doesn't know:

**Data rules:**
- Does the change maintain LOWER() in GROUP BY for article/model?
- Are all DB queries in shared/data_layer.py (not scattered)?
- Are percentage metrics weighted-average when combining channels?

**Infrastructure rules:**
- Config only through shared/config.py?
- Secrets only in .env?
- DB server is READ-ONLY (no writes)?
- New Supabase tables have RLS + policies?

**AI/Agent rules:**
- All LLM calls through OpenRouter?
- Correct model tier (LIGHT/MAIN/HEAVY)?
- Cost estimated for new agent?

**Upgrade/Downgrade findings:**
- If Codex flagged something that's actually fine per Wookiee rules → downgrade to INFO with note
- If Codex missed something that violates Wookiee rules → add as Claude-only CRITICAL/WARNING

### 6. Report

Present unified report to user:

```markdown
## Adversarial Architecture Review

### Summary
- Reviewed: <what was reviewed>
- Focus: <selected focus areas>
- Findings: X critical, Y warnings, Z info

### CRITICAL (must fix)
1. **<title>** — <description>
   - Impact: <what could go wrong>
   - Fix: <recommended action>

### WARNING (should address)
1. **<title>** — <description>
   - Risk: <potential impact>
   - Suggestion: <recommended approach>

### INFO (noted)
1. **<title>** — <description>

### Wookiee-specific checks
- [ ] LOWER() in GROUP BY: <pass/fail/N/A>
- [ ] data_layer.py only: <pass/fail/N/A>
- [ ] config.py only: <pass/fail/N/A>
- [ ] .env secrets: <pass/fail/N/A>
- [ ] RLS policies: <pass/fail/N/A>
- [ ] OpenRouter only: <pass/fail/N/A>
```

## Error handling

- If Codex is not installed → tell user to run `/codex:setup`
- If adversarial review returns empty → retry with broader focus
- If Codex times out → report partial findings from Claude-only analysis
- If no changes detected → ask user what to review
