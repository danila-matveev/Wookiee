# telemost_recorder

Сервис автоматической записи встреч Яндекс Телемоста — заходит в звонок как залогиненный пользователь Yandex 360 Business, пишет аудио через PulseAudio null-sink, транскрибирует через Yandex SpeechKit.

## Как запускается

В проде recorder работает не сам по себе — его запускает `telemost_recorder_api` в отдельном Docker-контейнере на каждую встречу. Локально для отладки:

```bash
python scripts/telemost_record.py join <meeting_url>
```

## Архитектура

- `browser.py` — Playwright + Chromium в headed-режиме через Xvfb. При наличии `TELEMOST_STORAGE_STATE_PATH` загружает cookies+localStorage авторизованного Yandex 360 юзера → бот заходит как сотрудник, а не гость.
- `join.py` — FSM присоединения: 6 экранных состояний (включая `AUTH_PRE_JOIN` для залогиненных юзеров и `NAME_FORM` для гостей), цикл записи, детект окончания встречи.
- `audio.py` — PulseAudio null-sink → ffmpeg → opus. Запись изолирована per-meeting (sink называется `telemost_<meeting_id>`).
- `transcribe.py` — SpeechKit recognition + дешёвый speaker resolve через OpenRouter (LIGHT-тир).
- `speakers.py` — резолв голос → реальное имя через `data/speakers.yml`.
- `state.py` — `MeetingStatus`, `FailReason`, валидация переходов FSM.
- `config.py` — env-конфиг.

## Авторизация через Yandex 360 Business (anti-bot fix)

