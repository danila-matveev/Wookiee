# Telemost Recorder — план укрепления (hardening)

**Дата:** 2026-05-13
**Контекст:** глубокий аудит всего стека (recorder контейнер + FastAPI + воркеры + внешние API + Telegram бот). Нашли 30 рисков, 7 критичных уже починены коммитами `f4ee16f` и `e45e06c`. Этот документ описывает что осталось и в каком порядке чинить.

## Что уже сделано

| ID | Что | Коммит |
|----|-----|--------|
| W1 | `transcribe_audio()` → `await transcribe_audio_async()` в `join.py` (был asyncio.run в running loop, транскрипция вообще не работала) | f4ee16f |
| W2 | Пустые записи без кнопок «Транскрипт / Сводка / Notion» — UX чистый | f4ee16f |
| W3 | Webhook auto-restore в startup lifespan + `TELEMOST_PUBLIC_URL` env | e45e06c |
| W4 | `_supervised(name, coro)` обёртка над воркерами — рестарт через 5 сек если loop умер целиком | e45e06c |
| W5 | OpenRouter retry 3x на 429/5xx с экспоненциальным backoff | e45e06c |
| W6 | Notion retry 4x с уважением `Retry-After` | e45e06c |
| W7 | Bitrix retry 3x на 5xx/429/network (4xx не ретраим) | e45e06c |
| W8 | `TelegramAPIError.error_code` + warning на 403/400 в notifier | e45e06c |
| W9 | Recorder transcript-lost (audio есть, raw_segments нет) → meeting failed с понятной ошибкой, не маскируется под «тишину» | e45e06c |

## Принцип приоритезации

- **Фаза 1 (CRITICAL):** ломает пользовательский путь или приводит к потере данных. Делать сейчас.
- **Фаза 2 (HIGH):** edge case, который точно встретится за месяц использования. Делать на этой неделе.
- **Фаза 3 (MEDIUM):** UX и устойчивость к редким сбоям. Делать когда будет час свободного времени.
- **Фаза 4 (LOW):** polish и эксплуатация. Делать когда сервис будет в проде у команды.

---

## Фаза 1 — CRITICAL (доделать сегодня-завтра)

### 1.1 Notion re-export не должен убивать страницу при сбое

**Где:** `services/telemost_recorder_api/notion_export.py:308-365`
**Проблема:** при повторном экспорте сначала `_delete_existing_children()` удаляет ВСЕ блоки страницы, потом `_append_blocks_paginated()` добавляет новые. Если второй шаг упал (например, network drop на середине, или 4xx из-за невалидного блока) — страница остаётся **пустой**, флаг `notion_page_id` уже стоит, повторный re-export не делает ничего нового.
**Как чинить:**
- Поменять порядок: сначала добавить новые блоки в конец страницы, потом удалить старые. Если упало посередине — у юзера будет дубль контента (не критично), но не пустая страница.
- Альтернатива: складывать новые блоки во временный список, удалять старые только после успешного создания. Но Notion API не даёт «черновика», так что первый вариант проще.
**Файлы:** `notion_export.py`, добавить тест в `tests/services/telemost_recorder_api/test_notion_export.py`.
**Оценка:** 30 минут.

### 1.2 Race condition: двойной webhook от Telegram на одну ссылку

**Где:** `services/telemost_recorder_api/handlers/record.py:91-93`
**Проблема:** `ON CONFLICT (meeting_url) WHERE status IN ('queued','recording','postprocessing') DO NOTHING` — partial unique index. Но если **два webhook** от Telegram прилетят за миллисекунды (Telegram повторяет на 5xx), оба пройдут `INSERT ... ON CONFLICT DO NOTHING` если строки ещё нет. Возможна гонка — два запуска recorder для одной встречи.
**Как чинить:**
- Использовать `INSERT ... RETURNING id` и проверять — если `id` None, значит уже есть. Это уже сделано.
- Но проблема в том, что **partial index** не блокирует одновременную вставку двух строк с разным `id` если ни одна ещё не зафиксировалась.
- Решение: добавить `pg_advisory_xact_lock(hashtext(meeting_url))` в транзакции перед INSERT.
**Файлы:** `handlers/record.py`, тест в `test_handlers_record.py`.
**Оценка:** 20 минут.

### 1.3 docker.sock недоступен — фейл должен быть громким

