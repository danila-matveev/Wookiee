"""Two-step delete route: 428 challenge → archive on confirmation."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.dependencies import CurrentUser, get_current_user
from services.product_matrix_api.models.schemas import VALID_ENTITY_TYPES
from services.product_matrix_api.services.validation import ValidationService
from services.product_matrix_api.services.archive_service import ArchiveService
from services.product_matrix_api.services.audit_service import AuditService

logger = logging.getLogger("product_matrix_api.routes.delete")

router = APIRouter(prefix="/api/matrix", tags=["delete"])

# Name fields per entity (for display)
ENTITY_NAME_FIELDS: dict[str, str] = {
    "modeli_osnova": "kod",
    "modeli": "kod",
    "artikuly": "artikul",
    "tovary": "barkod",
    "cveta": "color_code",
    "fabriki": "nazvanie",
    "importery": "nazvanie",
    "skleyki_wb": "nazvanie",
    "skleyki_ozon": "nazvanie",
    "sertifikaty": "nazvanie",
}


@router.delete("/{entity_type}/{entity_id}")
def delete_entity(
    entity_type: str,
    entity_id: int,
    x_confirm_challenge: Optional[str] = Header(None),
    x_challenge_hash: Optional[str] = Header(None),
    x_challenge_salt: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Two-step delete: first call returns 428 with challenge, second with answer archives."""
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(404, f"Unknown entity type: {entity_type}")

    # Check record exists
    row = db.execute(
        text(f"SELECT * FROM {entity_type} WHERE id = :eid"),
        {"eid": entity_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, f"{entity_type}#{entity_id} not found")

    name_field = ENTITY_NAME_FIELDS.get(entity_type, "id")
    entity_name = str(dict(row).get(name_field, entity_id))

    # Check impact
    impact_data = ValidationService.check_delete_impact(db, entity_type, entity_id)
    strategy = impact_data["strategy"]
    children = impact_data["children"]
    blocked_by = impact_data["blocked_by"]

    # Block if active dependents
    if strategy == "block_if_active" and blocked_by:
        message = ArchiveService.build_impact_message(strategy, children, blocked_by)
        return JSONResponse(status_code=409, content={
            "error": "blocked",
            "impact": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "strategy": strategy,
                "children": children,
                "blocked_by": blocked_by,
                "message": message,
            },
        })

    # Step 1: No challenge header → return 428 with challenge
    if not x_confirm_challenge:
        message = ArchiveService.build_impact_message(strategy, children, blocked_by)
        challenge_text, expected_hash, salt = ValidationService.generate_challenge()

        return JSONResponse(status_code=428, content={
            "requires_confirmation": True,
            "challenge": challenge_text,
            "expected_hash": expected_hash,
            "salt": salt,
            "impact": {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "entity_name": entity_name,
                "strategy": strategy,
                "children": children,
                "blocked_by": blocked_by,
                "message": message,
            },
        })

    # Step 2: Verify challenge answer
    if not x_challenge_hash or not x_challenge_salt:
        raise HTTPException(400, "Missing X-Challenge-Hash or X-Challenge-Salt headers")

    if not ValidationService.verify_challenge(x_confirm_challenge, x_challenge_hash, x_challenge_salt):
        raise HTTPException(403, "Incorrect challenge answer")

    # Archive the record
    archive = ArchiveService.archive_entity(db, entity_type, entity_id, deleted_by=user.email)

    AuditService.log(
        db,
        action="delete",
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        changes={"archived": True, "children": children},
        user_email=user.email,
    )
    db.commit()

    return {
        "archived": True,
        "archive_id": archive.id,
        "expires_at": archive.expires_at.isoformat() if archive.expires_at else None,
    }
