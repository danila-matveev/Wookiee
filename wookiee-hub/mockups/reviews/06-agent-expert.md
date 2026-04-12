# Agent 6: Agent Systems Expert — Observability Analysis

## Текущее состояние: что уже собирается

Проведён аудит всех файлов агентной системы. Вот что система уже записывает:

### Данные, которые ЕСТЬ

| Слой | Что записывается | Где хранится |
|------|-----------------|-------------|
| **ChainResult** | total_cost, total_duration_ms, total_steps, task_type, review_issues_found, review_notes | В памяти, передаётся в report_pipeline |
| **AgentStep** (chain) | agent, instruction, result, cost_usd, duration_ms, iterations | Внутри ChainResult.steps |
| **AgentStep** (react) | tool_name, tool_args, tool_result (первые 2000 символов), iteration, duration_ms, error (bool) | Внутри AgentResult.steps |
| **AgentResult** | content, total_usage (input/output tokens), total_cost, iterations, duration_ms, finish_reason | В памяти, не персистится целиком |
| **StateStore.report_log** | report_type, agent, status, created_at, duration_ms, cost_usd, chain_steps, error | SQLite `oleg.db` |
| **StateStore.recommendation_log** | signals_count, recommendations_count, validation_verdict, validation_attempts, advisor/validator_cost_usd, total_duration_ms | SQLite `oleg.db` |
| **StateStore.gate_history** | marketplace, gate_name, passed, is_hard, value, detail | SQLite `oleg.db` |
| **StateStore.feedback_log** | user_id, feedback_text, decision, reasoning, playbook_update | SQLite `oleg.db` |
| **CircuitBreaker** | state (closed/open/half_open), failure_count, last_failure_time | In-memory, теряется при рестарте |
| **Logging** | Все ключевые события через Python `logging` | stdout/stderr (не структурировано) |

### Критические пробелы

1. **Нет отдельной таблицы tool_call_log** — tool calls записываются в AgentResult.steps, но НЕ персистятся в SQLite. При рестарте все tool-level данные теряются.
2. **Нет token tracking по модели** — `total_usage` содержит input/output tokens, но не записывает КАКАЯ модель использовалась (при эскалации MAIN -> HEAVY).
3. **Нет LLM call log** — каждый вызов к OpenRouter (orchestrator decide, agent react, synthesize, review) не записывается отдельно. Невозможно анализировать latency per LLM call.
4. **Нет chain trace ID** — нет единого trace_id, связывающего pipeline run -> chain -> agent steps -> tool calls. Невозможно построить waterfall.
5. **CircuitBreaker state не персистится** — при рестарте сервиса CB сбрасывается. Если OpenRouter был down, после рестарта CB забывает об этом.
6. **report_log не записывает token usage** — записывает cost, но не tokens. Невозможно отследить token inflation (промпт растёт со временем).
7. **Нет prompt versioning** — playbook загружается из файлов, но версия промпта не фиксируется при каждом запуске. Невозможно корреляция "смена промпта → изменение качества".

---

## Must-Have метрики (MVP)

Метрики, которые ДОЛЖНЫ быть на дашборде с первого дня, отсортированы по ценности:

### Tier 1: Здоровье системы (нужно чтобы спать спокойно)

| Метрика | Почему критична | Источник |
|---------|----------------|----------|
| **Success Rate** по report_type | Основной SLO: "отчёты генерируются" | report_log.status |
| **Pipeline Duration P50/P95** | Деградация latency — первый симптом проблем | report_log.duration_ms |
| **Cost per Report (день/неделя)** | Бюджетный контроль при 4-тировой модели | report_log.cost_usd |
| **Circuit Breaker State** (все агенты) | Каскадный отказ → все отчёты падают | CircuitBreaker.status() |
| **Retry Rate** | >10% retries = деградация модели или промпта | Из _run_chain_with_retry |
| **Gate Pass Rate** | Проблемы с данными блокируют отчёты | gate_history |

