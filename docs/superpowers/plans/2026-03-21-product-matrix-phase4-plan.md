# Product Matrix Phase 4: Views & Custom Fields — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add view-based column switching (Spec/Stock/Finance/Rating), custom fields system via JSONB `custom_fields`, and saved views (user-defined column+filter+sort presets).

**Architecture:** Three layers — (1) Backend: schema routes for field_definitions CRUD, views routes for saved_views CRUD, view query param on list endpoints to filter columns; (2) Frontend: ViewTabs upgraded to render saved views + "+" button, column configs per view, field management dialog; (3) Data: `custom_fields` JSONB on entity tables, `field_definitions` registry, `hub.saved_views` storage.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, React 19, Zustand, TypeScript, Tailwind, shadcn/ui

---

## File Structure

### Backend (new files)

| File | Responsibility |
|------|----------------|
| `services/product_matrix_api/routes/schema.py` | Field definitions CRUD: list/create/update/delete per entity |
| `services/product_matrix_api/routes/views.py` | Saved views CRUD: list/create/update/delete per entity |
| `services/product_matrix_api/services/field_service.py` | Custom field value read/write via JSONB, validation, field definition management |
| `tests/product_matrix_api/test_schema_routes.py` | Tests for schema routes |
| `tests/product_matrix_api/test_views_routes.py` | Tests for views routes |
| `tests/product_matrix_api/test_field_service.py` | Tests for field service logic |

### Backend (modified files)

| File | Changes |
|------|---------|
| `services/product_matrix_api/models/database.py` | Add `HubSavedView` model |
| `services/product_matrix_api/models/schemas.py` | Add Pydantic schemas for fields, views, custom_fields on reads |
| `services/product_matrix_api/app.py` | Register schema + views routers |
| `services/product_matrix_api/services/crud.py` | Add `custom_fields` merge on create/update, include in `to_dict` |

### Frontend (new files)

| File | Responsibility |
|------|----------------|
| `wookiee-hub/src/lib/view-columns.ts` | Per-entity column configs for each built-in view (spec/stock/finance/rating) |
| `wookiee-hub/src/components/matrix/manage-fields-dialog.tsx` | Dialog for adding/editing/reordering custom fields |
| `wookiee-hub/src/components/matrix/save-view-dialog.tsx` | Dialog for saving current column+filter+sort as a named view |
| `wookiee-hub/src/stores/views-store.ts` | Zustand store for saved views state |

### Frontend (modified files)

| File | Changes |
|------|---------|
| `wookiee-hub/src/stores/matrix-store.ts` | Add `ViewTab` union with saved view IDs |
| `wookiee-hub/src/components/matrix/view-tabs.tsx` | Render saved views tabs + "+" create button |
| `wookiee-hub/src/lib/matrix-api.ts` | Add schema API and views API methods |
| `wookiee-hub/src/pages/product-matrix/models-page.tsx` | Use view-aware columns |
| All other entity pages | Same pattern: use view-aware columns |
| `wookiee-hub/src/components/matrix/matrix-topbar.tsx` | Add "Настроить поля" button |

---

## Task 1: HubSavedView SQLAlchemy Model + Pydantic Schemas

**Files:**
- Modify: `services/product_matrix_api/models/database.py`
- Modify: `services/product_matrix_api/models/schemas.py`
- Test: `tests/product_matrix_api/test_schemas_phase4.py`

- [ ] **Step 1: Write test for new Pydantic schemas**

Create `tests/product_matrix_api/test_schemas_phase4.py`:

```python
"""Tests for Phase 4 Pydantic schemas (fields, views)."""
import pytest
from pydantic import ValidationError

from services.product_matrix_api.models.schemas import (
    FieldDefinitionCreate,
    FieldDefinitionRead,
    FieldDefinitionUpdate,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
    ViewConfig,
)


def test_field_definition_create_valid():
    fd = FieldDefinitionCreate(
        entity_type="modeli_osnova",
        field_name="custom_weight",
        display_name="Custom Weight",
        field_type="number",
    )
    assert fd.entity_type == "modeli_osnova"
    assert fd.config == {}


def test_field_definition_create_with_select_config():
    fd = FieldDefinitionCreate(
        entity_type="artikuly",
        field_name="quality",
        display_name="Качество",
        field_type="select",
        config={"options": ["A", "B", "C"]},
        section="Основные",
    )
    assert fd.config["options"] == ["A", "B", "C"]


def test_field_definition_create_invalid_type():
    with pytest.raises(ValidationError):
        FieldDefinitionCreate(
            entity_type="modeli",
            field_name="test",
            display_name="Test",
            field_type="invalid_type",
        )


def test_field_definition_create_invalid_name():
    with pytest.raises(ValidationError):
        FieldDefinitionCreate(
            entity_type="modeli",
            field_name="has spaces",
            display_name="Test",
            field_type="text",
        )


def test_field_definition_read():
    fd = FieldDefinitionRead(
        id=1,
        entity_type="modeli_osnova",
        field_name="test",
        display_name="Test",
        field_type="text",
        config={},
        section=None,
        sort_order=0,
        is_system=False,
        is_visible=True,
    )
    assert fd.id == 1


def test_field_definition_update_partial():
    fu = FieldDefinitionUpdate(display_name="New Name")
    assert fu.display_name == "New Name"
    assert fu.field_type is None


def test_view_config():
    vc = ViewConfig(
        columns=["kod", "material"],
        filters=[{"field": "status_id", "op": "eq", "value": 1}],
        sort=[{"field": "kod", "dir": "asc"}],
    )
    assert len(vc.columns) == 2
    assert vc.group_by is None


def test_saved_view_create():
    sv = SavedViewCreate(
        entity_type="modeli_osnova",
        name="Мой вид",
        config=ViewConfig(columns=["kod", "material"]),
    )
    assert sv.name == "Мой вид"


def test_saved_view_read():
    sv = SavedViewRead(
        id=1,
        user_id=None,
        entity_type="modeli_osnova",
        name="Test",
        config={"columns": ["kod"]},
        is_default=False,
        sort_order=0,
    )
    assert sv.id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/product_matrix_api/test_schemas_phase4.py -v`
