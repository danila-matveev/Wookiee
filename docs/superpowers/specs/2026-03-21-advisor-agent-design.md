# Advisor Agent — универсальный рекомендательный движок

**Date:** 2026-03-21
**Status:** Draft
**Author:** Claude + Danila

## Problem

Текущие отчёты (финансовые, маркетинговые) показывают цифры, но не объясняют **почему** и не дают **что делать**. План-факт показывает "маржа +6.1%", но не говорит: "рост за счёт низкомаржинальной модели, перераспредели рекламу". Владельцу бизнеса нужны actionable рекомендации, привязанные к главным целям: максимизация оборачиваемости x маржинальности.

## Solution

Универсальный рекомендательный слой из трёх компонентов:

1. **Signal Detector** (Python-модуль) — детерминированное обнаружение паттернов в любых данных
2. **Advisor Agent** (LLM суб-агент) — интерпретация сигналов в рекомендации с разной глубиной
3. **Validator Agent** (LLM + скрипты) — перепроверка рекомендаций перед включением в отчёт

Плюс система самообучения: обнаруженные паттерны наполняют базу знаний.

## Goals

1. Каждый отчёт (финансовый, маркетинговый, любой будущий) содержит секцию рекомендаций
2. Рекомендации привязаны к оборачиваемости и маржинальности — главным бизнес-метрикам
3. Глубина рекомендаций зависит от типа отчёта (ежедневный / еженедельный / ежемесячный)
4. Все рекомендации проходят валидацию перед публикацией
5. Библиотека паттернов растёт со временем (вручную + semi-auto + авто)
6. Advisor доступен любому агенту системы, включая оркестратор Олег

## Non-Goals

- Автоматическое выполнение рекомендаций (пока только предложения, не действия)
- Замена существующих агентов (Reporter, Marketer продолжают работать, Advisor дополняет)
- Полная автоматизация добавления паттернов без подтверждения (авто-режим — только с verified: false)

---

## Architecture

### Оркестрация: chain-паттерн через Олега

Advisor и Validator — полноценные суб-агенты, которых вызывает **оркестратор** (Олег) как шаги цепочки. Суб-агенты (Reporter, Marketer) **не вызывают друг друга напрямую** — это сохраняет существующую архитектуру без вложенных ReactLoop'ов.

```
Олег (оркестратор) управляет цепочкой:

Шаг 1: Reporter / Marketer
  - Собирает данные через свои тулы
  - Возвращает structured_data (не финальный текст)
    |
    v
Шаг 2: Signal Detector (Python, вызывается Олегом)
  - detect_signals(structured_data) -> signals[]
  - Чистая функция: данные + kb_patterns на вход, signals на выход
  - KB-паттерны передаются Олегом (запрашивает заранее)
    |
    v
Шаг 3: Advisor Agent
  - Получает: signals[] + structured_data + kb_patterns + report_type
  - Возвращает: recommendations[] + new_patterns[]
    |
    v
Шаг 4: Validator Agent
  - Получает: recommendations[] + signals[] + structured_data
  - Запускает скрипты-тулы для проверки
  - Verdict: pass / fail
    |
    +-- pass --> Шаг 5
    +-- fail --> Олег возвращает ошибки Advisor (Шаг 3, попытка 2)
                  +-- 2-й fail --> Шаг 5 без рекомендаций
    |
    v
Шаг 5: Reporter / Marketer (финализация)
  - Получает: свои данные + validated recommendations
  - Формирует финальный отчёт с секцией "Рекомендации Advisor"
```

### Chain-паттерны в оркестраторе

```python
# agents/oleg/orchestrator.py — новые цепочки
CHAIN_PATTERNS = {
    # Финансовый отчёт с рекомендациями
    "financial_report_with_advisor": [
        ("reporter", "collect_data"),     # Reporter собирает данные
        ("signal_detector", "detect"),     # Python: detect_signals()
        ("advisor", "recommend"),          # Advisor: рекомендации
        ("validator", "validate"),         # Validator: проверка
        ("reporter", "format_report"),     # Reporter: финальный отчёт
    ],
    # Маркетинговый отчёт с рекомендациями
    "marketing_report_with_advisor": [
        ("marketer", "collect_data"),
        ("signal_detector", "detect"),
        ("advisor", "recommend"),
        ("validator", "validate"),
        ("marketer", "format_report"),
    ],
    # Олег сам проверяет любой отчёт
    "advisor_review": [
        ("signal_detector", "detect"),
        ("advisor", "recommend"),
        ("validator", "validate"),
    ],
}
```

