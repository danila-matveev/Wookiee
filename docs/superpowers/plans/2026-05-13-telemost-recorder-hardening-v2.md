# Telemost Recorder — план укрепления v2 (orchestrate-ready)

**Дата:** 2026-05-13
**Версия:** v2 — переписана после самокритики v1, для автономного исполнения через subagent-driven-development orchestrator.

## Правила исполнения для оркестратора

1. **Атомарность.** Каждая задача = один коммит. Если задача провалена — `git reset HEAD~1` и переходим к следующей с пометкой `SKIPPED`.
2. **TDD.** Сначала тесты (которые падают), потом код (тесты проходят), потом review.
3. **Никаких регрессий.** После каждой задачи прогон `pytest tests/services/telemost_recorder/ tests/services/telemost_recorder_api/ --ignore=tests/services/telemost_recorder_api/test_recorder_worker.py --ignore=tests/services/telemost_recorder_api/test_telegram_routes.py --ignore=tests/services/telemost_recorder_api/test_health.py --ignore=tests/services/telemost_recorder_api/test_docker_client.py --ignore=tests/services/telemost_recorder/test_url_validation.py --ignore=tests/services/telemost_recorder/test_participants_filter.py --ignore=tests/services/telemost_recorder/test_state_detection.py --ignore=tests/services/telemost_recorder/test_cli_args.py` (исключения из-за Python 3.9 на хосте; на сервере 3.11 — всё запустится).
4. **Деплой после каждой фазы.** Pull → rebuild recorder image → rebuild API → smoke test.
5. **Spec-reviewer** проверяет: «реализация делает ровно то, что в задаче, не больше и не меньше».
6. **Code-quality-reviewer** проверяет: type hints, naming, no dead code, no comments-explaining-what (только why).
7. **Rollback:** если после фазы smoke-test упал — `git revert <range>` и пересборка.

## Smoke test — обязательный после каждой фазы

```bash
# 1. API живой
curl -fsS https://recorder.os.wookiee.shop/health

# 2. Webhook зарегистрирован
BOT_TOKEN=$(ssh timeweb 'grep ^TELEGRAM_BOT_TOKEN= /home/danila/projects/wookiee/deploy/.env | cut -d= -f2')
curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq -e '.result.url == "https://recorder.os.wookiee.shop/telegram/webhook"'

# 3. Postprocess worker и recorder worker запущены
ssh timeweb "cd /home/danila/projects/wookiee/deploy && docker compose logs --tail=30 telemost-recorder-api | grep -E '(Recorder worker starting|Postprocess worker starting|Telegram webhook registered)' | wc -l" # >= 3

# 4. Container healthy
ssh timeweb "cd /home/danila/projects/wookiee/deploy && docker compose ps telemost-recorder-api" | grep -c healthy # == 1
```

Если любая команда вернула ошибку — STOP, rollback, debug.

---

## Фаза 1 — CRITICAL

### Task 1.1: Notion re-export — маркер-divider стратегия

**Файл:** `services/telemost_recorder_api/notion_export.py`

**Проблема:** при re-export сначала `_delete_existing_children()` чистит страницу, потом `_append_blocks_paginated()` добавляет новые. Если PATCH добавления упал — страница пустая, флаг `notion_page_id` уже стоит, повторный экспорт ничего не делает.

**Решение:**
1. В начале re-export добавить служебный divider-блок с `text="<<<wookiee-marker-{meeting_id}>>>"`.
2. Добавить новые блоки **после** маркера (через `_append_blocks_paginated`).
3. Только после успешного добавления — удалить все блоки **до и включая маркер** (`_delete_until_marker(page_id, marker_text, token)`).
4. Если шаг 2 упал — следующий re-export видит маркер, удаляет всё до него (включая частично записанное), и пробует снова чистый append.

