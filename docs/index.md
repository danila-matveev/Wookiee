# Wookiee — Documentation Index

## Quick Navigation

| Документ | Назначение |
|----------|-----------|
| [AGENTS.md](../AGENTS.md) | Универсальные правила (ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ) |
| [README.md](../README.md) | Обзор проекта и быстрый старт |
| [architecture.md](architecture.md) | Архитектура системы AI-агентов |
| [adr.md](adr.md) | Лог архитектурных решений |
| [infrastructure.md](infrastructure.md) | Production-сервер: подключение, деплой, мониторинг |
| [development-history.md](development-history.md) | Журнал последних изменений |

## AI-агенты

Каждый агент — автономная система с LLM, playbook, tools и memory. Бот — это интерфейс, агент — мозг.

| Агент | Статус | Документация |
|-------|--------|-------------|
| Олег (финансовый AI-агент) | Активен | [agents/telegram-bot.md](agents/telegram-bot.md) |
| Людмила (CRM AI-агент) | Активен | [agents/lyudmila-bot.md](agents/lyudmila-bot.md) |
| Ибрагим (дата-инженер) | Активен | [agents/ibrahim.md](agents/ibrahim.md) |
| Василий (логистический AI-агент) | В разработке | [agents/mp-localization.md](agents/mp-localization.md) |
| Analytics Engine | Активен | [agents/analytics-engine.md](agents/analytics-engine.md) |

Обзор агентной архитектуры: [agents/README.md](agents/README.md)

## Guides

| Guide | Назначение |
|-------|-----------|
| [dod.md](guides/dod.md) | Чеклист Definition of Done |
| [agent-principles.md](guides/agent-principles.md) | Принципы построения AI-агентов |
| [environment-setup.md](guides/environment-setup.md) | Настройка локального окружения |
| [logging.md](guides/logging.md) | Конвенции логирования |
| [archiving-and-temp.md](guides/archiving-and-temp.md) | Политика архивации и временных файлов |

## Доменная документация

| Документ | Назначение |
|----------|-----------|
| [DATABASE_REFERENCE.md](database/DATABASE_REFERENCE.md) | Полный справочник схем БД |
| [DATABASE_WORKPLAN.md](database/DATABASE_WORKPLAN.md) | Открытые вопросы по БД |
| [DATA_QUALITY_NOTES.md](database/DATA_QUALITY_NOTES.md) | Известные проблемы качества данных |

## Документация суб-проектов

| Проект | Документация |
|--------|-------------|
| SKU Database | [sku_database/README.md](../sku_database/README.md) |

## Правило

Читай ТОЛЬКО те документы, которые релевантны твоей текущей задаче. Не загружай всё подряд.
