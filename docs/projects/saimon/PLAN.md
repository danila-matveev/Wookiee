# Саймон — план реализации (для subagent-driven-development)

**Источник истины:** [`SPEC.md`](SPEC.md) (v1.1).
**Дата:** 2026-05-16.
**Кто исполняет:** оркестратор Claude через subagent-driven-development, каждая задача = отдельный имплементер + spec-ревью + code-quality-ревью + отдельный PR.

---

## Условия старта

1. **Ветка-стратегия:** каждая задача T1-T7 = ОТДЕЛЬНАЯ feature-ветка от свежего `main` вида `feat/saimon-t<N>-<short>` (например `feat/saimon-t1-rename`). НЕ создавай одну общую `feat/saimon-rollout` — каждая задача мёрджится в main как самостоятельный PR.
2. **Worktree:** через `EnterWorktree` (нативная изоляция платформы). Если EnterWorktree недоступен — fallback на `git worktree add` через skill `superpowers:using-git-worktrees`.
3. **Env-доступ:** оркестратор НЕ ходит на сервер сам. Если задаче нужны env-изменения на проде — имплементер пишет в PR description какие переменные должны быть выставлены, оператор сам добавляет в `.env` и делает recreate контейнера.
4. **Feature-flags по умолчанию OFF:** новые скиллы пишутся за env-флагом, дефолт выключенный. Включает оператор после merge.
5. **Уточнение путей:** SPEC.md указывает рабочие имена путей (например `scripts/telemost_check_cookies.py`, `services/telemost_recorder_api/telegram_routes.py`). При несовпадении с реальностью репо имплементер делает `grep` и работает с реальным файлом — это не блокер.

## Условия завершения

- 7 PR-ов смержены в main.
- Все интеграционные тесты зелёные.
- На проде стоят env-флаги в OFF, рассылка ничего не шлёт пока оператор не включит.
- Оператор получил короткий runbook (см. задачу T7 deliverables).

---

## Граф зависимостей

```
T1 (rename)  ──┐
               ├─→  T4 (scheduler multi-user)  ──→  T5 (morning_digest)  ──┐
T2 (yandex_   ──┤                                                          ├──→ T7 (voice Phase 2)
   telemost   ──┴─→  T3 (oauth_health)                                     │
   wrapper)                                                                │
                                                                           │
T6 (voice Phase 1) ────────────────────────────────────────────────────────┘
```

- T1 → T4: T4 правит тексты которые T1 уже переименовал, иначе merge-конфликт.
- T2 → T3: health-check использует wrapper из T2.
- T2 → T5: morning_digest вызывает `create_conference()` из T2.
- T4 → T5: morning_digest опирается на multi-user `telemost.users` (тот же запрос).
- T6 → T7: Phase 2 включает кнопки которые в Phase 1 нарисованы disabled.

**Запуск сабагентов — ПОСЛЕДОВАТЕЛЬНО, не параллельно** (иначе merge-конфликты).

---

## Задачи

### T1 — Переименование в «Саймон»

**Цель:** все юзер-видимые строки бота показывают имя «Саймон» вместо «Wookiee Recorder» / «Recorder Wookiee».

**Затрагиваемые файлы (рабочие имена, имплементер уточнит):**
- `services/telemost_recorder/config.py` — `BOT_NAME` дефолт + `KNOWN_BOT_NAMES`
- Telegram handlers (`routes/telegram.py` + `handlers/start.py`/`help.py` или единый `telegram_routes.py` — имплементер найдёт через `grep -r "BotCommand\|/start\|/help" services/telemost_recorder_api/`) — `/start`, `/help` тексты (черновик в SPEC §4.1)
- `services/telemost_recorder_api/notifier.py` — заголовки саммари
- `services/telemost_recorder_api/error_alerts.py` — шапка алертов
- `services/telemost_recorder/README.md` — упоминания
- Тесты в `tests/services/telemost_recorder_api/` — fixture strings (имплементер найдёт через `grep -r "Recorder Wookiee\|Wookiee Recorder" tests/`)

