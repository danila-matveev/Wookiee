# Telemost Recorder — Production Service Design

**Дата:** 2026-05-07
**Статус:** Approved (брейншторм завершён, ждёт user review)
**Контекст:** MVP записывает + транскрибирует через ручной `docker run`. Нужен production-сервис с автозахватом встреч из Bitrix24-календарей всех сотрудников + Telegram-бот для ручного триггера + LLM-постобработка с тегированием тем + хранение в Supabase + рассылка результата через Telegram.

---

## 1. Цель и границы

**Цель:** превратить существующий MVP-recorder в постоянно работающий многопользовательский сервис, который автоматически записывает все встречи команды Wookiee, постпроцессит транскрипт через LLM и публикует результат участникам.

**В границах:**
- Multi-user (auth по `telegram_id` из Bitrix-roster)
- Bitrix24 calendar polling + Telegram-триггер
- LLM-постобработка single-call (параграфы, пунктуация, спикеры, теги тем, structured summary) с словарём Wookiee
- Storage в Supabase (схема `telemost`)
- Audio TTL 30 дней, текст бессрочно

**Не в границах:**
- Notion-публикация (Phase 2)
- Извлечение задач → Bitrix (Phase 3)
- Pyannote-диаризация (Phase 3, если LLM-спикеры окажутся недостаточны)
- WebUI для поиска (Phase 3)
- Платное MTProto API для bot-creation (используем нативный Managed Bots в Bot API 9.6)

---

## 2. Архитектура

```
┌──────────────────────────────────────────────────────────────────────┐
│                      TRIGGER LAYER                                    │
├────────────────────────────────┬─────────────────────────────────────┤
│  Bitrix24 Calendar Poller      │  Telegram Bot Webhook               │
│  (asyncio task, каждые 60s)    │  (FastAPI route)                    │
│                                │                                     │
│  - calendar.event.get на всех  │  - Auth: telegram_id ∈ telemost.users │
│    активных сотрудников        │  - /record <url> → enqueue          │
│  - Дедуп по Telemost URL       │  - /status, /list, /help            │
│  - +5 минут вперёд каждый poll │                                     │
└──────────────────┬─────────────┴────────────────┬────────────────────┘
                   │                              │
                   └──────────────┬───────────────┘
                                  ▼
                    ┌──────────────────────────┐
                    │ telemost.meetings        │  ← Postgres queue
                    │ (Supabase)               │     status: queued →
                    │                          │     recording →
                    │                          │     postprocessing →
                    │                          │     done / failed
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  Worker Loop             │  ← max N parallel (config)
                    │  (asyncio + docker SDK)  │     UPDATE ... RETURNING
                    │                          │     for atomic pick
                    │  Спавнит контейнер       │
                    │  telemost_recorder       │
                    │  для каждой задачи       │
                    └─────────────┬────────────┘
                                  │ audio.opus + raw_segments.json
                                  ▼
                    ┌──────────────────────────┐
                    │  Postprocess Task        │  ← async background task
                    │  (single LLM call)       │     idempotent на raw artifacts
                    │                          │
                    │  Gemini Flash (MAIN)     │
                    │  + Wookiee dictionary    │
                    │  + Bitrix participants   │
                    │  → structured JSON       │
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  Supabase (single source │
                    │  of truth)               │
                    │  - telemost.meetings     │
                    │  - telemost.users        │
                    │  - telemost.processed_   │
                    │    calendar_events       │
                    │  + Storage bucket        │
                    │    "telemost-audio"      │
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  Notifier                │
                    │  - Telegram DM           │  → триггерщику
                    │                          │     + всем инвайтам
                    │                          │       с telegram_id
                    └──────────────────────────┘
```

**Деплой:** один долгоживущий FastAPI-сервис `telemost_recorder_api` (порт 8006) в `deploy/docker-compose.yml`. Внутри — HTTP webhook + календарный поллер + worker-loop как asyncio-таски одного процесса. Спавнит **разовые контейнеры** `telemost_recorder:latest` через mounted Docker socket для каждой записи.

**Recorder-контейнер не трогаем** (`services/telemost_recorder/`, `scripts/telemost_record.py`). API-сервис передаёт ему meeting URL через CLI-args, контейнер пишет artefact в `data/telemost/{meeting_id}/`, API забирает после exit.

---

## 3. Структура файлов

