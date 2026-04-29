# Перестройка ИИ-агента Олег v2 — План

## Контекст

Олег — ИИ финансовый аналитик бренда Wookiee — перестал создавать отчёты с 18 февраля 2026. За 5 дней ни одного дневного/недельного отчёта, никаких уведомлений в Telegram.

**Корневая причина:** 18 февраля ужесточили порог маржинальности в DataFreshnessService (50% → 80%). Gate 6 блокирует ВСЕ отчёты. Система молча "умерла" — нет эскалации, нет деградации, нет алерта.

**Архитектурные проблемы:**
1. Все 6 гейтов — hard-блокеры (all-or-nothing)
2. Нет эскалации при многодневном сбое
3. Recovery тоже заблокирован теми же гейтами
4. Crash в tool убивает весь ReAct loop (нет try-catch)
5. Feedback handler не подключён
6. Один монолитный агент — нет специализации (reporting ≠ deep analysis ≠ learning)

## Решение: Олег-оркестратор с коллаборативными суб-агентами

Олег становится **оркестратором**, который ведёт **диалог между суб-агентами** для достижения наилучшего результата. Не просто "маршрутизация к одному агенту", а **цепочка**: один проанализировал → другой поставил гипотезу → первый перепроверил данные → Олег подтвердил и синтезировал.

**Модель взаимодействия — collaborative chain:**

```
┌──────────────────────────────────────────────────────────────────┐
│                     Олег (Orchestrator LLM)                       │
│                                                                   │
│  Ведёт диалог между агентами. Решает:                            │
│  • Кого вызвать следующим                                        │
│  • Какой контекст передать                                       │
│  • Достаточно ли данных для финального ответа                    │
│  • Когда остановиться (max 5 шагов цепочки)                     │
│                                                                   │
│  Пример цепочки для еженедельного отчёта:                        │
│                                                                   │
│  ① Reporter: "Маржа -12%, ДРР вырос с 8% до 14%"               │
│  ② Олег → Researcher: "Почему ДРР вырос? Проверь рекламу."      │
│  ③ Researcher: "Гипотеза: рост расходов на внутр. рекламу WB    │
│     (+40%), при этом заказы выросли только на +5%"               │
│  ④ Олег → Reporter: "Подтверди цифры рекламы и заказов"         │
│  ⑤ Reporter: "Подтверждено: реклама 285K→398K, заказы 1420→1490"│
│  ⑥ Олег: Синтез финального отчёта с подтверждённой гипотезой    │
└──────────────────────────────────────────────────────────────────┘
           │              │              │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼───────┐
    │  Reporter   │ │ Researcher │ │  Quality   │
    │  Agent      │ │ Agent      │ │  Agent     │
    ├─────────────┤ ├────────────┤ ├────────────┤
    │ Сбор данных │ │ Гипотезы   │ │ Обработка  │
    │ и отчёты по │ │ глубокий   │ │ feedback   │
    │ проверенным │ │ анализ     │ │ улучшение  │
    │ формулам    │ │ "почему?"  │ │ playbook   │
    ├─────────────┤ ├────────────┤ ├────────────┤
    │ Tools:      │ │ Tools:     │ │ Tools:     │
    │ 12 SQL      │ │ WB API     │ │ playbook   │
    │ (data_layer)│ │ OZON API   │ │ reader/    │
    │ 9 price     │ │ МойСклад   │ │ writer     │
    │ tools       │ │ correlation│ │ report     │
    │             │ │ elasticity │ │ history    │
    │             │ │ trend anal │ │ verifier   │
    └─────────────┘ └────────────┘ └────────────┘
```

**Три суб-агента — реально разные роли:**

| Суб-агент | Роль | Отличие |
|-----------|------|---------|
| **Reporter** | Сбор данных, структурированные отчёты, подтверждение фактов цифрами | Tools: SQL через data_layer.py. Playbook: 5 рычагов маржи. |
| **Researcher** | Глубокий анализ "почему?". Гипотезы о связях маркетинг↔цена↔остатки↔заказы. | Tools: WB/OZON/МойСклад API, корреляции, эластичность. |
| **Quality** | Обработка ОС от команды. Верификация замечаний. Обновление playbook. | Tools: playbook R/W, история отчётов, лог feedback. |

**Суб-агенты — не отдельные процессы.** Это разные "профили" внутри одного Python-процесса: разный system prompt, разный набор tools. Олег вызывает их последовательно, передавая контекст от одного к другому.

### Типы задач и режимы оркестрации

**Логика аналитики одинаковая** для любого периода (день/неделя/месяц). Цель всегда одна: **максимизация маржинальной прибыли и маржинальности**. Меняется только временной отрезок.

