# Hygiene Autopilot — Tiered Auto-Merge + Autofix

**Date:** 2026-05-09 (recreated 2026-05-10 после потери оригинала в branch-switching эпизоде)
**Goal:** Убрать Danila из цикла мерджа hygiene-PR'ов с zero-blast-radius содержимым (docs, skill mirrors). Автоматически чинить `ask_user` находки, которые требуют только LLM-верификации.

**Принципы:**
1. Blast radius определяет policy. Doc-only PR → autopilot. `shared/**` → human only. Никогда не смешиваем.
2. Дёшево откатывать ≠ дорого аппрувить. Canary + auto-revert > pre-merge approve.
3. Hygiene = детектор. Autofix = LLM-фиксер с контекстом проекта. Auto-merge = path-guarded бот. Три отдельные ответственности, три отдельных workflow.

**Tiers:**

| Tier | Paths | Policy |
|------|-------|--------|
| 1 (Autopilot) | `docs/**`, `.claude/skills/**`, `.cursor/skills/**`, `.codex/skills/**`, `.claude/hygiene-config.yaml` (только дополнения в whitelist), все `*.md` вне `services/*/data/` | CI green → squash-merge мгновенно, no human |
| 2 (Soft gate) | `services/**` (без `/data/**`), `scripts/**`, `tests/**` | Codex pass + CI green → merge через 30 мин cooling-off |
| 3 (Human only) | `shared/**`, `database/sku/**`, `.env*`, `.github/workflows/**`, `services/*/data/**`, миграции, изменения tier-whitelist | Только Danila |

Phase 1 закрывает только Tier 1 + autofix. Tier 2 и canary — отдельный план после 2-недельного observation.

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `.github/workflows/tier-classifier.yml` | NEW | Опускает label `tier:1\|2\|3` на PR при open/sync на основе изменённых путей |
| `.github/workflows/hygiene-autofix.yml` | NEW | Cron 04:00 UTC: запускает Claude Code action со скиллом `/hygiene-autofix` на свежий hygiene PR |
| `.github/workflows/auto-merge-tier1.yml` | NEW | На событие `pull_request_review` или `check_suite completed`: если PR имеет label `tier:1` + green CI → squash-merge |
| `.claude/skills/hygiene-autofix/SKILL.md` | NEW | Инструкция Claude'у в headless: read PR + report URL, верифицировать каждое ask_user findings, починить безопасные, закоммитить, оставить summary в PR |
| `.claude/skills/hygiene-autofix/prompts/system.md` | NEW | System prompt с правилами (что трогать нельзя, как верифицировать) |
| `scripts/ci/classify_pr_tier.py` | NEW | Логика tier-классификации по diff'у |
| `.claude/hygiene-config.yaml` | EDIT | Добавить секцию `auto_merge_tiers:` с whitelists и правилом «изменения этой секции = tier:3» |

---

## Phase 1: Tier classifier + Tier 1 auto-merge

**Цель:** PR'ы, изменяющие только doc/skill-mirror пути, мерджатся автоматически на CI green.

### Task 1.1: Описать tiers в `.claude/hygiene-config.yaml`

- [ ] **Step 1.1.1: Добавить секцию `auto_merge_tiers`**

```yaml
auto_merge_tiers:
  # ВАЖНО: изменения этой секции = tier:3 (human only).
  # Это контракт безопасности — расширение whitelist всегда требует ревью.
  tier_1_autopilot:
    paths:
      - docs/**
      - .claude/skills/**
      - .cursor/skills/**
      - .codex/skills/**
      - "**/*.md"
    excluded_paths:
      - services/*/data/**
      - .env*
    max_files: 30
    max_lines_changed: 2000

  tier_2_soft_gate:
    paths:
      - services/**
      - scripts/**
      - tests/**
    excluded_paths:
      - services/*/data/**
    cooling_off_minutes: 30
    require_codex_pass: true

  tier_3_human:
    paths:
      - shared/**
      - database/sku/**
      - .env*
      - .github/workflows/**
      - services/*/data/**
      - .claude/hygiene-config.yaml  # self-protection
```

