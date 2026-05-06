from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# API-level status values (UI-friendly). DB stores different values — mapping
# lives in shared/data_layer/influencer_crm/briefs.py.
BriefStatus = Literal["draft", "on_review", "signed", "completed"]


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: Optional[str] = None
    status: BriefStatus = "draft"
    current_version: int = 1
    current_version_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BriefDetailOut(BriefOut):
    content_md: str = ""
    versions: list[BriefVersionOut] = []


class BriefVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brief_id: int
    version: int
    content_md: str
    created_at: Optional[datetime] = None


class BriefsPage(BaseModel):
    items: list[BriefOut]
    next_cursor: Optional[str] = None


class BriefCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_md: str


class BriefVersionCreate(BaseModel):
    content_md: str


class BriefUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    status: Optional[BriefStatus] = None


# Rebuild forward refs so BriefDetailOut.versions resolves BriefVersionOut
BriefDetailOut.model_rebuild()
