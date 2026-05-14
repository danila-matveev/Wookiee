# Wookiee Workflow Setup

**Дата:** 2026-05-12
**Автор плана:** Claude Opus 4.7 (1M)
**Статус:** APPROVED, готов к исполнению
**Оценка времени:** ~5 часов работы Claude (с паузами на пользователя)

---

## Зачем этот план

Сейчас репозиторий Wookiee — открытая квартира. У пользователя 5-10 параллельных Claude-сессий, и любая может:
- Запушить мусор в main (фактически: 96% коммитов в main за 14 дней — мимо PR)
- Локально смерджить ветку в main без ревью (так попала `feature/marketing-hub`)
- Сделать `git reset --hard` и потерять работу (46 раз за 24 дня)
- Создать незадокументированный worktree (накопилось 32 штуки)

Этот план ставит замок: после установки ни одна Claude-сессия не может слить мусор в main, всё идёт через PR с автоматическими проверками. Также чистим накопившийся хвост.

---

## Контекст и решения (зафиксированные в обсуждении)

**Принято:**
- Подход «правильный и надёжный» — устанавливаем полный замок, а не половинчатый
- Codex review на GitHub **НЕ добавляем на старте** (полдня работы, добавим позже отдельным PR если будет нужно)
- Защита от mac-терминала **ВКЛЮЧЕНА в план** (этап 4)
- Чистка stash **ВКЛЮЧЕНА** (этап 7)
- Автоматизация чистки веток в hygiene **ВКЛЮЧЕНА** (этап 4)
- GPG signing — НЕ делаем (для одного разработчика с AI избыточно)

**Стиль общения с пользователем:**
- Простой язык, бытовые аналогии, минимум жаргона
- Технические термины расшифровывать сразу: «PR (окошко для проверки кода)»
- Не давать пользователю выбирать между техническими вариантами — Claude решает сам и объясняет словами
- Перед каждым деструктивным действием — короткое подтверждение
- См. `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/feedback_plain_language.md`

**Параллельные сессии:**
- На момент написания плана активна **вторая VSCode-сессия Claude (pid 84837)**, работает над W2/W3/W4 каталога ~4 часа
- Этап 0 — дождаться когда она закроется/закончит (зависит от пользователя)

---

## Сводка фактов от аудита

**Worktree (всего 33):**
- 12 безопасных к удалению (без работы, без коммитов вне main)
- 8 от живой второй сессии (pid 84837) — не трогать
- 7 W1.0-W1.7 — реальная работа от мёртвой утренней сессии, сливать в main
- 6 прочих

**Open PRs:** #117 (catalog-w4), #112 (hygiene-bot), #111 (hygiene-autofix). CI красный на всех.

**CI failure root cause:** `ruff` падает с 9 ошибками — реальные мелочи:
- `services/sheets_sync/runner.py:189` — забыт `import os` (F821)
- `services/telemost_recorder/join.py:10` — unused/redefined `AudioCapture` (F401, F811)
- `services/telemost_recorder/speakers.py:5` — unused `from pathlib import Path` (F401)
- 4 из 9 — автофикс через `ruff check --fix`

**GitHub state:**
- Default branch `main`, public repo, classic protection отсутствует
- Активны 2 rulesets (id 12853246 «Protect main» и id 14295057 «Copilot review»)
- Текущее правило только блокирует force-push + deletion; **прямой push в main разрешён**
- Auto-merge на repo **выключен** (`allow_auto_merge: false`)
- Hygiene-бот пушит как `claude[bot]` (GitHub App)

**Глобальная Claude-конфигурация:**
- `~/.claude/settings.json` имеет `defaultMode: "bypassPermissions"` и `skipDangerousModePermissionPrompt: true`
- `deny`-секция была удалена (есть бэкап `settings.json.bak.20260417-124219`)

---

## Этап 0 — Дождаться второго окна

**Что:** найти второе VSCode-окно Claude (pid 84837) и дать ему завершить работу.

**Как:**
1. Спросить у пользователя: «Найди в Mac (Cmd+Tab по VSCode окнам) второе окно с Wookiee. Что оно сейчас делает?»
2. Два пути:
   - Сессия близка к завершению → попросить её оформить PR со всей работой W2/W3/W4 и закрыться, дождаться merge
   - Сессия в неопределённом состоянии → попросить «оформи PR со всем что есть, потом закройся»
3. После закрытия — проверить: `kill -0 84837` должен сказать «no such process»

**Что от пользователя:** найти окно, дать инструкции той сессии, подтвердить когда закроется.

**Контрольная точка перед этапом 1:** `kill -0 84837 2>&1 | grep -q "no such"` возвращает успех.

