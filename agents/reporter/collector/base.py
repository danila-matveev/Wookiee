# agents/reporter/collector/base.py
"""Base collector and CollectedData model."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from agents.reporter.types import ReportScope

logger = logging.getLogger(__name__)


class TopLevelMetrics(BaseModel):
    revenue_before_spp: float = 0.0
    revenue_after_spp: float = 0.0
    orders_count: int = 0
    orders_rub: float = 0.0
    sales_count: int = 0
    margin: float = 0.0
    margin_pct: float = 0.0
    adv_internal: float = 0.0
    adv_external: float = 0.0
    adv_total: float = 0.0
    drr_pct: float = 0.0
    spp_pct: float = 0.0
    logistics: float = 0.0
    storage: float = 0.0
    cost_of_goods: float = 0.0
    commission: float = 0.0
    buyout_pct: float = 0.0


class MarketplaceMetrics(BaseModel):
    marketplace: str  # "wb" or "ozon"
    metrics: TopLevelMetrics
    prev_metrics: TopLevelMetrics


class ModelMetrics(BaseModel):
    model: str
    rank: int
    metrics: TopLevelMetrics
    prev_metrics: TopLevelMetrics


class TrendData(BaseModel):
    daily_series: list[dict] = Field(default_factory=list)
    weekly_breakdown: list[dict] = Field(default_factory=list)


class ContextData(BaseModel):
    stock_by_model: dict[str, float] = Field(default_factory=dict)
    turnover_by_model: dict[str, dict] = Field(default_factory=dict)
    price_changes: list[dict] = Field(default_factory=list)
    ad_campaigns: list[dict] = Field(default_factory=list)
    ad_breakdown: dict = Field(default_factory=dict)


class CollectedData(BaseModel):
    scope: dict
    collected_at: str
    current: TopLevelMetrics
    previous: TopLevelMetrics
    marketplace_breakdown: list[MarketplaceMetrics] = Field(default_factory=list)
    model_breakdown: list[ModelMetrics] = Field(default_factory=list)
    trends: TrendData = Field(default_factory=TrendData)
    context: ContextData = Field(default_factory=ContextData)
    warnings: list[str] = Field(default_factory=list)


class BaseCollector(ABC):
    """Abstract base for data collectors. Subclasses implement _collect_sync()."""

    @abstractmethod
    def _collect_sync(self, scope: ReportScope) -> CollectedData:
        """Collect data synchronously (uses psycopg2 from shared/data_layer)."""
        ...

    async def collect(self, scope: ReportScope) -> CollectedData:
        """Async wrapper — runs sync collection in thread pool."""
        logger.info("Collecting data for %s", scope.report_type.value)
        data = await asyncio.to_thread(self._collect_sync, scope)
        logger.info(
            "Collected: %d models, %d warnings",
            len(data.model_breakdown),
            len(data.warnings),
        )
        return data
