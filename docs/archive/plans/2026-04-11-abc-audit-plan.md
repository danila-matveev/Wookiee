# ABC-аудит товарной матрицы — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать скилл `/abc-audit` — глубокий товарный ABC-анализ с командой из 6 субагентов, классификацией по матрице ABC x ROI, учётом color_code связок в коллекциях и адаптивной глубиной анализа.

**Architecture:** Python-коллектор собирает данные из WB/OZON БД + Supabase → Data Analyst обогащает и классифицирует → 3 эксперта (Товаровед, Финансист, Маркетолог) параллельно анализируют → Арбитр принимает решения → Synthesizer собирает MD-отчёт.

**Tech Stack:** Python 3.11+, psycopg2 (PostgreSQL), Supabase (direct SQL), ThreadPoolExecutor, Claude Code subagents.

**Spec:** `docs/superpowers/specs/2026-04-11-abc-audit-skill-design.md`

---

## File Structure

### New files to create:

```
scripts/abc_audit/
  __init__.py                    # Package marker
  utils.py                       # Date params, quality flags, helpers
  collect_data.py                # Main collector orchestrator
  collectors/
    __init__.py                  # Package marker
    finance.py                   # WB+OZON revenue, margin, cost structure per article
    inventory.py                 # WB+OZON+MoySklad stocks, turnover calculation
    advertising.py               # DRR per article (internal + external)
    hierarchy.py                 # Supabase product hierarchy, color_code groups
    buyouts.py                   # Buyout %, barcode-level (size) data

.claude/skills/abc-audit/
  SKILL.md                       # Orchestrator (5 stages)
  prompts/
    data_analyst.md              # Stage 2: data validation + metrics + ABC classification
    merchandiser.md              # Stage 3: Товаровед — hierarchy, collections, MOQ
    financier.md                 # Stage 3: Финансист — unit economics, pricing, ROI
    marketer.md                  # Stage 3: Маркетолог — DRR, conversion, budget allocation
    arbiter.md                   # Stage 4: Арбитр — final decisions, contradictions, confidence
    synthesizer.md               # Stage 5: MD report assembly
  references/
    abc-kb.md                    # Knowledge base: thresholds, formulas, business rules

tests/
  test_abc_audit_collector.py    # Unit tests for collector
```

---

## Task 1: Collector Utils

**Files:**
- Create: `scripts/abc_audit/__init__.py`
- Create: `scripts/abc_audit/utils.py`
- Create: `scripts/abc_audit/collectors/__init__.py`
- Test: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Create package markers**

```python
# scripts/abc_audit/__init__.py
"""ABC-аудит товарной матрицы — сбор данных."""

# scripts/abc_audit/collectors/__init__.py
"""Коллекторы данных для ABC-аудита."""
```

- [ ] **Step 2: Write failing test for date params**

```python
# tests/test_abc_audit_collector.py
"""Tests for ABC audit collector."""
from __future__ import annotations

import pytest
from datetime import date


def test_compute_abc_date_params_default():
    """30/90/180 day windows from reference date."""
    from scripts.abc_audit.utils import compute_abc_date_params

    params = compute_abc_date_params("2026-04-11")

    assert params["cut_date"] == "2026-04-11"
    assert params["p30_start"] == "2026-03-12"
    assert params["p90_start"] == "2026-01-11"
    assert params["p180_start"] == "2025-10-14"
    assert params["p30_end_exclusive"] == "2026-04-12"
    assert params["year_ago_start"] == "2025-03-12"
    assert params["year_ago_end"] == "2025-04-11"
    assert params["days_30"] == 30
    assert params["days_90"] == 90
    assert params["days_180"] == 180


def test_compute_abc_date_params_custom_date():
    """Custom reference date."""
    from scripts.abc_audit.utils import compute_abc_date_params

    params = compute_abc_date_params("2026-01-15")

    assert params["cut_date"] == "2026-01-15"
    assert params["p30_start"] == "2025-12-16"
    assert params["p90_start"] == "2025-10-17"


def test_build_abc_quality_flags_no_errors():
    """No errors → clean flags."""
    from scripts.abc_audit.utils import build_abc_quality_flags

    flags = build_abc_quality_flags(errors={}, article_count=142, supabase_count=142)

    assert flags["collector_errors"] == {}
    assert flags["coverage_pct"] == 100.0
    assert flags["ozon_buyout_available"] is False


def test_build_abc_quality_flags_with_errors():
    """Errors tracked, coverage calculated."""
    from scripts.abc_audit.utils import build_abc_quality_flags

    flags = build_abc_quality_flags(
        errors={"finance": "connection timeout"},
        article_count=120,
        supabase_count=142,
    )

    assert "finance" in flags["collector_errors"]
    assert abs(flags["coverage_pct"] - 84.5) < 0.1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_abc_audit_collector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.abc_audit'`

- [ ] **Step 4: Implement utils.py**