**Если пользователь сказал «не нашёл окно»:** проверить `ps -p 84837 -o command` — посмотреть запустилось ли оно из VSCode, попросить пользователя закрыть все VSCode-окна с Wookiee.

---

## Этап 1 — Уборка хвостов

**Кто:** только Claude.
**Время:** ~15 минут.

### Действия

**1.1. Снять симлинк секретов:**
```bash
rm /private/tmp/wookiee-crm-p5/.env
# Если есть и сама папка — удалить полностью
rm -rf /private/tmp/wookiee-crm-p5 /private/tmp/wookiee-crm-p4 /private/tmp/wookiee-crm-p2 /private/tmp/wookiee-verify
rm -f /private/tmp/wookiee-hub-preview*.log /private/tmp/wookiee-preview-root.html
```

**1.2. Поставить точку возврата:**
```bash
git tag pre-workflow-setup
git push origin pre-workflow-setup
```

**1.3. Прибрать призрак w4 (папка исчезла, запись в git осталась):**
```bash
git worktree prune
```

**1.4. Удалить 12 безопасных worktree.** Список:

| # | Путь | Branch | Причина |
|---|---|---|---|
| 1 | `.claude/worktrees/agent-a0b48d07e8e35c000` | worktree-agent-a0b48d07e8e35c000 | пустая, pid 5419 (мёртв) |
| 2 | `.claude/worktrees/agent-a139f042eb6f6276f` | worktree-agent-a139f042eb6f6276f | пустая, pid 5419 |
| 3 | `.claude/worktrees/agent-a14d33b9e11eac929` | worktree-agent-a14d33b9e11eac929 | пустая, pid 5419 |
| 4 | `.claude/worktrees/agent-a3a1f749007ddf2f8` | wave-2-b3-modelcard | коммиты уже в main, дубликат |
| 5 | `.claude/worktrees/agent-a6690224de4d0352b` | worktree-agent-a6690224de4d0352b | пустая, pid 5419 |
| 6 | `.claude/worktrees/agent-a76f74e4f55d59266` | worktree-agent-a76f74e4f55d59266 | пустая, pid 5419 |
| 7 | `.claude/worktrees/agent-aa0be2c1f709f0f9e` | worktree-agent-aa0be2c1f709f0f9e | пустая, pid 5419 |
| 8 | `.claude/worktrees/agent-aa8507c2e30c454cb` | worktree-agent-aa8507c2e30c454cb | пустая, pid 5419 |
| 9 | `.claude/worktrees/agent-ab3ec65d91f2995fb` | worktree-agent-ab3ec65d91f2995fb | пустая, pid 5419 |
| 10 | `.claude/worktrees/feature+catalog-overhaul-w2` | feature/catalog-overhaul-w2 | смерджено |
| 11 | `.claude/worktrees/feature+catalog-overhaul-w3` | feature/catalog-overhaul-w3 | смерджено |
| 12 | (призрак, исчез) feature+catalog-overhaul-w4 | feature/catalog-overhaul-w4 | удаляется через `git worktree prune` в 1.3 |

