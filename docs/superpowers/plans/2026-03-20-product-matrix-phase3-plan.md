# Product Matrix Editor — Phase 3: All Entities CRUD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Product Matrix Editor with CRUD for all remaining entities (articles, products, colors, factories, importers, marketplace cards, certificates), add global cross-entity search, and mass editing support.

**Prerequisites:** Phase 1+2 complete — FastAPI service running on port 8002 with CRUD for modeli_osnova/modeli, React frontend with DataTable, inline editing, sidebar, detail panel.

**Spec:** `docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md`

---

## File Structure

### Backend: new/modified files in `services/product_matrix_api/`

| File | Responsibility |
|------|---------------|
| `routes/articles.py` | `/api/matrix/articles/*` — CRUD for artikuly |
| `routes/products.py` | `/api/matrix/products/*` — CRUD for tovary |
| `routes/colors.py` | `/api/matrix/colors/*` — CRUD for cveta |
| `routes/factories.py` | `/api/matrix/factories/*` — CRUD for fabriki |
| `routes/importers.py` | `/api/matrix/importers/*` — CRUD for importery |
| `routes/cards.py` | `/api/matrix/cards/*` — CRUD for skleyki_wb and skleyki_ozon |
| `routes/certs.py` | `/api/matrix/certs/*` — CRUD for sertifikaty |
| `routes/search.py` | `/api/matrix/search` — global cross-entity search |
| `routes/bulk.py` | `/api/matrix/bulk` — mass edit/delete |
| `models/schemas.py` | New Pydantic schemas for all entities |
| `app.py` | Register new routers |

### Frontend: new/modified files in `wookiee-hub/src/`

| File | Responsibility |
|------|---------------|
| `pages/product-matrix/articles-page.tsx` | Articles table page |
| `pages/product-matrix/products-page.tsx` | Products/SKU table page |
| `pages/product-matrix/colors-page.tsx` | Colors table page |
| `pages/product-matrix/factories-page.tsx` | Factories table page |
| `pages/product-matrix/importers-page.tsx` | Importers table page |
| `pages/product-matrix/cards-wb-page.tsx` | WB cards table page |
| `pages/product-matrix/cards-ozon-page.tsx` | Ozon cards table page |
| `pages/product-matrix/certs-page.tsx` | Certificates table page |
| `components/matrix/global-search.tsx` | Cmd+K global search dialog |
| `components/matrix/mass-edit-bar.tsx` | Mass selection action bar |
| `lib/matrix-api.ts` | New types + API methods for all entities |
| `pages/product-matrix/index.tsx` | Route all entities to their pages |

---

## Phase 3: All Entities CRUD

### Task 16: Pydantic Schemas for All Entities

**Files:**
- Modify: `services/product_matrix_api/models/schemas.py`
- Test: `tests/product_matrix_api/test_schemas_phase3.py`

- [ ] **Step 1: Write test for new schemas**

```python
# tests/product_matrix_api/test_schemas_phase3.py
"""Validate Phase 3 Pydantic schemas instantiate correctly."""
from services.product_matrix_api.models.schemas import (
    ArtikulCreate, ArtikulRead,
    TovarCreate, TovarRead,
    CvetCreate, CvetRead,
    FabrikaCreate, FabrikaRead,
    ImporterCreate, ImporterRead,
    SleykaWBCreate, SleykaWBRead,
    SleykaOzonCreate, SleykaOzonRead,
    SertifikatCreate, SertifikatRead,
    SearchResult, SearchResponse,
    BulkActionRequest,
)


def test_artikul_schemas():
    c = ArtikulCreate(artikul="Vuki/Black")
    assert c.artikul == "Vuki/Black"
    r = ArtikulRead(id=1, artikul="Vuki/Black")
    assert r.id == 1


def test_tovar_schemas():
    c = TovarCreate(barkod="4670437802315")
    assert c.barkod == "4670437802315"
    r = TovarRead(id=1, barkod="4670437802315")
    assert r.id == 1


def test_cvet_schemas():
    c = CvetCreate(color_code="BLK")
    assert c.color_code == "BLK"
    r = CvetRead(id=1, color_code="BLK")
    assert r.id == 1


def test_fabrika_schemas():
    c = FabrikaCreate(nazvanie="Shanghai Factory")
    assert c.nazvanie == "Shanghai Factory"
    r = FabrikaRead(id=1, nazvanie="Shanghai Factory")
    assert r.id == 1


def test_importer_schemas():
    c = ImporterCreate(nazvanie="ИП Иванов")
    assert c.nazvanie == "ИП Иванов"
    r = ImporterRead(id=1, nazvanie="ИП Иванов")
    assert r.id == 1


def test_skleyka_wb_schemas():
    c = SleykaWBCreate(nazvanie="Vuki WB card")
    assert c.nazvanie == "Vuki WB card"
    r = SleykaWBRead(id=1, nazvanie="Vuki WB card")
    assert r.id == 1


def test_skleyka_ozon_schemas():
    c = SleykaOzonCreate(nazvanie="Vuki Ozon card")
    assert c.nazvanie == "Vuki Ozon card"
    r = SleykaOzonRead(id=1, nazvanie="Vuki Ozon card")
    assert r.id == 1


def test_sertifikat_schemas():
    c = SertifikatCreate(nazvanie="EAC Declaration")
    assert c.nazvanie == "EAC Declaration"
    r = SertifikatRead(id=1, nazvanie="EAC Declaration")
    assert r.id == 1


def test_search_result():
    r = SearchResult(entity="artikuly", id=1, name="Vuki/Black", match_field="artikul", match_text="Vuki/Black")
    assert r.entity == "artikuly"


def test_bulk_action():
    b = BulkActionRequest(ids=[1, 2, 3], action="update", changes={"status_id": 1})
    assert len(b.ids) == 3
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/product_matrix_api/test_schemas_phase3.py -v`
Expected: ImportError — new schemas not defined yet

- [ ] **Step 3: Add all new schemas to schemas.py**

Append to `services/product_matrix_api/models/schemas.py`:

```python
# ── Artikuly ─────────────────────────────────────────────────────────────────

class ArtikulCreate(BaseModel):
    artikul: str
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None


class ArtikulUpdate(BaseModel):
    artikul: Optional[str] = None
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None


class ArtikulRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artikul: str
    model_id: Optional[int] = None
    cvet_id: Optional[int] = None
    status_id: Optional[int] = None
    nomenklatura_wb: Optional[int] = None
    artikul_ozon: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_name: Optional[str] = None
    cvet_name: Optional[str] = None
    status_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Tovary (SKU) ─────────────────────────────────────────────────────────────

class TovarCreate(BaseModel):
    barkod: str
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None


class TovarUpdate(BaseModel):
    barkod: Optional[str] = None
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None


class TovarRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barkod: str
    barkod_gs1: Optional[str] = None
    barkod_gs2: Optional[str] = None
    barkod_perehod: Optional[str] = None
    artikul_id: Optional[int] = None
    razmer_id: Optional[int] = None
    status_id: Optional[int] = None
    status_ozon_id: Optional[int] = None
    ozon_product_id: Optional[int] = None
    ozon_fbo_sku_id: Optional[int] = None
    lamoda_seller_sku: Optional[str] = None
    sku_china_size: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    artikul_name: Optional[str] = None
    razmer_name: Optional[str] = None
    status_name: Optional[str] = None
    status_ozon_name: Optional[str] = None


# ── Cveta (Colors) ───────────────────────────────────────────────────────────

class CvetCreate(BaseModel):
    color_code: str
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None


class CvetUpdate(BaseModel):
    color_code: Optional[str] = None
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None


class CvetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    color_code: str
    cvet: Optional[str] = None
    color: Optional[str] = None
    lastovica: Optional[str] = None
    status_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status_name: Optional[str] = None
    artikuly_count: Optional[int] = None


# ── Fabriki (Factories) ─────────────────────────────────────────────────────

class FabrikaCreate(BaseModel):
    nazvanie: str
    strana: Optional[str] = None


class FabrikaUpdate(BaseModel):
    nazvanie: Optional[str] = None
    strana: Optional[str] = None


class FabrikaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    strana: Optional[str] = None
    modeli_count: Optional[int] = None


# ── Importery (Importers) ───────────────────────────────────────────────────

class ImporterCreate(BaseModel):
    nazvanie: str
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None


class ImporterUpdate(BaseModel):
    nazvanie: Optional[str] = None
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None


class ImporterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    nazvanie_en: Optional[str] = None
    inn: Optional[str] = None
    adres: Optional[str] = None
    modeli_count: Optional[int] = None


# ── Skleyki WB (Marketplace cards WB) ───────────────────────────────────────

class SleykaWBCreate(BaseModel):
    nazvanie: str
    importer_id: Optional[int] = None


class SleykaWBUpdate(BaseModel):
    nazvanie: Optional[str] = None
    importer_id: Optional[int] = None


class SleykaWBRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    importer_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    importer_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Skleyki Ozon (Marketplace cards Ozon) ───────────────────────────────────

class SleykaOzonCreate(BaseModel):
    nazvanie: str
    importer_id: Optional[int] = None


class SleykaOzonUpdate(BaseModel):
    nazvanie: Optional[str] = None
    importer_id: Optional[int] = None


class SleykaOzonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    importer_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    importer_name: Optional[str] = None
    tovary_count: Optional[int] = None


# ── Sertifikaty (Certificates) ──────────────────────────────────────────────

class SertifikatCreate(BaseModel):
    nazvanie: str
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[str] = None
    data_okonchaniya: Optional[str] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None


class SertifikatUpdate(BaseModel):
    nazvanie: Optional[str] = None
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[str] = None
    data_okonchaniya: Optional[str] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None


class SertifikatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
    tip: Optional[str] = None
    nomer: Optional[str] = None
    data_vydachi: Optional[datetime] = None
    data_okonchaniya: Optional[datetime] = None
    organ_sertifikacii: Optional[str] = None
    file_url: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Search ───────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    entity: str
    id: int
    name: str
    match_field: str
    match_text: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    by_entity: dict[str, int]


# ── Bulk Operations ─────────────────────────────────────────────────────────

class BulkActionRequest(BaseModel):
    ids: list[int]
    action: str  # "update" | "delete"
    changes: Optional[dict] = None  # for "update"
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_schemas_phase3.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/models/schemas.py tests/product_matrix_api/test_schemas_phase3.py
git commit -m "feat(matrix-api): add Pydantic schemas for all remaining entities, search, and bulk ops"
```

---

### Task 17: Articles CRUD Route

**Files:**
- Create: `services/product_matrix_api/routes/articles.py`
- Test: `tests/product_matrix_api/test_routes_articles.py`

- [ ] **Step 1: Write route test**

```python
# tests/product_matrix_api/test_routes_articles.py
"""Smoke test that articles routes are registered and respond."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_articles_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/articles")
    assert r.status_code != 404, "Articles route not registered"


@pytest.mark.anyio
async def test_get_article_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/articles/999999")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_routes_articles.py -v`
Expected: 404 — route not registered yet

- [ ] **Step 3: Create articles route**

```python
# services/product_matrix_api/routes/articles.py
"""CRUD routes for artikuly (articles = model + color)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    ArtikulCreate, ArtikulUpdate, ArtikulRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Artikul

router = APIRouter(prefix="/api/matrix/articles", tags=["articles"])


@router.get("", response_model=PaginatedResponse)
def list_articles(
    params: CommonQueryParams = Depends(common_params),
    model_id: Optional[int] = Query(None),
    cvet_id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if model_id:
        filters["model_id"] = model_id
    if cvet_id:
        filters["cvet_id"] = cvet_id
    if status_id:
        filters["status_id"] = status_id

    items, total = CrudService.get_list(
        db, Artikul,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[ArtikulRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{article_id}", response_model=ArtikulRead)
def get_article(article_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Artikul, article_id)
    if not item:
        raise HTTPException(404, "Article not found")
    return ArtikulRead.model_validate(item)


@router.post("", response_model=ArtikulRead, status_code=201)
def create_article(
    body: ArtikulCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Artikul, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="artikuly",
        entity_id=item.id, entity_name=item.artikul, user_email=user.email,
    )
    db.commit()
    return ArtikulRead.model_validate(item)


@router.patch("/{article_id}", response_model=ArtikulRead)
def update_article(
    article_id: int,
    body: ArtikulUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Artikul, article_id)
    if not item:
        raise HTTPException(404, "Article not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="artikuly",
            entity_id=item.id, entity_name=item.artikul,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return ArtikulRead.model_validate(item)
```

- [ ] **Step 4: Register router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.articles import router as articles_router

