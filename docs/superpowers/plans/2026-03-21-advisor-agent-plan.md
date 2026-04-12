# Advisor Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить универсальный рекомендательный движок (Signal Detector + Advisor Agent + Validator Agent) в систему Олег, чтобы все отчёты содержали actionable рекомендации, привязанные к оборачиваемости и маржинальности.

**Architecture:** Signal Detector (Python) обнаруживает паттерны в данных → Advisor Agent (LLM) интерпретирует сигналы в рекомендации → Validator Agent (LLM + скрипты) проверяет → результат встраивается в любой отчёт через orchestrator chain.

**Tech Stack:** Python 3.11, asyncio, existing BaseAgent/ReactLoop, Supabase (kb_patterns table), OpenRouter LLM API.

**Spec:** `docs/superpowers/specs/2026-03-21-advisor-agent-design.md`

---

## File Structure (what we're building)

```
shared/signals/                          # NEW: Signal Detector module
  __init__.py
  detector.py                            # detect_signals(data, kb_patterns) -> signals[]
  patterns.py                            # 25 base pattern definitions
  direction_map.py                       # DIRECTION_MAP for validator

agents/oleg/agents/advisor/              # NEW: Advisor Agent
  __init__.py
  agent.py                               # AdvisorAgent(BaseAgent)
  prompts.py                             # System prompt
  tools.py                               # Tool definitions + executor

agents/oleg/agents/validator/            # NEW: Validator Agent
  __init__.py
  agent.py                               # ValidatorAgent(BaseAgent)
  prompts.py                             # System prompt
  tools.py                               # Tool definitions + executor
  scripts/
    __init__.py
    check_numbers.py                     # Deterministic number validation
    check_coverage.py                    # Signal coverage check
    check_direction.py                   # Action direction validation
    check_kb_rules.py                    # KB pattern conflict check

services/knowledge_base/migrations/
  003_create_kb_patterns.py              # NEW: kb_patterns table

# MODIFIED files:
agents/oleg/orchestrator/chain.py        # AgentResult.structured_data
agents/oleg/orchestrator/orchestrator.py # New chain patterns
agents/oleg/app.py                       # Register Advisor + Validator
agents/oleg/agents/reporter/prompts.py   # Advisor recommendations section
agents/oleg/agents/marketer/prompts.py   # Advisor recommendations section
```

---

## Phase 1: Signal Detector

### Task 1: Base signal data structures

**Files:**
- Create: `shared/signals/__init__.py`
- Create: `shared/signals/detector.py`
- Test: `tests/shared/signals/test_detector.py`

- [ ] **Step 1: Write failing test for detect_signals with empty data**

```python
# tests/shared/signals/test_detector.py
import pytest
from shared.signals.detector import detect_signals, Signal

def test_detect_signals_empty_data_returns_empty():
    result = detect_signals(data={}, kb_patterns=[])
    assert result == []

def test_signal_dataclass_fields():
    s = Signal(
        id="test_2026-03-21",
        type="margin_lags_orders",
        category="margin",
        severity="warning",
        impact_on="margin",
        data={"gap_pct": 7.8},
        hint="Test hint",
        source="plan_vs_fact",
    )
    assert s.category == "margin"
    assert s.severity == "warning"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/shared/signals/test_detector.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement Signal dataclass and detect_signals skeleton**

```python
# shared/signals/__init__.py
from .detector import detect_signals, Signal

__all__ = ["detect_signals", "Signal"]
```

```python
# shared/signals/detector.py
"""Universal Signal Detector — finds patterns in any dataset."""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Signal:
    id: str
    type: str
    category: str           # margin | turnover | funnel | adv | price | model
    severity: str           # info | warning | critical
    impact_on: str          # margin | turnover | both
    data: dict              # exact numbers for validator
    hint: str               # human-readable description (Russian)
    source: str             # which tool produced the data

def detect_signals(
    data: dict,
    kb_patterns: list[dict] | None = None,
) -> list[Signal]:
    """Detect patterns in data using base rules + KB patterns.

    Pure function: no network calls, no side effects.
    """
    if not data:
        return []

    kb_patterns = kb_patterns or []
    signals: list[Signal] = []

    # Dispatch to source-specific detectors
    source = data.get("_source", "")
    if source == "plan_vs_fact":
        signals.extend(_detect_plan_fact_signals(data))
    if source == "brand_finance":
        signals.extend(_detect_finance_signals(data))
    if source == "margin_levers":
        signals.extend(_detect_margin_lever_signals(data))

    # Apply KB patterns
    signals.extend(_detect_kb_pattern_signals(data, kb_patterns))

    return signals

def _detect_plan_fact_signals(data: dict) -> list[Signal]:
    return []

def _detect_finance_signals(data: dict) -> list[Signal]:
    return []

def _detect_margin_lever_signals(data: dict) -> list[Signal]:
    return []

def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/shared/signals/test_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/signals/ tests/shared/signals/
git commit -m "feat(signals): add Signal dataclass and detect_signals skeleton"
```

---

### Task 2: Plan-fact signal detection (5 core patterns)

**Files:**
- Modify: `shared/signals/detector.py`
- Test: `tests/shared/signals/test_plan_fact_signals.py`

- [ ] **Step 1: Write failing tests for plan-fact signals**

```python
# tests/shared/signals/test_plan_fact_signals.py
import pytest
from shared.signals.detector import detect_signals

PLAN_FACT_DATA = {
    "_source": "plan_vs_fact",
    "brand_total": {
        "metrics": {
            "orders_count": {"completion_mtd_pct": 113.9, "forecast_vs_plan_pct": 10.2},
            "margin": {"completion_mtd_pct": 106.1, "forecast_vs_plan_pct": 4.8},
            "sales_count": {"completion_mtd_pct": 101.3, "forecast_vs_plan_pct": 1.5},
            "revenue": {"completion_mtd_pct": 120.4, "forecast_vs_plan_pct": 15.0},
            "adv_internal": {"completion_mtd_pct": 108.9, "forecast_vs_plan_pct": 12.0},
            "adv_external": {"completion_mtd_pct": 126.3, "forecast_vs_plan_pct": 30.0},
        },
    },
    "days_elapsed": 19,
    "days_in_month": 31,
}

def test_margin_lags_orders_detected():
    """Orders +13.9% but margin only +6.1% — gap > 5 pp."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "margin_lags_orders" in types

    signal = next(s for s in signals if s.type == "margin_lags_orders")
    assert signal.severity == "warning"
    assert signal.category == "margin"
    assert signal.data["gap_pct"] == pytest.approx(7.8, abs=0.1)

def test_sales_lag_expected_detected():
    """Orders +13.9% but sales only +1.3% — buyout lag."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "sales_lag_expected" in types

def test_adv_external_overspend_detected():
    """External ads +26.3% over plan — overspend."""
    signals = detect_signals(data=PLAN_FACT_DATA)
    types = [s.type for s in signals]
    assert "adv_overspend" in types

def test_no_false_signals_on_healthy_data():
    """All metrics ~100% — no signals."""
    healthy = {
        "_source": "plan_vs_fact",
        "brand_total": {
            "metrics": {
                "orders_count": {"completion_mtd_pct": 101.0, "forecast_vs_plan_pct": 1.0},
                "margin": {"completion_mtd_pct": 100.5, "forecast_vs_plan_pct": 0.5},
                "sales_count": {"completion_mtd_pct": 99.8, "forecast_vs_plan_pct": -0.2},
                "revenue": {"completion_mtd_pct": 100.2, "forecast_vs_plan_pct": 0.2},
                "adv_internal": {"completion_mtd_pct": 98.0, "forecast_vs_plan_pct": -2.0},
                "adv_external": {"completion_mtd_pct": 100.0, "forecast_vs_plan_pct": 0.0},
            },
        },
        "days_elapsed": 19,
        "days_in_month": 31,
    }
    signals = detect_signals(data=healthy)
    assert len(signals) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/shared/signals/test_plan_fact_signals.py -v`
Expected: FAIL — signals not detected

- [ ] **Step 3: Implement plan-fact signal detection**

```python
# In shared/signals/detector.py — replace _detect_plan_fact_signals