Для каждого (кроме #12, который уже обработан):
```bash
git worktree remove --force <path>
git branch -D <local-branch>
# Если есть на origin:
git push origin --delete <remote-branch> 2>/dev/null || true
```

**1.5. Удалить `w1-smoke-snapshot.yml`:**
```bash
cd /Users/danilamatveev/Projects/Wookiee/.claude/worktrees/feature+catalog-overhaul-w1
rm -f w1-smoke-snapshot.yml
cd /Users/danilamatveev/Projects/Wookiee
```

Сам worktree `feature+catalog-overhaul-w1` пока оставить — он не пустой, ветка может пригодиться. Удалим в этапе 2 если действительно лишний.

**1.6. Добавить `.claude/worktrees/` в `.gitignore`:**
```bash
# Проверить что записи ещё нет:
grep -q "^\.claude/worktrees/" .gitignore || echo ".claude/worktrees/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore .claude/worktrees/ from tracking"
```

### Контрольная точка после этапа 1

```bash
git worktree list
# Должно быть ~ 9-10 worktree (с учётом активного pid 84837 если ещё жив)
# Не должно быть: agent-a0b48*, a139f*, a14d3*, a3a1f*, a6690*, a76f7*, aa0be*, aa850*, ab3ec*, feature+catalog-overhaul-w2/w3/w4
```

**От пользователя:** просмотреть результат, сказать «ок» или «стоп».

---

## Этап 2 — Спасение работы W1.0–W1.7

**Кто:** только Claude.
**Время:** ~1 час (из-за разруливания конфликтов в `model-card.tsx`).

### Действия

**2.1. Подготовить ветку:**
```bash
git checkout main
git pull origin main
git checkout -b feature/catalog-w1-polish
```

**2.2. Cherry-pick 8 коммитов в строгом порядке:**

| # | Wave | SHA | Описание | Файл основного контента |
|---|---|---|---|---|
| 1 | W1.0 | `ed149ce` | Status badge for all modeli_osnova rows | `wookiee-hub/src/pages/catalog/matrix.tsx` |
| 2 | W1.1 | `e3a4c5d` | Tooltip collision avoidance via Radix | `wookiee-hub/src/components/catalog/ui/tooltip.tsx` |
| 3 | W1.2 | `ccf4f99` | Numeric inputs + unit-suffix on model-card | `fields.tsx` + `model-card.tsx` |
| 4 | W1.3 | `abec0df` | Remove duplicate attribute controls | `model-card.tsx` |
| 5 | W1.4 | `c10576c` | TagsCombobox with autocomplete | `service.ts` + `model-card.tsx` |
| 6 | W1.5 | `679e353` | Resizable table columns | `matrix.tsx` + `tovary.tsx` |
| 7 | W1.6 | `45d247f` | Hint tooltips on link/numeric fields | `model-card.tsx` |
| 8 | W1.7 | `44aa640` | Empty cert state in attach modal | `model-card.tsx` |

```bash
git cherry-pick ed149ce e3a4c5d ccf4f99 abec0df c10576c 679e353 45d247f 44aa640
```

**Конфликты:** ожидаются в `model-card.tsx` (5 коммитов трогают этот файл). При конфликте:
1. `git status` — увидеть конфликтующие файлы
2. Открыть файл, развести вручную: оставить **обе** функциональности (badge + numeric inputs + dedup + tags + tooltips + empty cert не противоречат друг другу — это разные UI-фичи)
3. `git add <file>` + `git cherry-pick --continue`

Если конфликт сложный/непонятный — остановиться и спросить пользователя.

**2.3. Починить ruff-ошибки отдельным коммитом:**

```bash
# Auto-fix первое что можно:
ruff check --fix services/

# Если что-то осталось — править вручную:
# services/sheets_sync/runner.py — добавить в начало `import os` если его нет
# services/telemost_recorder/join.py — убрать строку 10 (unused AudioCapture) и/или строку 464 (redefinition)
# services/telemost_recorder/speakers.py — убрать `from pathlib import Path`

# Подтвердить что чисто:
ruff check services/

# Закоммитить:
git add -p
git commit -m "chore(ci): fix ruff F821/F401/F811 errors blocking PR merges"
```

**2.4. Запушить ветку:**
```bash
git push -u origin feature/catalog-w1-polish
```

**2.5. Открыть PR:**
```bash
gh pr create --title "Catalog UI polish: W1.0-W1.7 + ruff fixes" --body "$(cat <<'EOF'
## Что в этом PR

Собрал в один PR 8 UI-улучшений каталога (Wave 1) которые делала параллельная сессия утром 2026-05-12, плюс починка ruff-ошибок которые блокировали CI на других PR.

### UI-фичи (W1.0–W1.7)
- W1.0 (`ed149ce`) — статус-бейдж для всех строк `modeli_osnova` в матрице
- W1.1 (`e3a4c5d`) — collision avoidance для tooltip через Radix
- W1.2 (`ccf4f99`) — numeric inputs с unit-suffix на полях размеров модели
- W1.3 (`abec0df`) — убраны дубликаты контроллов атрибутов из вкладки Описание
- W1.4 (`c10576c`) — TagsCombobox с автокомплитом и созданием тегов на лету
- W1.5 (`679e353`) — resizable колонки таблицы с сохранением в ui_preferences
- W1.6 (`45d247f`) — hint-tooltips на полях link/numeric model-card
- W1.7 (`44aa640`) — пустое состояние для сертификатов с ссылкой на создание

### CI fix
- `services/sheets_sync/runner.py` — добавлен `import os`
- `services/telemost_recorder/join.py` — убран unused/redefined `AudioCapture`
- `services/telemost_recorder/speakers.py` — убран unused `from pathlib import Path`

## Test plan
- [ ] CI quality passes (ruff)
- [ ] Каталог открывается без ошибок в консоли
- [ ] Все 8 фич работают (визуальная проверка на странице каталога)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

**2.6. Дождаться CI:** `gh pr checks <PR-NUM> --watch`. Должно стать зелёным.

**2.7. Запросить пользователя смерджить:** «PR готов, CI зелёный, нажми Merge → ссылка».

**2.8. После merge — очистить W1.x worktrees и ветки:**

```bash
# 8 W1.x worktrees:
for wt in agent-a958f411970aba543 agent-af6c30548a209e6ad agent-aa2b32a8e3f151efd agent-abb8e3b3315a09f1a agent-af530e55f6b94ab98 agent-a6b7fdbc39bb3a9f5 agent-ad86b86a93bcea906 agent-af20acd7b0eabef40; do
  git worktree remove --force ".claude/worktrees/$wt" 2>/dev/null || true
  git branch -D "worktree-$wt" 2>/dev/null || true
  git push origin --delete "worktree-$wt" 2>/dev/null || true
done

# feature/catalog-overhaul-w1 worktree (с уже удалённым snapshot-файлом):
git worktree remove --force .claude/worktrees/feature+catalog-overhaul-w1 2>/dev/null || true
git branch -D feature/catalog-overhaul-w1 2>/dev/null || true
# На origin — оставить как историю, не удалять

git worktree prune
```

### Контрольная точка после этапа 2

- PR в main, merged
- 8 W1.x worktrees удалены
- В main все 8 UI-фич + чистый CI
- `git worktree list` показывает 0-2 worktree (только W2-W4 от живой второй сессии если она ещё работает)

---

## Этап 3 — Завершение работы второго окна (если ещё активно)

**Условно:** если pid 84837 был жив в начале и до сих пор не оформил PR.

**Действия:** аналогично этапу 2, но для веток `worktree-agent-a0e71*`, `a12af*`, `a13f9*`, `a305b*`, `a3f23*`, `a4ea5*`, `a5b33*`, `a7e43*`, `a98556*`, `ae0eb*`, `aec38*`.

Коммиты соответствуют:
- W2.1 razmery, W2.2 kategoriya/atributy, W2.3 tipy_kollekciy
- W3.1 brendy, W3.2 brendy UI
- W4.1 NewModelModal, W4.2 variation, W4.3 артикулы+палитра, W4.4 SKU bulk, W4.5 inline-edit, W4.6 bulk-status

**Если pid 84837 уже оформил PR сам:**
- Дождаться его merge
- Очистить worktrees

**Если pid 84837 умер не оформив PR:**
- Собрать в `feature/catalog-w2-w4-bundle` аналогично этапу 2
- Открыть PR, мерджить, очищать

После этапа 3: `git worktree list` показывает только основной репо. Чисто.

---

## Этап 4 — Установка защитной системы

**Кто:** только Claude, на отдельной ветке `chore/claude-workflow-setup`.
**Время:** ~2-3 часа.

### Архитектура

5 слоёв:
1. **SessionStart hook** — на старте сессии инжектит контекст «ты на main / в worktree X»
2. **PreToolUse(Bash) hook** — блокирует опасные git-команды
3. **PreToolUse(Edit|Write|MultiEdit) hook** — блокирует правки на main и в защищённых файлах
4. **Stop hook** — чистит за собой (session-registry)
5. **Git pre-push hook** — блокирует push в main из mac-терминала

### Действия

**4.1. Создать ветку:**
```bash
git checkout main && git pull
git checkout -b chore/claude-workflow-setup
```

**4.2. Файлы для создания:**

```
.claude/hooks/
  session-start.sh       # SessionStart инжектор контекста
  git-firewall.sh        # PreToolUse(Bash) блокатор
  fs-firewall.sh         # PreToolUse(Edit|Write|MultiEdit) блокатор
  session-stop.sh        # Stop hook cleanup
  guard-lib.sh           # Общие функции (detect-worktree, registry-io, logging)
  smoke-test.sh          # Тест что хуки живы
.claude/commands/
  ship.md                # Slash command для PR с auto-merge
git-hooks/
  pre-push               # Git native hook для terminal protection
```

**Конкретика по каждому хуку:**

`session-start.sh`:
- Читает JSON из stdin (есть `session_id`, `cwd`)
- Вычисляет `GIT_DIR` и `GIT_COMMON_DIR` (определение worktree через `git rev-parse`)
- Прунит мёртвые записи в `.claude/session-registry/` (через `kill -0 <pid>`)
- Пишет свою запись `.claude/session-registry/<session_id>.json` с `{pid, cwd, branch, worktree_path, started_at}`
- Если на main → возвращает `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "...WOOKIEE-GUARD: ты на main, read-only..."}}`
- Если в worktree → инжектит «ты в worktree X, PID Z, не переключай ветки»

`git-firewall.sh`:
- Читает JSON из stdin (`tool_input.command`, `cwd`)
- Вычисляет current branch (`git -C "$cwd" rev-parse --abbrev-ref HEAD`)
- Регулярки для блокировки (deny):
  - `git push .* (origin/)?main\b` если current=main или explicit target=main
  - `git push .* --force` или `-f\b` (force-push куда угодно)
  - `git merge\b` если current=main
  - `git rebase main\b` если current=main
  - `git reset --hard\b` если current=main
  - `git branch -D main\b`
  - `git checkout main\s*&&` (heuristic на цепочки)
  - `rm -rf` с путём вне `cwd`
  - `python3? -c .*subprocess.*git`, `bash -c .*git`, `eval`, `base64 -d` (защита от обхода)
  - Запись в `\.claude/settings.*\.json` или `~/.claude/settings.*\.json` или `\.claude/hooks/`
- Allow: read-only git (status, log, diff, show, branch без -D)
- Возврат при deny: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}, "systemMessage": "ЗАБЛОКИРОВАНО WOOKIEE-GUARD: <причина>. Сделай так: <инструкция, например EnterWorktree>"}`

