---
name: codex-quality-gate
description: "Cross-model quality check before commit/PR — runs Codex review + Claude review in parallel, merges findings by confidence. Use before committing, before PR, for quality assurance. Triggers: quality gate, quality check, codex-quality-gate, pre-commit review, двойная проверка, проверка качества."
---

# Codex Quality Gate: parallel review → merge findings → report

## Overview

Cross-model quality gate: Codex (GPT) и Claude параллельно ревьюят изменения.
Совпадения = высокий приоритет (обе модели нашли → почти наверняка реальный баг).

## Arguments

```
/codex-quality-gate                    # Review staged + unstaged changes
/codex-quality-gate --base main        # Review branch vs main
/codex-quality-gate --staged           # Only staged changes
```

## Workflow

```
  ┌──────────────────────────┐
  │ 1. Collect changes       │
  │    (git diff)            │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────────────────┐
  │ 2. PARALLEL:                         │
  │    ├── Codex: /codex:review --wait   │
  │    └── Claude: independent review    │
  │        (with project rules context)  │
  └──────────┬───────────────────────────┘
             ▼
  ┌──────────────────────────┐
  │ 3. Merge findings        │
  │    Classify by agreement │
  └──────────┬───────────────┘
             ▼
  ┌──────────────────────────┐
  │ 4. Report + auto-fix     │
  └──────────────────────────┘
```

## Steps

### 1. Collect changes

Determine what to review:

```bash
# Default: all changes (staged + unstaged)
git diff
git diff --cached

# With --base: branch comparison
git diff main...HEAD

# With --staged: only staged
git diff --cached
```

Show summary to user:
```bash
git diff --stat
```

If no changes → tell user "nothing to review" and exit.

### 2. Run parallel reviews

#### 2a. Codex review (GPT)

```bash
/codex:review --wait
```

Or with base:
```bash
/codex:review --base main --wait
```

`--wait` ensures we get the result before proceeding.

#### 2b. Claude review (parallel)

While Codex works, Claude independently reviews the same diff.

**Claude review checklist:**

**Code quality:**
- Logic errors, off-by-one, null/None handling
- Error handling: uncaught exceptions, missing try/catch
- Resource leaks: unclosed files, connections, cursors
- Race conditions or concurrency issues

**Wookiee-specific rules:**
- GROUP BY uses `LOWER(SPLIT_PART(article, '/', 1))`
- DB queries only in `shared/data_layer.py`
- Config only from `shared/config.py`
- Secrets only in `.env`, not hardcoded
- Percentage metrics = weighted average across channels
- LLM calls through OpenRouter only
- New Supabase tables have RLS + policies

**Security:**
- SQL injection (parameterized queries?)
- XSS (escaped output?)
- Command injection (shell=True?)
- Secrets in code or logs

### 3. Merge findings

Compare findings from both reviewers and classify:

| Agreement | Priority | Label | Meaning |
|-----------|----------|-------|---------|
| Both found same issue | **HIGH** | `BOTH` | Almost certainly a real bug — fix it |
| Only Codex found | **MEDIUM** | `GPT` | Check if valid — may be false positive or genuine miss by Claude |
| Only Claude found | **MEDIUM** | `CLAUDE` | Check if valid — likely Wookiee-specific rule or context-aware finding |
| Neither found issues | **CLEAN** | `PASS` | Both models agree code is OK |

**Matching logic:**
- Same file + same area (within 5 lines) + similar concern = "both found"
- Different files or very different concerns = separate findings

### 4. Report

Present the merged report:

```markdown
## Quality Gate Report

### Summary
| Metric | Value |
|--------|-------|
| Files reviewed | X |
| Lines changed | +Y / -Z |
| Codex findings | A |
| Claude findings | B |
| Overlap (both found) | C |

### HIGH priority (both models agree)
1. **[file:line]** — <description>
   - Codex says: <summary>
   - Claude says: <summary>
   - Suggested fix: <action>

### MEDIUM priority (one model found)
1. **[GPT] [file:line]** — <description>
2. **[CLAUDE] [file:line]** — <description>

### Verdict
- BLOCK: X high-priority issues must be fixed
- WARN: Y medium-priority issues to consider  
- PASS: No issues found by either model
```

### 5. Auto-fix (optional)

If the user confirms, Claude can auto-fix:
- **HIGH priority issues:** Fix immediately
- **MEDIUM priority issues:** Ask user for each one
- After fixes, re-run tests:

```bash
pytest tests/ -x -q 2>&1 | head -50
```

## When to use this skill

| Situation | Recommended? |
|-----------|-------------|
| Before important commit | Yes — catch bugs early |
| Before creating PR | Yes — save review round-trips |
| After Codex refactoring | Yes — verify refactored code |
| Trivial typo fix | No — overkill |
| Documentation-only change | No — Codex adds little value |

## Error handling

- If Codex is not installed → run Claude-only review, note that cross-model check was skipped
- If Codex times out → report Claude findings only with note
- If no changes to review → exit with message
- If Codex returns "no issues" and Claude finds problems → report Claude findings as MEDIUM (Codex may have missed Wookiee-specific rules)