### Кто вызывает Advisor

| Вызывающий | Когда | report_type | Chain-паттерн |
|------------|-------|-------------|---------------|
| Олег (для Reporter) | Финансовый отчёт | daily / weekly / monthly | financial_report_with_advisor |
| Олег (для Marketer) | Маркетинговый отчёт | daily / weekly / monthly | marketing_report_with_advisor |
| Олег (проверка) | Ревью любого отчёта | определяется из контекста | advisor_review |
| Олег (ad-hoc) | Пользователь спросил | custom (лимит: 10 рекомендаций) | advisor_review |

### Data flow: как Reporter отдаёт structured_data

Reporter и Marketer получают новый режим работы: `collect_data` — собрать данные и вернуть structured dict (не текст отчёта). Финализация (`format_report`) — отдельный шаг, куда приходят данные + рекомендации.

```python
# AgentResult расширяется:
class AgentResult:
    content: str              # текстовый ответ (как сейчас)
    structured_data: dict     # НОВОЕ: данные для Signal Detector
    recommendations: list     # НОВОЕ: рекомендации от Advisor (заполняется оркестратором)
```

### Fallback при ошибках инфраструктуры

| Ситуация | Поведение |
|----------|-----------|
| Signal Detector: exception | Отчёт без рекомендаций, лог ошибки |
| KB недоступна | Signal Detector работает только на базовых паттернах (без KB) |
| Advisor: timeout (120с) | Отчёт без рекомендаций, лог ошибки |
| Validator: timeout (120с) | Рекомендации включаются БЕЗ валидации (с пометкой "не проверено") |

### Стоимость

| Агент | Модель | Примерные токены/вызов | Стоимость на 1000 отчётов |
|-------|--------|----------------------|--------------------------|
| Signal Detector | Python (без LLM) | 0 | $0 |
| Advisor | LIGHT (gemini-2.0-flash) | ~2000 in + ~1500 out | ~$1.75 |
| Validator | LIGHT (gemini-2.0-flash) | ~3000 in + ~500 out | ~$1.75 |
| **Итого доп. стоимость** | | | **~$3.50 / 1000 отчётов** |

---

## Signal Detector

### Расположение

`shared/signals/detector.py` — универсальный Python-модуль, не привязан к конкретному агенту.

### Формат сигнала

```python
{
    "id": "margin_lag_orders_2026-03-19",
    "type": "margin_lags_orders",
    "category": "margin",          # margin | turnover | funnel | adv | price | model
    "severity": "warning",         # info | warning | critical
    "impact_on": "margin",         # что пострадает: margin | turnover | both
    "data": {                      # точные числа для валидатора
        "orders_completion_pct": 113.9,
        "margin_completion_pct": 106.1,
        "gap_pct": 7.8
    },
    "hint": "Заказы растут быстрее маржи на 7.8 п.п.",
    "source": "plan_vs_fact"       # какой тул породил данные
}
```

### Базовые паттерны (стартовый набор — 25 штук)

#### 5 рычагов маржи

| Паттерн | Категория | Что ловит | Severity |
|---------|-----------|-----------|----------|
| `margin_lags_orders` | margin | Заказы растут быстрее маржи (разрыв > 5 п.п.) | warning |
| `spp_shift_up` | price | СПП выросла > 2 п.п. — можно поднять базовую цену | info |
| `spp_shift_down` | price | СПП упала > 2 п.п. — клиентская цена выросла, конверсия под угрозой | warning |
| `adv_overspend` | adv | ДРР выше нормы (>12% внутр. WB, >18% внутр. Ozon) | warning |
| `adv_underspend` | adv | ДРР ниже нормы, но заказы не растут — мало трафика | info |
| `logistics_overweight` | margin | Логистика > 8% от выручки | warning |
| `cogs_anomaly` | margin | Себестоимость отклонилась > 5% от нормы | critical |

#### Воронка