`fs-firewall.sh`:
- Читает JSON из stdin (`tool_input.file_path`)
- Проверки:
  - Если current branch == main → deny на запись любого файла
  - Если file_path указывает на `.claude/settings*.json`, `~/.claude/settings*.json`, `.claude/hooks/`, `git-hooks/` → deny
  - Если file_path под другим worktree из registry (не текущим) → deny
- Возврат: аналогично git-firewall

`session-stop.sh`:
- Читает `session_id` из JSON
- Удаляет `.claude/session-registry/<session_id>.json`
- Пишет лог `.claude/logs/session-<session_id>-end.log`

`guard-lib.sh`:
- Вспомогательные функции: `get_current_branch`, `is_in_worktree`, `read_registry`, `write_registry`, `prune_dead`, `emit_deny_response`

`smoke-test.sh`:
- Запускается из hygiene
- Симулирует deny-команду через хук, проверяет что хук вернул deny
- Если не deny → пишет alert в `.claude/logs/guard-smoke-FAILED.log` (hygiene его подхватит)

**4.3. Обновить `.claude/settings.json` — подключение хуков:**

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [...существующие...],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(sudo rm -rf*)",
      "Write(**/.env*)",
      "Write(**/*.pem)",
      "Write(**/*.key)",
      "Write(**/id_rsa*)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {"matcher": "startup|clear|compact", "hooks": [{"type": "command", "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/session-start.sh", "timeout": 5}]}
    ],
    "PreToolUse": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/git-firewall.sh", "timeout": 3}]},
      {"matcher": "Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/fs-firewall.sh", "timeout": 3}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "bash ${CLAUDE_PROJECT_DIR}/.claude/hooks/session-stop.sh", "timeout": 3}]}
    ]
  }
}
```

**4.4. Pre-push git hook для terminal-protection:**

Файл `git-hooks/pre-push` (в репо, tracked):
```bash
#!/usr/bin/env bash
# Blocks direct push to main from any client (mac terminal, IDE, etc.)
while read local_ref local_sha remote_ref remote_sha; do
  if [[ "$remote_ref" == "refs/heads/main" ]]; then
    echo "❌ Прямой push в main запрещён. Используй PR."
    echo "   (Это правило Wookiee Workflow Guard. См. AGENTS.md.)"
    exit 1
  fi