**Тесты в `tests/services/telemost_recorder_api/test_notion_export.py`:**
- `test_reexport_inserts_marker_before_new_content` — мок Notion API, проверяем что первый PATCH children содержит divider с marker_text.
- `test_reexport_deletes_until_marker_on_success` — после успешного append вызывается DELETE для блоков до маркера включительно.
- `test_reexport_recovers_from_failed_append` — если первый PATCH children упал, второй re-export видит маркер и продолжает (тест с двумя последовательными вызовами, первый падает).
- `test_export_to_new_page_does_not_use_marker` — для новой страницы (без existing_id) маркер не нужен.

**Acceptance:**
- Все 4 теста проходят.
- Существующие тесты `test_notion_export.py` (21 шт) продолжают работать.

**Commit message:** `fix(telemost): идемпотентный Notion re-export через marker-divider`

---

### Task 1.2: Advisory lock на двойной webhook

**Файл:** `services/telemost_recorder_api/handlers/record.py`

**Проблема:** Telegram retries POST на 5xx. Если два webhook'а прилетят за миллисекунды на одну ссылку, оба могут пройти `INSERT ... ON CONFLICT DO NOTHING` и создать две записи в гонке.

**Решение:**
- В транзакции перед INSERT взять `pg_advisory_xact_lock(hashtext($1::text))` где $1 = meeting_url.
- Лок отпускается при COMMIT/ROLLBACK автоматически.
- Второй параллельный webhook ждёт первый, видит существующую строку, выходит.

**Тест в `tests/services/telemost_recorder_api/test_handlers_record.py`:**
- `test_concurrent_record_requests_create_single_meeting` — два `asyncio.gather` вызова `handle_record_command()` с одним URL — должны создать ровно одну запись (проверка count в БД).
- Использовать `asyncpg` test fixture или mock через `monkeypatch`.

**Acceptance:**
- Новый тест проходит.
- Существующий `test_handlers_record.py` продолжает работать.

**Commit message:** `fix(telemost): advisory_xact_lock против двойного webhook на одну ссылку`

---

### Task 1.3: docker.sock health-check

**Файлы:** `services/telemost_recorder_api/docker_client.py`, `services/telemost_recorder_api/routes/health.py`

**Проблема:** `docker.from_env()` ленится. API стартует «здоровым», recorder валится при первом spawn.

**Решение:**
- В `docker_client.py` добавить функцию `async def docker_ping() -> bool` — пытается `client.ping()` с timeout 5 сек.
- В `routes/health.py` расширить ответ: `{"status": "ok", "docker": "ok" | "unhealthy", "db": "ok" | "unhealthy"}`. Если docker или db unhealthy — HTTP 503.
- В `app.py` lifespan startup — вызвать `docker_ping()`, если False — `logger.critical("docker.sock unreachable")` (не блокируем старт).

**Тесты в `tests/services/telemost_recorder_api/test_docker_client.py`:**
- `test_docker_ping_returns_true_when_socket_reachable` — мок `docker.from_env().ping()` → возвращает True.
- `test_docker_ping_returns_false_on_error` — мок выбрасывает `docker.errors.DockerException` → возвращает False.

**Тест в `tests/services/telemost_recorder_api/test_health.py`:**
- `test_health_returns_503_when_docker_unhealthy` — мок `docker_ping → False` → response 503 + `{"docker": "unhealthy"}`.

**Acceptance:**
- 3 новых теста проходят.
- `/health` возвращает 200 в обычной ситуации.

**Commit message:** `feat(telemost): health-check показывает статус docker.sock и БД`

---

### Task 1.4: Recorder — быстрый детект «встреча не найдена»

**Файл:** `services/telemost_recorder/join.py`

**Проблема:** для несуществующей встречи бот ждёт 30 сек таймаут вместо понятной ошибки.

**Решение:**
- В `_wait_for_known_state()` (вокруг строки 92) добавить параллельную проверку селекторов «встреча не найдена» / «meeting not found» / «такой встречи нет».
- Использовать `asyncio.wait(..., return_when=FIRST_COMPLETED)` с двумя задачами: ожидание известного состояния и ожидание not-found текста.
- Если not-found сработал быстрее — emit `{"status": "FAILED", "reason": "MEETING_NOT_FOUND"}` и выйти.
- Таймаут на not-found поиск — 10 сек (вместо общего 30 сек).

