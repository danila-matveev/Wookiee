"""External marketplace data routes: stock and finance for matrix entities."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from services.product_matrix_api.config import get_db
from services.product_matrix_api.models.schemas import StockResponse, FinanceResponse
from services.product_matrix_api.services.external_data import (
    ExternalDataService, ENTITIES_WITH_MP_DATA,
)

router = APIRouter(prefix="/api/matrix", tags=["external_data"])


@router.get("/{entity}/{entity_id}/stock", response_model=StockResponse)
def get_entity_stock(
    entity: str,
    entity_id: int,
    period: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get stock/inventory data for a matrix entity."""
    if entity not in ENTITIES_WITH_MP_DATA:
        raise HTTPException(status_code=404, detail=f"Entity '{entity}' has no marketplace data")
    try:
        return ExternalDataService.get_stock(entity, entity_id, period, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/{entity}/{entity_id}/finance", response_model=FinanceResponse)
def get_entity_finance(
    entity: str,
    entity_id: int,
    period: int = Query(7, ge=1, le=365),
    compare: str = Query("week", pattern="^(none|week|month)$"),
    db: Session = Depends(get_db),
):
    """Get unit-economics data for a matrix entity."""
    if entity not in ENTITIES_WITH_MP_DATA:
        raise HTTPException(status_code=404, detail=f"Entity '{entity}' has no marketplace data")
    try:
        return ExternalDataService.get_finance(entity, entity_id, period, compare, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