**Новые файлы:**
- `data/branding/README.md` — описание что сюда положатся PNG (сами PNG кладёт оператор после merge).

**DoD:**
- Все тесты зелёные.
- В коде нет hard-coded «Wookiee Recorder» / «Recorder Wookiee» (grep чист).
- PR description содержит чек-лист для оператора: BotFather /setname/setdescription/setuserpic, admin.yandex.ru переименование профиля, `TELEMOST_BOT_NAME=Саймон` в `.env`.

**Env:** `TELEMOST_BOT_NAME=Саймон` (оператор выставит после merge).

**Ветка:** `feat/saimon-t1-rename`
**PR title:** `feat(saimon): rename bot to Саймон`

---

### T2 — `shared/yandex_telemost.py` — wrapper над Telemost API

**Цель:** одна точка входа для всех вызовов Telemost API. Используется в T3 (health-check) и T5 (создание комнат из дайджеста).

**Новый файл:** `shared/yandex_telemost.py`.

**Public API:**
```python
async def create_conference(*, host_email: str | None = None) -> Conference:
    """POST /v1/telemost-api/conferences. Returns join_url + id."""

async def delete_conference(conference_id: str) -> None:
    """DELETE /v1/telemost-api/conferences/{id}. 204 on success."""

async def list_conferences(limit: int = 1) -> list[Conference]:
    """GET для health-check. 401 → TelemostTokenExpired."""

async def refresh_oauth_token() -> tuple[str, str]:
    """POST https://oauth.yandex.ru/token grant_type=refresh_token.
    Returns (new_access_token, new_refresh_token).
    Caller сам пишет в .env / persistence."""
```

**Env (через `shared/config.py`):**
- `YANDEX_TELEMOST_CLIENT_ID`
- `YANDEX_TELEMOST_CLIENT_SECRET`
- `YANDEX_TELEMOST_OAUTH_TOKEN`
- `YANDEX_TELEMOST_REFRESH_TOKEN`

**Header формат:** `Authorization: OAuth <access_token>` (не `Bearer`).

**Тесты:** `tests/shared/test_yandex_telemost.py` — все методы с моками `httpx.AsyncClient`. Тест на 401 → исключение `TelemostTokenExpired`. Тест на refresh успех. Тайм-аут на все вызовы = 15 сек.

**DoD:**
- Все 4 метода реализованы.
- pytest зелёный.
- Type hints на public API.
- Никаких прямых `os.environ[...]` — только через `shared/config.py`.

**Ветка:** `feat/saimon-t2-yandex-wrapper`
**PR title:** `feat(saimon): Yandex Telemost API wrapper`

---

### T3 — OAuth Telemost health-check (расширение T2)

