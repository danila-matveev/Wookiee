from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class SubstituteArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: Optional[int] = None
    purpose: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class PromoCodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    artikul_id: Optional[int] = None
    discount_percent: Optional[Decimal] = None
    status: Literal["active", "paused", "expired"]
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