def _detect_plan_fact_signals(data: dict) -> list[Signal]:
    signals = []
    brand = data.get("brand_total", {}).get("metrics", {})
    if not brand:
        return signals

    date_suffix = f"{data.get('days_elapsed', 0)}d"

    orders_pct = brand.get("orders_count", {}).get("completion_mtd_pct", 0) or 0
    margin_pct = brand.get("margin", {}).get("completion_mtd_pct", 0) or 0
    sales_pct = brand.get("sales_count", {}).get("completion_mtd_pct", 0) or 0
    adv_int_pct = brand.get("adv_internal", {}).get("completion_mtd_pct", 0) or 0
    adv_ext_pct = brand.get("adv_external", {}).get("completion_mtd_pct", 0) or 0

    # 1. margin_lags_orders: orders grow faster than margin (gap > 5 pp)
    gap = orders_pct - margin_pct
    if gap > 5:
        signals.append(Signal(
            id=f"margin_lags_orders_{date_suffix}",
            type="margin_lags_orders",
            category="margin",
            severity="warning" if gap < 15 else "critical",
            impact_on="margin",
            data={"orders_completion_pct": orders_pct, "margin_completion_pct": margin_pct, "gap_pct": round(gap, 1)},
            hint=f"Заказы опережают маржу на {round(gap, 1)} п.п. — возможен рост низкомаржинальных позиций",
            source="plan_vs_fact",
        ))

    # 2. sales_lag_expected: orders up but sales barely up (buyout lag)
    if orders_pct > 105 and sales_pct < orders_pct - 8:
        signals.append(Signal(
            id=f"sales_lag_expected_{date_suffix}",
            type="sales_lag_expected",
            category="funnel",
            severity="info",
            impact_on="turnover",
            data={"orders_pct": orders_pct, "sales_pct": sales_pct, "gap_pct": round(orders_pct - sales_pct, 1)},
            hint=f"Заказы +{round(orders_pct - 100, 1)}%, продажи +{round(sales_pct - 100, 1)}% — выкупы подтянутся через 5-10 дней",
            source="plan_vs_fact",
        ))

    # 3. sales_lag_problem: orders up but sales DOWN
    if orders_pct > 105 and sales_pct < 95:
        signals.append(Signal(
            id=f"sales_lag_problem_{date_suffix}",
            type="sales_lag_problem",
            category="funnel",
            severity="critical",
            impact_on="both",
            data={"orders_pct": orders_pct, "sales_pct": sales_pct},
            hint=f"Заказы растут (+{round(orders_pct - 100, 1)}%), но продажи падают ({round(sales_pct - 100, 1)}%) — возможны возвраты или отмены",
            source="plan_vs_fact",
        ))

    # 4. adv_overspend: internal or external ads significantly over plan
    if adv_int_pct > 115:
        signals.append(Signal(
            id=f"adv_overspend_int_{date_suffix}",
            type="adv_overspend",
            category="adv",
            severity="warning" if adv_int_pct < 130 else "critical",
            impact_on="margin",
            data={"adv_internal_pct": adv_int_pct, "type": "internal"},
            hint=f"Внутренняя реклама перерасход: {round(adv_int_pct, 1)}% от плана МТД",
            source="plan_vs_fact",
        ))
    if adv_ext_pct > 120:
        signals.append(Signal(
            id=f"adv_overspend_ext_{date_suffix}",
            type="adv_overspend",
            category="adv",
            severity="warning" if adv_ext_pct < 140 else "critical",
            impact_on="margin",
            data={"adv_external_pct": adv_ext_pct, "type": "external"},
            hint=f"Внешняя реклама перерасход: {round(adv_ext_pct, 1)}% от плана МТД",
            source="plan_vs_fact",
        ))

    # 5. margin_pct_drop: margin dropping while revenue grows
    revenue_pct = brand.get("revenue", {}).get("completion_mtd_pct", 0) or 0
    if revenue_pct > 110 and margin_pct < 100:
        signals.append(Signal(
            id=f"margin_pct_drop_{date_suffix}",
            type="margin_pct_drop",
            category="margin",
            severity="critical",
            impact_on="margin",
            data={"revenue_pct": revenue_pct, "margin_pct": margin_pct},
            hint=f"Выручка растёт (+{round(revenue_pct - 100, 1)}%), а маржа падает ({round(margin_pct - 100, 1)}%) — проверь структуру затрат",
            source="plan_vs_fact",
        ))

    return signals
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/shared/signals/test_plan_fact_signals.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_plan_fact_signals.py
git commit -m "feat(signals): implement plan-fact signal detection (5 core patterns)"
```

---

### Task 3: Direction map for validator

**Files:**
- Create: `shared/signals/direction_map.py`
- Test: `tests/shared/signals/test_direction_map.py`

- [ ] **Step 1: Write failing test**

```python
# tests/shared/signals/test_direction_map.py
from shared.signals.direction_map import DIRECTION_MAP, is_valid_direction

def test_adv_overspend_allows_reduce():
    assert is_valid_direction("adv_overspend", "reduce_budget")

def test_adv_overspend_rejects_increase():
    assert not is_valid_direction("adv_overspend", "increase_budget")

def test_unknown_signal_allows_anything():
    assert is_valid_direction("unknown_signal_type", "anything")

def test_all_signal_types_have_valid_actions():
    for signal_type, actions in DIRECTION_MAP.items():
        assert len(actions) > 0, f"{signal_type} has no valid actions"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/shared/signals/test_direction_map.py -v`

- [ ] **Step 3: Implement direction map**

```python
# shared/signals/direction_map.py
"""Maps signal types to valid action categories for Validator."""

DIRECTION_MAP: dict[str, list[str]] = {
    # Margin signals
    "margin_lags_orders": ["reallocate_budget", "optimize_keywords", "review_pricing"],
    "margin_pct_drop": ["review_pricing", "reduce_costs", "review_assortment"],
    "cogs_anomaly": ["check_supplier", "review_pricing"],

    # Funnel signals
    "sales_lag_expected": ["monitor", "no_action"],
    "sales_lag_problem": ["check_returns", "check_quality", "review_description"],
    "ctr_drop": ["update_photos", "review_pricing", "enter_promotion"],
    "cart_to_order_drop": ["review_pricing", "check_sizes", "review_description"],
    "cro_improvement": ["monitor", "scale_up"],
    "buyout_drop": ["check_quality", "review_description", "check_sizing"],

    # Advertising signals
    "adv_overspend": ["reduce_budget", "optimize_keywords", "pause_campaign"],
    "adv_underspend": ["increase_budget", "expand_keywords"],
    "romi_critical": ["pause_campaign", "optimize_keywords", "reduce_budget"],
    "cac_exceeds_profit": ["pause_campaign", "reduce_budget", "optimize_keywords"],
    "keyword_drain": ["add_negative_keyword", "reduce_bid"],
    "organic_declining": ["check_positions", "increase_budget", "optimize_seo"],
    "ad_no_organic_growth": ["review_card", "optimize_seo", "check_relevance"],

    # Price signals
    "spp_shift_up": ["raise_price", "monitor"],
    "spp_shift_down": ["lower_price", "monitor"],
    "price_signal": ["monitor", "review_pricing"],
    "price_up_rank_risk": ["monitor", "increase_budget"],

    # Turnover / ABC signals
    "low_roi_article": ["withdraw", "reduce_price", "liquidate"],
    "high_roi_opportunity": ["scale_up", "increase_budget", "increase_stock"],
    "big_inefficient": ["review_pricing", "reduce_budget"],
    "status_mismatch": ["return_to_sale", "review_status"],

    # Logistics
    "logistics_overweight": ["optimize_localization", "reduce_returns"],
}

def is_valid_direction(signal_type: str, action_category: str) -> bool:
    """Check if action_category is valid for the given signal_type."""
    valid_actions = DIRECTION_MAP.get(signal_type)
    if valid_actions is None:
        return True  # unknown signal type — allow anything
    return action_category in valid_actions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/shared/signals/test_direction_map.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/signals/direction_map.py tests/shared/signals/test_direction_map.py
git commit -m "feat(signals): add direction map for validator action checking"
```

---

### Task 4: KB patterns table migration

**Files:**
- Create: `services/knowledge_base/migrations/003_create_kb_patterns.py`

- [ ] **Step 1: Write migration script**

```python
# services/knowledge_base/migrations/003_create_kb_patterns.py
"""Create kb_patterns table for structured business rule storage."""
import os
from supabase import create_client

