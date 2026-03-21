"""Bulk operations (mass update/delete) for any entity."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.schemas import BulkActionRequest
from services.product_matrix_api.services.crud import CrudService
from services.product_matrix_api.services.audit_service import AuditService

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, Cvet, Fabrika, Importer,
    SleykaWB, SleykaOzon,
)
from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/bulk", tags=["bulk"])

ENTITY_MAP = {
    "modeli_osnova": (ModelOsnova, "kod"),
    "modeli": (Model, "kod"),
    "artikuly": (Artikul, "artikul"),
    "tovary": (Tovar, "barkod"),
    "cveta": (Cvet, "color_code"),
    "fabriki": (Fabrika, "nazvanie"),
    "importery": (Importer, "nazvanie"),
    "skleyki_wb": (SleykaWB, "nazvanie"),
    "skleyki_ozon": (SleykaOzon, "nazvanie"),
    "sertifikaty": (Sertifikat, "nazvanie"),
}


@router.post("/{entity_type}")
def bulk_action(
    entity_type: str,
    body: BulkActionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if entity_type not in ENTITY_MAP:
        raise HTTPException(404, f"Unknown entity type: {entity_type}")

    orm_model, name_field = ENTITY_MAP[entity_type]
    updated = 0
    errors = []

    for record_id in body.ids:
        item = CrudService.get_by_id(db, orm_model, record_id)
        if not item:
            errors.append({"id": record_id, "error": "not found"})
            continue

        if body.action == "update" and body.changes:
            old_data = CrudService.to_dict(item)
            CrudService.update(db, item, body.changes)
            changes = AuditService.diff_changes(old_data, CrudService.to_dict(item))
            if changes:
                AuditService.log(
                    db, action="bulk_update", entity_type=entity_type,
                    entity_id=item.id,
                    entity_name=str(getattr(item, name_field, "")),
                    changes=changes, user_email=user.email,
                )
            updated += 1
        else:
            errors.append({"id": record_id, "error": f"unsupported action: {body.action}"})

    db.commit()
    return {"updated": updated, "errors": errors}
