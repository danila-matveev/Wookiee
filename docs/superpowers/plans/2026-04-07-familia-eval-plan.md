# Familia Evaluation Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Multi-agent calculator that evaluates profitability of selling overstocked Wookiee articles to Familia retail chain vs continuing on WB/OZON.

**Architecture:** 4-wave pipeline: Collector (Python, data from MoySklad + DB) → Calculator (Python, scenario matrix) → MP Comparator + Familia Expert (parallel LLM agents via OpenRouter) → Advisor (LLM synthesis, final decisions). Uses existing `shared/data_layer/` and `shared/clients/openrouter_client.py`.

**Tech Stack:** Python 3.11, asyncio, OpenRouter (Gemini Flash + Claude Sonnet), shared/data_layer, shared/clients/openrouter_client

---

## File Structure

```
scripts/familia_eval/
├── __init__.py
├── config.py              # Constants: logistics costs, discount range, model tiers
├── collector.py            # Pulls MoySklad stock + DB pricing/finance/turnover
├── calculator.py           # Scenario matrix, breakeven, delta vs MP
├── agents/
│   ├── __init__.py
│   ├── mp_comparator.py    # LLM agent: Familia vs MP comparison
│   ├── familia_expert.py   # LLM agent: hidden costs & contract risks
│   └── advisor.py          # LLM agent: final decision synthesis
├── prompts/
│   ├── mp_comparator.md
│   ├── familia_expert.md
│   └── advisor.md
├── data/
│   ├── contract_summary.md # Key contract terms for LLM context
│   └── supply_conditions.md
├── run.py                  # Orchestrator: 4-wave pipeline
└── output/                 # Generated at runtime (gitignored)

tests/
└── test_familia_eval.py    # Calculator unit tests
```

---

### Task 1: Config + Static Data Files

**Files:**
- Create: `scripts/familia_eval/__init__.py`
- Create: `scripts/familia_eval/config.py`
- Create: `scripts/familia_eval/agents/__init__.py`
- Create: `scripts/familia_eval/data/contract_summary.md`
- Create: `scripts/familia_eval/data/supply_conditions.md`

- [ ] **Step 1: Create package init files**

```bash
mkdir -p scripts/familia_eval/agents scripts/familia_eval/prompts scripts/familia_eval/data scripts/familia_eval/output
touch scripts/familia_eval/__init__.py scripts/familia_eval/agents/__init__.py
echo "output/" > scripts/familia_eval/.gitignore
```

- [ ] **Step 2: Create config.py**

```python
# scripts/familia_eval/config.py
"""Configuration for Familia evaluation pipeline."""

CONFIG = {
    # --- Расходы на единицу ---
    "logistics_to_rc": 65,        # руб/шт доставка Москва → РЦ Бритово
    "packaging_cost": 20,         # руб/шт (гофрокороба, ярлыки, стрейч, паллеты)
    "loss_reserve_pct": 0.05,     # 5% резерв на потери/расхождения при приёмке
    "annual_rate": 0.18,          # стоимость денег (ключевая ставка ЦБ)
    "payment_delay_days": 90,     # отсрочка оплаты Familia

    # --- Сценарии скидок ---
    "discount_range": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65],

    # --- Фильтры артикулов ---
    "min_stock_moysklad": 10,     # мин. остаток на складе для анализа
    "status_filter": ["Выводим", "Архив"],

    # --- LLM модели (OpenRouter) ---
    "model_main": "google/gemini-2.5-flash-preview",
    "model_heavy": "anthropic/claude-sonnet-4-6",

    # --- Период для расчёта метрик МП (последние N дней) ---
    "lookback_days": 30,
}
```

- [ ] **Step 3: Create contract_summary.md**

```markdown
# Ключевые условия договора с Familia (ООО "Максима Групп")

## Оплата
- Срок: 90 календарных дней с момента передачи товара (п.5.1)
- Цена включает доставку до склада Покупателя (п.2.1)
- Одностороннее повышение цены запрещено (п.2.2)
- Покупатель вправе приостановить оплату при нарушении обязательств Продавца (п.5.3)

## Штрафы
- Недовоз: 1% от стоимости недовезённого товара (п.6.2)
- Опоздание >60 мин: 0.5% от стоимости товара (п.6.4)
- Нарушение маркировки Честный Знак: 300 000 руб (п.4.1.1)
- Нарушение интеллектуальной собственности: 1 000 000 руб (п.4.1.6)

## Приёмка
- По количеству: 30 дней после поставки (п.3.1.2)
- По качеству: 45 дней после поставки (п.3.1.3)
- Допуск до 5% расхождений без акта (п.3.1.4)
- Невывезенный конфликтный товар утилизируется через 10 дней (п.4.1.5)

## Документы
- УПД через ЭДО (КонтурДиадок) до момента приезда на РЦ
- ТТН/ТН с печатью и подписью (2 экз, бумажный)
- Сертификаты соответствия с печатью
- Доверенность на водителя

## Прочее
- Поставки вне плана не принимаются
- Переносы день-в-день невозможны (до 13:00 предыдущего дня)
- Продавец не вправе передавать права по договору третьим лицам
```

Save to `scripts/familia_eval/data/contract_summary.md`.

- [ ] **Step 4: Create supply_conditions.md**

