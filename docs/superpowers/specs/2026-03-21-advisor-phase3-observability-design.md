# Advisor Phase 3 — Observability, KB Integration & Self-Learning

**Date:** 2026-03-21
**Status:** Draft
**Author:** Claude + Danila
**Depends on:** Phase 1 (`advisor-agent-design.md`), Phase 2 (`advisor-phase2-activation-design.md`)

## Контекст

Phase 1 реализовал базовую архитектуру: Signal Detector (5 паттернов), Advisor Agent, Validator Agent (с 4 детерминированными скриптами), direction_map, retry-логику.

Phase 2 активировал chain в проде: извлечение structured_data из tool call history, 25 детекторов, status_mismatch с ABC/status из Supabase.

**Что осталось нереализованным:**

1. **Observability** — нет логирования рекомендаций, невозможно оценить качество работы advisor chain
2. **KB Integration** — `kb_patterns.py` загрузчик не реализован; `detect_signals()` вызывается без `kb_patterns`; Validator `check_kb_rules` есть, но `kb_patterns` не передаются
3. **Self-Learning** — механизм подтверждения/добавления паттернов через чат не реализован

---

## Проблема

Advisor chain работает, но работает вслепую:
- Нет данных о том, сколько сигналов срабатывает, какие рекомендации генерируются, проходят ли они валидацию
- Нет обратной связи — невозможно понять, полезны ли рекомендации
- Пороги захардкожены в коде (`patterns.py`); изменение порога = изменение кода + деплой
- Новые бизнес-правила невозможно добавить без разработчика

---

## Goals

1. **Observability**: каждый прогон advisor chain логируется в SQLite `recommendation_log` (через `StateStore`) — сигналы, рекомендации, вердикт, затраты токенов
2. **KB Pattern Loader**: `detect_signals()` подгружает пользовательские паттерны из `kb_patterns` таблицы и применяет generic evaluator (уже реализован)
3. **Validator KB Rules**: Validator получает `kb_patterns` при вызове `check_kb_rules`, проверяет конфликты
4. **Self-Learning (manual)**: Advisor предлагает новые паттерны в output; оркестратор сохраняет их как `verified: false`; пользователь подтверждает через Telegram

## Non-Goals

- Авто-верификация паттернов (Phase 5 — после накопления данных)
- Ежемесячный отчёт знаний в Notion (отдельная задача после observability)
- Расширение Signal Detector новыми источниками данных

---

## Компонент 1: recommendation_log (SQLite, StateStore)

Логи advisor chain пишутся в общую локальную БД (`agents/oleg/data/oleg.db`) через `StateStore` — как и все другие логи агентов (`report_log`, `gate_history`, `feedback_log`).

### Таблица (SQLite, добавляется в `StateStore.init_db()`)

```sql
CREATE TABLE IF NOT EXISTS recommendation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    report_type TEXT NOT NULL,              -- daily | weekly | monthly
    context TEXT NOT NULL DEFAULT 'financial',  -- financial | marketing | funnel
    channel TEXT,                           -- WB | OZON | null
    signals_count INTEGER DEFAULT 0,
    recommendations_count INTEGER DEFAULT 0,
    validation_verdict TEXT DEFAULT 'skipped',  -- pass | fail | skipped
    validation_attempts INTEGER DEFAULT 1,
    signals TEXT,                           -- JSON string
    recommendations TEXT,                   -- JSON string
    validation_details TEXT,                -- JSON string
    new_patterns TEXT,                      -- JSON string
    advisor_cost_usd REAL DEFAULT 0,
    validator_cost_usd REAL DEFAULT 0,
    total_duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Интеграция в StateStore

Новый метод `log_recommendation()` в `StateStore`:

```python
def log_recommendation(
    self, report_date: str, report_type: str, context: str,
    signals_count: int, recommendations_count: int,
    validation_verdict: str, validation_attempts: int,
    signals: list, recommendations: list,
    validation_details: dict, new_patterns: list,
    advisor_cost_usd: float, validator_cost_usd: float,
    total_duration_ms: int, channel: str = None,
) -> int:
    with sqlite3.connect(self.db_path) as conn:
        cur = conn.execute(
            "INSERT INTO recommendation_log "
            "(report_date, report_type, context, channel, signals_count, "
            "recommendations_count, validation_verdict, validation_attempts, "
            "signals, recommendations, validation_details, new_patterns, "
            "advisor_cost_usd, validator_cost_usd, total_duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (report_date, report_type, context, channel,
             signals_count, recommendations_count,
             validation_verdict, validation_attempts,
             json.dumps(signals, ensure_ascii=False, default=str),
             json.dumps(recommendations, ensure_ascii=False, default=str),
             json.dumps(validation_details, ensure_ascii=False, default=str),
             json.dumps(new_patterns, ensure_ascii=False, default=str),
             advisor_cost_usd, validator_cost_usd, total_duration_ms),
        )
        return cur.lastrowid
