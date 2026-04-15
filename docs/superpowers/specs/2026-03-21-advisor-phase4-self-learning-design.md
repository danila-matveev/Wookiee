# Advisor Phase 4 — Self-Learning & Feedback Loop

**Date:** 2026-03-21
**Status:** Draft (реализация после Phase 3 + 2-3 месяца накопления данных)
**Author:** Claude + Danila
**Depends on:** Phase 3 (`advisor-phase3-observability-design.md`)

## Контекст

Phase 3 реализует:
- `recommendation_log` (SQLite) — каждый прогон advisor chain логируется
- `kb_patterns` (Supabase) — загрузчик и generic evaluator
- Self-Learning (manual) — advisor предлагает `new_patterns`, они сохраняются как `verified: false`

**Что остаётся нерешённым после Phase 3:**

1. **Нет обратной связи** — пользователь видит рекомендации, но не может подтвердить или отклонить их
2. **Нет анализа эффективности** — нельзя понять, какие паттерны срабатывают часто, а какие бесполезны
3. **Подтверждение паттернов только вручную** — через SQL, нет UI
4. **Нет порогового тюнинга** — пороги меняются только через код или SQL

---

## Проблема

Advisor chain генерирует рекомендации, но работает в открытом цикле (open-loop):
- Нет данных о том, была ли рекомендация полезна
- Нет механизма "запомнить" хорошую/плохую рекомендацию
- Паттерны предлагаются, но лежат в `verified: false` без возможности подтверждения
- Пороги статичны — нельзя адаптировать к сезону или изменению ассортимента

---

## Goals

1. **Telegram Feedback Loop**: пользователь может оценить рекомендацию (полезно/бесполезно/неточно) прямо в Telegram
2. **Pattern Confirmation UI**: предложенные паттерны можно подтвердить/отклонить через Telegram (inline кнопки)
3. **Effectiveness Dashboard**: SQL-запросы + периодический отчёт: какие сигналы срабатывают, validation pass rate, top rejected patterns
4. **Threshold Tuning**: Telegram-команда для изменения порога существующего KB-паттерна

## Non-Goals

- Автоматическое изменение порогов (Phase 5)
- ML-модель для prediction quality (Phase 5)
- Web-UI (только Telegram)
- Real-time alerts (отдельная задача)

---

## Компонент 1: Feedback Collection

### Формат в Telegram

После каждого блока рекомендаций в отчёте добавляется inline-кнопки:

```
📋 Рекомендация: Снизить ДРР на модели X — перераспределить бюджет на модель Y

[👍 Полезно] [👎 Неточно] [🤔 Не актуально]
```

### Хранение feedback

Новая таблица в SQLite (`recommendation_feedback`):

```sql
CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_log_id INTEGER NOT NULL,
    recommendation_idx INTEGER NOT NULL,     -- индекс рекомендации в массиве
    signal_type TEXT,                        -- тип сигнала
    feedback TEXT NOT NULL,                  -- useful | inaccurate | irrelevant
    user_comment TEXT,                       -- опциональный комментарий
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recommendation_log_id) REFERENCES recommendation_log(id)
);
```

### Callback flow

1. Telegram бот получает callback с `rec_feedback:{log_id}:{rec_idx}:{feedback}`
2. Записывает в `recommendation_feedback`
3. Отправляет подтверждение: "Спасибо за обратную связь!"

---

## Компонент 2: Pattern Confirmation

### Telegram UI

Когда advisor предлагает новый паттерн (Phase 3), оркестратор отправляет сообщение:

```
🔍 Advisor предлагает новый паттерн:

**high_cancellation_rate**
Высокий % отмен (>15%) — проблемы с карточкой
Severity: warning | Source: advertising
Confidence: medium

[✅ Подтвердить] [❌ Отклонить] [📝 Изменить порог]
```

### Callback flow

- **Подтвердить**: `UPDATE hub.kb_patterns SET verified = true WHERE pattern_name = ?`
- **Отклонить**: `DELETE FROM hub.kb_patterns WHERE pattern_name = ? AND verified = false`
- **Изменить порог**: бот запрашивает новое значение, обновляет `trigger_condition.threshold`

---

## Компонент 3: Effectiveness Analysis

### Периодический отчёт (weekly)

SQL-запросы к `recommendation_log` и `recommendation_feedback`:

```python
def generate_advisor_effectiveness_report(days: int = 7) -> dict:
    """Generate effectiveness report from recommendation_log."""
    return {
        "total_runs": "COUNT(*) FROM recommendation_log WHERE report_date >= ...",
        "avg_signals": "AVG(signals_count)",
        "validation_pass_rate": "SUM(verdict='pass') / COUNT(*)",
        "top_signal_types": "parsed from signals JSON, GROUP BY type",
        "feedback_summary": {
            "useful_pct": "COUNT(feedback='useful') / COUNT(*)",
            "inaccurate_pct": "...",
            "irrelevant_pct": "...",
        },
        "unverified_patterns_count": "COUNT(*) FROM kb_patterns WHERE verified = false",
    }
```

### Интеграция

- Отчёт генерируется как часть weekly отчёта (отдельная секция)
- Или по команде `/advisor_stats` в Telegram

---

## Компонент 4: Threshold Tuning

### Telegram-команда

```
/threshold high_drr 15
→ "Порог для high_drr изменён: 12% → 15%"
```

### Реализация

```python
def update_pattern_threshold(pattern_name: str, new_threshold: float) -> bool:
    """Update threshold for a kb_pattern."""
    # UPDATE hub.kb_patterns
    # SET trigger_condition = jsonb_set(trigger_condition, '{threshold}', new_threshold)
    # WHERE pattern_name = ? AND verified = true
```

### Защита

- Только verified паттерны можно тюнить
- Логирование каждого изменения порога (audit trail в `recommendation_log` или отдельная таблица)
- Пределы: threshold не может быть отрицательным, не может превышать разумный максимум (задаётся per-pattern)

---

## Файловая структура изменений

```
# MODIFY
agents/oleg/storage/state_store.py         # + recommendation_feedback table
agents/oleg/app.py                         # Telegram callback handlers
agents/oleg/orchestrator/orchestrator.py   # Send pattern confirmation to Telegram

# CREATE
agents/oleg/services/advisor_feedback.py   # Feedback collection + effectiveness analysis
shared/signals/kb_patterns.py              # + update_pattern_threshold()

# TESTS
tests/agents/oleg/services/test_advisor_feedback.py
```

---

## Prerequisite: данные от Phase 3

Phase 4 имеет смысл начинать только после:

1. **2-3 месяца работы Phase 3** — накопление `recommendation_log` записей
2. **Минимум 50 записей** в `recommendation_log` — достаточно для статистики
3. **Минимум 5 предложенных паттернов** в `kb_patterns` (verified=false) — есть что подтверждать
4. **Validation pass rate > 70%** — chain стабилен и генерирует осмысленные рекомендации

Без этих данных Phase 4 будет инфраструктурой без контента.

---

## Критерий успеха

1. Пользователь может оценить каждую рекомендацию через Telegram (3 кнопки)
2. Предложенные паттерны можно подтвердить/отклонить через Telegram
3. Еженедельный effectiveness report генерируется автоматически
4. Пороги KB-паттернов можно менять через Telegram-команду
5. Все feedback и изменения логируются (audit trail)
