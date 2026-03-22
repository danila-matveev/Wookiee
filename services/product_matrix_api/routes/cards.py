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
