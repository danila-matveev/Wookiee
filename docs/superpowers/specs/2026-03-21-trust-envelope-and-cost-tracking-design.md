# Trust Envelope + Cost Tracking — Design Spec

**Дата**: 2026-03-21
**Статус**: Draft
**Контекст**: Оценка 5 принципов мультиагентных систем → выбраны Принцип 3 (Confidence) и Принцип 5 (Экономические границы)

---

## Цели

1. **Trust Envelope** — каждый агент сопровождает выводы оценкой достоверности, чтобы человек видел не факты, а вероятности
2. **Cost Tracking** — замкнуть существующий pipeline: токены и стоимость записываются в БД на каждый запуск агента и оркестратора

---

## Часть 1: Trust Envelope

### 1.1. `_meta` блок в артефакте агента

Каждый агент ОБЯЗАН включить блок `_meta` в корень JSON-артефакта:

```json
{
  "_meta": {
    "confidence": 0.82,
    "confidence_reason": "данные за 7/7 дней, все каналы",
    "data_coverage": 0.95,
    "limitations": [],
    "conclusions": [
      {
        "statement": "Маржа выросла за счёт снижения логистики",
        "type": "driver",
        "confidence": 0.91,
        "confidence_reason": "данные 7/7 дней, невязка 0.3%",
        "data_coverage": 0.98,
        "sources": ["get_margin_levers", "get_logistics_costs"]
      },
      {
        "statement": "SPP вырос и снизил маржу на 38К",
        "type": "anti_driver",
        "confidence": 0.68,
        "confidence_reason": "SPP точный, но эффект оценён без учёта промо",
        "data_coverage": 0.95,
        "limitations": [
          "промо 18-20 марта мог исказить базовый SPP",
          "нет данных по SPP от OZON"
        ],
        "sources": ["get_margin_levers", "get_brand_finance"]
      }
    ]
  },
  "period": {},
  "...остальной артефакт..."
}
```

### 1.2. Поля `_meta` — верхний уровень (секция)

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `confidence` | float 0.0–1.0 | обязательно | Общая надёжность выводов агента |
| `confidence_reason` | string | обязательно | Почему такой confidence (человекочитаемо) |
| `data_coverage` | float 0.0–1.0 | обязательно | Доля доступных данных от ожидаемых |
| `limitations` | string[] | обязательно (может быть []) | Конкретные оговорки |
| `conclusions` | object[] | обязательно | Ключевые выводы с индивидуальной метой |

### 1.3. Поля `conclusions[]` — уровень вывода

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `statement` | string | обязательно | Формулировка вывода (1 предложение) |
| `type` | enum | обязательно | `driver`, `anti_driver`, `recommendation`, `anomaly`, `metric` |
| `confidence` | float 0.0–1.0 | обязательно | Надёжность конкретного вывода |
| `confidence_reason` | string | обязательно | Почему такой confidence |
| `data_coverage` | float 0.0–1.0 | обязательно | Покрытие данных для этого вывода |
| `limitations` | string[] | если confidence < 0.75 | Оговорки |
| `sources` | string[] | обязательно | Какие MCP tools использовались |

### 1.4. Визуальные маркеры (3 уровня)

| Маркер | Диапазон confidence | Значение |
|--------|---------------------|----------|
| 🟢 | >= 0.75 | Надёжный вывод |
| 🟡 | 0.45–0.74 | Вывод с оговорками |
| 🔴 | < 0.45 | Низкая достоверность |

### 1.5. Санитарная проверка (runner.py)

После парсинга артефакта runner.py проверяет:

```python
# Если данных мало — confidence не может быть высоким
if meta.get("data_coverage", 1.0) < 0.5 and meta.get("confidence", 0) > 0.6:
    meta["confidence"] = min(meta["confidence"], 0.5)
    meta.setdefault("limitations", []).append(
        "confidence снижен автоматически: data_coverage < 50%"
    )
```

### 1.6. Отображение в Notion (полный отчёт)

#### Section 0. Паспорт — таблица достоверности

```markdown
## ▶ 0. Паспорт отчёта

**Период**: 17–23 марта 2026
**Сравнение с**: 10–16 марта 2026
**Каналы**: ВБ + ОЗОН

### Достоверность

| Блок анализа | Достоверность | Покрытие данных | Примечание |
|---|---|---|---|
| Маржа | 🟢 0.91 | 98% | — |
| Выручка | 🟢 0.85 | 95% | лаг выкупов 3-21 день |
| Реклама | 🟡 0.64 | 78% | OZON кабинет не обновлялся 2 дня |

**Ограничения этого отчёта:**
- OZON данные отсутствуют за 19-20 марта
- Маржа по 3 новым SKU = 0 (нет себестоимости)
```

#### Внутри секций — toggle-блоки на ключевых выводах

```markdown
## ▶ 1. Маржинальность 🟢

Маржа бренда: 847 200 ₽ (+12.3% к прошлой неделе).
Главный драйвер роста — снижение логистики на 14 ₽/шт.

▶ 🟢 0.91 | Маржа выросла за счёт логистики
  ├ confidence_reason: данные за 7/7 дней, все каналы, невязка 0.3%
  ├ data_coverage: 98%
  └ источники: get_margin_levers, get_logistics_costs

Главный антидрайвер — рост SPP на WB (+2.1 п.п.), ~38 000 ₽.

▶ 🟡 0.68 | SPP вырос и снизил маржу на 38К
  ├ confidence_reason: SPP точный, но эффект оценён без учёта промо
  ├ data_coverage: 95%
  ├ limitations:
  │   • промо 18-20 марта мог исказить базовый SPP
  │   • нет данных по SPP от OZON
  └ источники: get_margin_levers, get_brand_finance
```