def run_migration():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    sql = """
    CREATE TABLE IF NOT EXISTS kb_patterns (
        id SERIAL PRIMARY KEY,
        pattern_name VARCHAR(200) NOT NULL UNIQUE,
        description TEXT NOT NULL,
        category VARCHAR(20) NOT NULL
            CHECK (category IN ('margin', 'turnover', 'funnel', 'adv', 'price', 'model')),
        trigger_condition JSONB NOT NULL,
        action_hint TEXT,
        impact_on VARCHAR(10) NOT NULL
            CHECK (impact_on IN ('margin', 'turnover', 'both')),
        severity VARCHAR(10) DEFAULT 'warning'
            CHECK (severity IN ('info', 'warning', 'critical')),
        source_tag VARCHAR(30) NOT NULL
            CHECK (source_tag IN ('manual', 'insight', 'auto', 'base')),
        verified BOOLEAN DEFAULT FALSE,
        confidence VARCHAR(10) DEFAULT 'medium'
            CHECK (confidence IN ('high', 'medium', 'low')),
        trigger_count INT DEFAULT 0,
        last_triggered_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    ALTER TABLE kb_patterns ENABLE ROW LEVEL SECURITY;

    CREATE POLICY IF NOT EXISTS service_full_kb_patterns
        ON kb_patterns FOR ALL TO postgres USING (true) WITH CHECK (true);

    CREATE INDEX IF NOT EXISTS idx_kb_patterns_category ON kb_patterns(category);
    CREATE INDEX IF NOT EXISTS idx_kb_patterns_verified ON kb_patterns(verified);
    CREATE INDEX IF NOT EXISTS idx_kb_patterns_source ON kb_patterns(source_tag);
    """

    client.postgrest.schema("public")
    # Execute via SQL editor or psql
    print("Migration SQL generated. Execute manually via Supabase SQL editor:")
    print(sql)
    return sql

if __name__ == "__main__":
    run_migration()
```

- [ ] **Step 2: Commit**

```bash
git add services/knowledge_base/migrations/003_create_kb_patterns.py
git commit -m "feat(kb): add migration for kb_patterns table"
```

---

### Task 5: Seed base patterns into kb_patterns

**Files:**
- Create: `shared/signals/patterns.py`
- Test: `tests/shared/signals/test_patterns.py`

- [ ] **Step 1: Write test that base patterns are well-formed**

```python
# tests/shared/signals/test_patterns.py
from shared.signals.patterns import BASE_PATTERNS

def test_base_patterns_count():
    assert len(BASE_PATTERNS) >= 20

def test_pattern_has_required_fields():
    required = {"pattern_name", "description", "category", "trigger_condition",
                 "impact_on", "severity", "source_tag", "confidence"}
    for p in BASE_PATTERNS:
        missing = required - set(p.keys())
        assert not missing, f"Pattern {p.get('pattern_name', '?')} missing: {missing}"

def test_all_categories_covered():
    categories = {p["category"] for p in BASE_PATTERNS}
    assert categories >= {"margin", "funnel", "adv", "price", "turnover"}

def test_source_tag_is_base():
    for p in BASE_PATTERNS:
        assert p["source_tag"] == "base"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/shared/signals/test_patterns.py -v`

- [ ] **Step 3: Implement BASE_PATTERNS**

```python
# shared/signals/patterns.py
"""Base signal patterns — seeded into kb_patterns with source_tag='base'."""