### Task 1.2: Tier classifier workflow

- [ ] **Step 1.2.1: Создать `.github/workflows/tier-classifier.yml`**

```yaml
name: PR Tier Classifier

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  classify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Compute tier
        id: tier
        run: |
          python scripts/ci/classify_pr_tier.py \
            --pr ${{ github.event.pull_request.number }} \
            --config .claude/hygiene-config.yaml \
            --output tier.txt
          echo "tier=$(cat tier.txt)" >> $GITHUB_OUTPUT
      - name: Apply label
        run: |
          gh pr edit ${{ github.event.pull_request.number }} \
            --remove-label "tier:1" --remove-label "tier:2" --remove-label "tier:3" 2>/dev/null || true
          gh pr edit ${{ github.event.pull_request.number }} \
            --add-label "tier:${{ steps.tier.outputs.tier }}"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 1.2.2: Создать `scripts/ci/classify_pr_tier.py`**

Логика: `gh pr diff --name-only` → если хоть один путь matches tier_3 → tier:3 (escalate); иначе если все в tier_1 paths и нет excluded_paths и под лимитами → tier:1; иначе tier:2.

- [ ] **Step 1.2.3: Создать labels в репозитории**

```bash
gh label create "tier:1" --color 0e8a16 --description "Autopilot — auto-merge on CI green"
gh label create "tier:2" --color fbca04 --description "Soft gate — Codex pass + cooling-off"
gh label create "tier:3" --color d93f0b --description "Human review required"
```

### Task 1.3: Auto-merge Tier 1

- [ ] **Step 1.3.1: Создать `.github/workflows/auto-merge-tier1.yml`**

```yaml
name: Auto-merge Tier 1

on:
  pull_request:
    types: [labeled]
  check_suite:
    types: [completed]

permissions:
  contents: write
  pull-requests: write