### Tier 2: Качество output (нужно чтобы отчёты были полезными)

| Метрика | Почему критична | Источник |
|---------|----------------|----------|
| **Review Issues Found** (per report) | Multi-model review ловит галлюцинации | ChainResult.review_issues_found |
| **Report Substantiality** (detailed length, section count) | Деградация длины = модель "ленится" | Нужно начать собирать |
| **Degraded Sections Rate** | Сколько секций заполнены заглушками | validate_and_degrade() |
| **Advisor Validation Pass Rate** | Качество рекомендаций | recommendation_log.validation_verdict |
| **Tool Error Rate** (per tool) | Сломанный SQL tool = пустые данные в отчёте | AgentStep.error |

### Tier 3: Экономика (нужно чтобы не разориться)

| Метрика | Почему критична | Источник |
|---------|----------------|----------|
| **Token Usage Trend** (input/output, per model) | Token inflation = стоимость растёт | Нужно начать собирать |
| **Cost by Model Tier** | Частые эскалации MAIN→HEAVY = x10 стоимость | Нужно начать собирать |
| **Cost per Report Type** | Какие отчёты самые дорогие | report_log |
| **Orchestrator Decision Cost** | Стоимость "оркестрации" vs "работы" | Нужно начать собирать |

---

## Agent-Specific Observability

### Token & Cost Tracking

**Текущая проблема**: `_calc_cost()` в ReactLoop считает стоимость правильно, но не записывает разбивку по model tier. При эскалации (MAIN -> HEAVY) вся стоимость идёт как "одна цифра".

**Что нужно отслеживать:**

1. **Input tokens per LLM call** — не агрегат, а каждый вызов. Это ключ к обнаружению context window bloat. В текущей архитектуре ReactLoop после 5 итераций делает compress_context(), но эффективность компрессии не замеряется.

2. **Output tokens per LLM call** — диагностирует "многословность" модели. Если output растёт без роста качества — модель деградировала или промпт позволяет.

3. **Tokens wasted on retries** — когда _run_chain_with_retry делает повтор, токены первой попытки потеряны. Это скрытая стоимость, которая не видна в итоговом cost_usd.

4. **Model tier per call** — какая модель реально использовалась. Необходимо для расчёта: "если бы мы всегда использовали MAIN, стоимость была бы X, а реально из-за эскалаций стоимость Y".

**Рекомендуемая визуализация:**
- Stacked area chart: tokens over time, stacked by model tier
- Table: report_type | avg tokens (in/out) | avg cost | p95 cost
- Alert threshold: "средняя стоимость daily report превысила $X" (сейчас нет контроля)

### Chain Tracing

**Текущая архитектура**: Orchestrator делает LLM-driven решения через DECIDE_NEXT_STEP_PROMPT. Решение содержит `reasoning`, но reasoning НЕ записывается в state_store.

**Что нужно для chain tracing:**

1. **Trace Waterfall View** — самая ценная визуализация для LLM-агентов:
```
[Pipeline Start]
  |-- Gate Check (120ms) OK
  |-- Orchestrator Decide #1 (800ms, 450 tokens) → reporter
  |   |-- Reporter ReAct Loop
  |   |   |-- LLM Call #1 (1200ms, 2000in/800out)
  |   |   |-- Tool: get_plan_vs_fact (340ms) OK
  |   |   |-- Tool: get_brand_finance (280ms) OK
  |   |   |-- LLM Call #2 (1100ms, 3500in/1200out)
  |   |   |-- Tool: get_margin_levers (310ms) OK
  |   |   |-- ... (7 iterations total)
  |   |   |-- LLM Call #8 (900ms) → final answer
  |   |-- Reporter Done (18.2s, $0.024)
  |-- Orchestrator Decide #2 (700ms) → done=true
  |-- Advisor Chain
  |   |-- Signal Detection (12ms, 0 LLM calls) → 3 signals
  |   |-- Advisor (2.1s) → 2 recommendations
  |   |-- Validator (1.8s) → pass
  |-- Synthesize (2.3s)
  |-- Review (3.1s, gemini-3-flash)
[Pipeline End: 32.4s, $0.041]
```

