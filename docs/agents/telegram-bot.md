# Oleg Telegram Runtime

## Назначение

`agents/oleg` — финансовый AI-агент бренда Wookiee.
Telegram-бот является интерфейсом к агенту.

## Entry Points

```bash
# Telegram bot mode (default)
python -m agents.oleg

# Background agent mode
python -m agents.oleg agent
```

## Ключевые модули

- `agents/oleg/main.py` — bot runtime
- `agents/oleg/agent_runner.py` — автономный агентный цикл
- `agents/oleg/services/` — data tools, price analysis, report generation
- `agents/oleg/handlers/` — Telegram handlers

## Зависимости

```bash
pip install -r agents/oleg/requirements.txt
```

## Связанные документы

- [analytics-engine.md](analytics-engine.md)
- [../architecture.md](../architecture.md)
- [../guides/environment-setup.md](../guides/environment-setup.md)
