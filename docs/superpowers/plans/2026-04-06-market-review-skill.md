# Market Review Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/market-review` skill — monthly market & competitor analysis via MPStats API + internal DB + browser research, with LLM-driven analyst generating actionable hypotheses, published to Notion.

**Architecture:** Python collectors (ThreadPoolExecutor) pull data from MPStats API, internal PostgreSQL, and browser. Verifier (MAIN LLM) cross-checks consistency. Analyst (HEAVY LLM) synthesizes insights. Results go to MD file + Notion page.

**Tech Stack:** Python 3.11, httpx, psycopg2, MPStats REST API, Chrome DevTools MCP, OpenRouter LLM, Notion MCP

**Spec:** `docs/superpowers/specs/2026-04-06-market-review-skill-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `shared/clients/mpstats_client.py` | MPStats API client — auth, retries, rate-limit handling, typed methods per endpoint |
| `shared/config.py` | Add `MPSTATS_API_TOKEN` env var |
| `scripts/market_review/__init__.py` | Package marker |
| `scripts/market_review/config.py` | Categories, competitors, top models, Notion page ID |
| `scripts/market_review/collect_all.py` | Orchestrator — parallel collection, JSON output |
| `scripts/market_review/collectors/__init__.py` | Package marker |
| `scripts/market_review/collectors/market_categories.py` | MPStats category trends |
| `scripts/market_review/collectors/our_performance.py` | Internal DB — our revenue, orders, avg check |
| `scripts/market_review/collectors/competitors_brands.py` | MPStats brand trends for 18 competitors |
| `scripts/market_review/collectors/top_models_ours.py` | MPStats item sales + DB funnel for our 6 models |
| `scripts/market_review/collectors/top_models_rivals.py` | MPStats similar items for competitor analogs |
| `scripts/market_review/collectors/new_items.py` | MPStats new/trending items in our categories |
| `.claude/skills/market-review/SKILL.md` | Skill definition — stages, prompts, variables |
| `.claude/skills/market-review/prompts/verifier.md` | Verifier prompt — cross-check, completeness, arithmetic |
| `.claude/skills/market-review/prompts/analyst.md` | Analyst prompt — deep analysis, hypotheses, Notion format |
| `tests/test_mpstats_client.py` | Unit tests for MPStats client |
| `tests/test_market_review_collectors.py` | Unit tests for collectors (mocked API) |

---

### Task 1: MPStats API Client

**Files:**
- Modify: `shared/config.py:1-17` (add MPSTATS_API_TOKEN)
- Create: `shared/clients/mpstats_client.py`
- Test: `tests/test_mpstats_client.py`

- [ ] **Step 1: Add MPSTATS_API_TOKEN to config.py**

Open `shared/config.py` and add after the Supabase section (~line 60):

```python
# ============================================================================
# MPStats API
# ============================================================================
MPSTATS_API_TOKEN: str = os.getenv('X-Mpstats-TOKEN', '')
```

- [ ] **Step 2: Write the failing test for MPStats client**

Create `tests/test_mpstats_client.py`:

```python
"""Tests for MPStats API client."""
import json
from unittest.mock import patch, MagicMock
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client():
    with patch("shared.config.MPSTATS_API_TOKEN", "test-token-123"):
        from shared.clients.mpstats_client import MPStatsClient
        c = MPStatsClient()
        yield c
        c.close()


class TestMPStatsClientInit:
    def test_creates_with_token(self, client):
        assert client._token == "test-token-123"

    def test_base_url(self, client):
        assert client.BASE_URL == "https://mpstats.io/api/wb"


class TestCategoryTrends:
    def test_returns_trend_data(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"date": "2026-03-01", "revenue": 500000000, "sales": 120000, "avg_price": 1200}
            ]
        }
        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_category_trends(
                path="Женское белье/Комплекты белья",
                d1="2026-03-01", d2="2026-03-31"
            )
            assert "data" in result
            assert result["data"][0]["revenue"] == 500000000


class TestBrandTrends:
    def test_returns_brand_data(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"date": "2026-03-01", "revenue": 5000000, "sales": 3000}
            ]
        }
        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_brand_trends(
                path="Birka Art", d1="2026-03-01", d2="2026-03-31"
            )
            assert result["data"][0]["revenue"] == 5000000


class TestItemSales:
    def test_returns_item_sales(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"date": "2026-03-01", "sales": 150, "revenue": 180000}
            ]
        }
        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_item_sales(sku="12345678", d1="2026-03-01", d2="2026-03-31")
            assert result["data"][0]["sales"] == 150


class TestItemSimilar:
    def test_returns_similar_items(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": 99999, "name": "Аналог", "price": 1100}
            ]
        }
        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_item_similar(sku="12345678")
            assert len(result["data"]) == 1


class TestRetryOn429:
    def test_retries_on_rate_limit(self, client):
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"data": []}

        with patch.object(client._client, "get", side_effect=[rate_limit_response, ok_response]):
            with patch("time.sleep"):  # skip actual sleep
                result = client.get_category_trends(
                    path="test", d1="2026-03-01", d2="2026-03-31"
                )
                assert result == {"data": []}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_mpstats_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shared.clients.mpstats_client'`

- [ ] **Step 4: Write the MPStats client**

Create `shared/clients/mpstats_client.py`:

