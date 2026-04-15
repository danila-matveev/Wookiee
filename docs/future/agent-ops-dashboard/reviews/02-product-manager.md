# Agent 2: Product Manager — Feature Matrix

## Текущие данные (что уже есть в бэкенде)

### SQLite StateStore (`agents/oleg/data/oleg.db`) — 6 таблиц:

| Таблица | Что хранит | Полезные поля |
|---------|-----------|---------------|
| `report_log` | Каждый запуск отчёта (success/error) | report_type, agent, status, created_at, duration_ms, cost_usd, chain_steps, error |
| `gate_history` | Pre-flight проверки качества данных | marketplace, gate_name, passed, is_hard, value, detail |
| `feedback_log` | Обратная связь от пользователя | user_id, feedback_text, decision, reasoning, playbook_update |
| `recommendation_log` | Advisor chain: сигналы + рекомендации | report_type, signals_count, recommendations_count, validation_verdict, validation_attempts, total_duration_ms |
| `prompt_suggestions` | Предложения по улучшению промптов | target, category, suggestion, priority, status |
| `op_state` | Key-value оперативное состояние | key (last_heartbeat, anomaly_last_alerts), value |

### In-memory (только при работающем процессе):

| Компонент | Что доступно | Persistence |
|-----------|-------------|-------------|
| CircuitBreaker (per agent) | state (closed/open/half_open), failure_count, failure_threshold, cooldown_sec, last_failure_time | Нет — сбрасывается при рестарте |
| AnomalyMonitor | thresholds, dedup state (через op_state), последние алерты | Dedup через op_state, пороги — конфиг |
| Watchdog | last_heartbeat (через op_state), diagnostic checks | Heartbeat в op_state |
| ReactLoop (per agent) | iteration count, tool call history, cost tracking | Только в рамках одного запуска |

### ChainResult (результат каждого запуска):

| Поле | Описание |
|------|----------|
| summary / detailed / telegram_summary | Тексты отчёта |
| steps[] | AgentStep: agent, instruction, result, cost_usd, duration_ms, iterations |
| total_steps, total_cost, total_duration_ms | Агрегированные метрики |
| review_issues_found, review_notes | Multi-model review результат |

### ReportType Registry (8 типов отчётов):
daily, weekly, monthly, marketing_weekly, marketing_monthly, funnel_weekly, finolog_weekly, localization_weekly — каждый с display_name_ru, period, marketplaces, hard_gates, template_path.

---

## MVP Features (Phase 1)

Принцип: показываем данные, которые **уже записываются в SQLite**, через read-only API endpoints.

