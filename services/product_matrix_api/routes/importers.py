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