**Где:** `services/telemost_recorder_api/docker_client.py:26-31`
**Проблема:** `docker.from_env()` ленится, падает только при первом spawn. API стартует «здоровым», но при первом запросе recorder получает 500.
**Как чинить:**
- В `lifespan` startup сделать smoke check: `docker.from_env().ping()`. Если падает — log.critical и продолжать (worker сам потом упадёт и перезапустится через supervised).
- Альтернатива: пометить в health-check, что docker недоступен (даст оператору видимость).
**Файлы:** `app.py`, `docker_client.py`.
**Оценка:** 15 минут.

### 1.4 URL валидация: проверять, что встреча реально существует

**Где:** `services/telemost_recorder_api/handlers/record.py:74-99`
**Проблема:** проверяется только паттерн URL, но не что встреча реально живая. Юзер может отправить `https://telemost.yandex.ru/j/abc123` (выдуманный код) — бот примет, recorder запустится, 30 сек подождёт и упадёт с «MEETING_NOT_FOUND». UX отстой.
**Как чинить:**
- В `handlers/record.py` после валидации паттерна — сделать HEAD/GET на URL встречи. Если 404 — сразу сказать юзеру «Встреча не найдена, проверь ссылку».
- Telemost отвечает 200 даже для битых ссылок (это SPA), поэтому HEAD не поможет. Альтернатива: проверить только, что путь содержит валидную форму id (`/j/[0-9]{10,}` или подобное).
- На самом деле проще: оставить как есть, но recorder должен через 10-15 сек (а не 30) понять «встреча не найдена» и эмитить понятную ошибку.
**Файлы:** `handlers/record.py` или `services/telemost_recorder/join.py:_wait_for_known_state`.
**Оценка:** 30 минут.

---

## Фаза 2 — HIGH (на этой неделе)

### 2.1 Глобальный httpx.AsyncClient для Telegram

**Где:** `services/telemost_recorder_api/telegram_client.py:26-34`
**Проблема:** каждый `tg_call()` создаёт свой `AsyncClient`. При активной работе это десятки коротких TCP-соединений в минуту. Может исчерпать локальные порты или порты исходящего firewall.
**Как чинить:** singleton `AsyncClient` инициализируется в lifespan, закрывается в shutdown. Все методы используют его.
**Файлы:** `telegram_client.py`, `app.py`.
**Оценка:** 30 минут.

### 2.2 Унифицировать таймауты во внешних API

**Где:** `telegram_client.py:29` (30 сек), `:97` (60 сек), `bitrix_calendar.py:21` (15 сек), `notion_export.py:32` (30 сек), `audio_uploader.py` (?)
**Проблема:** разные таймауты на разных вызовах непредсказуемы. Юзер ждёт «загрузку транскрипта» — а sendDocument с timeout=60 может сидеть минуту впустую.
**Как чинить:** вынести в `config.py` константы `*_TIMEOUT_SECONDS`, согласовать (Telegram 60, Notion 30, Bitrix 15, audio 120).
**Файлы:** `config.py` + все http client'ы.
**Оценка:** 20 минут.

### 2.3 PulseAudio capture.stop() может зависнуть

**Где:** `services/telemost_recorder/audio.py:48-102` (примерно)
**Проблема:** если pulseaudio упал между `start()` и `stop()`, `ffmpeg` ждёт source бесконечно, `capture.stop()` блокируется. recorder контейнер висит до hard limit (4 часа).
**Как чинить:**
- `capture.stop()` обернуть в `asyncio.wait_for(timeout=10)` (или вообще `signal.alarm(10)` для sync).
- Если timeout — kill ffmpeg `-9`, продолжить с тем что было.
**Файлы:** `services/telemost_recorder/audio.py`, тест.
**Оценка:** 40 минут.

### 2.4 Bitrix enrichment fire-and-forget — нужны алёрты

**Где:** `handlers/record.py:133-140`
**Проблема:** если `enrich_meeting_from_bitrix()` упал (сеть, токен), `triggered_by` юзер этого не увидит — встреча просто будет с пустым `title`. Это маскирует развалившийся Bitrix-интеграл.
**Как чинить:** обернуть в try/except, в случае ошибки — log + telegram alert через `error_alerts`.
**Файлы:** `handlers/record.py`.
**Оценка:** 10 минут.

### 2.5 Long-meeting safety (>1ч): chunked transcription + pulseaudio

