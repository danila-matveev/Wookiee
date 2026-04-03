# Phase 4: Запуск и доставка - Context

**Gathered:** 2026-03-30 (updated 2026-03-31)
**Status:** Ready for planning

<domain>
## Phase Boundary

Все 8 типов отчётов запускаются автоматически по расписанию через cron и доставляются в Notion + Telegram. Runner использует `report_pipeline.run_report()` из Phase 3 — полный reliability flow (gates → retry → validate → Notion → Telegram) уже реализован. Phase 4 добавляет: runner-скрипт, cron-расписание, polling логику, Docker интеграцию.

</domain>

<decisions>
## Implementation Decisions

### Runner-скрипт
- **D-01:** Один новый скрипт `scripts/run_report.py` с двумя режимами:
  - `--type daily|weekly|...` — ручной запуск одного типа (для дебага/перезапуска)
  - `--schedule` — автоматический режим: определяет какие типы запускать сегодня и запускает последовательно через pipeline
- **D-02:** Runner инициализирует все клиенты (LLM, Notion, Alerter, GateChecker) и вызывает `report_pipeline.run_report()` для каждого типа
- **D-03:** Старые `run_oleg_v2_reports.py` и `run_oleg_v2_single.py` удаляются — заменены новым runner
- **D-04:** Inline delivery (генерация → Notion → Telegram) уже реализован в report_pipeline — runner просто вызывает pipeline

### Cron + polling
- **D-05:** Cron запускает `run_report.py --schedule` каждые 30 минут в окне 07:00-18:00 МСК
- **D-06:** Скрипт сам проверяет gates (через pipeline) и пропускает если данных нет. Lock-файл чтобы не дублировать уже сделанные отчёты за день
- **D-07:** Уведомление-заглушка в Telegram: в 09:00 если данных нет ("Данные пока не готовы, отслеживаем"), далее каждые 2 часа (11:00, 13:00, 15:00, 17:00)
- **D-08:** Если к 18:00 данных нет — финальное уведомление "Данные не появились за день"
- **D-09:** После готовности данных — отчёты запускаются последовательно: финансовый → маркетинговый → воронка → логистика/локализация → ДДС (последний)
- **D-10:** Какие типы запускаются зависит от дня: daily каждый день, weekly в понедельник, monthly в понедельник 1-7 числа

### Docker интеграция
- **D-11:** Cron добавляется внутрь контейнера wookiee-oleg (entrypoint: install cron + crontab + cron -f)
- **D-12:** finolog-cron контейнер полностью удаляется из docker-compose.yml (сейчас disabled с profiles: ["disabled"])
- **D-13:** run_finolog_weekly.py удаляется — заменён pipeline + новый runner

### Telegram-уведомления
- **D-14:** Формат: краткая сводка (название типа + 3-5 ключевых метрик + ссылка на Notion)
- **D-15:** Каждый отчёт — отдельное сообщение в Telegram
- **D-16:** Только уведомления, без бота с командами (решение из pre-planning)

### Русские названия типов
- **D-17:** Русские названия уже реализованы в `report_types.py` (Phase 3) через `display_name_ru`. Маппинг:
  - `daily` → Ежедневный фин анализ
  - `weekly` → Еженедельный фин анализ
  - `monthly` → Ежемесячный фин анализ
  - `marketing_weekly` → Еженедельный маркетинговый анализ
  - `marketing_monthly` → Ежемесячный маркетинговый анализ
  - `funnel_weekly` → Воронка продаж (еженедельная)
  - `finolog_weekly` → Еженедельная сводка ДДС
  - `localization_weekly` → Анализ логистических расходов (еженедельный)

### Claude's Discretion
- Конкретная реализация crontab-файла (интервалы, формат строк)
- Формат и детали уведомлений-заглушек
- Структура runner-скрипта (классы, функции, error handling)
- Как извлекать ключевые метрики для краткой сводки в Telegram
- Реализация lock-файла для предотвращения повторных запусков
- Порядок и логика retry при неудачной публикации в Notion

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Проект
- `AGENTS.md` — правила проекта (DB через shared/data_layer.py, config через shared/config.py)
- `.planning/REQUIREMENTS.md` — требования SCHED-01..04

