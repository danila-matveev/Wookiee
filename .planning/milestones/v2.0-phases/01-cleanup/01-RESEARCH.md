# Phase 1: Очистка - Research

**Researched:** 2026-03-30
**Domain:** Codebase cleanup — dead code removal, dependency purge, Docker reconfiguration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** agents/v3/ удаляется целиком со всем содержимым (20+ файлов)
- **D-02:** tests/v3/ и tests/agents/v3/ удаляются целиком
- **D-03:** Скрипты в scripts/, импортирующие agents.v3, удаляются: run_report.py, rerun_weekly_reports.py, test_v2_bridge.py, run_price_analysis.py, shadow_test_reporter.py
- **D-04:** run_finolog_weekly.py — НЕ удалять, починить позже (finolog-cron контейнер остаётся)
- **D-05:** run_localization_report.py — проверить: если единственная зависимость от V3 легко заменяема, развязать; иначе починить позже
- **D-06:** agents/oleg/services/price_tools.py импортирует agents.v3.config.get_wb_clients() — развязать (перенести функцию)
- **D-07:** Контейнер wookiee-oleg сейчас запускает python -m agents.v3 — Claude решит: переключить на V2 или убрать (Phase 4 займётся запуском)
- **D-08:** finolog-cron контейнер — оставить
- **D-09:** Volume agents/v3/data — удалить из docker-compose при удалении V3
- **D-10:** V3-related docs удаляются жёстко (6 конкретных файлов перечислены)
- **D-11:** Claude решает, есть ли ещё устаревшие docs для удаления
- **D-12:** Удалить langchain/langgraph/langchain-openai из agents/v3/requirements.txt (вместе с удалением всей директории)
- **D-13:** Проверить корневой requirements.txt и другие requirements*.txt на наличие V3-only зависимостей

### Claude's Discretion

- Решение куда перенести get_wb_clients() — shared/config.py или agents/oleg/config
- Что делать с run_localization_report.py — удалить или развязать
- Как обновить Docker-compose: переключить на V2 entrypoint или удалить контейнер wookiee-oleg
- Объём очистки docs — удалить всё V3-related, плюс при необходимости устаревшие docs

### Deferred Ideas (OUT OF SCOPE)

- Починка finolog-cron скрипта (run_finolog_weekly.py) — Phase 3 или 4
- Полная настройка Docker-compose для V2 — Phase 4 (Запуск и доставка)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLEAN-01 | agents/v3/ полностью удалён (все файлы, директории, зависимости) | Full file inventory below — 80+ files including __pycache__, data files, subdirs |
| CLEAN-02 | Зависимости langchain/langgraph/langchain-openai удалены из requirements | Only agents/v3/requirements.txt contains these — confirmed by grep scan |
| CLEAN-03 | V3-related docs, plans, specs удалены из docs/ | Full list of V3/stale docs inventoried below |
| CLEAN-04 | Docker-compose обновлён — контейнер запускает V2 систему напрямую, без V3 | wookiee-oleg currently runs `python -m agents.v3` with v3/data volume — both need updating |
</phase_requirements>

---

## Summary

Phase 1 is a pure deletion/cleanup phase with one surgical code change. No new features are built. The scope is bounded and well-understood: delete agents/v3/ entirely, cut two cross-references from live code into V3, clean stale docs, and fix docker-compose to no longer reference V3.

The main non-trivial work is the V3 cross-reference untangling. Two live files import from agents.v3: `agents/oleg/services/price_tools.py` imports `config.get_wb_clients()` (a simple function that reads env vars and creates WBClient instances), and `scripts/run_finolog_weekly.py` imports V3 config + delivery (but is deferred to a later phase per D-04). The `run_localization_report.py` script has a deep V3 dependency in its `_publish_to_notion()` function — it uses `agents.v3.delivery.router.deliver` and `agents.v3.config` directly.

After this phase, the codebase has zero imports of agents.v3, the directory does not exist, and docker-compose runs agents.oleg (V2) directly or has the wookiee-oleg service stubs pointing to V2.

**Primary recommendation:** Delete first, fix cross-references second, update docker-compose last. This ordering prevents broken imports while the directory still exists.

---

## Architecture Patterns

### Recommended Execution Order

The phase has four distinct areas of work. Order matters:

1. **Fix cross-references FIRST** — before deleting agents/v3/, patch the two files that import from it so no code is left broken
2. **Delete agents/v3/ and tests** — safe to delete after step 1
3. **Delete V3 scripts** — scripts that only wrap V3 can be deleted wholesale
4. **Update docker-compose** — remove V3 volume and change wookiee-oleg command
5. **Delete stale docs** — safest last, no code dependencies

### Pattern: Moving get_wb_clients() out of V3

The function `get_wb_clients()` in `agents/v3/config.py` (lines 126–136) is self-contained: it reads `WB_API_KEY_IP` / `WB_API_KEY_OOO` from env vars and returns `{cabinet_name: WBClient}`. It has no V3-specific logic whatsoever.

**Recommended destination:** Copy the function into `agents/oleg/services/price_tools.py` itself (at module level or as a local helper), since it is only called from `_handle_analyze_promotion()` in that file. This is the minimal-footprint option — no need to add it to shared/config.py (which is a data config module, not a client factory).

Alternative: put it in `agents/oleg/services/` as a small `marketplace_clients.py` if other oleg services need it in the future. But right now only price_tools.py calls it.

**The change:**
```python
# agents/oleg/services/price_tools.py — add at top of file (no V3 import needed)
def _get_wb_clients() -> dict:
    """Return dict {cabinet_name: WBClient} for all configured cabinets."""
    import os
    from shared.clients.wb_client import WBClient
    clients = {}
    if wb_ip := os.getenv("WB_API_KEY_IP", ""):
        clients["IP"] = WBClient(api_key=wb_ip, cabinet_name="IP")
    if wb_ooo := os.getenv("WB_API_KEY_OOO", ""):
        clients["OOO"] = WBClient(api_key=wb_ooo, cabinet_name="OOO")
    return clients

# Then in _handle_analyze_promotion(), replace:
#   from agents.v3 import config
#   clients = config.get_wb_clients()
# with:
#   clients = _get_wb_clients()
```

Same pattern applies for `get_ozon_clients()` if `_handle_analyze_promotion` also needs it (line 654 calls `config.get_ozon_clients()`).

### Pattern: run_localization_report.py Decision

The script imports V3 in `_publish_to_notion()` only — the data generation half (`_generate_report()`) is 100% V3-free. The V3 usage is: `agents.v3.delivery.router.deliver` and `agents.v3.config` (for tokens/IDs).

**Decision: DELETE the script.** Reasoning:
- The report generation service (`services/wb_localization/`) is complete and standalone
- V3 delivery layer (`agents.v3.delivery.router`) will not exist after this phase
- Rewriting the delivery portion requires importing from `shared/notion_client.py` and a Telegram HTTP call — this is exactly what Phase 3 (reliability) and Phase 4 (delivery) will build properly
- A broken delivery script is worse than no script

This fulfills D-05's "развязать; иначе починить позже" — the localization report service itself is untouched; only the manual runner script is removed.

### Pattern: Docker-compose wookiee-oleg Update

Current state:
```yaml
wookiee-oleg:
  command: ["python", "-m", "agents.v3"]
  volumes:
    - ../agents/v3/data:/app/agents/v3/data   # <- DELETE
    - ../agents/oleg/data:/app/agents/oleg/data
```

**Decision: Point to V2 directly** (not remove the container). The container infrastructure (env, networks, resource limits) is correct — only the entrypoint and one volume need changing:
```yaml
wookiee-oleg:
  command: ["python", "-m", "agents.oleg"]   # V2 entrypoint
  volumes:
    # Remove ../agents/v3/data line
    - ../agents/oleg/data:/app/agents/oleg/data
    - ../services/etl/data:/app/services/etl/data
    - ../reports:/app/reports
    - ../scripts:/app/scripts:ro
```

Note: Phase 4 will properly set up the V2 scheduling/entrypoint. For this phase, the goal is just removing V3 references — if `python -m agents.oleg` doesn't fully work yet, that's acceptable (Phase 4 handles it). CLEAN-04 only requires "без упоминаний V3", not that the container is fully functional.

---

## Complete Inventory

### agents/v3/ Contents (to delete entirely)

