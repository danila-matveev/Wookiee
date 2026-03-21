# Advisor Phase 2 — активация chain в проде

**Date:** 2026-03-21
**Status:** Draft
**Author:** Claude + Danila
**Depends on:** `2026-03-21-advisor-agent-design.md` (Phase 1 — реализован)

## Problem

Advisor chain (Signal Detector → Advisor Agent → Validator Agent) полностью реализован, но не работает в проде. Причина: оркестратор пытается `json.loads(step_entry.result)` на текстовом Markdown-ответе Reporter/Marketer — получает пустой `structured_data`, chain пропускается.

Дополнительно: Signal Detector реализует только 5 из 25 паттернов (`_detect_plan_fact_signals`), остальные 3 детектора — стабы.

## Goal

Advisor chain начинает реально работать в проде: Reporter/Marketer → structured_data извлекается → Signal Detector находит паттерны → Advisor генерирует рекомендации → Validator проверяет → рекомендации попадают в отчёт.

## Non-Goals

- Самообучение (Phase 4 оригинального спека)
- Авто-режим паттернов (Phase 5)
- `recommendation_log` таблица (observability — Phase B)
- `kb_patterns.py` загрузчик (Phase B)
- Ежемесячный отчёт знаний (Phase B)

---

## Архитектура

### Ключевое решение: извлечение structured_data из tool call history

Вместо двухпроходного режима (collect_data + format_report) — извлекаем данные из `AgentResult.steps`. Каждый tool call Reporter/Marketer уже содержит JSON-результат. Нужно только собрать их.

```
Reporter работает как обычно (один проход):
  → вызывает get_brand_finance → JSON результат сохраняется в steps[0]
  → вызывает get_plan_vs_fact → JSON результат сохраняется в steps[1]
  → вызывает get_margin_levers → JSON результат сохраняется в steps[2]
  → формирует Markdown отчёт → content

Оркестратор ПОСЛЕ прогона:
  → проходит по steps[]
  → парсит tool_result каждого релевантного тула
  → добавляет _source tag
  → собирает structured_data dict
  → передаёт в Signal Detector
```

**Преимущества:**
- Zero дополнительных LLM-вызовов
- Zero изменений промптов Reporter/Marketer
- Данные детерминированные (из SQL), не галлюцинированные
- Обратно совместимо — если тул не вызван, данных просто нет

### Data flow (полный)

```
run_chain():
  Шаг 1: Reporter/Marketer (как сейчас)
    → AgentResult с .steps[] (tool call history)
    |
  Шаг 2: _extract_structured_data(agent_result)
    → Проходит по steps[], парсит tool_result
    → SOURCE_MAP: tool_name → _source tag
    → Возвращает dict с ключами: plan_vs_fact, brand_finance, margin_levers, ...
    |
  Шаг 3: detect_signals(structured_data) — вызывается N раз, по одному на каждый source
    → Список Signal объектов
    |
  Шаг 4: _run_advisor_chain(signals, structured_data) — как сейчас
    → Advisor → Validator → retry → результат
    |
  Шаг 5: Reporter/Marketer рендерит рекомендации (через промпт, уже реализовано)
```

---

## Компонент 1: Извлечение structured_data

### Новый метод в orchestrator.py

```python
SOURCE_MAP = {
    "get_plan_vs_fact": "plan_vs_fact",
    "get_brand_finance": "brand_finance",
    "get_margin_levers": "margin_levers",
    "get_advertising_stats": "advertising",
    "get_model_breakdown": "model_breakdown",
}

def _extract_structured_data(self, result: AgentResult) -> dict:
    """Extract structured data from agent's tool call history."""
    collected = {}
    for step in result.steps:
        source_tag = SOURCE_MAP.get(step.tool_name)
        if not source_tag or not step.tool_result:
            continue
        try:
            parsed = json.loads(step.tool_result)
            if isinstance(parsed, dict):
                parsed["_source"] = source_tag
                # Несколько вызовов одного тула (разные каналы) — собираем в список
                if source_tag in collected:
                    if not isinstance(collected[source_tag], list):
                        collected[source_tag] = [collected[source_tag]]
                    collected[source_tag].append(parsed)
                else:
                    collected[source_tag] = parsed
        except (json.JSONDecodeError, TypeError):
            continue
    return collected
```