Помимо регулярных отчётов, пользователь может задать **любой вопрос** через Telegram: ABC-анализ, анализ воронки маркетинга, план-факт, анализ конкретной модели, сравнение периодов — всё что нужно для бизнес-решений.

| Задача | Как приходит | Цепочка агентов | ~Стоимость |
|--------|-------------|----------------|-----------|
| **Регулярный отчёт** (день/неделя/месяц) | Scheduler | Reporter → (аномалия?) Researcher → verify → синтез | $0.04-0.12 |
| **Любой вопрос** ("почему маржа упала?", "ABC-анализ", "воронка WB") | Telegram | Олег → нужные агенты в цепочке | $0.04-0.12 |
| **Feedback** ("отчёт неправильный") | /feedback или reply | Quality → Reporter verify → решение | $0.06-0.08 |

**Smart escalation для регулярных отчётов:**
1. Reporter собирает данные и формирует отчёт
2. Олег проверяет: есть аномалия? (маржа Δ>10%, ДРР Δ>30%)
   - Нет → готово (1 шаг, быстро и дёшево)
   - Да → Researcher объясняет "почему" → Reporter верифицирует → финальный отчёт с гипотезой

**Для произвольных вопросов** Олег сам решает какую цепочку выстроить:
- "ABC-анализ по маржинальности" → Reporter → Олег синтез
- "Почему заказы упали на Wendy?" → Researcher (гипотезы) → Reporter (верификация) → синтез
- "Проанализируй воронку WB" → Reporter (трафик) → Researcher (связки) → синтез

---

## Документация системы

При создании v2 создаются следующие документы:

### Главный документ (визуальная архитектура)
**`agents/oleg_v2/SYSTEM.md`** — единый документ с полным описанием системы:
- Визуальная диаграмма архитектуры (orchestrator + sub-agents)
- Как работают collaborative chains (примеры цепочек)
- Режимы оркестрации (регулярные отчёты, произвольные запросы, feedback)
- Общая структура файлов
- Конфигурация и переменные окружения
- Деплой и запуск

### Документы суб-агентов (по одному на агента)
Каждый суб-агент имеет свой `AGENT_SPEC.md`:

| Документ | Содержание |
|----------|-----------|
| **`agents/oleg_v2/agents/reporter/AGENT_SPEC.md`** | Миссия, tools (12 SQL + 9 price), system prompt, формат отчётов, тестовые сценарии |
| **`agents/oleg_v2/agents/researcher/AGENT_SPEC.md`** | Миссия, tools (API + статистика), гипотезный фреймворк, примеры анализа |
| **`agents/oleg_v2/agents/quality/AGENT_SPEC.md`** | Миссия, tools (playbook R/W), процесс обработки feedback, критерии accept/reject |

### Playbook (живой документ)
**`agents/oleg_v2/playbook.md`** — бизнес-правила (из v1). Обновляется Quality Agent при обработке feedback.

## Notion: сохранение и обновление отчётов

Текущий [notion_service.py](agents/oleg/services/notion_service.py) уже поддерживает **upsert**:
- Ищет страницу по "Период начала" + "Период конца"
- Если найдена → **перезаписывает** (удаляет контент + вставляет новый)
- Если нет → создаёт новую страницу

**В v2 сохраняем это поведение + расширяем:**
- Все отчёты (регулярные + по запросу) сохраняются в Notion DB
- При повторной генерации за тот же период → перезаписывается существующая страница
- Свойство "Источник" показывает: "Reporter (auto)", "Researcher (chain)", "Quality (feedback)"
- Свойство "Тип анализа" сохраняется: "Ежедневный фин анализ", "Еженедельный фин анализ", "Глубокий анализ", etc.
- **Новое**: добавить свойство "Chain steps" (число шагов цепочки) для мониторинга

---

## Фаза 0: Немедленный фикс (день 1)

**Цель:** восстановить генерацию отчётов прямо сейчас, до полной перестройки.

1. Снизить порог margin fill до 50% в [data_freshness_service.py](agents/oleg/services/data_freshness_service.py):339
2. Добавить Telegram-алерт при 3+ последовательных неудачах гейтов
3. Проверить Docker-контейнеры на сервере через SSH (`docker ps`, `docker logs`)
4. Сгенерировать пропущенные отчёты за 19-22 февраля

**Файлы:** [data_freshness_service.py](agents/oleg/services/data_freshness_service.py), [agent_runner.py](agents/oleg/agent_runner.py)

---

## Фаза 1: Архитектура Олег v2 (дни 2-5)