**Новый сервис:**
```
services/telemost_recorder_api/
├── __init__.py
├── app.py                  # FastAPI factory (create_app)
├── config.py               # env vars: TELEMOST_BOT_TOKEN, max_parallel и т.д.
├── routes/
│   ├── telegram.py         # POST /telegram/webhook
│   ├── internal.py         # POST /internal/jobs (для poller)
│   └── health.py           # GET /health
├── workers/
│   ├── calendar_poller.py  # asyncio task, опрашивает Bitrix calendar
│   ├── recorder_worker.py  # asyncio task, picks queued jobs, spawns container
│   └── postprocess_worker.py  # asyncio task, runs LLM postprocess
├── services/
│   ├── bitrix_calendar.py  # Bitrix REST: calendar.event.get
│   ├── docker_client.py    # docker SDK wrapper для recorder-spawn
│   ├── llm_postprocess.py  # OpenRouter single-call постпроцессор
│   ├── notifier.py         # Telegram sendMessage с summary
│   ├── supabase_client.py  # asyncpg connection pool
│   └── user_sync.py        # Bitrix → telemost.users синхронизация
└── tests/
    ├── test_telegram_routes.py
    ├── test_calendar_poller.py
    ├── test_postprocess.py
    └── ...

deploy/Dockerfile.telemost_recorder_api    # FastAPI image
deploy/docker-compose.yml                  # +service telemost-recorder-api

database/telemost/                          # SQL миграции
├── 001_schema.sql
├── 002_users.sql
├── 003_meetings.sql
└── README.md

scripts/telemost_audio_cleanup.py           # cron: удаление аудио > 30 дней
data/wookiee_dictionary.yml                 # YAML с маркетплейс-сленгом
```

**Изменения в существующем:**
- `deploy/docker-compose.yml` — добавить service `telemost-recorder-api`
- `deploy/docker-compose.yml` — в `wookiee-cron` добавить cron-job на cleanup
- `services/telemost_recorder/speakers.py` — переиспользуем как библиотеку для синка users + LLM resolve

---

## 4. Схема Supabase

Schema `telemost`. RLS включён, `anon` заблокирован, доступ по service-role key.

```sql
-- 001_schema.sql
CREATE SCHEMA IF NOT EXISTS telemost;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- для gen_random_uuid

-- 002_users.sql
CREATE TABLE telemost.users (
    telegram_id   bigint PRIMARY KEY,
    bitrix_id     text NOT NULL UNIQUE,
    name          text NOT NULL,
    short_name    text,
    is_active     boolean NOT NULL DEFAULT true,
    synced_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.users FROM anon;

-- 003_meetings.sql
CREATE TABLE telemost.meetings (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source               text NOT NULL CHECK (source IN ('telegram','calendar')),
    source_event_id      text,
    triggered_by         bigint REFERENCES telemost.users(telegram_id),
    meeting_url          text NOT NULL,
    title                text,
    organizer_id         bigint REFERENCES telemost.users(telegram_id),
    invitees             jsonb NOT NULL DEFAULT '[]',
    scheduled_at         timestamptz,
    started_at           timestamptz,
    ended_at             timestamptz,
    duration_seconds     integer,
    status               text NOT NULL DEFAULT 'queued'
                          CHECK (status IN ('queued','recording','postprocessing','done','failed')),
    error                text,
    audio_path           text,
    audio_expires_at     timestamptz,
    raw_segments         jsonb,
    processed_paragraphs jsonb,
    speakers_map         jsonb,
    summary              jsonb,
    tags                 text[],
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_meetings_status ON telemost.meetings(status);
CREATE INDEX idx_meetings_scheduled ON telemost.meetings(scheduled_at);
CREATE INDEX idx_meetings_source_event ON telemost.meetings(source_event_id) 
    WHERE source_event_id IS NOT NULL;
CREATE INDEX idx_meetings_audio_expires ON telemost.meetings(audio_expires_at) 
    WHERE audio_path IS NOT NULL;

ALTER TABLE telemost.meetings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.meetings FROM anon;

-- Trigger: updated_at
CREATE TRIGGER meetings_updated_at BEFORE UPDATE ON telemost.meetings
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- Дедуп календарных событий
CREATE TABLE telemost.processed_calendar_events (
    bitrix_event_id  text PRIMARY KEY,
    meeting_id       uuid REFERENCES telemost.meetings(id) ON DELETE CASCADE,
    processed_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE telemost.processed_calendar_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON telemost.processed_calendar_events FROM anon;
```