done
exit 0
```

Подключение через `core.hooksPath`:
```bash
chmod +x git-hooks/pre-push
git config core.hooksPath git-hooks
# Это команда применяется к локальной копии. В AGENTS.md записать что новые клоны должны делать `git config core.hooksPath git-hooks` после клонирования.
```

**4.5. Slash-команда `/ship`** (`.claude/commands/ship.md`):

```markdown
---
description: Создать PR с auto-merge — Claude закрывает задачу, GitHub мерджит после CI
---

Создай PR для текущей feature-ветки и поставь его на auto-merge.

Шаги:
1. Проверь что ты не на main: `git branch --show-current`
2. Если есть uncommitted — закоммить с описательным сообщением
3. `git push -u origin $(git branch --show-current)`
4. Создай PR через `gh pr create --title "..." --body "..."` с тестпланом
5. Включи auto-merge: `gh pr merge <num> --auto --squash --delete-branch`
6. Дай пользователю URL PR'а с комментарием «GitHub смерджит сам когда CI зелёный»

Не жди merge, не блокируй пользователя.
```

**4.6. Hygiene — добавить чек stale worktree и smoke-test:**

В `.claude/skills/hygiene/prompts/detect.md` добавить секции:
- Stale worktree: `git worktree list --porcelain` → для каждого, если mtime старше 7 дней И нет uncommitted И нет unmerged-коммитов И `kill -0 <pid>` ложен → пометить к удалению
- Guard smoke-test: запустить `.claude/hooks/smoke-test.sh`, если падает — alert в общий чат
- Stale branches: расширить существующий чек, добавить автоматическое создание summary-сообщения с кнопками да/нет

**4.7. AGENTS.md addendum:**

Добавить секцию «Workflow Guard» с:
- Краткое описание системы (3-4 предложения)
- Когда хук блокирует — что делать (`EnterWorktree`, `/ship`)
- Как отключить в emergency: открыть `.claude/settings.json` в обычном редакторе (не через Claude), удалить блок `"hooks": {...}`. Это последняя страховка.
- Ссылка на этот план

**4.8. Восстановить deny в global settings:**

В `~/.claude/settings.json` восстановить секцию `deny` из бэкапа `~/.claude/settings.json.bak.20260417-124219`. Это global, не git-tracked — делается отдельной командой:
```bash
# Backup current first
cp ~/.claude/settings.json ~/.claude/settings.json.bak.before-guard-install

