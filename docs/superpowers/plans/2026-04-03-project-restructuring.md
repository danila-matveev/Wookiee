# Wookiee Hub — Project Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up ~160MB of junk files, remove deprecated code, document every module with README, migrate global skills, and create PROJECT_MAP.md.

**Architecture:** Phased cleanup — first delete junk (safe, no code depends on it), then remove deprecated services (after verifying no imports), then document what remains, then reorganize skills, finally create the project map.

**Tech Stack:** Bash (file operations), Docker Compose (config cleanup), Markdown (documentation)

**Spec:** `docs/superpowers/specs/2026-04-03-project-restructuring-design.md`

---

## Task 1: Delete binary junk files (~160MB)

**Files:**
- Delete: `services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx`
- Delete: `services/logistics_audit/ИП Фисанов. Проверка логистики*.xlsx`
- Delete: `services/wb_localization/Отчеты готовые/` (entire directory)
- Delete: `services/wb_localization/data/reports/*.xlsx`
- Delete: `docs/database/POWERBI DATA SAMPLES/*.xlsx`
- Delete: `docs/archive/agents/vasily/docs/wb_references/*.pdf`
- Delete: `wookiee-hub/mockups/*.png`
- Delete: `wookiee-hub/e2e-*.png`
- Delete: `wookiee-hub/планы/` (entire directory)
- Delete: Root-level `*.png` files
- Delete: `agents/oleg/data/price_report_*.json`
- Keep: `services/logistics_audit/Расчет переплаты по логистике.pdf`
- Keep: `services/logistics_audit/Рекомендации к изменениям в расчете логистики.pdf`

- [ ] **Step 1: Delete Excel files**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee

# Logistics audit — large temp files
rm -f "services/logistics_audit/Аудит логистики 2026-01-01 — 2026-03-23.xlsx"
find services/logistics_audit -maxdepth 1 -name "ИП Фисанов*" -name "*.xlsx" -delete

