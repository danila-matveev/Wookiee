# Hygiene Autofix — Per-check Verification Rules

For each `ask_user` finding from the hygiene PR, look up the check name here. If a check is NOT listed → automatically `NEEDS_HUMAN`.

This file IS the safe-actions whitelist. Editing it requires a human PR (the `.claude/skills/hygiene-autofix/` directory is in `protected_zones`).

---

## orphan-imports

**Finding shape:** Python file in `shared/`, `services/`, `agents/`, or `scripts/` not imported by any module for 60+ days.

**Verification:**
```bash
MODULE_NAME=$(basename "$path" .py)
REFS=$(grep -rE "(from .* import .*${MODULE_NAME}|import .*${MODULE_NAME})" \
  --include="*.py" \
  --exclude-dir=.claude/worktrees \
  --exclude-dir=__pycache__ \
  --exclude-dir=.git \
  --exclude-dir=docs/archive \
  | grep -v "^${path}:" | wc -l)

# Also check string-based dynamic refs (importlib, registries):
DYNAMIC=$(grep -rE "[\"']${MODULE_NAME}[\"']" \
  --include="*.py" --include="*.yaml" --include="*.yml" --include="*.toml" \
  --exclude-dir=.claude/worktrees \
  | grep -v "^${path}:" | wc -l)

# Also check if file has __main__ entry-point pattern (CLI tool):
HAS_MAIN=$(grep -c 'if __name__ == "__main__"' "$path" || echo 0)
IS_MAIN_FILE=$(echo "$path" | grep -c '__main__\.py$' || echo 0)
```

**SAFE_IF:**
- `REFS == 0` AND
- `DYNAMIC == 0` AND
- `HAS_MAIN == 0` AND
- `IS_MAIN_FILE == 0` AND
- path does NOT match any protected_zone

**UNSAFE_IF:** any of the above conditions fail.

**Action (SAFE):**
```bash
git rm "$path"
git commit -m "chore(hygiene-autofix): orphan-imports — 1 item

Removed: $path
Verification:
- Direct import refs: $REFS
- Dynamic string refs: $DYNAMIC
- __main__ block: $HAS_MAIN
- __main__.py file: $IS_MAIN_FILE"
```

**Special case for `__main__.py` redirect files:** If file is named `__main__.py` AND its content is just `from X.runner import main; main()` AND no documented invocation uses bare `python -m X` (only `python -m X.runner`) → SAFE. Verify by `grep -rE "python -m ${PARENT_MODULE}\b" --include="*.md" --include="*.sh" --include="*.yml"` returns 0 lines that don't have `.runner` after.

---

## broken-doc-links

**Finding shape:** `BROKEN: <file>:<line> -> <link>` from detect.md check 11.

**Verification:**
```bash
SRC_FILE=$(echo "$finding_path" | cut -d: -f1)
LINK=$(echo "$evidence" | grep -oE '-> .*' | sed 's/^-> //')
SRC_DIR=$(dirname "$SRC_FILE")

# Try resolving relative to source file's directory AND repo root:
RESOLVED_FROM_SRC=$(cd "$SRC_DIR" && readlink -f "$LINK" 2>/dev/null)
RESOLVED_FROM_ROOT=$(readlink -f "$LINK" 2>/dev/null)

EXISTS_FROM_SRC=$([ -e "$RESOLVED_FROM_SRC" ] && echo 1 || echo 0)
EXISTS_FROM_ROOT=$([ -e "$RESOLVED_FROM_ROOT" ] && echo 1 || echo 0)
```

**SAFE_IF:** `EXISTS_FROM_SRC == 1` OR `EXISTS_FROM_ROOT == 1` — meaning the link target DOES exist; this is a detector false positive.

**Action (SAFE):** No file change. Comment in PR:

```
⏸️ broken-doc-links / $SRC_FILE:$LINE → $LINK
False positive: target exists at $(realpath of working candidate). Detector bug — see prompts/detect.md check 11. Skipped.
```

(In future iteration, fix the detector. For now, autofix only acknowledges the false positive.)

**UNSAFE_IF:** target does NOT exist anywhere.