| Паттерн | Категория | Что ловит | Severity |
|---------|-----------|-----------|----------|
| `ctr_drop` | funnel | CTR < 2% (WB) или < 1.5% (Ozon) | warning |
| `cart_to_order_drop` | funnel | CR корзина-заказ упал > 5 п.п. WoW | warning |
| `cro_improvement` | funnel | Сквозная конверсия выросла | info |
| `sales_lag_expected` | funnel | Заказы растут значительно, продажи слабо — выкупы догонят | info |
| `sales_lag_problem` | funnel | Заказы растут, продажи падают — возвраты или отмены | critical |
| `buyout_drop` | funnel | Выкуп < 45% WB или < 30% Ozon | warning |

#### Реклама

| Паттерн | Категория | Что ловит | Severity |
|---------|-----------|-----------|----------|
| `romi_critical` | adv | ROMI < 50% | critical |
| `cac_exceeds_profit` | adv | CAC > маржа на единицу | critical |
| `keyword_drain` | adv | Ключ: много трафика, 0 заказов | warning |
| `organic_declining` | adv | Доля органики упала > 5 п.п. WoW | warning |
| `ad_no_organic_growth` | adv | Рекламируем, но органика не растёт | warning |

#### Оборачиваемость + ABC

| Паттерн | Категория | Что ловит | Severity |
|---------|-----------|-----------|----------|
| `low_roi_article` | turnover | ABC=C + маржа <15% + оборачиваемость >1.5x медианы | warning |
| `high_roi_opportunity` | turnover | Быстрая оборачиваемость + маржа >25% | info |
| `big_inefficient` | model | ABC=A/B + маржа <10% | warning |
| `status_mismatch` | model | "Выводим" + ABC=A/B + маржа >15% | critical |

#### Ценовые и каскадные

| Паттерн | Категория | Что ловит | Severity |
|---------|-----------|-----------|----------|
| `price_signal` | price | Ср. чек заказов != ср. чек продаж (> 5%) — прогноз выручки | info |
| `margin_pct_drop` | margin | Маржинальность % падает при росте выручки | warning |
| `price_up_rank_risk` | price | Цена поднята — риск потери позиций и роста ДРР | info |

### KB-паттерны

Signal Detector — чистая функция без сетевых вызовов. KB-паттерны передаются на вход от оркестратора, который запрашивает их заранее. Это позволяет расширять библиотеку без изменения кода детектора.

```python
# Оркестратор запрашивает KB-паттерны перед вызовом детектора:
kb_patterns = search_kb("business patterns for signal detection")

# Детектор — чистая функция:
signals = detect_signals(data=structured_data, kb_patterns=kb_patterns)
```

### Хранение паттернов: таблица `kb_patterns`

Текущая `kb_chunks` хранит текстовые чанки с embedding'ами — не подходит для структурированных бизнес-правил. Новая таблица:

```sql
CREATE TABLE kb_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(20) NOT NULL
        CHECK (category IN ('margin', 'turnover', 'funnel', 'adv', 'price', 'model')),
    trigger_condition JSONB NOT NULL,     -- {"metric": "drr", "operator": ">", "threshold": 12, "scope": "model"}
    action_hint TEXT,                      -- подсказка для Advisor
    impact_on VARCHAR(10) NOT NULL
        CHECK (impact_on IN ('margin', 'turnover', 'both')),
    severity VARCHAR(10) DEFAULT 'warning'
        CHECK (severity IN ('info', 'warning', 'critical')),
    source_tag VARCHAR(30) NOT NULL       -- manual | insight | auto
        CHECK (source_tag IN ('manual', 'insight', 'auto', 'base')),
    verified BOOLEAN DEFAULT FALSE,
    confidence VARCHAR(10) DEFAULT 'medium'
        CHECK (confidence IN ('high', 'medium', 'low')),
    trigger_count INT DEFAULT 0,          -- сколько раз сработал
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE kb_patterns ENABLE ROW LEVEL SECURITY;
CREATE POLICY service_full ON kb_patterns FOR ALL TO postgres USING (true) WITH CHECK (true);

-- Индексы
CREATE INDEX idx_kb_patterns_category ON kb_patterns(category);
CREATE INDEX idx_kb_patterns_verified ON kb_patterns(verified);
```

### Пороговые значения — конфигурация, не код

Все числовые пороги (ДРР > 12%, CTR < 2%, логистика > 8%) хранятся в `kb_patterns` с `source_tag: "base"` и `verified: true`. Это позволяет менять пороги через KB без изменения кода.

---

## Advisor Agent

### Определение