BASE_PATTERNS: list[dict] = [
    # === 5 рычагов маржи ===
    {
        "pattern_name": "margin_lags_orders",
        "description": "Заказы растут быстрее маржи (разрыв > 5 п.п.)",
        "category": "margin",
        "trigger_condition": {"metric_pair": ["orders_completion_pct", "margin_completion_pct"], "operator": "gap_gt", "threshold": 5},
        "action_hint": "Проверить, какие модели дают рост заказов. Если низкомаржинальные — перераспределить рекламу",
        "impact_on": "margin",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "spp_shift_up",
        "description": "СПП выросла > 2 п.п. — можно поднять базовую цену",
        "category": "price",
        "trigger_condition": {"metric": "spp_delta_pp", "operator": ">", "threshold": 2},
        "action_hint": "Для A-группы (стратегия Маржа): поднять базовую цену. Для Growth: оставить, ловить долю рынка",
        "impact_on": "margin",
        "severity": "info",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "spp_shift_down",
        "description": "СПП упала > 2 п.п. — клиентская цена выросла, конверсия под угрозой",
        "category": "price",
        "trigger_condition": {"metric": "spp_delta_pp", "operator": "<", "threshold": -2},
        "action_hint": "Рассмотреть снижение базовой цены для сохранения клиентской цены и спроса",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "adv_overspend",
        "description": "ДРР выше нормы (>12% WB, >18% Ozon внутр.)",
        "category": "adv",
        "trigger_condition": {"metric": "drr_internal_pct", "operator": ">", "threshold": 12, "scope": "channel"},
        "action_hint": "Оптимизировать ключевые слова, снизить ставки на низкоконверсионных, проверить ROMI по кампаниям",
        "impact_on": "margin",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "adv_underspend",
        "description": "ДРР ниже нормы, но заказы не растут — мало трафика",
        "category": "adv",
        "trigger_condition": {"metric": "drr_internal_pct", "operator": "<", "threshold": 5, "and": {"metric": "orders_growth_pct", "operator": "<", "threshold": 0}},
        "action_hint": "Увеличить рекламный бюджет, расширить семантику",
        "impact_on": "both",
        "severity": "info",
        "source_tag": "base",
        "confidence": "medium",
    },
    {
        "pattern_name": "logistics_overweight",
        "description": "Логистика > 8% от выручки",
        "category": "margin",
        "trigger_condition": {"metric": "logistics_share_pct", "operator": ">", "threshold": 8},
        "action_hint": "Проверить индекс локализации (WB), сроки доставки (Ozon), уровень возвратов",
        "impact_on": "margin",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "cogs_anomaly",
        "description": "Себестоимость отклонилась > 5% от нормы (~350 руб)",
        "category": "margin",
        "trigger_condition": {"metric": "cogs_deviation_pct", "operator": ">", "threshold": 5},
        "action_hint": "Проверить поставщика, микс артикулов",
        "impact_on": "margin",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    # === Воронка ===
    {
        "pattern_name": "ctr_drop",
        "description": "CTR < 2% (WB) или < 1.5% (Ozon)",
        "category": "funnel",
        "trigger_condition": {"metric": "ctr_pct", "operator": "<", "threshold": 2, "scope": "channel"},
        "action_hint": "Обновить главное фото, проверить ценовую конкурентоспособность, войти в акцию МП",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "cart_to_order_drop",
        "description": "CR корзина-заказ упал > 5 п.п. WoW",
        "category": "funnel",
        "trigger_condition": {"metric": "cart_to_order_delta_pp", "operator": "<", "threshold": -5},
        "action_hint": "Проверить: цена изменилась? размеры в наличии? сроки доставки? конкуренты?",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "cro_improvement",
        "description": "Сквозная конверсия переход-заказ выросла",
        "category": "funnel",
        "trigger_condition": {"metric": "cro_delta_pp", "operator": ">", "threshold": 0.5},
        "action_hint": "Позитивный сигнал. Больше заказов с того же трафика = ДРР снижается",
        "impact_on": "both",
        "severity": "info",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "sales_lag_expected",
        "description": "Заказы растут значительно, продажи слабо — лаг выкупов",
        "category": "funnel",
        "trigger_condition": {"metric_pair": ["orders_growth_pct", "sales_growth_pct"], "operator": "gap_gt", "threshold": 8},
        "action_hint": "Не тревога. Продажи подтянутся через 5-10 дней. Мониторить",
        "impact_on": "turnover",
        "severity": "info",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "sales_lag_problem",
        "description": "Заказы растут, продажи падают — возвраты или отмены",
        "category": "funnel",
        "trigger_condition": {"and": [
            {"metric": "orders_growth_pct", "operator": ">", "threshold": 5},
            {"metric": "sales_growth_pct", "operator": "<", "threshold": -5},
        ]},
        "action_hint": "Проверить причины возвратов/отмен: качество, соответствие описанию, размерная сетка",
        "impact_on": "both",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "buyout_drop",
        "description": "Выкуп < 45% WB или < 30% Ozon",
        "category": "funnel",
        "trigger_condition": {"metric": "buyout_pct", "operator": "<", "threshold": 45, "scope": "channel"},
        "action_hint": "Анализировать: доставка, соответствие фото/описанию, качество, размерная сетка",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "medium",
    },
    # === Реклама ===
    {
        "pattern_name": "romi_critical",
        "description": "ROMI < 50% — реклама глубоко убыточна",
        "category": "adv",
        "trigger_condition": {"metric": "romi_pct", "operator": "<", "threshold": 50},
        "action_hint": "СТОП реклама, переход на органику. Исключение: новые модели < 4 нед.",
        "impact_on": "margin",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "cac_exceeds_profit",
        "description": "CAC > маржа на единицу — каждый заказ убыточен",
        "category": "adv",
        "trigger_condition": {"metric_pair": ["cac_rub", "margin_per_unit_rub"], "operator": "a_gt_b"},
        "action_hint": "Снизить ставки или остановить рекламу на этом артикуле",
        "impact_on": "margin",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "keyword_drain",
        "description": "Ключевое слово: много трафика, 0 заказов — пустышка",
        "category": "adv",
        "trigger_condition": {"metric": "keyword_orders", "operator": "==", "threshold": 0, "and": {"metric": "keyword_clicks", "operator": ">", "threshold": 50}},
        "action_hint": "Добавить в минус-слова или снизить ставку",
        "impact_on": "margin",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "organic_declining",
        "description": "Доля органики упала > 5 п.п. WoW — зависимость от рекламы растёт",
        "category": "adv",
        "trigger_condition": {"metric": "organic_share_delta_pp", "operator": "<", "threshold": -5},
        "action_hint": "Проверить позиции по ключевым запросам, новых конкурентов, изменения алгоритма WB",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "medium",
    },
    {
        "pattern_name": "ad_no_organic_growth",
        "description": "Рекламируем, но органика не растёт — проблема с карточкой",
        "category": "adv",
        "trigger_condition": {"and": [
            {"metric": "adv_spend_growth_pct", "operator": ">", "threshold": 10},
            {"metric": "organic_share_delta_pp", "operator": "<", "threshold": 0},
        ]},
        "action_hint": "Проверить карточку: релевантность запросам, фото, описание, отзывы",
        "impact_on": "both",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "medium",
    },
    # === Оборачиваемость + ABC ===
    {
        "pattern_name": "low_roi_article",
        "description": "ABC=C + маржа <15% + оборачиваемость > 1.5x медианы — кандидат на вывод",
        "category": "turnover",
        "trigger_condition": {"and": [
            {"metric": "abc_class", "operator": "==", "threshold": "C"},
            {"metric": "margin_pct", "operator": "<", "threshold": 15},
            {"metric": "turnover_ratio", "operator": ">", "threshold": 1.5},
        ]},
        "action_hint": "Кандидат на вывод. Проверить: можно ли снизить цену для ликвидации?",
        "impact_on": "turnover",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "high_roi_opportunity",
        "description": "Быстрая оборачиваемость + маржа > 25% — масштабировать",
        "category": "turnover",
        "trigger_condition": {"and": [
            {"metric": "margin_pct", "operator": ">", "threshold": 25},
            {"metric": "turnover_ratio", "operator": "<", "threshold": 0.8},
        ]},
        "action_hint": "Увеличить запас, нарастить рекламу, расширить размерный ряд",
        "impact_on": "both",
        "severity": "info",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "big_inefficient",
        "description": "ABC=A/B + маржа < 10% — большой, но неэффективный",
        "category": "model",
        "trigger_condition": {"and": [
            {"metric": "abc_class", "operator": "in", "threshold": ["A", "B"]},
            {"metric": "margin_pct", "operator": "<", "threshold": 10},
        ]},
        "action_hint": "Пересмотреть ценообразование. Проверить: можно ли поднять цену без потери объёма?",
        "impact_on": "margin",
        "severity": "warning",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "status_mismatch",
        "description": "Статус 'Выводим' + ABC=A/B + маржа > 15% — ошибка статуса",
        "category": "model",
        "trigger_condition": {"and": [
            {"metric": "status", "operator": "==", "threshold": "withdrawing"},
            {"metric": "abc_class", "operator": "in", "threshold": ["A", "B"]},
            {"metric": "margin_pct", "operator": ">", "threshold": 15},
        ]},
        "action_hint": "Проверить причину вывода. Если нет веской причины — вернуть в продажу",
        "impact_on": "both",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    # === Ценовые ===
    {
        "pattern_name": "price_signal",
        "description": "Ср. чек заказов != ср. чек продаж (> 5%) — прогноз выручки",
        "category": "price",
        "trigger_condition": {"metric_pair": ["avg_order_price", "avg_sale_price"], "operator": "gap_pct_gt", "threshold": 5},
        "action_hint": "Если чек заказов > чек продаж — выручка вырастет через 3-7 дней. Наоборот — упадёт",
        "impact_on": "margin",
        "severity": "info",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "margin_pct_drop",
        "description": "Маржинальность % падает при росте выручки — рост неэффективен",
        "category": "margin",
        "trigger_condition": {"and": [
            {"metric": "revenue_growth_pct", "operator": ">", "threshold": 10},
            {"metric": "margin_completion_pct", "operator": "<", "threshold": 100},
        ]},
        "action_hint": "Проверить 5 рычагов маржи: цена, СПП, ДРР, логистика, себестоимость",
        "impact_on": "margin",
        "severity": "critical",
        "source_tag": "base",
        "confidence": "high",
    },
    {
        "pattern_name": "price_up_rank_risk",
        "description": "Цена поднята — риск потери позиций и роста ДРР",
        "category": "price",
        "trigger_condition": {"metric": "price_change_pct", "operator": ">", "threshold": 3},
        "action_hint": "Мониторить: позиции, конверсию, ДРР на следующий день. Если конверсия упала > 10% — откатить",
        "impact_on": "both",
        "severity": "info",
        "source_tag": "base",
        "confidence": "medium",
    },
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/shared/signals/test_patterns.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/signals/patterns.py tests/shared/signals/test_patterns.py
git commit -m "feat(signals): add 25 base patterns for kb_patterns seeding"
```

---

## Phase 2: Advisor Agent

### Task 6: Advisor Agent — prompts, tools, agent class

**Files:**
- Create: `agents/oleg/agents/advisor/__init__.py`
- Create: `agents/oleg/agents/advisor/prompts.py`
- Create: `agents/oleg/agents/advisor/tools.py`
- Create: `agents/oleg/agents/advisor/agent.py`
- Test: `tests/agents/oleg/agents/advisor/test_advisor.py`

- [ ] **Step 1: Create advisor prompts**

```python
# agents/oleg/agents/advisor/prompts.py
"""Advisor Agent system prompt."""
import logging

logger = logging.getLogger(__name__)

ADVISOR_PREAMBLE = """Ты — Advisor, суб-агент системы Олег v2.

Твоя роль: формировать actionable рекомендации на основе обнаруженных сигналов в данных.
Все рекомендации привязаны к двум главным целям бизнеса:
1. Максимизация оборачиваемости товара
2. Максимизация маржинальности

## ВХОД
Ты получаешь:
- signals[] — обнаруженные паттерны (от Signal Detector)
- structured_data — сырые данные отчёта
- kb_patterns[] — известные паттерны из базы знаний
- report_type — "daily" | "weekly" | "monthly"

## ВЫХОД (structured JSON)
{
    "recommendations": [...],
    "new_patterns": [...]
}

## ГЛУБИНА ПО ТИПУ ОТЧЁТА
- daily: макс. 3 рекомендации, только critical + warning, короткие действия
- weekly: макс. 7 рекомендаций, все severity, конкретные действия с эффектом
- monthly: макс. 15 рекомендаций, стратегические решения + предложение новых паттернов

## ФОРМАТ РЕКОМЕНДАЦИИ
{
    "signal_id": "id сигнала",
    "priority": 1,
    "category": "margin|turnover|funnel|adv|price|model",
    "diagnosis": "Что происходит (с точными числами из signal.data)",
    "root_cause": "Почему это происходит",
    "action": "Конкретное действие",
    "action_category": "одно из допустимых действий для этого типа сигнала",
    "expected_impact": {
        "metric": "какая метрика изменится",
        "delta": "на сколько",
        "confidence": "high|medium|low"
    },
    "affects": "margin|turnover|both",
    "timeframe": "когда увидим эффект"
}

## ФОРМАТ НОВОГО ПАТТЕРНА (только weekly/monthly)
{
    "pattern_name": "snake_case_name",
    "description": "Описание на русском",
    "evidence": "На чём основано наблюдение",
    "category": "margin|turnover|funnel|adv|price|model",
    "confidence": "high|medium|low"
}

## ЯЗЫКОВЫЕ ПРАВИЛА
- Аббревиатуры на русском: ДРР, СПП, МТД
- Валюта: руб, тыс, млн
- Confidence на английском: high, medium, low
- Все тексты рекомендаций на русском

## КРИТИЧНО
- НИКОГДА не придумывай числа — бери только из signals[].data
- Каждая рекомендация ОБЯЗАНА ссылаться на конкретный signal_id
- action_category ОБЯЗАНА быть из допустимого списка для данного signal.type
- Приоритизируй по влиянию на маржу в рублях (не в процентах)
"""

def get_advisor_system_prompt() -> str:
    return ADVISOR_PREAMBLE
```

- [ ] **Step 2: Create advisor tools**

```python
# agents/oleg/agents/advisor/tools.py
"""Advisor Agent tool definitions and executor."""
import json

# Advisor has access to KB search for finding relevant patterns
_kb_available = False
try:
    from services.knowledge_base.tools import KB_SEARCH_TOOL_DEFINITIONS, execute_kb_tool
    _kb_available = True
except ImportError:
    KB_SEARCH_TOOL_DEFINITIONS = []

ADVISOR_TOOL_DEFINITIONS = list(KB_SEARCH_TOOL_DEFINITIONS)

async def execute_advisor_tool(tool_name: str, tool_args: dict) -> str:
    if _kb_available and tool_name == "search_knowledge_base":
        return await execute_kb_tool(tool_name, tool_args)
    return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
```

- [ ] **Step 3: Create advisor agent class**

```python
# agents/oleg/agents/advisor/agent.py
"""Advisor Agent — universal recommendation engine."""
from typing import List, Dict, Any, Optional
from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.advisor.tools import ADVISOR_TOOL_DEFINITIONS, execute_advisor_tool
from agents.oleg.agents.advisor.prompts import get_advisor_system_prompt

class AdvisorAgent(BaseAgent):
    def __init__(self, llm_client, model: str, pricing: Optional[dict] = None):
        super().__init__(
            llm_client, model, pricing=pricing,
            max_iterations=5,  # Advisor should be fast
            total_timeout_sec=90.0,
        )

    @property
    def agent_name(self) -> str:
        return "advisor"

    def get_system_prompt(self) -> str:
        return get_advisor_system_prompt()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return ADVISOR_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_advisor_tool(tool_name, tool_args)
```

```python
# agents/oleg/agents/advisor/__init__.py
from .agent import AdvisorAgent

__all__ = ["AdvisorAgent"]
```

- [ ] **Step 4: Write smoke tests for AdvisorAgent**

```python
# tests/agents/oleg/agents/advisor/test_advisor.py
"""Smoke tests for AdvisorAgent."""
import pytest
from unittest.mock import MagicMock
from agents.oleg.agents.advisor.agent import AdvisorAgent
from agents.oleg.agents.advisor.prompts import get_advisor_system_prompt


def test_advisor_agent_instantiation():
    mock_llm = MagicMock()
    agent = AdvisorAgent(mock_llm, "test-model")
    assert agent.agent_name == "advisor"


def test_advisor_system_prompt_not_empty():
    prompt = get_advisor_system_prompt()
    assert len(prompt) > 100
    assert "action_category" in prompt
    assert "оборачиваемость" in prompt.lower() or "маржинальность" in prompt.lower()


def test_advisor_tool_definitions_is_list():
    mock_llm = MagicMock()
    agent = AdvisorAgent(mock_llm, "test-model")
    tools = agent.get_tool_definitions()
    assert isinstance(tools, list)
```

- [ ] **Step 5: Run smoke tests**

Run: `python -m pytest tests/agents/oleg/agents/advisor/test_advisor.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agents/oleg/agents/advisor/ tests/agents/oleg/agents/advisor/
git commit -m "feat(advisor): add Advisor Agent — prompts, tools, agent class with tests"
```

---

## Phase 3: Validator Agent

### Task 7: Validator scripts (deterministic checks)

**Files:**
- Create: `agents/oleg/agents/validator/scripts/__init__.py`
- Create: `agents/oleg/agents/validator/scripts/check_numbers.py`
- Create: `agents/oleg/agents/validator/scripts/check_coverage.py`
- Create: `agents/oleg/agents/validator/scripts/check_direction.py`
- Create: `agents/oleg/agents/validator/scripts/check_kb_rules.py`
- Test: `tests/agents/oleg/agents/validator/test_scripts.py`

- [ ] **Step 1: Write failing tests for all 4 scripts**

```python
# tests/agents/oleg/agents/validator/test_scripts.py
import pytest
from agents.oleg.agents.validator.scripts.check_numbers import check_numbers
from agents.oleg.agents.validator.scripts.check_coverage import check_coverage
from agents.oleg.agents.validator.scripts.check_direction import check_direction
from agents.oleg.agents.validator.scripts.check_kb_rules import check_kb_rules

# --- check_numbers ---
def test_check_numbers_match():
    signal_data = {"orders_completion_pct": 113.9, "margin_completion_pct": 106.1}
    rec = {"diagnosis": "Заказы +113.9% к плану, маржа +106.1%", "signal_id": "test"}
    result = check_numbers(signal_data, rec)
    assert result["match"] is True

def test_check_numbers_mismatch():
    signal_data = {"orders_completion_pct": 113.9}
    rec = {"diagnosis": "Заказы +6% к плану", "signal_id": "test"}
    result = check_numbers(signal_data, rec)
    assert result["match"] is False
    assert len(result["mismatches"]) > 0

# --- check_coverage ---
def test_check_coverage_all_covered():
    signals = [
        {"id": "s1", "severity": "warning"},
        {"id": "s2", "severity": "critical"},
        {"id": "s3", "severity": "info"},
    ]
    recs = [{"signal_id": "s1"}, {"signal_id": "s2"}]
    result = check_coverage(signals, recs)
    assert len(result["missed"]) == 0  # info can be skipped

def test_check_coverage_missed_warning():
    signals = [{"id": "s1", "severity": "warning"}, {"id": "s2", "severity": "warning"}]
    recs = [{"signal_id": "s1"}]
    result = check_coverage(signals, recs)
    assert "s2" in result["missed"]

# --- check_direction ---
def test_check_direction_valid():
    result = check_direction("adv_overspend", "reduce_budget")
    assert result["valid"] is True

def test_check_direction_invalid():
    result = check_direction("adv_overspend", "increase_budget")
    assert result["valid"] is False

# --- check_kb_rules ---
def test_check_kb_rules_no_conflict():
    rec = {"action": "поднять цену", "action_category": "raise_price"}
    kb_patterns = [
        {"pattern_name": "no_price_drop_low_stock", "trigger_condition": {"metric": "stock_days", "operator": "<", "threshold": 14}, "action_hint": "не снижать цену"}
    ]
    # This recommendation raises price, not lowers — no conflict
    result = check_kb_rules(rec, kb_patterns)
    assert len(result["conflicts"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agents/oleg/agents/validator/test_scripts.py -v`

- [ ] **Step 3: Implement all 4 scripts**

```python
# agents/oleg/agents/validator/scripts/__init__.py
```

```python
# agents/oleg/agents/validator/scripts/check_numbers.py
"""Deterministic number validation: signal.data vs recommendation fields."""
import re

def _number_found(value: float, text: str) -> bool:
    """Check if number appears in text with word-boundary matching."""
    str_val = str(round(value, 1))
    # Word boundary regex: prevents 113.9 matching inside 1113.9
    pattern = r'(?<!\d)' + re.escape(str_val) + r'(?!\d)'
    if re.search(pattern, text):
        return True
    # Also check integer form for whole numbers (e.g., 114 for 114.0)
    if value == int(value):
        str_int = str(int(value))
        pattern_int = r'(?<!\d)' + re.escape(str_int) + r'(?!\d)'
        if re.search(pattern_int, text):
            return True
    return False

def check_numbers(signal_data: dict, recommendation: dict) -> dict:
    """Check that numbers in recommendation match signal data (field-by-field)."""
    mismatches = []
    diagnosis = recommendation.get("diagnosis", "")

    for field, expected_value in signal_data.items():
        if not isinstance(expected_value, (int, float)):
            continue
        if not _number_found(expected_value, diagnosis):
            mismatches.append({
                "field": field,
                "signal": expected_value,
                "not_found_in": "diagnosis",
            })

    return {
        "match": len(mismatches) == 0,
        "mismatches": mismatches,
    }
```

```python
# agents/oleg/agents/validator/scripts/check_coverage.py
"""Check that all warning/critical signals are covered by recommendations."""

def check_coverage(signals: list[dict], recommendations: list[dict]) -> dict:
    """Verify all signals with severity >= warning have a recommendation."""
    covered_ids = {r.get("signal_id") for r in recommendations}

    covered = []
    missed = []
    info_skipped = []

    for signal in signals:
        sid = signal.get("id", "")
        severity = signal.get("severity", "info")

        if sid in covered_ids:
            covered.append(sid)
        elif severity in ("warning", "critical"):
            missed.append(sid)
        else:
            info_skipped.append(sid)

    return {
        "covered": covered,
        "missed": missed,
        "info_skipped": info_skipped,
    }
```

```python
# agents/oleg/agents/validator/scripts/check_direction.py
"""Check action direction using DIRECTION_MAP."""
from shared.signals.direction_map import is_valid_direction, DIRECTION_MAP

def check_direction(signal_type: str, action_category: str) -> dict:
    """Check if action_category is valid for the given signal_type."""
    valid = is_valid_direction(signal_type, action_category)
    valid_actions = DIRECTION_MAP.get(signal_type, [])

    reason = ""
    if not valid:
        reason = (
            f"Сигнал '{signal_type}' допускает: {', '.join(valid_actions)}. "
            f"Получено: {action_category} — конфликт"
        )

    return {"valid": valid, "reason": reason}
```

```python
# agents/oleg/agents/validator/scripts/check_kb_rules.py
"""Check recommendation against KB pattern rules for conflicts."""

# Action categories that conflict with each other
OPPOSING_ACTIONS = {
    "raise_price": {"lower_price", "reduce_price", "liquidate"},
    "lower_price": {"raise_price"},
    "increase_budget": {"reduce_budget", "pause_campaign"},
    "reduce_budget": {"increase_budget", "scale_up"},
    "pause_campaign": {"increase_budget", "scale_up"},
    "scale_up": {"reduce_budget", "pause_campaign", "withdraw"},
    "withdraw": {"scale_up", "return_to_sale", "increase_stock"},
}

def check_kb_rules(recommendation: dict, kb_patterns: list[dict]) -> dict:
    """Check if recommendation conflicts with known KB rules."""
    conflicts = []
    rec_action = recommendation.get("action_category", "")

    for pattern in kb_patterns:
        hint = (pattern.get("action_hint", "") or "").lower()
        pattern_name = pattern.get("pattern_name", "")

        # Check if the pattern's action hint opposes the recommendation
        opposing = OPPOSING_ACTIONS.get(rec_action, set())
        for opp_action in opposing:
            if opp_action.replace("_", " ") in hint:
                conflicts.append({
                    "pattern_name": pattern_name,
                    "rule": pattern.get("description", ""),
                    "conflict": f"Рекомендация '{rec_action}' конфликтует с правилом: {pattern.get('action_hint', '')}",
                })

    return {"conflicts": conflicts}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agents/oleg/agents/validator/test_scripts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/oleg/agents/validator/ tests/agents/oleg/agents/validator/
git commit -m "feat(validator): add 4 deterministic validation scripts with tests"
```

---

### Task 8: Validator Agent — prompts, tools, agent class

**Files:**
- Create: `agents/oleg/agents/validator/prompts.py`
- Create: `agents/oleg/agents/validator/tools.py`
- Create: `agents/oleg/agents/validator/agent.py`
- Create: `agents/oleg/agents/validator/__init__.py`

- [ ] **Step 1: Create validator prompts**

```python
# agents/oleg/agents/validator/prompts.py
"""Validator Agent system prompt."""

VALIDATOR_PREAMBLE = """Ты — Validator, суб-агент системы Олег v2.

Твоя роль: проверить рекомендации от Advisor Agent перед включением в отчёт.
У тебя есть детерминированные скрипты для проверки + собственное экспертное суждение.

## ВХОД
- recommendations[] — рекомендации от Advisor
- signals[] — исходные сигналы
- structured_data — сырые данные

## ПРОЦЕСС
1. Вызови check_numbers для каждой рекомендации — числа совпадают с сигналом?
2. Вызови check_coverage — все warning/critical сигналы покрыты?
3. Вызови check_direction для каждой рекомендации — направление действия логично?
4. Вызови check_kb_rules — нет конфликтов с правилами KB?
5. Оцени сам: expected_impact реалистичен?

## ВЫХОД
Ответь JSON:
{
    "verdict": "pass" | "fail",
    "checks": [
        {"check": "numbers", "passed": true/false, "details": "..."},
        {"check": "coverage", "passed": true/false, "details": "..."},
        {"check": "direction", "passed": true/false, "details": "..."},
        {"check": "kb_rules", "passed": true/false, "details": "..."},
        {"check": "impact_plausibility", "passed": true/false, "details": "..."}
    ],
    "issues": ["описание проблемы 1", "..."],
    "recommendations_ok": [0, 1, 3],     # индексы прошедших рекомендаций
    "recommendations_failed": [2]         # индексы проваленных
}

## ПРАВИЛА
- verdict = "pass" если ВСЕ check_numbers и check_direction прошли + coverage покрыта
- verdict = "fail" если ХОТЯ БЫ ОДНА рекомендация имеет неверные числа или конфликт направления
- impact_plausibility — твоё экспертное суждение, не блокирует verdict
"""

def get_validator_system_prompt() -> str:
    return VALIDATOR_PREAMBLE
```

- [ ] **Step 2: Create validator tools (wrapping scripts)**

```python
# agents/oleg/agents/validator/tools.py
"""Validator Agent tool definitions and executor."""
import json
from agents.oleg.agents.validator.scripts.check_numbers import check_numbers
from agents.oleg.agents.validator.scripts.check_coverage import check_coverage
from agents.oleg.agents.validator.scripts.check_direction import check_direction
from agents.oleg.agents.validator.scripts.check_kb_rules import check_kb_rules

VALIDATOR_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "validate_numbers",
            "description": "Проверить, что числа в рекомендации совпадают с данными сигнала",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_data": {"type": "object", "description": "signal.data dict"},
                    "recommendation": {"type": "object", "description": "recommendation dict"},
                },
                "required": ["signal_data", "recommendation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_coverage",
            "description": "Проверить, что все warning/critical сигналы покрыты рекомендациями",
            "parameters": {
                "type": "object",
                "properties": {
                    "signals": {"type": "array", "description": "Массив сигналов"},
                    "recommendations": {"type": "array", "description": "Массив рекомендаций"},
                },
                "required": ["signals", "recommendations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_direction",
            "description": "Проверить, что направление действия допустимо для данного типа сигнала",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_type": {"type": "string"},
                    "action_category": {"type": "string"},
                },
                "required": ["signal_type", "action_category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_kb_rules",
            "description": "Проверить, что рекомендация не конфликтует с правилами из KB",
            "parameters": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "object"},
                    "kb_patterns": {"type": "array"},
                },
                "required": ["recommendation", "kb_patterns"],
            },
        },
    },
]

async def execute_validator_tool(tool_name: str, tool_args: dict) -> str:
    if tool_name == "validate_numbers":
        result = check_numbers(tool_args["signal_data"], tool_args["recommendation"])
    elif tool_name == "validate_coverage":
        result = check_coverage(tool_args["signals"], tool_args["recommendations"])
    elif tool_name == "validate_direction":
        result = check_direction(tool_args["signal_type"], tool_args["action_category"])
    elif tool_name == "validate_kb_rules":
        result = check_kb_rules(tool_args["recommendation"], tool_args["kb_patterns"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, ensure_ascii=False)
```

- [ ] **Step 3: Create validator agent class**

```python
# agents/oleg/agents/validator/agent.py
"""Validator Agent — recommendation verification with deterministic scripts."""
from typing import List, Dict, Any, Optional
from agents.oleg.agents.base_agent import BaseAgent
from agents.oleg.agents.validator.tools import VALIDATOR_TOOL_DEFINITIONS, execute_validator_tool
from agents.oleg.agents.validator.prompts import get_validator_system_prompt

class ValidatorAgent(BaseAgent):
    def __init__(self, llm_client, model: str, pricing: Optional[dict] = None):
        super().__init__(
            llm_client, model, pricing=pricing,
            max_iterations=5,
            total_timeout_sec=120.0,  # spec: 120s for validator
        )

    @property
    def agent_name(self) -> str:
        return "validator"

    def get_system_prompt(self) -> str:
        return get_validator_system_prompt()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return VALIDATOR_TOOL_DEFINITIONS

    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        return await execute_validator_tool(tool_name, tool_args)
```

```python
# agents/oleg/agents/validator/__init__.py
from .agent import ValidatorAgent

__all__ = ["ValidatorAgent"]
```

- [ ] **Step 4: Write smoke tests for ValidatorAgent**

```python
# tests/agents/oleg/agents/validator/test_validator_agent.py
"""Smoke tests for ValidatorAgent."""
from unittest.mock import MagicMock
from agents.oleg.agents.validator.agent import ValidatorAgent
from agents.oleg.agents.validator.prompts import get_validator_system_prompt


def test_validator_agent_instantiation():
    mock_llm = MagicMock()
    agent = ValidatorAgent(mock_llm, "test-model")
    assert agent.agent_name == "validator"


def test_validator_system_prompt_contains_checks():
    prompt = get_validator_system_prompt()
    assert "check_numbers" in prompt or "validate_numbers" in prompt
    assert "verdict" in prompt


def test_validator_has_4_tools():
    mock_llm = MagicMock()
    agent = ValidatorAgent(mock_llm, "test-model")
    tools = agent.get_tool_definitions()
    assert len(tools) == 4
    tool_names = {t["function"]["name"] for t in tools}
    assert tool_names == {"validate_numbers", "validate_coverage", "validate_direction", "validate_kb_rules"}
```

- [ ] **Step 5: Run smoke tests**

Run: `python -m pytest tests/agents/oleg/agents/validator/test_validator_agent.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agents/oleg/agents/validator/ tests/agents/oleg/agents/validator/
git commit -m "feat(validator): add Validator Agent with deterministic script tools and tests"
```

---

## Phase 4: Orchestrator Integration

### Task 9: Extend AgentResult, register agents, add advisor chain

**Files:**
- Modify: `agents/oleg/executor/react_loop.py` — add `structured_data` and `recommendations` to AgentResult
- Modify: `agents/oleg/app.py` — register AdvisorAgent + ValidatorAgent
- Modify: `agents/oleg/orchestrator/orchestrator.py` — add `_run_advisor_chain()` method
- Modify: `agents/oleg/orchestrator/prompts.py` — add advisor/validator to DECIDE_NEXT_STEP_PROMPT
- Test: `tests/agents/oleg/orchestrator/test_advisor_chain.py`

**Важно:** Эта задача модифицирует существующие файлы. Перед изменением ОБЯЗАТЕЛЬНО прочитай текущее содержимое и следуй существующим паттернам.

- [ ] **Step 1: Read current files**

Read: `agents/oleg/executor/react_loop.py` — find `AgentResult` dataclass
Read: `agents/oleg/app.py` — find where agents are initialized
Read: `agents/oleg/orchestrator/orchestrator.py` — find `run_chain` and `_decide_next_step`
Read: `agents/oleg/orchestrator/prompts.py` — find `DECIDE_NEXT_STEP_PROMPT`

- [ ] **Step 2: Extend AgentResult with structured_data and recommendations**

In `agents/oleg/executor/react_loop.py`, add two new fields to `AgentResult`:

```python
@dataclass
class AgentResult:
    """Final result of agent execution."""
    content: str
    steps: List[AgentStep] = field(default_factory=list)
    total_usage: Dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )
    total_cost: float = 0.0
    iterations: int = 0
    duration_ms: int = 0
    finish_reason: str = "stop"
    _messages: List[Dict] = field(default_factory=list, repr=False)
    # NEW: structured data for advisor chain
    structured_data: Dict = field(default_factory=dict)
    recommendations: List = field(default_factory=list)
```

- [ ] **Step 3: Add AdvisorAgent + ValidatorAgent to app.py setup()**

In `app.py`, add imports and initialization after existing agents:

```python
from agents.oleg.agents.advisor import AdvisorAgent
from agents.oleg.agents.validator import ValidatorAgent

# In setup(), after existing agent initialization:
self.advisor = AdvisorAgent(self.llm_client, self.config.ANALYTICS_MODEL, pricing=PRICING)
self.validator = ValidatorAgent(self.llm_client, self.config.ANALYTICS_MODEL, pricing=PRICING)

# Add to agents dict passed to orchestrator (find existing dict and add):
    "advisor": self.advisor,
    "validator": self.validator,
```

- [ ] **Step 4: Add `_run_advisor_chain()` to orchestrator**

In `agents/oleg/orchestrator/orchestrator.py`, add two methods to `OlegOrchestrator`:

```python
import json

async def _run_signal_detection(self, structured_data: dict) -> list[dict]:
    """Run Signal Detector on structured data. Pure Python, no LLM."""
    try:
        from shared.signals import detect_signals
        signals = detect_signals(data=structured_data)
        return [vars(s) for s in signals]
    except Exception as e:
        logger.warning(f"Signal detection failed: {e}")
        return []

async def _run_advisor_chain(
    self,
    structured_data: dict,
    report_type: str,
    chain_history: list,
) -> dict:
    """
    Run advisor chain: Signal Detection → Advisor → Validator.
    Returns validated recommendations or empty dict on failure.

    Flow:
    1. detect_signals(structured_data) → signals[]
    2. advisor.analyze(signals + data) → recommendations[]
    3. validator.analyze(recommendations + signals) → verdict
    4. If verdict=fail → retry advisor once with feedback
    5. If still fail → return recommendations without validation, marked unverified
    """
    # Step 1: Signal detection (pure Python, no LLM)
    signals = await self._run_signal_detection(structured_data)
    if not signals:
        logger.info("Advisor chain: no signals detected, skipping")
        return {"recommendations": [], "signals": []}

    logger.info(f"Advisor chain: {len(signals)} signals detected")

    # Step 2: Advisor — generate recommendations
    advisor = self.agents.get("advisor")
    if not advisor:
        logger.warning("Advisor agent not registered, skipping chain")
        return {"recommendations": [], "signals": signals}

    advisor_instruction = (
        f"Сформируй рекомендации для {report_type} отчёта.\n\n"
        f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
        f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}\n\n"
        f"report_type = \"{report_type}\""
    )

    advisor_result = await advisor.analyze(
        instruction=advisor_instruction,
        context="",
    )

    # Parse advisor output
    try:
        advisor_output = json.loads(advisor_result.content)
        recommendations = advisor_output.get("recommendations", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Advisor output is not valid JSON, skipping validation")
        return {"recommendations": [], "signals": signals, "raw_advisor": advisor_result.content}

    if not recommendations:
        return {"recommendations": [], "signals": signals}

    # Step 3: Validator — verify recommendations
    validator = self.agents.get("validator")
    if not validator:
        logger.warning("Validator agent not registered, returning unverified")
        for r in recommendations:
            r["verified"] = False
        return {"recommendations": recommendations, "signals": signals}

    validator_instruction = (
        f"Проверь рекомендации от Advisor.\n\n"
        f"recommendations = {json.dumps(recommendations, ensure_ascii=False, default=str)}\n\n"
        f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
        f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}"
    )

    validator_result = await validator.analyze(
        instruction=validator_instruction,
        context="",
    )

    try:
        verdict = json.loads(validator_result.content)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Validator output is not valid JSON, returning unverified")
        for r in recommendations:
            r["verified"] = False
        return {"recommendations": recommendations, "signals": signals}

    if verdict.get("verdict") == "pass":
        for r in recommendations:
            r["verified"] = True
        return {"recommendations": recommendations, "signals": signals, "verdict": verdict}

    # Step 4: Retry once — send validator feedback to advisor
    logger.info(f"Validator: FAIL — {verdict.get('issues', [])}")
    retry_instruction = (
        f"Валидатор отклонил рекомендации. Исправь и повтори.\n\n"
        f"Проблемы: {json.dumps(verdict.get('issues', []), ensure_ascii=False)}\n\n"
        f"Оригинальные рекомендации: {json.dumps(recommendations, ensure_ascii=False, default=str)}\n\n"
        f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
        f"report_type = \"{report_type}\""
    )

    retry_result = await advisor.analyze(instruction=retry_instruction, context="")
    try:
        retry_output = json.loads(retry_result.content)
        retry_recs = retry_output.get("recommendations", [])
    except (json.JSONDecodeError, AttributeError):
        # Give up — return original with unverified flag
        for r in recommendations:
            r["verified"] = False
        return {"recommendations": recommendations, "signals": signals}

    # Re-validate
    revalidate_instruction = (
        f"Проверь исправленные рекомендации.\n\n"
        f"recommendations = {json.dumps(retry_recs, ensure_ascii=False, default=str)}\n\n"
        f"signals = {json.dumps(signals, ensure_ascii=False, default=str)}\n\n"
        f"structured_data = {json.dumps(structured_data, ensure_ascii=False, default=str)}"
    )

    rev2 = await validator.analyze(instruction=revalidate_instruction, context="")
    try:
        verdict2 = json.loads(rev2.content)
    except (json.JSONDecodeError, AttributeError):
        verdict2 = {"verdict": "fail"}

    if verdict2.get("verdict") == "pass":
        for r in retry_recs:
            r["verified"] = True
        return {"recommendations": retry_recs, "signals": signals, "verdict": verdict2}

    # Final fallback — include unverified
    logger.warning("Advisor chain: validator failed twice, returning unverified")
    for r in retry_recs:
        r["verified"] = False
    return {"recommendations": retry_recs, "signals": signals, "verdict": verdict2}