app.include_router(articles_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_articles.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/articles.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_articles.py
git commit -m "feat(matrix-api): add CRUD route for artikuly (articles)"
```

---

### Task 18: Products CRUD Route

**Files:**
- Create: `services/product_matrix_api/routes/products.py`
- Test: `tests/product_matrix_api/test_routes_products.py`

- [ ] **Step 1: Write route test**

```python
# tests/product_matrix_api/test_routes_products.py
"""Smoke test that products routes are registered and respond."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_products_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/products")
    assert r.status_code != 404, "Products route not registered"


@pytest.mark.anyio
async def test_get_product_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/products/999999")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create products route**

```python
# services/product_matrix_api/routes/products.py
"""CRUD routes for tovary (products/SKU = article + size + barcode)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    TovarCreate, TovarUpdate, TovarRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Tovar

router = APIRouter(prefix="/api/matrix/products", tags=["products"])


@router.get("", response_model=PaginatedResponse)
def list_products(
    params: CommonQueryParams = Depends(common_params),
    artikul_id: Optional[int] = Query(None),
    razmer_id: Optional[int] = Query(None),
    status_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if artikul_id:
        filters["artikul_id"] = artikul_id
    if razmer_id:
        filters["razmer_id"] = razmer_id
    if status_id:
        filters["status_id"] = status_id

    items, total = CrudService.get_list(
        db, Tovar,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[TovarRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{product_id}", response_model=TovarRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Tovar, product_id)
    if not item:
        raise HTTPException(404, "Product not found")
    return TovarRead.model_validate(item)


@router.post("", response_model=TovarRead, status_code=201)
def create_product(
    body: TovarCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Tovar, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="tovary",
        entity_id=item.id, entity_name=item.barkod, user_email=user.email,
    )
    db.commit()
    return TovarRead.model_validate(item)


@router.patch("/{product_id}", response_model=TovarRead)
def update_product(
    product_id: int,
    body: TovarUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Tovar, product_id)
    if not item:
        raise HTTPException(404, "Product not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="tovary",
            entity_id=item.id, entity_name=item.barkod,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return TovarRead.model_validate(item)
```

- [ ] **Step 4: Register router in app.py**

```python
from services.product_matrix_api.routes.products import router as products_router

app.include_router(products_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_products.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/products.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_products.py
git commit -m "feat(matrix-api): add CRUD route for tovary (products/SKU)"
```

---

### Task 19: Colors, Factories, Importers CRUD Routes

These are simpler reference entities — one route file per entity, same pattern.

**Files:**
- Create: `services/product_matrix_api/routes/colors.py`
- Create: `services/product_matrix_api/routes/factories.py`
- Create: `services/product_matrix_api/routes/importers.py`
- Test: `tests/product_matrix_api/test_routes_reference.py`

- [ ] **Step 1: Write test for all three routes**

```python
# tests/product_matrix_api/test_routes_reference.py
"""Smoke tests for reference entity routes (colors, factories, importers)."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/colors",
    "/api/matrix/factories",
    "/api/matrix/importers",
])
async def test_list_route_exists(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code != 404, f"Route {path} not registered"


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/colors/999999",
    "/api/matrix/factories/999999",
    "/api/matrix/importers/999999",
])
async def test_get_404(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create colors route**

```python
# services/product_matrix_api/routes/colors.py
"""CRUD routes for cveta (colors)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    CvetCreate, CvetUpdate, CvetRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Cvet

router = APIRouter(prefix="/api/matrix/colors", tags=["colors"])


@router.get("", response_model=PaginatedResponse)
def list_colors(
    params: CommonQueryParams = Depends(common_params),
    status_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if status_id:
        filters["status_id"] = status_id
    items, total = CrudService.get_list(
        db, Cvet, page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[CvetRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{color_id}", response_model=CvetRead)
def get_color(color_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Cvet, color_id)
    if not item:
        raise HTTPException(404, "Color not found")
    return CvetRead.model_validate(item)


@router.post("", response_model=CvetRead, status_code=201)
def create_color(
    body: CvetCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Cvet, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="cveta",
        entity_id=item.id, entity_name=item.color_code, user_email=user.email,
    )
    db.commit()
    return CvetRead.model_validate(item)


@router.patch("/{color_id}", response_model=CvetRead)
def update_color(
    color_id: int,
    body: CvetUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Cvet, color_id)
    if not item:
        raise HTTPException(404, "Color not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="cveta",
            entity_id=item.id, entity_name=item.color_code,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return CvetRead.model_validate(item)
```

- [ ] **Step 4: Create factories route**

```python
# services/product_matrix_api/routes/factories.py
"""CRUD routes for fabriki (factories)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    FabrikaCreate, FabrikaUpdate, FabrikaRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Fabrika

router = APIRouter(prefix="/api/matrix/factories", tags=["factories"])


@router.get("", response_model=PaginatedResponse)
def list_factories(
    params: CommonQueryParams = Depends(common_params),
    db: Session = Depends(get_db),
):
    items, total = CrudService.get_list(
        db, Fabrika, page=params.page, per_page=params.per_page, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[FabrikaRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{factory_id}", response_model=FabrikaRead)
def get_factory(factory_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Fabrika, factory_id)
    if not item:
        raise HTTPException(404, "Factory not found")
    return FabrikaRead.model_validate(item)


@router.post("", response_model=FabrikaRead, status_code=201)
def create_factory(
    body: FabrikaCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Fabrika, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="fabriki",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return FabrikaRead.model_validate(item)


@router.patch("/{factory_id}", response_model=FabrikaRead)
def update_factory(
    factory_id: int,
    body: FabrikaUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Fabrika, factory_id)
    if not item:
        raise HTTPException(404, "Factory not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="fabriki",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return FabrikaRead.model_validate(item)
```

- [ ] **Step 5: Create importers route**

```python
# services/product_matrix_api/routes/importers.py
"""CRUD routes for importery (importers / legal entities)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    ImporterCreate, ImporterUpdate, ImporterRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Importer

router = APIRouter(prefix="/api/matrix/importers", tags=["importers"])


@router.get("", response_model=PaginatedResponse)
def list_importers(
    params: CommonQueryParams = Depends(common_params),
    db: Session = Depends(get_db),
):
    items, total = CrudService.get_list(
        db, Importer, page=params.page, per_page=params.per_page, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[ImporterRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{importer_id}", response_model=ImporterRead)
def get_importer(importer_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Importer, importer_id)
    if not item:
        raise HTTPException(404, "Importer not found")
    return ImporterRead.model_validate(item)


@router.post("", response_model=ImporterRead, status_code=201)
def create_importer(
    body: ImporterCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Importer, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="importery",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return ImporterRead.model_validate(item)


@router.patch("/{importer_id}", response_model=ImporterRead)
def update_importer(
    importer_id: int,
    body: ImporterUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Importer, importer_id)
    if not item:
        raise HTTPException(404, "Importer not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="importery",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return ImporterRead.model_validate(item)
```

- [ ] **Step 6: Register all three routers in app.py**

```python
from services.product_matrix_api.routes.colors import router as colors_router
from services.product_matrix_api.routes.factories import router as factories_router
from services.product_matrix_api.routes.importers import router as importers_router

app.include_router(colors_router)
app.include_router(factories_router)
app.include_router(importers_router)
```

- [ ] **Step 7: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_reference.py -v`
Expected: 6 passed

- [ ] **Step 8: Commit**

```bash
git add services/product_matrix_api/routes/colors.py services/product_matrix_api/routes/factories.py services/product_matrix_api/routes/importers.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_reference.py
git commit -m "feat(matrix-api): add CRUD routes for colors, factories, importers"
```

---

### Task 20: Marketplace Cards CRUD Routes (WB + Ozon)

**Files:**
- Create: `services/product_matrix_api/routes/cards.py`
- Test: `tests/product_matrix_api/test_routes_cards.py`

- [ ] **Step 1: Write test**

```python
# tests/product_matrix_api/test_routes_cards.py
"""Smoke tests for marketplace cards routes."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/cards-wb",
    "/api/matrix/cards-ozon",
])
async def test_list_cards_route_exists(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code != 404, f"Route {path} not registered"
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create cards route**

```python
# services/product_matrix_api/routes/cards.py
"""CRUD routes for marketplace cards (skleyki WB and Ozon)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    SleykaWBCreate, SleykaWBUpdate, SleykaWBRead,
    SleykaOzonCreate, SleykaOzonUpdate, SleykaOzonRead,
    PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import SleykaWB, SleykaOzon

router = APIRouter(prefix="/api/matrix", tags=["cards"])


# ── WB Cards ────────────────────────────────────────────────────────────────

@router.get("/cards-wb", response_model=PaginatedResponse)
def list_cards_wb(
    params: CommonQueryParams = Depends(common_params),
    importer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if importer_id:
        filters["importer_id"] = importer_id
    items, total = CrudService.get_list(
        db, SleykaWB, page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[SleykaWBRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/cards-wb/{card_id}", response_model=SleykaWBRead)
def get_card_wb(card_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, SleykaWB, card_id)
    if not item:
        raise HTTPException(404, "WB card not found")
    return SleykaWBRead.model_validate(item)


@router.post("/cards-wb", response_model=SleykaWBRead, status_code=201)
def create_card_wb(
    body: SleykaWBCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, SleykaWB, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="skleyki_wb",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return SleykaWBRead.model_validate(item)


@router.patch("/cards-wb/{card_id}", response_model=SleykaWBRead)
def update_card_wb(
    card_id: int,
    body: SleykaWBUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, SleykaWB, card_id)
    if not item:
        raise HTTPException(404, "WB card not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="skleyki_wb",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return SleykaWBRead.model_validate(item)


# ── Ozon Cards ──────────────────────────────────────────────────────────────

@router.get("/cards-ozon", response_model=PaginatedResponse)
def list_cards_ozon(
    params: CommonQueryParams = Depends(common_params),
    importer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if importer_id:
        filters["importer_id"] = importer_id
    items, total = CrudService.get_list(
        db, SleykaOzon, page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[SleykaOzonRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/cards-ozon/{card_id}", response_model=SleykaOzonRead)
def get_card_ozon(card_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, SleykaOzon, card_id)
    if not item:
        raise HTTPException(404, "Ozon card not found")
    return SleykaOzonRead.model_validate(item)


@router.post("/cards-ozon", response_model=SleykaOzonRead, status_code=201)
def create_card_ozon(
    body: SleykaOzonCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, SleykaOzon, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="skleyki_ozon",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return SleykaOzonRead.model_validate(item)


@router.patch("/cards-ozon/{card_id}", response_model=SleykaOzonRead)
def update_card_ozon(
    card_id: int,
    body: SleykaOzonUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, SleykaOzon, card_id)
    if not item:
        raise HTTPException(404, "Ozon card not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="skleyki_ozon",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return SleykaOzonRead.model_validate(item)
```

- [ ] **Step 4: Register router in app.py**

```python
from services.product_matrix_api.routes.cards import router as cards_router

app.include_router(cards_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_cards.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/cards.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_cards.py
git commit -m "feat(matrix-api): add CRUD routes for WB and Ozon marketplace cards"
```

---

### Task 21: Certificates CRUD Route

**Files:**
- Create: `services/product_matrix_api/routes/certs.py`
- Test: `tests/product_matrix_api/test_routes_certs.py`

- [ ] **Step 1: Write test**

```python
# tests/product_matrix_api/test_routes_certs.py
"""Smoke test for certificates route."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_certs_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/certs")
    assert r.status_code != 404, "Certs route not registered"


@pytest.mark.anyio
async def test_get_cert_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/certs/999999")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create certs route**

```python
# services/product_matrix_api/routes/certs.py
"""CRUD routes for sertifikaty (certificates)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    SertifikatCreate, SertifikatUpdate, SertifikatRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/certs", tags=["certs"])


@router.get("", response_model=PaginatedResponse)
def list_certs(
    params: CommonQueryParams = Depends(common_params),
    db: Session = Depends(get_db),
):
    items, total = CrudService.get_list(
        db, Sertifikat, page=params.page, per_page=params.per_page, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[SertifikatRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{cert_id}", response_model=SertifikatRead)
def get_cert(cert_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Sertifikat, cert_id)
    if not item:
        raise HTTPException(404, "Certificate not found")
    return SertifikatRead.model_validate(item)


@router.post("", response_model=SertifikatRead, status_code=201)
def create_cert(
    body: SertifikatCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Sertifikat, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="sertifikaty",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return SertifikatRead.model_validate(item)


@router.patch("/{cert_id}", response_model=SertifikatRead)
def update_cert(
    cert_id: int,
    body: SertifikatUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Sertifikat, cert_id)
    if not item:
        raise HTTPException(404, "Certificate not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="sertifikaty",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return SertifikatRead.model_validate(item)
```

Note: Sertifikat uses the model from `models/database.py` (new table), not from `sku_database`.

- [ ] **Step 4: Register router in app.py**

```python
from services.product_matrix_api.routes.certs import router as certs_router

app.include_router(certs_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_certs.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/certs.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_certs.py
git commit -m "feat(matrix-api): add CRUD route for sertifikaty (certificates)"
```

---

### Task 22: Global Search Endpoint

**Files:**
- Create: `services/product_matrix_api/routes/search.py`
- Test: `tests/product_matrix_api/test_routes_search.py`

- [ ] **Step 1: Write test**

```python
# tests/product_matrix_api/test_routes_search.py
"""Smoke test for global search endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_search_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/search?q=test")
    assert r.status_code != 404, "Search route not registered"


@pytest.mark.anyio
async def test_search_requires_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/search")
    assert r.status_code == 422, "Should require 'q' parameter"
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create search route**

```python
# services/product_matrix_api/routes/search.py
"""Global cross-entity search for the product matrix."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import SearchResult, SearchResponse

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, Cvet, Fabrika, Importer,
    SleykaWB, SleykaOzon,
)
from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/search", tags=["search"])

# Define search config: (ORM model, entity_name, searchable fields, name field)
SEARCH_CONFIG = [
    (ModelOsnova, "modeli_osnova", ["kod", "nazvanie_sayt", "material"], "kod"),
    (Model, "modeli", ["kod", "nazvanie", "artikul_modeli"], "kod"),
    (Artikul, "artikuly", ["artikul", "artikul_ozon"], "artikul"),
    (Tovar, "tovary", ["barkod", "barkod_gs1", "lamoda_seller_sku", "sku_china_size"], "barkod"),
    (Cvet, "cveta", ["color_code", "cvet", "color"], "color_code"),
    (Fabrika, "fabriki", ["nazvanie"], "nazvanie"),
    (Importer, "importery", ["nazvanie", "nazvanie_en", "inn"], "nazvanie"),
    (SleykaWB, "skleyki_wb", ["nazvanie"], "nazvanie"),
    (SleykaOzon, "skleyki_ozon", ["nazvanie"], "nazvanie"),
    (Sertifikat, "sertifikaty", ["nazvanie", "nomer", "tip"], "nazvanie"),
]


@router.get("", response_model=SearchResponse)
def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    results: list[SearchResult] = []
    by_entity: dict[str, int] = {}
    pattern = f"%{q}%"

    for orm_model, entity_name, fields, name_field in SEARCH_CONFIG:
        # Build ILIKE conditions for each searchable field
        conditions = []
        for field_name in fields:
            col = getattr(orm_model, field_name, None)
            if col is not None:
                # Cast non-string columns to string for ILIKE
                conditions.append(cast(col, String).ilike(pattern))

        if not conditions:
            continue

        rows = db.query(orm_model).filter(or_(*conditions)).limit(limit).all()
        by_entity[entity_name] = len(rows)

        for row in rows:
            name_val = str(getattr(row, name_field, ""))
            # Find which field matched
            match_field = name_field
            match_text = name_val
            for field_name in fields:
                val = getattr(row, field_name, None)
                if val and q.lower() in str(val).lower():
                    match_field = field_name
                    match_text = str(val)
                    break

            results.append(SearchResult(
                entity=entity_name,
                id=row.id,
                name=name_val,
                match_field=match_field,
                match_text=match_text,
            ))

    # Sort by relevance: exact matches first, then partial
    results.sort(key=lambda r: (0 if q.lower() == r.match_text.lower() else 1, r.entity, r.name))

    total = sum(by_entity.values())
    return SearchResponse(
        results=results[:limit],
        total=total,
        by_entity=by_entity,
    )
```

- [ ] **Step 4: Register router in app.py**

```python
from services.product_matrix_api.routes.search import router as search_router

app.include_router(search_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_search.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/search.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_search.py
git commit -m "feat(matrix-api): add global cross-entity search endpoint"
```

---

### Task 23: Bulk Operations Endpoint

**Files:**
- Create: `services/product_matrix_api/routes/bulk.py`
- Test: `tests/product_matrix_api/test_routes_bulk.py`

- [ ] **Step 1: Write test**

```python
# tests/product_matrix_api/test_routes_bulk.py
"""Smoke test for bulk operations endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_bulk_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/bulk/modeli_osnova",
            json={"ids": [1], "action": "update", "changes": {"material": "test"}},
        )
    assert r.status_code != 404, "Bulk route not registered"


@pytest.mark.anyio
async def test_bulk_unknown_entity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/bulk/unknown_entity",
            json={"ids": [1], "action": "update", "changes": {}},
        )
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Create bulk route**

```python
# services/product_matrix_api/routes/bulk.py
"""Bulk operations (mass update/delete) for any entity."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.schemas import BulkActionRequest
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, Cvet, Fabrika, Importer,
    SleykaWB, SleykaOzon,
)
from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/bulk", tags=["bulk"])

ENTITY_MAP = {
    "modeli_osnova": (ModelOsnova, "kod"),
    "modeli": (Model, "kod"),
    "artikuly": (Artikul, "artikul"),
    "tovary": (Tovar, "barkod"),
    "cveta": (Cvet, "color_code"),
    "fabriki": (Fabrika, "nazvanie"),
    "importery": (Importer, "nazvanie"),
    "skleyki_wb": (SleykaWB, "nazvanie"),
    "skleyki_ozon": (SleykaOzon, "nazvanie"),
    "sertifikaty": (Sertifikat, "nazvanie"),
}


@router.post("/{entity_type}")
def bulk_action(
    entity_type: str,
    body: BulkActionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if entity_type not in ENTITY_MAP:
        raise HTTPException(404, f"Unknown entity type: {entity_type}")

    orm_model, name_field = ENTITY_MAP[entity_type]
    updated = 0
    errors = []

    for record_id in body.ids:
        item = CrudService.get_by_id(db, orm_model, record_id)
        if not item:
            errors.append({"id": record_id, "error": "not found"})
            continue

        if body.action == "update" and body.changes:
            old_data = CrudService.to_dict(item)
            CrudService.update(db, item, body.changes)
            changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
            if changes:
                AuditService.log(
                    db, action="bulk_update", entity_type=entity_type,
                    entity_id=item.id,
                    entity_name=str(getattr(item, name_field, "")),
                    changes=changes, user_email=user.email,
                )
            updated += 1
        else:
            errors.append({"id": record_id, "error": f"unsupported action: {body.action}"})

    db.commit()
    return {"updated": updated, "errors": errors}
```

Note: Bulk delete is intentionally not implemented here — it will be added in Phase 5 (Safe deletion with challenge).

- [ ] **Step 4: Register router in app.py**

```python
from services.product_matrix_api.routes.bulk import router as bulk_router

app.include_router(bulk_router)
```

- [ ] **Step 5: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_bulk.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/bulk.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_bulk.py
git commit -m "feat(matrix-api): add bulk update endpoint for mass editing"
```

---

### Task 24: Frontend — API Types + Methods for All Entities

**Files:**
- Modify: `wookiee-hub/src/lib/matrix-api.ts`

- [ ] **Step 1: Add types and API methods**

Extend `wookiee-hub/src/lib/matrix-api.ts` with new interfaces and API methods:

```typescript
// ── New types (append after existing types) ────────────────────────────────

export interface Artikul {
  id: number
  artikul: string
  model_id: number | null
  cvet_id: number | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  created_at: string | null
  updated_at: string | null
  model_name: string | null
  cvet_name: string | null
  status_name: string | null
  tovary_count: number | null
}

export interface Tovar {
  id: number
  barkod: string
  barkod_gs1: string | null
  barkod_gs2: string | null
  barkod_perehod: string | null
  artikul_id: number | null
  razmer_id: number | null
  status_id: number | null
  status_ozon_id: number | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
  lamoda_seller_sku: string | null
  sku_china_size: string | null
  created_at: string | null
  updated_at: string | null
  artikul_name: string | null
  razmer_name: string | null
  status_name: string | null
  status_ozon_name: string | null
}

export interface Cvet {
  id: number
  color_code: string
  cvet: string | null
  color: string | null
  lastovica: string | null
  status_id: number | null
  created_at: string | null
  updated_at: string | null
  status_name: string | null
  artikuly_count: number | null
}

export interface Fabrika {
  id: number
  nazvanie: string
  strana: string | null
  modeli_count: number | null
}

export interface ImporterEntity {
  id: number
  nazvanie: string
  nazvanie_en: string | null
  inn: string | null
  adres: string | null
  modeli_count: number | null
}

export interface SleykaWB {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  tovary_count: number | null
}

export interface SleykaOzon {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  tovary_count: number | null
}

export interface Sertifikat {
  id: number
  nazvanie: string
  tip: string | null
  nomer: string | null
  data_vydachi: string | null
  data_okonchaniya: string | null
  organ_sertifikacii: string | null
  file_url: string | null
  gruppa_sertifikata: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SearchResult {
  entity: string
  id: number
  name: string
  match_field: string
  match_text: string
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  by_entity: Record<string, number>
}
```

Add new API methods to `matrixApi`:

```typescript
  // Articles
  listArticles: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Artikul>>("/api/matrix/articles", params),

  getArticle: (id: number) =>
    get<Artikul>(`/api/matrix/articles/${id}`),

  createArticle: (data: Partial<Artikul>) =>
    post<Artikul>("/api/matrix/articles", data),

  updateArticle: (id: number, data: Partial<Artikul>) =>
    patch<Artikul>(`/api/matrix/articles/${id}`, data),

  // Products
  listProducts: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Tovar>>("/api/matrix/products", params),

  getProduct: (id: number) =>
    get<Tovar>(`/api/matrix/products/${id}`),

  createProduct: (data: Partial<Tovar>) =>
    post<Tovar>("/api/matrix/products", data),

  updateProduct: (id: number, data: Partial<Tovar>) =>
    patch<Tovar>(`/api/matrix/products/${id}`, data),

  // Colors
  listColors: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Cvet>>("/api/matrix/colors", params),

  updateColor: (id: number, data: Partial<Cvet>) =>
    patch<Cvet>(`/api/matrix/colors/${id}`, data),

  // Factories
  listFactories: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Fabrika>>("/api/matrix/factories", params),

  updateFactory: (id: number, data: Partial<Fabrika>) =>
    patch<Fabrika>(`/api/matrix/factories/${id}`, data),

  // Importers
  listImporters: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ImporterEntity>>("/api/matrix/importers", params),

  updateImporter: (id: number, data: Partial<ImporterEntity>) =>
    patch<ImporterEntity>(`/api/matrix/importers/${id}`, data),

  // WB Cards
  listCardsWB: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<SleykaWB>>("/api/matrix/cards-wb", params),

  updateCardWB: (id: number, data: Partial<SleykaWB>) =>
    patch<SleykaWB>(`/api/matrix/cards-wb/${id}`, data),

  // Ozon Cards
  listCardsOzon: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<SleykaOzon>>("/api/matrix/cards-ozon", params),

  updateCardOzon: (id: number, data: Partial<SleykaOzon>) =>
    patch<SleykaOzon>(`/api/matrix/cards-ozon/${id}`, data),

  // Certs
  listCerts: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Sertifikat>>("/api/matrix/certs", params),

  updateCert: (id: number, data: Partial<Sertifikat>) =>
    patch<Sertifikat>(`/api/matrix/certs/${id}`, data),

  // Search
  search: (q: string, limit?: number) =>
    get<SearchResponse>("/api/matrix/search", { q, limit }),

  // Bulk
  bulkAction: (entityType: string, data: { ids: number[]; action: string; changes?: Record<string, unknown> }) =>
    post<{ updated: number; errors: Array<{ id: number; error: string }> }>(
      `/api/matrix/bulk/${entityType}`, data,
    ),
```

- [ ] **Step 2: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/lib/matrix-api.ts
git commit -m "feat(matrix-ui): add API types and methods for all entities, search, and bulk ops"
```

---

### Task 25: Frontend — Entity Pages (Articles, Products, Colors, Factories, Importers, Cards, Certs)

**Files:**
- Create: `wookiee-hub/src/pages/product-matrix/articles-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/products-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/colors-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/factories-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/importers-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/cards-wb-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/cards-ozon-page.tsx`
- Create: `wookiee-hub/src/pages/product-matrix/certs-page.tsx`

Each page follows the same pattern as `models-page.tsx`: define columns, use `useApiQuery`, render `DataTable`.

- [ ] **Step 1: Create articles-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/articles-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Artikul } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"

const columns: Column<Artikul>[] = [
  { key: "artikul", label: "Артикул", width: 160, type: "text" },
  { key: "model_name", label: "Модель", width: 140, type: "readonly" },
  { key: "cvet_name", label: "Цвет", width: 140, type: "readonly" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "nomenklatura_wb", label: "Номенклатура WB", width: 160, type: "number" },
  { key: "artikul_ozon", label: "Артикул Ozon", width: 140, type: "text" },
  { key: "tovary_count", label: "SKU", width: 80, type: "readonly" },
]

export function ArticlesPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listArticles({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateArticle(id, { [field]: value })
  }, [])

  return (
    <div className="space-y-3">
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        selectedRows={selectedRows}
        onToggleSelect={toggleRowSelected}
        onCellEdit={handleCellEdit}
        onRowClick={openDetailPanel}
      />
    </div>
  )
}
```

- [ ] **Step 2: Create products-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/products-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Tovar } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"

const columns: Column<Tovar>[] = [
  { key: "barkod", label: "Баркод", width: 160, type: "text" },
  { key: "artikul_name", label: "Артикул", width: 140, type: "readonly" },
  { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "barkod_gs1", label: "GS1", width: 140, type: "text" },
  { key: "ozon_product_id", label: "Ozon Product ID", width: 140, type: "number" },
  { key: "lamoda_seller_sku", label: "Lamoda SKU", width: 140, type: "text" },
  { key: "sku_china_size", label: "SKU China Size", width: 130, type: "text" },
]

export function ProductsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listProducts({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateProduct(id, { [field]: value })
  }, [])

  return (
    <div className="space-y-3">
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        selectedRows={selectedRows}
        onToggleSelect={toggleRowSelected}
        onCellEdit={handleCellEdit}
        onRowClick={openDetailPanel}
      />
    </div>
  )
}
```

- [ ] **Step 3: Create colors-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/colors-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Cvet } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<Cvet>[] = [
  { key: "color_code", label: "Код цвета", width: 120, type: "text" },
  { key: "cvet", label: "Цвет (рус)", width: 160, type: "text" },
  { key: "color", label: "Color (en)", width: 160, type: "text" },
  { key: "lastovica", label: "Ластовица", width: 140, type: "text" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "artikuly_count", label: "Артикулы", width: 100, type: "readonly" },
]

export function ColorsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listColors({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateColor(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 4: Create factories-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/factories-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Fabrika } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<Fabrika>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "strana", label: "Страна", width: 160, type: "text" },
  { key: "modeli_count", label: "Модели", width: 100, type: "readonly" },
]

export function FactoriesPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listFactories({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateFactory(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 5: Create importers-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/importers-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ImporterEntity } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<ImporterEntity>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "nazvanie_en", label: "Name (en)", width: 200, type: "text" },
  { key: "inn", label: "ИНН", width: 140, type: "text" },
  { key: "adres", label: "Адрес", width: 300, type: "text" },
  { key: "modeli_count", label: "Модели", width: 100, type: "readonly" },
]

export function ImportersPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listImporters({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateImporter(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 6: Create cards-wb-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/cards-wb-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type SleykaWB } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<SleykaWB>[] = [
  { key: "nazvanie", label: "Название", width: 240, type: "text" },
  { key: "importer_name", label: "Импортёр", width: 180, type: "readonly" },
  { key: "tovary_count", label: "Товары", width: 100, type: "readonly" },
]

export function CardsWBPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listCardsWB({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateCardWB(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 7: Create cards-ozon-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/cards-ozon-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type SleykaOzon } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<SleykaOzon>[] = [
  { key: "nazvanie", label: "Название", width: 240, type: "text" },
  { key: "importer_name", label: "Импортёр", width: 180, type: "readonly" },
  { key: "tovary_count", label: "Товары", width: 100, type: "readonly" },
]

export function CardsOzonPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listCardsOzon({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateCardOzon(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 8: Create certs-page.tsx**

```tsx
// wookiee-hub/src/pages/product-matrix/certs-page.tsx
import { useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Sertifikat } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"

const columns: Column<Sertifikat>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "tip", label: "Тип", width: 160, type: "text" },
  { key: "nomer", label: "Номер", width: 140, type: "text" },
  { key: "data_vydachi", label: "Дата выдачи", width: 120, type: "readonly" },
  { key: "data_okonchaniya", label: "Окончание", width: 120, type: "readonly" },
  { key: "organ_sertifikacii", label: "Орган", width: 200, type: "text" },
  { key: "gruppa_sertifikata", label: "Группа", width: 120, type: "text" },
]

export function CertsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listCerts({ per_page: 200 }),
    [],
  )

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateCert(id, { [field]: value })
  }, [])

  return (
    <DataTable
      columns={columns}
      data={data?.items ?? []}
      loading={loading}
      selectedRows={selectedRows}
      onToggleSelect={toggleRowSelected}
      onCellEdit={handleCellEdit}
      onRowClick={openDetailPanel}
    />
  )
}
```

- [ ] **Step 9: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 10: Commit**

```bash
git add wookiee-hub/src/pages/product-matrix/
git commit -m "feat(matrix-ui): add table pages for all entities (articles, products, colors, factories, importers, cards, certs)"
```

---

### Task 26: Frontend — Wire All Entity Pages to MatrixShell Router

**Files:**
- Modify: `wookiee-hub/src/pages/product-matrix/index.tsx`

- [ ] **Step 1: Update index.tsx to route all entities**

Replace the stub "Раздел в разработке" with actual page imports:

```tsx
// wookiee-hub/src/pages/product-matrix/index.tsx
import { MatrixSidebar } from "@/components/matrix/matrix-sidebar"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { DetailPanel } from "@/components/matrix/detail-panel"
import { useMatrixStore } from "@/stores/matrix-store"
import { ModelsPage } from "./models-page"
import { ArticlesPage } from "./articles-page"
import { ProductsPage } from "./products-page"
import { ColorsPage } from "./colors-page"
import { FactoriesPage } from "./factories-page"
import { ImportersPage } from "./importers-page"
import { CardsWBPage } from "./cards-wb-page"
import { CardsOzonPage } from "./cards-ozon-page"
import { CertsPage } from "./certs-page"

const ENTITY_PAGES = {
  models: ModelsPage,
  articles: ArticlesPage,
  products: ProductsPage,
  colors: ColorsPage,
  factories: FactoriesPage,
  importers: ImportersPage,
  "cards-wb": CardsWBPage,
  "cards-ozon": CardsOzonPage,
  certs: CertsPage,
} as const

export function ProductMatrixLayout() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const Page = ENTITY_PAGES[activeEntity]

  return (
    <div className="flex h-full">
      <MatrixSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MatrixTopbar />
        <main className="flex-1 overflow-auto p-4">
          <Page />
        </main>
      </div>
      <DetailPanel />
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/pages/product-matrix/index.tsx
git commit -m "feat(matrix-ui): wire all entity pages to MatrixShell router"
```

---

### Task 27: Frontend — Global Search Dialog (Cmd+K)

**Files:**
- Create: `wookiee-hub/src/components/matrix/global-search.tsx`
- Modify: `wookiee-hub/src/components/matrix/matrix-topbar.tsx` — open search on Cmd+K

- [ ] **Step 1: Create global-search.tsx**

```tsx
// wookiee-hub/src/components/matrix/global-search.tsx
import { useCallback, useEffect, useState } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog"
import { useMatrixStore, type MatrixEntity } from "@/stores/matrix-store"
import { matrixApi, type SearchResult } from "@/lib/matrix-api"

const ENTITY_LABELS: Record<string, string> = {
  modeli_osnova: "Модели основы",
  modeli: "Подмодели",
  artikuly: "Артикулы",
  tovary: "Товары",
  cveta: "Цвета",
  fabriki: "Фабрики",
  importery: "Импортёры",
  skleyki_wb: "Склейки WB",
  skleyki_ozon: "Склейки Ozon",
  sertifikaty: "Сертификаты",
}

// Map search entity names to sidebar entity names
const ENTITY_TO_PAGE: Record<string, MatrixEntity> = {
  modeli_osnova: "models",
  modeli: "models",
  artikuly: "articles",
  tovary: "products",
  cveta: "colors",
  fabriki: "factories",
  importery: "importers",
  skleyki_wb: "cards-wb",
  skleyki_ozon: "cards-ozon",
  sertifikaty: "certs",
}

export function GlobalSearch() {
  const searchOpen = useMatrixStore((s) => s.searchOpen)
  const setSearchOpen = useMatrixStore((s) => s.setSearchOpen)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)

  // Keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setSearchOpen(!searchOpen)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [searchOpen, setSearchOpen])

  // Debounced search
  useEffect(() => {
    if (!query || query.length < 2) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await matrixApi.search(query, 20)
        setResults(res.results)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const handleSelect = useCallback(
    (result: SearchResult) => {
      const page = ENTITY_TO_PAGE[result.entity]
      if (page) {
        setActiveEntity(page)
        openDetailPanel(result.id)
      }
      setSearchOpen(false)
      setQuery("")
    },
    [setActiveEntity, openDetailPanel, setSearchOpen],
  )

  // Group results by entity
  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    ;(acc[r.entity] ??= []).push(r)
    return acc
  }, {})

  return (
    <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
      <DialogContent className="max-w-lg gap-0 p-0">
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по всем сущностям..."
            className="border-0 shadow-none focus-visible:ring-0"
            autoFocus
          />
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {loading && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Поиск...
            </div>
          )}

          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Ничего не найдено
            </div>
          )}

          {Object.entries(grouped).map(([entity, items]) => (
            <div key={entity}>
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground">
                {ENTITY_LABELS[entity] ?? entity}
              </div>
              {items.map((item) => (
                <button
                  key={`${item.entity}-${item.id}`}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => handleSelect(item)}
                >
                  <span className="font-medium">{item.name}</span>
                  {item.match_field !== "name" && (
                    <span className="text-muted-foreground">
                      {item.match_field}: {item.match_text}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Add GlobalSearch to matrix-topbar.tsx**

In `matrix-topbar.tsx`, import and render `<GlobalSearch />`:

```tsx
import { GlobalSearch } from "./global-search"

// Inside the component JSX, add at the end:
<GlobalSearch />
```

Also update the search button onClick to use `setSearchOpen(true)` from the store.

- [ ] **Step 3: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/matrix/global-search.tsx wookiee-hub/src/components/matrix/matrix-topbar.tsx
git commit -m "feat(matrix-ui): add global search dialog with Cmd+K shortcut"
```

---

### Task 28: Frontend — Mass Edit Bar

**Files:**
- Create: `wookiee-hub/src/components/matrix/mass-edit-bar.tsx`
- Modify: `wookiee-hub/src/pages/product-matrix/index.tsx` — render bar when selection active

- [ ] **Step 1: Create mass-edit-bar.tsx**

```tsx
// wookiee-hub/src/components/matrix/mass-edit-bar.tsx
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useMatrixStore, type MatrixEntity } from "@/stores/matrix-store"
import { matrixApi } from "@/lib/matrix-api"

const ENTITY_TO_DB: Record<MatrixEntity, string> = {
  models: "modeli_osnova",
  articles: "artikuly",
  products: "tovary",
  colors: "cveta",
  factories: "fabriki",
  importers: "importery",
  "cards-wb": "skleyki_wb",
  "cards-ozon": "skleyki_ozon",
  certs: "sertifikaty",
}

export function MassEditBar() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const clearSelection = useMatrixStore((s) => s.clearSelection)
  const activeEntity = useMatrixStore((s) => s.activeEntity)

  if (selectedRows.size === 0) return null

  const handleBulkUpdate = async (changes: Record<string, unknown>) => {
    const entityType = ENTITY_TO_DB[activeEntity]
    await matrixApi.bulkAction(entityType, {
      ids: Array.from(selectedRows),
      action: "update",
      changes,
    })
    clearSelection()
    // Page will refetch data via useApiQuery dependency change
  }

  return (
    <div className="sticky bottom-0 flex items-center gap-3 border-t bg-background px-4 py-2 text-sm">
      <span className="font-medium">{selectedRows.size} выбрано</span>
      <Button variant="outline" size="sm" onClick={() => handleBulkUpdate({ status_id: 1 })}>
        Статус: Активный
      </Button>
      <Button variant="outline" size="sm" onClick={() => handleBulkUpdate({ status_id: 3 })}>
        Статус: Архив
      </Button>
      <div className="flex-1" />
      <Button variant="ghost" size="sm" onClick={clearSelection}>
        <X className="mr-1 h-3 w-3" /> Снять выделение
      </Button>
    </div>
  )
}
```

Note: The bar shows simple preset bulk actions. More advanced bulk editing (custom field changes) will be added in Phase 4.

- [ ] **Step 2: Add MassEditBar to index.tsx**

In `wookiee-hub/src/pages/product-matrix/index.tsx`, add after `<Page />`:

```tsx
import { MassEditBar } from "@/components/matrix/mass-edit-bar"

// Inside the <main> element, after <Page />:
<MassEditBar />
```

- [ ] **Step 3: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/matrix/mass-edit-bar.tsx wookiee-hub/src/pages/product-matrix/index.tsx
git commit -m "feat(matrix-ui): add mass edit bar with bulk status update actions"
```

---

### Task 29: Integration Test — All Phase 3 Routes

**Files:**
- Create: `tests/product_matrix_api/test_integration_phase3.py`

- [ ] **Step 1: Write comprehensive integration test**

```python
# tests/product_matrix_api/test_integration_phase3.py
"""Smoke tests for all Phase 3 API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
@pytest.mark.parametrize("path", [
    "/api/matrix/articles",
    "/api/matrix/products",
    "/api/matrix/colors",
    "/api/matrix/factories",
    "/api/matrix/importers",
    "/api/matrix/cards-wb",
    "/api/matrix/cards-ozon",
    "/api/matrix/certs",
])
async def test_entity_list_routes(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code != 404, f"Route {path} not registered"


@pytest.mark.anyio
async def test_search_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/search?q=test")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "total" in data
    assert "by_entity" in data


@pytest.mark.anyio
async def test_bulk_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/matrix/bulk/modeli_osnova",
            json={"ids": [], "action": "update", "changes": {}},
        )
    assert r.status_code == 200


@pytest.mark.anyio
async def test_openapi_includes_all_tags():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = list(spec["paths"].keys())
    expected_prefixes = [
        "/api/matrix/articles",
        "/api/matrix/products",
        "/api/matrix/colors",
        "/api/matrix/factories",
        "/api/matrix/importers",
        "/api/matrix/cards-wb",
        "/api/matrix/cards-ozon",
        "/api/matrix/certs",
        "/api/matrix/search",
        "/api/matrix/bulk",
    ]
    for prefix in expected_prefixes:
        assert any(p.startswith(prefix) for p in paths), f"Missing route prefix: {prefix}"
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/product_matrix_api/test_integration_phase3.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/product_matrix_api/test_integration_phase3.py
git commit -m "test(matrix-api): add Phase 3 integration smoke tests for all entity routes"
```

---

## Summary

| Task | What it delivers |
|------|-----------------|
| Task 16 | Pydantic schemas for all entities + search + bulk |
| Task 17 | CRUD route: artikuly (articles) |
| Task 18 | CRUD route: tovary (products/SKU) |
| Task 19 | CRUD routes: cveta, fabriki, importery |
| Task 20 | CRUD routes: skleyki_wb, skleyki_ozon (marketplace cards) |
| Task 21 | CRUD route: sertifikaty (certificates) |
| Task 22 | Global cross-entity search endpoint |
| Task 23 | Bulk update endpoint for mass editing |
| Task 24 | Frontend API types + methods for all entities |
| Task 25 | Frontend table pages for all 8 entities |
| Task 26 | Wire all entity pages to MatrixShell router |
| Task 27 | Global search dialog (Cmd+K) |
| Task 28 | Mass edit bar with bulk actions |
| Task 29 | Integration smoke tests for all Phase 3 routes |

After completing this plan, you will have:
- Full CRUD API for all 10 entity types (modeli_osnova, modeli, artikuly, tovary, cveta, fabriki, importery, skleyki_wb, skleyki_ozon, sertifikaty)
- Global cross-entity search with relevance sorting
- Bulk update endpoint for mass editing
- React pages for every entity with inline editing
- Cmd+K global search dialog
- Mass selection bar with preset bulk actions

**Next phases** (separate plans):
- Phase 4: Views, custom fields, saved views
- Phase 5: Safe deletion, archive, admin panel
- Phase 6: External data integration, Telegram auth
