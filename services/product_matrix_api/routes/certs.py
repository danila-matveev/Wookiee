"""CRUD routes for sertifikaty (certificates)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user, common_params, CommonQueryParams,
)
from services.product_matrix_api.models.schemas import (
    SertifikatCreate, SertifikatUpdate, SertifikatRead, PaginatedResponse,
)
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/certs", tags=["certs"])


@router.get("", response_model=PaginatedResponse)
def list_certs(
    params: CommonQueryParams = Depends(common_params),
    db: Session = Depends(get_db),
):
    items, total = CrudService.get_list(
        db, Sertifikat, page=params.page, per_page=params.per_page, sort=params.sort,
    )
    per_page = params.per_page
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return PaginatedResponse(
        items=[SertifikatRead.model_validate(item) for item in items],
        total=total, page=params.page, per_page=per_page, pages=pages,
    )


@router.get("/{cert_id}", response_model=SertifikatRead)
def get_cert(cert_id: int, db: Session = Depends(get_db)):
    item = CrudService.get_by_id(db, Sertifikat, cert_id)
    if not item:
        raise HTTPException(404, "Certificate not found")
    return SertifikatRead.model_validate(item)


@router.post("", response_model=SertifikatRead, status_code=201)
def create_cert(
    body: SertifikatCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.create(db, Sertifikat, body.model_dump(exclude_none=True))
    AuditService.log(
        db, action="create", entity_type="sertifikaty",
        entity_id=item.id, entity_name=item.nazvanie, user_email=user.email,
    )
    db.commit()
    return SertifikatRead.model_validate(item)


@router.patch("/{cert_id}", response_model=SertifikatRead)
def update_cert(
    cert_id: int,
    body: SertifikatUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    item = CrudService.get_by_id(db, Sertifikat, cert_id)
    if not item:
        raise HTTPException(404, "Certificate not found")

    old_data = CrudService.to_dict(item)
    item = CrudService.update(db, item, body.model_dump(exclude_none=True))

    changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
    if changes:
        AuditService.log(
            db, action="update", entity_type="sertifikaty",
            entity_id=item.id, entity_name=item.nazvanie,
            changes=changes, user_email=user.email,
        )
    db.commit()
    return SertifikatRead.model_validate(item)