```python
"""MPStats API client for Wildberries analytics.

Base URL: https://mpstats.io/api/wb
Auth: X-Mpstats-TOKEN header
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from shared.config import MPSTATS_API_TOKEN

logger = logging.getLogger(__name__)


class MPStatsClient:
    """Client for MPStats WB analytics API."""

    BASE_URL = "https://mpstats.io/api/wb"

    def __init__(self, token: str | None = None):
        self._token = token or MPSTATS_API_TOKEN
        if not self._token:
            raise ValueError("MPStats API token not configured. Set X-Mpstats-TOKEN in .env")
        self._client = httpx.Client(
            headers={
                "X-Mpstats-TOKEN": self._token,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def close(self):
        self._client.close()

    # ---- Core request with retries ----

    def _request(self, method: str, url: str, retries: int = 3, **kwargs) -> dict | list | None:
        """Central request method with retry and rate-limit handling."""
        for attempt in range(retries):
            try:
                resp = self._client.request(method, url, **kwargs)

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    logger.warning("[MPStats] Rate limited, waiting %ds (attempt %d/%d)",
                                   wait, attempt + 1, retries)
                    time.sleep(wait)
                    continue
                elif resp.status_code == 401:
                    logger.error("[MPStats] Unauthorized — check X-Mpstats-TOKEN")
                    return None
                else:
                    logger.warning("[MPStats] HTTP %d for %s (attempt %d/%d)",
                                   resp.status_code, url, attempt + 1, retries)
                    time.sleep(5)
            except httpx.RequestError as e:
                logger.warning("[MPStats] Request error: %s (attempt %d/%d)",
                               e, attempt + 1, retries)
                time.sleep(5)

        logger.error("[MPStats] All %d retries exhausted for %s", retries, url)
        return None

    # ---- Category endpoints ----

    def get_category_trends(self, path: str, d1: str, d2: str) -> dict:
        """GET /api/wb/get/category/trends — revenue, sales, avg_price over time."""
        url = f"{self.BASE_URL}/get/category/trends"
        result = self._request("GET", url, params={"path": path, "d1": d1, "d2": d2})
        return result or {"data": []}

    def get_category_list(self) -> dict:
        """GET /api/wb/get/categories — all WB categories."""
        url = f"{self.BASE_URL}/get/categories"
        return self._request("GET", url) or {"data": []}

    # ---- Brand endpoints ----

    def get_brand_trends(self, path: str, d1: str, d2: str) -> dict:
        """GET /api/wb/get/brand/trends — brand revenue/sales over time."""
        url = f"{self.BASE_URL}/get/brand/trends"
        result = self._request("GET", url, params={"path": path, "d1": d1, "d2": d2})
        return result or {"data": []}

    # ---- Item endpoints ----

    def get_item_sales(self, sku: str, d1: str, d2: str) -> dict:
        """GET /api/wb/get/item/{sku}/sales — daily sales for a specific SKU."""
        url = f"{self.BASE_URL}/get/item/{sku}/sales"
        result = self._request("GET", url, params={"d1": d1, "d2": d2})
        return result or {"data": []}

    def get_item_info(self, sku: str) -> dict:
        """GET /api/wb/get/item/{sku} — product card data."""
        url = f"{self.BASE_URL}/get/item/{sku}"
        return self._request("GET", url) or {}

    def get_item_similar(self, sku: str) -> dict:
        """GET /api/wb/get/item/{sku}/similar — similar products."""
        url = f"{self.BASE_URL}/get/item/{sku}/similar"
        return self._request("GET", url) or {"data": []}

    # ---- Search / Discovery ----

    def search_brands(self, query: str) -> dict:
        """POST /api/wb/get/brand/list — search brands by name."""
        url = f"{self.BASE_URL}/get/brand/list"
        return self._request("POST", url, json={"query": query}) or {"data": []}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_mpstats_client.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add shared/config.py shared/clients/mpstats_client.py tests/test_mpstats_client.py
git commit -m "feat(market-review): add MPStats API client with retries and rate-limit handling"
```

---

### Task 2: Market Review Config

**Files:**
- Create: `scripts/market_review/__init__.py`
- Create: `scripts/market_review/config.py`
- Create: `scripts/market_review/collectors/__init__.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p scripts/market_review/collectors
```

- [ ] **Step 2: Create __init__.py files**

Create `scripts/market_review/__init__.py` (empty file):
```python
```

Create `scripts/market_review/collectors/__init__.py` (empty file):
```python
```

- [ ] **Step 3: Write config.py**

Create `scripts/market_review/config.py`:

```python
"""Market Review — configuration.

All constants for the market review skill:
categories, competitors, our top models, Notion page ID.
"""

# WB categories to monitor (MPStats path format)
CATEGORIES = [
    "Женское белье/Комплекты белья",
    "Женское белье/Бюстгальтеры",
    "Женское белье/Трусы",
    "Женское белье/Боди",
]

# Competitors: brand name -> config
# mpstats_path: exact brand name as it appears in MPStats
# segment: pricing segment (for analyst context)
# instagram: Instagram handle (None if no account)
COMPETITORS = {
    # --- Direct competitors (seamless lingerie on marketplaces) ---
    "Birka Art": {"mpstats_path": "Birka Art", "segment": "econom-mid", "instagram": "@birka_art"},
    "Время Цвести": {"mpstats_path": "Время Цвести", "segment": "mid", "instagram": "@vremyazvesti"},
    "SOGU": {"mpstats_path": "SOGU", "segment": "mid-premium", "instagram": "@sogu.shop"},
    "Waistline": {"mpstats_path": "Waistline", "segment": "mid-premium", "instagram": "@waistline_shop"},
    "RIVERENZA": {"mpstats_path": "RIVERENZA", "segment": "econom", "instagram": None},
    "Blizhe": {"mpstats_path": "Blizhe", "segment": "mid", "instagram": None},
    # --- Wider landscape ---
    "Belle You": {"mpstats_path": "Belle You", "segment": "mid-premium", "instagram": "@belleyou.ru"},
    "Bonechka": {"mpstats_path": "Bonechka", "segment": "econom", "instagram": "@bonechka_lingerie"},
    "Lavarice": {"mpstats_path": "Lavarice", "segment": "mid", "instagram": "@lavarice_"},
    "Incanto": {"mpstats_path": "Incanto", "segment": "mid", "instagram": "@incanto_official"},
    "Mark Formelle": {"mpstats_path": "Mark Formelle", "segment": "econom-mid", "instagram": "@markformelle"},
    "VIKKIMO": {"mpstats_path": "VIKKIMO", "segment": "econom", "instagram": "@vikkimo_underwear"},
    "Love Secret": {"mpstats_path": "Love Secret", "segment": "econom", "instagram": "@lovesecret.shop"},
    "MASAR Lingerie": {"mpstats_path": "MASAR Lingerie", "segment": "mid", "instagram": "@masar.lingerie"},
    "Mirey": {"mpstats_path": "Mirey", "segment": "mid", "instagram": "@mirey.su"},
    "Morely": {"mpstats_path": "Morely", "segment": "premium", "instagram": "@morely.ru"},
    "Cecile": {"mpstats_path": "Cecile", "segment": "unknown", "instagram": None},
    "Where Underwear": {"mpstats_path": "Where Underwear", "segment": "unknown", "instagram": None},
}

# Our top models: osnova name -> list of WB nmId (SKU numbers)
# Populated from Supabase product matrix or manually
OUR_TOP_MODELS = {
    "Wendy": [],    # TODO: populate with actual WB nmId values
    "Audrey": [],
    "Ruby": [],
    "Joy": [],
    "Vuki": [],
    "Moon": [],
}

# Notion target page for publishing
NOTION_PAGE_ID = "2f458a2bd58780648974f98347b2d4d5"

# Competitors for deep WB card analysis (browser research)
WB_CARD_DEEP_ANALYSIS = ["Birka Art", "SOGU", "Waistline", "Belle You"]

# Minimum revenue (RUB) for new items to be included
NEW_ITEMS_MIN_REVENUE = 500_000
```

- [ ] **Step 4: Commit**

```bash
git add scripts/market_review/
git commit -m "feat(market-review): add config with categories, competitors, top models"
```

---

### Task 3: Category Trends Collector

**Files:**
- Create: `scripts/market_review/collectors/market_categories.py`
- Test: `tests/test_market_review_collectors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_market_review_collectors.py`:

```python
"""Tests for market review collectors."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestMarketCategories:
    def test_collects_category_trends(self):
        mock_client = MagicMock()
        mock_client.get_category_trends.return_value = {
            "data": [
                {"date": "2026-03-01", "revenue": 500_000_000, "sales": 120_000, "avg_price": 1200},
                {"date": "2026-03-15", "revenue": 480_000_000, "sales": 115_000, "avg_price": 1180},
            ]
        }

        with patch("scripts.market_review.collectors.market_categories.MPStatsClient", return_value=mock_client):
            from scripts.market_review.collectors.market_categories import collect_market_categories
            result = collect_market_categories(
                period_start="2026-03-01",
                period_end="2026-03-31",
                prev_start="2026-02-01",
                prev_end="2026-02-28",
            )

        assert "categories" in result
        # Should have data for each configured category
        assert len(result["categories"]) > 0
        first_cat = next(iter(result["categories"].values()))
        assert "current" in first_cat
        assert "previous" in first_cat
        assert "delta_pct" in first_cat

    def test_handles_api_error_gracefully(self):
        mock_client = MagicMock()
        mock_client.get_category_trends.return_value = {"data": []}

        with patch("scripts.market_review.collectors.market_categories.MPStatsClient", return_value=mock_client):
            from scripts.market_review.collectors.market_categories import collect_market_categories
            result = collect_market_categories(
                period_start="2026-03-01",
                period_end="2026-03-31",
                prev_start="2026-02-01",
                prev_end="2026-02-28",
            )

        assert "categories" in result
        # Categories should exist but with zero values
        for cat_data in result["categories"].values():
            assert cat_data["current"]["revenue"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_market_review_collectors.py::TestMarketCategories -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the collector**

Create `scripts/market_review/collectors/market_categories.py`:

```python
"""Collector: WB category trends from MPStats API.

Fetches revenue, sales, avg_price for each configured category
for current and previous periods. Computes deltas.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from scripts.market_review.config import CATEGORIES

logger = logging.getLogger(__name__)


def _aggregate_trend(data: list[dict]) -> dict:
    """Aggregate daily trend data into period totals."""
    if not data:
        return {"revenue": 0, "sales": 0, "avg_price": 0, "items": 0, "sellers": 0}

    total_revenue = sum(d.get("revenue", 0) or 0 for d in data)
    total_sales = sum(d.get("sales", 0) or 0 for d in data)
    avg_price = total_revenue / total_sales if total_sales > 0 else 0

    return {
        "revenue": round(total_revenue),
        "sales": round(total_sales),
        "avg_price": round(avg_price),
        "items": data[-1].get("items_count", 0) if data else 0,
        "sellers": data[-1].get("sellers_count", 0) if data else 0,
    }


def _calc_delta_pct(current: dict, previous: dict) -> dict:
    """Calculate percentage deltas for each metric."""
    delta = {}
    for key in current:
        cur_val = current[key]
        prev_val = previous.get(key, 0)
        if prev_val and prev_val != 0:
            delta[key] = round((cur_val - prev_val) / prev_val * 100, 1)
        else:
            delta[key] = None
    return delta


def collect_market_categories(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect category trends for all configured categories.

    Returns:
        {"categories": {"Комплекты белья": {"current": {...}, "previous": {...}, "delta_pct": {...}}}}
    """
    client = MPStatsClient()
    categories = {}

    for cat_path in CATEGORIES:
        cat_name = cat_path.split("/")[-1]  # "Женское белье/Комплекты белья" -> "Комплекты белья"
        logger.info("[MarketCategories] Fetching: %s", cat_path)

        # Current period
        current_raw = client.get_category_trends(path=cat_path, d1=period_start, d2=period_end)
        current = _aggregate_trend(current_raw.get("data", []))

        # Previous period
        prev_raw = client.get_category_trends(path=cat_path, d1=prev_start, d2=prev_end)
        previous = _aggregate_trend(prev_raw.get("data", []))

        categories[cat_name] = {
            "path": cat_path,
            "current": current,
            "previous": previous,
            "delta_pct": _calc_delta_pct(current, previous),
        }

    client.close()
    return {"categories": categories}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_market_review_collectors.py::TestMarketCategories -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/market_review/collectors/market_categories.py tests/test_market_review_collectors.py
git commit -m "feat(market-review): add category trends collector (MPStats)"
```

---

### Task 4: Competitors Brands Collector

**Files:**
- Create: `scripts/market_review/collectors/competitors_brands.py`
- Modify: `tests/test_market_review_collectors.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_market_review_collectors.py`:

```python
class TestCompetitorsBrands:
    def test_collects_all_competitors(self):
        mock_client = MagicMock()
        mock_client.get_brand_trends.return_value = {
            "data": [
                {"date": "2026-03-01", "revenue": 3_000_000, "sales": 2000, "avg_price": 1500},
            ]
        }

        with patch("scripts.market_review.collectors.competitors_brands.MPStatsClient", return_value=mock_client):
            from scripts.market_review.collectors.competitors_brands import collect_competitors_brands
            result = collect_competitors_brands(
                period_start="2026-03-01",
                period_end="2026-03-31",
                prev_start="2026-02-01",
                prev_end="2026-02-28",
            )

        assert "competitors" in result
        # Should have attempted all 18 competitors from config
        assert len(result["competitors"]) > 0
        first = next(iter(result["competitors"].values()))
        assert "current" in first
        assert "previous" in first
        assert "delta_pct" in first
        assert "segment" in first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_market_review_collectors.py::TestCompetitorsBrands -v`
Expected: FAIL

- [ ] **Step 3: Write the collector**

Create `scripts/market_review/collectors/competitors_brands.py`:

```python
"""Collector: competitor brand trends from MPStats API.

Fetches revenue, sales, avg_price for each competitor brand
from config, for current and previous periods.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from scripts.market_review.config import COMPETITORS

logger = logging.getLogger(__name__)


def _aggregate_brand_trend(data: list[dict]) -> dict:
    """Aggregate daily brand trend data into period totals."""
    if not data:
        return {"revenue": 0, "sales": 0, "avg_price": 0, "sku_count": 0}

    total_revenue = sum(d.get("revenue", 0) or 0 for d in data)
    total_sales = sum(d.get("sales", 0) or 0 for d in data)
    avg_price = total_revenue / total_sales if total_sales > 0 else 0

    return {
        "revenue": round(total_revenue),
        "sales": round(total_sales),
        "avg_price": round(avg_price),
        "sku_count": data[-1].get("items_count", 0) if data else 0,
    }


def _calc_delta_pct(current: dict, previous: dict) -> dict:
    delta = {}
    for key in current:
        cur_val = current[key]
        prev_val = previous.get(key, 0)
        if prev_val and prev_val != 0:
            delta[key] = round((cur_val - prev_val) / prev_val * 100, 1)
        else:
            delta[key] = None
    return delta


def collect_competitors_brands(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect brand trends for all configured competitors.

    Returns:
        {"competitors": {"Birka Art": {"current": {...}, "previous": {...}, "delta_pct": {...}, "segment": "..."}}}
    """
    client = MPStatsClient()
    competitors = {}

    for brand_name, brand_cfg in COMPETITORS.items():
        mpstats_path = brand_cfg["mpstats_path"]
        logger.info("[CompetitorsBrands] Fetching: %s (%s)", brand_name, mpstats_path)

        current_raw = client.get_brand_trends(path=mpstats_path, d1=period_start, d2=period_end)
        current = _aggregate_brand_trend(current_raw.get("data", []))

        prev_raw = client.get_brand_trends(path=mpstats_path, d1=prev_start, d2=prev_end)
        previous = _aggregate_brand_trend(prev_raw.get("data", []))

        competitors[brand_name] = {
            "current": current,
            "previous": previous,
            "delta_pct": _calc_delta_pct(current, previous),
            "segment": brand_cfg["segment"],
            "instagram": brand_cfg.get("instagram"),
        }

        time.sleep(0.5)  # rate-limit courtesy

    client.close()
    return {"competitors": competitors}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_market_review_collectors.py::TestCompetitorsBrands -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/market_review/collectors/competitors_brands.py tests/test_market_review_collectors.py