# Localization reports
rm -rf "services/wb_localization/Отчеты готовые"
rm -f services/wb_localization/data/reports/*.xlsx

# PowerBI samples
rm -f "docs/database/POWERBI DATA SAMPLES"/*.xlsx
```

- [ ] **Step 2: Delete PDF and PNG files**

```bash
# Vasily archived PDFs
rm -f docs/archive/agents/vasily/docs/wb_references/*.pdf

# Hub mockups and e2e screenshots
rm -f wookiee-hub/mockups/*.png
rm -f wookiee-hub/e2e-*.png
rm -rf "wookiee-hub/планы"

# Root-level mockups
find . -maxdepth 1 -name "*.png" -delete
```

- [ ] **Step 3: Delete auto-generated JSON data**

```bash
rm -f agents/oleg/data/price_report_*.json
```

- [ ] **Step 4: Verify deletions**

```bash
# Should show all deleted files
git status --short | grep "^ D\|^D " | head -40
# Should be ~30-50 files deleted
git status --short | grep "^ D\|^D " | wc -l
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "cleanup: remove ~160MB of binary junk files (Excel, PDF, PNG, JSON)

Deleted: logistics audit temp xlsx (148MB), localization reports,
PowerBI samples, hub mockups/e2e screenshots, Oleg price report JSONs,
archived Vasily PDFs.

Kept: logistics audit PDFs (actively used today).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Delete deprecated code and services

**Files:**
- Delete: `services/dashboard_api/` (entire directory)
- Delete: `deploy/Dockerfile.vasily_api`
- Delete: `deploy/Dockerfile.dashboard_api`
- Delete: `deploy/deploy-v3-migration.sh`
- Delete: `agents/oleg/logs/oleg_v2.log`
- Delete: `docs/archive/retired_agents/lyudmila/` (entire directory)
- Delete: `.playwright-mcp/` (entire directory)
- Modify: `deploy/docker-compose.yml` — remove vasily-api and dashboard-api services
- Modify: `shared/data_layer/quality.py` — remove unused `validate_wb_data_quality()`

- [ ] **Step 1: Verify dashboard_api has no dependents**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
# Check no imports from dashboard_api outside its own directory
grep -r "from services.dashboard_api\|import dashboard_api" --include="*.py" . | grep -v "services/dashboard_api/"
# Expected: no output
```

- [ ] **Step 2: Delete deprecated directories and files**

```bash
# Dashboard API — entire service
rm -rf services/dashboard_api

# Deploy artifacts for removed services
rm -f deploy/Dockerfile.vasily_api
rm -f deploy/Dockerfile.dashboard_api
rm -f deploy/deploy-v3-migration.sh

# Oleg legacy log
rm -f agents/oleg/logs/oleg_v2.log

# Retired agents
rm -rf docs/archive/retired_agents/lyudmila

# Playwright auto-generated logs
rm -rf .playwright-mcp
```

- [ ] **Step 3: Remove vasily-api and dashboard-api from docker-compose.yml**

Edit `deploy/docker-compose.yml` — remove the entire `vasily-api:` service block (lines 72-108) and the entire `dashboard-api:` service block (lines 197-234). Keep all other services intact.

The file should have these services remaining:
- `wookiee-oleg`
- `sheets-sync`
- `wb-mcp-ip`
- `wb-mcp-ooo`
- `bitrix24-mcp`
- `knowledge-base`

- [ ] **Step 4: Remove validate_wb_data_quality from quality.py**

The function `validate_wb_data_quality()` in `shared/data_layer/quality.py` has zero imports anywhere in the codebase. Two options:
- If it's the ONLY function in the file: delete the entire file and remove from `__init__.py` exports
- If there are other functions: remove only this function

Check `shared/data_layer/__init__.py` to see if `quality` is exported, and remove the import if so.

- [ ] **Step 5: Validate docker-compose**

```bash
cd deploy && docker compose config --quiet && echo "OK" || echo "INVALID"
cd ..
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "cleanup: remove deprecated services and dead code

Removed: dashboard_api service, vasily_api configs, v3 migration script,
Oleg v2 log, retired Lyudmila agent, Playwright MCP logs.
Cleaned docker-compose.yml (removed vasily-api, dashboard-api).
Removed unused validate_wb_data_quality() from data_layer.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Clean up planning/specs junk

**Files:**
- Delete: `.planning/archive/v1.0/` (entire directory, ~80 files)
- Delete: `.planning/research/` (5 files)
- Delete: `.planning/milestones/v2.0-phases/` (~30 files)
- Delete: `docs/future/agent-ops-dashboard/` (10 files, 3.2MB)
- Delete: `docs/plans/2026-02-25-dashboard-tz.md`
- Delete: `docs/plans/2026-02-25-db-audit-results.md`
- Delete: `docs/plans/2026-04-business-plan.md` (draft, final exists)
- Delete: `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md`
- Delete: `docs/superpowers/specs/2026-03-21-smart-conductor-design.md`
- Delete: `docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md`
- Stage: all `D` status files from `.planning/phases/` (already deleted in working tree)

- [ ] **Step 1: Delete planning archives and research**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee

rm -rf .planning/archive/v1.0
rm -rf .planning/research
rm -rf .planning/milestones/v2.0-phases
```

- [ ] **Step 2: Delete outdated docs**

```bash
rm -rf docs/future/agent-ops-dashboard
rm -f docs/plans/2026-02-25-dashboard-tz.md
rm -f docs/plans/2026-02-25-db-audit-results.md
rm -f docs/plans/2026-04-business-plan.md

rm -f docs/superpowers/specs/2026-03-19-multi-agent-redesign.md
rm -f docs/superpowers/specs/2026-03-21-smart-conductor-design.md
rm -f docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md
```

- [ ] **Step 3: Stage already-deleted .planning/phases files**

```bash
# These files show as "D" in git status — stage the deletions
git add .planning/phases/
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "cleanup: remove planning archives, outdated specs, and draft docs

Removed: .planning/archive/v1.0 (80+ files), .planning/research,
.planning/milestones/v2.0-phases, agent-ops-dashboard future spec,
old dashboard TZ, draft business plan, deprecated design specs
(multi-agent-redesign, smart-conductor, vasily-localization).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Write README for each service

**Files:**
- Create: `services/README.md`
- Create: `services/sheets_sync/README.md`
- Create: `services/wb_localization/README.md`
- Create: `services/knowledge_base/README.md`
- Create: `services/content_kb/README.md`
- Create: `services/product_matrix_api/README.md`
- Create: `services/logistics_audit/README.md`
- Create: `services/observability/README.md`

For each README, the agent must:
1. Read the service's main entry point (e.g. `__main__.py`, `server.py`, or `app.py`)
2. Read its imports to understand dependencies
3. Check if it has FastAPI routes (look for `@app.get`, `@router.get`)
4. Write README following this template:

```markdown
# <Service Name>

## Назначение
<2-3 sentences about what this service does>

## Как запускать
<Command to run locally, Docker container name if applicable>

## Зависимости
- Внутренние: <shared modules used>
- Внешние: <external APIs, databases>

## Endpoints (if FastAPI)
- `GET /endpoint` — description
- `POST /endpoint` — description

## Файлы
- `file.py` — description

## Статус
<Активен / На поддержке / Deprecated>
```

- [ ] **Step 1: Read each service's main files and write services/README.md (overview)**

The overview README lists all services with 1-line descriptions. Read each service directory to get accurate info.

- [ ] **Step 2: Write sheets_sync/README.md**

Read `services/sheets_sync/__main__.py` and `services/sheets_sync/config.py` first.

- [ ] **Step 3: Write wb_localization/README.md**

Read `services/wb_localization/` entry point first.

- [ ] **Step 4: Write knowledge_base/README.md**

Read `services/knowledge_base/` entry point first. Note: FastAPI service on port 8002.

- [ ] **Step 5: Write content_kb/README.md**

Read `services/content_kb/` entry point first. Note: has MCP server integration.

- [ ] **Step 6: Write product_matrix_api/README.md**

Read `services/product_matrix_api/` entry point first. Note: FastAPI with 16+ route modules.

- [ ] **Step 7: Write logistics_audit/README.md**

Read `services/logistics_audit/` entry point first.

- [ ] **Step 8: Write observability/README.md**

Read `services/observability/` entry point first. Note: logs to Supabase PostgreSQL.

- [ ] **Step 9: Commit**

```bash
git add services/README.md services/*/README.md
git commit -m "docs: add README for each service module