#### Правила отображения toggle с метой

| Тип вывода (type) | Когда показывать полную мету |
|---|---|
| `driver` / `anti_driver` | Всегда |
| `recommendation` | Всегда |
| `anomaly` | Всегда |
| `metric` | Только если confidence < 0.75 |

### 1.7. Отображение в Telegram (краткий формат)

Одна строка в футере — **средневзвешенный confidence**:

```
<i>🟢 0.85 | Агентов: 3/3 | 42с</i>
```

Если есть 🟡/🔴 агенты — дополнительная строка с самым критичным ограничением:

```
<i>🟡 0.68 | ⚠️ Реклама: OZON кабинет не обновлялся</i>
<i>Агентов: 3/3 | 42с</i>
```

### 1.8. Агрегация confidence по оркестратору

```python
# Средневзвешенный confidence
weights = {
    "margin-analyst": 1.0,
    "revenue-decomposer": 1.0,
    "ad-efficiency": 1.0,
    "price-strategist": 1.0,
    "pricing-impact-analyst": 0.5,
    "hypothesis-tester": 0.5,
    "anomaly-detector": 0.5,
}

aggregate = sum(w * c for w, c in zip(weights, confidences)) / sum(weights)
```

---

## Часть 2: Cost Tracking

### 2.1. Текущее состояние

| Компонент | Статус |
|---|---|
| DB schema (agent_runs, orchestrator_runs) | Готово — поля prompt_tokens, completion_tokens, total_tokens, cost_usd есть |
| Logger (services/observability/logger.py) | Готово — принимает token-поля |
| Config pricing dict | Готово — agents/v3/config.py:19-23 |
| runner.py — извлечение токенов из LLM | НЕ РЕАЛИЗОВАНО (передаёт None) |
| orchestrator.py — агрегация | НЕ РЕАЛИЗОВАНО (передаёт 0/0.0) |
| Telegram footer — стоимость | Поле есть, но показывает $0.00 |

### 2.2. Что нужно реализовать

#### runner.py — извлечение токенов

После `agent.ainvoke()` извлечь usage из последнего AIMessage:

```python
# LangChain ChatOpenAI через OpenRouter возвращает usage в response_metadata
messages = result["messages"]
usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

for msg in messages:
    if hasattr(msg, "response_metadata"):
        token_usage = msg.response_metadata.get("token_usage", {})
        usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
        usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
        usage["total_tokens"] += token_usage.get("total_tokens", 0)

# Расчёт стоимости
model = config.MODEL_MAIN  # или из agent_config
rates = config.PRICING.get(model, {"input": 0.001, "output": 0.001})
cost_usd = round(
    (usage["prompt_tokens"] / 1_000_000) * rates["input"]
    + (usage["completion_tokens"] / 1_000_000) * rates["output"],
    6,
)
```

Добавить в возвращаемый dict агента:

```python
return {
    "agent_name": ...,
    "status": ...,
    "artifact": ...,
    "raw_output": ...,
    "duration_ms": ...,
    "run_id": ...,
    # NEW:
    "prompt_tokens": usage["prompt_tokens"],
    "completion_tokens": usage["completion_tokens"],
    "total_tokens": usage["total_tokens"],
    "cost_usd": cost_usd,
}
```

#### orchestrator.py — агрегация

```python
total_tokens = sum(r.get("total_tokens", 0) for r in agent_results)
total_cost = sum(r.get("cost_usd", 0.0) for r in agent_results)

log_orchestrator_run(
    ...,
    total_tokens=total_tokens,
    total_cost_usd=total_cost,
)
```

#### Telegram footer

```python
# Было:
footer = f"Агентов: {succeeded}/{called} | Время: {duration:.1f}с"

# Стало:
footer = f"${total_cost:.4f} | Агентов: {succeeded}/{called} | {duration:.1f}с"
```

---

## Затрагиваемые файлы

| Файл | Изменения |
|---|---|
| `agents/v3/agents/*.md` (все ~20 агентов) | Добавить `_meta` с `conclusions` в Output Format |
| `agents/v3/agents/report-compiler.md` | Правила отображения маркеров, таблица Достоверности, toggle-блоки |
| `agents/v3/runner.py` | Санитарная проверка `_meta` + извлечение токенов + расчёт cost |
| `agents/v3/orchestrator.py` | Агрегация confidence + агрегация токенов/cost |
| `agents/v3/delivery/telegram.py` | Строка confidence + cost в футере |
| `agents/v3/config.py` | Возможно обновить PRICING если модели изменились |

---

## Что НЕ входит в scope

- Уровни автономии (Принцип 2) — будет при создании исполнительных агентов
- actionability параметр — будет при создании исполнительных агентов
- Red team агенты (Принцип 4) — оверкилл для аналитики
- Triangulation — уже заложена в фазовой архитектуре оркестратора
- Автоматический downgrade моделей — отдельная задача
- Per-agent ROI tracking — нужна бизнес-метрика привязки, отдельная задача