**Action (UNSAFE):** Skip with comment:

```
⏸️ broken-doc-links / $SRC_FILE:$LINE → $LINK
Target missing. Could be: (a) renamed file (need to find new path), (b) intentionally placeholder for future doc, (c) typo. Needs human judgment.
```

---

## structure-conventions

**Finding shape:** Service in `services/X/` deviates from the dominant Python module layout (no `__init__.py`, no `config.py`).

**Verification:**
```bash
SERVICE_DIR="$path"  # e.g. services/influencer_crm_ui
HAS_PACKAGE_JSON=$([ -f "$SERVICE_DIR/package.json" ] && echo 1 || echo 0)
HAS_TS_CONFIG=$([ -f "$SERVICE_DIR/tsconfig.json" ] && echo 1 || echo 0)
HAS_VITE=$([ -f "$SERVICE_DIR/vite.config.ts" ] || [ -f "$SERVICE_DIR/vite.config.js" ] && echo 1 || echo 0)
HAS_PY_FILES=$(find "$SERVICE_DIR" -maxdepth 2 -name "*.py" 2>/dev/null | head -1 | wc -l)
```

**SAFE_IF:** `(HAS_PACKAGE_JSON == 1 OR HAS_TS_CONFIG == 1 OR HAS_VITE == 1)` AND `HAS_PY_FILES == 0`. This means the service is genuinely non-Python (TS/Vite frontend, Node service, etc.) — adding `__init__.py` would be wrong.

**Action (SAFE):** Add to whitelist via PR comment, NOT direct edit:

> The hygiene-config.yaml is in `protected_zones`. Autofix MUST NOT edit it directly. Instead, leave a high-confidence comment for human:

```
⏸️ structure-conventions / $SERVICE_DIR
Verification: package.json=$HAS_PACKAGE_JSON tsconfig.json=$HAS_TS_CONFIG vite.config=$HAS_VITE py_files=$HAS_PY_FILES.
Conclusion: TS/Node frontend, not a Python module. Recommend adding to .claude/hygiene-config.yaml whitelist.structure_conventions_exceptions:
  - $SERVICE_DIR  # auto-detected: TS/Vite frontend (package.json + tsconfig.json present)

This recommendation has high confidence — please add the line and re-run hygiene to clear this finding.
```

**UNSAFE_IF:** Has Python files OR no clear non-Python signal.

**Action (UNSAFE):** Skip with reason "not clearly non-Python; needs human judgment".

---

## skill-registry-drift

**Finding shape:** Skill in Supabase `tools` registry but missing from `.claude/skills/` AND `~/.claude/skills/`. Suggested action: "ask-user — confirm deletion or restore".

**Verification:**
```bash
SLUG=$(echo "$evidence" | head -1)  # the missing slug
# Check both project-level AND user-level (skill might be user-level only):
ls .claude/skills/"$SLUG"/SKILL.md 2>/dev/null
ls "$HOME/.claude/skills/$SLUG"/SKILL.md 2>/dev/null

# Check if mirrors have it (might be partial-sync state):
ls .cursor/skills/"$SLUG"/SKILL.md 2>/dev/null
ls .codex/skills/"$SLUG"/SKILL.md 2>/dev/null
```

**SAFE_IF:** Skill exists in `.cursor/skills/` OR `.codex/skills/` (mirror has it but `.claude/skills/` is missing). This is a sync drift; the skill is not actually deleted.

**Action (SAFE):** Restore `.claude/skills/<slug>/` from `.cursor/skills/<slug>/` (rsync). Then commit.

```bash
SOURCE=".cursor/skills/$SLUG"
[ ! -d "$SOURCE" ] && SOURCE=".codex/skills/$SLUG"
rsync -a "$SOURCE/" ".claude/skills/$SLUG/"
git add ".claude/skills/$SLUG/"
git commit -m "chore(hygiene-autofix): skill-registry-drift — restored $SLUG from mirror"
```

**UNSAFE_IF:** Not in any of the 4 locations (truly orphaned). User needs to decide: delete from registry or restore manually.

---

## cross-platform-skill-prep