```python
# scripts/abc_audit/utils.py
"""Утилиты для ABC-аудита: даты, quality flags, helpers."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


def compute_abc_date_params(cut_date_str: str) -> dict:
    """Вычисляет все даты для ABC-аудита (30/90/180 дней назад от даты отсечки).

    Args:
        cut_date_str: Дата отсечки в формате YYYY-MM-DD.

    Returns:
        Словарь с датами всех периодов.
    """
    cut = date.fromisoformat(cut_date_str)

    p30_start = cut - timedelta(days=30)
    p90_start = cut - timedelta(days=90)
    p180_start = cut - timedelta(days=180)
    end_exclusive = cut + timedelta(days=1)

    year_ago_end = cut - timedelta(days=365)
    year_ago_start = year_ago_end - timedelta(days=30)

    return {
        "cut_date": cut.isoformat(),
        "p30_start": p30_start.isoformat(),
        "p90_start": p90_start.isoformat(),
        "p180_start": p180_start.isoformat(),
        "p30_end_exclusive": end_exclusive.isoformat(),
        "p90_end_exclusive": end_exclusive.isoformat(),
        "p180_end_exclusive": end_exclusive.isoformat(),
        "year_ago_start": year_ago_start.isoformat(),
        "year_ago_end": year_ago_end.isoformat(),
        "days_30": 30,
        "days_90": 90,
        "days_180": 180,
    }


def build_abc_quality_flags(
    errors: dict,
    article_count: int,
    supabase_count: int,
    moysklad_stale: bool = False,
) -> dict:
    """Строит quality flags для ABC-аудита.

    Args:
        errors: Словарь ошибок коллекторов {name: error_msg}.
        article_count: Количество артикулов с данными по продажам.
        supabase_count: Количество артикулов в Supabase (активные статусы).
        moysklad_stale: True если данные МойСклад устарели (>3 дней).

    Returns:
        Словарь с флагами качества.
    """
    coverage = (article_count / supabase_count * 100) if supabase_count > 0 else 0.0

    return {
        "collector_errors": dict(errors),
        "coverage_pct": round(coverage, 1),
        "ozon_buyout_available": False,
        "moysklad_stale": moysklad_stale,
        "buyout_lag_3_21_days": True,
    }


def safe_float(val) -> Optional[float]:
    """Безопасное приведение к float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Безопасное деление с дефолтом при нуле."""
    if not denominator:
        return default
    return numerator / denominator
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_abc_audit_collector.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/abc_audit/__init__.py scripts/abc_audit/utils.py scripts/abc_audit/collectors/__init__.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add collector utils — date params, quality flags, helpers"
```

---

## Task 2: Finance Collector

**Files:**
- Create: `scripts/abc_audit/collectors/finance.py`
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_abc_audit_collector.py
from unittest.mock import patch, MagicMock


def test_collect_finance_merges_wb_ozon():
    """Finance collector merges WB + OZON article data by article key."""
    from scripts.abc_audit.collectors.finance import collect_finance

    wb_articles = [
        {
            "article": "wendy/black",
            "model": "wendy",
            "orders_count": 100,
            "sales_count": 85,
            "revenue_before_spp": 50000.0,
            "margin": 12000.0,
            "adv_internal": 2000.0,
            "adv_external": 1000.0,
            "adv_vk": 500.0,
            "adv_creators": 0.0,
            "cost_of_goods": 15000.0,
            "logistics": 5000.0,
            "storage": 800.0,
            "commission": 3000.0,
            "nds": 2000.0,
        }
    ]
    ozon_articles = [
        {
            "article": "wendy/black",
            "model": "wendy",
            "sales_count": 15,
            "revenue_before_spp": 9000.0,
            "margin": 2200.0,
            "adv_internal": 400.0,
            "adv_external": 0.0,
            "adv_vk": 0.0,
            "cost_of_goods": 2700.0,
            "logistics": 900.0,
            "storage": 100.0,
            "nds": 400.0,
        }
    ]

    with (
        patch(
            "scripts.abc_audit.collectors.finance.get_wb_by_article",
            return_value=wb_articles,
        ),
        patch(
            "scripts.abc_audit.collectors.finance.get_ozon_by_article",
            return_value=ozon_articles,
        ),
    ):
        result = collect_finance(
            "2026-03-12", "2026-04-12",
            "2026-01-11", "2026-04-12",
            "2025-10-14", "2026-04-12",
        )

    data = result["finance"]
    assert "wendy/black" in data
    art = data["wendy/black"]
    assert art["revenue_30d"] == 50000.0 + 9000.0
    assert art["margin_30d"] == 12000.0 + 2200.0
    assert art["adv_internal_30d"] == 2000.0 + 400.0


def test_collect_finance_ozon_only_article():
    """Article present only on OZON should still appear."""
    from scripts.abc_audit.collectors.finance import collect_finance

    ozon_articles = [
        {
            "article": "audrey/red",
            "model": "audrey",
            "sales_count": 5,
            "revenue_before_spp": 3000.0,
            "margin": 800.0,
            "adv_internal": 100.0,
            "adv_external": 0.0,
            "adv_vk": 0.0,
            "cost_of_goods": 900.0,
            "logistics": 300.0,
            "storage": 50.0,
            "nds": 130.0,
        }
    ]

    with (
        patch(
            "scripts.abc_audit.collectors.finance.get_wb_by_article",
            return_value=[],
        ),
        patch(
            "scripts.abc_audit.collectors.finance.get_ozon_by_article",
            return_value=ozon_articles,
        ),
    ):
        result = collect_finance(
            "2026-03-12", "2026-04-12",
            "2026-01-11", "2026-04-12",
            "2025-10-14", "2026-04-12",
        )

    data = result["finance"]
    assert "audrey/red" in data
    assert data["audrey/red"]["margin_30d"] == 800.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abc_audit_collector.py::test_collect_finance_merges_wb_ozon -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement finance collector**