```

- [ ] **Step 5: Integrate advisor chain into run_chain()**

In `run_chain()`, add advisor chain call after the main agent loop (before synthesis). Find the line `# Synthesize final answer` and add before it:

```python
        # --- Advisor chain: detect signals and generate recommendations ---
        # Runs after main agent loop, before synthesis
        advisor_result = {}
        if chain_history:
            # Extract structured_data from last reporter/marketer result
            last_result = chain_history[-1]
            # Try to find structured_data in any step's result
            structured_data = {}
            for step_entry in chain_history:
                if step_entry.agent in ("reporter", "marketer", "funnel"):
                    # Try to parse structured data from agent result
                    try:
                        parsed = json.loads(step_entry.result)
                        if isinstance(parsed, dict):
                            structured_data.update(parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass

            if structured_data:
                report_type = "daily"
                if "weekly" in task_type:
                    report_type = "weekly"
                elif "monthly" in task_type:
                    report_type = "monthly"

                try:
                    advisor_result = await self._run_advisor_chain(
                        structured_data=structured_data,
                        report_type=report_type,
                        chain_history=chain_history,
                    )
                    # Add recommendations to chain context for synthesis
                    if advisor_result.get("recommendations"):
                        chain_history.append(AgentStep(
                            agent="advisor_chain",
                            instruction="Signal Detection → Advisor → Validator",
                            result=json.dumps(advisor_result, ensure_ascii=False, default=str),
                            cost_usd=0.0,
                            duration_ms=0,
                            iterations=0,
                        ))
                except Exception as e:
                    logger.warning(f"Advisor chain failed: {e}")
```

