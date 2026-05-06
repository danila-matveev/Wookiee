from __future__ import annotations
from typing import Optional

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MetricsSnapshotIn(BaseModel):
    fact_views: Optional[int] = None
    fact_clicks: Optional[int] = None
    fact_ctr: Optional[Decimal] = None
    fact_cpm: Optional[Decimal] = None
    fact_carts: Optional[int] = None
    fact_orders: Optional[int] = None
    fact_revenue: Optional[Decimal] = None
    # `note` accepted for API compatibility; stored as `source` in DB (defaults to 'manual')
    note: Optional[str] = None


class MetricsSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    integration_id: int
    captured_at: datetime
    fact_views: Optional[int] = None
    fact_clicks: Optional[int] = None
    fact_ctr: Optional[Decimal] = None
    fact_cpm: Optional[Decimal] = None
    fact_carts: Optional[int] = None
    fact_orders: Optional[int] = None
    fact_revenue: Optional[Decimal] = None
    # DB has `source` column (NOT NULL, default 'manual'); exposed as `note` for API compat.
    note: Optional[str] = None
