# Master Prompt — Telemost Recorder Phase 0 (autonomous execution)

> Этот файл — единственный prompt, который надо вставить в свежую сессию Claude Code (в директории `~/Projects/Wookiee`). Всё остальное — спека, план, .env, инфраструктура — уже на месте.

---

# 🎬 PROMPT START — копируй всё ниже

Ты работаешь в репозитории Wookiee. Твоя задача — реализовать **Telemost Recorder Phase 0** (Telegram-only MVP) полностью, автономно, через subagent-driven workflow.

## Контекст

- **Спека:** `docs/superpowers/specs/2026-05-07-telemost-recorder-production-design.md` (§11 — Phase 0)
- **План:** `docs/superpowers/plans/2026-05-08-telemost-recorder-phase-0.md` — 21 задача, полный TDD-код в каждом шаге
- **Конечная цель:** пользователь пишет `/record <url>` в `@wookiee_recorder_bot` → через ~50 минут получает в DM structured summary + полный transcript как `.txt` attachment.
- **Существующий MVP:** `services/telemost_recorder/` (recorder-контейнер) + `tests/services/telemost_recorder/` — НЕ ТРОГАЙ, он уже работает. Phase 0 строит API-слой над ним в `services/telemost_recorder_api/`.
- **Бот уже создан:** `@wookiee_recorder_bot` (id `8692087684`), токен в `.env` как `TELEMOST_BOT_TOKEN`.

## Pre-flight (выполни ДО первой задачи)

1. **Прочитай оба файла целиком:**
   - `docs/superpowers/specs/2026-05-07-telemost-recorder-production-design.md`
   - `docs/superpowers/plans/2026-05-08-telemost-recorder-phase-0.md`

2. **Проверь ветку.** Спека и план лежат на `catalog-rework-2026-05-07`. Перед началом:
   ```bash
   git checkout main && git pull
   git merge catalog-rework-2026-05-07 --no-edit  # подтяни spec+plan в main
   git checkout -b telemost-recorder-phase-0
   ```
   Если merge даёт конфликты — НЕ сливай, оставайся на `catalog-rework-2026-05-07` и работай там, а в финальном отчёте предупреди пользователя.

3. **Verify три риска из self-review плана:**
   - **CLI существующего recorder:** `python scripts/telemost_record.py --help` — поддерживает ли `--meeting-id` и `--output-dir`? Если нет — добавь argparse-флаги в `scripts/telemost_record.py` отдельной задачей 13.0 ДО Task 13. Сохрани обратную совместимость со старыми позиционными аргументами.
   - **Bitrix telegram-поле:** `curl ${BITRIX24_WEBHOOK_URL}/user.fields.json | jq` — в Task 7 в `_TELEGRAM_FIELD_KEYS` подставь реальное имя поля.
   - **Поддомен `recorder.os.wookiee.shop`:** wildcard `*.os` уже резолвится (см. memory `project_dns_subdomain_setup.md`). Если в Task 20 step 5 после `caddy reload` LE-handshake падает — fallback на `os.wookiee.shop/recorder` через path-routing.

4. **Capacity check:**
   ```bash
   ssh timeweb "free -h && df -h /home"
   ```
   В Phase 0 `MAX_PARALLEL_RECORDINGS=1` независимо от capacity, но если RAM < 4GB — пришли алерт через `TELEGRAM_ALERTS_BOT` владельцу, прежде чем продолжать.

## Способ исполнения

**Используй `superpowers:subagent-driven-development`.**

Для каждой из 21 задачи плана:
1. Извлеки полный текст задачи (все шаги, всё code) из `docs/superpowers/plans/2026-05-08-telemost-recorder-phase-0.md`.
2. Диспатчни **implementer-subagent** через `Task` с инструкциями: «Реализуй задачу N точно по плану. TDD. После каждого commit — STOP и report».
3. После DONE — диспатчни **spec-compliance reviewer** (проверяет, что код соответствует спеке + плану, ничего лишнего).
4. После ✅ — диспатчни **code-quality reviewer** (TDD discipline, type hints, idiomatic Python, no dead code).
5. Реви-цикл, пока обе review-стадии не дадут ✅.
6. Mark задачу complete в TodoWrite, переходи к следующей.

