# Hygiene Follow-up Skill — Design

**Дата:** 2026-04-29
**Цель:** автоматически закрывать issue/PR-ы от `/hygiene`, если их пункты исчезли (детектор был починен или мир изменился), без рисков авто-удаления живого кода.

## Контекст

Главный `/hygiene` cron бежит в 03:00 UTC. Если есть пункты на ревью — открывает issue или PR. Эти артефакты копятся, потому что:
1. Часть пунктов — false positive самого детектора. После фикса детектора пункт исчезает на следующем cron, но **старый issue остаётся открытым**.
2. Часть пунктов — реальные, и юзер их разрулил руками, но забыл закрыть.
3. Часть — ждёт следующего cron-прогона для авто-фикса.

Без автоматического follow-up каждый день добавляется один issue/PR, никто их не закрывает, тимлид (юзер) тонет в шуме.

## Не-цели (NON-GOALS)

**Это НЕ авто-рефактор.** Скилл НЕ удаляет код, НЕ редактирует файлы, НЕ ходит в БД на write. Только:
- читает issue/PR
- перезапускает соответствующие чек-команды на свежем `main`
- закрывает или комментирует issue/PR

Reasoning: за последнюю неделю 3+ пункта в `ask`-бакете оказались false positives детектора (8 живых `sync_*.py`, 4 валидных tools-row, 3 существующих файла). Auto-fix их бы сломал прод.

Возможный авто-фикс безопасных категорий — Phase 2 (отдельный milestone).

## Архитектура

```
            ┌─────────────────────┐
03:00 UTC   │  /hygiene (main)    │ ─── создаёт issue/PR с findings
            └─────────────────────┘
                       │
                       │ 3 часа на стабилизацию + buffer для main
                       ▼
            ┌─────────────────────┐
06:00 UTC   │ /hygiene-followup   │
            └─────────────────────┘
                       │
                       ▼
   ┌───────────────────────────────────────────┐
   │ 1. FETCH                                   │
   │    gh issue/PR list with title pattern    │
   │    "hygiene followups —" or label hygiene │
   ├───────────────────────────────────────────┤
   │ 2. PARSE                                   │
   │    Разобрать body → список (check, paths) │
   ├───────────────────────────────────────────┤
   │ 3. RE-RUN                                  │
   │    Для каждого check взять команду из     │
   │    detect.md и выполнить на свежем main   │
   ├───────────────────────────────────────────┤
   │ 4. CLASSIFY (по каждому пункту)            │
   │    a. RESOLVED — пункт исчез              │
   │    b. STILL — пункт всё ещё актуален      │
   │    c. PARTIAL — часть путей пропала       │
   ├───────────────────────────────────────────┤
   │ 5. ACT                                     │
   │    - все RESOLVED → close issue           │
   │    - смешанно → comment + strikethrough   │
   │    - все STILL → no-op                    │
   ├───────────────────────────────────────────┤
   │ 6. NOTIFY                                  │
   │    Telegram только если что-то закрыли    │
   ├───────────────────────────────────────────┤
   │ 7. LOG (tool_runs)                         │
   └───────────────────────────────────────────┘
```

## Маппинг finding → check

Hygiene-issue-body содержит секции вида:
```
### skill-registry-drift: orphan entries in DB
- Paths: tools table — bitrix-task, finolog
```

Парсер извлекает:
- `check_name` = `skill-registry-drift` (первое слово после `### ` до `:`)
- `paths` = из `Paths:` строки

Каждый `check_name` маппится на блок в `detect.md`. Скилл выполняет тот же bash и сравнивает вывод с оригинальными `paths`.

## Re-run policy

| Check | Re-run? | Закрытие если исчез? |
|---|---|---|
| `skill-registry-drift` | yes | yes |
| `orphan-imports` | yes | yes |
| `orphan-docs` | yes | yes |
| `broken-doc-links` | yes | yes |
| `missing-readme` | yes | yes |
| `stale-branches` | yes | yes |
| `structure-conventions` | LLM-driven, skip auto-revalidation | manual close |
| `obsolete-tracked-files` | yes | yes |
| `security-scan` | yes (но это flag_immediate, обычно не в ask) | yes |

`structure-conventions` — единственная LLM-driven проверка, авто-revalidation ненадёжна, оставляем юзеру.

## Hard-rules

- **NEVER** редактировать файлы / удалять / делать commit-push.
- **NEVER** трогать issue/PR не от hygiene (фильтр строго по title-паттерну `hygiene followups —` или label `hygiene`).
- **NEVER** закрывать issue с открытым PR, на который ссылается текст (если PR ещё не замерджен — пункт может зависеть от него).
- **NEVER** закрывать issue моложе 24 часов (даём юзеру шанс посмотреть до автоматики).

## Phase 1 (MVP, scope этого спеки)

Только верификация и закрытие. 6 шагов выше.

## Phase 2 (отдельный milestone, не делаем сейчас)

Авто-фикс STILL-пунктов в безопасных категориях:
- `missing-readme` → создать stub README с TODO
- `unregistered project skill` → вызвать `/tool-register`
- `cross-platform-skill-prep` → запустить `/ecosystem-sync sync`

Каждое расширение требует отдельной валидации.

## Файлы

- `.claude/skills/hygiene-followup/SKILL.md` — описание скилла
- `.github/workflows/hygiene-followup-daily.yml` — cron 06:00 UTC
- (опционально) `.claude/skills/hygiene-followup/prompts/parse.md` — парсер issue body
- (опционально) `.claude/skills/hygiene-followup/prompts/revalidate.md` — re-run logic per check

## Стоимость

- 1 раз в день, ~5-10 мин (только grep/bash, минимум LLM)
- ~5-10k tokens (парсинг body + decision per finding)
- Не блокирует пользователя

## Метрики успеха через 2 недели

- 0 открытых hygiene-issue старше 7 дней без активности
- среднее время жизни false-positive issue: < 36 часов (один cycle main + один follow-up)
- 0 случаев когда follow-up закрыл RESOLVED пункт по ошибке (false negative)