**Storage bucket:** `telemost-audio` (private, RLS включён, доступ только service-role).

---

## 5. LLM Postprocess

**Single Gemini-Flash call через OpenRouter (MAIN tier).** Вход — raw transcription chunks + Wookiee dictionary + Bitrix participants. Выход — structured JSON.

**Prompt template** (хранится в `services/telemost_recorder_api/services/llm_postprocess.py`):

```
Ты постпроцессор русскоязычной транскрипции встречи команды Wookiee. 
Бренд продаёт нижнее бельё на Wildberries и Ozon. 

Контекст словаря:
- Бренд-модели: <models from Supabase>
- Сотрудники: <Bitrix users>
- Маркетплейс-сленг: <YAML dictionary>

Дано: список 25-сек чанков с сырой транскрипцией, имена приглашённых.

Задачи:
1. Склей чанки в связные параграфы по смыслу. Если фраза разрезана на границе чанка — соедини.
2. Восстанови пунктуацию, заглавные буквы, нормализуй фамильярные формы.
3. Исправь искажения распознавания по словарю.
4. Сопоставь Speaker N → реальное имя из participants по контексту.
5. Извлеки темы (multi-select из канонического списка): креативы, реклама, маркетинг,
   продажи, разработка, отчётность, HR, финансы, ассортимент, поставки, логистика,
   упаковка, бренд, маркетплейс, конкуренты, аналитика, продукт, контент, операции, прочее.
6. Структурированный summary: участники, темы (с цитатой-якорем), решения, задачи.

Output (JSON):
{
  "paragraphs": [...],
  "speakers_map": {...},
  "tags": [...],
  "summary": {...}
}
```

**Output JSON schema:**
```typescript
{
  paragraphs: [{speaker: string, start_ms: int, text: string}],
  speakers_map: Record<string, string>,  // "Speaker 0" → "Полина Ермилова"
  tags: string[],                         // canonical topic tags
  summary: {
    participants: string[],
    topics: [{title: string, anchor: string}],  // anchor = "[MM:SS]"
    decisions: string[],
    tasks: [{assignee: string|null, what: string, when: string|null}]
  }
}
```

**Wookiee dictionary build** (`services/telemost_recorder_api/services/dictionary.py`):
1. Сотрудники → `SELECT name, short_name FROM telemost.users WHERE is_active = true`
2. Модели → `SELECT kod, nazvanie FROM public.modeli_osnova WHERE status_id IS NOT NULL`
   — ⚠️ В БД имена транслитом (Wendy, Audrey, Charlotte), в речи русские (Венди, Одри, Шарлотт).
   YAML словарь даёт map транслит→кириллица для нормализации в постпроцессе.
3. Маркетплейс-сленг + транслит-маппинг → `data/wookiee_dictionary.yml` (статика, ручное ведение)

Пример `wookiee_dictionary.yml`:
```yaml
brand_aliases:
  Wendy: [венди, вэнди, венде, вени]
  Audrey: [одри, оудри, авдрей]
  Charlotte: [шарлотт, шарлотта, шарлот]
  Bella: [белла, бела]
  Joy: [джой, джо, жой]
  Andie: [энди, анди, андре]

marketplace_terms:
  Wildberries: [валбериз, валберис, балбер, ВБ, валберес]
  Ozon: [озон, сазон, азон, оз]

corporate_jargon:
  - артикул
  - креатив
  - посевы
  - таргет
  - воронка
  - СПП  # скидка постоянного покупателя
  - ДРР  # доля рекламных расходов
  - ROI
  - выкуп
  - локализация
  - оборачиваемость
```

Кэш на 24 часа в памяти.

---

## 6. API Endpoints

| Method | Path | Описание |
|--------|------|----------|
| POST | `/telegram/webhook` | Telegram updates. Валидация `X-Telegram-Bot-Api-Secret-Token`. |
| POST | `/internal/jobs` | Для будущих internal-call (сейчас календарный поллер вызывает напрямую через DB). |
| GET | `/health` | Liveness. Проверки: last_calendar_poll < 5 min, queue_lag < 10 min, DB ping. |
| GET | `/meetings/{id}` | Internal API (для будущего UI и debug). |

