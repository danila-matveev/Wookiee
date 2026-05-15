# Nighttime DevOps Agent — Implementation Plan

**Date:** 2026-05-14
**Branch (future):** `feature/nighttime-devops-agent`
**Status:** PLAN — нулевая реализация, только дизайн. Источник истины для 5 параллельных sub-agent-ов.
**Owner:** Danila Matveev (non-technical business owner — все Telegram-сообщения на простом русском)

---

## 0. Цель и принципы

### 0.1 Что строим — одной фразой

Каждую ночь, пока владелец спит, агент находит в репо Wookiee все проблемы (hygiene findings, lint/type/dead-code, недостающие тесты), чинит всё, что может починить безопасно сам, и выпускает **ровно один Pull Request за ночь**, который автоматически мерджится. То, что требует решения человека, упаковывается в **одно** Telegram-сообщение на простом русском с готовой командой «вставь это в Claude Code, чтобы починить разом».

### 0.2 Ключевые инварианты (нарушать нельзя)

1. **Один PR за ночь.** Все 4 источника находок (hygiene, code-quality, test-coverage, future Phase 4) сливаются в один PR. Никаких «5 PR на каждый чих».
2. **Workflow Guard не обходим.** PR создаётся через `gh pr create`, мерджится через `gh pr merge --auto`. CI и rulesets работают как обычно. Никаких `--no-verify`, никаких force-push.
3. **Read-only режим по умолчанию.** Первая неделя жизни системы — `.hygiene/config.yaml: read_only: true`. Агент производит JSON-отчёты и Telegram-дайджест, но **не открывает PR и не пушит**. Флип в `read_only: false` делает владелец вручную после калибровки.
4. **Telegram — на простом русском.** Без жаргона. Аналогии из быта. Команда для копипасты в Claude Code в конце сообщения. См. `feedback_plain_language.md`.
5. **Codex CLI — через подписку, не API.** Все вызовы Codex идут через локальный `codex exec` с OAuth-токеном (`~/.codex/auth.json`). API-ключ не используется. См. `feedback_subscription_over_api.md`.
6. **Память агента.** Все решения человека пишутся в `.hygiene/decisions.yaml`. На следующую ночь агент сначала читает память: «вот это уже решали — повторять не нужно».
7. **Все Phase 0–3 строятся реализуемо. Phase 4 — только интерфейс, без кода.**

### 0.3 Принципы из MEMORY.md, которые этот дизайн соблюдает

| Memory entry | Как соблюдается |
|---|---|
| `feedback_plain_language.md` | Telegram-сообщения — бытовой язык, аналогии, я-сам-решил, владелец видит готовую команду для копипасты |
| `feedback_subscription_over_api.md` | Codex вызывается через `codex exec` (OAuth chatgpt subscription), а не Anthropic/OpenAI API ключ |
| `feedback_verify_before_done.md` | Каждый коммит ночного агента сопровождается postcondition-проверкой; rollback test в CI верифицирует обратимость |
| `feedback_no_editing_on_server.md` | Сервер deploy-only. Ночной агент работает только в GitHub Actions, никаких прямых правок на app-сервере |
| `feedback_hygiene_bot_design.md` | Используем существующий `@wookiee_alerts_bot` (TELEGRAM_ALERTS_BOT_TOKEN). Нового бота НЕ создаём. Просто расширяем шаблоны |
| `feedback_bot_creation_pattern.md` | Если когда-нибудь понадобится отдельный child-bot — через Батю, deeplink, токен в Postgres |
| `feedback_mcp_secrets_pattern.md` | Все секреты — через GH Actions Secrets и `.env`, никогда в plan/skill md |
| `feedback_no_secrets_in_docs.md` | В этом плане **нет** ни одного реального токена/ключа. Только плейсхолдеры |
| `project_workflow_guard.md` | Workflow Guard активен. Ночной агент использует `gh pr merge --auto` — ruleset сам пропустит после прохождения CI |
| `feedback_verify_links_playwright.md` | Если PR содержит ссылки в md, ночной агент опционально прогоняет их через простой curl-чек |

### 0.4 Out of scope (явно)

- Реализация любого кода в этой задаче. Это план, и только план.
- Изменение workflow-файлов, skill-файлов, settings.json. Только запись `.md`-плана.
- Спавн новых sub-agent-ов из этой задачи.
- Phase 4 (autonomous refactoring via Codex) — задизайнен на уровне интерфейса, но не строится.

---

## 1. Архитектура: высокоуровневый поток ночи

```
03:00 UTC ──► hygiene-daily.yml          ──► .hygiene/reports/hygiene-YYYY-MM-DD.json
03:30 UTC ──► code-quality-daily.yml     ──► .hygiene/reports/code-quality-YYYY-MM-DD.json
04:00 UTC ──► night-coordinator.yml      ──► читает оба JSON + decisions.yaml + queue.yaml
                                              │
                                              ├─► если все SAFE  → 1 PR + gh pr merge --auto
                                              └─► если NEEDS_HUMAN → queue.yaml + Telegram digest
04:30 UTC ──► test-coverage-check.yml    ──► gate: blocks merge if coverage drops
05:00 UTC ──► heartbeat.yml              ──► 1 короткое Telegram «я отработал, нашёл X»
```

**Concurrency:** все 5 job-ов в одной группе `concurrency: night-devops`, `cancel-in-progress: false`. Это гарантирует строго последовательное исполнение. Если `03:00 hygiene` затянулся до 03:35, `03:30 code-quality` ждёт. `04:00 night-coordinator` ждёт обоих. И т.д.

**Хранилище отчётов:** все JSON живут в `.hygiene/reports/` в коммите. Это сознательное решение: версионируется, легко grep-нуть «а что было 3 ночи назад», нет внешнего blob storage. Retention — 30 дней (отдельный cleanup-step в night-coordinator).

---

## 2. File layout

### 2.1 Новые файлы (создаются по фазам)

