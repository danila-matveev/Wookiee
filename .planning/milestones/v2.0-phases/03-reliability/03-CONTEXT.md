# Phase 3: Надёжность - Context

**Gathered:** 2026-03-31 (updated)
**Status:** Ready for planning

<domain>
## Phase Boundary

Система не публикует пустые/неполные отчёты и корректно обрабатывает ошибки на каждом этапе пайплайна: pre-flight проверка данных → retry при ошибках LLM → валидация полноты → publish в Notion → notify в Telegram.

Phase 3 строит **механизмы** (gate_checker, pipeline wrapper, retry, validation). Расписание запусков (cron, polling окно 6:00-18:00) — Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Pre-flight проверки данных
- **D-01:** Pre-flight проверяет свежесть данных в БД (Supabase PostgreSQL), НЕ в Google Sheets. Данные для отчётов берутся только из БД
- **D-02:** Ключевой индикатор готовности: поле `dateupdate` в каждой таблице БД. Если `dateupdate` = сегодня → данные свежие; если дата старая → ETL ещё не прошёл, отчёт не запускаем
- **D-03:** Проверяются все необходимые источники: финансовые данные, рекламные данные, заказы — по WB и Ozon
- **D-04:** Частичная готовность → запускаем то что готово. Если WB ready, Ozon нет — запускаем WB-отчёты. Ozon ждёт. Pre-flight сообщает что именно готово, что нет
- **D-05:** Hard gates = свежесть (dateupdate) + volume (заказов > 0). Soft gates = аномалии (данных меньше обычного, неожиданные нули) → предупреждение, не блокировка
- **D-06:** Механизм описан в SYSTEM.md как `pipeline/gate_checker.py` (3 hard + 3 soft data quality gates), но не реализован — создаётся в этой фазе
- **D-07:** gate_checker возвращает статус **по категориям** с процентом готовности: финансовые данные X%, рекламные данные X%, заказы X% — для информативных Telegram-сообщений (интерфейс для Phase 4)
- **D-08:** `get_article_unit_economics` (funnel tool) отсутствует в data-map.md — добавить в этой фазе при построении pre-flight checks

### Pipeline architecture
- **D-09:** Pipeline = wrapper СНАРУЖИ orchestrator. `pipeline.run(task_type)` → gate_check → orchestrator.run_chain → validate → publish → notify. Orchestrator не меняется, pipeline добавляет надёжность
- **D-10:** Retry = chain-level. Перезапускаем весь orchestrator.run_chain (до 2 раз согласно REL-02). Просто, надёжно, хоть и тратит токены

### Валидация полноты отчёта
- **D-11:** Обязательные секции для каждого типа отчёта берутся из шаблонов Phase 2 (playbook templates модули). Валидация проверяет наличие всех ожидаемых markdown-секций
- **D-12:** Если данных нет совсем — pre-flight предотвращает запуск. Если отчёт формируется, но часть данных недоступна — в секцию пишется объяснение человеческим языком + предложение решения (не технический error)
- **D-13:** Пустой отчёт не публикуется. Порядок: retry → graceful degradation (объяснение в секции) → публикация только если есть содержательные данные

### Порядок publish+notify
- **D-14:** Claude проверит текущую логику sync_report (upsert по период+тип) и убедится что она корректна для всех 8 типов отчётов (REL-06)
- **D-15:** Telegram-уведомление ТОЛЬКО после успешной публикации в Notion. При ошибке Telegram — Notion-публикация не откатывается (Notion = основной артефакт)

### Error UX
- **D-16:** Telegram сообщения о готовности данных: на русском языке, без техжаргона без пояснения. Формат:
  ```
  ✅ Данные за 29 марта загрузились:
  WB: заказов 1021, выручка обновлена
  Ozon: заказов 138, выручка обновлена
  📊 Запускаю отчёты: Daily фин, Weekly фин...
  ```
- **D-17:** Если данные ещё не готовы — сообщение каждые 2 часа: "⏳ Данные за [дата] пока не загрузились: финансовые 80%, рекламные 0%. Проверяю каждые 30 минут." (polling логика = Phase 4, но gate_checker должен поддерживать формат с процентами)
- **D-18:** После успешного retry — пользователь не знает о retry. Retry видно только в логах. В будущем — отдельная БД для workflow логов (не в этой фазе)
- **D-19:** При полном отказе (все retry исчерпаны) — лог + Telegram alert: "❌ Отчёт [тип] за [дата] не сгенерирован после 3 попыток. Причина: [описание]." В Notion ничего не публикуется

### Claude's Discretion
- Конкретные пороги для определения "пустого" LLM-ответа (длина, структура, наличие секций)
- Конкретные hard/soft gates для gate_checker (какие таблицы и поля проверять — на основе data-map.md)
- Формат process для pipeline.run (sync/async, error handling internals)
- Структура report_types registry

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Архитектура V2 оркестратора
- `agents/oleg/SYSTEM.md` — целевая архитектура, включая pipeline/ (gate_checker, report_pipeline, report_types)
- `agents/oleg/orchestrator/orchestrator.py` — текущий chain execution (нет pre-flight, нет retry)
- `agents/oleg/orchestrator/chain.py` — ChainResult dataclass (summary, detailed, telegram_summary)

### Плейбуки и data-map (Phase 2 output)
- `agents/oleg/playbooks/data-map.md` — карта tool → данные → секции. Основа для pre-flight checks. **NB: отсутствует get_article_unit_economics**
- `agents/oleg/playbooks/templates/` — 8 шаблонов с обязательными секциями для валидации
- `agents/oleg/playbooks/loader.py` — PlaybookLoader.load(task_type)

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
- `agents/oleg/watchdog/alerter.py` — Alerter с send_alert для Telegram. Можно переиспользовать для pre-flight notifications и error alerts
- `shared/notion_blocks.py` — remove_empty_sections уже фильтрует пустые секции из Markdown перед публикацией
- `agents/oleg/playbooks/loader.py` — PlaybookLoader.load(task_type) для получения списка обязательных секций

### Established Patterns
- Chain execution: orchestrator → agents → ChainResult (summary + detailed + telegram_summary)
- Diagnostics: gate_checker.check_all(marketplace) → GateResult с gates[].passed
- Notion: sync_report с per-report-type concurrency locks

### Integration Points
- `pipeline/` директория не существует — создаётся в этой фазе (gate_checker.py, report_pipeline.py, report_types.py)
- gate_checker подключается к DiagnosticRunner (уже принимает gate_checker параметр)
- pipeline.run(task_type) = новая entry point, вызывает orchestrator.run_chain внутри
- Валидация секций — между orchestrator output и Notion publish

</code_context>

<specifics>
## Specific Ideas

- Формат Telegram сообщения о готовности данных (D-16/D-17) — на русском, с процентами по категориям, без техжаргона
- Graceful degradation: текст ошибки должен быть человеческим языком с предложением решения, не техническим error
- Pipeline как wrapper: не трогаем orchestrator, вся reliability логика в отдельном слое
- gate_checker возвращает structured result с процентом готовности по категориям — интерфейс для Phase 4 polling

</specifics>

<deferred>
## Deferred Ideas

- **Расписание polling** (6:00-18:00 МСК, каждые 30 мин проверка, каждые 2 часа Telegram апдейт) — Phase 4
- **БД для workflow логов** (запись retry, ошибок, времени генерации) — отдельная задача после Phase 3
- Добавление LLM аналитики в ДДС/Локализацию — backlog

</deferred>

---

*Phase: 03-reliability*
*Context gathered: 2026-03-31*
