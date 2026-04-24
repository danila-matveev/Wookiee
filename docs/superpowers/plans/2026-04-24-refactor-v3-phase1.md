# Refactor v3 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Привести Wookiee-репозиторий в состояние, пригодное для коллективной работы — удалить Oleg/мусор, обрезать Hub до 2 модулей, закоммитить активный untracked, унифицировать документацию, переключить workflow на PR+auto-merge.

**Architecture:** Stage A (4 параллельных audit-субагента, read-only) → Stage A.5 (orchestrator-critic → refactor-manifest.md → user approval) → Stage B (7 последовательных PR через `/pullrequest`, auto-merge) → Stage C (verifier → опциональный PR #8 fixes).

**Tech Stack:** Git + GitHub CLI (`gh`), Python 3.11 (`pytest`, `ruff`), Node 20 (`npm` в wookiee-hub), Claude subagents через Agent tool (`general-purpose` или `Explore` subagent_type), `superpowers:dispatching-parallel-agents`, `/pullrequest` skill (Codex + Copilot review), Supabase CLI (если понадобится для `tools`/`tool_runs` правок).

**Source spec:** `docs/superpowers/specs/2026-04-24-refactor-v3-design.md`

---

## File Structure

Этот план не производит типичный код — он оркестрирует рефакторинг. Артефакты плана:

**Создаём:**
- `.planning/refactor-audit/code-audit.md` — отчёт audit-code
- `.planning/refactor-audit/docs-audit.md` — отчёт audit-docs
- `.planning/refactor-audit/hub-audit.md` — отчёт audit-hub
- `.planning/refactor-audit/infra-audit.md` — отчёт audit-infra
- `.planning/refactor-manifest.md` — финальный план от orchestrator
- `.planning/refactor-verification.md` — отчёт verifier
- `.github/pull_request_template.md` — шаблон PR
- `.claude/skills/hygiene/README.md` — placeholder для Фазы 2
- `.claude/hygiene-config.yaml` — placeholder конфиг
- `ONBOARDING.md` — новый файл для коллег
- `docs/skills/<name>.md` — по одному на каждый активный скилл
- `services/<module>/README.md` — по одному на каждый активный сервис
- `agents/README.md` — scaffold-описание
- `docs/archive/oleg-v2-architecture.md` — архитектурный конспект удаляемого Oleg

**Модифицируем:**
- `.gitignore` — hardening
- `.mcp.json` — удаление локальных MCP entries
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md` — обновление под новый workflow
- `docs/index.md`, `docs/architecture.md` — актуальная карта
- `wookiee-hub/src/router.tsx`, `App.tsx`, меню — под 2 модуля
- docker-compose.yml — удаление сервисов

**Удаляем (через git rm):**
- `agents/oleg/`, `agents/finolog_categorizer/`
- `mcp_servers/` (целиком)
- `services/product_matrix_api/`, опционально `services/dashboard_api/`, `services/knowledge_base/`, `services/ozon_delivery/` (orchestrator решит)
- `wookiee-hub/src/pages/*` — 13+ файлов (точный список в manifest)
- Бинарные файлы по cleanup-v2 + дельта

---

## Pre-flight

### Task 1: Проверить branch protection на GitHub main

**Files:**
- Read-only: GitHub API через `gh`

- [ ] **Step 1: Получить текущие branch protection settings**

Run:
```bash
gh api "repos/:owner/:repo/branches/main/protection" 2>&1 | head -50
```

Expected: JSON с текущими настройками защиты, либо ошибка "Branch not protected".

- [ ] **Step 2: Зафиксировать результат и принять решение**

Если защита отсутствует или не соответствует spec §5.1 (запрет прямых push, auto-merge, delete head branches):
  - Вариант A: Настроить программно (см. Step 3)
  - Вариант B: Попросить пользователя настроить через GitHub web UI

- [ ] **Step 3: Настроить branch protection (если решено настроить программно)**

Run:
```bash
gh api --method PUT "repos/:owner/:repo/branches/main/protection" \
  --input - <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false,
  "required_conversation_resolution": false
}
EOF
```

Expected: JSON response без ошибок, `enabled: true`.

- [ ] **Step 4: Включить auto-merge и delete head branches на репозитории**

Run:
```bash
gh api --method PATCH "repos/:owner/:repo" \
  -f allow_auto_merge=true \
  -f delete_branch_on_merge=true
```

Expected: JSON с обновлёнными полями `allow_auto_merge: true`, `delete_branch_on_merge: true`.

- [ ] **Step 5: Commit этого плана если он ещё не в git**

Проверь `git status`. План уже был создан в предыдущем шаге brainstorm — коммит не требуется, если он уже в main. Если нет:

```bash
git add docs/superpowers/plans/2026-04-24-refactor-v3-phase1.md
git commit -m "docs(plan): add refactor-v3 phase 1 implementation plan

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Создать директорию для audit-отчётов

**Files:**
- Create: `.planning/refactor-audit/.gitkeep`

- [ ] **Step 1: Создать директорию**

Run:
```bash
mkdir -p .planning/refactor-audit && touch .planning/refactor-audit/.gitkeep
```

Expected: Директория создана, файл `.gitkeep` пустой.

- [ ] **Step 2: Commit**

```bash
git add .planning/refactor-audit/.gitkeep
git commit -m "chore: prepare refactor-audit directory

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Stage A — Parallel Audit

### Task 3: Диспатч 4 audit-субагентов параллельно

**Files:**
- Output: `.planning/refactor-audit/code-audit.md`, `docs-audit.md`, `hub-audit.md`, `infra-audit.md`

- [ ] **Step 1: Подготовить общий контекст для всех 4 субагентов**

В одном сообщении вызови 4 Agent tool'а параллельно (subagent_type = `general-purpose`). Каждому передай:
- Путь к spec: `docs/superpowers/specs/2026-04-24-refactor-v3-design.md`
- Путь к cleanup-v2: `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md`
- Зону ответственности (см. Step 2-5)
- Строгую инструкцию: **только чтение, только запись в `.planning/refactor-audit/<file>.md`, никаких правок кода/конфига/файлов проекта**

- [ ] **Step 2: Agent #1 — `audit-code`**

Prompt:
```
You are audit-code, a read-only auditor for the Wookiee repo refactor.

GOAL: Write a file-by-file audit of the Python backend — which files are dead code,
orphaned, duplicated, and which are actively used.

ZONES: agents/, services/, scripts/, shared/, mcp_servers/

READ FIRST:
- docs/superpowers/specs/2026-04-24-refactor-v3-design.md (current spec)
- docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md (cleanup-v2)

RULES:
- READ-ONLY. Do not modify any project files. Do not run any command that mutates state.
- You may run: find, grep/rg, cat, python -c "import ast; ...", git log.
- For each file/directory in your zones, decide: DELETE / KEEP / MERGE / RENAME / FLAG.
- For each DELETE, provide evidence: grep shows 0 imports from remaining code.
- For each FLAG, state what question needs the orchestrator's or user's answer.

DELIVERABLE: Write to .planning/refactor-audit/code-audit.md with sections:
1. Summary (counts by verdict)
2. DELETE list (path | reason | grep evidence)
3. KEEP list (path | purpose | consumers)
4. MERGE/RENAME suggestions (from -> to | reason)
5. FLAG list (question | files involved)
6. Special checks:
   - mcp_servers/ — confirm none of the 4 local MCP servers are used anywhere
     besides the removed Oleg; check if they are referenced outside the repo
     (hard to verify — flag)
   - agents/oleg/services/*_tools.py — grep all references outside agents/oleg
     and outside mcp_servers/ to decide if extraction to shared/services/ is needed
   - scripts/ — for each script, find which skill/service calls it; orphans
     (called nowhere) → DELETE candidates
   - services/product_matrix_api/, services/dashboard_api/, services/knowledge_base/,
     services/ozon_delivery/ — confirm active/legacy status

Report total token/time budget: keep under 50k tokens.
```

- [ ] **Step 3: Agent #2 — `audit-docs`**

Prompt:
```
You are audit-docs, a read-only auditor for the Wookiee repo refactor.

GOAL: Audit documentation for staleness, duplicates, dead links, and fit with
the new colleague-ready structure.

ZONES: docs/, root-level *.md (README, AGENTS, CLAUDE, CONTRIBUTING, SECURITY),
.planning/ (all subdirs), .superpowers/

READ FIRST:
- docs/superpowers/specs/2026-04-24-refactor-v3-design.md (current spec, focus on §6)
- docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md
- docs/index.md (current map)

RULES:
- READ-ONLY.
- For each .md file, decide: KEEP / UPDATE / ARCHIVE / DELETE.
- For each UPDATE, list specific changes needed (e.g., "remove Oleg references",
  "update infrastructure diagram").
- Check for broken internal links (grep [text](path) patterns, verify path exists).
- Check for Oleg/Lyudmila/Vasily mentions as ACTIVE (should be archived).

DELIVERABLE: Write to .planning/refactor-audit/docs-audit.md with sections:
1. Summary (counts)
2. Target docs/ structure diff vs current (from spec §6.1)
3. DELETE list (path | reason)
4. ARCHIVE list (path -> docs/archive/... | reason)
5. UPDATE list (path | what to change)
6. CREATE list (new docs needed per spec §6 — ONBOARDING.md, docs/skills/*.md,
   module READMEs)
7. Broken links report

Report budget: under 40k tokens.
```

- [ ] **Step 4: Agent #3 — `audit-hub`**

Prompt:
```
You are audit-hub, a read-only auditor for the Wookiee Hub refactor.

GOAL: Build a dependency graph of wookiee-hub/src/ and produce a precise list
of files to delete/keep when trimming to 2 modules: "Комьюнити" and "Агенты".

TARGET:
- Комьюнити: Отзывы, Вопросы, Ответы, Аналитика (4 subsections)
- Агенты: Табло скиллов, История запусков (2 subsections)

ZONES: wookiee-hub/src/ (pages, components, stores, hooks, lib, data, types, config)

READ FIRST:
- docs/superpowers/specs/2026-04-24-refactor-v3-design.md §3, §4.1
- wookiee-hub/src/router.tsx, App.tsx, components/layout/*
- all src/pages/*.tsx

RULES:
- READ-ONLY.
- Build dependency graph: for each page file, list imports (components, stores,
  hooks, lib functions). Then for each component/store/hook/lib, list its consumers.
- Identify "kept" pages: current pages that serve the 2 target modules
  (candidates: comms-reviews.tsx, comms-analytics.tsx).
- Identify "kept components/stores": transitive closure from kept pages.
- Identify "orphaned after trim": everything not in transitive closure.
- Propose: should kept pages be renamed to community/*, agents/*, or stay as
  comms-*/ new agents.tsx? Give a recommendation.
- Flag: what needs to be newly created (pages/components for Агенты module,
  since it doesn't exist today).

DELIVERABLE: Write to .planning/refactor-audit/hub-audit.md:
1. Dependency graph summary
2. KEEP list (files | reason | which module)
3. DELETE list (files | reason)
4. CREATE list (new files needed for Агенты module)
5. RENAME recommendations (old path -> new path)
6. Router/App/menu changes needed
7. Missing pieces (e.g., "need supabase-js client for tools/tool_runs")

Report budget: under 50k tokens.
```

- [ ] **Step 5: Agent #4 — `audit-infra`**

Prompt:
```
You are audit-infra, a read-only auditor for the Wookiee infrastructure config.

GOAL: Audit non-code config for staleness and prepare gitignore hardening rules.

ZONES: deploy/, docker-compose*.yml, .claude/, .env.example, .gitignore,
pyproject.toml, Makefile, setup_bot.sh, .mcp.json, .github/, .agents/, .kiro/,
.superpowers/, .playwright-mcp/

READ FIRST:
- docs/superpowers/specs/2026-04-24-refactor-v3-design.md §5, §6
- docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md §2.5, §3
- current .gitignore, .mcp.json, docker-compose.yml

RULES:
- READ-ONLY.
- For docker-compose.yml: list services to remove (vasily-api, dashboard-api,
  any referencing removed code).
- For .mcp.json: list local MCP entries to remove (wookiee-data, wookiee-kb,
  wookiee-marketing, wookiee-price), preserve wildberries-ip/ooo.
- For .gitignore: propose additions to block future garbage
  (*.xlsx not in whitelist, *.wmv, *.mov, iCloud dupes " 2.", __pycache__,
  .pytest_cache, etc.). Include whitelist exceptions for files we keep
  (e.g., logistics_audit final xlsx).
- For .claude/: audit skills (which are active from user's skills list, which
  are orphaned), commands, settings. Reference Supabase `tools` table.
- For deploy/Dockerfiles: list those for removed services.
- For .github/: check if workflow files exist and are relevant.

DELIVERABLE: Write to .planning/refactor-audit/infra-audit.md:
1. Summary
2. docker-compose.yml changes (services to remove, services to update)
3. .mcp.json changes (entries to remove)
4. .gitignore additions (rules to add with whitelist exceptions)
5. .claude/ audit (active vs orphan skills, settings to update)
6. deploy/ audit (Dockerfiles to delete, scripts to update)
7. Other (pyproject, Makefile, .env.example — stale entries)

Report budget: under 40k tokens.
```

- [ ] **Step 6: Дождаться завершения всех 4 агентов**

Все 4 пишут файлы в `.planning/refactor-audit/`. Проверить что все 4 файла созданы:

Run:
```bash
ls -la .planning/refactor-audit/
```

Expected: `code-audit.md`, `docs-audit.md`, `hub-audit.md`, `infra-audit.md` присутствуют, размер >10KB каждый.

- [ ] **Step 7: Commit audit reports**

```bash
git add .planning/refactor-audit/
git commit -m "chore: add Stage A audit reports (code/docs/hub/infra)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Stage A.5 — Orchestrator

### Task 4: Диспатч refactor-orchestrator

**Files:**
- Input: `.planning/refactor-audit/*.md`, оба spec'а
- Output: `.planning/refactor-manifest.md`

- [ ] **Step 1: Запустить orchestrator**

Запустить Agent tool (`general-purpose`) с полным промптом:

```
You are refactor-orchestrator. Your role is to critically review the 4 audit reports,
cross-check their findings, and produce a final refactor manifest.

READ:
1. docs/superpowers/specs/2026-04-24-refactor-v3-design.md (full spec)
2. docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md (cleanup-v2)
3. .planning/refactor-audit/code-audit.md
4. .planning/refactor-audit/docs-audit.md
5. .planning/refactor-audit/hub-audit.md
6. .planning/refactor-audit/infra-audit.md

TASKS:
1. CRITIQUE: Find contradictions between reports (e.g., code-audit says delete X,
   hub-audit says keep X). Find gaps (files not covered). Find overly aggressive
   or overly timid decisions.

2. CROSS-CHECK: For every DELETE candidate across all 4 reports, independently
   grep for imports/references across ALL zones (not just the zone that flagged it).
   Use: rg "filename_without_ext|module_path" --type py --type md --type json
   --type yaml --type ts --type tsx -l
   Document findings.

3. MIRROR LIST: Files/dirs not covered by any audit zone (check repo root, hidden
   dirs). Decide verdict for each.

4. RISK CHECK: Each DELETE must have:
   - Evidence of no external use
   - Rollback note (it's git rm, so revert PR recovers it — but note if there are
     data files that would be lost)

5. RESOLVE OPEN QUESTIONS (from spec §10):
   (a) Final name for services/observability/ (candidates: tool_telemetry/,
       tool_metrics/, run_logger/). Choose one with reasoning.
   (b) services/dashboard_api/ — based on audit-hub's module «Агенты» design,
       is it needed? Verdict: KEEP (and how it's used) or DELETE.
   (c) services/knowledge_base/, services/ozon_delivery/ — based on audit-code,
       KEEP or DELETE.
   (d) docs/future/agent-ops-dashboard/ — ARCHIVE or DELETE.
   (e) Does agents/oleg/services/*_tools.py need extraction to shared/services/?
       Check: are they imported outside agents/oleg/ and mcp_servers/?
   (f) Hub module structure: tabs inside single page vs routed sub-pages for
       4+2 sections? Pick one based on audit-hub recommendation.

6. PRODUCE MANIFEST at .planning/refactor-manifest.md with:
   - Executive Summary (total files changed, counts by verdict, risks)
   - Resolved Open Questions (with your reasoning)
   - Per-PR breakdown (7 PRs from spec §2.3) — for each PR:
     * Branch name
     * Files to delete (exact paths)
     * Files to create (exact paths + one-line purpose)
     * Files to modify (exact paths + description of change)
     * Dependencies on prior PRs
     * Acceptance check (what command verifies success)
   - Flagged items (things that genuinely need user approval — keep minimal)
   - Changelog summary for each PR (1-2 sentences per PR)

RULES:
- READ-ONLY for project files. You may Write only to .planning/refactor-manifest.md.
- Use Bash for grep/find, not for mutations.
- If something is unclear, flag it — don't guess.
- Keep manifest under 30 pages (it's a working document).

Token budget: under 120k tokens (this is a large cross-check).
```

- [ ] **Step 2: Дождаться завершения и проверить manifest**

Run:
```bash
ls -la .planning/refactor-manifest.md && wc -l .planning/refactor-manifest.md
```

Expected: Файл существует, 300-800 строк.

- [ ] **Step 3: Sanity-check manifest вручную**

Прочитать manifest целиком. Проверить:
- Все 6 open questions разрешены с обоснованием
- Для каждого PR есть список files + acceptance check
- Нет «TBD»/«TODO»/«implement later»
- Flagged items — 0-3 штуки максимум (если больше, orchestrator паниковал)

Если manifest плохой — запустить orchestrator ещё раз с указанием что улучшить.

- [ ] **Step 4: Commit manifest**

```bash
git add .planning/refactor-manifest.md
git commit -m "chore: add refactor manifest from orchestrator

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: User approval gate

**Files:** No file changes

- [ ] **Step 1: Показать manifest пользователю**

Сообщение пользователю:
> Manifest готов: [ссылка на .planning/refactor-manifest.md]. Резюме:
> - Удаляем X файлов (Y MB)
> - Создаём Z файлов
> - Open Questions разрешены так-то…
> - Flagged items (требуют твоего решения): …
> 
> Подтверди или укажи что поправить перед Stage B.

- [ ] **Step 2: Дождаться user approval**

Если пользователь одобрил → следующий таск.
Если просит правки → вернуться к Task 4 Step 1 с уточнённым промптом.
Если нашёл критическую ошибку в spec-е → вернуться к brainstorming для правки spec'а.

---

## Stage B — Execution (7 PRs)

### Task 6: PR #1 — `refactor/binary-cleanup`

**Files:**
- Delete: см. `.planning/refactor-manifest.md` секция PR #1

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/binary-cleanup
git status  # verify clean
```

Expected: На новой ветке, working tree clean.

- [ ] **Step 2: Удалить все файлы из PR #1 списка в manifest**

Для каждого пути из manifest (cleanup-v2 §2.1–2.3 + дельта из spec §3.1 binary items):

```bash
git rm -f "<path>"
```

Пример (дополнить из manifest):
```bash
git rm -f "2026_Договор купли-продажи Familia -Чернецкая.docx"
git rm -f "Экосбор_ИП_Медведева_2025.xlsx"
git rm -f "Экосбор_ООО_Вуки_2025.xlsx"
git rm -f "Условия поставки Покупателя (статус РЦ).pdf"
git rm -f "agent-dashboard-full.png"
git rm -f "mockup-full-page.png"
git rm -f "scripts 2.txt"
git rm -f "scripts.txt"
git rm -f "skills-lock 2.json"
git rm -f "services/logistics_audit/Запись экрана"*.wmv
# + все остальные из manifest
```

- [ ] **Step 3: Проверить что осталось то, что должно**

Run:
```bash
ls services/logistics_audit/*.xlsx 2>/dev/null
```

Expected: Только whitelist (v2-final, Итоговый, Тарифы).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove binary garbage (docs, screenshots, videos)

Removes ~200MB of binary files per refactor-manifest PR #1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Push + открыть PR через /pullrequest**

```bash
git push -u origin refactor/binary-cleanup
```

Затем вызвать skill `/pullrequest` с:
- Title: `refactor: binary cleanup (PR 1/7)`
- Body: Ссылка на `.planning/refactor-manifest.md` § PR #1 + список удалённых файлов.

- [ ] **Step 6: Дождаться auto-merge**

Проверить в GitHub UI или через `gh`:
```bash
gh pr view --json state,mergeStateStatus
```

Expected: `state: MERGED` (после прохождения review + auto-merge).

- [ ] **Step 7: Обновить локальный main**

```bash
git checkout main && git pull
```

---

### Task 7: PR #2 — `refactor/gitignore-hardening`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/gitignore-hardening
```

- [ ] **Step 2: Добавить правила из manifest § PR #2**

Открыть `.gitignore` и добавить блок (точный набор — из manifest, базовый шаблон):

```gitignore

# === Refactor v3: anti-garbage rules ===

# Business documents — Google Drive only, not in repo
*.xlsx
*.xlsm
*.docx
*.pdf
!services/logistics_audit/*final*.xlsx
!services/logistics_audit/*Итоговый*.xlsx
!services/logistics_audit/*Тарифы*.xlsx
!services/logistics_audit/*v2-final*.xlsx

# Screenshots and video recordings
*.png
*.jpg
*.jpeg
*.wmv
*.mov
*.mp4
!wookiee-hub/public/**/*.png
!docs/images/**/*.png

# iCloud sync duplicates
* 2.*
* 3.*

# Python caches and artifacts
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Agent runtime artifacts
.playwright-mcp/
.superpowers/brainstorm/
.claude/scheduled_tasks.lock

# OS / editor
.DS_Store
Thumbs.db
.idea/
*.swp
```

- [ ] **Step 3: Untrack файлы, которые уже в репо но должны игнорироваться**

```bash
git rm -r --cached __pycache__ .ruff_cache .pytest_cache 2>/dev/null || true
git rm -r --cached .playwright-mcp .superpowers/brainstorm 2>/dev/null || true
```

- [ ] **Step 4: Проверить что важные файлы остались трекаемыми**

```bash
git ls-files | grep "logistics_audit/.*final.*\.xlsx$"
git ls-files | grep "logistics_audit/.*Итоговый.*\.xlsx$"
```

Expected: whitelist файлы присутствуют в git.

- [ ] **Step 5: Commit, push, PR**

```bash
git add .gitignore
git commit -m "chore(git): harden gitignore to block future garbage (PR 2/7)

Per refactor-manifest PR #2. Blocks binary files outside whitelist,
iCloud duplicates, Python caches, editor artifacts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin refactor/gitignore-hardening
```

Вызвать `/pullrequest` → дождаться auto-merge → `git checkout main && git pull`.

---

### Task 8: PR #3 — `refactor/commit-untracked`

**Files:**
- Add: `services/creative_kb/*`, `services/wb_logistics_api/*`, `services/wb_localization/calculators/*`, `services/wb_localization/sheets_export/*`, `tests/wb_localization/*`, `tests/services/logistics_audit/*`, `docs/superpowers/plans/*.md` (untracked) и др.
- Create: README в каждом новом сервисе

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/commit-untracked
```

- [ ] **Step 2: Получить текущий untracked список**

```bash
git ls-files --others --exclude-standard > /tmp/untracked.txt
cat /tmp/untracked.txt
```

Expected: список untracked файлов. Сверить с manifest PR #3 — какие добавляем, какие игнорим (должны быть в .gitignore теперь).

- [ ] **Step 3: Написать README для `services/creative_kb/`**

Путь: `services/creative_kb/README.md`

Шаблон (заполнить по коду):
```markdown
# creative_kb

## Назначение
<изучи код и опиши одним-двумя предложениями>

## Точка входа
<команда запуска — посмотри Makefile/scripts/__init__>

## Зависимости
- Data: <Supabase tables, external APIs>
- External: <OpenRouter, Gemini, etc.>

## Связанные скиллы
- `/content-search` — <как связан>

## Owner
danila-matveev
```

- [ ] **Step 4: Написать README для `services/wb_logistics_api/`**

Путь: `services/wb_logistics_api/README.md`

Аналогично creative_kb — изучить код + Dockerfile и описать назначение, точку входа, зависимости.

- [ ] **Step 5: Написать README для `services/wb_localization/calculators/` и `sheets_export/`**

Создать соответствующие README.md внутри.

- [ ] **Step 6: Привязать тесты к сервисам**

Файлы `tests/wb_localization/test_*.py` и `tests/services/logistics_audit/test_*.py` должны корректно импортироваться. Прогон:

```bash
pytest tests/wb_localization/ tests/services/logistics_audit/ --collect-only
```

Expected: Все тесты собираются без `ImportError`. Если не собираются — поправить импорты.

- [ ] **Step 7: Прогон тестов**

```bash
pytest tests/wb_localization/ tests/services/logistics_audit/ -v
```

Expected: Все тесты проходят (если фейлятся не по причине отсутствия импорта — зафиксировать в PR body).

- [ ] **Step 8: Add + commit**

```bash
git add services/creative_kb/ services/wb_logistics_api/ \
  services/wb_localization/calculators/ services/wb_localization/sheets_export/ \
  tests/wb_localization/ tests/services/logistics_audit/ \
  docs/superpowers/plans/*.md docs/superpowers/specs/*.md \
  docs/database/KTR_SYNC_VERIFICATION.md \
  deploy/Dockerfile.wb_logistics_api \
  .claude/skills/analytics-report/prompts/pattern-analyzer.md
# ... + другие untracked что в manifest

git commit -m "chore: commit active untracked services, tests, plans (PR 3/7)

- services/creative_kb (new service, Creative KB)
- services/wb_logistics_api (WB logistics HTTP API)
- services/wb_localization/{calculators,sheets_export}
- tests for wb_localization and logistics_audit
- pending plans/specs in docs/superpowers/

Per refactor-manifest PR #3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 9: Push + PR**

```bash
git push -u origin refactor/commit-untracked
```

`/pullrequest` → auto-merge → pull main.

---

### Task 9: PR #4 — `refactor/remove-dead-code`

**Files (точный список — из manifest):**
- Delete: `agents/finolog_categorizer/`, `services/product_matrix_api/`, `mcp_servers/` (целиком), `.mcp.json` entries, `services/dashboard_api/` (если manifest подтвердил DELETE), Dockerfiles старых сервисов, `.planning/archive/*`, `.superpowers/brainstorm/`, orphan scripts из audit-code

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/remove-dead-code
```

- [ ] **Step 2: Удалить neиспользуемые модули**

```bash
git rm -r agents/finolog_categorizer/
git rm -r services/product_matrix_api/
git rm -r mcp_servers/
```

Если manifest подтвердил DELETE для `dashboard_api`/`knowledge_base`/`ozon_delivery` — добавить `git rm -r` для них тоже.

- [ ] **Step 3: Очистить `.mcp.json` от локальных MCP**

Открыть `.mcp.json`, удалить блоки `wookiee-data`, `wookiee-kb`, `wookiee-marketing`, `wookiee-price`. Оставить `wildberries-ip`, `wildberries-ooo`, и любые другие внешние MCP.

Проверить JSON валидность:
```bash
python -m json.tool .mcp.json > /dev/null && echo OK
```

- [ ] **Step 4: Удалить старые Dockerfiles**

```bash
git rm -f deploy/Dockerfile.vasily_api 2>/dev/null || true
git rm -f deploy/Dockerfile.dashboard_api 2>/dev/null || true
git rm -f deploy/deploy-v3-migration.sh 2>/dev/null || true
# + другие из manifest
```

- [ ] **Step 5: Удалить сервисы из docker-compose.yml**

Открыть `docker-compose.yml`, удалить блоки `vasily-api`, `dashboard-api`, и другие по manifest.

Проверить YAML валидность:
```bash
python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))" && echo OK
```

- [ ] **Step 6: Удалить planning-мусор**

```bash
git rm -rf .planning/archive/ 2>/dev/null || true
git rm -rf .planning/research/ 2>/dev/null || true
# + другое из manifest
```

- [ ] **Step 7: Удалить orphan scripts**

Для каждого файла из manifest PR #4 «orphan scripts»:
```bash
git rm <path>
```

- [ ] **Step 8: Проверить что ничего не сломалось в остающемся коде**

```bash
# Питон — импорты
python -c "import shared.data_layer"
python -c "from services.sheets_sync import __init__" 2>/dev/null || true
# Тесты
pytest --collect-only 2>&1 | tail -20
```

Expected: Нет ImportError для остающихся модулей.

- [ ] **Step 9: Commit + push + PR**

```bash
git commit -m "refactor: remove dead code — product_matrix_api, 4 local MCPs, misc (PR 4/7)

Per refactor-manifest PR #4. Removes:
- agents/finolog_categorizer (obsolete)
- services/product_matrix_api (unused)
- mcp_servers/ (all 4 local MCPs, unused)
- .mcp.json entries for local MCPs
- old Dockerfiles (vasily, dashboard)
- .planning/archive, .superpowers/brainstorm
- orphan scripts (list in manifest)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin refactor/remove-dead-code
```

`/pullrequest` → auto-merge → pull main.

---

### Task 10: PR #5 — `refactor/oleg-cleanup`

**Files:**
- Delete: `agents/oleg/` (целиком)
- Create: `docs/archive/oleg-v2-architecture.md`
- Create (условно, если manifest подтвердил extraction): `shared/services/agent_tools.py`, `shared/services/price_tools.py`, `shared/services/marketing_tools.py`, `shared/services/funnel_tools.py`
- Modify (условно): все импорты этих модулей в остающемся коде

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/oleg-cleanup
```

- [ ] **Step 2: (Условно) Extraction tools — только если manifest подтвердил**

Если manifest §PR #5 говорит «extraction needed»:

```bash
mkdir -p shared/services
git mv agents/oleg/services/agent_tools.py shared/services/agent_tools.py
git mv agents/oleg/services/price_tools.py shared/services/price_tools.py
git mv agents/oleg/services/marketing_tools.py shared/services/marketing_tools.py
git mv agents/oleg/services/funnel_tools.py shared/services/funnel_tools.py
```

Обновить импорты. Найти все файлы, импортирующие эти модули:
```bash
rg "from agents.oleg.services" --type py -l
rg "import agents.oleg.services" --type py -l
```

Для каждого найденного файла — заменить:
- `from agents.oleg.services.agent_tools` → `from shared.services.agent_tools`
- (аналогично для остальных)

Проверить:
```bash
python -c "from shared.services import agent_tools, price_tools, marketing_tools, funnel_tools"
```

Expected: Без ошибок.

Если manifest говорит «extraction NOT needed» — перейти сразу к Step 3.

- [ ] **Step 3: Извлечь архитектурный конспект Oleg**

Создать `docs/archive/oleg-v2-architecture.md` с содержанием:

```markdown
# Oleg v2 — архитектурный конспект (retired)

**Retired:** 2026-04-24 (refactor-v3 phase 1)
**Reason:** Функциональность Oleg переведена на проектные скиллы (finance-report,
marketing-report, funnel-report, daily-brief и др.), которые используют общую
инфраструктуру (tool_logger, shared/data_layer, Supabase tool_runs).

## Что это было

Oleg — финансовый AI-агент Wookiee. Multi-agent orchestrator:
- Reporter, Marketer, Funnel Analyzer, Validator, Advisor
- ReAct loop + circuit breaker
- Telegram-интерфейс + scheduler (ежедневные/недельные отчёты)

## Ключевые аналитические знания (перенесены в скиллы)

1. Weekly finance narrative — см. /finance-report
2. Marketing P&L funnel — см. /marketing-report
3. Funnel CRO analysis — см. /funnel-report
4. Daily brief — см. /daily-brief

## Код (удалён)

- agents/oleg/orchestrator/ — ReAct decision loop
- agents/oleg/executor/ — tool executor + circuit breaker
- agents/oleg/services/*_tools.py — <либо перенесены в shared/services/, либо удалены>
- agents/oleg/pipeline/, storage/, anomaly/, playbooks/, watchdog/

## Почему удалили

Скиллы + Supabase `tools`/`tool_runs` дают ту же гибкость без поддержки отдельного
агентного рантайма. `/tool-status` заменяет dashboard Oleg. Единый провайдер
(OpenRouter) + прозрачные промпты внутри скиллов — проще для коллег онбордиться.
```

- [ ] **Step 4: Удалить `agents/oleg/`**

```bash
git rm -r agents/oleg/
```

- [ ] **Step 5: Создать placeholder README для agents/**

Путь: `agents/README.md`

```markdown
# agents/

Директория для true-agent реализаций (длительно работающих autonomous-агентов
с ReAct loop, memory, tool-use).

**Статус:** scaffold. Текущие скиллы (пайплайны под конкретную задачу) живут
в `.claude/skills/`.

Когда добавляется новый true-agent:
1. Создать `agents/<name>/` с `__init__.py`, `README.md`, `config.py`.
2. Обновить `docs/index.md`.
3. Добавить в Supabase `tools` с `type='agent'`.
```

Также убедиться что `agents/__init__.py` существует:
```bash
test -f agents/__init__.py || echo "" > agents/__init__.py
```

- [ ] **Step 6: Прогон тестов и sanity-check**

```bash
pytest --collect-only 2>&1 | tail -20
python -c "import shared; import services.content_kb"  # sample imports
```

Expected: Нет ImportError.

- [ ] **Step 7: Commit + push + PR**

```bash
git add -A
git commit -m "refactor: remove Oleg agent, archive architecture (PR 5/7)

Per refactor-manifest PR #5:
- agents/oleg/ removed (12M+ of retired code)
- agents/oleg/services/*_tools.py <extracted to shared/services/ | deleted>
- docs/archive/oleg-v2-architecture.md created
- agents/ reset to scaffold with README

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin refactor/oleg-cleanup
```

`/pullrequest` → auto-merge → pull main.

---

### Task 11: PR #6 — `refactor/hub-trim` (manual checkpoint)

**Files:**
- Delete: 13+ page.tsx + связанные компоненты/stores/hooks (точный список — manifest PR #6)
- Modify: `wookiee-hub/src/router.tsx`, `App.tsx`, `components/layout/*` (меню → 2 пункта)
- Create: файлы для модуля «Агенты» (`pages/agents/*`, `components/agents/*`) — если manifest требует

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/hub-trim
```

- [ ] **Step 2: Удалить orphan pages + components**

Из manifest PR #6 список DELETE — для каждого пути:
```bash
git rm <path>
```

Пример:
```bash
cd wookiee-hub
git rm src/pages/analytics-abc.tsx src/pages/analytics-overview.tsx \
  src/pages/analytics-promo.tsx src/pages/analytics-unit.tsx \
  src/pages/catalog.tsx src/pages/shipments.tsx src/pages/supply.tsx \
  src/pages/production.tsx src/pages/ideas.tsx src/pages/development.tsx \
  src/pages/dashboard.tsx src/pages/dashboard-placeholder.tsx \
  src/pages/comms-broadcasts.tsx src/pages/comms-store-settings.tsx
git rm -r src/pages/product-matrix/
# + все components/stores/hooks/data/lib orphans из manifest
cd ..
```

- [ ] **Step 3: Переименовать/создать файлы для 2 модулей**

Из manifest PR #6 решение по структуре (tabs vs routes). Пример (routes):

```bash
cd wookiee-hub
mkdir -p src/pages/community src/pages/agents
git mv src/pages/comms-reviews.tsx src/pages/community/reviews.tsx
# если comms-analytics остаётся — переименовать
# создать новые: community/questions.tsx, community/answers.tsx, community/analytics.tsx
# создать: agents/index.tsx (Табло скиллов), agents/history.tsx
cd ..
```

- [ ] **Step 4: Обновить `router.tsx`, `App.tsx`, меню**

Открыть `wookiee-hub/src/router.tsx` — оставить только роуты 2 модулей.
Открыть `wookiee-hub/src/App.tsx` — обновить default route.
Открыть `wookiee-hub/src/components/layout/<Sidebar>.tsx` — оставить 2 пункта меню.

Точные изменения — из manifest.

- [ ] **Step 5: Установить зависимости (если изменился package.json) и собрать**

```bash
cd wookiee-hub
npm install  # если изменились зависимости
npm run build 2>&1 | tail -20
cd ..
```

Expected: `npm run build` завершается без ошибок. **Сборка критична — она гейт перед PR.**

- [ ] **Step 6: Прогон vitest**

```bash
cd wookiee-hub
npm test 2>&1 | tail -10
cd ..
```

Expected: PASS (либо, если тесты зависели от удалённых страниц, обновить/удалить их — фиксировать в PR description).

- [ ] **Step 7: Smoke-test через dogfood (опционально, если есть время)**

Запустить:
```bash
cd wookiee-hub && npm run dev &
```

Вызвать skill `/dogfood` с минимальным сценарием: открыть 2 модуля, убедиться что загружаются.

Сохранить скриншоты → приложить к PR body.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(hub): trim to 2 modules — Community + Agents (PR 6/7)

Per refactor-manifest PR #6. Removes 13+ unused pages and their dependencies.
Keeps/creates:
- Комьюнити: reviews, questions, answers, analytics
- Агенты: tool dashboard, run history

Menu simplified to 2 items. Router updated.

Build verified green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin refactor/hub-trim
```

- [ ] **Step 9: Открыть PR БЕЗ auto-merge**

Вызвать `/pullrequest` — **указать `wait` режим** (не auto-merge). Причина — ручная проверка UI.

Run:
```bash
gh pr create --title "refactor(hub): trim to 2 modules (PR 6/7)" \
  --body-file <(cat <<'EOF'
## Что изменено
- Снос 13+ pages + связанных компонентов
- Меню → 2 пункта: Комьюнити, Агенты
- Модуль Агенты получил scaffold с таблицами из Supabase tools/tool_runs

## Почему
refactor-manifest.md § PR #6

## Как проверено
- [x] npm run build — зелёный
- [x] npm test — зелёный
- [x] Локальный smoke-test 2 модулей
- [ ] **Manual UI check by user needed перед merge**

## Связанные
- refactor-manifest.md § PR #6
- spec: docs/superpowers/specs/2026-04-24-refactor-v3-design.md § 4.1
EOF
)
```

- [ ] **Step 10: Дождаться ручного одобрения пользователя**

Сообщить пользователю:
> PR #6 открыт, build зелёный, но UI-регрессии боты не ловят. Проверь визуально
> 2 модуля (Комьюнити, Агенты) — заходят ли страницы, не поломана ли навигация.
> Когда ок — нажми Merge в GitHub.

Не переходить к следующему таску, пока PR #6 не смёржен.

- [ ] **Step 11: Обновить main**

```bash
git checkout main && git pull
```

---

### Task 12: PR #7 — `refactor/docs-unification`

**Files:**
- Create: `ONBOARDING.md`, `.github/pull_request_template.md`, `docs/skills/<name>.md` для каждого активного скилла, README для каждого активного сервиса, `.claude/skills/hygiene/README.md`, `.claude/hygiene-config.yaml`
- Modify: `README.md`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/index.md`, `docs/architecture.md`
- Move/Delete: `PROJECT_MAP.md` → удалить (заменён `docs/index.md`), устаревшие docs → archive

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/docs-unification
```

- [ ] **Step 2: (Условно) Переименовать `services/observability/`**

Если manifest содержит решение по переименованию (§PR #7 или раньше):

```bash
NEW_NAME="<из manifest, например tool_telemetry>"
git mv services/observability services/$NEW_NAME
# обновить импорты
rg "from services.observability" --type py -l | xargs sed -i '' "s|from services.observability|from services.$NEW_NAME|g"
rg "import services.observability" --type py -l | xargs sed -i '' "s|import services.observability|import services.$NEW_NAME|g"
```

Проверка:
```bash
python -c "from services.$NEW_NAME import tool_logger" || echo "FIX IMPORTS"
```

- [ ] **Step 3: Создать `.github/pull_request_template.md`**

Содержимое — из spec §5.2 (literal copy).

- [ ] **Step 4: Создать `ONBOARDING.md`**

Путь: `ONBOARDING.md` (root)
Содержимое — по шаблону из spec §6.3. Заполнить конкретными командами Wookiee.

- [ ] **Step 5: Создать README для каждого активного сервиса**

Для каждой директории в `services/` без README.md — создать по шаблону spec §4.2 Б.

Проверить:
```bash
for d in services/*/; do
  test -f "$d/README.md" || echo "MISSING: $d"
done
```

- [ ] **Step 6: Создать `docs/skills/<name>.md` для каждого активного скилла**

Для каждого `.claude/skills/<name>/SKILL.md` в проекте — создать `docs/skills/<name>.md` по шаблону spec §6.4.

Можно автоматизировать через короткий скрипт:
```bash
mkdir -p docs/skills
for skill_dir in .claude/skills/*/; do
  name=$(basename "$skill_dir")
  [ -f ".claude/skills/$name/SKILL.md" ] && \
    echo "Creating docs/skills/$name.md" && \
    cat > "docs/skills/$name.md" <<EOF
# /$name

## Назначение
<читается из .claude/skills/$name/SKILL.md — description>

## Триггеры
<из SKILL.md>

## Входные данные
<из SKILL.md + код>

## Выходные данные
<из SKILL.md + код>

## Команды запуска
<из SKILL.md>

## Связанные сервисы/скрипты
<grep по коду скилла>

## Статус
production
EOF
done
```

**Важно:** после генерации — вручную пройтись и заполнить конкретикой. Плейсхолдеры в docs — недопустимы.

- [ ] **Step 7: Создать `.claude/skills/hygiene/` scaffold**

```bash
mkdir -p .claude/skills/hygiene
cat > .claude/skills/hygiene/README.md <<'EOF'
# /hygiene (Phase 2 — planned)

**Статус:** планируется. Spec будет написан в отдельной brainstorm-сессии
после завершения Фазы 1 рефакторинга (см. `docs/superpowers/specs/2026-04-24-refactor-v3-design.md` §7).

**Концепция:** скилл для поддержания чистоты репо — запускается вручную
или по cron. Автономно коммитит, удаляет мусор по whitelist, синхронизирует
docs с кодом. Удаление/перенос вне whitelist — через PR-запрос аппрува.

**Config:** `.claude/hygiene-config.yaml` (placeholder рядом).

## TODO Phase 2
- [ ] Brainstorm sessions via /superpowers:brainstorm
- [ ] Spec at docs/superpowers/specs/<date>-hygiene-skill-design.md
- [ ] Implementation plan
- [ ] Implement SKILL.md + prompts
- [ ] Cron scheduling via /schedule
EOF

cat > .claude/hygiene-config.yaml <<'EOF'
# Placeholder — finalized in Phase 2
whitelist_zones:
  allow_binaries:
    - services/logistics_audit/*Итоговый*.xlsx
    - docs/images/

schedule:
  frequency: daily
  time: "06:00"
  timezone: Europe/Moscow

auto_fix:
  unpushed_work: true
  stray_binaries: true
  icloud_dupes: true
  pycache_committed: true

ask_user:
  orphan_imports: true
  orphan_docs: true
  stale_branches: true
  missing_readme: true

notification:
  channel: telegram
  only_if: ask_required
EOF
```

- [ ] **Step 8: Обновить `README.md`**

Переписать root `README.md` по шаблону spec §6.2. Включить:
- Одну фразу что это
- Буллеты «что умеет»
- Быстрый старт (реальные команды)
- Ссылки на `docs/index.md`, `ONBOARDING.md`, `AGENTS.md`, `CONTRIBUTING.md`
- Список активных скиллов
- Список активных сервисов

- [ ] **Step 9: Обновить `AGENTS.md`**

Удалить упоминания Oleg как активного. Обновить Quick Reference: заменить ссылки на удалённые модули. Секцию «AI-агенты» сделать: «Скиллы — основной рабочий инструмент. Будущие true-agent'ы — в `agents/`».

- [ ] **Step 10: Обновить `CLAUDE.md`**

Проверить что ссылки живые, убрать устаревшие.

- [ ] **Step 11: Переписать `CONTRIBUTING.md` под новый workflow**

Описать:
- Как клонировать, настроить
- Как создать ветку (feature/*, refactor/*, fix/*)
- Как открыть PR (через `/pullrequest` или вручную через `gh`)
- Что ждать от Codex/Copilot review
- Правила коммит-сообщений
- Как запускать тесты локально

- [ ] **Step 12: Обновить `docs/index.md`**

По структуре spec §6.1. Удалить ссылки на: Oleg (перенести в archive), dashboard_api (если удалён), старые плагины.

- [ ] **Step 13: Обновить `docs/architecture.md`**

Перерисовать runtime-архитектуру без Oleg. Обновить список активных сервисов/MCP (только wildberries external).

- [ ] **Step 14: Перенести устаревшее в `docs/archive/`**

Из manifest PR #7 список переносов:
```bash
mkdir -p docs/archive
git mv docs/future/agent-ops-dashboard docs/archive/agent-ops-dashboard 2>/dev/null || true
# + другие из manifest
```

Удалить `PROJECT_MAP.md` если он заменён `docs/index.md`:
```bash
git rm docs/PROJECT_MAP.md 2>/dev/null || true
```

- [ ] **Step 15: Проверить что доки валидны**

```bash
# markdown синтаксис — sanity check
find docs ONBOARDING.md README.md AGENTS.md CLAUDE.md CONTRIBUTING.md \
  -name "*.md" -exec python -c "import sys; open(sys.argv[1]).read()" {} \;
```

Expected: ошибок чтения нет.

- [ ] **Step 16: Commit, push, PR**

```bash
git add -A
git commit -m "docs: unify documentation for colleague-ready repo (PR 7/7)

Per refactor-manifest PR #7:
- New: ONBOARDING.md, .github/pull_request_template.md
- New: docs/skills/*.md (one per active skill)
- New: services/*/README.md (one per active service)
- New: .claude/skills/hygiene/ scaffold (Phase 2 placeholder)
- Updated: README.md, AGENTS.md, CLAUDE.md, CONTRIBUTING.md, docs/index.md,
  docs/architecture.md
- Archived: docs/future/agent-ops-dashboard, other stale docs
- Renamed: services/observability -> services/<new_name>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"

git push -u origin refactor/docs-unification
```

`/pullrequest` → auto-merge → pull main.

---

## Stage C — Verification

### Task 13: Dispatch refactor-verifier

**Files:**
- Output: `.planning/refactor-verification.md`

- [ ] **Step 1: Запустить verifier Agent**

Agent prompt:
```
You are refactor-verifier. Your role is to check whether refactor-v3 Phase 1
actually achieved its goals.

READ:
- docs/superpowers/specs/2026-04-24-refactor-v3-design.md (full spec)
- .planning/refactor-manifest.md
- current repo state

TASKS:
1. For each item in manifest (across all 7 PRs), verify the end state matches:
   - Each DELETE: file actually absent (test -e path; should fail)
   - Each CREATE: file actually present and non-empty
   - Each RENAME: old path absent, new path present, imports updated (grep)
   - Each MODIFY: expected content present

2. Run functional checks:
   - `pytest --collect-only` — no ImportError
   - `pytest tests/` (existing tests that should pass) — green
   - `cd wookiee-hub && npm run build` — green
   - `python -c "import shared.data_layer"` — OK
   - Sample 3 skills dry-run (if cheap): /tool-status, /finance-report --dry-run
     (report intent, don't actually execute expensive ones)

3. Check docs:
   - All links in README.md, AGENTS.md, docs/index.md point to existing files
   - No "Oleg" as active (grep -ri 'oleg' --include="*.md" | grep -v archive)
   - ONBOARDING.md flow works: clone instructions → first command

4. Check success criteria from spec §9.

5. Write .planning/refactor-verification.md:
   - Executive summary
   - GREEN section (confirmed working)
   - YELLOW section (needs manual check, e.g., UI)
   - RED section (broken — needs fix)
   - Per-success-criterion checklist

RULES:
- READ-ONLY for project files. Write only to .planning/refactor-verification.md.
- Don't run expensive skills (no actual report generation).
- Be honest — YELLOW is fine, RED means a real problem.

Token budget: under 80k tokens.
```

- [ ] **Step 2: Прочитать verification report**

```bash
cat .planning/refactor-verification.md | head -100
```

- [ ] **Step 3: Решить следующий шаг**

- Если RED отсутствует → Task 15 (close Phase 1)
- Если есть RED → Task 14 (PR #8 fixes)

- [ ] **Step 4: Commit verification report**

```bash
git checkout main && git pull
git add .planning/refactor-verification.md
git commit -m "chore: refactor-v3 phase 1 verification report

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

---

### Task 14: (Опционально) PR #8 — `refactor/verification-fixes`

**Files:** Зависит от RED items

- [ ] **Step 1: Создать ветку**

```bash
git checkout -b refactor/verification-fixes
```

- [ ] **Step 2: Для каждого RED item из verification-report — исправить**

Каждое исправление — отдельный мелкий commit с referenced item.

Пример если RED: «ImportError в services/X/foo.py»:
```bash
# найти и починить
# commit
git commit -m "fix: restore import in services/X/foo.py (verification item R-1)"
```

- [ ] **Step 3: Повторный прогон проверок**

```bash
pytest --collect-only && cd wookiee-hub && npm run build
```

Expected: Все зелёное.

- [ ] **Step 4: Push + PR (auto-merge)**

```bash
git push -u origin refactor/verification-fixes
```

`/pullrequest` → auto-merge → pull main.

---

### Task 15: Close Phase 1

**Files:**
- Modify: `docs/development-history.md` (добавить запись)
- No code changes

- [ ] **Step 1: Добавить запись в development-history**

Открыть `docs/development-history.md`, добавить в начало:

```markdown
## 2026-04-24 — Refactor v3 Phase 1 completed

- Removed: Oleg agent (12M), 4 local MCP servers, product_matrix_api, finolog_categorizer, 13+ Hub pages, ~200MB binary garbage
- Kept + completed: creative_kb, wb_logistics_api, wb_localization (calculators, sheets_export), tests
- Renamed: services/observability → services/<new_name>
- New: ONBOARDING.md, docs/skills/*.md, README per service, PR template, .github setup, hygiene scaffold
- Workflow: PR-based with Codex + Copilot review and auto-merge on main
- Spec: docs/superpowers/specs/2026-04-24-refactor-v3-design.md
- Manifest: .planning/refactor-manifest.md
- Verification: .planning/refactor-verification.md

Next: Phase 2 — /hygiene skill (separate brainstorm session).
```

- [ ] **Step 2: Commit**

```bash
git add docs/development-history.md
git commit -m "docs: mark refactor-v3 phase 1 as completed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

- [ ] **Step 3: Сообщение пользователю**

> Фаза 1 завершена. Репо в colleague-ready состоянии:
> - Main защищён, PR-workflow с auto-merge
> - Hub на 2 модуля
> - Oleg/мусор удалены
> - Документация унифицирована
> - ONBOARDING готов
>
> Рекомендую следующий шаг: новая brainstorm-сессия для Phase 2 — `/hygiene` skill.
> Теперь у нас есть реальные паттерны мусора для обоснованного дизайна скилла.

---

## Self-Review Notes

После написания плана — выполнено:

1. **Spec coverage:**
   - §1 Goal/Non-Goals — отражено в header
   - §2 Stages A/A.5/B/C — Task 3 / Task 4-5 / Task 6-12 / Task 13-15
   - §3 Delete list — распределено по PR #1, #4, #5, #6
   - §4 Keep/build — PR #3 (untracked), #6 (Hub), #7 (docs)
   - §5 Git workflow — Task 1 (pre-flight), каждый Task открывает PR через `/pullrequest`
   - §6 Docs unification — Task 12 (PR #7)
   - §7 Phase 2 preview — Task 12 Step 7 (scaffold)
   - §8 Execution order — структура плана
   - §9 Success criteria — Task 13 Step 1 (verifier проверяет)
   - §10 Open questions — Task 4 (orchestrator решает)

2. **Placeholder scan:** Нет «TBD/TODO/fill in later». Плейсхолдеры типа `<из manifest>` умышленны — manifest будет финальным источником точных путей, и это оправдано (иначе пришлось бы заранее guess'ить результат audit'а).

3. **Type consistency:** Имена PR-веток (`refactor/binary-cleanup`, `refactor/gitignore-hardening` и т.д.) согласованы со spec §2.3. Имена артефактов (`.planning/refactor-manifest.md`, `.planning/refactor-verification.md`) согласованы в Task 4 и Task 13.

4. **Скоуп:** План покрывает только Фазу 1. Фаза 2 (`/hygiene` skill) — отдельный будущий spec + plan, что соответствует решению в brainstorm.