```
.hygiene/
├── config.yaml                          # Phase 0  — read_only flag, thresholds, retention
├── decisions.yaml                       # Phase 0  — persistent memory of human decisions
├── queue.yaml                           # Phase 1  — NEEDS_HUMAN items awaiting /hygiene-resolve
├── reports/
│   ├── hygiene-YYYY-MM-DD.json          # Phase 0  — output of /hygiene
│   ├── code-quality-YYYY-MM-DD.json     # Phase 2  — output of /code-quality-scan
│   ├── coverage-YYYY-MM-DD.json         # Phase 3  — output of /test-coverage-check
│   └── coordinator-YYYY-MM-DD.json      # Phase 0  — output of /night-coordinator
└── codex_logs/
    └── YYYY-MM-DD/finding_<id>.log      # Phase 2  — raw codex exec output for debugging

.claude/skills/
├── hygiene/                             # MODIFIED — emits JSON instead of opening PR
│   └── prompts/emit_report.md           # Phase 0  — new prompt module
├── hygiene-autofix/                     # NEW (restored from PR #111)
│   ├── SKILL.md                         # Phase 0
│   ├── README.md                        # Phase 0
│   └── prompts/
│       ├── system.md                    # Phase 0
│       └── verify.md                    # Phase 0
├── hygiene-resolve/                     # NEW — interactive local skill
│   ├── SKILL.md                         # Phase 1
│   └── prompts/dialog.md                # Phase 1  — Russian-language Q&A flow
├── code-quality-scan/                   # NEW
│   ├── SKILL.md                         # Phase 2
│   └── prompts/
│       ├── runners.md                   # Phase 2  — ruff/mypy/vulture wrappers
│       └── codex_arbiter.md             # Phase 2  — codex sidecar prompt template
├── test-coverage-check/                 # NEW
│   ├── SKILL.md                         # Phase 3
│   └── prompts/threshold.md             # Phase 3
├── night-coordinator/                   # NEW — the orchestrator
│   ├── SKILL.md                         # Phase 0
│   ├── prompts/
│   │   ├── merge_strategy.md            # Phase 0
│   │   ├── telegram_digest.md           # Phase 0/1
│   │   └── pr_body.md                   # Phase 0
└── heartbeat/                           # NEW — cumulative day summary
    └── SKILL.md                         # Phase 0

scripts/nightly/                         # NEW — pure-Python helpers (callable from skills)
├── __init__.py
├── report_schema.py                     # Phase 0  — dataclasses + jsonschema validators
├── telegram_render.py                   # Phase 0/1 — message builder, plain Russian
├── queue_ops.py                          # Phase 1  — enqueue/dequeue/expire
├── decisions_ops.py                     # Phase 0  — read/write decisions.yaml
├── supabase_fix_log.py                  # Phase 3  — write to fix_log table
└── rollback_check.py                    # Phase 3  — CI test: verify rollback_command works

.github/workflows/
├── hygiene-daily.yml                    # MODIFIED — emit JSON, no PR
├── code-quality-daily.yml               # NEW      — Phase 2
├── night-coordinator.yml                # NEW      — Phase 0  (the only PR-opener)
├── test-coverage-check.yml              # NEW      — Phase 3
└── heartbeat.yml                        # NEW      — Phase 0

database/sku/migrations/                 # Supabase (existing folder)
└── 014_fix_log.sql                      # Phase 3  — fix_log table + RLS policies

docs/superpowers/plans/
└── 2026-05-14-nighttime-devops-agent-impl.md   # THIS FILE
```

### 2.2 Модифицируемые файлы

| Path | Phase | Что меняем |
|---|---|---|
| `.github/workflows/hygiene-daily.yml` | 0 | Удалить шаги «open PR». Добавить шаги «commit JSON to `.hygiene/reports/`». Прометить, что cron остаётся 03:00 UTC. |
| `.claude/skills/hygiene/SKILL.md` | 0 | Добавить флаг `--emit-json`. По умолчанию (без флага) — старое поведение (для ручного запуска). С флагом — пишет JSON, не открывает PR. Cron всегда вызывает с флагом. |
| `AGENTS.md` | 1 | Раздел «Ночной DevOps-агент: что это, как отключить, как режим read-only». 30–50 строк. |
| `.claude/settings.json` (project) | 1 | Добавить permission allowlist для `gh pr create`, `gh pr merge --auto`, `codex exec`. Правка делается вручную владельцем — fs-firewall блокирует правку settings из Claude. |

### 2.3 Файлы, которые НЕ трогаем

- `.github/workflows/ci.yml` — там есть известные pre-existing test failures, которые уже игнорируются. Их трогать **нельзя** в рамках этой работы. Если ночной агент находит fail в этих тестах — он считается ожидаемым.
- `.github/workflows/hygiene-followup-daily.yml` — отдельный пайплайн hygiene-followup. Не пересекается. Оставляем как есть.
- `.claude/hooks/*` — Workflow Guard. Не трогать. Никогда.
- Любой код в `shared/`, `services/`, `agents/`, `scripts/` (кроме `scripts/nightly/`).

---

## 3. Interface contracts (JSON schemas)

Все схемы валидируются через `jsonschema` в `scripts/nightly/report_schema.py`. Любое нарушение схемы = job FAIL + Telegram alert.

### 3.1 Hygiene report

`.hygiene/reports/hygiene-YYYY-MM-DD.json`

```json
{
  "$schema": "https://wookiee.shop/schemas/hygiene-report-v1.json",
  "version": "1.0.0",
  "run_id": "hygiene-2026-05-14-0300-utc",
  "started_at": "2026-05-14T03:00:00Z",
  "finished_at": "2026-05-14T03:18:43Z",
  "commit_sha": "abc123...",
  "findings": [
    {
      "id": "hygiene-orphan-import-shared-helpers-old",
      "category": "orphan-imports",
      "severity": "low",
      "safe_to_autofix": true,
      "autofix_kind": "delete-file",
      "files": ["shared/helpers_old.py"],
      "rationale": "0 grep refs in repo, no __main__, last touched 2025-12-01",
      "rollback_command": "git revert <SHA>",
      "ask_user": null
    },
    {
      "id": "hygiene-orphan-doc-finance-v2-spec",
      "category": "orphan-docs",
      "severity": "low",
      "safe_to_autofix": false,
      "autofix_kind": null,
      "files": ["docs/finance-v2-spec.md"],
      "rationale": "Not referenced anywhere, but content looks active",
      "rollback_command": null,
      "ask_user": {
        "question_ru": "Документ docs/finance-v2-spec.md нигде не используется. Это старая спека (можно перенести в архив) или живой документ?",
        "options": ["archive", "keep", "delete"],
        "default_after_7d": "archive"
      }
    }
  ],
  "summary": {
    "total": 12,
    "safe_to_autofix": 9,
    "needs_human": 3,
    "categories": {
      "orphan-imports": 4,
      "orphan-docs": 3,
      "skill-registry-drift": 2,
      "broken-doc-links": 3
    }
  }
}
```