# Прочитать bak.20260417 и аккуратно вставить deny-секцию в текущий settings.json
# Делается через Python скрипт или jq.
```

**4.9. .gitignore:**

Добавить:
```
.claude/session-registry/
.claude/logs/
.claude/state/
```

**4.10. Открыть PR:**

```bash
git add .claude/ git-hooks/ AGENTS.md .gitignore
git commit -m "chore: install Wookiee Workflow Guard"
git push -u origin chore/claude-workflow-setup
gh pr create --title "chore: install Wookiee Workflow Guard" --body "$(cat <<'EOF'
## Что в этом PR

Установка системы автоматической защиты репозитория от случайных деструктивных действий Claude-сессий (включая параллельные).

### Что включается
- 4 защитных хука в `.claude/hooks/` (SessionStart, Bash, Edit/Write, Stop)
- Git pre-push hook (защита от прямого push в main из любого клиента)
- Slash command `/ship` для авто-PR с auto-merge
- Hygiene расширение: stale-worktree cleanup + guard smoke-test
- AGENTS.md addendum с инструкцией экстренного отключения

### Что гарантируется после merge
- Любая Claude-сессия на main = read-only (Edit/Write блокированы)
- `git push origin main`, `git merge → main`, `git reset --hard` на main → блокировка
- Правки `.claude/settings.json`, `.claude/hooks/` через Claude → блокировка
- Несколько параллельных сессий не пересекаются (session-registry)
- Stale-worktree чистятся через hygiene daily

### Что НЕ включается (для отдельных PR)
- Codex review GitHub Action (отложено)
- GitHub-side rules (отдельный шаг после merge, см. этап 5 плана)

## Test plan
- [ ] CI quality passes
- [ ] Smoke-test: попытка `git commit` на main → блокировка (тест в этапе 6)
- [ ] Smoke-test: попытка `git push origin main` → блокировка
- [ ] Smoke-test: попытка Edit на `.claude/settings.json` → блокировка
- [ ] Существующая работа (daily-brief, hygiene, finance-report) не сломалась

См. план: `docs/superpowers/plans/2026-05-12-claude-workflow-setup.md`

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Контрольная точка после этапа 4

- PR `chore/claude-workflow-setup` открыт, CI зелёный
- **Пользователь нажимает Merge** (последний ручной merge)

---

## Этап 5 — Включение защиты на GitHub

**Кто:** только Claude (через `gh api`).
**Время:** ~10 минут.

### Действия

**5.1. Включить auto-merge и cleanup на репо:**
```bash
gh api -X PATCH /repos/danila-matveev/Wookiee \
  -f allow_auto_merge=true \
  -F delete_branch_on_merge=true \
  -F allow_update_branch=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false
# Оставляем только squash-merge для линейной истории
```

**5.2. Узнать installation_id hygiene-бота:**
```bash
gh api /repos/danila-matveev/Wookiee/installations 2>/dev/null | jq '.installations[] | select(.app_slug=="claude") | {id, app_slug, target_type}'
# Сохранить id, понадобится в bypass_actors
```

**5.3. Заменить ruleset «Protect main» (id 12853246):**

```bash
# Сохранить текущий ruleset для отката
gh api /repos/danila-matveev/Wookiee/rulesets/12853246 > /tmp/ruleset-12853246-backup.json

# Применить новый
gh api -X PUT /repos/danila-matveev/Wookiee/rulesets/12853246 --input - <<EOF
{
  "name": "Protect main branch",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": false,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,
      "required_status_checks": [{"context": "quality"}]
    }}
  ],
  "bypass_actors": [
    {"actor_id": <CLAUDE_BOT_INSTALLATION_ID>, "actor_type": "Integration", "bypass_mode": "pull_request"}
  ]
}
EOF
```

**5.4. Проверить применение:**
```bash
gh api /repos/danila-matveev/Wookiee/rulesets/12853246 | jq '.rules[] | .type'
# Должно быть: deletion, non_fast_forward, required_linear_history, pull_request, required_status_checks
```

