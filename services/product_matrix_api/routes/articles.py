"""CRUD routes for artikuly (articles = model + color)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
    parse_multi_param,
)
from services.product_matrix_api.models.schemas import (
    ArtikulCreate, ArtikulUpdate, ArtikulRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import Artikul, Model


def get_model_ids_for_osnova(db: Session, model_osnova_id: int) -> list[int]:
    """Return list of modeli.id that belong to the given modeli_osnova."""
    rows = db.execute(
        select(Model.id).where(Model.model_osnova_id == model_osnova_id)
    ).all()
    return [row[0] for row in rows]

router = APIRouter(prefix="/api/matrix/articles", tags=["articles"])


@router.get("", response_model=PaginatedResponse)
def list_articles(
    params: CommonQueryParams = Depends(common_params),
    model_id: Optional[str] = Query(None),
    cvet_id: Optional[str] = Query(None),
    status_id: Optional[str] = Query(None),
    model_osnova_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    filters = {}

    # model_osnova_id drill-down: resolve child model IDs via subquery
    if model_osnova_id is not None:
        child_model_ids = get_model_ids_for_osnova(db, model_osnova_id)
        if not child_model_ids:
            # No child models -> return empty response immediately
            per_page = params.per_page
            return PaginatedResponse(
                items=[], total=0, page=params.page,
                per_page=per_page, pages=0,
            )
        filters["model_id"] = child_model_ids
    else:
        parsed_model_id = parse_multi_param(model_id)
        if parsed_model_id is not None:
            filters["model_id"] = parsed_model_id

    parsed_cvet = parse_multi_param(cvet_id)
    if parsed_cvet is not None:
        filters["cvet_id"] = parsed_cvet

    parsed_status = parse_multi_param(status_id)
    if parsed_status is not None:
        filters["status_id"] = parsed_status

    sort_param = f"{params.sort}:{params.order or 'asc'}" if params.sort else None
    items, total = CrudService.get_list(
        db, Artikul,
        page=params.page, per_page=params.per_page,
        filters=filters, sort=sort_param,
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
