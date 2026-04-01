# Phase 5: Верификация - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Все 8 типов отчётов запущены на реальных данных, проверены по критериям качества (полнота, глубина, точность, формат) и доведены до уровня эталонов. Эталоны — лучшие отчёты за последний месяц из Notion. Каждый тип отчёта проходит цикл: генерация → проверка → исправление → повторная генерация, пока качество не будет приемлемым.

</domain>

<decisions>
## Implementation Decisions

### Выбор эталонов (VER-02)
- **D-01:** Claude автономно находит лучшие отчёты за последний месяц в Notion для каждого из 8 типов
- **D-02:** Критерии отбора эталонов: длина, полнота секций, наличие реальных данных (не заглушек), глубина анализа
- **D-03:** Формат хранения эталонов — Claude решает (Notion-ссылки или локальные markdown-копии)

### Критерии качества
- **D-04:** 4 равнозначных критерия качества отчёта:
  1. **Полнота данных** — все секции заполнены реальными цифрами, нет заглушек
  2. **Глубина анализа** — monthly содержит P&L + юнит-экономику + стратегию; weekly — тренды и гипотезы; daily — компактную сводку
  3. **Точность цифр** — ключевые метрики (выручка, заказы, ДРР) совпадают с данными в БД
  4. **Формат и читаемость** — toggle-заголовки, единообразная структура, русский язык, профессиональный вид
- **D-05:** Проверка точности — SQL-запросы к БД для сверки ключевых метрик (выручка, количество заказов, ДРР). Плюс проверка адекватности (числа в разумных диапазонах, нет нолей/миллиардов)
- **D-06:** Специфика по типам:
  - Финансовые (daily/weekly/monthly): выручка WB+Ozon, заказы, маржа, ДРР с разбивкой
  - Маркетинговые (weekly/monthly): кампании, CTR, ДРР, бюджет
  - Воронка: конверсии по этапам
  - ДДС: поступления/списания по категориям
  - Локализация: логистические расходы WB

### Процесс верификации
- **D-07:** Последовательно по одному типу с чекпоинтом — генерация → проверка → фикс → повторная генерация → следующий тип
- **D-08:** Порядок: daily → weekly → monthly → marketing_weekly → marketing_monthly → funnel_weekly → finolog_weekly → localization_weekly
- **D-09:** Даты для тестирования: свежие данные — вчера для daily, прошлая неделя для weekly, прошлый месяц для monthly. Claude определяет конкретные даты с полными данными в БД
- **D-10:** Запуск через существующий runner: `python scripts/run_report.py --type <type> --date <date>`

### Исправление проблем
- **D-11:** Claude автономно диагностирует причину проблемы и фиксит там, где нужно:
  - Плейбуки/промпты (templates/*.md) — если LLM не следует инструкциям по структуре/глубине
  - Код pipeline/agents — если баги в передаче данных, ошибки в tools
  - Data layer — если данные не доставляются или неправильно агрегируются
- **D-12:** Количество итераций на тип — Claude решает исходя из прогресса. Нет жёсткого лимита

### Claude's Discretion
- Формат хранения эталонов (Notion-ссылки vs локальные markdown-копии)
- Конкретные SQL-запросы для сверки метрик
- Порог "приемлемого качества" для каждого типа отчёта
- Решение когда прекращать итерации (когда отчёт достаточно хорош)
- Стратегия исправления: менять плейбук, код или данные
- Использование LLM для проверки адекватности (опционально, если SQL недостаточно)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline (Phase 3/4 output — основной код)
- `agents/oleg/pipeline/report_pipeline.py` — `run_report()` — полный reliability flow
- `agents/oleg/pipeline/report_types.py` — ReportType enum, 8 конфигов с display_name_ru, hard_gates, template_path
- `agents/oleg/pipeline/gate_checker.py` — GateChecker, pre-flight проверка данных

### Runner (Phase 4 output)
- `scripts/run_report.py` — ручной запуск: `--type <type> --date <date>`, schedule режим

### Плейбуки (Phase 2 output — инструкции для LLM)
- `agents/oleg/playbooks/templates/daily.md` — шаблон ежедневного финансового
- `agents/oleg/playbooks/templates/weekly.md` — шаблон еженедельного финансового
- `agents/oleg/playbooks/templates/monthly.md` — шаблон ежемесячного финансового
- `agents/oleg/playbooks/templates/marketing_weekly.md` — шаблон маркетинг еженедельный
- `agents/oleg/playbooks/templates/marketing_monthly.md` — шаблон маркетинг ежемесячный
- `agents/oleg/playbooks/templates/funnel_weekly.md` — шаблон воронка продаж
- `agents/oleg/playbooks/templates/dds.md` — шаблон ДДС
- `agents/oleg/playbooks/templates/localization.md` — шаблон локализация

### Notion публикация
- `shared/notion_client.py` — NotionClient.sync_report(), upsert по период+тип

### Данные
- `shared/data_layer.py` — все DB-запросы (по правилам AGENTS.md)
- `agents/oleg/playbooks/data-map.md` — карта tool → данные → секции

### Правила проекта
- `AGENTS.md` — правила проекта
- `.planning/REQUIREMENTS.md` — требования RPT-01..08, VER-01, VER-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/run_report.py --type <type> --date <date>` — ручной запуск любого типа на любую дату
- `report_pipeline.run_report()` — полный flow с retry, validation, Notion publish
- `ReportType` enum + `REPORT_CONFIGS` — все 8 типов с metadata
- `_load_required_sections()` — парсит ## заголовки из шаблона для валидации
- `has_substantial_content()` — проверяет что отчёт не состоит только из заглушек
- `shared/data_layer.py` — SQL-запросы к БД для сверки метрик

### Established Patterns
- Pipeline: gates → retry → validate → Notion → Telegram (Phase 3)
- Runner: init_clients → build_orchestrator → run_report (Phase 4)
- Playbooks: core.md + templates/{type}.md + rules.md → PlaybookLoader.load(task_type)
- Notion MCP tools доступны для поиска эталонных отчётов

### Integration Points
- `run_report.py --type <type>` → entry point для генерации каждого отчёта
- Notion API → поиск эталонных отчётов, чтение содержимого
- `shared/data_layer.py` → SQL-сверка метрик
- `agents/oleg/playbooks/templates/*.md` → правки промптов если нужно

</code_context>

<specifics>
## Specific Ideas

- Сверка точности через SQL: выручка, заказы, ДРР — достать из БД и сравнить с цифрами в отчёте
- Эталоны = лучшие отчёты за последний месяц из Notion, отобранные по полноте и глубине
- Последовательная верификация: один тип за раз, фикс → перегенерация → следующий
- Финансовые отчёты первые (daily → weekly → monthly), потом маркетинг, потом спецтипы

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-verification*
*Context gathered: 2026-03-31*