2. **Decision Reasoning Log** — для каждого orchestrator decide, записать:
   - Какие агенты были доступны
   - Какой выбран и ПОЧЕМУ (reasoning из JSON)
   - Был ли это shortcut (первый шаг daily → reporter) или LLM decision

3. **Chain Pattern Analysis** — агрегат за N дней:
   - "Reporter only" (1 step): 72% запусков
   - "Reporter → Researcher" (2 steps): 15% — аномалии маржи
   - "Reporter → Marketer" (2 steps): 8% — аномалии ДРР
   - "Reporter → Researcher → Reporter verify" (3 steps): 5%

   Это позволяет отслеживать: "стало больше 2-3 step chains" = чаще детектируются аномалии, или оркестратор стал "нерешительным".

### Tool Call Analytics

**Текущее состояние**: AgentStep в ReactLoop записывает tool_name, tool_args, duration_ms, error. Но это только в памяти (AgentResult.steps), не в SQLite.

**Ключевые метрики для 30+ tools:**

1. **Tool Hit Map** (heatmap: tool x report_type):
   - Какие tools используются в daily vs weekly vs marketing_weekly
   - Tools которые НИКОГДА не вызываются — кандидаты на удаление
   - Tools которые вызываются, но всегда возвращают ошибку

2. **Tool Duration Distribution** (histogram per tool):
   - P50, P95, P99 для каждого tool
   - get_plan_vs_fact может занимать 200ms или 5s в зависимости от нагрузки на DB
   - Аномально долгий tool = деградация DB или сети

3. **Tool Error Rate** (per tool, per day):
   - Стабильный 0% → внезапный 100% = tool сломался (DB schema change, API down)
   - Стабильный 5% → это нормальная ошибка или скрытый баг?

4. **Tool Call Sequences** (Sankey diagram):
   ```
   get_plan_vs_fact → get_brand_finance → get_margin_levers → get_advertising_stats
   ```
   Типичная последовательность для daily report. Если модель начинает вызывать tools в другом порядке или добавляет лишние вызовы — промпт деградировал.

5. **Tool Result Size Distribution**:
   - tool_result обрезается до 2000 символов в AgentStep и до 8500 в messages
   - Если tool стабильно возвращает >8500 → данные обрезаются → модель теряет контекст
   - Нужно отслеживать: original size vs truncated size

### Prompt Quality

**Это самый сложный и самый важный аспект LLM observability.**

**Проблема**: Промпты в Wookiee загружаются из playbook файлов и hardcoded строк. Нет механизма для отслеживания "этот промпт работал лучше/хуже предыдущего".

**Сигналы деградации промпта:**

1. **Iteration Count Drift** — если reporter стабильно завершался за 5 итераций, а теперь за 8-9, промпт стал менее точным (модель "блуждает").

2. **Tool Call Count per Report** — рост числа tool calls без роста качества = модель не может сформулировать ответ с первого раза.

3. **Finish Reason Distribution**:
   - `stop` (нормально) → должно быть >95%
   - `max_iterations` → промпт не приводит к решению
   - `llm_error` → инфраструктурная проблема
   - `circuit_breaker` → каскадный отказ
   - `total_timeout` → промпт слишком сложный или tool calls слишком долгие

4. **Review Issues Trend** — multi-model review (Gemini проверяет GLM-4.7):
   - Рост review_issues_found = основная модель стала чаще ошибаться
   - Типы ошибок (из review_notes): фактические, логические, форматные

5. **Report Section Completeness** — сколько секций из template.md реально заполнено данными vs заглушками. Тренд: 95% → 80% = деградация.

6. **Feedback Signal Correlation** — StateStore уже записывает feedback_log. Нужно:
   - Трекать: feedback "плохой отчёт" → какой промпт использовался → какие tool calls
   - Строить: "после обновления playbook X, feedback стал лучше/хуже"