**Категории `category`** (whitelisted, расширяется по мере фаз):
- `orphan-imports`, `orphan-docs`, `skill-registry-drift`, `broken-doc-links`, `cross-platform-skill-prep`, `structure-conventions` — из Phase 0
- `lint-error`, `type-error`, `dead-code`, `unused-dep` — из Phase 2
- `coverage-drop`, `missing-test` — из Phase 3

**Severity:** `low` / `medium` / `high` / `critical`. Critical = блокирует ночной merge независимо от safe_to_autofix.

### 3.2 Code-quality report

`.hygiene/reports/code-quality-YYYY-MM-DD.json`

```json
{
  "$schema": "https://wookiee.shop/schemas/code-quality-report-v1.json",
  "version": "1.0.0",
  "run_id": "code-quality-2026-05-14-0330-utc",
  "tools": {
    "ruff": {"version": "0.5.x", "exit_code": 1, "errors": 14},
    "mypy": {"version": "1.10.x", "exit_code": 1, "errors": 3},
    "vulture": {"version": "2.x", "exit_code": 0, "candidates": 7},
    "pip-deptree": {"version": "2.x", "unused": 2}
  },
  "findings": [
    {
      "id": "ruff-E501-shared-data-layer-line-203",
      "category": "lint-error",
      "tool": "ruff",
      "rule": "E501",
      "severity": "low",
      "safe_to_autofix": true,
      "autofix_kind": "ruff-fix",
      "files": ["shared/data_layer.py"],
      "line": 203,
      "codex_confidence": null,
      "rollback_command": "git revert <SHA>",
      "ask_user": null
    },
    {
      "id": "vulture-dead-fn-services-old-aggregator-compute",
      "category": "dead-code",
      "tool": "vulture",
      "severity": "medium",
      "safe_to_autofix": false,
      "codex_confidence": 0.72,
      "codex_verdict": "likely-dead-but-imported-dynamically",
      "files": ["services/old_aggregator.py"],
      "rationale_from_codex": "Function is referenced via getattr() in services/dispatcher.py line 88",
      "ask_user": {
        "question_ru": "Функция compute() в services/old_aggregator.py выглядит как мёртвый код, но вызывается через getattr — это ломает её безопасное удаление. Удалить и проверить, или оставить как есть?",
        "options": ["delete", "keep"],
        "default_after_7d": "keep"
      }
    }
  ],
  "codex_calls": {
    "total": 18,
    "high_confidence_auto": 11,
    "ambiguous_queued": 5,
    "low_confidence_discarded": 2,
    "total_tokens_in": 42000,
    "total_tokens_out": 8500
  },
  "summary": {
    "total": 24,
    "safe_to_autofix": 11,
    "needs_human": 5,
    "discarded": 8
  }
}
```

**Codex confidence buckets:**
- `>= 0.90` → `safe_to_autofix: true` (auto)
- `0.60 .. 0.90` → `safe_to_autofix: false`, queue для `/hygiene-resolve`
- `< 0.60` → discard, не попадает в отчёт, но логируется в `.hygiene/codex_logs/`

### 3.3 Queue items

`.hygiene/queue.yaml`

```yaml
# Persistent queue of NEEDS_HUMAN findings awaiting /hygiene-resolve.
# Auto-expires items > 7 days old (default: skip + log).
version: 1
items:
  - id: hygiene-orphan-doc-finance-v2-spec
    source_report: .hygiene/reports/hygiene-2026-05-14.json
    enqueued_at: "2026-05-14T04:00:00Z"
    expires_at: "2026-05-21T04:00:00Z"
    category: orphan-docs
    files: ["docs/finance-v2-spec.md"]
    question_ru: "Документ docs/finance-v2-spec.md нигде не используется. Это старая спека или живой документ?"
    options: ["archive", "keep", "delete"]
    default_after_7d: archive
    times_surfaced: 1
    last_surfaced_at: "2026-05-14T04:00:00Z"
```

### 3.4 Decisions memory

`.hygiene/decisions.yaml` — persistent. Никогда не очищается автоматически.

```yaml
# Past human decisions. Night-coordinator consults this BEFORE queuing a new finding.
# If a finding pattern matches a decision (same category + same file glob), reuse it.
version: 1
decisions:
  - decision_id: dec-2026-05-09-finance-v2-archive
    decided_at: "2026-05-09T10:24:00Z"
    decided_by: "owner-via-hygiene-resolve"
    category: orphan-docs
    file_glob: "docs/finance-v2-*.md"
    answer: archive
    rationale_ru: "Финансовая спека v2 заменена v3 в марте, можно архивировать"
    expires_at: null  # never expires
  - decision_id: dec-2026-05-12-deptree-pyyaml-keep
    decided_at: "2026-05-12T08:01:00Z"
    decided_by: "owner-via-hygiene-resolve"
    category: unused-dep
    file_glob: "requirements*.txt"
    pattern: "pyyaml"
    answer: keep
    rationale_ru: "Используется в скриптах через yaml.safe_load — vulture не видит"
```

### 3.5 Config

`.hygiene/config.yaml`

```yaml
version: 1

# Master kill-switch. First week of life: true (no PRs, just JSON + Telegram).
# Owner flips to false manually after calibration.
read_only: true

# Thresholds.
coverage_min_pct: 60        # block merge if test coverage drops below this
codex_confidence_auto: 0.90 # >= → auto-fix
codex_confidence_queue: 0.60 # >= → queue, < → discard

# Auto-expire.
queue_expire_days: 7
reports_retention_days: 30

# Heartbeat.
heartbeat_enabled: true
heartbeat_quiet_if_zero: true  # don't send if 0 findings 0 fixes

# Token budgets per skill (hard cap; exceeding → fail + Telegram alert).
token_budgets:
  hygiene: 150000
  code_quality_scan: 250000      # codex sidecar adds up
  test_coverage_check: 50000
  night_coordinator: 100000
  heartbeat: 20000

# Telegram destination (chat_id only; token from env).
telegram:
  chat_id_env: HYGIENE_TELEGRAM_CHAT_ID
  bot_token_env: TELEGRAM_ALERTS_BOT_TOKEN

# Workflow Guard interaction.
pr:
  base_branch: main
  branch_prefix: night-devops/
  auto_merge: true
  merge_method: squash
```

---

## 4. Supabase schema

### 4.1 Table: `fix_log`

Миграция `database/sku/migrations/014_fix_log.sql`. RLS включён, `anon` блокируется, доступ только `service_role`.

