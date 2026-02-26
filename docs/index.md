# Wookiee — Documentation Index

## Core

| Документ | Назначение |
|---|---|
| [AGENTS.md](../AGENTS.md) | Единые правила разработки и качества |
| [README.md](../README.md) | Обзор проекта, актуальные entrypoints |
| [architecture.md](architecture.md) | Текущая архитектура runtime-контура |
| [adr.md](adr.md) | Архитектурные решения (ADR) |
| [development-history.md](development-history.md) | Последние изменения |
| [infrastructure.md](infrastructure.md) | Сервер и деплой |

## Active Runtime

| Компонент | Статус | Документация |
|---|---|---|
| Олег (финансовый AI-агент) | Активен | [agents/telegram-bot.md](agents/telegram-bot.md) |
| Ибрагим (ETL/DB) | Активен | [agents/ibrahim.md](agents/ibrahim.md) |
| WB localization service | Активен | [agents/mp-localization.md](agents/mp-localization.md) |
| Analytics Engine | Активен | [agents/analytics-engine.md](agents/analytics-engine.md) |

## Guides

| Документ | Назначение |
|---|---|
| [guides/dod.md](guides/dod.md) | Definition of Done |
| [guides/environment-setup.md](guides/environment-setup.md) | Локальная и серверная настройка |
| [guides/logging.md](guides/logging.md) | Логирование |
| [guides/agent-principles.md](guides/agent-principles.md) | Принципы проектирования агентов |
| [guides/archiving-and-temp.md](guides/archiving-and-temp.md) | Архивирование и временные файлы |

## Database Docs

| Документ | Назначение |
|---|---|
| [database/DB_METRICS_GUIDE.md](database/DB_METRICS_GUIDE.md) | Справочник метрик |
| [database/DB_QUESTIONS_FOR_DEVELOPER.md](database/DB_QUESTIONS_FOR_DEVELOPER.md) | Вопросы к разработчику БД |
| [database/DATABASE_REFERENCE.md](database/DATABASE_REFERENCE.md) | Legacy reference |
| [database/DATABASE_WORKPLAN.md](database/DATABASE_WORKPLAN.md) | План работ по БД |
| [database/DATA_QUALITY_NOTES.md](database/DATA_QUALITY_NOTES.md) | Ноты по качеству данных |

## Plans

| Документ | Статус |
|---|---|
| [plans/ibrahim-deploy-and-etl.md](plans/ibrahim-deploy-and-etl.md) | Active |
| [plans/2026-02-25-db-audit-results.md](plans/2026-02-25-db-audit-results.md) | Completed |
| [plans/2026-02-25-db-improvement-proposals.md](plans/2026-02-25-db-improvement-proposals.md) | Active |
| [plans/2026-02-25-dashboard-tz.md](plans/2026-02-25-dashboard-tz.md) | Active |

## Archive

| Документ | Назначение |
|---|---|
| [archive/agents/lyudmila-bot.md](archive/agents/lyudmila-bot.md) | Retired docs: Lyudmila |
| [archive/plans/lyudmila-bitrix24-agent-retired.md](archive/plans/lyudmila-bitrix24-agent-retired.md) | Retired plan |
| [archive/retired_agents/](archive/retired_agents/) | Архив runtime-кода удалённых агентов |

Правило: держать в активной навигации только текущий runtime-контур.
