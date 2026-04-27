# Wookiee — Hygiene Skill Design (Phase 2)

**Date:** 2026-04-27
**Status:** Draft — pending user approval
**Phase 1 reference:** `docs/superpowers/specs/2026-04-24-refactor-v3-design.md` (§7 — concept preview)
**Phase 1 outcome:** completed via PRs #51–#58 (closed in commit `889aeb9`).

---

## 1. Цель и Non-Goals

### Цель
Поддерживать репозиторий Wookiee в colleague-ready состоянии **без ручной работы**. Скилл `/hygiene` сам:
1. Пушит готовое (untracked файлы и локальные коммиты по white-list путям).
2. Удаляет явный мусор (бинарники, iCloud-дубликаты, `__pycache__`, пустые директории-сироты).
3. Наводит порядок в структуре и именах (отклонения от паттернов проекта → ask-user PR).
4. Синхронизирует артефакты (`docs/skills/<name>.md` ↔ `.claude/skills/<name>/SKILL.md`, `.gitignore`-violations, cross-platform skill setup через `/ecosystem-sync`).
5. Проверяет безопасность (lightweight tripwire — секреты в треке, `.env*` не утекли) и шлёт немедленный Telegram-alert при находке.
6. Сообщает о результате (Cloudflare-публикация + Telegram при ask-user/security).

### Non-Goals
- Не пишет тесты, не реализует фичи.
- Не модифицирует бизнес-логику в `shared/`, `services/*` (только их metadata: README, gitignore patterns).
- Не трогает `sku_database/` schema, `.env*`, branch protection, CI workflows.
- Не делает `force-push`, не отменяет чужие коммиты.
- Не запускает другие тяжёлые скиллы (`/finance-report`, `/marketing-report` и т.п.).
- Не пишет в глобальные скиллы `~/.claude/skills/` (только читает их для cross-platform-skill-prep).
- Полноценный security-аудит — отдельная работа (`gstack-cso`/`security-review`); hygiene делает только tripwire.

### Что значит «готов к коллегам»
- Main всегда зелёный (тесты + npm build).
- Untracked не висит дольше 24 часов (cron daily).
- Структура предсказуемая (отклонения от паттерна → ask-user).
- Никаких утечек секретов в трек.
- Все скиллы готовы к работе на других платформах (Codex CLI, Cursor, Antigravity).

---

## 2. Архитектура

### Стек
**Pure SKILL.md** (вариант A из brainstorm). Никакого Python orchestrator, никакого `scripts/hygiene/run.py`. Логика — в SKILL.md + prompts. Claude читает, гоняет git/grep команды, принимает решения, открывает PR.

Обоснование:
- Routines (`/schedule`) уже решают cron-вопрос — они запускают любой скилл по расписанию.
- 90% запусков вернут «нет drift» (короткий ответ, минимум токенов).
- LLM-decision на drift items даёт обучаемость — он подстраивается под паттерны проекта, а не следует hardcoded rules.
- Один файл легче поддерживать, чем Python + SKILL.md.

### Структура файлов
```
.claude/skills/hygiene/
  SKILL.md              ← главный документ: trigger, фазы, действия для Claude
  README.md             ← человеческое описание (заменяет placeholder из Phase 1)
  prompts/
    detect.md           ← scan: какие команды гонять, какие findings собирать
    classify.md         ← classify: какие findings auto-fix vs ask-user vs skip
    publish.md          ← шаблоны Cloudflare-статьи и Telegram-сообщения

.claude/hygiene-config.yaml    ← whitelist, пороги, defaults для checks (расширяется из placeholder Phase 1)
```

### Флоу одного запуска (ожидаемое время — 5 мин)
```
1. SCAN     → Bash-команды (git status, find, grep) собирают findings структурированно
2. CLASSIFY → Claude применяет config + правила: auto-fix | ask-user | skip
3. ACT
   ├─ auto-fix         → ветка chore/hygiene-YYYY-MM-DD → коммиты по группам
   ├─ ask-user         → отдельная секция в PR description "FOLLOW-UP NEEDED"
   └─ security-flag    → отдельный PR + Telegram alert немедленно
4. PR       → /pullrequest → Codex+Copilot review → auto-merge зелёных
5. PUBLISH  → /cloudflare-pub: статья "Hygiene Run YYYY-MM-DD"
              с findings, что сделано, что висит на ask-user
6. NOTIFY   → Telegram пинг ТОЛЬКО если ask-user > 0 ИЛИ security-flag
              (если только auto-fix → молча, ссылка в Cloudflare для ревью)
7. LOG      → tool_runs запись через shared/tool_logger
```

