# Familia Evaluation Tool — Design Spec

## Summary

Multi-agent калькулятор для оценки целесообразности продажи затоваренных/выводимых артикулов бренда Wookiee в off-price сеть "Фамилия" (ООО "Максима Групп").

**Цель:** Для каждого выводимого артикула ответить — выгоднее продать в Familia со скидкой 50-60% от РРЦ или продолжать распродавать на WB/OZON?

## Context

### Бизнес-контекст
- Бренд Wookiee (нижнее бельё), оборот ~40М/мес на WB+OZON
- Есть затоваренные модели на собственном складе (МойСклад): Vuki (191-245d), Moon (116-176d), Alice/Valery (280-300d DEAD STOCK), Eva (убыточная)
- Не все артикулы модели выводятся — анализ на уровне артикулов, не моделей
- Ходовые модели (Wendy, Audrey, Charlotte, Ruby) НЕ рассматриваются

### Условия Familia (из договора)
- Покупатель: ООО "Максима Групп" (сеть "Фамилия")
- Оплата: **90 календарных дней** после поставки (п.5.1)
- Цена включает доставку до РЦ Бритово, МО (п.2.1)
- Одностороннее повышение цены запрещено (п.2.2)
- Штрафы: 1% за недовоз, 0.5% за опоздание >60 мин (п.6.2, 6.4)
- Допуск на расхождения: до 5% без акта (п.3.1.4)
- Проверка качества: 45 дней после поставки (п.3.1.3)
- ЭДО: КонтурДиадок, маркировка Честный Знак обязательна
- Поставка на РЦ Бритово: европаллеты 120x80, высота <=180см, масса короба <=30кг

### Ценовая модель
- Familia покупает со скидкой 50-60% от РРЦ (типично для off-price)
- Порог выгодности: положительная маржа (покрыть COGS + логистику + скрытые расходы)
- Идеал: 15-20% маржи
- Нужен полный сценарный анализ: при каких скидках в плюсе, в нуле, в минусе

### Ключевой принцип
Для dead stock с оборачиваемостью 200-300 дней, 90 дней отсрочки — это ускорение. Источник данных по остаткам — **МойСклад** (собственный склад в Москве).

## Architecture

### Pipeline (4 волны)

```
Wave 1: Collector (Python)
  └── МойСклад остатки + DB: COGS, РРЦ, скорость продаж, маржа МП, хранение
  
Wave 2: Calculator (Python)
  └── Сценарная матрица скидок 40-65%, breakeven, P&L по артикулу

Wave 3 (параллельно):
  ├── MP Comparator (LLM MAIN) — сравнение Familia vs WB/OZON
  └── Familia Expert (LLM MAIN) — скрытые расходы и риски договора

Wave 4: Advisor (LLM HEAVY)
  └── Синтез → решение по каждому артикулу → финальный отчёт
```

### Агенты

| Агент | Тип | Модель | Задача |
|-------|-----|--------|--------|
| Collector | Python | — | Сбор данных: остатки МойСклад, COGS, РРЦ, daily_sales, margin_pct, storage_cost |
| Calculator | Python | — | Сценарная матрица скидок, breakeven, дельта vs МП |
| MP Comparator | LLM | MAIN (gemini-2.5-flash) | Для каждого артикула: прогноз распродажи на МП, суммарная прибыль, сравнение с Familia |
| Familia Expert | LLM | MAIN (gemini-2.5-flash) | Анализ договора, скрытые расходы (логистика, упаковка, документооборот), риски (штрафы, отсрочка, потери) |
| Advisor | LLM | HEAVY (claude-sonnet-4-6) | Синтез MP Comparator + Familia Expert → решение: ГРУЗИТЬ / НЕ ГРУЗИТЬ / ТОРГОВАТЬСЯ |

## Data Model

### Входные данные (Collector)

**Из МойСклад** (`get_moysklad_stock_by_article()`):
- `stock_moysklad` — остатки на собственном складе, шт
- `article` — артикул (модель/цвет)

**Из БД WB/OZON** (`data_layer/pricing`, `finance`, `inventory`):
- `cogs_per_unit` — себестоимость единицы, руб
- `rrc` — розничная цена (РРЦ), руб
- `daily_sales_mp` — средние продажи на МП, шт/день (30д)
- `margin_pct_mp` — текущая маржа на МП, %
- `storage_cost_per_day` — стоимость хранения МП, руб/шт/день
- `turnover_days` — текущая оборачиваемость, дни
- `drr_pct` — ДРР (доля рекламных расходов), %
- `spp_pct` — СПП (скидка постоянного покупателя на МП), %

