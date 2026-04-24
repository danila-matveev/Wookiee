# Wookiee — Refactor v3 Phase 1 Manifest

**Date:** 2026-04-24
**Generated-by:** refactor-orchestrator (Stage A.5)
**Inputs:** 2 specs (`2026-04-24-refactor-v3-design.md`, `2026-04-13-project-cleanup-v2-design.md`) + 4 audit reports (`code-audit.md`, `docs-audit.md`, `hub-audit.md`, `infra-audit.md`)
**Status:** Pending user approval — Stage B (PR #1-#7) does not start until signed-off.

---

## 0. Executive Summary

| Metric | Count |
|---|---:|
| PRs in Stage B | 7 |
| Files to DELETE (git rm) — tracked | ~470 |
| Files to DELETE (disk rm) — untracked / gitignored | ~100 (+ 604 MB jsonl) |
| Files to CREATE | 38 |
| Files to MODIFY | 29 |
| Files to RENAME | 16 (`services/observability/` + 14 hub sources + 1 container) |
| Disk space freed (estimated) | ≥ **780 MB** (604 MB output/ + ~175 MB logistics_audit xlsx already gone in git but whitelisted back + misc) |
| Flagged items awaiting user decision | 3 |

**Biggest wins**:
- 604 MB jsonl disk artifact purged + output/ permanently gitignored.
- Oleg V2 tree (~200 files across agents/oleg + tests + scripts + MCP + docs/agents) retired cleanly.
- Hub trimmed from ~180 src files to ~64 (-65%).
- Spec's 4 wrong assumptions corrected (see §2).

**Key risks**:
- PR #5 (Oleg) is the largest; must extract `finolog_service.py` to `shared/services/finolog_service.py` BEFORE deleting `agents/oleg/` else `/finolog-dds-report` skill breaks.
- PR #6 (hub trim) has no CI coverage for visual regressions — requires local `npm run build` + manual eyeballing before merge (spec §5.4).
- Branch protection is GitHub Pro-locked on this private repo → workflow is "gh pr create → wait for green Codex+Copilot → manual `gh pr merge --squash --delete-branch`", NOT auto-merge. Spec §5.1 over-promised.

---

## 1. Critique of the 4 audit reports

### 1.1 Contradictions found

| # | Contradiction | Resolution |
|---|---|---|
| C1 | audit-code §2.2 says `agents/finolog_categorizer/` is tracked (git rm needed). Spec §3.1 says "came back untracked, delete permanently". | **audit-code is correct** — `git ls-files agents/finolog_categorizer/` shows 13 tracked files. PR #4 = `git rm -r`. |
| C2 | audit-docs §3 marks `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md` as borderline KEEP-in-specs. audit-code + v3 spec §1.3 reference it as source-of-truth for garbage list. | **KEEP** in `docs/superpowers/specs/` (v3 spec explicitly cites it). |
| C3 | audit-code §6.4 says `services/knowledge_base/` "EXISTS on disk", and all importers are DELETE targets (Oleg + 1 MCP). audit-infra §2.3 lists `knowledge-base` as a `profiles: [optional]` compose service — "не деплоится на прод". | **DELETE** `services/knowledge_base/`, `deploy/Dockerfile.knowledge_base`, and the `knowledge-base` compose block in PR #4. Content KB (`services/content_kb/`) is the active replacement. Resolves Open Question 10(c)+F1. |
| C4 | audit-infra §2.3 proposes renaming `wookiee-oleg` → `wookiee-cron`. audit-code has no opinion. | **Rename to `wookiee-cron`** in PR #5 (same PR that deletes Oleg). See §3(g). |
| C5 | audit-infra says `Dockerfile.sheets_sync` may be unused (flag F4). `deploy/docker-compose.yml` lines 47-48 confirm: `sheets-sync` service `build.dockerfile: deploy/Dockerfile` (main one), NOT `Dockerfile.sheets_sync`. | **DELETE** `deploy/Dockerfile.sheets_sync` in PR #4 (dead file). |

### 1.2 Gaps found

- **`.kiro/` directory** (symlinks to `.agents/`) — covered only implicitly by audit-infra §5.1 as "keep" via symlinks but never audited as a first-class target. Verdict: KEEP (cleanup-v2 §3 approved). No PR action.
- **`mcp/` root directory** (ls showed it exists) — not mentioned by any audit. Likely cloned MCP helper. Verdict: leave untouched, it's outside core zones. No PR action.
- **Root-level `data/` directory** (dated Apr 18) — not covered. Verdict: leave; small and potentially actively used. No PR action.
- **Random root PNGs**: `agent-dashboard-full.png`, `mockup-full-page.png`, `airtable-templates-search.png`, `google-notion-search.png`, `notion-crm-gallery.png`, `notion-influencer-crm-top.png` — covered implicitly by audit-docs "binaries" + audit-infra `.gitignore *.png` rule. PR #1 disk-rm.
- **`scripts 2.txt`**, **`skills-lock 2.json`** — already match ignore pattern `* 2.*`. Covered by PR #1 disk-rm.
- **`.venv/`, `.pytest_cache/`, `.ruff_cache/`** — already gitignored; no action needed.

### 1.3 Aggressive / timid decisions flagged

| Audit | Decision | Verdict |
|---|---|---|
| audit-docs §3 | DELETE ~140 `.planning/` & `.superpowers/brainstorm/` files | **Accepted** — cleanup-v2 §2.6 pre-approves this. |
| audit-code F8 | DELETE `scripts/data_layer.py` shim (after migrating `services/wb_localization/generate_localization_report_v3.py`) | **Defer to PR #4**: leave shim for now; migration is out-of-scope for phase 1 (risk of breaking wb_localization). Mark as F-DEFER. |
| audit-code F2 | DELETE `shared/signals/` + `tests/shared/signals/` | **Accepted** (PR #5). All consumers die with Oleg; brainstorm mention of "pattern-first architecture" is Фаза 2+. |
| audit-code F9 | DELETE `scripts/notion_sync.py` | **KEEP** — still referenced in docs as standalone CLI + in README. Remove when Oleg-era abc_analysis scripts are gone but don't break it now. |
| audit-code F10 | `shared/utils/json_utils.py` orphan | **KEEP** (low risk, tiny file) — orchestrator saw `__init__` exports; could be used dynamically. |
| audit-code F4+F6 | `scripts/financial_overview/`, `scripts/audit_remediation/` | **ARCHIVE via PR #4 git mv** → `.planning/archive/standalone-scripts/` (preserves historical, not clutter). |
| audit-code F5 | `scripts/familia_eval/` orphan | **KEEP** — memory says it's active; retain pending user feedback. |
| audit-hub §5.1 | Hub = routes (NOT tabs) with `pages/community/*` + `pages/agents/*` | **Accepted** — clear UX + bookmarkability wins. |
| audit-hub §5.2 Option A (rename `comms` → `community`) | Rename all `comms-*` to `community-*` | **Accepted** — one-time cost, matches UI naming. Without it, future hires get confused. |

### 1.4 Verdict on contradictions

Contradictions found: 5. All resolved above. No unresolved blockers for Stage B.

---

## 2. Spec-drift corrections (what the v3 spec got wrong)

The orchestrator must correct the following silently in the manifest; user approval still applies.

| # | Spec claim | Reality | Fix location in this manifest |
|---|---|---|---|
| D1 | Spec §2.3 PR #4 says "delete `.mcp.json` entries `wookiee-data/kb/marketing/price`" | `.mcp.json` does NOT contain those entries (it has 4 external Node MCPs). The 4 local MCPs live in `.claude/settings.local.json`. Both files are **gitignored**. | PR #4: skip `.mcp.json`. Add manual post-step: user edits `.claude/settings.local.json` locally (not committed). |
| D2 | Spec §4.1 lists `services/marketplace_etl/`, `services/etl/`, `services/ozon_delivery/`, `services/vasily_api/`, `services/product_matrix_api/`, `services/dashboard_api/` as active runtime | All 6 removed on disk (commits `f476499` + `fcd6f58`). Only doc references remain. | PR #7 (docs-unification): purge stale doc refs. Active runtime list updated in §6 below. |
| D3 | Spec §5.1 mandates "Branch protection + auto-merge включён на уровне репозитория" | GitHub Free (private repo) → branch protection, rulesets, `allow_auto_merge` are all Pro-locked. `allow_auto_merge=true` was silently refused. `delete_branch_on_merge=true` IS set. | Manifest workflow: "gh pr create → wait for green Codex+Copilot → manual `gh pr merge --squash --delete-branch`". Not auto-merge toggles. |
| D4 | Spec §3.1 lists `agents/finolog_categorizer/` as "came back untracked" | Currently tracked (13 files). | PR #4: use `git rm -r`. |
| D5 | Spec §3.2 leaves `agents/oleg/services/*_tools.py` extraction as "orchestrator decides" | audit-code §6.2 verified: **ONLY `finolog_service.py`** has an external consumer (`scripts/finolog_dds_report/collect_data.py`). All other `*_tools.py` files have 0 external hits. | PR #5: extract only `finolog_service.py` (+ its `finolog_categorizer.py` helper if referenced — audit flags it only internal). Formalized in §3(e). |
| D6 | Spec §3.2 asks "is `services/dashboard_api/` needed" | Already removed (commit `fcd6f58`). audit-hub confirms: Hub will hit Supabase directly via `supabase-js`, no backend service required for Agents module. | Resolved as CONFIRM-DELETE. No code changes needed; only doc clean-ups in PR #7. |
| D7 | Spec §3.2 asks about `services/knowledge_base/`, `services/ozon_delivery/` | `services/ozon_delivery/` already removed on disk. `services/knowledge_base/` exists but all consumers are DELETE. See §3(c). | PR #4: delete `services/knowledge_base/` + `deploy/Dockerfile.knowledge_base` + compose block. `ozon_delivery` = doc cleanup only. |

---

## 3. Open Questions — Resolved

### (a) Rename target for `services/observability/`

**Decision: `services/tool_telemetry/`**

Reasoning:
- `observability/` is industry-generic (implies metrics+logs+traces pipeline) — overclaims what we have.
- `run_logger/` focuses on past-tense (logging) but misses the catalog + version-tracking sub-modules.
- `tool_telemetry/` accurately describes: "telemetry about tool runs" = exactly what `tools` + `tool_runs` Supabase tables record. Aligns with `shared/tool_logger.py` (the actual writer).

**Scope of rename in PR #7**:
- `git mv services/observability/ services/tool_telemetry/`
- Update imports: `grep -rln "services.observability\|services/observability"` → all references (0 in `.py`, only docs).
- Update `docs/TOOLS_CATALOG.md` if referenced.

### (b) `services/dashboard_api/` → CONFIRM-DELETE

Already physically removed (commit `fcd6f58`). audit-hub §7 confirms Hub→Supabase direct, no need to resurrect. Action in PR #4: purge remaining references — `deploy/Dockerfile.dashboard_api` (not checked — grep in PR #4), `scripts/init_tool_registry.py` (DELETE anyway per audit-code §2.4). Doc cleanup in PR #7.

### (c) `services/knowledge_base/`, `services/ozon_delivery/` → CONFIRM-DELETE

- `services/ozon_delivery/` — physically gone. Doc cleanup only (PR #7).
- `services/knowledge_base/` — exists on disk, all consumers (Oleg agents + mcp_servers/wookiee_kb) are DELETE. Content-KB (`services/content_kb/`) is the active replacement. **Delete in PR #4** together with `deploy/Dockerfile.knowledge_base` and `knowledge-base` service block in `docker-compose.yml`.

### (d) `docs/future/agent-ops-dashboard/` → DELETE

audit-docs §3 flagged it: content is Oleg-v2 ops dashboard that conflicts with the new "Агенты" Hub module. Nothing salvageable for the new module (Hub uses live `tools`+`tool_runs`). **DELETE** entire directory in PR #4 (ARCHIVE adds no value — the actual architectural notes for Oleg V2 go into `docs/archive/oleg-v2-architecture.md`, created in PR #5).

### (e) Oleg extraction → EXTRACT `finolog_service.py` ONLY

Confirmed by audit-code §6.2:
- `agents/oleg/services/finolog_service.py` → consumer `scripts/finolog_dds_report/collect_data.py` (active `/finolog-dds-report` skill).
- Helper `agents/oleg/services/finolog_categorizer.py` + `finolog_categorizer_store.py` — 0 external consumers, die with Oleg.
- All other `*_tools.py` (agent, price, marketing, funnel, seo, time_utils) + `price_analysis/` → 0 external consumers, die with Oleg.

**Action in PR #5 (step 1, BEFORE deleting `agents/oleg/`)**:
```
git mv agents/oleg/services/finolog_service.py shared/services/finolog_service.py
# Update import in scripts/finolog_dds_report/collect_data.py:
#   from agents.oleg.services.finolog_service import X
# →
#   from shared.services.finolog_service import X
# Create shared/services/__init__.py if missing.
```

### (f) Hub: routes vs tabs → ROUTES (audit-hub §5.1 recommendation)

**Accepted:** routes with `pages/community/*` + `pages/agents/*`. Bookmarkability, deep-linkable state, lazy-loading win over tabs. Existing `source=review|question|chat` filter in comms-reviews can drive Вопросы/Ответы sub-pages via props without deep refactor.

Additionally accepted: **Option A (rename `comms-*` → `community-*`)** — keeps code naming consistent with UI label "Комьюнити".

### (g) Container rename for `wookiee-oleg` → `wookiee-cron`

**Decision: `wookiee-cron`.**

Reasoning:
- It IS a cron dispatcher — the compose `command:` installs crontab entries for: `scripts/run_report.py` (DELETE in PR #5), `scripts/run_search_queries_sync.py`, `scripts/sync_sheets_to_supabase.py`, `scripts/retention_cleanup.py`.
- After PR #5 removes `run_report.py` + `retention_cleanup.py`, the remaining cron jobs are `search_queries_sync` (weekly) + `sync_sheets_to_supabase` (daily). Pure cron dispatcher.
- Alternative names considered: `wookiee-scheduler` (too generic, clashes with Claude Code `ScheduleWakeup`), `wookiee-dispatcher` (too abstract). `wookiee-cron` wins on clarity.

Scope in PR #5:
- `deploy/docker-compose.yml`: rename service `wookiee-oleg` → `wookiee-cron`, `container_name: wookiee_oleg` → `wookiee_cron`.
- Drop volume mount `../agents/oleg/data:/app/agents/oleg/data`.
- Update crontab command block (drop run_report + retention_cleanup lines).
- `deploy/deploy.sh` lines 14-15: update `CONTAINER=wookiee_cron`, `SERVICE=wookiee-cron`.
- `.github/workflows/deploy.yml`: update container name in healthcheck loop.

---

## 4. Cross-check table for DELETE candidates

For every major DELETE candidate, the orchestrator independently grepped imports across ALL zones (not just the one that flagged it). Findings:

| Path | Who flagged | Cross-check evidence | External hits | Verdict |
|---|---|---|---|---|
| `agents/oleg/services/*_tools.py` (agent, price, marketing, funnel, seo, time_utils) | code-audit §2.1 | `grep "from agents.oleg.services.\(agent\|price\|marketing\|funnel\|seo\|time_utils\)" --include='*.py'` outside oleg+mcp_servers | 0 | **DELETE** (PR #5) |
| `agents/oleg/services/finolog_service.py` | code-audit §2.1 MERGE | `grep "finolog_service"` → scripts/finolog_dds_report/collect_data.py + agents/finolog_categorizer/* (DELETE) | 1 active | **EXTRACT** to `shared/services/` then DELETE source (PR #5) |
| `agents/oleg/services/price_analysis/` (13 files) | code-audit §2.1 | `grep "agents.oleg.services.price_analysis"` outside oleg | 0 | **DELETE** (PR #5) |
| `agents/oleg/agents/*` (5 roles) | code-audit §2.1 | Used only internally by Oleg pipeline | 0 | **DELETE** (PR #5) |
| `agents/oleg/orchestrator/`, `executor/`, `pipeline/`, `storage/`, `anomaly/`, `playbooks/`, `watchdog/` | cleanup-v2 §2.4 + v3 §3.5 | Internal only | 0 | **DELETE** (PR #5) |
| `agents/finolog_categorizer/` (13 files) | code-audit §2.2 + v3 §3.1 | `grep "finolog_categorizer"` outside itself | 0 | **DELETE** (PR #4; tracked — `git rm -r`) |
| `mcp_servers/wookiee_data/` | code-audit §2.3 | `grep "wookiee_data\|mcp_servers"` in `agents/services/scripts/shared/tests/deploy/wookiee-hub/` | 0 | **DELETE** (PR #4) |
| `mcp_servers/wookiee_kb/` | code-audit §2.3 | same | 0 | **DELETE** (PR #4) |
| `mcp_servers/wookiee_marketing/` | code-audit §2.3 | same | 0 | **DELETE** (PR #4) |
| `mcp_servers/wookiee_price/` | code-audit §2.3 | same | 0 | **DELETE** (PR #4) |
| `mcp_servers/common/`, `mcp_servers/__init__.py` | code-audit §2.3 | Used only by 4 servers above | 0 | **DELETE** (PR #4) |
| `services/knowledge_base/` (all files) | code-audit F1 | `grep "services.knowledge_base"` → agents/oleg/* (DELETE) + services/knowledge_base/* (self) + deploy/Dockerfile.knowledge_base | 0 active | **DELETE** (PR #4) |
| `shared/clients/bitrix_client.py` | code-audit §2.5 | `grep "BitrixClient\|bitrix_client"` | 0 | **DELETE** (PR #4) |
| `shared/signals/` (5 files) | code-audit F2 | `grep "shared.signals"` → tests/shared/signals/* + agents/oleg/* (DELETE) + tests/integration/test_advisor_pipeline.py | 0 non-DELETE | **DELETE** (PR #5 with Oleg) |
| `shared/data_layer/quality.py` `validate_wb_data_quality()` | code-audit §2.5 + cleanup-v2 §2.7 | Only Oleg's `agent_tools.py` + `shared/data_layer/__init__.py` re-export | 0 | **DELETE function** (PR #4); file can stay empty or go |
| `scripts/abc_analysis.py`, `abc_analysis_unified.py`, `abc_helpers.py` | code-audit §2.4 | `.claude/skills/abc-audit/` uses `scripts/abc_audit/*` not these | 0 skills | **DELETE** (PR #4) |
| `scripts/calc_irp.py` | code-audit §2.4 | byte-identical to `services/wb_localization/calc_irp.py`; `grep "scripts/calc_irp\|from scripts.calc_irp"` | 0 | **DELETE** (PR #4) |
| `scripts/retention_cleanup.py` | code-audit §2.4 | Referenced only in `deploy/docker-compose.yml` crontab (wookiee-oleg) | 0 active skill | **DELETE** (PR #5, drop from crontab) |
| `scripts/returns_analysis.py` | code-audit §2.4 | `grep "returns_analysis"` everywhere | 0 | **DELETE** (PR #4) |
| `scripts/run_report.py` | code-audit §2.4 | Imports `agents.oleg.*` directly | 0 non-DELETE | **DELETE** (PR #5) |
| `scripts/shadow_test_reporter.py` | code-audit §2.4 | `grep` outside scripts | 0 | **DELETE** (PR #5) |
| `scripts/wb_promocodes_test.py` | code-audit §2.4 (untracked) | Only consumer of `output/wb_promocodes_test/` | 0 | **DELETE** (PR #1 — untracked file, disk rm) |
| `scripts/init_tool_registry.py` | code-audit §2.4 | Imports `services.dashboard_api` (doesn't exist) — broken | 0 | **DELETE** (PR #4) |
| `tests/product_matrix_api/` (22 files) | code-audit §2.6 | `services/product_matrix_api/` gone | orphan | **DELETE** (PR #4) |
| `tests/agents/oleg/` subtree | code-audit §2.6 | Imports `agents.oleg.*` | orphan after PR #5 | **DELETE** (PR #5) |
| `tests/oleg/` subtree | code-audit §2.6 | Imports `agents.oleg.*` | orphan | **DELETE** (PR #5) |
| `tests/integration/test_advisor_pipeline.py` | code-audit §2.6 | Imports `shared.signals` | orphan | **DELETE** (PR #5) |
| `tests/shared/signals/` (10 files) | code-audit §2.6 | Tests for `shared/signals/` | orphan | **DELETE** (PR #5) |
| Wookiee Hub pages (13 root + product-matrix/ + system/ + stubs/) | hub-audit §3.1 | Only referenced by `router.tsx` (rewritten) | 0 non-DELETE | **DELETE** (PR #6) |
| Wookiee Hub components/analytics, catalog, dashboard, kanban, matrix, promo, supply, unit | hub-audit §3.2 | Used only by deleted pages | 0 | **DELETE** (PR #6) |
| Wookiee Hub stores (comms-broadcasts, filters, kanban, matrix, supply, views, 3 matrix tests) | hub-audit §3.3 | Used only by deleted pages | 0 | **DELETE** (PR #6) |
| Wookiee Hub lib/api/* (abc, finance, promo, series, stocks, supply, traffic), entity-registry, field-def-columns, matrix-api, model-columns, supply-calc, view-columns | hub-audit §3.4 | Used by deleted modules | 0 | **DELETE** (PR #6) |
| Hub data/analytics-mock, catalog-mock, dashboard-mock, kanban-mock, supply-mock | hub-audit §3.5 | Used by deleted pages | 0 | **DELETE** (PR #6) |
| `docs/future/agent-ops-dashboard/` (all 8 files) | docs-audit §3 + spec §10.4 | Oleg-v2 specific | 0 | **DELETE** (PR #4) |
| `docs/agents/` (7 files except mp-localization which is UPDATE→merge into services/wb_localization/README) | docs-audit §3 | Stale references to Oleg/Ibrahim/Lyudmila | 0 active | **DELETE** (PR #7) |
| `.planning/archive/`, `.planning/milestones/`, `.planning/phases/`, `.planning/research/`, `.planning/debug/`, `.planning/MILESTONES.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `config.json` | docs-audit §3 + cleanup-v2 §2.6 | Stale | 0 | **DELETE** (PR #4) |
| `.superpowers/brainstorm/` (2 sessions) | docs-audit §3 + cleanup-v2 §2.6 | Brainstorm cache | 0 | **DELETE** (PR #4) |
| Old `docs/superpowers/plans/` + `specs/` (per docs-audit §3) | docs-audit §3 | Executed plans | 0 | **DELETE / ARCHIVE** (PR #7) |
| `deploy/deploy-v3-migration.sh` | infra-audit §6.1 + cleanup-v2 §2.5 | One-shot migration, executed | 0 | **DELETE** (PR #4) |
| `deploy/docker-compose.local.yml` | infra-audit §6.1 | Runs `agents.oleg.mcp_server` | 0 | **DELETE** (PR #4) |
| `deploy/Dockerfile.sheets_sync` | infra-audit + orchestrator recheck | `grep Dockerfile.sheets_sync deploy/*.yml` → 0 hits; compose uses main `Dockerfile` for sheets-sync | 0 | **DELETE** (PR #4) |
| `deploy/Dockerfile.knowledge_base` | code-audit F1 + infra audit | knowledge_base service DELETE | 0 | **DELETE** (PR #4) |
| `deploy/healthcheck_agent.py` | infra-audit §6.1 | Oleg-specific (checks `oleg_agent.pid`) | 0 non-DELETE | **DELETE** (PR #5) |
| `setup_bot.sh` | infra-audit §7.4 | References non-existent `bot/` dir | 0 | **DELETE** (PR #5 — contents are Oleg-era bot install) |
| `.claude/skills/sync-sheets.md` (file, not dir) | infra-audit §5.2 | Stale pre-skill-dir convention; duplicates `gws-sheets` + `sync_sheets_to_supabase.py` | 0 | **DELETE** (PR #4) |
| `output/wb_promocodes_test/` (604 MB jsonl + 4 small files) | infra-audit §8.2 | Untracked test artifact | 0 | **DISK-DELETE** (PR #2 preflight step — NOT git action) |
| `.playwright-mcp/` (3 tracked + ~95 untracked yml/log) | infra-audit §8.1 | Browser snapshots with potential sensitive data | 0 | **DELETE** (PR #1 — `git rm --cached` 3 tracked; disk-rm untracked) |
| Random root garbage: `2026_Договор...docx`, `agent-dashboard-full.png`, `mockup-full-page.png`, `airtable-templates-search.png`, `google-notion-search.png`, `notion-crm-gallery.png`, `notion-influencer-crm-top.png`, `scripts.txt`, `scripts 2.txt`, `skills-lock 2.json` | cleanup-v2 §2.1 + infra-audit §8.4 | Root clutter | 0 | **DELETE** (PR #1) |
| `wookiee-hub/index 2.html`, `package-lock 2.json`, `tsconfig.temp 2.json`, `e2e-*.png` (5), `mockups/`, `планы/` | hub-audit §8 | iCloud dupes + e2e leftovers | 0 | **DELETE** (PR #1) |

**Cross-check result**: every DELETE candidate has ≥ one evidence line above. No surprise non-DELETE consumer found.

---

## 5. Mirror list (directories not covered by any audit)

| Path | Audit coverage | Orchestrator decision |
|---|---|---|
| `.agents/skills/` | audit-infra §5.1 (keep; auto-installed) | KEEP |
| `.kiro/skills/` | audit-infra §5.1 (symlinks to `.agents/`) | KEEP |
| `mcp/` (root dir) | NONE | KEEP (peripheral; not in refactor scope) |
| `data/` (root dir) | NONE | KEEP (peripheral; `.gitignore` already covers `data/reports/`) |
| `sku_database/` | Not in audit scope | KEEP (live Supabase-driven) |
| `.ruff_cache/`, `.pytest_cache/`, `.venv/` | Already gitignored | KEEP (gitignored) |
| `reports/` | Implicitly in audit-docs (not audited as mutable) | KEEP; verify `.gitignore` rule for auto-generated files works |
| `wookiee-hub/mockups/` | hub-audit §8 recommends DELETE or move to `docs/archive/mockups/` | DELETE in PR #1 (no active use) |
| `wookiee-hub/планы/` | hub-audit §8 + cleanup-v2 §2.3 | DELETE in PR #1 |

No hidden orphans.

---

## 6. Final active-runtime list (after refactor)

### Python backend (post-refactor)

```
shared/
  config.py, model_mapping.py, notion_blocks.py, notion_client.py, tool_logger.py
  clients/
    mpstats_client.py, moysklad_client.py, openrouter_client.py,
    ozon_client.py, sheets_client.py, wb_client.py
  data_layer/       (quality.py can stay empty or be removed)
  services/         NEW — holds extracted finolog_service.py (from oleg)
  utils/

services/
  content_kb/       — vector photo search (pgvector)
  creative_kb/      — (untracked → committed in PR #3)
  logistics_audit/  — WB+OZON logistics audit
  sheets_sync/      — Google Sheets ↔ Supabase
  tool_telemetry/   — renamed from observability/
  wb_localization/  — localization + calculators + sheets_export
  wb_logistics_api/ — (untracked → committed in PR #3)

agents/             — empty scaffold + README (future true agents)
scripts/            — CLI scripts; orphans removed; abc_audit/, analytics_report/, daily_brief/, finolog_dds_report/, funnel_report/, logistics_report/, market_review/, monthly_plan/, reviews_audit/ etc.
sku_database/
mcp_servers/        — REMOVED
docs/
wookiee-hub/        — 2-module trim (Комьюнити + Агенты)
```

### Hub (post-refactor)

```
wookiee-hub/src/
  pages/
    community/{reviews,questions,answers,analytics}.tsx
    agents/{skills,runs}.tsx
  components/
    community/*   (renamed from comms/)
    agents/*      (NEW)
    layout/*, shared/*, ui/*
  stores/{community, community-settings, integrations, theme, navigation, agents}.ts
  lib/{utils, api-client, community-service, agents-service, supabase, motion, format}.ts
  config/{navigation, service-registry}.ts
  types/{community, community-settings, integrations, navigation, dashboard, agents}.ts
  data/{community-mock, community-settings-mock, integrations-mock}.ts
  router.tsx, main.tsx, index.css
```

---

## 7. Workflow — per-PR process (adjusted for GitHub Free)

For every PR in Stage B:

```
1. git checkout -b refactor/<branch-name>
2. Make edits per manifest
3. Local verification (per PR's "Acceptance check")
4. git commit (HEREDOC body with Co-Authored-By claude)
5. git push -u origin refactor/<branch-name>
6. gh pr create (use .github/pull_request_template.md once PR #7 creates it; before that, inline body)
7. Invoke /pullrequest skill → parallel Codex + Copilot review
8. If BLOCK → fix → re-push → re-review loop
9. All green → gh pr merge --squash --delete-branch
10. git checkout main && git pull --ff-only
11. Start next PR
```

Special case: **PR #6 (hub trim)** — spec §5.4 requires manual checkpoint; user runs `npm run build` + eyeballs live hub before merge. Orchestrator calls out: no auto-merge anyway, so this is the natural default.

---

## 8. Per-PR breakdown

### PR #1 — `refactor/binary-cleanup`

**Purpose:** Delete binary junk, iCloud dupes, untracked browser snapshots, and the 604 MB disk artifact. Pure cleanup, no code changes.

**Pre-flight (disk actions before commit):**
```bash
rm -rf output/wb_promocodes_test/
rm -rf wookiee-hub/mockups/ wookiee-hub/планы/
rm -rf .playwright-mcp/*.yml .playwright-mcp/*.log   # untracked ones only
```

**Files to DELETE (tracked → `git rm`):**

Root:
- `2026_Договор купли-продажи Familia -Чернецкая.docx`
- `scripts.txt`
- `agent-dashboard-full.png`, `mockup-full-page.png`
- (iCloud dupes ignored by `* 2.*` pattern — already untracked; disk rm)
- `scripts 2.txt`, `skills-lock 2.json` → disk rm (untracked)
- `airtable-templates-search.png`, `google-notion-search.png`, `notion-crm-gallery.png`, `notion-influencer-crm-top.png` → disk rm (untracked)

Logistics audit binaries (cleanup-v2 §2.2 "УДАЛИТЬ"):
- `services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx`
- `services/logistics_audit/ООО_Вуки_проверка_логистики_05_01_01_02.xlsx`
- `services/logistics_audit/ООО Wookiee — Перерасчёт логистики (v2).xlsx`
- `services/logistics_audit/Расчет переплаты по логистике.pdf`
- `services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf`
- `services/logistics_audit/Запись экрана (01.04.2026 15-30-09) (2).wmv`

wb_localization binaries:
- `services/wb_localization/data/reports/*.xlsx` (2 files)
- `services/wb_localization/Отчеты готовые/*` (6 files)

Archive + misc binaries:
- `docs/database/POWERBI DATA SAMPLES/*.xlsx` (2)
- `docs/archive/agents/vasily/docs/wb_references/*.pdf` (2)
- `docs/archive/agents/vasily/docs/wb_references/*.png` (2)

Playwright-mcp tracked:
- `.playwright-mcp/page-2026-03-31T23-56-07-942Z.yml`
- `.playwright-mcp/page-2026-03-31T23-56-50-135Z.yml`
- `.playwright-mcp/page-2026-04-01T00-06-46-413Z.yml`

Hub iCloud dupes (tracked):
- `wookiee-hub/index 2.html`
- `wookiee-hub/package-lock 2.json`
- `wookiee-hub/tsconfig.temp 2.json`
- `wookiee-hub/e2e-analytics.png`, `e2e-broadcasts.png`, `e2e-dashboard.png`, `e2e-reviews.png`, `e2e-settings.png`
- `wookiee-hub/mockups/*` (if tracked)
- `wookiee-hub/планы/*` (if tracked)

agent-ops-dashboard mockups (from cleanup-v2 §2.3):
- `docs/future/agent-ops-dashboard/mockups/*.png`

**Files to CREATE:** none

**Files to MODIFY:** none

**Depends on:** nothing

**Acceptance check:**
```bash
du -sh output/   # should be ≤ 100 KB or absent
du -sh .   # total repo size should drop ≥ 200 MB
git status --porcelain | grep -E '\.(docx|wmv|xlsx|pdf|png)$' | wc -l   # should be ≤ whitelist count
```

**Changelog line for PR body:** `refactor: remove binary junk (logistics xlsx, iCloud dupes, playwright snapshots, docx) and 604 MB output artifact (untracked)`

---

### PR #2 — `refactor/gitignore-hardening`

**Purpose:** Extend `.gitignore` so future junk of these types never gets committed. Add whitelist for logistics audit deliverables.

**Files to DELETE:** none

**Files to CREATE:** none

**Files to MODIFY:**
- `.gitignore` — add the following blocks (see infra-audit §4.2, merged + deduped):

```gitignore
# ── Whitelist: logistics audit finalized deliverables ──
!services/logistics_audit/*Итоговый*.xlsx
!services/logistics_audit/*v2-final*.xlsx
!services/logistics_audit/*Тарифы*.xlsx

# ── Additional binary extensions ──
*.docx
*.wmv
*.mp4
*.mov

# ── Shell history ──
scripts.txt
scripts*.txt

# ── Claude Code runtime state ──
.claude/scheduled_tasks.lock

# ── Playwright browser snapshots ──
.playwright-mcp/
!.playwright-mcp/.gitkeep

# ── Output / generated ──
output/
scratch/
_scratch/
.scratch/

# ── Tool caches ──
.ruff_cache/
.pytype/
.pyre/
.cache/

# ── Superpowers per-session cache ──
.superpowers/**/artifacts/
.superpowers/**/*.cache

# ── GSD debug scratch ──
.planning/debug/
```

After adding these rules:
```bash
# Re-add whitelisted logistics xlsx that may have been caught by *.xlsx rule:
git add -f services/logistics_audit/*Итоговый*.xlsx \
           services/logistics_audit/*v2-final*.xlsx \
           services/logistics_audit/*Тарифы*.xlsx
```

**Depends on:** PR #1 (must be merged first so untracked junk is already purged)

**Acceptance check:**
```bash
git check-ignore -v output/ .playwright-mcp/*.yml "scripts.txt" ".claude/scheduled_tasks.lock"
# All must return "matched"
git ls-files | grep -E 'Итоговый|v2-final|Тарифы' | wc -l  # must be ≥ 3 (whitelisted deliverables tracked)
```

**Changelog line:** `refactor: harden .gitignore — block output/, .playwright-mcp/, *.docx/.wmv, tool caches; whitelist logistics deliverables`

---

### PR #3 — `refactor/commit-untracked`

**Purpose:** Commit active untracked code (`creative_kb`, `wb_logistics_api`, `wb_localization/calculators+sheets_export`, tests) + add READMEs.

**Files to DELETE:** none

**Files to CREATE:**
- `services/creative_kb/README.md` — purpose + entrypoint + deps + skill linkage
- `services/wb_logistics_api/README.md`
- `services/wb_localization/calculators/README.md` (short; links to main wb_localization README)
- `services/wb_localization/sheets_export/README.md` (short)

**Files to MODIFY (only by adding — no content edits):**
- (Git adds for currently untracked tree: `services/creative_kb/**`, `services/wb_logistics_api/**`, `services/wb_localization/calculators/**`, `services/wb_localization/sheets_export/**`, `tests/wb_localization/**`, `tests/services/logistics_audit/**`)
- `services/wb_localization/README.md` — update to mention calculators+sheets_export sub-modules

**Depends on:** PR #2 (.gitignore must block future noise)

**Acceptance check:**
```bash
git status --porcelain | grep -E "^\?\?" | wc -l   # all whitelisted untracked committed → 0 (except .playwright-mcp/ new files, which gitignore now suppresses)
pytest tests/wb_localization/ tests/services/logistics_audit/ -q   # must pass
```

**Changelog line:** `refactor: commit creative_kb, wb_logistics_api, wb_localization calculators+sheets_export + tests + READMEs`

---

### PR #4 — `refactor/remove-dead-code`

**Purpose:** Remove dead code — `mcp_servers/`, `agents/finolog_categorizer/`, `services/knowledge_base/`, old planning dirs, abc_analysis scripts, broken init_tool_registry, etc. NOT Oleg (PR #5 owns that).

**Files to DELETE (git rm):**

MCP servers:
- `mcp_servers/__init__.py`
- `mcp_servers/common/` (+ all files)
- `mcp_servers/wookiee_data/` (+ all files)
- `mcp_servers/wookiee_kb/` (+ all files)
- `mcp_servers/wookiee_marketing/` (+ all files)
- `mcp_servers/wookiee_price/` (+ all files)

Finolog-categorizer agent (tracked):
- `agents/finolog_categorizer/` (all 13 files)

Knowledge base service:
- `services/knowledge_base/` (all files — Dockerfile moved below)
- `deploy/Dockerfile.knowledge_base`

Scripts dead code:
- `scripts/abc_analysis.py`
- `scripts/abc_analysis_unified.py`
- `scripts/abc_helpers.py`
- `scripts/calc_irp.py` (byte-identical duplicate of `services/wb_localization/calc_irp.py`)
- `scripts/returns_analysis.py`
- `scripts/init_tool_registry.py` (broken — imports dashboard_api)

Shared dead code:
- `shared/clients/bitrix_client.py`
- `shared/data_layer/quality.py`'s `validate_wb_data_quality()` function (remove from file + remove export from `shared/data_layer/__init__.py`)

Tests:
- `tests/product_matrix_api/` (22 files — orphaned after service was removed)

Deploy dead code:
- `deploy/deploy-v3-migration.sh` (one-shot V2→V3 migration, already run)
- `deploy/docker-compose.local.yml` (references `agents.oleg.mcp_server`)
- `deploy/Dockerfile.sheets_sync` (unreferenced — compose uses main `Dockerfile`)

.claude cleanup:
- `.claude/skills/sync-sheets.md` (stale, pre-skill-dir file; content duplicated by `gws-sheets` skill + `sync_sheets_to_supabase.py`)

Planning / superpowers purge:
- `.planning/archive/` (entire tree; cleanup-v2 §2.6)
- `.planning/milestones/` (entire tree)
- `.planning/phases/` (entire tree)
- `.planning/research/` (5 files)
- `.planning/debug/` (4 files)
- `.planning/MILESTONES.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md`, `config.json`
- `.superpowers/brainstorm/` (entire — 2 session caches)

Stale specs / plans (docs-audit §3 DELETE list — not ARCHIVE):
- `docs/PROJECT_MAP.md`
- `docs/QUICKSTART.md`
- `docs/system.md`
- `docs/plans/ibrahim-deploy-and-etl.md`
- `docs/plans/2026-04-verification-prompt.md`
- `docs/plans/2026-04-verification-v2-prompt.md`
- `docs/future/agent-ops-dashboard/` (entire — 8 files)
- `docs/workflows/oleg-report-pipeline.html`
- `docs/workflows/vasily-localization-pipeline.html`
- `docs/workflows/ibrahim-etl-flow.html`
- `docs/workflows/agent-system-architecture.html`
- `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md`
- `docs/superpowers/specs/2026-03-21-smart-conductor-design.md`
- `docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md`
- `docs/superpowers/specs/2026-04-03-project-restructuring-design.md`
- `docs/superpowers/plans/2026-04-03-project-restructuring.md`
- Advisor agent plans + specs (5 files × 2) — per docs-audit §3
- Product-matrix plans + specs (6+2+1+1 files) — per docs-audit §3
- Reporter V4 plan + spec
- Notification-spam-fix plan
- MCP-observability plan
- Content-KB early design + plan (content_kb README has current docs)
- Trust-envelope plan + spec
- Telegram-UX-cleanup plan + spec
- Smart-conductor plan
- Report-templates-stabilization plan + spec
- Comms-live-api plan + spec
- Sports-research design
- Familia-eval design + plan
- Ozon-MCP-server plan + spec
- Financial-overview skill plan + spec

(Full list: copy docs-audit §3 verbatim.)

docker-compose.yml `knowledge-base` service block removal (see MODIFY below).

**Files to CREATE:**
- none (placeholders for PR #7)

**Files to MODIFY:**
- `shared/data_layer/__init__.py` — remove `validate_wb_data_quality` from exports
- `shared/data_layer/quality.py` — remove the function OR delete file entirely (no other content to preserve — verify).
- `deploy/docker-compose.yml` — remove the `knowledge-base:` service block entirely (lines ~180-220).

**Files to move (archive, not delete):**
- `scripts/financial_overview/` → `.planning/archive/standalone-scripts/financial_overview/` (preserve history)
- `scripts/audit_remediation/` → `.planning/archive/standalone-scripts/audit_remediation/` (already-ran migrations)

**Depends on:** PR #3 (so untracked tests are committed and can be checked for regressions)

**Acceptance check:**
```bash
pytest -q   # must pass (new orphan tests removed; Oleg tests still present but not failing yet — PR #5 removes)
ruff check services shared scripts   # no new errors
test ! -d mcp_servers
test ! -d agents/finolog_categorizer
test ! -d services/knowledge_base
test ! -d docs/future/agent-ops-dashboard
```

**Changelog line:** `refactor: remove dead code (mcp_servers/, finolog_categorizer, knowledge_base, abc_analysis*, broken init_tool_registry, stale planning/superpowers/docs artifacts)`

---

### PR #5 — `refactor/oleg-cleanup`

**Purpose:** Retire Oleg V2 entirely. Extract `finolog_service.py` first. Rename `wookiee-oleg` → `wookiee-cron`. Create `docs/archive/oleg-v2-architecture.md` as knowledge capture.

**Step A — Extract (must happen BEFORE any `git rm` of oleg):**

```bash
mkdir -p shared/services
git mv agents/oleg/services/finolog_service.py shared/services/finolog_service.py
touch shared/services/__init__.py   # if not exists
# Then edit: scripts/finolog_dds_report/collect_data.py
#   line 79: from agents.oleg.services.finolog_service import X
#   →        from shared.services.finolog_service import X
```

**Files to DELETE (after step A):**

- `agents/oleg/` entire tree:
  - `SYSTEM.md`, `__init__.py`, `main.py`, `run_daily.py`, `cli.py`, all `*.md` playbooks, `requirements.txt`
  - `agents/` (advisor, marketer, reporter, funnel, validator — all subdirs)
  - `orchestrator/`, `executor/`, `pipeline/`, `storage/`, `anomaly/`, `playbooks/`, `watchdog/`
  - `services/` (except finolog_service.py which is already moved): `agent_tools.py`, `price_tools.py`, `marketing_tools.py`, `funnel_tools.py`, `seo_tools.py`, `time_utils.py`, `finolog_categorizer.py`, `finolog_categorizer_store.py`, `price_analysis/*` (13 files)
  - `data/` (SQLite DBs, JSON reports)
  - `logs/`
  - `tests/` (if any inside oleg)

Scripts (Oleg-related):
- `scripts/run_report.py`
- `scripts/shadow_test_reporter.py`
- `scripts/retention_cleanup.py` (only consumer is the Oleg crontab)

Tests:
- `tests/agents/oleg/` (entire tree)
- `tests/oleg/` (entire tree)
- `tests/integration/test_advisor_pipeline.py`
- `tests/shared/signals/` (10 files)
- `tests/agents/__init__.py` + empty `tests/agents/` after oleg subtree gone
- `tests/integration/` (empty after above)
- `tests/shared/signals/` parent empty → delete `tests/shared/` if nothing else inside

Shared (Oleg-only consumer):
- `shared/signals/` (5 files: `detector.py`, `direction_map.py`, `kb_patterns.py`, `patterns.py`, `__init__.py`)

Deploy (Oleg infra):
- `deploy/healthcheck_agent.py` (checks oleg_agent.pid)
- `setup_bot.sh` (root — Oleg Telegram bot install, references non-existent `bot/`)

Stale archive docs:
- `docs/archive/retired_agents/lyudmila/` (cleanup-v2 §2.5 — 3.2M legacy agent)

**Files to CREATE:**
- `shared/services/__init__.py` (if not yet)
- `docs/archive/oleg-v2-architecture.md` — knowledge capture (cleanup-v2 §2.4): 5 roles, ReAct loop, circuit breaker, orchestrator decision flow, analytical knowledge extracted into skills

**Files to MODIFY:**
- `scripts/finolog_dds_report/collect_data.py` — import change (see Step A)
- `deploy/docker-compose.yml`:
  - Rename service `wookiee-oleg` → `wookiee-cron`
  - `container_name: wookiee_oleg` → `wookiee_cron`
  - Drop volume `../agents/oleg/data:/app/agents/oleg/data`
  - Crontab command: drop `run_report.py` line and `retention_cleanup.py` line. Keep: `run_search_queries_sync.py` (weekly Mon 10:00), `sync_sheets_to_supabase.py` (daily 06:00)
- `deploy/deploy.sh`:
  - Line ~14-15: `CONTAINER=wookiee_cron`, `SERVICE=wookiee-cron`
  - Drop Oleg-specific log strings if any
- `deploy/Dockerfile`:
  - Drop `COPY agents/ ./agents/` line (agents/ is empty scaffold; COPY of empty tree is fine but redundant)
- `.github/workflows/ci.yml`:
  - Remove `pip install -r agents/oleg/requirements.txt`; replace with root `requirements.txt` consolidation or drop (no-op if nothing imports it)
- `.github/workflows/deploy.yml`:
  - Container name in healthcheck loop: `wookiee_oleg` → `wookiee_cron`
- `.env.example`:
  - Remove: `LYUDMILA_BOT_TOKEN`, `VASILY_SPREADSHEET_ID`, `VASILY_BITRIX_CHAT_ID`, `VASILY_BITRIX_FOLDER_ID`, `VASILY_API_KEY`, `ZAI_API_KEY` (lines per infra-audit §7.3)
  - Fix misleading comment line 53 ("z.ai primary" → "OpenRouter primary")

**Depends on:** PR #4 (dead code removed first so tests don't have stale imports to oleg from outside oleg)

**Acceptance check:**
```bash
pytest -q   # must pass (all oleg tests removed; finolog-dds scripts still work)
python -c "from shared.services.finolog_service import *"   # must import cleanly
python scripts/finolog_dds_report/collect_data.py --dry-run   # if dry-run supported
test ! -d agents/oleg
test ! -d tests/agents
test ! -d tests/shared/signals
grep -rln "agents.oleg\|from agents.oleg" --include="*.py" . | grep -v ".venv/\|__pycache__/" | wc -l   # must be 0
```

**Changelog line:** `refactor: retire Oleg V2 — extract finolog_service to shared/services, delete agents/oleg/ tree, rename wookiee-oleg → wookiee-cron, archive architecture notes`

---

### PR #6 — `refactor/hub-trim`

**Purpose:** Trim Wookiee Hub to 2 modules (Комьюнити + Агенты). ~180 → ~64 src files. Add Supabase direct client.

**Files to DELETE (per hub-audit §3 — exact list):**

Pages (17):
- `src/pages/dashboard.tsx`, `dashboard-placeholder.tsx`, `catalog.tsx`, `development.tsx`, `production.tsx`, `shipments.tsx`, `supply.tsx`, `ideas.tsx`, `analytics-overview.tsx`, `analytics-abc.tsx`, `analytics-promo.tsx`, `analytics-unit.tsx`, `comms-broadcasts.tsx`, `comms-dashboard.tsx`, `comms-store-settings.tsx`
- `src/pages/product-matrix/` (11 files)
- `src/pages/system/` (6 files: api-explorer, archive-manager, audit-log, db-stats, matrix-admin-layout, schema-explorer)
- `src/pages/stubs/` (all ~22 files)

Components (per hub-audit §3.2 — verbatim):
- `components/analytics/` (6 files)
- `components/catalog/` (3 files)
- `components/dashboard/` (9 files)
- `components/kanban/` (13 files)
- `components/matrix/` (~25 files incl. `panel/`, `tabs/`)
- `components/promo/` (6 files)
- `components/supply/` (6 files)
- `components/unit/` (1 file)
- `components/comms/`: broadcast-create-form, broadcast-list, comms-dashboard-chart, comms-dashboard-header, comms-dashboard-metrics, comms-dashboard-stores, comms-dashboard-tabs, comms-dashboard-top-products, settings-tab-ai-learning, settings-tab-chats, settings-tab-extended, settings-tab-questions, settings-tab-recommendations, settings-tab-reviews, settings-tab-signature
- `components/shared/`: chart-skeleton, metric-card-skeleton, module-stub, multi-select-filter, priority-dot, status-pill, table-skeleton, view-switcher
- `components/component-example.tsx`, `components/example.tsx`
- `components/ui/`: `alert-dialog`, `badge`, `card`, `combobox`, `field`, `input-group`, `label`, `select`, `sheet`, `skeleton` (verify with grep; `tabs.tsx` — KEEP if new agents pages use tabs; otherwise delete)

Stores (6 + 3 tests):
- `stores/comms-broadcasts.ts`, `filters.ts`, `kanban.ts`, `matrix-store.ts`, `supply.ts`, `views-store.ts`
- `stores/__tests__/detail-panel-routing.test.ts`, `entity-update-stamp.test.ts`, `matrix-store-filters.test.ts`

Lib (8):
- `lib/api/abc.ts`, `finance.ts`, `promo.ts`, `series.ts`, `stocks.ts`, `supply.ts`, `traffic.ts`
- `lib/entity-registry.ts`, `field-def-columns.ts`, `matrix-api.ts`, `model-columns.ts`, `supply-calc.ts`, `view-columns.ts`
- `lib/__tests__/entity-registry.test.ts`

Data (5):
- `data/analytics-mock.ts`, `catalog-mock.ts`, `dashboard-mock.ts`, `kanban-mock.ts`, `supply-mock.ts`

Types (5):
- `types/analytics.ts`, `catalog.ts`, `comms-broadcasts.ts`, `kanban.ts`, `supply.ts`

Config (1):
- `config/boards.ts`

Hooks (2):
- `hooks/use-api-query.ts`, `hooks/use-table-state.ts`

Misc:
- `src/App.tsx` (dead — imports deleted `component-example`)
- `src/assets/react.svg`

**Files to RENAME (comms → community):**
- `src/pages/comms-reviews.tsx` → `src/pages/community/reviews.tsx`
- `src/pages/comms-analytics.tsx` → `src/pages/community/analytics.tsx`
- `src/components/comms/` → `src/components/community/`
- `src/stores/comms.ts` → `src/stores/community.ts`
- `src/stores/comms-settings.ts` → `src/stores/community-settings.ts`
- `src/types/comms.ts` → `src/types/community.ts`
- `src/types/comms-settings.ts` → `src/types/community-settings.ts`
- `src/lib/comms-service.ts` → `src/lib/community-service.ts`
- `src/data/comms-mock.ts` → `src/data/community-mock.ts`
- `src/data/comms-settings-mock.ts` → `src/data/community-settings-mock.ts`

Update all imports inside these files to use new paths (sed/grep post-rename).

**Files to CREATE:**
- `src/pages/community/questions.tsx` (wraps reviews with `initialSource="question"` prop)
- `src/pages/community/answers.tsx` (wraps reviews with `initialTab="processed"`, `initialProcessedSubTab="answered"`)
- `src/pages/agents/skills.tsx` — scaffold table reading from Supabase `tools`
- `src/pages/agents/runs.tsx` — scaffold table reading from Supabase `tool_runs`
- `src/components/agents/tools-table.tsx`
- `src/components/agents/runs-table.tsx`
- `src/components/agents/run-status-badge.tsx`
- `src/stores/agents.ts` (zustand: tools[], runs[], fetchers)
- `src/lib/agents-service.ts` (supabase query wrapper)
- `src/lib/supabase.ts` (`@supabase/supabase-js` client singleton)
- `src/types/agents.ts`

**Files to MODIFY:**
- `wookiee-hub/package.json` — add `"@supabase/supabase-js": "^2.45.0"`. Remove `@dnd-kit/core`, `@dnd-kit/sortable` (kanban-only — hygiene).
- `wookiee-hub/.env.example` — add `VITE_SUPABASE_URL=`, `VITE_SUPABASE_ANON_KEY=`
- `wookiee-hub/src/router.tsx` — full rewrite per hub-audit §6.1
- `wookiee-hub/src/config/navigation.ts` — rewrite to 2 groups per hub-audit §6.3
- `wookiee-hub/src/components/layout/mobile-nav.tsx` — 3 tabs (Комьюнити, Агенты, Ещё) per §6.4
- `wookiee-hub/src/components/layout/app-shell.tsx` — drop `/dashboard` shortcut
- `wookiee-hub/src/components/layout/top-bar.tsx` — fix breadcrumbs (drop `/dashboard`)
- `wookiee-hub/src/pages/community/reviews.tsx` — accept `initialSource`, `initialTab`, `initialProcessedSubTab` props
- `services/logistics_audit/README.md` — no-op (not in hub; listed here for consistency)

**DB-side dependency (flag for user):**
- Verify RLS policies on Supabase tables `tools` + `tool_runs`. Hub uses anon key → needs `SELECT` policy with `USING (true)` (read-only internal dashboard). If missing, Orchestrator flags F-DB for user to add before merging PR #6.

**Depends on:** PR #5 (main PRs must land first so manifest reflects active state)

**Acceptance check:**
```bash
cd wookiee-hub
npm install
npm run build   # must succeed
npm run test    # vitest
# Manual smoke test: load /community/reviews, /community/analytics, /agents/skills, /agents/runs
```

**Manual checkpoint (spec §5.4):** User eyeballs local hub before merge. No auto-merge.

**Changelog line:** `refactor(hub): trim to 2 modules — Комьюнити (reviews/questions/answers/analytics) + Агенты (skills/runs), rename comms→community, add supabase-js direct client`

---

### PR #7 — `refactor/docs-unification`

**Purpose:** Rename `services/observability/` → `services/tool_telemetry/`. Create READMEs + ONBOARDING + skill docs + PR template. Update stale root docs. Archive executed plans/specs.

**Files to DELETE (archive moves handled below):**
- `docs/agents/README.md`, `analytics-engine.md`, `telegram-bot.md`, `ibrahim.md`, `mp-localization.md` (after merging content into services/wb_localization/README.md)

**Files to ARCHIVE (git mv to `docs/archive/…`):**
Per docs-audit §4 — full list. Key ones:
- `docs/agents/bitrix-crm.md` → `docs/archive/agents/`
- `docs/agents/wb-sheets-sync-plan.md` → `docs/archive/plans/`
- `docs/plans/oleg-v2-rebuild.md`, `2026-02-25-*.md`, `2026-04-business-plan*.md` (3 files) → `docs/archive/plans/`
- `docs/abc_analysis_playbook.md` → `docs/archive/`
- All executed superpowers plans + specs per docs-audit §4 (monthly-plan, logistics-audit, logistics-cost, db-audit, sheets-to-supabase, analytics-report, reviews-audit, finance-report, marketing-report, abc-audit, search-query-analytics, funnel-report, finolog-logistics, tool-registry, finolog-logistics-v2-fixes, wb-logistics-optimizer, wb-tariffs-bootstrap, localization-service-redesign)

**Files to CREATE:**

Root:
- `ONBOARDING.md` — per spec §6.3 template (Russian)
- `.github/pull_request_template.md` — per spec §5.2

Agent scaffold:
- `agents/README.md` — per spec §3.5

Archive capture (already in PR #5; verify existence):
- `docs/archive/oleg-v2-architecture.md`

docs/skills/ (14 files, per docs-audit §6.2, Russian, per spec §6.4 template):
- `docs/skills/finance-report.md`
- `docs/skills/marketing-report.md`
- `docs/skills/daily-brief.md`
- `docs/skills/funnel-report.md`
- `docs/skills/logistics-report.md`
- `docs/skills/abc-audit.md`
- `docs/skills/market-review.md`
- `docs/skills/analytics-report.md`
- `docs/skills/reviews-audit.md`
- `docs/skills/monthly-plan.md`
- `docs/skills/finolog-dds-report.md`
- `docs/skills/content-search.md`
- `docs/skills/tool-status.md`
- `docs/skills/tool-register.md`

Module READMEs (verify existing, create missing — per docs-audit §6.3):
- `services/tool_telemetry/README.md` (NEW — after rename below)
- `services/creative_kb/README.md` (already created in PR #3)
- `services/wb_logistics_api/README.md` (already created in PR #3)
- Verify / refresh existing: `services/logistics_audit/`, `services/wb_localization/`, `services/sheets_sync/`, `services/content_kb/`

Hygiene skill placeholder:
- `.claude/skills/hygiene/README.md` — "Фаза 2 — планируется"
- `.claude/hygiene-config.yaml` — placeholder per spec §7.4

**Files to RENAME:**
- `services/observability/` → `services/tool_telemetry/` (git mv)
- Update all Python imports (grep found 0, but double-check)
- Update `docs/TOOLS_CATALOG.md` if referenced

**Files to MODIFY:**

Root:
- `README.md` — rewrite per docs-audit §5 (skills-first, no Lyudmila/Vasily, update tree, entrypoints)
- `AGENTS.md` — remove marketplace_etl/etl references, drop Oleg as "активен", sync LLM model names with .claude/rules/economics.md, add ONBOARDING link
- `CLAUDE.md` — add links to ONBOARDING + docs/skills/
- `CONTRIBUTING.md` — rewrite under new PR workflow (gh pr create + /pullrequest + manual merge), drop agents/vasily_agent example
- `SECURITY.md` — fix `wookiee_sku_database/` → `sku_database/`, drop ZAI_API_KEY + ANTHROPIC_API_KEY direct, add OPENROUTER_API_KEY + FINOLOG_API_TOKEN + MPSTATS_API_KEY

docs/:
- `docs/index.md` — full rewrite (27 active skills + 8 services + database + guides + archive)
- `docs/architecture.md` — drop Olga/Ibrahim/Vasily as active; add logistics_audit, wb_logistics_api, content_kb, creative_kb, tool_telemetry; update entrypoints
- `docs/infrastructure.md` — update container list (wookiee-cron, sheets-sync, wb-logistics-api)
- `docs/adr.md` — add ADR-008 (Refactor V3 phase 1)
- `docs/development-history.md` — trim to 10 entries, add refactor-v3 record
- `docs/guides/environment-setup.md` — drop vasily_api/marketplace_etl references, drop TELEGRAM_BOT_TOKEN if Oleg-only
- `docs/guides/logging.md` — remove Oleg alerter/watchdog references
- `docs/guides/agent-principles.md` — replace Oleg examples with generic skill examples

Makefile:
- Full rewrite per infra-audit §7.2 (test / test-etl / lint / deploy / help)

pyproject.toml:
- Keep `agents` in `src` list (scaffold stays)
- Refresh ruff ignore comments if they reference stale counts

.github/:
- `PULL_REQUEST_TEMPLATE.md` (uppercase, existing) — replace with spec §5.2 content
  - Note: spec refers to `.github/pull_request_template.md` (lowercase); GitHub matches case-insensitively. Keep existing uppercase filename to avoid git rename noise.

**Files to regenerate (auto):**
- `docs/TOOLS_CATALOG.md` — run `python scripts/generate_tools_catalog.py` (no commit if unchanged)

**Depends on:** PR #4, PR #5, PR #6 (all structural changes land first; docs reflect final state)

**Acceptance check:**
```bash
# Link check
grep -rln "agents/oleg\|agents/lyudmila\|agents/vasily\|agents/ibrahim\|services/marketplace_etl\|services/vasily_api\|services/dashboard_api\|services/ozon_delivery\|services/product_matrix_api" --include="*.md" docs/ README.md AGENTS.md CLAUDE.md CONTRIBUTING.md SECURITY.md | grep -v "archive/\|development-history\|refactor-v3\|cleanup-v2"
# → should be empty

test -f ONBOARDING.md
test -f .github/PULL_REQUEST_TEMPLATE.md
test -f docs/archive/oleg-v2-architecture.md
ls docs/skills/*.md | wc -l   # must be ≥ 14
test -d services/tool_telemetry
test ! -d services/observability

make help   # should work with new targets
python scripts/generate_tools_catalog.py   # should regenerate without error
```

**Changelog line:** `refactor(docs): colleague-ready repo — ONBOARDING + docs/skills/ + module READMEs + PR template; purge Oleg/Vasily/Lyudmila as active; rename observability→tool_telemetry`

---

## 9. Flagged items (user decision required)

Orchestrator kept this list tight — 3 items:

| # | Flag | Question | Recommendation |
|---|---|---|---|
| **F1** | **RLS on `tools` + `tool_runs`** | Hub (PR #6) uses anon key to read these tables. Are SELECT policies in place with `USING (true)` for `anon` role? If not, PR #6 can't merge. | **Verify via Supabase MCP or dashboard before PR #6 starts**. If missing, user adds a one-line policy per table. Small task, not a blocker for PR #1-5. |
| **F2** | **`scripts/familia_eval/`** | Orphan tool — no skill, but memory says project is active. Keep or archive? | **Default: KEEP** in scripts/ (with a `scripts/familia_eval/README.md` stub noting "standalone tool, not yet a skill"). User can override at approval. |
| **F3** | **Manual edit of `.claude/settings.local.json`** | File is gitignored, so PR #4 can't edit it. The 4 local MCP entries become dead after PR #4 deletes `mcp_servers/` — Claude will fail to start those servers on next launch. | **Post-PR-#4 step for the user**: manually delete the 4 `wookiee-*` entries from `.claude/settings.local.json`. Orchestrator mentions in final summary. |

Everything else was decided autonomously with reasoning above.

---

## 10. Sequence note — the 604 MB output artifact

`output/wb_promocodes_test/rows_2026-04-24.jsonl` (604 MB) is NOT tracked in git. Rules:

1. **Disk action (not git action)**: must be deleted manually on the executor's machine: `rm -rf output/wb_promocodes_test/`.
2. **Happens in PR #1** as a pre-flight step BEFORE any `git` commands. Rationale: want repo size drop visible in PR #1 narrative; if .gitignore is added first (PR #2), `git status` wouldn't surface `output/` anyway but disk size wouldn't change.
3. **PR #2** then adds `output/` to `.gitignore` so the directory can be used freely for future test artifacts without contaminating `git status`.

**Execution order in PR #1** (strict):
```
1. rm -rf output/wb_promocodes_test/       # 604 MB gone from disk
2. rm -rf .playwright-mcp/page-*.yml .playwright-mcp/page-*.log   # untracked noise
3. rm -rf wookiee-hub/mockups/ wookiee-hub/планы/   # if present
4. git rm <tracked binaries per PR #1 list>
5. git commit -m "refactor: remove binary junk (604 MB output + iCloud dupes + playwright + docs binaries)"
6. git push / gh pr create / review / merge
```

---

## 11. Post-refactor cleanup (after all 7 PRs)

Manual steps the user performs (not PR actions):

1. Edit `.claude/settings.local.json` — delete 4 `wookiee-*` entries from `mcpServers` block.
2. Restart Claude Code to pick up the clean MCP config.
3. Verify `gh pr list --state merged --author @me --limit 10` shows all 7 PRs merged.
4. Run `/tool-status` to sanity-check active skills still working.
5. Start Stage C (`refactor-verifier` subagent) per spec §2.4.

---

## 12. Rollback strategy per PR

Per spec §5.5 — adjusted for manual-merge reality:

- **PR already merged, broke main** → `git revert <merge-commit-sha>` → new PR → Codex+Copilot review → manual merge.
- **PR still open, wrong direction** → `gh pr close <N>` + `git branch -D refactor/<n>`. Update manifest line if needed. New PR.
- **PR #5 partial failure** (e.g., `finolog_service` extract breaks) → critical path; abort by closing PR without merge, fix import, reopen.

No force-push to main. No amending merged commits. Branches auto-delete on squash-merge (repo-level setting is live).

---

## 13. Summary for user approval

Orchestrator recommends **APPROVE AS-IS** and begin Stage B with PR #1.

Primary risks:
- PR #5 is the most delicate — extraction must happen in the same PR as deletion, else `/finolog-dds-report` breaks for anyone on that intermediate commit. (Acceptance check guards.)
- PR #6 has no automated visual regression — manual eyeball checkpoint is the gate. (Spec §5.4 built-in.)
- Branch protection is Pro-locked — workflow is "gh pr create + manual squash merge after green Codex+Copilot", which is already what `/pullrequest` skill supports.

Three user actions required across the sequence:
1. Before PR #6: confirm RLS policies on `tools` + `tool_runs` (F1).
2. Keep-or-archive `scripts/familia_eval/` (F2, recommended KEEP, override if needed).
3. After PR #4 merges: manually clean `.claude/settings.local.json` of 4 MCP entries (F3).

---

*End of refactor-manifest.md.*
