"""Pydantic schemas mirroring crm.bloggers + drawer payload."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BloggerStatus = Literal["active", "in_progress", "new", "paused"]


class BloggerOut(BaseModel):
    """List-row payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_handle: str
    real_name: str | None = None
    status: BloggerStatus
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BloggerChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    handle: str
    url: str | None = None


class BloggerDetailOut(BloggerOut):
    """Drawer payload — includes channels, recent integrations, totals."""
    channels: list[BloggerChannelOut] = Field(default_factory=list)
    integrations_count: int = 0
    integrations_done: int = 0
    last_integration_at: datetime | None = None
    total_spent: Decimal = Decimal("0")
    avg_cpm_fact: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
    geo_country: list[str] | None = None


class BloggerCreate(BaseModel):
    display_handle: str = Field(min_length=1, max_length=200)
    real_name: str | None = None
    status: BloggerStatus = "new"
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class BloggerUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    display_handle: str | None = Field(default=None, min_length=1, max_length=200)
    real_name: str | None = None
    status: BloggerStatus | None = None
    default_marketer_id: int | None = None
    price_story_default: Decimal | None = None
    price_reels_default: Decimal | None = None
    contact_tg: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None
