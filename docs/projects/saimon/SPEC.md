# Саймон — полная спецификация раскатки на команду

**Версия:** 1.1 (после автономного аудита)
**Дата:** 2026-05-16
**Статус:** DRAFT — ждёт approval от Данилы, потом по фазам в код
**Базируется на:** PR #142 (auth-bot) + PR #146 (cookie health-check) уже в проде

---

## Журнал изменений после самоаудита (v1.0 → v1.1)

После того как Данила сказал «проверь все сам», я прошёлся по коду и нашёл 6 расхождений между v1.0 спеки и реальностью репо. Все они уменьшают объём работы, ни одно не добавляет. Запись здесь — чтобы было видно что было исправлено.

| # | Что в v1.0 я написал не так | Реальность | Влияние |
|---|------------------------------|-----------|---------|
| F1 | «Создаём новый `calendar_poller.py` с нуля (1.5 дня)» | `services/telemost_recorder_api/workers/scheduler_worker.py` УЖЕ существует, уже запущен в lifespan app.py, уже использует `source='calendar'`, уже идемпотентен через partial unique index. Сейчас активируется только при наличии env-переменных `TELEMOST_SCHEDULER_BITRIX_USER_ID` + `TELEMOST_SCHEDULER_TELEGRAM_ID`, на проде они НЕ выставлены. | Трек C1 уменьшается с 1.5 дня до ~4 часов: только расширить под множество юзеров |
| F2 | «Нужна миграция 006: добавить `source` enum и `bitrix_event_id`» | `telemost.meetings.source` уже есть с CHECK `('telegram','calendar')`. `source_event_id` уже есть. Партиальный unique `idx_meetings_active_unique ON (meeting_url) WHERE status IN (...)` + `uniq_meetings_calendar_event_slot ON (source, source_event_id, scheduled_at)` уже созданы. | Миграция 006 не нужна |
| F3 | «Использовать `source='manual'` / `'calendar_auto'` / `'voice_trigger'`» | CHECK constraint допускает только `'telegram'` и `'calendar'`. Мои значения сразу бы упали на INSERT. | Использую существующие значения: `'telegram'` для `/record`, `'calendar'` для авто-поллера. Для voice-trigger-кандидатов — отдельная таблица `telemost.voice_trigger_candidates`, не отдельный `source` |
| F4 | «`app.py` использует `@app.on_event("startup")`» | `app.py:155` использует `@asynccontextmanager async def _lifespan(app: FastAPI)` + `_supervised(...)` обёртку. Шаблон в спеке был бы устаревший. | Поправил в §2.4 |
| F5 | «Поллер тикает каждые 5 минут» | Существующий `SCHEDULER_TICK_SECONDS=60` (раз в минуту). Чаще = лучше — меньше шанс пропустить встречу. | Принял 60 сек как дефолт |
| F6 | «Авто-поллер видит ВСЕ календари команды» | Существующий scheduler видит ровно ОДНОГО юзера (`SCHEDULER_BITRIX_USER_ID` единичный). Для multi-user нужно расширение: либо iterate `telemost.users` внутри `run_forever`, либо принимать список ID через запятую | Расширяю в трек C1 |

**Подтверждено живыми проверками (через curl и SSH в эту сессию):**
- ✅ Yandex Telemost API: создал и удалил тестовую конференцию (POST 201 + DELETE 204)
- ✅ OAuth refresh flow: новый access_token + refresh_token валидны, старый access_token продолжает работать после refresh (Yandex не инвалидирует автоматически)
- ✅ Bitrix webhook права (через существующие `/bitrix-task` и `/calendar` скиллы, которые работают на этом же URL)
- ✅ Telegram inline buttons: инфра в `services/telemost_recorder_api/keyboards.py` уже есть, новые кнопки voice-triggers ложатся в существующий паттерн `callback_data: meet:<id>:<action>`

**Операционное предупреждение:** контейнер `wookiee_cron` сейчас НЕ видит `YANDEX_TELEMOST_*` env-переменные, потому что был пересоздан до их добавления в .env. Когда буду включать OAuth health-check (трек E) — нужно `docker compose up -d wookiee-cron` (без `--build`).

---

## 0. TL;DR — что строим в одном абзаце

Существующий `telemost_recorder` переименовываем в **«Саймон»**, раскатываем на всю команду (12 активных юзеров с привязанным `telegram_id` в Битриксе). Саймон сам ходит на ВСЕ встречи команды (60-секундный поллер Bitrix-календаря, не только те которые лично пригласили), пишет, расшифровывает, сохраняет навсегда. Каждое утро в 09:00 МСК шлёт каждому DM-дайджест что у него сегодня и какие встречи без Telemost-ссылки — с кнопкой «➕ Добавить» которая создаёт комнату через Telemost API и пишет URL обратно в Битрикс. Во время звонка можно сказать «Саймон, поставь задачу/созвон/заметку/запомни» — он на постпроцессе вычленяет команды и добавляет в саммари с кнопками подтверждения, по клику пишет в Bitrix (`tasks.task.add` / `calendar.event.add`).

---

## 1. Принятые решения (decisions log)

| # | Решение | Что значит на практике |
|---|---------|------------------------|
| D1 | **Имя бота — «Саймон»** | Переименование в коде, BotFather, Yandex 360 профиле, всех текстах `/start`/`/help` |
| D2 | **Аватарки сделал Данила сам** | 1) квадратная для TG (через @BotFather, Telegram API не позволяет ботам менять свою фотку), 2) прямоугольная для Yandex 360 (через admin.yandex.ru). PNG-файлы будут закоммичены в `data/branding/` как brand-ассеты |
| D3 | **Privacy — ВСЕ встречи** | Саймон ходит на любую встречу с Telemost-ссылкой, включая встречи с внешними участниками. Решение Данилы, юридическая ответственность на нём. Один safety vent: тег `#nobot` в названии встречи = пропустить |
| D4 | **Задачи без дефолтов** | LLM парсит из речи постановщика/исполнителя/наблюдателей/соисполнителей. Если постановщик не назван — fallback на спикера, который произнёс команду. Все остальные поля без значений → confirmation buttons |
| D5 | **Voice-triggers — только постобработка, без real-time** | LLM на постпроцессе сканит транскрипт на «Саймон, ...» обращения и добавляет 4 новые секции в саммари: «Важные моменты», «Задачи», «Предлагаемые встречи», «Заметки». В Битрикс пишет только после клика на кнопку «✅ Создать» |
| D6 | **Yandex Telemost API подключён** | OAuth-приложение `wookiee recorder` создано, ClientID/Secret/Access/Refresh токены в `.env` на сервере. Smoke-test пройден: POST conferences → 201 + DELETE → 204 |
| D7 | **Bitrix webhook остаётся один** | `Bitrix_rest_api` уже имеет права и на `tasks.task.add`, и на `calendar.event.add` (проверено через `/bitrix-task` и `/calendar` скиллы которые работают на этом же вебхуке). Новых прав/вебхуков не запрашиваем |
| D8 | **Существующие скиллы переиспользуем** | `/bitrix-task` SKILL.md шаблоны (`TITLE`/`RESPONSIBLE_ID`/`CREATED_BY`/...) и `/calendar` SKILL.md шаблоны (для `calendar.event.add`) — Саймон зовёт ИХ JSON-контракт, выносим Bitrix-вызовы в `shared/bitrix_writes.py` |
| D9 | **Multi-tenant — deferred** | Один тенант (Wookiee). Расширим когда появится второй кабинет |
| D10 | **Health-check куки уже в проде** | PR #146 — daily cron 08:00 МСК. Расширим в трек E: добавить проверку OAuth Telemost-токена (TTL 364 дн., refresh logic). Точный путь скрипта проверить перед T3 (`scripts/telemost_check_cookies.py` — рабочее предположение, имплементер уточнит) |