**Тест в `tests/services/telemost_recorder/test_state_detection.py`:**
- `test_meeting_not_found_detected_via_text_selector` — мок page.locator на тексте «встреча не найдена» — возвращает MEETING_NOT_FOUND state.

**Acceptance:**
- Новый тест проходит (если коллекция тестов в Python 3.9 — гонять только на сервере через docker exec).
- Ручной smoke: послать боту `https://telemost.yandex.ru/j/0000000000` — получить отказ за ≤15 сек.

**Commit message:** `feat(telemost): быстрый детект 'встреча не найдена' в recorder`

---

## Фаза 2 — HIGH

### Task 2.1: Глобальный httpx.AsyncClient для Telegram

**Файлы:** `services/telemost_recorder_api/telegram_client.py`, `services/telemost_recorder_api/app.py`

**Решение:**
- В `telegram_client.py` добавить module-level `_client: httpx.AsyncClient | None = None` и функции `init_client(timeout)`, `close_client()`, `get_client()`.
- Все `tg_call`, `tg_send_message`, `tg_send_document` используют `get_client()`.
- В `app.py` lifespan: `init_client(timeout=60)` на startup, `close_client()` на shutdown.

**Тесты в `tests/services/telemost_recorder_api/test_telegram_client.py`:**
- `test_get_client_raises_if_not_initialized` — `get_client()` без `init_client()` → RuntimeError.
- `test_tg_call_uses_singleton_client` — после `init_client()`, два `tg_call` используют один и тот же AsyncClient (через `id()` или mock-counter).
- `test_close_client_idempotent` — двойной вызов `close_client()` не падает.

**Commit message:** `refactor(telemost): singleton httpx.AsyncClient для Telegram`

---

### Task 2.2: Унифицированные таймауты в config

**Файл:** `services/telemost_recorder_api/config.py` + использование во всех http-клиентах.

**Решение:**
- Добавить в `config.py`:
  ```python
  TELEGRAM_TIMEOUT_SECONDS: int = int(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "60"))
  NOTION_TIMEOUT_SECONDS: int = int(os.getenv("NOTION_TIMEOUT_SECONDS", "30"))
  BITRIX_TIMEOUT_SECONDS: int = int(os.getenv("BITRIX_TIMEOUT_SECONDS", "15"))
  SUPABASE_STORAGE_TIMEOUT_SECONDS: int = int(os.getenv("SUPABASE_STORAGE_TIMEOUT_SECONDS", "120"))
  ```
- Заменить hardcoded `timeout=30/60/15` в `telegram_client.py`, `notion_export.py`, `bitrix_calendar.py`, `audio_uploader.py` на эти константы.

**Тест:**
- `test_config_exposes_timeouts` — простой импорт + проверка дефолтов в `tests/services/telemost_recorder_api/test_config.py`.

**Commit message:** `refactor(telemost): конфигурируемые таймауты для всех внешних API`

---

### Task 2.3: capture.stop() с timeout

**Файл:** `services/telemost_recorder/audio.py`

**Решение:**
- В `AudioCapture.stop()` обернуть ffmpeg termination в `subprocess.communicate(timeout=10)`. Если TimeoutExpired — `proc.kill()` + повтор communicate(timeout=2).
- Логировать как warning если пришлось kill -9.

**Тест в `tests/services/telemost_recorder/test_audio_capture.py` (создать если нет):**
- `test_stop_kills_ffmpeg_after_timeout` — мок subprocess который вечно ждёт; stop() возвращает за <12 сек, вызывает kill.

**Commit message:** `fix(telemost): timeout 10 сек на capture.stop() против зависания ffmpeg`

---

### Task 2.4: Bitrix enrichment — алёрт если упал

