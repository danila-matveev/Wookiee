# telemost_recorder

Сервис автоматической записи встреч Яндекс.Телемоста с последующей транскрипцией через SpeechKit.

## Запуск

```bash
python scripts/telemost_record.py join <meeting_url>
```

## Архитектура

- `browser.py` — запуск headful Chromium через Playwright + Xvfb (виртуальный дисплей)
- `join.py` — FSM-логика присоединения к встрече
- `state.py` — состояния FSM (`MeetingStatus`, `FailReason`)
- `config.py` — конфиг (URL-паттерны, таймауты)

## Требования

- Xvfb + PulseAudio (для headless-записи аудио)
- Playwright с Chromium (`playwright install chromium`)
- Переменные из `.env`: `SPEECHKIT_API_KEY`, `SUPABASE_*`

## Статус

MVP — базовый join-flow реализован. Транскрипция и интеграция с Notion в разработке.