### Pipeline (Phase 3 output — ГЛАВНЫЙ ИНТЕРФЕЙС)
- `agents/oleg/pipeline/report_pipeline.py` — `run_report()` — полный reliability flow, runner вызывает именно его
- `agents/oleg/pipeline/gate_checker.py` — GateChecker, pre-flight проверка данных
- `agents/oleg/pipeline/report_types.py` — ReportType enum, REPORT_CONFIGS с display_name_ru, hard_gates, template_path

### V2 оркестратор
- `agents/oleg/orchestrator/orchestrator.py` — OlegOrchestrator (вызывается внутри pipeline, runner не трогает напрямую)
- `agents/oleg/orchestrator/chain.py` — ChainResult dataclass

### Notion публикация
- `shared/notion_client.py` — NotionClient с sync_report(), upsert логика
- `shared/notion_blocks.py` — конвертация MD → Notion blocks

### Telegram доставка
- `agents/oleg/watchdog/alerter.py` — Alerter.send_alert() — используется pipeline для Telegram

### Docker
- `deploy/docker-compose.yml` — текущая конфигурация (wookiee-oleg + finolog-cron[disabled])
- `deploy/Dockerfile` — текущий Dockerfile для wookiee-oleg

### Старые скрипты (будут удалены)
- `scripts/run_oleg_v2_reports.py` — старый ручной запуск (паттерн инициализации клиентов)
- `scripts/run_oleg_v2_single.py` — старый одиночный запуск
- `scripts/run_finolog_weekly.py` — broken V3 import (удаляется)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `report_pipeline.run_report()` — ПОЛНЫЙ pipeline (Phase 3): gates → retry → validate → Notion → Telegram. Runner просто вызывает его
- `ReportType` enum + `REPORT_CONFIGS` — все 8 типов с metadata (display_name_ru, period, marketplaces, hard_gates, template_path)
- `GateChecker.check_all()` — pre-flight проверка с structured result (can_run, hard_failed, soft_warnings)
- `Alerter.send_alert()` — Telegram уведомления через aiogram
- `NotionClient.sync_report()` — upsert в Notion с properties
- `scripts/run_oleg_v2_reports.py` — паттерн инициализации клиентов (LLM, Notion, agents) — скопировать логику в новый runner

### Established Patterns
- Pipeline принимает: report_type, target_date, orchestrator, notion_client, alerter, gate_checker
- ReportConfig.period определяет "daily"|"weekly"|"monthly" — runner использует для выбора типов по дню
- format_preflight_message() — готовый формат Telegram сообщений о статусе данных
- finolog-cron контейнер использует crontab в Docker: `apt-get install cron && echo "..." | crontab - && cron -f`

### Integration Points
- Runner → pipeline.run_report() (ЕДИНСТВЕННЫЙ entry point для генерации)
- Cron → runner → pipeline → orchestrator → Notion → Telegram
- Lock-файл (новый) предотвращает повторный запуск уже сделанных отчётов
- docker-compose.yml: entrypoint wookiee-oleg меняется на cron-based

</code_context>

<specifics>
## Specific Ideas

- Расписание привязано к готовности данных — "если данные готовы в 8 утра, отчёт формируется в 8 утра"
- Уведомления-заглушки каждые 2 часа чтобы команда не переживала что что-то сломалось
- ДДС отчёт всегда последний в цепочке
- Отчёт по логистике — это "логистика и локализация логистики", не просто "локализация"
- Lock-файл per report_type per date — чтобы при каждом запуске cron не переделывать уже опубликованные отчёты

</specifics>

<deferred>
## Deferred Ideas

- Алерты при резких изменениях метрик — v3.0 (ALERT-01)
- Telegram бот с командами — v3.0 (BOT-01)
- Watchdog мониторинг — v3.0 (ALERT-02)
- БД для workflow логов (retry, ошибки, время генерации) — отдельная задача

</deferred>

---

*Phase: 04-scheduling-delivery*
*Context gathered: 2026-03-30, updated: 2026-03-31*
