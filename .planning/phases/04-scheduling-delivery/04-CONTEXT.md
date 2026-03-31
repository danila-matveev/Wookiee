# Phase 4: Запуск и доставка - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Все 8 типов отчётов запускаются автоматически по расписанию через cron и доставляются в Notion + Telegram. Runner проверяет готовность данных (pre-flight из Phase 3), генерирует отчёт через V2 оркестратор, публикует в Notion, верифицирует публикацию, и отправляет Telegram-уведомление.

</domain>

<decisions>
## Implementation Decisions

### Cron-архитектура
- **D-01:** System crontab внутри Docker-контейнера wookiee-oleg (как finolog-cron сейчас)
- **D-02:** Один универсальный runner-скрипт (`scripts/run_report.py`) с аргументом `--type` для всех 8 типов
- **D-03:** Inline delivery: runner генерирует → публикует в Notion → верифицирует → отправляет Telegram. Один процесс на один отчёт.
- **D-04:** Верификация после Notion-публикации: прочитать страницу из Notion, убедиться что блоки на месте и контент не пустой. Только после этого Telegram.

### Расписание отчётов
- **D-05:** Расписание привязано к готовности данных, не к фиксированным часам
- **D-06:** Первая проверка данных: 07:00 МСК, retry каждые 30 мин до 18:00 МСК
- **D-07:** Уведомление-заглушка в Telegram: в 09:00 если данных нет ("Данные пока не готовы, отслеживаем"), далее каждые 2 часа (11:00, 13:00, 15:00, 17:00)
- **D-08:** Если к 18:00 данных нет — финальное уведомление "Данные не появились за день"
- **D-09:** После готовности данных — отчёты запускаются последовательно: финансовый → маркетинговый → воронка → логистика/локализация → ДДС (последний)
- **D-10:** Какие типы запускаются зависит от дня: daily каждый день, weekly в понедельник, monthly в понедельник 1-7 числа

### Telegram-уведомления
- **D-11:** Формат: краткая сводка (название типа + 3-5 ключевых метрик + ссылка на Notion)
- **D-12:** Каждый отчёт — отдельное сообщение в Telegram
- **D-13:** Только уведомления, без бота с командами (решение из pre-planning)

### Русские названия типов
- **D-14:** Маппинг русских названий для Notion и Telegram:
  - `daily` → Финансовый отчёт (ежедневный)
  - `weekly` → Финансовый отчёт (еженедельный)
  - `monthly` → Финансовый отчёт (ежемесячный)
  - `marketing_weekly` → Маркетинговый отчёт (еженедельный)
  - `marketing_monthly` → Маркетинговый отчёт (ежемесячный)
  - `funnel_weekly` → Воронка продаж (еженедельный)
  - `finolog_weekly` → ДДС отчёт (еженедельный)
  - `localization_weekly` → Логистика и локализация (еженедельный)

### Claude's Discretion
- Конкретная реализация crontab-файла (интервалы, формат строк)
- Формат и детали уведомлений-заглушек
- Структура runner-скрипта (классы, функции, error handling)
- Как извлекать ключевые метрики для краткой сводки в Telegram
- Порядок и логика retry при неудачной публикации в Notion

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Проект
- `AGENTS.md` — правила проекта (DB через shared/data_layer.py, config через shared/config.py)
- `.planning/REQUIREMENTS.md` — требования SCHED-01..04

### V2 оркестратор
- `agents/oleg/orchestrator/orchestrator.py` — OlegOrchestrator, основной класс генерации отчётов
- `scripts/run_oleg_v2_reports.py` — текущий ручной запуск V2 отчётов (паттерн для runner)

### Notion публикация
- `shared/notion_client.py` — NotionClient с sync_report(), upsert логика, properties, маппинг типов
- `shared/notion_blocks.py` — конвертация MD → Notion blocks

### Telegram доставка
- `agents/v3/delivery/telegram.py` — текущая реализация Telegram (будет удалена в Phase 1, но паттерн полезен)

### Docker
- `deploy/docker-compose.yml` — текущая конфигурация контейнеров

### Pre-flight (Phase 3)
- Pre-flight проверка данных будет реализована в Phase 3 (REL-01) — runner должен использовать эту логику

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared/notion_client.py`: NotionClient.sync_report() — полная логика upsert в Notion с properties, готова к использованию
- `shared/notion_blocks.py`: md_to_notion_blocks() — конвертация markdown в Notion API формат
- `agents/oleg/orchestrator/orchestrator.py`: OlegOrchestrator — V2 оркестратор для генерации отчётов
- `scripts/run_oleg_v2_reports.py`: паттерн запуска V2 отчётов с delivery

### Established Patterns
- NotionClient уже имеет `_REPORT_TYPE_MAP` с 22 типами — нужно обновить для русских названий
- Telegram delivery через aiogram Bot с HTML parse mode и split на 4000 char chunks
- finolog-cron контейнер уже использует system crontab в Docker — проверенный паттерн

### Integration Points
- Runner вызывает OlegOrchestrator.run() → получает markdown отчёт
- Отчёт передаётся в NotionClient.sync_report() → получает page_url
- page_url передаётся в Telegram delivery → уведомление с ссылкой
- Pre-flight (из Phase 3) проверяет данные перед запуском оркестратора

</code_context>

<specifics>
## Specific Ideas

- Расписание должно быть привязано к готовности данных, а не к фиксированным часам — "если данные готовы в 8 утра, отчёт формируется в 8 утра"
- Уведомления-заглушки каждые 2 часа чтобы команда не переживала что что-то сломалось
- ДДС отчёт всегда последний в цепочке
- Отчёт по логистике — это "логистика и локализация логистики", не просто "локализация"

</specifics>

<deferred>
## Deferred Ideas

- Починка finolog-cron скрипта (run_finolog_weekly.py) — уже отложено из Phase 1
- Алерты при резких изменениях метрик — v3.0 (ALERT-01)
- Telegram бот с командами — v3.0 (BOT-01)
- Watchdog мониторинг — v3.0 (ALERT-02)

</deferred>

---

*Phase: 04-scheduling-delivery*
*Context gathered: 2026-03-30*