**Цель:** существующий ежедневный cron 08:00 МСК (PR #146) проверяет ещё и OAuth-токен Telemost. При 401 — автоматический refresh, при ошибке refresh — алерт.

**Затрагиваемые файлы:**
- Cookie-чек-скрипт. Рабочее имя `scripts/telemost_check_cookies.py`. Если имя другое — имплементер найдёт через `crontab -l` на сервере + `grep -l "cookie\|cookies" scripts/`.
- `deploy/docker-compose.yml` (или где определён `wookiee-cron`) — пробросить 4 `YANDEX_TELEMOST_*` env.

**Логика (см. SPEC §4.4):**
```python
async def check_telemost_oauth():
    try:
        await yandex_telemost.list_conferences(limit=1)
        logger.info("OAuth: OK")
    except TelemostTokenExpired:
        new_access, new_refresh = await yandex_telemost.refresh_oauth_token()
        await alert(
            f"Telemost OAuth обновлён. Перезапиши в .env:\n"
            f"YANDEX_TELEMOST_OAUTH_TOKEN={new_access[:8]}...\n"
            f"YANDEX_TELEMOST_REFRESH_TOKEN={new_refresh[:8]}..."
        )
    except Exception as e:
        await alert(f"Telemost OAuth check failed: {e}")
```

**Persistence новых токенов после refresh — НЕ автоматический в этой задаче.** Алерт оператору с новыми токенами, оператор сам обновит `.env`.

**Тесты:** mock `yandex_telemost.*` функций. Сценарии: OK, 401+refresh OK, 401+refresh fail.

**DoD:**
- Cron шлёт алерт когда токен скоро истекает / истёк.
- Smoke от руки: ручной запуск скрипта → успех.
- PR description: инструкция `docker compose up -d wookiee-cron` (без `--build`) после merge.

**Ветка:** `feat/saimon-t3-oauth-health`
**PR title:** `feat(saimon): OAuth Telemost health check`

---

### T4 — `scheduler_worker.py` multi-user расширение

**Цель:** существующий `services/telemost_recorder_api/workers/scheduler_worker.py` сейчас опрашивает одного юзера через env-переменную. Расширить до итерации по `telemost.users.is_active=true`.

**Затрагиваемые файлы:**
- `services/telemost_recorder_api/workers/scheduler_worker.py` — основная правка (см. SPEC §4.2 pseudocode).
- `services/telemost_recorder_api/config.py` — добавить `TELEMOST_SCHEDULER_ENABLED` (default `false`).
- `tests/services/telemost_recorder_api/workers/test_scheduler_worker.py` — расширить тесты.

**Что меняется в `run_forever`:**
1. Источник юзеров: `telemost.users WHERE is_active=true` если `TELEMOST_SCHEDULER_BITRIX_USER_ID` пустой; иначе legacy single-user.
2. In-memory дедупликация `(meeting_url, scheduled_at)` внутри одного тика.
3. Фильтр `#nobot` в `event.name`.
4. `triggered_by` = `telegram_id` владельца календаря, на котором событие нашлось первым.
5. Флаг `TELEMOST_SCHEDULER_ENABLED=false` → loop не стартует.

**Тесты:**
- 1 встреча в 12 календарях → 1 INSERT (in-memory дедуп).
- Встреча с `#nobot` → пропуск.
- Встреча без Telemost URL → пропуск.
- Bitrix API падает на одном юзере → loop продолжается, остальные юзеры обработаны.
- Legacy single-user mode (env выставлен) → опрашивает только его.
- `TELEMOST_SCHEDULER_ENABLED=false` → loop не запускается.

**DoD:**
- Все тесты зелёные.
- На проде после merge остаётся `TELEMOST_SCHEDULER_ENABLED=false` (включает оператор отдельно).
- PR description: список env-переменных + smoke-инструкция (включить флаг на 5 минут, проверить INSERT-ы, выключить).

**Ветка:** `feat/saimon-t4-scheduler-multiuser`
**PR title:** `feat(saimon): scheduler_worker multi-user expansion`

---

### T5 — `morning_digest.py` + кнопка «➕ Добавить Telemost»

**Цель:** каждое утро в 09:00 МСК — DM каждому активному юзеру со списком встреч на день и кнопкой создать Telemost-комнату прямо из чата.

**Новый файл:** `services/telemost_recorder_api/workers/morning_digest.py`.

**Затрагиваемые файлы:**
- `services/telemost_recorder_api/app.py` — в `_lifespan` стартует `_supervised("morning_digest", morning_digest_loop)`.
- Telegram handlers — callback handler `add_telemost:<bitrix_event_id>` (точное место — `routes/telegram.py` или `handlers/*.py`, имплементер уточнит).
- `services/telemost_recorder_api/keyboards.py` — генератор клавиатуры для дайджеста.
- `services/telemost_recorder_api/config.py` — `MORNING_DIGEST_ENABLED` (default `false`), `MORNING_DIGEST_HOUR_MSK=9`.

**Логика (см. SPEC §4.3):**
- При старте loop рассчитывает время до следующих 09:00 МСК (через `zoneinfo("Europe/Moscow")`), спит, рассылает, спит до следующего дня.
- Для каждого `telemost.users.is_active=true` — `calendar.event.get` на сегодняшний день, классификация на 3 группы: 🎙 / ⚠️ / ⏭.
- Пустой день → не шлём ничего.
- Кнопка `add_telemost:<event_id>` → `yandex_telemost.create_conference()` → `bitrix_calendar.event.update(LOCATION=current+\n+join_url)` → ответ юзеру.

**Тесты:**
- Юзер без встреч → не шлём.
- Юзер с 2 ⚠️ → дайджест с 2 кнопками.
- Клик кнопки → mock Telemost API + mock Bitrix → проверка вызовов.
- `MORNING_DIGEST_ENABLED=false` → loop не запускается.
- Дайджест приходит только в 09:00 МСК (тест с подменой `now()`).

**DoD:**
- На проде `MORNING_DIGEST_ENABLED=false` (включает оператор).
- Smoke от руки: ручной вызов `send_daily_digest_to_user(<test_user>)` → DM приходит.
- PR description: пошаговая инструкция включения.

**Ветка:** `feat/saimon-t5-morning-digest`
**PR title:** `feat(saimon): morning digest + Telemost room creation button`

---

### T6 — Voice-triggers Phase 1 (детекция без записи в Bitrix)

**Цель:** на постпроцессе вычленяем обращения «Саймон, ...» из транскрипта, добавляем 4 новые секции в саммари. Кнопки «✅ Создать» нарисованы, но шлют placeholder-ответ.

**Новые файлы:**
- `services/telemost_recorder_api/voice_triggers.py` — двухстадийный pipeline.
- `tests/services/telemost_recorder_api/test_voice_triggers.py` + 3-5 fixture-транскриптов в `tests/fixtures/transcripts/`.

**Затрагиваемые файлы:**
- `services/telemost_recorder_api/llm_postprocess.py` — после генерации саммари вызывает `voice_triggers.extract(transcript, team_users)` и кладёт результат в prompt-контекст для финальной сборки.
- `services/telemost_recorder_api/notifier.py` — рендер новых секций (см. SPEC §4.5 markdown).
- `services/telemost_recorder_api/keyboards.py` — кнопки рисует, callback_data placeholder `voice:<id>:disabled` (в T7 заменим на реальные).
- Telegram handlers — обработчик `voice:*:disabled` → ответ «пока недоступно, ждём Phase 2».
- `services/telemost_recorder_api/config.py` — `VOICE_TRIGGERS_ENABLED` (default `false`).

**Pipeline (см. SPEC §4.5):**
- Stage 1 (LIGHT model `google/gemini-3-flash-preview`): найти кандидатов `Саймон, ...`, вернуть JSON со списком.
- Stage 2 (HEAVY model `anthropic/claude-sonnet-4-6`): для каждого кандидата с `confidence>=0.5` — slot-filling по intent type, шаблоны промтов адаптированы из `/bitrix-task` и `/calendar` SKILL.md.

**Тесты:**
- Транскрипт без обращений → 0 кандидатов.
- Транскрипт с 1 task → 1 кандидат с заполненными полями.
- Транскрипт с 1 meeting + 1 note → 2 кандидата.
- `VOICE_TRIGGERS_ENABLED=false` → stage 1 не вызывается, секции в саммари не появляются.

**Метрика после prod-rollout:** precision ≥ 0.7, recall ≥ 0.8 на 5-10 реальных звонках. Замеряется ручной выборкой, результат пишется в `docs/projects/saimon/PHASE1_METRICS.md` (создаст оператор).

**DoD:**
- На проде `VOICE_TRIGGERS_ENABLED=false`.
- Кнопки рисуются, при клике placeholder-ответ.
- PR description: пошаговая инструкция включения + где собирать метрики.

**Ветка:** `feat/saimon-t6-voice-phase1`
**PR title:** `feat(saimon): voice triggers detection (Phase 1)`

---

### T7 — Voice-triggers Phase 2 (запись в Bitrix)

**Цель:** кнопки `[✅ Создать]` реально создают задачи и события в Bitrix.

**Новые файлы:**
- `shared/bitrix_writes.py` — обёртки `create_task(...)` + `create_calendar_event(...)`.
- `services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql` — таблица для persistence (последняя существующая миграция — 005, поэтому новая = 006).
- `tests/shared/test_bitrix_writes.py`.
- `docs/projects/saimon/RUNBOOK.md` — финальный operator-runbook.

**Затрагиваемые файлы:**
- `services/telemost_recorder_api/voice_triggers.py` — после Stage 2 INSERT каждого кандидата в `telemost.voice_trigger_candidates`.
- Telegram handlers — handlers для `task_create:<id>` / `task_edit:<id>` / `task_ignore:<id>` + `meeting_create/edit/ignore`.
- `services/telemost_recorder_api/keyboards.py` — callback_data на реальные actions.

**Миграция 006 (см. SPEC §2.5):**
```sql
CREATE TABLE telemost.voice_trigger_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  meeting_id UUID REFERENCES telemost.meetings(id) ON DELETE CASCADE,
  intent TEXT NOT NULL CHECK (intent IN ('task','meeting','note','attention','reminder')),
  speaker TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  extracted_fields JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','created','edited','ignored')),
  bitrix_id TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vtc_meeting ON telemost.voice_trigger_candidates(meeting_id);
ALTER TABLE telemost.voice_trigger_candidates ENABLE ROW LEVEL SECURITY;
```

**`shared/bitrix_writes.py` API:** см. SPEC §4.6.

**Тесты:**
- `create_task` mock → корректный POST на `tasks.task.add.json`.
- `create_calendar_event` mock → корректный POST на `calendar.event.add.json`.
- Клик `task_create` → INSERT в БД status='pending' → POST в Bitrix → UPDATE status='created' + bitrix_id.
- Клик `task_ignore` → UPDATE status='ignored'.
- Если LLM не заполнил deadline / responsible → handler шлёт юзеру inline-форму с просьбой дозаполнить.

**`docs/projects/saimon/RUNBOOK.md` (финальный operator-runbook):**
1. Чек-лист включения каждого env-флага в правильном порядке (T1 → T3 → T4 → T5 → T6 → T7).
2. Как смотреть health-check алерты.
3. Как откатиться: какой флаг выключить под какую проблему.
4. Где собирать метрики precision/recall.
5. Что делать когда OAuth-токен сообщил о refresh.

**DoD:**
- Все тесты зелёные.
- Миграция 006 применена через `supabase db push` (или dependency-free путь — оператор применяет вручную).
- RUNBOOK.md в репо.
- На проде включают по очереди: T7 в OFF, потом T6+T7 ON одновременно.

**Ветка:** `feat/saimon-t7-voice-phase2`
**PR title:** `feat(saimon): voice triggers Phase 2 (Bitrix writes)`

---

## Что НЕ делаем в этой раскатке

- PNG-аватарки в `data/branding/` — кладёт оператор сам после T1 merge.
- BotFather переименование — оператор.
- admin.yandex.ru переименование — оператор.
- Ротация Yandex OAuth Client Secret — оператор (после первого боевого теста).
- Real-time voice commands — out-of-scope (см. SPEC §8).
- Multi-tenant — deferred.

---

## Что делаем после merge всех 7 задач

Оператор включает фичи в таком порядке:

| День | Действие | Флаг → значение |
|------|----------|-----------------|
| 0 | T1 merged → BotFather rename + PNG | `TELEMOST_BOT_NAME=Саймон` |
| 1 | T2+T3 merged → recreate wookiee_cron | (env уже в .env) |
| 2 | T4 merged → 10-минутный smoke | `TELEMOST_SCHEDULER_ENABLED=true` затем `=false` |
| 3 | T5 merged → запустить дайджест в 09:00 | `MORNING_DIGEST_ENABLED=true` |
| 4 | Включить scheduler постоянно | `TELEMOST_SCHEDULER_ENABLED=true` |
| 5-7 | T6 merged → 5-10 звонков под наблюдением | `VOICE_TRIGGERS_ENABLED=true` |
| 8 | Метрики precision/recall в `PHASE1_METRICS.md` | — |
| 9 | T7 merged → migration 006 → флаги | (T6 уже on, T7 включается тем же флагом) |
| 10 | Финальный smoke-test всего цикла | — |