**Recommended dashboard view:**
- Timeline: iterations per report type (с трендлинией)
- Timeline: review issues per report type
- Table: prompt version | success_rate | avg_iterations | avg_cost | feedback_score

---

## Данные которые нужно начать собирать СЕЙЧАС

### Приоритет 1: Минимальные изменения, максимальная ценность

#### 1. Таблица `llm_call_log` в StateStore

```sql
CREATE TABLE IF NOT EXISTS llm_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,       -- связка pipeline → chain → call
    call_type TEXT NOT NULL,      -- 'orchestrator_decide' | 'agent_react' | 'synthesize' | 'review' | 'anomaly_comment'
    agent TEXT,                   -- 'reporter', 'marketer', null для orchestrator
    model TEXT NOT NULL,          -- 'z-ai/glm-4.7', 'google/gemini-3-flash-preview'
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    duration_ms INTEGER,
    finish_reason TEXT,           -- 'stop', 'length', 'tool_calls'
    temperature REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Где инструментировать**: ReactLoop.run() после каждого `self.llm.complete_with_tools()` — строка 141. И OlegOrchestrator._decide_next_step() — строка 321. И _synthesize() — строка 435. И _review_synthesis() — строка 758.

**Оценка трудозатрат**: 2-3 часа. Нужно пробросить trace_id через pipeline → orchestrator → react_loop.

#### 2. Таблица `tool_call_log` в StateStore

```sql
CREATE TABLE IF NOT EXISTS tool_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_args_json TEXT,          -- для дебага
    duration_ms INTEGER,
    result_size INTEGER,          -- размер до truncation
    truncated BOOLEAN DEFAULT 0,
    error BOOLEAN DEFAULT 0,
    error_type TEXT,              -- 'timeout', 'exception', null
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Где инструментировать**: ReactLoop._execute_tool_safe() — строка 430, после try-catch.

**Оценка трудозатрат**: 1-2 часа.

#### 3. Добавить `trace_id` в ChainResult и report_log

Изменения в `chain.py`:
```python
@dataclass
class ChainResult:
    trace_id: str = ""           # UUID, генерируется в run_chain()
    # ... existing fields ...
```

Изменения в `report_log`:
```sql
ALTER TABLE report_log ADD COLUMN trace_id TEXT;
ALTER TABLE report_log ADD COLUMN input_tokens INTEGER DEFAULT 0;
ALTER TABLE report_log ADD COLUMN output_tokens INTEGER DEFAULT 0;
ALTER TABLE report_log ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE report_log ADD COLUMN detailed_length INTEGER DEFAULT 0;
ALTER TABLE report_log ADD COLUMN sections_total INTEGER DEFAULT 0;
ALTER TABLE report_log ADD COLUMN sections_degraded INTEGER DEFAULT 0;
```

**Оценка трудозатрат**: 1 час.

### Приоритет 2: Средняя сложность, высокая ценность

#### 4. Prompt Version Tracking

При каждом запуске ReporterAgent.get_system_prompt(), вычислять hash промпта и записывать:

```sql
CREATE TABLE IF NOT EXISTS prompt_version_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT,
    agent TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,    -- SHA256 первых 500 символов
    prompt_length INTEGER,
    playbook_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Это позволяет строить корреляцию: "с этого commit промпт изменился → quality metrics изменились".

#### 5. Персистить CircuitBreaker state

Добавить в StateStore:
```python
def save_circuit_breaker(self, name: str, state: str, failure_count: int): ...
def load_circuit_breaker(self, name: str) -> dict: ...
```

Вызывать при каждом record_failure() / record_success().

### Приоритет 3: Долгосрочная инструментация

#### 6. Context Window Utilization

В ReactLoop._compress_context() уже логгируется reduction percentage. Нужно записывать:
- Текущий размер context window в символах перед каждым LLM call
- Процент использования context window (chars / model_max_context)
- Эффективность компрессии

#### 7. Structured Output Parsing Success Rate

Orchestrator и Advisor ожидают JSON от LLM. Сейчас JSON parse ошибки логгируются как warning. Нужно считать: `json_parse_success / total_calls`. Падение этой метрики = модель стала хуже следовать format instructions.

---

## Визуализации для agent monitoring

### 1. Health Overview (верхняя панель)

**4 KPI карточки** (уже частично в mockup):
- Reports Generated Today: X/Y expected (с ring chart: success/failed/skipped)
- System Cost Today: $X.XX (с трендом vs вчера)
- Avg Pipeline Duration: XXs (с P95 мелким шрифтом)
- Active Alerts: N (CB open, high error rate, gate failures)

### 2. Chain Waterfall (новая визуализация, специфичная для LLM-систем)

Горизонтальная timeline для одного pipeline run:
```
|----Gate----|
             |-------Orchestrator Decide-------|
                                               |---Reporter React (7 iter)---|
                                                                              |--Decide--|
                                                                                         |--Advisor--|
                                                                                                     |--Synth--|
                                                                                                               |--Review--|
