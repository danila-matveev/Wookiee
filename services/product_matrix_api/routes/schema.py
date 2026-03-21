"""CRUD routes for field definitions (schema management)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import (
    CurrentUser, get_current_user,
)
from services.product_matrix_api.models.schemas import (
    VALID_ENTITY_TYPES,
    FieldDefinitionCreate,
    FieldDefinitionUpdate,
    FieldDefinitionRead,
)
from services.product_matrix_api.models.database import FieldDefinition
from services.product_matrix_api.services.audit_service import AuditService

router = APIRouter(prefix="/api/matrix/schema", tags=["schema"])

MAX_FIELDS_PER_ENTITY = 50


def _validate_entity(entity_type: str) -> None:
    """Raise 422 if entity_type is not in VALID_ENTITY_TYPES."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"entity_type must be one of {sorted(VALID_ENTITY_TYPES)}, got '{entity_type}'",
        )


@router.get("/{entity_type}", response_model=list[FieldDefinitionRead])
def list_fields(
    entity_type: str,
    db: Session = Depends(get_db),
):
    """List field definitions for an entity type, ordered by sort_order, id."""
    _validate_entity(entity_type)
    query = (
        select(FieldDefinition)
        .where(FieldDefinition.entity_type == entity_type)
        .order_by(FieldDefinition.sort_order, FieldDefinition.id)
    )
    items = list(db.execute(query).scalars().all())
    return [FieldDefinitionRead.model_validate(item) for item in items]


@router.post("/{entity_type}/fields", response_model=FieldDefinitionRead, status_code=201)
def create_field(
    entity_type: str,
    body: FieldDefinitionCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new field definition."""
    _validate_entity(entity_type)

    # Ensure body entity_type matches URL
    if body.entity_type != entity_type:
        raise HTTPException(
            status_code=422,
            detail=f"Body entity_type '{body.entity_type}' does not match URL entity_type '{entity_type}'",
        )

    # Check uniqueness (entity_type + field_name)
    existing = db.execute(
        select(FieldDefinition).where(
            FieldDefinition.entity_type == entity_type,
            FieldDefinition.field_name == body.field_name,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Field '{body.field_name}' already exists for entity '{entity_type}'",
        )

    # Check max 50 fields per entity
    count = db.execute(
        select(func.count()).select_from(FieldDefinition).where(
            FieldDefinition.entity_type == entity_type,
        )
    ).scalar() or 0
    if count >= MAX_FIELDS_PER_ENTITY:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {MAX_FIELDS_PER_ENTITY} fields per entity type reached",
        )

    item = FieldDefinition(**body.model_dump(exclude_none=True))
    db.add(item)
    db.flush()
    db.refresh(item)

    AuditService.log(
        db,
        action="create",
        entity_type="field_definitions",
        entity_id=item.id,
        entity_name=f"{entity_type}.{item.field_name}",
        user_email=user.email,
    )
    db.commit()
    return FieldDefinitionRead.model_validate(item)


@router.patch("/{entity_type}/fields/{field_id}", response_model=FieldDefinitionRead)
def update_field(
    entity_type: str,
    field_id: int,
    body: FieldDefinitionUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Update an existing field definition."""
    _validate_entity(entity_type)

    item = db.get(FieldDefinition, field_id)
    if not item or item.entity_type != entity_type:
        raise HTTPException(404, "Field definition not found")

    if item.is_system:
        raise HTTPException(403, "Cannot modify system field")

    old_data = {c.key: getattr(item, c.key) for c in FieldDefinition.__table__.columns}
    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    db.flush()
    db.refresh(item)

    new_data = {c.key: getattr(item, c.key) for c in FieldDefinition.__table__.columns}
    changes = AuditService.diff_changes(old_data, new_data)
    if changes:
        AuditService.log(
            db,
            action="update",
            entity_type="field_definitions",
            entity_id=item.id,
            entity_name=f"{entity_type}.{item.field_name}",
            changes=changes,
            user_email=user.email,
        )
    db.commit()
    return FieldDefinitionRead.model_validate(item)


@router.delete("/{entity_type}/fields/{field_id}", status_code=204)
def delete_field(
    entity_type: str,
    field_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Delete a field definition."""
    _validate_entity(entity_type)

    item = db.get(FieldDefinition, field_id)
    if not item or item.entity_type != entity_type:
        raise HTTPException(404, "Field definition not found")

    if item.is_system:
        raise HTTPException(403, "Cannot delete system field")

    field_name = item.field_name
    db.delete(item)

    AuditService.log(
        db,
        action="delete",
        entity_type="field_definitions",
        entity_id=field_id,
        entity_name=f"{entity_type}.{field_name}",
        user_email=user.email,
    )
    db.commit()