```python
# scripts/abc_audit/collectors/finance.py
"""Коллектор финансовых данных: выручка, маржа, себестоимость по артикулам."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.article import get_wb_by_article, get_ozon_by_article
from scripts.abc_audit.utils import safe_float


# Ключи, которые суммируются при merge WB + OZON
_SUM_KEYS = (
    "sales_count", "revenue_before_spp", "margin",
    "adv_internal", "adv_external", "adv_vk", "adv_creators",
    "cost_of_goods", "logistics", "storage", "commission", "nds",
)


def _empty_article() -> dict:
    return {k: 0.0 for k in _SUM_KEYS}


def _merge_channel(target: dict, source: dict) -> None:
    """Суммирует числовые поля из source в target."""
    for key in _SUM_KEYS:
        val = safe_float(source.get(key))
        if val is not None:
            target[key] = target.get(key, 0.0) + val


def _collect_period(
    wb_start: str, wb_end: str, ozon_start: str, ozon_end: str,
) -> dict[str, dict]:
    """Собирает WB+OZON данные за один период и мержит по артикулу."""
    merged: dict[str, dict] = defaultdict(_empty_article)

    for row in get_wb_by_article(wb_start, wb_end):
        article = row.get("article", "").lower()
        if not article:
            continue
        _merge_channel(merged[article], row)
        merged[article]["model"] = row.get("model", "")

    for row in get_ozon_by_article(ozon_start, ozon_end):
        article = row.get("article", "").lower()
        if not article:
            continue
        _merge_channel(merged[article], row)
        if "model" not in merged[article] or not merged[article]["model"]:
            merged[article]["model"] = row.get("model", "")

    return dict(merged)


def collect_finance(
    p30_start: str, p30_end: str,
    p90_start: str, p90_end: str,
    p180_start: str, p180_end: str,
) -> dict:
    """Собирает финансовые данные по артикулам за 3 периода.

    Returns:
        {"finance": {article: {revenue_30d, margin_30d, ..., revenue_90d, ...}}}
    """
    data_30 = _collect_period(p30_start, p30_end, p30_start, p30_end)
    data_90 = _collect_period(p90_start, p90_end, p90_start, p90_end)
    data_180 = _collect_period(p180_start, p180_end, p180_start, p180_end)

    # Объединяем все артикулы из всех периодов
    all_articles = set(data_30) | set(data_90) | set(data_180)
    result: dict[str, dict] = {}

    for article in all_articles:
        entry: dict = {"article": article}
        d30 = data_30.get(article, _empty_article())
        d90 = data_90.get(article, _empty_article())
        d180 = data_180.get(article, _empty_article())

        entry["model"] = d30.get("model") or d90.get("model") or d180.get("model", "")

        for key in _SUM_KEYS:
            entry[f"{key}_30d"] = d30.get(key, 0.0)
            entry[f"{key}_90d"] = d90.get(key, 0.0)
            entry[f"{key}_180d"] = d180.get(key, 0.0)

        # Вычисляемые метрики
        rev30 = entry["revenue_before_spp_30d"]
        mar30 = entry["margin_30d"]
        entry["margin_pct_30d"] = round(mar30 / rev30 * 100, 1) if rev30 else 0.0

        rev90 = entry["revenue_before_spp_90d"]
        mar90 = entry["margin_90d"]
        entry["margin_pct_90d"] = round(mar90 / rev90 * 100, 1) if rev90 else 0.0

        adv30 = entry.get("adv_internal_30d", 0.0) + entry.get("adv_external_30d", 0.0) + entry.get("adv_vk_30d", 0.0) + entry.get("adv_creators_30d", 0.0)
        entry["drr_30d"] = round(adv30 / rev30 * 100, 1) if rev30 else 0.0

        result[article] = entry

    return {"finance": result}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "finance" -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/abc_audit/collectors/finance.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add finance collector — WB+OZON merge, 3 periods"
```

---

## Task 3: Inventory Collector

**Files:**
- Create: `scripts/abc_audit/collectors/inventory.py`
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_abc_audit_collector.py

def test_collect_inventory_total_stock():
    """Inventory collector sums WB + OZON + MoySklad stocks."""
    from scripts.abc_audit.collectors.inventory import collect_inventory

    with (
        patch(
            "scripts.abc_audit.collectors.inventory.get_wb_avg_stock",
            return_value={"wendy/black": 200.0, "audrey/red": 50.0},
        ),
        patch(
            "scripts.abc_audit.collectors.inventory.get_ozon_avg_stock",
            return_value={"wendy/black": 80.0},
        ),
        patch(
            "scripts.abc_audit.collectors.inventory.get_moysklad_stock_by_article",
            return_value={
                "wendy/black": {
                    "stock_main": 150, "stock_transit": 50,
                    "total": 200, "snapshot_date": "2026-04-11", "is_stale": False,
                },
            },
        ),
    ):
        result = collect_inventory("2026-03-12", "2026-04-12")

    data = result["inventory"]
    assert data["wendy/black"]["stock_wb"] == 200.0
    assert data["wendy/black"]["stock_ozon"] == 80.0
    assert data["wendy/black"]["stock_moysklad"] == 200
    assert data["wendy/black"]["stock_total"] == 480.0
    assert data["audrey/red"]["stock_total"] == 50.0
    assert data["meta"]["moysklad_stale"] is False


def test_collect_inventory_turnover_calc():
    """Turnover = total_stock / daily_sales. MOQ months calc."""
    from scripts.abc_audit.collectors.inventory import calc_turnover_metrics

    metrics = calc_turnover_metrics(stock_total=480.0, daily_sales=16.0)

    assert metrics["turnover_days"] == 30.0
    assert metrics["moq_months"] == pytest.approx(500 / (16.0 * 30), rel=0.01)
    assert metrics["roi_annual"] == pytest.approx(0, abs=1)  # needs margin_pct


