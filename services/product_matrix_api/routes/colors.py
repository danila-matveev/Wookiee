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
