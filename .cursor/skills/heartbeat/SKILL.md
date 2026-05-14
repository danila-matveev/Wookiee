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

В 05:00 UTC:

1. Читает `.hygiene/config.yaml`. Если `heartbeat_enabled=false` — выходит без действий.
2. Подтягивает today-репорты: hygiene, code-quality, coverage, coordinator (если есть).
3. Считает: сколько починили, сколько ждёт твоё решение, что с покрытием, какой PR.
4. Рендерит ≤500 символов простой русский.
5. Шлёт в `@wookiee_alerts_bot`.

Если за день ноль fixes, ноль NEEDS_HUMAN и нет открытого PR (т.е. `heartbeat_quiet_if_zero=true`) — **молчит**.

## Quick start

```bash
python scripts/nightly/heartbeat.py            # отправить
python scripts/nightly/heartbeat.py --dry-run  # только напечатать, не слать
```

## Конфиг

```yaml
# .hygiene/config.yaml
heartbeat_enabled: true
heartbeat_quiet_if_zero: true
```

## Файлы

- `scripts/nightly/heartbeat.py` — логика
- `shared/telegram_digest.py` — рендеринг и отправка

## Pre-conditions

- Env `TELEGRAM_ALERTS_BOT_TOKEN`, `HYGIENE_TELEGRAM_CHAT_ID`
- `requests` библиотека установлена
- `.hygiene/` существует

## Примеры рендера

См. `tests/skills/test_heartbeat.py` и план §5.
