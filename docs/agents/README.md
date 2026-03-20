# Wookiee Agents and Runtime Modules

## Agent Definition

Агент — это автономная система (LLM + playbook + tools + memory). Бот — только интерфейс.

## Active Registry

| Компонент | Статус | Назначение | Путь |
|---|---|---|---|
| [Олег](telegram-bot.md) | Активен | Финансовый AI-агент (аналитика, отчёты, рекомендации) | `agents/oleg/` |
| ETL Pipeline | Активен | ETL и управление данными маркетплейсов | `services/etl/` |
| [WB Localization](mp-localization.md) | Активен | Сервис локализации WB (расчёт + экспорт) | `services/wb_localization/` |
| [Analytics Engine](analytics-engine.md) | Активен | Аналитический контур и метрики | `agents/oleg/services/` |

## Retired

| Компонент | Статус | Архив |
|---|---|---|
| Людмила (CRM) | Retired | `docs/archive/agents/lyudmila-bot.md` |
| Vasily agent runtime | Retired | `docs/archive/retired_agents/vasily_agent_runtime/` |