**Где:** `services/telemost_recorder/transcribe.py` + `audio.py`
**Проблема:** PulseAudio + ffmpeg тестировались на 2-минутных встречах. На 2-часовой могут быть memory leaks в null-sink или ffmpeg muxer (накапливается timestamps). ASR chunking разбивает на 25-сек чанки, на 1 час = 144 чанка, semaphore=8 → ~18 параллельных HTTP. Может упереться в OpenRouter rate-limit (TPM/RPM).
**Как чинить:**
- Добавить ffmpeg `-segment_format opus -segment_time 600 -segment_atclocktime 1` чтобы писать в 10-минутные сегменты (восстановление в случае краша).
- В `_split_into_chunks_async` добавить мониторинг disk space перед split (если меньше 1GB — abort).
- SpeechKit rate limit: задокументировать (Yandex даёт ~50 RPS, мы делаем 8 параллельно по 25 сек = безопасно).
**Файлы:** `audio.py`, `transcribe.py`, доку.
**Оценка:** 1 час.

### 2.6 Bitrix datetime parsing — таймзона

**Где:** `bitrix_calendar.py:46-59`
**Проблема:** парсится `"13.05.2026 08:30:00"` без явной TZ, помечается `tzinfo=timezone.utc`. На самом деле Bitrix возвращает в TZ кабинета (Europe/Moscow), а мы лжём что это UTC. Сравниваем с `datetime.now(timezone.utc)` — получаем смещение на 3 часа. `_pick_closest_meeting` может выбрать не ту встречу.
**Как чинить:** парсить с явной `ZoneInfo("Europe/Moscow")` (или брать из env). Конвертировать в UTC перед сравнением.
**Файлы:** `bitrix_calendar.py`, тест.
**Оценка:** 20 минут.

### 2.7 audio_uploader без retry на Supabase

**Где:** `audio_uploader.py:28-77`
**Проблема:** если Supabase Storage кратковременно недоступен, upload упадёт, meeting перейдёт в postprocessing без `audio_path`. Аудио теряется (есть локально, но юзер не увидит ссылки).
**Как чинить:** retry 3x с backoff аналогично OpenRouter.
**Файлы:** `audio_uploader.py`.
**Оценка:** 15 минут.

---

## Фаза 3 — MEDIUM (когда час есть)

### 3.1 Disk space rotation для audio.opus

**Где:** `data/telemost/<meeting_id>/audio.opus`
**Проблема:** аудиофайлы локально не удаляются. Через месяцы накопится 10+ GB.
**Как чинить:** cron-задача (или встроенный worker) удаляющая папки старше `AUDIO_RETENTION_DAYS` (уже есть в config). Supabase Storage уже даёт TTL через signed URL.
**Файлы:** новый воркер `cleanup_worker.py` или systemd-timer на сервере.
**Оценка:** 30 минут.

### 3.2 db.py pool init — double-check после lock

**Где:** `services/telemost_recorder_api/db.py:26-38`
**Проблема:** при concurrent старте двух tasks (recorder + postprocess) оба могут попытаться создать pool одновременно. Asyncpg создаст два, утечка.
**Как чинить:** `asyncio.Lock()` + double-check pattern.
**Файлы:** `db.py`, тест.
**Оценка:** 20 минут.

### 3.3 Empty meeting recovery: кнопка «удалить» / «переотправить»

**Где:** `notifier.py`
**Проблема:** на пустой записи кнопки убрали (W2), но юзер может захотеть удалить запись из БД совсем. Сейчас она там висит вечно.
**Как чинить:** для empty оставить только кнопку «🗑 Удалить» (без транскрипта/Notion).
**Файлы:** `notifier.py`, `keyboards.py`.
**Оценка:** 15 минут.

### 3.4 Notify operator about bot-blocked users

**Где:** `notifier.py`
**Проблема:** если юзер заблокировал бота, мы тихо логируем warning. Оператор не видит, что юзер «отвалился».
**Как чинить:** через `error_alerts.send_alert(...)` оповещать админ-чат раз в день (агрегация).
**Файлы:** `notifier.py`, `error_alerts.py`.
**Оценка:** 30 минут.

### 3.5 detect_meeting_ended — больше сигналов, меньше false-positives

**Где:** `services/telemost_recorder/join.py:233-277`
**Проблема:** сейчас полагаемся на: (а) URL не содержит `/j/`, (б) текст-маркер «Встреча завершена», (в) badge_count ≤ 1. Если Telemost UI поменяется, может застрять.
**Как чинить:**
- Добавить мониторинг audio levels: если 10 минут полная тишина при badge_count > 1 — выйти.
- Логировать html-snapshot при выходе (для отладки).
**Файлы:** `join.py`, `audio.py` (level monitor).
**Оценка:** 1.5 часа.

### 3.6 Playwright локаторы — таймауты на каждом

