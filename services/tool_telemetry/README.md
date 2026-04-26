# services/tool_telemetry/

Каталог инструментов и DDL для телеметрии запусков (Supabase).

## Назначение

`tool_telemetry/` хранит схему и историческую обёртку над логированием запусков. Текущая запись происходит через `shared/tool_logger.py` — он пишет строки в `tool_runs` при каждом вызове скилла Claude Code.

Содержимое:
- `schema.sql` — DDL для таблиц `tools` + `tool_runs` (применяется в Supabase вручную)
- `version_tracker.py` — `register_agent_version()` для трекинга версий
- `logger.py` — устаревшие no-op обёртки `log_agent_run` / `log_orchestrator_run` (writes отключены 2026-04-13, таблицы `agent_runs` / `orchestrator_runs` сохранены для исторических данных)

## Запись новых run-ов

Используй `shared/tool_logger.py` напрямую — это основной writer для текущей таблицы `tool_runs`. См. примеры в скриптах: `scripts/finance_report/run.py`, `scripts/daily_brief/run.py`.

## Связанное

- `shared/tool_logger.py` — основной writer для `tool_runs`
- `docs/TOOLS_CATALOG.md` — каталог инструментов (автогенерация из Supabase)
- Скилл `/tool-status` — статус инструментов через Claude Code
- Скилл `/tool-register` — регистрация нового инструмента в каталоге