git commit -m "feat(market-review): add competitors brands collector (MPStats)"
```

---

### Task 5: Our Performance Collector (Internal DB)

**Files:**
- Create: `scripts/market_review/collectors/our_performance.py`
- Modify: `tests/test_market_review_collectors.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_market_review_collectors.py`:

```python
class TestOurPerformance:
    def test_collects_wb_and_ozon(self):
        mock_wb_rows = [
            ("current", 5000, 4500, 25_000_000, 22_000_000, 800_000, 200_000, 8_000_000,
             1_500_000, 500_000, 2_000_000, 3_000_000, 500_000, 50_000, 100_000, 30_000, 6_000_000, 0, 25_000_000),
            ("previous", 4800, 4300, 24_000_000, 21_000_000, 750_000, 180_000, 7_800_000,
             1_400_000, 480_000, 1_900_000, 2_800_000, 470_000, 45_000, 95_000, 28_000, 5_700_000, 0, 24_000_000),
        ]
        mock_ozon_rows = [
            ("current", 2000, 12_000_000, 10_000_000, 400_000, 0, 2_500_000,
             4_000_000, 700_000, 200_000, 800_000, 1_200_000, 200_000),
        ]

        with patch("scripts.market_review.collectors.our_performance.get_wb_finance", return_value=(mock_wb_rows, [])):
            with patch("scripts.market_review.collectors.our_performance.get_ozon_finance", return_value=(mock_ozon_rows, [])):
                from scripts.market_review.collectors.our_performance import collect_our_performance
                result = collect_our_performance(
                    period_start="2026-03-01",
                    period_end="2026-03-31",
                    prev_start="2026-02-01",
                    prev_end="2026-02-28",
                )

        assert "our" in result
        assert "current" in result["our"]
        assert result["our"]["current"]["revenue"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_market_review_collectors.py::TestOurPerformance -v`
Expected: FAIL

- [ ] **Step 3: Write the collector**

Create `scripts/market_review/collectors/our_performance.py`:

```python
"""Collector: our performance from internal DB.

Pulls WB + OZON revenue, orders, avg check for current and previous periods.
Uses the same data_layer functions as financial_overview.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.data_layer import get_wb_finance, get_ozon_finance

logger = logging.getLogger(__name__)


def _parse_finance_row(row: tuple) -> dict:
    """Parse a finance row into a dict. Works for both WB (19 cols) and OZON (13 cols)."""
    if len(row) >= 17:
        return {
            "sales_count": int(row[2] or 0),
            "revenue": float(row[3] or 0),  # revenue_before_spp
            "revenue_after_spp": float(row[4] or 0),
            "margin": float(row[16] or 0) if len(row) > 16 else 0,
        }
    elif len(row) >= 7:
        return {
            "sales_count": int(row[1] or 0),
            "revenue": float(row[2] or 0),
            "revenue_after_spp": float(row[3] or 0),
            "margin": float(row[6] or 0),
        }
    return {"sales_count": 0, "revenue": 0, "revenue_after_spp": 0, "margin": 0}


def collect_our_performance(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect our financial performance for both periods.

    Returns:
        {"our": {"current": {...}, "previous": {...}, "delta_pct": {...}}}
    """
    logger.info("[OurPerformance] Fetching WB + OZON finance for %s to %s", period_start, period_end)

    # WB data
    wb_rows, _ = get_wb_finance(period_start, prev_start, period_end)
    wb_current = {}
    wb_previous = {}
    for row in wb_rows:
        if row[0] == "current":
            wb_current = _parse_finance_row(row)
        elif row[0] == "previous":
            wb_previous = _parse_finance_row(row)

    # OZON data
    ozon_rows, _ = get_ozon_finance(period_start, prev_start, period_end)
    ozon_current = {}
    ozon_previous = {}
    for row in ozon_rows:
        if row[0] == "current":
            ozon_current = _parse_finance_row(row)
        elif row[0] == "previous":
            ozon_previous = _parse_finance_row(row)

    # Combined
    def _combine(wb: dict, ozon: dict) -> dict:
        revenue = wb.get("revenue", 0) + ozon.get("revenue", 0)
        sales = wb.get("sales_count", 0) + ozon.get("sales_count", 0)
        return {
            "revenue": round(revenue),
            "sales_count": sales,
            "avg_check": round(revenue / sales) if sales > 0 else 0,
            "margin": round(wb.get("margin", 0) + ozon.get("margin", 0)),
            "wb_revenue": round(wb.get("revenue", 0)),
            "ozon_revenue": round(ozon.get("revenue", 0)),
        }

    current = _combine(wb_current, ozon_current)
    previous = _combine(wb_previous, ozon_previous)

    delta_pct = {}
    for key in ["revenue", "sales_count", "avg_check", "margin"]:
        prev_val = previous.get(key, 0)
        if prev_val and prev_val != 0:
            delta_pct[key] = round((current[key] - prev_val) / prev_val * 100, 1)
        else:
            delta_pct[key] = None

    return {
        "our": {
            "current": current,
            "previous": previous,
            "delta_pct": delta_pct,
        }
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_market_review_collectors.py::TestOurPerformance -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/market_review/collectors/our_performance.py tests/test_market_review_collectors.py
git commit -m "feat(market-review): add our_performance collector (internal DB)"
```

---

### Task 6: Top Models Collectors (Ours + Rivals)

**Files:**
- Create: `scripts/market_review/collectors/top_models_ours.py`
- Create: `scripts/market_review/collectors/top_models_rivals.py`
- Modify: `tests/test_market_review_collectors.py`

- [ ] **Step 1: Write the failing test for top_models_ours**

Append to `tests/test_market_review_collectors.py`:

```python
class TestTopModelsOurs:
    def test_collects_model_data(self):
        mock_client = MagicMock()
        mock_client.get_item_sales.return_value = {
            "data": [{"date": "2026-03-01", "sales": 50, "revenue": 60000}]
        }

        with patch("scripts.market_review.collectors.top_models_ours.MPStatsClient", return_value=mock_client):
            with patch("scripts.market_review.collectors.top_models_ours.OUR_TOP_MODELS",
                       {"Wendy": ["111111"], "Audrey": ["222222"]}):
                from scripts.market_review.collectors.top_models_ours import collect_top_models_ours
                result = collect_top_models_ours(
                    period_start="2026-03-01", period_end="2026-03-31",
                    prev_start="2026-02-01", prev_end="2026-02-28",
                )

        assert "our_models" in result
        assert "Wendy" in result["our_models"]
```

- [ ] **Step 2: Write top_models_ours.py**

Create `scripts/market_review/collectors/top_models_ours.py`:

```python
"""Collector: our top models — MPStats sales + DB funnel data.

For each model in OUR_TOP_MODELS config, fetches item-level sales
from MPStats and (optionally) funnel data from internal DB.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from scripts.market_review.config import OUR_TOP_MODELS

logger = logging.getLogger(__name__)


def _aggregate_item_sales(data: list[dict]) -> dict:
    """Sum daily sales data for a single SKU."""
    if not data:
        return {"sales": 0, "revenue": 0, "avg_price": 0}
    total_sales = sum(d.get("sales", 0) or 0 for d in data)
    total_revenue = sum(d.get("revenue", 0) or 0 for d in data)
    return {
        "sales": total_sales,
        "revenue": round(total_revenue),
        "avg_price": round(total_revenue / total_sales) if total_sales > 0 else 0,
    }


def collect_top_models_ours(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Collect MPStats sales for our top models.

    Returns:
        {"our_models": {"Wendy": {"skus": [...], "current": {...}, "previous": {...}, "delta_pct": {...}}}}
    """
    client = MPStatsClient()
    models = {}

    for model_name, sku_list in OUR_TOP_MODELS.items():
        if not sku_list:
            logger.warning("[TopModelsOurs] No SKUs configured for %s, skipping", model_name)
            models[model_name] = {
                "skus": [],
                "current": {"sales": 0, "revenue": 0, "avg_price": 0},
                "previous": {"sales": 0, "revenue": 0, "avg_price": 0},
                "delta_pct": {},
                "note": "no SKUs configured",
            }
            continue

        logger.info("[TopModelsOurs] Fetching %s (%d SKUs)", model_name, len(sku_list))

        # Aggregate across all SKUs for this model
        current_total = {"sales": 0, "revenue": 0}
        previous_total = {"sales": 0, "revenue": 0}

        for sku in sku_list:
            cur_raw = client.get_item_sales(sku=str(sku), d1=period_start, d2=period_end)
            cur = _aggregate_item_sales(cur_raw.get("data", []))
            current_total["sales"] += cur["sales"]
            current_total["revenue"] += cur["revenue"]

            prev_raw = client.get_item_sales(sku=str(sku), d1=prev_start, d2=prev_end)
            prev = _aggregate_item_sales(prev_raw.get("data", []))
            previous_total["sales"] += prev["sales"]
            previous_total["revenue"] += prev["revenue"]

            time.sleep(0.3)

        current_total["avg_price"] = (
            round(current_total["revenue"] / current_total["sales"])
            if current_total["sales"] > 0 else 0
        )
        previous_total["avg_price"] = (
            round(previous_total["revenue"] / previous_total["sales"])
            if previous_total["sales"] > 0 else 0
        )

        delta_pct = {}
        for key in ["sales", "revenue", "avg_price"]:
            prev_val = previous_total.get(key, 0)
            if prev_val and prev_val != 0:
                delta_pct[key] = round((current_total[key] - prev_val) / prev_val * 100, 1)
            else:
                delta_pct[key] = None

        models[model_name] = {
            "skus": sku_list,
            "current": current_total,
            "previous": previous_total,
            "delta_pct": delta_pct,
        }

    client.close()
    return {"our_models": models}
```

- [ ] **Step 3: Write top_models_rivals.py**

Create `scripts/market_review/collectors/top_models_rivals.py`:

```python
"""Collector: competitor analogs for our top models via MPStats similar items.

For each model's first SKU, finds similar items on WB and fetches their sales.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from scripts.market_review.config import OUR_TOP_MODELS

logger = logging.getLogger(__name__)

TOP_N_ANALOGS = 3  # keep top 3 by revenue


def collect_top_models_rivals(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Find and analyze competitor analogs for our top models.

    Returns:
        {"rival_models": {"Wendy": {"analogs": [{"sku": ..., "brand": ..., ...}]}}}
    """
    client = MPStatsClient()
    rivals = {}

    for model_name, sku_list in OUR_TOP_MODELS.items():
        if not sku_list:
            rivals[model_name] = {"analogs": [], "note": "no SKUs configured"}
            continue

        # Use first SKU to find similar items
        primary_sku = str(sku_list[0])
        logger.info("[TopModelsRivals] Finding analogs for %s (SKU: %s)", model_name, primary_sku)

        similar_raw = client.get_item_similar(sku=primary_sku)
        similar_items = similar_raw.get("data", [])

        if not similar_items:
            rivals[model_name] = {"analogs": [], "note": "no similar items found"}
            continue

        # Fetch sales for each similar item, pick top N by revenue
        analogs = []
        for item in similar_items[:10]:  # check at most 10
            item_sku = str(item.get("id", ""))
            if not item_sku:
                continue

            sales_raw = client.get_item_sales(sku=item_sku, d1=period_start, d2=period_end)
            sales_data = sales_raw.get("data", [])
            total_revenue = sum(d.get("revenue", 0) or 0 for d in sales_data)
            total_sales = sum(d.get("sales", 0) or 0 for d in sales_data)

            analogs.append({
                "sku": item_sku,
                "brand": item.get("brand", "Unknown"),
                "name": item.get("name", ""),
                "price": item.get("price", 0),
                "revenue": round(total_revenue),
                "sales": total_sales,
                "rating": item.get("rating", 0),
                "reviews": item.get("reviews_count", 0),
            })
            time.sleep(0.3)

        # Sort by revenue desc, take top N
        analogs.sort(key=lambda x: x["revenue"], reverse=True)
        rivals[model_name] = {"analogs": analogs[:TOP_N_ANALOGS]}

    client.close()
    return {"rival_models": rivals}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_market_review_collectors.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/market_review/collectors/top_models_ours.py scripts/market_review/collectors/top_models_rivals.py tests/test_market_review_collectors.py
git commit -m "feat(market-review): add top models collectors (ours + rivals)"
```

---

### Task 7: New Items Collector

**Files:**
- Create: `scripts/market_review/collectors/new_items.py`

- [ ] **Step 1: Write the collector**

Create `scripts/market_review/collectors/new_items.py`:

```python
"""Collector: new/trending items in our categories from MPStats.

Searches for recently appeared SKUs with significant revenue.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from shared.clients.mpstats_client import MPStatsClient
from scripts.market_review.config import CATEGORIES, NEW_ITEMS_MIN_REVENUE

logger = logging.getLogger(__name__)


def collect_new_items(
    period_start: str,
    period_end: str,
    prev_start: str,
    prev_end: str,
) -> dict:
    """Find successful new items in our categories.

    Fetches category items, filters for those with first_seen in current period
    and revenue above threshold.

    Returns:
        {"new_items": [{"sku": ..., "brand": ..., "category": ..., "revenue": ..., ...}]}
    """
    client = MPStatsClient()
    new_items = []

    for cat_path in CATEGORIES:
        cat_name = cat_path.split("/")[-1]
        logger.info("[NewItems] Searching new items in: %s", cat_path)

        # Fetch category items for current period
        url = f"{client.BASE_URL}/get/category"
        result = client._request("POST", url, json={
            "startRow": 0,
            "endRow": 500,
            "path": cat_path,
            "d1": period_start,
            "d2": period_end,
        })

        if not result or "data" not in result:
            continue

        for item in result.get("data", []):
            revenue = item.get("revenue", 0) or 0
            if revenue < NEW_ITEMS_MIN_REVENUE:
                continue

            # Check if item is "new" — appeared recently
            first_seen = item.get("start_date", "") or item.get("first_date", "")
            if first_seen and first_seen >= prev_start:
                new_items.append({
                    "sku": str(item.get("id", "")),
                    "brand": item.get("brand", "Unknown"),
                    "name": item.get("name", ""),
                    "category": cat_name,
                    "price": item.get("price", 0),
                    "revenue": round(revenue),
                    "sales": item.get("sales", 0),
                    "rating": item.get("rating", 0),
                    "reviews": item.get("reviews_count", 0),
                    "first_seen": first_seen,
                })

        time.sleep(0.5)

    client.close()

    # Sort by revenue desc
    new_items.sort(key=lambda x: x["revenue"], reverse=True)
    return {"new_items": new_items[:30]}  # top 30
```

- [ ] **Step 2: Commit**

```bash
git add scripts/market_review/collectors/new_items.py
git commit -m "feat(market-review): add new items collector (MPStats)"
```

---

### Task 8: Orchestrator (collect_all.py)

**Files:**
- Create: `scripts/market_review/collect_all.py`

- [ ] **Step 1: Write the orchestrator**

Create `scripts/market_review/collect_all.py`:

```python
#!/usr/bin/env python3
"""Market Review — parallel data collection orchestrator.

Usage:
    python scripts/market_review/collect_all.py \
        --month 2026-03 \
        --output /tmp/market_review_data.json

Collects data from MPStats API and internal DB in parallel.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _month_range(month_str: str) -> tuple[str, str]:
    """Convert 'YYYY-MM' to (start, end) date strings."""
    dt = datetime.strptime(month_str + "-01", "%Y-%m-%d")
    start = dt.strftime("%Y-%m-%d")
    # End = first day of next month
    if dt.month == 12:
        end_dt = dt.replace(year=dt.year + 1, month=1)
    else:
        end_dt = dt.replace(month=dt.month + 1)
    end = end_dt.strftime("%Y-%m-%d")
    return start, end


def _prev_month(month_str: str) -> str:
    """Return previous month as 'YYYY-MM'."""
    dt = datetime.strptime(month_str + "-01", "%Y-%m-%d")
    if dt.month == 1:
        prev = dt.replace(year=dt.year - 1, month=12)
    else:
        prev = dt.replace(month=dt.month - 1)
    return prev.strftime("%Y-%m")


def run_collector(name: str, func, kwargs: dict) -> tuple[str, dict | None, str | None]:
    """Run a single collector, return (name, result, error)."""
    try:
        result = func(**kwargs)
        return name, result, None
    except Exception as e:
        return name, None, f"{type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Market Review data collector")
    parser.add_argument("--month", required=True,
                        help="Month to analyze: YYYY-MM (e.g. 2026-03)")
    parser.add_argument("--sections",
                        default="categories,our,competitors,models_ours,models_rivals,new_items",
                        help="Comma-separated sections to collect")
    parser.add_argument("--output", default="/tmp/market_review_data.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    month = args.month
    prev_month = _prev_month(month)
    period_start, period_end = _month_range(month)
    prev_start, prev_end = _month_range(prev_month)
    sections = [s.strip() for s in args.sections.split(",")]

    common_kwargs = {
        "period_start": period_start,
        "period_end": period_end,
        "prev_start": prev_start,
        "prev_end": prev_end,
    }

    collectors = {}

    if "categories" in sections:
        from scripts.market_review.collectors.market_categories import collect_market_categories
        collectors["market_categories"] = (collect_market_categories, common_kwargs)

    if "our" in sections:
        from scripts.market_review.collectors.our_performance import collect_our_performance
        collectors["our_performance"] = (collect_our_performance, common_kwargs)

    if "competitors" in sections:
        from scripts.market_review.collectors.competitors_brands import collect_competitors_brands
        collectors["competitors_brands"] = (collect_competitors_brands, common_kwargs)

    if "models_ours" in sections:
        from scripts.market_review.collectors.top_models_ours import collect_top_models_ours
        collectors["top_models_ours"] = (collect_top_models_ours, common_kwargs)

    if "models_rivals" in sections:
        from scripts.market_review.collectors.top_models_rivals import collect_top_models_rivals
        collectors["top_models_rivals"] = (collect_top_models_rivals, common_kwargs)

    if "new_items" in sections:
        from scripts.market_review.collectors.new_items import collect_new_items
        collectors["new_items"] = (collect_new_items, common_kwargs)

    # Run collectors in parallel
    t0 = time.time()
    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(run_collector, name, func, kwargs): name
            for name, (func, kwargs) in collectors.items()
        }
        for future in as_completed(futures):
            name, result, error = future.result()
            if error:
                errors[name] = error
                print(f"[WARN] Collector {name} failed: {error}", file=sys.stderr)
            else:
                results[name] = result
                print(f"[OK] Collector {name} done")

    duration = round(time.time() - t0, 1)

    output = {
        **results,
        "meta": {
            "month": month,
            "period": {"start": period_start, "end": period_end},
            "prev_period": {"start": prev_start, "end": prev_end},
            "sections": sections,
            "errors": errors,
            "collection_duration_sec": duration,
        },
    }

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    print(f"\nData saved to {args.output} ({duration}s, {len(errors)} errors)")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python scripts/market_review/collect_all.py --month 2026-03 --sections "categories" --output /tmp/test_market_review.json`

Check output exists: `cat /tmp/test_market_review.json | python -m json.tool | head -20`

- [ ] **Step 3: Commit**

```bash
git add scripts/market_review/collect_all.py
git commit -m "feat(market-review): add parallel collection orchestrator"
```

---

### Task 9: Skill Definition (SKILL.md)

**Files:**
- Create: `.claude/skills/market-review/SKILL.md`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p .claude/skills/market-review/prompts
```

- [ ] **Step 2: Write SKILL.md**

Create `.claude/skills/market-review/SKILL.md`:

```markdown
---
name: market-review
description: Monthly market & competitor review — MPStats data collection, LLM analysis, Notion publication. Covers market dynamics, competitor tracking, top model comparison.
triggers:
  - /market-review
  - обзор рынка
  - market review
  - анализ конкурентов
---

# Market Review Skill

Generates a monthly market & competitor analysis report using MPStats API + internal DB + browser research, with HEAVY LLM generating actionable hypotheses.

## Stage 0: Interactive Setup

Ask the user using AskUserQuestion:

**Q1 — Month:**
```
question: "Какой месяц анализировать?"
header: "Месяц"
options:
  - label: "Прошлый месяц (авто)" / description: "Автоматически определяется"
  - label: "Март 2026" / description: "2026-03"
  - label: "Февраль 2026" / description: "2026-02"
  (+ Other для ввода YYYY-MM)
```

**Q2 — Sections (multiSelect):**
```
question: "Какие разделы включить?"
header: "Разделы"
options:
  - "Динамика категорий" — categories
  - "Наши метрики" — our
  - "Конкуренты" — competitors
  - "Наши топ-модели" — models_ours
  - "Аналоги конкурентов" — models_rivals
  - "Новинки" — new_items
All selected by default.
```

Store answers as:
- `month` = "YYYY-MM"
- `sections` = "categories,our,competitors,models_ours,models_rivals,new_items"

## Stage 1: Data Collection

Run the collector orchestrator:

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 scripts/market_review/collect_all.py \
  --month "{{month}}" \
  --sections "{{sections}}" \
  --output /tmp/market_review_data.json
```

Check exit code:
- Exit 0: all collectors succeeded
- Exit 1: some collectors failed — check `meta.errors`, warn user, continue

## Stage 1.5: Browser Research (Optional)

If browser tools are available (agent-browser or chrome-devtools MCP):

**Instagram Research:**
For each competitor with an Instagram account (from config):
1. Navigate to their Instagram profile
2. Collect last 10-15 posts from the analysis month
3. Note: type (reels/photo/carousel), likes, comments, topic, hook
4. Identify top-engagement posts (above average)

**WB Card Research:**
For competitors in WB_CARD_DEEP_ANALYSIS config:
1. Open their top WB product cards
2. Note: cover image, video, infographics, description structure, UTP

Save browser research results to `/tmp/market_review_browser.json` and merge into main data.

## Stage 2: Verify + Analyze

### 2a. Verification Agent

Launch a background Agent with the verifier prompt:

```
Read prompt from: .claude/skills/market-review/prompts/verifier.md
Replace {{DATA_FILE}} with: /tmp/market_review_data.json
Execute verification checklist.
Report: STATUS, ISSUES, WARNINGS.
```

If STATUS == FAIL: report issues to user and stop.
If STATUS == WARN or PASS: proceed.

### 2b. Analyst Agent

Launch an Agent with the analyst prompt:

```
Read prompt from: .claude/skills/market-review/prompts/analyst.md
Replace placeholders:
  {{DATA_FILE}} = /tmp/market_review_data.json
  {{MONTH_LABEL}} = "Март 2026"
  {{VERIFIER_WARNINGS}} = warnings from 2a (if any)

Tasks:
1. Read JSON data
2. Analyze market dynamics, competitor movements, model comparisons
3. Generate hypotheses with estimated impact
4. Write MD report to: docs/reports/YYYY-MM-market-review.md
5. Publish to Notion page (ID: 2f458a2bd58780648974f98347b2d4d5)
```

## Stage 3: Delivery

After analyst completes:
1. Confirm MD file path
2. Confirm Notion page URL
3. Show summary: key findings + top 3 hypotheses
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/market-review/SKILL.md
git commit -m "feat(market-review): add skill definition (SKILL.md)"
```

---

### Task 10: Verifier Prompt

**Files:**
- Create: `.claude/skills/market-review/prompts/verifier.md`

- [ ] **Step 1: Write the verifier prompt**

Create `.claude/skills/market-review/prompts/verifier.md`:

```markdown
# Data Verifier — Market Review

You are a data verification agent. Your job is to cross-check the collected market review data for consistency, completeness, and correctness.

## Input

Read the data file at: `{{DATA_FILE}}`

## Verification Checklist

### 1. Cross-Source Consistency
- If both `our_performance` and `market_categories` data present:
  - Our revenue should be a reasonable fraction of category revenue (0.1%-10%)
  - If our share > 10% or < 0.01%, flag as suspicious
- Competitor revenue should not exceed category total revenue
- Delta percentages should be consistent with raw numbers

### 2. Arithmetic Checks
- Growth percentages: `(current - previous) / previous * 100`
- Average price: `revenue / sales` (not simple average)
- All delta_pct values should match manual calculation from current/previous values

### 3. Data Completeness
- All configured categories have data for BOTH periods
- All 18 competitors have entries (even if some have zero data)
- Our top models section exists (even if SKUs not yet configured)
- No section returns entirely null/zero values without explanation in `meta.errors`

### 4. Quality Flags
- MPStats revenue estimates may differ 10-30% from actual — note as caveat
- If any collector failed (check `meta.errors`), note which sections are missing
- If competitor brand not found in MPStats (returns empty), flag for config review

### 5. Sensitive Data
- No API tokens or credentials in output
- No server IPs or internal URLs
- No personal data (ИНН, юрлица names)

## Output Format

```
STATUS: PASS | WARN | FAIL
ISSUES: [list of critical issues requiring abort]
WARNINGS: [list of non-critical issues to note in report footer]
```

**FAIL conditions:**
- Our own performance data completely missing (internal DB unreachable)
- More than 50% of collectors returned errors
- Arithmetic errors detected

**WARN conditions:**
- Some competitors returned empty data
- Browser research unavailable
- Revenue cross-check delta > 20%
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/market-review/prompts/verifier.md
git commit -m "feat(market-review): add verifier prompt"
```

---

### Task 11: Analyst Prompt

**Files:**
- Create: `.claude/skills/market-review/prompts/analyst.md`

- [ ] **Step 1: Write the analyst prompt**

Create `.claude/skills/market-review/prompts/analyst.md`:

```markdown
# Market Analyst — Monthly Review

You are a senior market analyst for Wookiee, a women's seamless lingerie brand on WB and OZON (~35-40M RUB/month revenue, 200+ SKUs, 10+ models).

## Input

- Data file: `{{DATA_FILE}}` (JSON with all collected data)
- Month: `{{MONTH_LABEL}}`
- Verifier warnings: `{{VERIFIER_WARNINGS}}`

## Your Task

Analyze the collected data and write a monthly market review report. This is NOT a data dump — it's an analytical document that answers "what happened, why, and what should we do about it."

## Competitor Context

Wookiee competes primarily in seamless lingerie on WB. Key segments:
- Econom (< 800 RUB/set): RIVERENZA, Bonechka, VIKKIMO
- Mid (800-2000): Время Цвести, Lavarice, Blizhe, MASAR
- Mid-Premium (2000+): SOGU, Waistline, Belle You
- Our positioning: Econom-Mid (600-1500 RUB/set)

## Report Structure

Write the report in Markdown with Notion-compatible formatting.

### I. Рынок: динамика категорий

Create a table for each category with columns:
| Категория | Выручка (тек) | Выручка (пред) | Дельта % | Ср. чек | Продавцы |

Then compare with our performance:
- Calculate our market share per category
- Use callouts:
  - Green (`<callout icon="✅" color="green_bg">`) if we grow faster than market
  - Red (`<callout icon="🔴" color="red_bg">`) if market grows and we don't
- Write 2-3 sentences explaining WHY (not just stating facts)

### II. Конкуренты: кто вырос/упал и почему

Create competitor table:
| Бренд | Сегмент | Выручка (тек) | Дельта % | Ср. чек | SKU |

Then analyze:
- Top 3 fastest growing — what are they doing differently?
- Top 3 declining — what went wrong?
- Patterns: what do growing brands have in common?

### III. Наши топ-модели vs конкуренты

For each model (Wendy, Audrey, Ruby, Joy, Vuki, Moon):
- Our sales, revenue, avg price
- vs Top 3 competitor analogs (from rival_models data)
- Where we're significantly worse → growth focus
- Where we're better → preserve advantage

Use a callout for "main focus of the month" — 1-2 models with highest growth potential.

### IV. Контент и соцсети (if browser data available)

If social media / WB card data is present:
- Top 5 viral posts from competitors (link + why it worked)
- WB card patterns: what top performers do (covers, videos, infographics)
- Format: "Practice → Where seen → Why it works → How we test it"

If browser data is NOT available, write: "Секция требует ручного сбора данных командой."

### V. Гипотезы и действия

Generate 5-7 testable hypotheses. Each MUST follow this format:

**Наблюдение:** [what you noticed in data]
**Подтверждение:** [specific number or link]
**Действие:** [what to do, specific and implementable]
**Ожидаемый эффект:** [if X improves by Y% → +Z RUB/month]
**Метрика успеха:** [how to measure if hypothesis worked]
**Срок проверки:** [when to evaluate]

Prioritize Quick Wins first (low effort, high impact).

### Footer

- Data sources: MPStats API, Internal DB (WB+OZON), Browser research (if applicable)
- Quality caveats: MPStats estimates ±15-30%, known data gaps
- Verifier warnings (if any)

## Rules

1. **No fluff.** Never write "competitor X is doing great" — write "competitor X did THIS specifically, and we can do THIS"
2. **Only testable hypotheses.** Each must have a success metric and timeline
3. **Numbers always with delta.** Show both absolute (1 234 567) and percentage (+12.3%)
4. **Weighted averages only** for percentage metrics: `sum(numerator) / sum(denominator) * 100`
5. **If data is missing, say so.** Never fabricate or estimate without marking it
6. **Space-separated thousands** for all numbers: 1 234 567
7. **Notion tables:** use `<table>` with `header-row="true"` where appropriate
8. **Callouts:** use `<callout icon="emoji" color="color_bg">text</callout>` for insights

## Output

1. Write the full report to: `docs/reports/{{MONTH_LABEL}}-market-review.md`
2. Publish to Notion page ID: `2f458a2bd58780648974f98347b2d4d5`
   - Use Notion MCP tools
   - Title: "Обзор рынка — {{MONTH_LABEL}}"
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/market-review/prompts/analyst.md
git commit -m "feat(market-review): add analyst prompt (HEAVY LLM)"
```

---

### Task 12: Integration Test — Full Pipeline Dry Run

**Files:**
- No new files — end-to-end validation

- [ ] **Step 1: Run all unit tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/test_mpstats_client.py tests/test_market_review_collectors.py -v`
Expected: All tests PASS

- [ ] **Step 2: Test orchestrator with categories only**

Run:
```bash
python scripts/market_review/collect_all.py \
  --month 2026-03 \
  --sections "categories" \
  --output /tmp/market_review_test.json
```

Check output structure:
```bash
python -c "
import json
data = json.load(open('/tmp/market_review_test.json'))
print('Keys:', list(data.keys()))
print('Meta:', json.dumps(data.get('meta', {}), indent=2))
if 'market_categories' in data:
    cats = data['market_categories'].get('categories', {})
    print('Categories:', list(cats.keys()))
"
```

Expected: JSON with `market_categories` key containing category data, `meta` with month info

- [ ] **Step 3: Verify skill is discoverable**

Run: Check that `.claude/skills/market-review/SKILL.md` exists and has proper frontmatter:
```bash
head -10 .claude/skills/market-review/SKILL.md
```

Expected: YAML frontmatter with `name: market-review` and `triggers`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(market-review): complete skill with collectors, prompts, orchestrator"
```

---

## Summary

| Task | What it builds | Depends on |
|------|---------------|------------|
| 1 | MPStats API client | — |
| 2 | Config (categories, competitors) | — |
| 3 | Category trends collector | 1, 2 |
| 4 | Competitors brands collector | 1, 2 |
| 5 | Our performance collector (DB) | — |
| 6 | Top models collectors (ours + rivals) | 1, 2 |
| 7 | New items collector | 1, 2 |
| 8 | Orchestrator (collect_all.py) | 3, 4, 5, 6, 7 |
| 9 | Skill definition (SKILL.md) | — |
| 10 | Verifier prompt | — |
| 11 | Analyst prompt | — |
| 12 | Integration test | All above |

**Parallelizable:** Tasks 1+2 can run in parallel. Tasks 3-7 can run in parallel (all depend on 1+2). Tasks 9-11 can run in parallel with 3-7. Task 8 needs 3-7. Task 12 needs everything.