### Формулы (Calculator)

```python
# === ЦЕНА FAMILIA ===
familia_price = rrc * (1 - discount_pct)

# === РАСХОДЫ FAMILIA (на единицу) ===
logistics_to_rc    = CONFIG["logistics_to_rc"]     # ~65 руб/шт
packaging_cost     = CONFIG["packaging_cost"]       # ~20 руб/шт
loss_reserve       = familia_price * CONFIG["loss_reserve_pct"]  # 5%
money_freeze_cost  = familia_price * (CONFIG["annual_rate"] / 365) * CONFIG["payment_delay_days"]

total_cost_familia = cogs + logistics_to_rc + packaging_cost + loss_reserve + money_freeze_cost

# === МАРЖА FAMILIA ===
margin_familia     = familia_price - total_cost_familia
margin_pct_familia = margin_familia / familia_price * 100

# === СРАВНЕНИЕ С МП ===
days_to_sell_mp    = stock_moysklad / max(daily_sales_mp, 0.05)
storage_total_mp   = storage_cost_per_day * stock_moysklad * days_to_sell_mp
revenue_mp         = stock_moysklad * rrc * (1 - spp_pct)
profit_mp          = revenue_mp * margin_pct_mp / 100 - storage_total_mp

profit_familia     = stock_moysklad * margin_familia

# === ДЕЛЬТА ===
delta = profit_familia - profit_mp  # > 0 → Familia выгоднее

# === BREAKEVEN ===
breakeven_discount = 1 - (total_cost_familia / rrc)
```

### Выходная структура (scenarios.json)

```json
{
  "generated_at": "2026-04-07",
  "params": {
    "logistics_to_rc": 65,
    "packaging_cost": 20,
    "annual_rate": 0.18,
    "loss_reserve_pct": 0.05,
    "payment_delay_days": 90
  },
  "articles": [
    {
      "article": "vuki/black",
      "model": "Vuki",
      "status": "Выводим",
      "stock_moysklad": 450,
      "cogs": 380,
      "rrc": 1180,
      "daily_sales_mp": 2.3,
      "turnover_days": 196,
      "margin_pct_mp": 22.9,
      "drr_pct": 2.8,
      "scenarios": [
        {
          "discount": 0.50,
          "price": 590,
          "margin": 81,
          "margin_pct": 13.7,
          "profit_familia_total": 36450,
          "profit_mp_total": 24050,
          "delta": 12400
        }
      ],
      "breakeven_discount": 0.57,
      "recommendation": null
    }
  ]
}
```

## Agent Prompts

### MP Comparator

Анализирует эффективность продолжения продаж на WB/OZON vs отгрузка в Familia. Для каждого артикула:

1. **Прогноз распродажи на МП:**
   - Дни до полной распродажи при текущей скорости
   - Оценка ускорения при скидке -20-30% (по эластичности)
   - Суммарная прибыль за период (выручка - COGS - хранение - реклама)

2. **Сравнение с Familia** для каждого уровня скидки (50%, 55%, 60%)

3. **Вердикт:** FAMILIA_ЛУЧШЕ / МП_ЛУЧШЕ / ПАРИТЕТ с оптимальной скидкой и суммой дельты

Особые правила:
- Dead stock (>250d): учитывать что на МП может никогда не продаться без глубокой скидки
- Хранение на собственном складе = 0 руб, но это замороженные деньги в COGS
- При распродаже на МП нужна реклама (ДРР текущий по артикулу)

### Familia Expert

Анализирует скрытые расходы и риски работы с Familia на основе договора и условий поставки:

1. **Логистика:** стоимость доставки до РЦ Бритово, требования к упаковке, маркировка Честный Знак
2. **Документооборот:** ЭДО (КонтурДиадок), ТТН/ТН, сертификаты, доверенности, трудозатраты
3. **Финансовые риски:** 90д отсрочка, штрафы (1% недовоз, 0.5% опоздание), 5% потери, право приостановить оплату, возврат некачественного товара 50 дней
4. **Операционные риски:** поставки вне плана не принимаются, утилизация невывезенного товара 10 дней, переносы

Итог: общая сумма скрытых расходов на единицу + рейтинг рисков (НИЗКИЙ / СРЕДНИЙ / ВЫСОКИЙ)

### Advisor

Синтезирует MP Comparator + Familia Expert. Для каждого артикула выносит решение:

