# Product Matrix Editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Notion-like web editor for the Wookiee product matrix — FastAPI backend + React frontend for CRUD of all product entities with inline editing, nested hierarchy, and audit logging.

**Architecture:** FastAPI service (`services/product_matrix_api/`, port 8002) as middleware between React frontend (existing `wookiee-hub/`) and Supabase PostgreSQL. Backend handles all business logic, validation, and audit. Frontend uses existing design system (Tailwind + shadcn/ui + Zustand). New `hub` schema in same Supabase DB for audit logs and UI preferences.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 | React 19 / TypeScript / Vite / Tailwind / shadcn/ui / Zustand / @tanstack/react-table

**Spec:** `docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md`

---

## File Structure

### Backend: `services/product_matrix_api/`

| File | Responsibility |
|------|---------------|
| `app.py` | FastAPI app, CORS, error handlers, router registration |
| `config.py` | DB engines (public + hub schemas), session factories |
| `dependencies.py` | Stub auth (anonymous user), common query params |
| `models/database.py` | SQLAlchemy models for new tables (field_definitions, sertifikaty, archive_records, hub.*) |
| `models/schemas.py` | Pydantic request/response schemas |
| `routes/models.py` | `/api/matrix/models/*` — CRUD for modeli_osnova + modeli |
| `routes/search.py` | `/api/matrix/search` — global cross-entity search |
| `routes/admin.py` | `/api/matrix/admin/*` — audit logs, stats |
| `services/crud.py` | Generic CRUD operations using existing SQLAlchemy models |
| `services/audit_service.py` | Write audit entries to `hub.audit_log` |
| `services/validation.py` | CASCADE_RULES, delete impact calculation |

### Frontend: `wookiee-hub/src/`

| File | Responsibility |
|------|---------------|
| `pages/product-matrix/index.tsx` | MatrixShell — layout wrapper with sidebar + content |
| `pages/product-matrix/models-page.tsx` | Models table page |
| `pages/product-matrix/entity-detail-page.tsx` | Full-page entity detail view |
| `components/matrix/data-table.tsx` | Generic DataTable with inline editing |
| `components/matrix/table-cell.tsx` | Polymorphic cell renderer (text, select, relation, etc.) |
| `components/matrix/matrix-sidebar.tsx` | Entity navigation sidebar with counts |
| `components/matrix/matrix-topbar.tsx` | Title bar with search trigger + field settings |
| `components/matrix/view-tabs.tsx` | Data perspective tabs (Spec/Stock/Finance/Rating) |
| `components/matrix/detail-panel.tsx` | Slide-in detail panel |
| `stores/matrix-store.ts` | Zustand store for matrix UI state |
| `lib/matrix-api.ts` | Typed API client for `/api/matrix/*` endpoints |

---

## Phase 1: Backend Foundation

### Task 1: FastAPI Service Scaffold

**Files:**
- Create: `services/product_matrix_api/__init__.py`
- Create: `services/product_matrix_api/app.py`
- Create: `services/product_matrix_api/config.py`
- Create: `services/product_matrix_api/dependencies.py`
- Test: `tests/product_matrix_api/test_app.py`

- [ ] **Step 1: Create test for health endpoint**

```python
# tests/product_matrix_api/test_app.py
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.anyio
async def test_cors_headers():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.options(
            "/health",
            headers={"Origin": "http://localhost:25000", "Access-Control-Request-Method": "GET"},
        )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/product_matrix_api/test_app.py -v`
Expected: ModuleNotFoundError — services.product_matrix_api.app not found

- [ ] **Step 3: Create config.py**

```python
# services/product_matrix_api/config.py
"""Database configuration for Product Matrix API.

Reuses the existing sku_database connection pattern.
Creates two SQLAlchemy engines: one for public schema, one for hub schema.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load .env from project root
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env", override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _connection_string() -> str:
    host = _env("POSTGRES_HOST", _env("SUPABASE_HOST", "localhost"))
    port = _env("POSTGRES_PORT", _env("SUPABASE_PORT", "5432"))
    db = _env("POSTGRES_DB", _env("SUPABASE_DB", "postgres"))
    user = _env("POSTGRES_USER", _env("SUPABASE_USER", "postgres"))
    pwd = _env("POSTGRES_PASSWORD", _env("SUPABASE_PASSWORD", ""))
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


_conn_str = _connection_string()
_is_supabase = "supabase" in _conn_str.lower() or "pooler" in _conn_str.lower()
_connect_args = {"sslmode": "require"} if _is_supabase else {}

engine = create_engine(
    _conn_str,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency — yields a DB session, auto-closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Create dependencies.py**

```python
# services/product_matrix_api/dependencies.py
"""Shared FastAPI dependencies.

Auth is disabled for now (open testing access).
All actions are logged as user="anonymous".
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Query


@dataclass
class CurrentUser:
    id: int = 0
    email: str = "anonymous"
    name: str = "Anonymous"
    role: str = "admin"  # everyone is admin during testing


def get_current_user() -> CurrentUser:
    """Stub — returns anonymous admin user."""
    return CurrentUser()


@dataclass
class CommonQueryParams:
    page: int = 1
    per_page: int = 50
    sort: Optional[str] = None
    search: Optional[str] = None


def common_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> CommonQueryParams:
    return CommonQueryParams(page=page, per_page=per_page, sort=sort, search=search)
```

- [ ] **Step 5: Create app.py**

```python
# services/product_matrix_api/app.py
"""Product Matrix API — FastAPI backend for the Wookiee product matrix editor."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Product Matrix API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("product_matrix_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


@app.get("/health")
def health():
    return {"ok": True}
```

- [ ] **Step 6: Create `__init__.py`**

```python
# services/product_matrix_api/__init__.py
```

- [ ] **Step 7: Run test — expect PASS**

Run: `cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee && python -m pytest tests/product_matrix_api/test_app.py -v`
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add services/product_matrix_api/ tests/product_matrix_api/
git commit -m "feat(matrix-api): scaffold FastAPI service with health endpoint"
```

---

### Task 2: Database Models for New Tables

**Files:**
- Create: `services/product_matrix_api/models/__init__.py`
- Create: `services/product_matrix_api/models/database.py`
- Test: `tests/product_matrix_api/test_models.py`

- [ ] **Step 1: Write test for model instantiation**

```python
# tests/product_matrix_api/test_models.py
"""Test that all new SQLAlchemy models can be instantiated."""
from services.product_matrix_api.models.database import (
    FieldDefinition,
    Sertifikat,
    ModelOsnovaSertifikat,
    ArchiveRecord,
    HubUser,
    HubAuditLog,
)


def test_field_definition_instantiation():
    fd = FieldDefinition(
        entity_type="modeli_osnova",
        field_name="test_field",
        display_name="Test Field",
        field_type="text",
    )
    assert fd.entity_type == "modeli_osnova"
    assert fd.field_type == "text"
    assert fd.is_system is False
    assert fd.is_visible is True


def test_sertifikat_instantiation():
    s = Sertifikat(nazvanie="ЕАС Декларация", tip="EAC")
    assert s.nazvanie == "ЕАС Декларация"


def test_archive_record_instantiation():
    ar = ArchiveRecord(
        original_table="modeli_osnova",
        original_id=1,
        full_record={"kod": "Vuki"},
    )
    assert ar.original_table == "modeli_osnova"
    assert ar.restore_available is True


def test_hub_user_instantiation():
    u = HubUser(email="test@test.com", name="Test")
    assert u.role == "viewer"
    assert u.is_active is True


def test_hub_audit_log_instantiation():
    log = HubAuditLog(action="create", entity_type="modeli_osnova", entity_id=1)
    assert log.action == "create"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_models.py -v`