- [ ] **Step 6: Update DECIDE_NEXT_STEP_PROMPT**

In `agents/oleg/orchestrator/prompts.py`, update `DECIDE_NEXT_STEP_PROMPT` to mention advisor/validator:

```python
# Add after christina description:
- **advisor**: Формирует actionable рекомендации на основе сигналов в данных. НЕ вызывается напрямую — запускается автоматически после сбора данных reporter/marketer.
- **validator**: Проверяет рекомендации advisor детерминированными скриптами. НЕ вызывается напрямую — часть advisor chain.

# Update the agent list in the JSON format:
    "next_agent": "reporter" | "marketer" | "funnel" | "researcher" | "quality" | "christina",
# NOTE: advisor/validator not in this list — they run automatically via _run_advisor_chain
```

- [ ] **Step 7: Write test for advisor chain integration**

```python
# tests/agents/oleg/orchestrator/test_advisor_chain.py
"""Test advisor chain integration in orchestrator."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator


@pytest.fixture
def mock_orchestrator():
    llm = MagicMock()
    advisor = MagicMock()
    advisor.analyze = AsyncMock()
    validator = MagicMock()
    validator.analyze = AsyncMock()
    agents = {
        "reporter": MagicMock(),
        "advisor": advisor,
        "validator": validator,
    }
    orch = OlegOrchestrator(llm, "test-model", agents)
    return orch, advisor, validator


@pytest.mark.asyncio
async def test_advisor_chain_no_signals(mock_orchestrator):
    orch, advisor, validator = mock_orchestrator
    with patch("agents.oleg.orchestrator.orchestrator.detect_signals", return_value=[]):
        result = await orch._run_advisor_chain({}, "daily", [])
    assert result["recommendations"] == []
    advisor.analyze.assert_not_called()


@pytest.mark.asyncio
async def test_advisor_chain_pass(mock_orchestrator):
    orch, advisor, validator = mock_orchestrator
    from shared.signals.detector import Signal

    mock_signals = [Signal(
        id="test_1", type="margin_lags_orders", category="margin",
        severity="warning", impact_on="margin",
        data={"gap_pct": 7.8}, hint="Test", source="plan_vs_fact",
    )]

    advisor.analyze.return_value = MagicMock(
        content=json.dumps({"recommendations": [{"signal_id": "test_1", "action": "test"}]}),
        total_cost=0.01,
    )
    validator.analyze.return_value = MagicMock(
        content=json.dumps({"verdict": "pass", "checks": []}),
        total_cost=0.01,
    )

    with patch("agents.oleg.orchestrator.orchestrator.detect_signals", return_value=mock_signals):
        result = await orch._run_advisor_chain(
            {"_source": "plan_vs_fact"}, "daily", [],
        )

    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["verified"] is True
```