### Безопасность исполнения
**Защищённые зоны (никогда не писать):**
- `shared/**`
- `sku_database/**`
- `.env*` (любые .env файлы)
- `services/*/data/**`
- `.github/workflows/**`

**Read-only зоны:**
- `~/.claude/skills/` (глобальные скиллы — только для сравнения при `cross-platform-skill-prep`)

**Forbidden ops:**
- `git push --force` любого вида
- `git reset --hard origin/main`
- `gh pr close` чужих PR
- `rm -rf` любых tracked-файлов вне явного whitelist
- модификация branch protection / GitHub repo settings / CI workflows

---

## 3. Список checks

| # | Check | Что проверяет | Default action |
|---|---|---|---|
| 1 | `unpushed-work` | Локальные коммиты не запушены, untracked файлы по white-list путям | auto-commit + push |
| 2 | `stray-binaries` | `.xlsx/.pdf/.docx/.png/.wmv/.mov` вне whitelist | auto-delete |
| 3 | `icloud-dupes` | Файлы с « 2.» / « 3.» в имени | auto-delete |
| 4 | `pycache-committed` | `__pycache__/`, `.pytest_cache/` в треке | auto-untrack + add to gitignore |
| 5 | `gitignore-violations` | Файлы которые должны быть в gitignore | auto-ignore |
| 6 | `skill-registry-drift` | `.claude/skills/*` ≠ Supabase `tools` | auto-sync (insert/update в tools) |
| 7 | `cross-platform-skill-prep` | Новый/изменённый скилл без cross-platform setup | auto-sync через `/ecosystem-sync` |
| 8 | `empty-directories` | Пустые директории (residuals после удалений) | mixed: untracked → auto-delete, tracked-but-empty → ask-user |
| 9 | `orphan-imports` | Python модули с 0 импортами (60+ дней) | ask-user |
| 10 | `orphan-docs` | `.md` файлы без ссылок откуда-либо | ask-user |
| 11 | `broken-doc-links` | Битые внутренние ссылки в `.md` | ask-user |
| 12 | `missing-readme` | Новая директория `services/<X>/` без README | ask-user |
| 13 | `stale-branches` | Feature-ветки старше 14 дней без активности | ask-user (предложить close или продолжить) |
| 14 | `structure-conventions` | Отклонения от паттернов проекта (snake_case, расположение) | ask-user (LLM выводит паттерны автоматически) |
| 15 | `obsolete-tracked-files` | Tracked файлы без упоминаний 60+ дней | ask-user |
| 16 | `security-scan` | grep на секреты (API_KEY=, SECRET=, password=), `.env*` не трекается, `.env.example` имеет только плейсхолдеры | **flag immediate** + Telegram alert (не правит) |

**Принцип «правильно/неправильно»:** скилл **не диктует** свои конвенции, а **детектирует отклонения от паттернов проекта** через LLM-анализ существующего кода. Например, если 8 из 10 сервисов имеют структуру `services/X/{__init__.py, README.md, run.py}` — то 9-й сервис без этого помечается как drift.

---

## 4. Конфиг (`.claude/hygiene-config.yaml`)