---

## 2. Архитектура — текущая + новая

### 2.1 Что есть (LIVE в проде сегодня)

| Компонент | Файл | Что делает | Меняем? |
|-----------|------|-----------|---------|
| Recorder worker | `services/telemost_recorder/join.py` | Заходит в встречу через Playwright + Xvfb, пишет аудио, делает скриншоты | Нет |
| Audio capture | `services/telemost_recorder/audio.py` | PulseAudio null-sink + ffmpeg/opus | Нет |
| Transcribe | `services/telemost_recorder/transcribe.py` | Yandex SpeechKit + speaker resolve | Нет |
| API + lifespan | `services/telemost_recorder_api/app.py` | FastAPI, Telegram webhook, очередь meetings, supervised asyncio tasks через `_lifespan` + `_supervised(...)` | Чуть-чуть: добавить task `morning_digest` |
| Docker spawn | `services/telemost_recorder_api/docker_client.py` | Спавн recorder-контейнеров через docker.sock | Нет |
| Bitrix enrich | `services/telemost_recorder_api/bitrix_calendar.py` | Подтягивает title и invitees при `/record` | Нет (read-only client) |
| **Calendar scheduler** | `services/telemost_recorder_api/workers/scheduler_worker.py` | **Уже есть!** Polling Bitrix-календаря одного юзера, INSERT в `meetings` с `source='calendar'`. Сейчас отключён на проде (нет env). | **Да — расширить под multi-user, включить, опубликовать** |
| LLM postprocess | `services/telemost_recorder_api/llm_postprocess.py` | OpenRouter Claude-Sonnet, генерит саммари | Да: добавить вызов voice-triggers |
| Notifier + keyboards | `services/telemost_recorder_api/notifier.py` + `keyboards.py` | Рендерит саммари + inline-кнопки (`meet:<id>:<action>` pattern) | Да: новые кнопки + новые секции |
| Notion export | `services/telemost_recorder_api/notion_export.py` | По кнопке создаёт страницу в DB «Записи встреч» | Нет |
| Cookie health (PR #146) | `scripts/telemost_check_cookies.py` (предположительно — имплементер уточнит фактический путь) | Daily cron 08:00 МСК, алерт за 7 дней до истечения куки | Да: добавить проверку OAuth Telemost-токена + auto-refresh |
| Telegram routes | `services/telemost_recorder_api/routes/telegram.py` + `handlers/*.py` | Webhook + handlers (start/help/record/meeting_actions/...) | Да: новые callback_data + voice-trigger handlers |

**Замечание для имплементеров:** имена точных путей `routes/telegram.py` vs `telegram_routes.py` и `scripts/telemost_check_cookies.py` я указываю как рабочие гипотезы. При несовпадении — имплементер делает `grep` по symbol/функции (например `webhook` или `cookie`) и работает с реальным файлом. Это нормально и НЕ блокер.

### 2.2 Что новое (всё, что строим в этой спеке)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Bitrix24 (calendar events of 12 active team members)                    │
└────────────────────────────┬────────────────────────────────────────────┘
                             │  calendar.event.get
                             │  (раз в SCHEDULER_TICK_SECONDS=60s)
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ scheduler_worker.py  (УЖЕ ЕСТЬ — расширяем под multi-user)              │
│  • Сейчас опрашивает ОДНОГО юзера (env SCHEDULER_BITRIX_USER_ID).       │
│    Расширяем: итерируем по telemost.users.is_active=true.               │
│  • Дедуп по (meeting_url) уже работает через partial unique             │
│    idx_meetings_active_unique (миграция 001) +                          │
│    uniq_meetings_calendar_event_slot (миграция 005).                    │
│  • Фильтр #nobot — добавить (сейчас нет).                                │
│  • INSERT с source='calendar' (CHECK constraint допускает).             │
└──────────────┬───────────────────────────────────┬──────────────────────┘
               │                                    │
               │ existing INSERT flow              │ daily 09:00 MSK
               ▼                                    ▼
┌────────────────────────────────┐    ┌─────────────────────────────────┐
│ recorder_worker (LIVE)         │    │ morning_digest.py  (NEW task)   │
│ → spawn recorder container     │    │ • для каждого user → события    │
│ → write audio                  │    │   на день                       │
│ → transcribe                   │    │ • groups: 🎙 / ⚠️ / ⏭          │
│ → llm_postprocess              │    │ • кнопки [➕ Добавить Telemost] │
│   (now with voice-triggers!)   │    │   под ⚠️                        │
│ → notifier                     │    └────────────┬────────────────────┘
└────────────────────────────────┘                 │
                                                    │ click
                                                    ▼
                                  ┌──────────────────────────────────┐
                                  │ shared/yandex_telemost.py (NEW)  │
                                  │ create_conference() →            │
                                  │   POST /v1/telemost-api/...      │
                                  │   → join_url                     │
                                  │ → calendar.event.update Bitrix   │
                                  └──────────────────────────────────┘

llm_postprocess.py (EXTENDED for voice-triggers):
   stage 1: LIGHT model — find "Саймон, ..." candidates in transcript
   stage 2: HEAVY model — slot-fill per intent type (note/task/meeting/reminder)
                          using existing /bitrix-task and /calendar templates
   output: 4 new sections in summary with action buttons

shared/bitrix_writes.py (NEW):
   create_task(...)   — adapted from /bitrix-task SKILL.md
   create_calendar_event(...)  — adapted from /calendar SKILL.md
   Called by notifier when user clicks "✅ Создать"
```

### 2.3 Новые файлы (список с описанием)

| Путь | Назначение | Размер ≈ |
|------|-----------|----------|
| `services/telemost_recorder_api/workers/morning_digest.py` | Дневной 09:00 МСК дайджест в Telegram | 180 строк |
| `shared/yandex_telemost.py` | Wrapper над Telemost API: create/delete/list/refresh | 150 строк |
| `shared/bitrix_writes.py` | Тонкий слой для tasks.task.add + calendar.event.add | 120 строк |
| `services/telemost_recorder_api/voice_triggers.py` | Двухстадийный pipeline детекции `Саймон, ...` | 250 строк |
| `services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql` | Новая таблица для трека D | ~30 строк |
| `data/branding/saimon_avatar_square.png` | Brand-ассет (от Данилы) | бинарный |
| `data/branding/saimon_avatar_telemost.png` | Brand-ассет (от Данилы) | бинарный |

Заметь: `calendar_poller.py` НЕТ в списке новых файлов. Вместо него **расширяется существующий `services/telemost_recorder_api/workers/scheduler_worker.py`** — см. трек C1.

**Нумерация миграций:** последняя существующая миграция — `005_meetings_calendar_uniq.sql`. Следующая новая — `006_voice_trigger_candidates.sql` (для трека D).

### 2.4 Расширения существующих файлов

| Файл | Что меняется |
|------|--------------|
| `services/telemost_recorder/config.py` | `BOT_NAME` дефолт → "Саймон", `KNOWN_BOT_NAMES` += "саймон" |
| `services/telemost_recorder_api/workers/scheduler_worker.py` | Multi-user: итерировать `telemost.users.is_active=true` вместо одного `SCHEDULER_BITRIX_USER_ID`. Добавить фильтр `#nobot` в имени события. |
| `services/telemost_recorder_api/app.py` | В `_lifespan` (~строки 155–189) добавить `asyncio.create_task(_supervised("morning_digest", morning_digest_loop), name="morning_digest")`. Scheduler уже стартует на ~181-й строке — не трогаем код запуска, только включаем env. |
| `services/telemost_recorder_api/config.py` | Новые env: `MORNING_DIGEST_ENABLED`, `MORNING_DIGEST_HOUR_MSK=9`, `TELEMOST_SCHEDULER_ENABLED`. |
| `services/telemost_recorder_api/llm_postprocess.py` | Вызов `voice_triggers.extract()` → передача результатов в промт саммари |
| `services/telemost_recorder_api/notifier.py` | Рендер 4 новых секций + inline-кнопки `[✅ Создать]` / `[✏️ Поправить]` / `[❌ Игнор]` |
| Telegram handlers (`routes/telegram.py` + `handlers/*.py`) | Новые callback_query обработчики для voice-trigger кнопок + `add_telemost:<id>` |
| `scripts/telemost_check_cookies.py` (или фактическое имя — имплементер уточнит) | + проверка OAuth Telemost-токена (TTL + refresh) |
| `deploy/docker-compose.yml` | `wookiee-cron` env пробрасывает `YANDEX_TELEMOST_OAUTH_TOKEN` + `REFRESH_TOKEN` + `CLIENT_ID` + `CLIENT_SECRET`. После правки compose контейнер нужно `up -d wookiee-cron` (без `--build`). |
| `.env` (на сервере, не в репо) | Уже добавлены: `YANDEX_TELEMOST_CLIENT_ID/SECRET/OAUTH_TOKEN/REFRESH_TOKEN` |
| Тексты `/start`, `/help` | Переписать от имени Саймона (см. §4.1) |

### 2.5 Миграции БД

**Для C1/C2 (auto-join + digest) — миграции не нужны.** Все нужные колонки и индексы уже есть в миграциях 001 + 005:

- `telemost.meetings.source TEXT CHECK (source IN ('telegram','calendar'))` — миграция 001
- `telemost.meetings.source_event_id TEXT` — миграция 001
- `telemost.meetings.triggered_by bigint REFERENCES telemost.users(telegram_id)` — миграция 001
- `idx_meetings_active_unique ON (meeting_url) WHERE status IN ('queued','recording','postprocessing')` — миграция 001
- `uniq_meetings_calendar_event_slot ON (source, source_event_id, scheduled_at) WHERE source='calendar' AND source_event_id IS NOT NULL` — миграция 005

Поллер использует `source='calendar'` для авто-INSERT-ов, `source='telegram'` остаётся для ручного `/record`. Для аналитики этого хватит — отдельный `'calendar_auto'` vs `'calendar_manual'` не нужен.

**Для трека D (voice-triggers Phase 2) — одна новая миграция:**

```sql
-- services/telemost_recorder_api/migrations/006_voice_trigger_candidates.sql
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
-- RLS: service_role полный доступ, anon заблокирован (стандартный шаблон Wookiee)
```

Эта миграция применяется только перед треком D, не блокирует C1/C2.

---

## 3. Внешние интеграции — креды и контракты

### 3.1 Yandex Telemost API (✅ работает)

```
OAuth app:    wookiee recorder
ClientID:     03dedc8876ea47e5ae5452062679a8ac
Owner:        recorder@wookiee.shop (Yandex 360 Business)
Scopes:       telemost-api:conferences.{create,read,update,delete}
Token TTL:    364 дня (refresh_token валиден неограниченно до revoke)

Env vars (на сервере, в .env):
  YANDEX_TELEMOST_CLIENT_ID       = 03dedc...8ac
  YANDEX_TELEMOST_CLIENT_SECRET   = 7ed9464...215
  YANDEX_TELEMOST_OAUTH_TOKEN     = <59 chars>  (истекает 2027-05-16)
  YANDEX_TELEMOST_REFRESH_TOKEN   = <139 chars>

Endpoints:
  POST   https://cloud-api.yandex.net/v1/telemost-api/conferences   → 201
  DELETE https://cloud-api.yandex.net/v1/telemost-api/conferences/{id} → 204
  GET    https://cloud-api.yandex.net/v1/telemost-api/conferences   → 200 (для health-check)
  POST   https://oauth.yandex.ru/token  (для refresh)

Smoke-test (выполнен 2026-05-16):
  POST → conference 0158581158 → join_url telemost.360.yandex.ru/j/0158581158
  DELETE → 204 OK

Header формат:  Authorization: OAuth <access_token>
```

### 3.2 Bitrix24 REST (✅ работает)

```
Webhook:  ${Bitrix_rest_api}  (env переменная)
Права:    подтверждены через /bitrix-task и /calendar скиллы
           - tasks.task.add  ✅
           - tasks.task.update ✅
           - task.checklistitem.add ✅
           - calendar.event.add ✅
           - calendar.event.update ✅ (для кнопки "➕ Добавить Telemost")
           - calendar.event.get ✅ (УЖЕ используется scheduler_worker.py для одного юзера)
           - user.get ✅ (для синка telemost.users)

Templates: services/telemost_recorder_api/bitrix_calendar.py  (read, существующий)
           services/telemost_recorder_api/workers/scheduler_worker.py  (использует bitrix_calendar)
           shared/bitrix_writes.py  (NEW, write — для тасков и эвентов в треке D)
```

### 3.3 Telegram (✅ работает, ограничение признано)

```
Bot:      @wookiee_recorder_bot (без переименования — username не трогаем)
Display name (то что юзеры видят): "Recorder Wookiee" → "Саймон"
Avatar:   только через @BotFather (Telegram API не даёт ботам менять свою фотку)
Action:   Данила сам через BotFather после получения PNG от себя

Alerts bot: @wookiee_alerts_bot (общий, не трогаем)
Env для алертов: TELEGRAM_ALERTS_BOT_TOKEN + TELEGRAM_ALERTS_CHAT_ID
```

### 3.4 OpenRouter (✅ работает, без изменений)

```
LIGHT model: google/gemini-3-flash-preview ($0.50/$3.00)
             — для voice-trigger detection (stage 1)
HEAVY model: anthropic/claude-sonnet-4-6 ($3/$15)
             — для slot-filling (stage 2) + основной саммари

Routing через shared OpenRouter wrapper (уже используется в llm_postprocess.py).
```

---

## 4. Фазы реализации

Каждая фаза — отдельная ветка и PR. Между фазами есть зависимости (см. граф). Время — оценка на одного человека при автономной работе.

```
Трек A (Бренд)  ──┐
                  ├──> Трек C1 (scheduler)  ──> Трек C2 (digest)  ──┐
Трек E (OAuth   ──┘                                                  ├──> ПРОД rollout
       health)                                                       │
                                                                     │
Трек B (voice   ──> Трек D (voice phase 2: buttons + Bitrix) ────────┘
       phase 1)
```

### 4.1 Трек A — Brand renaming (1 день)

**Цель:** имя «Саймон» во всех точках где юзеры видят бота.

**Файлы:**
1. `services/telemost_recorder/config.py` → `BOT_NAME = os.getenv("TELEMOST_BOT_NAME", "Саймон")`
2. `services/telemost_recorder/config.py` → в `KNOWN_BOT_NAMES` добавить `"саймон"`
3. Telegram handlers → тексты `/start`, `/help`:

   ```
   Привет, я Саймон.
   Я хожу на ваши Telemost-встречи и записываю их —
   расшифровка, саммари в DM, экспорт в Notion по кнопке.

   Команды:
   /record <url>  — записать конкретную встречу прямо сейчас
   /status        — что я сейчас пишу
   /list          — мои последние записи (10 шт)
   /help          — эта подсказка

   Если у вас в Bitrix-календаре есть встречи с Telemost-ссылкой —
   я приду сам, ничего делать не надо. Каждое утро в 9:00 я пришлю
   список того, что у вас на день.

   Если на встречу не хочется чтобы я приходил — поставьте #nobot
   в название встречи в Bitrix.
   ```

4. `services/telemost_recorder_api/notifier.py` → "Recorder Wookiee" → "Саймон" в текстах
5. `services/telemost_recorder_api/error_alerts.py` → "Wookiee Recorder" → "Саймон" в шапке алертов
6. README + операторский runbook → обновить упоминания
7. `data/branding/` → положить 2 PNG аватарки + `README.md` про источник (PNG кладёт оператор после merge)

**На стороне Данилы:**
- @BotFather → /setname → «Саймон»
- @BotFather → /setdescription → новое описание
- @BotFather → /setuserpic → загрузить квадратный PNG
- admin.yandex.ru → recorder@wookiee.shop → переименовать в «Саймон» + загрузить прямоугольный PNG

**Env-изменение на сервере:**
```
TELEMOST_BOT_NAME=Саймон   # уже стоит "Wookiee Recorder", поменять
```

**Deploy:** один `docker compose restart telemost-recorder-api`.

**Тесты:** обновить fixture-строки в существующих тестах notifier (имплементер найдёт через `grep -r "Recorder Wookiee\|Wookiee Recorder" tests/`).

---

### 4.2 Трек C1 — расширение scheduler_worker (~4 часа)

**Цель:** существующий `scheduler_worker.py` сейчас опрашивает ровно одного юзера через `SCHEDULER_BITRIX_USER_ID` и шлёт результат на `SCHEDULER_TELEGRAM_ID`. Расширяем до multi-user: опрос календарей всех `telemost.users.is_active=true`.

**Файл:** `services/telemost_recorder_api/workers/scheduler_worker.py` (правка существующего, не создание нового).

**Что меняем в существующей логике:**

1. **Источник списка юзеров.** Сейчас в `run_forever()` берётся ровно один `SCHEDULER_BITRIX_USER_ID`. Меняем на цикл по `telemost.users WHERE is_active = true`. Legacy-single-user режим сохраняем как fallback (если env переменная выставлена — поверх БД-юзеров).

2. **Дедупликация одного события на N календарей.** Та же планёрка (13 чел) сейчас была бы INSERT-нута 13 раз через разные ownerId. Партиальный unique `idx_meetings_active_unique ON (meeting_url) WHERE status IN ('queued','recording','postprocessing')` ловит на стороне БД (ON CONFLICT DO NOTHING). Дополнительно делаем in-memory дедуп `(meeting_url, scheduled_at)` внутри одного тика — чтобы не делать 13 одинаковых INSERT в одном проходе.

3. **Фильтр `#nobot`.** Перед INSERT — проверка `if "#nobot" in event_name.lower(): continue`. Сейчас этой проверки нет.

4. **`triggered_by`.** Сейчас единый `SCHEDULER_TELEGRAM_ID` пишется в `triggered_by`. Меняем: пишем `telegram_id` владельца календаря, на котором событие нашлось первым (после дедупа).

5. **Tick rate.** Существующий `SCHEDULER_TICK_SECONDS=60` оставляем. `SCHEDULER_LEAD_SECONDS=90` (запас на спавн контейнера) оставляем. `SCHEDULER_GRACE_SECONDS=300` (не подбирать встречи которые начались >5 мин назад) оставляем.

**Pseudocode (только изменения в `run_forever`):**
```python
async def run_forever() -> None:
    if not TELEMOST_SCHEDULER_ENABLED:
        logger.info("scheduler disabled by env")
        return
    while True:
        try:
            await _tick_all_users()
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(SCHEDULER_TICK_SECONDS)

async def _tick_all_users() -> None:
    users = await fetch_active_users()  # SELECT FROM telemost.users WHERE is_active
    horizon_start = now() - timedelta(seconds=SCHEDULER_GRACE_SECONDS)
    horizon_end = now() + timedelta(seconds=SCHEDULER_LEAD_SECONDS + 30)

    # In-memory buffer на дедуп
    candidates: dict[tuple[str, datetime], _Candidate] = {}

    for u in users:
        try:
            events = await bitrix_calendar_event_get(
                owner_id=u.bitrix_id, from_ts=horizon_start, to_ts=horizon_end,
            )
        except Exception:
            logger.exception("bitrix failed for user %s", u.bitrix_id)
            continue
        for ev in events:
            if "#nobot" in ev.name.lower():
                continue
            url = extract_telemost_url(ev)
            if not url:
                continue
            key = (url, ev.date_from)
            candidates.setdefault(key, _Candidate(
                url=url, title=ev.name, scheduled_at=ev.date_from,
                triggered_by=u.telegram_id, source_event_id=str(ev.id),
            ))

    for c in candidates.values():
        await insert_meeting_if_not_exists(c)  # ON CONFLICT DO NOTHING
```

**Запуск:** менять не надо. `app.py` `_lifespan` уже стартует `_supervised("scheduler_worker", scheduler_loop)`. Просто выставляем env (см. ниже) — задача активируется.

**Env-переменные:**
```
TELEMOST_SCHEDULER_ENABLED=true              # новый флаг для отключения (default false)
TELEMOST_SCHEDULER_TICK_SECONDS=60           # оставляем как есть
TELEMOST_SCHEDULER_LEAD_SECONDS=90           # оставляем как есть
TELEMOST_SCHEDULER_GRACE_SECONDS=300         # оставляем как есть
# TELEMOST_SCHEDULER_BITRIX_USER_ID=...      # legacy single-user, в проде НЕ ставим
# TELEMOST_SCHEDULER_TELEGRAM_ID=...         # legacy single-user, в проде НЕ ставим
```

Когда `TELEMOST_SCHEDULER_BITRIX_USER_ID` пустой — берём всех `is_active=true` юзеров. Когда выставлен — legacy mode (для dev).

**Что НЕ делает scheduler:**
- Не вызывает recorder напрямую — INSERT в `telemost.meetings` + дальше работает существующий `recorder_worker` (он подхватывает по `FOR UPDATE SKIP LOCKED`).
- Не пишет в Bitrix — read-only.

**Edge cases:**
- Bitrix API падает на одном юзере → logged exception, остальные юзеры обрабатываются.
- Юзер удалил Telemost-ссылку после нашего INSERT → recorder зайдёт по URL → `MEETING_NOT_FOUND` → status=failed, не страшно.
- Встреча перенесена → новый `DATE_FROM`. Partial unique `idx_meetings_active_unique` по `meeting_url` — старый INSERT (queued, old time) останется. **Решение для C1.1 (после первой недели):** добавить UPDATE `scheduled_at` если статус='queued' и `source_event_id` совпал. Для первой версии — accept rare false starts.
- Юзер в команде ушёл → `is_active=false` → его календарь не опрашивается.

**Тесты (на моках):**
- 1 встреча в 1 календаре → 1 INSERT
- 1 встреча в 12 календарях (одна и та же планёрка) → 1 INSERT (in-memory дедуп)
- Встреча с `#nobot` → пропуск
- Встреча без Telemost-ссылки → пропуск
- Падение Bitrix API на одном юзере → loop продолжается, остальные обработаны
- Legacy single-user (env `SCHEDULER_BITRIX_USER_ID` выставлен) → опрашивает только его
- `TELEMOST_SCHEDULER_ENABLED=false` → loop не запускается

**Smoke-data (прогон от 2026-05-16, неделя 18-24 мая):**
- 26 уникальных встреч после дедупа (было 56 копий по календарям)
- 8 с Telemost-ссылкой → реально пойдут в очередь
- 3 без ссылки → будут в дайджесте с кнопкой
- 15 личных (отпуск/няня/уроки/...) → не попадают (фильтр `attendees<2 AND is_meeting=False`)

---

### 4.3 Трек C2 — morning digest (1 день)

**Цель:** каждое утро в 09:00 МСК — DM каждому юзеру со списком встреч на день и кнопками действий.

**Файл:** `services/telemost_recorder_api/workers/morning_digest.py`

**Trigger:** asyncio.sleep до следующих 09:00 МСК (учёт TZ через `zoneinfo("Europe/Moscow")`).

**Логика:**
```python
async def morning_digest_loop() -> None:
    if not MORNING_DIGEST_ENABLED:
        logger.info("morning_digest disabled by env")
        return
    while True:
        next_run = compute_next_msk_hour(MORNING_DIGEST_HOUR_MSK)
        await asyncio.sleep((next_run - now()).total_seconds())
        try:
            await send_digests_to_all_users()
        except Exception:
            logger.exception("morning_digest tick failed")

async def send_daily_digest_to_user(user):
    today_start = msk_now().replace(hour=0, minute=0, second=0)
    today_end = today_start + timedelta(days=1)

    events = await bitrix_calendar_event_get(
        owner_id=user.bitrix_id, from_ts=today_start, to_ts=today_end
    )
    events = dedup(events)
    events = filter_real_meetings(events)  # attendees>=2 OR is_meeting

    has_link, needs_link, skip = classify(events)

    if not (has_link or needs_link):
        return  # пустой день — не шлём дайджест

    msg = render_digest(user, has_link, needs_link)
    keyboard = build_buttons_for_needs_link(needs_link)

    await tg_send_message(user.telegram_id, msg, reply_markup=keyboard)
```

**Шаблон сообщения:**
```
Доброе утро, {user.short_name}.

Сегодня у тебя {N} встреч:

🎙 Запишу (есть Telemost-ссылка):
   • 11:00 — Стенд-ап продакт-команды
   • 14:30 — Ревью октября

⚠️ Нет ссылки — добавлю если нажмёшь:
   • 16:00 — Встреча с Леной  [➕ Добавить Telemost]

⏭ Личное (не приду):
   • 08:30 — Терапевт Оливии
```

**Кнопка `[➕ Добавить Telemost]` (callback_data: `add_telemost:<bitrix_event_id>`):**

```python
async def on_add_telemost_click(event_id):
    # 1. Создаём Telemost-комнату
    conference = await yandex_telemost.create_conference(
        host_email="recorder@wookiee.shop"  # бот хост
    )

    # 2. Читаем текущий Bitrix-event чтобы достать ownerId + LOCATION
    ev = await bitrix_calendar_event_get_one(event_id)

    # 3. Пишем URL в LOCATION
    new_location = (ev.location or "") + f"\n{conference.join_url}"
    await bitrix_calendar_event_update(
        event_id=event_id, owner_id=ev.owner_id, fields={"LOCATION": new_location}
    )

    # 4. Отвечаем юзеру
    await tg_send_message(
        user.telegram_id,
        f"✅ Добавил ссылку:\n{conference.join_url}\n\nПриду на встречу."
    )
```

**На следующем 60-секундном тике scheduler-а** встреча перекласифицируется в «🎙 запишу» и автоматически встанет в очередь.

**Тесты:**
- Юзер без встреч → не шлём ничего
- Юзер только с личным → не шлём
- Юзер с 2 ⚠️ → дайджест с 2 кнопками
- Клик кнопки → mock Telemost API + mock Bitrix update → проверка вызовов
- `MORNING_DIGEST_ENABLED=false` → loop не запускается

---

### 4.4 Трек E — OAuth Telemost health-check (0.5 дня)

**Цель:** заранее знать что OAuth-токен Telemost API скоро истекает или revoked. Использует `shared/yandex_telemost.py` из трека T2.

**Файл:** расширение существующего cookie-чек-скрипта (имплементер найдёт точный путь через `grep -l "cookie" scripts/` или по `crontab -l` на сервере). Если файла нет — создать `scripts/telemost_check_cookies.py`.

**Логика:**
```python
async def check_telemost_oauth():
    try:
        await yandex_telemost.list_conferences(limit=1)
        logger.info("OAuth: OK")
    except TelemostTokenExpired:
        new_access, new_refresh = await yandex_telemost.refresh_oauth_token()
        # MVP: алерт оператору с просьбой перезаписать вручную в .env
        # Auto-update .env — отдельный backlog (требует прав на запись + recreate)
        await alert(
            f"Telemost OAuth обновлён. Перезапиши в .env:\n"
            f"YANDEX_TELEMOST_OAUTH_TOKEN={new_access[:8]}...\n"
            f"YANDEX_TELEMOST_REFRESH_TOKEN={new_refresh[:8]}..."
        )
    except Exception as e:
        await alert(f"Telemost OAuth check failed: {e}")
```

**Persistence новых токенов после refresh — НЕ автоматический в этой задаче.**

---

### 4.5 Трек B — Voice-triggers Фаза 1 (1.5 дня)

**Цель:** на постпроцессе детектить обращения «Саймон, ...» в транскрипте, рендерить в саммари без действий.

**Файл:** `services/telemost_recorder_api/voice_triggers.py` + правка `llm_postprocess.py` и `notifier.py`.

**Двухстадийный pipeline:**

**Stage 1 — Detection (LIGHT model, ~$0.001/звонок):**
```
Промт:
"Найди в транскрипте все фразы где собеседник обращается к ассистенту
по имени Саймон.

ASR-варианты имени: Саймон, Симон, Сайман, Семён, Семёна, Сын мой, Пай-мон.

Кандидат = первое слово после паузы (или в начале фразы) + дальше команда
(глагол в повелительном или ключевые слова: запомни, заметка, задача, поставь,
напомни).

НЕ кандидат = если 'Саймон' — это начало обычной фразы без команды.

Верни JSON:
[
  {
    'speaker': 'Данила',
    'timestamp': '14:23',
    'raw_text': '<цитата фрагмента 1-2 предложения>',
    'intent_guess': 'task' | 'meeting' | 'note' | 'attention' | 'reminder',
    'confidence': 0.0..1.0
  }
]

Транскрипт:
{transcript_with_speakers_and_timestamps}"
```

**Stage 2 — Slot-filling per intent (HEAVY model):**

Для каждого кандидата с confidence >= 0.5 вызывается отдельный промт под тип. Промты адаптированы из существующих SKILL.md:

**`task` промт** (адаптация `/bitrix-task` SKILL.md):
```
В этом фрагменте {speaker} попросил Саймона поставить задачу.

Фрагмент: "{raw_text}"
Контекст (предыдущие 30 сек): "{prev_context}"
Команда Wookiee (для резолва имён в bitrix_id):
{telemost.users}

Извлеки структурированную задачу:
- title: краткое название (5-10 слов)
- responsible: на кого ставится (имя из команды или 'не указано')
- created_by: от кого ставится. Если не сказано явно — спикер ({speaker}).
- auditors: список наблюдателей (имена из команды)
- accomplices: список соисполнителей
- description: цитата из транскрипта + контекст
- deadline: ISO datetime. Если 'до пятницы' — ближайшая пятница 18:00 МСК.
            Если не указан — null (попросим юзера уточнить).

Верни JSON с этими полями. Незаполненные поля = null.
```

**`meeting` промт** (адаптация `/calendar` SKILL.md): аналогично, поля `name` / `from` / `to` / `attendees` / `description`.

**`note` / `attention` промт**: простой — сохраняем фрагмент как цитату.

**`reminder` промт**: парсит «через X» / «к Y» в ISO datetime.

**Что попадает в саммари** (новые секции под существующим саммари):

```markdown
🔖 Важные моменты (Саймон обратил внимание)
─────────────────────────────────────────────
• 14:23 (Данила) "обсуждение цены на Wendy — не ниже 4500"

📌 Задачи (готовы к постановке в Битрикс)
─────────────────────────────────────────────
• Алина — собрать выкупаемость по бомберам за октябрь
  Постановщик: Данила (1) → Исполнитель: Алина (1625)
  Наблюдатели: —
  Соисполнители: —
  Дедлайн: пт 22.05 18:00 МСК
  [✅ Создать]  [✏️ Поправить]  [❌ Игнор]

📅 Предлагаемые встречи
─────────────────────────────────────────────
• С Леной, пн 25.05 14:00, повестка: обзор поставок
  Участники: Лена, Данила
  [✅ Создать]  [✏️ Поправить]  [❌ Игнор]

🔔 Напоминания
─────────────────────────────────────────────
• Напомнить Даниле в пт 22.05 09:00 — перезвонить Сергею

📝 Заметки
─────────────────────────────────────────────
• 11:42 (Данила) "Идея: добавить опцию 'я подумаю' в флоу выкупа"
```

**В Фазе 1 кнопки `[✅ Создать]` РИСУЮТСЯ, но НЕ работают** (отрисовываются с placeholder callback `voice:<id>:disabled` который шлёт юзеру «пока недоступно, ждём Phase 2»). Реальная запись в Битрикс — в Фазе 2 (трек D).

**Метрика успеха Фазы 1:**
- Precision (доля валидных кандидатов от всех показанных) ≥ 0.7
- Recall (доля пойманных команд от реально сказанных) ≥ 0.8

Если метрика хуже — итерируем промт перед Фазой 2.

---

### 4.6 Трек D — Voice-triggers Фаза 2 (1 день, после B)

**Цель:** кнопки `[✅ Создать]` реально пишут в Bitrix.

**Файл:** `shared/bitrix_writes.py` + расширение Telegram handlers + миграция 006.

**`shared/bitrix_writes.py` API:**
```python
async def create_task(
    *,
    title: str,
    responsible_id: int,
    created_by: int,
    description: str,
    deadline: datetime | None = None,
    auditors: list[int] = (),
    accomplices: list[int] = (),
    priority: int = 1,
) -> int:
    """Returns Bitrix task ID."""
    payload = {"fields": {
        "TITLE": title,
        "RESPONSIBLE_ID": responsible_id,
        "CREATED_BY": created_by,
        "DESCRIPTION": description,
        "DEADLINE": deadline.strftime("%Y-%m-%dT%H:%M:%S") if deadline else None,
        "AUDITORS": auditors,
        "ACCOMPLICES": accomplices,
        "PRIORITY": priority,
    }}
    r = await httpx.post(f"{BITRIX_WEBHOOK}/tasks.task.add.json", json=payload)
    return r.json()["result"]["task"]["id"]


async def create_calendar_event(
    *,
    owner_id: int,
    name: str,
    from_ts: datetime,
    to_ts: datetime,
    description: str,
    location: str | None = None,
    attendees: list[int] = (),
) -> int:
    """Returns Bitrix event ID."""
    # аналогично, через calendar.event.add
```

**Кнопки в Telegram (callback_data):**
- `task_create:{cand_id}` → читает task-кандидат из БД, вызывает `create_task()`, отвечает «✅ Готово, https://bitrix24/.../task/{id}»
- `task_edit:{cand_id}` → шлёт inline-форму с полями
- `task_ignore:{cand_id}` → помечает кандидат как `ignored`, кнопки скрываются
- Аналогично для `meeting_create/edit/ignore`

**Persistence:** воркфлоу нужен где хранить кандидатов между моментом саммари и кликом кнопки (может пройти час). Таблица `telemost.voice_trigger_candidates` создаётся миграцией 006 (см. §2.5).

---

## 5. Тестовое ревью — что Саймон сделал бы на 18-24 мая 2026

Прогон против живого Bitrix-календаря команды (12 активных юзеров, выполнен 2026-05-16):

| Группа | Кол-во |
|--------|--------|
| 🎙 С Telemost-ссылкой → запишет | 8 |
| ⚠️ Без ссылки → кнопка «➕ Добавить» в дайджесте | 3 |
| ⏭ Личное → не трогает | 15 |
| **Всего уникальных событий** | **26** |

### 🎙 Запишу:
- Пн 18.05 09:30 — Обсуждаем итоги второго месяца работы (2 чел)
- Пн 18.05 14:00 — **Планерка команды Wookiee** (13 чел)
- Вт 19.05 14:00 — Dayli (5 чел)
- Вт 19.05 14:30 — Наши соцсети (3 чел)
- Ср 20.05 14:00 — Dayli
- Чт 21.05 14:00 — Dayli
- Пт 22.05 14:00 — Dayli
- Пн 25.05 14:00 — Планерка команды Wookiee

### ⚠️ Нужна ссылка:
- Ср 20.05 11:30 — созвон ВК и внутренний маркетинг (2 чел)
- Чт 21.05 11:00 — **Воркшоп по ИИ — разбор задач с командой** (13 чел) ← наибольшая ценность кнопки
- Пт 22.05 16:00 — Обсуждение задач по продукту (5 чел)

### ⏭ Не трогает:
Терапевт Оливии, няня, отпуск Анастасии, уроки английского, дни рождения, проверки — 15 событий с `attendees<2 AND is_meeting=False`.

---

## 6. Privacy, safety, rollback

### 6.1 Privacy (D3)
- **Дефолт:** Саймон ходит на ВСЕ встречи у которых есть Telemost-ссылка и `attendees>=2 OR is_meeting=True`.
- **Юридический риск:** запись встреч с внешними участниками без явного согласия может нарушать 152-ФЗ. Решение Данилы.
- **Safety vent:** тег `#nobot` в названии встречи → пропуск без вопросов. Документируем в `/help` + первом DM каждому юзеру при онбординге.
- **Удаление:** существующая кнопка `🗑 Удалить` под саммари (soft-delete через `deleted_at`).

### 6.2 Rollback (что делать если что-то сломается)
- **scheduler_worker флудит**: env `TELEMOST_SCHEDULER_ENABLED=false` → asyncio task не стартует на старте. Дефолт `false`.
- **morning_digest шлёт ложные дайджесты**: env `MORNING_DIGEST_ENABLED=false`.
- **voice-triggers галлюцинируют**: env `VOICE_TRIGGERS_ENABLED=false` → постпроцесс не вызывает stage 1, новые секции не появляются в саммари.
- **Telemost API упал**: кнопка «➕ Добавить» отвечает «Telemost API недоступен, добавь ссылку руками. Подробности в логах».

### 6.3 Health checks (мониторинг)
| Что | Когда | Где смотреть |
|-----|-------|-------------|
| Куки Yandex 360 (запись) | Daily 08:00 МСК | `@wookiee_alerts_bot` |
| OAuth Telemost API (генерация комнат) | Daily 08:00 МСК (extends cookie check) | `@wookiee_alerts_bot` |
| scheduler_worker жив | last_successful_tick в Supabase, алерт если >5 мин нет тика | `@wookiee_alerts_bot` |
| morning_digest сработал | Проверка раз в сутки: за последние 25 ч был ли запуск | `@wookiee_alerts_bot` |

**Операционное замечание:** контейнер `wookiee_cron` подтянет новые `YANDEX_TELEMOST_*` env переменные только после `docker compose up -d wookiee-cron` (без `--build`). Сейчас контейнер был пересоздан до того как переменные добавили в `.env`, поэтому видеть их он не будет — перед включением OAuth health-check (трек E) обязательный recreate.

---

## 7. Открытые задачи на Данилу

Эти шаги я не могу сделать сам (политика платформ или физическое отсутствие доступа):

1. **PNG-аватарки в репо** → положить в `data/branding/` (квадрат + прямоугольник)
2. **@BotFather** → /setname=Саймон, /setdescription, /setuserpic с квадратной PNG
3. **admin.yandex.ru** → переименовать `recorder@wookiee.shop` в «Саймон» + загрузить прямоугольную PNG
4. **После первого боевого теста**: ротировать Yandex OAuth Client Secret (он засветился в нашей переписке) → пришлёшь новый Secret → я обновлю .env и сделаю refresh токена

---

## 8. Out-of-scope (не в этой спеке)

| Что | Почему отложено |
|-----|-----------------|
| Real-time voice commands (ассистент отвечает голосом в звонке) | Сложно, +неделя работы, ROI неясен. Постобработка покрывает 90% ценности. |
| Multi-tenant (несколько Yandex 360 организаций) | YAGNI — один тенант, второго клиента нет. |
| Фикс `extract_participants()` для Yandex 360 UI | Нужен живой DOM-дамп, инфра под него уже в проде (PR #146 + `TELEMOST_DUMP_PARTICIPANTS_DOM`). Сделаем при первом звонке где станет важно. |
| Кнопка «Перегенерить summary без перезаписи звука» | Backlog, не блокирует rollout. |
| Поиск по транскриптам через Telegram | Не запрошен. Идея на будущее: `/search <query>` → Саймон ищет в pgvector embeddings всех транскриптов. |
| Голосовые ответы Саймона (TTS) | Out-of-scope для постобработки. |
| Авто-запись новых OAuth токенов в .env | После refresh — алерт оператору с просьбой перезаписать. Auto-update — отдельный backlog. |

---

## 9. Rollout-стратегия и таймлайн

### День 1 (когда стартую)
- **Утро:** Трек A (рейнэйм) — PR open до полудня.
- **День:** Трек E (OAuth health) — extends cookie-check скрипт. Recreate `wookiee_cron`.
- **Вечер:** Трек C1 — расширение `scheduler_worker.py` под multi-user (~4 часа: правка + тесты на моках + локальный прогон против реального Bitrix). PR open.

### День 2
- C1 в проде с `TELEMOST_SCHEDULER_ENABLED=false`. Проверяю что без флага задача даже не стартует.
- Включаю флаг на полчаса в 13:00 МСК — смотрю что INSERT-ы по реальной планёрке создаются корректно. После 2-3 успешных тиков выключаю обратно до утренней рассылки.
- Параллельно: старт Трека C2 (morning_digest).

### День 3
- Трек C2 завершаю — рендер + кнопка `[➕ Добавить Telemost]`.
- Параллельно: Трек B Stage 1 — детекция кандидатов.

### День 4
- Трек B Stage 2 — slot-filling, новые секции в саммари (БЕЗ записи в Bitrix).
- Включаю `MORNING_DIGEST_ENABLED=true` — первая утренняя рассылка в 09:00 МСК.

### День 5
- Дайджест прислан утром, наблюдаю как команда реагирует.
- В 12:00–14:00 включаю `TELEMOST_SCHEDULER_ENABLED=true` — первая авто-запись планёрки в 14:00.
- Smoke-watch один звонок до конца.

### День 6-7
- Наблюдение Фазы 1 voice-triggers на 5-10 реальных звонках.
- Метрика precision/recall.

### День 8-9
- Трек D (Фаза 2 voice-triggers) — кнопки реально пишут в Bitrix.
- Применяю миграцию 006 (`voice_trigger_candidates`).
- `shared/bitrix_writes.py` + persistence.

### День 10
- Финальный smoke-test на всём цикле: встреча из календаря → авто-запись → саммари с командами «Саймон, ...» → клик «✅ Создать» → задача в Битриксе видна.
- Готовим короткий онбординг-DM от Саймона каждому юзеру с шорт-листом фич.

### Прод (День 10+)
- Все 4 трека на проде. Voice-triggers и auto-join активны для всей команды.
- Дальше операционный режим: мониторинг health-checks, разбор edge-кейсов.

**Сравнение с v1.0:** общий таймлайн сократился с ~12 дней до 10 (трек C1 был 1.5 дня → 4 часа, потому что не строим с нуля).

---

## 10. Метрики которые буду собирать после прода

- **Coverage** — % внутренних встреч которые Саймон записал автоматически (без `/record` руками)
- **Voice-trigger precision** — % команд `Саймон, ...` которые оператор подтвердил кнопкой `✅` от всех показанных
- **Voice-trigger recall** — оценочно (трудно мерить точно), через ручную выборку 10 звонков в неделю
- **Telemost-room generation usage** — сколько раз кнопка `➕ Добавить Telemost` была нажата
- **Bitrix task creation** — сколько задач Саймон создал из голосовых команд (вклад в продуктивность команды)

Дашборд: можно в существующий Hub `/operations/saimon` или просто `SELECT` в Supabase.

---

## 11. Approval

Спека готова к ревью. Что мне нужно от Данилы:

1. **Прочесть §1 (decisions log)** — точно ли всё что там я зафиксировал = твоё намерение?
2. **§4.5-4.6 (voice-triggers UX)** — устраивает ли формат секций в саммари? Кнопки `✅ Создать` / `✏️ Поправить` / `❌ Игнор` ОК?
3. **§9 (таймлайн)** — параллельный или последовательный rollout? Я предлагаю параллельный с feature-flags (`*_ENABLED` env vars).
4. **§6.1 (privacy)** — окончательно подтверждаешь: все встречи, без internal-фильтра, только `#nobot` opt-out?

После approval — начинаю с Трека A (имя + аватарки в репо).