0s          0.1s                              1s                            19s         20s          22s        24s        28s
```

Цвет каждого блока: зелёный (OK), жёлтый (slow), красный (error).
Клик по блоку раскрывает tool calls внутри.

**Это killer feature для debugging LLM-агентов.** В традиционных системах такой waterfall показывает HTTP calls. Здесь — LLM reasoning steps.

### 3. Agent Fleet Status (уже в mockup)

Таблица агентов с real-time статусом. Дополнить:
- Колонка "Model Tier" — какая модель используется сейчас
- Колонка "CB State" — closed/open/half_open с визуальным индикатором
- Колонка "Last 24h Cost" — мини-sparkline

### 4. Tool Analytics (новая панель)

**Top tools by call count** (bar chart, horizontal):
```
get_plan_vs_fact       ████████████ 342
get_brand_finance      ██████████ 298
get_advertising_stats  ████████ 245
get_margin_levers      ██████ 189
search_knowledge_base  █████ 156
...
```

**Tool error rate** (bar chart, red overlay):
```
get_ozon_orders  ███░░ 12% error (timeout)
get_wb_keywords  ██░░░ 8% error (API rate limit)
```

### 5. Cost Breakdown (новая панель)

**Stacked bar chart по дням:**
- X: даты
- Y: стоимость ($)
- Stacked: по report_type (daily, weekly, marketing, funnel)
- Линия: кумулятивная стоимость за месяц

**Pie chart** по model tier:
- MAIN (z-ai/glm-4.7): 65% вызовов, 40% стоимости
- HEAVY (gemini-3-flash): 5% вызовов, 35% стоимости
- LIGHT (glm-4.7-flash): 28% вызовов, 3% стоимости
- FREE: 2% вызовов, 0% стоимости

### 6. Quality Trends (новая панель)

**Line chart, 30 дней:**
- Review Issues Found (per report) — должен тренд к нулю
- Report Detailed Length — стабильность
- Iterations per Report — стабильность
- Degraded Sections — должен быть 0

### 7. Anomaly Detection Effectiveness (новая панель)

**Confusion matrix view:**
- True Positive: аномалия детектирована, команда подтвердила
- False Positive: аномалия детектирована, оказалась ложной (alert fatigue!)
- False Negative: аномалия пропущена (узнали из feedback)
- True Negative: всё нормально

**Alert Fatigue Metric**: `false_positive_rate = FP / (TP + FP)`. Если >30% — команда начнёт игнорировать алерты.

**Threshold Tuning Table:**
```
Метрика        | Текущий порог | Сработок (7д) | FP rate | Рекомендация
Revenue        | 20%           | 3             | 33%     | Увеличить до 25%
Margin         | 10 п.п.       | 1             | 0%      | OK
DRR            | 30 п.п.       | 5             | 60%     | Увеличить до 40%
Orders         | 25%           | 2             | 50%     | Добавить min-absolute фильтр
```

---

## Anti-patterns

### 1. Не считать средний latency — считать перцентили

**Ошибка**: "Средний pipeline duration = 25 секунд, всё ок."
**Реальность**: P50 = 18s, P95 = 65s, P99 = 120s. 5% пользователей ждут больше минуты.

Для LLM-систем distribution ВСЕГДА multimodal: быстрые (1-step chain) и медленные (3-step с researcher). Среднее арифметическое бессмысленно. Всегда показывать P50 + P95.

### 2. Не мониторить cost на уровне организации — мониторить per-report-type

**Ошибка**: "Общие расходы на LLM = $X/день, ок."
**Реальность**: Daily report стоит $0.02, а monthly report стоит $0.30 из-за 3-step chain + review. Один тип отчёта может съедать 80% бюджета.

### 3. Не полагаться только на "report generated = success"

**Ошибка**: 100% success rate в report_log.
**Реальность**: Отчёт сгенерирован, но 40% секций — заглушки. has_substantial_content() возвращает true потому что хотя бы одна секция заполнена. Нужен metric: `real_sections / total_sections`.

### 4. Не логировать полный prompt при каждом вызове

**Ошибка**: Записывать system_prompt целиком в каждый log entry.
**Реальность**: system_prompt для reporter = 3-5K символов x 8 итераций x 10 отчётов/день = 400K символов/день мусора в логах. Логировать hash + длину, полный текст — по trace_id при расследовании.

### 5. Не собирать метрики синхронно в hot path

**Ошибка**: Вставлять INSERT в SQLite внутри ReactLoop на каждой итерации.
**Реальность**: SQLite lock на запись = +5-20ms на каждый tool call. При 30 tool calls = +150-600ms к pipeline. Метрики нужно буферизировать и писать батчем в конце.

### 6. Не создавать dashboard с 50 графиками

**Ошибка**: Показать ВСЁ сразу.
**Реальность**: Dashboard с 50 метриками = dashboard который никто не смотрит. Правило: 4-6 KPI на верхнем уровне. Drill-down по клику. Начать с Tier 1 метрик (success rate, duration, cost, CB state).

### 7. Не игнорировать "тихие" отказы

**Ошибка**: Мониторить только explicit errors.
**Реальность**: Самые опасные проблемы LLM-систем — "тихие": модель возвращает ответ, но он не содержит запрошенных данных. finish_reason = "stop", но content пустой или содержит только "извините, не могу". Нужен content quality check помимо error check.

### 8. Не ставить алерты на абсолютные значения cost

**Ошибка**: Alert "cost > $0.05 per report".
**Реальность**: Monthly report ВСЕГДА дороже $0.05 — это нормально. Нужны relative alerts: "cost вырос на 50% vs 7-day average для ЭТОГО report_type".

---

## Рекомендации по архитектуре телеметрии

### Принцип 1: Buffered Write, не синхронный INSERT

Текущая архитектура записывает report_log и recommendation_log в конце pipeline (`_log_recommendation`, `log_report`). Это правильный подход. Расширить его на tool_call_log и llm_call_log:

```python
class TelemetryBuffer:
    """Collects telemetry during pipeline run, flushes once at the end."""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.llm_calls: list[dict] = []
        self.tool_calls: list[dict] = []

    def record_llm_call(self, **kwargs):
        self.llm_calls.append({"trace_id": self.trace_id, **kwargs})

    def record_tool_call(self, **kwargs):
        self.tool_calls.append({"trace_id": self.trace_id, **kwargs})

    def flush(self, store: StateStore):
        """Single transaction, all inserts."""
        store.bulk_insert_llm_calls(self.llm_calls)
        store.bulk_insert_tool_calls(self.tool_calls)