**Root Python files (confirmed):**
- `__init__.py`, `__main__.py`, `app.py`, `christina.py`, `config.py`, `gates.py`, `monitor.py`, `orchestrator.py`, `prompt_tuner.py`, `report_formatter.py`, `runner.py`, `scheduler.py`, `state.py`
- `data_catalog.json`
- `requirements.txt`

**Subdirectories:**
- `agents/` — 20 `.md` micro-agent definition files
- `conductor/` — `__init__.py`, `conductor.py`, `schedule.py`, `state.py`, `validator.py`
- `delivery/` — `__init__.py`, `messages.py`, `router.py`, `telegram.py` (note: no `notion.py` in delivery — it was merged into shared/notion_client.py)
- `data/` — `.gitkeep`, `conductor.db`, `v3_state.db`, `test_reports/` (5 markdown files)
- `__pycache__/` — 15+ `.pyc` files

**Total: ~80 files across 7 subdirectories**

### tests/ to delete

- `tests/v3/` — `__init__.py`, `conftest.py`, `test_monitor.py`, `test_messages.py`, `test_orchestrator_pi.py`, `test_prompt_tuner.py`, `test_notion_add_comment.py` + `conductor/` subdir (6 test files)
- `tests/agents/v3/` — `__init__.py`, `test_trust_envelope.py`

### scripts/ to delete

Confirmed V3-only scripts (all import from agents.v3):
- `run_report.py` — V3 orchestrator wrapper
- `rerun_weekly_reports.py` — V3 weekly restart
- `test_v2_bridge.py` — V3/V2 bridge test
- `run_price_analysis.py` — V3 config-based price analysis
- `run_localization_report.py` — V3 delivery layer (see decision above: DELETE)

Already deleted (per git status):
- `shadow_test_reporter.py` — shows as `D` in git status (already staged for deletion)

**Keep (do not delete):**
- `run_finolog_weekly.py` — per D-04, deferred fix

### scripts/ to keep with modifications needed (V3 import but deferred)

- `run_finolog_weekly.py` — imports `from agents.v3 import config` and `agents.v3.delivery.telegram.split_html_message`. After V3 is deleted this script will be broken. This is ACCEPTED — it's explicitly deferred to Phase 3/4. The finolog-cron container should be stopped (or its healthcheck will fail) until fixed in a later phase.

### Cross-references to patch before deletion

| File | Line | What to change |
|------|------|----------------|
| `agents/oleg/services/price_tools.py` | 639 | Replace `from agents.v3 import config` + `config.get_wb_clients()` + `config.get_ozon_clients()` with inline helper |
| `shared/notion_client.py` | 5 | Comment-only reference — no code change needed, just delete the comment |

### docs/ to delete

**Explicitly listed in D-10:**
- `docs/superpowers/specs/2026-03-22-v3-full-migration-design.md`
- `docs/superpowers/specs/2026-03-22-v3-report-depth-gap.md`
- `docs/superpowers/specs/2026-03-24-v3-reports-audit.md`
- `docs/superpowers/plans/2026-03-20-v3-full-migration.md`
- `docs/superpowers/plans/2026-03-23-v3-full-migration-plan.md`
- `docs/superpowers/plans/2026-03-24-v3-reports-fix-plan.md`

**Additional stale docs (D-11 discretion — delete these too):**
- `docs/superpowers/plans/2026-03-26-stage1-cleanup-plan.md` — superseded cleanup plan from a prior attempt
- `docs/superpowers/plans/2026-03-28-project-cleanup-plan.md` — superseded by current v2.0 milestone
- `docs/superpowers/specs/2026-03-26-stage1-cleanup-design.md` — superseded cleanup design
- `docs/superpowers/specs/2026-03-26-unified-reporting-system.md` — V3-era unified system design, replaced by v2.0
- `docs/superpowers/specs/2026-03-27-reporting-system-audit.md` — V3-era audit
- `docs/superpowers/specs/2026-03-28-project-cleanup-design.md` — superseded

**Keep (not V3-specific):**
- All advisor/product-matrix/content-kb/logistics/comms plans and specs — unrelated to V3
- `docs/superpowers/plans/2026-03-28-notification-spam-fix-plan.md` — may still be relevant, not V3

### requirements.txt scan results

**Only `agents/v3/requirements.txt` contains langchain/langgraph/langchain-openai.** Confirmed by scan of all 10 requirements files in the project. No other requirements file needs modification for CLEAN-02.

