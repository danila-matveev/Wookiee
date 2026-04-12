# Analytics Report Skill — Implementation Plan (Subproject 1: Core + Finance)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/analytics-report` skill that generates financial analysis reports for any date range, publishes to MD + Notion.

**Architecture:** Python collectors gather data from shared.data_layer into JSON bundle → LLM analyst subagent generates MD report → LLM verifier checks numbers → publish to Notion. Follows financial-overview pattern (ThreadPoolExecutor collectors → subagent pipeline).

**Tech Stack:** Python 3, shared.data_layer (PostgreSQL), shared.notion_client (Notion API), Claude Code skill (SKILL.md + prompts)

**Test period:** 2026-03-30 to 2026-04-05 (неделя)

---

## File Structure

```
.claude/skills/analytics-report/
├── SKILL.md                              # Orchestrator: parse args → collect → analyze → verify → publish
├── prompts/
│   ├── analyst.md                        # Financial analyst prompt with business rules
│   └── verifier.md                       # Data verification prompt
└── config.py                             # Thresholds, depth rules

scripts/analytics_report/
├── collect_all.py                        # CLI orchestrator: --start --end → JSON
├── collectors/
│   ├── finance_wb.py                     # WB financial data collector
│   ├── finance_ozon.py                   # OZON financial data collector
│   ├── funnel.py                         # WB traffic funnel (content_analysis)
│   ├── inventory.py                      # Stocks + turnover (WB/OZON/MoySklad)
│   ├── pricing.py                        # Price changes + SPP history
│   └── anomalies.py                      # Anomaly detector (share deltas > 3pp)
└── utils.py                              # Date math, formatting helpers

tests/test_analytics_report/
├── test_utils.py                         # Date math, depth detection
├── test_finance_wb.py                    # WB collector parsing
├── test_finance_ozon.py                  # OZON collector parsing
├── test_anomalies.py                     # Anomaly detection logic
└── test_collect_all.py                   # Integration: all collectors
```

---

### Task 1: Utils + Config

**Files:**
- Create: `scripts/analytics_report/utils.py`
- Create: `.claude/skills/analytics-report/config.py`
- Create: `scripts/analytics_report/__init__.py`
- Create: `scripts/analytics_report/collectors/__init__.py`
- Create: `tests/test_analytics_report/__init__.py`
- Test: `tests/test_analytics_report/test_utils.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p scripts/analytics_report/collectors
mkdir -p .claude/skills/analytics-report/prompts
mkdir -p tests/test_analytics_report
touch scripts/analytics_report/__init__.py
touch scripts/analytics_report/collectors/__init__.py
touch tests/test_analytics_report/__init__.py
```

- [ ] **Step 2: Write failing tests for utils**

```python
# tests/test_analytics_report/test_utils.py
"""Tests for analytics report date utilities."""
import pytest
from datetime import date


def test_compute_prev_period_same_length():
    from scripts.analytics_report.utils import compute_prev_period
    prev_start, prev_end = compute_prev_period(
        date(2026, 3, 30), date(2026, 4, 5)
    )
    assert prev_start == date(2026, 3, 23)
    assert prev_end == date(2026, 3, 29)


def test_compute_prev_period_single_day():
    from scripts.analytics_report.utils import compute_prev_period
    prev_start, prev_end = compute_prev_period(
        date(2026, 4, 5), date(2026, 4, 5)
    )
    assert prev_start == date(2026, 4, 4)
    assert prev_end == date(2026, 4, 4)


def test_compute_prev_period_month():
    from scripts.analytics_report.utils import compute_prev_period
    prev_start, prev_end = compute_prev_period(
        date(2026, 3, 1), date(2026, 3, 31)
    )
    assert prev_start == date(2026, 1, 30)
    assert prev_end == date(2026, 2, 28)


def test_detect_depth_day():
    from scripts.analytics_report.utils import detect_depth
    assert detect_depth(date(2026, 4, 5), date(2026, 4, 5)) == "day"


def test_detect_depth_week():
    from scripts.analytics_report.utils import detect_depth
    assert detect_depth(date(2026, 3, 30), date(2026, 4, 5)) == "week"


def test_detect_depth_month():
    from scripts.analytics_report.utils import detect_depth
    assert detect_depth(date(2026, 3, 1), date(2026, 3, 31)) == "month"


def test_calc_share():
    from scripts.analytics_report.utils import calc_share
    assert calc_share(200, 1000) == 20.0
    assert calc_share(0, 0) == 0.0
    assert calc_share(100, 0) == 0.0


def test_calc_change():
    from scripts.analytics_report.utils import calc_change
    result = calc_change(110, 100)
    assert result["abs"] == 10
    assert result["pct"] == pytest.approx(10.0, abs=0.1)


def test_calc_change_from_zero():
    from scripts.analytics_report.utils import calc_change
    result = calc_change(100, 0)
    assert result["abs"] == 100
    assert result["pct"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_analytics_report/test_utils.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Implement utils.py**

```python
# scripts/analytics_report/utils.py
"""Date math and formatting helpers for analytics report."""
from __future__ import annotations

from datetime import date, timedelta


def compute_prev_period(start: date, end: date) -> tuple[date, date]:
    """Compute previous period of same length, ending the day before start."""
    days = (end - start).days + 1  # inclusive
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return prev_start, prev_end


def detect_depth(start: date, end: date) -> str:
    """Determine report depth: day (1), week (2-13), month (14+)."""
    days = (end - start).days + 1
    if days <= 1:
        return "day"
    elif days <= 13:
        return "week"
    else:
        return "month"


