# Telemost Recorder — Design Spec

**Date:** 2026-05-02  
**Status:** Approved — ready for planning  
**Scope:** Full service architecture + Phase 1 detailed design

---

## 1. Problem & Goal

Команда Wookiee (~5 чел) проводит созвоны в Яндекс Телемосте (бесплатный тариф). Встречи не записываются автоматически, транскрибировать вручную некому. Нужен внутренний сервис, который:

1. Подключается к встрече как видимый виртуальный участник `Wookiee Recorder`
2. Захватывает аудио встречи
3. Создаёт полный русский транскрипт + короткое саммари
4. Сохраняет результат в Notion (существующая БД «Записи встреч»)

Финальный сценарий: автоматическое подключение по расписанию из Bitrix24 Calendar.  
MVP1: ручная передача ссылки, полная цепочка для одной встречи.

---

## 2. Constraints

| Факт | Импакт |
|------|--------|
| Бесплатный Телемост (не Yandex 360 Business) | Нет нативной транскрипции, нет SIP — только браузер-бот |
| ~5% встреч — чужие (создал не Wookiee) | Бот нужен для всех встреч без исключения |
| Календарь команды — Bitrix24 | Будущий автополлер через Bitrix24 REST API |
| Deploy target — Timeweb (77.233.212.61) | Linux-сервер, Docker + autopull pipeline уже работает |
| Существующая Notion БД «Записи встреч» (id `34e58a2bd58780ed9d48ed21a5ac6b94`) | Дополняем, не создаём новую |

---

## 3. Target Architecture

```
[Ручная ссылка (MVP1)]       [Bitrix24 Calendar API (будущее)]
          │                              │
          └──────────────┬───────────────┘
                         ▼
              ┌─────────────────────┐
              │   Meeting Scheduler │  Supabase: таблица meetings (FSM)
              └──────────┬──────────┘
                         │  (за 1 мин до начала или сразу)
                         ▼
              ┌─────────────────────┐
              │   Browser Worker    │  Docker контейнер на Timeweb
              │   Playwright +      │  Ubuntu 22.04 + Xvfb :99 +
              │   Chromium headful  │  PulseAudio virtual sink
              └──────────┬──────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
       [Аудио-захват]         [Статус/скриншоты]
   PulseAudio loopback         stdout JSON +
   ffmpeg → opus chunks        data/telemost/<id>/
              │
              ▼
   ┌─────────────────────┐
   │  Yandex SpeechKit   │  streaming ASR, русский
   │  (primary STT)      │
   └──────────┬──────────┘
   fallback: openai/whisper-large-v3 via OpenRouter
              │
              ▼
   ┌─────────────────────┐
   │  OpenRouter LLM     │  Gemini 3 Flash (MAIN тир)
   │  Summary            │  ~20K tokens, $0.01/встреча
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐     ┌──────────────────────┐
   │  Notion API         │     │  Supabase Storage    │
   │  БД «Записи встреч» │     │  аудио-файл + ссылка │
   └─────────────────────┘     └──────────────────────┘
```

---

## 4. Meeting State Machine (FSM)

```
PENDING
  → JOINING          (браузер открыт, форма заполняется)
  → IN_MEETING       (бот виден участникам)  ← Phase 1 terminal success
  → WAITING_ROOM     (бот ждёт впуска)       ← Phase 1: ждём + уведомляем
    → IN_MEETING     (впустили)
    → NOT_ADMITTED   (таймаут 10 мин)        ← FAILED
  → RECORDING        (Phase 2: аудио пишется)
  → TRANSCRIBING     (Phase 3)
  → SUMMARIZING      (Phase 4)
  → PUBLISHING       (Phase 5: Notion)
  → DONE
  → FAILED(reason)
```

Phase 1 реализует: `PENDING → JOINING → IN_MEETING | WAITING_ROOM | FAILED`

---

## 5. Tech Stack

| Слой | Инструмент | Обоснование |
|------|-----------|-------------|
| Браузер | Playwright Python + Chromium headful + Xvfb | headful для WebRTC, Playwright = prod-ready |
| Аудио (Phase 2) | PulseAudio virtual sink + ffmpeg → opus | стандарт для безголового Linux |
| STT | Yandex SpeechKit streaming ASR | лучший русский, диаризация, пунктуация |
| STT fallback | `openai/whisper-large-v3` via OpenRouter | тот же ключ, нет нового вендора |
| LLM summary | Gemini 3 Flash via OpenRouter | MAIN тир из config, 1M ctx |
| Хранилище аудио | Supabase Storage | один вендор, RLS уже настроен |
| Метаданные / FSM | Supabase Postgres таблица `meetings` | shared/data_layer.py |
| Notion | existing БД «Записи встреч» | `transcribe_meetings.py` как референс |
| Деплой | Docker + autopull, Timeweb | как остальные сервисы Wookiee |
| Параллель (Phase 7) | docker-compose pool, 2–3 контейнера | scheduler выдаёт свободный |
| Календарь (будущее) | Bitrix24 REST API `calendar.event.get` | уже используется в проекте |

---

## 6. Repository Structure

```
services/
  telemost_recorder/
    __init__.py
    browser.py       # Playwright: запуск контекста, permissions, скриншоты
    join.py          # логика входа: навигация → форма → детекция состояния
    state.py         # dataclass Meeting + FSM transitions + Supabase persist
    config.py        # BOT_NAME, таймауты, известные CSS-селекторы

deploy/
  Dockerfile.telemost_recorder   # Ubuntu 22.04 + Xvfb + PulseAudio + Chromium + Playwright

scripts/
  telemost_record.py   # shim: python scripts/telemost_record.py join <url> [--name ...]

tests/
  telemost_recorder/
    test_url_validation.py         # unit: валидация Telemost URL
    test_state_detection.py        # Playwright против mock-HTML экранов Телемоста
    test_live_join.py              # интеграционный: требует --url= и реальной встречи
```