```markdown
# Условия поставки на РЦ Familia (Бритово)

## Адрес
140126, МО, Раменский р-н, с.п. Софьинское, промзона ООО «ССТ», Корпус 6, секция 3
Координаты: 55.479790, 38.155007

## Требования к упаковке
- Короба: цельные, закрытые скотчем, макс. 30 кг
- Товар по коробам: по артикулам (обязательно), по размерам/цветам (желательно)
- Коробочный ярлык на каждом коробе: номер поставщика, номер короба, артикул, кол-во
- Паллеты: европаллеты 120×80, высота ≤180 см, стрейч-плёнка, паллетная опись

## Маркировка
- ШК на товаре = ШК в шаблоне байера
- Если товар подлежит маркировке Честный Знак — DataMatrix код + КИЗы в УПД по ЭДО
- Старые ценники / маркировки сторонних сетей — не принимаются

## Приёмка
- Этап 1: по коробам при разгрузке (сверка с ТТН)
- Этап 2: внутритарная поштучная приёмка (сканирование каждой единицы)
- При расхождении >5% — акт ТОРГ-2, товар вывезти за 3 дня

## Скрытые расходы (оценка)
- Гофрокороба: ~10-15 руб/шт товара
- Коробочные ярлыки: ~1-2 руб/шт
- Стрейч-плёнка: ~3-5 руб/шт
- Паллетная опись: ~0.5 руб/шт
- Транспорт Москва → Бритово: ~50-80 руб/шт (зависит от объёма)
- Подготовка документов (ТТН, УПД, сертификаты): ~2-4 человеко-часа на поставку
```

Save to `scripts/familia_eval/data/supply_conditions.md`.

- [ ] **Step 5: Commit**

```bash
git add scripts/familia_eval/
git commit -m "feat(familia-eval): add config and static data files"
```

---

### Task 2: Collector — сбор данных из МойСклад + DB

**Files:**
- Create: `scripts/familia_eval/collector.py`
- Test: `tests/test_familia_eval.py`

- [ ] **Step 1: Write test for collector data merging logic**

```python
# tests/test_familia_eval.py
"""Tests for Familia evaluation pipeline."""

from scripts.familia_eval.collector import merge_article_data


def test_merge_article_data_basic():
    """Merge MoySklad stock with pricing and status data."""
    ms_stock = {
        "vuki/black": {"stock_main": 450, "stock_transit": 0, "total": 450},
    }
    statuses = {
        "vuki/black": "Выводим",
    }
    wb_pricing = [
        {
            "model": "vuki",
            "avg_price_per_unit": 1180,
            "margin_pct": 22.9,
            "spp_pct": 15.0,
            "drr_pct": 2.8,
        }
    ]
    wb_turnover = {
        "vuki": {"daily_sales": 2.3, "turnover_days": 196},
    }
    wb_finance = [
        ("current", "vuki", 69, 81420, 2279, 0, 18645, 26148),
    ]
    finance_cols = [
        "period", "model", "sales_count", "revenue_before_spp",
        "adv_internal", "adv_external", "margin", "cost_of_goods",
    ]

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=wb_pricing,
        ozon_pricing=[],
        wb_turnover=wb_turnover,
        ozon_turnover={},
        wb_finance=wb_finance,
        ozon_finance=[],
        finance_cols=finance_cols,
    )

    assert len(result) == 1
    art = result[0]
    assert art["article"] == "vuki/black"
    assert art["stock_moysklad"] == 450
    assert art["status"] == "Выводим"
    assert art["model"] == "vuki"
    assert art["rrc"] == 1180
    assert art["margin_pct_mp"] == 22.9
    assert art["daily_sales_mp"] == 2.3
    assert art["turnover_days"] == 196
    assert art["cogs_per_unit"] > 0


def test_merge_filters_by_status():
    """Only articles with status in filter list are included."""
    ms_stock = {
        "wendy/black": {"stock_main": 200, "stock_transit": 0, "total": 200},
    }
    statuses = {
        "wendy/black": "Продается",
    }

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=[], ozon_pricing=[],
        wb_turnover={}, ozon_turnover={},
        wb_finance=[], ozon_finance=[],
        finance_cols=[],
    )

    assert len(result) == 0


def test_merge_filters_by_min_stock():
    """Articles below min_stock threshold are excluded."""
    ms_stock = {
        "alice/pink": {"stock_main": 5, "stock_transit": 0, "total": 5},
    }
    statuses = {"alice/pink": "Архив"}

    result = merge_article_data(
        ms_stock=ms_stock,
        statuses=statuses,
        status_filter=["Выводим", "Архив"],
        min_stock=10,
        wb_pricing=[], ozon_pricing=[],
        wb_turnover={}, ozon_turnover={},
        wb_finance=[], ozon_finance=[],
        finance_cols=[],
    )

    assert len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_familia_eval.py -v
```

Expected: FAIL — `ImportError: cannot import name 'merge_article_data'`

- [ ] **Step 3: Write collector.py**

