"""Slices view — model_osnova → integrations roll-up."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductSliceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_osnova_id: int
    model_name: str
    integrations_count: int = 0
    integrations_done: int = 0
    last_publish_date: date | None = None
    total_spent: Decimal = Decimal("0")
    total_revenue_fact: Decimal = Decimal("0")


class ProductDetailIntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    integration_id: int
    blogger_handle: str
    publish_date: date
    stage: str
    total_cost: Decimal
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None


class ProductDetailOut(ProductSliceOut):
    integrations: list[ProductDetailIntegrationOut] = Field(default_factory=list)
