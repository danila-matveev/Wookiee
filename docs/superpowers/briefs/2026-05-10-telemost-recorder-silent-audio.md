# Telemost Recorder — записывает тишину вместо WebRTC-аудио

**Дата:** 2026-05-10
**Статус:** UX работает, бот заходит во встречу, но `audio.opus` всегда тишина → 0 segments → "тишина" в DM. Воспроизводится 100%.
**Тестовая ссылка:** `https://telemost.360.yandex.ru/j/5655083346` (можно заходить, открывать заново — пользователь подтвердил)
**Ветка:** работаем на `main`. Сервер автодеплоит API через `git pull` каждые 5 минут (cron `deploy` user); recorder-образ собирается вручную (см. ниже).

---

## TL;DR проблемы

Пользователь шлёт боту `@wookiee_recorder_bot` ссылку Я.Телемоста → бот ставит запись в очередь → API спавнит docker-контейнер `telemost_recorder:latest` через docker.sock → recorder заходит во встречу через Playwright + Chromium, делает screenshot'ы (видно 5 минут активности) → но `audio.opus` финальный = ~20-66 КБ за 2-5 минут (Opus DTX-тишина) → ASR (SpeechKit) находит 0 сегментов → notifier шлёт `"Запись завершена, речь не была распознана (тишина)"`.

**4 теста подряд** (last container `fae236f6c423`, meeting `eb010e40-98f1-4a7c-bf45-97c87ad37a50`) — одинаковый результат.

---

## Архитектура

**Сервер:** Timeweb Cloud `77.233.212.61`, ssh alias `timeweb`. Репо `/home/danila/projects/wookiee`. Деплой: `cd deploy && docker compose up -d --build telemost-recorder-api`.

**Два docker-образа:**
1. `deploy-telemost-recorder-api:latest` — FastAPI service (port 8006, за Caddy на `recorder.os.wookiee.shop`). Принимает webhook от Telegram, держит две worker-таски (`recorder_loop` + `postprocess_loop`), спавнит контейнеры recorder через docker.sock.
2. `telemost_recorder:latest` — Playwright + Chromium + Xvfb + PulseAudio + ffmpeg + SpeechKit. Спавнится API на каждую встречу командой `python scripts/telemost_record.py join <url> --meeting-id <id> --output-dir /app/data/telemost/<id>`. Образ собирается **вручную** командой `cd /home/danila/projects/wookiee && docker build -f deploy/Dockerfile.telemost_recorder -t telemost_recorder:latest .` (не в compose). Текущий tag latest содержит фикс `TELEMOST_HEADLESS=false` (commit `8033c4c`).

**База:** Supabase project `gjvwcdtfglupewcwzfhw`, schema `telemost`, таблицы `users` (12 синхронизированы из Bitrix24) + `meetings` (queue с FOR UPDATE SKIP LOCKED).

**Telegram bot:** `@wookiee_recorder_bot`, токен в `.env` (`TELEMOST_BOT_TOKEN`), webhook на `https://recorder.os.wookiee.shop/telegram/webhook`.

---

## Что точно РАБОТАЕТ