def calc_share(part: float, total: float) -> float:
    """Calculate percentage share. Returns 0 if total is 0."""
    if not total:
        return 0.0
    return round(part / total * 100, 2)


def calc_change(current: float, previous: float) -> dict:
    """Calculate absolute and percentage change."""
    abs_change = round(current - previous, 2)
    if previous:
        pct_change = round((current - previous) / abs(previous) * 100, 2)
    else:
        pct_change = None
    return {"abs": abs_change, "pct": pct_change}


def format_date_str(d: date) -> str:
    """Format date as YYYY-MM-DD string."""
    return d.strftime("%Y-%m-%d")
```

- [ ] **Step 5: Implement config.py**

```python
# .claude/skills/analytics-report/config.py
"""Constants and thresholds for analytics report skill."""

# Anomaly detection: flag if share changes by more than this (percentage points)
ANOMALY_THRESHOLD_PP = 3.0

# Anomaly severity thresholds
SEVERITY_HIGH_PP = 5.0       # > 5 pp or > 100K RUB
SEVERITY_HIGH_RUB = 100_000

# Depth rules: which collectors run at each depth
DEPTH_COLLECTORS = {
    "day": ["finance_wb", "finance_ozon", "anomalies"],
    "week": ["finance_wb", "finance_ozon", "funnel", "inventory", "pricing", "anomalies"],
    "month": ["finance_wb", "finance_ozon", "funnel", "inventory", "pricing", "anomalies"],
}