---

## 7. Phase 1: Join Flow Detail

### Entry point
```bash
python scripts/telemost_record.py join https://telemost.yandex.ru/j/XXXX
# или в контейнере на сервере:
docker exec telemost_recorder python scripts/telemost_record.py join <url>
```

### Шаги
1. Валидация URL (pattern: `telemost.yandex.ru/j/` или `telemost.yandex.com/join`)
2. Playwright открывает Chromium headful (DISPLAY=:99 под Xvfb)
3. Browser context блокирует микрофон и камеру через `permissions: {microphone: deny, camera: deny}`
4. `navigate(url)` → ждём до 30 сек одно из состояний:
   - Появился кнопка «Продолжить в браузере» → кликаем
   - Появилась форма с полем имени → сразу к шагу 5
   - Ошибка/404 → `FAILED(MEETING_NOT_FOUND)`
5. Заполняем имя «Wookiee Recorder» (один или два поля — определяется на реальной встрече в Phase 1)
6. Кликаем «Присоединиться» / «Войти»
7. Ждём до 60 сек одно из:
   - Участники/controls встречи видны → `IN_MEETING`
   - Экран ожидания → `WAITING_ROOM`
   - Таймаут → `FAILED(JOIN_TIMEOUT)`
8. Каждые 30 сек скриншот → `data/telemost/<meeting_id>/screenshot_NNN.png`
9. JSON-статус в stdout:
   ```json
   {"status": "IN_MEETING", "meeting_id": "uuid", "screenshot": "path/to/latest.png"}
   ```
10. Процесс удерживает браузер открытым до Ctrl+C / до закрытия вкладки Телемостом

### Waiting room handling
- Статус `WAITING_ROOM` — не ошибка
- Stdout: `«Wookiee Recorder в зале ожидания — впустите его в интерфейсе Телемоста»`
- Процесс polling каждые 5 сек → как только детектирует переход в `IN_MEETING`, обновляет статус
- Таймаут ожидания: 10 минут → `FAILED(NOT_ADMITTED)`

---

## 8. Error States

| Код | Триггер | Сообщение |
|-----|---------|-----------|
| `INVALID_URL` | URL не Телемост | «Ссылка не похожа на Яндекс Телемост» |
| `MEETING_NOT_FOUND` | 404 или «встреча завершена» | «Встреча не найдена или уже закончилась» |
| `JOIN_TIMEOUT` | 60 сек без перехода | «Тайм-аут при подключении — скриншот в logs/» |
| `UI_DETECTION_FAILED` | ни один селектор не нашёлся | «Интерфейс Телемоста изменился — нужна актуализация селекторов» |
| `NOT_ADMITTED` | 10 мин в WAITING_ROOM | «Организатор не впустил бота в течение 10 минут» |

---

## 9. Testing Strategy

### Unit тесты (без сети, без браузера)
- `test_url_validation.py` — принимает/отклоняет URL-паттерны
- `test_state_machine.py` — FSM transitions, нет невалидных переходов

### Playwright тесты против mock HTML
- `test_state_detection.py` — локальный HTTP-сервер поднимает копии экранов Телемоста (форма имени, waiting room, meeting UI). Playwright проходит flow, тест проверяет корректную детекцию состояния.

### Интеграционный тест с реальной встречей
```bash
pytest tests/telemost_recorder/test_live_join.py \
  --url="https://telemost.yandex.ru/j/XXXX" \
  -v
```
- Playwright автоматически проходит весь join flow
- Тест ждёт `IN_MEETING` или `WAITING_ROOM` (оба = success для Phase 1)
- Если `WAITING_ROOM`: тест выводит «Впустите Wookiee Recorder в Телемосте» и ждёт до 10 мин автоматически
- После впуска (или если waiting room не включён) — тест сам детектирует `IN_MEETING` и проходит
- Артефакты: скриншоты + JSON-report сохраняются в `data/telemost/<id>/`

**Роль пользователя в интеграционном тесте:**  
1. Создать встречу в Телемосте, скинуть ссылку  
2. Если waiting room: одним кликом впустить бота  
Всё остальное — автоматически.

---

## 10. Phase 1 Acceptance Criteria

Фаза считается успешной при всех пяти условиях:
1. `pytest test_url_validation.py test_state_machine.py test_state_detection.py` — все green
2. Интеграционный тест с реальной ссылкой завершается статусом `IN_MEETING`
3. Скриншот показывает интерфейс встречи с видимым участником «Wookiee Recorder»
4. Камера и микрофон бота выключены (видно по иконкам в интерфейсе)
5. Процесс удерживает сессию до явного завершения

---

## 11. Out of Scope for Phase 1

- Аудио-захват (Phase 2)
- Транскрипция, саммари, Notion (Phase 3–5)
- Несколько пользователей / параллельность (Phase 6–7)
- Bitrix24 Calendar автоподключение (Phase 8, вне MVP1)
- Telegram-уведомления
- Веб-интерфейс / API endpoint

---

## 12. Prerequisites Before Implementation

- [ ] Yandex.Cloud аккаунт + API ключ SpeechKit (Phase 3, не нужен в Phase 1)
- [ ] `TELEMOST_BOT_NAME` в `.env` (default: `Wookiee Recorder`)
- [ ] Тестовая встреча Телемоста для интеграционного теста Phase 1
- [ ] Timeweb: проверить, что Docker может запустить headful Chromium + Xvfb (известное ограничение на shared VPS)