### Контрольная точка после этапа 5

- Auto-merge включён на repo
- Ruleset требует PR + зелёный CI `quality`
- Hygiene-бот в bypass_actors

---

## Этап 6 — Проверка что замок работает

**Кто:** только Claude.
**Время:** ~15 минут.

### Тесты (каждый должен ПРОЙТИ, иначе откат)

**6.1. SessionStart на main:**
- Открыть новую сессию Claude в этом проекте (можно `claude --resume` с фейковым sid или просто новый прогон)
- Первое сообщение от пользователя — проверить что в системном промпте есть текст «ты на main, read-only»

**6.2. Bash-блокировка на main:**
```bash
# В свежей сессии:
git checkout main  # uже на main
# Попробовать запрещённое — Claude должен получить deny от хука
echo "test" > test-file.txt  # должно быть заблокировано fs-firewall
git push origin main  # должно быть заблокировано git-firewall
```

**6.3. Edit-блокировка на main:**
- Попытаться Edit `.claude/settings.json` → блокировка fs-firewall
- Попытаться Edit любой файл проекта на main → блокировка

**6.4. Pre-push hook (terminal):**
```bash
git checkout main
git commit --allow-empty -m "test" 2>/dev/null  # если коммит прошёл — это уже проблема, должно быть заблочено
git push origin main  # должно упасть с сообщением «Прямой push в main запрещён»
```

**6.5. GitHub-side:**
- Создать тестовую ветку с пустым изменением (пробел в README)
- `git push origin test-branch`
- Открыть PR через `gh pr create`
- Поставить на auto-merge: `gh pr merge --auto --squash`
- Дождаться CI: должен пройти зелёным
- GitHub должен мерджить сам
- Удалить тестовую ветку

**6.6. Smoke-test:**
```bash
bash .claude/hooks/smoke-test.sh
# Должно выйти 0 (всё ок)
```

**Если любой тест провалился:**
1. Записать что именно не сработало
2. Откатить через rollback plan (см. ниже)
3. Доложить пользователю, разобраться

### Контрольная точка после этапа 6

- Все 6 тестов пройдены
- Тестовый PR смерджен автоматически (proof of concept)
- Пользователь получил отчёт «всё работает»

---

## Этап 7 — Чистка stash

**Кто:** Claude + пользователь.
**Время:** ~10 минут.

### Действия

**7.1. Выдать пользователю обозримый список:**
```bash
git stash list --date=short --pretty='%gd | %cd | %s'
# 19 строк. Для каждой:
git stash show stash@{N} --stat | head -5
```

**7.2. Сгруппировать по принципу очевидности:**
- Старше 30 дней + неясное название → предложить drop по умолчанию
- С понятным WIP-маркером → спросить пользователя
- Свежие (< 7 дней) → не трогать без явного «да»

**7.3. Выдать пользователю одним сообщением:**
```
stash@{0}: <name>, <date>, <files> — RECOMMEND: <keep/drop>
stash@{1}: ...
...
```
И вопрос: «По умолчанию делаю drop на всё что RECOMMEND drop. Оставить какие-то?»

**7.4. По ответу — `git stash drop` или `git stash pop` или оставить.**

### Контрольная точка

- `git stash list` короткий (< 5 записей), пользователь подтвердил каждую остающуюся.

---

## Этап 8 — Финальный отчёт и обновление памяти

**Кто:** только Claude.
**Время:** ~5 минут.

### Действия

**8.1. Обновить `MEMORY.md`:**

Добавить запись:
```markdown
- [Workflow Guard](project_workflow_guard.md) — DONE 2026-05-12: хуки + GitHub защита + terminal pre-push, см. план `docs/superpowers/plans/2026-05-12-claude-workflow-setup.md`
```

И создать `project_workflow_guard.md` с описанием итогов.

**8.2. Финальный отчёт пользователю:**
- Что сделано (галочкой по этапам)
- Сколько worktree удалено / сколько осталось
- Сколько коммитов слилось в main
- Тестовый PR смерджен в автомате (URL)
- Что мониторить первые дни: hygiene smoke-test alerts

**8.3. Открытые follow-ups для будущих сессий:**
- (опционально) Codex GH Action для второго AI-ревьюера
- Чистка 60 локальных + 71 удалённых веток через расширенный hygiene (произойдёт само в следующие дни)
- Мониторить первую неделю: не блокирует ли guard легитимную работу

---

## Rollback план

Если что-то пойдёт не так на любом этапе:

