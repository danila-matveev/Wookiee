"""Global cross-entity search for the product matrix."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import SearchResult, SearchResponse

from sku_database.database.models import (
    ModelOsnova, Model, Artikul, Tovar, Cvet, Fabrika, Importer,
    SleykaWB, SleykaOzon,
)
from services.product_matrix_api.models.database import Sertifikat

router = APIRouter(prefix="/api/matrix/search", tags=["search"])

# Define search config: (ORM model, entity_name, searchable fields, name field)
SEARCH_CONFIG = [
    (ModelOsnova, "modeli_osnova", ["kod", "nazvanie_sayt", "material"], "kod"),
    (Model, "modeli", ["kod", "nazvanie", "artikul_modeli"], "kod"),
    (Artikul, "artikuly", ["artikul", "artikul_ozon"], "artikul"),
    (Tovar, "tovary", ["barkod", "barkod_gs1", "lamoda_seller_sku", "sku_china_size"], "barkod"),
    (Cvet, "cveta", ["color_code", "cvet", "color"], "color_code"),
    (Fabrika, "fabriki", ["nazvanie"], "nazvanie"),
    (Importer, "importery", ["nazvanie", "nazvanie_en", "inn"], "nazvanie"),
    (SleykaWB, "skleyki_wb", ["nazvanie"], "nazvanie"),
    (SleykaOzon, "skleyki_ozon", ["nazvanie"], "nazvanie"),
    (Sertifikat, "sertifikaty", ["nazvanie", "nomer", "tip"], "nazvanie"),
]


@router.get("", response_model=SearchResponse)
def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    results: list[SearchResult] = []
    by_entity: dict[str, int] = {}
    pattern = f"%{q}%"

    for orm_model, entity_name, fields, name_field in SEARCH_CONFIG:
        # Build ILIKE conditions for each searchable field
        conditions = []
        for field_name in fields:
            col = getattr(orm_model, field_name, None)
            if col is not None:
                conditions.append(cast(col, String).ilike(pattern))

        if not conditions:
            continue

        rows = db.query(orm_model).filter(or_(*conditions)).limit(limit).all()
        by_entity[entity_name] = len(rows)

        for row in rows:
            name_val = str(getattr(row, name_field, ""))
            # Find which field matched
            match_field = name_field
            match_text = name_val
            for field_name in fields:
                val = getattr(row, field_name, None)
                if val and q.lower() in str(val).lower():
                    match_field = field_name
                    match_text = str(val)
                    break

            results.append(SearchResult(
                entity=entity_name,
                id=row.id,
                name=name_val,
                match_field=match_field,
                match_text=match_text,
            ))

    # Sort by relevance: exact matches first, then partial
    results.sort(key=lambda r: (0 if q.lower() == r.match_text.lower() else 1, r.entity, r.name))

    total = sum(by_entity.values())
    return SearchResponse(
        results=results[:limit],
        total=total,
        by_entity=by_entity,
    )
