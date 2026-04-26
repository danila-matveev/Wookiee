# Wookiee Hub — Project Cleanup v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove ~200MB of junk files, extract Oleg Agent knowledge into skills, clean Docker config, add .gitignore rules to prevent future junk.

**Architecture:** Sequential cleanup — delete binaries first (safest), then deprecated code, then extract Oleg services for MCP, then archive Oleg, then Docker cleanup, then .gitignore.

**Spec:** `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md`

---

## Task 1: Delete root-level junk files

**Files to delete:**
- `2026_Договор купли-продажи Familia -Чернецкая.docx`
- `Экосбор_ИП_Медведева_2025.xlsx`
- `Экосбор_ООО_Вуки_2025.xlsx`
- `Запрос_сведений_для_подготовки_отчетности_по_экологическому_сбору.xlsx`
- `Условия поставки Покупателя (статус РЦ).pdf`
- `agent-dashboard-full.png`
- `mockup-full-page.png`
- `CleanShot 2026-03-28 at 15.28.34@2x.png`
- `scripts.txt`

- [ ] **Step 1: Delete root junk**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
rm -f "2026_Договор купли-продажи Familia -Чернецкая.docx"
rm -f "Экосбор_ИП_Медведева_2025.xlsx"
rm -f "Экосбор_ООО_Вуки_2025.xlsx"
rm -f "Запрос_сведений_для_подготовки_отчетности_по_экологическому_сбору.xlsx"
rm -f "Условия поставки Покупателя (статус РЦ).pdf"
rm -f agent-dashboard-full.png mockup-full-page.png
rm -f "CleanShot 2026-03-28 at 15.28.34@2x.png"
rm -f scripts.txt
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "cleanup: remove root-level business docs, mockups, shell history

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Delete binary files from services and docs

**Delete from logistics_audit (keep finals):**
- DELETE: `Аудит логистики 2026-01-01 — 2026-03-23.xlsx` (124M)
- DELETE: `ООО_Вуки_проверка_логистики_05_01_01_02.xlsx` (55M)
- DELETE: `ООО Wookiee — Перерасчёт логистики (v2).xlsx` (1.3M, draft)
- DELETE: `Расчет переплаты по логистике.pdf` (634K)
- DELETE: `Рекомендации к изменениям в расчете логистики.pdf` (342K)
- KEEP: `ООО Wookiee — Перерасчёт логистики (v2-final).xlsx`
- KEEP: `ИП Фисанов. Проверка логистики...Итоговый.xlsx`
- KEEP: `ИП Фисанов — Исправленный расчёт логистики (v2).xlsx`
- KEEP: `Тарифы на логискику.xlsx`

**Delete all from other services/docs:**
- `services/wb_localization/data/reports/*.xlsx`
- `services/wb_localization/Отчеты готовые/` (entire dir)
- `docs/database/POWERBI DATA SAMPLES/*.xlsx`
- `docs/archive/agents/vasily/docs/wb_references/` (PDFs + PNGs)
- `docs/future/agent-ops-dashboard/` (entire dir, 3.2M)
- `wookiee-hub/mockups/` (entire dir)
- `wookiee-hub/e2e-*.png`
- `wookiee-hub/планы/` (entire dir)

