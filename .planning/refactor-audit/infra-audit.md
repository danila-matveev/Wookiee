# Infra Audit — Refactor v3 Phase 1

**Date:** 2026-04-24
**Auditor:** audit-infra (read-only)
**Zones:** `deploy/`, `docker-compose*.yml`, `.claude/` (project), `.env.example`, `.gitignore`, `pyproject.toml`, `Makefile`, `setup_bot.sh`, `.mcp.json`, `.github/`, `.agents/`, `.kiro/`, `.superpowers/`, `.playwright-mcp/`, `output/`

---

## 1. Summary

| File | Change count | Severity |
|---|---|---|
| `deploy/docker-compose.yml` | 0 services to remove, 0 to update — **already clean** (vasily-api/dashboard-api already gone) | LOW |
| `.mcp.json` | 0 entries to remove (file contains only external MCPs) — **real target is `.claude/settings.local.json`** (4 entries to remove) | MEDIUM |
| `.gitignore` | ~15 additions (binaries, output/, playwright-mcp, agent runtime, editor) + 2 whitelist exceptions | HIGH |
| `git rm --cached` | 4 paths (3 .playwright-mcp yml, 1 .docx business doc) | MEDIUM |
| `deploy/` | 2 files to delete (`deploy-v3-migration.sh`, `docker-compose.local.yml`) | LOW |
| `.claude/` | 3 broken symlinks to audit (agent-browser, agentcore, etc. → `.agents/skills/`), 1 stale command (`sync-sheets.md`) | LOW |
| `pyproject.toml` | 1 stale path reference (`src = ["agents", ...]` — agents/ будет пустым после PR#5) | LOW |
| `Makefile` | 3 targets to remove (all Oleg-specific), replace with new ones | MEDIUM |
| `.env.example` | 3 stale sections (VASILY_*, LYUDMILA_BOT_TOKEN, ZAI_API_KEY), 1 misleading comment | LOW |
| `setup_bot.sh` | **Delete entirely** — references `bot/` dir which doesn't exist | MEDIUM |
| Untracked artifacts | `.playwright-mcp/` ignore permanently, `output/` ignore + delete contents (604MB rogue file), `scripts/wb_promocodes_test.py` commit or delete | HIGH (disk space) |

**Critical find:** `output/wb_promocodes_test/rows_2026-04-24.jsonl` = **604 MB**. Must be deleted before any git operations.

**Critical find:** `.mcp.json` does NOT contain the 4 local MCPs (wookiee-data/kb/marketing/price). Those entries live in `.claude/settings.local.json` — spec §5.1 target wrong file. Plan step will address this.

---

## 2. docker-compose.yml changes

### 2.1 Current state (deploy/docker-compose.yml, 239 lines)

**Services present (7):**
1. `wookiee-oleg` — Oleg v2 cron container
2. `sheets-sync` — Google Sheets ↔ Supabase daily
3. `wb-logistics-api` — HTTP endpoint for Sheets button
4. `wb-mcp-ip` — Wildberries MCP (ИП cabinet)
5. `wb-mcp-ooo` — Wildberries MCP (ООО cabinet)
6. `bitrix24-mcp` — Bitrix24 MCP
7. `knowledge-base` — Vector KB API (profile: optional)

**NO services for `vasily-api` or `dashboard-api` present.** cleanup-v2 §2.5 targets are already fulfilled in this file.

### 2.2 Services to remove

**None** — `vasily-api` and `dashboard-api` already absent. Verified line-by-line, 239 lines.

### 2.3 Services to update

| Service | Change | Why |
|---|---|---|
| `wookiee-oleg` | Remove `../agents/oleg/data:/app/agents/oleg/data` volume mount | After PR #5 removes `agents/oleg/` the mount becomes orphan. Replace with `../data:/app/data` if runtime data persists, else drop. |
| `wookiee-oleg` | Consider rename to `wookiee-cron` or `wookiee-scheduler` — it's a cron dispatcher for scripts, not Oleg-specific | cleanup-v2 §3.4 equivalent rename decision; orchestrator finalizes |
| `knowledge-base` | Confirm `services/knowledge_base/` keep/drop (spec §3.2 flagged item) before leaving or removing | If removed → drop this service block |

### 2.4 Sister file: `deploy/docker-compose.local.yml`

**Delete entirely (35 lines).** Runs `agents.oleg.mcp_server` which will not exist after PR #5.

### 2.5 Final YAML sketch (after PR #5 — oleg cleanup)

```yaml
services:
  wookiee-cron:            # renamed from wookiee-oleg
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    # cron command unchanged (uses scripts/, not agents/oleg)
    volumes:
      - ../data:/app/data         # or drop entirely
      - ../services/etl/data:/app/services/etl/data
      - ../reports:/app/reports
      - ../scripts:/app/scripts:ro
    # ...

  sheets-sync:        # unchanged
  wb-logistics-api:   # unchanged
  wb-mcp-ip:          # unchanged
  wb-mcp-ooo:         # unchanged
  bitrix24-mcp:       # unchanged
  knowledge-base:     # conditional — remove if service/knowledge_base/ is gone
```

---

## 3. .mcp.json changes

### 3.1 Current state (root `.mcp.json`, 45 lines)

```json
{
  "mcpServers": {
    "wildberries-ip":  { "command": "node", "args": ["../wildberries-mcp-server/dist/index.js"], ... },
    "wildberries-ooo": { ... },
    "finolog":         { "command": "node", "args": ["../finolog-mcp-server/dist/index.js"], ... },
    "ozon":            { "command": "node", "args": ["../ozon-mcp-server/dist/index.js"], ... }
  }
}
```

**No `wookiee-data` / `wookiee-kb` / `wookiee-marketing` / `wookiee-price` in this file.**

### 3.2 Where the 4 local MCPs actually live

**`.claude/settings.local.json`** (lines 11-44) — the spec §3 target. These 4 entries reference `mcp_servers/wookiee_*/server.py` which PR #4 removes.

### 3.3 Changes required

#### root `.mcp.json`

**Entries to remove:** NONE (file is already clean). Note: this file is gitignored (`.gitignore` line 120) — so it's a local dev file and not committed.

**Entries to preserve:**
- `wildberries-ip`, `wildberries-ooo` — external MCP clone, actively used
- `finolog` — external MCP clone, actively used
- `ozon` — external MCP clone, actively used

**Final sketch:** identical to current (no change).

#### `.claude/settings.local.json`

Remove entire `mcpServers` block + remove `wookiee-*` names from `disabledMcpjsonServers` (the list currently only has external names, so that part is already fine, but double-check after edit).

**Final sketch of settings.local.json after PR #4:**
```json
{
  "permissions": { "allow": [] },
  "disabledMcpjsonServers": [
    "wildberries-ip",
    "wildberries-ooo",
    "finolog",
    "ozon"
  ]
}
```

**Note for spec/manifest:** The spec line 82 says "`.mcp.json` entries" — orchestrator must redirect this to `.claude/settings.local.json`. `.mcp.json` itself needs no change.

---

## 4. .gitignore additions

### 4.1 Current contents overview

`.gitignore` has 195 lines in 14 logical sections: Python, IDEs, env/secrets, OS files (incl. iCloud `* 2.*` glob — good), agent data/logs, reports, Notion cache, Docker, Jupyter, testing, type-checking, Claude Code (ignores `.claude/settings.local.json` + `.mcp.json`), archives, binaries (`*.xlsx *.xls *.zip *.pdf *.png *.jpg *.jpeg` — **no whitelist exceptions**), runtime, logs, node_modules, MCP cloned repos, generated data, KB reference files, worktrees. Good coverage overall; gaps are binaries whitelist, output/, .playwright-mcp, editor leftovers, agent runtime state.

### 4.2 Rules to add

#### Binary whitelist exceptions (CRITICAL — otherwise pattern `*.xlsx` wipes kept files)

```gitignore
# Whitelist: logistics audit finalized deliverables + tariff reference
!services/logistics_audit/*Итоговый*.xlsx
!services/logistics_audit/*v2-final*.xlsx
!services/logistics_audit/*Тарифы*.xlsx
```

These names match cleanup-v2 §2.2 "ОСТАВИТЬ" list.

#### Additional binary extensions

```gitignore
*.docx
*.wmv
*.mp4
*.mov
```

(`.docx` currently tracked: `2026_Договор купли-продажи Familia -Чернецкая.docx` — needs untrack.)

#### iCloud numbered dupes (extend current `* 2.*` glob)

```gitignore
* 2.*
* 2/
* 2 [0-9]*
'* 2.*'
"scripts 2.txt"
"skills-lock 2.json"
```

Current `* 2.*` rule in `.gitignore` line 65 already covers most — but verify untracked `scripts 2.txt` and `skills-lock 2.json` are ignored (the glob does catch them: `scripts 2.txt` matches `* 2.*`). **No change needed here** — but `git rm --cached` may be needed (see §4.4).

#### Agent runtime / scheduled-tasks

```gitignore
# Claude Code runtime
.claude/scheduled_tasks.lock
.claude/plans/      # already present
```

(`.claude/scheduled_tasks.lock` currently exists untracked at repo root — add to ignore.)

#### Playwright MCP outputs

```gitignore
.playwright-mcp/
!.playwright-mcp/.gitkeep
```

(Currently 3 `page-*.yml` files are tracked from 2026-03-31 — per cleanup-v2 §2.5 should be gone. PR #1 deletes them; PR #2 adds this rule.)

#### Output / temp generated

```gitignore
output/
scratch/
_scratch/
.scratch/
```

(`output/` currently contains 604MB jsonl test artifact — must be deleted + ignored.)

#### Editor / OS leftovers (extend)

```gitignore
.cursorignore           # currently tracked — decide keep or ignore (it's a cursor config, typically commit)
.ruff_cache/
.pytype/
.pyre/
.cache/
```

(`.cursorignore` IS committed currently, acceptable. `.ruff_cache/` is not yet ignored — add it.)

#### Project-local build artifacts

```gitignore
# Superpowers per-session state — only brainstorm/ currently ignored
.superpowers/**/artifacts/
.superpowers/**/*.cache

# GSD planning scratch
.planning/debug/
!.planning/refactor-audit/
!.planning/phases/
!.planning/milestones/
```

### 4.3 Whitelist exceptions (consolidated)

| Pattern blocked | Whitelist exception | Reason |
|---|---|---|
| `*.xlsx` | `!services/logistics_audit/*Итоговый*.xlsx` | ИП Фисанов итоговый аудит — source-of-truth deliverable |
| `*.xlsx` | `!services/logistics_audit/*v2-final*.xlsx` | ООО Wookiee перерасчёт (финал) |
| `*.xlsx` | `!services/logistics_audit/*Тарифы*.xlsx` | справочник тарифов (используется скриптами) |
| `*.png` | `!wookiee-hub/public/**/*.png` | фронтенд-ассеты (hub оставляем 2 модуля) |
| `.playwright-mcp/` | `!.playwright-mcp/.gitkeep` | сохранить пустую директорию если нужна |
| `.superpowers/brainstorm/` (уже есть) | `!.superpowers/brainstorm/README.md` (опционально) | если документация про то что тут не коммитится |

### 4.4 Files currently tracked — need `git rm --cached` after new rules added

| Path | Why |
|---|---|
| `.playwright-mcp/page-2026-03-31T23-56-07-942Z.yml` | Снимок браузера, case-by-case tracked (bug in git) |
| `.playwright-mcp/page-2026-03-31T23-56-50-135Z.yml` | то же |
| `.playwright-mcp/page-2026-04-01T00-06-46-413Z.yml` | то же |
| `2026_Договор купли-продажи Familia -Чернецкая.docx` | Бизнес-документ в трекинге (cleanup-v2 §2.1) |

**Potentially also check** (from cleanup-v2, spec indicates should already be unstaged):
- Any of the `*Итоговый*.xlsx`, `*v2-final*.xlsx`, `*Тарифы*.xlsx` from logistics_audit — should be **re-added** after whitelist rule lands, since `*.xlsx` currently ignored them.

Command sequence for PR #2:
```bash
git rm --cached '.playwright-mcp/page-2026-03-31T23-56-07-942Z.yml'
git rm --cached '.playwright-mcp/page-2026-03-31T23-56-50-135Z.yml'
git rm --cached '.playwright-mcp/page-2026-04-01T00-06-46-413Z.yml'
git rm --cached '2026_Договор купли-продажи Familia -Чернецкая.docx'
# After .gitignore updated:
git add -f services/logistics_audit/*Итоговый*.xlsx services/logistics_audit/*v2-final*.xlsx services/logistics_audit/*Тарифы*.xlsx
```

---

## 5. .claude/ audit (project-level only)

### 5.1 Active skills in `.claude/skills/`

26 entries total (directories + symlinks + one stray .md):

**Project-owned skill dirs (22):**
- `abc-audit/`
- `analytics-report/`
- `codex-arch-review/`
- `codex-quality-gate/`
- `codex-refactor/`
- `content-search/`
- `daily-brief/`
- `finance-report/`
- `finolog-dds-report/`
- `funnel-report/`
- `gws/`
- `gws-drive/`
- `gws-sheets/`
- `logistics-report/`
- `market-review/`
- `marketing-report/`
- `monthly-plan/`
- `pullrequest/`
- `reviews-audit/`
- `tool-register/`
- `tool-status/`
- `ui-ux-pro-max/`
- `workflow-diagram/`

**Symlinks to `.agents/skills/` (6) — external Vercel Labs skills:**
- `agent-browser` → `../../.agents/skills/agent-browser`
- `agentcore` → `../../.agents/skills/agentcore`
- `dogfood` → `../../.agents/skills/dogfood`
- `electron` → `../../.agents/skills/electron`
- `slack` → `../../.agents/skills/slack`
- `vercel-sandbox` → `../../.agents/skills/vercel-sandbox`

All symlink targets resolve (verified `.agents/skills/` contains 6 matching dirs). **Per cleanup-v2 §3:** these auto-install via `skills-lock.json` — keep.

### 5.2 Orphan / test dirs

| Path | Verdict |
|---|---|
| `.claude/skills/sync-sheets.md` (file, not dir) | **Stale** — predates skill-dir convention. 2675 bytes, `Apr 18`. Either convert to `sync-sheets/SKILL.md` or delete (content probably duplicated in `gws-sheets` + sheets_sync service). |
| `.claude/commands/sync-sheets.md` equivalent | Not found — just the skills-level file. Safe to delete. |
| `.claude/plans/` | Already gitignored; noted OK. |
| `.claude/scheduled_tasks.lock` | Runtime lock, 91 bytes, untracked — add to `.gitignore` (see §4.2). |

### 5.3 `.claude/commands/` (5 files)

All active project commands:
- `gws-drive.md`, `gws-sheets.md` — wrappers for gws CLI
- `pullrequest.md` — matches the bundled `pullrequest` skill
- `update-docs.md` — docs update routine
- `workflow-diagram.md` — wraps the workflow-diagram skill

**No changes.** Keep all.

### 5.4 `.claude/agents/` (3 files)

- `data-analyst.md`
- `etl-engineer.md`
- `wb-specialist.md`

Custom agent personas. Not referenced in recent refactor specs. **Keep** (low risk). Orchestrator can flag if redundant.

### 5.5 `.claude/rules/` (5 files)

- `analytics.md`, `data-quality.md`, `economics.md`, `infrastructure.md`, `python.md`

All actively sourced by `CLAUDE.md`. Keep unchanged.

### 5.6 `.claude/settings.json` & `.claude/settings.local.json`

- `settings.json` — 22 lines, permissions include legacy `Desktop/Документы/Cursor/Wookiee/.claude/**` paths (pre-migration). **Update:** drop those rows once migration is confirmed complete. Keep current-repo permissions.
- `settings.local.json` — contains the 4 local MCP entries that must be removed in PR #4 (see §3.3).

### 5.7 Hooks

`settings.json` has empty `"hooks": {}`. Nothing to preserve/update. If Phase 2 `/hygiene` skill adds hooks, that PR owns them.

---

## 6. deploy/ audit

### 6.1 Current files (10)

| File | Status | Action |
|---|---|---|
| `Dockerfile` | Main image (oleg/sheets_sync). Copies `agents/`, `services/`, `scripts/`, `shared/`. | **Update** PR #5: drop `COPY agents/` line after oleg removal; `agents/` will be empty scaffold. |
| `Dockerfile.knowledge_base` | Active | Keep (or drop with service if §3.2 decides) |
| `Dockerfile.sheets_sync` | 432 bytes, likely minimal — appears unused (main Dockerfile handles sheets_sync via compose command override) | **Flag for orchestrator** — grep usage: referenced only in compose? If not, delete. |
| `Dockerfile.wb_logistics_api` | Active | Keep |
| `deploy-v3-migration.sh` | **One-shot V2→V3 migration script**, already executed months ago, references retired `agents.v3` | **DELETE** (cleanup-v2 §2.5 explicitly lists) |
| `deploy.sh` | Current active deploy script | Keep (update: remove Oleg-specific references in log strings; service rename `wookiee-oleg` → new name if rename lands) |
| `docker-compose.yml` | Active | Update per §2 |
| `docker-compose.local.yml` | Launches `agents.oleg.mcp_server` (V2 artifact, removed in PR #5) | **DELETE** |
| `healthcheck.py` | Active | Keep |
| `healthcheck_agent.py` | References Oleg agent? **Flag for orchestrator** — if references agents/oleg, delete after PR #5 | Flagged |

### 6.2 Scripts to update

- `deploy.sh` lines 14-15: rename `CONTAINER="wookiee_oleg"` / `SERVICE="wookiee-oleg"` if service renamed. Russian log strings unchanged.
- `healthcheck.py` + `healthcheck_agent.py`: grep for oleg imports. Adjust.

---

## 7. Other (pyproject, Makefile, .env.example, setup_bot.sh, .github/)

### 7.1 pyproject.toml (45 lines)

**Stale entries:**
- `src = ["agents", "shared", "scripts", "services"]` — `agents/` will be empty scaffold after PR #5. **Keep `agents`** in src list (scaffold stays), or drop — low impact.
- `testpaths = ["tests", "services/marketplace_etl/tests"]` — confirmed both paths exist. Keep.
- All ruff ignores reference "existing" counts (130, 110, 29, etc.) — comment refs are stale post-cleanup but don't affect behaviour. **Refresh comments in PR #7** (docs-unification).

**No dependencies block** — no stale deps to prune here. (Deps live in `agents/oleg/requirements.txt` + `services/sheets_sync/requirements.txt`.)

### 7.2 Makefile (24 lines)

**Stale targets (ALL 4 current):**
- `oleg` — runs `python3 -m agents.oleg` (module deleted PR #5)
- `oleg-test` — runs `pytest tests/oleg` (dir deleted PR #5)
- `oleg-check` — runs `agents.oleg.check_scheduler` (deleted PR #5)
- `oleg-deploy` — runs `deploy/deploy.sh` (still valid, rename target)

**Proposed replacement (PR #7):**
```makefile
.PHONY: test lint deploy help

# ── Testing ────────────────────────────────
test:             ## Все тесты
	python3 -m pytest tests/ -v

test-etl:         ## ETL тесты
	python3 -m pytest services/marketplace_etl/tests -v

# ── Quality ────────────────────────────────
lint:             ## Ruff lint
	ruff check agents services shared scripts

# ── Deploy ─────────────────────────────────
deploy:           ## Собрать и задеплоить на прод (timeweb)
	bash deploy/deploy.sh

help:             ## Показать команды
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
```

### 7.3 .env.example (105 lines)

**Stale sections:**
- `LYUDMILA_BOT_TOKEN` (line 44) — Lyudmila retired (cleanup-v2 §2.5 archive). **Remove.**
- `VASILY_SPREADSHEET_ID`, `VASILY_BITRIX_CHAT_ID`, `VASILY_BITRIX_FOLDER_ID` (lines 89-91) — Vasily removed. **Remove.**
- `VASILY_API_KEY` (line 104) — same. **Remove.**
- `ZAI_API_KEY` (lines 53-54) — z.ai was primary, now OpenRouter is sole LLM provider (per `.claude/rules/economics.md`). **Remove.**
- `CLAUDE_API_KEY` (line 60) — OpenRouter wraps Claude, so direct key unused. **Flag for orchestrator** (may still be used as escape hatch).

**Misleading comments:**
- Line 53: `# z.ai (primary - дешевый, ~$0.002/запрос)` — primary is OpenRouter per economics rules.

**Keep:** WB, OZON, MPSTATS, FINOLOG, Google Sheets, МойСклад, Bitrix24, TELEGRAM_BOT_TOKEN, BOT_PASSWORD_HASH, OPENROUTER_API_KEY, GEMINI_API_KEY, DB_*, SUPABASE_*, NOTION_*, ADMIN_CHAT_ID, LOG_LEVEL.

### 7.4 setup_bot.sh (109 lines)

**Entire file is stale.** References:
- `bot/requirements.txt` — `bot/` dir doesn't exist in repo
- `bot/.env`, `bot/.env.example` — don't exist
- `bot/data`, `bot/logs` directories
- `python -m bot.main` — module doesn't exist
- `DEPLOYMENT.md` — doesn't exist

**Verdict: DELETE entirely.** Add proper install steps to `ONBOARDING.md` (PR #7) instead.

### 7.5 .github/ (3 files)

**`.github/PULL_REQUEST_TEMPLATE.md`** — 737 bytes, Apr 18. Content unknown here but spec §5.2 prescribes a new template; PR #7 overwrites.

**`.github/workflows/ci.yml`** — installs `agents/oleg/requirements.txt` + `services/sheets_sync/requirements.txt`. After PR #5, Oleg reqs file path disappears. **Update needed:**
```yaml
# Change:
pip install -r agents/oleg/requirements.txt
# To:
pip install -r requirements.txt   # or consolidate into pyproject.toml deps
```
Also: `ruff check agents services shared scripts` — `agents/` empty is fine (ruff skips empty), keep.

**`.github/workflows/deploy.yml`** — healthcheck loop references `wookiee_oleg wookiee_sheets_sync`. After rename: update container name. Uses `DEPLOY_HOST/USER/SSH_KEY` secrets (OK).

### 7.6 Summary of non-docker config updates

| File | Lines touched | PR |
|---|---|---|
| `pyproject.toml` | ~1 (`src` list if scaffolded `agents/` dropped) | #7 |
| `Makefile` | Full rewrite | #7 |
| `.env.example` | -6 lines (Vasily/Lyudmila/ZAI) | #4 or #5 |
| `setup_bot.sh` | **-109 (delete)** | #5 |
| `.github/workflows/ci.yml` | ~3 (requirements path) | #5 |
| `.github/workflows/deploy.yml` | ~1 (container name) | #5 or #7 |
| `.github/PULL_REQUEST_TEMPLATE.md` | Rewrite per spec §5.2 | #7 |

---

## 8. Untracked root-level artifacts

### 8.1 `.playwright-mcp/` (99 files, 1.6 MB total)

- **Tracked (3):** `page-2026-03-31T23-56-07-942Z.yml`, `page-2026-03-31T23-56-50-135Z.yml`, `page-2026-04-01T00-06-46-413Z.yml`
- **Untracked (45 .yml page snapshots + 51 .log console dumps):** all dates 2026-03-26 to 2026-04-24. Contain HTML snapshots of admin UIs (Supabase, Notion, Google Search) with potential sensitive tokens visible.

**Verdict: IGNORE PERMANENTLY.**
- Add `.playwright-mcp/` to `.gitignore` (§4.2)
- `git rm --cached` the 3 tracked files
- Delete all content locally in PR #1 (no commit): `rm -rf .playwright-mcp/*`

### 8.2 `output/` (590 MB, contains `wb_promocodes_test/`)

Contents of `output/wb_promocodes_test/`:
- `rows_2026-04-24.jsonl` — **604 MB** (!!) raw WB promocodes API dump
- `raw_2026-04-24.json` — 14 KB sample
- `promo_samples_2026-04-24.json` — 14 KB samples
- `report_2026-04-24.md` — 4 KB report
- `keys_2026-04-24.txt` — 1.3 KB

**Verdict: IGNORE PERMANENTLY + DELETE NOW.** Test artifacts from `scripts/wb_promocodes_test.py`. The 604 MB file is the #1 disk-space offender in the repo.

Actions:
- Add `output/` to `.gitignore` (§4.2)
- Manual: `rm -rf output/wb_promocodes_test/` — user should do (disk cleanup, not git action)
- Reason to keep `output/` as a convention directory: scripts routinely write test artifacts here; permanently-ignored is the right model

### 8.3 `scripts/wb_promocodes_test.py`

Untracked test script. Produces the 604 MB artifact above.

**Verdict options (orchestrator picks):**
1. **Commit** — if this is a reusable tool, add it to `scripts/`. Pair with a `scripts/README.md` note.
2. **Move to `tests/scripts/` + commit** — if it's a one-off verification (likely, given `_test` suffix).
3. **Delete** — if already replaced by proper integration in logistics-report or a service.

Recommendation: **move to `tests/manual/wb_promocodes.py`** + add a short docstring + .gitignore the `output/` it writes to. Lightweight middle path.

### 8.4 Other untracked noteworthy at root

- `.claude/scheduled_tasks.lock` — runtime state (ignore rule §4.2)
- `scripts 2.txt`, `skills-lock 2.json` — iCloud dupes, already caught by `* 2.*` glob (verify with `git check-ignore -v "scripts 2.txt"` before trusting)
- `agent-dashboard-full.png`, `mockup-full-page.png`, `google-notion-search.png`, `notion-crm-gallery.png` — covered by `*.png` rule already
- `scripts.txt` (shell history) — `*.txt` not currently ignored; **add `scripts.txt`** explicitly or a pattern `scripts*.txt` to `.gitignore`

---

## 9. Cross-file alignment with refactor-v3 spec

| Spec ref | Item | Status in this audit |
|---|---|---|
| §3.1 | `.mcp.json` entries wookiee-* | Redirected: actually in `settings.local.json` (§3.3) |
| §3.1 | `mcp_servers/*` | Dir exists, 5 subdirs (common + 4 servers), ~0 bytes `__init__.py` — all empty placeholders. Safe to delete entirely in PR #4. |
| §3.1 | `.wmv` file in logistics_audit | Already covered by new `*.wmv` ignore rule (§4.2) + manual rm |
| §3.1 | `scripts 2.txt`, `skills-lock 2.json` | Already covered by `* 2.*` glob |
| §5.1 | branch protection / auto-merge | Out of scope for this audit (GitHub config, not repo files) |
| §5.2 | `.github/pull_request_template.md` | Template exists as `PULL_REQUEST_TEMPLATE.md` (uppercase). Spec's lowercase may indicate new file; orchestrator clarifies. |

---

## 10. Change counts per file

| File / area | Add | Remove | Update | Total edits |
|---|---|---|---|---|
| `.gitignore` | ~18 lines | 0 | 0 | 18 |
| `.mcp.json` | 0 | 0 | 0 | 0 |
| `.claude/settings.local.json` | 0 | 4 MCP entries (~35 lines) | 0 | 1 |
| `.claude/settings.json` | 0 | ~6 legacy-path permissions | 0 | 1 |
| `.claude/skills/sync-sheets.md` | 0 | 1 file | 0 | 1 |
| `deploy/docker-compose.yml` | 0 | 0 services | 1-2 services (oleg volume, optional rename) | 1 |
| `deploy/docker-compose.local.yml` | 0 | 1 file (35 lines) | 0 | 1 |
| `deploy/deploy-v3-migration.sh` | 0 | 1 file (135 lines) | 0 | 1 |
| `deploy/Dockerfile` | 0 | 0 | 1 line (COPY agents/) | 1 |
| `deploy/Dockerfile.sheets_sync` | 0 | possibly 1 file (verify) | 0 | 0-1 |
| `deploy/deploy.sh` | 0 | 0 | ~2 lines | 1 |
| `pyproject.toml` | 0 | 0 | 0-1 line | 0-1 |
| `Makefile` | 5 lines | 15 lines | 0 | full rewrite |
| `.env.example` | 0 | ~6 lines | ~1 comment | 2 |
| `setup_bot.sh` | 0 | 1 file (109 lines) | 0 | 1 |
| `.github/workflows/ci.yml` | 0 | 0 | ~2 lines | 1 |
| `.github/workflows/deploy.yml` | 0 | 0 | ~1 line | 1 |
| `.github/PULL_REQUEST_TEMPLATE.md` | 0 | 0 | rewrite | 1 |
| `git rm --cached` | 0 | 4 paths | 0 | 4 |
| `rm -rf` (disk) | 0 | `.playwright-mcp/*`, `output/wb_promocodes_test/` | 0 | 2 |

**Total files touched: ~17.**

---

## 11. Flagged items (orchestrator decides)

1. **Rename `wookiee-oleg` container** — to `wookiee-cron`? `wookiee-scheduler`? Keep for compatibility?
2. **`services/knowledge_base/` + `knowledge-base` compose service** — keep or drop (spec §3.2).
3. **`services/dashboard_api/`** — not in compose but may still be in code. Not examined here (audit-code zone).
4. **`deploy/Dockerfile.sheets_sync`** — unused? Needs grep in compose; if only main Dockerfile is referenced, delete.
5. **`deploy/healthcheck_agent.py`** — references which agent? If Oleg, delete with PR #5.
6. **`.env.example` CLAUDE_API_KEY** — still used anywhere outside OpenRouter chain? Grep.
7. **`scripts/wb_promocodes_test.py` + output artifact** — commit / move to tests/ / delete.
8. **`.claude/skills/sync-sheets.md` standalone file** — delete (content covered by gws-sheets + sheets_sync service)?
9. **`.claude/agents/*.md` custom personas** — still referenced anywhere?
10. **`.claude/settings.json` legacy additionalDirectories** — drop `/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/**` paths (pre-migration ghost paths).

---

**Deliverable path:** `/Users/danilamatveev/Projects/Wookiee/.planning/refactor-audit/infra-audit.md`