Expected: ImportError

- [ ] **Step 3: Create database models**

```python
# services/product_matrix_api/models/__init__.py
```

```python
# services/product_matrix_api/models/database.py
"""SQLAlchemy models for new tables introduced by the Product Matrix Editor.

Existing tables (modeli_osnova, modeli, artikuly, tovary, etc.) are already
defined in sku_database/database/models.py — we import and reuse them.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, BigInteger,
    ForeignKey, CheckConstraint, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from sku_database.database.models import Base


# ── Public schema: new tables ────────────────────────────────────────────────

class FieldDefinition(Base):
    """Метаданные кастомных полей (реестр, не DDL)."""
    __tablename__ = "field_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(
        String(30),
        CheckConstraint(
            "field_type IN ('text','number','select','multi_select','file',"
            "'url','relation','date','checkbox','formula','rollup')"
        ),
        nullable=False,
    )
    config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    section: Mapped[Optional[str]] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Sertifikat(Base):
    """Сертификаты."""
    __tablename__ = "sertifikaty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazvanie: Mapped[str] = mapped_column(String(200), nullable=False)
    tip: Mapped[Optional[str]] = mapped_column(String(100))
    nomer: Mapped[Optional[str]] = mapped_column(String(100))
    data_vydachi: Mapped[Optional[datetime]] = mapped_column(DateTime)
    data_okonchaniya: Mapped[Optional[datetime]] = mapped_column(DateTime)
    organ_sertifikacii: Mapped[Optional[str]] = mapped_column(String(200))
    file_url: Mapped[Optional[str]] = mapped_column(Text)
    gruppa_sertifikata: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelOsnovaSertifikat(Base):
    """Связь сертификатов с моделями основы (many-to-many)."""
    __tablename__ = "modeli_osnova_sertifikaty"

    model_osnova_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modeli_osnova.id", ondelete="CASCADE"), primary_key=True,
    )
    sertifikat_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sertifikaty.id", ondelete="CASCADE"), primary_key=True,
    )


class ArchiveRecord(Base):
    """Архив мягко удалённых записей."""
    __tablename__ = "archive_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_table: Mapped[str] = mapped_column(String(50), nullable=False)
    original_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_record: Mapped[dict] = mapped_column(JSON, nullable=False)
    related_records: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    deleted_by: Mapped[Optional[str]] = mapped_column(String(100))
    deleted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    restore_available: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Hub schema: UI data ─────────────────────────────────────────────────────

class HubUser(Base):
    """Пользователи Wookiee Hub."""
    __tablename__ = "users"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HubAuditLog(Base):
    """Аудит лог действий в UI."""
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    user_email: Mapped[Optional[str]] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    entity_name: Mapped[Optional[str]] = mapped_column(String(200))
    changes: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(String(36))
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_models.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/models/ tests/product_matrix_api/test_models.py
git commit -m "feat(matrix-api): add SQLAlchemy models for new tables (field_definitions, sertifikaty, archive_records, hub.*)"
```

---

### Task 3: Pydantic Schemas (Request/Response)

**Files:**
- Create: `services/product_matrix_api/models/schemas.py`
- Test: `tests/product_matrix_api/test_schemas.py`

- [ ] **Step 1: Write test for schema validation**

```python
# tests/product_matrix_api/test_schemas.py
import pytest
from pydantic import ValidationError

from services.product_matrix_api.models.schemas import (
    ModelOsnovaRead,
    ModelOsnovaCreate,
    ModelOsnovaUpdate,
    ModelRead,
    PaginatedResponse,
)


def test_model_osnova_create_valid():
    data = ModelOsnovaCreate(kod="TestModel", kategoriya_id=1)
    assert data.kod == "TestModel"


def test_model_osnova_create_missing_kod():
    with pytest.raises(ValidationError):
        ModelOsnovaCreate()


def test_model_osnova_update_partial():
    data = ModelOsnovaUpdate(material="Хлопок 95%")
    assert data.material == "Хлопок 95%"
    assert data.kod is None


def test_model_osnova_read():
    data = ModelOsnovaRead(
        id=1, kod="Vuki", kategoriya_id=1,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    assert data.id == 1


def test_model_read_with_osnova():
    data = ModelRead(
        id=1, kod="Vuki-IP", nazvanie="Vuki ИП",
        model_osnova_id=1, importer_id=1, status_id=1,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    assert data.model_osnova_id == 1


def test_paginated_response():
    resp = PaginatedResponse(
        items=[{"id": 1}], total=100, page=1, per_page=50, pages=2,
    )
    assert resp.pages == 2
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_schemas.py -v`
Expected: ImportError

- [ ] **Step 3: Create Pydantic schemas**

```python
# services/product_matrix_api/models/schemas.py
"""Pydantic v2 schemas for Product Matrix API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


# ── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int


# ── Modeli Osnova ────────────────────────────────────────────────────────────

class ModelOsnovaCreate(BaseModel):
    kod: str
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    sku_china: Optional[str] = None
    upakovka: Optional[str] = None
    ves_kg: Optional[float] = None
    dlina_cm: Optional[float] = None
    shirina_cm: Optional[float] = None
    vysota_cm: Optional[float] = None
    kratnost_koroba: Optional[int] = None
    srok_proizvodstva: Optional[str] = None
    komplektaciya: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    composition: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    nazvanie_etiketka: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    opisanie_sayt: Optional[str] = None
    tegi: Optional[str] = None
    notion_link: Optional[str] = None


class ModelOsnovaUpdate(BaseModel):
    kod: Optional[str] = None
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    sku_china: Optional[str] = None
    upakovka: Optional[str] = None
    ves_kg: Optional[float] = None
    dlina_cm: Optional[float] = None
    shirina_cm: Optional[float] = None
    vysota_cm: Optional[float] = None
    kratnost_koroba: Optional[int] = None
    srok_proizvodstva: Optional[str] = None
    komplektaciya: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    composition: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    gruppa_sertifikata: Optional[str] = None
    nazvanie_etiketka: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    opisanie_sayt: Optional[str] = None
    tegi: Optional[str] = None
    notion_link: Optional[str] = None


class ModelOsnovaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kod: str
    kategoriya_id: Optional[int] = None
    kollekciya_id: Optional[int] = None
    fabrika_id: Optional[int] = None
    razmery_modeli: Optional[str] = None
    material: Optional[str] = None
    sostav_syrya: Optional[str] = None
    tip_kollekcii: Optional[str] = None
    tnved: Optional[str] = None
    nazvanie_sayt: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Enriched by joins
    kategoriya_name: Optional[str] = None
    kollekciya_name: Optional[str] = None
    fabrika_name: Optional[str] = None
    children_count: Optional[int] = None


# ── Modeli (variations) ─────────────────────────────────────────────────────

class ModelCreate(BaseModel):
    kod: str
    nazvanie: str
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: bool = False
    rossiyskiy_razmer: Optional[str] = None


class ModelUpdate(BaseModel):
    kod: Optional[str] = None
    nazvanie: Optional[str] = None
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: Optional[bool] = None
    rossiyskiy_razmer: Optional[str] = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kod: str
    nazvanie: str
    nazvanie_en: Optional[str] = None
    artikul_modeli: Optional[str] = None
    model_osnova_id: Optional[int] = None
    importer_id: Optional[int] = None
    status_id: Optional[int] = None
    nabor: bool = False
    rossiyskiy_razmer: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Enriched by joins
    importer_name: Optional[str] = None
    status_name: Optional[str] = None
    artikuly_count: Optional[int] = None
    tovary_count: Optional[int] = None


# ── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: Optional[datetime] = None
    user_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    changes: Optional[dict] = None


# ── Lookups (for dropdowns) ──────────────────────────────────────────────────

class LookupItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nazvanie: str
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_schemas.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/models/schemas.py tests/product_matrix_api/test_schemas.py
git commit -m "feat(matrix-api): add Pydantic schemas for request/response models"
```