**Telegram-команды бота:**
- `/start` — приветствие + проверка auth (telegram_id ∈ telemost.users)
- `/record <url>` — поставить в очередь
- `/status` — твои активные/последние записи
- `/list` — последние 10 встреч с твоим участием
- `/help` — справка
- (Phase 3) `/extract_tasks <meeting_id>` — извлечь задачи из встречи и создать в Bitrix

---

## 7. Развёртывание

### 7.1. Dockerfile

`deploy/Dockerfile.telemost_recorder_api`:
- Python 3.11-slim
- Зависимости: fastapi, uvicorn, asyncpg, docker, httpx, pyyaml
- Не нужны Playwright/Chromium/Xvfb (это только в `Dockerfile.telemost_recorder`)
- Запуск: `uvicorn services.telemost_recorder_api.app:create_app --host 0.0.0.0 --port 8006 --factory`

### 7.2. docker-compose service

```yaml
telemost-recorder-api:
  build:
    context: ..
    dockerfile: deploy/Dockerfile.telemost_recorder_api
  container_name: telemost_recorder_api
  restart: unless-stopped
  env_file: [../.env]
  environment:
    - PYTHONUNBUFFERED=1
    - TZ=Europe/Moscow
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ../data/telemost:/app/data/telemost
  networks: [n8n-docker-caddy_default]
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8006/health"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 30s
  deploy:
    resources:
      limits: {cpus: '1.0', memory: 1024M}
      reservations: {cpus: '0.5', memory: 512M}
```

### 7.3. Caddy

Внешний домен для Telegram webhook (Telegram требует HTTPS):
```
recorder.os.wookiee.shop {
    reverse_proxy telemost_recorder_api:8006
}
```

### 7.4. Cron в wookiee-cron

```
0 4 * * *  cd /app && python scripts/telemost_audio_cleanup.py >> /proc/1/fd/1 2>&1
```

### 7.5. Capacity check

**Перед стартом:** `ssh timeweb "free -h"`. Recorder-контейнеры по 1.5GB RAM каждый, max 5 параллельных = 7.5GB пиково. Если памяти мало — лимит параллельности до 2-3 в config.

---

## 8. Privacy & Security

- **Bot avatar:** `Wookiee Recorder` с распознаваемой иконкой (загрузим через Telegram setMyPhoto при первом запуске)
- **Opt-out:** события с `[no-record]` или `🚫` в названии — пропускаем
- **Audio TTL:** 30 дней, daily cleanup-cron удаляет из Storage + обнуляет `audio_path`
- **Транскрипт TTL:** бессрочно (текст занимает мало места, ценность высокая)
- **RLS на `telemost.*`** — `anon` заблокирован, доступ только service-role
- **Telegram webhook secret** — валидация `X-Telegram-Bot-Api-Secret-Token` header
- **Secrets в `.env`** — `TELEMOST_BOT_TOKEN`, `TELEGRAM_MANAGER_BOT_TOKEN`, `OPENROUTER_API_KEY`, `SPEECHKIT_API_KEY`, `BITRIX24_WEBHOOK_URL`, `SUPABASE_*` (всё уже есть)

---

## 9. Failure modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Recording упал mid-meeting | exit code != 0 | Mark `failed`, error в `error` поле, нотификация триггерщику |
| LLM postprocess timeout/error | exception в task | Retry 3x с экспоненциальным backoff; если все провалились — mark `failed`, raw transcript остаётся |
| Bitrix API down во время poll | request error | Skip cycle, log, retry next 60s |
| Telegram webhook receive error | HTTP error в bot | Telegram сам ретраит ~24h |
| API service crash | container exit | docker-compose `restart: unless-stopped` |
| Recorder-контейнер orphaned (API упал, контейнер живой) | startup recovery | При старте API сервис ищет контейнеры с label `telemost.meeting_id` без активной задачи в очереди → реконсилирует |
| SpeechKit квота кончилась | response error | Mark `failed`, нотификация admin (TELEGRAM_ALERTS_BOT) |

---

## 10. Тесты

Покрытие критическим:
- `test_telegram_routes.py` — auth по telegram_id, парсинг команд, валидация webhook secret
- `test_calendar_poller.py` — дедуп по URL, +5 минут окно, skip [no-record]
- `test_postprocess.py` — JSON schema валидация, fallback на пустые секции
- `test_user_sync.py` — Bitrix → telemost.users (включая deactivate)
- `test_dictionary.py` — сборка из 3 источников + кэш
- `test_recorder_worker.py` — atomic pick (FOR UPDATE SKIP LOCKED), exit handling

