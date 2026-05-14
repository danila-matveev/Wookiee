---
name: heartbeat
description: "Ночная сводка-маячок. Собирает все today-репорты (hygiene, code-quality, coverage, coordinator), рендерит короткое сообщение на простом русском (≤500 символов) и шлёт в @wookiee_alerts_bot. Если за ночь ничего не происходило и heartbeat_quiet_if_zero=true — молчит. Cron 05:00 UTC."
triggers:
  - /heartbeat
  - сводка за ночь
  - что было ночью
metadata:
  category: devops
  version: 0.1.0
  owner: danila
  wave: B4
---

# Heartbeat

Часть ночного DevOps-агента (план: `docs/superpowers/plans/2026-05-14-nighttime-devops-agent-impl.md` §5.6).

## Что делает

В 05:00 UTC (после `night-coordinator` и `test-coverage-check`):

1. Читает `.hygiene/config.yaml`. Если `heartbeat_enabled=false` — выходит без действий.
2. Подтягивает today-репорты: `hygiene-YYYY-MM-DD.json`, `code-quality-YYYY-MM-DD.json`, `coverage-YYYY-MM-DD.json`, `coordinator-YYYY-MM-DD.json` (если есть).
3. Считает: сколько починили, сколько ждёт твоё решение, что с покрытием, какой PR.
4. Через `shared.telegram_digest.render_heartbeat` рендерит ≤500 символов простой русский.
5. Через `shared.telegram_digest.send_digest` шлёт в `@wookiee_alerts_bot`.

Если за день ноль fixes, ноль NEEDS_HUMAN и нет открытого PR (т.е. `heartbeat_quiet_if_zero=true`) — **молчит**, ничего не шлёт.

## Quick start

```bash
# Полный прогон
python scripts/nightly/heartbeat.py

# Просто отрендерить, не отправлять
python scripts/nightly/heartbeat.py --dry-run
```

## Файлы

- `scripts/nightly/heartbeat.py` — основная логика
- `shared/telegram_digest.py` — рендеринг и отправка

## Конфиг

```yaml
# .hygiene/config.yaml
heartbeat_enabled: true        # выключить → false
heartbeat_quiet_if_zero: true  # не шлёт пустые ночи; false → шлёт всегда
```

## Pre-conditions

- Env `TELEGRAM_ALERTS_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID` (в GH Actions secrets)
- `requests` библиотека установлена (project-wide dep)
- `.hygiene/` существует

## Cron

`.github/workflows/heartbeat.yml` (Wave A3, ещё не создан) — расписание 05:00 UTC, concurrency group `night-devops`.

## Failure modes

| Что | Что делает |
|---|---|
| Telegram API недоступен | Exit 1, лог в GH Action; владелец увидит failure-статус |
| Reports отсутствуют (ни одного today) | Шлёт «чисто, делать нечего» или молчит если quiet flag |
| Config недоступен | Дефолты: enabled=true, quiet_if_zero=true |

## Примеры рендера

См. plan §5 и unit-тесты `tests/skills/test_heartbeat.py`.