**Файл:** `services/telemost_recorder_api/handlers/record.py`

**Решение:**
- Обернуть `enrich_meeting_from_bitrix()` в try/except.
- При ошибке — `logger.exception` + `error_alerts.send_alert("bitrix-enrichment", str(e))`.
- Не блокировать выполнение основного flow (juzер получает запись с пустым title — это не катастрофа).

**Тест в `tests/services/telemost_recorder_api/test_handlers_record.py`:**
- `test_record_handles_bitrix_failure_gracefully` — мок enrich → raises; handler возвращает 200, alert вызван.

**Commit message:** `fix(telemost): Bitrix enrichment failure алёртит и не блокирует запись`

---

### Task 2.5: Bitrix datetime в Moscow TZ

**Файл:** `services/telemost_recorder_api/bitrix_calendar.py`

**Решение:**
- В `_parse_bitrix_date()` парсить с `ZoneInfo("Europe/Moscow")`, потом `.astimezone(timezone.utc)`.
- В `find_event_by_url`, `_pick_closest_meeting` сравнивать UTC-aware с UTC-aware.

**Тесты в `tests/services/telemost_recorder_api/test_bitrix_calendar.py`:**
- `test_parse_bitrix_date_assumes_moscow_tz` — `"13.05.2026 08:30:00"` → datetime в UTC = 05:30 (Moscow -3h).
- `test_pick_closest_uses_moscow_tz` — два события в одном часовом окне выбираются правильно.

**Commit message:** `fix(telemost): Bitrix datetime парсится как Europe/Moscow, не UTC`

---

### Task 2.6: Retry для audio_uploader

**Файл:** `services/telemost_recorder_api/audio_uploader.py`

**Решение:**
- Аналогично OpenRouter retry: 3 попытки на 429/5xx/network с экспоненциальным backoff (1s, 2s, 4s).
- Внешний интерфейс не меняется.

**Тест в `tests/services/telemost_recorder_api/test_audio_uploader.py` (создать если нет):**
- `test_upload_retries_on_5xx` — мок httpx 500 дважды, 200 на третий — успех.
- `test_upload_fails_after_all_retries` — мок всегда 500 — raises.

**Commit message:** `fix(telemost): retry для audio_uploader на Supabase Storage`

---

### Task 2.7: Long-meeting safety — disk check + segment write

**Файл:** `services/telemost_recorder/audio.py` и/или `transcribe.py`

**Решение:**
- В `AudioCapture.start()` перед запуском ffmpeg — проверить свободное место в `output_dir.parent` через `shutil.disk_usage()`. Если меньше 1 GB — log.error + raise.
- В ffmpeg запуске добавить `-f segment -segment_time 600 -reset_timestamps 1 audio_%04d.opus`. На конце записи — concat сегментов в один `audio.opus` через ffmpeg concat demuxer.

**Тесты:**
- `test_audio_capture_aborts_on_low_disk` — мок shutil.disk_usage → 500MB free → raises.

**Commit message:** `feat(telemost): long-meeting safety — disk check + segmented write`

---

## Фаза 3 — MEDIUM

### Task 3.1: Disk rotation для старых записей

**Файл:** новый `services/telemost_recorder_api/workers/cleanup_worker.py`

**Решение:**
- Async worker, тикает раз в час.
- Сканирует `DATA_DIR` (host data dir), для каждой папки `<meeting_id>/`:
  - Если `meeting.created_at + AUDIO_RETENTION_DAYS < now()` — удалить папку через `shutil.rmtree(ignore_errors=True)`.
- В `app.py` добавить третий supervised task.

**Проблема uid mismatch:** recorder контейнер пишет от своего uid, API контейнер от своего. Решение: оба контейнера запускать с `user: 1000:1000` в docker-compose, либо API контейнер запускать как root (текущий дефолт у python:slim).

**Тест в `tests/services/telemost_recorder_api/test_cleanup_worker.py`:**
- `test_cleanup_removes_old_meetings` — фейк tmp dir с папками, БД mock возвращает created_at, проверка что старые удалены.