### 1.1 Единый процесс (2 контейнера → 1)

```
wookiee-oleg (один Docker-контейнер)
├── aiogram Dispatcher (Telegram polling)
├── APScheduler (cron jobs для отчётов)
├── Watchdog (health monitoring)
├── Orchestrator + 3 Sub-agents (в памяти)
└── SQLite (reports, state, feedback)
```

Отчёт готов → `bot.send_message()` напрямую. Нет delivery queue, нет polling.

### 1.2 Структура файлов

```
agents/oleg_v2/
├── __init__.py
├── __main__.py                      # Единственный entrypoint
├── config.py                        # Конфигурация
├── app.py                           # OlegApp: bot + scheduler + watchdog + orchestrator
│
├── orchestrator/                    # Оркестратор Олег
│   ├── __init__.py
│   ├── orchestrator.py              # Collaborative chain: диалог между суб-агентами
│   ├── chain.py                     # ChainResult, AgentStep, chain execution logic
│   └── prompts.py                   # System prompt оркестратора (decide_next_step, synthesize)
│
├── agents/                          # Суб-агенты
│   ├── __init__.py
│   ├── base_agent.py                # Базовый класс: ReAct loop + tools + system prompt
│   ├── reporter/                    # Reporter Agent — отчёты
│   │   ├── __init__.py
│   │   ├── agent.py                 # ReporterAgent(BaseAgent)
│   │   ├── tools.py                 # 12 финансовых + 9 ценовых tools
│   │   └── prompts.py               # System prompt Reporter
│   ├── researcher/                  # Researcher Agent — глубокий анализ
│   │   ├── __init__.py
│   │   ├── agent.py                 # ResearcherAgent(BaseAgent)
│   │   ├── tools.py                 # API tools + статистические tools
│   │   └── prompts.py               # System prompt Researcher
│   └── quality/                     # Quality Agent — feedback + обучение
│       ├── __init__.py
│       ├── agent.py                 # QualityAgent(BaseAgent)
│       ├── tools.py                 # playbook R/W, verifier, feedback log
│       └── prompts.py               # System prompt Quality
│
├── executor/                        # Общий ReAct движок (для всех агентов)
│   ├── __init__.py
│   ├── react_loop.py                # ReAct loop с try-catch, timeout, compression
│   └── circuit_breaker.py           # Circuit breaker для LLM/tool вызовов
│
├── pipeline/                        # Pipeline генерации отчётов
│   ├── __init__.py
│   ├── gate_checker.py              # Гейты: hard + soft
│   ├── report_pipeline.py           # gate → orchestrator → format → deliver
│   └── report_types.py              # Определения типов отчётов
│
├── bot/                             # Telegram-интерфейс
│   ├── __init__.py
│   ├── telegram_bot.py              # Bot setup, middleware, прямая доставка
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── auth.py                  # (перенос из v1)
│   │   ├── menu.py                  # (перенос из v1)
│   │   ├── reports.py               # Отчёты (регулярные + по запросу)
│   │   └── feedback.py              # НОВЫЙ: /feedback + inline кнопки + reply
│   └── formatter.py                 # ReportFormatter
│
├── watchdog/                        # Операционная надёжность + самодиагностика
│   ├── __init__.py
│   ├── watchdog.py                  # Dead man's switch + timeline + эскалация
│   ├── diagnostic.py                # DiagnosticRunner: автодиагностика при сбое
│   └── alerter.py                   # Telegram-алерты с результатами диагностики
│
├── storage/                         # Хранилище
│   ├── __init__.py
│   ├── report_storage.py            # Отчёты
│   ├── state_store.py               # Operational state (гейты, heartbeats)
│   └── feedback_store.py            # Лог feedback + решения Quality Agent
│
├── services/                        # Переиспользуемые сервисы
│   ├── notion_service.py            # (из v1)
│   ├── time_utils.py                # (из v1)
│   └── price_analysis/              # (из v1 целиком)
│
├── playbook.md                      # Бизнес-правила (живой документ, обновляется Quality Agent)
├── data/                            # SQLite, auth
└── logs/
```

### 1.3 Оркестратор — collaborative chain

Олег-оркестратор — это **LLM, который ведёт цепочку** между суб-агентами. Он решает:
- Кого вызвать следующим
- Какой контекст передать от предыдущего агента
- Достаточно ли данных для финального ответа
- Когда остановиться (лимит: 5 шагов цепочки)

**Реализация — `orchestrator/orchestrator.py`:**