- **ГРУЗИТЬ** — Familia выгоднее, оптимальная скидка X%
- **ГРУЗИТЬ ПРИ УСЛОВИИ** — выгодно только при скидке <= X%
- **НЕ ГРУЗИТЬ** — МП выгоднее или маржа отрицательная
- **ТОРГОВАТЬСЯ** — breakeven близко, нужно выбить скидку <= X%

Финальный отчёт включает:
1. Сводную таблицу решений по всем артикулам
2. Общий объём поставки (шт и руб)
3. Ожидаемую маржу
4. Рекомендации для переговоров с байером (минимальная скидка, аргументы, red lines)

## File Structure

```
scripts/familia_eval/
├── run.py                    # Orchestrator — запуск pipeline
├── collector.py              # Сбор данных МойСклад + DB
├── calculator.py             # Сценарная матрица, breakeven
├── agents/
│   ├── mp_comparator.py      # LLM: сравнение с WB/OZON
│   ├── familia_expert.py     # LLM: анализ условий Familia
│   └── advisor.py            # LLM: финальное решение
├── prompts/
│   ├── mp_comparator.md      # Промпт MP Comparator
│   ├── familia_expert.md     # Промпт Familia Expert
│   └── advisor.md            # Промпт Advisor
├── data/
│   ├── contract_summary.md   # Выжимка из договора
│   └── supply_conditions.md  # Выжимка из условий поставки
└── output/
    ├── scenarios.json        # Выход Calculator
    ├── mp_comparator.md      # Отчёт MP Comparator
    ├── familia_expert.md     # Отчёт Familia Expert
    └── familia_eval_report.md # Финальный отчёт
```

## Configuration

```python
CONFIG = {
    # Параметры расчёта
    "logistics_to_rc": 65,        # руб/шт доставка до Бритово
    "packaging_cost": 20,         # руб/шт упаковка (гофротара, ярлыки, стрейч)
    "loss_reserve_pct": 0.05,     # 5% резерв на потери/расхождения
    "annual_rate": 0.18,          # стоимость денег (ключевая ставка ЦБ)
    "payment_delay_days": 90,     # отсрочка оплаты Familia
    
    # Скидки для сценариев
    "discount_range": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65],
    
    # Фильтр артикулов
    "min_stock_moysklad": 10,     # мин. остаток для анализа
    "status_filter": ["Выводим", "Архив"],  # статусы из SKU DB
    
    # LLM модели (OpenRouter)
    "model_main": "google/gemini-2.5-flash-preview",
    "model_heavy": "anthropic/claude-sonnet-4-6",
}
```

## CLI Interface

```bash
# Полный pipeline
python scripts/familia_eval/run.py

# Только расчёт без LLM
python scripts/familia_eval/run.py --calc-only

# Кастомные параметры
python scripts/familia_eval/run.py --logistics 80 --discount-min 0.45

# Пересчёт только LLM (данные уже собраны)
python scripts/familia_eval/run.py --llm-only
```

## Output Format

Финальный отчёт (Markdown):

```
# Оценка работы с сетью "Фамилия" — Wookiee

## Резюме
- Артикулов к отгрузке: X из Y
- Общий объём: X шт на сумму X₽
- Ожидаемая маржа: X₽ (X%)
- Срок получения денег: ~90 дней

## Сводная таблица решений
| Артикул | Сток МС | РРЦ | Скидка | Цена Fam | Маржа/шт | Маржа% | Решение |

## Детальный анализ по артикулам
(для каждого: обоснование, сравнение с МП, риски)

## Сравнение: Familia vs МП
(агрегированное сравнение)

## Риски и скрытые расходы
(из Familia Expert)

## Рекомендации для байера
(минимальная скидка, аргументы, red lines)
```

## Dependencies

- `shared/data_layer/inventory.py` — `get_moysklad_stock_by_article()`
- `shared/data_layer/pricing.py` — `get_wb_price_margin_by_model_period()`, `get_ozon_price_margin_by_model_period()`
- `shared/data_layer/finance.py` — `get_wb_by_model()`, `get_ozon_by_model()`
- `shared/config.py` — OpenRouter API key, DB connections
- `sku_database/` — статусы артикулов (Выводим, Архив)

## Assumptions to Verify at Runtime

- `logistics_to_rc` (65 руб) — уточнить реальную стоимость доставки до Бритово
- `packaging_cost` (20 руб) — зависит от наличия гофротары и паллет
- `annual_rate` (18%) — привязать к актуальной ключевой ставке ЦБ
- Хранение на собственном складе = 0 руб/шт (если аренда фиксированная)
- Маркировка Честный Знак для белья — проверить обязательность DataMatrix