```python
# scripts/familia_eval/collector.py
"""Collector: pulls MoySklad stock + DB pricing/finance/turnover data."""

import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.data_layer.inventory import (
    get_moysklad_stock_by_article,
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
)
from shared.data_layer.pricing import (
    get_wb_price_margin_by_model_period,
    get_ozon_price_margin_by_model_period,
)
from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.sku_mapping import get_artikuly_statuses

from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

WB_FINANCE_COLS = [
    "period", "model", "sales_count", "revenue_before_spp",
    "adv_internal", "adv_external", "margin", "cost_of_goods",
]


def collect_all() -> dict:
    """Run all data collection in parallel. Returns raw data dict."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=CONFIG["lookback_days"])).strftime("%Y-%m-%d")
    prev_start = (datetime.now() - timedelta(days=CONFIG["lookback_days"] * 2)).strftime("%Y-%m-%d")

    tasks = {
        "ms_stock": lambda: get_moysklad_stock_by_article(),
        "statuses": lambda: get_artikuly_statuses(),
        "wb_pricing": lambda: get_wb_price_margin_by_model_period(start, end),
        "ozon_pricing": lambda: get_ozon_price_margin_by_model_period(start, end),
        "wb_turnover": lambda: get_wb_turnover_by_model(start, end),
        "ozon_turnover": lambda: get_ozon_turnover_by_model(start, end),
        "wb_finance": lambda: get_wb_by_model(start, prev_start, end),
        "ozon_finance": lambda: get_ozon_by_model(start, prev_start, end),
    }

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                log.error("Collector %s failed: %s", name, e)
                errors[name] = str(e)
                results[name] = {} if name not in ("wb_finance", "ozon_finance") else []

    articles = merge_article_data(
        ms_stock=results["ms_stock"],
        statuses=results["statuses"],
        status_filter=CONFIG["status_filter"],
        min_stock=CONFIG["min_stock_moysklad"],
        wb_pricing=results["wb_pricing"],
        ozon_pricing=results["ozon_pricing"],
        wb_turnover=results["wb_turnover"],
        ozon_turnover=results["ozon_turnover"],
        wb_finance=results["wb_finance"],
        ozon_finance=results["ozon_finance"],
        finance_cols=WB_FINANCE_COLS,
    )

    return {
        "articles": articles,
        "meta": {
            "collected_at": datetime.now().isoformat(timespec="seconds"),
            "period": f"{start} — {end}",
            "errors": errors,
        },
    }


def merge_article_data(
    ms_stock: dict,
    statuses: dict,
    status_filter: list,
    min_stock: int,
    wb_pricing: list,
    ozon_pricing: list,
    wb_turnover: dict,
    ozon_turnover: dict,
    wb_finance: list,
    ozon_finance: list,
    finance_cols: list,
) -> list:
    """Merge all data sources into a list of article dicts for Calculator."""
    # Build model-level lookups
    pricing_by_model = {}
    for row in wb_pricing:
        pricing_by_model[row["model"].lower()] = row
    for row in ozon_pricing:
        m = row["model"].lower()
        if m not in pricing_by_model:
            pricing_by_model[m] = row

    # Finance: extract COGS per unit by model
    cogs_by_model = {}
    for fin_data in (wb_finance, ozon_finance):
        for row in fin_data:
            if isinstance(row, (list, tuple)) and len(row) >= len(finance_cols):
                d = dict(zip(finance_cols, row))
            elif isinstance(row, dict):
                d = row
            else:
                continue
            if d.get("period") != "current":
                continue
            model = d.get("model", "").lower()
            sales = d.get("sales_count", 0) or 0
            cogs_total = d.get("cost_of_goods", 0) or 0
            if model and sales > 0:
                cogs_by_model[model] = cogs_total / sales

    # Turnover: merge WB + OZON (take higher daily_sales)
    turnover_by_model = {}
    for src in (wb_turnover, ozon_turnover):
        for model, data in src.items():
            m = model.lower()
            if m not in turnover_by_model:
                turnover_by_model[m] = data
            else:
                existing = turnover_by_model[m]
                turnover_by_model[m] = {
                    "daily_sales": existing["daily_sales"] + data.get("daily_sales", 0),
                    "turnover_days": min(
                        existing.get("turnover_days", 999),
                        data.get("turnover_days", 999),
                    ),
                }

    # Build article list
    articles = []
    for article, stock_data in ms_stock.items():
        art_lower = article.lower()
        status = statuses.get(art_lower)
        if status not in status_filter:
            continue
        stock = stock_data.get("total", 0) or stock_data.get("stock_main", 0)
        if stock < min_stock:
            continue

        model = art_lower.split("/")[0] if "/" in art_lower else art_lower
        pricing = pricing_by_model.get(model, {})
        turnover = turnover_by_model.get(model, {})
        cogs = cogs_by_model.get(model, 0)

        articles.append({
            "article": art_lower,
            "model": model,
            "status": status,
            "stock_moysklad": stock,
            "cogs_per_unit": round(cogs, 2),
            "rrc": pricing.get("avg_price_per_unit", 0),
            "daily_sales_mp": turnover.get("daily_sales", 0),
            "turnover_days": turnover.get("turnover_days", 0),
            "margin_pct_mp": pricing.get("margin_pct", 0),
            "spp_pct": pricing.get("spp_pct", 0),
            "drr_pct": pricing.get("drr_pct", 0),
        })

    articles.sort(key=lambda x: x["turnover_days"], reverse=True)
    return articles
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_familia_eval.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/familia_eval/collector.py tests/test_familia_eval.py
git commit -m "feat(familia-eval): add collector with MoySklad + DB data merging"
```

---

### Task 3: Calculator — сценарная матрица

**Files:**
- Create: `scripts/familia_eval/calculator.py`
- Modify: `tests/test_familia_eval.py`

- [ ] **Step 1: Write test for calculator**

Append to `tests/test_familia_eval.py`:

```python
from scripts.familia_eval.calculator import calculate_scenarios


def test_calculate_scenarios_basic():
    """Calculate scenario matrix for one article."""
    articles = [{
        "article": "vuki/black",
        "model": "vuki",
        "status": "Выводим",
        "stock_moysklad": 450,
        "cogs_per_unit": 380,
        "rrc": 1180,
        "daily_sales_mp": 2.3,
        "turnover_days": 196,
        "margin_pct_mp": 22.9,
        "spp_pct": 15.0,
        "drr_pct": 2.8,
    }]

    result = calculate_scenarios(articles)

    assert len(result) == 1
    art = result[0]
    assert art["article"] == "vuki/black"
    assert len(art["scenarios"]) == 6  # 40% to 65%
    assert "breakeven_discount" in art

    # At 50% discount: price = 590, should have positive margin
    s50 = [s for s in art["scenarios"] if s["discount"] == 0.50][0]
    assert s50["price"] == 590
    assert s50["margin"] > 0  # COGS 380 + costs ~130 < 590

    # At 65% discount: price = 413, should have negative margin
    s65 = [s for s in art["scenarios"] if s["discount"] == 0.65][0]
    assert s65["price"] == 413
    assert s65["margin"] < 0  # COGS 380 + costs ~130 > 413


def test_breakeven_discount():
    """Breakeven discount should be between profitable and unprofitable."""
    articles = [{
        "article": "test/art",
        "model": "test",
        "status": "Выводим",
        "stock_moysklad": 100,
        "cogs_per_unit": 400,
        "rrc": 1000,
        "daily_sales_mp": 1.0,
        "turnover_days": 100,
        "margin_pct_mp": 20.0,
        "spp_pct": 15.0,
        "drr_pct": 3.0,
    }]

    result = calculate_scenarios(articles)
    be = result[0]["breakeven_discount"]

    # breakeven should be between 0 and 1
    assert 0 < be < 1
    # At breakeven price, total_cost ~= price
    price_at_be = 1000 * (1 - be)
    assert price_at_be > 400  # must be above COGS at minimum
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_familia_eval.py::test_calculate_scenarios_basic -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write calculator.py**

```python
# scripts/familia_eval/calculator.py
"""Calculator: scenario matrix, breakeven, delta vs MP."""

from scripts.familia_eval.config import CONFIG


def calculate_scenarios(articles: list) -> list:
    """For each article, compute P&L at each discount level.

    Returns articles list enriched with 'scenarios' and 'breakeven_discount'.
    """
    results = []
    for art in articles:
        cogs = art["cogs_per_unit"]
        rrc = art["rrc"]
        stock = art["stock_moysklad"]
        daily_sales = max(art["daily_sales_mp"], 0.05)
        margin_pct_mp = art["margin_pct_mp"]
        spp_pct = art.get("spp_pct", 0)

        if rrc <= 0:
            continue

        scenarios = []
        for discount in CONFIG["discount_range"]:
            price = round(rrc * (1 - discount))
            costs = _calc_costs(cogs, price)
            margin = round(price - costs, 2)
            margin_pct = round(margin / price * 100, 1) if price > 0 else 0

            profit_familia = round(stock * margin)
            profit_mp = _estimate_mp_profit(art)
            delta = round(profit_familia - profit_mp)

            scenarios.append({
                "discount": discount,
                "price": price,
                "costs_total": round(costs, 2),
                "margin": margin,
                "margin_pct": margin_pct,
                "profit_familia_total": profit_familia,
                "profit_mp_total": profit_mp,
                "delta": delta,
            })

        breakeven = _calc_breakeven(cogs, rrc)

        results.append({
            **art,
            "scenarios": scenarios,
            "breakeven_discount": round(breakeven, 4),
        })

    return results


def _calc_costs(cogs: float, familia_price: float) -> float:
    """Total cost per unit for Familia channel."""
    logistics = CONFIG["logistics_to_rc"]
    packaging = CONFIG["packaging_cost"]
    loss = familia_price * CONFIG["loss_reserve_pct"]
    freeze = familia_price * (CONFIG["annual_rate"] / 365) * CONFIG["payment_delay_days"]
    return cogs + logistics + packaging + loss + freeze


def _calc_breakeven(cogs: float, rrc: float) -> float:
    """Max discount where margin >= 0.

    Solve: rrc*(1-d) - cogs - logistics - packaging - rrc*(1-d)*loss - rrc*(1-d)*freeze_rate = 0
    Let P = rrc*(1-d), fixed = cogs + logistics + packaging
    P - fixed - P*loss - P*freeze = 0
    P*(1 - loss - freeze) = fixed
    P = fixed / (1 - loss - freeze)
    d = 1 - P/rrc
    """
    if rrc <= 0:
        return 0.0
    fixed = cogs + CONFIG["logistics_to_rc"] + CONFIG["packaging_cost"]
    variable_rate = CONFIG["loss_reserve_pct"] + (CONFIG["annual_rate"] / 365) * CONFIG["payment_delay_days"]
    price_breakeven = fixed / (1 - variable_rate)
    return max(0.0, min(1.0, 1 - price_breakeven / rrc))


def _estimate_mp_profit(art: dict) -> float:
    """Estimate total profit if continuing to sell on MP.

    Simplified: stock * rrc * (1 - spp) * margin_pct / 100
    Minus: storage cost on MP warehouses (estimated from turnover).
    Note: own warehouse storage = 0 (fixed rent).
    """
    stock = art["stock_moysklad"]
    rrc = art["rrc"]
    spp = art.get("spp_pct", 0) / 100
    margin_pct = art["margin_pct_mp"] / 100
    daily_sales = max(art["daily_sales_mp"], 0.05)

    days_to_sell = stock / daily_sales
    revenue = stock * rrc * (1 - spp)
    gross_profit = revenue * margin_pct

    # Estimated MP storage cost (from WB FBO rates, ~5 руб/шт/день average)
    storage_cost_per_day = 5.0
    # Only count MP warehouse stock (assume ~30% of stock is on MP)
    mp_stock_share = 0.3
    storage_total = storage_cost_per_day * stock * mp_stock_share * days_to_sell

    return round(gross_profit - storage_total)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_familia_eval.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/familia_eval/calculator.py tests/test_familia_eval.py