**Между задачами** — мини-диагностика: `git log --oneline -5`, `pytest tests/services/telemost_recorder_api/ -q`. Все тесты накапливаются и должны проходить на любом этапе.

**Параллелить НЕЛЬЗЯ.** Задачи 1-21 идут строго последовательно — каждая зависит от предыдущей.

## Quality gates

После каждой задачи:
- Все тесты сервиса проходят: `pytest tests/services/telemost_recorder_api/ -v`
- Существующие тесты не сломаны: `pytest tests/services/telemost_recorder/ -v`
- Один коммит на задачу, conventional commits format

Финальный gate (после Task 21):
- E2E acceptance в боте прошёл (см. Task 21 шаги 1-14)
- Запись реальной 3-минутной встречи → DM с summary + transcript.txt
- Edge: пустая встреча → «речь не распознана»
- Edge: invalid URL → корректное сообщение
- Edge: concurrent uniqueness → второй `/record` отвечает «уже в работе»

## Стоп-условия

**Останавливайся и эскалируй пользователю**, если:
- 3 раза подряд reviewer возвращает ту же claim
- Tests падают по причине, которой нет в плане (новый bug в существующем коде)
- Spec противоречит сама себе (приоритетнее план — он более детальный)
- Любая destructive операция: `docker rmi`, `git reset --hard`, `git push --force`, удаление таблиц — НИКОГДА без явного approval от пользователя
- Нужны секреты, которых нет в `.env`
- Capacity check показал RAM < 2GB или disk < 5GB

**НЕ ОСТАНАВЛИВАЙСЯ** на:
- LLM-сабагент задаёт вопрос → отвечай сам, исходя из плана/спеки. План достаточно детален.
- Реви находит мелкие nits → пускай implementer фиксит, продолжай.
- Тест требует обновления mock из-за уточнения — это нормальная часть TDD, обнови тест и повтори.

## Важные правила проекта (из CLAUDE.md)

- Общение с пользователем — на русском
- Деньги: НЕ float, только Decimal (Phase 0 не имеет money-логики, неактуально)
- Type hints на public API в `services/`
- async-паттерны: `asyncio.gather` для параллели, `asyncio.wait_for` на внешние вызовы, никогда `time.sleep` в async
- Секреты — только `.env`, никогда в коде
- НЕ редактируй файлы НА сервере (autopull сотрёт)
- Деплой: `ssh timeweb` → `cd /home/danila/projects/wookiee && git pull` → `docker compose up -d --build`
- Supabase: RLS обязателен на всех новых таблицах (миграции 001-002 уже это включают)

## Финальный отчёт

Когда Task 21 закрыт и acceptance пройден — пришли пользователю:

1. **Summary:** что сделано (одним абзацем)
2. **Branch:** `telemost-recorder-phase-0`, N коммитов
3. **Tests:** счётчики (X passed, Y total)
4. **Live URL:** `https://recorder.os.wookiee.shop/health` — статус
5. **Bot status:** результат `/start` от пользователя в `@wookiee_recorder_bot`
6. **Известные ограничения Phase 0** (без календаря, без Notion, MAX_PARALLEL=1)
7. **Что делать пользователю прямо сейчас:** «Поставь любую встречу в Я.Телемост, кинь её URL мне в `/record` — приду с summary через ~50 минут после её окончания.»
8. **Готов ли к Phase 1?** — да/нет/блокеры
9. **Memory updates:** добавь/обнови `project_telemost_recorder.md` в `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/` — что Phase 0 деплойнут, ссылка на бот, branch и PR.

Поехали. Начинай с pre-flight, потом Task 1.

# 🎬 PROMPT END
