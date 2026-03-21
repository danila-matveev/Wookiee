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
