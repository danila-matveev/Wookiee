"""GET /products + GET /products/{model_osnova_id}."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from services.influencer_crm.deps import get_session, verify_api_key
from services.influencer_crm.pagination import Page
from services.influencer_crm.schemas.product import ProductDetailOut, ProductSliceOut
from shared.data_layer.influencer_crm import products as repo

router = APIRouter(
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("", response_model=Page[ProductSliceOut])
def list_products(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> Page[ProductSliceOut]:
    items, next_cursor = repo.list_products(session, limit=limit, cursor=cursor)
    return Page[ProductSliceOut](items=items, next_cursor=next_cursor)


@router.get("/{model_osnova_id}", response_model=ProductDetailOut)
def get_product(
    model_osnova_id: int,
    session: Session = Depends(get_session),
) -> ProductDetailOut:
    detail = repo.get_product(session, model_osnova_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    return detail