```sql
CREATE TABLE IF NOT EXISTS public.fix_log (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  run_id TEXT NOT NULL,                    -- e.g. "night-coordinator-2026-05-14-0400-utc"
  agent TEXT NOT NULL,                     -- "hygiene-autofix" | "code-quality-scan" | "night-coordinator"
  finding_id TEXT NOT NULL,                -- matches finding.id in JSON reports
  category TEXT NOT NULL,                  -- orphan-imports | lint-error | dead-code | ...
  severity TEXT NOT NULL,                  -- low | medium | high | critical
  files_changed JSONB NOT NULL,            -- ["shared/helpers_old.py", ...]
  commit_sha TEXT NOT NULL,                -- the commit that applied the fix
  pr_number INTEGER,                       -- linked PR
  rollback_command TEXT NOT NULL,          -- e.g. "git revert abc123"
  rollback_verified BOOLEAN NOT NULL DEFAULT FALSE, -- CI test sets this true
  rolled_back_at TIMESTAMPTZ,
  rolled_back_reason TEXT,
  metadata JSONB                           -- free-form: codex_confidence, token_usage, etc.
);

CREATE INDEX idx_fix_log_run_id ON public.fix_log (run_id);
CREATE INDEX idx_fix_log_finding_id ON public.fix_log (finding_id);
CREATE INDEX idx_fix_log_occurred_at ON public.fix_log (occurred_at DESC);
CREATE INDEX idx_fix_log_rolled_back ON public.fix_log (rolled_back_at) WHERE rolled_back_at IS NOT NULL;

ALTER TABLE public.fix_log ENABLE ROW LEVEL SECURITY;

-- Only service_role writes. Anon completely blocked.
CREATE POLICY fix_log_service_role_all ON public.fix_log
  FOR ALL TO service_role USING (true) WITH CHECK (true);

REVOKE ALL ON public.fix_log FROM anon, authenticated;
```

### 4.2 Запись

`scripts/nightly/supabase_fix_log.py` — функция `log_fix(finding, commit_sha, pr_number, rollback_command, metadata)`. Вызывается **после успешного коммита** в night-coordinator. Подключение — через существующий `shared/data_layer.py` (Supabase service role, см. CLAUDE.md).

### 4.3 Rollback verification

Отдельный CI job (`test-coverage-check.yml` step «rollback_verify»):

```python
# scripts/nightly/rollback_check.py
# For each fix_log row in last 24h where rollback_verified=false:
#   1. Check rollback_command parses cleanly (must start with `git revert ` or `git restore `)
#   2. In a sandbox clone, run the command. Verify exit 0.
#   3. Verify HEAD diff includes the files in files_changed.
#   4. Set rollback_verified=true.
# Fail job (and Telegram alert) if ANY row fails to verify.
```

Это гарантирует: каждое изменение, которое ночной агент применил, **обратимо одной командой**, и это **проверено в CI**, а не на честном слове.

---

## 5. Telegram message format

Бот: **@wookiee_alerts_bot** (`TELEGRAM_ALERTS_BOT_TOKEN`). Новый бот не создаём. Просто добавляем шаблоны в `scripts/nightly/telegram_render.py`.

Тон: простой русский, бытовые аналогии, я-сам-решил, короткие предложения. Никаких emoji-смайликов.

### 5.1 Случай: 0 NEEDS_HUMAN, всё починилось само (heartbeat only)

```
[wookiee night] 14 мая, ночь спокойная

За ночь нашёл 12 мелочей, починил все сам. Открыл 1 PR — он уже зелёный и автоматически смерджится.

Чинил: 4 неиспользуемых импорта, 3 ссылки на старые доки, 5 lint-замечаний.

Ничего от тебя не нужно.
```

(Если `heartbeat_quiet_if_zero: true` и **ноль** находок и **ноль** фиксов — Telegram вообще молчит.)

### 5.2 Случай: 1 NEEDS_HUMAN

```
[wookiee night] 14 мая — 1 вопрос на твоё решение

Большую часть починил сам (11 штук — PR #234 уже зелёный, замерджится автоматом).

Но осталась одна штука, где я не уверен и не хочу гадать:

— Документ docs/finance-v2-spec.md лежит в репо, но нигде на него ссылок нет. Это старая спека (можно унести в архив) или живой документ, который ты ещё открываешь?

Если хочешь решить сейчас — открой Claude Code и вставь:

  /hygiene-resolve

Я задам тот же вопрос голосом и сделаю что скажешь. Если не ответишь — через 7 дней сам унесу в архив, это безопасный дефолт.
```

### 5.3 Случай: 3 NEEDS_HUMAN

```
[wookiee night] 14 мая — 3 вопроса на твоё решение

Большую часть починил сам (18 штук — PR #235 уже зелёный, замерджится автоматом).

Осталось 3 штуки, где нужна твоя голова:

1) Документ docs/finance-v2-spec.md ни на что не ссылается. Архив или оставить?
2) Функция compute() в services/old_aggregator.py выглядит мёртвой, но её зовут хитро (через getattr). Удалить и проверить, или оставить?
3) В requirements.txt есть пакет httpx — pip-deptree говорит, что он нигде не используется. Удалить или оставить (вдруг где-то нужен)?

Все три можно решить разом одной командой. Открой Claude Code и вставь:

  /hygiene-resolve

Я задам эти три вопроса по очереди простым языком. Если не ответишь — через 7 дней применю безопасные дефолты (архив / оставить / оставить).
```

### 5.4 Случай: many (>5) NEEDS_HUMAN

```
[wookiee night] 14 мая — накопилось 8 вопросов

Большую часть починил сам (24 штуки — PR #236 уже зелёный).

Но за тобой накопилось 8 вопросов (3 свежих за эту ночь + 5 в очереди с прошлых дней). Это много — лучше разобрать.

Открой Claude Code и вставь:

  /hygiene-resolve

Я пройдусь по всем восьми по очереди, простым языком, 2–3 минуты твоего времени. Если останется хвост — через 7 дней применю безопасные дефолты, ничего не сломаю.

Самые горькие (которые точно стоит решить):
  • Удалить ли services/old_aggregator.py (мёртвый код, но getattr-зависимости)
  • Снести 4 черновика отчётов в docs/drafts/ (последний touch 3 мес назад)
```

### 5.5 Случай: ошибка ночного агента (failure mode)

```
[wookiee night] 14 мая — ночной агент сломался

Один из ночных job-ов упал. PR не создан, фиксы не применены.

Что упало: code-quality-scan (превысил лимит токенов 250k, не успел доехать до конца)
Лог: https://github.com/danila-matveev/Wookiee/actions/runs/<RUN_ID>

Это не страшно — состояние репо не тронуто. Завтра попробую ещё раз с тем же бюджетом.

Если такое будет повторяться 3 ночи подряд — приходи разбираться, что-то фундаментально съезжает.
```