```python
class OlegOrchestrator:
    """Олег ведёт диалог между суб-агентами для наилучшего результата."""

    async def run_chain(self, task: str, task_type: str, context: dict) -> ChainResult:
        """
        Запускает цепочку агентов. Олег (LLM) на каждом шаге решает:
        - next_agent: кого вызвать
        - instruction: что именно попросить
        - done: достаточно ли данных для финального ответа
        """
        chain_history = []  # Результаты всех шагов

        for step in range(MAX_CHAIN_STEPS):  # max 5
            # Олег решает следующий шаг
            decision = await self.llm.decide_next_step(
                task=task,
                chain_history=chain_history,
                available_agents=["reporter", "researcher", "quality"]
            )

            if decision.done:
                # Олег синтезирует финальный ответ из всех шагов
                return await self.synthesize(task, chain_history)

            # Вызвать суб-агента с инструкцией от Олега
            agent = self.agents[decision.next_agent]
            result = await agent.execute(
                instruction=decision.instruction,
                context=chain_history  # Агент видит всё что было до него
            )
            chain_history.append(AgentStep(
                agent=decision.next_agent,
                instruction=decision.instruction,
                result=result
            ))

        # Лимит шагов — синтезировать из того что есть
        return await self.synthesize(task, chain_history)
```

**Цепочки для разных задач:**

**Дневной отчёт (smart escalation):**
```
① Reporter: собирает данные, формирует отчёт с 5 рычагами маржи
② Олег: проверяет — есть аномалия? (маржа Δ>10%, ДРР Δ>30%)
   Нет аномалии → финальный отчёт (1 шаг, ~$0.04)
   Есть аномалия → продолжить:
③ Researcher: "Почему {аномалия}? Сформируй гипотезы."
④ Reporter: "Подтверди цифры для гипотез Researcher."
⑤ Олег: Синтез отчёта с подтверждённой гипотезой (~$0.10)
```

**Недельный отчёт (всегда полная цепочка):**
```
① Reporter: недельные данные, тренды, 5 рычагов
② Researcher: гипотезы о трендах, причинно-следственные связи
③ Reporter: верификация гипотез цифрами
④ Олег: синтез с рекомендациями (~$0.12)
```

**Произвольный вопрос "почему маржа упала?":**
```
① Researcher: формирует 2-3 гипотезы из API/данных
② Reporter: проверяет каждую гипотезу через SQL
③ Олег: подтверждённые гипотезы → ответ пользователю (~$0.10)
```

**Feedback "отчёт неправильный":**
```
① Quality: анализирует замечание, определяет что проверить
② Reporter: перепроверяет данные (SQL-запросы)
③ Quality: сопоставляет, решает accept/reject, обновляет playbook
④ Олег: уведомляет пользователя о решении (~$0.08)
```

### 1.4 Суб-агенты — детальное описание

#### Reporter Agent (из текущего Олега, захарденный)

**Роль:** Структурированные финансовые отчёты по проверенным формулам.

**System prompt:** Текущий playbook.md + правила 5 рычагов маржи.

**Tools (из v1, проверены):**
| Tool | Источник данных |
|------|----------------|
| `get_brand_finance` | PostgreSQL → data_layer.py |
| `get_channel_finance` | PostgreSQL → data_layer.py |
| `get_model_breakdown` | PostgreSQL → data_layer.py |
| `get_daily_trend` | PostgreSQL → data_layer.py |
| `get_advertising_stats` | PostgreSQL → data_layer.py |
| `get_model_advertising` | PostgreSQL → data_layer.py |
| `get_orders_by_model` | PostgreSQL → data_layer.py |
| `get_margin_levers` | PostgreSQL → data_layer.py |
| `get_weekly_breakdown` | PostgreSQL → data_layer.py |
| `validate_data_quality` | PostgreSQL → data_layer.py |
| `get_product_statuses` | Supabase → REST API |
| `calculate_metric` | Python вычисления |
| + 9 price tools | PostgreSQL + Python |

**Стоимость:** ~$0.03-0.06 за отчёт (как сейчас).

#### Researcher Agent (НОВЫЙ)

**Роль:** Глубокий аналитик. Отвечает на "почему?" — строит гипотезы, ищет причинно-следственные связи между маркетингом, ценой, остатками, заказами.

**System prompt:** Аналитический фреймворк: гипотеза → данные → подтверждение/опровержение → вывод. Знание бизнес-домена Wookiee.