- Webhook + dispatch + handlers (UX redesigned, inline keyboards, callback_query routing — 99/99 unit tests pass)
- API спавнит recorder контейнер с правильными CLI args (после ребилда recorder-образа сегодня)
- Recorder открывает Chromium → заходит во встречу → видит UI (10 screenshot'ов с правильным контентом за 5 мин)
- Recorder корректно завершается (MEETING_ENDED_DETECTED → TRANSCRIBING → DONE)
- API спавнит postprocess worker → notifier шлёт DM с результатом
- ASR (SpeechKit) корректно работает на ненулевом аудио (тестировано раньше Phase 0)

---

## Что СЛОМАНО — детально

**Аудиофайл `audio.opus` пустой по содержимому.**
Метаданные ffmpeg-выхлопа (через `ffprobe`):
```
sample_rate=48000
channels=1
duration=293.253354   <- ffmpeg реально писал 5 минут
bit_rate=N/A          <- Opus VBR с DTX (silence detection) сжимает тишину почти в ноль
```
Размер: 66 КБ за 5 мин = ~1.7 Kbit/s — это Opus-сжатая чистая тишина.

ffmpeg-команда (см. `services/telemost_recorder/audio.py:62-71`):
```
ffmpeg -y -f pulse -i telemost_<id8>.monitor -c:a libopus -b:a 64k -ar 48000 -ac 1 -t 14400 audio.opus
```

---

## КРИТИЧНОЕ — что показали PA-debug логи (commit `fd48647`)

В контейнере `fae236f6c423` (meeting `eb010e40`) добавлено логирование PulseAudio-состояния каждые 30 сек. Ключевая выдержка:

```
PA[after-create-sink] sinks: 1 telemost_eb010e40 module-null-sink.c s16le 2ch 44100Hz IDLE
PA[after-create-sink] sink-inputs: (none)
PA[after-create-sink] clients: 4 protocol-native.c pactl

[после старта Chromium]
PA[reroute-tick] sinks: 1 telemost_eb010e40 module-null-sink.c s16le 2ch 48000Hz RUNNING
PA[reroute-tick] sink-inputs: 0 1 8 protocol-native.c float32le 2ch 44100Hz | 1 1 9 protocol-native.c float32le 2ch 44100Hz
PA[reroute-tick] clients: 6 protocol-native.c ffmpeg | 7 protocol-native.c chrome-headless-shell | 8 protocol-native.c chrome-headless-shell | 9 protocol-native.c chrome-headless-shell | 12 protocol-native.c pactl
```

**3 ключевых факта:**
1. Sink `telemost_eb010e40` есть, статус `RUNNING` (на него льются данные).
2. Sink-inputs от Chromium ЕСТЬ: `0 1 8` и `1 1 9` (формат: `id sink_id client_id`). Sink_id=`1` совпадает с нашим sink — то есть **Chromium уже маршрутизирует на наш sink** (rerouting не нужен).
3. **Но клиент называется `chrome-headless-shell`** — Playwright запустил минималистичный headless-binary, а не полный Chromium.

Это совпадает с известной проблемой: **в `chrome-headless-shell` WebRTC inbound audio (звук другой стороны) не выводится на PulseAudio playback** — sink-inputs создаются как placeholder, но реального audio data в них нет. Sink RUNNING потому что headless-shell держит коннект, но шлёт тишину.

---

## Что я уже попробовал — БЕЗ результата

### Попытка 1: `PULSE_SINK` env override (commit `5f42459`)
Гипотеза: `pactl set-default-sink` не подхватывается Chromium, нужен явный per-client sink override. Добавил `os.environ["PULSE_SINK"] = self._sink_name` в `audio.py` после создания sink + форвард в browser.py launch env.
**Результат:** не помог. Sink-inputs и так уже на нашем sink — проблема не в маршрутизации.

### Попытка 2: `TELEMOST_HEADLESS=false` через Dockerfile ENV (commit `8033c4c`)
Гипотеза: chrome-headless-shell не воспроизводит WebRTC audio → нужно переключить на полный Chromium с Xvfb.
**Изменение:** `ENV TELEMOST_HEADLESS=false` в `deploy/Dockerfile.telemost_recorder`.
**ПОЧЕМУ НЕ СРАБОТАЛО (КРИТИЧНО):** API runtime **перезаписывает** Dockerfile ENV при спавне контейнера. См. `services/telemost_recorder_api/docker_client.py:46-86`:
```python
def spawn_recorder_container(
    *,
    meeting_id: UUID,
    meeting_url: str,
    data_dir: str,
    headless: bool = True,        # <-- ДЕФОЛТ TRUE
) -> str:
    ...
    container = client.containers.run(
        ...
        environment={
            "TELEMOST_HEADLESS": "true" if headless else "false",   # <-- ВСЕГДА передаётся, перебивает Dockerfile ENV
            ...
        },
    )
```
И вызов в `services/telemost_recorder_api/workers/recorder_worker.py`:
```python
container_id = await asyncio.to_thread(
    spawn_recorder_container,
    meeting_id=meeting_id,
    meeting_url=pick["meeting_url"],
    # headless НЕ передан → используется default True
)
```
**Итог:** в новом контейнере (с моим ENV TELEMOST_HEADLESS=false) `os.getenv` всё равно вернёт `"true"`, потому что docker run -e перезатёр. Поэтому Chromium снова стартанул как `chrome-headless-shell`.

**ЭТО ПЕРВЫЙ ФИКС, КОТОРЫЙ ДОЛЖЕН СДЕЛАТЬ СУБАГЕНТ:**
- Поменять default `headless: bool = True` → `False` в `docker_client.py:51`
- ИЛИ не передавать `TELEMOST_HEADLESS` в `environment={}` совсем — пусть Dockerfile ENV выигрывает
- ИЛИ явно передать `headless=False` из `recorder_worker.py`

После этого фикса — ребилд API через `docker compose up -d --build telemost-recorder-api` (recorder image НЕ нужен пересобирать, изменения только в API), потом тест.

### Что НЕ пробовал (если #2-фикс не помог сам по себе)

- **Опция `--autoplay-policy=no-user-gesture-required`** в Chromium флагах — бот не делал явного user gesture, может, audio output autoplay блокируется
- **Снять `--use-fake-device-for-media-stream`** — этот флаг подменяет mic input на 440Hz tone, но может также активировать "fake" path для playback. Без него Chromium должен воспроизводить через PulseAudio нормально. Альтернатива: оставить флаг, но дать `--use-file-for-fake-audio-capture=/dev/null`.
- **Включить ffmpeg stderr-лог** — сейчас в `audio.py:73-74` идёт в DEVNULL. Перенаправь в файл `/app/data/telemost/<id>/ffmpeg.log` чтобы увидеть, может быть ffmpeg видит underflow / format mismatch / EOF.
- **Попробовать `parec` вместо `ffmpeg -f pulse`** — `parec --device=<sink>.monitor --record-with-format=...` иногда более стабильный fallback. Но это уже от безысходности.
- **Telemost UI gesture** — возможно бот не нажал «Включить звук» при заходе. В `services/telemost_recorder/join.py:_dismiss_modals` и `_mute_bot` — посмотри что происходит после admission. Если есть кнопка «Подключить аудио» — добавить её клик. Маловероятно (host же не получает алёрт о muted bot), но проверить.

---

## Файлы для входа в код

**Recorder (audio + browser pipeline):**
- `services/telemost_recorder/audio.py` — AudioCapture класс: создаёт null-sink, запускает ffmpeg, имеет PA-debug логгер `_pa_state()`
- `services/telemost_recorder/browser.py` — `launch_browser()` async ctx-mgr: Xvfb + Playwright + env vars
- `services/telemost_recorder/config.py` — `HEADLESS`, `BROWSER_FLAGS`, `AUDIO_BITRATE`, `MAX_RECORDING_MINUTES`, `TELEMOST_CAPTURE`
- `services/telemost_recorder/join.py:430-560` — главный цикл: `capture.start()` → `launch_browser()` → meeting loop с `reroute_streams()` каждые SCREENSHOT_INTERVAL сек
- `scripts/telemost_record.py` — CLI entrypoint, принимает `join <url> --meeting-id <id> --output-dir <dir>`

**API + spawn:**
- `services/telemost_recorder_api/workers/recorder_worker.py:80-130` — спавнит recorder контейнер
- `services/telemost_recorder_api/docker_client.py` — обёртка для docker SDK

**Deploy:**
- `deploy/Dockerfile.telemost_recorder` — содержит сейчас `ENV TELEMOST_HEADLESS=false` (коммит `8033c4c`)
- `deploy/telemost_entrypoint.sh` — `pulseaudio --start --exit-idle-time=-1 --daemon` затем `exec "$@"` (НЕ запускает Xvfb — это делает browser.py при HEADLESS=False)

**Тесты (66 passed, 2 skipped в `tests/services/telemost_recorder/`):**
- `test_state_machine.py`, `test_state_detection.py`, `test_transcribe.py`, `test_speakers.py`, etc. Все НЕ интегрируют PulseAudio/Chromium.

**Память Claude (контекст проекта):**
- `~/.claude/projects/-Users-danilamatveev-Projects-Wookiee/memory/project_telemost_recorder.md`

---

## Как тестировать

**Тестовая ссылка:** `https://telemost.360.yandex.ru/j/5655083346` (юзер сказал — заходи и тестируй сам, не мешай)

**Цикл (5-7 минут):**
1. Открыть Я.Телемост по ссылке выше в браузере (выступать как «host»)
2. Шлёшь боту `@wookiee_recorder_bot` эту же ссылку (или сразу через DB INSERT в `telemost.meetings`)
3. Recorder контейнер спавнится через ~3 сек
4. Через ~30 сек бот заходит во встречу (видишь нового участника)
5. **Говоришь вслух 60+ секунд** (нужно живое аудио для проверки)
6. Выходишь из встречи (или ждёшь auto-detect — bot сам уйдёт когда останется один)
7. Через ~5 мин — DM с результатом

**Прямой spawn для итерации (быстрее чем через бота):**
```bash
ssh timeweb 'docker run --rm \
  --network deploy_default \
  -v /home/danila/projects/wookiee/data/telemost:/app/data/telemost \
  --env-file /home/danila/projects/wookiee/.env \
  --name test_recorder_$(date +%s) \
  telemost_recorder:latest \
  python scripts/telemost_record.py join \
    https://telemost.360.yandex.ru/j/5655083346 \
    --meeting-id 99999999-9999-9999-9999-999999999999 \
    --output-dir /app/data/telemost/test'
```
(юзер откроет встречу с другого устройства параллельно)

**Чтение результата:**
```bash
# PA debug:
ssh timeweb 'docker logs <container_id> 2>&1 | grep "PA\[" | head -50'

# Audio file size + duration:
ssh timeweb 'ls -la /home/danila/projects/wookiee/data/telemost/<meeting_id>/audio.opus && \
  docker run --rm -v /home/danila/projects/wookiee/data/telemost/<id>:/data telemost_recorder:latest \
  ffprobe -v error -show_entries stream=duration,bit_rate /data/audio.opus'

# Если файл > 500 KB / минута — есть звук, идём в transcript.json смотреть что распознал
```

---

## Acceptance criteria

✅ ЗАПИСАНО: после 5-минутной встречи `/home/danila/projects/wookiee/data/telemost/<id>/audio.opus` ≥ 250 КБ (минимум для разговорной речи в Opus 64k)
✅ РАСПОЗНАНО: `transcript.json` содержит ≥ 1 сегмент с непустым `text`
✅ E2E: пользователь получает в DM сообщение НЕ начинающееся с «📭 ... тишина»

---

## Подсказки субагенту

1. **Перед commit: `git branch --show-current` → должно быть `main`.** В этой сессии я дважды по ошибке коммитил на feature-branch (auto-checkout уводил), пришлось cherry-pick. Если оказался не на main — `git checkout main && git cherry-pick <sha>` → push.
2. **Recorder image НЕ собирается через docker compose.** После изменения `services/telemost_recorder/*` или `Dockerfile.telemost_recorder` нужен ручной `cd /home/danila/projects/wookiee && docker build -f deploy/Dockerfile.telemost_recorder -t telemost_recorder:latest .` (~15 сек если кеш есть). API-контейнер пересобирается стандартом `cd deploy && docker compose up -d --build telemost-recorder-api`.
3. **PA-debug logs уже на месте** (`services/telemost_recorder/audio.py`, `_pa_state()` функция). Используй их, не убирай. Можно расширить (например, `pactl list sinks long` для verbose).
4. **Перед каждым тестом — проверь что в контейнере правильный env:** `ssh timeweb "docker run --rm telemost_recorder:latest sh -c 'env | grep TELEMOST_HEADLESS'"`. Должно быть `false`. Если `true` — Dockerfile rebuild не подхватился, гоняй `docker build ...` с `--no-cache`.
5. **При спавне через API `TELEMOST_HEADLESS` всегда перезаписывается** — см. секцию «Попытка 2». Проверяй `docker inspect <container_id> | jq '.[0].Config.Env'` после спавна — там увидишь реальные env var, переданные docker daemon'у.
6. **Не трогай UX код** (`services/telemost_recorder_api/handlers/`, `keyboards.py`, `_format.py`) — он работает, 99/99 unit tests pass. Если случайно сломал — последний known-good commit для UX `d154c46`.
7. **Не пиши план в `docs/superpowers/plans/`** — задача узкая, plan не нужен. Диагноз → фикс → ребилд → тест → DM с реальным summary.
8. **Pre-commit / formatter может съесть твои edits** — в этой сессии видел, что после `Edit` файл частично откатывался автоматическим инструментом. После каждого Edit делай `Read` чтобы убедиться что код реально такой какой ты хотел.
9. **SSH к серверу может транзиентно упасть** — был 9-часовой outage сегодня (`07:33 → 17:17 UTC`). Если SSH timeout > 20s — подожди 5 мин, попробуй ещё раз. Сервер crash'ился вместе с healthcheck'ами Hub/CRM (вся машина).
10. **Тестовый user в Bitrix:** `telegram_id=252698672` (Данила Матвеев). Если хочешь спавнить встречи прямым SQL INSERT в `telemost.meetings`, используй этот ID как `triggered_by`.
11. **Recorder auto-exit:** бот сам уйдёт из встречи когда останется один участник + прошло 90 сек grace period (см. `join.py:_detect_meeting_ended` + grace в meeting loop). Если хочешь принудительно остановить — `docker stop telemost_rec_<id>`.
12. **Множество worktree-копий в репо:** `find` найдёт `.claude/worktrees/agent-*/scripts/telemost_record.py` — это ЛЕВЫЕ копии других агентов. Канонический файл — в корне `services/telemost_recorder/` и `scripts/telemost_record.py`.
13. **Бюджет:** один subagent invocation для главного исследования. Если первая гипотеза (headless override) не закрывает → попробуй ещё 1-2 (autoplay-policy, ffmpeg stderr). Если не зашло за 45 минут — выходи с отчётом и новыми гипотезами.

---

## Рекомендуемый workflow для оркестратора в новом окне

Не пытайся всё сделать одним монолитом. Разбей на 3 фазы, каждую делегируй субагенту с узким scope. После каждого субагента — читай его отчёт, не дублируй работу.

### Фаза 1 — диагностика (1 subagent, type=`general-purpose`)

```
prompt: |
  Прочитай docs/superpowers/briefs/2026-05-10-telemost-recorder-silent-audio.md.
  Тебе нужно ТОЛЬКО подтвердить или опровергнуть главную гипотезу:
  что headless-override в docker_client.py — реальная причина того, что
  recorder image сейчас запускает chrome-headless-shell вместо полного Chromium.

  Не фикси код. Только проведи исследование:
  1. Inspect последний реально спавненный recorder контейнер на сервере:
     ssh timeweb 'docker ps -a --filter ancestor=telemost_recorder:latest \
       --format "{{.ID}} {{.CreatedAt}}" | head -3'
     Возьми последний, сделай docker inspect, найди реальные env vars.
  2. Прочитай PA-debug логи последнего контейнера, подтверди что там
     `chrome-headless-shell` (не `chrome` / `chromium`).
  3. Прочитай services/telemost_recorder_api/docker_client.py:46-86
     и services/telemost_recorder_api/workers/recorder_worker.py — подтверди
     что headless=True default передаётся.
  4. Скажи мне в отчёте: «Гипотеза подтверждена / опровергнута + что именно покажет dock inspect».

  Не делай никаких git commit. Не меняй файлы. Бюджет — 10 минут.
```

### Фаза 2 — фикс (1 subagent, type=`general-purpose`)

После Фазы 1 — если гипотеза подтверждена, дай этому агенту чёткое задание:

```
prompt: |
  Контекст: смотри docs/superpowers/briefs/2026-05-10-telemost-recorder-silent-audio.md
  Гипотеза подтверждена (см. отчёт Фазы 1).

  Задача — пофиксить headless-override + проверить, что фикс достаточен:
  1. В services/telemost_recorder_api/docker_client.py:46 поменяй default
     `headless: bool = True` → `headless: bool = False`. (Это safer чем убирать
     передачу env — explicit > implicit, и старая семантика ломается шумно.)
  2. Запусти tests: .venv/bin/python -m pytest tests/services/telemost_recorder_api/test_docker_client.py -v
     Если тест ассертит headless=True default — обнови тест.
  3. git checkout main && git add + commit + push.
  4. Деплой: ssh timeweb 'cd /home/danila/projects/wookiee && git pull origin main \
     && cd deploy && docker compose up -d --build telemost-recorder-api'
  5. Verify: ssh timeweb 'docker ps --filter name=telemost_recorder_api --format "{{.Status}}"'
     должно быть Up + healthy.

  НЕ запускай контрольный E2E — это сделает Фаза 3.
  Бюджет — 20 минут.
```

### Фаза 3 — контрольный E2E (1 subagent, type=`general-purpose`)

```
prompt: |
  Тестовая ссылка: https://telemost.360.yandex.ru/j/5655083346
  Юзер сказал — заходить и тестировать самостоятельно можно.

  Задача:
  1. Открой ссылку в headless-браузере (можешь использовать Playwright MCP или
     просто заходи через Chromium — ssh timeweb может прокинуть тестовую
     сессию: docker run -it --rm telemost_recorder:latest python -c "
     from playwright.sync_api import sync_playwright
     with sync_playwright() as p:
         b=p.chromium.launch(headless=False)
         page=b.new_page()
         page.goto('https://telemost.360.yandex.ru/j/5655083346')
         input('press enter to leave')")
     ИЛИ — пинай юзера: «Открой в своём браузере и говори вслух 60+ сек,
     пока бот не начнёт запись».
  2. Параллельно — спавни тестовый recorder напрямую через docker run
     (см. секцию "Прямой spawn" в брифинге), переопределив TELEMOST_HEADLESS=false.
     Watch logs живым: docker logs -f <container_id>
  3. Когда контейнер выйдет — проверь acceptance criteria:
     - audio.opus ≥ 250 КБ
     - transcript.json содержит ≥ 1 сегмент с непустым text
     - В логах видно `chrome` (не `chrome-headless-shell`) в PA[reroute-tick] clients
  4. Если хоть один critterion не пройден — вернись с детальным отчётом
     PA-логов + ffmpeg stderr (нужно временно убрать DEVNULL в audio.py:73-74).

  Бюджет — 30 минут.
```

### Промт для самого оркестратора в новом окне

Просто скопируй это и вставь в свежий чат Claude Code:

```
Прочитай docs/superpowers/briefs/2026-05-10-telemost-recorder-silent-audio.md.

В этом файле — полный контекст бага: бот заходит во встречу Я.Телемоста,
но `audio.opus` всегда тишина, потому что Chromium запускается как
`chrome-headless-shell` который не воспроизводит WebRTC inbound audio.
Главная гипотеза + первый фикс описаны в брифинге.

Действуй по workflow из секции "Рекомендуемый workflow для оркестратора"
в самом конце брифинга. Запусти 3 субагента последовательно
(Фаза 1 → 2 → 3), читай отчёт каждого перед запуском следующего.

Всё что нужно — есть в брифинге: тестовая ссылка, ssh alias, какие файлы
трогать, acceptance criteria, чего НЕ делать.

Когда всё пофикшено и контрольный E2E прошёл — покажи мне:
1. финальный размер audio.opus + длительность
2. первые 3 сегмента из transcript.json
3. сообщение которое бот прислал в DM (скриншот или текст)

Если за 3 фазы не победил — детальный отчёт что именно не сработало
и какие новые гипотезы появились.
```