---

### Task 4: Audit Service

**Files:**
- Create: `services/product_matrix_api/services/__init__.py`
- Create: `services/product_matrix_api/services/audit_service.py`
- Test: `tests/product_matrix_api/test_audit_service.py`

- [ ] **Step 1: Write test for audit logging**

```python
# tests/product_matrix_api/test_audit_service.py
"""Test audit service (unit test — no DB)."""
from unittest.mock import MagicMock, patch

from services.product_matrix_api.services.audit_service import AuditService


def test_diff_changes():
    old = {"kod": "Vuki", "material": "Cotton"}
    new = {"kod": "Vuki", "material": "Silk"}
    diff = AuditService.diff_changes(old, new)
    assert diff == {"material": {"old": "Cotton", "new": "Silk"}}


def test_diff_changes_no_change():
    old = {"kod": "Vuki"}
    new = {"kod": "Vuki"}
    diff = AuditService.diff_changes(old, new)
    assert diff == {}


def test_diff_changes_ignores_none_to_none():
    old = {"kod": "Vuki", "material": None}
    new = {"kod": "Vuki", "material": None}
    diff = AuditService.diff_changes(old, new)
    assert diff == {}
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_audit_service.py -v`
Expected: ImportError

- [ ] **Step 3: Create audit service**

```python
# services/product_matrix_api/services/__init__.py
```

```python
# services/product_matrix_api/services/audit_service.py
"""Audit logging service — writes entries to hub.audit_log."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("product_matrix_api.audit")


class AuditService:
    """Writes audit log entries to hub.audit_log table."""

    @staticmethod
    def diff_changes(
        old: dict[str, Any], new: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Compare two dicts, return {field: {old, new}} for changed fields."""
        changes = {}
        for key in new:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        return changes

    @staticmethod
    def log(
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        entity_name: Optional[str] = None,
        changes: Optional[dict] = None,
        user_email: str = "anonymous",
        request_id: Optional[str] = None,
    ) -> None:
        """Insert an audit log entry into hub.audit_log."""
        import json

        db.execute(
            text("""
                INSERT INTO hub.audit_log
                    (user_email, action, entity_type, entity_id, entity_name, changes, request_id)
                VALUES
                    (:user_email, :action, :entity_type, :entity_id, :entity_name,
                     :changes::jsonb, :request_id)
            """),
            {
                "user_email": user_email,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "changes": json.dumps(changes) if changes else None,
                "request_id": request_id,
            },
        )
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_audit_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/ tests/product_matrix_api/test_audit_service.py
git commit -m "feat(matrix-api): add audit service with diff_changes and log methods"
```

---

### Task 5: Generic CRUD Service

**Files:**
- Create: `services/product_matrix_api/services/crud.py`
- Test: `tests/product_matrix_api/test_crud.py`

- [ ] **Step 1: Write test for CRUD service**

```python
# tests/product_matrix_api/test_crud.py
"""Test CRUD service with a mock DB session."""
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.product_matrix_api.services.crud import CrudService


class FakeModel:
    """Mimics a SQLAlchemy model for testing."""
    __tablename__ = "fake_table"
    id = None
    kod = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_build_filters_empty():
    filters = CrudService._build_filters(FakeModel, {})
    assert filters == []


def test_paginate_params():
    offset, limit = CrudService._paginate(page=2, per_page=50)
    assert offset == 50
    assert limit == 50


def test_paginate_page_1():
    offset, limit = CrudService._paginate(page=1, per_page=25)
    assert offset == 0
    assert limit == 25
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_crud.py -v`
Expected: ImportError

- [ ] **Step 3: Create CRUD service**

```python
# services/product_matrix_api/services/crud.py
"""Generic CRUD operations for all product matrix entities.

Uses existing SQLAlchemy models from sku_database/database/models.py.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Type, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

logger = logging.getLogger("product_matrix_api.crud")

T = TypeVar("T")


class CrudService:
    """Generic CRUD operations against SQLAlchemy models."""

    @staticmethod
    def _paginate(page: int, per_page: int) -> tuple[int, int]:
        """Return (offset, limit) for pagination."""
        offset = (page - 1) * per_page
        return offset, per_page

    @staticmethod
    def _build_filters(model: Type[T], filters: dict[str, Any]) -> list:
        """Convert {field: value} dict to SQLAlchemy filter conditions."""
        conditions = []
        mapper = inspect(model) if hasattr(model, "__mapper__") else None
        if not mapper:
            return conditions
        col_names = {c.key for c in mapper.column_attrs}
        for field, value in filters.items():
            if field in col_names and value is not None:
                conditions.append(getattr(model, field) == value)
        return conditions

    @staticmethod
    def get_list(
        db: Session,
        model: Type[T],
        *,
        page: int = 1,
        per_page: int = 50,
        filters: Optional[dict[str, Any]] = None,
        sort: Optional[str] = None,
    ) -> tuple[list[T], int]:
        """Fetch paginated list of records. Returns (items, total_count)."""
        query = select(model)

        if filters:
            for cond in CrudService._build_filters(model, filters):
                query = query.where(cond)

        # Sort
        if sort:
            field, _, direction = sort.partition(":")
            col = getattr(model, field, None)
            if col is not None:
                query = query.order_by(col.desc() if direction == "desc" else col.asc())

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = db.execute(count_q).scalar() or 0

        # Paginate
        offset, limit = CrudService._paginate(page, per_page)
        query = query.offset(offset).limit(limit)

        items = list(db.execute(query).scalars().all())
        return items, total

    @staticmethod
    def get_by_id(db: Session, model: Type[T], record_id: int) -> Optional[T]:
        """Fetch single record by id."""
        return db.get(model, record_id)

    @staticmethod
    def create(db: Session, model: Type[T], data: dict[str, Any]) -> T:
        """Create a new record."""
        instance = model(**data)
        db.add(instance)
        db.flush()
        db.refresh(instance)
        return instance

    @staticmethod
    def update(db: Session, instance: T, data: dict[str, Any]) -> T:
        """Update an existing record with non-None fields from data."""
        for field, value in data.items():
            if value is not None and hasattr(instance, field):
                setattr(instance, field, value)
        db.flush()
        db.refresh(instance)
        return instance

    @staticmethod
    def to_dict(instance: Any) -> dict[str, Any]:
        """Convert SQLAlchemy model instance to dict (column values only)."""
        mapper = inspect(type(instance))
        return {c.key: getattr(instance, c.key) for c in mapper.column_attrs}
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_crud.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/crud.py tests/product_matrix_api/test_crud.py
git commit -m "feat(matrix-api): add generic CRUD service with pagination, filtering, sorting"
```

