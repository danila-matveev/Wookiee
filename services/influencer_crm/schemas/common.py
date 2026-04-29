"""Shared pydantic models — Cursor, Page wrapper, simple FK refs."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class MarketerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class TimestampMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime
