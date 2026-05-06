"""Pydantic schemas mirroring crm.bloggers + drawer payload."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


BloggerStatus = Literal["active", "in_progress", "new", "paused"]


class BloggerOut(BaseModel):
    """List-row payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_handle: str
    real_name: Optional[str] = None
    status: BloggerStatus
    default_marketer_id: Optional[int] = None
    price_story_default: Optional[Decimal] = None
    price_reels_default: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BloggerChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    handle: str
    url: Optional[str] = None


class BloggerDetailOut(BloggerOut):
    """Drawer payload — includes channels, recent integrations, totals."""
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    channels: list[BloggerChannelOut] = Field(default_factory=list)
    integrations_count: int = 0
    integrations_done: int = 0
    last_integration_at: Optional[datetime] = None
    total_spent: Decimal = Decimal("0")
    avg_cpm_fact: Optional[Decimal] = None
    contact_tg: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    geo_country: Optional[list[str]] = None


class BloggerCreate(BaseModel):
    display_handle: str = Field(min_length=1, max_length=200)
    real_name: Optional[str] = None
    status: BloggerStatus = "new"
    default_marketer_id: Optional[int] = None
    price_story_default: Optional[Decimal] = None
    price_reels_default: Optional[Decimal] = None
    contact_tg: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


class BloggerUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    display_handle: Optional[str] = Field(default=None, min_length=1, max_length=200)
    real_name: Optional[str] = None
    status: Optional[BloggerStatus] = None
    default_marketer_id: Optional[int] = None
    price_story_default: Optional[Decimal] = None
    price_reels_default: Optional[Decimal] = None
    contact_tg: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


class ChannelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    handle: str
    url: Optional[str] = None


class BloggerSummaryOut(BaseModel):
    """Enriched blogger row for table view — includes channels + aggregate metrics."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_handle: str
    real_name: Optional[str] = None
    status: str
    default_marketer_id: Optional[int] = None
    price_story_default: Optional[str] = None
    price_reels_default: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    channels: list[ChannelBrief] = Field(default_factory=list)
    integrations_count: int = 0
    integrations_done: int = 0
    last_integration_at: Optional[str] = None
    total_spent: str = "0"
    avg_cpm_fact: Optional[str] = None


class BloggerSummaryPage(BaseModel):
    items: list[BloggerSummaryOut]
    total: int