def test_calc_turnover_with_margin():
    """ROI annual = margin_pct * (365 / turnover_days)."""
    from scripts.abc_audit.collectors.inventory import calc_turnover_metrics

    metrics = calc_turnover_metrics(
        stock_total=480.0, daily_sales=16.0, margin_pct=25.0,
    )

    # turnover_days = 480/16 = 30
    # ROI = 25 * (365/30) = 304.2
    assert metrics["roi_annual"] == pytest.approx(304.2, rel=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "inventory" -v`
Expected: FAIL

- [ ] **Step 3: Implement inventory collector**

```python
# scripts/abc_audit/collectors/inventory.py
"""Коллектор запасов: WB + OZON + МойСклад, оборачиваемость, ROI."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.inventory import (
    get_wb_avg_stock,
    get_ozon_avg_stock,
    get_moysklad_stock_by_article,
)

MOQ = 500  # Минимальный заказ, шт (будет в Supabase позже)


def calc_turnover_metrics(
    stock_total: float,
    daily_sales: float,
    margin_pct: float = 0.0,
) -> dict:
    """Считает оборачиваемость, месяцы на MOQ, годовой ROI.

    Args:
        stock_total: Суммарный сток (WB + OZON + МойСклад).
        daily_sales: Среднедневные продажи (шт).
        margin_pct: Маржинальность (%).

    Returns:
        {turnover_days, moq_months, roi_annual}
    """
    if daily_sales <= 0:
        return {
            "turnover_days": 999.0,
            "moq_months": 999.0,
            "roi_annual": 0.0,
        }

    turnover_days = round(stock_total / daily_sales, 1)
    moq_months = round(MOQ / (daily_sales * 30), 2)
    roi_annual = round(margin_pct * (365 / turnover_days), 1) if turnover_days > 0 else 0.0

    return {
        "turnover_days": turnover_days,
        "moq_months": moq_months,
        "roi_annual": roi_annual,
    }


def collect_inventory(start_date: str, end_date: str) -> dict:
    """Собирает стоки со всех складов.

    Args:
        start_date: Начало периода (для snapshot WB/OZON).
        end_date: Конец периода.

    Returns:
        {"inventory": {article: {stock_wb, stock_ozon, stock_moysklad, stock_total}}, "meta": {...}}
    """
    wb_stocks = get_wb_avg_stock(start_date, end_date)
    ozon_stocks = get_ozon_avg_stock(start_date, end_date)
    ms_stocks = get_moysklad_stock_by_article()

    moysklad_stale = any(v.get("is_stale", False) for v in ms_stocks.values())

    all_articles = set(wb_stocks) | set(ozon_stocks) | set(ms_stocks)
    result: dict[str, dict] = {}

    for article in all_articles:
        s_wb = wb_stocks.get(article, 0.0)
        s_ozon = ozon_stocks.get(article, 0.0)
        ms_data = ms_stocks.get(article, {})
        s_ms = ms_data.get("total", 0) if isinstance(ms_data, dict) else 0

        result[article] = {
            "stock_wb": s_wb,
            "stock_ozon": s_ozon,
            "stock_moysklad": s_ms,
            "stock_total": s_wb + s_ozon + s_ms,
        }

    return {
        "inventory": result,
        "meta": {"moysklad_stale": moysklad_stale},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "inventory" -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/abc_audit/collectors/inventory.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add inventory collector — stocks, turnover, ROI calc"
```

---

## Task 4: Hierarchy Collector (Supabase)

**Files:**
- Create: `scripts/abc_audit/collectors/hierarchy.py`
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_abc_audit_collector.py

def test_collect_hierarchy_groups_by_color_code():
    """Hierarchy collector groups tricot articles by color_code."""
    from scripts.abc_audit.collectors.hierarchy import collect_hierarchy

    fake_info = {
        "vuki/black": {
            "status": "Продается", "model_kod": "VukiN",
            "model_osnova": "Vuki", "color_code": "2",
            "cvet": "черный", "color": "black",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
        "moon/black": {
            "status": "Продается", "model_kod": "MoonN",
            "model_osnova": "Moon", "color_code": "2",
            "cvet": "черный", "color": "black",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
        "wendy/red": {
            "status": "Продается", "model_kod": "WendyN",
            "model_osnova": "Wendy", "color_code": "WE005",
            "cvet": "красный", "color": "red",
            "skleyka_wb": None, "tip_kollekcii": "seamless_wendy",
        },
    }

    with patch(
        "scripts.abc_audit.collectors.hierarchy.get_artikuly_full_info",
        return_value=fake_info,
    ):
        result = collect_hierarchy()

    h = result["hierarchy"]

    # Все артикулы должны быть в articles
    assert "vuki/black" in h["articles"]
    assert h["articles"]["vuki/black"]["tip_kollekcii"] == "tricot"

    # Color_code группы для tricot
    cc_key = ("tricot", "2")
    assert cc_key in h["color_code_groups"]
    group = h["color_code_groups"][cc_key]
    assert set(group["models"]) == {"Vuki", "Moon"}
    assert len(group["articles"]) == 2

    # Wendy не в tricot color_code группе
    assert ("seamless_wendy", "WE005") in h["color_code_groups"]

    # Status counts
    assert h["status_counts"]["Продается"] == 3


def test_collect_hierarchy_excludes_archive():
    """Archive articles excluded from active analysis."""
    from scripts.abc_audit.collectors.hierarchy import collect_hierarchy

    fake_info = {
        "old/model": {
            "status": "Архив", "model_kod": "OldN",
            "model_osnova": "Old", "color_code": "99",
            "cvet": "серый", "color": "grey",
            "skleyka_wb": None, "tip_kollekcii": "tricot",
        },
    }

    with patch(
        "scripts.abc_audit.collectors.hierarchy.get_artikuly_full_info",
        return_value=fake_info,
    ):
        result = collect_hierarchy()

    h = result["hierarchy"]
    assert h["articles"]["old/model"]["active"] is False
    assert h["status_counts"]["Архив"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "hierarchy" -v`
Expected: FAIL

- [ ] **Step 3: Implement hierarchy collector**

```python
# scripts/abc_audit/collectors/hierarchy.py
"""Коллектор товарной иерархии из Supabase: модели, цвета, коллекции, статусы."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.sku_mapping import get_artikuly_full_info

# Статусы, участвующие в активном анализе
_ACTIVE_STATUSES = {"Продается", "Выводим", "Новый", "Запуск"}


def collect_hierarchy() -> dict:
    """Собирает полную товарную иерархию из Supabase.

    Returns:
        {"hierarchy": {
            "articles": {article: {status, model_osnova, color_code, tip_kollekcii, active}},
            "color_code_groups": {(tip_kollekcii, color_code): {articles, models, statuses}},
            "status_counts": {status: count},
        }}
    """
    raw = get_artikuly_full_info()

    articles: dict[str, dict] = {}
    color_groups: dict[tuple, dict] = defaultdict(
        lambda: {"articles": [], "models": set(), "statuses": set()}
    )
    status_counts: dict[str, int] = defaultdict(int)

    for article, info in raw.items():
        status = info.get("status", "")
        model_osnova = info.get("model_osnova", "")
        color_code = info.get("color_code", "")
        tip_kol = info.get("tip_kollekcii", "")
        active = status in _ACTIVE_STATUSES

        articles[article] = {
            "status": status,
            "model_kod": info.get("model_kod", ""),
            "model_osnova": model_osnova,
            "color_code": color_code,
            "cvet": info.get("cvet", ""),
            "color": info.get("color", ""),
            "tip_kollekcii": tip_kol,
            "active": active,
        }

        status_counts[status] += 1

        if color_code and tip_kol:
            key = (tip_kol, color_code)
            color_groups[key]["articles"].append(article)
            color_groups[key]["models"].add(model_osnova)
            color_groups[key]["statuses"].add(status)

    # Конвертируем set → list для JSON-сериализации
    serializable_groups = {}
    for key, group in color_groups.items():
        serializable_groups[key] = {
            "articles": group["articles"],
            "models": sorted(group["models"]),
            "statuses": sorted(group["statuses"]),
        }

    return {
        "hierarchy": {
            "articles": articles,
            "color_code_groups": serializable_groups,
            "status_counts": dict(status_counts),
        }
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "hierarchy" -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/abc_audit/collectors/hierarchy.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add hierarchy collector — Supabase articles, color_code groups"
```

---

## Task 5: Buyouts + Size Collector

**Files:**
- Create: `scripts/abc_audit/collectors/buyouts.py`
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_abc_audit_collector.py

def test_collect_buyouts_calculates_pct():
    """Buyout collector returns buyout % per article."""
    from scripts.abc_audit.collectors.buyouts import collect_buyouts

    wb_buyouts = [
        ("wendy", "wendy/black", 100, 85, 15),
        ("audrey", "audrey/red", 50, 30, 20),
    ]

    with patch(
        "scripts.abc_audit.collectors.buyouts.get_wb_buyouts_returns_by_artikul",
        return_value=wb_buyouts,
    ):
        result = collect_buyouts("2026-03-12", "2026-04-12")

    data = result["buyouts"]
    assert data["wendy/black"]["buyout_pct"] == 85.0
    assert data["audrey/red"]["buyout_pct"] == 60.0


def test_collect_size_data():
    """Size collector aggregates sales by size from barcode data."""
    from scripts.abc_audit.collectors.buyouts import collect_size_data

    wb_barcodes = [
        {"barcode": "123", "article": "wendy/black", "ts_name": "S", "sales_count": 30, "model": "wendy"},
        {"barcode": "124", "article": "wendy/black", "ts_name": "M", "sales_count": 50, "model": "wendy"},
        {"barcode": "125", "article": "wendy/black", "ts_name": "L", "sales_count": 35, "model": "wendy"},
    ]

    with patch(
        "scripts.abc_audit.collectors.buyouts.get_wb_fin_data_by_barcode",
        return_value=wb_barcodes,
    ):
        result = collect_size_data("2026-03-12", "2026-04-12")

    sizes = result["sizes"]
    assert "wendy/black" in sizes
    size_dist = sizes["wendy/black"]
    assert size_dist["S"] == 30
    assert size_dist["M"] == 50
    assert size_dist["L"] == 35
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "buyout or size" -v`
Expected: FAIL

- [ ] **Step 3: Implement buyouts + size collector**

```python
# scripts/abc_audit/collectors/buyouts.py
"""Коллектор выкупов и размерного распределения."""
from __future__ import annotations

from collections import defaultdict

from shared.data_layer.finance import get_wb_buyouts_returns_by_artikul
from shared.data_layer.article import get_wb_fin_data_by_barcode


def collect_buyouts(start_date: str, end_date: str) -> dict:
    """Собирает данные по выкупам (WB). OZON buyout недоступен.

    Args:
        start_date: Начало периода.
        end_date: Конец периода (exclusive).

    Returns:
        {"buyouts": {article: {orders, buyouts, returns, buyout_pct}}}
    """
    wb_data = get_wb_buyouts_returns_by_artikul(start_date, end_date)
    result: dict[str, dict] = {}

    for row in wb_data:
        # row = (model, artikul, orders_count, buyout_count, return_count)
        article = row[1].lower() if row[1] else ""
        if not article:
            continue

        orders = row[2] or 0
        buyouts = row[3] or 0
        returns = row[4] or 0
        buyout_pct = round(buyouts / orders * 100, 1) if orders > 0 else 0.0

        result[article] = {
            "orders": orders,
            "buyouts": buyouts,
            "returns": returns,
            "buyout_pct": buyout_pct,
        }

    return {"buyouts": result}


def collect_size_data(start_date: str, end_date: str) -> dict:
    """Собирает распределение продаж по размерам (из barcode-level данных WB).

    Returns:
        {"sizes": {article: {size_name: sales_count, ...}}}
    """
    wb_barcodes = get_wb_fin_data_by_barcode(start_date, end_date)
    result: dict[str, dict] = defaultdict(dict)

    for row in wb_barcodes:
        article = (row.get("article") or "").lower()
        size = row.get("ts_name", "")
        sales = row.get("sales_count", 0) or 0

        if article and size:
            result[article][size] = result[article].get(size, 0) + sales

    return {"sizes": dict(result)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_abc_audit_collector.py -k "buyout or size" -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/abc_audit/collectors/buyouts.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add buyout + size collectors — WB buyout %, size distribution"
```

---

## Task 6: Main Collector Orchestrator

**Files:**
- Create: `scripts/abc_audit/collect_data.py`
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_abc_audit_collector.py

def test_main_collector_runs_all_collectors():
    """Main collector calls all sub-collectors and merges."""
    from scripts.abc_audit.collect_data import run_collection

    with (
        patch("scripts.abc_audit.collect_data.collect_finance", return_value={"finance": {"a/b": {"margin_30d": 100}}}),
        patch("scripts.abc_audit.collect_data.collect_inventory", return_value={"inventory": {"a/b": {"stock_total": 50}}, "meta": {"moysklad_stale": False}}),
        patch("scripts.abc_audit.collect_data.collect_hierarchy", return_value={"hierarchy": {"articles": {"a/b": {"status": "Продается"}}, "color_code_groups": {}, "status_counts": {"Продается": 1}}}),
        patch("scripts.abc_audit.collect_data.collect_buyouts", return_value={"buyouts": {"a/b": {"buyout_pct": 85.0}}}),
        patch("scripts.abc_audit.collect_data.collect_size_data", return_value={"sizes": {"a/b": {"M": 10}}}),
    ):
        result = run_collection("2026-04-11")

    assert "finance" in result
    assert "inventory" in result
    assert "hierarchy" in result
    assert "buyouts" in result
    assert "sizes" in result
    assert "meta" in result
    assert result["meta"]["cut_date"] == "2026-04-11"
    assert "errors" in result["meta"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abc_audit_collector.py::test_main_collector_runs_all_collectors -v`
Expected: FAIL

- [ ] **Step 3: Implement main collector**

```python
# scripts/abc_audit/collect_data.py
"""ABC-аудит: главный коллектор данных.

Запуск:
    python scripts/abc_audit/collect_data.py --date 2026-04-11
    python scripts/abc_audit/collect_data.py  # по умолчанию: сегодня
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from scripts.abc_audit.utils import compute_abc_date_params, build_abc_quality_flags
from scripts.abc_audit.collectors.finance import collect_finance
from scripts.abc_audit.collectors.inventory import collect_inventory
from scripts.abc_audit.collectors.hierarchy import collect_hierarchy
from scripts.abc_audit.collectors.buyouts import collect_buyouts, collect_size_data


def run_collection(cut_date_str: str | None = None) -> dict:
    """Запускает все коллекторы параллельно и объединяет результаты.

    Args:
        cut_date_str: Дата отсечки YYYY-MM-DD (по умолчанию — сегодня).

    Returns:
        Единый JSON с блоками finance, inventory, hierarchy, buyouts, sizes, meta.
    """
    if cut_date_str is None:
        cut_date_str = datetime.now().strftime("%Y-%m-%d")

    t0 = time.time()
    params = compute_abc_date_params(cut_date_str)

    p30s = params["p30_start"]
    p90s = params["p90_start"]
    p180s = params["p180_start"]
    end_ex = params["p30_end_exclusive"]

    tasks = {
        "finance": lambda: collect_finance(p30s, end_ex, p90s, end_ex, p180s, end_ex),
        "inventory": lambda: collect_inventory(p30s, end_ex),
        "hierarchy": lambda: collect_hierarchy(),
        "buyouts": lambda: collect_buyouts(p30s, end_ex),
        "sizes": lambda: collect_size_data(p30s, end_ex),
    }

    results: dict = {}
    errors: dict = {}
    inventory_meta: dict = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                block = future.result()
                # Inventory возвращает доп. meta
                if name == "inventory" and "meta" in block:
                    inventory_meta = block.pop("meta")
                results.update(block)
            except Exception as e:
                errors[name] = str(e)
                results[name] = {}

    # Подсчёт покрытия
    hierarchy = results.get("hierarchy", {})
    articles_info = hierarchy.get("articles", {})
    status_counts = hierarchy.get("status_counts", {})
    active_statuses = {"Продается", "Выводим", "Новый", "Запуск"}
    supabase_active = sum(
        v for k, v in status_counts.items() if k in active_statuses
    )
    finance_articles = len(results.get("finance", {}))

    results["meta"] = {
        "cut_date": params["cut_date"],
        "p30_start": p30s,
        "p90_start": p90s,
        "p180_start": p180s,
        "end_exclusive": end_ex,
        "year_ago_start": params["year_ago_start"],
        "year_ago_end": params["year_ago_end"],
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "duration_sec": round(time.time() - t0, 1),
        "errors": errors,
        "quality_flags": build_abc_quality_flags(
            errors=errors,
            article_count=finance_articles,
            supabase_count=supabase_active,
            moysklad_stale=inventory_meta.get("moysklad_stale", False),
        ),
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Сбор данных для ABC-аудита")
    parser.add_argument(
        "--date",
        default=None,
        help="Дата отсечки YYYY-MM-DD (по умолчанию: сегодня)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Путь для сохранения JSON (по умолчанию: /tmp/abc-audit-{DATE}.json)",
    )
    args = parser.parse_args()

    data = run_collection(args.date)

    cut_date = data["meta"]["cut_date"]
    output_path = args.output or f"/tmp/abc-audit-{cut_date}.json"

    output = json.dumps(data, ensure_ascii=False, default=str)
    with open(output_path, "w") as f:
        f.write(output)

    duration = data["meta"]["duration_sec"]
    err_count = len(data["meta"]["errors"])
    print(
        f"ABC-audit data collected: {output_path} "
        f"({len(output)} bytes, {duration}s, {err_count} errors)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_abc_audit_collector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/abc_audit/collect_data.py tests/test_abc_audit_collector.py
git commit -m "feat(abc-audit): add main collector orchestrator — ThreadPool, JSON output"
```

---

## Task 7: ABC Knowledge Base

**Files:**
- Create: `.claude/skills/abc-audit/references/abc-kb.md`

- [ ] **Step 1: Create knowledge base file**

Write `.claude/skills/abc-audit/references/abc-kb.md` with the complete business rules, formulas, thresholds, and terminology. Content based directly on the spec (section 3, 4, 7).

Key sections:
- ABC classification (Pareto 80/15/5)
- ROI formula and zones (>150%, 50-150%, <50%)
- Decision matrix 3x3 with actions
- MOQ thresholds (1 мес / 3 мес / 6 мес / 12 мес)
- Turnover calculation (all warehouses)
- Color_code rules (tricot: 2 independent layers)
- Status handling (Продается / Выводим / Новинка / Архив)
- ИП vs ООО strategic context
- Seasonality protection
- Sell-at-loss strategy
- Formatting rules (Russian terminology, number formats)
- Confidence levels (HIGH/MEDIUM/LOW)

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/abc-audit/references/abc-kb.md
git commit -m "feat(abc-audit): add ABC knowledge base — formulas, thresholds, business rules"
```

---

## Task 8: Data Analyst Prompt

**Files:**
- Create: `.claude/skills/abc-audit/prompts/data_analyst.md`

- [ ] **Step 1: Create Data Analyst prompt**

Prompt structure:
- Role: Дата-аналитик, gate перед экспертным советом
- Input: `{{DATA_BUNDLE}}` — raw JSON from collector
- 7 tasks (integrity check, coverage, depth, metrics, ABC classification, color_code aggregation, quality_flags)
- Metrics per article: выручка, маржа₽, маржинальность%, оборачиваемость, ROI годовой, ДРР%, выкуп%, среднедневные продажи, месяцев на MOQ, тренд, сезонность
- ABC Pareto logic with exact formulas from abc-kb.md
- Gate rule: >30% артикулов без данных → СТОП
- Output format: enriched JSON

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/abc-audit/prompts/data_analyst.md
git commit -m "feat(abc-audit): add Data Analyst prompt — validation, metrics, ABC classification"
```

---

## Task 9: Expert Prompts (Товаровед + Финансист + Маркетолог)

**Files:**
- Create: `.claude/skills/abc-audit/prompts/merchandiser.md`
- Create: `.claude/skills/abc-audit/prompts/financier.md`
- Create: `.claude/skills/abc-audit/prompts/marketer.md`

- [ ] **Step 1: Create Merchandiser (Товаровед) prompt**

Prompt structure:
- Role: Эксперт по товарной иерархии, коллекциям, производственным ограничениям
- Input: `{{ENRICHED_DATA}}` — from Data Analyst
- Tasks: validate hierarchy, color_code analysis (2 layers), model drill-down with benchmark, status handling, MOQ analysis, matrix expansion (colors + sizes)
- Explicit rules: tricot color_code constraint, ИП+ООО pairs, sets as separate layer, seasonal protection
- Output: JSON findings + recommendations + confidence

- [ ] **Step 2: Create Financier (Финансист) prompt**

Prompt structure:
- Role: Эксперт по юнит-экономике, ценообразованию, ROI
- Input: `{{ENRICHED_DATA}}`
- Tasks: 3x3 matrix (Продается only), unit economics, pricing anomalies, ИП vs ООО (different strategic goals), "what if" scenarios, frozen capital, separate Выводим matrix
- Explicit rules: revenue as diagnostic metric, buyout % impact, margin formulas from kb
- Output: JSON findings + recommendations + confidence

- [ ] **Step 3: Create Marketer (Маркетолог) prompt**

Prompt structure:
- Role: Эксперт по рекламе, конверсии, продвижению
- Input: `{{ENRICHED_DATA}}`
- Tasks: DRR by article, ads↔orders linkage, conversion anomalies, budget reallocation, underinvested stars
- Explicit rules: DRR split (internal + external), never cut ads if orders growing
- Output: JSON findings + recommendations + confidence

- [ ] **Step 4: Commit all 3 prompts**

```bash
git add .claude/skills/abc-audit/prompts/merchandiser.md .claude/skills/abc-audit/prompts/financier.md .claude/skills/abc-audit/prompts/marketer.md
git commit -m "feat(abc-audit): add 3 expert prompts — Товаровед, Финансист, Маркетолог"
```

---

## Task 10: Arbiter + Synthesizer Prompts

**Files:**
- Create: `.claude/skills/abc-audit/prompts/arbiter.md`
- Create: `.claude/skills/abc-audit/prompts/synthesizer.md`

- [ ] **Step 1: Create Arbiter prompt**

Prompt structure:
- Role: CEO / совет директоров. Финальные решения.
- Input: `{{MERCHANDISER_FINDINGS}}`, `{{FINANCIER_FINDINGS}}`, `{{MARKETER_FINDINGS}}`, `{{ENRICHED_DATA}}`
- Tasks: find contradictions, check collection constraints, assign confidence (HIGH/MEDIUM/LOW), verdict per article (НАРАЩИВАТЬ / ПОДДЕРЖИВАТЬ / ОПТИМИЗИРОВАТЬ / ГОТОВИТЬ К ВЫВОДУ / ВЫВОДИТЬ НЕМЕДЛЕННО), prioritize (P0/P1/P2), seasonal protection
- Verdict protocol: APPROVE / CORRECT / REJECT (max 1 REJECT, then mark as unreliable)
- Output: JSON verdicts + priority list

- [ ] **Step 2: Create Synthesizer prompt**

Prompt structure:
- Role: Copywriter/designer. Assembles MD report. No own analysis.
- Input: `{{ARBITER_VERDICTS}}`, `{{ENRICHED_DATA}}`, `{{QUALITY_FLAGS}}`
- 13-section structure (from spec section 6)
- All formatting rules (section 7): Russian terminology, number formats, pipe tables, callouts, cause-effect chains, bold for Δ>10%
- Template for each section with example markup

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/abc-audit/prompts/arbiter.md .claude/skills/abc-audit/prompts/synthesizer.md
git commit -m "feat(abc-audit): add Arbiter + Synthesizer prompts — decisions, MD assembly"
```

---

## Task 11: SKILL.md Orchestrator

**Files:**
- Create: `.claude/skills/abc-audit/SKILL.md`

- [ ] **Step 1: Create SKILL.md**

Complete orchestrator with:

```yaml
---
name: abc-audit
description: "ABC-аудит товарной матрицы Wookiee (WB+OZON) — классификация ABC x ROI, color_code анализ, рекомендации по каждому артикулу"
triggers:
  - /abc-audit
  - abc анализ
  - товарная аналитика
  - аудит товаров
---
```

5 stages:
- **Stage 0:** Parse `$ARGUMENTS` (date or default today). Compute all date params.
- **Stage 1:** Run collector `python3 scripts/abc_audit/collect_data.py --date {CUT_DATE} --output /tmp/abc-audit-{CUT_DATE}.json`. Read JSON. Check errors (>3 = STOP).
- **Stage 2:** Launch Data Analyst subagent. Read `prompts/data_analyst.md`. Replace `{{DATA_BUNDLE}}` with collector JSON. Save output as `enriched_data`.
- **Stage 3:** Launch 3 experts IN PARALLEL (single message, 3 Agent calls). Each reads their prompt + `references/abc-kb.md`. Replace `{{ENRICHED_DATA}}`. Wait for all 3.
- **Stage 4:** Launch Arbiter. Replace `{{MERCHANDISER_FINDINGS}}`, `{{FINANCIER_FINDINGS}}`, `{{MARKETER_FINDINGS}}`, `{{ENRICHED_DATA}}`. Handle APPROVE/CORRECT/REJECT (max 1 retry).
- **Stage 5:** Launch Synthesizer. Replace `{{ARBITER_VERDICTS}}`, `{{ENRICHED_DATA}}`, `{{QUALITY_FLAGS}}`. Save to `docs/reports/{CUT_DATE}_abc_audit.md`. Report to user.

Timing estimate: ~25 min.

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/abc-audit/SKILL.md
git commit -m "feat(abc-audit): add SKILL.md orchestrator — 5 stages, 6 agents"
```

---

## Task 12: Integration Smoke Test

**Files:**
- Modify: `tests/test_abc_audit_collector.py`

- [ ] **Step 1: Add integration test for collector JSON schema**

```python
# Add to tests/test_abc_audit_collector.py

def test_full_collector_json_schema():
    """Smoke test: collector output has all required top-level keys."""
    from scripts.abc_audit.collect_data import run_collection

    with (
        patch("scripts.abc_audit.collect_data.collect_finance", return_value={"finance": {}}),
        patch("scripts.abc_audit.collect_data.collect_inventory", return_value={"inventory": {}, "meta": {"moysklad_stale": False}}),
        patch("scripts.abc_audit.collect_data.collect_hierarchy", return_value={"hierarchy": {"articles": {}, "color_code_groups": {}, "status_counts": {}}}),
        patch("scripts.abc_audit.collect_data.collect_buyouts", return_value={"buyouts": {}}),
        patch("scripts.abc_audit.collect_data.collect_size_data", return_value={"sizes": {}}),
    ):
        result = run_collection("2026-04-11")

    # Top-level keys
    required_keys = {"finance", "inventory", "hierarchy", "buyouts", "sizes", "meta"}
    assert required_keys.issubset(set(result.keys()))

    # Meta structure
    meta = result["meta"]
    assert meta["cut_date"] == "2026-04-11"
    assert "p30_start" in meta
    assert "p90_start" in meta
    assert "p180_start" in meta
    assert "errors" in meta
    assert "quality_flags" in meta
    assert "duration_sec" in meta

    # Quality flags structure
    qf = meta["quality_flags"]
    assert "coverage_pct" in qf
    assert "ozon_buyout_available" in qf
    assert qf["ozon_buyout_available"] is False
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest tests/test_abc_audit_collector.py -v`
Expected: ALL PASS (12+ tests)

- [ ] **Step 3: Final commit**

```bash
git add tests/test_abc_audit_collector.py
git commit -m "test(abc-audit): add integration smoke test for collector JSON schema"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Plan Task | Status |
|---|---|---|
| 3.1 ABC classification | Task 8 (Data Analyst prompt) | Covered |
| 3.2 Decision matrix 3x3 | Task 7 (KB) + Task 9 (Financier) | Covered |
| 3.3 Turnover calculation | Task 3 (inventory collector) | Covered |
| 3.4 Adaptive depth | Task 8 (Data Analyst prompt) | Covered |
| 4.1-4.5 Hierarchy, statuses, color_code | Task 4 (hierarchy collector) + Task 9 (Merchandiser) | Covered |
| 5.1-5.6 All 6 agents | Tasks 6-11 | Covered |
| 6. Report structure (13 sections) | Task 10 (Synthesizer) | Covered |
| 7. Formatting rules | Task 7 (KB) + Task 10 (Synthesizer) | Covered |
| Revenue as metric | Task 2 (finance collector computes it) | Covered |
| Buyout % | Task 5 (buyouts collector) | Covered |
| Size analysis | Task 5 (size data collector) | Covered |
| ИП vs ООО strategy | Task 7 (KB) + Task 9 (Financier) | Covered |
| Seasonal protection | Task 7 (KB) + Task 10 (Arbiter) | Covered |
| MOQ thresholds | Task 7 (KB) + Task 3 (inventory) | Covered |
| Sell at loss strategy | Task 7 (KB) + Task 10 (Arbiter) | Covered |
| Matrix expansion (colors + sizes) | Task 5 (sizes) + Task 9 (Merchandiser) | Covered |

### Placeholder Scan

No TBD, TODO, or "implement later" found. All code steps have complete code. Prompt tasks (7-11) describe structure and content requirements — not "fill in later" but explicit section lists with rules.

### Type Consistency

- `collect_finance()` signature: `(p30_start, p30_end, p90_start, p90_end, p180_start, p180_end)` — consistent in Task 2 implementation and Task 6 call
- `collect_inventory()` signature: `(start_date, end_date)` — consistent
- `collect_hierarchy()` signature: no args — consistent
- `collect_buyouts()` / `collect_size_data()`: `(start_date, end_date)` — consistent
- `run_collection()` in main collector matches test mocks