- [ ] **Step 8: Run tests**

Run: `python -m pytest tests/agents/oleg/orchestrator/test_advisor_chain.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add agents/oleg/executor/react_loop.py agents/oleg/app.py \
      agents/oleg/orchestrator/orchestrator.py agents/oleg/orchestrator/prompts.py \
      tests/agents/oleg/orchestrator/test_advisor_chain.py
git commit -m "feat(orchestrator): integrate advisor chain — AgentResult extension, signal detection, retry logic"
```

---

### Task 10: Update Reporter/Marketer prompts for recommendations section

**Files:**
- Modify: `agents/oleg/agents/reporter/prompts.py`
- Modify: `agents/oleg/agents/marketer/prompts.py`

- [ ] **Step 1: Read current prompts**

Read both files to find where to add the recommendations section template.

- [ ] **Step 2: Add recommendations section to Reporter**

After the "План-факт" section in REPORTER_PREAMBLE, add:

```python
# Add to the СТРУКТУРА detailed_report section:
"""
### N) Рекомендации Advisor
## ▶ Рекомендации Advisor
Если в контексте есть validated_recommendations — вставь их как секцию отчёта.
Группируй по severity:
### 🔴 Критичные (делай сегодня)
### 🟡 Внимание (на этой неделе / в этом месяце)
### 🟢 Позитивные сигналы
Каждая рекомендация: **Сигнал** -> Действие. Эффект: X. Confidence: Y.
Если validated_recommendations отсутствуют — пропусти секцию.
"""
```

