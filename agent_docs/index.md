# Wookiee Analytics — Documentation Index

## Quick Navigation

| Документ | Назначение |
|----------|-----------|
| [AGENTS.md](../AGENTS.md) | Универсальные правила (ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ) |
| [README.md](../README.md) | Обзор проекта и быстрый старт |
| [architecture.md](architecture.md) | Архитектура системы |
| [adr.md](adr.md) | Лог архитектурных решений |
| [development-history.md](development-history.md) | Журнал последних изменений |

## Агенты проекта

Бизнес-описания и техническая документация модулей проекта. Каждый агент — автономный модуль, решающий конкретную бизнес-задачу.

| Агент | Статус | Документация |
|-------|--------|-------------|
| Telegram Bot | Активен | [agents/telegram-bot.md](../agents/telegram-bot.md) |
| Analytics Engine | Активен | [agents/analytics-engine.md](../agents/analytics-engine.md) |
| MP Localization | В разработке | [agents/mp-localization.md](../agents/mp-localization.md) |
| Bitrix CRM | Планируется | [agents/bitrix-crm.md](../agents/bitrix-crm.md) |

Обзор агентной архитектуры: [agents/README.md](../agents/README.md)

> **agents/ vs agent_docs/:** `agents/` описывает бизнес-агентов проекта (что делают, как использовать). `agent_docs/` (эта папка) — руководства для AI-агентов разработки (как писать код).

## Guides

| Guide | Назначение |
|-------|-----------|
| [dod.md](guides/dod.md) | Чеклист Definition of Done |
| [environment-setup.md](guides/environment-setup.md) | Настройка локального окружения |
| [logging.md](guides/logging.md) | Конвенции логирования |
| [archiving-and-temp.md](guides/archiving-and-temp.md) | Политика архивации и временных файлов |

## Доменная документация

| Документ | Назначение |
|----------|-----------|
| [database_docs/DATABASE_REFERENCE.md](../database_docs/DATABASE_REFERENCE.md) | Полный справочник схем БД |
| [database_docs/DATABASE_WORKPLAN.md](../database_docs/DATABASE_WORKPLAN.md) | Открытые вопросы по БД |
| [database_docs/DATA_QUALITY_NOTES.md](../database_docs/DATA_QUALITY_NOTES.md) | Известные проблемы качества данных |

## Документация суб-проектов

| Проект | Документация |
|--------|-------------|
| Telegram Bot | [bot/GET_BOT_TOKEN.md](../bot/GET_BOT_TOKEN.md) |
| SKU Database | [wookiee_sku_database/README.md](../wookiee_sku_database/README.md) |

## Правило

Читай ТОЛЬКО те документы, которые релевантны твоей текущей задаче. Не загружай всё подряд.
