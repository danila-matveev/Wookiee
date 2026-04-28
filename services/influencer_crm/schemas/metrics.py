from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MetricsSnapshotIn(BaseModel):
    fact_views: int | None = None
    fact_clicks: int | None = None
    fact_ctr: Decimal | None = None
    fact_cpm: Decimal | None = None
    fact_carts: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    # `note` accepted for API compatibility; stored as `source` in DB (defaults to 'manual')
    note: str | None = None


class MetricsSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    integration_id: int
    captured_at: datetime
    fact_views: int | None = None
    fact_clicks: int | None = None
    fact_ctr: Decimal | None = None
    fact_cpm: Decimal | None = None
    fact_carts: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    # DB has `source` column (NOT NULL, default 'manual'); exposed as `note` for API compat.
    note: str | None = None