### 5.6 Heartbeat (05:00 UTC, отдельное сообщение)

Если `heartbeat_quiet_if_zero: true` и за день ноль активности — молчит. Иначе:

```
[wookiee night] Сводка за 14 мая

PR #235 — смерджился в 04:12, всё ок.
Починил: 11 мелочей (4 импорта, 3 доки, 4 lint).
Залогировал в Supabase fix_log, каждый фикс откатывается одной командой.

Очередь на твоё решение: 1 вопрос (см. сообщение в 04:00).
```

### 5.7 Реализация renderer

`scripts/nightly/telegram_render.py`:

```python
def render_digest(
    pr_number: int | None,
    safe_fixes_count: int,
    needs_human: list[QueueItem],
    queue_carryover: list[QueueItem],
    failure: FailureInfo | None,
    config: HygieneConfig,
) -> str:
    """Returns plain Russian message. No HTML, no Markdown — plain text only."""
    ...
```

Тон-чеклист (validator в той же функции):
- Нет английских терминов кроме `PR`, `Claude Code`, `getattr`, имена файлов
- Нет emoji
- Нет «обращаемся к вашему вниманию» — простые короткие предложения
- В конце — копипаст-команда, если нужна
- Дефолт-after-7d упомянут, если есть NEEDS_HUMAN

---

## 6. Workflow Guard interaction

### 6.1 Как PR создаётся и мерджится

Все 4 источника фиксов идут в **одну ветку** `night-devops/YYYY-MM-DD`. Branch создаётся в `night-coordinator`:

```bash
git checkout -b night-devops/$(date -u +%Y-%m-%d) origin/main
# ... apply fixes (commits per category) ...
git push origin night-devops/$(date -u +%Y-%m-%d)

gh pr create \
  --base main \
  --head night-devops/2026-05-14 \
  --title "night-devops: 14 мая — 11 авто-фиксов" \
  --body-file /tmp/pr_body.md

gh pr merge --auto --squash <PR_NUMBER>
```

`--auto` означает: GitHub **сам** смерджит PR, как только пройдут все required checks (CI + любые branch protection rules). Это полностью совместимо с Workflow Guard: ruleset `12853246` требует «PR required + quality CI + linear history» — а ночной агент именно так и работает.

### 6.2 Что НЕ делаем

- ❌ `git push origin main` напрямую — заблокировано pre-push hook
- ❌ `--no-verify`, `--no-gpg-sign`, force-push — нет, ruleset запрещает
- ❌ `gh pr merge --admin` — обход CI, нет
- ❌ Self-approve PR от имени бота как owner — нет

### 6.3 Что делаем

- ✅ `gh pr create` с ветки `night-devops/*`
- ✅ `gh pr merge --auto` — GitHub дождётся CI и сам смерджит
- ✅ Если CI красный — PR останется открытым, никакого мерджа. Бот получает webhook (или мы видим на heartbeat следующее утро) и Telegram-алертит «вчерашний PR не смерджился, CI красный»
- ✅ Token: `secrets.GITHUB_TOKEN` (для action) или PAT с `repo` scope (для cross-repo case). См. `feedback_mcp_secrets_pattern.md`

### 6.4 Failure recovery

Если PR не смерджился за 12 часов после открытия:
- night-coordinator на следующую ночь видит «вчерашний PR ещё открыт»
- Не открывает новый PR, докидывает свежие фиксы в ту же ветку
- Telegram alert: «вчерашний PR висит без merge, посмотри почему»

---

## 7. Read-only mode

`.hygiene/config.yaml` → `read_only: true` (дефолт первой недели).

**В read-only режиме:**
- ✅ `/hygiene` пишет JSON в `.hygiene/reports/`
- ✅ `/code-quality-scan` пишет JSON
- ✅ `/test-coverage-check` пишет JSON
- ✅ `/night-coordinator` строит план PR-а, рендерит Telegram-дайджест в **dry-run mode**
- ✅ Telegram сообщение приходит с пометкой `[read-only mode]` в первой строке
- ❌ `gh pr create` — **не вызывается**
- ❌ `git push` — **не вызывается** (JSON-отчёты коммитятся в служебную ветку `night-devops/reports-only-YYYY-MM-DD` и пушатся туда, но **PR не открывается**)

После 7 ночей в read-only владелец смотрит:
- Сколько мелочей агент находит за ночь (ожидание: 5–25)
- Сколько NEEDS_HUMAN в среднем (ожидание: 1–3)
- Соответствует ли digest реальности

Если ок — флипает `read_only: false` коммитом в `.hygiene/config.yaml`. С этой ночи агент сам открывает PR.

### 7.1 Telegram preview in read-only

```
[wookiee night] [read-only mode] 14 мая — предпросмотр

Если бы был не read-only, я бы:
  • Открыл PR с 11 авто-фиксами (4 импорта, 3 доки, 4 lint)
  • Задал тебе 1 вопрос (про docs/finance-v2-spec.md)

Сейчас просто показываю, что бы я сделал. Реальный PR не создан.

Если калибровка устраивает — выключи read-only:
  открой .hygiene/config.yaml и поставь read_only: false
```

---

## 8. Auto-expire logic

Queue items (`.hygiene/queue.yaml`) старше 7 дней (`queue_expire_days: 7`) автоматически применяют `default_after_7d` ответ.

Логика в `scripts/nightly/queue_ops.py`:

```python
def expire_old_items(queue: Queue, now: datetime) -> list[ExpiredItem]:
    expired = []
    for item in queue.items:
        age_days = (now - item.enqueued_at).days
        if age_days >= queue.config.queue_expire_days:
            apply_default(item)  # write to decisions.yaml as decided_by="auto-expire"
            log_to_fix_log(item, agent="night-coordinator", metadata={"expired": True})
            expired.append(item)
    return expired
```

Действие, которое выполнится на expire:
- Если `default_after_7d: archive` → файл уезжает в `docs/_archive/YYYY-MM/`
- Если `default_after_7d: keep` → ничего не делаем, но финдинг помечается как «решено: оставить», и больше не всплывает
- Если `default_after_7d: skip` → ничего не делаем, но finding закрыт (на случай если повторится — снова появится с новым id)

Telegram-сообщение в день expiry:

```
[wookiee night] 14 мая — применил безопасные дефолты по очереди

2 вопроса висели в очереди дольше 7 дней. Применил безопасные дефолты:

  • docs/finance-v2-spec.md → перенёс в docs/_archive/2026-05/ (это был дефолт «archive»)
  • requirements.txt → оставил httpx как есть (дефолт «keep»)

Оба зафиксированы в decisions.yaml. Если что — откатывается одной командой, см. fix_log в Supabase.
```

---

## 9. Token budgets

Hard caps определены в `.hygiene/config.yaml` (см. §3.5). Энфорсятся в каждом skill-е через переменную окружения `CLAUDE_TOKEN_BUDGET=<N>` и проверку накопления.

| Skill | Budget | На что |
|---|---|---|
| `/hygiene` | 150k | 7-phase flow, существующий бюджет уже работает |
| `/code-quality-scan` | 250k | ruff/mypy/vulture сами по себе токенов не жрут, основной бюджет — Codex sidecar (по 5–15k на ambiguous finding × ~10–20 findings/ночь) |
| `/test-coverage-check` | 50k | в основном computer-tool, мало LLM |
| `/night-coordinator` | 100k | merge planning + Telegram digest render + PR body |
| `/heartbeat` | 20k | одно короткое сообщение |

**На overrun:**

1. Skill ловит `BudgetExceededError` (свой custom error)
2. Записывает partial JSON-отчёт с флагом `"truncated": true` и `"reason": "token_budget_exceeded"`
3. Отправляет Telegram-алерт (см. §5.5)
4. Завершает job с exit 1

`/night-coordinator` ловит флаг `truncated` в любом из входных JSON и:
- Не открывает PR (даже если есть SAFE-фиксы) — это страховка от частичной работы
- Telegram: «вчерашний агент не доехал, повторим сегодня ночью»

---

## 10. Failure modes and recovery

Каждый из 5 cron jobs обрабатывает свои отказы. **Silent fail запрещён.** Любая ошибка → Telegram + exit 1 + GitHub Actions «failed» status.

| Job | Failure mode | Recovery |
|---|---|---|
| `03:00 hygiene` | Token budget exceeded | Partial JSON commit, Telegram alert, next 04:00 ничего не делает |
| | jsonschema validation fail на output | Job fail, Telegram «hygiene выдал невалидный JSON», 04:00 видит отсутствие файла → skip |
| | Workflow Guard smoke-test fail | Telegram «хуки сломаны», но job продолжает (как сейчас) |
| `03:30 code-quality` | ruff/mypy не нашёл `python` | Job fail, Telegram «окружение сломано» |
| | Codex CLI не отвечает (rate limit / network) | Job помечает все ambiguous как «discard» с reason, продолжает |
| | Codex auth expired | Telegram alert «codex auth протух, обнови `~/.codex/auth.json`», job fail |
| `04:00 night-coordinator` | Любой входной JSON отсутствует | Skip того источника, продолжает с тем что есть, Telegram «не было JSON от X» |
| | Все 2 источника отсутствуют | Job fail, Telegram «оба источника молчат — что-то фундаментально съехало» |
| | `gh pr create` fail | Telegram alert, job fail, не пытается ещё раз (на следующую ночь — новая попытка) |
| | Push fail (Workflow Guard сработал — не должно случиться, но мало ли) | Telegram «Workflow Guard заблокировал push — это бага в дизайне, разобраться» |
| `04:30 coverage-check` | coverage упал ниже порога | PR помечается как «do not merge» через `gh pr edit --add-label do-not-merge`, Telegram alert |
| | Rollback verification fail для какой-то записи fix_log | Telegram alert «фикс N необратим, посмотри», запись помечается `rollback_verified: false` |
| `05:00 heartbeat` | Supabase недоступна | Heartbeat шлёт «не смог прочитать историю», но это soft fail, не критично |

---

## 11. Concurrency

Все 5 workflow-файлов:

```yaml
concurrency:
  group: night-devops
  cancel-in-progress: false
```

**Эффект:**
- Только один job из 5 может бежать одновременно
- Если предыдущий ещё не закончился, новый ждёт
- Ничего не отменяется (`cancel-in-progress: false`) — нам важно дотянуть hygiene до конца, даже если coordinator уже хочет стартовать

**Cron timing — почему такие зазоры:**
- 03:00 → 03:30 — hygiene обычно 15–25 мин, запас 5–15 мин
- 03:30 → 04:00 — code-quality + codex sidecar обычно 20–25 мин, запас 5 мин
- 04:00 → 04:30 — coordinator 10–15 мин (он быстрый, в основном чтение JSON)
- 04:30 → 05:00 — coverage 10–20 мин
- 05:00 → конец — heartbeat 1–2 мин

Если что-то затянулось — следующий job просто подождёт. Это нормально.

---

## 12. Codex CLI sidecar (Phase 2)

### 12.1 Когда и зачем вызываем

В `/code-quality-scan`, для каждого finding, который `vulture` / `mypy` пометили как «возможно проблема, но не уверен». Это:
- Vulture-кандидат на dead code, который **где-то импортируется** (нужно решить: реально мёртвый или dynamic dispatch)
- mypy `unreachable` warning, который может быть false-positive
- ruff `unused-argument` в overridden method (часто false-positive)

Cases, где Codex **не нужен**:
- Чистые lint-fix (E501, trailing whitespace) → ruff сам чинит, никакого LLM
- mypy hard error «no attribute X on Y» — это не ambiguity, это либо чинится механически, либо ask_user

### 12.2 Вызов

```bash
codex exec \
  --output-format json \
  --max-tokens 8000 \
  --prompt-file /tmp/codex_prompt_finding_<ID>.md
```

OAuth-токен в `~/.codex/auth.json` — пробрасывается в GitHub Actions через secrets: secret `CODEX_AUTH_JSON` → step «write `~/.codex/auth.json`».

### 12.3 Prompt template

`.claude/skills/code-quality-scan/prompts/codex_arbiter.md`:

```markdown
You are a code reviewer. You receive:
1. A `finding` object describing a code-quality concern (dead code, etc.)
2. The relevant code snippet + context (3 surrounding files, grep results)
3. Project conventions from CLAUDE.md / AGENTS.md (key rules only)

Your task: return ONE JSON object with these fields:

{
  "verdict": "safe-to-autofix" | "needs-human" | "discard",
  "confidence": 0.0-1.0,
  "rationale_ru": "<one paragraph in Russian, plain language>",
  "ask_user_question_ru": "<if needs-human: a clear yes/no or 2-option question in Russian>",
  "suggested_default": "<one of the options>",
  "autofix_diff": "<if safe-to-autofix: unified diff>"
}

Rules:
- Confidence >= 0.90 only if you are highly certain a fix is safe AND reversible
- Confidence < 0.60 → discard (we won't bother the human)
- 0.60..0.90 → needs-human, queue
- Never invent context. If you don't have enough info, lower confidence.
```

