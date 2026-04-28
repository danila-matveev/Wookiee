from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    current_version_id: int | None = None
    created_at: datetime | None = None


class BriefVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brief_id: int
    version: int
    content_md: str
    created_at: datetime | None = None


class BriefCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_md: str


class BriefVersionCreate(BaseModel):
    content_md: str