### Изменение в run_chain()

Текущий код (lines 138-148):
```python
# БЫЛО: пытается json.loads на текстовом result
structured_data = {}
for step_entry in chain_history:
    if step_entry.agent in ("reporter", "marketer", "funnel"):
        try:
            parsed = json.loads(step_entry.result)
            ...
```

Новый код:
```python
# СТАЛО: извлекает из tool call history
structured_data = {}
for step_entry in chain_history:
    if step_entry.agent in ("reporter", "marketer", "funnel"):
        if hasattr(step_entry, 'agent_result') and step_entry.agent_result:
            extracted = self._extract_structured_data(step_entry.agent_result)
            structured_data.update(extracted)
```

### Сохранение AgentResult в chain_history

Нужно расширить `AgentStep` — добавить поле `agent_result: Optional[AgentResult]` (не сериализуется, используется только в runtime).

Или проще: сохранять AgentResult в отдельный dict `self._agent_results: dict[str, AgentResult]` по имени агента, и доставать оттуда при извлечении.

**Выбор:** отдельный dict `_agent_results` — не ломает существующий AgentStep, не увеличивает memory footprint chain_history.

---

## Компонент 2: Signal Detector — вызов на множественных источниках

Текущий `detect_signals()` принимает один `data: dict` с одним `_source`. Нужно вызывать его для каждого источника:

```python
# В orchestrator._run_signal_detection()
all_signals = []
for source_tag, source_data in structured_data.items():
    if isinstance(source_data, list):
        for item in source_data:
            all_signals.extend(detect_signals(item))
    else:
        all_signals.extend(detect_signals(source_data))
```

---

## Компонент 3: Реализация стабов Signal Detector

### _detect_finance_signals(data) — source: brand_finance

Входные данные из `get_brand_finance`:
```python
data["brand"]["current"]  # margin_pct, drr_pct, logistics, cogs, turnover_days, roi_annual
data["brand"]["previous"] # те же поля
data["brand"]["changes"]  # {metric}_change_pct
```

Паттерны для реализации:

| Паттерн | Логика | Severity |
|---------|--------|----------|
| `margin_pct_drop` | `margin_pct` текущая < предыдущей на > 2 п.п., при этом revenue растёт | warning/critical |
| `cogs_anomaly` | `cogs_per_unit` change_pct > 5% | critical |
| `logistics_overweight` | `logistics` / `revenue` > 8% | warning |
| `price_signal` | abs(avg_check_orders - avg_check_sales) / avg_check_sales > 5% | info |

### _detect_margin_lever_signals(data) — source: margin_levers

Входные данные из `get_margin_levers`:
```python
data["levers"]     # price_before_spp_per_unit, spp_pct, drr_pct, logistics_per_unit, cogs_per_unit
data["waterfall"]  # revenue_change, commission_change, advertising_change, ...
```

Паттерны для реализации:

| Паттерн | Логика | Severity |
|---------|--------|----------|
| `spp_shift_up` | `spp_pct.current - spp_pct.previous > 2` | info |
| `spp_shift_down` | `spp_pct.previous - spp_pct.current > 2` | warning |
| `adv_overspend` | `drr_pct.current > 12` (WB) или `> 18` (Ozon) | warning/critical |
| `adv_underspend` | `drr_pct.current < 3` и revenue не растёт | info |

### _detect_advertising_signals(data) — НОВЫЙ детектор, source: advertising

Входные данные из `get_advertising_stats`:
```python
data["advertising"]["current"]  # ctr_pct, cpo_rub, ad_spend, ad_orders
data["advertising"]["previous"]
data["funnel"]["current"]       # cart_to_order_pct (только WB)
data["funnel"]["previous"]
```

Паттерны:

| Паттерн | Логика | Severity |
|---------|--------|----------|
| `ctr_drop` | `ctr_pct < 2%` (WB) или `< 1.5%` (Ozon) | warning |
| `cart_to_order_drop` | `cart_to_order_pct` упал > 5 п.п. WoW | warning |
| `cro_improvement` | `cr_full_pct` вырос > 1 п.п. | info |
| `buyout_drop` | `order_to_buyout_pct < 45%` (WB) | warning |