```yaml
schedule:
  cron: "0 3 * * *"          # 03:00 UTC = 00:00 São Paulo (UTC-3)
  timezone: America/Sao_Paulo

cost_caps:
  soft_tokens: 50000          # мягкий потолок — log warning, продолжай
  hard_tokens: 150000         # жёсткий — abort + Telegram alert

protected_zones:
  never_modify:
    - shared/**
    - sku_database/**
    - .env*
    - services/*/data/**
    - .github/workflows/**

whitelist:
  binaries_keep:
    - services/logistics_audit/*Итоговый*.xlsx
    - services/logistics_audit/*final*.xlsx
    - services/logistics_audit/*Тарифы*.xlsx
    - docs/images/**

  unpushed_paths:           # пути, которые auto-commit делает без вопросов
    - docs/superpowers/plans/**
    - docs/superpowers/specs/**
    - docs/skills/**
    - docs/database/**

checks:
  unpushed_work: { default: auto_commit_push }
  stray_binaries: { default: auto_delete }
  icloud_dupes: { default: auto_delete }
  pycache_committed: { default: auto_untrack }
  gitignore_violations: { default: auto_ignore }
  skill_registry_drift: { default: auto_sync }
  cross_platform_skill_prep: { default: auto_sync, via: /ecosystem-sync }
  empty_directories: { default: mixed }
  orphan_imports: { default: ask_user }
  orphan_docs: { default: ask_user }
  broken_doc_links: { default: ask_user }
  missing_readme: { default: ask_user }
  stale_branches: { default: ask_user, threshold_days: 14 }
  structure_conventions: { default: ask_user }
  obsolete_tracked_files: { default: ask_user, no_reference_days: 60 }
  security_scan: { default: flag_immediate, telegram_alert: true }

notifications:
  cloudflare:
    always_publish: true       # каждый запуск = статья в Cloudflare
    title_format: "Hygiene Run {date} — {summary}"

  telegram:
    bot_env: HYGIENE_TELEGRAM_BOT_TOKEN
    chat_env: HYGIENE_TELEGRAM_CHAT_ID
    only_if_ask_user_or_security: true   # тихо, если только auto-fix
    message_format: |
      🧹 Hygiene {date}
      Auto-fixed: {auto_count}
      Needs review: {ask_count}
      Security flags: {security_count}

      Full report: {cloudflare_url}
      PR: {pr_url}
```

---

## 5. Notification format

### Cloudflare-статья (всегда, каждый запуск)
Заголовок: `Hygiene Run {YYYY-MM-DD} — {summary}` где summary = `clean` / `N auto-fixed` / `N ask-user` / `security flag`.

Структура статьи:
- **Summary:** счётчики по категориям, ссылка на PR.
- **Auto-fixed:** список изменений с путями и причинами.
- **Needs review:** список ask-user findings с обоснованием каждого.
- **Security flags:** найденные потенциальные утечки (если есть).
- **Stats:** время выполнения, токены, cron run #.

### Telegram (только при ask-user > 0 OR security flag)
Короткое сообщение со ссылкой на Cloudflare-страницу и PR. Никакого spam'а на пустые запуски.

### Supabase `tool_runs` (всегда)
Запись через `shared/tool_logger`:
- `tool_name`: `hygiene`
- `status`: `success` | `partial` | `failed`
- `metrics`: counts, tokens, duration
- `metadata`: cloudflare_url, pr_url

---

## 6. Setup

### 6.1 Pre-setup (вручную пользователь)
1. В Telegram открыть `@BotFather` → `/newbot`.
2. Имя: `Wookiee Hygiene Bot`, username: `@wookiee_hygiene_bot` (или другое на выбор пользователя).
3. Скопировать новый токен.
4. Получить chat_id — через `@userinfobot` в Telegram или curl `getUpdates` после `/start` боту.
5. Добавить в локальный `.env`:
   ```
   HYGIENE_TELEGRAM_BOT_TOKEN=...
   HYGIENE_TELEGRAM_CHAT_ID=...
   ```

### 6.2 Skill implementation (Claude делает)
1. `.claude/skills/hygiene/SKILL.md` — главный документ (фазы, действия).
2. `.claude/skills/hygiene/prompts/detect.md` — scan-инструкции.
3. `.claude/skills/hygiene/prompts/classify.md` — правила классификации.
4. `.claude/skills/hygiene/prompts/publish.md` — шаблоны Cloudflare/Telegram.
5. `.claude/skills/hygiene/README.md` — человеческое описание (заменяет placeholder из Phase 1).
6. `.claude/hygiene-config.yaml` — финальный конфиг (расширяет placeholder из Phase 1).
7. `.env.example` — добавить плейсхолдеры `HYGIENE_TELEGRAM_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`.

### 6.3 Routine setup (через `/schedule`)
- Routine name: `wookiee-hygiene-daily`
- Cron: `0 3 * * *` (UTC) = 00:00 São Paulo
- Action: запустить `/hygiene`

