# Саймон — план боевого запуска (исполнение)

**Контекст:** Все 7 PR смержены в `main`. Главный коммит `b34e8ade feat(saimon): voice triggers Phase 2 (Bitrix writes) (#163)` от 2026-05-17. Этот файл — точная пошаговая инструкция для **новой сессии Claude Code** чтобы развернуть Саймона в продакшен прямо сейчас, без растягивания на 10 дней.

**Источники истины:**
- [SPEC.md](SPEC.md) — что и зачем строим (v1.1)
- [RUNBOOK.md](RUNBOOK.md) — operator runbook (написан в T7)
- [PLAN.md](PLAN.md) — план задач T1-T7
- этот файл — конкретный одношаговый rollout

**Решение пользователя (Данила, 2026-05-17):** запускаем всё сейчас, в одной волне, без поэтапной раскатки по дням. Все технические fixes и backlog'и собираем сразу.

---

## Карта PR (для контекста новой сессии)

| # | Задача | PR | Merge time |
|---|--------|-----|------------|
| T1 | Переименование в «Саймон» | [#155](https://github.com/danila-matveev/Wookiee/pull/155) | merged |
| T2 | `shared/yandex_telemost.py` wrapper | [#157](https://github.com/danila-matveev/Wookiee/pull/157) | merged |
| T3 | OAuth Telemost health-check | [#159](https://github.com/danila-matveev/Wookiee/pull/159) | merged |
| T4 | scheduler_worker multi-user | [#160](https://github.com/danila-matveev/Wookiee/pull/160) | merged |
| T5 | Утренний дайджест + кнопка ➕ Добавить Telemost | [#161](https://github.com/danila-matveev/Wookiee/pull/161) | merged |
| T6 | Voice-triggers Phase 1 (детекция) | [#162](https://github.com/danila-matveev/Wookiee/pull/162) | 2026-05-17 14:14 UTC |
| T7 | Voice-triggers Phase 2 (Bitrix writes) + миграция 006 + RUNBOOK | [#163](https://github.com/danila-matveev/Wookiee/pull/163) | 2026-05-17 14:37 UTC |

---

## Промт для новой сессии Claude Code

```
Я — Данила. У меня все 7 PR Саймона смержены в main (#155, #157, #159, #160, #161, #162, #163). Сейчас раскатываю в прод за одну волну, не растягивая на 10 дней.

ИСТОЧНИК ИСТИНЫ:
- docs/projects/saimon/ROLLOUT_EXECUTION.md — этот файл, точный план
- docs/projects/saimon/RUNBOOK.md — operator runbook
- docs/projects/saimon/SPEC.md — спецификация v1.1

ИНСТРУКЦИЯ:
Выполни блоки 0-9 строго по порядку. После каждого блока — отчёт «✅ Блок N выполнен» + что именно сделано + куда смотреть в случае проблем. Если блок упал — STOP, опиши проблему, жди от меня указаний.

Я в Mode 1 (Solo). Не дёргай сабагентов, работай прямо. Я даю явное разрешение на:
- Применение миграции через Supabase MCP
- SSH на timeweb сервер (`ssh timeweb`)
- Правка .env на сервере (через /update-env скилл если есть, иначе ssh + nano) — это явное разрешение, обычное правило «не редактировать на сервере» в этом случае не применяется
- docker compose restart / up -d на сервере
- Создание PR с фиксами багов (блоки 5-8 ниже) — auto-merge через /ship или gh pr merge --auto

Я НЕ хочу чтобы ты создавал worktrees для fix-PR — используй ветки из main checkout (parent worktree сейчас на feat/hub-shell-unification, переключайся на main через git checkout main).

Начинай с блока 0 (pre-flight checks).
```

---

## Блок 0 — Pre-flight checks (валидация состояния)

**Что:** убедиться что main содержит #163 и все артефакты T7 на месте, до того как трогать прод.

```bash
cd /Users/danilamatveev/Projects/Wookiee
git fetch origin main
git log -1 --pretty='%h %s' origin/main
# Ожидание: содержит "voice triggers Phase 2 (Bitrix writes) (#163)"

# Проверка артефактов T7
ls -la services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql
ls -la shared/bitrix_writes.py
ls -la services/telemost_recorder_api/voice_candidates_repo.py
ls -la services/telemost_recorder_api/handlers/voice_actions.py
ls -la docs/projects/saimon/RUNBOOK.md
```

**Проверка наличия критичных env на сервере** (без раскрытия значений):
```bash
ssh timeweb 'grep -E "^(BITRIX24_WEBHOOK_URL|OPENROUTER_API_KEY|DATABASE_URL|TELEMOST_BOT_TOKEN|YANDEX_TELEMOST_OAUTH_TOKEN|YANDEX_TELEMOST_REFRESH_TOKEN|YANDEX_TELEMOST_CLIENT_ID|YANDEX_TELEMOST_CLIENT_SECRET)=" /home/danila/projects/wookiee/.env | awk -F= "{print \$1}"'
```

Должны вывестись все 8 ключей. Если чего-то нет — STOP, спроси Данилу.

**ВАЖНО про Bitrix webhook:** `BITRIX24_WEBHOOK_URL` должен поддерживать `tasks.task.add` + `calendar.event.add` (write scope). Если текущий webhook был выпущен только на чтение — `create_task()` / `create_calendar_event()` будут отвечать 401. Уточни у Данилы перед блоком 6 (тестирование handlers).

Если pre-flight всё ОК → переходи к блоку 1.

---

## Блок 1 — Применить миграцию 006 в Supabase

**Что:** создать таблицу `telemost.voice_trigger_candidates` (T7 persistence).

**Файл:** `services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql`

**Способ A — через Supabase MCP (предпочтительно):**

```
mcp__supabase__apply_migration
  project_id: "gjvwcdtfglupewcwzfhw"
  name: "006_voice_trigger_candidates"
  query: <вставить содержимое файла 006_*.sql>
```

**Способ B — через psql на сервере (если MCP недоступен):**

```bash
ssh timeweb 'PGPASSWORD=$(grep ^DATABASE_URL /home/danila/projects/wookiee/.env | sed -E "s/.*:([^:@]+)@.*/\1/") \
  psql -h 89.23.119.253 -p 6433 -U claude -d wookiee_db' \
  < services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql
```

**Проверка:**
```sql
SELECT count(*) FROM telemost.voice_trigger_candidates;  -- 0
SELECT * FROM pg_indexes WHERE tablename = 'voice_trigger_candidates';  -- idx_vtc_meeting должен быть
SELECT relrowsecurity FROM pg_class WHERE oid = 'telemost.voice_trigger_candidates'::regclass;  -- true
```

**Если упало:** проверь что миграция 005 (`005_meetings_calendar_uniq.sql`) уже применена через `SELECT * FROM supabase_migrations.schema_migrations`.

---

## Блок 2 — Обновить .env на сервере (все Саймон-флаги)

**Что:** включить 3 flag-env'а + закрепить `TELEMOST_BOT_NAME`. Остальные env (`YANDEX_TELEMOST_*`, `BITRIX24_WEBHOOK_URL`) должны быть уже из предыдущих rollout-ов (T2, T3) — проверили в блоке 0.

**Что добавляем/правим:**

| Env | Значение | Откуда |
|---|---|---|
| `TELEMOST_BOT_NAME` | `Саймон` | T1, после BotFather rename — должен совпадать |
| `TELEMOST_SCHEDULER_ENABLED` | `true` | T4, по умолчанию `false` |
| `MORNING_DIGEST_ENABLED` | `true` | T5, по умолчанию `false` |
| `VOICE_TRIGGERS_ENABLED` | `true` | T6/T7, по умолчанию `false` |

**Что НЕ трогаем (уже должны быть):**
- `TELEMOST_BOT_TOKEN`, `BITRIX24_WEBHOOK_URL`, `OPENROUTER_API_KEY`, `DATABASE_URL`
- `YANDEX_TELEMOST_OAUTH_TOKEN`, `YANDEX_TELEMOST_REFRESH_TOKEN`, `YANDEX_TELEMOST_CLIENT_ID`, `YANDEX_TELEMOST_CLIENT_SECRET`

**Через скилл `/update-env`** (если доступен в новой сессии), либо вручную:

```bash
ssh timeweb 'cat >> /home/danila/projects/wookiee/.env <<EOF

# Саймон rollout 2026-05-17 (одношаговая раскатка вместо 10-дневной)
TELEMOST_BOT_NAME=Саймон
TELEMOST_SCHEDULER_ENABLED=true
MORNING_DIGEST_ENABLED=true
VOICE_TRIGGERS_ENABLED=true
EOF'
```

**Проверка:**
```bash
ssh timeweb 'grep -E "^(TELEMOST_BOT_NAME|TELEMOST_SCHEDULER_ENABLED|MORNING_DIGEST_ENABLED|VOICE_TRIGGERS_ENABLED)=" /home/danila/projects/wookiee/.env'
```

**Замечание:** `TELEMOST_BOT_NAME=Саймон` должен совпадать с тем именем которое Данила выставит в BotFather (см. раздел «Что делает Данила»). Если у Данилы получилось «Саймон 🎙» с эмодзи или другой вариант — обновить `.env` соответственно.

---

## Блок 3 — Перезапустить контейнеры

**Что:** Recreate `wookiee_cron` (новые env-переменные подхватятся) + restart `wookiee_api` (зарегистрировать новые callback handlers из T7).

**Важно из SPEC §6.3:** контейнер `wookiee_cron` подтянет новые `YANDEX_TELEMOST_*` только после `docker compose up -d wookiee-cron` (без `--build`). Просто `restart` не пересоздаст env-окружение контейнера.

```bash
ssh timeweb 'cd /home/danila/projects/wookiee/deploy && \
  docker compose up -d wookiee-cron && \
  docker compose restart wookiee-api && \
  docker compose ps | grep -E "wookiee-(cron|api)"'
```

**Проверка логов:**
```bash
ssh timeweb 'docker logs wookiee-api --tail 80 2>&1 | grep -iE "saimon|telemost|scheduler|morning_digest|handlers|error"'
ssh timeweb 'docker logs wookiee-cron --tail 80 2>&1 | grep -iE "saimon|telemost|cookie|oauth|error"'
```

Ожидаемые строки в `wookiee-api`:
- `scheduler_worker started` (или аналог — реальное имя см. в `services/telemost_recorder_api/workers/scheduler_worker.py`)
- `morning_digest loop started at 09:00 MSK`
- handlers registered: `task_create`, `task_edit`, `task_ignore`, `meeting_create`, `meeting_edit`, `meeting_ignore`, `add_telemost`, `voice:*:disabled` (legacy fallback)

Ожидаемое в `wookiee-cron`:
- cookie health check at 08:00 MSK
- OAuth Telemost health check

**Проверка Telegram webhook (важно для callback кнопок):**
```bash
ssh timeweb 'docker exec wookiee-api python3 -c "
import asyncio, httpx, os
async def main():
    token = os.environ[\"TELEMOST_BOT_TOKEN\"]
    async with httpx.AsyncClient() as c:
        r = await c.get(f\"https://api.telegram.org/bot{token}/getWebhookInfo\")
        print(r.json())
asyncio.run(main())
"'
```

Поле `allowed_updates` должно содержать `callback_query`. Если нет — restart api не помог, нужно перерегистрировать webhook через `scripts/telemost_setup_webhook.py`.

---

## Блок 4 — Запустить полный test suite локально

**Что:** убедиться что main зелёный после всех 7 merge-ей.

```bash
cd /Users/danilamatveev/Projects/Wookiee
git checkout main && git pull
python3 -m pytest -q tests \
  --ignore=tests/product_matrix_api \
  --ignore=tests/services/influencer_crm \
  --ignore=tests/services/telemost_recorder \
  --ignore=tests/services/telemost_recorder_api \
  --ignore=tests/scripts/test_telemost_setup_webhook.py \
  --ignore=tests/wb_localization/test_cabinet_filter.py \
  --deselect tests/services/logistics_audit/test_excel_sheets.py::test_generate_full_workbook \
  --deselect tests/services/logistics_audit/test_models.py::test_audit_config \
  --deselect tests/services/logistics_audit/test_tariff_etl.py::test_load_historical_tariff_rows_maps_defaults_and_counts \
  --deselect tests/test_market_review_collectors.py::TestTopModelsOurs::test_returns_note_when_no_skus \
  --deselect tests/test_market_review_collectors.py::TestTopModelsRivals::test_returns_note_when_no_skus \
  --deselect tests/test_reviews_audit_collector.py::TestCollectDataV2::test_output_structure_v2 \
  --deselect tests/services/analytics_api/test_marketing_sync.py::test_trigger_sync_without_api_key_returns_401 \
  --deselect tests/services/analytics_api/test_marketing_sync.py::test_trigger_sync_with_wrong_api_key_returns_401 \
  2>&1 | tail -25
```

(Точный набор `--ignore` и `--deselect` — из `.github/workflows/ci.yml`.)

Затем отдельно прогнать T6+T7 тесты которые работают на моках:
```bash
TELEMOST_DISABLE_DOTENV=1 python3 -m pytest \
  tests/services/telemost_recorder_api/test_voice_triggers.py \
  tests/services/telemost_recorder_api/handlers/test_voice_actions.py \
  tests/shared/test_bitrix_writes.py \
  -v 2>&1 | tail -30
```

Ожидание: 35+ T6/T7 тестов passed, общий suite green (с исключениями выше).

**Pre-existing flaky** (которые упадут даже на main):
- `tests/services/telemost_recorder_api/test_notifier.py::test_notify_sends_summary_and_transcript` — фикстура шлёт 1 параграф, порог `_TRANSCRIPT_FILE_MIN_PARAGRAPHS = 15` (фикс в блоке 5)
- `test_notifier.py` целиком требует env stubs (`TELEMOST_BOT_TOKEN` и др.) — нормально что он падает в локальном прогоне без `.env`, в CI он исключён через `--ignore=tests/services/telemost_recorder_api`

---

## Блок 5 — Fix PR #1: pre-existing flaky тест notifier

**Проблема:** `tests/services/telemost_recorder_api/test_notifier.py::test_notify_sends_summary_and_transcript` падает потому что фикстура шлёт 1 параграф, а порог `_TRANSCRIPT_FILE_MIN_PARAGRAPHS = 15`. Тест устарел с коммита `0b9e9855` (13 мая, до T6).

**Фикс:** обновить фикстуру — добавить 15+ параграфов.

**Workflow:**
1. `git checkout main && git pull && git checkout -b fix/saimon-notifier-test-threshold`
2. Открыть `tests/services/telemost_recorder_api/test_notifier.py` строки 158-160, развернуть `processed_paragraphs` до 15+ записей с разными speaker/text
3. Локальный прогон (с env stubs):
   ```bash
   TELEMOST_DISABLE_DOTENV=1 TELEMOST_BOT_TOKEN=stub DATABASE_URL=postgresql://stub OPENROUTER_API_KEY=stub BITRIX24_WEBHOOK_URL=https://stub \
     python3 -m pytest tests/services/telemost_recorder_api/test_notifier.py -v 2>&1 | tail -15
   ```
4. Коммит:
   ```
   fix(saimon): expand notifier fixture to 15 paragraphs for transcript threshold

   _TRANSCRIPT_FILE_MIN_PARAGRAPHS=15 introduced in 0b9e9855 (May 13)
   left existing test_notify_sends_summary_and_transcript fixture
   below threshold — assertions on docs[0] passed at write time but
   broke after the threshold landed. Test was masked because the
   whole tests/services/telemost_recorder_api/ tree is excluded in
   CI. Restore fixture to match production preconditions.

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
5. Push, открыть PR через `gh pr create`, auto-merge через `gh pr merge --auto --squash --delete-branch`.

---

## Блок 6 — Fix PR #2: `_resolve_bitrix_id` substring → word-boundary

**Проблема:** `_resolve_bitrix_id` в `services/telemost_recorder_api/handlers/voice_actions.py` использует substring search по `short_name`. False positive: «Ева» внутри «Евдокия», «Аня» внутри «Татьяна». Сейчас в команде Wookiee коллизий нет, но это технический долг — отметили в spec/quality review T7.

**Фикс:** заменить substring на word-boundary regex или точное сравнение `name.strip().lower() == query.strip().lower()`.

**Workflow:**
1. `git checkout main && git pull && git checkout -b fix/saimon-bitrix-id-word-boundary`
2. Поправить `_resolve_bitrix_id` (поиск через `grep -n _resolve_bitrix_id services/telemost_recorder_api/handlers/voice_actions.py`):
   - подход: точное сравнение по нормализованному short_name + fallback на word-boundary regex по полному name
3. Добавить тест на коллизию имён в `tests/services/telemost_recorder_api/handlers/test_voice_actions.py`:
   ```python
   async def test_resolve_no_false_positive_on_short_name_substring():
       users = [{"bitrix_id": 1, "name": "Евдокия", "short_name": "Евдокия"},
                {"bitrix_id": 2, "name": "Ева", "short_name": "Ева"}]
       assert _resolve_bitrix_id("Ева", users) == 2
       assert _resolve_bitrix_id("Евдокия", users) == 1
   ```
4. Локальный прогон, push, PR с conventional commit:
   ```
   fix(saimon): use exact match + word boundary for Bitrix user resolution
   ```
5. Auto-merge.

---

## Блок 7 — Fix PR #3: `meeting_create` owner_id=1 fallback warning

**Проблема:** В `handlers/voice_actions.py::handle_meeting_create` (из quality review T7): когда спикер не резолвится через `telemost.users` → owner_id дефолтится в `1` (CEO Данила). Документировано в коде, но создание Bitrix-эвентов от лица CEO без явного предупреждения юзеру = тихая ошибка attribution. После роста команды это станет проблемой.

**Фикс:** при fallback на owner_id=1 — добавить:
1. `logger.warning("voice_action: speaker not resolved, defaulting owner_id=1 (CEO) for meeting candidate %s", candidate_id)`
2. К ответному сообщению юзеру дописать: `⚠️ Спикер не определён, событие создано от CEO. Перепривяжь владельца в Bitrix.`

**Workflow:**
1. `git checkout main && git pull && git checkout -b fix/saimon-meeting-owner-fallback-warning`
2. Найти `handle_meeting_create` в `services/telemost_recorder_api/handlers/voice_actions.py`
3. Добавить warning логи + текст в response
4. Обновить тест `test_voice_actions.py::test_meeting_create_*` чтобы покрыть fallback path и проверить что warning отправляется
5. Push, PR, auto-merge:
   ```
   fix(saimon): warn explicitly when meeting candidate falls back to CEO owner
   ```

---

## Блок 8 — Fix PR #4: маркер «автоматическая задача» в title + description

**Проблема:** Сейчас `handlers/voice_actions.py::handle_task_create` и `handle_meeting_create` создают задачи/события в Bitrix с тем title, который LLM извлёк из transcript (`extracted_fields["title"]` / `["name"]`). LLM может ошибиться — формулировка корявая, имена перепутаны, дедлайн неточный. Без явной метки получателю не понятно что задача автогенерирована и в ней могут быть некорректности — её не будут проверять/править, а просто примут к исполнению.

**Требование Данилы (2026-05-17):** каждая задача и каждое событие, которые Саймон создаёт автоматически по voice-trigger, должны быть явно помечены как auto-generated. Если в названии есть неточности — получателю нужно вернуться к Даниле/постановщику для уточнения, а не просто закрыть как есть.

**Фикс:**

1. **Title:** добавить префикс `[🤖 Саймон]` к `TITLE` для tasks и `name` для events:
   - Было: `"Сделать дашборд по продажам"`
   - Стало: `"[🤖 Саймон] Сделать дашборд по продажам"`

2. **Description:** добавить disclaimer-блок в начало `DESCRIPTION`:
   ```
   ⚠️ Эта задача создана автоматически Саймоном на основе расшифровки встречи [<meeting_id или title>] от <date>.

   Если формулировка некорректна, дедлайн/исполнитель указаны неверно — свяжись с постановщиком (Лиза Литвинова или Данила) для уточнения, не закрывай как есть.

   ---

   <оригинальный description с контекстом из transcript>
   ```

3. То же для `create_calendar_event`:
   - Префикс `[🤖 Саймон]` к `name`
   - Disclaimer в `description`

**Где править:**
- `services/telemost_recorder_api/handlers/voice_actions.py` — функции `handle_task_create` и `handle_meeting_create`, в местах где формируется `title`/`name` и `description` перед вызовом `create_task()` / `create_calendar_event()`.
- НЕ править `shared/bitrix_writes.py` — это generic-обёртка, маркер — это бизнес-логика конкретного caller'а.

**Тесты в `tests/services/telemost_recorder_api/handlers/test_voice_actions.py`:**
- `test_task_create_adds_saimon_marker_to_title` — проверить что `create_task` вызвался с `title` начинающимся с `[🤖 Саймон]`
- `test_task_create_adds_disclaimer_to_description` — проверить что `description` содержит «создана автоматически Саймоном»
- `test_meeting_create_adds_saimon_marker` — аналогично для calendar event

**Workflow:**
1. `git checkout main && git pull && git checkout -b fix/saimon-auto-marker`
2. Поправить `handle_task_create` + `handle_meeting_create` в `voice_actions.py`
3. Обновить существующие тесты + добавить 3 новых
4. Прогнать `TELEMOST_DISABLE_DOTENV=1 python3 -m pytest tests/services/telemost_recorder_api/handlers/test_voice_actions.py -v`
5. PR с conventional commit:
   ```
   fix(saimon): mark voice-trigger-created Bitrix tasks/events as auto-generated

   Adds [🤖 Саймон] prefix to title/name + disclaimer block to
   description for every task and calendar event created via
   voice-trigger handlers. Without explicit marking, recipients
   treated LLM-extracted formulations as human-curated and didn't
   flag inaccuracies in titles, deadlines, or assigned people.

   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   ```
6. Auto-merge через `gh pr merge --auto --squash --delete-branch`.

**Уточнения для эстетики (можно обсудить с Данилой):**
- Эмодзи `🤖` vs `🎙` (микрофон, как Саймон-бот в Telegram) — обсудить.
- Длина префикса: `[🤖 Саймон]` (15 символов) vs `[Саймон/auto]` (13) vs `🤖 ` (3). Чем короче префикс, тем больше места под суть в Bitrix-списках. Рекомендация: `[🤖 Саймон]` для максимальной заметности, особенно если в Bitrix UI title часто обрезается.

---

## Блок 9 — Создать `PHASE1_METRICS.md` template (для precision/recall)

**Что:** заготовка для сбора метрик voice-triggers Phase 1 после первых 5-10 звонков. Без этого не получится принять решение о calibration Stage 1 confidence threshold или о переходе на Phase 2 в более агрессивных условиях.

**Файл:** `docs/projects/saimon/PHASE1_METRICS.md` (новый)

**Структура:**
```markdown
# Voice-triggers Phase 1 — метрики precision/recall

После 5-10 реальных звонков с `VOICE_TRIGGERS_ENABLED=true` (без T7
персистенции — Phase 1 only) сюда заносим:

## Прогон от <дата>

| Звонок | Дата | Длительность | Stage 1 кандидатов | Stage 2 прошло | Реально valid (manual review) | False positives | Missed (recall miss) |
|--------|------|--------------|--------------------|----------------|-------------------------------|-----------------|----------------------|
| ... | ... | ... | ... | ... | ... | ... | ... |

## Итоги

- Precision: <valid / Stage2_passed * 100>%
- Recall (subjective): <valid / (valid+missed) * 100>%
- Stage 1 confidence threshold check: <текущий 0.5 — увеличить/уменьшить>
- Stage 2 model accuracy: <google/gemini-3-flash-preview vs anthropic/claude-sonnet-4-6 fallback>

## Решения

- [ ] Тюнить confidence threshold до X
- [ ] Переключить Stage 1/2 на другую модель
- [ ] Добавить нового intent type
- [ ] Что-то ещё
```

**Workflow:** добавить файл, коммит `docs(saimon): phase 1 metrics template for precision/recall tracking`, не пуш — оставить на ветке fix/* которая уже открыта (последняя из блоков 5-7), либо отдельным PR `docs/saimon-phase1-metrics`.

---

## Блок 10 — Финальный отчёт Даниле

После блоков 0-9 — структурированный отчёт:

```
✅ Pre-flight: main = b34e8ade (#163), все артефакты на месте, env критичные ОК
✅ Миграция 006 применена в Supabase (row count подтверждён)
✅ Env-флаги выставлены на сервере:
   TELEMOST_BOT_NAME=Саймон
   TELEMOST_SCHEDULER_ENABLED=true
   MORNING_DIGEST_ENABLED=true
   VOICE_TRIGGERS_ENABLED=true
✅ Контейнеры перезапущены:
   wookiee-cron recreated → новые env подхватились
   wookiee-api restarted → 6 callback handlers зарегистрированы
   webhook allowed_updates содержит callback_query
✅ Тесты:
   Общий suite: X passed (Y deselected как pre-existing — список Y)
   T6+T7 на моках: 35/35 passed
✅ Fix PR #1 (#NNN merged): notifier test threshold
✅ Fix PR #2 (#NNN merged): word-boundary Bitrix resolution
✅ Fix PR #3 (#NNN merged): meeting owner_id=1 warning
✅ Fix PR #4 (#NNN merged): [🤖 Саймон] auto-marker в title + disclaimer в description
✅ Блок 9: PHASE1_METRICS.md template создан

ОТКРЫТО:
1. ❗ Данила: BotFather rename + PNG (см. чек-лист ниже)
2. ❗ Данила: admin.yandex.ru rename + PNG
3. ❗ Данила: коммит PNG в data/branding/
4. ❗ Данила: ротация Yandex OAuth Client Secret (засветился в переписке)
5. ❗ Данила: боевой smoke-test (записать встречу с фразой «Саймон, ...»)
6. 🟡 T8 backlog: реальные edit-формы для дозаполнения дедлайна/исполнителя (сейчас placeholder, помечает кандидата `edited` и просит дозаполнить в Bitrix руками)
```

---

## Что делает Данила (физически — не из CLI)

### 1. PNG аватарки (квадрат + прямоугольник)

**Размеры:**
- Telegram (BotFather `/setuserpic`): квадратная PNG, рекомендация Telegram — **640×640 px** минимум, **PNG/JPG**, до 5 MB. Telegram сожмёт до 512×512.
- Yandex 360 (admin.yandex.ru аватар пользователя `recorder@wookiee.shop`): прямоугольная или квадратная, **400×400 px** минимум, **PNG/JPG**, до 5 MB.

**Куда положить:** в репо `data/branding/saimon_square.png` (для Telegram) и `data/branding/saimon_landscape.png` (для Yandex, если есть отдельный landscape вариант) или один квадратный для обоих.

**Workflow Данилы:**
1. Сгенерировать/нарисовать аватарку. Можно через DALL-E / Midjourney промптом «professional friendly meeting assistant robot avatar, Wookiee brand colors». Или поручить дизайнеру.
2. Сохранить как `data/branding/saimon_square.png` (минимум 640×640).
3. `git add data/branding/saimon_square.png && git commit -m "feat(saimon): add bot avatar PNG" && /ship`.
4. После merge — выполнить шаги 2-3 ниже (BotFather + admin.yandex.ru).

### 2. BotFather rename

В Telegram открыть @BotFather:
1. `/mybots` → выбрать существующий бот Telemost Recorder
2. `Edit Bot` → `Edit Name` → **«Саймон»** (или «Саймон 🎙» если хочешь эмодзи; убедись что `TELEMOST_BOT_NAME` в `.env` тоже совпадает)
3. `Edit Bot` → `Edit Description` → текст из SPEC §4.1 (адаптировать под Саймона)
4. `Edit Bot` → `Edit About` → краткая (≤120 символов): «Записываю и расшифровываю встречи команды Wookiee. Команда «Саймон, …» во время звонка → задачи и события в Bitrix.»
5. `Edit Bot` → `Edit Botpic` → загрузить `saimon_square.png`

### 3. admin.yandex.ru rename

1. Зайти в [admin.yandex.ru](https://admin.yandex.ru/) как admin организации Wookiee
2. Найти пользователя `recorder@wookiee.shop`
3. Переименовать в **«Саймон»** (отображаемое имя в Telemost-встречах)
4. Загрузить аватар (PNG из `data/branding/`)

### 4. Ротация Yandex OAuth Client Secret

Текущий `YANDEX_TELEMOST_CLIENT_SECRET` засветился в нашей переписке во время разработки T2-T3. После того как Саймон поработает 1-2 дня в проде:

1. В [oauth.yandex.ru](https://oauth.yandex.ru/) → найти приложение «Telemost Recorder» (или как названо)
2. Сбросить Client Secret → получить новый
3. Прислать новый секрет в чат — Claude обновит `.env` через `/update-env` и сделает `refresh_oauth_token()` через `shared/yandex_telemost.py`
4. Recreate `wookiee_cron` (тот же шаг что в блоке 3)

### 5. Боевой smoke-test

Когда блоки 0-9 выполнены и пункты 1-4 выше готовы:

1. **Утренний дайджест в 09:00 МСК:** проверить в чате Саймон-бота, что пришло сообщение со списком встреч на сегодня (см. SPEC §4.3 для формата). Если нет встреч — придёт «Сегодня встреч нет». Если бот молчит — `docker logs wookiee-api 2>&1 | grep morning_digest`.
2. **Кнопка «➕ Добавить Telemost»:** найти встречу в дайджесте у которой нет Telemost-ссылки, нажать кнопку. Бот должен ответить «✅ Готово, ссылка: https://telemost.yandex.ru/...» и обновить событие в Bitrix-календаре (`bitrix_calendar.event_update` из T5).
3. **Voice-trigger Phase 1+2:** записать тестовую встречу с командой 2-3 человек. Во время звонка сказать:
   - «Саймон, поставь задачу Сане сделать дашборд по продажам к пятнице»
   - (опционально) «Саймон, поставь встречу с Петей на завтра в 15:00 обсудить запуск»
4. После окончания звонка дождаться summary в Telegram (~5 минут). В summary должны быть секции:
   - 📌 Задачи (с кнопками «✅ Создать», «✏️ Поправить», «🚫 Пропустить»)
   - 📅 Встречи (аналогично)
5. Нажать «✅ Создать» под задачей — должен прийти ответ «✅ Готово, https://wookiee.bitrix24.ru/.../task/NNN». Открыть задачу в Bitrix, проверить что:
   - **Title начинается с `[🤖 Саймон]`** (Fix PR #4 — auto-marker)
   - **Description начинается с disclaimer-блока** «⚠️ Эта задача создана автоматически Саймоном на основе расшифровки встречи …»
   - Постановщик — Елизавета Литвинова (ID 2349) [из MEMORY.md feedback_bitrix_task_creator]
   - Ответственный — резолвится по имени из voice trigger
   - Описание содержит контекст из transcript

Если title/disclaimer не появились — Fix PR #4 либо не смержен, либо контейнер не рестартился после merge. Проверить `git log main | grep "auto-marker"` и `docker logs wookiee-api`.

Если что-то не работает — `docker logs wookiee-api 2>&1 | grep -E "voice_action|voice_trigger|bitrix_write"`.

---

## Контактные точки на проблемы

| Проблема | Где смотреть | Что делать |
|---|---|---|
| `wookiee-api` не стартует | `docker logs wookiee-api` | проверить .env, проверить миграцию 006 применена |
| Cron не шлёт OAuth health-check | `docker logs wookiee-cron` | проверить `YANDEX_TELEMOST_*` env, recreate cron |
| Дайджест не пришёл в 09:00 МСК | `docker logs wookiee-api 2>&1 \| grep morning_digest` | проверить `MORNING_DIGEST_ENABLED=true` |
| Voice-triggers молчат на звонках | `docker logs wookiee-api 2>&1 \| grep voice_triggers` | проверить `VOICE_TRIGGERS_ENABLED=true`, проверить миграцию 006, проверить `OPENROUTER_API_KEY` |
| Кнопки в Telegram не работают | `docker logs wookiee-api 2>&1 \| grep callback_query` | проверить webhook (`getWebhookInfo` → allowed_updates) |
| `BitrixWriteError` при создании задачи | логи `wookiee-api` | проверить write scope у `BITRIX24_WEBHOOK_URL` — может быть нужен новый webhook с правами на запись |
| Бот молчит — не отвечает на /start | проверить что `TELEMOST_BOT_TOKEN` корректен | `scripts/telemost_setup_webhook.py` |
| Cookie health-check падает | telegram алерт от `@wookiee_alerts_bot` | обновить куки через `scripts/telemost_check_cookies.py` |
| OAuth health-check падает | telegram алерт от `@wookiee_alerts_bot` | проверить `YANDEX_TELEMOST_OAUTH_TOKEN`, refresh через `shared/yandex_telemost.refresh_oauth_token()` |

**Rollback любой фичи:** соответствующий флаг → `false` + restart контейнера. Подробности и rollback-таблица в `docs/projects/saimon/RUNBOOK.md` §3.

---

## ВАЖНО: этот файл сейчас не в main

Этот ROLLOUT_EXECUTION.md закоммичен в ветку `feat/hub-shell-unification`, **в main ещё не попал**. Для того чтобы новая сессия Claude гарантированно увидела файл при `git checkout main`, нужно:

**Вариант A:** Данила запускает `/ship` из ветки `feat/hub-shell-unification` → PR с auto-merge → файл в main.

**Вариант B:** Данила в новой сессии сначала переключается на `feat/hub-shell-unification` (`git checkout feat/hub-shell-unification`), читает план, потом возвращается на main для работы.

**Вариант C:** Данила копирует содержимое блока «Промт для новой сессии» прямо в первое сообщение новой сессии — план не нужно открывать из файла.

Рекомендация: вариант A (один маленький doc-PR через /ship) — план будет частью репо, всегда доступен.