| # | Feature | Data Source | Backend Work | Frontend Work | Value |
|---|---------|-------------|--------------|---------------|-------|
| 1 | **Summary KPI Cards** (4 карточки: активных агентов, отчётов сегодня, success rate 7d, расход за сутки) | `report_log` — COUNT/SUM за period + CB state в runtime | New endpoint: `GET /api/agents/summary` — один запрос, возвращает 4 метрики | Simple display (4 cards, как в mockup) | Мгновенное понимание состояния системы без Telegram |
| 2 | **Report Log Table** (история запусков с фильтрацией) | `report_log` — прямой SELECT с пагинацией | New endpoint: `GET /api/reports?status=&type=&days=` | Таблица с сортировкой + фильтры по статусу/типу | Заменяет ручной поиск в Telegram-чате «что упало?» |
| 3 | **Agent Fleet Status** (список агентов со статусом CB) | CircuitBreaker.status() per agent (in-memory) + last entry из `report_log` per agent | New endpoint: `GET /api/agents/fleet` — собирает CB status + last run per agent | Таблица как в mockup: имя, статус, последний запуск, runs, errors, avg time | Видно кто работает, кто в CB open, кто давно не запускался |
| 4 | **Gate Check History** (последние gate checks) | `gate_history` — SELECT last N | New endpoint: `GET /api/gates?days=7` | Simple table: время, marketplace, gate, passed/failed, detail | Понимание почему отчёт был пропущен (hard gate failure) |
| 5 | **Circuit Breaker Panel** (состояние CB каждого агента + кнопка Reset) | CircuitBreaker instances (in-memory) | New endpoints: `GET /api/agents/{name}/cb` + `POST /api/agents/{name}/cb/reset` | CB cards (6 шт, как в mockup): state, failure count, progress bar | **Критично**: единственный способ сбросить CB без SSH/restart |
| 6 | **Activity Feed** (live лог событий за день) | `report_log` + `gate_history` + `op_state` (anomaly alerts) — объединённый stream | New endpoint: `GET /api/activity?limit=50` — UNION из 3 таблиц, сортировка по времени | Scrollable feed (как в mockup): время, тип, статус, meta | Заменяет мониторинг Telegram-канала — всё в одном месте |
| 7 | **Daily Cost Breakdown** (расход LLM по агентам) | `report_log.cost_usd` — GROUP BY agent | New endpoint: `GET /api/costs/daily` | Bar chart per agent (как в mockup) | Контроль расходов, раннее обнаружение LLM-утечек |
| 8 | **Error Detail View** (просмотр ошибки конкретного запуска) | `report_log.error` + связанный chain log | New endpoint: `GET /api/reports/{id}` | Modal/slide-over с error text, chain steps, cost | Диагностика без SSH — понимание почему отчёт упал |

**Итого бэкенд MVP**: 7-8 REST endpoints, читающих из существующей SQLite + in-memory CB status.
**Нет новых таблиц.** Все данные уже записываются.

---

## v2 Features (Phase 2)

| # | Feature | Data Source | Backend Work | Frontend Work | Value |
|---|---------|-------------|--------------|---------------|-------|
| 1 | **Pipeline Timeline** (7-дневная визуализация: какие отчёты прошли/упали каждый день) | `report_log` — GROUP BY date, report_type | Endpoint + агрегация: `GET /api/pipelines/timeline?days=7` | Timeline grid (как в mockup): дни x типы отчётов, цветные блоки | Паттерны сбоев: «daily падает 3 дня подряд» |
| 2 | **Recommendation Analytics** (статистика advisor chain) | `recommendation_log` — signals_count, validation_verdict, pass_rate | New endpoint: `GET /api/advisor/stats?days=30` | Dashboard: pass rate trend, avg signals, top signal types | Оценка качества рекомендаций, ROI advisor chain |
| 3 | **Manual Report Trigger** (запуск отчёта из UI) | Новая очередь задач (in-memory или Redis) | New endpoint: `POST /api/reports/trigger` с task_type + date range. Нужен task queue | Form + button + progress indicator | Перезапуск без SSH, ad-hoc отчёты для руководителя |
| 4 | **Anomaly Monitor Dashboard** (текущие пороги, история алертов) | `op_state` (anomaly_last_alerts) + AnomalyMonitor.thresholds (in-memory) | New endpoint: `GET /api/anomalies` + `PUT /api/anomalies/thresholds` (сохранять в op_state) | Threshold editor + alert history table | Настройка чувствительности без деплоя кода |
| 5 | **Feedback History Viewer** (все фидбэки + решения) | `feedback_log` — прямой SELECT | New endpoint: `GET /api/feedback?limit=50` | Table + expandable rows: feedback, decision, playbook_update | Аудит: как система обрабатывала обратную связь |
| 6 | **Chain Step Viewer** (пошаговая визуализация цепочки агентов) | Требует **новую таблицу** `chain_steps_log` — сейчас AgentStep не персистируется | New table `chain_steps_log` (report_id FK, agent, instruction, result_preview, cost, duration, iterations) + endpoint | Interactive stepper: agent -> instruction -> result (collapsible) | Глубокая диагностика: на каком шаге что пошло не так |
| 7 | **Health Check Endpoint** (watchdog diagnostics) | Watchdog.check_health() (in-memory diagnostics) | New endpoint: `GET /api/health` — вызывает diagnostic_runner.diagnose() | Health page: component checklist (DB, LLM, Notion, Telegram) | Быстрая проверка при инциденте: что именно сломалось |
| 8 | **Cost Budget Alerts** | `report_log.cost_usd` — SUM per day + пороги в конфиге | New endpoint + budget config в op_state + alert logic | Budget bar с порогом + alert badge | Защита от LLM-перерасхода ($10+/день) |
| 9 | **Prompt Suggestions Viewer** | `prompt_suggestions` — SELECT with status filter | New endpoint: `GET /api/prompts/suggestions` | Table + approve/reject actions | Управление эволюцией промптов через UI |