git commit -m "feat(familia-eval): add calculator with scenario matrix and breakeven"
```

---

### Task 4: LLM Agent Prompts

**Files:**
- Create: `scripts/familia_eval/prompts/mp_comparator.md`
- Create: `scripts/familia_eval/prompts/familia_expert.md`
- Create: `scripts/familia_eval/prompts/advisor.md`

- [ ] **Step 1: Write mp_comparator.md**

```markdown
Ты — аналитик эффективности продаж бренда нижнего белья Wookiee на маркетплейсах WB и OZON.

## ЗАДАЧА

Для каждого артикула из предоставленных данных оцени, что выгоднее — продолжать продавать на маркетплейсах или отгрузить в off-price сеть "Фамилия".

## ВХОДНЫЕ ДАННЫЕ

Тебе предоставлены сценарные расчёты по каждому артикулу: текущие остатки на складе, себестоимость, РРЦ, скорость продаж на МП, текущая маржа, оборачиваемость, и расчёты маржи при разных скидках для Familia.

## ДЛЯ КАЖДОГО АРТИКУЛА ОТВЕТЬ

### 1. Прогноз распродажи на МП
- При текущей скорости продаж: сколько дней до полной распродажи остатка
- Если дать скидку -20-30% на МП: оценка ускорения (используй эластичность если есть, иначе предположи x1.5-2.0)
- Суммарная прибыль за период распродажи на МП (учти хранение, рекламу ДРР)

### 2. Сравнение с Familia
- Для ключевых скидок (50%, 55%, 60%): маржа на единицу, общая прибыль
- Учти: товар продаётся за 1 отгрузку, но деньги через 90 дней

### 3. Вердикт
- **FAMILIA_ЛУЧШЕ** — Familia даёт больше прибыли и/или быстрее
- **МП_ЛУЧШЕ** — на МП прибыль выше даже с учётом времени
- **ПАРИТЕТ** — разница менее 10%

Укажи оптимальную скидку для Familia и сумму дельты в рублях.

## ВАЖНЫЕ ПРАВИЛА
- Dead stock (>250 дней оборачиваемости): на МП может НИКОГДА не продаться без глубокой скидки. Учитывай это.
- Хранение на собственном складе = 0 руб, но это замороженные деньги в COGS.
- При распродаже на МП нужна реклама — учитывай текущий ДРР по артикулу.
- Не хардкодь — считай на основе предоставленных данных.

## ФОРМАТ ОТВЕТА

Ответь в формате JSON:

```json
{
  "articles": [
    {
      "article": "...",
      "days_to_sell_mp_current": 999,
      "days_to_sell_mp_discounted": 999,
      "profit_mp_estimate": 99999,
      "profit_familia_at_50": 99999,
      "profit_familia_at_55": 99999,
      "profit_familia_at_60": 99999,
      "verdict": "FAMILIA_ЛУЧШЕ",
      "optimal_discount": 0.50,
      "delta_rub": 99999,
      "reasoning": "..."
    }
  ],
  "summary": "..."
}
```
```

Save to `scripts/familia_eval/prompts/mp_comparator.md`.

- [ ] **Step 2: Write familia_expert.md**

```markdown
Ты — эксперт по работе с off-price розничными сетями в России. Ты детально знаешь условия работы с сетью магазинов "Фамилия" (ООО "Максима Групп").

## ЗАДАЧА

Проанализируй скрытые расходы и риски работы с Familia для бренда нижнего белья Wookiee, на основе условий договора и поставки.

## УСЛОВИЯ ДОГОВОРА

{contract_summary}

## УСЛОВИЯ ПОСТАВКИ

{supply_conditions}

## ДАННЫЕ О ТОВАРЕ

{scenarios_summary}

## ПРОАНАЛИЗИРУЙ

### 1. Логистика (руб/шт)
- Стоимость доставки из Москвы до РЦ Бритово (Раменский р-н МО, ~60 км)
- Упаковка: гофрокороба, коробочные ярлыки, стрейч-плёнка, паллеты
- Подлежит ли нижнее бельё маркировке Честный Знак (DataMatrix)?

### 2. Документооборот (руб/поставка)
- ЭДО КонтурДиадок — есть ли подключение?
- ТТН/ТН, сертификаты, доверенности — трудозатраты на подготовку
- Оцени в человеко-часах и рублях (средняя ставка логиста)

### 3. Финансовые риски (руб)
- Стоимость замороженных денег за 90 дней при ставке ЦБ
- Штраф 1% за недовоз — при типичном объёме поставки
- Штраф 0.5% за опоздание — вероятность и сумма
- Потенциальные потери до 5% при расхождениях
- Риск приостановки оплаты (п.5.3)
- Возврат некачественного товара (45 дней после поставки)

### 4. Операционные риски
- Координация с байером (только по плану)
- Утилизация невывезенного товара (10 дней)
- Ограничения по переносам

## ФОРМАТ ОТВЕТА