Expected: ImportError — schemas don't exist yet

- [ ] **Step 3: Add HubSavedView to database.py**

Add to `services/product_matrix_api/models/database.py` after `HubAuditLog`:

```python
class HubSavedView(_DefaultsMixin, Base):
    """Сохранённые представления таблиц (per user)."""
    __tablename__ = "saved_views"
    __table_args__ = {"schema": "hub"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Add Pydantic schemas to schemas.py**

Add to `services/product_matrix_api/models/schemas.py`:

```python
# ── Field Definitions ───────────────────────────────────────────────────────

VALID_FIELD_TYPES = {
    "text", "number", "select", "multi_select", "file",
    "url", "relation", "date", "checkbox", "formula", "rollup",
}

VALID_ENTITY_TYPES = {
    "modeli_osnova", "modeli", "artikuly", "tovary", "cveta",
    "fabriki", "importery", "skleyki_wb", "skleyki_ozon", "sertifikaty",
}

FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,99}$"


class FieldDefinitionCreate(BaseModel):
    entity_type: str
    field_name: str  # validated below
    display_name: str
    field_type: str  # validated below
    config: dict = {}
    section: Optional[str] = None
    sort_order: int = 0

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: str) -> str:
        if v not in VALID_FIELD_TYPES:
            raise ValueError(f"field_type must be one of {VALID_FIELD_TYPES}")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {VALID_ENTITY_TYPES}")
        return v

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        import re
        if not re.match(FIELD_NAME_PATTERN, v):
            raise ValueError("field_name must match [a-z][a-z0-9_]*, max 100 chars")
        return v


class FieldDefinitionUpdate(BaseModel):
    display_name: Optional[str] = None
    field_type: Optional[str] = None
    config: Optional[dict] = None
    section: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None

    @field_validator("field_type")
    @classmethod
    def validate_field_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_FIELD_TYPES:
            raise ValueError(f"field_type must be one of {VALID_FIELD_TYPES}")
        return v


class FieldDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    field_name: str
    display_name: str
    field_type: str
    config: dict
    section: Optional[str]
    sort_order: int
    is_system: bool
    is_visible: bool


# ── Saved Views ──────────────────────────────────────────────────────────────

class ViewConfig(BaseModel):
    columns: list[str] = []
    filters: list[dict] = []
    sort: list[dict] = []
    group_by: Optional[str] = None


class SavedViewCreate(BaseModel):
    entity_type: str
    name: str
    config: ViewConfig
    is_default: bool = False
    sort_order: int = 0

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {VALID_ENTITY_TYPES}")
        return v


class SavedViewUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[ViewConfig] = None
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int]
    entity_type: str
    name: str
    config: dict
    is_default: bool
    sort_order: int
```

Note: Add `from pydantic import field_validator` to imports.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/product_matrix_api/test_schemas_phase4.py -v`
Expected: All 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/product_matrix_api/test_schemas_phase4.py services/product_matrix_api/models/database.py services/product_matrix_api/models/schemas.py
git commit -m "feat(matrix): add Phase 4 schemas — FieldDefinition, SavedView Pydantic + HubSavedView ORM"
```

---

## Task 2: Field Service — Custom Field Value Logic

**Files:**
- Create: `services/product_matrix_api/services/field_service.py`
- Test: `tests/product_matrix_api/test_field_service.py`

- [ ] **Step 1: Write tests for field service**

Create `tests/product_matrix_api/test_field_service.py`:

```python
"""Tests for FieldService — custom field definition management + value operations."""
import pytest

from services.product_matrix_api.services.field_service import FieldService


def test_validate_custom_value_text():
    assert FieldService.validate_value("text", "hello") == "hello"


def test_validate_custom_value_number():
    assert FieldService.validate_value("number", 42) == 42
    assert FieldService.validate_value("number", "3.14") == 3.14


def test_validate_custom_value_number_invalid():
    with pytest.raises(ValueError):
        FieldService.validate_value("number", "not_a_number")


def test_validate_custom_value_checkbox():
    assert FieldService.validate_value("checkbox", True) is True
    assert FieldService.validate_value("checkbox", "false") is False


def test_validate_custom_value_select():
    config = {"options": ["A", "B", "C"]}
    assert FieldService.validate_value("select", "A", config) == "A"


def test_validate_custom_value_select_invalid():
    config = {"options": ["A", "B", "C"]}
    with pytest.raises(ValueError, match="not in allowed options"):
        FieldService.validate_value("select", "D", config)


def test_validate_custom_value_multi_select():
    config = {"options": ["A", "B", "C"]}
    assert FieldService.validate_value("multi_select", ["A", "C"], config) == ["A", "C"]


def test_validate_custom_value_multi_select_invalid():
    config = {"options": ["A", "B"]}
    with pytest.raises(ValueError):
        FieldService.validate_value("multi_select", ["A", "Z"], config)


def test_validate_custom_value_url():
    assert FieldService.validate_value("url", "https://example.com") == "https://example.com"


def test_validate_custom_value_date():
    assert FieldService.validate_value("date", "2026-01-15") == "2026-01-15"


def test_validate_custom_value_date_invalid():
    with pytest.raises(ValueError):
        FieldService.validate_value("date", "not-a-date")


def test_merge_custom_fields():
    existing = {"weight": 100, "note": "old"}
    updates = {"weight": 200, "color_tag": "red"}
    result = FieldService.merge_custom_fields(existing, updates)
    assert result == {"weight": 200, "note": "old", "color_tag": "red"}


def test_merge_custom_fields_none_removes():
    existing = {"weight": 100, "note": "old"}
    updates = {"note": None}
    result = FieldService.merge_custom_fields(existing, updates)
    assert result == {"weight": 100}