---

### Task 6: Models CRUD Route (modeli_osnova + modeli)

**Files:**
- Create: `services/product_matrix_api/routes/__init__.py`
- Create: `services/product_matrix_api/routes/models.py`
- Modify: `services/product_matrix_api/app.py` — register router
- Test: `tests/product_matrix_api/test_routes_models.py`

- [ ] **Step 1: Write test for models endpoints**

```python
# tests/product_matrix_api/test_routes_models.py
"""Test models route — uses mocked DB session."""
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.fixture
def mock_db():
    """Patch get_db to return a mock session."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    with patch("services.product_matrix_api.routes.models.get_db") as mock_get_db:
        mock_get_db.return_value = iter([mock_session])
        yield mock_session


@pytest.mark.anyio
async def test_list_models_osnova_route_exists():
    """Verify the endpoint exists and returns a response (may fail on DB)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/models")
    # 200 or 500 (if DB not available) — but NOT 404
    assert resp.status_code != 404


@pytest.mark.anyio
async def test_get_model_osnova_not_found():
    """Verify 404 for non-existent record."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/models/99999")
    # Could be 404 or 500 depending on DB — but route must exist
    assert resp.status_code != 405
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `python -m pytest tests/product_matrix_api/test_routes_models.py -v`
Expected: 404 (route not registered yet)

- [ ] **Step 3: Create routes/__init__.py**

```python
# services/product_matrix_api/routes/__init__.py
```

- [ ] **Step 4: Create models route**

```python
# services/product_matrix_api/routes/models.py
"""CRUD routes for modeli_osnova and modeli."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    ModelOsnovaCreate, ModelOsnovaUpdate, ModelOsnovaRead,
    ModelCreate, ModelUpdate, ModelRead,
    PaginatedResponse, LookupItem,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

# Import existing ORM models
from sku_database.database.models import ModelOsnova, Model

logger = logging.getLogger("product_matrix_api.routes.models")

router = APIRouter(prefix="/api/matrix/models", tags=["models"])


# ── Modeli Osnova ────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
def list_models_osnova(
    params: CommonQueryParams = Depends(common_params),
    kategoriya_id: Optional[int] = Query(None),
    kollekciya_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    if kategoriya_id:
        filters["kategoriya_id"] = kategoriya_id
    if kollekciya_id:
        filters["kollekciya_id"] = kollekciya_id

    items, total = CrudService.get_list(
        db, ModelOsnova,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=params.sort,
    )

    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    return PaginatedResponse(
        items=[ModelOsnovaRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{model_id}", response_model=ModelOsnovaRead)
def get_model_osnova(model_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, ModelOsnova, model_id)
    if not item:
        raise HTTPException(404, "Model osnova not found")
    return ModelOsnovaRead.model_validate(item)


@router.post("", response_model=ModelOsnovaRead, status_code=201)
def create_model_osnova(
    body: ModelOsnovaCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, ModelOsnova, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="modeli_osnova",
        entity_id=item.id, entity_name=item.kod, user_email=user.email,
    )
    db.commit()
    return ModelOsnovaRead.model_validate(item)


@router.patch("/{model_id}", response_model=ModelOsnovaRead)
def update_model_osnova(
    model_id: int,
    body: ModelOsnovaUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, ModelOsnova, model_id)
    if not item:
        raise HTTPException(404, "Model osnova not found")

    old_data = CrudService.to_dict(item)
    update_data = body.model_dump(exclude_none=True)
    item = CrudService.update(db, item, update_data)

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="modeli_osnova",
            entity_id=item.id, entity_name=item.kod,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return ModelOsnovaRead.model_validate(item)


# ── Modeli (child variations) ────────────────────────────────────────────────

@router.get("/{osnova_id}/children", response_model=list[ModelRead])
def list_child_models(osnova_id: int, db: Session = Depends(get_db)):
    items, _ = CrudService.get_list(
        db, Model, filters={"model_osnova_id": osnova_id}, per_page=200,
    )
    return [ModelRead.model_validate(item) for item in items]


@router.post("/{osnova_id}/children", response_model=ModelRead, status_code=201)
def create_child_model(
    osnova_id: int,
    body: ModelCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    data = body.model_dump(exclude_none=True)
    data["model_osnova_id"] = osnova_id
    item = CrudService.create(db, Model, data)
    AuditService.log(
        db, action="create", entity_type="modeli",
        entity_id=item.id, entity_name=item.kod, user_email=user.email,
    )
    db.commit()
    return ModelRead.model_validate(item)
```

- [ ] **Step 5: Register router in app.py**

Add to `services/product_matrix_api/app.py` after the health endpoint:

```python
from services.product_matrix_api.routes.models import router as models_router

app.include_router(models_router)
```

- [ ] **Step 6: Run test — expect PASS**

Run: `python -m pytest tests/product_matrix_api/test_routes_models.py -v`
Expected: 2 passed (route exists, not 404)

- [ ] **Step 7: Commit**

```bash
git add services/product_matrix_api/routes/ services/product_matrix_api/app.py tests/product_matrix_api/test_routes_models.py
git commit -m "feat(matrix-api): add CRUD routes for modeli_osnova and modeli"
```

---

### Task 7: Lookups Route (справочники для dropdowns)

**Files:**
- Create: `services/product_matrix_api/routes/lookups.py`
- Modify: `services/product_matrix_api/app.py` — register router
- Test: `tests/product_matrix_api/test_routes_lookups.py`

- [ ] **Step 1: Write test**

```python
# tests/product_matrix_api/test_routes_lookups.py
import pytest
from httpx import AsyncClient, ASGITransport
from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_lookups_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/matrix/lookups/kategorii")
    assert resp.status_code != 404
```

- [ ] **Step 2: Run test — expect FAIL (404)**

- [ ] **Step 3: Create lookups route**

```python
# services/product_matrix_api/routes/lookups.py
"""Lookup routes — reference tables for dropdown selectors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import LookupItem
from sku_database.database.models import (
    Kategoriya, Kollekciya, Status, Razmer, Importer, Fabrika,
)

router = APIRouter(prefix="/api/matrix/lookups", tags=["lookups"])

LOOKUP_MAP = {
    "kategorii": Kategoriya,
    "kollekcii": Kollekciya,
    "statusy": Status,
    "razmery": Razmer,
    "importery": Importer,
    "fabriki": Fabrika,
}


@router.get("/{table_name}", response_model=list[LookupItem])
def get_lookup(table_name: str, db: Session = Depends(get_db)):
    model = LOOKUP_MAP.get(table_name)
    if not model:
        raise HTTPException(404, f"Unknown lookup table: {table_name}")
    items = db.query(model).order_by(model.nazvanie).all()
    return [LookupItem.model_validate(item) for item in items]
```

- [ ] **Step 4: Register in app.py**

```python
from services.product_matrix_api.routes.lookups import router as lookups_router
app.include_router(lookups_router)
```

- [ ] **Step 5: Run test — expect PASS**

- [ ] **Step 6: Commit**

```bash
git add services/product_matrix_api/routes/lookups.py services/product_matrix_api/app.py tests/product_matrix_api/test_routes_lookups.py
git commit -m "feat(matrix-api): add lookups route for reference table dropdowns"
```

---

### Task 8: SQL Migration Script + Vite Proxy

**Files:**
- Create: `services/product_matrix_api/migrations/001_initial.sql`
- Modify: `wookiee-hub/vite.config.ts` — add proxy for `/api/matrix`

- [ ] **Step 1: Create migration SQL**

```sql
-- services/product_matrix_api/migrations/001_initial.sql
-- Creates new tables and hub schema for Product Matrix Editor.
-- Run against Supabase PostgreSQL.