**Tools (НОВЫЕ — прямой доступ к API):**
| Tool | Что делает | Источник |
|------|-----------|---------|
| `search_wb_analytics` | Поисковые запросы, позиции, CTR | WBClient API |
| `get_wb_feedbacks` | Отзывы покупателей по модели | WBClient API |
| `get_wb_ad_campaigns` | Детали рекламных кампаний | WBClient API |
| `get_ozon_product_analytics` | Аналитика товаров OZON | OzonClient API |
| `get_moysklad_inventory` | Остатки на складах МойСклад | МойСклад API |
| `get_moysklad_cost_history` | История себестоимости | МойСклад API |
| `calculate_correlation` | Корреляция между двумя метриками за период | Python (scipy) |
| `analyze_price_elasticity` | Связь цена↔спрос для модели | Python + PostgreSQL |
| `compare_periods_deep` | Структурированное сравнение двух периодов | PostgreSQL |
| `get_traffic_funnel` | Показы→клики→корзина→заказ→выкуп | PostgreSQL (content_analysis) |

**System prompt Researcher включает:**
- Фреймворк гипотез: "Если маржа упала → проверь 5 рычагов → для каждого рычага найди причину → проверь через данные"
- Связки: реклама↔трафик↔заказы, цена↔СПП↔конверсия, остатки↔out-of-stock↔потери
- Правило: каждая гипотеза должна быть подкреплена данными, не мнением

**Стоимость:** ~$0.05-0.10 за глубокий анализ.

#### Quality Agent (НОВЫЙ)

**Роль:** Менеджер качества. Обрабатывает ОС от команды, верифицирует замечания через данные, обновляет playbook и правила.

**System prompt:** Процесс обработки feedback: получить → перепроверить через данные → принять/отклонить → обновить playbook → уведомить.

**Tools:**
| Tool | Что делает |
|------|-----------|
| `read_playbook` | Читает текущий playbook.md |
| `update_playbook` | Добавляет/обновляет правило в playbook.md |
| `read_feedback_history` | История всех feedback с решениями |
| `log_feedback_decision` | Записывает решение (принято/отклонено + обоснование) |
| `get_report_by_date` | Получает отчёт для перепроверки |
| `verify_claim` | Вызывает Reporter tools для проверки утверждения через данные |

**Процесс обработки feedback:**
1. Получает текст ОС + контекст отчёта
2. Перепроверяет через `verify_claim` (запускает SQL-запросы для верификации)
3. Решает: принять / отклонить / частично принять
4. Если принять → `update_playbook` → логирует → уведомляет
5. Если отклонить → логирует с обоснованием → уведомляет с объяснением почему

**Стоимость:** ~$0.03-0.05 за обработку feedback.

### 1.5 GateChecker с деградацией

**Hard gates** (данные должны существовать):
| # | Гейт | Что проверяет |
|---|------|--------------|
| 1 | ETL ran today | `abc_date.dateupdate` = сегодня |
| 2 | Yesterday's data exists | `MAX(date)` = вчера |
| 3 | Logistics > 0 | Данные о расходах присутствуют |

**Soft gates** (при неудаче генерируем отчёт с caveat):
| # | Гейт | Порог |
|---|------|-------|
| 4 | Orders cross-check | ≤ 5% |
| 5 | Revenue vs 7-day avg | ≥ 70% |
| 6 | Margin fill | ≥ 50% |

**Поведение:**
- Hard passed + soft passed → отчёт
- Hard passed + soft failed → отчёт с caveat
- Hard failed → skip + watchdog трекает + эскалация

### 1.6 Watchdog Service — самодиагностика, а не просто алерты

**Главный принцип:** если отчёт не создан — система **сама ищет причину**, диагностирует проблему и сообщает владельцу: "вот что сломалось, вот как починить".

**Не просто "ошибка" → а два сообщения:**
1. **Алерт #1**: "Отчёт не создан. Запустил диагностику, ищу причину."
2. **Алерт #2** (через 5-10 мин): "Нашёл проблему: {конкретный баг}. Починить: {конкретные шаги}."

**Как работает самодиагностика:**

Когда watchdog обнаруживает, что отчёт не создан, он запускает **диагностическую цепочку** — серию проверок:

```python
class DiagnosticRunner:
    """Автоматическая диагностика при сбое отчёта."""

    async def diagnose(self, report_type: str) -> DiagnosticReport:
        checks = []

        # 1. Проверка гейтов данных
        gates = self.gate_checker.check_all()
        for gate in gates:
            if not gate.passed:
                checks.append(DiagCheck(
                    component="Data Gate",
                    status="FAIL",
                    detail=gate.detail,  # "маржа: 45/200 строк (22%, порог 50%)"
                    fix="Проверить ETL загрузку: abc_date не заполнена"
                ))

        # 2. Проверка PostgreSQL
        for db in ["WB", "OZON"]:
            try:
                conn = psycopg2.connect(...)
                conn.cursor().execute("SELECT 1")
                checks.append(DiagCheck("PostgreSQL " + db, "OK"))
            except Exception as e:
                checks.append(DiagCheck(
                    "PostgreSQL " + db, "FAIL",
                    detail=str(e),
                    fix="БД недоступна. Проверить сервер БД."
                ))

        # 3. Проверка LLM API
        try:
            await self.llm_client.health_check()
            checks.append(DiagCheck("LLM API (OpenRouter)", "OK"))
        except:
            checks.append(DiagCheck(
                "LLM API", "FAIL",
                fix="OpenRouter недоступен. Проверить API ключ или статус сервиса."
            ))

        # 4. Проверка ETL (когда последний раз обновлялась abc_date)
        last_update = self._get_last_etl_update()
        if last_update < today:
            checks.append(DiagCheck(
                "ETL загрузка", "FAIL",
                detail=f"Последнее обновление: {last_update}",
                fix="ETL не запускался сегодня. Проверить контейнер Ибрагим."
            ))

        # 5. Проверка предыдущих ошибок в логе
        recent_errors = self.state_store.get_recent_errors(hours=24)
        if recent_errors:
            checks.append(DiagCheck(
                "Ошибки за 24ч", "WARN",
                detail=f"{len(recent_errors)} ошибок",
                fix=recent_errors[0]['error']  # Последняя ошибка
            ))

        return DiagnosticReport(checks=checks)
```

**Timeline при сбое отчёта:**

| Время | Событие | Сообщение владельцу |
|-------|---------|---------------------|
| 09:00 | Попытка #1 — отчёт не создан | _(нет сообщения, ещё рано)_ |
| 12:00 | Попытка #2 — отчёт не создан | **"Дневной отчёт ещё не создан. Запустил диагностику."** |
| 12:05 | Диагностика завершена | **"Нашёл проблему: {результат диагностики}. Как починить: {шаги}."** |
| 16:00 | Дедлайн — если ещё не починено | **"⚠️ Отчёт за {дата} не создан к дедлайну. Проблема: {причина}. Требуется ваше вмешательство."** |