**Commit message:** `feat(telemost): cleanup_worker — ротация audio файлов после AUDIO_RETENTION_DAYS`

---

### Task 3.2: Empty meeting → кнопка "Удалить"

**Файлы:** `services/telemost_recorder_api/notifier.py`, `services/telemost_recorder_api/keyboards.py`

**Решение:**
- В `keyboards.py` добавить `empty_meeting_actions(short_id) -> dict` — только одна кнопка «🗑 Удалить».
- В `notifier.py` для `is_empty=True` использовать `empty_meeting_actions(...)`.

**Тест:**
- `test_notify_empty_meeting_uses_delete_only_keyboard` — мок meeting с empty=True, проверка reply_markup содержит callback_data вида `delete:*`.

**Commit message:** `feat(telemost): empty meeting → кнопка "Удалить" вместо отсутствия кнопок`

---

### Task 3.3: Bot-blocked агрегированный алёрт

**Файл:** `services/telemost_recorder_api/notifier.py`, новая таблица `telemost.bot_blocked_users` (миграция)

**Решение:**
- При получении 403 от Telegram — записать `(user_id, last_seen)` в `bot_blocked_users` через UPSERT.
- Worker раз в день читает таблицу, шлёт agent alert «N юзеров заблокировали бота: список».

**Решение упрощённое:** просто `error_alerts.send_alert("user-blocked-bot", chat_id)` сразу. Без агрегации. Если шумно — добавим rate limit в `error_alerts` (отдельная задача).

**Commit message:** `feat(telemost): алёрт оператору когда юзер заблокировал бота`

---

### Task 3.4: detect_meeting_ended — audio level monitor

**Файлы:** `services/telemost_recorder/join.py`, `services/telemost_recorder/audio.py`

**Решение:**
- В `AudioCapture` добавить метод `current_rms_db()` — читает последние N миллисекунд из ffmpeg loudnorm filter / pa monitor.
- В `run_session` loop: если `badge_count > 1` но `current_rms_db() < -60dB` в течение 10 минут — выйти как «meeting ended».
- Это устойчивее к UI breakage чем DOM-селекторы.

**Тесты:**
- Сложно мокать, оставить как ручной smoke.

**Commit message:** `feat(telemost): silence-based meeting-end detection`

---

### Task 3.5: Playwright default_timeout

**Файл:** `services/telemost_recorder/join.py`

**Решение:**
- После `await page.goto(...)` добавить `page.set_default_timeout(5000)`.
- Не использовать локальные timeout в `is_visible(timeout=200)` если не нужно.

**Commit message:** `fix(telemost): глобальный default_timeout=5s на Playwright локаторы`

---

### Task 3.6: LLM chunking — `summary.partial=true` если paragraphs не собрались

**Файлы:** `services/telemost_recorder_api/llm_postprocess.py`, `services/telemost_recorder_api/notifier.py`

**Решение:**
- В `postprocess_meeting` если paragraphs chunk упал — установить `result["summary"]["partial"] = True` (а не молча возвращать пустой).
- В `notifier.format_summary_message` если `partial=True` — добавить header «⚠ Транскрипт собрать не удалось, ниже только итоги».

**Тесты:**
- `test_partial_summary_renders_warning` — мок meeting с summary.partial=True → message содержит «⚠».

**Commit message:** `feat(telemost): partial-summary флаг + UX warning когда транскрипт не собрался`

---

## Фаза 4 — LOW

### Task 4.1: Pin версий в requirements

**Файлы:** `services/telemost_recorder/requirements.txt`, `services/telemost_recorder_api/requirements.txt`

**Решение:** `httpx>=0.27,<0.30`, `playwright>=1.45,<2.0`, etc.

**Commit message:** `chore(telemost): зафиксировать верхние границы версий зависимостей`

---

### Task 4.2: Schema validation на startup

**Файл:** `services/telemost_recorder_api/app.py`