### _detect_model_signals(data) — НОВЫЙ детектор, source: model_breakdown

Входные данные из `get_model_breakdown`:
```python
data["models"]  # список моделей с margin_pct, drr_pct, turnover_days, roi_annual, margin
```

Паттерны:

| Паттерн | Логика | Severity |
|---------|--------|----------|
| `low_roi_article` | `roi_annual < 50` и `margin_pct < 15` и `turnover_days > median * 1.5` | warning |
| `high_roi_opportunity` | `turnover_days < median * 0.5` и `margin_pct > 25` | info |
| `big_inefficient` | top-5 по revenue, `margin_pct < 10` | warning |
| `romi_critical` | модель с `drr_pct > 0` и ROMI < 50% (margin/adv_total < 0.5) | critical |
| `cac_exceeds_profit` | `adv_total / orders_count > margin / sales_count` (CAC > profit per sale) | critical |
| `status_mismatch` | модель помечена "Выводим", но ABC=A/B и `margin_pct > 15%` | critical |

### _detect_kb_pattern_signals(data, kb_patterns) — generic pattern matcher

KB-паттерны хранят `trigger_condition` как JSON:
```python
{"metric": "drr_pct", "operator": ">", "threshold": 12, "scope": "brand"}
```

Реализация — generic evaluator:
```python
def _evaluate_condition(condition: dict, data: dict) -> bool:
    metric = condition.get("metric")
    operator = condition.get("operator")
    threshold = condition.get("threshold")
    value = _extract_metric(data, metric)  # deep get by dotted path
    if value is None:
        return False
    return _compare(value, operator, threshold)
```

Операторы: `>`, `<`, `>=`, `<=`, `==`, `gap_gt` (для пар метрик).

---

## Компонент 4: Обновление detect_signals() dispatcher

Текущий dispatcher знает 3 source:
```python
if source == "plan_vs_fact": ...
if source == "brand_finance": ...
if source == "margin_levers": ...
```

Добавить:
```python
if source == "advertising": signals.extend(_detect_advertising_signals(data))
if source == "model_breakdown": signals.extend(_detect_model_signals(data))
```

Все детекторы — graceful: если нужных полей нет в data, возвращают `[]`.

---

## Файловая структура изменений

```
# MODIFY
agents/oleg/orchestrator/orchestrator.py   # _extract_structured_data(), обновить run_chain()
shared/signals/detector.py                 # 4 новых детектора + обновить dispatcher

# TESTS
tests/shared/signals/test_finance_signals.py     # тесты _detect_finance_signals
tests/shared/signals/test_margin_lever_signals.py # тесты _detect_margin_lever_signals
tests/shared/signals/test_advertising_signals.py  # тесты _detect_advertising_signals
tests/shared/signals/test_model_signals.py        # тесты _detect_model_signals
tests/shared/signals/test_kb_pattern_signals.py   # тесты _detect_kb_pattern_signals
tests/agents/oleg/orchestrator/test_extract_structured_data.py  # тесты извлечения
```

---

## Риски и mitigation

| Риск | Mitigation |
|------|-----------|
| `tool_result` обрезан до 2000 символов в AgentStep | Читаем из AgentResult.steps напрямую (не из chain_history AgentStep) |
| Тул не вызван (Reporter решил не вызывать get_margin_levers) | Graceful skip — детектор просто не вызывается для этого source |
| Несколько вызовов одного тула (WB + Ozon) | Собираем в список, обрабатываем каждый |
| get_model_breakdown возвращает большой JSON | Не проблема — парсится в memory, не передаётся в LLM |
| Ложные сигналы на некачественных данных | validate_data_quality уже вызывается Reporter; добавить проверку quality flag |

---

## Критерий успеха

1. При запуске дневного/недельного отчёта advisor chain активируется и генерирует хотя бы 1 рекомендацию (если данные содержат аномалию)
2. Все 25 паттернов из BASE_PATTERNS имеют работающий детектор (graceful skip если данных нет)
3. Нет регрессии в существующих отчётах — если advisor chain падает, отчёт выходит как раньше
4. 32+ новых тестов проходят
