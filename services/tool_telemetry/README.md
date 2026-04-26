# services/tool_telemetry/

Логирование запусков инструментов (скиллов) в Supabase.

## Назначение

Каждый запуск Claude Code скилла (`/finance-report`, `/daily-brief` и т.д.) записывает строку в таблицу `tool_runs` через `shared/tool_logger.py`. `tool_telemetry/` содержит:
- `logger.py` — утилита записи (обёртка над `shared/tool_logger.py`)
- `version_tracker.py` — версионирование инструментов
- `schema.sql` — DDL для таблиц `tools` + `tool_runs`

## Использование

```python
from services.tool_telemetry.logger import log_tool_run
await log_tool_run(tool_name="finance-report", status="success", duration_ms=1234)
```

## Связанное

- `shared/tool_logger.py` — основной writer
- `docs/TOOLS_CATALOG.md` — каталог инструментов (автогенерация)
- Скилл `/tool-status` — статус инструментов через Claude Code