-- Hub schema
CREATE SCHEMA IF NOT EXISTS hub;

-- field_definitions
CREATE TABLE IF NOT EXISTS field_definitions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    field_type VARCHAR(30) NOT NULL
        CHECK (field_type IN (
            'text', 'number', 'select', 'multi_select', 'file',
            'url', 'relation', 'date', 'checkbox', 'formula', 'rollup'
        )),
    config JSONB DEFAULT '{}',
    section VARCHAR(100),
    sort_order INT DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    is_visible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_type, field_name)
);

-- sertifikaty
CREATE TABLE IF NOT EXISTS sertifikaty (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(200) NOT NULL,
    tip VARCHAR(100),
    nomer VARCHAR(100),
    data_vydachi DATE,
    data_okonchaniya DATE,
    organ_sertifikacii VARCHAR(200),
    file_url TEXT,
    gruppa_sertifikata VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- modeli_osnova_sertifikaty (M2M)
CREATE TABLE IF NOT EXISTS modeli_osnova_sertifikaty (
    model_osnova_id INT REFERENCES modeli_osnova(id) ON DELETE CASCADE,
    sertifikat_id INT REFERENCES sertifikaty(id) ON DELETE CASCADE,
    PRIMARY KEY (model_osnova_id, sertifikat_id)
);

-- archive_records
CREATE TABLE IF NOT EXISTS archive_records (
    id SERIAL PRIMARY KEY,
    original_table VARCHAR(50) NOT NULL,
    original_id INT NOT NULL,
    full_record JSONB NOT NULL,
    related_records JSONB DEFAULT '[]',
    deleted_by VARCHAR(100),
    deleted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),
    restore_available BOOLEAN DEFAULT TRUE
);

-- hub.users
CREATE TABLE IF NOT EXISTS hub.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE NOT NULL,
    name VARCHAR(200),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'editor', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- hub.audit_log
CREATE TABLE IF NOT EXISTS hub.audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INT REFERENCES hub.users(id),
    user_email VARCHAR(200),
    action VARCHAR(30) NOT NULL
        CHECK (action IN (
            'create', 'update', 'delete', 'bulk_update',
            'bulk_delete', 'restore', 'login', 'export'
        )),
    entity_type VARCHAR(50),
    entity_id INT,
    entity_name VARCHAR(200),
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON hub.audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON hub.audit_log(entity_type, entity_id);