- [ ] **Step 3: Add same section to Marketer**

Same pattern as Reporter.

- [ ] **Step 4: Commit**

```bash
git add agents/oleg/agents/reporter/prompts.py agents/oleg/agents/marketer/prompts.py
git commit -m "feat(prompts): add Advisor recommendations section to Reporter and Marketer"
```

---

## Phase 5: Integration Test

### Task 11: End-to-end integration test

**Files:**
- Create: `tests/integration/test_advisor_pipeline.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_advisor_pipeline.py
"""End-to-end test: data -> signals -> advisor -> validator."""
import pytest
from shared.signals import detect_signals

# Test the full signal detection pipeline
def test_plan_fact_to_signals_to_recommendations_shape():
    """Signals from real-looking plan-fact data have correct structure."""
    data = {
        "_source": "plan_vs_fact",
        "brand_total": {
            "metrics": {
                "orders_count": {"completion_mtd_pct": 113.9, "forecast_vs_plan_pct": 10.2},
                "margin": {"completion_mtd_pct": 106.1, "forecast_vs_plan_pct": 4.8},
                "sales_count": {"completion_mtd_pct": 101.3, "forecast_vs_plan_pct": 1.5},
                "revenue": {"completion_mtd_pct": 120.4, "forecast_vs_plan_pct": 15.0},
                "adv_internal": {"completion_mtd_pct": 108.9, "forecast_vs_plan_pct": 12.0},
                "adv_external": {"completion_mtd_pct": 126.3, "forecast_vs_plan_pct": 30.0},
            },
        },
        "days_elapsed": 19,
        "days_in_month": 31,
    }

    signals = detect_signals(data)

    # Should detect multiple signals
    assert len(signals) >= 2

    # All signals should have required fields
    for s in signals:
        assert s.id
        assert s.type
        assert s.category in ("margin", "turnover", "funnel", "adv", "price", "model")
        assert s.severity in ("info", "warning", "critical")
        assert s.impact_on in ("margin", "turnover", "both")
        assert isinstance(s.data, dict)
        assert s.hint
        assert s.source == "plan_vs_fact"

def test_direction_map_covers_all_signal_types():
    """Every signal type in patterns has a direction map entry."""
    from shared.signals.patterns import BASE_PATTERNS
    from shared.signals.direction_map import DIRECTION_MAP

    pattern_types = {p["pattern_name"] for p in BASE_PATTERNS}
    mapped_types = set(DIRECTION_MAP.keys())

    unmapped = pattern_types - mapped_types
    assert not unmapped, f"Patterns without direction map: {unmapped}"
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/integration/test_advisor_pipeline.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_advisor_pipeline.py
git commit -m "test: add end-to-end integration test for advisor pipeline"
```

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| **1: Signal Detector** | Tasks 1-5 | Python module detecting 25 patterns + KB patterns table + direction map |
| **2: Advisor Agent** | Task 6 | LLM agent producing structured recommendations + smoke tests |
| **3: Validator Agent** | Tasks 7-8 | LLM agent with 4 deterministic validation scripts + smoke tests |
| **4: Orchestrator** | Tasks 9-10 | AgentResult extension, advisor chain with retry logic, prompt updates |
| **5: Integration** | Task 11 | E2E test |

**Not in this plan (future phases from spec):**
- Phase 4 (spec): Self-learning — manual/semi-auto/auto pattern addition
- Phase 5 (spec): Expansion — monthly knowledge report in Notion, threshold tuning
- `recommendation_log` table (observability) — deferred to Phase 5
- `shared/signals/kb_patterns.py` (spec listed, but loading done by orchestrator via `detect_signals(kb_patterns=...)`)
- Full 25-pattern detection — this plan implements ~6 patterns for `plan_vs_fact` source; other sources (funnel, ABC, price) need additional `_detect_*` functions

**Notes:**
- `adv_overspend` from `plan_vs_fact` source checks plan completion overshoot (>115%), not absolute ДРР %. Absolute ДРР threshold (>12% WB, >18% Ozon) requires `brand_finance` data source — future detector.
- Migration `003_create_kb_patterns.py` generates SQL for manual execution via Supabase SQL editor (consistent with project's existing migration approach).