- [ ] **Step 1: Delete logistics audit drafts**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
rm -f "services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx"
rm -f "services/logistics_audit/ООО_Вуки_проверка_логистики_05_01_01_02.xlsx"
rm -f "services/logistics_audit/ООО Wookiee — Перерасчёт логистики (v2).xlsx"
rm -f "services/logistics_audit/Расчет переплаты по логистике.pdf"
rm -f "services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf"
```

- [ ] **Step 2: Delete localization, docs, hub binaries**

```bash
rm -f services/wb_localization/data/reports/*.xlsx
rm -rf "services/wb_localization/Отчеты готовые"
rm -f "docs/database/POWERBI DATA SAMPLES"/*.xlsx
rm -rf docs/archive/agents/vasily/docs/wb_references
rm -rf docs/future/agent-ops-dashboard
rm -rf wookiee-hub/mockups
rm -f wookiee-hub/e2e-*.png
rm -rf "wookiee-hub/планы"
```

- [ ] **Step 3: Delete auto-generated JSON data**

```bash
rm -f agents/oleg/data/price_report_*.json
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "cleanup: remove ~200MB binary files (xlsx, pdf, png, json)

Kept: logistics audit finals (v2-final, ИП Итоговый, тарифы).
Removed: draft audits, localization reports, PowerBI samples,
Vasily references, hub mockups, Oleg price report JSONs.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Delete deprecated code and planning junk

**Files to delete:**
- `services/dashboard_api/` (entire)
- `deploy/Dockerfile.vasily_api`
- `deploy/Dockerfile.dashboard_api`
- `deploy/deploy-v3-migration.sh`
- `docs/archive/retired_agents/lyudmila/` (3.2M)
- `.playwright-mcp/` (30+ files)
- `.superpowers/brainstorm/` (cached session)
- `.planning/archive/v1.0/` (80+ files)
- `.planning/research/` (5 files)
- `.planning/milestones/v2.0-phases/` (~30 files)
- `docs/plans/2026-02-25-dashboard-tz.md`
- `docs/plans/2026-02-25-db-audit-results.md`
- `docs/plans/2026-04-business-plan.md`
- `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md`
- `docs/superpowers/specs/2026-03-21-smart-conductor-design.md`
- `docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md`
- `docs/superpowers/specs/2026-04-03-project-restructuring-design.md` (superseded by v2)

- [ ] **Step 1: Verify dashboard_api has no dependents**

```bash
grep -r "from services.dashboard_api\|import dashboard_api" --include="*.py" . | grep -v "services/dashboard_api/"
# Expected: no output
```

- [ ] **Step 2: Delete deprecated code**

```bash
rm -rf services/dashboard_api
rm -f deploy/Dockerfile.vasily_api deploy/Dockerfile.dashboard_api deploy/deploy-v3-migration.sh
rm -rf docs/archive/retired_agents/lyudmila
rm -rf .playwright-mcp
rm -rf .superpowers/brainstorm
```

- [ ] **Step 3: Delete planning junk**

```bash
rm -rf .planning/archive/v1.0
rm -rf .planning/research
rm -rf .planning/milestones/v2.0-phases
rm -f docs/plans/2026-02-25-dashboard-tz.md
rm -f docs/plans/2026-02-25-db-audit-results.md
rm -f docs/plans/2026-04-business-plan.md
rm -f docs/superpowers/specs/2026-03-19-multi-agent-redesign.md
rm -f docs/superpowers/specs/2026-03-21-smart-conductor-design.md
rm -f docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md
rm -f docs/superpowers/specs/2026-04-03-project-restructuring-design.md
```

- [ ] **Step 4: Stage already-deleted files from git status**

```bash
git add .planning/phases/ 2>/dev/null || true
```

- [ ] **Step 5: Remove dead code**

Read `shared/data_layer/quality.py`. If `validate_wb_data_quality()` is the only function, delete the file and remove from `shared/data_layer/__init__.py`. Otherwise remove only the function.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "cleanup: remove deprecated services, planning archives, dead code

Removed: dashboard_api, Dockerfile.vasily_api, Dockerfile.dashboard_api,
v3 migration script, Lyudmila agent, Playwright logs, brainstorm cache,
planning v1.0/v2.0 archives, outdated specs, dead validate_wb_data_quality().

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Extract Oleg services → shared/services/

**Critical:** 3 MCP servers depend on agents/oleg/services/. Must extract before deleting Oleg.

**Move:**
- `agents/oleg/services/agent_tools.py` → `shared/services/agent_tools.py`
- `agents/oleg/services/price_tools.py` → `shared/services/price_tools.py`
- `agents/oleg/services/marketing_tools.py` → `shared/services/marketing_tools.py`
- `agents/oleg/services/funnel_tools.py` → `shared/services/funnel_tools.py`

- [ ] **Step 1: Create shared/services/ and move files**

```bash
mkdir -p shared/services
cp agents/oleg/services/agent_tools.py shared/services/
cp agents/oleg/services/price_tools.py shared/services/
cp agents/oleg/services/marketing_tools.py shared/services/
cp agents/oleg/services/funnel_tools.py shared/services/
touch shared/services/__init__.py
```

- [ ] **Step 2: Check what each tool file imports from agents/oleg/**

```bash
grep -n "from agents.oleg\|import agents.oleg" shared/services/*.py
```

Fix any internal imports to point to new locations or to shared/.

- [ ] **Step 3: Update MCP server imports**

Check and update import paths in:
- `mcp_servers/wookiee_data/server.py`
- `mcp_servers/wookiee_price/server.py`
- `mcp_servers/wookiee_marketing/server.py`

Change `from agents.oleg.services.X import Y` → `from shared.services.X import Y`

- [ ] **Step 4: Verify MCP servers still importable**

```bash
python -c "from shared.services.agent_tools import *; print('agent_tools OK')"
python -c "from shared.services.price_tools import *; print('price_tools OK')"
python -c "from shared.services.marketing_tools import *; print('marketing_tools OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: extract Oleg tool services to shared/services/

Moved agent_tools, price_tools, marketing_tools, funnel_tools
from agents/oleg/services/ to shared/services/.
Updated MCP server imports.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Extract Oleg knowledge + archive agent

- [ ] **Step 1: Read Oleg analytical prompts and playbooks**

Read these files to extract analytics knowledge:
- `agents/oleg/playbooks/` — all .md files
- `agents/oleg/agents/` — agent role definitions (Reporter, Marketer, etc.)
- `agents/oleg/orchestrator/` — decision logic
- `agents/oleg/pipeline/` — report generation pipeline

Extract: analytical rules, WB/OZON domain knowledge, report structure patterns, validation logic.

- [ ] **Step 2: Create architecture doc**

Write `docs/archive/oleg-v2-architecture.md` containing:
- Overview of what Oleg was (5 roles, ReAct loop, circuit breaker)
- Key analytical rules extracted from prompts
- Report generation pipeline description
- Why it was retired (replaced by Claude Code skills)
- What knowledge was moved to which skills

- [ ] **Step 3: Delete Oleg agent (except services already moved)**

```bash
# Keep only the architecture doc reference
rm -rf agents/oleg/orchestrator
rm -rf agents/oleg/executor
rm -rf agents/oleg/pipeline
rm -rf agents/oleg/storage
rm -rf agents/oleg/anomaly
rm -rf agents/oleg/playbooks
rm -rf agents/oleg/watchdog
rm -rf agents/oleg/agents
rm -rf agents/oleg/data
rm -rf agents/oleg/logs
rm -rf agents/oleg/services  # Already moved to shared/services/
```

- [ ] **Step 4: Create agents/oleg/README.md**

```markdown
# Oleg Agent v2 (Archived)

Oleg was the automated reporting orchestrator for Wookiee (cron, 7-18 MSK).
Replaced by Claude Code skills (financial-overview, monthly-plan, analytics-report, etc.)

## Architecture documentation
See: [docs/archive/oleg-v2-architecture.md](../../docs/archive/oleg-v2-architecture.md)

## Extracted services
Tool services moved to `shared/services/` (used by MCP servers).
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "archive: document and remove Oleg Agent v2

Created docs/archive/oleg-v2-architecture.md with extracted knowledge.
Removed agent code (orchestrator, executor, pipeline, watchdog, etc.).
Services preserved in shared/services/ for MCP server compatibility.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Clean Docker config

- [ ] **Step 1: Remove vasily-api from docker-compose.yml**

Edit `deploy/docker-compose.yml` — remove the entire `vasily-api:` service block (lines 72-108).

- [ ] **Step 2: Remove dashboard-api from docker-compose.yml**

Remove the entire `dashboard-api:` service block (lines 197-234).

- [ ] **Step 3: Update wookiee-oleg volumes if needed**

Check if any volumes reference agents/oleg/services. If so, update to shared/services.

- [ ] **Step 4: Validate**

```bash
cd deploy && docker compose config --quiet && echo "OK" || echo "INVALID"
cd ..
```

- [ ] **Step 5: Commit**

```bash
git add deploy/docker-compose.yml && git commit -m "cleanup: remove vasily-api and dashboard-api from docker-compose

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Add .gitignore rules to prevent future junk

- [ ] **Step 1: Add rules to .gitignore**

Append to `.gitignore`:

```gitignore
# === Business documents — use Google Drive, not git ===
*.xlsx
*.docx
*.pdf
# Exceptions: logistics audit finals
!services/logistics_audit/*final*.xlsx
!services/logistics_audit/*Итоговый*.xlsx
!services/logistics_audit/*Тарифы*.xlsx
!services/logistics_audit/*v2*.xlsx

# === Screenshots and mockups ===
*.png
*.jpg
*.jpeg
# Exception: hub public assets
!wookiee-hub/public/**/*.png
!wookiee-hub/src/assets/**/*.png