```

### Интеграция в orchestrator

В `_run_advisor_chain()`, после получения финального результата:

```python
def _log_recommendation(self, result: dict, report_type: str, duration_ms: int):
    """Log advisor chain result to local SQLite via StateStore."""
    try:
        from agents.oleg.storage.state_store import StateStore
        store = StateStore("agents/oleg/data/oleg.db")
        store.log_recommendation(
            report_date=date.today().isoformat(),
            report_type=report_type,
            context="financial",
            signals_count=len(result.get("signals", [])),
            recommendations_count=len(result.get("recommendations", [])),
            validation_verdict=result.get("verdict", {}).get("verdict", "skipped"),
            validation_attempts=result.get("attempts", 1),
            signals=result.get("signals", []),
            recommendations=result.get("recommendations", []),
            validation_details=result.get("verdict", {}),
            new_patterns=result.get("new_patterns", []),
            advisor_cost_usd=0.0,
            validator_cost_usd=0.0,
            total_duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning(f"Failed to log recommendation: {e}")
```

**Примечание:** orchestrator уже использует StateStore для `log_report()` — шаблон знаком. Не требуется async, SQLite работает синхронно.

### Метрики (SQL-запросы к SQLite)

- **Signal detection rate** — `SELECT AVG(signals_count) FROM recommendation_log WHERE report_date >= date('now', '-7 days')`
- **Validation pass rate** — `SELECT CAST(SUM(CASE WHEN validation_verdict='pass' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) FROM recommendation_log`
- **Pattern trigger frequency** — парсинг JSON из `signals` column в Python
- **Top unresolved signals** — сигналы без рекомендаций (coverage gap)

---

## Компонент 2: kb_patterns таблица и загрузчик

### Таблица

```sql
CREATE TABLE hub.kb_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,          -- margin | adv | funnel | price | turnover
    source_tag VARCHAR(50) NOT NULL,        -- plan_vs_fact | brand_finance | ...
    trigger_condition JSONB NOT NULL,       -- {"metric": "drr_pct", "operator": ">", "threshold": 12}
    severity VARCHAR(10) DEFAULT 'info',    -- info | warning | critical
    hint_template TEXT,                     -- "ДРР {drr_pct}% > порога {threshold}%"
    verified BOOLEAN DEFAULT false,
    created_by VARCHAR(50) DEFAULT 'system', -- system | advisor | user
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE hub.kb_patterns ENABLE ROW LEVEL SECURITY;
CREATE POLICY service_full ON hub.kb_patterns FOR ALL TO postgres USING (true) WITH CHECK (true);

CREATE INDEX idx_kb_patterns_source ON hub.kb_patterns(source_tag);
CREATE INDEX idx_kb_patterns_verified ON hub.kb_patterns(verified);
```

### Загрузчик: `shared/signals/kb_patterns.py`

```python
def load_kb_patterns(verified_only: bool = True) -> list[dict]:
    """Load patterns from hub.kb_patterns table."""
    conn = get_hub_connection()
    cur = conn.cursor()

    query = "SELECT pattern_name, description, category, source_tag, trigger_condition, severity, hint_template FROM hub.kb_patterns"
    if verified_only:
        query += " WHERE verified = true"

    cur.execute(query)
    patterns = []
    for row in cur.fetchall():
        patterns.append({
            "name": row[0],
            "description": row[1],
            "category": row[2],
            "source_tag": row[3],
            "trigger_condition": row[4],  # уже JSONB → dict
            "severity": row[5],
            "hint_template": row[6],
        })
    cur.close()
    conn.close()
    return patterns
```

### Seed: миграция BASE_PATTERNS → kb_patterns

Все 25 паттернов из `shared/signals/patterns.py` которые имеют `trigger_condition` — вставить в `hub.kb_patterns` с `verified: true, created_by: 'system'`. Это позволит менять пороги без деплоя.

### Интеграция в orchestrator

```python
# В _run_signal_detection():
from shared.signals.kb_patterns import load_kb_patterns

kb_patterns = load_kb_patterns(verified_only=True)

for source_tag, source_data in structured_data.items():
    # Фильтруем KB-паттерны по source_tag
    relevant_kb = [p for p in kb_patterns if p["source_tag"] == source_tag]
    if isinstance(source_data, list):
        for item in source_data:
            all_signals.extend(detect_signals(data=item, kb_patterns=relevant_kb))
    else:
        all_signals.extend(detect_signals(data=source_data, kb_patterns=relevant_kb))
```

**Важно:** `_detect_kb_pattern_signals()` generic evaluator уже реализован в Phase 2. Нужно только:
1. Создать таблицу
2. Написать загрузчик
3. Передавать `kb_patterns` в `detect_signals()`

---

## Компонент 3: Validator — wiring kb_patterns

Сейчас orchestrator вызывает Validator без передачи kb_patterns. Validator имеет тул `validate_kb_rules`, но он вызывается с пустым `kb_patterns: []`.

### Изменения

1. Orchestrator передаёт `kb_patterns` в instruction для Validator:
```python
validator_instruction = (
    f"Проверь рекомендации.\n\n"
    f"recommendations = {json.dumps(recommendations)}\n"
    f"signals = {json.dumps(signals)}\n"
    f"structured_data = {json.dumps(structured_data)}\n"
    f"kb_patterns = {json.dumps(kb_patterns)}"  # НОВОЕ
)
```

2. Validator system prompt уже инструктирует вызывать `validate_kb_rules` — нужно только обеспечить передачу данных.

---

## Компонент 4: Self-Learning (manual mode)

### Advisor output: new_patterns

Advisor system prompt дополняется инструкцией предлагать новые паттерны:

```
Если ты видишь аномалию, которая НЕ покрыта существующими сигналами,
предложи новый паттерн в поле "new_patterns":

{
  "recommendations": [...],
  "new_patterns": [
    {
      "pattern_name": "high_cancellation_rate",
      "description": "Высокий % отмен (>15%) сигнализирует о проблемах с карточкой",
      "category": "funnel",
      "source_tag": "advertising",
      "trigger_condition": {"metric": "cancellation_pct", "operator": ">", "threshold": 15},
      "severity": "warning",
      "hint_template": "Отмены {cancellation_pct}% > {threshold}%"
    }
  ]
}
```

### Сохранение предложенных паттернов

В orchestrator, после получения advisor output:

```python
new_patterns = advisor_output.get("new_patterns", [])
if new_patterns:
    from shared.signals.kb_patterns import save_proposed_patterns
    save_proposed_patterns(new_patterns)  # verified=false, created_by='advisor'
```

### Подтверждение через Telegram

Реализация — в следующей итерации (после observability). Формат:

```
🔍 Advisor предлагает новый паттерн:

**high_cancellation_rate**
Высокий % отмен (>15%) сигнализирует о проблемах с карточкой
Severity: warning
Source: advertising

Подтвердить? (Да / Нет / Изменить порог)
```

При "Да" — `UPDATE hub.kb_patterns SET verified = true WHERE pattern_name = ...`

---

## Файловая структура изменений

```
# CREATE
shared/signals/kb_patterns.py              # load_kb_patterns(), save_proposed_patterns()
migrations/004_kb_patterns.sql             # CREATE TABLE hub.kb_patterns + seed (Supabase)

# MODIFY
agents/oleg/storage/state_store.py         # + recommendation_log таблица + log_recommendation()
agents/oleg/orchestrator/orchestrator.py   # _log_recommendation(), kb_patterns в signal detection + validator
agents/oleg/agents/advisor/prompts.py      # new_patterns в output schema
```

---

## Data flow (полный)

```
run_chain():
  Шаг 1: Reporter/Marketer (как сейчас)
    → AgentResult с .steps[]
    |
  Шаг 2: _extract_structured_data(agent_result)      [Phase 2 ✅]
    → structured_data dict
    |
  Шаг 3: load_kb_patterns()                          [Phase 3 — НОВОЕ]
    → kb_patterns list
    |
  Шаг 4: detect_signals(data, kb_patterns)            [Phase 2 ✅ + Phase 3 wiring]
    → signals[]
    |
  Шаг 5: Advisor(signals, structured_data, kb_patterns)
    → recommendations[] + new_patterns[]
    |
  Шаг 6: Validator(recommendations, signals, kb_patterns) [Phase 3 — kb_patterns wiring]
    → verdict
    |
  Шаг 7: _log_recommendation(result)                 [Phase 3 — НОВОЕ]
    → SQLite recommendation_log (через StateStore)
    |
  Шаг 8: save_proposed_patterns(new_patterns)         [Phase 3 — НОВОЕ]
    → hub.kb_patterns (verified=false)
```

---

## Порядок реализации

### Batch A: Observability (без внешних зависимостей)
1. `state_store.py` — `recommendation_log` таблица + `log_recommendation()` метод
2. `orchestrator.py` — `_log_recommendation()` + вызов в `_run_advisor_chain()`
3. Тесты

### Batch B: KB Patterns (зависит от hub schema)
1. Миграция `hub.kb_patterns` + seed из BASE_PATTERNS
2. `shared/signals/kb_patterns.py` — `load_kb_patterns()`
3. `orchestrator.py` — wiring `kb_patterns` в `detect_signals()` и Validator instruction
4. Тесты

### Batch C: Self-Learning (зависит от B)
1. Обновить Advisor prompt — `new_patterns` в output
2. `kb_patterns.py` — `save_proposed_patterns()`
3. Тесты
4. (Отдельно) Telegram UI для подтверждения — может быть отдельной задачей

---

## Риски и mitigation

| Риск | Mitigation |
|------|-----------|
| SQLite файл повреждён / потерян | WAL mode + бекапы; данные не критичны, chain работает без логов |
| load_kb_patterns() добавляет латентность | Кэшировать на 5 минут (TTL cache); KB-паттерны меняются редко |
| Advisor генерирует мусорные new_patterns | verified=false по умолчанию; не влияют на detection до подтверждения |
| recommendation_log растёт быстро | SQLite cleanup: DELETE WHERE created_at < date('now', '-6 months') |
| Конфликт между BASE_PATTERNS (код) и kb_patterns (БД) | Seed BASE_PATTERNS в БД; в будущем — убрать из кода, оставить только БД |

---

## Критерий успеха

1. Каждый прогон advisor chain создаёт запись в `recommendation_log` (SQLite)
2. KB-паттерны загружаются из БД и применяются в `detect_signals()`
3. Validator проверяет рекомендации на конфликты с KB-правилами
4. Advisor может предложить новый паттерн; он сохраняется как `verified: false`
5. Нет регрессии — если observability или KB недоступны, chain работает как раньше (graceful)