def test_max_custom_fields_exceeded():
    existing = {f"field_{i}": i for i in range(50)}
    with pytest.raises(ValueError, match="Maximum 50"):
        FieldService.merge_custom_fields(existing, {"field_51": "overflow"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/product_matrix_api/test_field_service.py -v`
Expected: ImportError

- [ ] **Step 3: Implement field service**

Create `services/product_matrix_api/services/field_service.py`:

```python
"""Custom field value validation and management."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional


MAX_CUSTOM_FIELDS = 50


class FieldService:
    """Stateless helpers for custom field operations."""

    @staticmethod
    def validate_value(
        field_type: str,
        value: Any,
        config: Optional[dict] = None,
    ) -> Any:
        """Validate and coerce a custom field value based on its type."""
        if value is None:
            return None

        config = config or {}

        if field_type == "text":
            return str(value)

        if field_type == "number":
            try:
                return float(value) if "." in str(value) else int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert {value!r} to number")

        if field_type == "checkbox":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)

        if field_type == "select":
            options = config.get("options", [])
            if options and value not in options:
                raise ValueError(f"{value!r} not in allowed options: {options}")
            return value

        if field_type == "multi_select":
            if not isinstance(value, list):
                raise ValueError("multi_select value must be a list")
            options = config.get("options", [])
            if options:
                invalid = [v for v in value if v not in options]
                if invalid:
                    raise ValueError(f"{invalid} not in allowed options: {options}")
            return value

        if field_type == "date":
            if isinstance(value, date):
                return value.isoformat()
            try:
                date.fromisoformat(str(value))
                return str(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date: {value!r}")

        if field_type in ("url", "file"):
            return str(value)

        # relation, formula, rollup — pass through
        return value

    @staticmethod
    def merge_custom_fields(
        existing: dict,
        updates: dict,
    ) -> dict:
        """Merge updates into existing custom_fields. None values remove keys."""
        result = dict(existing)
        for k, v in updates.items():
            if v is None:
                result.pop(k, None)
            else:
                result[k] = v
        if len(result) > MAX_CUSTOM_FIELDS:
            raise ValueError(f"Maximum {MAX_CUSTOM_FIELDS} custom fields per entity")
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/product_matrix_api/test_field_service.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/product_matrix_api/services/field_service.py tests/product_matrix_api/test_field_service.py
git commit -m "feat(matrix): add FieldService for custom field validation and merge"
```

---

## Task 3: Schema Routes — Field Definitions CRUD

**Files:**
- Create: `services/product_matrix_api/routes/schema.py`
- Modify: `services/product_matrix_api/app.py`
- Test: `tests/product_matrix_api/test_schema_routes.py`

- [ ] **Step 1: Write tests**

Create `tests/product_matrix_api/test_schema_routes.py`:

```python
"""Tests for /api/matrix/schema routes — field definitions CRUD."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_fields_returns_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/schema/modeli_osnova")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_list_fields_invalid_entity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/schema/nonexistent")
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_field():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/matrix/schema/modeli_osnova/fields", json={
            "entity_type": "modeli_osnova",
            "field_name": "test_weight",
            "display_name": "Test Weight",
            "field_type": "number",
        })
    # 201 if DB is available, or we just check it's not 404/405
    assert r.status_code != 404, "Route not registered"
    assert r.status_code != 405, "Method not allowed"


@pytest.mark.anyio
async def test_create_field_invalid_type():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/matrix/schema/modeli_osnova/fields", json={
            "entity_type": "modeli_osnova",
            "field_name": "bad",
            "display_name": "Bad",
            "field_type": "invalid",
        })
    assert r.status_code == 422


@pytest.mark.anyio
async def test_update_field_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.patch("/api/matrix/schema/modeli_osnova/fields/999", json={
            "display_name": "Updated",
        })
    assert r.status_code != 404 or r.json().get("detail") == "Field definition not found"


@pytest.mark.anyio
async def test_delete_field_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete("/api/matrix/schema/modeli_osnova/fields/999")
    assert r.status_code != 405, "DELETE not allowed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/product_matrix_api/test_schema_routes.py -v`
Expected: FAIL — routes not registered

- [ ] **Step 3: Implement schema routes**

Create `services/product_matrix_api/routes/schema.py`:

```python
"""Field definitions CRUD — /api/matrix/schema/{entity_type}."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.database import FieldDefinition
from services.product_matrix_api.models.schemas import (
    VALID_ENTITY_TYPES,
    FieldDefinitionCreate,
    FieldDefinitionRead,
    FieldDefinitionUpdate,
)
from services.product_matrix_api.services.audit_service import AuditService

logger = logging.getLogger("product_matrix_api.routes.schema")

router = APIRouter(prefix="/api/matrix/schema", tags=["schema"])


def _validate_entity(entity_type: str) -> str:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(422, f"Invalid entity_type: {entity_type}")
    return entity_type


@router.get("/{entity_type}", response_model=list[FieldDefinitionRead])
def list_fields(
    entity_type: str = Path(...),
    db: Session = Depends(get_db),
):
    _validate_entity(entity_type)
    q = (
        select(FieldDefinition)
        .where(FieldDefinition.entity_type == entity_type)
        .order_by(FieldDefinition.sort_order, FieldDefinition.id)
    )
    items = list(db.execute(q).scalars().all())
    return [FieldDefinitionRead.model_validate(item) for item in items]


@router.post("/{entity_type}/fields", response_model=FieldDefinitionRead, status_code=201)
def create_field(
    body: FieldDefinitionCreate,
    entity_type: str = Path(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _validate_entity(entity_type)
    if body.entity_type != entity_type:
        raise HTTPException(400, "entity_type in body must match URL path")

    # Check uniqueness
    existing = db.execute(
        select(FieldDefinition).where(
            FieldDefinition.entity_type == entity_type,
            FieldDefinition.field_name == body.field_name,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Field '{body.field_name}' already exists for {entity_type}")

    # Count existing fields (max 50)
    count = db.execute(
        select(FieldDefinition)
        .where(FieldDefinition.entity_type == entity_type)
    ).scalars().all()
    if len(count) >= 50:
        raise HTTPException(400, "Maximum 50 custom fields per entity")

    field = FieldDefinition(**body.model_dump())
    db.add(field)
    db.flush()
    db.refresh(field)

    AuditService.log(
        db, action="create", entity_type="field_definitions",
        entity_id=field.id, entity_name=f"{entity_type}.{body.field_name}",
        user_email=user.email,
    )
    db.commit()
    return FieldDefinitionRead.model_validate(field)


@router.patch("/{entity_type}/fields/{field_id}", response_model=FieldDefinitionRead)
def update_field(
    field_id: int,
    body: FieldDefinitionUpdate,
    entity_type: str = Path(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _validate_entity(entity_type)
    field = db.get(FieldDefinition, field_id)
    if not field or field.entity_type != entity_type:
        raise HTTPException(404, "Field definition not found")
    if field.is_system:
        raise HTTPException(403, "Cannot modify system field")

    update_data = body.model_dump(exclude_none=True)
    for k, v in update_data.items():
        setattr(field, k, v)
    db.flush()
    db.refresh(field)

    AuditService.log(
        db, action="update", entity_type="field_definitions",
        entity_id=field.id, entity_name=f"{entity_type}.{field.field_name}",
        changes=update_data, user_email=user.email,
    )
    db.commit()
    return FieldDefinitionRead.model_validate(field)


@router.delete("/{entity_type}/fields/{field_id}", status_code=204)
def delete_field(
    field_id: int,
    entity_type: str = Path(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _validate_entity(entity_type)
    field = db.get(FieldDefinition, field_id)
    if not field or field.entity_type != entity_type:
        raise HTTPException(404, "Field definition not found")
    if field.is_system:
        raise HTTPException(403, "Cannot delete system field")

    AuditService.log(
        db, action="delete", entity_type="field_definitions",
        entity_id=field.id, entity_name=f"{entity_type}.{field.field_name}",
        user_email=user.email,
    )
    db.delete(field)
    db.commit()
```