Не тестируем:
- Recorder-контейнер изнутри (он уже протестирован в `tests/services/telemost_recorder/`)
- LLM-выход на реальном API (mock OpenRouter response)

---

## 11. Phasing

**Phase 0 — Telegram-only MVP (1 день):**
- Migration `telemost.users`, `telemost.meetings`
- FastAPI-сервис с `/telegram/webhook` + `/health`
- Команды `/record`, `/status`, `/list`, `/help`
- Auth-синк из Bitrix (раз в день + при старте)
- Worker-loop (1 параллельная запись)
- LLM-постпроцессор single-call
- Telegram DM триггерщику со summary
- Аватарка для бота
- **Acceptance:** `/record <url>` → через ~50 минут DM с summary

**Phase 1 — Calendar auto + multi-user (2 дня):**
- Bitrix calendar poller (60s)
- Дедуп по URL (через `processed_calendar_events`)
- Распределение DM всем инвайтам с telegram_id
- Opt-out маркер
- Audio retention cron
- Параллельность до 5 (с проверкой capacity)
- **Acceptance:** ставишь встречу в Bitrix → через 60s в очереди → после встречи DM всем

**Phase 2 — Notion + Wookiee dictionary (1 день):**
- Wookiee dictionary fetcher (Supabase product matrix + Bitrix users + YAML)
- Notion-публикация в существующую DB «Записи встреч» (вариант C — расширенные свойства)
- **Acceptance:** Notion-страница с summary, тегами, участниками; словарь правильно нормализует «вэнди»→Венди

**Phase 3 — Полировка (по запросу):**
- `/extract_tasks` команда → Bitrix REST
- Pyannote-диаризация если LLM-спикеры недостаточны
- WebUI поиск

---

## 12. Cost estimate

Per meeting (60 минут):
- SpeechKit: 16.6 ₽
- LLM postprocess (Gemini Flash): ~$0.01 ≈ 1 ₽
- Storage: pro-rata ~0.13 ₽/месяц/встреча

100 встреч/месяц: **~1.8 K ₽/мес.**

---

## 13. Open questions resolved

| Question | Decision |
|----------|----------|
| Trigger source | Hybrid: Bitrix calendar polling + Telegram bot |
| Notion in scope? | Phase 2, не блокирует Phase 0/1 |
| Distribution | Telegram-триггер → триггерщику; Calendar-триггер → инвайтам с telegram_id |
| Dictionary source | Hybrid B+YAML: Bitrix users + Supabase product matrix + YAML jargon |
| Bot strategy | Managed Bot via Bati Bot (created: `@wookiee_recorder_bot`, id 8692087684) |
| Where to deploy | docker-compose service `telemost-recorder-api` на timeweb |
| Privacy mode | Always record + visible bot + opt-out marker `[no-record]`/🚫 |
| Audio retention | 30 days, transcript бессрочно |
| Phasing | Phase 0 (Telegram-only) → Phase 1 (Calendar) → Phase 2 (Notion) → Phase 3 (polish) |

---

## 14. References

- Existing recorder: [services/telemost_recorder/](../../../services/telemost_recorder/)
- Speakers resolution (LLM + Bitrix): [services/telemost_recorder/speakers.py](../../../services/telemost_recorder/speakers.py)
- Notion DB pattern (для Phase 2): [scripts/transcribe_meetings.py](../../../scripts/transcribe_meetings.py) (DB id `34e58a2bd58780ed9d48ed21a5ac6b94`)
- OpenRouter wrapper: [shared/clients/openrouter_client.py](../../../shared/clients/openrouter_client.py)
- Supabase connection: [shared/data_layer/_connection.py](../../../shared/data_layer/_connection.py)
- FastAPI patterns: [services/wb_logistics_api/app.py](../../../services/wb_logistics_api/app.py), [services/influencer_crm/app.py](../../../services/influencer_crm/app.py)
- Bitrix calendar example: [modules/bitrix-analytics/fetch_data.py](../../../modules/bitrix-analytics/fetch_data.py)
- Telegram Managed Bots API: https://core.telegram.org/bots/api