---

## Backlog

| # | Feature | Description | Why defer |
|---|---------|-------------|-----------|
| 1 | **Real-time WebSocket Feed** | Замена polling на WS для activity feed и agent status | Требует WebSocket infra (сейчас нет WS слоя), архитектурное изменение |
| 2 | **Schedule Editor** (визуальный редактор расписания отчётов) | Drag-and-drop расписание: daily в 09:00, weekly — понедельник 10:00 и т.д. | Расписание сейчас в коде/n8n; нужна persistence + scheduler integration |
| 3 | **Agent Playground** (интерактивный тест агента с произвольным промптом) | Отправить произвольную инструкцию агенту, посмотреть step-by-step | Требует sandbox execution, изоляция от production, UI для tool call viewer |
| 4 | **Knowledge Base Management** (CRUD для KB patterns) | UI для просмотра/создания/верификации KB patterns (kb_patterns Supabase table) | Сейчас KB в Supabase; нужен отдельный API + авторизация |
| 5 | **Multi-tenant Agent Comparison** (A/B тестирование промптов) | Запуск двух версий агента параллельно, сравнение output + cost | Значительная архитектурная работа: параллельные chains, diff engine |
| 6 | **Notion Report Preview** (embedded preview отчёта до публикации) | Показать rendered markdown до отправки в Notion + approve/reject | Нужен review workflow, blocking pipeline step, UI editor |
| 7 | **Telegram Integration Panel** (управление TG-каналами из UI) | Выбор канала для отчёта, мьют для выходных, custom templates | Telegram bot config сейчас в .env; нужна persistence + validation |
| 8 | **Historical Cost Analytics** (стоимость по моделям, трендам, бюджет-план) | Графики cost over time, breakdown per model (GLM vs Gemini), прогноз бюджета | Нужна новая таблица с cost per LLM call (не per report); метрики model tier |
| 9 | **Anomaly Auto-Investigation** (при аномалии — автоматический drill-down) | При обнаружении аномалии автоматически запускать Researcher с целевым вопросом | Требует orchestration logic change + новый pipeline mode |

---

## Пользовательские сценарии

### US-1: Утренняя проверка
> Как оператор, я хочу открыть Dashboard в 09:15 и за 10 секунд понять: все ли отчёты сгенерировались, нет ли ошибок, не в CB ли агенты — **чтобы не листать 50 сообщений в Telegram**.

**MVP Features**: #1 (Summary KPI Cards), #3 (Fleet Status), #6 (Activity Feed)

### US-2: Диагностика сбоя
> Как оператор, я хочу при красной карточке "Success Rate 70%" кликнуть и увидеть какой именно отчёт упал, на каком шаге, с какой ошибкой — **чтобы понять нужен ли мой вмешательство или система восстановится**.

**MVP Features**: #2 (Report Log), #8 (Error Detail), #4 (Gate History)

### US-3: Сброс Circuit Breaker
> Как оператор, я хочу увидеть что Validator в CB Open, нажать кнопку Reset и увидеть что он перешёл в Closed — **чтобы не ходить на сервер по SSH**.

**MVP Feature**: #5 (CB Panel + Reset)