### 6.4 Регистрация в Supabase
- Через `/tool-register` создать запись в таблице `tools`:
  - `name`: `hygiene`
  - `type`: `maintenance`
  - `schedule`: `daily 00:00 BRT`
  - `description`: «Автоматическая гигиена репо: чистка мусора, push готового, sync скиллов, security tripwire, отчёт в Cloudflare + Telegram».

### 6.5 Verification (один тестовый прогон)
- Вручную запустить `/hygiene` после полного setup.
- Проверить: Cloudflare-статья создана, в `tool_runs` есть запись, если есть ask-user → Telegram пришёл.
- Если что-то не так — fix → повторный прогон.

---

## 7. Edge cases & error handling

### 7.1 Conflict с другим открытым PR
Если уже есть открытый PR `chore/hygiene-*` (предыдущий запуск завис) — hygiene сначала проверяет статус. Если зелёный и можно мёржить — мёржит. Если ждёт ask-user — добавляет новые findings комментарием в существующий PR, не открывает новый.

### 7.2 Cron-запуск во время твоей работы
Hygiene видит uncommitted changes которые ты ещё не доделал → НЕ коммитит их. White-list `unpushed_paths` ограничивает auto-commit только до явно безопасных директорий (planning/specs/docs). Код в `services/` или `shared/` — никогда auto-commit.

### 7.3 Превышение cost cap
- Soft cap: log warning в Cloudflare-статью, продолжай.
- Hard cap: abort, частичный PR (что успел auto-fix), Telegram alert «hygiene aborted, hit hard cap, см. ссылку».

### 7.4 Cloudflare/Telegram API failure
- Cloudflare fail → fallback: PR description содержит весь findings inline.
- Telegram fail → log warning в `tool_runs`, не фейлим весь запуск.

### 7.5 LLM hallucination на ask-user (предлагает удалить нужное)
- Безопасность: hygiene никогда сам не удаляет ask-user item, только предлагает в PR description.
- Codex+Copilot review на PR ловит обоснованность.
- Финальное решение — за тобой при merge.

### 7.6 Что если после Phase 1 в проекте нет drift'а вообще (rare)
- Cloudflare-статья «всё чисто» (короткая запись со счётчиками 0/0/0).
- Никакого PR.
- `tool_runs` запись с `status: success`, `metrics: {auto: 0, ask: 0, security: 0}`.

---

## 8. Success criteria

Phase 2 считается успешной, когда:
- `/hygiene` запускается вручную и завершается без ошибок.
- Routine `wookiee-hygiene-daily` зарегистрирован через `/schedule`.
- Минимум один cron-запуск прошёл автоматически (наблюдается в `tool_runs`).
- Cloudflare-статья создаётся каждый запуск.
- Telegram алерты приходят только при ask-user/security.
- Live drift на момент Phase 2 (`.codex/`, `.cursor/`, `.mcp.json.example`, `docs/CODEX-CURSOR-SETUP.md`, untracked plans, sku_database migrations) обработан первым же запуском (auto-commit или ask-user).
- Запись `hygiene` есть в Supabase `tools`.

---

## 9. Open Questions (минимум, фиксируется в impl plan)

1. **Точный username Telegram-бота** — выбирает пользователь при создании через @BotFather.
2. **Cloudflare Pages namespace** — куда именно публиковать (на твой Cloudflare-аккаунт). Решит skill `/cloudflare-pub` сам — он уже сконфигурирован.
3. **Стоимость на запуск** — измерим после первых 7 дней (collection через `tool_runs.metrics.tokens`). Оптимизация — отдельный future-spec, если будут проблемы.

---

## 10. Phase 3 hint (за рамками этого spec)

Возможные расширения в будущем (не делаем сейчас):
- **Self-tuning**: hygiene учится на твоих решениях по ask-user → понижает false-positive-rate.
- **Multi-repo support**: один скилл для нескольких репо.
- **Adaptive cron**: учащение при высоком drift, замедление при чистоте.
- **Integration с GitHub Issues**: ask-user findings → автоматические Issues с label `hygiene`.

Эти идеи фиксируются здесь только для контекста — реализуются отдельным брейнштормом, если возникнет потребность.
