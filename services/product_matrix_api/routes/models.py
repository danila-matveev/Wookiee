"""CRUD routes for modeli_osnova and modeli."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
    parse_multi_param,
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
    kategoriya_id: Optional[str] = Query(None),
    kollekciya_id: Optional[str] = Query(None),
    status_id: Optional[str] = Query(None),
    fabrika_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}
    parsed_kategoriya = parse_multi_param(kategoriya_id)
    if parsed_kategoriya is not None:
        filters["kategoriya_id"] = parsed_kategoriya
    parsed_kollekciya = parse_multi_param(kollekciya_id)
    if parsed_kollekciya is not None:
        filters["kollekciya_id"] = parsed_kollekciya
    parsed_status = parse_multi_param(status_id)
    if parsed_status is not None:
        filters["status_id"] = parsed_status
    parsed_fabrika = parse_multi_param(fabrika_id)
    if parsed_fabrika is not None:
        filters["fabrika_id"] = parsed_fabrika

    sort_param = f"{params.sort}:{params.order or 'asc'}" if params.sort else None
    items, total = CrudService.get_list(
        db, ModelOsnova,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=sort_param,
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