### 12.4 Confidence calibration

Первые 4 недели — все Codex verdicts логируются в `.hygiene/codex_logs/`, владелец вручную (через `/hygiene-resolve`) видит «Codex сказал 0.85, ты ответил X». Из этого можно потом откалибровать пороги (например, поднять auto-cutoff до 0.95, если 0.90–0.95 часто ошибается).

---

## 13. Phase 4 — interface only (NOT implemented)

Phase 4 — autonomous refactoring via Codex. **Не строим.** Но резервируем хуки.

### 13.1 Что собираем в Phases 0–3, чтобы Phase 4 можно было задизайнить грамотно

В каждой ночной записи `coordinator-YYYY-MM-DD.json`:

```json
{
  "phase4_signals": {
    "duplicate_code_blocks": 12,
    "files_with_high_cyclomatic": ["services/x.py", "agents/y.py"],
    "dead_code_candidates": 7,
    "unused_deps": 2,
    "test_coverage_gaps": [
      {"file": "shared/data_layer.py", "uncovered_lines": 23}
    ],
    "ambiguous_codex_verdicts_count": 5
  }
}
```

Через 30 ночей у нас будет 30 таких records → можно строить тренды:
- Растёт ли дублирование?
- Какие файлы стабильно «горячие»?
- Где Codex чаще всего нечёткий — там и нужен Phase 4 refactor

### 13.2 Зарезервированные интерфейсы

В `night-coordinator/SKILL.md` (Phase 0) уже есть placeholder-секция:

```markdown
## Phase 4 hook (not implemented)

If `.hygiene/config.yaml` has `phase4.enabled: true` (default: false):
  1. Read all coordinator-*.json from last 30 days
  2. Run `/codex-refactor` skill (already exists in repo) on top-3 hottest files
  3. Codex produces a refactor PR — but it goes through SAME night PR pipeline
     (single PR, auto-merge if CI green, queue if ambiguous)
  4. Refactor PRs are tagged `phase4-refactor` for easy filter

For now (Phase 0-3), this section is a no-op.
```

### 13.3 Чего НЕ делаем сейчас

- Не пишем код для phase4 hook (только пустая ветка `if config.phase4.enabled` → `return`)
- Не строим refactor strategy
- Не интегрируем `codex-refactor` skill (он существует, но мы его не зовём)

---

## 14. Implementation waves — параллельный план для 5 sub-agent-ов

Sub-agent-ы строят параллельно. Каждая Wave — самостоятельная единица. Между waves — sync point.

### Wave A — Phase 0 foundation (3 sub-agents параллельно)

**A1: «Hygiene-autofix restore + JSON output» (1 sub-agent)**
- Восстановить файлы из коммита `b7f68430` через `git fetch origin b7f68430...`
- Создать `.claude/skills/hygiene-autofix/` (SKILL.md, README, prompts/)
- Создать `.cursor/skills/hygiene-autofix/` и `.codex/skills/hygiene-autofix/` mirrors
- Адаптировать: skill теперь пишет JSON в `.hygiene/reports/`, не открывает PR

**A2: «Hygiene workflow modification + config/decisions» (1 sub-agent)**
- Модифицировать `.github/workflows/hygiene-daily.yml`: убрать «open PR» steps, добавить «emit JSON»
- Создать `.hygiene/config.yaml` (с `read_only: true`)
- Создать `.hygiene/decisions.yaml` (пустой со схемой)
- Создать `scripts/nightly/__init__.py`, `report_schema.py`, `decisions_ops.py`
- Модифицировать `.claude/skills/hygiene/SKILL.md` — добавить `--emit-json` режим

**A3: «Night-coordinator + heartbeat scaffold» (1 sub-agent)**
- Создать `.claude/skills/night-coordinator/` (SKILL.md, prompts)
- Создать `.claude/skills/heartbeat/SKILL.md`
- Создать `.github/workflows/night-coordinator.yml` и `heartbeat.yml`
- В этой Wave coordinator только **читает** JSON и шлёт Telegram (PR-открытие в Wave C)
- Создать `scripts/nightly/telegram_render.py` (Russian renderer)

**Sync point Wave A:** все 3 файла в `.hygiene/reports/` появляются ночью, Telegram-digest приходит на простом русском в read-only режиме. PR не создаётся.

### Wave B — Phase 1 interactive resolve (1 sub-agent, serial after A)

- Создать `.claude/skills/hygiene-resolve/` — interactive local skill
- Создать `scripts/nightly/queue_ops.py` (enqueue/dequeue/expire)
- Создать `.hygiene/queue.yaml` initial empty
- Расширить `telegram_render.py` — все 5 шаблонов (§5)
- Тестовый flow: положить в queue.yaml 2 искусственных finding-а, запустить `/hygiene-resolve` локально, ответить, увидеть запись в `decisions.yaml`

### Wave C — Phase 0 PR pipeline (1 sub-agent, serial after A+B)

