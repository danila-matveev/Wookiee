# Trust Envelope + Cost Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confidence metadata (`_meta`) to every agent's output and wire up token/cost tracking through the existing observability pipeline.

**Architecture:** Two independent features sharing the same files. Trust Envelope adds `_meta` block to agent prompts and teaches report-compiler to render it. Cost Tracking extracts token usage from LangChain responses in runner.py, aggregates in orchestrator.py, and displays in Telegram footer.

**Tech Stack:** Python 3.11, LangGraph, LangChain (ChatOpenAI via OpenRouter), Supabase (observability), aiogram (Telegram)

**Spec:** `docs/superpowers/specs/2026-03-21-trust-envelope-and-cost-tracking-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `agents/v3/runner.py` | Modify | Token extraction from LLM response + `_meta` sanity check + cost calculation |
| `agents/v3/orchestrator.py` | Modify | Aggregate confidence + tokens/cost + pass to delivery |
| `agents/v3/delivery/telegram.py` | Modify | Confidence + cost in footer |
| `agents/v3/agents/report-compiler.md` | Modify | Rules for rendering trust envelope in reports |
| `agents/v3/agents/*.md` (23 files) | Modify | Add `_meta` with `conclusions` to Output Format |
| `agents/v3/config.py` | Modify (minor) | Add `calc_cost()` helper |
| `tests/agents/v3/test_trust_envelope.py` | Create | Tests for sanity check, aggregation, cost calc |

---

## Task 1: Cost calculation helper in config.py

**Files:**
- Modify: `agents/v3/config.py:19-23`
- Create: `tests/agents/v3/test_trust_envelope.py`

- [ ] **Step 0: Create test directory**

```bash
mkdir -p tests/agents/v3
touch tests/agents/v3/__init__.py
```

- [ ] **Step 1: Write tests for calc_cost**

```python
# tests/agents/v3/test_trust_envelope.py
"""Tests for Trust Envelope and Cost Tracking."""
import pytest


# --- Cost Calculation ---

def test_calc_cost_known_model():
    from agents.v3.config import calc_cost
    # z-ai/glm-4.7: input=0.00006/1K, output=0.0004/1K
    cost = calc_cost(
        model="z-ai/glm-4.7",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    # 1000/1000 * 0.00006 + 500/1000 * 0.0004 = 0.00006 + 0.0002 = 0.00026
    assert cost == pytest.approx(0.00026, abs=1e-6)


def test_calc_cost_unknown_model_uses_default():
    from agents.v3.config import calc_cost
    cost = calc_cost(
        model="unknown/model",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    # default: input=0.001, output=0.001
    # 1000/1000 * 0.001 + 1000/1000 * 0.001 = 0.002
    assert cost == pytest.approx(0.002, abs=1e-6)


def test_calc_cost_zero_tokens():
    from agents.v3.config import calc_cost
    assert calc_cost("z-ai/glm-4.7", 0, 0) == 0.0
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "calc_cost"
```
Expected: ImportError — `calc_cost` not found

- [ ] **Step 3: Implement calc_cost in config.py**

Add after the PRICING dict (after line 23):

```python
def calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost in USD based on model pricing (per 1K tokens)."""
    rates = PRICING.get(model, {"input": 0.001, "output": 0.001})
    return round(
        (prompt_tokens / 1_000) * rates["input"]
        + (completion_tokens / 1_000) * rates["output"],
        6,
    )
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "calc_cost"
```

- [ ] **Step 5: Commit**

```bash
git add agents/v3/config.py tests/agents/v3/test_trust_envelope.py
git commit -m "feat: add calc_cost helper to config.py"
```

---

## Task 2: Token extraction + cost tracking in runner.py

**Files:**
- Modify: `agents/v3/runner.py:336-384`
- Modify: `tests/agents/v3/test_trust_envelope.py`

- [ ] **Step 1: Write tests for token extraction**

Append to `tests/agents/v3/test_trust_envelope.py`:

```python
# --- Token Extraction ---

def test_extract_usage_from_ai_messages():
    """Verify we sum token usage across all AIMessages in a ReAct chain."""
    from agents.v3.runner import extract_token_usage
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    messages = [
        HumanMessage(content="query"),
        AIMessage(
            content="thinking...",
            response_metadata={"token_usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}},
        ),
        ToolMessage(content="tool result", tool_call_id="1"),
        AIMessage(
            content="final answer",
            response_metadata={"token_usage": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280}},
        ),
    ]
    usage = extract_token_usage(messages)
    assert usage["prompt_tokens"] == 300
    assert usage["completion_tokens"] == 130
    assert usage["total_tokens"] == 430


def test_extract_usage_no_metadata():
    """If no response_metadata, return zeros."""
    from agents.v3.runner import extract_token_usage
    from langchain_core.messages import AIMessage

    messages = [AIMessage(content="answer")]
    usage = extract_token_usage(messages)
    assert usage["prompt_tokens"] == 0
    assert usage["completion_tokens"] == 0
    assert usage["total_tokens"] == 0


def test_extract_usage_empty_messages():
    from agents.v3.runner import extract_token_usage
    usage = extract_token_usage([])
    assert usage["total_tokens"] == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "extract_usage"
```

- [ ] **Step 3: Implement extract_token_usage in runner.py**

Add as a module-level function (before `run_agent()`):

```python
from langchain_core.messages import AIMessage

def extract_token_usage(messages: list) -> dict[str, int]:
    """Sum token usage from all AIMessages in a LangGraph result."""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "response_metadata"):
            token_usage = msg.response_metadata.get("token_usage", {})
            usage["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
            usage["completion_tokens"] += token_usage.get("completion_tokens", 0)
            usage["total_tokens"] += token_usage.get("total_tokens", 0)
    return usage
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "extract_usage"
```

- [ ] **Step 5: Wire into run_agent() — token extraction + cost + return dict**

In `runner.py`, after the artifact extraction block (~line 341), add:

```python
# Token usage & cost
usage = extract_token_usage(result.get("messages", []))
model_used = model or config.MODEL_MAIN
cost_usd = config.calc_cost(model_used, usage["prompt_tokens"], usage["completion_tokens"])
```

Update `log_agent_run()` call (~line 357-375) to pass token fields:

```python
prompt_tokens=usage["prompt_tokens"],
completion_tokens=usage["completion_tokens"],
total_tokens=usage["total_tokens"],
cost_usd=cost_usd,
```

Update return dict (~line 377-384) to include:

```python
"prompt_tokens": usage["prompt_tokens"],
"completion_tokens": usage["completion_tokens"],
"total_tokens": usage["total_tokens"],
"cost_usd": cost_usd,
```

- [ ] **Step 6: Commit**

```bash
git add agents/v3/runner.py tests/agents/v3/test_trust_envelope.py
git commit -m "feat: extract token usage and calculate cost in runner.py"
```

---

## Task 3: `_meta` sanity check in runner.py

**Files:**
- Modify: `agents/v3/runner.py` (after artifact parsing)
- Modify: `tests/agents/v3/test_trust_envelope.py`

- [ ] **Step 1: Write tests for sanity check**

Append to test file:

```python
# --- Meta Sanity Check ---

def test_sanitize_meta_low_coverage_caps_confidence():
    from agents.v3.runner import sanitize_meta
    meta = {"confidence": 0.9, "data_coverage": 0.3, "limitations": []}
    sanitize_meta(meta)
    assert meta["confidence"] <= 0.5
    assert "data_coverage < 50%" in meta["limitations"][0]


def test_sanitize_meta_ok_coverage_keeps_confidence():
    from agents.v3.runner import sanitize_meta
    meta = {"confidence": 0.9, "data_coverage": 0.8, "limitations": []}
    sanitize_meta(meta)
    assert meta["confidence"] == 0.9
    assert meta["limitations"] == []


def test_sanitize_meta_missing_fields_no_mutation():
    from agents.v3.runner import sanitize_meta
    meta = {}
    sanitize_meta(meta)  # should not raise
    # Empty dict should not be mutated (coverage=1.0 default, no cap triggered)
    assert "confidence" not in meta
    assert "limitations" not in meta
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "sanitize_meta"
```

- [ ] **Step 3: Implement sanitize_meta in runner.py**

```python
def sanitize_meta(meta: dict) -> None:
    """Enforce sanity rules on _meta block (mutates in place)."""
    coverage = meta.get("data_coverage", 1.0)
    confidence = meta.get("confidence", 0.0)
    if coverage < 0.5 and confidence > 0.6:
        meta["confidence"] = min(confidence, 0.5)
        meta.setdefault("limitations", []).append(
            "confidence снижен автоматически: data_coverage < 50%"
        )
```

- [ ] **Step 4: Wire into run_agent() — call after artifact parsing**

After JSON artifact extraction (~line 341):

```python
# Sanitize _meta if present
if artifact and isinstance(artifact, dict) and "_meta" in artifact:
    sanitize_meta(artifact["_meta"])
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "sanitize_meta"
```

- [ ] **Step 6: Commit**

```bash
git add agents/v3/runner.py tests/agents/v3/test_trust_envelope.py
git commit -m "feat: add _meta sanity check in runner.py"
```

---

## Task 4: Confidence + cost aggregation in orchestrator.py

**Files:**
- Modify: `agents/v3/orchestrator.py:148-251, 555-570`
- Modify: `tests/agents/v3/test_trust_envelope.py`

- [ ] **Step 1: Write tests for aggregation functions**

Append to test file:

```python
# --- Confidence Aggregation ---

def test_aggregate_confidence_weighted():
    from agents.v3.orchestrator import aggregate_confidence
    confidences = {
        "margin-analyst": 0.9,     # weight 1.0
        "revenue-decomposer": 0.8, # weight 1.0
        "hypothesis-tester": 0.5,  # weight 0.5
    }
    result = aggregate_confidence(confidences)
    # (1.0*0.9 + 1.0*0.8 + 0.5*0.5) / (1.0+1.0+0.5) = 1.95/2.5 = 0.78
    assert result == pytest.approx(0.78, abs=0.01)


def test_aggregate_confidence_empty():
    from agents.v3.orchestrator import aggregate_confidence
    assert aggregate_confidence({}) == 0.0


def test_aggregate_confidence_unknown_agent_gets_default_weight():
    from agents.v3.orchestrator import aggregate_confidence
    confidences = {"some-new-agent": 0.7}
    result = aggregate_confidence(confidences)
    assert result == pytest.approx(0.7, abs=0.01)


def test_worst_limitation_picks_lowest_confidence():
    from agents.v3.orchestrator import worst_limitation, FAILED_AGENT_META
    artifacts = {
        "margin-analyst": {
            "_meta": {"confidence": 0.9, "limitations": []},
        },
        "ad-efficiency": {
            "_meta": {"confidence": 0.5, "limitations": ["OZON кабинет не обновлялся"]},
        },
    }
    result = worst_limitation(artifacts)
    assert "ad-efficiency" in result
    assert "OZON" in result


def test_worst_limitation_all_green():
    from agents.v3.orchestrator import worst_limitation
    artifacts = {
        "margin-analyst": {"_meta": {"confidence": 0.9, "limitations": []}},
    }
    assert worst_limitation(artifacts) is None


def test_failed_agent_meta_injected():
    from agents.v3.orchestrator import FAILED_AGENT_META
    assert FAILED_AGENT_META["confidence"] == 0.0
    assert FAILED_AGENT_META["conclusions"] == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "aggregate_confidence or worst_limitation or failed_agent"
```

- [ ] **Step 3: Implement aggregation functions in orchestrator.py**

Add at module level:

```python
FAILED_AGENT_META: dict = {
    "confidence": 0.0,
    "confidence_reason": "агент не выполнился",
    "data_coverage": 0.0,
    "limitations": ["агент завершился с ошибкой"],
    "conclusions": [],
}

AGENT_WEIGHTS: dict[str, float] = {
    "margin-analyst": 1.0,
    "revenue-decomposer": 1.0,
    "ad-efficiency": 1.0,
    "price-strategist": 1.0,
    "pricing-impact-analyst": 0.5,
    "hypothesis-tester": 0.5,
    "anomaly-detector": 0.5,
}


def aggregate_confidence(confidences: dict[str, float]) -> float:
    """Weighted average confidence across agents."""
    if not confidences:
        return 0.0
    total_weight = 0.0
    weighted_sum = 0.0
    for agent_name, conf in confidences.items():
        w = AGENT_WEIGHTS.get(agent_name, 0.5)
        weighted_sum += w * conf
        total_weight += w
    return round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0


def worst_limitation(artifacts: dict) -> str | None:
    """Return worst limitation string for Telegram footer.

    MUST be called AFTER FAILED_AGENT_META injection for failed agents.
    Missing _meta is treated as confidence=0.0 (worst case).
    Excludes report-compiler (it doesn't produce analytical conclusions).
    """
    candidates = []
    for name, art in artifacts.items():
        if name == "report-compiler":
            continue
        meta = art.get("_meta") or {}
        conf = meta.get("confidence", 0.0)
        if conf < 0.75:
            candidates.append((name, conf))
    if not candidates:
        return None
    name, _ = min(candidates, key=lambda x: x[1])
    meta = (artifacts[name].get("_meta") or {})
    lims = meta.get("limitations", [])
    return f"{name}: {lims[0]}" if lims else None
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v -k "aggregate_confidence or worst_limitation or failed_agent"
```

- [ ] **Step 5: Wire aggregation into _run_report_pipeline**

In the artifact collection loop (~lines 148-171), after checking status:

```python
# For failed agents, inject stub _meta
if result["status"] != "success":
    if isinstance(result.get("artifact"), dict) or result.get("artifact") is None:
        result.setdefault("artifact", {})
        result["artifact"]["_meta"] = FAILED_AGENT_META.copy()
```

After all agents complete, before `log_orchestrator_run()` (~line 225):

```python
# Aggregate confidence (exclude report-compiler — it doesn't analyse data)
confidences = {}
for name, result in artifacts.items():
    if name == "report-compiler":
        continue
    art = result.get("artifact") if isinstance(result, dict) else result
    meta = (art.get("_meta") or {}) if isinstance(art, dict) else {}
    if "confidence" in meta:
        confidences[name] = meta["confidence"]

agg_confidence = aggregate_confidence(confidences)

# Build artifacts view for worst_limitation (needs _meta at top level)
artifacts_for_lim = {}
for name, result in artifacts.items():
    art = result.get("artifact") if isinstance(result, dict) else result
    artifacts_for_lim[name] = art if isinstance(art, dict) else {}

worst_lim = worst_limitation(artifacts_for_lim)

# Aggregate tokens & cost
total_tokens = sum(r.get("total_tokens", 0) for r in artifacts.values() if isinstance(r, dict))
total_cost = sum(r.get("cost_usd", 0.0) for r in artifacts.values() if isinstance(r, dict))
```

Replace `total_tokens=0` and `total_cost_usd=0.0` in `log_orchestrator_run()` calls (lines 238-239, 568-569):

```python
total_tokens=total_tokens,
total_cost_usd=total_cost,
```

Update return dict (~lines 242-251) to add:

```python
"aggregate_confidence": agg_confidence,
"worst_limitation": worst_lim,
"total_tokens": total_tokens,
"total_cost_usd": total_cost,
```

- [ ] **Step 6: Apply aggregation to run_price_analysis pipeline (~lines 505-570)**

This pipeline has 3 phases and does NOT use `_run_report_pipeline` for the final aggregation. Apply explicitly:

```python
# After all_artifacts = {**phase1["artifacts"], **phase2["artifacts"]}
# and compiler_result is added:

# Inject FAILED_AGENT_META for failed agents
for name, result in all_artifacts.items():
    if name == "report-compiler":
        continue
    if isinstance(result, dict) and result.get("status") != "success":
        result.setdefault("artifact", {})
        result["artifact"]["_meta"] = FAILED_AGENT_META.copy()

# Aggregate confidence (same pattern, exclude report-compiler)
confidences = {}
for name, result in all_artifacts.items():
    if name == "report-compiler":
        continue
    art = result.get("artifact") if isinstance(result, dict) else result
    meta = (art.get("_meta") or {}) if isinstance(art, dict) else {}
    if "confidence" in meta:
        confidences[name] = meta["confidence"]

agg_confidence = aggregate_confidence(confidences)

artifacts_for_lim = {
    n: (r.get("artifact") if isinstance(r, dict) else r) or {}
    for n, r in all_artifacts.items()
}
worst_lim = worst_limitation(artifacts_for_lim)

# Aggregate tokens & cost
total_tokens = sum(r.get("total_tokens", 0) for r in all_artifacts.values() if isinstance(r, dict))
total_cost = sum(r.get("cost_usd", 0.0) for r in all_artifacts.values() if isinstance(r, dict))
```

Replace `total_tokens=0` and `total_cost_usd=0.0` in `log_orchestrator_run()` call (lines 568-569) and add `aggregate_confidence`, `worst_limitation`, `total_tokens`, `total_cost_usd` to the return dict.

- [ ] **Step 7: Commit**

```bash
git add agents/v3/orchestrator.py tests/agents/v3/test_trust_envelope.py
git commit -m "feat: aggregate confidence and cost in orchestrator"
```

---

## Task 5: Telegram footer — confidence + cost

**Files:**
- Modify: `agents/v3/delivery/telegram.py:120-135`

- [ ] **Step 1: Replace format_report_message footer**

In `format_report_message()`, **REPLACE the existing footer block (~lines 125-135)** with the following code. Do NOT add after it — remove the old `footer_parts` construction entirely:

```python
# Trust Envelope + Cost in footer
agg_confidence = report.get("aggregate_confidence")
worst_lim = report.get("worst_limitation")
total_cost = report.get("total_cost_usd", 0.0)

# Confidence marker
if agg_confidence is not None:
    if agg_confidence >= 0.75:
        conf_marker = f"🟢 {agg_confidence}"
    elif agg_confidence >= 0.45:
        conf_marker = f"🟡 {agg_confidence}"
    else:
        conf_marker = f"🔴 {agg_confidence}"
else:
    conf_marker = None

# Build footer parts
footer_parts = []
if conf_marker:
    footer_parts.append(conf_marker)
if total_cost > 0:
    footer_parts.append(f"${total_cost:.4f}")
footer_parts.append(f"Агентов: {agents_succeeded}/{agents_called}")
footer_parts.append(f"{duration_ms / 1000:.1f}с")

body += f"\n\n<i>{' | '.join(footer_parts)}</i>"

# Worst limitation line (if yellow/red)
if worst_lim and agg_confidence is not None and agg_confidence < 0.75:
    body += f"\n<i>⚠️ {worst_lim}</i>"
```

- [ ] **Step 2: Test manually with a mock report dict**

Verify the format produces valid Telegram HTML:
```
<i>🟢 0.85 | $0.0026 | Агентов: 3/3 | 42.1с</i>
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/delivery/telegram.py
git commit -m "feat: add confidence and cost to Telegram footer"
```

---

## Task 6: Update report-compiler.md — Trust Envelope rendering rules

**Files:**
- Modify: `agents/v3/agents/report-compiler.md`

- [ ] **Step 1: Add Trust Envelope rendering rules to Rules section**

After existing rules, add:

```markdown
## Trust Envelope Rendering

### Section 0 — Паспорт: таблица Достоверности

After period/comparison/channels, add:

### Достоверность

| Блок анализа | Достоверность | Покрытие данных | Примечание |
|---|---|---|---|
(one row per input agent, using _meta.confidence and _meta.data_coverage)

Маркеры:
- 🟢 confidence >= 0.75
- 🟡 0.45 <= confidence < 0.75
- 🔴 confidence < 0.45

After table, list all unique limitations from all agents under:
**Ограничения этого отчёта:**
- (each limitation as bullet)

### Секции — маркер в заголовке

Add confidence marker emoji to each section heading:
`## ▶ 1. Маржинальность 🟢`

### Ключевые выводы — toggle-блоки

For each conclusion in _meta.conclusions where type is driver, anti_driver, recommendation, or anomaly, add a toggle block after the related text:

▶ 🟢 0.91 | Statement text
  ├ confidence_reason: ...
  ├ data_coverage: ...%
  └ источники: tool1, tool2

For conclusions where type=metric, only add toggle if confidence < 0.75.

If a conclusion has limitations (non-empty array), add:
  ├ limitations:
  │   • limitation text
```

- [ ] **Step 2: Update Output Format section**

The report-compiler output already has `warnings: [string]`. No schema change needed — trust envelope data flows from input artifacts through the report text, not as separate output fields.

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/report-compiler.md
git commit -m "feat: add trust envelope rendering rules to report-compiler"
```

---

## Task 7: Add `_meta` to all agent MD Output Formats

**Files:**
- Modify: all 23 agent MD files in `agents/v3/agents/` (excluding report-compiler.md which was done in Task 6)

- [ ] **Step 1: Add _meta block to Output Format of each agent**

For each of the 23 agent MD files, prepend to the Output Format section:

```markdown
## Output Format

JSON artifact with:
- _meta: {confidence: float 0-1, confidence_reason: string, data_coverage: float 0-1, limitations: [string], conclusions: [{statement: string, type: "driver"|"anti_driver"|"recommendation"|"anomaly"|"metric", confidence: float 0-1, confidence_reason: string, data_coverage: float 0-1, limitations: [string], sources: [string]}]}
```

The `_meta` line goes FIRST in the Output Format list, before existing fields.

Agent list (23 files):
1. margin-analyst.md
2. revenue-decomposer.md
3. ad-efficiency.md
4. kb-searcher.md
5. kb-curator.md
6. kb-auditor.md
7. data-navigator.md
8. price-strategist.md
9. hypothesis-tester.md
10. campaign-optimizer.md
11. organic-vs-paid.md
12. funnel-digitizer.md
13. keyword-analyst.md
14. anomaly-detector.md
15. finolog-analyst.md
16. data-validator.md
17. quality-checker.md
18. agent-monitor.md
19. logistics-analyst.md
20. review-analyst.md
21. content-optimizer.md
22. pricing-impact-analyst.md
23. prompt-tuner.md

- [ ] **Step 2: Verify all files have _meta in Output Format**

```bash
grep -l "_meta" agents/v3/agents/*.md | wc -l
# Expected: 24 (23 agents + report-compiler)
```

- [ ] **Step 3: Commit**

```bash
git add agents/v3/agents/*.md
git commit -m "feat: add _meta trust envelope to all agent output formats"
```

---

## Task 8: Integration smoke test

**Files:**
- Modify: `tests/agents/v3/test_trust_envelope.py`

- [ ] **Step 1: Add integration test for full pipeline**

```python
# --- Integration: full pipeline mock ---

def test_full_trust_envelope_pipeline():
    """Verify _meta flows from agent artifact through aggregation."""
    from agents.v3.orchestrator import (
        aggregate_confidence, worst_limitation, FAILED_AGENT_META,
    )

    # Simulate 3 agent results
    artifacts = {
        "margin-analyst": {
            "_meta": {"confidence": 0.9, "data_coverage": 0.98, "limitations": [], "conclusions": []},
            "artifact": {"margin_rub": 847200},
        },
        "ad-efficiency": {
            "_meta": {"confidence": 0.64, "data_coverage": 0.78, "limitations": ["OZON кабинет лаг 2 дня"], "conclusions": []},
            "artifact": {"drr_pct": 8.2},
        },
        "hypothesis-tester": {
            "_meta": FAILED_AGENT_META.copy(),
            "artifact": {},
        },
    }

    # Aggregate
    confidences = {n: a["_meta"]["confidence"] for n, a in artifacts.items()}
    agg = aggregate_confidence(confidences)
    worst = worst_limitation(artifacts)

    # margin-analyst: 1.0 * 0.9 = 0.9
    # ad-efficiency: 1.0 * 0.64 = 0.64
    # hypothesis-tester: 0.5 * 0.0 = 0.0
    # total weights: 1.0 + 1.0 + 0.5 = 2.5
    # weighted sum: 0.9 + 0.64 + 0.0 = 1.54
    # agg = 1.54 / 2.5 = 0.616 → 0.62
    assert 0.5 < agg < 0.7

    # Worst should be hypothesis-tester (confidence=0.0)
    assert worst is not None
    assert "hypothesis-tester" in worst
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/agents/v3/test_trust_envelope.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/agents/v3/test_trust_envelope.py
git commit -m "test: add integration smoke test for trust envelope pipeline"
```