**Verified (none contain langchain):**
- `agents/oleg/requirements.txt`
- `services/content_kb/requirements.txt`
- `services/knowledge_base/requirements.txt`
- `services/sheets_sync/requirements.txt`
- `services/product_matrix_api/requirements.txt`
- `services/dashboard_api/requirements.txt`
- `sku_database/requirements.txt`
- `docs/archive/retired_agents/*/requirements.txt` (archive, skip)

CLEAN-02 is automatically satisfied by deleting agents/v3/ (the only file containing these dependencies is deleted in CLEAN-01).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deleting directories with Python | Custom deletion script | Shell `rm -rf` or Python `shutil.rmtree` | Standard tools, no edge cases |
| Finding V3 imports | Manual grep | `grep -r "agents.v3" --include="*.py"` | Exhaustive, fast, no misses |

---

## Common Pitfalls

### Pitfall 1: Deleting agents/v3/ Before Patching Price_tools.py
**What goes wrong:** If agents/v3/ is deleted while `price_tools.py` still has `from agents.v3 import config`, the agents/oleg container will fail to import on startup with ModuleNotFoundError.
**Why it happens:** Import is inside a function (`_handle_analyze_promotion`) — it runs lazily but will crash on first price analysis request.
**How to avoid:** Patch price_tools.py first, verify the import is gone, then delete agents/v3/.
**Warning signs:** `ModuleNotFoundError: No module named 'agents.v3'` in oleg container logs.

### Pitfall 2: run_finolog_weekly.py Left Broken in Live Container
**What goes wrong:** finolog-cron container continues running `python -m scripts.run_finolog_weekly`, which now imports deleted `agents.v3`. Monday 09:00 cron fires → ImportError → no report.
**Why it happens:** The script is kept (D-04) but V3 is deleted.
**How to avoid:** Either disable the finolog-cron container in docker-compose (add `profiles` or comment it out) OR document explicitly that it will fail until Phase 3/4. The planner must address this — it cannot be silently left broken on the live server.
**Recommended action:** Disable finolog-cron container in docker-compose for now (add `# disabled until Phase 3` comment and remove from active services or add `profiles: [disabled]`).

### Pitfall 3: __pycache__ Contamination
**What goes wrong:** After deleting agents/v3/ source files, Python may still find .pyc files if __pycache__ is somehow reachable. This is not an issue when using `rm -rf` but is relevant if using selective file deletion.
**How to avoid:** Delete the entire agents/v3/ directory tree at once, including all __pycache__ subdirectories.

### Pitfall 4: docker-compose Volume Reference After Directory Deletion
**What goes wrong:** If docker-compose still mounts `../agents/v3/data:/app/agents/v3/data` but the directory no longer exists, Docker will create an empty directory on the host — not an error, but causes confusion.
**How to avoid:** Remove the volume line from docker-compose in the same commit as deleting the directory.