- Расширить `night-coordinator` — теперь умеет создавать PR через `gh pr create` + `gh pr merge --auto`
- Добавить permission в `.claude/settings.json` (вручную — fs-firewall блокирует правку Claude'м)
- Раздел в `AGENTS.md` про ночной агент и read-only
- Тест: вручную флипнуть `read_only: false` в test branch, прогнать coordinator, увидеть PR

### Wave D — Phase 2 code quality (2 sub-agents параллельно после C)

**D1: «Code-quality skill + tooling»**
- Создать `.claude/skills/code-quality-scan/SKILL.md` + prompts/runners.md
- Реализовать wrapper-вызовы ruff/mypy/vulture/pip-deptree
- Создать `.github/workflows/code-quality-daily.yml`

**D2: «Codex sidecar integration»**
- Реализовать `codex exec` интеграцию
- Реализовать `.claude/skills/code-quality-scan/prompts/codex_arbiter.md`
- Реализовать сохранение logs в `.hygiene/codex_logs/`
- GitHub Actions secret `CODEX_AUTH_JSON` → step «write `~/.codex/auth.json`»

**Sync point Wave D:** code-quality JSON появляется в `.hygiene/reports/` каждую ночь, coordinator его читает.

### Wave E — Phase 3 coverage + rollback verify + Supabase (2 sub-agents)

**E1: «Coverage skill + workflow»**
- Создать `.claude/skills/test-coverage-check/SKILL.md`
- Создать `.github/workflows/test-coverage-check.yml`
- Реализовать gate logic (block merge на падение покрытия)

**E2: «Supabase fix_log + rollback verifier»**
- Создать миграцию `database/sku/migrations/014_fix_log.sql`
- Применить через Supabase MCP
- Создать `scripts/nightly/supabase_fix_log.py`
- Создать `scripts/nightly/rollback_check.py`
- Интегрировать вызов rollback_check в coverage workflow

**Sync point Wave E:** rollback test зелёный, fix_log заполняется, coverage gate работает.

### Final readiness gate

Перед флипом `read_only: false`:
- 7 ночей подряд в read-only без crash-ов
- Telegram digest читается как «нормальный человеческий текст» (subjective check)
- Никаких schema-validation fails в логах
- В fix_log есть хотя бы 1 запись с `rollback_verified: true`

---

## 15. Failure budget и kill switches

### 15.1 Kill switches (по убыванию radius)

1. **Полный стоп:** `.hygiene/config.yaml` → `read_only: true`. PR-открытие отключается, JSON всё ещё пишется. Можно делать commit прямо в main через гарду (PR на изменение конфига).
2. **Heartbeat off:** `heartbeat_enabled: false` — никаких 05:00-сообщений.
3. **Disable workflow:** в GitHub UI «Disable workflow» для нужного `.yml`-файла. На уровне Actions.
4. **Удалить cron schedule:** PR, удаляющий `schedule:` block. Workflow остаётся, но не запускается автоматически.
5. **Удалить весь pipeline:** revert PR-а с этим планом (см. Wave A onwards).

### 15.2 Что владелец видит, когда что-то не так

- Каждая ошибка → Telegram alert (см. §5.5, §10)
- 3 ночи подряд с failure → escalation message «приходи разбираться»
- Если Telegram alerts вдруг замолчали — heartbeat 05:00 это покажет (т.к. он шлёт ежедневно если включён)

---

## 16. Что план НЕ покрывает (явно out of scope)

- Реальное написание кода ночного агента (это план, не реализация)
- Тест на сервере (вся работа — в GitHub Actions, локально и в репо)
- Метрики latency / cost dashboards (можно добавить в Phase 4 при необходимости)
- Многоязычность Telegram (только русский, владелец один)
- Web dashboard для просмотра findings (можно добавить в Hub позже, не сейчас)
- Интеграция с Bitrix / Notion (это про DevOps репо, не про бизнес-процессы)

---

## 17. Acceptance criteria (как проверить, что план достроен)

После выполнения всех Wave A–E:

1. ✅ За 7 ночей подряд (в read-only) приходит Telegram-digest, без crash-ов в Actions
2. ✅ `.hygiene/reports/*.json` все валидируются по JSON Schema
3. ✅ `/hygiene-resolve` локально читает `queue.yaml`, задаёт вопросы на русском, пишет в `decisions.yaml`
4. ✅ В Supabase `fix_log` есть >= 1 запись с `rollback_verified: true` (после реального ночного запуска не в read-only)
5. ✅ Workflow Guard ни разу не сработал на pre-push hook — потому что бот пушит только в feature ветки, не в main
6. ✅ Codex sidecar отрабатывает без вызова Anthropic/OpenAI API (только `codex exec` через подписку)
7. ✅ Auto-merge срабатывает: бот открыл PR, CI зелёный, в течение 15 минут после CI — PR смерджен
8. ✅ Heartbeat 05:00 шлёт корректное summary за день
9. ✅ Rollback test зелёный — каждая запись fix_log реально откатывается
10. ✅ Token budget превышение → graceful fail + Telegram alert + следующая ночь работает как обычно

---

## 18. Открытые вопросы (на этап исполнения)

Эти вопросы НЕ блокируют start, но нужно ответить во время Wave A:

1. **Branch protection rules:** ruleset `12853246` требует `linear history`. `gh pr merge --squash` совместим? Проверить.
2. **Coverage tool:** `coverage.py` vs `pytest-cov`. Что уже в `requirements*.txt`? Если ничего — выбрать самый лёгкий вариант.
3. **Vulture false-positive rate:** на текущем codebase ожидаемо ~30%. Это значит Codex sidecar будет звать `vulture-candidates × ~30%` × 8k токенов. Уложимся в 250k budget или нет — узнаем после первого реального запуска.
4. **`.hygiene/decisions.yaml` rotation:** растёт линейно. Через год — ~365 entries. Это ок? Если станет тяжёлым — можно архивировать ежеквартально.
5. **Cloudflare Pages preview для PR-body:** опционально — рендерить `coordinator-YYYY-MM-DD.json` как читаемую страничку и линковать в PR-body. Не блокирует, но nice-to-have.

---

## 19. Связанные документы и memory

- `project_workflow_guard.md` — как защита main работает, в каких случаях ломается
- `project_hygiene_skill.md` — текущий 7-phase flow
- `feedback_plain_language.md` — тон для Telegram
- `feedback_subscription_over_api.md` — почему Codex через OAuth, не API
- `feedback_hygiene_bot_design.md` — @wookiee_alerts_bot, не плодим новые боты
- `feedback_bot_creation_pattern.md` — если когда-то понадобится child-bot
- `feedback_mcp_secrets_pattern.md` — секреты только через wrapper/env
- `feedback_no_secrets_in_docs.md` — в плане нет ни одного реального токена
- `feedback_verify_before_done.md` — rollback test = postcondition verifier
- `feedback_no_editing_on_server.md` — всё в Actions, сервер deploy-only
- `feedback_thorough_analysis.md` — план должен быть детальным с первого прохода
- Commit `b7f68430688f8bc768e377b66556eaeee13c6cf8` — исходник `/hygiene-autofix` (Phase 0 restore)
- `.github/workflows/hygiene-daily.yml` — текущий 03:00 cron (модифицируется)
- `.github/workflows/hygiene-followup-daily.yml` — отдельный followup-pipeline (НЕ трогаем)
- `.github/workflows/ci.yml` — known pre-existing failures (НЕ трогаем)

---

## 20. Подпись

Этот документ — **источник истины** для 5 параллельных sub-agent-ов в Waves A–E.
Изменения в плане после старта Wave A — только через явный PR на этот же файл.

Финальная цель: после Wave E владелец просыпается утром, видит **одно** Telegram-сообщение, читает за 30 секунд, и либо ничего не делает (всё уже смерджено), либо вставляет `/hygiene-resolve` в Claude Code и за 2 минуты разбирает накопившиеся вопросы.