Added overview README and individual READMEs for:
sheets_sync, wb_localization, knowledge_base, content_kb,
product_matrix_api, logistics_audit, observability.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Write README for agents, shared, mcp, hub, sku_database, deploy

**Files:**
- Create: `agents/oleg/README.md`
- Create: `shared/README.md`
- Create: `shared/data_layer/README.md`
- Create: `mcp_servers/README.md`
- Modify: `mcp/README.md` (update existing)
- Create: `wookiee-hub/README.md`
- Create: `sku_database/README.md`
- Create: `deploy/README.md`

- [ ] **Step 1: Write agents/oleg/README.md**

Read `agents/oleg/` structure. Key info:
- Cron-based reporting orchestrator (every 30 min, 7-18 MSK)
- Has services/: price_analysis, marketing_tools, agent_tools, price_tools
- Has watchdog/: health monitoring, alerter, diagnostic
- Entry: `scripts/run_report.py`
- Dependencies: shared/data_layer, shared/clients, shared/model_mapping

- [ ] **Step 2: Write shared/README.md and shared/data_layer/README.md**

For data_layer README, list ALL modules:
- `finance.py` — WB/OZON финансовые данные
- `pricing.py` — ценовые данные и маржинальность
- `inventory.py` — остатки, оборачиваемость
- `traffic.py` — трафик и конверсия
- `advertising.py` — рекламные расходы
- `article.py` — артикулы и артикульная аналитика
- `time_series.py` — временные ряды
- `planning.py` — данные для планирования
- `funnel_seo.py` — воронка и SEO
- `pricing_article.py` — ценовая аналитика по артикулам
- `sku_mapping.py` — маппинг SKU
- `quality.py` — (после чистки: может быть удалён или содержать оставшиеся функции)
- `_connection.py` — подключение к БД
- `_sql_fragments.py` — переиспользуемые SQL-фрагменты

Include section: **Известные проблемы (для будущего рефакторинга)**
- 12+ параллельных WB/OZON функций
- 5 дубликатов Supabase connection в sku_mapping.py

- [ ] **Step 3: Write mcp_servers/README.md and update mcp/README.md**

For mcp_servers/:
- `wookiee-data` — финансовая аналитика (wraps agents/oleg/services/agent_tools.py)
- `wookiee-price` — ценовой анализ (wraps agents/oleg/services/price_tools.py)
- `wookiee-marketing` — маркетинг (wraps agents/oleg/services/marketing_tools.py)
- `wookiee-kb` — база знаний (wraps services/knowledge_base/tools.py)
- All run as local MCP stdio servers, configured in `.claude/settings.local.json`

For mcp/:
- Wildberries API (TypeScript, 158 tools, 2 instances: IP + OOO)
- Finolog API (TypeScript, 79 tools, currently disabled)

- [ ] **Step 4: Write wookiee-hub/README.md**