### Pitfall 5: tests/v3/__pycache__ Contains Compiled References
**What goes wrong:** pytest discovers test modules from cache paths. Not a real problem since the source .py files are also deleted, but confusing if seen in error messages.
**How to avoid:** Delete entire tests/v3/ and tests/agents/v3/ trees including __pycache__.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agents/v3/data/conductor.db` and `agents/v3/data/v3_state.db` — SQLite DBs tracking conductor state and V3 pipeline runs | Deleted as part of `agents/v3/data/` removal — no migration needed, data is V3-only |
| Stored data | `agents/v3/data/test_reports/` — 5 markdown report files from March 2026 | Deleted as part of `agents/v3/data/` removal — historical only, no production value |
| Live service config | `deploy/docker-compose.yml` service `wookiee-oleg` runs `python -m agents.v3` — this is in git, not a UI | Code edit in docker-compose.yml |
| Live service config | `deploy/docker-compose.yml` service `finolog-cron` runs `scripts.run_finolog_weekly` which imports V3 — will break after deletion | Disable container or add comment; fix in Phase 3/4 |
| OS-registered state | No OS-level registrations found (no cron entries outside Docker, no systemd units for V3) | None |
| Secrets/env vars | V3 config reads same env vars as V2 (WB_API_KEY_IP, NOTION_TOKEN, etc.) — no V3-specific env var names | None — env vars are shared, no rename needed |
| Build artifacts | `agents/v3/__pycache__/` and `tests/v3/__pycache__/` with compiled .pyc files | Deleted as part of directory tree removal |

**Nothing found in category:** OS-registered state — verified by checking docker-compose is the only scheduled runner; no systemd, no host cron entries exist in the repo.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — this phase is pure code/file deletion and text edits with no new tools required).

---

## Validation Architecture

`workflow.nyquist_validation` key is absent from `.planning/config.json` — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (inferred from `.pyc` files named `*-pytest-9.0.2.pyc`) |
| Config file | Not found in repo root — likely implicit discovery |
| Quick run command | `cd /path/to/project && python -m pytest tests/ -x -q --ignore=tests/v3 --ignore=tests/agents/v3` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLEAN-01 | agents/v3/ directory does not exist | smoke | `python -c "import os; assert not os.path.exists('agents/v3'), 'V3 dir still exists'"` | Wave 0 (inline check) |
| CLEAN-02 | No langchain imports anywhere except archive | smoke | `python -c "import subprocess, sys; r=subprocess.run(['grep','-r','langchain','--include=*.txt','agents/','services/'],capture_output=True,text=True); assert not r.stdout, r.stdout"` | Wave 0 (inline check) |
| CLEAN-03 | V3 docs deleted | smoke | `python -c "from pathlib import Path; docs=list(Path('docs').rglob('*v3*')); assert not docs, docs"` | Wave 0 (inline check) |
| CLEAN-04 | docker-compose has no V3 references | smoke | `python -c "t=open('deploy/docker-compose.yml').read(); assert 'agents.v3' not in t, 'V3 found in docker-compose'"` | Wave 0 (inline check) |

All four requirements are verifiable with one-liner smoke tests — no test files need to be created. The existing test suite should still pass after cleanup (V3 tests are deleted; V2 tests in `tests/agents/oleg/` are untouched).

### Sampling Rate
- **Per task commit:** Run quick smoke assertions above
- **Per wave merge:** `python -m pytest tests/ -q` (V2 tests only, V3 tests deleted)
- **Phase gate:** Full suite green + all 4 smoke checks pass before `/gsd:verify-work`

### Wave 0 Gaps
None — existing infrastructure covers all phase requirements via smoke checks.

---

## Project Constraints (from CLAUDE.md)

- **DB queries:** only through `shared/data_layer.py` (not relevant for cleanup phase)
- **Config:** only through `shared/config.py` — when moving `get_wb_clients()`, do NOT put it in shared/config.py (it's a client factory, not config); keep it in price_tools.py
- **Documentation:** Update `README.md`, `docs/development-history.md` after structural changes
- **Architecture changes:** Update `docs/agents/README.md`, `docs/index.md`, `docs/architecture.md` when removing V3
- **Git conventions:** commit messages in English, use `refactor/` branch prefix for this type of work
- **Secrets:** never hardcode; env vars only — no action needed here, we're only deleting

---

## Sources

### Primary (HIGH confidence)
- Direct file inspection: `agents/v3/` tree — 80+ files enumerated by `find`
- Direct file inspection: `deploy/docker-compose.yml` — exact service config verified
- Direct grep: `grep -r "agents.v3" --include="*.py"` — all cross-references verified
- Direct grep: `grep -r "langchain|langgraph" --include="requirements*.txt"` — only in agents/v3/requirements.txt
- Direct file read: `agents/v3/config.py` lines 126–136 — `get_wb_clients()` function body verified
- Direct file read: `scripts/run_localization_report.py` — V3 import scope confirmed (delivery only)
- Direct file read: `scripts/run_finolog_weekly.py` — V3 import scope confirmed (config + delivery)

### Secondary (MEDIUM confidence)
- None required — all findings are from direct codebase inspection

---

## Metadata

**Confidence breakdown:**
- File inventory: HIGH — direct filesystem scan
- Cross-reference map: HIGH — direct grep across all .py files
- Architectural decisions (where to move get_wb_clients): HIGH — function is self-contained, only one caller
- Docker-compose fix: HIGH — current config verified, V2 module path confirmed (agents/oleg exists)
- Docs cleanup scope: HIGH — direct directory listing

**Research date:** 2026-03-30
**Valid until:** This phase; no staleness concern (codebase doesn't change until phase executes)
