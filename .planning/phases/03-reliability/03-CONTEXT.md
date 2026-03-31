# Phase 3: Надёжность - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Система не публикует пустые/неполные отчёты и корректно обрабатывает ошибки на каждом этапе пайплайна: pre-flight проверка данных → retry при ошибках LLM → валидация полноты → publish в Notion → notify в Telegram.

</domain>

<decisions>
## Implementation Decisions

### Pre-flight проверки данных
- **D-01:** Pre-flight проверяет свежесть данных в БД (Supabase PostgreSQL), НЕ в Google Sheets. Данные для отчётов берутся только из БД
- **D-02:** Ключевой индикатор готовности: поле `dateupdate` в каждой таблице БД. Если `dateupdate` = сегодня → данные свежие; если дата старая → ETL ещё не прошёл, отчёт не запускаем
- **D-03:** Проверяются все необходимые источники: финансовые данные, рекламные данные, заказы — по WB и Ozon
- **D-04:** Если данные за целевой день неполные — отчёт за этот день не запускается; можно анализировать другие дни, за которые данные уже загружены
- **D-05:** Результат pre-flight отправляется в Telegram ("✅ Данные за X готовы: WB заказов N, выручка X%..." + список запускаемых отчётов) + запись в лог
- **D-06:** Механизм описан в SYSTEM.md как `pipeline/gate_checker.py` (3 hard + 3 soft data quality gates), но не реализован — создаётся в этой фазе

### Retry стратегия
- **D-07:** Claude определяет критерии "пустого/неполного" ответа LLM и стратегию retry (до 2 повторов, согласно REL-02)
- **D-08:** Claude выбирает оптимальный уровень retry (LLM-вызов или chain) на основе анализа кода orchestrator

### Валидация полноты отчёта
- **D-09:** Обязательные секции для каждого типа отчёта берутся из шаблонов Phase 2 (playbook templates модули). Валидация проверяет наличие всех ожидаемых markdown-секций
- **D-10:** Если данных нет совсем — pre-flight предотвращает запуск. Если отчёт формируется, но часть данных недоступна — в секцию пишется объяснение человеческим языком + предложение решения (не технический error)
- **D-11:** Пустой отчёт не публикуется. Порядок: retry → graceful degradation (объяснение в секции) → публикация только если есть содержательные данные

### Порядок publish+notify
- **D-12:** Claude проверит текущую логику sync_report (upsert по период+тип) и убедится что она корректна для всех 8 типов отчётов (REL-06)
- **D-13:** Claude определяет поведение при ошибке Telegram — Notion является основным артефактом

### Claude's Discretion
- Конкретные пороги для определения "пустого" LLM-ответа (длина, структура, наличие секций)
- Уровень retry: LLM-вызов vs chain перезапуск
- Поведение при Telegram failure после успешного Notion publish
- Конкретные hard/soft gates для gate_checker (какие таблицы и поля проверять)
- Формат Telegram-сообщения о готовности данных

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Архитектура V2 оркестратора
- `agents/oleg/SYSTEM.md` — целевая архитектура, включая pipeline/ (gate_checker, report_pipeline, report_types)
- `agents/oleg/orchestrator/orchestrator.py` — текущий chain execution (нет pre-flight, нет retry)
- `agents/oleg/orchestrator/chain.py` — ChainResult dataclass (summary, detailed, telegram_summary)

### Существующие компоненты надёжности
- `agents/oleg/watchdog/diagnostic.py` — DiagnosticRunner с gate_checker interface (check_all → gates[].passed)
- `agents/oleg/watchdog/watchdog.py` — Health monitoring, использует gate_checker
- `agents/oleg/watchdog/alerter.py` — Telegram alerting (send_alert, send_diagnostic_alert)

### Публикация и доставка
- `shared/notion_client.py` — NotionClient.sync_report (upsert по период+тип), _REPORT_TYPE_MAP (22 entries)
- `shared/notion_blocks.py` — md_to_notion_blocks, remove_empty_sections

### Правила проекта
- `AGENTS.md` — DB только через shared/data_layer.py, config через shared/config.py
- `.planning/REQUIREMENTS.md` — требования REL-01..REL-07

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared/notion_client.py` — upsert уже работает (sync_report → _find_existing_page по период+тип). Покрывает REL-06 базово
- `agents/oleg/watchdog/diagnostic.py` — DiagnosticRunner с interface для gate_checker (check_all, DiagCheck, DiagnosticReport). gate_checker можно создать, подключить к существующему interface
- `agents/oleg/watchdog/alerter.py` — Alerter с send_alert для Telegram. Можно переиспользовать для pre-flight notifications
- `shared/notion_blocks.py` — remove_empty_sections уже фильтрует пустые секции из Markdown перед публикацией

### Established Patterns
- Chain execution: orchestrator → agents → ChainResult (summary + detailed + telegram_summary)
- Diagnostics: gate_checker.check_all(marketplace) → GateResult с gates[].passed
- Notion: sync_report с per-report-type concurrency locks

### Integration Points
- `pipeline/` директория не существует — создаётся в этой фазе (gate_checker.py, report_pipeline.py, report_types.py)
- gate_checker подключается к DiagnosticRunner (уже принимает gate_checker параметр)
- Retry логика встраивается в orchestrator.run_chain или в pipeline wrapper
- Валидация секций — между orchestrator output и Notion publish

</code_context>

<specifics>
## Specific Ideas

- Формат Telegram pre-flight сообщения проверен пользователем:
  ```
  ✅ Данные за 29 марта готовы
  WB: | заказов 1021 | выручка 102% | маржа 100%
  OZON: | заказов 138 | выручка 114% | маржа 100%
  📊 Запускаю: Daily фин, Weekly фин, Weekly маркетинг, Weekly воронка, Weekly ценовой
  ```
- Graceful degradation: текст ошибки должен быть человеческим языком с предложением решения, не техническим error

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-reliability*
*Context gathered: 2026-03-30*
