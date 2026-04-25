# Code Audit — Python Backend (Refactor v3, Phase 1)

**Date:** 2026-04-24
**Auditor:** audit-code (read-only)
**Zones:** `agents/`, `services/`, `scripts/`, `shared/`, `mcp_servers/`, `tests/`
**Input:** `docs/superpowers/specs/2026-04-24-refactor-v3-design.md`, `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md`

---

## Status of pre-existing targets (reality vs cleanup-v2)

Before auditing, noted that some cleanup-v2 targets **already deleted on disk** between 2026-04-13 and 2026-04-24:

| Target from cleanup-v2 2.5 | Current state |
|---|---|
| `services/product_matrix_api/` | **Already removed from filesystem** — `git ls-files services/` shows no product_matrix_api dir. Git log has commit `f476499 chore: remove icloud-migration leftovers`. Only the **tests** directory `tests/product_matrix_api/` remains (orphan). |
| `services/dashboard_api/` | **Already removed** (git log `fcd6f58 chore: remove dead code — marketplace_etl, etl, ozon_delivery, vasily_api`). Still referenced by 1 Python file: `scripts/init_tool_registry.py`. |
| `services/ozon_delivery/` | **Already removed** (same commit). Referenced only in docs (README.md, AGENTS.md, docs/architecture.md, etc.) and `.claude/agents/etl-engineer.md` — stale references. |
| `services/marketplace_etl/`, `services/etl/`, `services/vasily_api/` | Already removed (commit `fcd6f58`). Spec `refactor-v3` §4.1 wrongly lists `services/marketplace_etl/` and `services/etl/` as "active runtime" — they do not exist on disk. **FLAG for orchestrator.** |

---

## 1. Summary

| Verdict | Count |
|---|---:|
| **DELETE** | 44 files/dirs |
| **KEEP** | 38 files/dirs |
| **MERGE/RENAME** | 3 |
| **FLAG** | 6 |

---

## 2. DELETE list

### 2.1 `agents/oleg/` — entire subtree (per spec §2.3 PR #5)

| Path | Reason | Evidence |
|---|---|---|
| `agents/oleg/` (all subdirs + files) | Retired agent per spec §3.5. No active skill invokes it. | `grep -rn "agents.oleg" --include="*.py" outside agents/oleg, tests/, mcp_servers/` → only `scripts/run_report.py` (itself dead, see below), `scripts/finolog_dds_report/collect_data.py` (needs only `finolog_service`, see MERGE §4), `agents/finolog_categorizer/*.py` (needs `finolog_service` — itself DELETE), `deploy/healthcheck*.py` (pid path string only — see DELETE). |
| `agents/oleg/services/agent_tools.py` | 0 external imports | `grep "from agents.oleg.services.agent_tools"` outside oleg/mcp_servers → **0 hits**. Only used by `mcp_servers/wookiee_data/server.py` (itself DELETE). |
| `agents/oleg/services/price_tools.py` | 0 external imports | `grep "from agents.oleg.services.price_tools"` outside oleg/mcp_servers → **0 hits**. Only used by `mcp_servers/wookiee_price/` and `wookiee_data/` (both DELETE). |
| `agents/oleg/services/marketing_tools.py` | 0 external imports | `grep "from agents.oleg.services.marketing_tools"` outside oleg/mcp_servers → **0 hits**. Only used by `mcp_servers/wookiee_marketing/` (DELETE). |
| `agents/oleg/services/funnel_tools.py` | 0 external imports | `grep "from agents.oleg.services.funnel_tools"` outside oleg/mcp_servers → **0 hits**. Only used by `mcp_servers/wookiee_marketing/` (DELETE). |
| `agents/oleg/services/seo_tools.py` | 0 external imports | `grep "oleg.services.seo_tools"` outside oleg/mcp_servers → **0 hits**. |
| `agents/oleg/services/time_utils.py` | 0 external imports | `grep "oleg.services.time_utils"` outside oleg → **0 hits**. |
| `agents/oleg/services/price_analysis/` (subdir) | 0 external imports | `grep "agents.oleg.services.price_analysis"` outside oleg → **0 hits**. All 13 files used only internally by oleg's price_tools.py / agent_tools.py. |
| `agents/oleg/services/finolog_service.py` | Needs **MERGE** (see §4) to `shared/services/finolog_service.py` — used by `scripts/finolog_dds_report/collect_data.py` (active skill) + `agents/finolog_categorizer/*.py` (DELETE) | grep hits: 3 files import it, 1 is an active script. |
| `agents/oleg/services/finolog_categorizer.py`, `agents/oleg/services/finolog_categorizer_store.py` | 0 external imports; only used internally by `agents/finolog_categorizer/` (DELETE) | grep shows only `agents/finolog_categorizer/` imports these. |
| `agents/oleg/SYSTEM.md`, `playbook*.md`, `marketing_playbook*.md`, `funnel_playbook*.md` | oleg-specific prompts. Extract knowledge to skills if not already; else archive to `docs/archive/oleg-v2-architecture.md` per spec §3.1. |