**Откат этапа 1 (cleanup):** 
- Точка возврата `pre-workflow-setup` (tag)
- `git reset --hard pre-workflow-setup` если что-то критичное удалили
- Worktree-ветки восстановить не получится (force-deleted), но через `git reflog` можно достать SHA коммитов и пересоздать

**Откат этапа 2 (W1 merge):**
- `git revert <merge-commit-sha>` если merge оказался плохим
- Worktree-ветки сохранены до merge, можно пересоздать из них

**Откат этапа 4 (hooks):**
- Открыть `.claude/settings.json` ВНЕ Claude (через VSCode/nano/etc)
- Удалить блок `"hooks": {...}`
- Сохранить — хуки перестают срабатывать с следующей сессии
- Также `git config --unset core.hooksPath` чтобы pre-push не блокировал

**Откат этапа 5 (GitHub):**
- `gh api -X PUT /repos/.../rulesets/12853246 --input /tmp/ruleset-12853246-backup.json`
- `gh api -X PATCH /repos/danila-matveev/Wookiee -F allow_auto_merge=false`

---

## Critical assumptions and what could go wrong

**1. CI квалити как единственный гейт** — после починки ruff CI станет зелёным, но pytest тесты слабые. Auto-merge будет срабатывать на «зелёный ruff + compileall + slim tests». Это **сознательная плата за автономность** на старте. Усиление через Codex GH Action — отдельный PR позже.

**2. Хук-обход через творческий bash** — `python -c`, `bash -c`, `eval`, `base64 -d` блокируются регексами в git-firewall, но любой sufficiently-creative обход возможен. Реальная гарантия — этап 5 (GitHub-side). Локальные хуки = первая линия + UX.

**3. Сессии-зомби** — если Claude-сессия упала через kill -9, Stop hook не сработает, session-registry будет грязный. SessionStart на следующем старте прунит мёртвые pid'ы — self-healing.

**4. Hygiene-бот после migration** — может упереться в required_status_checks если его собственные коммиты вызовут ruff-ошибки. Решение: hygiene в bypass_actors mode=pull_request (применяется в 5.3).

**5. CI flaky** — если quality job начнёт падать на network/Supabase availability, auto-merge встанет. Мониторить первую неделю.

**6. Pre-push hook не активируется автоматически** — нужно `git config core.hooksPath git-hooks` в каждом клоне локально. В AGENTS.md — инструкция для будущих клонов. На текущем repo — применяется в этапе 4.

**7. Параллельные сессии и subagents** — если Claude дёргает Task (subagent), у subagent отдельный session_id, отдельная SessionStart-инжекция. Может дублировать записи в registry. Smoke-test проверит что не ломается.

---

## Success criteria

После полного исполнения плана:

✓ Все 32+ worktree удалены кроме легитимных
✓ Все 8 W1.x коммитов в main одним PR
✓ Все W2-W4 коммиты в main (либо своим PR от второй сессии, либо нашим bundle)
✓ Симлинк `/tmp/wookiee-crm-p5/.env` снят
✓ CI quality зелёный
✓ Прямой push в main невозможен ни из Claude-сессии, ни из mac-терминала, ни через GitHub UI (только force через bypass-actors)
✓ Любая правка `.claude/settings.json` через Claude → блокировка
✓ Любая Claude-сессия на main → read-only с автоматической инжекцией контекста
✓ Auto-merge срабатывает после CI green без участия пользователя
✓ Hygiene daily включает stale-worktree чистку + smoke-test защиты
✓ Stash короткий
✓ MEMORY.md обновлён с pointer на этот план

---

## Что НЕ в этом плане (осознанно)

- **Codex review как обязательный GitHub gate** — полдня работы, отложено до следующей итерации
- **GPG подпись коммитов** — избыточно для одного разработчика
- **Чистка 60 локальных + 71 remote веток** — произойдёт автоматически через расширенный hygiene в течение 14 дней после установки
- **CODEOWNERS файл** — не нужен с `required_approving_review_count: 0`
- **Required signatures** — сломает hygiene-бот и Claude commits

---

## Reference

- Memory style: `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/feedback_plain_language.md`
- Memory communication: `~/.claude/projects/.../memory/feedback_communication_rules.md`
- Memory verification: `~/.claude/projects/.../memory/feedback_verify_before_done.md`
- Существующие skill'ы для переиспользования: `~/.claude/skills/gstack-careful/bin/check-careful.sh`, `~/.claude/skills/gstack-freeze/bin/check-freeze.sh`, `~/.claude/skills/pullrequest/SKILL.md`
- Hook docs reference: `~/.claude/plugins/cache/claude-plugins-official/claude-code-setup/1.0.0/skills/claude-automation-recommender/references/hooks-patterns.md`
- AGENTS.md проекта
- CLAUDE.md проекта
