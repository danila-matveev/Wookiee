# /heartbeat

Ночной маячок: одно короткое сообщение по итогам ночи. Часть Wave B4 ночного DevOps-агента.

## Зачем

Чтобы каждое утро владелец видел одну строчку «вот что было ночью» — без необходимости лезть в GH Actions или в Supabase. Если ночью ничего не происходило и `heartbeat_quiet_if_zero=true` (дефолт) — `/heartbeat` промолчит.

## Что в сообщении

- Дата ночи: «🌙 Ночь 14 мая»
- Сколько починил сам: «✅ Починил 3 штуки (битая ссылка, лишний импорт, drift зеркала)»
- Сколько ждёт твоё решение: «🤔 Ждёт твоё решение: 1 пункт (вставь `/hygiene-resolve`)»
- Что с покрытием: «📊 Покрытие тестами: 67% (без изменений)»
- (Опционально) Статус PR за ночь
- Жёсткий лимит: ≤500 символов

## Как запустить вручную

```bash
python scripts/nightly/heartbeat.py            # отправить
python scripts/nightly/heartbeat.py --dry-run  # только напечатать, не слать
```

## Конфиг

См. `.hygiene/config.yaml`:

```yaml
heartbeat_enabled: true
heartbeat_quiet_if_zero: true
```

## Файлы

- `SKILL.md` — описание скилла (фронт-маттер для индекса)
- `runner.py` — тонкая обёртка
- `README.md` — этот файл
- Логика: `scripts/nightly/heartbeat.py`
- Рендер + отправка: `shared/telegram_digest.py`

## Связанное

- Plan: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md` §5.6
- Tests: `tests/skills/test_heartbeat.py`
- Bot: `@wookiee_alerts_bot` (используется существующий, не плодим новых — см. `feedback_hygiene_bot_design.md`)