Key info:
- React 19 + TypeScript + Vite + Tailwind + Shadcn/UI
- 22 page components, 16 reusable components
- Standalone SPA, no backend dependency (dashboard_api removed)
- Currently has placeholder pages — will be rebuilt as separate project

- [ ] **Step 5: Write sku_database/README.md**

Key info:
- Supabase PostgreSQL schema and migrations
- `database/schema.sql` — core SKU schema
- `database/triggers.sql` — database triggers
- `scripts/deploy_to_supabase.py` — schema deployment
- `scripts/migrate_data.py` — Excel → PostgreSQL migration
- `scripts/migrations/` — 6 versioned migration files

- [ ] **Step 6: Write deploy/README.md**

Key info:
- Docker Compose с сервисами: wookiee-oleg, sheets-sync, wb-mcp-ip, wb-mcp-ooo, bitrix24-mcp, knowledge-base
- App Server: 77.233.212.61 (Timeweb Cloud), ssh timeweb
- DB Server: 89.23.119.253:6433 (read-only)
- healthcheck.py, healthcheck_agent.py

- [ ] **Step 7: Commit**

```bash
git add agents/oleg/README.md shared/README.md shared/data_layer/README.md \
      mcp_servers/README.md mcp/README.md wookiee-hub/README.md \
      sku_database/README.md deploy/README.md
git commit -m "docs: add README for agents, shared, MCP, hub, SKU DB, deploy

Documented: Oleg agent architecture, shared utilities and data_layer
(with known duplication issues), MCP servers (4 Python + 2 TypeScript),
React hub, SKU database schema, deployment infrastructure.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Migrate global skills to user-level

**Files:**
- Move: `.claude/skills/workflow-diagram/` → `~/.claude/skills/workflow-diagram/`
- Move: `.claude/skills/gws/` → `~/.claude/skills/gws/`
- Move: `.claude/skills/gws-drive/` → `~/.claude/skills/gws-drive/`
- Move: `.claude/skills/gws-sheets/` → `~/.claude/skills/gws-sheets/`
- Move: `.claude/skills/ui-ux-pro-max/` → `~/.claude/skills/ui-ux-pro-max/`
- Move: `.claude/skills/pullrequest/` → `~/.claude/skills/pullrequest/`
- Move: `.claude/commands/workflow-diagram.md` → `~/.claude/commands/workflow-diagram.md`
- Move: `.claude/commands/gws-drive.md` → `~/.claude/commands/gws-drive.md`
- Move: `.claude/commands/gws-sheets.md` → `~/.claude/commands/gws-sheets.md`
- Move: `.claude/commands/pullrequest.md` → `~/.claude/commands/pullrequest.md`

- [ ] **Step 1: Create target directories**

```bash
mkdir -p ~/.claude/skills
mkdir -p ~/.claude/commands
```

- [ ] **Step 2: Copy skills to global level**

Copy first (not move) — so we can verify before deleting from project.

```bash
cp -r .claude/skills/workflow-diagram ~/.claude/skills/
cp -r .claude/skills/gws ~/.claude/skills/
cp -r .claude/skills/gws-drive ~/.claude/skills/
cp -r .claude/skills/gws-sheets ~/.claude/skills/
cp -r .claude/skills/ui-ux-pro-max ~/.claude/skills/
cp -r .claude/skills/pullrequest ~/.claude/skills/
```

- [ ] **Step 3: Copy commands to global level**

```bash
cp .claude/commands/workflow-diagram.md ~/.claude/commands/
cp .claude/commands/gws-drive.md ~/.claude/commands/
cp .claude/commands/gws-sheets.md ~/.claude/commands/
cp .claude/commands/pullrequest.md ~/.claude/commands/
```

- [ ] **Step 4: Verify skills exist at global level**

```bash
ls ~/.claude/skills/
# Expected: workflow-diagram, gws, gws-drive, gws-sheets, ui-ux-pro-max, pullrequest

ls ~/.claude/commands/
# Expected: workflow-diagram.md, gws-drive.md, gws-sheets.md, pullrequest.md
```

- [ ] **Step 5: Remove from project**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee

rm -rf .claude/skills/workflow-diagram
rm -rf .claude/skills/gws
rm -rf .claude/skills/gws-drive
rm -rf .claude/skills/gws-sheets
rm -rf .claude/skills/ui-ux-pro-max
rm -rf .claude/skills/pullrequest

rm -f .claude/commands/workflow-diagram.md
rm -f .claude/commands/gws-drive.md
rm -f .claude/commands/gws-sheets.md
rm -f .claude/commands/pullrequest.md
```