```

Пробросить TelemetryBuffer через: `run_report()` → `OlegOrchestrator.run_chain()` → `ReactLoop.run()`.

### Принцип 2: Trace ID как скелет

Генерировать UUID в `run_report()` и пробрасывать через все слои:

```
trace_id = "rpt-20260331-daily-a1b2c3"
  ├── report_log (trace_id)
  ├── llm_call_log (trace_id, call_type="orchestrator_decide")
  ├── llm_call_log (trace_id, call_type="agent_react", agent="reporter")
  ├── tool_call_log (trace_id, agent="reporter", tool="get_plan_vs_fact")
  ├── tool_call_log (trace_id, agent="reporter", tool="get_brand_finance")
  ├── llm_call_log (trace_id, call_type="synthesize")
  └── recommendation_log (trace_id)
```

Один trace_id → полная картина одного pipeline run. Дашборд: клик по report → waterfall всех вызовов.

### Принцип 3: Структурированные логи, не string parsing

Текущие logger.info() полезны для дебага, но бесполезны для дашборда. Не пытаться парсить логи — использовать SQLite tables как structured telemetry store.

При этом логи ОСТАВИТЬ как есть — они нужны для terminal debugging. Телеметрия для дашборда — отдельный канал (SQLite).

### Принцип 4: Инструментация через middleware, не изменение бизнес-логики

Вместо добавления telemetry кода внутрь ReactLoop.run(), рассмотреть обёртку:

```python
class InstrumentedReactLoop(ReactLoop):
    def __init__(self, *args, telemetry: TelemetryBuffer, **kwargs):
        super().__init__(*args, **kwargs)
        self.telemetry = telemetry

    async def run(self, *args, **kwargs) -> AgentResult:
        start = time.time()
        result = await super().run(*args, **kwargs)
        # Record metrics from result
        for step in result.steps:
            self.telemetry.record_tool_call(
                agent=..., tool_name=step.tool_name,
                duration_ms=step.duration_ms, error=step.error,
            )
        return result
```

Это минимизирует изменения в core logic и позволяет отключить телеметрию для тестов.

### Принцип 5: Ротация данных

SQLite для telemetry — ок для масштаба Wookiee (~10-20 pipeline runs/день). Но через 6 месяцев таблица tool_call_log будет содержать 50K+ записей. Добавить ротацию:

```python
def rotate_telemetry(self, keep_days: int = 90):
    """Delete telemetry older than N days."""
    with sqlite3.connect(self.db_path) as conn:
        for table in ('llm_call_log', 'tool_call_log'):
            conn.execute(
                f"DELETE FROM {table} WHERE created_at < datetime('now', ?)",
                (f"-{keep_days} days",),
            )
```

### Принцип 6: Dashboard API endpoint

Дашборд (wookiee-hub) должен получать данные через API, не читать SQLite напрямую. Предусмотреть endpoint:

```
GET /api/agent-ops/overview?period=7d
GET /api/agent-ops/trace/{trace_id}
GET /api/agent-ops/tools/stats?period=7d
GET /api/agent-ops/cost/breakdown?period=30d
```

SQLite читается сервером, агрегируется, отдаётся как JSON. Это позволяет в будущем мигрировать телеметрию в PostgreSQL без изменения фронтенда.

---

## Итого: план действий

| Этап | Что делать | Трудозатраты | Ценность |
|------|-----------|-------------|----------|
| **Сейчас** | Добавить trace_id + TelemetryBuffer + таблицы llm_call_log, tool_call_log | 4-6 часов | Фундамент для всего дашборда |
| **Сейчас** | Расширить report_log (tokens, retry_count, detailed_length, sections) | 1 час | Tier 1 метрики без новых таблиц |
| **MVP дашборд** | 4 KPI карточки + Fleet table + Activity feed (уже в mockup) | В рамках Hub | Базовый health monitoring |
| **Итерация 2** | Chain Waterfall view + Tool Analytics panel | 1-2 дня фронт | Ключевая ценность для debugging |
| **Итерация 3** | Cost Breakdown + Quality Trends + Prompt Version tracking | 1 день бэк + 1 день фронт | Экономика + quality loop |
| **Позже** | Anomaly Detection effectiveness + Feedback correlation | Требует ручной разметки FP/FN | Замкнутый feedback loop |