```json
{
  "hidden_costs_per_unit": {
    "logistics_delivery": 99,
    "packaging_materials": 99,
    "documentation_per_unit": 99,
    "marking_chestnyznak": 99,
    "total": 99
  },
  "hidden_costs_per_shipment": {
    "documentation_hours": 9,
    "documentation_cost": 9999,
    "chestnyznak_setup": 9999
  },
  "financial_risks": {
    "money_freeze_cost_per_unit": 99,
    "fine_late_delivery_probability": "НИЗКАЯ/СРЕДНЯЯ/ВЫСОКАЯ",
    "fine_undershipping_probability": "НИЗКАЯ/СРЕДНЯЯ/ВЫСОКАЯ",
    "loss_5pct_expected": 99999,
    "payment_suspension_risk": "НИЗКИЙ/СРЕДНИЙ/ВЫСОКИЙ"
  },
  "overall_risk_rating": "НИЗКИЙ/СРЕДНИЙ/ВЫСОКИЙ",
  "total_hidden_cost_per_unit": 99,
  "recommendations": ["..."],
  "reasoning": "..."
}
```
```

Save to `scripts/familia_eval/prompts/familia_expert.md`.

- [ ] **Step 3: Write advisor.md**

```markdown
Ты — стратегический советник бренда нижнего белья Wookiee.
Оборот бренда ~40М/мес на WB+OZON, целевая маржа 22%+.

## ЗАДАЧА

На основе анализа двух экспертов прими финальное решение по каждому артикулу: отгружать ли его в off-price сеть "Фамилия" или продолжать продавать на маркетплейсах.

## ВХОДНЫЕ ДАННЫЕ

### Отчёт MP Comparator (сравнение каналов)
{mp_comparator_report}

### Отчёт Familia Expert (скрытые расходы и риски)
{familia_expert_report}

### Сценарные расчёты
{scenarios_summary}

## ФОРМАТ РЕШЕНИЯ

Для каждого артикула вынеси решение:

- ✅ **ГРУЗИТЬ** — Familia выгоднее, грузить при скидке X%
- ⚠️ **ГРУЗИТЬ ПРИ УСЛОВИИ** — выгодно только при скидке ≤ X%
- ❌ **НЕ ГРУЗИТЬ** — МП выгоднее или маржа отрицательная
- 🔄 **ТОРГОВАТЬСЯ** — breakeven близко, попробовать скидку ≤ X%

## ФОРМАТ ОТВЕТА

Ответь в Markdown:

### Сводная таблица

| Артикул | Сток | РРЦ | Рек. скидка | Цена Fam | Маржа/шт | Маржа% | Общая маржа | Решение |
|---------|------|-----|-------------|----------|----------|--------|-------------|---------|

### Детальный анализ

Для каждого артикула:
- Решение и обоснование
- Сравнение: Familia vs МП (в рублях и днях)
- Учёт скрытых расходов из отчёта Familia Expert
- Риски

### Общий итог

- Артикулов к отгрузке: X из Y
- Общий объём: X шт на сумму X₽
- Ожидаемая маржа: X₽ (X%)
- Экономия vs продолжение на МП: X₽

### Рекомендации для байера

1. Минимальная приемлемая скидка (ниже — отказываемся)
2. Оптимальная скидка (наш идеал)
3. Аргументы для торга
4. Red lines — при каких условиях отказываемся полностью
```

Save to `scripts/familia_eval/prompts/advisor.md`.

- [ ] **Step 4: Commit**

```bash
git add scripts/familia_eval/prompts/
git commit -m "feat(familia-eval): add LLM agent prompts (comparator, expert, advisor)"
```

---

### Task 5: LLM Agents — mp_comparator, familia_expert, advisor

**Files:**
- Create: `scripts/familia_eval/agents/mp_comparator.py`
- Create: `scripts/familia_eval/agents/familia_expert.py`
- Create: `scripts/familia_eval/agents/advisor.py`

- [ ] **Step 1: Write mp_comparator.py**

```python
# scripts/familia_eval/agents/mp_comparator.py
"""MP Comparator agent: compares Familia vs WB/OZON for each article."""

import json
import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "mp_comparator.md")


async def run_mp_comparator(scenarios: list) -> str:
    """Analyze each article: Familia vs MP profitability.

    Args:
        scenarios: list of article dicts with 'scenarios' key from Calculator

    Returns:
        LLM response text (JSON with verdicts)
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()

    # Build compact data summary for LLM context
    data_summary = _build_summary(scenarios)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_main"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот данные для анализа:\n\n```json\n{data_summary}\n```"},
        ],
        temperature=0.3,
        max_tokens=8000,
    )

    log.info(
        "MP Comparator: %d input, %d output tokens",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
    )
    return result["content"]


def _build_summary(scenarios: list) -> str:
    """Build compact JSON summary for LLM (drop unnecessary fields)."""
    compact = []
    for art in scenarios:
        compact.append({
            "article": art["article"],
            "model": art["model"],
            "status": art["status"],
            "stock": art["stock_moysklad"],
            "cogs": art["cogs_per_unit"],
            "rrc": art["rrc"],
            "daily_sales_mp": art["daily_sales_mp"],
            "turnover_days": art["turnover_days"],
            "margin_pct_mp": art["margin_pct_mp"],
            "drr_pct": art["drr_pct"],
            "breakeven_discount": art["breakeven_discount"],
            "scenarios": [
                {
                    "discount": s["discount"],
                    "price": s["price"],
                    "margin": s["margin"],
                    "margin_pct": s["margin_pct"],
                    "delta": s["delta"],
                }
                for s in art["scenarios"]
            ],
        })
    return json.dumps(compact, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Write familia_expert.py**

```python
# scripts/familia_eval/agents/familia_expert.py
"""Familia Expert agent: analyzes hidden costs and contract risks."""

import json
import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "familia_expert.md")
CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contract_summary.md")
CONDITIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "supply_conditions.md")


async def run_familia_expert(scenarios: list) -> str:
    """Analyze hidden costs and risks of working with Familia.

    Args:
        scenarios: list of article dicts with 'scenarios' key from Calculator

    Returns:
        LLM response text (JSON with risk assessment)
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()
    with open(CONTRACT_PATH) as f:
        contract = f.read()
    with open(CONDITIONS_PATH) as f:
        conditions = f.read()

    # Fill placeholders in prompt
    system_prompt = system_prompt.replace("{contract_summary}", contract)
    system_prompt = system_prompt.replace("{supply_conditions}", conditions)

    # Build scenarios summary
    summary = _build_scenarios_summary(scenarios)
    system_prompt = system_prompt.replace("{scenarios_summary}", summary)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_main"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Проанализируй скрытые расходы и риски для этой поставки."},
        ],
        temperature=0.3,
        max_tokens=6000,
    )

    log.info(
        "Familia Expert: %d input, %d output tokens",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
    )
    return result["content"]