**Finding shape:** Skill in `.claude/skills/` but missing from `.cursor/skills/` and/or `.codex/skills/`. Suggested action: `auto_sync via /ecosystem-sync`.

**Note:** /hygiene auto-fixes most of these in its own auto bucket. By the time autofix runs, only "ask_user" cases remain — typically ones blocked by some edge case in /ecosystem-sync.

**Verification:**
```bash
SLUG="$path"  # e.g. product-launch-review
SOURCE_DIR=".claude/skills/$SLUG"
[ ! -d "$SOURCE_DIR" ] && exit 1  # not in source — different problem

# Check what mirror is missing it:
MISSING_CURSOR=$([ ! -d ".cursor/skills/$SLUG" ] && echo 1 || echo 0)
MISSING_CODEX=$([ ! -d ".codex/skills/$SLUG" ] && echo 1 || echo 0)
```

**SAFE_IF:** Source exists at `.claude/skills/$SLUG/` and at least one mirror is missing.

**Action (SAFE):**
```bash
[ "$MISSING_CURSOR" = "1" ] && rsync -a --delete ".claude/skills/$SLUG/" ".cursor/skills/$SLUG/"
[ "$MISSING_CODEX" = "1" ] && rsync -a --delete ".claude/skills/$SLUG/" ".codex/skills/$SLUG/"
git add .cursor/skills/"$SLUG"/ .codex/skills/"$SLUG"/
git commit -m "chore(hygiene-autofix): cross-platform-skill-prep — synced $SLUG to mirrors"
```

---

## orphan-docs

**Finding shape:** `.md` file in `docs/` not referenced by any other doc for 60+ days.

**Verification:**
```bash
# Check if refactor-audit notes mark this file as ARCHIVE:
AUDIT_NOTE=$(grep -rE "$(basename "$path") *(→|->|=>) *(docs/archive|ARCHIVE|archive/)" \
  .planning/refactor-audit/ \
  --include="*.md" 2>/dev/null | head -3)

# Already in docs/archive/?
IN_ARCHIVE=$(echo "$path" | grep -c "^docs/archive/" || echo 0)
```

**SAFE_IF:** `IN_ARCHIVE == 0` AND `AUDIT_NOTE` non-empty (refactor-audit explicitly marked as ARCHIVE).

**Action (SAFE):**
```bash
TARGET="docs/archive/$(basename "$path")"
git mv "$path" "$TARGET"
git commit -m "chore(hygiene-autofix): orphan-docs — moved $(basename "$path") to archive

Refactor-audit note: $AUDIT_NOTE"
```

**UNSAFE_IF:** Already in archive (nothing to do — should not be flagged) OR no audit note (judgment call: archive vs delete vs index — needs human).

---

## All other checks → NEEDS_HUMAN

These are deliberately NOT in autofix v1 scope:

- `stale-branches` — could be active feature work, requires team context
- `obsolete-tracked-files` — too broad, false-positive prone
- `missing-readme` — writing README content requires judgment about service purpose
- `empty-directories` (tracked .gitkeep) — could be intentional placeholder for future code
- `gitignore-violations` — auto-fixed by /hygiene already; if it reaches autofix, something complex
- `pycache-committed` — auto-fixed by /hygiene already
- `security-scan` — NEVER autofix security findings; always human
- `unpushed-work` — auto-fixed by /hygiene
- `stray-binaries` — auto-fixed by /hygiene
- `icloud-dupes` — auto-fixed by /hygiene

If autofix sees any of these in ask_user, comment with:

```
⏸️ <check> / <path>
Outside autofix v1 scope — needs human review. Reason: <one line of why this requires judgment>.
```

---

## Adding new checks to the SAFE list

Process for expanding this whitelist:

1. Run /hygiene-autofix in observation mode for ≥2 weeks to see how many of `<check>` findings appear
2. Manually review what the right action would be for each
3. If the action is mechanical and verifiable → write a verification rule here
4. Open a PR (this directory is in protected_zones — human review required)
5. After merge, autofix picks up the new check on the next run

**Never** silently expand the whitelist via env var, config flag, or runtime override. Whitelist additions are auditable changes to this file only.