### US-4: Перезапуск отчёта
> Как оператор, я хочу перезапустить daily отчёт, который не сгенерировался утром из-за LLM timeout — **чтобы руководитель получил отчёт до обеда**.

**v2 Feature**: #3 (Manual Report Trigger)

### US-5: Контроль расходов
> Как оператор, я хочу видеть расходы за день/неделю с разбивкой по агентам — **чтобы заметить аномальный рост (зацикленный агент) до того как он сожрёт бюджет**.

**MVP Feature**: #7 (Daily Cost Breakdown), **v2**: #8 (Budget Alerts)

---

## Actions — что оператор должен уметь делать

### Критичные (MVP)

| Приоритет | Action | Текущий способ | Dashboard способ |
|-----------|--------|----------------|-----------------|
| P0 | **Reset Circuit Breaker** | SSH на сервер + restart процесса | Кнопка в CB Panel |
| P0 | **Просмотр ошибок** | Поиск в Telegram + SSH логи | Report Log + Error Detail |
| P0 | **Проверка здоровья системы** | Telegram heartbeat + SSH | Summary Cards + Fleet Status |

### Важные (v2)

| Приоритет | Action | Текущий способ | Dashboard способ |
|-----------|--------|----------------|-----------------|
| P1 | **Перезапуск отчёта** | SSH + manual script run | Кнопка Trigger Report |
| P1 | **Настройка anomaly порогов** | Изменение кода + deploy | UI threshold editor |
| P1 | **Просмотр chain шагов** | Не доступно (в логах частично) | Chain Step Viewer |
| P2 | **Approve/reject prompt suggestions** | Не доступно | Prompt Suggestions Viewer |

### Backlog Actions

| Приоритет | Action |
|-----------|--------|
| P3 | Изменение расписания отчётов |
| P3 | Управление KB patterns |
| P3 | A/B тест промптов |
| P3 | Preview отчёта до публикации |

---

## Интеграции

### Telegram
- **Текущее состояние**: Alerter отправляет сообщения через bot API. Конфигурация в `.env` (BOT_TOKEN, CHAT_ID).
- **MVP**: Read-only — показывать статус доставки TG-сообщений в Activity Feed (report_log.warnings содержит "Telegram failed").
- **v2**: Управление мьютом алертов (weekend silence), выбор канала для разных типов отчётов.
- **Backlog**: Полный TG management UI.

### Notion
- **Текущее состояние**: NotionClient.sync_report() — upsert по дате/типу. URL возвращается в pipeline.
- **MVP**: Показывать notion_url в Report Log (кликабельная ссылка на опубликованный отчёт).
- **v2**: Embedded preview (iframe или rendered markdown).
- **Backlog**: Bidirectional sync (правки в Notion отражаются в dashboard).

### Schedule (расписание отчётов)
- **Текущее состояние**: 8 типов в `REPORT_CONFIGS`, расписание через n8n / cron на сервере.
- **MVP**: Read-only — показывать «следующий запланированный запуск» на основе REPORT_CONFIGS period.
- **v2**: Visualisation — pipeline timeline (когда что запускалось, когда следующий).
- **Backlog**: Schedule editor с drag-and-drop.

### Watchdog / Health
- **Текущее состояние**: Watchdog пишет heartbeat в op_state, DiagnosticRunner проверяет DB, LLM, data freshness.
- **MVP**: Health indicator в header (зелёная/красная точка, как в mockup) — `GET /api/health` вызывает `check_health()`.
- **v2**: Detailed health page с breakdown по компонентам.

### OpenRouter / LLM
- **Текущее состояние**: 4 тира моделей (LIGHT/MAIN/HEAVY/FREE), cost tracking per report в report_log.
- **MVP**: Суммарный cost за день в KPI card.
- **v2**: Breakdown по моделям (какой tier сколько стоит), budget alerts.
- **Backlog**: Model usage analytics, auto-tier optimization.
