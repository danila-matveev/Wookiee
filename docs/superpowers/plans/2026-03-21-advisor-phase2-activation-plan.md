# Advisor Phase 2 — Activation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Активировать advisor chain в проде — извлекать structured_data из tool call history Reporter/Marketer и реализовать все 20 оставшихся сигнальных детекторов.

**Architecture:** Оркестратор сохраняет `AgentResult` в `_agent_results` dict после каждого агента. После основного цикла — проходит по tool call history, парсит JSON-результаты через `SOURCE_MAP`, и вызывает `detect_signals()` для каждого источника. Существующий advisor chain (Advisor → Validator → retry) работает без изменений.

**Tech Stack:** Python 3.9, asyncio, existing BaseAgent/ReactLoop, shared/signals/

**Spec:** `docs/superpowers/specs/2026-03-21-advisor-phase2-activation-design.md`

---

## File Structure

```
# MODIFY
agents/oleg/orchestrator/orchestrator.py   # _extract_structured_data(), _run_signal_detection(), run_chain()
shared/signals/detector.py                 # 4 новых детектора + обновить dispatcher + kb_pattern evaluator

# CREATE (tests)
tests/agents/oleg/orchestrator/test_extract_structured_data.py
tests/shared/signals/test_finance_signals.py
tests/shared/signals/test_margin_lever_signals.py
tests/shared/signals/test_advertising_signals.py
tests/shared/signals/test_model_signals.py
tests/shared/signals/test_kb_pattern_signals.py
```

---

## Phase 1: Orchestrator — structured_data extraction

### Task 1: Extract structured_data from tool call history

**Files:**
- Create: `tests/agents/oleg/orchestrator/test_extract_structured_data.py`
- Modify: `agents/oleg/orchestrator/orchestrator.py:38-40` (add `_agent_results` dict)
- Modify: `agents/oleg/orchestrator/orchestrator.py:120-136` (save AgentResult, replace extraction)
- Modify: `agents/oleg/orchestrator/orchestrator.py:468-477` (update `_run_signal_detection`)

