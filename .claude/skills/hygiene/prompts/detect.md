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

Skills can live in two places: project-level `.claude/skills/` (committed, project-specific) and user-level `~/.claude/skills/` (personal, available across all projects). The Supabase `tools` registry tracks all skills. A skill is orphaned only if it exists in neither location.

```bash
# Combine both locations, dedupe.
{ ls .claude/skills/ 2>/dev/null; ls "$HOME/.claude/skills/" 2>/dev/null; } | sort -u > /tmp/hygiene-skills-fs.txt

PYTHONPATH=. python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv('database/sku/.env')
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT','5432'), dbname=os.getenv('POSTGRES_DB','postgres'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD'))
cur = conn.cursor()
cur.execute(\"SELECT slug FROM tools WHERE type='skill' ORDER BY slug\")
for r in cur.fetchall(): print(r[0])
" | sort -u > /tmp/hygiene-skills-db.txt

diff /tmp/hygiene-skills-fs.txt /tmp/hygiene-skills-db.txt
```

Also list project-level only — used to distinguish project skills (committable) from user-level skills (personal):

```bash
ls .claude/skills/ 2>/dev/null | sort -u > /tmp/hygiene-skills-project.txt
```

Match-rules:
- Lines `<` (combined FS, not in DB) → finding `skill-registry-drift / unregistered`, suggested_action: "register via /tool-register". Only flag if also present in `/tmp/hygiene-skills-project.txt` (project-level skills are the ones that should be registered for the team; user-level personal skills can be registered or not at user's discretion — skip them to avoid false positives).
- Lines `>` (in DB, not in combined FS) → finding `skill-registry-drift / orphan`, suggested_action: "ask-user — confirm deletion or restore". This is a real orphan: the skill is gone from both locations.

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
# One git pass for all file mtimes (avoid O(N²) subprocess loop).
git ls-files -z 'shared/*.py' 'services/*.py' 'agents/*.py' 'scripts/*.py' 2>/dev/null \
  | xargs -0 -I{} git log -1 --format='%cr %H {}' -- '{}' 2>/dev/null \
  > /tmp/hygiene-py-ages.txt 2>&1 || true
PYTHONPATH=. python3 - <<'PY'
import ast, pathlib, re
roots = ['shared','services','agents','scripts']
modules = {}
for r in roots:
    if not pathlib.Path(r).exists(): continue
    for p in pathlib.Path(r).rglob('*.py'):
        if '__pycache__' in p.parts: continue
        modules[str(p)] = p.stem
seen = set()
for p in modules:
    try:
        tree = ast.parse(pathlib.Path(p).read_text())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            seen.add(node.module.split('.')[-1])
        elif isinstance(node, ast.Import):
            for n in node.names: seen.add(n.name.split('.')[-1])
ages = {}
try:
    with open('/tmp/hygiene-py-ages.txt') as f:
        for ln in f:
            m = re.match(r'(\d+)\s+(years?|months?|weeks?|days?)\s+ago\s+\S+\s+(.+)$', ln.strip())
            if not m: continue
            n, unit, path = int(m.group(1)), m.group(2), m.group(3)
            days = n * (365 if 'year' in unit else 30 if 'month' in unit else 7 if 'week' in unit else 1)
            ages[path] = days
except FileNotFoundError:
    pass
for p, name in modules.items():
    if name in seen or name == '__init__': continue
    if ages.get(p, 0) >= 60: print(p)
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
# Real secrets in tracked files. Use NUL-separated to handle filenames with spaces/specials.
# Exclude *_FILE=, *_PATH=, *_DIR= (path-shaped values, not secrets). Require base64-shape value.
git ls-files -z \
  | grep -zvE '\.(md|example|sample|json|yaml|yml|toml|html|svg|webp|woff2|css|svelte|eot|tsx|lock)$' \
  | xargs -0 grep -lE '(API_KEY|SECRET|PASSWORD|TOKEN)[A-Z_]*\s*=\s*["\x27]?[A-Za-z0-9+/=_-]{20,}' 2>/dev/null \
  | grep -vE '_(FILE|PATH|DIR)\s*=' \
  | head -20
# .env tracked check
git ls-files | grep -E '^\.env$|/\.env$|\.env\.local$|\.env\.production$' | head
# .env.example sanity (no real values). Skip *_FILE/_PATH/_DIR (path values legit).
grep -E '^[A-Z_]+=([A-Za-z0-9_/+=-]{20,})' .env.example \
  | grep -vE '^[A-Z_]+_(FILE|PATH|DIR)=' \
  | grep -vE '(your-|0000|placeholder|example|xxxxxxxx|sk-or-v1-\.\.\.|ntn_\.\.\.|sk-ant-api03-\.\.\.|AIza\.\.\.|eyJ\.\.\.)' \
  | head
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