# Report type labels for Notion
DEPTH_NOTION_TYPE = {
    "day": "Ежедневный фин анализ",
    "week": "Еженедельный фин анализ",
    "month": "Ежемесячный фин анализ",
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_analytics_report/test_utils.py -v`
Expected: 9 PASSED

- [ ] **Step 7: Commit**

```bash
git add scripts/analytics_report/ .claude/skills/analytics-report/config.py tests/test_analytics_report/
git commit -m "feat(analytics-report): add utils + config (Task 1)"
```

---

### Task 2: WB Finance Collector

**Files:**
- Create: `scripts/analytics_report/collectors/finance_wb.py`
- Test: `tests/test_analytics_report/test_finance_wb.py`

- [ ] **Step 1: Write failing test for WB finance parsing**

```python
# tests/test_analytics_report/test_finance_wb.py
"""Tests for WB finance collector — parsing logic (no DB required)."""
import pytest
from datetime import date


def test_parse_wb_brand_finance():
    """Test that raw DB rows are parsed into structured dict with shares."""
    from scripts.analytics_report.collectors.finance_wb import _parse_brand_finance

    # Simulate row from get_wb_finance: (period, orders, sales, rev_before_spp,
    # rev_after_spp, adv_int, adv_ext, cogs, logistics, storage, commission,
    # spp_amount, nds, penalty, retention, deduction, margin, returns_rev, rev_gross)
    row = ("current", 1500, 1300, 5_000_000, 4_200_000, 200_000, 50_000,
           1_000_000, 400_000, 150_000, 800_000, 800_000, 100_000,
           10_000, 5_000, 3_000, 1_200_000, 100_000, 5_100_000)

    result = _parse_brand_finance(row)

    assert result["revenue_before_spp"] == 5_000_000
    assert result["margin"] == 1_200_000
    assert result["orders_count"] == 1500
    assert result["logistics_share"] == pytest.approx(8.0, abs=0.1)
    assert result["commission_share"] == pytest.approx(16.0, abs=0.1)
    assert result["margin_pct"] == pytest.approx(24.0, abs=0.1)


def test_parse_model_row():
    """Test model row parsing."""
    from scripts.analytics_report.collectors.finance_wb import _parse_model_row

    # (period, model, sales, rev_before_spp, adv_int, adv_ext, margin, cogs)
    row = ("current", "wendy", 500, 2_000_000, 80_000, 20_000, 500_000, 400_000)

    result = _parse_model_row(row)
    assert result["model"] == "wendy"
    assert result["revenue_before_spp"] == 2_000_000
    assert result["margin_pct"] == pytest.approx(25.0, abs=0.1)


def test_enrich_with_changes():
    """Test that current vs previous produces correct changes dict."""
    from scripts.analytics_report.collectors.finance_wb import _enrich_with_changes

    current = {"revenue_before_spp": 5_000_000, "margin_pct": 24.0, "logistics_share": 8.0}
    previous = {"revenue_before_spp": 4_500_000, "margin_pct": 22.0, "logistics_share": 8.5}

    result = _enrich_with_changes(current, previous)
    assert result["changes"]["revenue_before_spp"]["abs"] == 500_000
    assert result["changes"]["margin_pct"]["abs"] == pytest.approx(2.0)
    assert result["changes"]["logistics_share"]["abs"] == pytest.approx(-0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_analytics_report/test_finance_wb.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement WB finance collector**

```python
# scripts/analytics_report/collectors/finance_wb.py
"""WB finance collector — brand + model level with shares and changes."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analytics_report.utils import calc_share, calc_change


def _parse_brand_finance(row) -> dict:
    """Parse get_wb_finance row into structured dict with shares."""
    rev = float(row[3] or 0)  # revenue_before_spp
    result = {
        "orders_count": int(row[1] or 0),
        "sales_count": int(row[2] or 0),
        "revenue_before_spp": rev,
        "revenue_after_spp": float(row[4] or 0),
        "adv_internal": float(row[5] or 0),
        "adv_external": float(row[6] or 0),
        "cogs": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
        "penalty": float(row[13] or 0),
        "retention": float(row[14] or 0),
        "deduction": float(row[15] or 0),
        "margin": float(row[16] or 0),
    }
    # Shares (% of revenue_before_spp)
    for key in ("adv_internal", "adv_external", "cogs", "logistics",
                "storage", "commission", "nds", "penalty"):
        result[f"{key}_share"] = calc_share(result[key], rev)
    result["margin_pct"] = calc_share(result["margin"], rev)
    result["spp_pct"] = calc_share(result["spp_amount"], rev)
    if len(row) >= 19:
        result["returns_revenue"] = float(row[17] or 0)
        result["revenue_before_spp_gross"] = float(row[18] or 0)
    return result


def _parse_model_row(row) -> dict:
    """Parse get_wb_by_model row."""
    rev = float(row[3] or 0)
    margin = float(row[6] or 0)
    return {
        "model": row[1],
        "sales_count": int(row[2] or 0),
        "revenue_before_spp": rev,
        "adv_internal": float(row[4] or 0),
        "adv_external": float(row[5] or 0),
        "margin": margin,
        "cogs": float(row[7] or 0),
        "margin_pct": calc_share(margin, rev),
    }


def _enrich_with_changes(current: dict, previous: dict) -> dict:
    """Add changes dict comparing current vs previous."""
    changes = {}
    for key in current:
        if key in previous and isinstance(current[key], (int, float)) and isinstance(previous[key], (int, float)):
            changes[key] = calc_change(current[key], previous[key])
    return {**current, "changes": changes}


def collect_finance_wb(start: str, end: str, prev_start: str, prev_end: str) -> dict:
    """Collect WB financial data for current and previous periods.

    Returns: {"brand": {"current": {...}, "previous": {...}, "changes": {...}},
              "models": {"wendy": {"current": {...}, ...}, ...}}
    """
    from shared.data_layer import get_wb_finance, get_wb_by_model

    d_start = date.fromisoformat(start)
    d_prev = date.fromisoformat(prev_start)
    d_end = date.fromisoformat(end)

    # Brand level
    fin_rows, _ = get_wb_finance(d_start, d_prev, d_end)
    brand_current = {}
    brand_previous = {}
    for row in fin_rows:
        parsed = _parse_brand_finance(row)
        if row[0] == "current":
            brand_current = parsed
        else:
            brand_previous = parsed

    brand = _enrich_with_changes(brand_current, brand_previous)

    # Model level
    model_rows = get_wb_by_model(d_start, d_prev, d_end)
    models = {}
    for row in model_rows:
        parsed = _parse_model_row(row)
        model_name = parsed.pop("model")
        period = row[0]
        if model_name not in models:
            models[model_name] = {"current": {}, "previous": {}}
        models[model_name][period] = parsed

    for model_name, data in models.items():
        if data["current"] and data["previous"]:
            data.update(_enrich_with_changes(data["current"], data["previous"]))

    return {"brand": brand, "models": models}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_analytics_report/test_finance_wb.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/analytics_report/collectors/finance_wb.py tests/test_analytics_report/test_finance_wb.py
git commit -m "feat(analytics-report): add WB finance collector (Task 2)"
```

---

### Task 3: OZON Finance Collector

**Files:**
- Create: `scripts/analytics_report/collectors/finance_ozon.py`
- Test: `tests/test_analytics_report/test_finance_ozon.py`

- [ ] **Step 1: Write failing test for OZON finance parsing**

```python
# tests/test_analytics_report/test_finance_ozon.py
"""Tests for OZON finance collector — parsing logic (no DB required)."""
import pytest


def test_parse_ozon_brand_finance():
    from scripts.analytics_report.collectors.finance_ozon import _parse_brand_finance

    # (period, sales, rev_before_spp, rev_after_spp, adv_int, adv_ext,
    #  margin, cogs, logistics, storage, commission, spp_amount, nds)
    row = ("current", 800, 3_000_000, 2_500_000, 100_000, 30_000,
           700_000, 600_000, 250_000, 80_000, 450_000, 500_000, 60_000)

    result = _parse_brand_finance(row)
    assert result["revenue_before_spp"] == 3_000_000
    assert result["margin"] == 700_000
    assert result["margin_pct"] == pytest.approx(23.3, abs=0.1)
    assert result["logistics_share"] == pytest.approx(8.3, abs=0.1)


def test_parse_ozon_model_row():
    from scripts.analytics_report.collectors.finance_ozon import _parse_model_row

    row = ("current", "wendy", 300, 1_200_000, 40_000, 10_000, 300_000, 240_000)

    result = _parse_model_row(row)
    assert result["model"] == "wendy"
    assert result["margin_pct"] == pytest.approx(25.0, abs=0.1)
```

- [ ] **Step 2: Run tests — verify fail**

Run: `python -m pytest tests/test_analytics_report/test_finance_ozon.py -v`

- [ ] **Step 3: Implement OZON finance collector**

```python
# scripts/analytics_report/collectors/finance_ozon.py
"""OZON finance collector — brand + model level with shares and changes."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analytics_report.utils import calc_share, calc_change
from scripts.analytics_report.collectors.finance_wb import _enrich_with_changes


def _parse_brand_finance(row) -> dict:
    """Parse get_ozon_finance row into structured dict with shares."""
    rev = float(row[2] or 0)  # revenue_before_spp
    result = {
        "sales_count": int(row[1] or 0),
        "revenue_before_spp": rev,
        "revenue_after_spp": float(row[3] or 0),
        "adv_internal": float(row[4] or 0),
        "adv_external": float(row[5] or 0),
        "margin": float(row[6] or 0),
        "cogs": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
    }
    for key in ("adv_internal", "adv_external", "cogs", "logistics",
                "storage", "commission", "nds"):
        result[f"{key}_share"] = calc_share(result[key], rev)
    result["margin_pct"] = calc_share(result["margin"], rev)
    result["spp_pct"] = calc_share(result["spp_amount"], rev)
    return result


def _parse_model_row(row) -> dict:
    """Parse get_ozon_by_model row."""
    rev = float(row[3] or 0)
    margin = float(row[6] or 0)
    return {
        "model": row[1],
        "sales_count": int(row[2] or 0),
        "revenue_before_spp": rev,
        "adv_internal": float(row[4] or 0),
        "adv_external": float(row[5] or 0),
        "margin": margin,
        "cogs": float(row[7] or 0),
        "margin_pct": calc_share(margin, rev),
    }


def collect_finance_ozon(start: str, end: str, prev_start: str, prev_end: str) -> dict:
    """Collect OZON financial data for current and previous periods."""
    from shared.data_layer import get_ozon_finance, get_ozon_by_model

    d_start = date.fromisoformat(start)
    d_prev = date.fromisoformat(prev_start)
    d_end = date.fromisoformat(end)

    fin_rows = get_ozon_finance(d_start, d_prev, d_end)
    brand_current = {}
    brand_previous = {}
    for row in fin_rows:
        parsed = _parse_brand_finance(row)
        if row[0] == "current":
            brand_current = parsed
        else:
            brand_previous = parsed

    brand = _enrich_with_changes(brand_current, brand_previous)

    model_rows = get_ozon_by_model(d_start, d_prev, d_end)
    models = {}
    for row in model_rows:
        parsed = _parse_model_row(row)
        model_name = parsed.pop("model")
        period = row[0]
        if model_name not in models:
            models[model_name] = {"current": {}, "previous": {}}
        models[model_name][period] = parsed

    for model_name, data in models.items():
        if data["current"] and data["previous"]:
            data.update(_enrich_with_changes(data["current"], data["previous"]))

    return {"brand": brand, "models": models}
```

- [ ] **Step 4: Run tests — verify pass**

Run: `python -m pytest tests/test_analytics_report/test_finance_ozon.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/analytics_report/collectors/finance_ozon.py tests/test_analytics_report/test_finance_ozon.py
git commit -m "feat(analytics-report): add OZON finance collector (Task 3)"
```

---

### Task 4: Anomaly Detector

**Files:**
- Create: `scripts/analytics_report/collectors/anomalies.py`
- Test: `tests/test_analytics_report/test_anomalies.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_analytics_report/test_anomalies.py
"""Tests for anomaly detection logic."""
import pytest


def test_detect_anomalies_finds_large_delta():
    from scripts.analytics_report.collectors.anomalies import detect_anomalies

    wb_data = {
        "brand": {
            "current": {"logistics_share": 11.2, "commission_share": 16.0, "cogs_share": 20.0,
                        "storage_share": 3.0, "logistics": 560_000},
            "previous": {"logistics_share": 7.5, "commission_share": 15.8, "cogs_share": 20.1,
                         "storage_share": 3.1, "logistics": 375_000},
        }
    }

    anomalies = detect_anomalies(wb_data, {}, threshold_pp=3.0)
    assert len(anomalies) >= 1
    logistics_anomaly = [a for a in anomalies if a["metric"] == "logistics_share"][0]
    assert logistics_anomaly["delta_pp"] == pytest.approx(3.7, abs=0.1)
    assert logistics_anomaly["severity"] == "high"


def test_detect_anomalies_ignores_small_delta():
    from scripts.analytics_report.collectors.anomalies import detect_anomalies

    wb_data = {
        "brand": {
            "current": {"logistics_share": 8.0, "commission_share": 16.0},
            "previous": {"logistics_share": 7.5, "commission_share": 15.8},
        }
    }

    anomalies = detect_anomalies(wb_data, {}, threshold_pp=3.0)
    assert len(anomalies) == 0


def test_detect_anomalies_handles_empty():
    from scripts.analytics_report.collectors.anomalies import detect_anomalies
    assert detect_anomalies({}, {}, threshold_pp=3.0) == []
```

- [ ] **Step 2: Run tests — verify fail**

Run: `python -m pytest tests/test_analytics_report/test_anomalies.py -v`

- [ ] **Step 3: Implement anomaly detector**

```python
# scripts/analytics_report/collectors/anomalies.py
"""Anomaly detector: flags metrics where share changed > threshold."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

SHARE_METRICS = [
    "logistics_share", "commission_share", "cogs_share", "storage_share",
    "adv_internal_share", "adv_external_share", "nds_share", "penalty_share",
]

SEVERITY_HIGH_PP = 5.0
SEVERITY_HIGH_RUB = 100_000


def _check_brand(brand_data: dict, channel: str, threshold_pp: float) -> list[dict]:
    """Check brand-level share anomalies for one channel."""
    anomalies = []
    current = brand_data.get("current", {})
    previous = brand_data.get("previous", {})
    if not current or not previous:
        return anomalies

    for metric in SHARE_METRICS:
        curr_val = current.get(metric)
        prev_val = previous.get(metric)
        if curr_val is None or prev_val is None:
            continue
        delta = round(curr_val - prev_val, 2)
        if abs(delta) >= threshold_pp:
            base_metric = metric.replace("_share", "")
            abs_rub = abs(current.get(base_metric, 0) - previous.get(base_metric, 0))
            severity = "high" if (abs(delta) >= SEVERITY_HIGH_PP or abs_rub >= SEVERITY_HIGH_RUB) else "medium"
            anomalies.append({
                "metric": metric,
                "channel": channel,
                "model": None,
                "prev_share": prev_val,
                "curr_share": curr_val,
                "delta_pp": delta,
                "abs_rub": round(abs_rub, 2),
                "severity": severity,
            })
    return anomalies


def detect_anomalies(wb_data: dict, ozon_data: dict, threshold_pp: float = 3.0) -> list[dict]:
    """Detect anomalies across WB and OZON brand-level data."""
    anomalies = []
    if wb_data and "brand" in wb_data:
        anomalies.extend(_check_brand(wb_data["brand"], "wb", threshold_pp))
    if ozon_data and "brand" in ozon_data:
        anomalies.extend(_check_brand(ozon_data["brand"], "ozon", threshold_pp))
    anomalies.sort(key=lambda a: abs(a["delta_pp"]), reverse=True)
    return anomalies
```

- [ ] **Step 4: Run tests — verify pass**

Run: `python -m pytest tests/test_analytics_report/test_anomalies.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/analytics_report/collectors/anomalies.py tests/test_analytics_report/test_anomalies.py
git commit -m "feat(analytics-report): add anomaly detector (Task 4)"
```

---

### Task 5: Funnel, Inventory, Pricing Collectors

**Files:**
- Create: `scripts/analytics_report/collectors/funnel.py`
- Create: `scripts/analytics_report/collectors/inventory.py`
- Create: `scripts/analytics_report/collectors/pricing.py`

These collectors are thin wrappers around existing `shared.data_layer` functions — they call the functions and structure the results. No complex parsing logic to unit test (the data_layer functions are already tested). Integration tested in Task 6.

- [ ] **Step 1: Implement funnel collector**

```python
# scripts/analytics_report/collectors/funnel.py
"""WB traffic funnel collector (content_analysis table)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analytics_report.utils import calc_share, calc_change


def collect_funnel(start: str, end: str, prev_start: str, prev_end: str) -> dict:
    """Collect WB funnel data: impressions → cart → orders → buyouts."""
    from shared.data_layer import get_wb_organic_vs_paid_funnel

    rows = get_wb_organic_vs_paid_funnel(start, prev_start, end)

    current = {}
    previous = {}
    for row in rows:
        period = row[0]
        data = {
            "card_opens": int(row[1] or 0),
            "add_to_cart": int(row[2] or 0),
            "orders": int(row[3] or 0),
            "buyouts": int(row[4] or 0),
        }
        data["cr_cart"] = calc_share(data["add_to_cart"], data["card_opens"])
        data["cr_order"] = calc_share(data["orders"], data["add_to_cart"])
        data["cr_buyout"] = calc_share(data["buyouts"], data["orders"])
        if period == "current":
            current = data
        else:
            previous = data

    changes = {}
    for key in current:
        if key in previous and isinstance(current[key], (int, float)):
            changes[key] = calc_change(current[key], previous[key])

    return {"wb": {"current": current, "previous": previous, "changes": changes}}
```

- [ ] **Step 2: Implement inventory collector**

```python
# scripts/analytics_report/collectors/inventory.py
"""Inventory collector: stocks + turnover from WB, OZON, MoySklad."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def collect_inventory(start: str, end: str, prev_start: str, prev_end: str, depth: str) -> dict:
    """Collect inventory data. ABC only for depth=month."""
    from shared.data_layer import (
        get_wb_turnover_by_model,
        get_ozon_turnover_by_model,
        get_moysklad_stock_by_model,
    )

    wb_turnover = get_wb_turnover_by_model(start, end)
    ozon_turnover = get_ozon_turnover_by_model(start, end)

    try:
        moysklad = get_moysklad_stock_by_model()
    except Exception:
        moysklad = {}

    by_model = {}
    all_models = set(list(wb_turnover.keys()) + list(ozon_turnover.keys()))
    for model in all_models:
        wb = wb_turnover.get(model, {})
        ozon = ozon_turnover.get(model, {})
        ms = moysklad.get(model, {})

        wb_stock = wb.get("avg_stock", 0)
        ozon_stock = ozon.get("avg_stock", 0)
        ms_stock = ms.get("stock", 0) if isinstance(ms, dict) else 0

        by_model[model] = {
            "wb_stock": wb_stock,
            "ozon_stock": ozon_stock,
            "moysklad_stock": ms_stock,
            "total_stock": wb_stock + ozon_stock + ms_stock,
            "wb_turnover_days": wb.get("turnover_days", 0),
            "ozon_turnover_days": ozon.get("turnover_days", 0),
            "wb_daily_sales": wb.get("daily_sales", 0),
        }

    result = {"by_model": by_model}

    if depth == "month":
        try:
            from shared.data_layer import get_active_models_with_abc
            abc_data = get_active_models_with_abc(start, end)
            result["abc"] = abc_data
        except Exception:
            result["abc"] = {}

    return result
```

- [ ] **Step 3: Implement pricing collector**

```python
# scripts/analytics_report/collectors/pricing.py
"""Pricing collector: price changes + SPP history."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def collect_pricing(start: str, end: str, prev_start: str, prev_end: str) -> dict:
    """Collect price changes and SPP history for the period."""
    from shared.data_layer import (
        get_wb_price_changes,
        get_wb_spp_history_by_model,
        get_wb_price_margin_by_model_period,
    )

    try:
        price_changes = get_wb_price_changes(start, end)
    except Exception:
        price_changes = []

    try:
        spp_history = get_wb_spp_history_by_model(start, end)
    except Exception:
        spp_history = []

    try:
        price_margin = get_wb_price_margin_by_model_period(start, prev_start, end)
    except Exception:
        price_margin = []

    return {
        "changes": [
            {"model": r[0], "date": str(r[1]) if r[1] else None,
             "old_price": float(r[2] or 0), "new_price": float(r[3] or 0)}
            for r in (price_changes or []) if len(r) >= 4
        ],
        "spp_history": [
            {"model": r[0], "date": str(r[1]) if r[1] else None,
             "spp_pct": float(r[2] or 0)}
            for r in (spp_history or []) if len(r) >= 3
        ],
    }
```

- [ ] **Step 4: Commit**

```bash
git add scripts/analytics_report/collectors/funnel.py scripts/analytics_report/collectors/inventory.py scripts/analytics_report/collectors/pricing.py
git commit -m "feat(analytics-report): add funnel, inventory, pricing collectors (Task 5)"
```

---

### Task 6: Collect All Orchestrator

**Files:**
- Create: `scripts/analytics_report/collect_all.py`

- [ ] **Step 1: Implement collect_all.py**

```python
#!/usr/bin/env python3
"""Analytics Report — parallel data collection orchestrator.

Usage:
    python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.analytics_report.utils import compute_prev_period, detect_depth, format_date_str

# Depth → collector names
DEPTH_COLLECTORS = {
    "day": ["finance_wb", "finance_ozon", "anomalies"],
    "week": ["finance_wb", "finance_ozon", "funnel", "inventory", "pricing", "anomalies"],
    "month": ["finance_wb", "finance_ozon", "funnel", "inventory", "pricing", "anomalies"],
}


def _run_collector(name: str, func, kwargs: dict) -> tuple[str, dict | None, str | None]:
    try:
        result = func(**kwargs)
        return name, result, None
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Analytics Report data collector")
    parser.add_argument("--start", required=True, help="Start date: YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date: YYYY-MM-DD")
    parser.add_argument("--output", default="/tmp/analytics-report-data.json")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    prev_start, prev_end = compute_prev_period(start, end)
    depth = detect_depth(start, end)

    s_start = format_date_str(start)
    s_end = format_date_str(end)
    s_prev_start = format_date_str(prev_start)
    s_prev_end = format_date_str(prev_end)

    base_kwargs = {
        "start": s_start, "end": s_end,
        "prev_start": s_prev_start, "prev_end": s_prev_end,
    }

    # Import collectors
    active = DEPTH_COLLECTORS[depth]
    collectors = {}

    if "finance_wb" in active:
        from scripts.analytics_report.collectors.finance_wb import collect_finance_wb
        collectors["finance_wb"] = (collect_finance_wb, base_kwargs)

    if "finance_ozon" in active:
        from scripts.analytics_report.collectors.finance_ozon import collect_finance_ozon
        collectors["finance_ozon"] = (collect_finance_ozon, base_kwargs)

    if "funnel" in active:
        from scripts.analytics_report.collectors.funnel import collect_funnel
        collectors["funnel"] = (collect_funnel, base_kwargs)

    if "inventory" in active:
        from scripts.analytics_report.collectors.inventory import collect_inventory
        collectors["inventory"] = (collect_inventory, {**base_kwargs, "depth": depth})

    if "pricing" in active:
        from scripts.analytics_report.collectors.pricing import collect_pricing
        collectors["pricing"] = (collect_pricing, base_kwargs)

    # Run data quality check
    from shared.data_layer import validate_wb_data_quality
    quality = {"warnings": [], "adjustments": {}}
    try:
        dq = validate_wb_data_quality(start)
        if dq:
            quality = dq
    except Exception as e:
        quality["warnings"].append(f"DQ check failed: {e}")

    # SKU statuses
    sku_statuses = {}
    try:
        from shared.data_layer import get_model_statuses
        sku_statuses = get_model_statuses()
    except Exception:
        pass

    # Run collectors in parallel (except anomalies — needs finance results)
    t0 = time.time()
    results = {}
    errors = {}

    non_anomaly = {k: v for k, v in collectors.items() if k != "anomalies"}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_run_collector, name, func, kwargs): name
            for name, (func, kwargs) in non_anomaly.items()
        }
        for future in as_completed(futures):
            name, result, error = future.result()
            if error:
                errors[name] = error
                print(f"[WARN] Collector {name} failed: {error}", file=sys.stderr)
            else:
                results[name] = result
                print(f"[OK] Collector {name} done")

    # Run anomaly detector after finance
    if "anomalies" in active:
        from scripts.analytics_report.collectors.anomalies import detect_anomalies
        anomalies = detect_anomalies(
            results.get("finance_wb", {}),
            results.get("finance_ozon", {}),
        )
        results["anomalies"] = anomalies

    # Add model statuses to finance data
    for channel in ("finance_wb", "finance_ozon"):
        if channel in results and "models" in results[channel]:
            for model_name in results[channel]["models"]:
                results[channel]["models"][model_name]["status"] = sku_statuses.get(model_name, "Неизвестно")

    duration = round(time.time() - t0, 1)

    output = {
        **results,
        "meta": {
            "start": s_start,
            "end": s_end,
            "prev_start": s_prev_start,
            "prev_end": s_prev_end,
            "depth": depth,
            "errors": errors,
            "quality": quality,
            "collection_duration_sec": duration,
        },
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\n[DONE] Output: {output_path} ({output_path.stat().st_size / 1024:.0f} KB, {duration}s)")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test (requires DB access)**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05`
Expected: JSON file at `/tmp/analytics-report-data.json`, all collectors `[OK]`

- [ ] **Step 3: Commit**

```bash
git add scripts/analytics_report/collect_all.py
git commit -m "feat(analytics-report): add collect_all orchestrator (Task 6)"
```

---

### Task 7: Analyst Prompt

**Files:**
- Create: `.claude/skills/analytics-report/prompts/analyst.md`

- [ ] **Step 1: Write analyst prompt**

```markdown
<!-- .claude/skills/analytics-report/prompts/analyst.md -->
# Финансовый аналитик Wookiee

Ты — финансовый аналитик e-commerce бренда Wookiee (женская одежда, WB + OZON).
Твоя задача: написать аналитический отчёт на основе данных из JSON-бандла.

## Входные данные

Файл: `{{DATA_FILE}}`
Прочитай его полностью через Read tool.

## Обязательные правила

1. **Выкуп %** — ЛАГОВЫЙ показатель (задержка 3-21 дней). НЕЛЬЗЯ использовать как причину изменения маржинальности. Показывать только как информационный с пометкой "⚠️ лаг 3-21 дн".
2. **ДРР** — ВСЕГДА с разбивкой: внутренняя (МП) и внешняя (блогеры, ВК) отдельно.
3. **СПП** — НЕ управляемый нами показатель. Рост СПП = рост спроса = рост заказов. Влияет на конечную цену для покупателя.
4. **Комиссия** — НЕ управляемый показатель. Фиксируй, но не рекомендуй действия.
5. **Наши инструменты = ЦЕНА + МАРКЕТИНГ**. Все рекомендации только через эти 2 рычага.
6. Товары со статусом "Выводим" — задача распродать быстрее, можно жертвовать маржой.
7. Товары "Продается" — целевая маржа ≥ 20%, оборачиваемость в диапазоне.
8. **Аномалии** (из `anomalies` секции JSON) — ОБЯЗАТЕЛЬНО упомяни каждую с гипотезой причины.
9. **Рекомендации** — "что если" сценарии с расчётом эффекта в ₽.
10. **Реклама → Заказы**: если реклама выросла, проверь выросли ли заказы. Реклама + рост заказов = эффективно. Реклама растёт, заказы нет = неэффективно.

## Формат чисел

- Деньги: `1 234 567 ₽` (пробелы-разделители)
- Проценты: `24.1%`
- Изменения: `+500 000 ₽ (+10.5%)` или `-200 000 ₽ (-4.2%)`
- Доли: `8.0% → 11.2% (+3.2 п.п.)`

## Структура отчёта

Посмотри поле `meta.depth` в JSON:

### Если depth = "day"

```markdown
# Аналитический отчёт: {start}

## Сводка
Ключевые цифры бренда (WB+OZON): выручка, маржа, маржа%, заказы шт.
Топ-3 изменения vs вчера (по ₽ эффекту).

## Финансовая воронка (бренд)
Таблица: метрика | WB | OZON | Итого | Δ vs вчера
Все строки: ₽ + доля% + изменение

## По моделям
Таблица: модель | статус | выручка | маржа% | заказы | Δ

## Аномалии
Каждая аномалия из JSON + гипотеза + рекомендация
```

### Если depth = "week"

Добавь:
- ## По каналам (WB / OZON) — полная воронка отдельно
- ## Воронка трафика — показы → корзина → заказы → выкупы, CR
- ## Оборачиваемость — по моделям с рекомендацией

### Если depth = "month"

Добавь:
- ## Детализация по артикулам — топ/анти-топ по маржинальности
- ## ABC-классификация
- ## Ценовые изменения — все изменения + эффект

## Notion-форматирование

- Заголовки ## — делай toggle (сворачиваемые)
- Таблицы: полноширинные, с заголовком строки и столбца
- Цвета:
  - 🟢 зелёный фон — положительные изменения
  - 🔴 красный фон — отрицательные
  - 🟡 жёлтый фон — предупреждения
  - ⬜ серый фон — итоговые строки
- Callout-блоки для предупреждений (выкупы, data quality)

## Важно

- ВСЕ цифры берутся ТОЛЬКО из JSON. Не придумывай данные.
- Если секция в JSON пустая или отсутствует — пропусти этот раздел.
- Проверь что `meta.quality.warnings` отражены в отчёте.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/prompts/analyst.md
git commit -m "feat(analytics-report): add analyst prompt (Task 7)"
```

---

### Task 8: Verifier Prompt

**Files:**
- Create: `.claude/skills/analytics-report/prompts/verifier.md`

- [ ] **Step 1: Write verifier prompt**

```markdown
<!-- .claude/skills/analytics-report/prompts/verifier.md -->
# Верификатор аналитического отчёта

Ты — дата-аналитик, проверяющий отчёт на точность и полноту.

## Входные данные

1. JSON-бандл: `{{DATA_FILE}}`
2. Draft отчёта: `{{DRAFT_FILE}}`

Прочитай оба файла через Read tool.

## Чеклист проверок

### 1. Точность цифр (±1% допуск)
Для каждой цифры в отчёте найди соответствующее значение в JSON.
Допуск: ±1% на округление. Если отклонение > 1% — это ошибка.

### 2. Отсутствие артефактов
Ищи в тексте: "0%", "—", "н/д", "NaN", "None", "null" — вместо реальных данных.
Если данные действительно отсутствуют — должно быть явно написано "данные отсутствуют".

### 3. Суммарные доли
Доли расходов (комиссия + логистика + хранение + себестоимость + реклама + НДС + штрафы) ≈ 100% - маржа%. Допуск ±2%.

### 4. Аномалии упомянуты
Каждая аномалия из `anomalies` массива в JSON должна быть упомянута в отчёте.

### 5. Логика выводов
- "Маржа выросла" → margin текущий > previous ✓
- "Логистика снизилась" → logistics_share текущий < previous ✓
- Рекомендации соответствуют инструментам (цена / маркетинг)

### 6. Notion-форматирование
- Заголовки ## с toggle
- Таблицы с header-row
- Цвета (зелёный/красный/жёлтый)
- Callout для предупреждений

## Выходной формат

Ответь СТРОГО в формате JSON:
```json
{
  "passed": true | false,
  "score": 85,
  "corrections": [
    {"section": "Финансовая воронка", "issue": "Логистика указана 400К, в данных 380К", "severity": "error"},
    {"section": "По моделям", "issue": "Модель Ivy отсутствует в таблице", "severity": "warning"}
  ]
}
```

- `passed`: true если нет error-level issues
- `score`: 0-100 (100 = идеально)
- `corrections`: все найденные проблемы
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/prompts/verifier.md
git commit -m "feat(analytics-report): add verifier prompt (Task 8)"
```

---

### Task 9: SKILL.md Orchestrator

**Files:**
- Create: `.claude/skills/analytics-report/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: analytics-report
description: Generate financial analytics report for any period. Collects WB/OZON data, analyzes with LLM, verifies, publishes to Notion.
triggers:
  - /analytics-report
  - аналитический отчёт
  - analytics report
  - финансовый анализ
---

# Analytics Report Skill

Generate a financial analytics report for any date range with adaptive depth.

## Stage 0: Parse Arguments

Parse the user's input to extract dates:
- `/analytics-report 2026-04-05` → single day (start=end=2026-04-05)
- `/analytics-report 2026-03-30 2026-04-05` → date range

If no dates provided, ask:
```
question: "За какой период сделать отчёт?"
header: "Период"
options:
  - label: "Вчера" / description: "Один день"
  - label: "Прошлая неделя" / description: "Пн-Вс"
  - label: "Прошлый месяц" / description: "Полный месяц"
  (+ Other для custom дат YYYY-MM-DD YYYY-MM-DD)
```

## Stage 1: Data Collection

Run the collector orchestrator:

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 scripts/analytics_report/collect_all.py \
  --start "{{start_date}}" \
  --end "{{end_date}}" \
  --output /tmp/analytics-report-data.json
```

Check exit code:
- Exit 0: all collectors succeeded → proceed
- Exit 1: some failed → check stderr warnings, continue with available data

Read `/tmp/analytics-report-data.json` and verify `meta.errors` is empty or acceptable.

## Stage 2: Analysis + Verification

### 2a. Analyst Agent

Launch a subagent (Agent tool) with the analyst prompt:

```
Read the prompt: .claude/skills/analytics-report/prompts/analyst.md
Replace {{DATA_FILE}} with: /tmp/analytics-report-data.json
Generate the report as markdown.
Save draft to: /tmp/analytics-report-draft.md
```

Model preference: Use default (main context model).

### 2b. Verifier Agent

Launch a subagent with the verifier prompt:

```
Read the prompt: .claude/skills/analytics-report/prompts/verifier.md
Replace {{DATA_FILE}} with: /tmp/analytics-report-data.json
Replace {{DRAFT_FILE}} with: /tmp/analytics-report-draft.md
Return JSON verdict.
```

### 2c. Retry Logic

If verifier returns `passed: false`:
1. Send corrections to analyst agent with instruction to fix
2. Save corrected version to `/tmp/analytics-report-draft.md`
3. Do NOT re-verify (max 1 retry)
4. If still has issues, add "⚠️ Требует ручной проверки" header

If `passed: true`: use draft as final.

## Stage 3: Publication

### 3a. Save MD file

Save final report to: `docs/reports/{{start_date}}_{{end_date}}_analytics.md`

### 3b. Publish to Notion

```python
# Run inline or via bash
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from shared.notion_client import NotionClient

async def publish():
    client = NotionClient()
    url = await client.sync_report(
        start_date='{{start_date}}',
        end_date='{{end_date}}',
        report_md=open('/tmp/analytics-report-draft.md').read(),
        report_type='{{notion_type}}',
        source='Analytics Skill v1'
    )
    print(url)

asyncio.run(publish())
"
```

Where `{{notion_type}}` depends on depth:
- day → "daily"
- week → "weekly"
- month → "monthly"

### 3c. Summary

Show the user:
- 📊 **Отчёт готов**
- Период: {start} — {end} ({depth})
- Notion: {url}
- Файл: docs/reports/{start}_{end}_analytics.md
- Ключевые цифры: выручка, маржа%, топ аномалия
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/analytics-report/SKILL.md
git commit -m "feat(analytics-report): add SKILL.md orchestrator (Task 9)"
```

---

### Task 10: Integration Test

- [ ] **Step 1: Run full pipeline on test period**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python scripts/analytics_report/collect_all.py --start 2026-03-30 --end 2026-04-05
```

Verify:
- All 6 collectors return `[OK]`
- `/tmp/analytics-report-data.json` contains all expected sections
- `meta.depth` == "week"
- `meta.errors` is empty
- `finance_wb.brand.current.revenue_before_spp` > 0
- `anomalies` array exists (may be empty)

- [ ] **Step 2: Run all unit tests**

```bash
python -m pytest tests/test_analytics_report/ -v
```

Expected: All tests PASS (9 utils + 3 wb + 2 ozon + 3 anomalies = 17 tests)

- [ ] **Step 3: Test the skill manually**

In Claude Code, run: `/analytics-report 2026-03-30 2026-04-05`

Verify:
- Data collected successfully
- Analyst produces report with correct structure
- Verifier validates or catches issues
- Report published to Notion
- MD file saved to docs/reports/

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(analytics-report): integration test passed, skill complete (Task 10)"
```
