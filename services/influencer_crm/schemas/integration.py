"""Pydantic schemas for crm.integrations + drawer payload + Kanban transitions."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Stages from migration 008 schema (10 columns Kanban)
Stage = Literal[
    "lead", "negotiation", "agreed", "content_received",
    "content_approved", "scheduled", "published", "paid", "done", "rejected",
]
Outcome = Literal["delivered", "cancelled", "no_show", "failed_compliance"]
Channel = Literal["instagram", "telegram", "tiktok", "youtube", "vk", "rutube"]
AdFormat = Literal["story", "short_video", "long_video", "long_post", "image_post", "integration", "live_stream"]
Marketplace = Literal["wb", "ozon", "both"]


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    blogger_id: int
    marketer_id: int
    brief_id: int | None = None
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage
    outcome: Outcome | None = None
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    total_cost: Decimal = Decimal("0")
    erid: str | None = None
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class IntegrationSubstituteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    substitute_article_id: int
    code: str
    artikul_id: int | None
    display_order: int
    tracking_url: str | None = None


class IntegrationPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_url: str | None
    posted_at: datetime | None
    fact_views: int | None
    fact_clicks: int | None


class IntegrationDetailOut(IntegrationOut):
    blogger_handle: str
    marketer_name: str
    substitutes: list[IntegrationSubstituteOut] = Field(default_factory=list)
    posts: list[IntegrationPostOut] = Field(default_factory=list)
    contract_url: str | None = None
    post_url: str | None = None
    tz_url: str | None = None
    post_content: str | None = None
    notes: str | None = None
    has_marking: bool | None = None
    has_contract: bool | None = None


class IntegrationCreate(BaseModel):
    blogger_id: int
    marketer_id: int
    publish_date: date
    channel: Channel
    ad_format: AdFormat
    marketplace: Marketplace
    stage: Stage = "lead"
    is_barter: bool = False
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None


class IntegrationUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    blogger_id: int | None = None
    marketer_id: int | None = None
    publish_date: date | None = None
    channel: Channel | None = None
    ad_format: AdFormat | None = None
    marketplace: Marketplace | None = None
    stage: Stage | None = None
    outcome: Outcome | None = None
    is_barter: bool | None = None
    cost_placement: Decimal | None = None
    cost_delivery: Decimal | None = None
    cost_goods: Decimal | None = None
    erid: str | None = None
    notes: str | None = None
    fact_views: int | None = None
    fact_orders: int | None = None
    fact_revenue: Decimal | None = None


class StageTransitionIn(BaseModel):
    """POST /integrations/{id}/stage body — Kanban drag-drop."""
    target_stage: Stage
    note: str | None = None
