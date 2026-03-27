"""Lookup routes — reference tables for dropdown selectors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import LookupItem
from sku_database.database.models import (
    Kategoriya, Kollekciya, Status, Razmer, Importer, Fabrika, Cvet,
)

router = APIRouter(prefix="/api/matrix/lookups", tags=["lookups"])

LOOKUP_MAP = {
    "kategorii": Kategoriya,
    "kollekcii": Kollekciya,
    "statusy": Status,
    "razmery": Razmer,
    "importery": Importer,
    "fabriki": Fabrika,
    "cveta": Cvet,
}


@router.get("/{table_name}", response_model=list[LookupItem])
def get_lookup(table_name: str, db: Session = Depends(get_db)):
    model = LOOKUP_MAP.get(table_name)
    if not model:
        raise HTTPException(404, f"Unknown lookup table: {table_name}")
    items = db.query(model).order_by(model.nazvanie).all()
    return [LookupItem.model_validate(item) for item in items]