Новый суб-агент в `agents/oleg/agents/advisor/`. Микро-агент с собственным промптом и тулами.

### Вход

```python
{
    "signals": [...],            # от Signal Detector
    "report_type": "weekly",     # daily | weekly | monthly
    "context": "financial",      # financial | marketing | custom
    "kb_patterns": [...]         # релевантные паттерны из KB
}
```

### Выход (structured output)

```python
{
    "recommendations": [...],    # массив рекомендаций (см. формат ниже)
    "new_patterns": [...]        # обнаруженные новые паттерны для KB
}
```

### Глубина по типу отчёта

| | Ежедневный | Еженедельный | Ежемесячный |
|--|-----------|-------------|-------------|
| **Фокус** | Что горит прямо сейчас | Что делать на этой неделе | Стратегия на месяц |
| **Макс. рекомендаций** | 3 | 7 | 15 |
| **Severity** | Только critical + warning | Все | Все + стратегические |
| **Формат действия** | "Проверь ДРР по Wendy" | "Снизь ставку на ключ X с 300-200 руб, ожидаемый эффект: ДРР -3 п.п." | "Пересмотри ценообразование моделей группы B: поднять цену на 5% даст +180К маржи/мес" |
| **Новые паттерны** | Нет | Предлагает (semi-auto) | Предлагает + стратегические |

### Формат рекомендации

```python
{
    "signal_id": "margin_lags_orders_2026-03-19",
    "priority": 1,                    # 1 = делай первым
    "category": "margin",
    "diagnosis": "Заказы +13.9% к плану МТД, маржа только +6.1%. Разрыв 7.8 п.п.",
    "root_cause": "Модель Wendy (маржа 18%) даёт 35% прироста заказов. Низкомаржинальный рост.",
    "action": "Перераспределить рекламный бюджет: Wendy -30%, Joy +20%, Ruby +10%",
    "action_category": "optimize_keywords",  # для детерминированной проверки направления
    "expected_impact": {
        "metric": "маржинальность %",
        "delta": "+2.1 п.п.",
        "confidence": "medium"        # high | medium | low
    },
    "affects": "margin",              # margin | turnover | both
    "timeframe": "3-5 дней"           # когда увидим эффект
}
```

### Формат нового паттерна (для KB)

```python
{
    "pattern_name": "wendy_drags_margin_at_high_drr",
    "description": "Когда ДРР по Wendy > 12%, маржинальность бренда падает > 2 п.п.",
    "evidence": "Наблюдалось 3 раза за последние 30 дней",
    "category": "adv",
    "action": "auto_propose",         # auto_propose | auto_add
    "confidence": "medium"
}
```

### Языковые правила

- Аббревиатуры на русском: ДРР (не DRR), СПП (не SPP), МТД (не MTD)
- Confidence остаётся на английском: high / medium / low
- Валюта: руб, тыс, млн (не $, не rub)
- Все тексты рекомендаций на русском

---

## Validator Agent

### Определение

Отдельный суб-агент в `agents/oleg/agents/validator/`. Имеет доступ к детерминированным скриптам-тулам для проверки.

### Тулы Validator

**Детерминированные (Python-скрипты):**

```python
# 1. Числа в structured-полях рекомендации совпадают с signal.data?
# Сравнение field-by-field (не текстовый поиск), поэтому надёжно.
check_numbers(signal_data: dict, recommendation: dict) -> {
    "match": bool,
    "mismatches": [{"field": "orders_completion_pct", "signal": 113.9, "recommendation": 6.0}]
}
# Проверяет: diagnosis, expected_impact.delta — против signal.data

# 2. Все сигналы с severity >= warning покрыты рекомендациями?
check_coverage(signals: list, recommendations: list) -> {
    "covered": ["signal_1", "signal_2"],
    "missed": ["signal_3"],        # только warning/critical
    "info_skipped": ["signal_4"]   # info можно пропустить
}

# 3. Направление действия: mapping signal_type -> допустимые действия
check_direction(signal_type: str, action_category: str) -> {
    "valid": bool,
    "reason": "Сигнал 'adv_overspend' допускает: reduce_budget, optimize_keywords. Получено: increase_budget — конфликт"
}
# Использует явный маппинг (не NLP):
# DIRECTION_MAP = {
#     "adv_overspend": ["reduce_budget", "optimize_keywords", "pause_campaign"],
#     "adv_underspend": ["increase_budget", "expand_keywords"],
#     ...
# }
# Advisor указывает action_category в structured output.

# 4. Рекомендация не противоречит правилам из kb_patterns?
check_kb_rules(recommendation: dict, kb_patterns: list) -> {
    "conflicts": [{"pattern_id": 5, "rule": "не снижать цену при остатке < 14 дней", "conflict": "рекомендация предлагает снизить цену"}]
}
```