**Решение:**
- В lifespan startup SELECT из information_schema columns для `telemost.meetings`, проверить ожидаемый список полей.
- Если поле отсутствует — log.critical + поднять `RuntimeError` (блокируем старт).

**Тест:**
- `test_schema_check_passes_on_complete_schema` — mock pool.fetch → return полный список — не raises.
- `test_schema_check_raises_on_missing_column` — mock возвращает неполный список — raises.

**Commit message:** `feat(telemost): schema validation на startup чтобы поймать missing миграции`

---

### Task 4.3: meeting_id в каждом log statement

**Все воркеры и handlers.**

**Решение:** заменить `logger.info("...")` на `logger.info("[%s] ...", meeting_id, ...)` везде где есть meeting_id в области видимости.

**Тест:** ручная проверка через grep.

**Commit message:** `chore(telemost): meeting_id во всех log statements для отладки`

---

### Task 4.4: Smoke-test cron

**Файл:** новый `scripts/telemost_smoke.py` + cron на сервере.

**Решение:**
- Скрипт `getWebhookInfo()`. Если url пустой или не наш — alert.
- cron: `*/10 * * * * python /home/danila/projects/wookiee/scripts/telemost_smoke.py`.

**Commit message:** `feat(telemost): smoke-test cron каждые 10 минут — алёрт при сломанном webhook`

---

### Task 4.5: Мгновенный ack

**Файл:** `services/telemost_recorder_api/handlers/record.py`

**Решение:**
- На webhook сразу `tg_send_message(triggered_by, "⏳ Получил, проверяю...")`.
- Через 1-3 сек (после Bitrix enrichment) — отдельным сообщением полное «✅ Принял ссылку, иду на встречу».

**Тест:**
- `test_record_sends_immediate_ack_before_enrichment` — мок Bitrix медленный (delay 2s), проверка что первый sendMessage вызван за <500ms.

**Commit message:** `feat(telemost): мгновенный ack перед Bitrix enrichment для UX`

---

## Acceptance criteria по фазам (executable)

### Фаза 1 готова, когда:
- `git log --oneline main..HEAD` показывает 4 коммита.
- `pytest tests/services/telemost_recorder_api/test_notion_export.py tests/services/telemost_recorder_api/test_handlers_record.py tests/services/telemost_recorder_api/test_docker_client.py tests/services/telemost_recorder_api/test_health.py -v` — все зелёные.
- Smoke test (выше) проходит после деплоя.
- Ручной тест: послать `https://telemost.yandex.ru/j/0000000000` боту → отказ за ≤15 сек с понятной причиной.

### Фаза 2 готова, когда:
- 7 коммитов после фазы 1.
- Все new тесты проходят.
- `lsof -p $(docker inspect telemost_recorder_api -f '{{.State.Pid}}') | grep ESTABLISHED | grep telegram | wc -l` ≤ 3 (singleton client).
- Smoke test проходит.

### Фаза 3 готова, когда:
- 6 коммитов после фазы 2.
- Cleanup worker удаляет тестовую папку старше retention.
- Empty meeting в Telegram имеет кнопку «🗑 Удалить».
- Smoke test проходит.

### Фаза 4 готова, когда:
- 5 коммитов после фазы 3.
- `requirements.txt` имеет `<X.Y` ограничения.
- Smoke-cron на сервере зарегистрирован.
- Schema check срабатывает (тест prove).
- Smoke test проходит.

---

## Rollback стратегия

После каждой фазы:
1. Тег `git tag phase-{N}-pre` ставится **перед** началом фазы.
2. После всех коммитов фазы — тег `phase-{N}-done`.
3. Если smoke-test упал — `git reset --hard phase-{N}-pre`, force push, передеплой.

## Что НЕ делаем

- 3.2 (pool double-check) выкинут как несуществующая проблема (asyncpg уже thread-safe в singleton).
- Любая optimизация query без замеров.
- UI на сайте для записей.
- Поддержка не-Telemost.