**Пример сообщения диагностики (алерт #2):**
```
🔍 Диагностика завершена. Найдена проблема:

❌ Data Gate: маржа рассчитана для 22% артикулов (порог 50%)
✅ PostgreSQL WB: OK
✅ PostgreSQL OZON: OK
✅ LLM API: OK
❌ ETL загрузка: последнее обновление 21.02.2026

Причина: ETL не загрузил свежие данные.
abc_date обновлялась вчера, а не сегодня.

Как починить:
1. Проверить контейнер Ибрагима: docker logs wookiee-etl
2. Если контейнер упал — перезапустить: docker restart wookiee-etl
3. После перезапуска ETL отчёт будет создан автоматически.
```

**При многодневном сбое — диагностика каждый день:**
| День | Сообщение |
|------|-----------|
| 1 | "Отчёт не создан → диагностика → вот проблема → вот как починить" |
| 2 | "⚠️ Отчёт не создан 2-й день подряд. Проблема та же: {причина}. Починка не произведена." |
| 3+ | "🚨 КРИТИЧНО: {N} дней без отчётов. Проблема: {причина}. Это требует вашего внимания СЕЙЧАС." |

**Cron jobs watchdog:**
| Время | Job |
|-------|-----|
| 09:00 МСК | Попытка отчёта |
| 12:00 МСК | Retry + диагностика при сбое |
| 16:00 МСК | Дедлайн-алерт если не починено |
| Пн 10:15 | Недельный отчёт |
| Пн 16:00 | Дедлайн недельного |
| Каждые 6ч | Heartbeat |
| Пн 12:00 | Итоги недели: отчёты, сбои, стоимость |

### 1.7 Устойчивый ReAct loop (общий для всех агентов)

`executor/react_loop.py` — базовый движок, используемый всеми суб-агентами:

1. **Try-catch на каждый tool call** — `{"error": "..."}` вместо crash
2. **Timeout** — 30с на tool, 120с общий
3. **Circuit breaker** — 3 ошибки подряд → 5 мин cooldown
4. **Context compression** — после итерации 5
5. **Partial result** — при max_iterations: "дай ответ с собранными данными"

### 1.8 State Store + Feedback Store

```sql
-- Оперативное состояние
CREATE TABLE op_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP);

-- История проверок гейтов
CREATE TABLE gate_history (
    id INTEGER PRIMARY KEY, check_time TIMESTAMP, marketplace TEXT,
    gate_name TEXT, passed BOOLEAN, is_hard BOOLEAN, value REAL, detail TEXT
);

-- Лог отчётов
CREATE TABLE report_log (
    id INTEGER PRIMARY KEY, report_type TEXT, agent TEXT, -- 'reporter'|'researcher'
    status TEXT, created_at TIMESTAMP, duration_ms INTEGER, cost_usd REAL, error TEXT
);

-- Feedback и решения Quality Agent
CREATE TABLE feedback_log (
    id INTEGER PRIMARY KEY, user_id INTEGER, feedback_text TEXT,
    report_context TEXT, decision TEXT, -- 'accepted'|'rejected'|'partial'
    reasoning TEXT, playbook_update TEXT, created_at TIMESTAMP
);
```

---

## Фаза 2: Реализация (дни 6-14)

### Шаг 2.1: Скелет + Executor (дни 6-7)
- Структура `agents/oleg_v2/`
- `executor/react_loop.py` — общий ReAct движок с try-catch, timeout, circuit breaker
- `executor/circuit_breaker.py`
- `agents/base_agent.py` — BaseAgent(system_prompt, tools, executor)
- `app.py` — OlegApp (скелет)
- `__main__.py`

### Шаг 2.2: Reporter Agent (дни 7-8)
- `agents/reporter/agent.py` — ReporterAgent(BaseAgent)
- `agents/reporter/tools.py` — перенос 12+9 tools из v1
- `agents/reporter/prompts.py` — system prompt из playbook.md
- `pipeline/gate_checker.py` — hard/soft гейты
- `pipeline/report_pipeline.py` — gate → Reporter → format → deliver
- `pipeline/report_types.py`

### Шаг 2.3: Orchestrator + Chain (дни 8-9)
- `orchestrator/orchestrator.py` — OlegOrchestrator: `run_chain()` с LLM decide_next_step
- `orchestrator/chain.py` — ChainResult, AgentStep, MAX_CHAIN_STEPS=5
- `orchestrator/prompts.py` — system prompt оркестратора: как выбирать агента, когда остановиться, как синтезировать
- Интеграция: для cron-отчётов → `run_chain(task_type="daily")` (Reporter first, escalation при аномалии)
- Интеграция: для запросов пользователя → `run_chain(task_type="query", task=user_message)`

### Шаг 2.4: Researcher Agent (дни 9-11)
- `agents/researcher/agent.py` — ResearcherAgent(BaseAgent)
- `agents/researcher/tools.py` — API tools (WB, OZON, МойСклад) + statistical tools
- `agents/researcher/prompts.py` — гипотезный фреймворк
- Интеграция: `shared/clients/wb_client.py`, `shared/clients/ozon_client.py` для прямого API доступа

### Шаг 2.5: Quality Agent + Feedback (дни 11-12)
- `agents/quality/agent.py` — QualityAgent(BaseAgent)
- `agents/quality/tools.py` — playbook R/W, verifier, feedback log
- `bot/handlers/feedback.py` — `/feedback`, inline кнопки, reply-to-report
- `storage/feedback_store.py` — SQLite таблица feedback_log

### Шаг 2.6: Watchdog + Bot + Deploy (дни 12-13)
- `watchdog/watchdog.py` — dead man's switch, timeline (09:00→12:00→16:00)
- `watchdog/diagnostic.py` — DiagnosticRunner: проверка гейтов, БД, LLM, ETL + формирование "как починить"
- `watchdog/alerter.py` — Telegram-алерты с результатами диагностики
- `storage/state_store.py` — operational state
- Перенос handlers (auth, menu, reports) в `bot/handlers/`
- `bot/telegram_bot.py` — setup, middleware, прямая доставка
- `config.py` — расширенная конфигурация
- Обновить `deploy/docker-compose.yml` (1 контейнер)
- Обновить `deploy/Dockerfile`, healthcheck

### Шаг 2.7: Документация (день 14)
- **`agents/oleg_v2/SYSTEM.md`** — главный документ с визуальной архитектурой
- **`agents/oleg_v2/agents/reporter/AGENT_SPEC.md`** — спецификация Reporter
- **`agents/oleg_v2/agents/researcher/AGENT_SPEC.md`** — спецификация Researcher
- **`agents/oleg_v2/agents/quality/AGENT_SPEC.md`** — спецификация Quality
- Обновить Notion DB: добавить свойство "Chain steps"
- Обновить `notion_service.py`: передавать chain metadata в Notion

---

## Фаза 3: Тестирование (дни 15-17)

1. Локальный запуск `python -m agents.oleg_v2`
2. **Reporter Agent:**
   - Дневной отчёт с полными данными
   - Отчёт с soft gate fail → caveat
   - Недельный, месячный отчёт
3. **Researcher Agent:**
   - "Почему маржа упала на прошлой неделе?" → гипотеза с данными
   - "Как связаны реклама и заказы?" → корреляция
4. **Quality Agent:**
   - `/feedback "Формула маржи неправильная"` → перепроверка → ответ
   - Reply на отчёт → обработка
5. **Orchestrator:**
   - Произвольный запрос → правильная цепочка агентов
   - Scheduled report → Reporter (без LLM overhead)
6. **Watchdog:**
   - Пропуск отчёта → уведомление → retry → эскалация
   - Circuit breaker: LLM недоступен → cooldown → восстановление
7. Сравнить качество Reporter v2 vs текущего Олега v1

## Фаза 4: Деплой (день 18)

1. Deploy на Timeweb VPS
2. Мониторинг 3 дня
3. Деком v1: архивировать `agents/oleg/` → `docs/archive/retired_agents/oleg_v1/`
4. Обновить: README, AGENTS.md, docs/index.md, docs/architecture.md

---

## Что переиспользуется без изменений

| Модуль | Использует |
|--------|-----------|
| [shared/data_layer.py](shared/data_layer.py) | Reporter Agent (60+ SQL-запросов) |
| [shared/config.py](shared/config.py) | Все компоненты |
| [shared/clients/openrouter_client.py](shared/clients/openrouter_client.py) | Все агенты (LLM) |
| [shared/clients/wb_client.py](shared/clients/wb_client.py) | Researcher Agent (WB API) |
| [shared/clients/ozon_client.py](shared/clients/ozon_client.py) | Researcher Agent (OZON API) |
| [shared/model_mapping.py](shared/model_mapping.py) | Reporter + Researcher |
| `agents/oleg/playbook.md` (агент удалён) | Reporter (+ обновляется Quality Agent) |
| [agents/oleg/services/price_analysis/](agents/oleg/services/price_analysis/) | Reporter Agent |
| [agents/oleg/services/notion_service.py](agents/oleg/services/notion_service.py) | Pipeline |

## Что меняется

| Компонент | Было (v1) | Стало (v2) |
|-----------|-----------|------------|
| Архитектура | Монолитный агент | Orchestrator + 3 sub-agents |
| Контейнеры | 2 (agent + bot) | 1 (unified) |
| Data freshness | 6 hard гейтов | 3 hard + 3 soft (graceful degradation) |
| Deep analysis | Тот же ReAct что и для отчётов | Отдельный Researcher с API tools + гипотезами |
| Feedback | Реализован, не подключён | Quality Agent: полный цикл verify → decide → update |
| Tool calls | Нет try-catch | try-catch + timeout + circuit breaker |
| Мониторинг | Только логи | Watchdog + dead man's switch + эскалация |
| Recovery | 3 дня, через гейты | 7 дней, bypass soft gates |
| Доставка | SQLite queue + polling | Прямой `bot.send_message()` |

## Стоимость

| Сценарий | v1 | v2 (chain) |
|----------|----|----|
| Дневной отчёт (без аномалии) | ~$0.04 | ~$0.05 (Reporter + Олег синтез) |
| Дневной отчёт (с аномалией → escalation) | ~$0.04 | ~$0.10 (Reporter → Researcher → verify) |
| Недельный отчёт (полная цепочка) | ~$0.04 | ~$0.12 (Reporter → Researcher → verify → синтез) |
| Запрос "почему маржа упала?" | ~$0.04 | ~$0.10 (Researcher → Reporter verify → синтез) |
| Запрос "отчёт за январь" | ~$0.04 | ~$0.05 (Reporter → синтез) |
| Feedback обработка | не было | ~$0.08 (Quality → Reporter verify → решение) |
| **Месяц** (30 daily + 4 weekly + 15 запросов + 8 feedback) | **~$7.50** | **~$15-18** |

Рост ~2x за: collaborative chains с гипотезами, верификацией и обучением на ОС. При ~$15/мес — это $0.50/день за полноценного AI-аналитика.

## Верификация

После деплоя:
1. `docker logs wookiee_oleg` — heartbeat каждые 6ч, нет ошибок
2. Дневной отчёт в Telegram к 09:30 МСК
3. "Почему маржа упала?" → Researcher находит причину через API данные
4. `/feedback` → Quality Agent проверяет и отвечает
5. Watchdog: при недоступности данных → caveat, не молчание
6. Circuit breaker: LLM down → retry → алерт
7. Notion: отчёты синхронизируются