**Context for implementer:**
- `AgentResult` is defined in `agents/oleg/executor/react_loop.py:35-49`. It has `.steps: List[AgentStep]` where each step has `.tool_name: str` and `.tool_result: str` (JSON string).
- The chain-level `AgentStep` is in `agents/oleg/orchestrator/chain.py:12-19` — different class, only has `.agent`, `.instruction`, `.result` (text).
- The current broken code at `orchestrator.py:138-148` tries `json.loads(step_entry.result)` on Markdown text — always fails silently.
- `_run_signal_detection()` at line 470 currently calls `detect_signals(data=structured_data)` once with the whole dict. It needs to iterate over sources.

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/oleg/orchestrator/test_extract_structured_data.py
"""Tests for structured_data extraction from tool call history."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock
from agents.oleg.executor.react_loop import AgentStep as ToolStep, AgentResult
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator


def _make_agent_result(*tool_calls: tuple) -> AgentResult:
    """Create AgentResult with given tool calls: (tool_name, result_dict)."""
    steps = []
    for name, result in tool_calls:
        steps.append(ToolStep(
            tool_name=name,
            tool_args={},
            tool_result=json.dumps(result, ensure_ascii=False),
            iteration=1,
        ))
    return AgentResult(content="markdown report", steps=steps)


def _make_orchestrator() -> OlegOrchestrator:
    """Create orchestrator with minimal config for testing."""
    return OlegOrchestrator(
        agents={},
        llm_client=MagicMock(),
        config={},
    )


def test_extract_plan_vs_fact():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_plan_vs_fact", {"brand_total": {"metrics": {}}, "days_elapsed": 15}),
    )
    data = orch._extract_structured_data(result)
    assert "plan_vs_fact" in data
    assert data["plan_vs_fact"]["_source"] == "plan_vs_fact"
    assert data["plan_vs_fact"]["days_elapsed"] == 15


def test_extract_multiple_sources():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_brand_finance", {"brand": {"current": {"margin": 100}}}),
        ("get_plan_vs_fact", {"brand_total": {}, "days_elapsed": 10}),
        ("get_margin_levers", {"levers": {}, "waterfall": {}}),
    )
    data = orch._extract_structured_data(result)
    assert len(data) == 3
    assert "brand_finance" in data
    assert "plan_vs_fact" in data
    assert "margin_levers" in data


def test_extract_duplicate_tool_becomes_list():
    """When same tool called twice (WB + Ozon), results become a list."""
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("get_margin_levers", {"channel": "WB", "levers": {}}),
        ("get_margin_levers", {"channel": "OZON", "levers": {}}),
    )
    data = orch._extract_structured_data(result)
    assert isinstance(data["margin_levers"], list)
    assert len(data["margin_levers"]) == 2
    assert data["margin_levers"][0]["channel"] == "WB"


def test_extract_ignores_unknown_tools():
    orch = _make_orchestrator()
    result = _make_agent_result(
        ("validate_data_quality", {"status": "ok"}),
        ("search_knowledge_base", {"results": []}),
    )
    data = orch._extract_structured_data(result)
    assert data == {}


def test_extract_handles_malformed_json():
    orch = _make_orchestrator()
    steps = [ToolStep(
        tool_name="get_brand_finance",
        tool_args={},
        tool_result="not json at all",
        iteration=1,
    )]
    result = AgentResult(content="report", steps=steps)
    data = orch._extract_structured_data(result)
    assert data == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/agents/oleg/orchestrator/test_extract_structured_data.py -v`
Expected: FAIL — `_extract_structured_data` method does not exist

- [ ] **Step 3: Implement `_extract_structured_data` and update `run_chain`**

In `agents/oleg/orchestrator/orchestrator.py`:

1. Add `SOURCE_MAP` constant after imports (around line 35):
```python
# Tool name -> signal source tag
SOURCE_MAP = {
    "get_plan_vs_fact": "plan_vs_fact",
    "get_brand_finance": "brand_finance",
    "get_margin_levers": "margin_levers",
    "get_advertising_stats": "advertising",
    "get_model_breakdown": "model_breakdown",
}
```

2. In `__init__` (around line 40-60), add:
```python
self._agent_results: dict[str, AgentResult] = {}  # runtime only, not serialized
```

3. After `result = await agent.analyze(...)` at line 124, before `chain_history.append(...)` at line 128, add:
```python
# Save full AgentResult for structured_data extraction
self._agent_results[agent_name] = result
```

4. Add new method after `_build_chain_context` (around line 467):
```python
def _extract_structured_data(self, result) -> dict:
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

5. Replace the broken extraction at lines 138-148 with:
```python
# --- Advisor chain: detect signals and generate recommendations ---
if chain_history:
    structured_data = {}
    for step_entry in chain_history:
        if step_entry.agent in ("reporter", "marketer", "funnel"):
            agent_result = self._agent_results.get(step_entry.agent)
            if agent_result:
                extracted = self._extract_structured_data(agent_result)
                structured_data.update(extracted)
```

6. Update `_run_signal_detection` at line 470 to iterate over sources:
```python
async def _run_signal_detection(self, structured_data: dict) -> list:
    """Run Signal Detector on structured data. Pure Python, no LLM."""
    try:
        all_signals = []
        for source_tag, source_data in structured_data.items():
            if isinstance(source_data, list):
                for item in source_data:
                    all_signals.extend(detect_signals(data=item))
            else:
                all_signals.extend(detect_signals(data=source_data))
        return [vars(s) for s in all_signals]
    except Exception as e:
        logger.warning(f"Signal detection failed: {e}")
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/agents/oleg/orchestrator/test_extract_structured_data.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Run existing advisor chain tests to check no regression**

Run: `python3 -m pytest tests/agents/oleg/orchestrator/ -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add agents/oleg/orchestrator/orchestrator.py tests/agents/oleg/orchestrator/test_extract_structured_data.py
git commit -m "feat(orchestrator): extract structured_data from tool call history

Replace broken json.loads on Markdown text with extraction from
AgentResult.steps tool call results. Iterate detect_signals per source."
```

---

## Phase 2: Signal Detectors

### Task 2: Finance signals detector (`brand_finance`)

**Files:**
- Create: `tests/shared/signals/test_finance_signals.py`
- Modify: `shared/signals/detector.py:144-145` (replace stub)

**Context for implementer:**
- `get_brand_finance` returns: `data["brand"]["current"]` with fields: `margin_pct`, `drr_pct`, `logistics`, `revenue_before_spp` (or `revenue_after_spp`), `cogs_per_unit`, `orders_rub`, `revenue_after_spp`. `data["brand"]["previous"]` has same fields. `data["brand"]["changes"]` has `{metric}_change_pct`.
- Signal dataclass: `Signal(id, type, category, severity, impact_on, data, hint, source)` from `shared/signals/detector.py`.
- All existing detectors follow the pattern in `_detect_plan_fact_signals` (lines 49-141).
- Use `data.get("_source")` — it will be `"brand_finance"` when called from orchestrator.
- Graceful: if any key is missing, return `[]`.

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/signals/test_finance_signals.py
"""Tests for _detect_finance_signals (brand_finance source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals, Signal


def _make_finance_data(**overrides) -> dict:
    """Build brand_finance data with sensible defaults."""
    base = {
        "_source": "brand_finance",
        "brand": {
            "current": {
                "margin_pct": 22.0,
                "revenue_before_spp": 1_000_000,
                "revenue_after_spp": 850_000,
                "logistics": 60_000,
                "cogs_per_unit": 300,
                "orders_rub": 1_200_000,
                "sales_count": 500,
            },
            "previous": {
                "margin_pct": 24.0,
                "revenue_before_spp": 900_000,
                "revenue_after_spp": 770_000,
                "logistics": 50_000,
                "cogs_per_unit": 280,
                "orders_rub": 1_000_000,
                "sales_count": 450,
            },
            "changes": {
                "cogs_per_unit_change_pct": 7.14,
                "revenue_before_spp_change_pct": 11.1,
            },
        },
    }
    # Apply overrides to current
    for k, v in overrides.items():
        if k.startswith("prev_"):
            base["brand"]["previous"][k[5:]] = v
        elif k.startswith("change_"):
            base["brand"]["changes"][k[7:]] = v
        else:
            base["brand"]["current"][k] = v
    return base


def test_margin_pct_drop_detected():
    """margin_pct drops > 2 pp while revenue grows."""
    data = _make_finance_data(margin_pct=20.0, prev_margin_pct=24.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "margin_pct_drop" in types


def test_cogs_anomaly_detected():
    """cogs_per_unit change > 5%."""
    data = _make_finance_data(change_cogs_per_unit_change_pct=8.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cogs_anomaly" in types


def test_logistics_overweight_detected():
    """logistics / revenue > 8%."""
    data = _make_finance_data(logistics=90_000, revenue_after_spp=850_000)
    # 90_000 / 850_000 = 10.6%
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "logistics_overweight" in types


def test_price_signal_detected():
    """avg check orders vs avg check sales differ > 5%."""
    data = _make_finance_data(
        orders_rub=1_200_000, sales_count=500,
        prev_orders_rub=1_000_000, prev_sales_count=450,
    )
    # orders avg = 1_200_000 / orders_count (need orders_count)
    # Simpler: add orders_count fields
    data["brand"]["current"]["orders_count"] = 400
    data["brand"]["current"]["sales_count"] = 500
    # avg_order = 1_200_000/400 = 3000, avg_sale = revenue/sales = 850_000/500 = 1700
    # diff = |3000-1700|/1700 = 76% >> 5%
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "price_signal" in types


def test_no_signals_on_healthy_finance():
    """No signals when all metrics are within normal range."""
    data = _make_finance_data(
        margin_pct=24.5, prev_margin_pct=24.0,
        logistics=50_000, revenue_after_spp=850_000,
    )
    data["brand"]["changes"]["cogs_per_unit_change_pct"] = 2.0
    signals = detect_signals(data)
    # May have price_signal but no critical/warning signals
    critical_warning = [s for s in signals if s.severity in ("critical", "warning")]
    assert len(critical_warning) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/shared/signals/test_finance_signals.py -v`
Expected: FAIL — stub returns `[]`

- [ ] **Step 3: Implement `_detect_finance_signals`**

Replace the stub at `shared/signals/detector.py:144-145`:

```python
def _detect_finance_signals(data: dict) -> list[Signal]:
    signals = []
    brand = data.get("brand", {})
    current = brand.get("current", {})
    previous = brand.get("previous", {})
    changes = brand.get("changes", {})
    if not current:
        return signals

    channel = data.get("channel", "brand")

    # 1. margin_pct_drop: margin % drops > 2 pp while revenue grows
    margin_cur = current.get("margin_pct", 0) or 0
    margin_prev = previous.get("margin_pct", 0) or 0
    rev_change = changes.get("revenue_before_spp_change_pct", 0) or 0
    margin_drop = margin_prev - margin_cur
    if margin_drop > 2 and rev_change > 0:
        signals.append(Signal(
            id=f"margin_pct_drop_{channel}",
            type="margin_pct_drop",
            category="margin",
            severity="critical" if margin_drop > 5 else "warning",
            impact_on="margin",
            data={"margin_pct_current": margin_cur, "margin_pct_previous": margin_prev, "drop_pp": round(margin_drop, 1)},
            hint=f"Маржинальность упала на {round(margin_drop, 1)} п.п. ({margin_prev}% → {margin_cur}%) при росте выручки",
            source="brand_finance",
        ))

    # 2. cogs_anomaly: cogs_per_unit change > 5%
    cogs_change = abs(changes.get("cogs_per_unit_change_pct", 0) or 0)
    if cogs_change > 5:
        signals.append(Signal(
            id=f"cogs_anomaly_{channel}",
            type="cogs_anomaly",
            category="margin",
            severity="critical",
            impact_on="margin",
            data={"cogs_change_pct": round(cogs_change, 1), "cogs_current": current.get("cogs_per_unit", 0)},
            hint=f"Себестоимость на единицу изменилась на {round(cogs_change, 1)}% — проверь поставщика",
            source="brand_finance",
        ))

    # 3. logistics_overweight: logistics / revenue > 8%
    logistics = current.get("logistics", 0) or 0
    revenue = current.get("revenue_after_spp", 0) or current.get("revenue_before_spp", 0) or 0
    if revenue > 0:
        logistics_pct = logistics / revenue * 100
        if logistics_pct > 8:
            signals.append(Signal(
                id=f"logistics_overweight_{channel}",
                type="logistics_overweight",
                category="margin",
                severity="warning",
                impact_on="margin",
                data={"logistics_pct": round(logistics_pct, 1), "logistics": logistics, "revenue": revenue},
                hint=f"Логистика {round(logistics_pct, 1)}% от выручки (норма < 8%)",
                source="brand_finance",
            ))

    # 4. price_signal: avg check orders vs avg check sales differ > 5%
    orders_rub = current.get("orders_rub", 0) or 0
    orders_count = current.get("orders_count", 0) or 0
    sales_count = current.get("sales_count", 0) or 0
    if orders_count > 0 and sales_count > 0 and revenue > 0:
        avg_order = orders_rub / orders_count
        avg_sale = revenue / sales_count
        if avg_sale > 0:
            diff_pct = abs(avg_order - avg_sale) / avg_sale * 100
            if diff_pct > 5:
                direction = "выше" if avg_order > avg_sale else "ниже"
                signals.append(Signal(
                    id=f"price_signal_{channel}",
                    type="price_signal",
                    category="price",
                    severity="info",
                    impact_on="margin",
                    data={"avg_order": round(avg_order), "avg_sale": round(avg_sale), "diff_pct": round(diff_pct, 1)},
                    hint=f"Ср. чек заказов ({round(avg_order)}₽) {direction} ср. чека продаж ({round(avg_sale)}₽) на {round(diff_pct, 1)}%",
                    source="brand_finance",
                ))

    return signals
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/shared/signals/test_finance_signals.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_finance_signals.py
git commit -m "feat(signals): implement finance signal detector (4 patterns)

Detects: margin_pct_drop, cogs_anomaly, logistics_overweight, price_signal
from get_brand_finance tool results."
```

---

### Task 3: Margin lever signals detector (`margin_levers`)

**Files:**
- Create: `tests/shared/signals/test_margin_lever_signals.py`
- Modify: `shared/signals/detector.py:148-149` (replace stub)

**Context for implementer:**
- `get_margin_levers` returns: `data["levers"]` with keys like `spp_pct: {current: float, previous: float}`, `drr_pct: {current, previous}`. Also `data["waterfall"]` with `advertising_change`, `revenue_change`, etc. `data["channel"]` = "WB" or "OZON".
- DRR thresholds: WB > 12%, Ozon > 18%.
- `adv_underspend`: DRR < 3% AND revenue did not grow (revenue_change <= 0 in waterfall).

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/signals/test_margin_lever_signals.py
"""Tests for _detect_margin_lever_signals (margin_levers source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_lever_data(channel="WB", **lever_overrides) -> dict:
    base = {
        "_source": "margin_levers",
        "channel": channel,
        "levers": {
            "spp_pct": {"current": 15.0, "previous": 15.0},
            "drr_pct": {"current": 8.0, "previous": 7.0},
            "logistics_per_unit": {"current": 120, "previous": 115},
            "cogs_per_unit": {"current": 300, "previous": 290},
            "price_before_spp_per_unit": {"current": 2000, "previous": 1950},
        },
        "waterfall": {
            "revenue_change": 50000,
            "advertising_change": -10000,
        },
    }
    for k, v in lever_overrides.items():
        keys = k.split("__")
        if len(keys) == 2:
            base["levers"][keys[0]][keys[1]] = v
        else:
            base["levers"][k] = v
    return base


def test_spp_shift_up():
    data = _make_lever_data(spp_pct__current=18.0, spp_pct__previous=15.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "spp_shift_up" in types


def test_spp_shift_down():
    data = _make_lever_data(spp_pct__current=12.0, spp_pct__previous=15.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "spp_shift_down" in types


def test_adv_overspend_wb():
    data = _make_lever_data(channel="WB", drr_pct__current=14.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "adv_overspend" in types


def test_adv_overspend_ozon_higher_threshold():
    data = _make_lever_data(channel="OZON", drr_pct__current=15.0)
    signals = detect_signals(data)
    # 15% < 18% threshold for Ozon — should NOT fire
    types = {s.type for s in signals}
    assert "adv_overspend" not in types


def test_adv_underspend():
    data = _make_lever_data(drr_pct__current=2.0)
    data["waterfall"]["revenue_change"] = -5000  # revenue declining
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "adv_underspend" in types


def test_no_signals_healthy_levers():
    data = _make_lever_data()
    signals = detect_signals(data)
    assert len(signals) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/shared/signals/test_margin_lever_signals.py -v`
Expected: FAIL — stub returns `[]`

- [ ] **Step 3: Implement `_detect_margin_lever_signals`**

Replace the stub at `shared/signals/detector.py:148-149`:

```python
def _detect_margin_lever_signals(data: dict) -> list[Signal]:
    signals = []
    levers = data.get("levers", {})
    waterfall = data.get("waterfall", {})
    if not levers:
        return signals

    channel = data.get("channel", "unknown")

    # 1. spp_shift_up: SPP grew > 2 pp
    spp = levers.get("spp_pct", {})
    spp_cur = spp.get("current", 0) or 0
    spp_prev = spp.get("previous", 0) or 0
    spp_delta = spp_cur - spp_prev
    if spp_delta > 2:
        signals.append(Signal(
            id=f"spp_shift_up_{channel}",
            type="spp_shift_up",
            category="price",
            severity="info",
            impact_on="margin",
            data={"spp_current": spp_cur, "spp_previous": spp_prev, "delta_pp": round(spp_delta, 1)},
            hint=f"СПП выросла на {round(spp_delta, 1)} п.п. ({spp_prev}% → {spp_cur}%) — можно поднять базовую цену",
            source="margin_levers",
        ))

    # 2. spp_shift_down: SPP dropped > 2 pp
    if spp_delta < -2:
        signals.append(Signal(
            id=f"spp_shift_down_{channel}",
            type="spp_shift_down",
            category="price",
            severity="warning",
            impact_on="margin",
            data={"spp_current": spp_cur, "spp_previous": spp_prev, "delta_pp": round(spp_delta, 1)},
            hint=f"СПП упала на {round(abs(spp_delta), 1)} п.п. ({spp_prev}% → {spp_cur}%) — клиентская цена выросла",
            source="margin_levers",
        ))

    # 3. adv_overspend: DRR above threshold (WB > 12%, Ozon > 18%)
    drr = levers.get("drr_pct", {})
    drr_cur = drr.get("current", 0) or 0
    threshold = 18 if channel.upper() in ("OZON", "ОЗОН") else 12
    if drr_cur > threshold:
        signals.append(Signal(
            id=f"adv_overspend_{channel}",
            type="adv_overspend",
            category="adv",
            severity="critical" if drr_cur > threshold * 1.5 else "warning",
            impact_on="margin",
            data={"drr_pct": drr_cur, "threshold": threshold, "channel": channel},
            hint=f"ДРР {channel} = {round(drr_cur, 1)}% при норме < {threshold}%",
            source="margin_levers",
        ))

    # 4. adv_underspend: DRR < 3% and revenue not growing
    revenue_change = waterfall.get("revenue_change", 0) or 0
    if drr_cur < 3 and revenue_change <= 0:
        signals.append(Signal(
            id=f"adv_underspend_{channel}",
            type="adv_underspend",
            category="adv",
            severity="info",
            impact_on="turnover",
            data={"drr_pct": drr_cur, "revenue_change": revenue_change},
            hint=f"ДРР {channel} всего {round(drr_cur, 1)}%, выручка не растёт — мало трафика",
            source="margin_levers",
        ))

    return signals
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/shared/signals/test_margin_lever_signals.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_margin_lever_signals.py
git commit -m "feat(signals): implement margin lever signal detector (4 patterns)

Detects: spp_shift_up, spp_shift_down, adv_overspend, adv_underspend
from get_margin_levers tool results."
```

---

### Task 4: Advertising signals detector (`advertising`)

**Files:**
- Create: `tests/shared/signals/test_advertising_signals.py`
- Modify: `shared/signals/detector.py` (add new function + update dispatcher)

**Context for implementer:**
- `get_advertising_stats` returns: `data["advertising"]["current"]` with `ctr_pct`, `cr_full_pct`, `ad_orders`, etc. `data["funnel"]["current"]` with `cart_to_order_pct` (WB only), `order_to_buyout_pct`. `data["channel"]` = "WB" or "OZON".
- OZON does NOT have `funnel` data — must graceful skip funnel-dependent patterns.
- This is a NEW function, not replacing a stub. Also need to add `"advertising"` source to the dispatcher in `detect_signals()`.

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/signals/test_advertising_signals.py
"""Tests for _detect_advertising_signals (advertising source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_ad_data(channel="WB", **overrides) -> dict:
    base = {
        "_source": "advertising",
        "channel": channel,
        "advertising": {
            "current": {
                "ctr_pct": 3.0,
                "cr_full_pct": 2.5,
                "ad_orders": 100,
                "ad_spend": 50000,
            },
            "previous": {
                "ctr_pct": 3.2,
                "cr_full_pct": 2.3,
                "ad_orders": 90,
                "ad_spend": 45000,
            },
        },
        "funnel": {
            "current": {
                "cart_to_order_pct": 30.0,
                "order_to_buyout_pct": 55.0,
            },
            "previous": {
                "cart_to_order_pct": 32.0,
                "order_to_buyout_pct": 58.0,
            },
        },
    }
    for k, v in overrides.items():
        parts = k.split("__")
        if len(parts) == 3:
            base[parts[0]][parts[1]][parts[2]] = v
        elif len(parts) == 2:
            base[parts[0]][parts[1]] = v
    return base


def test_ctr_drop_wb():
    data = _make_ad_data(channel="WB", advertising__current__ctr_pct=1.5)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "ctr_drop" in types


def test_ctr_ok_wb():
    data = _make_ad_data(channel="WB", advertising__current__ctr_pct=2.5)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "ctr_drop" not in types


def test_cart_to_order_drop():
    data = _make_ad_data(
        funnel__current__cart_to_order_pct=24.0,
        funnel__previous__cart_to_order_pct=32.0,
    )
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cart_to_order_drop" in types


def test_cro_improvement():
    data = _make_ad_data(
        advertising__current__cr_full_pct=4.0,
        advertising__previous__cr_full_pct=2.5,
    )
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cro_improvement" in types


def test_buyout_drop():
    data = _make_ad_data(funnel__current__order_to_buyout_pct=40.0)
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "buyout_drop" in types


def test_no_funnel_signals_for_ozon():
    """OZON has no funnel data — funnel-dependent signals should not fire."""
    data = _make_ad_data(channel="OZON")
    del data["funnel"]
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "cart_to_order_drop" not in types
    assert "buyout_drop" not in types
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/shared/signals/test_advertising_signals.py -v`
Expected: FAIL — function not found / source not dispatched

- [ ] **Step 3: Implement `_detect_advertising_signals` and update dispatcher**

Add to `shared/signals/detector.py`:

1. In `detect_signals()`, add after `margin_levers` dispatch (around line 41):
```python
    if source == "advertising":
        signals.extend(_detect_advertising_signals(data))
    if source == "model_breakdown":
        signals.extend(_detect_model_signals(data))
```

2. Add new function (before `_detect_kb_pattern_signals`):

```python
def _detect_advertising_signals(data: dict) -> list[Signal]:
    signals = []
    ad = data.get("advertising", {})
    ad_cur = ad.get("current", {})
    ad_prev = ad.get("previous", {})
    funnel = data.get("funnel", {})
    funnel_cur = funnel.get("current", {})
    funnel_prev = funnel.get("previous", {})
    channel = data.get("channel", "unknown")
    if not ad_cur:
        return signals

    # 1. ctr_drop: CTR below threshold
    ctr = ad_cur.get("ctr_pct", 0) or 0
    threshold = 1.5 if channel.upper() in ("OZON", "ОЗОН") else 2.0
    if ctr > 0 and ctr < threshold:
        signals.append(Signal(
            id=f"ctr_drop_{channel}",
            type="ctr_drop",
            category="funnel",
            severity="warning",
            impact_on="turnover",
            data={"ctr_pct": ctr, "threshold": threshold, "channel": channel},
            hint=f"CTR {channel} = {ctr}% ниже нормы ({threshold}%)",
            source="advertising",
        ))

    # 2. cart_to_order_drop: cart-to-order fell > 5 pp (WB only, needs funnel)
    if funnel_cur and funnel_prev:
        c2o_cur = funnel_cur.get("cart_to_order_pct", 0) or 0
        c2o_prev = funnel_prev.get("cart_to_order_pct", 0) or 0
        c2o_drop = c2o_prev - c2o_cur
        if c2o_drop > 5:
            signals.append(Signal(
                id=f"cart_to_order_drop_{channel}",
                type="cart_to_order_drop",
                category="funnel",
                severity="warning",
                impact_on="turnover",
                data={"c2o_current": c2o_cur, "c2o_previous": c2o_prev, "drop_pp": round(c2o_drop, 1)},
                hint=f"Конверсия корзина→заказ упала на {round(c2o_drop, 1)} п.п. ({c2o_prev}% → {c2o_cur}%)",
                source="advertising",
            ))

    # 3. cro_improvement: full conversion grew > 1 pp
    cr_cur = ad_cur.get("cr_full_pct", 0) or 0
    cr_prev = ad_prev.get("cr_full_pct", 0) or 0
    cr_growth = cr_cur - cr_prev
    if cr_growth > 1:
        signals.append(Signal(
            id=f"cro_improvement_{channel}",
            type="cro_improvement",
            category="funnel",
            severity="info",
            impact_on="turnover",
            data={"cr_current": cr_cur, "cr_previous": cr_prev, "growth_pp": round(cr_growth, 1)},
            hint=f"Сквозная конверсия выросла на {round(cr_growth, 1)} п.п. ({cr_prev}% → {cr_cur}%)",
            source="advertising",
        ))

    # 4. buyout_drop: buyout rate < 45% WB (needs funnel)
    if funnel_cur:
        buyout = funnel_cur.get("order_to_buyout_pct", 0) or 0
        if buyout > 0 and buyout < 45:
            signals.append(Signal(
                id=f"buyout_drop_{channel}",
                type="buyout_drop",
                category="funnel",
                severity="warning",
                impact_on="both",
                data={"buyout_pct": buyout, "channel": channel},
                hint=f"Выкуп {channel} = {buyout}% (норма > 45%)",
                source="advertising",
            ))

    return signals


def _detect_model_signals(data: dict) -> list[Signal]:
    return []  # Implemented in Task 5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/shared/signals/test_advertising_signals.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_advertising_signals.py
git commit -m "feat(signals): implement advertising signal detector (4 patterns)

Detects: ctr_drop, cart_to_order_drop, cro_improvement, buyout_drop
from get_advertising_stats tool results. OZON graceful skip for funnel."
```

---

### Task 5: Model signals detector (`model_breakdown`)

**Files:**
- Create: `tests/shared/signals/test_model_signals.py`
- Modify: `shared/signals/detector.py` (replace `_detect_model_signals` stub)

**Context for implementer:**
- `get_model_breakdown` returns: `data["models"]` — list of dicts with: `model`, `margin_pct`, `drr_pct`, `turnover_days`, `roi_annual`, `margin`, `adv_total`, `orders_count`, `sales_count`, `revenue_before_spp`.
- Median calculation needed for `turnover_days` (for `low_roi_article` and `high_roi_opportunity`).
- `status_mismatch` requires a "status" field on models — check if `get_product_statuses()` data is available. If not, skip pattern (graceful). The model dict from `get_model_breakdown` does NOT include product status, so `status_mismatch` will be deferred — leave as TODO comment.
- Top-5 by revenue for `big_inefficient` = sort models by `revenue_before_spp` desc, take first 5.

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/signals/test_model_signals.py
"""Tests for _detect_model_signals (model_breakdown source)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _make_model_data(models: list[dict]) -> dict:
    return {
        "_source": "model_breakdown",
        "channel": "WB",
        "models": models,
    }


def _model(name="TestModel", margin_pct=20, drr_pct=5, turnover_days=30,
           roi_annual=200, margin=50000, adv_total=10000, orders_count=100,
           sales_count=80, revenue_before_spp=300000):
    return {
        "model": name, "margin_pct": margin_pct, "drr_pct": drr_pct,
        "turnover_days": turnover_days, "roi_annual": roi_annual,
        "margin": margin, "adv_total": adv_total, "orders_count": orders_count,
        "sales_count": sales_count, "revenue_before_spp": revenue_before_spp,
    }


def test_low_roi_article():
    models = [
        _model("Good", turnover_days=20, margin_pct=25, roi_annual=300),
        _model("Bad", turnover_days=60, margin_pct=10, roi_annual=30),
    ]
    # median turnover = 40, Bad = 60 > 40*1.5=60 — edge case, use 61
    models[1]["turnover_days"] = 61
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "low_roi_article" in types
    bad_signal = [s for s in signals if s.type == "low_roi_article"][0]
    assert "Bad" in bad_signal.hint


def test_high_roi_opportunity():
    models = [
        _model("Slow", turnover_days=40),
        _model("Fast", turnover_days=10, margin_pct=30, roi_annual=500),
    ]
    # median = 25, Fast = 10 < 25*0.5=12.5 ✓, margin_pct > 25 ✓
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "high_roi_opportunity" in types


def test_big_inefficient():
    models = [
        _model(f"Model{i}", revenue_before_spp=1000000 - i * 100000, margin_pct=8)
        for i in range(6)
    ]
    # All top-5 have margin_pct=8% < 10%
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "big_inefficient" in types


def test_romi_critical():
    models = [
        _model("Romi_bad", margin=5000, adv_total=15000, drr_pct=20),
        # ROMI = 5000/15000 = 0.33 < 0.5 ✓, drr > 0 ✓
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "romi_critical" in types


def test_cac_exceeds_profit():
    models = [
        _model("Cac_bad", adv_total=20000, orders_count=10, margin=8000, sales_count=8, drr_pct=15),
        # CAC = 20000/10 = 2000, profit/sale = 8000/8 = 1000 → CAC > profit ✓
    ]
    signals = detect_signals(_make_model_data(models))
    types = {s.type for s in signals}
    assert "cac_exceeds_profit" in types


def test_no_signals_healthy_models():
    models = [
        _model("A", margin_pct=25, drr_pct=5, turnover_days=25, roi_annual=250, margin=100000, adv_total=15000),
        _model("B", margin_pct=22, drr_pct=6, turnover_days=30, roi_annual=200, margin=80000, adv_total=12000),
    ]
    signals = detect_signals(_make_model_data(models))
    critical = [s for s in signals if s.severity in ("critical", "warning")]
    assert len(critical) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/shared/signals/test_model_signals.py -v`
Expected: FAIL — stub returns `[]`

- [ ] **Step 3: Implement `_detect_model_signals`**

Replace the stub in `shared/signals/detector.py`:

```python
def _detect_model_signals(data: dict) -> list[Signal]:
    signals = []
    models = data.get("models", [])
    if not models:
        return signals

    channel = data.get("channel", "unknown")

    # Pre-compute median turnover_days (excluding 0)
    turnover_values = [m.get("turnover_days", 0) or 0 for m in models if (m.get("turnover_days", 0) or 0) > 0]
    median_turnover = sorted(turnover_values)[len(turnover_values) // 2] if turnover_values else 0

    for m in models:
        name = m.get("model", "?")
        margin_pct = m.get("margin_pct", 0) or 0
        drr_pct = m.get("drr_pct", 0) or 0
        turnover = m.get("turnover_days", 0) or 0
        roi = m.get("roi_annual", 0) or 0
        margin = m.get("margin", 0) or 0
        adv_total = m.get("adv_total", 0) or 0
        orders_count = m.get("orders_count", 0) or 0
        sales_count = m.get("sales_count", 0) or 0

        # 1. low_roi_article: low ROI + low margin + slow turnover
        if median_turnover > 0 and roi < 50 and margin_pct < 15 and turnover > median_turnover * 1.5:
            signals.append(Signal(
                id=f"low_roi_article_{channel}_{name}",
                type="low_roi_article",
                category="turnover",
                severity="warning",
                impact_on="both",
                data={"model": name, "roi_annual": roi, "margin_pct": margin_pct, "turnover_days": turnover},
                hint=f"{name}: ROI {roi}%, маржа {margin_pct}%, оборачиваемость {turnover} дн. — кандидат на вывод",
                source="model_breakdown",
            ))

        # 2. high_roi_opportunity: fast turnover + high margin
        if median_turnover > 0 and turnover > 0 and turnover < median_turnover * 0.5 and margin_pct > 25:
            signals.append(Signal(
                id=f"high_roi_opportunity_{channel}_{name}",
                type="high_roi_opportunity",
                category="turnover",
                severity="info",
                impact_on="both",
                data={"model": name, "margin_pct": margin_pct, "turnover_days": turnover, "roi_annual": roi},
                hint=f"{name}: маржа {margin_pct}%, оборачиваемость {turnover} дн. — потенциал для масштабирования",
                source="model_breakdown",
            ))

        # 4. romi_critical: ROMI < 50% for advertised models
        if adv_total > 0 and drr_pct > 0:
            romi = margin / adv_total if adv_total > 0 else 999
            if romi < 0.5:
                signals.append(Signal(
                    id=f"romi_critical_{channel}_{name}",
                    type="romi_critical",
                    category="adv",
                    severity="critical",
                    impact_on="margin",
                    data={"model": name, "romi": round(romi, 2), "margin": margin, "adv_total": adv_total},
                    hint=f"{name}: ROMI = {round(romi * 100)}% (маржа {margin}₽ / реклама {adv_total}₽) — убыточная реклама",
                    source="model_breakdown",
                ))

        # 5. cac_exceeds_profit: CAC > profit per sale
        if adv_total > 0 and orders_count > 0 and sales_count > 0 and drr_pct > 0:
            cac = adv_total / orders_count
            profit_per_sale = margin / sales_count
            if cac > profit_per_sale:
                signals.append(Signal(
                    id=f"cac_exceeds_profit_{channel}_{name}",
                    type="cac_exceeds_profit",
                    category="adv",
                    severity="critical",
                    impact_on="margin",
                    data={"model": name, "cac": round(cac), "profit_per_sale": round(profit_per_sale)},
                    hint=f"{name}: CAC ({round(cac)}₽) > прибыль/продажу ({round(profit_per_sale)}₽)",
                    source="model_breakdown",
                ))

    # 3. big_inefficient: top-5 by revenue with margin_pct < 10%
    sorted_by_rev = sorted(models, key=lambda m: m.get("revenue_before_spp", 0) or 0, reverse=True)
    for m in sorted_by_rev[:5]:
        mp = m.get("margin_pct", 0) or 0
        if mp < 10:
            name = m.get("model", "?")
            signals.append(Signal(
                id=f"big_inefficient_{channel}_{name}",
                type="big_inefficient",
                category="model",
                severity="warning",
                impact_on="margin",
                data={"model": name, "margin_pct": mp, "revenue": m.get("revenue_before_spp", 0)},
                hint=f"{name}: топ по выручке, но маржинальность всего {mp}%",
                source="model_breakdown",
            ))

    # status_mismatch: requires product status data not available in model_breakdown
    # TODO: Implement when get_product_statuses data is integrated

    return signals
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/shared/signals/test_model_signals.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_model_signals.py
git commit -m "feat(signals): implement model signal detector (5 patterns)

Detects: low_roi_article, high_roi_opportunity, big_inefficient,
romi_critical, cac_exceeds_profit from get_model_breakdown results.
status_mismatch deferred (needs product status data)."
```

---

### Task 6: KB pattern signals detector (generic evaluator)

**Files:**
- Create: `tests/shared/signals/test_kb_pattern_signals.py`
- Modify: `shared/signals/detector.py:152-153` (replace stub)

**Context for implementer:**
- KB patterns have `trigger_condition` JSONB: `{"metric": "drr_pct", "operator": ">", "threshold": 12}`.
- The `metric` is a dot-path into the flat data dict (e.g. `"margin_pct"`, `"drr_pct"`). For nested data, use dotted paths like `"brand.current.margin_pct"`.
- Operators: `>`, `<`, `>=`, `<=`, `==`, `gap_gt` (for metric pairs).
- `gap_gt` requires `metric_pair: [metricA, metricB]` — fires if A - B > threshold.
- KB patterns also have `pattern_name`, `category`, `severity`, `impact_on`, `action_hint`, `confidence`.

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/signals/test_kb_pattern_signals.py
"""Tests for _detect_kb_pattern_signals (generic evaluator)."""
from __future__ import annotations

from shared.signals.detector import detect_signals


def _pattern(name, metric, operator, threshold, **kwargs):
    return {
        "pattern_name": name,
        "description": f"Test pattern {name}",
        "category": kwargs.get("category", "margin"),
        "trigger_condition": {"metric": metric, "operator": operator, "threshold": threshold, **kwargs.get("extra_cond", {})},
        "action_hint": kwargs.get("action_hint", "test action"),
        "impact_on": kwargs.get("impact_on", "margin"),
        "severity": kwargs.get("severity", "warning"),
        "source_tag": "base",
        "confidence": "high",
    }


def test_simple_gt_fires():
    data = {"_source": "brand_finance", "brand": {"current": {"drr_pct": 15.0}}}
    patterns = [_pattern("high_drr", "brand.current.drr_pct", ">", 12)]
    signals = detect_signals(data, kb_patterns=patterns)
    types = {s.type for s in signals}
    assert "kb_high_drr" in types


def test_simple_gt_does_not_fire():
    data = {"_source": "brand_finance", "brand": {"current": {"drr_pct": 10.0}}}
    patterns = [_pattern("high_drr", "brand.current.drr_pct", ">", 12)]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 0


def test_gap_gt_fires():
    data = {
        "_source": "plan_vs_fact",
        "brand_total": {"metrics": {
            "orders_count": {"completion_mtd_pct": 120},
            "margin": {"completion_mtd_pct": 100},
        }},
    }
    patterns = [_pattern(
        "order_margin_gap", "", "gap_gt", 10,
        extra_cond={"metric_pair": [
            "brand_total.metrics.orders_count.completion_mtd_pct",
            "brand_total.metrics.margin.completion_mtd_pct",
        ]},
    )]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 1


def test_missing_metric_does_not_fire():
    data = {"_source": "brand_finance", "brand": {"current": {}}}
    patterns = [_pattern("missing", "brand.current.nonexistent", ">", 0)]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 0


def test_lt_operator():
    data = {"_source": "brand_finance", "brand": {"current": {"margin_pct": 8.0}}}
    patterns = [_pattern("low_margin", "brand.current.margin_pct", "<", 10, severity="critical")]
    signals = detect_signals(data, kb_patterns=patterns)
    kb_signals = [s for s in signals if s.source == "kb_pattern"]
    assert len(kb_signals) == 1
    assert kb_signals[0].severity == "critical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/shared/signals/test_kb_pattern_signals.py -v`
Expected: FAIL — stub returns `[]`

- [ ] **Step 3: Implement `_detect_kb_pattern_signals`**

Replace the stub at `shared/signals/detector.py:152-153`:

```python
def _detect_kb_pattern_signals(data: dict, kb_patterns: list[dict]) -> list[Signal]:
    signals = []
    if not kb_patterns:
        return signals

    for pattern in kb_patterns:
        condition = pattern.get("trigger_condition", {})
        if not condition:
            continue

        operator = condition.get("operator", "")
        threshold = condition.get("threshold", 0)

        if operator == "gap_gt":
            pair = condition.get("metric_pair", [])
            if len(pair) != 2:
                continue
            val_a = _deep_get(data, pair[0])
            val_b = _deep_get(data, pair[1])
            if val_a is None or val_b is None:
                continue
            if not _compare(val_a - val_b, ">", threshold):
                continue
        else:
            metric = condition.get("metric", "")
            if not metric:
                continue
            value = _deep_get(data, metric)
            if value is None:
                continue
            if not _compare(value, operator, threshold):
                continue

        name = pattern.get("pattern_name", "unknown")
        signals.append(Signal(
            id=f"kb_{name}",
            type=f"kb_{name}",
            category=pattern.get("category", "margin"),
            severity=pattern.get("severity", "warning"),
            impact_on=pattern.get("impact_on", "margin"),
            data={"pattern_name": name, "trigger_condition": condition},
            hint=pattern.get("description", name),
            source="kb_pattern",
        ))

    return signals


def _deep_get(data: dict, path: str):
    """Get nested value by dot-separated path. Returns None if missing."""
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
        if current is None:
            return None
    return current


def _compare(value, operator: str, threshold) -> bool:
    """Compare value against threshold using operator string."""
    try:
        value = float(value)
        threshold = float(threshold)
    except (TypeError, ValueError):
        return False

    if operator == ">":
        return value > threshold
    elif operator == "<":
        return value < threshold
    elif operator == ">=":
        return value >= threshold
    elif operator == "<=":
        return value <= threshold
    elif operator == "==":
        return abs(value - threshold) < 0.001
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/shared/signals/test_kb_pattern_signals.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Run ALL signal tests to verify no regression**

Run: `python3 -m pytest tests/shared/signals/ tests/agents/oleg/orchestrator/ tests/integration/test_advisor_pipeline.py -v`
Expected: All tests pass (existing 32 + new ~30)

- [ ] **Step 6: Commit**

```bash
git add shared/signals/detector.py tests/shared/signals/test_kb_pattern_signals.py
git commit -m "feat(signals): implement KB pattern generic evaluator

Supports operators: >, <, >=, <=, ==, gap_gt.
Uses dot-path metric resolution for nested data structures."
```

---

## Phase 3: Final integration test

### Task 7: End-to-end integration test

**Files:**
- Modify: `tests/integration/test_advisor_pipeline.py` (add new tests)

**Context for implementer:**
- The existing integration test file has 2 tests. Add tests that verify the full flow: tool results → extract → detect signals → correct signal types.
- Use realistic data shapes matching what `get_brand_finance` and `get_margin_levers` actually return.

- [ ] **Step 1: Add integration tests**

```python
# Append to tests/integration/test_advisor_pipeline.py

def test_finance_data_produces_signals():
    """Brand finance data with anomalies produces correct signal types."""
    data = {
        "_source": "brand_finance",
        "brand": {
            "current": {
                "margin_pct": 18.0, "revenue_before_spp": 1_000_000,
                "revenue_after_spp": 850_000, "logistics": 90_000,
                "cogs_per_unit": 320, "orders_rub": 1_200_000,
                "orders_count": 400, "sales_count": 500,
            },
            "previous": {
                "margin_pct": 24.0, "revenue_before_spp": 900_000,
                "revenue_after_spp": 770_000, "logistics": 50_000,
                "cogs_per_unit": 280, "orders_rub": 1_000_000,
                "orders_count": 380, "sales_count": 450,
            },
            "changes": {
                "cogs_per_unit_change_pct": 14.3,
                "revenue_before_spp_change_pct": 11.1,
            },
        },
    }
    signals = detect_signals(data)
    types = {s.type for s in signals}
    # margin drop (24 -> 18 = 6 pp, revenue up), cogs anomaly (14.3%), logistics (10.6%)
    assert "margin_pct_drop" in types
    assert "cogs_anomaly" in types
    assert "logistics_overweight" in types


def test_model_breakdown_detects_romi():
    """Model breakdown with low ROMI model produces romi_critical signal."""
    data = {
        "_source": "model_breakdown",
        "channel": "WB",
        "models": [
            {"model": "Good", "margin_pct": 25, "drr_pct": 5, "turnover_days": 20,
             "roi_annual": 300, "margin": 100000, "adv_total": 15000,
             "orders_count": 200, "sales_count": 180, "revenue_before_spp": 500000},
            {"model": "Bad", "margin_pct": 8, "drr_pct": 25, "turnover_days": 45,
             "roi_annual": 30, "margin": 5000, "adv_total": 25000,
             "orders_count": 50, "sales_count": 40, "revenue_before_spp": 100000},
        ],
    }
    signals = detect_signals(data)
    types = {s.type for s in signals}
    assert "romi_critical" in types
    romi_sig = [s for s in signals if s.type == "romi_critical"][0]
    assert "Bad" in romi_sig.hint


def test_multiple_sources_all_detected():
    """Signals from different sources are all collected."""
    plan_fact = {
        "_source": "plan_vs_fact",
        "days_elapsed": 15,
        "brand_total": {"metrics": {
            "orders_count": {"completion_mtd_pct": 130},
            "margin": {"completion_mtd_pct": 95},
            "sales_count": {"completion_mtd_pct": 110},
            "revenue": {"completion_mtd_pct": 115},
            "adv_internal": {"completion_mtd_pct": 100},
            "adv_external": {"completion_mtd_pct": 100},
        }},
    }
    margin_levers = {
        "_source": "margin_levers",
        "channel": "WB",
        "levers": {
            "spp_pct": {"current": 20.0, "previous": 15.0},
            "drr_pct": {"current": 8.0, "previous": 7.0},
        },
        "waterfall": {"revenue_change": 50000},
    }

    signals_pf = detect_signals(plan_fact)
    signals_ml = detect_signals(margin_levers)
    all_signals = signals_pf + signals_ml

    sources = {s.source for s in all_signals}
    assert "plan_vs_fact" in sources
    assert "margin_levers" in sources
    # plan_fact: margin_lags_orders (gap 35pp), margin_pct_drop (rev 115, margin 95)
    # margin_levers: spp_shift_up (delta 5pp)
    types = {s.type for s in all_signals}
    assert "margin_lags_orders" in types
    assert "spp_shift_up" in types
```

- [ ] **Step 2: Run all tests**

Run: `python3 -m pytest tests/ -v --ignore=tests/agents/oleg/orchestrator/test_extract_structured_data.py -k "signal or advisor or pipeline"`
Expected: All pass

Run: `python3 -m pytest tests/integration/test_advisor_pipeline.py -v`
Expected: 5 PASSED (2 old + 3 new)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_advisor_pipeline.py
git commit -m "test(integration): add cross-source signal detection integration tests

Verifies finance, model, and multi-source data all produce correct signals."
```

---

## Summary

| Task | Component | Patterns | Tests |
|------|-----------|----------|-------|
| 1 | Orchestrator extraction + multi-source detection | - | 5 |
| 2 | Finance detector | 4 | 5 |
| 3 | Margin lever detector | 4 | 6 |
| 4 | Advertising detector | 4 | 6 |
| 5 | Model detector | 5 (+1 deferred) | 7 |
| 6 | KB pattern evaluator | generic | 5 |
| 7 | Integration tests | - | 3 |
| **Total** | | **17 new + 5 existing** | **37 new** |