- [ ] **Step 4: Register router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.schema import router as schema_router
# ...
app.include_router(schema_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/product_matrix_api/test_schema_routes.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python3 -m pytest tests/product_matrix_api/ -v`
Expected: All existing + new tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/product_matrix_api/routes/schema.py services/product_matrix_api/app.py tests/product_matrix_api/test_schema_routes.py
git commit -m "feat(matrix): add schema routes — field definitions CRUD"
```

---

## Task 4: Views Routes — Saved Views CRUD

**Files:**
- Create: `services/product_matrix_api/routes/views.py`
- Modify: `services/product_matrix_api/app.py`
- Test: `tests/product_matrix_api/test_views_routes.py`

- [ ] **Step 1: Write tests**

Create `tests/product_matrix_api/test_views_routes.py`:

```python
"""Tests for /api/matrix/views routes — saved views CRUD."""
import pytest
from httpx import AsyncClient, ASGITransport

from services.product_matrix_api.app import app


@pytest.mark.anyio
async def test_list_views():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/views?entity_type=modeli_osnova")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_list_views_requires_entity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/matrix/views")
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_view():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/matrix/views", json={
            "entity_type": "modeli_osnova",
            "name": "Test View",
            "config": {"columns": ["kod", "material"], "filters": [], "sort": []},
        })
    assert r.status_code != 404, "Route not registered"
    assert r.status_code != 405, "Method not allowed"


@pytest.mark.anyio
async def test_update_view_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.patch("/api/matrix/views/999", json={"name": "Renamed"})
    # Should be 404 (view not found) or 200, not 405
    assert r.status_code != 405


@pytest.mark.anyio
async def test_delete_view_route_exists():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.delete("/api/matrix/views/999")
    assert r.status_code != 405
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/product_matrix_api/test_views_routes.py -v`
Expected: FAIL — routes not registered

- [ ] **Step 3: Implement views routes**

Create `services/product_matrix_api/routes/views.py`:

```python
"""Saved views CRUD — /api/matrix/views."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.database import HubSavedView
from services.product_matrix_api.models.schemas import (
    VALID_ENTITY_TYPES,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
)
from services.product_matrix_api.services.audit_service import AuditService

logger = logging.getLogger("product_matrix_api.routes.views")

router = APIRouter(prefix="/api/matrix/views", tags=["views"])


@router.get("", response_model=list[SavedViewRead])
def list_views(
    entity_type: str = Query(...),
    db: Session = Depends(get_db),
):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(422, f"Invalid entity_type: {entity_type}")
    q = (
        select(HubSavedView)
        .where(HubSavedView.entity_type == entity_type)
        .order_by(HubSavedView.sort_order, HubSavedView.id)
    )
    items = list(db.execute(q).scalars().all())
    return [SavedViewRead.model_validate(item) for item in items]


@router.post("", response_model=SavedViewRead, status_code=201)
def create_view(
    body: SavedViewCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = HubSavedView(
        user_id=user.id if user.id else None,
        entity_type=body.entity_type,
        name=body.name,
        config=body.config.model_dump(),
        is_default=body.is_default,
        sort_order=body.sort_order,
    )
    db.add(view)
    db.flush()
    db.refresh(view)

    AuditService.log(
        db, action="create", entity_type="saved_views",
        entity_id=view.id, entity_name=view.name,
        user_email=user.email,
    )
    db.commit()
    return SavedViewRead.model_validate(view)


@router.patch("/{view_id}", response_model=SavedViewRead)
def update_view(
    view_id: int,
    body: SavedViewUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = db.get(HubSavedView, view_id)
    if not view:
        raise HTTPException(404, "Saved view not found")

    update_data = body.model_dump(exclude_none=True)
    for k, v in update_data.items():
        if k == "config" and v is not None:
            setattr(view, k, v.model_dump() if hasattr(v, "model_dump") else v)
        else:
            setattr(view, k, v)
    db.flush()
    db.refresh(view)

    AuditService.log(
        db, action="update", entity_type="saved_views",
        entity_id=view.id, entity_name=view.name,
        changes=update_data, user_email=user.email,
    )
    db.commit()
    return SavedViewRead.model_validate(view)


@router.delete("/{view_id}", status_code=204)
def delete_view(
    view_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = db.get(HubSavedView, view_id)
    if not view:
        raise HTTPException(404, "Saved view not found")

    AuditService.log(
        db, action="delete", entity_type="saved_views",
        entity_id=view.id, entity_name=view.name,
        user_email=user.email,
    )
    db.delete(view)
    db.commit()
```

- [ ] **Step 4: Register router in app.py**

Add to `services/product_matrix_api/app.py`:

```python
from services.product_matrix_api.routes.views import router as views_router
# ...
app.include_router(views_router)
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/product_matrix_api/test_views_routes.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest tests/product_matrix_api/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add services/product_matrix_api/routes/views.py services/product_matrix_api/app.py tests/product_matrix_api/test_views_routes.py
git commit -m "feat(matrix): add saved views routes — list/create/update/delete"
```

---

## Task 5: Frontend — View Column Configs + API Methods

**Files:**
- Create: `wookiee-hub/src/lib/view-columns.ts`
- Modify: `wookiee-hub/src/lib/matrix-api.ts`

- [ ] **Step 1: Add API methods for schema and views**

Add to `wookiee-hub/src/lib/matrix-api.ts` — new types:

```typescript
export interface FieldDefinition {
  id: number
  entity_type: string
  field_name: string
  display_name: string
  field_type: string
  config: Record<string, unknown>
  section: string | null
  sort_order: number
  is_system: boolean
  is_visible: boolean
}

export interface ViewConfig {
  columns: string[]
  filters: Array<{ field: string; op: string; value: unknown }>
  sort: Array<{ field: string; dir: string }>
  group_by?: string
}

export interface SavedView {
  id: number
  user_id: number | null
  entity_type: string
  name: string
  config: ViewConfig
  is_default: boolean
  sort_order: number
}
```

Add to `matrixApi` object:

```typescript
  // Schema — field definitions
  listFields: (entityType: string) =>
    get<FieldDefinition[]>(`/api/matrix/schema/${entityType}`),

  createField: (entityType: string, data: Partial<FieldDefinition>) =>
    post<FieldDefinition>(`/api/matrix/schema/${entityType}/fields`, data),

  updateField: (entityType: string, fieldId: number, data: Partial<FieldDefinition>) =>
    patch<FieldDefinition>(`/api/matrix/schema/${entityType}/fields/${fieldId}`, data),

  deleteField: (entityType: string, fieldId: number) =>
    del(`/api/matrix/schema/${entityType}/fields/${fieldId}`),

  // Saved views
  listViews: (entityType: string) =>
    get<SavedView[]>("/api/matrix/views", { entity_type: entityType }),

  createView: (data: { entity_type: string; name: string; config: ViewConfig }) =>
    post<SavedView>("/api/matrix/views", data),

  updateView: (viewId: number, data: Partial<SavedView>) =>
    patch<SavedView>(`/api/matrix/views/${viewId}`, data),

  deleteView: (viewId: number) =>
    del(`/api/matrix/views/${viewId}`),
```

Note: Need to add `del` function to `api-client.ts` (or use `fetch` with DELETE method):
```typescript
export async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) throw new ApiError(res.status, await res.text())
  if (res.status === 204) return undefined as T
  return res.json()
}
```

- [ ] **Step 2: Create view-columns.ts**

Create `wookiee-hub/src/lib/view-columns.ts`:

```typescript
import type { Column } from "@/components/matrix/data-table"

// Built-in view definitions per entity.
// Each entity has a "spec" view (default) and optional stock/finance/rating views.
// Views that need external data (stock, finance, rating) show placeholder columns
// that will be filled when external data integration is added in Phase 6.

type ViewId = "spec" | "stock" | "finance" | "rating"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ColumnDef = Column<any>

const MODELS_VIEWS: Record<ViewId, ColumnDef[]> = {
  spec: [
    { key: "kod", label: "Код", width: 140, type: "text" },
    { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
    { key: "kollekciya_name", label: "Коллекция", width: 160, type: "readonly" },
    { key: "fabrika_name", label: "Фабрика", width: 140, type: "readonly" },
    { key: "material", label: "Материал", width: 200, type: "text" },
    { key: "razmery_modeli", label: "Размеры", width: 120, type: "text" },
    { key: "tip_kollekcii", label: "Тип коллекции", width: 180, type: "readonly" },
    { key: "children_count", label: "Подмодели", width: 100, type: "readonly" },
  ],
  stock: [
    { key: "kod", label: "Код", width: 140, type: "text" },
    { key: "kategoriya_name", label: "Категория", width: 140, type: "readonly" },
    { key: "children_count", label: "Подмодели", width: 100, type: "readonly" },
    // Phase 6 placeholders — will come from WB/Ozon API
    { key: "_stock_wb", label: "Остаток WB", width: 120, type: "readonly" },
    { key: "_stock_ozon", label: "Остаток Ozon", width: 120, type: "readonly" },
    { key: "_stock_transit", label: "В пути", width: 100, type: "readonly" },
    { key: "_days_supply", label: "Дней запаса", width: 110, type: "readonly" },
  ],
  finance: [
    { key: "kod", label: "Код", width: 140, type: "text" },
    { key: "kategoriya_name", label: "Категория", width: 140, type: "readonly" },
    // Phase 6 placeholders
    { key: "_revenue", label: "Выручка", width: 120, type: "readonly" },
    { key: "_margin", label: "Маржа %", width: 100, type: "readonly" },
    { key: "_drr", label: "ДРР %", width: 90, type: "readonly" },
    { key: "_orders", label: "Заказы", width: 100, type: "readonly" },
    { key: "_abc", label: "ABC", width: 80, type: "readonly" },
  ],
  rating: [
    { key: "kod", label: "Код", width: 140, type: "text" },
    { key: "kategoriya_name", label: "Категория", width: 140, type: "readonly" },
    // Phase 6 placeholders
    { key: "_rating_wb", label: "Рейтинг WB", width: 110, type: "readonly" },
    { key: "_rating_ozon", label: "Рейтинг Ozon", width: 110, type: "readonly" },
    { key: "_reviews_count", label: "Отзывы", width: 100, type: "readonly" },
    { key: "_avg_score", label: "Ср. оценка", width: 100, type: "readonly" },
  ],
}

const ARTICLES_VIEWS: Record<ViewId, ColumnDef[]> = {
  spec: [
    { key: "artikul", label: "Артикул", width: 160, type: "text" },
    { key: "model_name", label: "Модель", width: 160, type: "readonly" },
    { key: "cvet_name", label: "Цвет", width: 140, type: "readonly" },
    { key: "status_name", label: "Статус", width: 120, type: "readonly" },
    { key: "nomenklatura_wb", label: "Номенклатура WB", width: 160, type: "readonly" },
    { key: "artikul_ozon", label: "Артикул Ozon", width: 160, type: "readonly" },
    { key: "tovary_count", label: "SKU", width: 80, type: "readonly" },
  ],
  stock: [
    { key: "artikul", label: "Артикул", width: 160, type: "text" },
    { key: "cvet_name", label: "Цвет", width: 120, type: "readonly" },
    { key: "status_name", label: "Статус", width: 100, type: "readonly" },
    { key: "_stock_wb", label: "Остаток WB", width: 120, type: "readonly" },
    { key: "_stock_ozon", label: "Остаток Ozon", width: 120, type: "readonly" },
  ],
  finance: [
    { key: "artikul", label: "Артикул", width: 160, type: "text" },
    { key: "cvet_name", label: "Цвет", width: 120, type: "readonly" },
    { key: "_revenue", label: "Выручка", width: 120, type: "readonly" },
    { key: "_margin", label: "Маржа %", width: 100, type: "readonly" },
    { key: "_orders", label: "Заказы", width: 100, type: "readonly" },
  ],
  rating: [
    { key: "artikul", label: "Артикул", width: 160, type: "text" },
    { key: "_rating_wb", label: "Рейтинг WB", width: 110, type: "readonly" },
    { key: "_reviews_count", label: "Отзывы", width: 100, type: "readonly" },
  ],
}

const PRODUCTS_VIEWS: Record<ViewId, ColumnDef[]> = {
  spec: [
    { key: "barkod", label: "Баркод", width: 160, type: "text" },
    { key: "artikul_name", label: "Артикул", width: 160, type: "readonly" },
    { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
    { key: "status_name", label: "Статус", width: 120, type: "readonly" },
    { key: "ozon_product_id", label: "Ozon Product ID", width: 160, type: "readonly" },
    { key: "ozon_fbo_sku_id", label: "Ozon FBO SKU", width: 140, type: "readonly" },
    { key: "lamoda_seller_sku", label: "Lamoda SKU", width: 140, type: "text" },
    { key: "sku_china_size", label: "SKU China", width: 120, type: "text" },
  ],
  stock: [
    { key: "barkod", label: "Баркод", width: 160, type: "text" },
    { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
    { key: "_stock_wb", label: "WB", width: 80, type: "readonly" },
    { key: "_stock_ozon", label: "Ozon", width: 80, type: "readonly" },
    { key: "_stock_transit", label: "В пути", width: 80, type: "readonly" },
  ],
  finance: [
    { key: "barkod", label: "Баркод", width: 160, type: "text" },
    { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
    { key: "_revenue", label: "Выручка", width: 120, type: "readonly" },
    { key: "_price", label: "Цена", width: 100, type: "readonly" },
  ],
  rating: [
    { key: "barkod", label: "Баркод", width: 160, type: "text" },
    { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
  ],
}

// Entity types -> view-column mapping
// Entities without multi-view (colors, factories, etc.) only have "spec"
export type EntityType =
  | "models" | "articles" | "products" | "colors"
  | "factories" | "importers" | "cards-wb" | "cards-ozon" | "certs"

// Map entity to whether it supports multi-view tabs
export const ENTITY_HAS_VIEWS: Record<EntityType, boolean> = {
  models: true,
  articles: true,
  products: true,
  colors: false,
  factories: false,
  importers: false,
  "cards-wb": false,
  "cards-ozon": false,
  certs: false,
}

const VIEW_COLUMNS: Partial<Record<EntityType, Record<ViewId, ColumnDef[]>>> = {
  models: MODELS_VIEWS,
  articles: ARTICLES_VIEWS,
  products: PRODUCTS_VIEWS,
}

/**
 * Get columns for a built-in view tab.
 * Falls back to the entity's default "spec" columns if no view-specific config exists.
 */
export function getViewColumns(
  entity: EntityType,
  view: ViewId,
  defaultColumns: ColumnDef[],
): ColumnDef[] {
  const entityViews = VIEW_COLUMNS[entity]
  if (!entityViews) return defaultColumns
  return entityViews[view] ?? defaultColumns
}
```

- [ ] **Step 3: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd wookiee-hub && git add src/lib/view-columns.ts src/lib/matrix-api.ts src/lib/api-client.ts && git commit -m "feat(matrix): add view column configs + schema/views API methods"
```

---

## Task 6: Frontend — Views Store + ViewTabs with Saved Views

**Files:**
- Create: `wookiee-hub/src/stores/views-store.ts`
- Modify: `wookiee-hub/src/stores/matrix-store.ts`
- Modify: `wookiee-hub/src/components/matrix/view-tabs.tsx`

- [ ] **Step 1: Create views store**

Create `wookiee-hub/src/stores/views-store.ts`:

```typescript
import { create } from "zustand"
import type { SavedView } from "@/lib/matrix-api"
import { matrixApi } from "@/lib/matrix-api"

// Map frontend entity names to backend entity_type strings
const ENTITY_TYPE_MAP: Record<string, string> = {
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

interface ViewsState {
  savedViews: SavedView[]
  loading: boolean

  fetchViews: (entity: string) => Promise<void>
  addView: (entity: string, name: string, columns: string[]) => Promise<SavedView>
  removeView: (viewId: number, entity: string) => Promise<void>
}

export const useViewsStore = create<ViewsState>((set, get) => ({
  savedViews: [],
  loading: false,

  fetchViews: async (entity) => {
    const entityType = ENTITY_TYPE_MAP[entity]
    if (!entityType) return
    set({ loading: true })
    try {
      const views = await matrixApi.listViews(entityType)
      set({ savedViews: views })
    } catch {
      set({ savedViews: [] })
    } finally {
      set({ loading: false })
    }
  },

  addView: async (entity, name, columns) => {
    const entityType = ENTITY_TYPE_MAP[entity]!
    const view = await matrixApi.createView({
      entity_type: entityType,
      name,
      config: { columns, filters: [], sort: [] },
    })
    set((s) => ({ savedViews: [...s.savedViews, view] }))
    return view
  },

  removeView: async (viewId, entity) => {
    await matrixApi.deleteView(viewId)
    set((s) => ({ savedViews: s.savedViews.filter((v) => v.id !== viewId) }))
  },
}))
```

- [ ] **Step 2: Update matrix-store.ts**

Change `ViewTab` type in `wookiee-hub/src/stores/matrix-store.ts`:

```typescript
// Allow both built-in views and saved view IDs (prefixed with "saved-")
export type ViewTab = "spec" | "stock" | "finance" | "rating" | `saved-${number}`
```

- [ ] **Step 3: Upgrade ViewTabs component**

Replace `wookiee-hub/src/components/matrix/view-tabs.tsx`:

```typescript
import { useEffect } from "react"
import { Plus, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMatrixStore, type ViewTab } from "@/stores/matrix-store"
import { useViewsStore } from "@/stores/views-store"
import { ENTITY_HAS_VIEWS } from "@/lib/view-columns"

const BUILT_IN_TABS: { id: ViewTab; label: string }[] = [
  { id: "spec", label: "Спецификация" },
  { id: "stock", label: "Склад" },
  { id: "finance", label: "Финансы" },
  { id: "rating", label: "Рейтинг" },
]

export function ViewTabs() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const activeView = useMatrixStore((s) => s.activeView)
  const setActiveView = useMatrixStore((s) => s.setActiveView)

  const { savedViews, fetchViews, addView, removeView } = useViewsStore()

  useEffect(() => {
    fetchViews(activeEntity)
  }, [activeEntity, fetchViews])

  // Only show built-in multi-view tabs for entities that support it
  const showBuiltIn = ENTITY_HAS_VIEWS[activeEntity] ?? false

  const handleAddView = async () => {
    const name = prompt("Название вида:")
    if (!name?.trim()) return
    const view = await addView(activeEntity, name.trim(), [])
    setActiveView(`saved-${view.id}`)
  }

  const handleRemoveView = async (e: React.MouseEvent, viewId: number) => {
    e.stopPropagation()
    await removeView(viewId, activeEntity)
    setActiveView("spec")
  }

  return (
    <div className="flex items-center gap-1 border-b border-border">
      {showBuiltIn &&
        BUILT_IN_TABS.map((tab) => (
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

      {savedViews.map((view) => {
        const tabId: ViewTab = `saved-${view.id}`
        return (
          <button
            key={view.id}
            onClick={() => setActiveView(tabId)}
            className={cn(
              "group flex items-center gap-1 px-3 py-1.5 text-sm transition-colors",
              activeView === tabId
                ? "border-b-2 border-primary font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {view.name}
            <X
              className="h-3 w-3 opacity-0 group-hover:opacity-60 hover:opacity-100"
              onClick={(e) => handleRemoveView(e, view.id)}
            />
          </button>
        )
      })}

      <button
        onClick={handleAddView}
        className="ml-1 rounded p-1 text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        title="Создать вид"
      >
        <Plus className="h-4 w-4" />
      </button>
    </div>
  )
}
```

- [ ] **Step 4: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd wookiee-hub && git add src/stores/views-store.ts src/stores/matrix-store.ts src/components/matrix/view-tabs.tsx && git commit -m "feat(matrix): ViewTabs with saved views + views store"
```

---

## Task 7: Frontend — View-Aware Entity Pages

**Files:**
- Modify: `wookiee-hub/src/pages/product-matrix/models-page.tsx`
- Modify: `wookiee-hub/src/pages/product-matrix/articles-page.tsx`
- Modify: `wookiee-hub/src/pages/product-matrix/products-page.tsx`
- Modify: all other entity pages (minimal — just ensure ViewTabs shows/hides correctly)

- [ ] **Step 1: Update ModelsPage to use view-aware columns**

Modify `wookiee-hub/src/pages/product-matrix/models-page.tsx`:

```typescript
import { useCallback, useEffect, useState } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { getViewColumns } from "@/lib/view-columns"

const defaultColumns: Column<ModelOsnova>[] = [
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
  const activeView = useMatrixStore((s) => s.activeView)
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

  // Pick columns based on active view
  const builtInView = activeView.startsWith("saved-") ? "spec" : activeView
  const columns = getViewColumns("models", builtInView as "spec" | "stock" | "finance" | "rating", defaultColumns)

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

- [ ] **Step 2: Update ArticlesPage similarly**

Same pattern: import `getViewColumns`, use `activeView` from store, call `getViewColumns("articles", ...)`.

- [ ] **Step 3: Update ProductsPage similarly**

Same pattern with `getViewColumns("products", ...)`.

- [ ] **Step 4: Ensure other pages don't show ViewTabs**

For entities where `ENTITY_HAS_VIEWS[entity] === false` (colors, factories, importers, cards-wb, cards-ozon, certs), the ViewTabs component already handles this — it hides built-in tabs. But these pages should still render `<ViewTabs />` to show saved views.

Add `<ViewTabs />` to each entity page that doesn't already have it (colors, factories, importers, cards-wb, cards-ozon, certs pages).

- [ ] **Step 5: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
cd wookiee-hub && git add -A && git commit -m "feat(matrix): view-aware columns for models/articles/products + ViewTabs on all pages"
```

---

## Task 8: Frontend — Manage Fields Dialog

**Files:**
- Create: `wookiee-hub/src/components/matrix/manage-fields-dialog.tsx`
- Modify: `wookiee-hub/src/components/matrix/matrix-topbar.tsx`

- [ ] **Step 1: Create ManageFieldsDialog**

Create `wookiee-hub/src/components/matrix/manage-fields-dialog.tsx`:

```typescript
import { useEffect, useState } from "react"
import { Plus, GripVertical, Trash2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { matrixApi, type FieldDefinition } from "@/lib/matrix-api"

// Map frontend entity names to backend entity_type strings
const ENTITY_TYPE_MAP: Record<string, string> = {
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

const FIELD_TYPES = [
  { value: "text", label: "Текст" },
  { value: "number", label: "Число" },
  { value: "select", label: "Выбор" },
  { value: "multi_select", label: "Мульти-выбор" },
  { value: "checkbox", label: "Чекбокс" },
  { value: "date", label: "Дата" },
  { value: "url", label: "URL" },
  { value: "file", label: "Файл" },
]

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  entity: string
}

export function ManageFieldsDialog({ open, onOpenChange, entity }: Props) {
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(false)

  // New field form
  const [newName, setNewName] = useState("")
  const [newDisplayName, setNewDisplayName] = useState("")
  const [newType, setNewType] = useState("text")

  const entityType = ENTITY_TYPE_MAP[entity] ?? entity

  useEffect(() => {
    if (open) {
      setLoading(true)
      matrixApi
        .listFields(entityType)
        .then(setFields)
        .finally(() => setLoading(false))
    }
  }, [open, entityType])

  const handleAdd = async () => {
    if (!newName.trim() || !newDisplayName.trim()) return
    const field = await matrixApi.createField(entityType, {
      entity_type: entityType,
      field_name: newName.trim().toLowerCase().replace(/\s+/g, "_"),
      display_name: newDisplayName.trim(),
      field_type: newType,
    })
    setFields((prev) => [...prev, field])
    setNewName("")
    setNewDisplayName("")
    setNewType("text")
  }

  const handleDelete = async (fieldId: number) => {
    await matrixApi.deleteField(entityType, fieldId)
    setFields((prev) => prev.filter((f) => f.id !== fieldId))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Настроить поля</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-muted-foreground">Загрузка...</div>
        ) : (
          <div className="space-y-3">
            {/* Existing fields */}
            <div className="max-h-64 space-y-1 overflow-y-auto">
              {fields.map((field) => (
                <div
                  key={field.id}
                  className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-accent/20"
                >
                  <GripVertical className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1 text-sm">{field.display_name}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                    {field.field_type}
                  </span>
                  {!field.is_system && (
                    <button
                      onClick={() => handleDelete(field.id)}
                      className="rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
              {fields.length === 0 && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  Нет кастомных полей
                </div>
              )}
            </div>

            {/* Add new field */}
            <div className="border-t border-border pt-3">
              <div className="mb-2 text-xs font-medium text-muted-foreground">
                Добавить поле
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder="field_name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-28 text-sm"
                />
                <Input
                  placeholder="Отображаемое имя"
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  className="flex-1 text-sm"
                />
                <Select value={newType} onValueChange={setNewType}>
                  <SelectTrigger className="w-28 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FIELD_TYPES.map((ft) => (
                      <SelectItem key={ft.value} value={ft.value}>
                        {ft.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button size="sm" onClick={handleAdd} disabled={!newName || !newDisplayName}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Add "Настроить поля" button to MatrixTopbar**

Modify `wookiee-hub/src/components/matrix/matrix-topbar.tsx`:
- Import `ManageFieldsDialog` and `useState`
- Add state: `const [fieldsOpen, setFieldsOpen] = useState(false)`
- Add button: `<button onClick={() => setFieldsOpen(true)}>Настроить поля</button>`
- Render: `<ManageFieldsDialog open={fieldsOpen} onOpenChange={setFieldsOpen} entity={activeEntity} />`

- [ ] **Step 3: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd wookiee-hub && git add src/components/matrix/manage-fields-dialog.tsx src/components/matrix/matrix-topbar.tsx && git commit -m "feat(matrix): manage fields dialog + topbar button"
```

---

## Task 9: Frontend — Save View Dialog

**Files:**
- Create: `wookiee-hub/src/components/matrix/save-view-dialog.tsx`

- [ ] **Step 1: Create SaveViewDialog**

Create `wookiee-hub/src/components/matrix/save-view-dialog.tsx`:

```typescript
import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useMatrixStore } from "@/stores/matrix-store"
import { useViewsStore } from "@/stores/views-store"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentColumns: string[]
}

export function SaveViewDialog({ open, onOpenChange, currentColumns }: Props) {
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setActiveView = useMatrixStore((s) => s.setActiveView)
  const addView = useViewsStore((s) => s.addView)

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      const view = await addView(activeEntity, name.trim(), currentColumns)
      setActiveView(`saved-${view.id}`)
      onOpenChange(false)
      setName("")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Сохранить вид</DialogTitle>
        </DialogHeader>
        <Input
          placeholder="Название вида..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          autoFocus
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={!name.trim() || saving}>
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: TypeScript check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd wookiee-hub && git add src/components/matrix/save-view-dialog.tsx && git commit -m "feat(matrix): save view dialog component"
```

---

## Task 10: Full Backend + Frontend Verification

- [ ] **Step 1: Run full backend test suite**

Run: `python3 -m pytest tests/product_matrix_api/ -v`
Expected: All tests PASS (existing 54 + new ~25 = ~79 tests)

- [ ] **Step 2: TypeScript full check**

Run: `cd wookiee-hub && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Verify no regressions in existing tests**

Run: `python3 -m pytest tests/product_matrix_api/test_integration.py tests/product_matrix_api/test_integration_phase3.py -v`
Expected: All existing integration tests still pass

- [ ] **Step 4: Final commit (if any unstaged changes)**

```bash
git status
cd wookiee-hub && git status
```

Review and commit any remaining changes.

---

## Summary

| Task | What | Backend/Frontend | Tests |
|------|------|-----------------|-------|
| 1 | HubSavedView ORM + Pydantic schemas | Backend | 10 |
| 2 | FieldService — custom field validation | Backend | 14 |
| 3 | Schema routes — field definitions CRUD | Backend | 6 |
| 4 | Views routes — saved views CRUD | Backend | 5 |
| 5 | View column configs + API methods | Frontend | TypeScript |
| 6 | Views store + ViewTabs upgrade | Frontend | TypeScript |
| 7 | View-aware entity pages | Frontend | TypeScript |
| 8 | Manage fields dialog | Frontend | TypeScript |
| 9 | Save view dialog | Frontend | TypeScript |
| 10 | Full verification | Both | All |

**Total new tests:** ~35 backend + TypeScript compilation
**Total new files:** 8 (4 backend, 4 frontend)
**Total modified files:** ~16 (4 backend, ~12 frontend)
