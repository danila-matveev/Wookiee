---
name: hygiene-followup
description: Daily auto-resolver of /hygiene follow-up artifacts. Re-runs detect.md checks against fresh main, closes issues whose findings are resolved, comments PRs with current status. Read-only — never edits files.
---

# Hygiene Follow-up Skill

Спека: `docs/superpowers/specs/2026-04-29-hygiene-followup-design.md`.

## Что делает

После основного `/hygiene` (03:00 UTC) cron в **06:00 UTC** запускает этот скилл. Он:
1. Находит открытые issue/PR от hygiene
2. Парсит каждое finding из тела
3. Перезапускает соответствующую проверку из `detect.md` на свежем `main`
4. Если все findings в issue исчезли → закрывает issue
5. Если PR содержит findings и часть исчезла → добавляет комментарий с обновлённым статусом, **сам PR не трогает**
6. Если ничего не изменилось → no-op

## Quick start

```
/hygiene-followup                # full run (default)
/hygiene-followup --dry-run      # парсинг + re-run, без закрытия и комментариев
/hygiene-followup --only ISSUE_N # обработать только конкретный номер
```

## Hard rules — DO NOT VIOLATE

- **NEVER** редактировать файлы (Read, Bash, gh — да; Edit/Write — НЕТ).
- **NEVER** делать commit / push / merge.
- **NEVER** трогать issue или PR без префикса `hygiene followups —` в title (issue) или `chore(hygiene):` (PR).
- **NEVER** закрывать issue моложе **24 часов** (даём пользователю шанс посмотреть до автоматики).
- **NEVER** закрывать PR. Максимум — добавить comment.
- **NEVER** обрабатывать pull requests в состоянии MERGED или DRAFT.
- **NEVER** запускать `structure-conventions` re-validation — это LLM-driven, авто-revalidation ненадёжна. Эти findings оставляем юзеру.

## 7-Phase Flow

### Phase 1 — FETCH

```bash
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)

# Открытые hygiene-issue (title pattern)
gh issue list --state open --search 'hygiene followups in:title' \
  --json number,title,body,createdAt,labels \
  > /tmp/hyg-followup-issues-$RUN_ID.json

# Открытые hygiene-PR (для read-only комментирования)
gh pr list --state open --search 'chore(hygiene) in:title' \
  --json number,title,body,createdAt,labels \
  > /tmp/hyg-followup-prs-$RUN_ID.json
```

Skip пустой набор → exit 0 без notification.

### Phase 2 — PARSE

Для каждого item (issue или PR) распарсить body. Hygiene использует формат:

```markdown
### <check-name>: <short label>
- Paths: <comma-separated paths or quoted entities>
- Reason: <reason>
- Suggested action: <suggested>
- Evidence: <evidence>
```

Парсер извлекает:
- `check_name` — первое слово после `### ` до первого `:`
- `paths` — нормализуем как массив строк (split по `,`, trim, strip backticks)

Если check_name == `structure-conventions` → помечаем `skip_revalidation=true` (см. hard-rules).

Сохраняем в `/tmp/hyg-followup-parsed-$RUN_ID.json`:
```json
[
  {
    "item_type": "issue",
    "number": 85,
    "created_at": "2026-04-29T06:14:00Z",
    "findings": [
      {"check": "skill-registry-drift", "paths": ["bitrix-task", "finolog"]},
      ...
    ]
  }
]
```

### Phase 3 — RE-RUN

Для каждого `finding` (кроме `skip_revalidation=true`):

1. Открыть `.claude/skills/hygiene/prompts/detect.md`
2. Найти секцию `## N. <check_name>` (по соответствию имени)
3. Выполнить bash-блок (или Python-блок) **из этой секции**, ничего больше
4. Сохранить вывод в `/tmp/hyg-followup-rerun-$RUN_ID-<check>.txt`

**Лимит:** 60 секунд на одну проверку (как в основной hygiene). Таймаут → пометить finding как `revalidation_failed`, не закрывать.

### Phase 4 — CLASSIFY

Для каждого finding сравнить `original_paths` (из issue/PR body) с `current_paths` (из re-run output):

| Случай | Действие |
|---|---|
| `current_paths ∩ original_paths` пусто | RESOLVED |
| `current_paths ⊇ original_paths` | STILL (все ещё там) |
| Частично пересекаются | PARTIAL |

Для `revalidation_failed` → пометить `unknown`, оставить как есть.

### Phase 5 — ACT

Для каждого item:

**Issue:**
- Если все findings RESOLVED → close с комментарием:
  ```
  ✅ Hygiene-followup проверил пункты заново — все исчезли. Закрываю.

  Подробности:
  - <check>: было N путей, сейчас 0
  - ...
  ```
- Если PARTIAL (часть RESOLVED) → comment с зачёркнутыми (~~text~~) пунктами:
  ```
  Часть пунктов исправилась автоматически (детектор был починен). Оставляю открытым для остальных.
  ```
- Если все STILL → no-op (не комментируем чтобы не шуметь)
- Если все unknown → no-op

**PR:**
- Если все RESOLVED → comment "Все findings из этого PR исчезли. PR можно мерджить или закрывать на ваше усмотрение."
- Если PARTIAL → comment с обновлённым списком
- НИКОГДА не закрывать сам PR

**Проверка возраста:** перед close проверить `created_at`. Если `now - created_at < 24h` → skip.

### Phase 6 — NOTIFY

Только если что-то закрыли или прокомментировали. Telegram-сообщение в общий `@wookiee_alerts_bot`:

```
🧹 Hygiene-followup убрал пыль.

Закрыл {N} issue: #{numbers}.
Прокомментировал {M} PR: #{numbers}.

Если что-то закрыл по ошибке — переоткрой issue.
```

Если ничего не сделал → не шумим, тишина.

### Phase 7 — LOG

```python
PYTHONPATH=. python3 -c "
from shared.tool_logger import ToolLogger
import os, json
log = ToolLogger('hygiene-followup')
run_id = log.start(trigger=os.getenv('HYGIENE_TRIGGER', 'manual'), version='1.0.0', environment=os.getenv('HYGIENE_ENV', 'local'))
log.finish(run_id, status='${STATUS}', details=json.dumps({
  'issues_closed': ${CLOSED},
  'prs_commented': ${COMMENTED},
  'still_open': ${STILL},
  'duration_seconds': ${DURATION},
}))
"
```

## Pre-conditions

- `gh` CLI авторизован (token с правами `issues:write`, `pull_requests:write`)
- `.env` (или env vars в CI) содержит `TELEGRAM_ALERTS_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`, `POSTGRES_*` (для tool_logger)
- Свежий `main` (cron делает `git pull` перед стартом)

## Edge cases

- **Несколько issue от одного дня:** обрабатываем все.
- **Issue закрыт но re-opened:** считается открытым, обрабатываем.
- **Issue без `### ` секций (просто markdown):** skip — не парсится, оставить.
- **Hygiene выложил issue с `title="hygiene followups — 2026-04-29"`, но в body другой формат:** парсер должен это пережить (return пустой findings list → no-op).
- **Re-run проверки требует Postgres (skill-registry-drift):** если БД недоступна → revalidation_failed, не закрывать.
- **Issue ссылается на закрытый PR:** не учитываем, закрываем по логике findings.

## See also

- `docs/superpowers/specs/2026-04-29-hygiene-followup-design.md` — design rationale
- `.claude/skills/hygiene/prompts/detect.md` — источник check-команд
- `.github/workflows/hygiene-followup-daily.yml` — production runner
