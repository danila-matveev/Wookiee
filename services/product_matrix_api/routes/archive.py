"""Archive CRUD routes — list, restore, hard-delete archived records."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.database import ArchiveRecord
from services.product_matrix_api.models.schemas import ArchiveRecordRead, PaginatedResponse
from services.product_matrix_api.services.archive_service import ArchiveService
from services.product_matrix_api.services.audit_service import AuditService

router = APIRouter(prefix="/api/matrix/archive", tags=["archive"])


@router.get("", response_model=PaginatedResponse)
def list_archive(
    entity_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List archived records with optional entity_type filter."""
    query = select(ArchiveRecord)
    count_query = select(func.count()).select_from(ArchiveRecord)

    if entity_type:
        query = query.where(ArchiveRecord.original_table == entity_type)
        count_query = count_query.where(ArchiveRecord.original_table == entity_type)

    query = query.order_by(ArchiveRecord.deleted_at.desc())

    total = db.execute(count_query).scalar() or 0
    offset = (page - 1) * per_page
    items = list(db.execute(query.offset(offset).limit(per_page)).scalars().all())
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    return PaginatedResponse(
        items=[ArchiveRecordRead.model_validate(a) for a in items],
        total=total, page=page, per_page=per_page, pages=pages,
    )


@router.post("/{archive_id}/restore")
def restore_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Restore an archived record and its children."""
    try:
        result = ArchiveService.restore_record(db, archive_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    AuditService.log(
        db,
        action="restore",
        entity_type=result["table"],
        entity_id=result["id"],
        user_email=user.email,
    )
    db.commit()
    return result


@router.delete("/{archive_id}")
def hard_delete_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Permanently delete an archived record (admin only)."""
    try:
        result = ArchiveService.hard_delete_archived(db, archive_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    AuditService.log(
        db,
        action="delete",
        entity_type=result["table"],
        entity_id=result["id"],
        changes={"hard_delete": True},
        user_email=user.email,
    )
    db.commit()
    return result