def _build_scenarios_summary(scenarios: list) -> str:
    """Compact summary of articles for expert context."""
    total_stock = sum(a["stock_moysklad"] for a in scenarios)
    total_value = sum(a["stock_moysklad"] * a["rrc"] for a in scenarios)
    models = set(a["model"] for a in scenarios)

    lines = [
        f"Всего артикулов: {len(scenarios)}",
        f"Моделей: {len(models)} ({', '.join(sorted(models))})",
        f"Общий сток: {total_stock} шт",
        f"Общая стоимость по РРЦ: {total_value:,.0f} руб",
        "",
        "Артикулы:",
    ]
    for a in scenarios:
        lines.append(
            f"- {a['article']}: {a['stock_moysklad']} шт, "
            f"РРЦ {a['rrc']}₽, COGS {a['cogs_per_unit']}₽, "
            f"оборачиваемость {a['turnover_days']}д"
        )
    return "\n".join(lines)
```

- [ ] **Step 3: Write advisor.py**

```python
# scripts/familia_eval/agents/advisor.py
"""Advisor agent: synthesizes analysis into final decisions."""

import logging
import os

from shared.clients.openrouter_client import OpenRouterClient
from shared.config import OPENROUTER_API_KEY
from scripts.familia_eval.config import CONFIG

log = logging.getLogger(__name__)

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "advisor.md")


async def run_advisor(
    scenarios_summary: str,
    mp_comparator_report: str,
    familia_expert_report: str,
) -> str:
    """Synthesize expert reports into final decisions.

    Args:
        scenarios_summary: JSON string with scenario data
        mp_comparator_report: MP Comparator output
        familia_expert_report: Familia Expert output

    Returns:
        Markdown report with decisions per article
    """
    with open(PROMPT_PATH) as f:
        system_prompt = f.read()

    system_prompt = system_prompt.replace("{mp_comparator_report}", mp_comparator_report)
    system_prompt = system_prompt.replace("{familia_expert_report}", familia_expert_report)
    system_prompt = system_prompt.replace("{scenarios_summary}", scenarios_summary)

    llm = OpenRouterClient(
        api_key=OPENROUTER_API_KEY,
        model=CONFIG["model_heavy"],
    )

    result = await llm.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                "Прими финальное решение по каждому артикулу. "
                "Сформируй отчёт с рекомендациями для байера Familia."
            )},
        ],
        temperature=0.3,
        max_tokens=12000,
    )

    log.info(
        "Advisor: %d input, %d output tokens, model: %s",
        result.get("usage", {}).get("input_tokens", 0),
        result.get("usage", {}).get("output_tokens", 0),
        result.get("model", "unknown"),
    )
    return result["content"]
