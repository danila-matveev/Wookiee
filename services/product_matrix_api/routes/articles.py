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
