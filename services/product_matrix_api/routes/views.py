"""CRUD routes for saved views."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.schemas import (
    VALID_ENTITY_TYPES,
    SavedViewCreate,
    SavedViewUpdate,
    SavedViewRead,
)
from services.product_matrix_api.models.database import HubSavedView
from services.product_matrix_api.services.audit_service import AuditService

logger = logging.getLogger("product_matrix_api.routes.views")

router = APIRouter(prefix="/api/matrix/views", tags=["views"])


@router.get("", response_model=list[SavedViewRead])
def list_views(
    entity_type: str = Query(..., description="Entity type to filter views"),
    db: Session = Depends(get_db),
):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(422, f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}")

    views = (
        db.query(HubSavedView)
        .filter(HubSavedView.entity_type == entity_type)
        .order_by(HubSavedView.sort_order, HubSavedView.id)
        .all()
    )
    return [SavedViewRead.model_validate(v) for v in views]


@router.post("", response_model=SavedViewRead, status_code=201)
def create_view(
    body: SavedViewCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = HubSavedView(
        user_id=user.id if user.id != 0 else None,
        entity_type=body.entity_type,
        name=body.name,
        config=body.config,
        is_default=body.is_default,
        sort_order=body.sort_order,
    )
    db.add(view)
    db.flush()

    AuditService.log(
        db,
        action="create",
        entity_type="saved_views",
        entity_id=view.id,
        entity_name=view.name,
        user_email=user.email,
    )
    db.commit()
    db.refresh(view)
    return SavedViewRead.model_validate(view)


@router.patch("/{view_id}", response_model=SavedViewRead)
def update_view(
    view_id: int,
    body: SavedViewUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = db.query(HubSavedView).filter(HubSavedView.id == view_id).first()
    if not view:
        raise HTTPException(404, "View not found")

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(view, field, value)

    AuditService.log(
        db,
        action="update",
        entity_type="saved_views",
        entity_id=view.id,
        entity_name=view.name,
        changes=update_data,
        user_email=user.email,
    )
    db.commit()
    db.refresh(view)
    return SavedViewRead.model_validate(view)


@router.delete("/{view_id}", status_code=204)
def delete_view(
    view_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    view = db.query(HubSavedView).filter(HubSavedView.id == view_id).first()
    if not view:
        raise HTTPException(404, "View not found")

    view_name = view.name
    view_id_val = view.id
    db.delete(view)

    AuditService.log(
        db,
        action="delete",
        entity_type="saved_views",
        entity_id=view_id_val,
        entity_name=view_name,
        user_email=user.email,
    )
    db.commit()
    return Response(status_code=204)
