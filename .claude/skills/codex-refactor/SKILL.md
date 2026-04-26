---
name: codex-refactor
description: "Automated refactoring pipeline: Claude analyzes code → creates plan → delegates to Codex → reviews result → commits + PR. Use when user asks to refactor code, reduce duplication, clean up files. Triggers: refactor, codex-refactor, рефакторинг, clean up, reduce duplication."
---

# Codex Refactor: analyze → plan → delegate → review → PR

## Overview

Автоматический рефакторинг с делегированием Codex и контролем Claude.
Claude анализирует код и создаёт план, Codex выполняет, Claude ревьюит результат на соответствие проектным правилам.

## Arguments

```
/codex-refactor <file_or_dir> "<task description>"
```

Примеры:
- `/codex-refactor shared/clients/wb_client.py "reduce duplication in API methods"`
- `/codex-refactor shared/data_layer/ "consolidate similar queries"`
- `/codex-refactor services/sheets_sync/ "extract common patterns"`

## Workflow

```
  ┌──────────────────────────┐
  │ 1. Analyze current code  │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 2. Create refactoring    │
  │    plan (Claude)         │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 3. Show plan to user     │
  │    (confirm / adjust)    │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 4. Delegate to Codex     │
  │    /codex:rescue         │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 5. Poll status           │
  │    /codex:status         │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 6. Get result            │
  │    /codex:result         │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 7. Claude reviews result │
  │    (project rules check) │
  └──────────┬───────────────┘
       ┌─────┴──────┐
       ▼            ▼
    ✅ OK        ❌ Issues
       │            │
       ▼            ▼
    Commit      Claude fixes
    + PR        → re-review
```

## Steps

### 1. Analyze current code

Read the target file(s) specified by the user. Understand:
- Current structure and patterns
- Code smells and duplication
- Dependencies (imports, callers)
- Test coverage (check if tests exist for this code)

```bash
# Find related tests
find . -name "test_*.py" -o -name "*_test.py" | grep -i "<module_name>"
```

### 2. Create refactoring plan

Write a concrete plan with:
- **What changes:** specific functions/classes/patterns to refactor
- **Why:** which code smell or duplication this addresses
- **How:** the refactoring technique (extract method, pull up, replace conditional, etc.)
- **Risk assessment:** what could break

Format as a numbered list of changes.

### 3. Confirm with user

Present the plan to the user. Wait for confirmation before proceeding.
If user adjusts the plan, incorporate changes.

### 4. Delegate to Codex

Build a focused prompt for Codex and delegate:

```bash
/codex:rescue --effort high "Refactor <file>. Plan:
1. <change 1>
2. <change 2>
...
Constraints:
- Do NOT change public API signatures (keep backward compat)
- Do NOT add new dependencies
- Keep all existing tests passing
- Follow existing code style"
```

**Sizing rules:**
- Small refactor (1-2 files, < 200 lines changed) → foreground: `/codex:rescue --wait`
- Large refactor (3+ files, > 200 lines) → background: `/codex:rescue --background`

### 5. Poll status (if background)

```bash
/codex:status
```

Wait for completion. Check every 30-60 seconds if background.

### 6. Get result

```bash
/codex:result
```

Review the diff that Codex produced.

### 7. Claude reviews result

**CRITICAL:** Claude MUST review every Codex change against project rules.

Checklist:
- [ ] **LOWER() in GROUP BY** — if SQL uses GROUP BY on article/model, MUST use `LOWER(SPLIT_PART(article, '/', 1))`
- [ ] **data_layer.py only** — all DB queries MUST be in `shared/data_layer.py`, not scattered in scripts
- [ ] **config.py only** — configuration MUST come from `shared/config.py`, not hardcoded
- [ ] **Secrets in .env** — no hardcoded secrets, API keys, passwords
- [ ] **No new dependencies** — unless explicitly approved
- [ ] **Tests still pass** — run existing tests
- [ ] **No public API breakage** — callers of refactored code still work

```bash
# Run tests
pytest tests/ -x -q 2>&1 | head -50
```

### 8. Fix or commit

**If issues found:** Claude fixes them directly, then re-runs tests.

**If clean:**
1. Stage changes
2. Create descriptive commit
3. Ask user: create PR via `/pullrequest` or just commit?

## What NOT to delegate to Codex

- SQL queries for data_layer.py (Codex doesn't know LOWER() rule)
- Business logic with Wookiee-specific tariffs, SPP, DRR formulas
- MCP server code (Codex has no MCP access)
- OpenRouter model tier configuration

For these, Claude does the refactoring directly.

## Error handling

- If `/codex:rescue` times out → `/codex:cancel` and report to user
- If Codex produces empty result → retry once with simpler prompt
- If tests fail after Codex changes → Claude fixes, does NOT re-delegate
- If Codex is not installed → tell user to run `/codex:setup`