Command run: `grep -rln "agents.oleg\|from agents.oleg\|oleg\.services" --include="*.py" /Users/danilamatveev/Projects/Wookiee | grep -v "agents/oleg/\|tests/\|mcp_servers/\|\.venv/\|__pycache__/"` → only 4 files total (3 of which are themselves DELETE: healthcheck*.py, run_report.py, finolog_categorizer/*). Surviving consumer: **only `scripts/finolog_dds_report/collect_data.py`** (`from agents.oleg.services.finolog_service import ...`).

### 2.2 `agents/finolog_categorizer/` — entire subtree (per spec §3.1)

| Path | Reason |
|---|---|
| `agents/finolog_categorizer/` (all 8 files) | Per spec §3.1 — "was deleted in 789d005, came back untracked, delete permanently". |

Evidence: `grep -rln "finolog_categorizer" --include="*.py" /Users/danilamatveev/Projects/Wookiee | grep -v "agents/finolog_categorizer/\|\.venv/\|__pycache__/"` → 0 hits. Only `agents/oleg/services/finolog_categorizer.py` is related (also DELETE). No docker-compose or deploy reference: `grep -rln finolog_categorizer --include="*.yml" --include="*.sh" deploy/` → **0 hits**.

### 2.3 `mcp_servers/` — entire subtree (per spec §3.1)

| Path | Reason |
|---|---|
| `mcp_servers/__init__.py` | Package marker, orphaned |
| `mcp_servers/common/` (2 files) | Used only by 4 local servers below |
| `mcp_servers/wookiee_data/` (2 files) | Not referenced in `.mcp.json`. Not referenced outside `docs/superpowers/plans/2026-03-19-multi-agent-phase1-mcp-and-observability.md` (old plan). |
| `mcp_servers/wookiee_kb/` (2 files) | Not referenced in `.mcp.json`. |
| `mcp_servers/wookiee_marketing/` (2 files) | Not referenced in `.mcp.json`. |
| `mcp_servers/wookiee_price/` (2 files) | Not referenced in `.mcp.json`. |

Commands run:
- `cat .mcp.json` → only 4 external Node-based servers: `wildberries-ip`, `wildberries-ooo`, `finolog`, `ozon`. **None of the 4 `wookiee_*` local Python MCP servers are listed.**
- `grep -rn "mcp_servers" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.sh" --include="Dockerfile*" agents/ services/ scripts/ shared/ tests/ deploy/ wookiee-hub/` → **0 hits** (outside mcp_servers/ itself).
- All 4 servers import from `agents/oleg/services/*_tools.py` (which is DELETE) and `services/knowledge_base/tools.py` (wookiee_kb, FLAG).
- Safe to delete `mcp_servers/` entirely per spec §3.1.

### 2.4 Scripts — orphans with 0 consumers

| Path | Reason | Evidence |
|---|---|---|
| `scripts/abc_analysis.py` | Superseded by `/abc-audit` skill (uses `scripts/abc_audit/collect_data.py`). Not called by any active skill. | `grep -rn "scripts/abc_analysis\|scripts\.abc_analysis" .claude/skills/` → **0 hits**. Only references are README.md, docs/PROJECT_MAP.md (stale docs), docs/plans/2026-02-25-db-audit-results.md (old). |
| `scripts/abc_analysis_unified.py` | Superseded by `/abc-audit` skill. Not called by any active skill. | Same — 0 hits in `.claude/skills/`. |
| `scripts/abc_helpers.py` | Support module for the two scripts above only. | `grep "abc_helpers"` → only `scripts/abc_analysis.py`, `scripts/abc_analysis_unified.py`, `scripts/init_tool_registry.py`. |
| `scripts/calc_irp.py` | **Duplicate** of `services/wb_localization/calc_irp.py` (`diff` shows zero-byte difference, both 434 lines). The canonical one is `services/wb_localization/calc_irp.py`. | `diff scripts/calc_irp.py services/wb_localization/calc_irp.py` → **no differences**. |
| `scripts/retention_cleanup.py` | Orphan — only referenced in `deploy/docker-compose.yml` (for a service that may also be dead) and one old plan. Not in any skill. | `grep -rn "retention_cleanup" --include="*.py"` → only the script itself. |
| `scripts/returns_analysis.py` | **0 references** anywhere. | `grep -rln "returns_analysis"` everywhere → **0 hits**. |
| `scripts/run_report.py` | Oleg V4 pipeline entry point. Oleg is DELETE. | Imports `agents.oleg.pipeline`, `agents.oleg.orchestrator`, `agents.oleg.agents.*`. Referenced only in `deploy/docker-compose.yml` (Oleg container) and old Oleg docs/plans. |
| `scripts/shadow_test_reporter.py` | Oleg V4 shadow test (see docstring "Reporter V4 Shadow Test"). Oleg V4 is DELETE. | `grep -rln "shadow_test_reporter"` outside scripts → only `.planning/milestones/` (archive) + `.planning/phases/01-cleanup/` (archive). |
| `scripts/wb_promocodes_test.py` | **Untracked file** (see `git status`). One-off test/spike. | `grep -rln "wb_promocodes_test"` → only the script + its output `output/wb_promocodes_test/`. 0 skill/doc references. |
| `scripts/init_tool_registry.py` | One-off registry seeder. Already ran (table exists). Registers services that are DELETE (`dashboard_api`). | Imports from `services.dashboard_api` which doesn't exist on disk — script is broken. Only referenced in `docs/superpowers/plans/2026-04-13-tool-registry.md` (plan, archived context). |

### 2.5 `shared/` — dead code

| Path | Reason | Evidence |
|---|---|---|
| `shared/data_layer/quality.py` → `validate_wb_data_quality()` | Per cleanup-v2 §2.7: 0 usages | `grep -rn "validate_wb_data_quality"` everywhere → only the function itself + `shared/data_layer/__init__.py` re-export + `agents/oleg/services/agent_tools.py` (DELETE). No other consumers. **Remove function; keep file empty or delete file + remove import from `__init__.py`.** |
| `shared/clients/bitrix_client.py` | **0 external imports** | `grep -rn "BitrixClient\|bitrix_client"` → only the file itself. |
| `shared/signals/` (entire subdir: detector.py, direction_map.py, kb_patterns.py, patterns.py) | Only used by Oleg (advisor pipeline) and its tests | `grep -rln "shared.signals"` → only `agents/oleg/*`, `tests/integration/test_advisor_pipeline.py`, `tests/shared/signals/*`, `tests/agents/oleg/*`. With Oleg gone, this becomes dead code. **FLAG** — orchestrator should confirm no planned future use. |

### 2.6 `tests/` — must go with their targets (to prevent CI breakage)

Per spec rule: "any test file that imports from agents/oleg/, agents/finolog_categorizer/, mcp_servers/, services/product_matrix_api/, or other DELETE candidates must be marked DELETE itself".

| Path | Reason |
|---|---|
| `tests/agents/oleg/` (entire subtree — advisor, validator, orchestrator, playbooks, runner, storage) | All import from `agents.oleg.*` |
| `tests/oleg/` (entire subtree — conftest, test_circuit_breaker.py, test_orchestrator.py, test_react_loop.py, test_state_store.py, pipeline/) | All import from `agents.oleg.*` |
| `tests/integration/test_advisor_pipeline.py` | Imports `shared.signals.*` (tied to Oleg advisor chain) — dies with Oleg |
| `tests/shared/signals/` (all 10 test files) | Tests for `shared/signals/*` which dies with Oleg |
| `tests/product_matrix_api/` (entire subtree, 22 test files) | `services/product_matrix_api/` already gone — these fail at import time |

Evidence: `grep -l "agents.oleg\|services.product_matrix_api" tests/agents/oleg tests/oleg tests/integration tests/product_matrix_api tests/shared/signals -r` → all files match.

`tests/agents/__init__.py` — reconsider: if `tests/agents/oleg/` is deleted, `tests/agents/` becomes empty shell → DELETE.

---

## 3. KEEP list

### 3.1 `shared/` — actively used

| Path | Purpose | Main consumers |
|---|---|---|
| `shared/__init__.py` | package marker | — |
| `shared/config.py` | unified config (.env loader) | 18+ importers in scripts/services |
| `shared/data_layer/` (except `quality.py`) | SQL query layer | All analytics scripts + services |
| `shared/clients/openrouter_client.py` | LLM client | analytics/marketing/reviews/abc skills |
| `shared/clients/mpstats_client.py` | MPStats | market-review, funnel-report, tests |
| `shared/clients/wb_client.py` | WB API | many; 11 importers |
| `shared/clients/ozon_client.py` | OZON API | logistics/ETL |
| `shared/clients/sheets_client.py` | Google Sheets | wb_localization, sheets_sync, marketing |
| `shared/clients/moysklad_client.py` | MoySklad | wb_localization |
| `shared/model_mapping.py` | model-name mapping | 13+ importers |
| `shared/notion_blocks.py`, `shared/notion_client.py` | Notion helpers | daily-brief, scripts/notion_sync.py, reporters |
| `shared/tool_logger.py` | tool_runs logger (Supabase) | sheets_sync/runner, logistics_audit, sync_sheets_to_supabase, analytics_report (via skills). |
| `shared/utils/json_utils.py` | JSON helpers | (check — 0 direct imports found; light FLAG) |

### 3.2 `services/` — actively used

| Path | Purpose | Consumers |
|---|---|---|
| `services/__init__.py` | package | — |
| `services/sheets_sync/` | Google Sheets ↔ Supabase | `scripts/run_search_queries_sync.py`, `scripts/calc_irp.py` (→keep IRP in wb_localization), `services/wb_localization/*`, `deploy/docker-compose.yml: wookiee-sheets-sync` |
| `services/wb_localization/` | Локализация WB + calculators + sheets_export | `scripts/logistics_report/collect_data.py`, `tests/wb_localization/*`, `docker-compose.yml: wookiee-localization` |
| `services/wb_localization/calculators/` (untracked) | calculators | `services/wb_localization/run_localization.py`, tests |
| `services/wb_localization/sheets_export/` (untracked) | Sheets export | `services/wb_localization/run_localization.py` |
| `services/wb_logistics_api/` (untracked) | FastAPI service | `deploy/Dockerfile.wb_logistics_api`, `docker-compose.yml` line 76 |
| `services/logistics_audit/` | WB+OZON logistics audit | `shared/tool_logger.py` consumer + tests |
| `services/content_kb/` | photo vector search | `/content-search` skill (`.claude/skills/content-search/SKILL.md`), `tests/content_kb/*`, `scripts/init_tool_registry.py` mention |
| `services/creative_kb/` (untracked) | creatives vector KB | spec `2026-04-17-creative-kb-design.md`; no active skill yet. **FLAG** — active but pre-skill. |
| `services/observability/` | **legacy** — nobody imports from `services.observability` | `grep "from services.observability"` → **0 Python hits**. Only docs references. `shared/tool_logger.py` replaces this. **Candidate to RENAME/RETIRE (see §4).** |

### 3.3 `scripts/` — actively used

| Path | Purpose | Consumer skill |
|---|---|---|
| `scripts/data_layer.py` | Backward-compat shim (`from scripts.data_layer import *`) | `agents/oleg/services/agent_tools.py` (DELETE), `services/wb_localization/generate_localization_report_v3.py`. **FLAG** — after Oleg cleanup, used by 1 file; can migrate to `shared.data_layer` direct import. |
| `scripts/notion_sync.py` | Notion sync for reports | `scripts/abc_analysis*.py` (DELETE), imported via `from scripts.notion_sync import sync_report_to_notion`. **FLAG** — once abc_analysis.py gone, check remaining consumers (grep suggests none in Python). Referenced in docs as standalone CLI tool. |
| `scripts/generate_tools_catalog.py` | Regenerate `docs/TOOLS_CATALOG.md` from Supabase `tools` table | `/tool-register` skill |
| `scripts/run_search_queries_sync.py` | WB search queries sync | `docker-compose.yml: wookiee-search-queries` cron |
| `scripts/sync_sheets_to_supabase.py` | Sheets sync | `/sync-sheets` skill |
| `scripts/abc_audit/` (collect_data.py, utils.py, collectors/) | ABC audit collector | `/abc-audit` skill |
| `scripts/analytics_report/` (collect_all.py, collectors/, utils.py) | All analytics collectors | `/finance-report`, `/marketing-report`, `/funnel-report` skills |
| `scripts/daily_brief/` (run.py, collector.py, forecast.py, funnel.py, marketing_sheets.py, patterns.py) | Daily brief bundle | `/daily-brief` skill |
| `scripts/financial_overview/` (collect_all.py, collectors/) | **FLAG** — referenced only in old spec `2026-04-02-financial-overview-skill-design.md`. Is `/financial-overview` skill active or retired? No such skill in `.claude/skills/`. |
| `scripts/finolog_dds_report/collect_data.py` | Finolog DDS collector | `/finolog-dds-report` skill. **Needs extraction of `finolog_service`** (see §4). |
| `scripts/funnel_report/validate_output.py` | Gate check for funnel | `/funnel-report` skill (SKILL.md line uses it) |
| `scripts/logistics_report/collect_data.py` | Logistics collector | `/logistics-report` skill |
| `scripts/market_review/` (collect_all.py, collectors/, config.py) | Market review collector | `/market-review` skill |
| `scripts/monthly_plan/` (collect_all.py, utils.py, collectors/) | Monthly plan | `/monthly-plan` skill |
| `scripts/reviews_audit/collect_data.py` | Reviews collector | `/reviews-audit` skill |
| `scripts/audit_remediation/` (4 files: wave1_cleanup, wave3_schema_migration, delete_legacy_models, fix_barcodes) | DB audit remediation scripts | Standalone, referenced only in `docs/superpowers/plans/2026-04-12-database-audit-remediation.md` and `2026-04-13-audit-deferred-tasks.md`. **FLAG** — already-ran migrations or still needed? |
| `scripts/familia_eval/` (run.py, agents/, collector.py, calculator.py, config.py, prompts/, data/, output/) | Familia competitor eval | No active skill, but `tests/test_familia_eval.py` exercises it; referenced in spec `2026-04-07-familia-eval-design.md`. **FLAG** — standalone tool, is it still used? |

### 3.4 `agents/`

| Path | Purpose |
|---|---|
| `agents/__init__.py` | Keep as empty scaffold per spec §3.5 (add README later). |

### 3.5 `tests/` — actively useful

| Path | Purpose |
|---|---|
| `tests/__init__.py`, `tests/conftest.py` | Root test infra |
| `tests/analytics_report/test_utils.py` | Tests `scripts/analytics_report/utils.py` |
| `tests/monthly_plan/*` (test_collect_all.py, test_utils.py) | Tests `scripts/monthly_plan/*` |
| `tests/logistics_audit/*` (4 files) | Tests `services/logistics_audit/*` (duplicate/legacy? see §4) |
| `tests/services/logistics_audit/*` (7 files) | Tests `services/logistics_audit/*` — newer set |
| `tests/content_kb/*` (4 files) | Tests `services/content_kb/*` |
| `tests/wb_localization/*` (13 files) | Tests `services/wb_localization/*` |
| `tests/test_abc_audit_collector.py` | `scripts/abc_audit/utils.py` |
| `tests/test_familia_eval.py` | `scripts/familia_eval/*` — keep if that stays |
| `tests/test_market_review_collectors.py` | `scripts/market_review/*` |
| `tests/test_mpstats_client.py` | `shared/clients/mpstats_client.py` |
| `tests/test_reviews_audit_collector.py` | `scripts/reviews_audit/*` |
| `tests/test_sync_sheets_to_supabase.py` | `scripts/sync_sheets_to_supabase.py` |
| `tests/test_wb_client_chats.py` | `shared/clients/wb_client.py` |

---

## 4. MERGE / RENAME suggestions

| From | To | Reason |
|---|---|---|
| `agents/oleg/services/finolog_service.py` | `shared/services/finolog_service.py` (or `services/finolog_client/finolog_service.py`) | **MUST extract** — active consumer `scripts/finolog_dds_report/collect_data.py` imports it. Per spec §2.3 PR #5 "Если orchestrator подтвердил что `*_tools.py` нужны где-то ещё — extraction в `shared/services/` перед удалением." `finolog_service.py` is the only such file (others are 0-hit outside oleg+mcp_servers). |
| `scripts/calc_irp.py` | DELETE (duplicate of `services/wb_localization/calc_irp.py`) | `diff` shows files are byte-identical. Keep the services/ copy; remove the scripts/ copy. Update README.md/AGENTS.md references. |
| `services/observability/` | **RENAME** to `services/tool_telemetry/` or similar per spec §3.4 | Orphan directory; `shared/tool_logger.py` is the active writer to `tool_runs`. Rename or merge the schema + version_tracker into `shared/tool_logger.py`. **Orchestrator finalizes name per §3.4.** |
| `tests/logistics_audit/` + `tests/services/logistics_audit/` | MERGE into single `tests/services/logistics_audit/` | Two parallel test dirs for same module (one has 4 files, other 7 — non-overlapping). Consolidate. |

---

## 5. FLAG list (orchestrator decisions needed)

| # | Question | Files involved |
|---|---|---|
| F1 | `services/knowledge_base/` — KEEP or DELETE? Currently imported by 4 Oleg agent files (DELETE), 1 MCP server (DELETE), and has a `deploy/Dockerfile.knowledge_base` + `docker-compose.yml` entry `wookiee_knowledge_base`. No active Python skill imports it. Is the Dockerfile deployment still active (supports any skill?), or is Content KB (`services/content_kb/`) the replacement? `docs/system.md` says wookiee_knowledge_base "Не используется в pipeline". **Strongly suspected DELETE** after oleg/mcp removal. | `services/knowledge_base/` (all files), `deploy/Dockerfile.knowledge_base`, `deploy/docker-compose.yml` lines 201-203 |
| F2 | `shared/signals/` — KEEP or DELETE? Only used by Oleg + its tests. With Oleg removed, 0 consumers. Brainstorm plan mentions "new pattern-first architecture"; is signals/ part of the future or legacy? | `shared/signals/*` (5 files), `tests/shared/signals/*` (10 files), `tests/integration/test_advisor_pipeline.py` |
| F3 | `services/creative_kb/` — active untracked, but no skill consumes it yet. Per spec §3.3 commit-and-keep. Confirm no active code depends on it yet. | `services/creative_kb/` (untracked tree) |
| F4 | `scripts/financial_overview/` — orphan collector for a skill that doesn't exist in `.claude/skills/`. Delete or keep as future use? | `scripts/financial_overview/collect_all.py`, `scripts/financial_overview/collectors/` |
| F5 | `scripts/familia_eval/` — orphan tool. `tests/test_familia_eval.py` exists but no skill. Per feedback memory the project is active. Keep or archive? | `scripts/familia_eval/*`, `tests/test_familia_eval.py` |
| F6 | `scripts/audit_remediation/` — 4 one-off migration scripts. Already ran? Keep for reference or DELETE? | `scripts/audit_remediation/{wave1_cleanup,wave3_schema_migration,delete_legacy_models,fix_barcodes}.py` |
| F7 | **Spec §4.1 lists `services/marketplace_etl/` and `services/etl/` as active runtime, but they do not exist** (removed in commit `fcd6f58`). Orchestrator must correct the spec in the manifest. | spec `2026-04-24-refactor-v3-design.md` §4.1 |
| F8 | `scripts/data_layer.py` shim — after Oleg cleanup, only `services/wb_localization/generate_localization_report_v3.py` imports from it. Migrate that one to `from shared.data_layer import` and delete the shim? | `scripts/data_layer.py` |
| F9 | `scripts/notion_sync.py` — Python consumers are `scripts/abc_analysis*.py` (DELETE). After that, 0 Python consumers. Referenced in docs as standalone CLI (`python scripts/notion_sync.py --file reports/...`). Keep as CLI tool or fold into shared? | `scripts/notion_sync.py` |
| F10 | `shared/utils/json_utils.py` — no importers found in Python. Verify vs dead code. | `shared/utils/json_utils.py` |

---

## 6. Special checks (per audit instructions)

### 6.1 `mcp_servers/` verification

- `.mcp.json` entries: `wildberries-ip`, `wildberries-ooo`, `finolog`, `ozon` — **all external Node servers**, none point to local `mcp_servers/wookiee_*`.
- `grep -rn "mcp_servers" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.sh" --include="Dockerfile*" agents/ services/ scripts/ shared/ tests/ deploy/ wookiee-hub/` → **0 hits** (all references are inside mcp_servers/ itself or in docs/superpowers/plans/).
- No external `.mcp.json` anywhere else (verified repo root only).
- **Verdict:** All 4 local MCP servers (`wookiee_data`, `wookiee_kb`, `wookiee_marketing`, `wookiee_price`) + `mcp_servers/common/` + `mcp_servers/__init__.py` are safe to DELETE.

### 6.2 `agents/oleg/services/*_tools.py` extraction grep

Command: `grep -rn "from agents.oleg.services.\(agent_tools\|price_tools\|marketing_tools\|funnel_tools\|seo_tools\|time_utils\)" --include="*.py" outside agents/oleg/ and mcp_servers/`

Result: **0 hits**. No extraction needed for these six tools files — they die with Oleg + MCP.

Separate finding: `from agents.oleg.services.finolog_service import ...` — **3 hits**:
- `agents/finolog_categorizer/scanner.py:18` (DELETE with finolog_categorizer)
- `agents/finolog_categorizer/app.py:22` (DELETE)
- `scripts/finolog_dds_report/collect_data.py:79` — **active consumer** (`/finolog-dds-report` skill)

**Conclusion:** `finolog_service.py` is the single Oleg services file that needs extraction to `shared/services/finolog_service.py` (or similar). All other `*_tools.py` files die with Oleg.

### 6.3 `scripts/` orphan check

Mapping script → consumer skill (present in `.claude/skills/<name>/SKILL.md`):

| Script | Consumer | Status |
|---|---|---|
| `scripts/abc_audit/collect_data.py` | `/abc-audit` | KEEP |
| `scripts/analytics_report/collect_all.py` | `/finance-report`, `/marketing-report`, `/funnel-report` | KEEP |
| `scripts/daily_brief/run.py` | `/daily-brief` | KEEP |
| `scripts/finolog_dds_report/collect_data.py` | `/finolog-dds-report` | KEEP |
| `scripts/funnel_report/validate_output.py` | `/funnel-report` | KEEP |
| `scripts/logistics_report/collect_data.py` | `/logistics-report` | KEEP |
| `scripts/market_review/collect_all.py` | `/market-review` | KEEP |
| `scripts/monthly_plan/collect_all.py` | `/monthly-plan` | KEEP |
| `scripts/reviews_audit/collect_data.py` | `/reviews-audit` | KEEP |
| `scripts/generate_tools_catalog.py` | `/tool-register` | KEEP |
| `scripts/sync_sheets_to_supabase.py` | `/sync-sheets` + `docker-compose.yml` cron | KEEP |
| `scripts/run_search_queries_sync.py` | `docker-compose.yml` cron | KEEP |
| `scripts/abc_analysis.py` | (none — superseded) | **DELETE** |
| `scripts/abc_analysis_unified.py` | (none — superseded) | **DELETE** |
| `scripts/abc_helpers.py` | (only the two above) | **DELETE** |
| `scripts/calc_irp.py` | (duplicate) | **DELETE** |
| `scripts/data_layer.py` | shim, 1 legacy consumer | **FLAG** |
| `scripts/notion_sync.py` | standalone CLI | **FLAG** |
| `scripts/retention_cleanup.py` | docker-compose only | **DELETE** candidate |
| `scripts/returns_analysis.py` | (none) | **DELETE** |
| `scripts/run_report.py` | Oleg V4 pipeline — DELETE with Oleg | **DELETE** |
| `scripts/shadow_test_reporter.py` | Oleg V4 shadow test | **DELETE** |
| `scripts/wb_promocodes_test.py` | one-off, untracked | **DELETE** |
| `scripts/init_tool_registry.py` | one-off, broken (imports dashboard_api) | **DELETE** |
| `scripts/familia_eval/*` | standalone, no skill | **FLAG** |
| `scripts/financial_overview/*` | standalone, no skill | **FLAG** |
| `scripts/audit_remediation/*` | migrations, maybe already ran | **FLAG** |

### 6.4 `services/product_matrix_api/`, `dashboard_api/`, `knowledge_base/`, `ozon_delivery/` status

- `services/product_matrix_api/` — **already physically removed from disk** (filesystem shows no dir). Git log: commit `f476499 chore: remove icloud-migration leftovers + finalize Vasily→WB Logistics`. Only `tests/product_matrix_api/` remains (22 orphan test files — **DELETE**).
- `services/dashboard_api/` — **already physically removed** (commit `fcd6f58`). Still referenced in code by exactly **one** file: `scripts/init_tool_registry.py` (which is itself DELETE per §6.3). Stale doc references in README, docs/PROJECT_MAP.md.
- `services/knowledge_base/` — **EXISTS on disk.** Imports only from Oleg + 1 MCP server (both DELETE) — **see FLAG F1**. Strongly DELETE after Oleg/MCP cleanup.
- `services/ozon_delivery/` — **already physically removed** (commit `fcd6f58`). Only referenced in stale docs (README, AGENTS.md, docs/architecture.md, `.claude/agents/etl-engineer.md`) — **update docs** (out of scope for audit-code).
- `services/observability/` — **EXISTS on disk** but has 0 Python importers (verified: `grep "from services.observability" --include="*.py"` returns empty). Only doc references. See §4 RENAME.

### 6.5 `tests/` cascade DELETE list

Tests that must be DELETEd (otherwise CI breaks after PR #4/#5):

| Test path | Imports from (DELETE target) |
|---|---|
| `tests/agents/` entire subtree | `agents/oleg/*` |
| `tests/oleg/` entire subtree | `agents/oleg/*` |
| `tests/integration/test_advisor_pipeline.py` | `shared/signals/*` (FLAG F2) |
| `tests/shared/signals/` (10 files) | `shared/signals/*` (FLAG F2) |
| `tests/product_matrix_api/` (22 files) | `services/product_matrix_api/*` (already gone) |

After deletion, check that `tests/integration/` and `tests/shared/` parent dirs don't become empty; they might still hold other tests. Currently: after removal, `tests/integration/` and `tests/shared/` both become empty — **DELETE directories too**.

`tests/integration/` had only `test_advisor_pipeline.py` → empty after → DELETE.
`tests/shared/signals/` was the only thing under `tests/shared/` → empty after → DELETE `tests/shared/`.
`tests/agents/` after removing `oleg/` subtree is empty → DELETE.

---

## 7. Appendix: Key grep commands run

```bash
# MCP server references
grep -rn "mcp_servers\|wookiee_data\|wookiee_kb\|wookiee_marketing\|wookiee_price" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.json" \
  --include="*.sh" --include="Dockerfile*" \
  /Users/danilamatveev/Projects/Wookiee/{agents,services,scripts,shared,tests,deploy,wookiee-hub}
# → 0 hits outside mcp_servers/ itself

cat .mcp.json  # → 4 external Node MCP servers only

# Oleg services external imports
grep -rn "from agents.oleg.services\." --include="*.py" \
  /Users/danilamatveev/Projects/Wookiee \
  | grep -v "agents/oleg/\|tests/\|mcp_servers/\|\.venv/\|__pycache__/"
# → only agents/finolog_categorizer/*, scripts/finolog_dds_report/*, 
#   deploy/healthcheck*.py (pid strings), scripts/run_report.py (DELETE)
# → only finolog_service needs extraction

# Script consumers
grep -rn "scripts/<name>\|scripts\.<name>" --include="*.py" --include="*.md" \
  .claude/skills/ deploy/ docs/
# Per-script evidence in §6.3

# Service existence check
ls services/ && git ls-files services/ | cut -d/ -f1-2 | sort -u
# → product_matrix_api, dashboard_api, ozon_delivery directories are ABSENT

# calc_irp duplicate check
diff scripts/calc_irp.py services/wb_localization/calc_irp.py
# → no differences (byte-identical)
```

---

## 8. Suggested PR mapping (informational, orchestrator decides)

| Spec PR # | Files this audit identifies |
|---|---|
| #4 (remove-dead-code) | `mcp_servers/` (all), `agents/finolog_categorizer/` (all), `tests/product_matrix_api/`, `tests/shared/signals/`, `tests/integration/test_advisor_pipeline.py`, `shared/clients/bitrix_client.py`, `scripts/{abc_analysis,abc_analysis_unified,abc_helpers,calc_irp,retention_cleanup,returns_analysis,wb_promocodes_test,init_tool_registry}.py`, `shared/data_layer/quality.py` (remove `validate_wb_data_quality` at minimum) |
| #5 (oleg-cleanup) | `agents/oleg/` (all), `scripts/run_report.py`, `scripts/shadow_test_reporter.py`, `tests/agents/oleg/`, `tests/oleg/`, + **extract** `finolog_service.py` to `shared/services/` first; after F2 confirm, optionally delete `shared/signals/` |
| #7 (docs-unification) | Rename `services/observability/` → new name (F7 decides); MERGE `tests/logistics_audit/` + `tests/services/logistics_audit/` |

---

*End of code-audit.md.*