jobs:
  automerge:
    runs-on: ubuntu-latest
    steps:
      - name: Find candidate PRs
        run: |
          gh pr list --state open --label "tier:1" --json number,labels,statusCheckRollup,mergeable \
            | jq -c '.[] | select(
              (.labels | map(.name) | contains(["do-not-merge"]) | not) and
              (.mergeable == "MERGEABLE") and
              ((.statusCheckRollup // []) | all(.conclusion == "SUCCESS" or .conclusion == "NEUTRAL" or .conclusion == "SKIPPED"))
            ) | .number' > candidates.txt
          while read pr; do
            gh pr merge "$pr" --squash --auto --delete-branch
          done < candidates.txt
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 1.3.2: Branch protection (без require-review)**

```bash
gh api repos/danila-matveev/Wookiee/branches/main/protection \
  --method PUT --input - <<EOF
{
  "required_status_checks": {"strict": true, "contexts": ["classify", "quality"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

- [ ] **Step 1.3.3: Escape hatches** — label `do-not-merge` пропускает PR; `gh pr revert` создаёт revert-PR.

### Task 1.4: Smoke test

- [ ] **Step 1.4.1:** Тестовый doc-only PR → tier:1 → auto-merge в течение 5 мин
- [ ] **Step 1.4.2:** PR с `shared/` → tier:3 → автомердж не сработал
- [ ] **Step 1.4.3:** Commit Phase 1

---

## Phase 2: Hygiene Autofix cron

**Цель:** Заменить ручную сессию (как 2026-05-09) cron-job'ом, который запускает Claude в headless на свежий hygiene-PR и фиксит безопасные ask_user находки.

### Task 2.1: Skill `hygiene-autofix`

- [ ] **Step 2.1.1: `.claude/skills/hygiene-autofix/SKILL.md`**

Phases:
1. Locate latest hygiene PR (`gh pr list --label "hygiene" --state open --limit 1`)
2. Fetch Cloudflare hygiene report URL from PR body, extract findings
3. For each finding — verify (grep, read related files, refactor-audit notes), classify SAFE/UNSAFE/NEEDS_HUMAN
4. Apply SAFE fixes, push to PR branch
5. Comment summary on PR

- [ ] **Step 2.1.2: System prompt с правилами**

- НИКОГДА не трогать `protected_zones.never_modify`
- НИКОГДА не force-push, не `--no-verify`
- НИКОГДА не мерджить PR (только пушить)
- При неуверенности — пропустить, оставить комментарий
- Лимит: ≤10 fixes за прогон
- Token cap: hard 100K / soft 50K (warn → abort + Telegram)

- [ ] **Step 2.1.3: Sync skill в .cursor и .codex mirrors**

### Task 2.2: Workflow

- [ ] **Step 2.2.1: `.github/workflows/hygiene-autofix.yml`**

Базируется на структуре существующего `hygiene-daily.yml`. Cron `0 4 * * *` (час после hygiene). Использует `anthropics/claude-code-action@v1` с `prompt: "/hygiene-autofix"`.

- [ ] **Step 2.2.2: Telegram уведомление в конце run**

Использовать `TELEGRAM_ALERTS_BOT_TOKEN` (общий @wookiee_alerts_bot). Формат:
```
🔧 Hygiene Autofix — день 2026-MM-DD
Починил: N (список)
Оставил человеку: M (с reason)
PR: <url>
```

### Task 2.3: Smoke test

- [ ] `gh workflow run hygiene-autofix.yml` → новые коммиты в hygiene PR от bot user → Telegram alert → следующий tier-classifier ставит `tier:1` → auto-merge

---

## Phase 3: Observation period (1-2 weeks)

### Task 3.1: Метрики

- [ ] Notion-страница `Hygiene Autopilot Stats` или `tool_runs` в Supabase:

| date | hygiene_findings | autofix_applied | autofix_skipped | tier_1_merged | tier_3_pending | regressions_caught_next_day |

### Task 3.2: Stop-conditions для расширения

Перейти к Tier 2 / canary ТОЛЬКО если за 2 недели:
- ≥10 успешных tier:1 авто-мерджей
- 0 регрессий с ручным revert'ом из прода
- ≥80% autofix-исправлений приняты CI без правок

---

## Verification (для Phase 1 + 2)

| Проверка | Команда / факт | Expected |
|---|---|---|
| Tier labels существуют | `gh label list \| grep tier:` | 3 строки |
| Classifier запускается | `gh run list --workflow tier-classifier.yml --limit 3` | runs за последние 3 PR |
| Auto-merge срабатывает на тестовый doc-PR | merged_at != null в течение 10 мин | ✅ |
| Auto-merge НЕ срабатывает на mixed PR (tier:3) | label = tier:3, status = open | ✅ |
| Hygiene-autofix пишет в свежий hygiene PR | last commit author = github-actions | ✅ |
| Telegram alert приходит | сообщение в @wookiee_alerts_bot | ✅ |

---

## Escape hatches

1. **Стоп всего autopilot'а:** `gh workflow disable auto-merge-tier1.yml && gh workflow disable hygiene-autofix.yml`
2. **Стоп конкретного PR:** `gh pr edit N --add-label do-not-merge`
3. **Откат вчерашнего автомерджа:** `gh pr revert <merged-PR-number>` создаст revert-PR
4. **Расширение whitelist (требует tier:3 ручной мердж):** `auto_merge_tiers.tier_1_autopilot.paths` сам в `protected_zones.never_modify`

---

## Out of scope (для отдельного плана после observation)

- Tier 2 (services/scripts с Codex pass + cooling-off)
- Canary watcher после деплоя (мониторинг ошибок 30 мин, auto-revert при spike)
- Расширение autofix на не-hygiene PR'ы
- Fix hygiene-детектора false-positive по `archive/retired_agents/` (повторяется 2 дня подряд)