- [ ] **Step 6: Verify remaining project skills are Wookiee-specific**

```bash
ls .claude/skills/
# Expected: content-search, financial-overview, monthly-plan (only 3)

ls .claude/commands/
# Expected: daily-report.md, marketing-report.md, period-report.md, update-docs.md, weekly-report.md (only 5)
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: migrate 6 global skills and 4 commands to user-level

Moved to ~/.claude/skills/: workflow-diagram, gws, gws-drive, gws-sheets,
ui-ux-pro-max, pullrequest.
Moved to ~/.claude/commands/: workflow-diagram, gws-drive, gws-sheets, pullrequest.

Remaining in project: financial-overview, monthly-plan, content-search (Wookiee-specific).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Create PROJECT_MAP.md

**Files:**
- Create: `PROJECT_MAP.md` (root level)

- [ ] **Step 1: Read current state after all cleanups**

Before writing the map, verify the current directory structure:
```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
find . -maxdepth 2 -type d \
  -not -path "./.git*" \
  -not -path "./.venv*" \
  -not -path "./node_modules*" \
  -not -path "./__pycache__*" \
  -not -path "./wookiee-hub/node_modules*" | sort
```

- [ ] **Step 2: Write PROJECT_MAP.md**

The PROJECT_MAP.md must contain:

1. **Обзор проекта** — 2-3 sentences about Wookiee Hub
2. **Модули** — table with every top-level directory, 1-line description, status
3. **Что деплоится на сервер** — list of Docker containers from docker-compose.yml
4. **MCP серверы** — Python (local, 4 servers) + TypeScript (external, 2 servers)
5. **Скиллы и команды** — remaining Wookiee-specific skills + commands
6. **Взаимосвязи** — text diagram showing:
   ```
   Oleg Agent (cron) ──→ shared/data_layer ──→ PostgreSQL DB
       │                      ↑
       │                      │
   MCP Servers ───────────────┘
       ↑
   Claude Code Skills (financial-overview, monthly-plan)
       ↑
   Claude Commands (/daily-report, /weekly-report, etc.)
   ```
7. **Сервисы** — brief list with links to READMEs
8. **Отложенные задачи** — data_layer refactoring, observability rename, repo split

- [ ] **Step 3: Commit**

```bash
git add PROJECT_MAP.md
git commit -m "docs: add PROJECT_MAP.md — complete project navigation guide

Overview of all modules, deployment, MCP servers, skills, commands,
inter-module dependencies, and deferred tasks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Final verification

- [ ] **Step 1: Verify git status is clean**

```bash
git status
# Expected: nothing to commit, working tree clean
```

- [ ] **Step 2: Verify all READMEs exist**

```bash
for f in \
  services/README.md \
  services/sheets_sync/README.md \
  services/wb_localization/README.md \
  services/knowledge_base/README.md \
  services/content_kb/README.md \
  services/product_matrix_api/README.md \
  services/logistics_audit/README.md \
  services/observability/README.md \
  agents/oleg/README.md \
  shared/README.md \
  shared/data_layer/README.md \
  mcp_servers/README.md \
  wookiee-hub/README.md \
  sku_database/README.md \
  deploy/README.md \
  PROJECT_MAP.md; do
  [ -f "$f" ] && echo "OK: $f" || echo "MISSING: $f"
done
```

- [ ] **Step 3: Verify docker-compose is valid**

```bash
cd deploy && docker compose config --quiet && echo "docker-compose: OK" || echo "docker-compose: INVALID"
cd ..
```

- [ ] **Step 4: Verify global skills exist**

```bash
for s in workflow-diagram gws gws-drive gws-sheets ui-ux-pro-max pullrequest; do
  [ -d "$HOME/.claude/skills/$s" ] && echo "OK: $s" || echo "MISSING: $s"
done
```

- [ ] **Step 5: Verify only Wookiee skills remain in project**

```bash
ls .claude/skills/
# Expected: content-search, financial-overview, monthly-plan
ls .claude/commands/
# Expected: daily-report.md, marketing-report.md, period-report.md, update-docs.md, weekly-report.md
```

- [ ] **Step 6: Report summary**

Print summary of what was done:
- Files deleted (count)
- READMEs created (count)
- Skills migrated (count)
- Docker services removed (count)
- Total git commits in this session
