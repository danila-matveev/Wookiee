# Phase 1: Очистка - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Полное удаление V3 reporting system (agents/v3/) и всех зависимостей. После этой фазы кодовая база содержит только V2 оркестратор (agents/oleg/) как единственную систему отчётов.

</domain>

<decisions>
## Implementation Decisions

### Удаление agents/v3/
- **D-01:** Директория agents/v3/ удаляется целиком со всем содержимым (20+ файлов: orchestrator, agents, conductor, delivery, config, scheduler, etc.)
- **D-02:** Директория tests/v3/ и tests/agents/v3/ удаляются целиком

### Скрипты
- **D-03:** Все скрипты в scripts/, импортирующие agents.v3, удаляются:
  - `run_report.py` — обёртка V3 (daily/weekly/monthly/marketing/funnel)
  - `rerun_weekly_reports.py` — перезапуск weekly через V3
  - `test_v2_bridge.py` — тест моста V2↔V3
  - `run_price_analysis.py` — ценовой анализ через V3 config
  - `shadow_test_reporter.py` — V3-related
- **D-04:** `run_finolog_weekly.py` — НЕ удалять, починить позже (finolog-cron контейнер остаётся)
- **D-05:** `run_localization_report.py` — проверить: если единственная зависимость от V3 легко заменяема, развязать; иначе починить позже

### V2→V3 зависимость
- **D-06:** agents/oleg/services/price_tools.py импортирует `agents.v3.config.get_wb_clients()` — развязать (перенести функцию куда нужно)

### Claude's Discretion
- Решение куда перенести `get_wb_clients()` (shared/config.py или agents/oleg/config)
- Что делать с `run_localization_report.py` — удалить или развязать
- Как обновить Docker-compose: переключить на V2 entrypoint или удалить контейнер wookiee-oleg (V2 запуск будет настроен в Phase 4)
- Объём очистки docs — удалить всё V3-related, плюс при необходимости устаревшие docs

### Docker-compose
- **D-07:** Контейнер wookiee-oleg сейчас запускает `python -m agents.v3` — Claude решит: переключить на V2 или убрать (Phase 4 займётся запуском)
- **D-08:** finolog-cron контейнер — оставить, скрипт починить в следующих фазах
- **D-09:** Volume `agents/v3/data` — удалить из docker-compose при удалении V3

### Документация
- **D-10:** V3-related docs удаляются жёстко:
  - `docs/superpowers/specs/2026-03-22-v3-full-migration-design.md`
  - `docs/superpowers/specs/2026-03-22-v3-report-depth-gap.md`
  - `docs/superpowers/specs/2026-03-24-v3-reports-audit.md`
  - `docs/superpowers/plans/2026-03-20-v3-full-migration.md`
  - `docs/superpowers/plans/2026-03-23-v3-full-migration-plan.md`
  - `docs/superpowers/plans/2026-03-24-v3-reports-fix-plan.md`
- **D-11:** Claude решает, есть ли ещё устаревшие docs для удаления

### Зависимости
- **D-12:** Удалить langchain/langgraph/langchain-openai из agents/v3/requirements.txt (вместе с удалением всей директории)
- **D-13:** Проверить корневой requirements.txt и другие requirements*.txt на наличие V3-only зависимостей

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Проект
- `AGENTS.md` — правила проекта (DB через shared/data_layer.py, config через shared/config.py)
- `.planning/REQUIREMENTS.md` — требования CLEAN-01..04

### V3 система (для понимания что удалять)
- `agents/v3/` — весь код V3 системы
- `agents/v3/requirements.txt` — зависимости V3
- `deploy/docker-compose.yml` — текущая конфигурация контейнеров

### V2 система (для понимания что оставить)
- `agents/oleg/` — V2 оркестратор (единственная рабочая система)

</canonical_refs>

<code_context>
## Existing Code Insights

### V3 зависимости в кодовой базе
- `agents/v3/` — 20+ файлов: orchestrator.py, runner.py, scheduler.py, app.py, config.py, monitor.py, prompt_tuner.py, gates.py, christina.py, state.py + поддиректории (agents/, conductor/, delivery/, data/)
- `tests/v3/` — тесты V3 (test_messages, test_orchestrator_pi, test_prompt_tuner, test_monitor, conftest)
- `tests/agents/v3/` — дополнительные тесты (test_trust_envelope)
- 6+ скриптов в scripts/ импортируют agents.v3

### Перекрёстная зависимость V2→V3
- `agents/oleg/services/price_tools.py:639` — `from agents.v3 import config` для `config.get_wb_clients()`
- `shared/notion_client.py:5` — комментарий упоминает agents/v3/delivery/notion.py

### Docker
- `deploy/docker-compose.yml` — wookiee-oleg запускает `python -m agents.v3`, монтирует agents/v3/data
- finolog-cron запускает scripts.run_finolog_weekly (V3-зависимый)

</code_context>

<specifics>
## Specific Ideas

Пользователь хочет жёсткую зачистку: удалять всё V3-related без колебаний. Claude принимает решение что оставить — минимальный набор для работающей системы.

</specifics>

<deferred>
## Deferred Ideas

- Починка finolog-cron скрипта (run_finolog_weekly.py) — Phase 3 или 4
- Полная настройка Docker-compose для V2 — Phase 4 (Запуск и доставка)

</deferred>

---

*Phase: 01-cleanup*
*Context gathered: 2026-03-30*