# === Generated/temporary data ===
agents/*/data/
agents/*/logs/
.playwright-mcp/
.superpowers/brainstorm/
scripts.txt
```

- [ ] **Step 2: Verify kept files aren't gitignored**

```bash
git check-ignore services/logistics_audit/*final*.xlsx && echo "BUG: final ignored" || echo "OK: final not ignored"
git check-ignore services/logistics_audit/*Итоговый*.xlsx && echo "BUG: itog ignored" || echo "OK: itog not ignored"
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore && git commit -m "chore: add .gitignore rules to prevent binary junk accumulation

Block xlsx/docx/pdf/png by default, with exceptions for logistics
audit finals and hub public assets. Block agent data/logs dirs.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Final verification

- [ ] **Step 1: Verify no binary junk remains**

```bash
find . -type f \( -name "*.xlsx" -o -name "*.pdf" -o -name "*.docx" -o -name "*.png" \) \
  -not -path "./.git/*" -not -path "./.venv/*" -not -path "*/node_modules/*" \
  -not -path "./.agents/*" -not -path "./.claude/skills/ui-ux-pro-max/*" | sort
# Expected: only logistics audit finals + kept files
```

- [ ] **Step 2: Verify MCP servers work**

```bash
python -c "from shared.services.agent_tools import *; print('OK')"
```

- [ ] **Step 3: Verify docker-compose valid**

```bash
cd deploy && docker compose config --quiet && echo "OK"
cd ..
```

- [ ] **Step 4: Print summary**

```bash
echo "=== Cleanup Summary ==="
git log --oneline HEAD~7..HEAD
echo ""
echo "Commits: $(git log --oneline HEAD~7..HEAD | wc -l)"
echo "Remaining binary files:"
find . -type f \( -name "*.xlsx" -o -name "*.pdf" \) -not -path "./.git/*" -not -path "./.venv/*" | wc -l
```