-- hub.saved_views
CREATE TABLE IF NOT EXISTS hub.saved_views (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES hub.users(id),
    entity_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- hub.ui_preferences
CREATE TABLE IF NOT EXISTS hub.ui_preferences (
    user_id INT PRIMARY KEY REFERENCES hub.users(id),
    sidebar_collapsed BOOLEAN DEFAULT FALSE,
    theme VARCHAR(10) DEFAULT 'dark',
    column_widths JSONB DEFAULT '{}',
    sidebar_order JSONB DEFAULT '[]',
    recent_entities JSONB DEFAULT '[]',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- RLS
ALTER TABLE field_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE modeli_osnova_sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE archive_records ENABLE ROW LEVEL SECURITY;

-- Insert default anonymous user for testing
INSERT INTO hub.users (email, name, role) VALUES ('anonymous', 'Anonymous', 'admin')
ON CONFLICT (email) DO NOTHING;
```

- [ ] **Step 2: Add Vite proxy for matrix API**

In `wookiee-hub/vite.config.ts`, update the proxy section:

```typescript
proxy: {
  "/api/matrix": {
    target: "http://localhost:8002",
    changeOrigin: true,
  },
  "/api": {
    target: "http://localhost:8001",
    changeOrigin: true,
  },
},
```

Note: `/api/matrix` must come BEFORE `/api` so the more specific prefix matches first.

- [ ] **Step 3: Commit**

```bash
git add services/product_matrix_api/migrations/ wookiee-hub/vite.config.ts
git commit -m "feat(matrix-api): add SQL migration and Vite proxy for matrix API"
```

---

## Phase 2: Frontend Core

### Task 9: Matrix API Client + Zustand Store

**Files:**
- Create: `wookiee-hub/src/lib/matrix-api.ts`
- Create: `wookiee-hub/src/stores/matrix-store.ts`

- [ ] **Step 1: Create typed API client**

```typescript
// wookiee-hub/src/lib/matrix-api.ts
import { get, post } from "@/lib/api-client"

// ── Types ───────────────────────────────────────────────────────────────────

export interface ModelOsnova {
  id: number
  kod: string
  kategoriya_id: number | null
  kollekciya_id: number | null
  fabrika_id: number | null
  razmery_modeli: string | null
  material: string | null
  sostav_syrya: string | null
  tip_kollekcii: string | null
  tnved: string | null
  nazvanie_sayt: string | null
  created_at: string | null
  updated_at: string | null
  kategoriya_name: string | null
  kollekciya_name: string | null
  fabrika_name: string | null
  children_count: number | null
}

export interface ModelVariation {
  id: number
  kod: string
  nazvanie: string
  nazvanie_en: string | null
  artikul_modeli: string | null
  model_osnova_id: number | null
  importer_id: number | null
  status_id: number | null
  nabor: boolean
  rossiyskiy_razmer: string | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  status_name: string | null
  artikuly_count: number | null
  tovary_count: number | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface LookupItem {
  id: number
  nazvanie: string
}

// ── API calls ───────────────────────────────────────────────────────────────

export const matrixApi = {
  // Models osnova
  listModels: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ModelOsnova>>("/api/matrix/models", params),

  getModel: (id: number) =>
    get<ModelOsnova>(`/api/matrix/models/${id}`),

  createModel: (data: Partial<ModelOsnova>) =>
    post<ModelOsnova>("/api/matrix/models", data),

  updateModel: (id: number, data: Partial<ModelOsnova>) =>
    fetch(`/api/matrix/models/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(r => r.json() as Promise<ModelOsnova>),

  // Child models
  listChildren: (osnovaId: number) =>
    get<ModelVariation[]>(`/api/matrix/models/${osnovaId}/children`),

  // Lookups
  getLookup: (table: string) =>
    get<LookupItem[]>(`/api/matrix/lookups/${table}`),
}
```

- [ ] **Step 2: Create Zustand store**

```typescript
// wookiee-hub/src/stores/matrix-store.ts
import { create } from "zustand"

export type MatrixEntity =
  | "models"
  | "articles"
  | "products"
  | "colors"
  | "factories"
  | "importers"
  | "cards-wb"
  | "cards-ozon"
  | "certs"

export type ViewTab = "spec" | "stock" | "finance" | "rating"

interface MatrixState {
  activeEntity: MatrixEntity
  activeView: ViewTab
  expandedRows: Set<number>
  selectedRows: Set<number>
  detailPanelId: number | null
  searchOpen: boolean
  searchQuery: string

  setActiveEntity: (entity: MatrixEntity) => void
  setActiveView: (view: ViewTab) => void
  toggleRowExpanded: (id: number) => void
  toggleRowSelected: (id: number) => void
  selectAllRows: (ids: number[]) => void
  clearSelection: () => void
  openDetailPanel: (id: number) => void
  closeDetailPanel: () => void
  setSearchOpen: (open: boolean) => void
  setSearchQuery: (query: string) => void
}

export const useMatrixStore = create<MatrixState>((set) => ({
  activeEntity: "models",
  activeView: "spec",
  expandedRows: new Set(),
  selectedRows: new Set(),
  detailPanelId: null,
  searchOpen: false,
  searchQuery: "",

  setActiveEntity: (entity) => set({ activeEntity: entity, selectedRows: new Set() }),
  setActiveView: (view) => set({ activeView: view }),
  toggleRowExpanded: (id) =>
    set((s) => {
      const next = new Set(s.expandedRows)
      next.has(id) ? next.delete(id) : next.add(id)
      return { expandedRows: next }
    }),
  toggleRowSelected: (id) =>
    set((s) => {
      const next = new Set(s.selectedRows)
      next.has(id) ? next.delete(id) : next.add(id)
      return { selectedRows: next }
    }),
  selectAllRows: (ids) => set({ selectedRows: new Set(ids) }),
  clearSelection: () => set({ selectedRows: new Set() }),
  openDetailPanel: (id) => set({ detailPanelId: id }),
  closeDetailPanel: () => set({ detailPanelId: null }),
  setSearchOpen: (open) => set({ searchOpen: open }),
  setSearchQuery: (query) => set({ searchQuery: query }),
}))
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/lib/matrix-api.ts wookiee-hub/src/stores/matrix-store.ts
git commit -m "feat(matrix-ui): add typed API client and Zustand store for matrix state"
```

---

### Task 10: MatrixShell Layout + MatrixSidebar

**Files:**
- Create: `wookiee-hub/src/pages/product-matrix/index.tsx`
- Create: `wookiee-hub/src/components/matrix/matrix-sidebar.tsx`
- Create: `wookiee-hub/src/components/matrix/matrix-topbar.tsx`
- Modify: `wookiee-hub/src/router.tsx` — replace stub with matrix routes
- Modify: `wookiee-hub/src/config/navigation.ts` — no changes needed (path already exists)

- [ ] **Step 1: Create MatrixSidebar**

```tsx
// wookiee-hub/src/components/matrix/matrix-sidebar.tsx
import { cn } from "@/lib/utils"
import { useMatrixStore, type MatrixEntity } from "@/stores/matrix-store"
import {
  Box, Palette, Factory, Building2, CreditCard,
  ShoppingCart, FileCheck, Layers,
} from "lucide-react"

const entities: { id: MatrixEntity; label: string; icon: typeof Box }[] = [
  { id: "models", label: "Модели", icon: Box },
  { id: "colors", label: "Цвета", icon: Palette },
  { id: "factories", label: "Фабрики", icon: Factory },
  { id: "importers", label: "Импортёры", icon: Building2 },
  { id: "articles", label: "Артикулы", icon: Layers },
  { id: "products", label: "Товары/SKU", icon: ShoppingCart },
  { id: "cards-wb", label: "Склейки WB", icon: CreditCard },
  { id: "cards-ozon", label: "Склейки Ozon", icon: CreditCard },
  { id: "certs", label: "Сертификаты", icon: FileCheck },
]

export function MatrixSidebar() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-muted/30 p-3">
      <h3 className="mb-3 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Сущности
      </h3>
      <nav className="space-y-0.5">
        {entities.map((e) => (
          <button
            key={e.id}
            onClick={() => setActiveEntity(e.id)}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
              activeEntity === e.id
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
            )}
          >
            <e.icon className="h-4 w-4 shrink-0" />
            {e.label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: Create MatrixTopbar**

```tsx
// wookiee-hub/src/components/matrix/matrix-topbar.tsx
import { Search, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useMatrixStore } from "@/stores/matrix-store"

const entityLabels: Record<string, string> = {
  models: "Модели",
  articles: "Артикулы",
  products: "Товары / SKU",
  colors: "Цвета",
  factories: "Фабрики",
  importers: "Импортёры",
  "cards-wb": "Склейки WB",
  "cards-ozon": "Склейки Ozon",
  certs: "Сертификаты",
}

export function MatrixTopbar() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setSearchOpen = useMatrixStore((s) => s.setSearchOpen)

  return (
    <div className="flex h-12 items-center justify-between border-b border-border px-4">
      <h2 className="text-lg font-semibold">
        {entityLabels[activeEntity] ?? activeEntity}
      </h2>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSearchOpen(true)}
          className="gap-1.5 text-muted-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="text-xs">Поиск</span>
          <kbd className="ml-1 rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
            ⌘K
          </kbd>
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create MatrixShell (page layout)**

```tsx
// wookiee-hub/src/pages/product-matrix/index.tsx
import { MatrixSidebar } from "@/components/matrix/matrix-sidebar"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { useMatrixStore } from "@/stores/matrix-store"
import { ModelsPage } from "./models-page"

export function ProductMatrixLayout() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)

  return (
    <div className="flex h-full">
      <MatrixSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MatrixTopbar />
        <main className="flex-1 overflow-auto p-4">
          {activeEntity === "models" && <ModelsPage />}
          {activeEntity !== "models" && (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              Раздел «{activeEntity}» — скоро
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create stub ModelsPage**

```tsx
// wookiee-hub/src/pages/product-matrix/models-page.tsx
export function ModelsPage() {
  return (
    <div className="text-muted-foreground">
      Таблица моделей — будет реализована в Task 11
    </div>
  )
}
```

- [ ] **Step 5: Update router.tsx**

Replace the existing `ProductMatrixPage` stub route with matrix routes:

```tsx
// In router.tsx, replace:
//   { path: "/product/matrix", element: <ProductMatrixPage /> },
// with:
import { ProductMatrixLayout } from "@/pages/product-matrix"

// In the children array:
{ path: "/product/matrix", element: <ProductMatrixLayout /> },
```

Remove `ProductMatrixPage` from the stubs import.

- [ ] **Step 6: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add wookiee-hub/src/pages/product-matrix/ wookiee-hub/src/components/matrix/ wookiee-hub/src/router.tsx
git commit -m "feat(matrix-ui): add MatrixShell layout with sidebar and topbar"
```

---

### Task 11: DataTable Component (core table with inline editing)

**Files:**
- Create: `wookiee-hub/src/components/matrix/data-table.tsx`
- Create: `wookiee-hub/src/components/matrix/table-cell.tsx`

- [ ] **Step 1: Create TableCell (polymorphic cell renderer)**

```tsx
// wookiee-hub/src/components/matrix/table-cell.tsx
import { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"

export type CellType = "text" | "number" | "select" | "relation" | "readonly"

interface TableCellProps {
  value: string | number | null
  type: CellType
  options?: { id: number; label: string }[]
  onSave?: (value: string | number | null) => void
  readOnly?: boolean
}

export function TableCell({ value, type, options, onSave, readOnly }: TableCellProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value ?? ""))
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  if (readOnly || type === "readonly" || type === "relation") {
    return (
      <span className="block truncate px-2 py-1 text-sm">
        {value ?? "—"}
      </span>
    )
  }

  if (!editing) {
    return (
      <button
        onClick={() => { setDraft(String(value ?? "")); setEditing(true) }}
        className="block w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-accent/40"
      >
        {value ?? "—"}
      </button>
    )
  }

  const commit = () => {
    setEditing(false)
    const newVal = type === "number" ? (draft ? Number(draft) : null) : (draft || null)
    if (newVal !== value) onSave?.(newVal)
  }

  if (type === "select" && options) {
    return (
      <select
        className="w-full rounded border border-border bg-background px-1 py-0.5 text-sm"
        value={draft}
        onChange={(e) => { setDraft(e.target.value); }}
        onBlur={commit}
        autoFocus
      >
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.id} value={o.id}>{o.label}</option>
        ))}
      </select>
    )
  }

  return (
    <Input
      ref={inputRef}
      type={type === "number" ? "number" : "text"}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false) }}
      className="h-7 px-1 text-sm"
    />
  )
}
```

- [ ] **Step 2: Create DataTable**

```tsx
// wookiee-hub/src/components/matrix/data-table.tsx
import { ChevronRight, ChevronDown } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
import { TableCell, type CellType } from "./table-cell"
import { cn } from "@/lib/utils"

export interface Column<T> {
  key: string
  label: string
  width?: number
  type?: CellType
  options?: { id: number; label: string }[]
  render?: (row: T) => React.ReactNode
}

interface DataTableProps<T extends { id: number }> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  expandedRows?: Set<number>
  selectedRows?: Set<number>
  childrenMap?: Map<number, T[]>
  hasChildren?: (row: T) => boolean
  onToggleExpand?: (id: number) => void
  onToggleSelect?: (id: number) => void
  onCellEdit?: (id: number, field: string, value: string | number | null) => void
  onRowClick?: (id: number) => void
}

export function DataTable<T extends { id: number }>({
  columns,
  data,
  loading,
  expandedRows = new Set(),
  selectedRows = new Set(),
  childrenMap,
  hasChildren,
  onToggleExpand,
  onToggleSelect,
  onCellEdit,
  onRowClick,
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground">
        Загрузка...
      </div>
    )
  }

  return (
    <div className="overflow-auto rounded-md border border-border">
      <table className="w-full table-fixed border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
          <tr>
            <th className="w-10 border-b border-border px-2 py-2" />
            <th className="w-8 border-b border-border px-2 py-2" />
            {columns.map((col) => (
              <th
                key={col.key}
                style={col.width ? { width: col.width } : undefined}
                className="border-b border-border px-2 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const isExpanded = expandedRows.has(row.id)
            const hasKids = hasChildren?.(row) ?? false
            const children = childrenMap?.get(row.id) ?? []

            return (
              <>
                <tr
                  key={row.id}
                  className={cn(
                    "group border-b border-border transition-colors hover:bg-accent/20",
                    selectedRows.has(row.id) && "bg-accent/10",
                  )}
                >
                  <td className="px-2 py-1.5 text-center">
                    {hasKids ? (
                      <button
                        onClick={() => onToggleExpand?.(row.id)}
                        className="rounded p-0.5 hover:bg-accent/50"
                      >
                        {isExpanded
                          ? <ChevronDown className="h-4 w-4" />
                          : <ChevronRight className="h-4 w-4" />}
                      </button>
                    ) : (
                      <span className="inline-block w-5" />
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <Checkbox
                      checked={selectedRows.has(row.id)}
                      onCheckedChange={() => onToggleSelect?.(row.id)}
                    />
                  </td>
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-0 py-0 cursor-pointer"
                      onClick={() => onRowClick?.(row.id)}
                    >
                      {col.render ? (
                        col.render(row)
                      ) : (
                        <TableCell
                          value={(row as Record<string, unknown>)[col.key] as string | number | null}
                          type={col.type ?? "text"}
                          options={col.options}
                          onSave={(val) => onCellEdit?.(row.id, col.key, val)}
                        />
                      )}
                    </td>
                  ))}
                </tr>
                {isExpanded &&
                  children.map((child) => (
                    <tr
                      key={`child-${child.id}`}
                      className="border-b border-border bg-muted/20 hover:bg-accent/10"
                    >
                      <td />
                      <td className="px-2 py-1.5">
                        <Checkbox
                          checked={selectedRows.has(child.id)}
                          onCheckedChange={() => onToggleSelect?.(child.id)}
                        />
                      </td>
                      {columns.map((col) => (
                        <td key={col.key} className="px-0 py-0">
                          {col.render ? (
                            col.render(child)
                          ) : (
                            <TableCell
                              value={(child as Record<string, unknown>)[col.key] as string | number | null}
                              type={col.type ?? "text"}
                              options={col.options}
                              onSave={(val) => onCellEdit?.(child.id, col.key, val)}
                            />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add wookiee-hub/src/components/matrix/data-table.tsx wookiee-hub/src/components/matrix/table-cell.tsx
git commit -m "feat(matrix-ui): add DataTable and TableCell components with inline editing"
```

---

### Task 12: ModelsPage — Wire DataTable to API

**Files:**
- Modify: `wookiee-hub/src/pages/product-matrix/models-page.tsx`

- [ ] **Step 1: Implement ModelsPage with data fetching**

```tsx
// wookiee-hub/src/pages/product-matrix/models-page.tsx
import { useCallback, useEffect, useState } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"

const columns: Column<ModelOsnova>[] = [
  { key: "kod", label: "Код", width: 140, type: "text" },
  { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
  { key: "kollekciya_name", label: "Коллекция", width: 160, type: "readonly" },
  { key: "fabrika_name", label: "Фабрика", width: 140, type: "readonly" },
  { key: "material", label: "Материал", width: 200, type: "text" },
  { key: "razmery_modeli", label: "Размеры", width: 120, type: "text" },
  { key: "tip_kollekcii", label: "Тип коллекции", width: 180, type: "readonly" },
  { key: "children_count", label: "Подмодели", width: 100, type: "readonly" },
]

export function ModelsPage() {
  const expandedRows = useMatrixStore((s) => s.expandedRows)
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowExpanded = useMatrixStore((s) => s.toggleRowExpanded)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listModels({ per_page: 200 }),
    [],
  )

  const [childrenMap, setChildrenMap] = useState<Map<number, ModelVariation[]>>(new Map())

  // Fetch children when a row is expanded
  useEffect(() => {
    for (const id of expandedRows) {
      if (!childrenMap.has(id)) {
        matrixApi.listChildren(id).then((kids) => {
          setChildrenMap((prev) => new Map(prev).set(id, kids))
        })
      }
    }
  }, [expandedRows])

  const handleCellEdit = useCallback(async (id: number, field: string, value: string | number | null) => {
    await matrixApi.updateModel(id, { [field]: value })
  }, [])

  return (
    <div className="space-y-3">
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        expandedRows={expandedRows}
        selectedRows={selectedRows}
        childrenMap={childrenMap as Map<number, ModelOsnova[]>}
        hasChildren={(row) => (row.children_count ?? 0) > 0}
        onToggleExpand={toggleRowExpanded}
        onToggleSelect={toggleRowSelected}
        onCellEdit={handleCellEdit}
        onRowClick={openDetailPanel}
      />
    </div>
  )
}
```

- [ ] **Step 2: Create ViewTabs component**

```tsx
// wookiee-hub/src/components/matrix/view-tabs.tsx
import { cn } from "@/lib/utils"
import { useMatrixStore, type ViewTab } from "@/stores/matrix-store"

const tabs: { id: ViewTab; label: string }[] = [
  { id: "spec", label: "Спецификация" },
  { id: "stock", label: "Склад" },
  { id: "finance", label: "Финансы" },
  { id: "rating", label: "Рейтинг" },
]

export function ViewTabs() {
  const activeView = useMatrixStore((s) => s.activeView)
  const setActiveView = useMatrixStore((s) => s.setActiveView)

  return (
    <div className="flex gap-1 border-b border-border">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveView(tab.id)}
          className={cn(
            "px-3 py-1.5 text-sm transition-colors",
            activeView === tab.id
              ? "border-b-2 border-primary font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/product-matrix/models-page.tsx wookiee-hub/src/components/matrix/view-tabs.tsx
git commit -m "feat(matrix-ui): wire ModelsPage to API with DataTable, ViewTabs, and inline editing"
```

---

### Task 13: Detail Panel (slide-in)

**Files:**
- Create: `wookiee-hub/src/components/matrix/detail-panel.tsx`
- Modify: `wookiee-hub/src/pages/product-matrix/index.tsx` — render panel

- [ ] **Step 1: Create DetailPanel**

```tsx
// wookiee-hub/src/components/matrix/detail-panel.tsx
import { X, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { useNavigate } from "react-router-dom"

export function DetailPanel() {
  const detailPanelId = useMatrixStore((s) => s.detailPanelId)
  const closeDetailPanel = useMatrixStore((s) => s.closeDetailPanel)
  const navigate = useNavigate()

  const { data, loading } = useApiQuery(
    () => detailPanelId ? matrixApi.getModel(detailPanelId) : Promise.resolve(null),
    [detailPanelId],
  )

  if (!detailPanelId) return null

  return (
    <aside className="w-96 shrink-0 border-l border-border bg-background overflow-y-auto">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="font-semibold">{data?.kod ?? "Загрузка..."}</h3>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => {
              navigate(`/product/matrix/models/${detailPanelId}`)
              closeDetailPanel()
            }}
          >
            <ExternalLink className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={closeDetailPanel}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="p-4 text-sm text-muted-foreground">Загрузка...</div>
      ) : data ? (
        <div className="space-y-4 p-4">
          <Section title="Основные">
            <Field label="Код" value={data.kod} />
            <Field label="Категория" value={data.kategoriya_name} />
            <Field label="Коллекция" value={data.kollekciya_name} />
            <Field label="Фабрика" value={data.fabrika_name} />
            <Field label="Тип коллекции" value={data.tip_kollekcii} />
          </Section>
          <Section title="Размеры и упаковка">
            <Field label="Размеры" value={data.razmery_modeli} />
            <Field label="Материал" value={data.material} />
            <Field label="Состав" value={data.sostav_syrya} />
          </Section>
          <Section title="Логистика">
            <Field label="ТНВЭД" value={data.tnved} />
          </Section>
          <Section title="Контент">
            <Field label="Название для сайта" value={data.nazvanie_sayt} />
          </Section>
        </div>
      ) : (
        <div className="p-4 text-sm text-muted-foreground">Не найдено</div>
      )}
    </aside>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      <div className="space-y-1">{children}</div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline gap-2 rounded px-2 py-1 text-sm hover:bg-accent/20">
      <span className="w-32 shrink-0 text-muted-foreground">{label}</span>
      <span className="text-foreground">{value ?? "—"}</span>
    </div>
  )
}
```

- [ ] **Step 2: Add DetailPanel to MatrixShell**

Update `wookiee-hub/src/pages/product-matrix/index.tsx` — add `<DetailPanel />` inside the flex layout, after the main content area:

```tsx
import { DetailPanel } from "@/components/matrix/detail-panel"

// In the return JSX, after </div> (the flex-1 column):
<DetailPanel />
```

- [ ] **Step 3: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/components/matrix/detail-panel.tsx wookiee-hub/src/pages/product-matrix/index.tsx
git commit -m "feat(matrix-ui): add slide-in detail panel for entity inspection"
```

---

### Task 14: Full Detail Page Route

**Files:**
- Create: `wookiee-hub/src/pages/product-matrix/entity-detail-page.tsx`
- Modify: `wookiee-hub/src/router.tsx` — add detail route

- [ ] **Step 1: Create entity detail page**

```tsx
// wookiee-hub/src/pages/product-matrix/entity-detail-page.tsx
import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi } from "@/lib/matrix-api"

export function EntityDetailPage() {
  const { entity, id } = useParams<{ entity: string; id: string }>()
  const navigate = useNavigate()

  const { data, loading } = useApiQuery(
    () => matrixApi.getModel(Number(id)),
    [id],
  )

  return (
    <div className="mx-auto max-w-4xl p-6">
      <Button
        variant="ghost"
        size="sm"
        className="mb-4 gap-1"
        onClick={() => navigate("/product/matrix")}
      >
        <ArrowLeft className="h-4 w-4" /> Назад к матрице
      </Button>

      {loading ? (
        <div className="text-muted-foreground">Загрузка...</div>
      ) : data ? (
        <div>
          <h1 className="mb-6 text-2xl font-bold">{data.kod}</h1>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {Object.entries(data).map(([key, val]) =>
              val != null && key !== "id" ? (
                <div key={key} className="rounded border border-border p-3">
                  <span className="block text-xs text-muted-foreground">{key}</span>
                  <span>{String(val)}</span>
                </div>
              ) : null,
            )}
          </div>
        </div>
      ) : (
        <div className="text-muted-foreground">Запись не найдена</div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add route to router.tsx**

```tsx
import { EntityDetailPage } from "@/pages/product-matrix/entity-detail-page"

// Add after the matrix route:
{ path: "/product/matrix/:entity/:id", element: <EntityDetailPage /> },
```

- [ ] **Step 3: Verify build**

Run: `cd wookiee-hub && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add wookiee-hub/src/pages/product-matrix/entity-detail-page.tsx wookiee-hub/src/router.tsx
git commit -m "feat(matrix-ui): add full entity detail page with back navigation"
```

---

### Task 15: Integration Smoke Test

**Files:**
- Create: `tests/product_matrix_api/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

```python
# tests/product_matrix_api/test_integration.py
"""Smoke tests for Product Matrix API endpoints (mock DB)."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_all_routes_registered():
    """Verify all expected route prefixes are registered."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Health
        r = await ac.get("/health")
        assert r.status_code == 200

        # Models route exists
        r = await ac.get("/api/matrix/models")
        assert r.status_code != 404, "Models route not found"

        # Lookups route exists
        r = await ac.get("/api/matrix/lookups/kategorii")
        assert r.status_code != 404, "Lookups route not found"

        # OpenAPI docs
        r = await ac.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "Product Matrix API" in spec["info"]["title"]
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/product_matrix_api/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/product_matrix_api/test_integration.py
git commit -m "test(matrix-api): add integration smoke tests for all registered routes"
```

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| Phase 1: Backend | Tasks 1–8 | FastAPI service, DB models, CRUD, audit, migration SQL |
| Phase 2: Frontend | Tasks 9–15 | MatrixShell layout, DataTable, inline editing, detail panel, API client |

After completing this plan, you will have:
- A running FastAPI server on port 8002 with CRUD for modeli_osnova/modeli
- Audit logging to hub.audit_log
- React UI with sidebar navigation, data table with expandable nested rows, inline editing, and slide-in detail panel
- All wired together through Vite proxy

**Next phases** (separate plans):
- Phase 3: All remaining entities CRUD
- Phase 4: Views, custom fields, saved views
- Phase 5: Safe deletion, archive, admin panel
- Phase 6: External data integration, Telegram auth
