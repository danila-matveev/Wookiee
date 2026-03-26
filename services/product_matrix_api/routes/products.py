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

    sort_param = f"{params.sort}:{params.order or 'asc'}" if params.sort else None
    items, total = CrudService.get_list(
        db, Tovar,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=sort_param,
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