**Проблема (до PR #142):** Telemost кикал анонимных гостей через 30-300 секунд после захода — встроенная anti-spam защита. Записи получались по 3-5 минут вместо часа.

**Решение:** бот заходит как **залогиненный сотрудник** организации Yandex 360 Business (`recorder@wookiee.shop`). Авторизованные участники под anti-bot не подпадают.

**Как это работает:**
1. Один раз оператор запускает [`scripts/telemost_export_cookies.py`](../../scripts/telemost_export_cookies.py) на локальной машине — открывается видимый Chromium, происходит авто-логин (через env `TELEMOST_LOGIN`+`TELEMOST_PASSWORD`) или ручной если auth-форма поменялась.
2. Скрипт ждёт появления cookie `Session_id` (надёжный сигнал успешного логина), потом seedит куки на `telemost.yandex.ru`, сохраняет `data/telemost_storage_state.json`.
3. Оператор копирует файл на сервер в `/opt/wookiee/secrets/telemost_storage_state.json` (perms 600).
4. `deploy/docker-compose.yml` маунтит `/opt/wookiee/secrets:ro` в API-контейнер — один путь работает и для API (`os.path.isfile()`), и как host-source для бинд-маунта в recorder-контейнерах.
5. `services/telemost_recorder_api/docker_client.py` пробрасывает файл readonly в каждый спавненый recorder-контейнер на `/app/data/telemost_storage_state.json` + env `TELEMOST_STORAGE_STATE_PATH`.
6. `browser.py` грузит `storage_state` в Playwright context — бот авторизован.

**Fallback:** если env-переменная пустая или файл отсутствует — recorder откатывается на гостевой режим (старое поведение). Это нужно для локальных тестов и чтобы полугнилая кука не положила все записи. В API-контейнере вылетает warning в лог.

**Ротация:** Yandex просит перелогиниться раз в ~60 дней. Когда это случится, бот начнёт падать на authentication step. Решение — повторить шаг 1-3.

См. подробный operator-runbook в [docs/operations/telemost_bot.md](../../docs/operations/telemost_bot.md).

## Состояния FSM при заходе

| Состояние | Когда | Что делает recorder |
|-----------|-------|---------------------|
| `CONTINUE_IN_BROWSER` | Telemost попросил «продолжить в браузере» | Клик «Продолжить» |
| `NAME_FORM` | Гостевой флоу: поле «введите имя» + кнопка | Заполняет `TELEMOST_BOT_NAME` и кликает «Подключиться» |
| `AUTH_PRE_JOIN` | Авторизованный флоу: аватар + email + только кнопка | Кликает «Подключиться» |
| `WAITING_ROOM` | Хост ещё не впустил | Ждёт до `WAITING_ROOM_TIMEOUT` (10 мин по умолчанию) |
| `IN_MEETING` | В звонке | Стартует запись, переходит в loop |
| `MEETING_NOT_FOUND` | Ссылка протухла или неверная | FAILED с понятным сообщением |

## Детект окончания встречи

Через 5 минут после начала записи (`elapsed >= 300`) включается проверка `detect_meeting_ended()`. Использует **только два надёжных сигнала**:

1. URL ушёл с `/j/` — реальный «end meeting» хоста или принудительный кик
2. Видимый оверлей «Встреча завершена» / «Meeting ended»

**Что было раньше (PR #144 убрал):** третий сигнал через подсчёт участников ломался на Yandex 360 — `extract_participants()` не находит имена через CSS-селекторы корпоративного UI и возвращает `[]`, рекордер на 5-минутной отметке думал «людей нет» и сам выходил из живой встречи.

Защита от вечной записи в пустой комнате — через `RECORDING_HARD_LIMIT_HOURS` (default 4ч, в API-конфиге).

## Известные ограничения

- `extract_participants()` возвращает `[]` на `telemost.360.yandex.ru` — селекторы под публичный домен, корпоративный использует другие. Влияет только на список спикеров в финальной саммари. Speaker resolution через `raw_segments.json` + `speakers.yml` работает независимо. Чинить нужно с живым DOM-дампом из звонка на Yandex 360 — см. инструкцию [docs/operations/telemost_bot.md → «Починка extract_participants()»](../../docs/operations/telemost_bot.md). Два варианта:
  - `TELEMOST_DUMP_PARTICIPANTS_DOM=1` — рекордер один раз сам сохранит панель + полную страницу как `data/telemost/<meeting_id>/dom_participants_<ts>.html`, если через 2 минуты после старта список участников пустой.
  - `scripts/telemost_dump_participants.py <meeting_url>` — оператор-флоу через локальный Chromium с авторизацией.

## Health-check куки

Каждый день в 08:00 MSK `scripts/telemost_check_cookies.py` (запускается из `wookiee-cron`):
1. Парсит `Session_id.expires` из `TELEMOST_STORAGE_STATE_PATH`. Если осталось <7 дней — алерт в `@wookiee_alerts_bot`.
2. Дёргает `passport.yandex.ru/profile` с этими куками. Если Яндекс отвечает страницей логина — куки revoked, отдельный алерт.

Если всё хорошо — пишет `OK: Session_id valid, days_left=N` в stdout (виден в `docker logs wookiee_cron`). Цель — узнавать о протухании за неделю до того, как бот начнёт падать.

## Требования

- Xvfb + PulseAudio (Linux only; для headful Chromium в Docker)
- Playwright с Chromium (`playwright install chromium` + `playwright install-deps`)
- Переменные из `.env`:
  - `SPEECHKIT_API_KEY`, `YANDEX_FOLDER_ID` — транскрипция
  - `OPENROUTER_API_KEY` — speaker resolve
  - `TELEMOST_BOT_NAME` — отображаемое имя в гостевом режиме (для авторизованного — имя берётся из Yandex 360 профиля)
  - `TELEMOST_STORAGE_STATE_PATH` — путь к storage_state.json (опционально, без него гостевой режим)
  - `TELEMOST_DUMP_PARTICIPANTS_DOM=1` — диагностический флаг: один раз дампит DOM панели участников, если `extract_participants()` вернул пусто через 2+ минуты после начала записи (выкл. по умолчанию)
  - `TELEGRAM_ALERTS_BOT_TOKEN` + `HYGIENE_TELEGRAM_CHAT_ID` — для алертов от cookie health-check (нужны в cron-контейнере)

## Статус

Продакшен. Авторизация через Yandex 360 Business работает, anti-bot kick устранён. Smoke-тесты от 2026-05-15:
- `091300db` — 5 мин (баг с false-positive ended-detection, починен в PR #144)
- `1af24f67` — 23 мин (после PR #144), DONE clean, 43 скриншота, 23 транскрипт-сегмента