**LLM-проверка (Validator сам оценивает):**

```python
# 5. Expected impact реалистичен? (LLM-суждение, не скрипт)
# Validator сам оценивает: "дельта +2.1 п.п. маржинальности за 3-5 дней
# при перераспределении рекламы — это реалистично?"
# Это контекстная оценка, не формализуемая в код.
```

### Процесс валидации

1. Validator получает `recommendations[]` + `signals[]` + `original_data`
2. LLM решает, какие проверки запустить (не все нужны каждый раз)
3. Вызывает скрипты-тулы
4. Оценивает результаты + добавляет своё контекстное суждение
5. Возвращает verdict: `pass` или `fail` с причинами

### Retry логика

```
Advisor -> recommendations
                |
Validator: pass? ---> да ---> в отчёт
                |
                нет (fail + причины)
                |
Advisor: перегенерирует с учётом ошибок (попытка 2)
                |
Validator: pass? ---> да ---> в отчёт
                |
                нет ---> отчёт без рекомендаций (только данные)
```

---

## Самообучение: библиотека паттернов

### Три режима добавления

#### 1. Вручную (пользователь через чат)

Пользователь пишет: "Запомни: когда остаток < 14 дней, не снижать цену"

Бот (Christina / KB-агент) **обязательно** формализует и переспрашивает:

```
Я правильно понимаю, что вы хотите добавить правило в базу знаний?

Паттерн: "Когда остаток товара < 14 дней, не снижать цену"
Категория: price
Влияет на: turnover

Добавить? Да / Нет
```

**Без подтверждения — не сохранять.** Только после "Да":
- Сохраняется в KB с `source_tag: "manual"`, `verified: true`

#### 2. Semi-auto (Advisor предлагает, пользователь подтверждает)

В еженедельных и ежемесячных отчётах Advisor добавляет секцию:

```markdown
## Обнаруженные паттерны
1. Когда ДРР по Wendy > 12%, маржинальность бренда падает > 2 п.п.
   Наблюдалось: 3 раза за 30 дней. Confidence: medium.
   Добавить в базу знаний?
```

После подтверждения пользователем --> KB с `source_tag: "insight"`, `verified: true`

#### 3. Авто (в будущем, после набора доверия)

Advisor сам добавляет в KB с `verified: false`. Проверка:
- Если паттерн подтвердился на данных 3+ раз --> `verified: true` автоматически
- Если не подтвердился 3 раза --> удаляется

### Ежемесячный отчёт знаний (в Notion)

Раз в месяц Advisor формирует отчёт "Чему я научился" и публикует в Notion:

```markdown
# Отчёт знаний Advisor — Март 2026

## Активные паттерны (23)
| # | Паттерн | Категория | Источник | Срабатываний | Confidence |
|---|---------|-----------|----------|-------------|------------|
| 1 | ДРР Wendy > 12% -> маржа -2 п.п. | adv | insight | 5 | high |
| 2 | Остаток < 14 дней -> не снижать цену | price | manual | 2 | high |
| ... |

## Новые паттерны этого месяца (3)
- [описание + данные]

## Паттерны на проверке (verified: false) (2)
- [описание + сколько раз сработали]

## Устаревшие / удалённые (1)
- [что удалили и почему]
```

Пользователь может дать обратную связь прямо в Notion или в чате:
- "Паттерн #5 устарел, удали"
- "Паттерн #2 — измени порог с 14 на 10 дней"
- "Добавь новый: когда рейтинг падает > 0.2 за неделю — остановить рекламу"

### Жизненный цикл паттерна

```
Обнаружен --> Предложен --> Подтверждён --> Используется --> Проверка (каждые 30 дней)
                                                                |
                                                    Паттерн сработал на данных?
                                                    Да --> продолжает работать
                                                    Нет --> severity снижается --> архив
```

---

## Интеграция в отчёты

### Обязательная секция во ВСЕХ отчётах