**Где:** `services/telemost_recorder/join.py` весь файл
**Проблема:** `page.goto()` имеет timeout, но `page.locator(...).is_visible()` без — может застрять если селектор сломан.
**Как чинить:** глобальный default timeout через `page.set_default_timeout(5000)`. Уже может быть, проверить.
**Файлы:** `join.py`.
**Оценка:** 15 минут.

### 3.7 LLM chunking: не скрывать failure под empty paragraphs

**Где:** `llm_postprocess.py:337-380`
**Проблема:** при `LLM (paragraphs chunk) failed, falling back to empty paragraphs` — юзер получает summary, но без transcript. Это странно, лучше открыто сказать.
**Как чинить:** если paragraphs пустой а summary полный — добавить в summary поле `partial: true`, notifier допишет «⚠ Транскрипт восстановить не удалось, есть только итоги».
**Файлы:** `llm_postprocess.py`, `notifier.py`.
**Оценка:** 30 минут.

---

## Фаза 4 — LOW (polish)

### 4.1 requirements.txt — зафиксировать минимальные версии

**Где:** `services/telemost_recorder/requirements.txt`, `services/telemost_recorder_api/requirements.txt`
**Проблема:** `httpx>=0.27` — слишком мягко, мажорное обновление может сломать.
**Как чинить:** добавить верхний предел: `httpx>=0.27,<0.30`. Аналогично для остальных.
**Оценка:** 10 минут.

### 4.2 Database schema validation на старте

**Проблема:** код селектит `notion_page_id`, `notion_page_url` — если миграция не накатилась на новый инстанс, упадёт при первом запросе.
**Как чинить:** в lifespan startup сделать `SELECT column_name FROM information_schema.columns WHERE table_schema='telemost'` и проверить ожидаемые поля.
**Оценка:** 30 минут.

### 4.3 meeting_id в каждом log statement

**Проблема:** в логах часто `logger.exception("Failed to send")` без meeting_id — дебажить тяжело.
**Как чинить:** structured logging через `extra={"meeting_id": ...}` или хотя бы в format string везде.
**Оценка:** 1 час, много мелких правок.

### 4.4 Smoke tests как cron

**Проблема:** только узнаём что webhook слетел, когда юзер пишет.
**Как чинить:** скрипт раз в 10 минут: `getWebhookInfo()`, проверка url. Если не наш — алёрт.
**Файлы:** новый cron-job на сервере.
**Оценка:** 30 минут.

### 4.5 Long pre-validation feedback

**Проблема:** юзер кидает ссылку, ждёт 5-15 сек до «Принял ссылку». Если за это время передумал — не отменить.
**Как чинить:** мгновенный ack «Получил, проверяю...» (≤500мс), потом «Принял» с деталями.
**Оценка:** 20 минут.

---

## Порядок исполнения

**Сегодня (если время есть):** Фаза 1 целиком (1.1 → 1.2 → 1.3 → 1.4). Это ~1.5 часа кода + час тестов и деплой.

**Эта неделя:** Фаза 2 — 7 пунктов, ~3-4 часа.

**Когда сервис закрепится у команды (2-3 человека пользуются):** Фазы 3 и 4 как тех-долг.

---

## Acceptance criteria для каждой фазы

**Фаза 1 готова, когда:**
- Notion re-export повторно: страница не пустеет даже при искусственном падении PATCH (тест есть).
- Симуляция двойного webhook (parallel POST) не создаёт два recorder контейнера (тест есть).
- API падает на старте если docker.sock недоступен (или логирует critical).
- Невалидный URL отбивается за ≤15 сек, юзер видит понятную ошибку.

**Фаза 2 готова, когда:**
- `lsof | grep ESTABLISHED` показывает не больше 3 long-lived соединений к api.telegram.org (singleton client).
- 2-часовая запись проходит без OOM (тест на staging).
- Запись с упавшей Supabase делает retry и в логах видны 3 попытки.
- Bitrix события в Moscow TZ выбираются правильно (тест с фиксированными датами).

**Фаза 3 готова, когда:**
- `data/telemost/` не растёт безгранично.
- При перезагрузке API нет утечки connection pool'ов.
- Empty meeting в Telegram имеет кнопку «Удалить».

**Фаза 4 — когда полностью документировано в `services/telemost_recorder/README.md`.**

---

## Что НЕ делаем (out of scope)

- Multi-tenancy (разные команды на одном инстансе) — не нужно.
- Параллельная запись больше 3 встреч одновременно — `MAX_PARALLEL_RECORDINGS=3` достаточно.
- Поддержка не-Telemost (Zoom, GMeet) — отдельный проект.
- UI на сайте для просмотра записей — пока всё через Telegram + Notion.
