from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SubstituteArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: int | None = None
    purpose: str | None = None
    status: str
    created_at: datetime | None = None


class PromoCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: int | None = None
    discount_percent: Decimal | None = None
    status: Literal["active", "paused", "expired"]
    valid_from: date | None = None
    valid_until: date | None = None
