# PIM Phase 6: External Data Integration & Detail Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stock/finance external data endpoints to Product Matrix API and rebuild the entity detail page with tabbed layout showing stock, unit-economics, and stubs for rating/tasks.

**Architecture:** New `ExternalDataService` in Product Matrix API queries contractor DB (via `shared/data_layer/_connection`) for stock and finance data, resolves marketplace keys from Supabase entities, and caches bulk results in-memory. Frontend rewrites `entity-detail-page.tsx` with shadcn/ui Tabs component and 5 tab panels.

**Tech Stack:** Python/FastAPI, SQLAlchemy, psycopg2 (via shared/_connection), cachetools, React 19/TypeScript, Tailwind CSS, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-03-21-product-matrix-phase6-design.md`

---

## File Structure

### Backend (main repo)

| File | Action | Responsibility |
|---|---|---|
| `services/product_matrix_api/services/external_data.py` | CREATE | `resolve_marketplace_key()`, `ExternalDataService` (stock + finance), SQL functions for full unit-economics, TTLCache |
| `services/product_matrix_api/routes/external_data.py` | CREATE | 2 GET endpoints: `/{entity}/{id}/stock`, `/{entity}/{id}/finance` |
| `services/product_matrix_api/models/schemas.py` | MODIFY | Add Pydantic schemas: StockChannel, MoySkladStock, StockResponse, ExpenseItem, DRR, FinanceChannel, FinanceDelta, FinanceResponse |
| `services/product_matrix_api/app.py` | MODIFY | Register external_data router |
| `tests/product_matrix_api/test_external_data.py` | CREATE | Tests for resolve_marketplace_key, stock endpoint, finance endpoint |

### Frontend (wookiee-hub/ repo)

| File | Action | Responsibility |
|---|---|---|
| `src/lib/matrix-api.ts` | MODIFY | Add TS types (StockResponse, FinanceResponse, etc.) + fetchEntityStock, fetchEntityFinance |
| `src/pages/product-matrix/entity-detail-page.tsx` | REWRITE | Tabbed layout with shadcn/ui Tabs |
| `src/components/matrix/tabs/info-tab.tsx` | CREATE | Entity fields grouped by section + related entities |
| `src/components/matrix/tabs/stock-tab.tsx` | CREATE | 3 stock cards (WB/Ozon/МойСклад) + turnover indicators |
| `src/components/matrix/tabs/finance-tab.tsx` | CREATE | KPI cards + expense table + DRR |
| `src/components/matrix/tabs/rating-tab.tsx` | CREATE | Stub placeholder |
| `src/components/matrix/tabs/tasks-tab.tsx` | CREATE | Stub placeholder |

---

## Task 1: Pydantic Schemas for Stock & Finance Responses

**Files:**
- Modify: `services/product_matrix_api/models/schemas.py`
- Test: `tests/product_matrix_api/test_external_data.py`

- [ ] **Step 1: Write schema validation test**

Create `tests/product_matrix_api/test_external_data.py`:

```python
"""Tests for external data integration (stock + finance endpoints)."""
import pytest
from services.product_matrix_api.models.schemas import (
    StockChannel, MoySkladStock, StockResponse,
    ExpenseItem, DRR, FinanceChannel, FinanceDelta, FinanceResponse,
)


def test_stock_response_with_null_channels():
    """StockResponse accepts null wb/ozon/moysklad."""
    resp = StockResponse(
        entity_type="models_osnova", entity_id=1, entity_name="Vuki",
        period_days=30, wb=None, ozon=None, moysklad=None,
        total_stock=0, total_turnover_days=None,
    )
    assert resp.wb is None
    assert resp.total_stock == 0


def test_stock_response_with_data():
    """StockResponse with all channels populated."""
    wb = StockChannel(stock_mp=142, daily_sales=34.2, turnover_days=4.2, sales_count=1045, days_in_stock=28)
    ozon = StockChannel(stock_mp=38, daily_sales=5.1, turnover_days=7.5, sales_count=152, days_in_stock=28)
    ms = MoySkladStock(stock_main=230, stock_transit=85, total=315, snapshot_date="2026-03-20", is_stale=False)
    resp = StockResponse(
        entity_type="models_osnova", entity_id=1, entity_name="Vuki",
        period_days=30, wb=wb, ozon=ozon, moysklad=ms,
        total_stock=495, total_turnover_days=12.6,
    )
    assert resp.wb.stock_mp == 142
    assert resp.moysklad.total == 315


def test_finance_response_with_expenses():
    """FinanceChannel with expenses dict and DRR."""
    expenses = {
        "commission": ExpenseItem(value=511900, pct=37.8, delta_value=452, delta_pct=-0.2),
        "logistics": ExpenseItem(value=126300, pct=9.3, delta_value=-2800, delta_pct=-0.3),
        "cost_price": ExpenseItem(value=262400, pct=19.4, delta_value=104, delta_pct=-0.1),
        "advertising": ExpenseItem(value=32900, pct=2.4, delta_value=-7400, delta_pct=-0.6),
        "storage": ExpenseItem(value=31700, pct=2.3, delta_value=-542, delta_pct=-0.1),
        "nds": ExpenseItem(value=42800, pct=3.2, delta_value=1200, delta_pct=0.1),
        "other": ExpenseItem(value=10700, pct=0.8, delta_value=-5100, delta_pct=-0.4),
    }
    ch = FinanceChannel(
        revenue_before_spp=1370000, revenue_after_spp=898556,
        margin=332000, margin_pct=24.5,
        orders_count=1045, orders_sum=2000000,
        sales_count=745, sales_sum=1400000,
        avg_check_before_spp=1816, avg_check_after_spp=1206,
        spp_pct=33.2, buyout_pct=71.3, returns_count=9, returns_pct=1.2,
        expenses=expenses, drr=DRR(total=2.6, internal=2.1, external=0.5),
    )
    assert ch.expenses["commission"].value == 511900
    assert ch.drr.total == 2.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py -v`
Expected: FAIL with ImportError (schemas not yet defined)

- [ ] **Step 3: Add schemas to schemas.py**

Add at the end of `services/product_matrix_api/models/schemas.py`:

```python
# ── External Data: Stock ─────────────────────────────────────────────────────

class StockChannel(BaseModel):
    stock_mp: float
    daily_sales: float
    turnover_days: float
    sales_count: int
    days_in_stock: int


class MoySkladStock(BaseModel):
    stock_main: float
    stock_transit: float
    total: float
    snapshot_date: str | None
    is_stale: bool


class StockResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_days: int
    wb: StockChannel | None
    ozon: StockChannel | None
    moysklad: MoySkladStock | None
    total_stock: float
    total_turnover_days: float | None


# ── External Data: Finance ───────────────────────────────────────────────────

class ExpenseItem(BaseModel):
    value: float
    pct: float
    delta_value: float | None = None
    delta_pct: float | None = None


class DRR(BaseModel):
    total: float
    internal: float
    external: float


class FinanceChannel(BaseModel):
    revenue_before_spp: float
    revenue_after_spp: float
    margin: float
    margin_pct: float
    orders_count: int
    orders_sum: float
    sales_count: int
    sales_sum: float
    avg_check_before_spp: float
    avg_check_after_spp: float
    spp_pct: float
    buyout_pct: float
    returns_count: int
    returns_pct: float
    expenses: dict[str, ExpenseItem]
    drr: DRR


class FinanceDelta(BaseModel):
    revenue_before_spp: float
    revenue_after_spp: float
    margin: float
    margin_pct: float
    orders_count: int
    orders_sum: float
    sales_count: int
    avg_check_before_spp: float
    avg_check_after_spp: float
    spp_pct: float
    buyout_pct: float
    returns_count: int
    returns_pct: float
    drr_total: float
    drr_internal: float
    drr_external: float


class FinanceResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str
    period_start: str
    period_end: str
    compare_period_start: str | None
    compare_period_end: str | None
    wb: FinanceChannel | None
    ozon: FinanceChannel | None
    delta_wb: FinanceDelta | None
    delta_ozon: FinanceDelta | None
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v --timeout=30`
Expected: all existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/models/schemas.py tests/product_matrix_api/test_external_data.py
git commit -m "feat(matrix): add Pydantic schemas for stock and finance external data responses"
```

---

## Task 2: resolve_marketplace_key + ExternalDataService Skeleton

**Files:**
- Create: `services/product_matrix_api/services/external_data.py`
- Test: `tests/product_matrix_api/test_external_data.py`

- [ ] **Step 1: Write resolve_marketplace_key tests**

Append to `tests/product_matrix_api/test_external_data.py`:

```python
from unittest.mock import MagicMock, patch, PropertyMock
from services.product_matrix_api.services.external_data import (
    resolve_marketplace_key, MarketplaceKey,
    ENTITIES_WITH_MP_DATA,
)


class TestResolveMarketplaceKey:
    def _mock_db(self):
        return MagicMock()

    def test_models_osnova_uses_kod(self):
        db = self._mock_db()
        record = MagicMock()
        record.kod = "Vuki"
        db.get.return_value = record

        key = resolve_marketplace_key("models_osnova", 1, db)
        assert key.level == "model"
        assert key.key == "vuki"

    def test_models_uses_kod(self):
        db = self._mock_db()
        record = MagicMock()
        record.kod = "VukiN"
        db.get.return_value = record

        key = resolve_marketplace_key("models", 1, db)
        assert key.level == "model"
        assert key.key == "vukin"

    def test_articles_uses_artikul(self):
        db = self._mock_db()
        record = MagicMock()
        record.artikul = "компбел-ж-бесшов/чер"
        db.get.return_value = record

        key = resolve_marketplace_key("articles", 1, db)
        assert key.level == "article"
        assert key.key == "компбел-ж-бесшов/чер"

    def test_products_uses_barkod(self):
        db = self._mock_db()
        record = MagicMock()
        record.barkod = "2000989949060"
        db.get.return_value = record

        key = resolve_marketplace_key("products", 1, db)
        assert key.level == "barcode"
        assert key.key == "2000989949060"

    def test_cards_wb_traverses_m2m(self):
        db = self._mock_db()
        record = MagicMock()
        t1, t2 = MagicMock(), MagicMock()
        t1.barkod = "2000989949060"
        t2.barkod = "2010165489006"
        record.tovary = [t1, t2]
        db.get.return_value = record

        key = resolve_marketplace_key("cards_wb", 1, db)
        assert key.level == "barcode_list"
        assert key.keys == ["2000989949060", "2010165489006"]
        assert key.channel == "wb"

    def test_unsupported_entity_raises(self):
        db = self._mock_db()
        with pytest.raises(ValueError, match="no marketplace mapping"):
            resolve_marketplace_key("colors", 1, db)

    def test_entities_with_mp_data_constant(self):
        assert "models_osnova" in ENTITIES_WITH_MP_DATA
        assert "colors" not in ENTITIES_WITH_MP_DATA
        assert "factories" not in ENTITIES_WITH_MP_DATA
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py::TestResolveMarketplaceKey -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create external_data.py with resolve logic**

Create `services/product_matrix_api/services/external_data.py`:

```python
"""External marketplace data integration for Product Matrix entities.

Provides stock/inventory and unit-economics data by resolving matrix entities
to marketplace keys and querying the contractor database.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from cachetools import TTLCache
from sqlalchemy.orm import Session

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, SleykaWB, SleykaOzon,
)
from shared.data_layer._connection import _get_wb_connection, _get_ozon_connection, to_float
from shared.data_layer._sql_fragments import WB_MARGIN_SQL
from shared.model_mapping import get_osnova_sql
from shared.data_layer.inventory import (
    get_wb_turnover_by_model,
    get_ozon_turnover_by_model,
    get_moysklad_stock_by_model,
)

from services.product_matrix_api.models.schemas import (
    StockChannel, MoySkladStock, StockResponse,
    ExpenseItem, DRR, FinanceChannel, FinanceDelta, FinanceResponse,
)

logger = logging.getLogger(__name__)

# Entity types that have marketplace data (stock/finance tabs visible)
ENTITIES_WITH_MP_DATA = frozenset({
    "models_osnova", "models", "articles", "products", "cards_wb", "cards_ozon",
})

# Bulk data cache: TTL 1 hour, max 32 entries
_bulk_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)

_BULK_FUNCS = {
    "wb_turnover": get_wb_turnover_by_model,
    "ozon_turnover": get_ozon_turnover_by_model,
    "moysklad": get_moysklad_stock_by_model,
}


@dataclass
class MarketplaceKey:
    level: str          # "model" | "article" | "barcode" | "barcode_list"
    key: str | None = None
    keys: list[str] | None = None
    channel: str | None = None  # "wb" | "ozon" | None (both)


def resolve_marketplace_key(entity_type: str, entity_id: int, db: Session) -> MarketplaceKey:
    """Resolve a matrix entity to its marketplace lookup key."""
    if entity_type == "models_osnova":
        record = db.get(ModelOsnova, entity_id)
        if not record:
            raise ValueError(f"ModelOsnova #{entity_id} not found")
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "models":
        record = db.get(Model, entity_id)
        if not record:
            raise ValueError(f"Model #{entity_id} not found")
        return MarketplaceKey(level="model", key=record.kod.lower())

    elif entity_type == "articles":
        record = db.get(Artikul, entity_id)
        if not record:
            raise ValueError(f"Artikul #{entity_id} not found")
        return MarketplaceKey(level="article", key=record.artikul.lower())

    elif entity_type == "products":
        record = db.get(Tovar, entity_id)
        if not record:
            raise ValueError(f"Tovar #{entity_id} not found")
        return MarketplaceKey(level="barcode", key=record.barkod)

    elif entity_type == "cards_wb":
        record = db.get(SleykaWB, entity_id)
        if not record:
            raise ValueError(f"SleykaWB #{entity_id} not found")
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="wb")

    elif entity_type == "cards_ozon":
        record = db.get(SleykaOzon, entity_id)
        if not record:
            raise ValueError(f"SleykaOzon #{entity_id} not found")
        barcodes = [t.barkod for t in record.tovary if t.barkod]
        return MarketplaceKey(level="barcode_list", keys=barcodes, channel="ozon")

    else:
        raise ValueError(f"Entity type '{entity_type}' has no marketplace mapping")


def _get_cached_bulk(func_name: str, *args):
    """Cache result of a bulk data_layer function."""
    cache_key = f"{func_name}:{args}"
    if cache_key not in _bulk_cache:
        _bulk_cache[cache_key] = _BULK_FUNCS[func_name](*args)
    return _bulk_cache[cache_key]


def _calc_dates(period_days: int, compare: str):
    """Calculate date ranges for finance queries.

    Returns (current_start, prev_start, current_end, compare_period_end).
    """
    today = date.today()
    current_end = today.isoformat()
    current_start = (today - timedelta(days=period_days)).isoformat()

    if compare == "week":
        prev_start = (today - timedelta(days=period_days + 7)).isoformat()
    elif compare == "month":
        prev_start = (today - timedelta(days=period_days + 30)).isoformat()
    else:
        prev_start = current_start

    compare_period_end = current_start if compare != "none" else None
    return current_start, prev_start, current_end, compare_period_end
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py::TestResolveMarketplaceKey -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/external_data.py tests/product_matrix_api/test_external_data.py
git commit -m "feat(matrix): add resolve_marketplace_key and ExternalDataService skeleton"
```

---

## Task 3: Stock Endpoint (Backend)

**Files:**
- Modify: `services/product_matrix_api/services/external_data.py`
- Create: `services/product_matrix_api/routes/external_data.py`
- Modify: `services/product_matrix_api/app.py`
- Test: `tests/product_matrix_api/test_external_data.py`

- [ ] **Step 1: Write stock endpoint test**

Append to `tests/product_matrix_api/test_external_data.py`:

```python
from fastapi.testclient import TestClient
from services.product_matrix_api.app import app

client = TestClient(app)


class TestStockEndpoint:
    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_cached_bulk")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_stock_model_level(self, mock_resolve, mock_bulk, mock_db):
        """GET /api/matrix/models_osnova/1/stock returns stock data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        mock_resolve.return_value = MarketplaceKey(level="model", key="vuki")
        mock_bulk.side_effect = lambda name, *args: {
            "wb_turnover": {"vuki": {"avg_stock": 142, "stock_mp": 142, "stock_moysklad": 0, "stock_transit": 0, "daily_sales": 34.2, "turnover_days": 4.2, "sales_count": 1045, "days_in_stock": 28, "revenue": 1370000, "margin": 332000, "low_sales": False}},
            "ozon_turnover": {"vuki": {"avg_stock": 38, "stock_mp": 38, "stock_moysklad": 0, "stock_transit": 0, "daily_sales": 5.1, "turnover_days": 7.5, "sales_count": 152, "days_in_stock": 28, "revenue": 200000, "margin": 40000, "low_sales": False}},
            "moysklad": {"vuki": {"stock_main": 230, "stock_transit": 85, "total": 315, "snapshot_date": "2026-03-20", "is_stale": False}},
        }[name]

        resp = client.get("/api/matrix/models_osnova/1/stock?period=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "models_osnova"
        assert data["wb"]["stock_mp"] == 142
        assert data["ozon"]["stock_mp"] == 38
        assert data["moysklad"]["stock_main"] == 230
        assert data["total_stock"] == 495  # 142 + 38 + 315

    @patch("services.product_matrix_api.routes.external_data.get_db")
    def test_stock_unsupported_entity_returns_404(self, mock_db):
        """GET /api/matrix/colors/1/stock returns 404."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        resp = client.get("/api/matrix/colors/1/stock")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py::TestStockEndpoint -v`
Expected: FAIL (route not registered)

- [ ] **Step 3: Add get_stock to ExternalDataService**

Append to `services/product_matrix_api/services/external_data.py`:

```python
class ExternalDataService:
    """Service for fetching external marketplace data for matrix entities."""

    @staticmethod
    def get_stock(entity_type: str, entity_id: int, period_days: int, db: Session) -> StockResponse:
        """Get stock/inventory data for a matrix entity."""
        key = resolve_marketplace_key(entity_type, entity_id, db)
        entity_name = _get_entity_name(entity_type, entity_id, db)

        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=period_days)).isoformat()

        wb_channel = None
        ozon_channel = None
        ms_stock = None

        if key.level == "model":
            wb_data = _get_cached_bulk("wb_turnover", start_date, end_date)
            ozon_data = _get_cached_bulk("ozon_turnover", start_date, end_date)
            ms_data = _get_cached_bulk("moysklad")

            wb_raw = wb_data.get(key.key)
            ozon_raw = ozon_data.get(key.key)
            ms_raw = ms_data.get(key.key)

            if wb_raw:
                wb_channel = StockChannel(
                    stock_mp=wb_raw["stock_mp"],
                    daily_sales=wb_raw["daily_sales"],
                    turnover_days=wb_raw["turnover_days"],
                    sales_count=wb_raw["sales_count"],
                    days_in_stock=wb_raw.get("days_in_stock", period_days),
                )
            if ozon_raw:
                ozon_channel = StockChannel(
                    stock_mp=ozon_raw["stock_mp"],
                    daily_sales=ozon_raw["daily_sales"],
                    turnover_days=ozon_raw["turnover_days"],
                    sales_count=ozon_raw["sales_count"],
                    days_in_stock=ozon_raw.get("days_in_stock", period_days),
                )
            if ms_raw:
                ms_stock = MoySkladStock(
                    stock_main=ms_raw["stock_main"],
                    stock_transit=ms_raw["stock_transit"],
                    total=ms_raw["total"],
                    snapshot_date=ms_raw.get("snapshot_date"),
                    is_stale=ms_raw.get("is_stale", False),
                )

        # TODO: article/barcode/barcode_list levels (Task 3b — future iteration)

        total = (
            (wb_channel.stock_mp if wb_channel else 0)
            + (ozon_channel.stock_mp if ozon_channel else 0)
            + (ms_stock.total if ms_stock else 0)
        )

        # Weighted turnover
        total_daily = (
            (wb_channel.daily_sales if wb_channel else 0)
            + (ozon_channel.daily_sales if ozon_channel else 0)
        )
        total_turnover = (total / total_daily) if total_daily > 0 else None

        return StockResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            period_days=period_days,
            wb=wb_channel,
            ozon=ozon_channel,
            moysklad=ms_stock,
            total_stock=total,
            total_turnover_days=round(total_turnover, 1) if total_turnover else None,
        )


def _get_entity_name(entity_type: str, entity_id: int, db: Session) -> str:
    """Get display name for an entity."""
    model_map = {
        "models_osnova": (ModelOsnova, "kod"),
        "models": (Model, "kod"),
        "articles": (Artikul, "artikul"),
        "products": (Tovar, "barkod"),
        "cards_wb": (SleykaWB, "nazvanie"),
        "cards_ozon": (SleykaOzon, "nazvanie"),
    }
    cls, attr = model_map[entity_type]
    record = db.get(cls, entity_id)
    return getattr(record, attr, f"#{entity_id}") if record else f"#{entity_id}"
```

- [ ] **Step 4: Create routes/external_data.py**

Create `services/product_matrix_api/routes/external_data.py`:

```python
"""External marketplace data routes: stock and finance for matrix entities."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import StockResponse, FinanceResponse
from services.product_matrix_api.services.external_data import (
    ExternalDataService, ENTITIES_WITH_MP_DATA,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matrix", tags=["external-data"])


def _validate_entity_has_mp(entity: str) -> None:
    if entity not in ENTITIES_WITH_MP_DATA:
        raise HTTPException(status_code=404, detail=f"Entity type '{entity}' has no marketplace data")


@router.get("/{entity}/{entity_id}/stock", response_model=StockResponse)
def get_entity_stock(
    entity: str,
    entity_id: int,
    period: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get stock/inventory data for a matrix entity."""
    _validate_entity_has_mp(entity)
    try:
        return ExternalDataService.get_stock(entity, entity_id, period, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Stock fetch failed for %s/%s", entity, entity_id)
        raise HTTPException(status_code=503, detail="Marketplace database temporarily unavailable")


@router.get("/{entity}/{entity_id}/finance", response_model=FinanceResponse)
def get_entity_finance(
    entity: str,
    entity_id: int,
    period: int = Query(7, ge=1, le=365),
    compare: str = Query("week", pattern="^(week|month|none)$"),
    db: Session = Depends(get_db),
):
    """Get unit-economics data for a matrix entity."""
    _validate_entity_has_mp(entity)
    try:
        return ExternalDataService.get_finance(entity, entity_id, period, compare, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Finance fetch failed for %s/%s", entity, entity_id)
        raise HTTPException(status_code=503, detail="Marketplace database temporarily unavailable")
```

- [ ] **Step 5: Register router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.external_data import router as external_data_router
# ... (after other router imports)
app.include_router(external_data_router)
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py -v`
Expected: all tests PASS

- [ ] **Step 7: Run full test suite**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v --timeout=30`
Expected: all tests PASS (no regressions)

- [ ] **Step 8: Commit**

```bash
git add services/product_matrix_api/services/external_data.py services/product_matrix_api/routes/external_data.py services/product_matrix_api/app.py tests/product_matrix_api/test_external_data.py
git commit -m "feat(matrix): add stock endpoint with model-level turnover data"
```

---

## Task 4: Finance Endpoint (Backend)

**Files:**
- Modify: `services/product_matrix_api/services/external_data.py`
- Test: `tests/product_matrix_api/test_external_data.py`

- [ ] **Step 1: Write finance endpoint test**

Append to `tests/product_matrix_api/test_external_data.py`:

```python
class TestFinanceEndpoint:
    @patch("services.product_matrix_api.routes.external_data.get_db")
    @patch("services.product_matrix_api.services.external_data._get_full_wb_finance")
    @patch("services.product_matrix_api.services.external_data._get_full_ozon_finance")
    @patch("services.product_matrix_api.services.external_data.resolve_marketplace_key")
    def test_finance_model_level(self, mock_resolve, mock_ozon_fin, mock_wb_fin, mock_db):
        """GET /api/matrix/models_osnova/1/finance returns finance data."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])
        mock_resolve.return_value = MarketplaceKey(level="model", key="vuki")

        # Mock WB finance: sales_data tuple + orders_data tuple
        # (period, sales_count, revenue_before_spp, revenue_after_spp, adv_int, adv_ext, cost, logistics, storage, commission, spp, nds, penalty, retention, deduction, margin, returns_revenue)
        mock_wb_fin.return_value = (
            [("current", 745, 1370000, 898556, 30000, 2900, 262400, 126300, 31700, 511900, 471444, 42800, 1000, 500, 200, 332000, 13589)],
            [("current", 1045, 2000000)],
        )
        mock_ozon_fin.return_value = ([], [])

        resp = client.get("/api/matrix/models_osnova/1/finance?period=7&compare=none")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wb"] is not None
        assert data["wb"]["revenue_before_spp"] == 1370000
        assert data["wb"]["margin"] == 332000
        assert data["wb"]["orders_count"] == 1045
        assert "commission" in data["wb"]["expenses"]
        assert data["ozon"] is None

    @patch("services.product_matrix_api.routes.external_data.get_db")
    def test_finance_unsupported_entity_returns_404(self, mock_db):
        """GET /api/matrix/factories/1/finance returns 404."""
        mock_session = MagicMock()
        mock_db.return_value = iter([mock_session])

        resp = client.get("/api/matrix/factories/1/finance")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py::TestFinanceEndpoint -v`
Expected: FAIL

- [ ] **Step 3: Add _get_full_wb_finance and _get_full_ozon_finance**

Add to `services/product_matrix_api/services/external_data.py`:

```python
def _get_full_wb_finance(current_start: str, prev_start: str, current_end: str, model_key: str):
    """Full WB unit-economics for a single model. Two SQL queries."""
    conn = _get_wb_connection()
    cur = conn.cursor()

    try:
        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(full_counts) as sales_count,
            SUM(revenue_spp) - COALESCE(SUM(revenue_return_spp), 0) as revenue_before_spp,
            SUM(revenue) - COALESCE(SUM(revenue_return), 0) as revenue_after_spp,
            SUM(reclama) as adv_internal,
            SUM(reclama_vn + COALESCE(reclama_vn_vk, 0)) as adv_external,
            SUM(sebes) as cost_of_goods,
            SUM(logist) as logistics,
            SUM(storage) as storage,
            SUM(comis_spp) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            SUM(penalty) as penalty,
            SUM(retention) as retention,
            SUM(deduction) as deduction,
            {WB_MARGIN_SQL} as margin,
            COALESCE(SUM(revenue_return_spp), 0) as returns_revenue
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND {get_osnova_sql("SPLIT_PART(article, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        sales_data = cur.fetchall()

        cur.execute(f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(pricewithdisc) as orders_rub
        FROM orders
        WHERE date >= %s AND date < %s
          AND {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return sales_data, orders_data


def _get_full_ozon_finance(current_start: str, prev_start: str, current_end: str, model_key: str):
    """Full Ozon unit-economics for a single model. Two SQL queries."""
    conn = _get_ozon_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            SUM(count_end) as sales_count,
            SUM(price_end) as revenue_before_spp,
            SUM(price_end_spp) as revenue_after_spp,
            SUM(reclama_end) as adv_internal,
            SUM(adv_vn) as adv_external,
            SUM(sebes_end) as cost_of_goods,
            SUM(logist_end) as logistics,
            SUM(storage_end) as storage,
            SUM(comission_end) as commission,
            SUM(spp) as spp_amount,
            SUM(nds) as nds,
            0 as penalty, 0 as retention, 0 as deduction,
            SUM(marga) - SUM(nds) as margin,
            0 as returns_revenue
        FROM abc_date
        WHERE date >= %s AND date < %s
          AND LOWER(SPLIT_PART(article, '/', 1)) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        sales_data = cur.fetchall()

        cur.execute("""
        SELECT
            CASE WHEN in_process_at::date >= %s THEN 'current' ELSE 'previous' END as period,
            COUNT(*) as orders_count,
            SUM(price) as orders_rub
        FROM orders
        WHERE in_process_at::date >= %s AND in_process_at::date < %s
          AND LOWER(SPLIT_PART(offer_id, '/', 1)) = %s
        GROUP BY 1
        ORDER BY period DESC;
        """, (current_start, prev_start, current_end, model_key))
        orders_data = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return sales_data, orders_data
```

- [ ] **Step 4: Add get_finance to ExternalDataService and _build_finance_channel helper**

Add to `ExternalDataService` class and module:

```python
def _build_finance_channel(sales_row, orders_row) -> FinanceChannel | None:
    """Build FinanceChannel from raw SQL row tuples."""
    if not sales_row:
        return None

    # Unpack sales: (period, sales_count, rev_before, rev_after, adv_int, adv_ext, cost, logistics, storage, commission, spp, nds, penalty, retention, deduction, margin, returns_rev)
    (_, sales_count, rev_before, rev_after, adv_int, adv_ext, cost,
     logistics, storage, commission, spp, nds, penalty, retention,
     deduction, margin, returns_rev) = sales_row

    sales_count = int(to_float(sales_count))
    rev_before = to_float(rev_before)
    rev_after = to_float(rev_after)
    margin_val = to_float(margin)

    orders_count = int(to_float(orders_row[1])) if orders_row else 0
    orders_rub = to_float(orders_row[2]) if orders_row else 0

    margin_pct = (margin_val / rev_before * 100) if rev_before > 0 else 0
    avg_before = rev_before / sales_count if sales_count > 0 else 0
    avg_after = rev_after / sales_count if sales_count > 0 else 0
    spp_pct = (1 - rev_after / rev_before) * 100 if rev_before > 0 else 0
    buyout_pct = (sales_count / orders_count * 100) if orders_count > 0 else 0
    returns_count = max(0, orders_count - sales_count)
    returns_pct = (returns_count / orders_count * 100) if orders_count > 0 else 0

    total_adv = to_float(adv_int) + to_float(adv_ext)
    drr_total = (total_adv / orders_rub * 100) if orders_rub > 0 else 0
    drr_int = (to_float(adv_int) / orders_rub * 100) if orders_rub > 0 else 0
    drr_ext = (to_float(adv_ext) / orders_rub * 100) if orders_rub > 0 else 0

    def _expense(val):
        v = to_float(val)
        return ExpenseItem(value=v, pct=(v / rev_before * 100) if rev_before > 0 else 0)

    expenses = {
        "commission": _expense(commission),
        "logistics": _expense(logistics),
        "cost_price": _expense(cost),
        "advertising": _expense(total_adv),
        "storage": _expense(storage),
        "nds": _expense(nds),
        "other": _expense(to_float(penalty) + to_float(retention) + to_float(deduction)),
    }

    return FinanceChannel(
        revenue_before_spp=rev_before, revenue_after_spp=rev_after,
        margin=margin_val, margin_pct=round(margin_pct, 1),
        orders_count=orders_count, orders_sum=orders_rub,
        sales_count=sales_count, sales_sum=rev_before,
        avg_check_before_spp=round(avg_before, 0), avg_check_after_spp=round(avg_after, 0),
        spp_pct=round(spp_pct, 1), buyout_pct=round(buyout_pct, 1),
        returns_count=returns_count, returns_pct=round(returns_pct, 1),
        expenses=expenses, drr=DRR(total=round(drr_total, 1), internal=round(drr_int, 1), external=round(drr_ext, 1)),
    )


def _build_delta(current: FinanceChannel, previous: FinanceChannel) -> FinanceDelta:
    """Compute delta between current and previous period."""
    return FinanceDelta(
        revenue_before_spp=current.revenue_before_spp - previous.revenue_before_spp,
        revenue_after_spp=current.revenue_after_spp - previous.revenue_after_spp,
        margin=current.margin - previous.margin,
        margin_pct=round(current.margin_pct - previous.margin_pct, 1),
        orders_count=current.orders_count - previous.orders_count,
        orders_sum=current.orders_sum - previous.orders_sum,
        sales_count=current.sales_count - previous.sales_count,
        avg_check_before_spp=round(current.avg_check_before_spp - previous.avg_check_before_spp, 0),
        avg_check_after_spp=round(current.avg_check_after_spp - previous.avg_check_after_spp, 0),
        spp_pct=round(current.spp_pct - previous.spp_pct, 1),
        buyout_pct=round(current.buyout_pct - previous.buyout_pct, 1),
        returns_count=current.returns_count - previous.returns_count,
        returns_pct=round(current.returns_pct - previous.returns_pct, 1),
        drr_total=round(current.drr.total - previous.drr.total, 1),
        drr_internal=round(current.drr.internal - previous.drr.internal, 1),
        drr_external=round(current.drr.external - previous.drr.external, 1),
    )
```

Add `get_finance` to `ExternalDataService`:

```python
    @staticmethod
    def get_finance(entity_type: str, entity_id: int, period_days: int,
                    compare: str, db: Session) -> FinanceResponse:
        """Get unit-economics data for a matrix entity."""
        key = resolve_marketplace_key(entity_type, entity_id, db)
        entity_name = _get_entity_name(entity_type, entity_id, db)
        current_start, prev_start, current_end, compare_end = _calc_dates(period_days, compare)

        wb_channel = None
        ozon_channel = None
        delta_wb = None
        delta_ozon = None

        if key.level == "model":
            # WB
            wb_sales, wb_orders = _get_full_wb_finance(current_start, prev_start, current_end, key.key)
            wb_current_sales = next((r for r in wb_sales if r[0] == "current"), None)
            wb_prev_sales = next((r for r in wb_sales if r[0] == "previous"), None)
            wb_current_orders = next((r for r in wb_orders if r[0] == "current"), None)
            wb_prev_orders = next((r for r in wb_orders if r[0] == "previous"), None)

            wb_channel = _build_finance_channel(wb_current_sales, wb_current_orders)

            if compare != "none" and wb_prev_sales and wb_channel:
                wb_prev_channel = _build_finance_channel(wb_prev_sales, wb_prev_orders)
                if wb_prev_channel:
                    delta_wb = _build_delta(wb_channel, wb_prev_channel)
                    # Fill expense deltas
                    for exp_key in wb_channel.expenses:
                        if exp_key in wb_prev_channel.expenses:
                            wb_channel.expenses[exp_key].delta_value = round(
                                wb_channel.expenses[exp_key].value - wb_prev_channel.expenses[exp_key].value, 0)
                            wb_channel.expenses[exp_key].delta_pct = round(
                                wb_channel.expenses[exp_key].pct - wb_prev_channel.expenses[exp_key].pct, 1)

            # Ozon (same pattern)
            oz_sales, oz_orders = _get_full_ozon_finance(current_start, prev_start, current_end, key.key)
            oz_current_sales = next((r for r in oz_sales if r[0] == "current"), None)
            oz_prev_sales = next((r for r in oz_sales if r[0] == "previous"), None)
            oz_current_orders = next((r for r in oz_orders if r[0] == "current"), None)
            oz_prev_orders = next((r for r in oz_orders if r[0] == "previous"), None)

            ozon_channel = _build_finance_channel(oz_current_sales, oz_current_orders)

            if compare != "none" and oz_prev_sales and ozon_channel:
                oz_prev_channel = _build_finance_channel(oz_prev_sales, oz_prev_orders)
                if oz_prev_channel:
                    delta_ozon = _build_delta(ozon_channel, oz_prev_channel)
                    for exp_key in ozon_channel.expenses:
                        if exp_key in oz_prev_channel.expenses:
                            ozon_channel.expenses[exp_key].delta_value = round(
                                ozon_channel.expenses[exp_key].value - oz_prev_channel.expenses[exp_key].value, 0)
                            ozon_channel.expenses[exp_key].delta_pct = round(
                                ozon_channel.expenses[exp_key].pct - oz_prev_channel.expenses[exp_key].pct, 1)

        return FinanceResponse(
            entity_type=entity_type, entity_id=entity_id, entity_name=entity_name,
            period_start=current_start, period_end=current_end,
            compare_period_start=prev_start if compare != "none" else None,
            compare_period_end=compare_end,
            wb=wb_channel, ozon=ozon_channel,
            delta_wb=delta_wb, delta_ozon=delta_ozon,
        )
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_external_data.py -v`
Expected: all tests PASS

- [ ] **Step 6: Run full test suite**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v --timeout=30`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/product_matrix_api/services/external_data.py tests/product_matrix_api/test_external_data.py
git commit -m "feat(matrix): add finance endpoint with full unit-economics and delta comparison"
```

---

## Task 5: Frontend — TypeScript Types + API Client

**Files:**
- Modify: `wookiee-hub/src/lib/matrix-api.ts`

- [ ] **Step 1: Add TypeScript interfaces and API functions**

Add to `wookiee-hub/src/lib/matrix-api.ts`, before the `matrixApi` export:

```typescript
// ── External Data Types ─────────────────────────────────────────────────────

export interface StockChannel {
  stock_mp: number;
  daily_sales: number;
  turnover_days: number;
  sales_count: number;
  days_in_stock: number;
}

export interface MoySkladStock {
  stock_main: number;
  stock_transit: number;
  total: number;
  snapshot_date: string | null;
  is_stale: boolean;
}

export interface StockResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_days: number;
  wb: StockChannel | null;
  ozon: StockChannel | null;
  moysklad: MoySkladStock | null;
  total_stock: number;
  total_turnover_days: number | null;
}

export interface ExpenseItem {
  value: number;
  pct: number;
  delta_value: number | null;
  delta_pct: number | null;
}

export interface DRR {
  total: number;
  internal: number;
  external: number;
}

export interface FinanceChannel {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  sales_sum: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  expenses: Record<string, ExpenseItem>;
  drr: DRR;
}

export interface FinanceDelta {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  drr_total: number;
  drr_internal: number;
  drr_external: number;
}

export interface FinanceResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_start: string;
  period_end: string;
  compare_period_start: string | null;
  compare_period_end: string | null;
  wb: FinanceChannel | null;
  ozon: FinanceChannel | null;
  delta_wb: FinanceDelta | null;
  delta_ozon: FinanceDelta | null;
}
```

Add to the `matrixApi` object:

```typescript
  // External data
  fetchEntityStock: (entity: string, id: number, period = 30) =>
    get<StockResponse>(`/api/matrix/${entity}/${id}/stock`, { period }),

  fetchEntityFinance: (entity: string, id: number, period = 7, compare = "week") =>
    get<FinanceResponse>(`/api/matrix/${entity}/${id}/finance`, { period, compare }),
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit (in wookiee-hub repo)**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/lib/matrix-api.ts
git commit -m "feat(matrix): add TypeScript types and API client for stock/finance endpoints"
```

---

## Task 6: Frontend — Stub Tabs (Rating + Tasks)

**Files:**
- Create: `wookiee-hub/src/components/matrix/tabs/rating-tab.tsx`
- Create: `wookiee-hub/src/components/matrix/tabs/tasks-tab.tsx`

- [ ] **Step 1: Create rating-tab.tsx**

Create `wookiee-hub/src/components/matrix/tabs/rating-tab.tsx`:

```tsx
export function RatingTab() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-lg font-medium">Средний рейтинг: — | Отзывы: —</p>
      <p className="mt-2 text-sm">Функционал будет доступен в следующей версии.</p>
    </div>
  );
}
```

- [ ] **Step 2: Create tasks-tab.tsx**

Create `wookiee-hub/src/components/matrix/tabs/tasks-tab.tsx`:

```tsx
export function TasksTab() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-lg font-medium">Задачи</p>
      <p className="mt-2 text-sm">Задачи будут доступны в следующей версии.</p>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/components/matrix/tabs/rating-tab.tsx src/components/matrix/tabs/tasks-tab.tsx
git commit -m "feat(matrix): add stub tabs for rating and tasks"
```

---

## Task 7: Frontend — Stock Tab

**Files:**
- Create: `wookiee-hub/src/components/matrix/tabs/stock-tab.tsx`

- [ ] **Step 1: Create stock-tab.tsx**

Create `wookiee-hub/src/components/matrix/tabs/stock-tab.tsx`:

```tsx
import { useApiQuery } from "@/hooks/use-api-query";
import { matrixApi, type StockResponse, type StockChannel, type MoySkladStock } from "@/lib/matrix-api";
import { cn } from "@/lib/utils";

interface StockTabProps {
  entityType: string;
  entityId: number;
}

function turnoverColor(days: number): string {
  if (days < 3) return "text-red-600 bg-red-50 border-red-200";
  if (days < 7) return "text-yellow-600 bg-yellow-50 border-yellow-200";
  if (days <= 30) return "text-green-600 bg-green-50 border-green-200";
  return "text-gray-500 bg-gray-50 border-gray-200";
}

function turnoverLabel(days: number): string {
  if (days < 3) return "Риск OOS";
  if (days < 7) return "Мало";
  if (days <= 30) return "Норма";
  return "Затоваривание";
}

function formatNum(n: number): string {
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

function ChannelCard({ title, channel }: { title: string; channel: StockChannel }) {
  return (
    <div className={cn("rounded-lg border p-4", turnoverColor(channel.turnover_days))}>
      <h3 className="text-sm font-medium opacity-70">{title}</h3>
      <p className="mt-1 text-2xl font-bold">{formatNum(channel.stock_mp)} шт</p>
      <div className="mt-2 space-y-1 text-sm">
        <p>{formatNum(channel.turnover_days)} дн. ({turnoverLabel(channel.turnover_days)})</p>
        <p>{formatNum(channel.daily_sales)} шт/день</p>
        <p className="opacity-70">Продаж за период: {channel.sales_count}</p>
      </div>
    </div>
  );
}

function MoySkladCard({ data }: { data: MoySkladStock }) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-blue-700">
      <h3 className="text-sm font-medium opacity-70">МойСклад</h3>
      <p className="mt-1 text-2xl font-bold">{formatNum(data.total)} шт</p>
      <div className="mt-2 space-y-1 text-sm">
        <p>Склад: {formatNum(data.stock_main)}</p>
        <p>В пути: {formatNum(data.stock_transit)}</p>
        {data.is_stale && (
          <p className="text-orange-600">Данные от {data.snapshot_date}</p>
        )}
      </div>
    </div>
  );
}

export function StockTab({ entityType, entityId }: StockTabProps) {
  const { data, loading } = useApiQuery(
    () => matrixApi.fetchEntityStock(entityType, entityId),
    [entityType, entityId],
  );

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-4 p-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (!data) {
    return <p className="p-4 text-muted-foreground">Нет данных</p>;
  }

  return (
    <div className="space-y-4 p-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {data.wb && <ChannelCard title="WB FBO" channel={data.wb} />}
        {data.ozon && <ChannelCard title="Ozon FBO" channel={data.ozon} />}
        {data.moysklad && <MoySkladCard data={data.moysklad} />}
      </div>

      {!data.wb && !data.ozon && !data.moysklad && (
        <p className="text-muted-foreground">Нет данных об остатках для этой записи.</p>
      )}

      <div className="flex items-center gap-6 rounded-lg border bg-muted/30 p-3 text-sm">
        <span>Итого: <strong>{formatNum(data.total_stock)} шт</strong></span>
        {data.total_turnover_days != null && (
          <span>Оборачиваемость: <strong>{formatNum(data.total_turnover_days)} дней</strong></span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/components/matrix/tabs/stock-tab.tsx
git commit -m "feat(matrix): add stock tab with turnover indicators and МойСклад card"
```

---

## Task 8: Frontend — Finance Tab

**Files:**
- Create: `wookiee-hub/src/components/matrix/tabs/finance-tab.tsx`

- [ ] **Step 1: Create finance-tab.tsx**

Create `wookiee-hub/src/components/matrix/tabs/finance-tab.tsx`:

```tsx
import { useState } from "react";
import { useApiQuery } from "@/hooks/use-api-query";
import { matrixApi, type FinanceResponse, type FinanceChannel, type FinanceDelta, type ExpenseItem } from "@/lib/matrix-api";
import { cn } from "@/lib/utils";

interface FinanceTabProps {
  entityType: string;
  entityId: number;
}

type ChannelFilter = "all" | "wb" | "ozon";

function fmtRub(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} млн`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)} тыс`;
  return n.toFixed(0);
}

function fmtPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

function DeltaArrow({ value, suffix = "" }: { value: number | null; suffix?: string }) {
  if (value == null) return null;
  const color = value > 0 ? "text-green-600" : value < 0 ? "text-red-600" : "text-muted-foreground";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "→";
  return <span className={cn("text-sm", color)}>{arrow} {fmtRub(Math.abs(value))}{suffix}</span>;
}

function KpiCard({ title, mainValue, subValue, delta }: {
  title: string;
  mainValue: string;
  subValue?: string;
  delta?: number | null;
}) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 text-2xl font-bold">{mainValue}</p>
      {subValue && <p className="text-sm text-muted-foreground">{subValue}</p>}
      {delta != null && <DeltaArrow value={delta} />}
    </div>
  );
}

const EXPENSE_LABELS: Record<string, string> = {
  commission: "Комиссия",
  logistics: "Логистика",
  cost_price: "Себестоимость",
  advertising: "Реклама",
  storage: "Хранение",
  nds: "НДС",
  other: "Ост. расходы",
};

const EXPENSE_ORDER = ["commission", "logistics", "cost_price", "advertising", "storage", "nds", "other"];

function ExpenseTable({ expenses }: { expenses: Record<string, ExpenseItem> }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-muted-foreground">
          <th className="py-2">Расходы</th>
          <th className="py-2 text-right">Сумма</th>
          <th className="py-2 text-right">%</th>
          <th className="py-2 text-right">Δ</th>
          <th className="py-2 text-right">Δ%</th>
        </tr>
      </thead>
      <tbody>
        {EXPENSE_ORDER.map((key) => {
          const item = expenses[key];
          if (!item) return null;
          return (
            <tr key={key} className="border-b">
              <td className="py-2">{EXPENSE_LABELS[key] ?? key}</td>
              <td className="py-2 text-right font-mono">{fmtRub(item.value)}</td>
              <td className="py-2 text-right font-mono">{fmtPct(item.pct)}</td>
              <td className="py-2 text-right">
                <DeltaArrow value={item.delta_value} />
              </td>
              <td className="py-2 text-right">
                <DeltaArrow value={item.delta_pct} suffix=" п.п." />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function combineChannels(wb: FinanceChannel | null, ozon: FinanceChannel | null): FinanceChannel | null {
  if (!wb && !ozon) return null;
  if (!wb) return ozon;
  if (!ozon) return wb;

  const totalRev = wb.revenue_before_spp + ozon.revenue_before_spp;

  // Combine expenses
  const expenses: Record<string, ExpenseItem> = {};
  for (const key of EXPENSE_ORDER) {
    const wbE = wb.expenses[key];
    const ozE = ozon.expenses[key];
    const val = (wbE?.value ?? 0) + (ozE?.value ?? 0);
    const pct = totalRev > 0 ? (val / totalRev) * 100 : 0;
    const dv = (wbE?.delta_value ?? 0) + (ozE?.delta_value ?? 0);
    expenses[key] = { value: val, pct, delta_value: dv, delta_pct: null };
  }

  const totalMargin = wb.margin + ozon.margin;

  return {
    revenue_before_spp: totalRev,
    revenue_after_spp: wb.revenue_after_spp + ozon.revenue_after_spp,
    margin: totalMargin,
    margin_pct: totalRev > 0 ? (totalMargin / totalRev) * 100 : 0,
    orders_count: wb.orders_count + ozon.orders_count,
    orders_sum: wb.orders_sum + ozon.orders_sum,
    sales_count: wb.sales_count + ozon.sales_count,
    sales_sum: wb.sales_sum + ozon.sales_sum,
    avg_check_before_spp: totalRev / (wb.sales_count + ozon.sales_count || 1),
    avg_check_after_spp: (wb.revenue_after_spp + ozon.revenue_after_spp) / (wb.sales_count + ozon.sales_count || 1),
    spp_pct: totalRev > 0 ? (1 - (wb.revenue_after_spp + ozon.revenue_after_spp) / totalRev) * 100 : 0,
    buyout_pct: (wb.orders_count + ozon.orders_count) > 0
      ? ((wb.sales_count + ozon.sales_count) / (wb.orders_count + ozon.orders_count)) * 100
      : 0,
    returns_count: wb.returns_count + ozon.returns_count,
    returns_pct: (wb.orders_count + ozon.orders_count) > 0
      ? ((wb.returns_count + ozon.returns_count) / (wb.orders_count + ozon.orders_count)) * 100
      : 0,
    expenses,
    drr: {
      total: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.total * wb.orders_sum + ozon.drr.total * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
      internal: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.internal * wb.orders_sum + ozon.drr.internal * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
      external: (wb.orders_sum + ozon.orders_sum) > 0
        ? ((wb.drr.external * wb.orders_sum + ozon.drr.external * ozon.orders_sum) / (wb.orders_sum + ozon.orders_sum))
        : 0,
    },
  };
}

export function FinanceTab({ entityType, entityId }: FinanceTabProps) {
  const [filter, setFilter] = useState<ChannelFilter>("all");

  const { data, loading } = useApiQuery(
    () => matrixApi.fetchEntityFinance(entityType, entityId),
    [entityType, entityId],
  );

  if (loading) {
    return (
      <div className="space-y-4 p-4">
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-32 animate-pulse rounded-lg bg-muted" />)}
        </div>
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!data) return <p className="p-4 text-muted-foreground">Нет данных</p>;

  const ch: FinanceChannel | null =
    filter === "wb" ? data.wb :
    filter === "ozon" ? data.ozon :
    combineChannels(data.wb, data.ozon);

  const delta: FinanceDelta | null =
    filter === "wb" ? data.delta_wb :
    filter === "ozon" ? data.delta_ozon :
    null; // combined delta not computed for "all" mode

  if (!ch) return <p className="p-4 text-muted-foreground">Нет финансовых данных для этого канала.</p>;

  return (
    <div className="space-y-6 p-4">
      {/* Channel filter */}
      <div className="flex gap-2">
        {(["all", "wb", "ozon"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-md px-3 py-1 text-sm transition-colors",
              filter === f ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80",
            )}
          >
            {f === "all" ? "Все" : f === "wb" ? "WB" : "Ozon"}
          </button>
        ))}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          title="Заказы до СПП"
          mainValue={`${fmtRub(ch.orders_sum)} ₽`}
          subValue={`${ch.orders_count.toLocaleString("ru-RU")} шт`}
          delta={delta?.orders_sum}
        />
        <KpiCard
          title="Продажи до СПП"
          mainValue={`${fmtRub(ch.sales_sum)} ₽`}
          subValue={`${ch.sales_count.toLocaleString("ru-RU")} шт`}
          delta={delta?.revenue_before_spp}
        />
        <KpiCard
          title="Маржа"
          mainValue={`${fmtRub(ch.margin)} ₽`}
          subValue={fmtPct(ch.margin_pct)}
          delta={delta?.margin}
        />
      </div>

      {/* Expense table */}
      <div className="rounded-lg border p-4">
        <ExpenseTable expenses={ch.expenses} />
      </div>

      {/* Additional metrics */}
      <div className="grid grid-cols-2 gap-4 rounded-lg border p-4 text-sm md:grid-cols-4">
        <div>
          <p className="text-muted-foreground">Ср. чек до СПП</p>
          <p className="font-mono font-medium">{fmtRub(ch.avg_check_before_spp)} ₽</p>
        </div>
        <div>
          <p className="text-muted-foreground">Ср. чек после СПП</p>
          <p className="font-mono font-medium">{fmtRub(ch.avg_check_after_spp)} ₽</p>
        </div>
        <div>
          <p className="text-muted-foreground">СПП</p>
          <p className="font-mono font-medium">{fmtPct(ch.spp_pct)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Выкупаемость</p>
          <p className="font-mono font-medium">{fmtPct(ch.buyout_pct)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Возвраты</p>
          <p className="font-mono font-medium">{ch.returns_count} шт ({fmtPct(ch.returns_pct)})</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR общий</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.total)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR внутр.</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.internal)}</p>
        </div>
        <div>
          <p className="text-muted-foreground">DRR внешн.</p>
          <p className="font-mono font-medium">{fmtPct(ch.drr.external)}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/components/matrix/tabs/finance-tab.tsx
git commit -m "feat(matrix): add finance tab with KPI cards, expense table, and channel filter"
```

---

## Task 9: Frontend — Info Tab

**Files:**
- Create: `wookiee-hub/src/components/matrix/tabs/info-tab.tsx`

- [ ] **Step 1: Create info-tab.tsx**

Create `wookiee-hub/src/components/matrix/tabs/info-tab.tsx`:

```tsx
import { Link } from "react-router-dom";

interface InfoTabProps {
  data: Record<string, unknown>;
  entityType: string;
  children?: Array<{ type: string; label: string; items: Array<{ id: number; name: string }> }>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">{title}</h3>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: unknown }) {
  const display = value == null || value === "" ? "—" : String(value);
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm">{display}</span>
    </div>
  );
}

function RelatedList({ title, entityType, items }: {
  title: string;
  entityType: string;
  items: Array<{ id: number; name: string }>;
}) {
  if (!items.length) return null;
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-medium text-muted-foreground">{title} ({items.length})</h4>
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              to={`/product/matrix/${entityType}/${item.id}`}
              className="text-sm text-primary hover:underline"
            >
              {item.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Fields to skip in display (internal/technical)
const SKIP_FIELDS = new Set(["id", "created_at", "updated_at", "status_id"]);

export function InfoTab({ data, entityType, children }: InfoTabProps) {
  const fields = Object.entries(data).filter(([k]) => !SKIP_FIELDS.has(k));

  return (
    <div className="space-y-6 p-4">
      <Section title="Основные">
        {fields.map(([key, value]) => (
          <Field key={key} label={key} value={value} />
        ))}
      </Section>

      {children && children.length > 0 && (
        <div className="space-y-4 border-t pt-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Связанные</h3>
          {children.map((group) => (
            <RelatedList
              key={group.type}
              title={group.label}
              entityType={group.type}
              items={group.items}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/components/matrix/tabs/info-tab.tsx
git commit -m "feat(matrix): add info tab with field display and related entities"
```

---

## Task 10: Frontend — Rewrite Entity Detail Page with Tabs

**Files:**
- Rewrite: `wookiee-hub/src/pages/product-matrix/entity-detail-page.tsx`

- [ ] **Step 1: Rewrite entity-detail-page.tsx**

Rewrite `wookiee-hub/src/pages/product-matrix/entity-detail-page.tsx`:

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { get } from "@/lib/api-client";
import { matrixApi } from "@/lib/matrix-api";
import { InfoTab } from "@/components/matrix/tabs/info-tab";
import { StockTab } from "@/components/matrix/tabs/stock-tab";
import { FinanceTab } from "@/components/matrix/tabs/finance-tab";
import { RatingTab } from "@/components/matrix/tabs/rating-tab";
import { TasksTab } from "@/components/matrix/tabs/tasks-tab";

const ENTITIES_WITH_MP = new Set([
  "models_osnova", "models", "articles", "products", "cards_wb", "cards_ozon",
]);

const ENTITY_LABELS: Record<string, string> = {
  models_osnova: "Модель основа",
  models: "Модель",
  articles: "Артикул",
  products: "Товар",
  colors: "Цвет",
  cards_wb: "Склейка WB",
  cards_ozon: "Склейка Ozon",
  factories: "Фабрика",
  importers: "Импортёр",
  certs: "Сертификат",
};

export default function EntityDetailPage() {
  const { entity, id } = useParams<{ entity: string; id: string }>();
  const navigate = useNavigate();
  const entityId = Number(id);

  const fetchEntity = () => {
    switch (entity) {
      case "models_osnova":
      case "models": return matrixApi.getModel(entityId);
      case "articles": return matrixApi.getArticle(entityId);
      case "products": return matrixApi.getProduct(entityId);
      default: return get<Record<string, unknown>>(`/api/matrix/${entity}/${entityId}`);
    }
  };

  const { data, loading } = useApiQuery(fetchEntity, [entity, entityId]);

  const hasMp = entity ? ENTITIES_WITH_MP.has(entity) : false;
  const entityLabel = entity ? (ENTITY_LABELS[entity] ?? entity) : "";
  const entityName = data ? (data as Record<string, unknown>).kod ?? (data as Record<string, unknown>).nazvanie ?? `#${entityId}` : `#${entityId}`;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад
        </Button>
        <div className="flex-1">
          <h1 className="text-lg font-semibold">{String(entityName)}</h1>
          <p className="text-sm text-muted-foreground">{entityLabel}</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info" className="flex-1">
        <TabsList className="mx-4 mt-2">
          <TabsTrigger value="info">Информация</TabsTrigger>
          {hasMp && <TabsTrigger value="stock">Остатки</TabsTrigger>}
          {hasMp && <TabsTrigger value="finance">Финансы</TabsTrigger>}
          {hasMp && <TabsTrigger value="rating">Рейтинг</TabsTrigger>}
          <TabsTrigger value="tasks">Задачи</TabsTrigger>
        </TabsList>

        <TabsContent value="info" className="mt-0">
          {loading ? (
            <div className="p-4 text-muted-foreground">Загрузка...</div>
          ) : data ? (
            <InfoTab data={data as Record<string, unknown>} entityType={entity ?? ""} />
          ) : (
            <div className="p-4 text-muted-foreground">Запись не найдена</div>
          )}
        </TabsContent>

        {hasMp && entity && (
          <>
            <TabsContent value="stock" className="mt-0">
              <StockTab entityType={entity} entityId={entityId} />
            </TabsContent>

            <TabsContent value="finance" className="mt-0">
              <FinanceTab entityType={entity} entityId={entityId} />
            </TabsContent>

            <TabsContent value="rating" className="mt-0">
              <RatingTab />
            </TabsContent>
          </>
        )}

        <TabsContent value="tasks" className="mt-0">
          <TasksTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub
git add src/pages/product-matrix/entity-detail-page.tsx
git commit -m "feat(matrix): rewrite entity detail page with tabbed layout (info/stock/finance/rating/tasks)"
```

---

## Task 11: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/ -v --timeout=30`
Expected: all tests PASS

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Verify app loads**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -c "from services.product_matrix_api.app import app; print('OK, routes:', len(app.routes))"`
Expected: prints OK with increased route count

- [ ] **Step 4: Verify no regressions in existing routes**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python3 -m pytest tests/product_matrix_api/test_routes_models.py tests/product_matrix_api/test_integration.py -v`
Expected: all PASS