```

- [ ] **Step 4: Commit**

```bash
git add scripts/familia_eval/agents/
git commit -m "feat(familia-eval): add LLM agents (mp_comparator, familia_expert, advisor)"
```

---

### Task 6: Orchestrator (run.py)

**Files:**
- Create: `scripts/familia_eval/run.py`

- [ ] **Step 1: Write run.py**

```python
#!/usr/bin/env python3
# scripts/familia_eval/run.py
"""Familia Evaluation Pipeline — orchestrator.

Usage:
    python scripts/familia_eval/run.py                  # Full pipeline
    python scripts/familia_eval/run.py --calc-only      # Data + calc, no LLM
    python scripts/familia_eval/run.py --llm-only       # Reuse cached scenarios.json
    python scripts/familia_eval/run.py --logistics 80   # Override logistics cost
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

# Ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.familia_eval.config import CONFIG
from scripts.familia_eval.collector import collect_all
from scripts.familia_eval.calculator import calculate_scenarios

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("familia_eval")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def parse_args():
    parser = argparse.ArgumentParser(description="Familia evaluation pipeline")
    parser.add_argument("--calc-only", action="store_true", help="Skip LLM agents")
    parser.add_argument("--llm-only", action="store_true", help="Reuse cached scenarios.json")
    parser.add_argument("--logistics", type=int, help="Override logistics cost per unit")
    parser.add_argument("--discount-min", type=float, help="Min discount (e.g. 0.45)")
    parser.add_argument("--discount-max", type=float, help="Max discount (e.g. 0.60)")
    return parser.parse_args()


async def run_llm_agents(scenarios: list) -> str:
    """Wave 3 (parallel) + Wave 4 (sequential)."""
    from scripts.familia_eval.agents.mp_comparator import run_mp_comparator, _build_summary
    from scripts.familia_eval.agents.familia_expert import run_familia_expert
    from scripts.familia_eval.agents.advisor import run_advisor

    # Wave 3: parallel LLM agents
    log.info("Wave 3: running MP Comparator + Familia Expert in parallel...")
    mp_task = asyncio.create_task(run_mp_comparator(scenarios))
    expert_task = asyncio.create_task(run_familia_expert(scenarios))

    mp_report, expert_report = await asyncio.gather(mp_task, expert_task)

    # Save intermediate reports
    _save_output("mp_comparator.md", mp_report)
    _save_output("familia_expert.md", expert_report)
    log.info("Wave 3 complete. Reports saved.")

    # Wave 4: Advisor synthesis
    log.info("Wave 4: running Advisor...")
    scenarios_summary = _build_summary(scenarios)
    advisor_report = await run_advisor(scenarios_summary, mp_report, expert_report)

    _save_output("familia_eval_report.md", advisor_report)
    log.info("Wave 4 complete. Final report saved.")

    return advisor_report


def main():
    args = parse_args()
    t0 = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Apply CLI overrides
    if args.logistics:
        CONFIG["logistics_to_rc"] = args.logistics
    if args.discount_min or args.discount_max:
        lo = args.discount_min or CONFIG["discount_range"][0]
        hi = args.discount_max or CONFIG["discount_range"][-1]
        CONFIG["discount_range"] = [round(lo + i * 0.05, 2) for i in range(int((hi - lo) / 0.05) + 1)]

    if args.llm_only:
        # Load cached scenarios
        cache_path = os.path.join(OUTPUT_DIR, "scenarios.json")
        if not os.path.exists(cache_path):
            log.error("No cached scenarios.json found. Run without --llm-only first.")
            sys.exit(1)
        with open(cache_path) as f:
            data = json.load(f)
        scenarios = data["articles"]
        log.info("Loaded %d articles from cache.", len(scenarios))
    else:
        # Wave 1: Collect
        log.info("Wave 1: collecting data...")
        raw = collect_all()
        articles = raw["articles"]
        log.info("Collected %d articles (errors: %s)", len(articles), raw["meta"].get("errors", {}))

        if not articles:
            log.warning("No articles found matching filters. Check status_filter and min_stock.")
            sys.exit(0)

        # Wave 2: Calculate
        log.info("Wave 2: calculating scenarios...")
        scenarios = calculate_scenarios(articles)
        log.info("Calculated scenarios for %d articles.", len(scenarios))

        # Save scenarios.json
        output = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "params": {k: v for k, v in CONFIG.items() if k != "discount_range"},
            "discount_range": CONFIG["discount_range"],
            "articles": scenarios,
        }
        _save_output("scenarios.json", json.dumps(output, ensure_ascii=False, indent=2, default=str))

        # Print summary
        for art in scenarios:
            best = max(art["scenarios"], key=lambda s: s["margin"])
            worst = min(art["scenarios"], key=lambda s: s["margin"])
            log.info(
                "  %s: stock=%d, breakeven=%.0f%%, best=%.0f%% (margin %.1f₽), worst=%.0f%% (margin %.1f₽)",
                art["article"], art["stock_moysklad"],
                art["breakeven_discount"] * 100,
                best["discount"] * 100, best["margin"],
                worst["discount"] * 100, worst["margin"],
            )

    if args.calc_only:
        log.info("--calc-only: skipping LLM agents. See output/scenarios.json")
        return

    # Wave 3-4: LLM agents
    report = asyncio.run(run_llm_agents(scenarios))

    elapsed = round(time.time() - t0, 1)
    log.info("Pipeline complete in %.1f sec. Report: output/familia_eval_report.md", elapsed)
    print(f"\n{'='*60}")
    print(report[:500] + "..." if len(report) > 500 else report)
    print(f"{'='*60}")
    print(f"\nFull report: scripts/familia_eval/output/familia_eval_report.md")


def _save_output(filename: str, content: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test dry-run with --calc-only**

```bash
python scripts/familia_eval/run.py --calc-only
```

Expected: Collects data, calculates scenarios, saves `output/scenarios.json`, no LLM calls.

- [ ] **Step 3: Commit**

```bash
git add scripts/familia_eval/run.py scripts/familia_eval/.gitignore
git commit -m "feat(familia-eval): add orchestrator with 4-wave pipeline"
```

---

### Task 7: Integration Test — Full Pipeline

**Files:**
- No new files, testing existing pipeline

- [ ] **Step 1: Run calc-only to verify data collection works**

```bash
python scripts/familia_eval/run.py --calc-only
```

Verify: `scripts/familia_eval/output/scenarios.json` exists and contains articles.

- [ ] **Step 2: Inspect scenarios.json**

```bash
python -c "
import json
with open('scripts/familia_eval/output/scenarios.json') as f:
    data = json.load(f)
print(f'Articles: {len(data[\"articles\"])}')
for a in data['articles']:
    print(f'  {a[\"article\"]}: stock={a[\"stock_moysklad\"]}, rrc={a[\"rrc\"]}, breakeven={a[\"breakeven_discount\"]:.0%}')
"
```

- [ ] **Step 3: Run full pipeline with LLM agents**

```bash
python scripts/familia_eval/run.py
```

Verify:
- `output/mp_comparator.md` exists with verdicts
- `output/familia_expert.md` exists with risk assessment
- `output/familia_eval_report.md` exists with decisions table

- [ ] **Step 4: Review final report quality**

Open `scripts/familia_eval/output/familia_eval_report.md` and check:
- Every article has a decision (ГРУЗИТЬ / НЕ ГРУЗИТЬ / ТОРГОВАТЬСЯ)
- Sводная таблица present with all columns
- Recommendations section has concrete numbers for байер

- [ ] **Step 5: Final commit**

```bash
git add -A scripts/familia_eval/
git commit -m "feat(familia-eval): complete pipeline — collector, calculator, 3 LLM agents"
```