Новая секция после план-факта (финансовый) или после ключевых метрик (маркетинговый):

```markdown
## Рекомендации Advisor

### Критичные (делай сегодня)
1. **ДРР по Wendy 14%** при норме 8% -> снизить ставку на ключ "белье женское" с 300 до 180 руб
   Ожидаемый эффект: ДРР -4 п.п., маржа +85 тыс/нед. Confidence: high.

### Внимание (на этой неделе)
2. **Заказы +14%, маржа +6%** -> рост за счёт низкомаржинальных моделей.
   Перераспределить бюджет: Wendy -30%, Joy +20%, Ruby +10%.
   Эффект: маржинальность +2.1 п.п. за 3-5 дней. Confidence: medium.

### Позитивные сигналы
3. **Заказы +10%, продажи +1%** -> лаг выкупов, продажи догонят через 5-10 дней.
```

### Цветовая маркировка severity

- Критичные = красный (critical + warning с impact > порога)
- Внимание = жёлтый (warning)
- Позитивные = зелёный (info с положительным трендом)

---

## Observability: аудит рекомендаций

Все рекомендации логируются для анализа качества:

```sql
CREATE TABLE hub.recommendation_log (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    report_type VARCHAR(10) NOT NULL,       -- daily | weekly | monthly
    context VARCHAR(20) NOT NULL,           -- financial | marketing | custom
    signals_count INT,
    recommendations_count INT,
    validation_verdict VARCHAR(10),         -- pass | fail | skipped
    validation_attempts INT DEFAULT 1,
    signals JSONB,                          -- полный массив сигналов
    recommendations JSONB,                  -- финальные рекомендации
    validation_details JSONB,               -- результаты проверок
    new_patterns JSONB,                     -- предложенные паттерны
    advisor_tokens_used INT,
    validator_tokens_used INT,
    total_duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rec_log_date ON hub.recommendation_log(report_date DESC);
```

Метрики для мониторинга:
- **Signal detection rate** — среднее кол-во сигналов на отчёт
- **Validation pass rate** — % рекомендаций, прошедших валидацию с первой попытки
- **Retry rate** — % случаев, когда потребовалась перегенерация
- **Pattern trigger rate** — какие паттерны срабатывают чаще всего

---

## Файловая структура

```
shared/signals/
  __init__.py
  detector.py              -- Signal Detector: detect_signals(data) -> signals[]
  patterns.py              -- базовые паттерны (25 штук)
  kb_patterns.py           -- загрузка паттернов из KB

agents/oleg/agents/advisor/
  agent.py                 -- Advisor Agent
  prompts.py               -- системный промпт
  tools.py                 -- тулы (search_kb, detect_signals)

agents/oleg/agents/validator/
  agent.py                 -- Validator Agent
  prompts.py               -- системный промпт
  tools.py                 -- тулы (check_numbers, check_coverage, check_direction, check_kb_rules)
  scripts/
    check_numbers.py       -- детерминированная проверка чисел (field-by-field)
    check_coverage.py      -- детерминированная проверка покрытия сигналов
    check_direction.py     -- маппинг signal_type -> допустимые action_category
    check_kb_rules.py      -- проверка на конфликты с kb_patterns

shared/signals/
  direction_map.py         -- DIRECTION_MAP: {signal_type -> [valid_actions]}
```

---

## Implementation Phases

### Phase 1: Signal Detector
- `shared/signals/` модуль с 25 базовыми паттернами
- Интеграция с `get_plan_vs_fact` — возвращает signals[] вместе с данными
- Юнит-тесты на каждый паттерн

### Phase 2: Advisor Agent
- Промпт, structured output, три глубины (daily/weekly/monthly)
- Интеграция с KB (подгрузка паттернов)
- Вызов из Reporter и Marketer

### Phase 3: Validator Agent
- 5 скриптов-тулов для проверки
- Retry логика (макс. 2 попытки)
- Интеграция в pipeline

### Phase 4: Самообучение
- Подтверждение через чат (формализация + "Да/Нет")
- Semi-auto предложения в еженедельных/ежемесячных отчётах
- Ежемесячный отчёт знаний в Notion

### Phase 5: Расширение
- Авто-режим (verified: false -> auto-verify после 3 подтверждений)
- Оркестратор Олег вызывает Advisor для проверки любых отчётов
- Расширение Signal Detector новыми источниками данных
